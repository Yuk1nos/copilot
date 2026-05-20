import os
import uuid
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.models import Document, DocStatus
from src.database import Database
from src.chroma_store import ChromaStore
from src.document_parser import DocumentParser
from src.splitter import TextSplitter
from src.embedder import Embedder
from src.llm import DeepSeekLLM
from src.workflows import AskWorkflow, SummaryWorkflow

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

_db = Database(os.getenv("DB_PATH", "copilot.db"))
_db.initialize()

_llm = DeepSeekLLM()
_embedder = Embedder()
_chroma_store = ChromaStore(collection_name="doc_chunks", embed_fn=_embedder.embed)
_parser = DocumentParser()
_splitter = TextSplitter(chunk_size=500, chunk_overlap=50)

app = FastAPI(title="Enterprise Copilot MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


class SummaryRequest(BaseModel):
    document_ids: list[str] | None = None


@app.get("/api/documents")
def list_documents():
    return _db.list_documents()


@app.get("/api/sessions")
def list_sessions():
    return _db.list_sessions()


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No filename")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10MB)")

    filepath = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{file.filename}"
    filepath.write_bytes(content)

    doc = Document(
        filename=file.filename,
        mime_type=_parser.guess_mime_type(file.filename),
    )

    def generate():
        _db.insert_document(doc)
        yield json.dumps({"step": "parsing", "filename": doc.filename}, ensure_ascii=False) + "\n"

        try:
            text = _parser.parse(str(filepath))
        except Exception as e:
            _db.update_document(doc.id, status=DocStatus.ERROR.value)
            yield json.dumps({"step": "error", "error": str(e)}, ensure_ascii=False) + "\n"
            return

        yield json.dumps({"step": "chunking", "char_count": len(text)}, ensure_ascii=False) + "\n"

        chunks = _splitter.split(text)
        _db.update_document(doc.id, status=DocStatus.CHUNKING.value, chunk_count=len(chunks))

        yield json.dumps({"step": "embedding", "chunk_count": len(chunks)}, ensure_ascii=False) + "\n"

        _embedder.embed_batch(chunks)

        yield json.dumps({"step": "indexing", "chunk_count": len(chunks)}, ensure_ascii=False) + "\n"

        try:
            chunk_data = [
                (doc.id, i, chunk, {"filename": doc.filename})
                for i, chunk in enumerate(chunks)
            ]
            embedding_ids = _chroma_store.add(chunk_data)

            for i, chunk in enumerate(chunks):
                chunk_id = uuid.uuid4().hex[:12]
                _db.insert_chunk(chunk_id, doc.id, i, chunk, len(chunk), embedding_ids[i])

            _db.update_document(doc.id, status=DocStatus.INDEXED.value, char_count=len(text))
            yield json.dumps({"step": "done", "doc_id": doc.id, "filename": doc.filename, "status": "indexed"}, ensure_ascii=False) + "\n"
        except Exception as e:
            _db.update_document(doc.id, status=DocStatus.ERROR.value)
            yield json.dumps({"step": "error", "error": str(e)}, ensure_ascii=False) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.post("/api/ask")
async def ask_question(req: AskRequest):
    wf = AskWorkflow(db=_db, chroma_store=_chroma_store, llm=_llm)
    answer = wf.run(req.question)
    return {"question": req.question, "answer": answer}


@app.post("/api/summary")
async def generate_summary(req: SummaryRequest):
    wf = SummaryWorkflow(db=_db, chroma_store=_chroma_store, llm=_llm)
    summary = wf.run(req.document_ids)
    return {"summary": summary}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    doc = _db.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    _db.delete_document(doc_id)
    _chroma_store.delete_by_document(doc_id)
    for f in UPLOAD_DIR.glob(f"*_{doc['filename']}"):
        f.unlink()
    return {"deleted": doc_id}
