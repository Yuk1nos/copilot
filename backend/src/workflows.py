import uuid
from src.models import Document, DocStatus
from src.tools import ToolRegistry
from src.agent_loop import ReActAgent


class IngestWorkflow:
    def __init__(self, db, parser, splitter, embedder, chroma_store):
        self._db = db
        self._parser = parser
        self._splitter = splitter
        self._embedder = embedder
        self._chroma = chroma_store

    def run(self, doc: Document, filepath: str):
        self._db.insert_document(doc)

        text = self._parser.parse(filepath)

        chunks = self._splitter.split(text)
        self._db.update_document(doc.id, status=DocStatus.CHUNKING.value, chunk_count=len(chunks))

        embeddings = self._embedder.embed_batch(chunks)

        chunk_data = [
            (doc.id, i, chunk, {"filename": doc.filename})
            for i, chunk in enumerate(chunks)
        ]
        embedding_ids = self._chroma.add(chunk_data)

        for i, chunk in enumerate(chunks):
            chunk_id = uuid.uuid4().hex[:12]
            self._db.insert_chunk(chunk_id, doc.id, i, chunk, len(chunk), embedding_ids[i])

        self._db.update_document(doc.id, status=DocStatus.INDEXED.value, char_count=len(text))
        return doc


class AskWorkflow:
    def __init__(self, db, chroma_store, llm):
        self._db = db
        self._chroma = chroma_store
        self._llm = llm

    def run(self, question: str) -> str:
        tools = ToolRegistry(chroma_store=self._chroma, llm=self._llm)
        agent = ReActAgent(llm=self._llm, tools=tools)
        answer = agent.run(question)
        self._db.insert_session(question, answer, [])
        return answer


class SummaryWorkflow:
    def __init__(self, db, chroma_store, llm):
        self._db = db
        self._chroma = chroma_store
        self._llm = llm

    def run(self, document_ids: list[str] | None = None) -> str:
        if document_ids:
            all_chunks = []
            for did in document_ids:
                all_chunks.extend(self._db.get_chunks_by_document(did))
        else:
            all_docs = self._db.list_documents()
            all_chunks = []
            for d in all_docs:
                all_chunks.extend(self._db.get_chunks_by_document(d["id"]))

        if not all_chunks:
            return "没有找到可用的文档内容，请先上传并索引文档。"

        context = "\n\n".join(c["content"] for c in all_chunks[:60])

        prompt = (
            "请基于以下文档内容生成结构化摘要，按主题和要点组织：\n\n"
            f"{context}\n\n"
            "输出格式：\n## 一、概览\n...\n## 二、要点\n...\n## 三、细节\n..."
        )

        return self._llm.chat([{"role": "user", "content": prompt}], max_tokens=4096)
