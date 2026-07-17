from __future__ import annotations

from exam_packer.gui import _bind_dropdown_handler


class _CurrentDropdown:
    on_select: object | None = None


class _LegacyDropdown:
    on_change: object | None = None


def test_bind_dropdown_handler_uses_current_flet_event() -> None:
    dropdown = _CurrentDropdown()
    handler = object()

    _bind_dropdown_handler(dropdown, handler)

    assert dropdown.on_select is handler


def test_bind_dropdown_handler_supports_legacy_flet_event() -> None:
    dropdown = _LegacyDropdown()
    handler = object()

    _bind_dropdown_handler(dropdown, handler)

    assert dropdown.on_change is handler
