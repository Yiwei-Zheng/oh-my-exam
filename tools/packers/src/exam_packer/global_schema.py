from __future__ import annotations

import sqlite3


SCHEMA_VERSION = 1


def migrate_global_catalog(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS exam_boards (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS qualifications (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS exam_programs (
            id INTEGER PRIMARY KEY,
            exam_board_id INTEGER NOT NULL REFERENCES exam_boards(id),
            qualification_id INTEGER NOT NULL REFERENCES qualifications(id),
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE (exam_board_id, qualification_id, code)
        );

        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY,
            exam_program_id INTEGER NOT NULL REFERENCES exam_programs(id),
            stable_key TEXT NOT NULL UNIQUE,
            source_key TEXT NOT NULL,
            year INTEGER,
            session TEXT,
            component TEXT,
            variant TEXT,
            UNIQUE (exam_program_id, source_key)
        );

        CREATE TABLE IF NOT EXISTS paper_documents (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (
                role IN ('question_paper', 'mark_scheme', 'answer_key', 'worked_answer', 'formula_booklet')
            ),
            storage_key TEXT NOT NULL UNIQUE,
            original_filename TEXT NOT NULL,
            mime_type TEXT NOT NULL DEFAULT 'application/pdf',
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            UNIQUE (paper_id, role, storage_key)
        );

        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            stable_key TEXT NOT NULL UNIQUE,
            local_key TEXT NOT NULL,
            question_number TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL,
            question_type TEXT NOT NULL DEFAULT 'unknown',
            max_marks INTEGER CHECK (max_marks IS NULL OR max_marks >= 0),
            UNIQUE (paper_id, local_key)
        );

        CREATE TABLE IF NOT EXISTS question_relations (
            parent_question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            child_question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            relation_type TEXT NOT NULL CHECK (relation_type IN ('part', 'shared_stem')),
            position INTEGER NOT NULL,
            PRIMARY KEY (parent_question_id, child_question_id),
            CHECK (parent_question_id != child_question_id)
        );

        CREATE TABLE IF NOT EXISTS question_texts (
            id INTEGER PRIMARY KEY,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            text_kind TEXT NOT NULL CHECK (text_kind IN ('official', 'search', 'ocr', 'normalized')),
            language TEXT NOT NULL DEFAULT 'en',
            content TEXT NOT NULL,
            UNIQUE (question_id, text_kind, language)
        );

        CREATE TABLE IF NOT EXISTS question_regions (
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            document_id INTEGER NOT NULL REFERENCES paper_documents(id) ON DELETE CASCADE,
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
            PRIMARY KEY (question_id, document_id, region_order),
            CHECK (x1 > x0 AND y1 > y0)
        );

        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            source_document_id INTEGER REFERENCES paper_documents(id) ON DELETE SET NULL,
            answer_kind TEXT NOT NULL CHECK (
                answer_kind IN ('final_answer', 'mark_scheme', 'answer_key', 'worked_solution', 'reference_solution', 'ai_solution')
            ),
            authority TEXT NOT NULL CHECK (authority IN ('official', 'curated', 'generated')),
            status TEXT NOT NULL CHECK (status IN ('source_only', 'draft', 'reviewed', 'published', 'rejected')),
            UNIQUE (question_id, answer_kind, source_document_id)
        );

        CREATE TABLE IF NOT EXISTS answer_regions (
            answer_id INTEGER NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
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
            PRIMARY KEY (answer_id, region_order),
            CHECK (x1 > x0 AND y1 > y0)
        );

        CREATE TABLE IF NOT EXISTS answer_versions (
            id INTEGER PRIMARY KEY,
            answer_id INTEGER NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
            version INTEGER NOT NULL CHECK (version > 0),
            language TEXT NOT NULL DEFAULT 'en',
            markdown TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('draft', 'reviewed', 'published', 'rejected')),
            UNIQUE (answer_id, version, language)
        );

        CREATE TABLE IF NOT EXISTS marking_points (
            id INTEGER PRIMARY KEY,
            answer_version_id INTEGER NOT NULL REFERENCES answer_versions(id) ON DELETE CASCADE,
            sequence_no INTEGER NOT NULL,
            mark_code TEXT,
            marks INTEGER NOT NULL CHECK (marks >= 0),
            criterion_markdown TEXT NOT NULL,
            dependency_note TEXT,
            UNIQUE (answer_version_id, sequence_no)
        );

        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL CHECK (kind IN ('concept', 'skill', 'method', 'object', 'format')),
            canonical_code TEXT NOT NULL UNIQUE,
            parent_feature_id INTEGER REFERENCES features(id)
        );

        CREATE TABLE IF NOT EXISTS feature_labels (
            feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
            language TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (feature_id, language)
        );

        CREATE TABLE IF NOT EXISTS question_features (
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'secondary' CHECK (role IN ('primary', 'secondary', 'prerequisite')),
            weight REAL NOT NULL DEFAULT 1.0 CHECK (weight >= 0.0 AND weight <= 1.0),
            PRIMARY KEY (question_id, feature_id)
        );

        CREATE TABLE IF NOT EXISTS syllabuses (
            id INTEGER PRIMARY KEY,
            exam_program_id INTEGER NOT NULL REFERENCES exam_programs(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            effective_from_year INTEGER,
            effective_to_year INTEGER,
            storage_key TEXT,
            UNIQUE (exam_program_id, name)
        );

        CREATE TABLE IF NOT EXISTS syllabus_topics (
            id INTEGER PRIMARY KEY,
            syllabus_id INTEGER NOT NULL REFERENCES syllabuses(id) ON DELETE CASCADE,
            parent_topic_id INTEGER REFERENCES syllabus_topics(id),
            code TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            UNIQUE (syllabus_id, code)
        );

        CREATE TABLE IF NOT EXISTS syllabus_topic_features (
            syllabus_topic_id INTEGER NOT NULL REFERENCES syllabus_topics(id) ON DELETE CASCADE,
            feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
            PRIMARY KEY (syllabus_topic_id, feature_id)
        );

        CREATE TABLE IF NOT EXISTS embedding_models (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            dimensions INTEGER NOT NULL CHECK (dimensions > 0),
            UNIQUE (name, version)
        );

        CREATE TABLE IF NOT EXISTS question_embeddings (
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            embedding_model_id INTEGER NOT NULL REFERENCES embedding_models(id),
            view_kind TEXT NOT NULL CHECK (view_kind IN ('normalized_text', 'mathematical_structure', 'solution_method')),
            embedding BLOB NOT NULL,
            PRIMARY KEY (question_id, embedding_model_id, view_kind)
        );

        CREATE TABLE IF NOT EXISTS similarity_algorithms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            configuration_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE (name, version)
        );

        CREATE TABLE IF NOT EXISTS question_similarities (
            source_question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            target_question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            algorithm_id INTEGER NOT NULL REFERENCES similarity_algorithms(id) ON DELETE CASCADE,
            rank INTEGER NOT NULL CHECK (rank > 0),
            score REAL NOT NULL,
            PRIMARY KEY (source_question_id, target_question_id, algorithm_id),
            UNIQUE (source_question_id, algorithm_id, rank),
            CHECK (source_question_id != target_question_id)
        );

        CREATE INDEX IF NOT EXISTS idx_papers_program ON papers(exam_program_id, year, session, component);
        CREATE INDEX IF NOT EXISTS idx_questions_paper ON questions(paper_id, sort_order);
        CREATE INDEX IF NOT EXISTS idx_question_texts_search ON question_texts(text_kind, language);
        CREATE INDEX IF NOT EXISTS idx_question_regions_document ON question_regions(document_id, question_id);
        CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id, answer_kind);
        CREATE INDEX IF NOT EXISTS idx_question_features_feature ON question_features(feature_id, question_id);
        CREATE INDEX IF NOT EXISTS idx_similarities_source ON question_similarities(source_question_id, algorithm_id, rank);
        """
    )
    conn.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()
