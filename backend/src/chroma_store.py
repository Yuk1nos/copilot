from __future__ import annotations

import uuid
from chromadb import Client, Collection


class ChromaStore:
    def __init__(self, client: Client | None = None, collection_name: str = "doc_chunks",
                 embed_fn=None):
        import chromadb
        self._client = client or chromadb.Client()
        self._collection: Collection = self._client.get_or_create_collection(name=collection_name)
        self._embed_fn = embed_fn or (lambda text: [0.0] * 384)

    def set_embed_fn(self, fn):
        self._embed_fn = fn

    def add(self, chunks: list[tuple[str, int, str, dict]]) -> list[str]:
        ids = [uuid.uuid4().hex[:16] for _ in chunks]
        contents = [c[2] for c in chunks]
        metadatas = [
            {"document_id": c[0], "chunk_index": c[1], **c[3]}
            for c in chunks
        ]
        embeddings = [self._embed_fn(text) for text in contents]
        self._collection.add(ids=ids, embeddings=embeddings, documents=contents, metadatas=metadatas)
        return ids

    def query(self, query_text: str, top_k: int = 5) -> list[dict]:
        query_embedding = self._embed_fn(query_text)
        results = self._collection.query(query_embeddings=[query_embedding], n_results=top_k)
        out = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                out.append({
                    "id": doc_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": results["distances"][0][i] if results["distances"] else 0.0,
                })
        return out

    def delete_by_document(self, document_id: str):
        self._collection.delete(where={"document_id": document_id})
