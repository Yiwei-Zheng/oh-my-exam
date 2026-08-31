from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QuestionUpdateProbeRequest(BaseModel):
    subjects: list[str] = Field(min_length=1, max_length=20)


class QuestionUpdateStartRequest(BaseModel):
    subjects: list[str] = Field(min_length=1, max_length=20)
    concurrency: int = Field(default=4, ge=1, le=12)
    stage: Literal["all", "download", "split", "inventory", "search"] = "all"
    mode: Literal["update", "overwrite"] = "update"
