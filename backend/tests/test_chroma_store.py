import pytest
from src.chroma_store import ChromaStore


@pytest.fixture
def store():
    import chromadb
    client = chromadb.Client()
    s = ChromaStore(client=client, collection_name="test_docs")
    yield s
    try:
        client.delete_collection("test_docs")
    except Exception:
        pass


class TestChromaStore:
    def test_add_and_query(self, store):
        # Use a simple embed_fn for testing: text length as pseudo-embedding
        store.set_embed_fn(lambda text: [float(len(text))] * 384)

        ids = store.add([
            ("doc1", 0, "光伏产业市场报告", {"filename": "a.pdf"}),
            ("doc1", 1, "新能源汽车销量增长", {"filename": "a.pdf"}),
        ])
        assert len(ids) == 2

        results = store.query("光伏产业", top_k=1)
        assert len(results) == 1
        assert results[0]["content"] == "光伏产业市场报告"

    def test_query_returns_metadata(self, store):
        store.set_embed_fn(lambda text: [float(len(text))] * 384)

        store.add([
            ("doc1", 0, "测试内容", {"filename": "x.pdf", "page": 1}),
        ])
        results = store.query("测试", top_k=1)
        assert results[0]["metadata"]["filename"] == "x.pdf"
