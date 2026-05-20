import pytest
from src.database import Database
from src.models import Document


@pytest.fixture
def db():
    d = Database(":memory:")
    d.initialize()
    yield d


class TestDatabase:
    def test_initialize_creates_tables(self, db):
        tables = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [t[0] for t in tables]
        assert "documents" in names
        assert "chunks" in names
        assert "sessions" in names

    def test_insert_and_get_document(self, db):
        doc = Document(filename="test.pdf", mime_type="application/pdf")
        db.insert_document(doc)
        result = db.get_document(doc.id)
        assert result["filename"] == "test.pdf"
        assert result["status"] == "uploaded"

    def test_list_documents(self, db):
        db.insert_document(Document(filename="a.pdf", mime_type="application/pdf"))
        db.insert_document(Document(filename="b.txt", mime_type="text/plain"))
        docs = db.list_documents()
        assert len(docs) == 2

    def test_update_document_status(self, db):
        doc = Document(filename="x.pdf", mime_type="application/pdf")
        db.insert_document(doc)
        db.update_document(doc.id, status="indexed", char_count=100, chunk_count=5)
        result = db.get_document(doc.id)
        assert result["status"] == "indexed"
        assert result["char_count"] == 100
        assert result["chunk_count"] == 5

    def test_insert_and_get_chunks(self, db):
        db.insert_document(Document(filename="d.pdf", mime_type="application/pdf", id="d1"))
        db.insert_chunk("c1", "d1", 0, "hello world", 2, "emb-1")
        db.insert_chunk("c2", "d1", 1, "foo bar", 2, "emb-2")
        chunks = db.get_chunks_by_document("d1")
        assert len(chunks) == 2
        assert chunks[0]["content"] == "hello world"

    def test_insert_and_list_sessions(self, db):
        db.insert_session("什么是AI", "AI是人工智能", ["c1", "c2"])
        sessions = db.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["query"] == "什么是AI"
