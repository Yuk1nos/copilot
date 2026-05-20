import sqlite3
import json
from typing import Optional
from src.models import Document


class Database:
    def __init__(self, db_path: str = "copilot.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def initialize(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                char_count INTEGER DEFAULT 0,
                chunk_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'uploaded',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                token_count INTEGER DEFAULT 0,
                embedding_id TEXT,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                answer TEXT,
                referenced_chunk_ids TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
        """)
        self._conn.commit()

    def insert_document(self, doc: Document):
        self._conn.execute(
            "INSERT INTO documents (id, filename, mime_type, char_count, chunk_count, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [doc.id, doc.filename, doc.mime_type, doc.char_count, doc.chunk_count, doc.status.value, doc.created_at],
        )
        self._conn.commit()

    def get_document(self, doc_id: str) -> Optional[dict]:
        row = self._conn.execute("SELECT * FROM documents WHERE id = ?", [doc_id]).fetchone()
        return dict(row) if row else None

    def list_documents(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def update_document(self, doc_id: str, **kwargs):
        allowed = {"status", "char_count", "chunk_count", "mime_type"}
        filtered = {k: v for k, v in kwargs.items() if k in allowed}
        if not filtered:
            return
        set_clause = ", ".join(f"{k} = ?" for k in filtered)
        values = list(filtered.values()) + [doc_id]
        self._conn.execute(f"UPDATE documents SET {set_clause} WHERE id = ?", values)
        self._conn.commit()

    def insert_chunk(self, chunk_id: str, document_id: str, chunk_index: int, content: str, token_count: int, embedding_id: str):
        self._conn.execute(
            "INSERT INTO chunks (id, document_id, chunk_index, content, token_count, embedding_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [chunk_id, document_id, chunk_index, content, token_count, embedding_id],
        )
        self._conn.commit()

    def get_chunks_by_document(self, document_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index", [document_id]
        ).fetchall()
        return [dict(r) for r in rows]

    def insert_session(self, query: str, answer: str, referenced_chunk_ids: list[str]):
        self._conn.execute(
            "INSERT INTO sessions (query, answer, referenced_chunk_ids) VALUES (?, ?, ?)",
            [query, answer, json.dumps(referenced_chunk_ids, ensure_ascii=False)],
        )
        self._conn.commit()

    def list_sessions(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, doc_id: str):
        self._conn.execute("DELETE FROM chunks WHERE document_id = ?", [doc_id])
        self._conn.execute("DELETE FROM documents WHERE id = ?", [doc_id])
        self._conn.commit()
