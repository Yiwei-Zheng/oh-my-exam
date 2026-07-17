from __future__ import annotations

import sqlite3


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = OFF;

        DROP TABLE IF EXISTS question_fts;
        DROP TABLE IF EXISTS question_texts;
        DROP TABLE IF EXISTS crop_regions;
        DROP TABLE IF EXISTS questions;
        DROP TABLE IF EXISTS papers;
        DROP TABLE IF EXISTS database_info;

        DROP TABLE IF EXISTS paper_documents;
        DROP TABLE IF EXISTS metadata_fields;
        DROP TABLE IF EXISTS question_sources;
        DROP TABLE IF EXISTS schema_migrations;

        PRAGMA foreign_keys = ON;

        CREATE TABLE database_info (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            qualification TEXT NOT NULL,
            exam_board TEXT NOT NULL,
            course_code TEXT NOT NULL,
            course_display_name TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE papers (
            id INTEGER PRIMARY KEY,
            qp_stem TEXT NOT NULL UNIQUE,
            ms_stem TEXT NOT NULL,
            qp_url TEXT NOT NULL DEFAULT '',
            ms_url TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE questions (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            local_question_key TEXT NOT NULL,
            question_number TEXT NOT NULL DEFAULT '',
            UNIQUE (paper_id, local_question_key)
        );

        CREATE TABLE crop_regions (
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            source_type INTEGER NOT NULL CHECK (source_type IN (0, 1)),
            region_order INTEGER NOT NULL,
            page_index INTEGER NOT NULL,
            x0 REAL NOT NULL,
            y0 REAL NOT NULL,
            x1 REAL NOT NULL,
            y1 REAL NOT NULL,
            render_dpi INTEGER,
            join_gap_px INTEGER NOT NULL DEFAULT 0,
            post_left INTEGER,
            post_top INTEGER,
            post_right INTEGER,
            post_bottom INTEGER,
            PRIMARY KEY (question_id, source_type, region_order)
        );

        CREATE TABLE question_texts (
            question_id INTEGER PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE,
            content TEXT NOT NULL
        );

        CREATE INDEX idx_questions_local_key ON questions(local_question_key);
        CREATE INDEX idx_crop_regions_question ON crop_regions(question_id, source_type, region_order);
        """
    )
    conn.commit()
