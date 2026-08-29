from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from .catalog import CatalogNotFoundError, GlobalCatalog
from .config import Settings
from .paper_store import FileSystemPaperStore, PaperNotFoundError
from .question_document import QuestionDocumentError, crop_question_pdf


class PlaceholderRequest(BaseModel):
    input: str = ""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    catalog = GlobalCatalog(settings.database_path)
    papers = FileSystemPaperStore(settings.paper_root)
    app = FastAPI(title="Oh-My-Exam API", version="0.1.0")

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST"],
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
            "authentication": {"status": "placeholder", "target": "oidc"},
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

    @app.get("/api/v1/me")
    def current_user() -> JSONResponse:
        return _placeholder("authentication", "Configure an OIDC provider and PostgreSQL user tables.")

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
