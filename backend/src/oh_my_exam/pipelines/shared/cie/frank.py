from __future__ import annotations


FRANK_CIE_REDIR_BASE = "https://cie.fraft.org/obj/Common/Fetch/redir"


def build_frank_cie_url_from_stem(stem: str) -> str:
    clean_stem = stem.strip()
    if not clean_stem:
        raise ValueError("CIE paper stem must not be empty")
    return f"{FRANK_CIE_REDIR_BASE}/{clean_stem}.pdf"
