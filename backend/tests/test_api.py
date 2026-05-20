import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=False):
        with patch("src.embedder.SentenceTransformer", MagicMock()), \
             patch("src.main._db", MagicMock()), \
             patch("src.main._chroma_store", MagicMock()), \
             patch("src.main._llm", MagicMock()), \
             patch("src.main._embedder", MagicMock()), \
             patch("src.main._parser", MagicMock()), \
             patch("src.main._splitter", MagicMock()):
            from src.main import app
            yield TestClient(app)


class TestAPI:
    def test_list_documents_empty(self, client):
        import src.main as m
        m._db.list_documents.return_value = []
        response = client.get("/api/documents")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_documents_with_data(self, client):
        import src.main as m
        m._db.list_documents.return_value = [
            {"id": "1", "filename": "a.pdf", "status": "indexed", "char_count": 100, "chunk_count": 3}
        ]
        response = client.get("/api/documents")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_sessions(self, client):
        import src.main as m
        m._db.list_sessions.return_value = [
            {"id": 1, "query": "test", "answer": "ok", "referenced_chunk_ids": "[]"}
        ]
        response = client.get("/api/sessions")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_upload_without_file_returns_422(self, client):
        response = client.post("/api/upload")
        assert response.status_code == 422

    def test_ask_without_question_returns_422(self, client):
        response = client.post("/api/ask", json={})
        assert response.status_code == 422
