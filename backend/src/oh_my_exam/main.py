from __future__ import annotations

from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from .ai_usage import AiUsageStore
from .catalog import CatalogNotFoundError, GlobalCatalog
from .config import Settings
from .identity import (
    DuplicateUserError,
    IdentityStore,
    InvalidInvitationError,
    InvalidUserError,
    SESSION_COOKIE,
    User,
)
from .login_security import LoginRateLimited, LoginRateLimiter
from .paper_store import FileSystemPaperStore, PaperNotFoundError
from .question_document import QuestionDocumentError, crop_question_pdf
from .update_jobs import UpdateJobManager


class PlaceholderRequest(BaseModel):
    input: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=15, max_length=1024)
    role: Literal["student", "teacher", "admin"]


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=15, max_length=1024)
    invitation_code: str = Field(min_length=8, max_length=64)


class CreateInvitationRequest(BaseModel):
    role: Literal["student", "teacher", "admin"]
    max_uses: int = Field(default=1, ge=1, le=100)
    expires_in_days: int = Field(default=7, ge=1, le=365)


class AnswerRevisionRequest(BaseModel):
    raw_text: str
    markdown: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    catalog = GlobalCatalog(settings.database_path)
    papers = FileSystemPaperStore(settings.paper_root)
    app_database_path = settings.app_database_path or (
        settings.project_root / "backend" / "data" / "application.sqlite3"
    )
    identity = IdentityStore(app_database_path, settings.jwt_secret)
    identity.bootstrap_admin(settings.bootstrap_admin_email, settings.bootstrap_admin_password)
    login_limiter = LoginRateLimiter(settings.login_rate_limit_storage_uri)
    updates = UpdateJobManager(app_database_path, settings.question_update_command)
    ai_usage = AiUsageStore(app_database_path)
    app = FastAPI(title="Oh-My-Exam API", version="0.1.0")

    def current_user(request: Request) -> User:
        user = identity.user_from_session(request.cookies.get(SESSION_COOKIE))
        if user is None:
            raise HTTPException(status_code=401, detail="authentication_required")
        return user

    def admin_user(user: User = Depends(current_user)) -> User:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="admin_required")
        return user

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/capabilities")
    def capabilities() -> dict[str, object]:
        exam_ids = {exam["id"] for exam in catalog.list_exams()}
        return {
            "catalog": {"status": "ready", "source": "global_sqlite"},
            "paper_storage": {
                "status": "ready",
                "backend": "local_filesystem",
                "access": "development_only_until_authentication_is_ready",
            },
            "authentication": {"status": "ready", "method": "email_password"},
            "question_update": {"status": "ready" if updates.configured else "needs_configuration"},
            "primary_database": {"status": "placeholder", "target": "postgresql"},
            "ai_tutor": {"status": "placeholder", "targets": ["ragflow", "deepseek"]},
            "math_harness": {"status": "placeholder", "targets": ["sympy", "matplotlib"]},
            "tmua_data": {
                "status": "ready" if any(exam_id.endswith(":tmua") for exam_id in exam_ids) else "missing"
            },
        }

    @app.get("/api/v1/exams")
    def list_exams() -> list[dict[str, object]]:
        return catalog.list_exams()

    @app.get("/api/v1/questions/search")
    def search_questions(
        query: str = Query("", max_length=500),
        exam_id: str | None = None,
        topic: list[str] = Query(default=[]),
        limit: int = Query(50, ge=1, le=200),
    ) -> list[dict[str, object]]:
        try:
            return catalog.search_questions(
                query, exam_id=exam_id, topic_codes=tuple(topic), limit=limit
            )
        except CatalogNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/topics")
    def list_topics(exam_id: str | None = None) -> list[dict[str, object]]:
        try:
            return catalog.list_topics(exam_id)
        except CatalogNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/exams/{exam_id}/questions")
    def list_questions(
        exam_id: str,
        query: str = "",
        limit: int = Query(50, ge=1, le=200),
    ) -> list[dict[str, object]]:
        try:
            return catalog.list_questions(exam_id, query, limit)
        except CatalogNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/exams/{exam_id}/questions/{question_id}")
    def get_question(exam_id: str, question_id: int) -> dict[str, object]:
        try:
            return catalog.get_question(exam_id, question_id)
        except CatalogNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/exams/{exam_id}/questions/{question_id}/similar")
    def list_similar_questions(
        exam_id: str,
        question_id: int,
        limit: int = Query(10, ge=1, le=50),
    ) -> list[dict[str, object]]:
        try:
            return catalog.list_similar_questions(exam_id, question_id, limit)
        except CatalogNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/exams/{exam_id}/questions/{question_id}/{kind}.pdf")
    def get_question_pdf(exam_id: str, question_id: int, kind: str) -> Response:
        try:
            document = catalog.get_question_document(exam_id, question_id, kind)
            source_path = papers.find_by_storage_key(document.storage_key)
            content = crop_question_pdf(source_path, document.crop_regions)
        except (CatalogNotFoundError, PaperNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuestionDocumentError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{document.filename}"',
                "Cache-Control": "private, max-age=3600",
            },
        )

    @app.get("/api/v1/exams/{exam_id}/papers/{paper_id}/{kind}")
    def get_paper(exam_id: str, paper_id: int, kind: str) -> FileResponse:
        try:
            storage_key = catalog.get_paper_storage_key(exam_id, paper_id, kind)
            path = papers.find_by_storage_key(storage_key)
        except (CatalogNotFoundError, PaperNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @app.post("/api/v1/auth/login")
    def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, object]:
        client_ip = "unknown" if request.client is None else request.client.host
        try:
            login_limiter.check(payload.email, client_ip)
        except LoginRateLimited as exc:
            raise HTTPException(
                status_code=429,
                detail="too_many_login_attempts",
                headers={"Retry-After": str(exc.retry_after)},
            ) from exc
        user = identity.authenticate(payload.email, payload.password)
        if user is None:
            raise HTTPException(status_code=401, detail="invalid_credentials")
        login_limiter.reset_account(payload.email)
        response.set_cookie(
            SESSION_COOKIE,
            identity.issue_session(user),
            max_age=12 * 60 * 60,
            httponly=True,
            secure=settings.secure_cookies,
            samesite="lax",
            path="/",
        )
        return {"user": user.as_dict()}

    @app.post("/api/v1/auth/logout", status_code=204)
    def logout(response: Response) -> None:
        response.delete_cookie(SESSION_COOKIE, path="/", samesite="lax")

    @app.post("/api/v1/auth/register", status_code=201)
    def register(payload: RegisterRequest) -> dict[str, object]:
        try:
            user = identity.register_with_invitation(
                payload.email, payload.password, payload.invitation_code
            )
        except DuplicateUserError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (InvalidInvitationError, InvalidUserError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"user": user.as_dict()}

    @app.get("/api/v1/me")
    def me(user: User = Depends(current_user)) -> dict[str, object]:
        return {"user": user.as_dict()}

    @app.get("/api/v1/admin/statistics")
    def admin_statistics(_: User = Depends(admin_user)) -> dict[str, object]:
        return identity.dashboard_statistics()

    @app.get("/api/v1/admin/assets")
    def admin_assets(_: User = Depends(admin_user)) -> dict[str, object]:
        try:
            return catalog.asset_inventory()
        except CatalogNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/admin/ai-usage")
    def admin_ai_usage(
        month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
        _: User = Depends(admin_user),
    ) -> dict[str, object]:
        try:
            return ai_usage.monthly_bill(month)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/admin/users")
    def admin_users(_: User = Depends(admin_user)) -> dict[str, object]:
        return {"users": [user.as_dict() for user in identity.list_users()]}

    @app.post("/api/v1/admin/users", status_code=201)
    def admin_create_user(
        payload: CreateUserRequest,
        _: User = Depends(admin_user),
    ) -> dict[str, object]:
        try:
            user = identity.create_user(payload.email, payload.password, payload.role)
        except DuplicateUserError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InvalidUserError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"user": user.as_dict()}

    @app.get("/api/v1/admin/invitations")
    def admin_invitations(_: User = Depends(admin_user)) -> dict[str, object]:
        return {"invitations": [item.as_dict() for item in identity.list_invitations()]}

    @app.post("/api/v1/admin/invitations", status_code=201)
    def admin_create_invitation(
        payload: CreateInvitationRequest,
        user: User = Depends(admin_user),
    ) -> dict[str, object]:
        try:
            invitation, code = identity.create_invitation(
                user.id, payload.role, payload.max_uses, payload.expires_in_days
            )
        except InvalidInvitationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"invitation": invitation.as_dict(), "code": code}

    @app.delete("/api/v1/admin/invitations/{invitation_id}")
    def admin_revoke_invitation(
        invitation_id: int,
        _: User = Depends(admin_user),
    ) -> dict[str, object]:
        invitation = identity.revoke_invitation(invitation_id)
        if invitation is None:
            raise HTTPException(status_code=404, detail="invitation_not_found")
        return {"invitation": invitation.as_dict()}

    @app.get("/api/v1/admin/question-tree")
    def admin_question_tree(_: User = Depends(admin_user)) -> list[dict[str, object]]:
        try:
            return catalog.question_tree()
        except CatalogNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/admin/papers/{paper_id}/questions")
    def admin_paper_questions(paper_id: int, _: User = Depends(admin_user)) -> list[dict[str, object]]:
        try:
            return catalog.list_paper_questions(paper_id)
        except CatalogNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/v1/admin/questions/{question_id}/answer-text")
    def admin_save_answer_text(
        question_id: int,
        payload: AnswerRevisionRequest,
        _: User = Depends(admin_user),
    ) -> dict[str, object]:
        try:
            return {"answer_structured": catalog.save_answer_revision(
                question_id, payload.raw_text, payload.markdown
            )}
        except CatalogNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/admin/question-update")
    def latest_question_update(_: User = Depends(admin_user)) -> dict[str, object]:
        return {"configured": updates.configured, "job": updates.latest()}

    @app.post("/api/v1/admin/question-update", status_code=202)
    def start_question_update(user: User = Depends(admin_user)) -> dict[str, object]:
        try:
            return {"job": updates.start(user.id)}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/ai/answer")
    def ai_answer(_: PlaceholderRequest) -> JSONResponse:
        return _placeholder("ai_tutor", "Configure RAGFlow retrieval and a DeepSeek API key.")

    @app.post("/api/v1/math/evaluate")
    def math_evaluate(_: PlaceholderRequest) -> JSONResponse:
        return _placeholder("math_harness", "Implement the restricted expression grammar and sandbox runner.")

    return app


def _placeholder(capability: str, next_step: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"error": "capability_not_implemented", "capability": capability, "next_step": next_step},
    )


app = create_app()
