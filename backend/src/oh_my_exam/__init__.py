"""Hosted Oh-My-Exam API."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

    from .config import Settings


def create_app(settings: "Settings | None" = None) -> "FastAPI":
    from .main import create_app as create

    return create(settings)

__all__ = ["create_app"]
