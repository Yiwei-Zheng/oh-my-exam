from __future__ import annotations


CIE_A_LEVEL_ENGLISH_SUBJECT_NAMES = {
    "9231": "Further Mathematics",
    "9618": "Computer Science",
    "9701": "Chemistry",
    "9702": "Physics",
    "9708": "Economics",
    "9709": "Mathematics",
}


def english_subject_name(exam_board: str, qualification: str, subject_code: str, fallback: str) -> str:
    if exam_board == "cie" and qualification == "a_level":
        return CIE_A_LEVEL_ENGLISH_SUBJECT_NAMES.get(str(subject_code), fallback)
    return fallback

