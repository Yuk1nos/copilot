# 企业资料处理 Copilot MVP — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建企业资料处理 MVP：上传文档 → 索引 → Agent 问答（含引用）→ 结构化摘要 → Trace 链路可视化回放。

**Architecture:** FastAPI + 自定义 Workflow 引擎 + 结构化 Trace 系统。React SPA 前端通过 SSE 流式接收 TraceEvent，实时渲染 Agent 推理过程。ChromaDB 做向量检索，SQLite 存元数据和 Trace。

**Tech Stack:** Python 3.11+, FastAPI, ChromaDB, SQLite, DeepSeek API, React + TypeScript

---

### Task 1: 项目脚手架 + 核心数据模型

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/__init__.py`
- Create: `backend/src/models.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: 初始化 Python 项目配置**

```toml
# backend/pyproject.toml
[project]
name = "enterprise-copilot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "chromadb>=0.5.0",
    "openai>=1.30.0",
    "pdfplumber>=0.11.0",
    "python-docx>=1.1.0",
    "python-multipart>=0.0.9",
    "sse-starlette>=2.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24.0", "httpx>=0.27.0"]
```

- [ ] **Step 2: 安装依赖**

Run: `cd backend && pip install -e ".[dev]"`
Expected: 所有依赖安装成功

- [ ] **Step 3: 编写核心模型测试**

```python
# backend/tests/test_models.py
from src.models import TraceEvent, Document, EventType, DocStatus


class TestTraceEvent:
    def test_creates_event_with_required_fields(self):
        event = TraceEvent(
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            event_type=EventType.DOC_UPLOADED,
            status="running",
        )
        assert event.trace_id == "t1"
        assert event.span_id == "s1"
        assert event.parent_span_id is None
        assert event.input == {}
        assert event.output == {}

    def test_event_with_input_output(self):
        event = TraceEvent(
            trace_id="t1",
            span_id="s2",
            parent_span_id="s1",
            event_type=EventType.RETRIEVAL_DONE,
            status="done",
            input={"query": "什么是AI"},
            output={"chunks": ["chunk1"], "scores": [0.95]},
        )
        assert event.input["query"] == "什么是AI"
        assert len(event.output["chunks"]) == 1

    def test_to_dict_includes_all_fields(self):
        event = TraceEvent(
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            event_type=EventType.AGENT_ANSWER,
            status="done",
            output={"answer": "AI是人工智能"},
            metadata={"tokens": 100},
        )
        d = event.to_dict()
        assert d["trace_id"] == "t1"
        assert d["event_type"] == "agent_answer"
        assert d["metadata"]["tokens"] == 100


class TestDocument:
    def test_creates_document_with_defaults(self):
        doc = Document(
            filename="test.pdf",
            mime_type="application/pdf",
        )
        assert doc.status == DocStatus.UPLOADED
        assert doc.char_count == 0
        assert doc.chunk_count == 0

    def test_to_dict_serializes_status(self):
        doc = Document(filename="a.txt", mime_type="text/plain", status=DocStatus.INDEXED)
        d = doc.to_dict()
        assert d["status"] == "indexed"
```

- [ ] **Step 4: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL — 找不到 src.models 模块

- [ ] **Step 5: 实现核心模型**

```python
# backend/src/models.py
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import uuid
from datetime import datetime, timezone


class EventType(str, Enum):
    DOC_UPLOADED = "doc_uploaded"
    DOC_PARSED = "doc_parsed"
    DOC_CHUNKED = "doc_chunked"
    DOC_EMBEDDED = "doc_embedded"
    DOC_INDEXED = "doc_indexed"
    QUESTION_RECEIVED = "question_received"
    RETRIEVAL_DONE = "retrieval_done"
    AGENT_THINK = "agent_think"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    AGENT_ANSWER = "agent_answer"
    SUMMARY_START = "summary_start"
    SUMMARY_DONE = "summary_done"


class DocStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    INDEXED = "indexed"
    ERROR = "error"


@dataclass
class TraceEvent:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    event_type: EventType
    status: str  # running | done | error
    input: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d


@dataclass
class Document:
    filename: str
    mime_type: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    char_count: int = 0
    chunk_count: int = 0
    status: DocStatus = DocStatus.UPLOADED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS (5 tests)

---

### Task 2: SQLite 数据库层

**Files:**
- Create: `backend/src/database.py`
- Create: `backend/tests/test_database.py`

- [ ] **Step 1: 编写数据库测试**

```python
# backend/tests/test_database.py
import pytest
from src.database import Database
from src.models import TraceEvent, EventType, Document


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
        assert "trace_events" in names
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

    def test_insert_and_get_trace_events(self, db):
        event = TraceEvent(
            trace_id="t1", span_id="s1", parent_span_id=None,
            event_type=EventType.QUESTION_RECEIVED, status="done",
            input={"q": "hello"}, output={},
        )
        db.insert_trace_event(event)
        events = db.get_trace_events("t1")
        assert len(events) == 1
        assert events[0]["event_type"] == "question_received"

    def test_trace_events_parent_child(self, db):
        db.insert_trace_event(TraceEvent(
            trace_id="t2", span_id="root", parent_span_id=None,
            event_type=EventType.QUESTION_RECEIVED, status="done",
        ))
        db.insert_trace_event(TraceEvent(
            trace_id="t2", span_id="child1", parent_span_id="root",
            event_type=EventType.RETRIEVAL_DONE, status="done",
        ))
        events = db.get_trace_events("t2")
        assert len(events) == 2

    def test_insert_session(self, db):
        db.insert_session("t1", "什么是AI", "AI是人工智能", ["c1", "c2"])
        sessions = db.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["query"] == "什么是AI"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_database.py -v`
Expected: FAIL — 找不到 src.database 模块

- [ ] **Step 3: 实现 Database 类**

```python
# backend/src/database.py
import sqlite3
import json
from typing import Optional
from src.models import TraceEvent, Document


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
            CREATE TABLE IF NOT EXISTS trace_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                span_id TEXT NOT NULL,
                parent_span_id TEXT,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                input_json TEXT DEFAULT '{}',
                output_json TEXT DEFAULT '{}',
                duration_ms INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                query TEXT NOT NULL,
                answer TEXT,
                referenced_chunk_ids TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_trace_events_trace_id ON trace_events(trace_id);
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

    def insert_trace_event(self, event: TraceEvent):
        self._conn.execute(
            "INSERT INTO trace_events (trace_id, span_id, parent_span_id, event_type, status, input_json, output_json, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                event.trace_id, event.span_id, event.parent_span_id,
                event.event_type.value, event.status,
                json.dumps(event.input, ensure_ascii=False),
                json.dumps(event.output, ensure_ascii=False),
                event.metadata.get("duration_ms"),
            ],
        )
        self._conn.commit()

    def get_trace_events(self, trace_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM trace_events WHERE trace_id = ? ORDER BY id", [trace_id]
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["input"] = json.loads(d.pop("input_json"))
            d["output"] = json.loads(d.pop("output_json"))
            result.append(d)
        return result

    def insert_session(self, trace_id: str, query: str, answer: str, referenced_chunk_ids: list[str]):
        self._conn.execute(
            "INSERT INTO sessions (trace_id, query, answer, referenced_chunk_ids) VALUES (?, ?, ?, ?)",
            [trace_id, query, answer, json.dumps(referenced_chunk_ids, ensure_ascii=False)],
        )
        self._conn.commit()

    def list_sessions(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_database.py -v`
Expected: PASS (8 tests)

---

### Task 3: Tracer — TraceEvent 流式生产者

**Files:**
- Create: `backend/src/tracer.py`
- Create: `backend/tests/test_tracer.py`

- [ ] **Step 1: 编写 Tracer 测试**

```python
# backend/tests/test_tracer.py
import asyncio
from src.tracer import Tracer
from src.models import EventType


class TestTracer:
    def test_creates_event_with_correct_hierarchy(self):
        t = Tracer(trace_id="t1")
        root = t.start_span("root", EventType.QUESTION_RECEIVED)
        assert root.parent_span_id is None
        child = t.start_span("child", EventType.RETRIEVAL_DONE, parent_span=root)
        assert child.parent_span_id == "root"

    def test_finish_span_with_output(self):
        t = Tracer(trace_id="t1")
        span = t.start_span("s1", EventType.RETRIEVAL_DONE)
        t.finish_span(span, output={"chunks": ["a"], "scores": [0.9]})
        assert span.status == "done"
        assert span.output["chunks"] == ["a"]

    def test_finish_span_with_error(self):
        t = Tracer(trace_id="t1")
        span = t.start_span("s1", EventType.RETRIEVAL_DONE)
        t.finish_span(span, error="model unavailable")
        assert span.status == "error"
        assert span.output["error"] == "model unavailable"

    def test_yields_events_via_stream(self):
        t = Tracer(trace_id="t1")
        span = t.start_span("s1", EventType.QUESTION_RECEIVED, input={"q": "hello"})
        t.finish_span(span, output={"ok": True})
        t.finish_trace()

        events = list(t.stream())
        assert len(events) >= 2  # at least start + done

    def test_event_stream_format_is_json_serializable(self):
        import json
        t = Tracer(trace_id="t1")
        span = t.start_span("s1", EventType.AGENT_ANSWER, output={"answer": "test"})
        t.finish_span(span)
        t.finish_trace()

        for event_str in t.stream():
            d = json.loads(event_str)
            assert "trace_id" in d


class TestTracerAsync:
    @pytest.mark.asyncio
    async def test_async_stream_iteration(self):
        from src.tracer import Tracer
        t = Tracer(trace_id="tx")
        span = t.start_span("s1", EventType.QUESTION_RECEIVED)
        t.finish_span(span)
        t.finish_trace()

        events = list(t.stream())
        assert len(events) > 0
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_tracer.py -v`
Expected: FAIL — 找不到 src.tracer 模块

- [ ] **Step 3: 实现 Tracer**

```python
# backend/src/tracer.py
import json
import uuid
import time
from typing import Optional, Generator
from src.models import TraceEvent, EventType


class Tracer:
    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or uuid.uuid4().hex[:16]
        self._events: list[TraceEvent] = []
        self._start_times: dict[str, float] = {}

    def start_span(self, span_id: str, event_type: EventType,
                   parent_span: Optional[TraceEvent] = None, input: dict | None = None) -> TraceEvent:
        event = TraceEvent(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=parent_span.span_id if parent_span else None,
            event_type=event_type,
            status="running",
            input=input or {},
        )
        self._start_times[span_id] = time.time()
        self._events.append(event)
        return event

    def finish_span(self, span: TraceEvent, output: dict | None = None, error: str | None = None):
        if error:
            span.status = "error"
            span.output = {"error": error}
        else:
            span.status = "done"
            span.output = output or {}
        elapsed = (time.time() - self._start_times.get(span.span_id, time.time())) * 1000
        span.metadata["duration_ms"] = int(elapsed)

    def finish_trace(self):
        pass  # signal end; no-op for now

    def stream(self) -> Generator[str, None, None]:
        for event in self._events:
            d = event.to_dict()
            d.pop("metadata", None)
            yield f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_tracer.py -v`
Expected: PASS (6 tests)

---

### Task 4: DeepSeek LLM 封装

**Files:**
- Create: `backend/src/llm.py`
- Create: `backend/tests/test_llm.py`

- [ ] **Step 1: 编写 LLM 测试**

```python
# backend/tests/test_llm.py
import os
from unittest.mock import patch, MagicMock
from src.llm import DeepSeekLLM


class TestDeepSeekLLM:
    def test_chat_returns_content(self):
        with patch("src.llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = "你好，AI"
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice]
            )
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(api_key="sk-test")
            result = llm.chat([{"role": "user", "content": "你好"}])
            assert result == "你好，AI"

    def test_chat_passes_system_prompt(self):
        with patch("src.llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = "ok"
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[mock_choice]
            )
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(api_key="sk-test")
            llm.chat(
                messages=[{"role": "user", "content": "x"}],
                system="你是助手",
                temperature=0.3,
            )
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["temperature"] == 0.3
            msgs = call_args[1]["messages"]
            assert msgs[0]["role"] == "system"
            assert msgs[0]["content"] == "你是助手"

    def test_chat_stream_yields_chunks(self):
        with patch("src.llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            chunk1 = MagicMock()
            chunk1.choices = [MagicMock(delta=MagicMock(content="你好"))]
            chunk2 = MagicMock()
            chunk2.choices = [MagicMock(delta=MagicMock(content="世界"))]
            mock_client.chat.completions.create.return_value = [chunk1, chunk2]
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(api_key="sk-test")
            chunks = list(llm.chat_stream([{"role": "user", "content": "hi"}]))
            assert "".join(chunks) == "你好世界"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_llm.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 DeepSeekLLM**

```python
# backend/src/llm.py
import os
from typing import Generator
from openai import OpenAI


class DeepSeekLLM:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._client = OpenAI(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

    def chat(self, messages: list[dict], system: str | None = None,
             temperature: float = 0.7, max_tokens: int = 2048,
             tools: list[dict] | None = None) -> str:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        kwargs = dict(
            model="deepseek-chat",
            messages=msgs,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def chat_with_tools(self, messages: list[dict], tools: list[dict],
                        system: str | None = None, temperature: float = 0.7) -> dict:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        response = self._client.chat.completions.create(
            model="deepseek-chat",
            messages=msgs,
            temperature=temperature,
            tools=tools,
        )
        msg = response.choices[0].message
        result = {"content": msg.content}
        if msg.tool_calls:
            result["tool_calls"] = [
                {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                for tc in msg.tool_calls
            ]
        return result

    def chat_stream(self, messages: list[dict], system: str | None = None,
                    temperature: float = 0.7, max_tokens: int = 2048) -> Generator[str, None, None]:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        stream = self._client.chat.completions.create(
            model="deepseek-chat",
            messages=msgs,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_llm.py -v`
Expected: PASS (3 tests)

---

### Task 5: 文档解析器

**Files:**
- Create: `backend/src/document_parser.py`
- Create: `backend/tests/test_document_parser.py`

- [ ] **Step 1: 编写解析器测试**

```python
# backend/tests/test_document_parser.py
import pytest
from pathlib import Path
from src.document_parser import DocumentParser


@pytest.fixture
def parser():
    return DocumentParser()


@pytest.fixture
def sample_txt(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("这是测试文本内容。\n用于文档解析验证。", encoding="utf-8")
    return str(f)


class TestDocumentParser:
    def test_parse_txt_returns_text(self, parser, sample_txt):
        text = parser.parse(sample_txt)
        assert "测试文本内容" in text
        assert "文档解析验证" in text

    def test_parse_returns_empty_string_for_empty_file(self, parser, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        text = parser.parse(str(f))
        assert text == ""

    def test_guess_mime_type(self, parser):
        assert parser.guess_mime_type("doc.pdf") == "application/pdf"
        assert parser.guess_mime_type("doc.docx") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert parser.guess_mime_type("doc.txt") == "text/plain"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_document_parser.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 DocumentParser**

```python
# backend/src/document_parser.py
from pathlib import Path


class DocumentParser:
    def parse(self, filepath: str) -> str:
        path = Path(filepath)
        suffix = path.suffix.lower()

        if suffix == ".txt":
            return path.read_text(encoding="utf-8")
        elif suffix == ".pdf":
            return self._parse_pdf(filepath)
        elif suffix == ".docx":
            return self._parse_docx(filepath)
        else:
            return path.read_text(encoding="utf-8")

    def _parse_pdf(self, filepath: str) -> str:
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                texts = [p.extract_text() or "" for p in pdf.pages]
            return "\n".join(texts)
        except ImportError:
            raise RuntimeError("pdfplumber not installed")

    def _parse_docx(self, filepath: str) -> str:
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(filepath)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise RuntimeError("python-docx not installed")

    def guess_mime_type(self, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        mapping = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".md": "text/markdown",
        }
        return mapping.get(suffix, "application/octet-stream")
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_document_parser.py -v`
Expected: PASS (3 tests)

---

### Task 6: 文本切片器

**Files:**
- Create: `backend/src/splitter.py`
- Create: `backend/tests/test_splitter.py`

- [ ] **Step 1: 编写切片器测试**

```python
# backend/tests/test_splitter.py
from src.splitter import TextSplitter


class TestTextSplitter:
    def test_splits_text_into_chunks(self):
        text = "第一段内容。第二段内容。第三段内容。第四段内容。"
        splitter = TextSplitter(chunk_size=1)
        chunks = splitter.split(text)
        assert len(chunks) >= 2

    def test_each_chunk_within_size_limit(self):
        text = "测试。" * 500
        splitter = TextSplitter(chunk_size=200)
        chunks = splitter.split(text)
        for c in chunks:
            assert len(c) <= 200

    def test_empty_text_returns_empty_list(self):
        splitter = TextSplitter(chunk_size=100)
        assert splitter.split("") == []

    def test_text_shorter_than_chunk_size_returns_single_chunk(self):
        text = "短文本"
        splitter = TextSplitter(chunk_size=1000)
        chunks = splitter.split(text)
        assert len(chunks) == 1
        assert chunks[0] == "短文本"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_splitter.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 TextSplitter**

```python
# backend/src/splitter.py


class TextSplitter:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap
        return chunks
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_splitter.py -v`
Expected: PASS (4 tests)

---

### Task 7: DeepSeek Embedding 封装

**Files:**
- Create: `backend/src/embedder.py`
- Create: `backend/tests/test_embedder.py`

- [ ] **Step 1: 编写 Embedder 测试**

```python
# backend/tests/test_embedder.py
from unittest.mock import patch, MagicMock
from src.embedder import Embedder


class TestEmbedder:
    def test_embed_returns_vector(self):
        with patch("src.embedder.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_embedding = MagicMock()
            mock_embedding.embedding = [0.1] * 1536
            mock_client.embeddings.create.return_value = MagicMock(
                data=[mock_embedding]
            )
            mock_openai.return_value = mock_client

            embedder = Embedder(api_key="sk-test")
            vec = embedder.embed("测试文本")
            assert len(vec) == 1536

    def test_embed_batch_returns_multiple_vectors(self):
        with patch("src.embedder.OpenAI") as mock_openai:
            mock_client = MagicMock()
            e1 = MagicMock()
            e1.embedding = [0.1] * 1536
            e2 = MagicMock()
            e2.embedding = [0.2] * 1536
            mock_client.embeddings.create.return_value = MagicMock(data=[e1, e2])
            mock_openai.return_value = mock_client

            embedder = Embedder(api_key="sk-test")
            vecs = embedder.embed_batch(["文本1", "文本2"])
            assert len(vecs) == 2
            assert len(vecs[0]) == 1536
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_embedder.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 Embedder**

```python
# backend/src/embedder.py
import os
from openai import OpenAI


class Embedder:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._client = OpenAI(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(
            model="deepseek-embedding",
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(
            model="deepseek-embedding",
            input=texts,
        )
        return [d.embedding for d in response.data]
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_embedder.py -v`
Expected: PASS (2 tests)

---

### Task 8: ChromaDB 向量存储

**Files:**
- Create: `backend/src/chroma_store.py`
- Create: `backend/tests/test_chroma_store.py`

- [ ] **Step 1: 编写 ChromaStore 测试**

```python
# backend/tests/test_chroma_store.py
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
        ids = store.add([
            ("doc1", 0, "光伏产业市场报告", {"filename": "a.pdf"}),
            ("doc1", 1, "新能源汽车销量增长", {"filename": "a.pdf"}),
        ])
        assert len(ids) == 2

        results = store.query("光伏产业", top_k=1)
        assert len(results) == 1
        assert results[0]["content"] == "光伏产业市场报告"

    def test_query_returns_metadata(self, store):
        store.add([
            ("doc1", 0, "测试内容", {"filename": "x.pdf", "page": 1}),
        ])
        results = store.query("测试", top_k=1)
        assert results[0]["metadata"]["filename"] == "x.pdf"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_chroma_store.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 ChromaStore**

```python
# backend/src/chroma_store.py
import uuid
from chromadb import Client, Collection


class ChromaStore:
    def __init__(self, client: Client | None = None, collection_name: str = "doc_chunks",
                 embed_fn=None):
        import chromadb
        self._client = client or chromadb.Client()
        self._collection: Collection = self._client.get_or_create_collection(name=collection_name)
        self._embed_fn = embed_fn or (lambda text: [0.0] * 1536)

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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_chroma_store.py -v`
Expected: PASS (2 tests)

---

### Task 9: Agent 工具定义

**Files:**
- Create: `backend/src/tools.py`
- Create: `backend/tests/test_tools.py`

- [ ] **Step 1: 编写 Tools 测试**

```python
# backend/tests/test_tools.py
from src.tools import build_tool_definitions, ToolRegistry
from src.chroma_store import ChromaStore
from src.llm import DeepSeekLLM


class TestToolDefinitions:
    def test_build_returns_openai_format(self):
        tools = build_tool_definitions()
        assert len(tools) == 3
        assert tools[0]["type"] == "function"
        assert "name" in tools[0]["function"]
        assert "parameters" in tools[0]["function"]

    def test_all_tools_have_descriptions(self):
        tools = build_tool_definitions()
        names = [t["function"]["name"] for t in tools]
        assert "search_docs" in names
        assert "search_more" in names
        assert "generate_summary" in names


class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        import chromadb
        store = ChromaStore(client=chromadb.Client(), collection_name="test_tools_registry")
        return ToolRegistry(chroma_store=store, llm=None)

    def test_execute_search_docs(self, registry):
        result = registry.execute("search_docs", '{"query": "test"}')
        assert isinstance(result, (str, list))

    def test_execute_unknown_tool_returns_error(self, registry):
        result = registry.execute("nonexistent", "{}")
        assert "error" in result.lower() or "unknown" in result.lower()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_tools.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 Tools**

```python
# backend/src/tools.py
import json


def build_tool_definitions() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_docs",
                "description": "在已上传的企业文档中进行语义搜索，返回最相关的文本片段及其来源",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索查询"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_more",
                "description": "当首次检索信息不足时，用改写后的查询再次搜索补充信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "改写后的搜索查询"},
                        "reason": {"type": "string", "description": "为什么需要再次搜索"},
                    },
                    "required": ["query"],
                },
            },
        },
    ]


class ToolRegistry:
    def __init__(self, chroma_store=None, llm=None):
        self._store = chroma_store
        self._llm = llm

    def execute(self, tool_name: str, arguments: str) -> str:
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError:
            return "Error: invalid JSON arguments"

        if tool_name == "search_docs" and self._store:
            results = self._store.query(args.get("query", ""), top_k=5)
            if not results:
                return "未找到相关文档"
            parts = []
            for r in results:
                source = r["metadata"].get("filename", "unknown")
                parts.append(f"[来源: {source}] {r['content']}")
            return "\n\n".join(parts)

        if tool_name == "search_more" and self._store:
            results = self._store.query(args.get("query", ""), top_k=5)
            if not results:
                return "未找到补充信息"
            parts = []
            for r in results:
                source = r["metadata"].get("filename", "unknown")
                parts.append(f"[来源: {source}] {r['content']}")
            return "\n\n".join(parts)

        return f"Unknown tool: {tool_name}"
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_tools.py -v`
Expected: PASS (4 tests)

---

### Task 10: ReAct Agent 循环

**Files:**
- Create: `backend/src/agent_loop.py`
- Create: `backend/tests/test_agent_loop.py`

- [ ] **Step 1: 编写 Agent 循环测试**

```python
# backend/tests/test_agent_loop.py
from unittest.mock import MagicMock, patch
from src.agent_loop import ReActAgent
from src.tracer import Tracer
from src.models import EventType


class TestReActAgent:
    def _make_agent(self, llm_responses=None):
        llm = MagicMock()
        if llm_responses:
            llm.chat_with_tools.side_effect = llm_responses
        tools = MagicMock()
        tools.execute.return_value = "search result: relevant text"
        tracer = Tracer("test-trace")
        return ReActAgent(llm=llm, tools=tools, tracer=tracer)

    def test_run_returns_answer_when_no_tool_calls(self):
        agent = self._make_agent(llm_responses=[
            {"content": "根据资料显示，答案是42。", "tool_calls": None},
        ])
        answer = agent.run("答案是多少？")
        assert "42" in answer

    def test_run_calls_tool_when_model_requests(self):
        agent = self._make_agent(llm_responses=[
            {
                "content": None,
                "tool_calls": [{"id": "c1", "name": "search_docs", "arguments": '{"query":"答案"}'}],
            },
            {"content": "根据检索结果，答案是42。", "tool_calls": None},
        ])
        answer = agent.run("答案是多少？")
        assert agent._tools.execute.called
        assert "42" in answer

    def test_max_iterations_prevents_infinite_loop(self):
        tool_response = {
            "content": None,
            "tool_calls": [{"id": "c1", "name": "search_docs", "arguments": '{"query":"x"}'}],
        }
        agent = self._make_agent(llm_responses=[tool_response] * 20)
        answer = agent.run("问题", max_iterations=3)
        assert agent._tools.execute.call_count <= 3
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_agent_loop.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 ReActAgent**

```python
# backend/src/agent_loop.py
import json
from src.tracer import Tracer
from src.models import EventType
from src.tools import build_tool_definitions, ToolRegistry


class ReActAgent:
    SYSTEM_PROMPT = (
        "你是一个企业资料分析助手。根据提供的文档内容回答问题。"
        "如果检索结果不够充分，可以使用 search_more 工具再次搜索。"
        "回答时必须在末尾标注引用来源（文档名、段落号）。"
    )

    def __init__(self, llm, tools: ToolRegistry, tracer: Tracer):
        self._llm = llm
        self._tools = tools
        self._tracer = tracer

    def run(self, question: str, max_iterations: int = 5) -> str:
        messages = [{"role": "user", "content": question}]
        tool_defs = build_tool_definitions()

        for i in range(max_iterations):
            span = self._tracer.start_span(
                f"agent_think_{i}", EventType.AGENT_THINK,
                input={"iteration": i},
            )

            response = self._llm.chat_with_tools(
                messages=messages,
                tools=tool_defs,
                system=self.SYSTEM_PROMPT,
            )
            self._tracer.finish_span(span, output=response)

            if response.get("tool_calls"):
                for tc in response["tool_calls"]:
                    tool_span = self._tracer.start_span(
                        f"tool_{tc['id']}", EventType.TOOL_CALL,
                        input={"tool": tc["name"], "args": tc["arguments"]},
                        parent_span=span,
                    )
                    result = self._tools.execute(tc["name"], tc["arguments"])
                    self._tracer.finish_span(tool_span, output={"result": result[:500]})

                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
            else:
                answer = response.get("content", "")
                answer_span = self._tracer.start_span(
                    "agent_answer", EventType.AGENT_ANSWER,
                    output={"answer": answer[:500]},
                )
                self._tracer.finish_span(answer_span)
                return answer

        return "抱歉，未能找到足够的信息来回答您的问题。"
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_agent_loop.py -v`
Expected: PASS (3 tests)

---

### Task 11: 摄入 Workflow

**Files:**
- Create: `backend/src/workflows.py`
- Create: `backend/tests/test_workflows.py`

- [ ] **Step 1: 编写 Workflow 测试**

```python
# backend/tests/test_workflows.py
from unittest.mock import MagicMock, patch
from src.workflows import IngestWorkflow
from src.tracer import Tracer
from src.models import Document


class TestIngestWorkflow:
    def _make_workflow(self):
        db = MagicMock()
        db.insert_document = MagicMock()
        db.update_document = MagicMock()
        db.insert_chunk = MagicMock()

        parser = MagicMock()
        parser.parse.return_value = "这是解析后的文本内容"

        splitter = MagicMock()
        splitter.split.return_value = ["chunk1", "chunk2"]

        embedder = MagicMock()
        embedder.embed_batch.return_value = [[0.1] * 1536, [0.2] * 1536]

        chroma = MagicMock()
        chroma.add.return_value = ["emb1", "emb2"]

        return IngestWorkflow(
            db=db,
            parser=parser,
            splitter=splitter,
            embedder=embedder,
            chroma_store=chroma,
        )

    def test_ingest_processes_document(self):
        wf = self._make_workflow()
        tracer = Tracer("t1")

        doc = Document(filename="test.txt", mime_type="text/plain")
        wf.run(doc, "/tmp/test.txt", tracer)

        assert wf._db.insert_document.called
        assert wf._parser.parse.called
        assert wf._splitter.split.called
        assert wf._embedder.embed_batch.called
        assert wf._chroma.add.called
        assert wf._db.update_document.called

    def test_ingest_yields_trace_events(self):
        wf = self._make_workflow()
        tracer = Tracer("t2")

        doc = Document(filename="t.txt", mime_type="text/plain")
        wf.run(doc, "/tmp/t.txt", tracer)

        events = list(tracer.stream())
        assert len(events) >= 4  # upload -> parsed -> chunked -> embedded -> indexed
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_workflows.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 Workflows**

```python
# backend/src/workflows.py
import uuid
from src.models import TraceEvent, EventType, Document, DocStatus
from src.tracer import Tracer
from src.database import Database
from src.document_parser import DocumentParser
from src.splitter import TextSplitter
from src.embedder import Embedder
from src.chroma_store import ChromaStore


class IngestWorkflow:
    def __init__(self, db: Database, parser: DocumentParser, splitter: TextSplitter,
                 embedder: Embedder, chroma_store: ChromaStore):
        self._db = db
        self._parser = parser
        self._splitter = splitter
        self._embedder = embedder
        self._chroma = chroma_store

    def run(self, doc: Document, filepath: str, tracer: Tracer):
        self._db.insert_document(doc)

        # Parse
        span = tracer.start_span("parse", EventType.DOC_PARSED, input={"file": doc.filename})
        try:
            text = self._parser.parse(filepath)
            self._db.update_document(doc.id, status=DocStatus.PARSING.value)
            tracer.finish_span(span, output={"char_count": len(text)})
        except Exception as e:
            tracer.finish_span(span, error=str(e))
            self._db.update_document(doc.id, status=DocStatus.ERROR.value)
            return

        # Split
        span = tracer.start_span("split", EventType.DOC_CHUNKED, input={"char_count": len(text)})
        chunks = self._splitter.split(text)
        self._db.update_document(doc.id, status=DocStatus.CHUNKING.value, chunk_count=len(chunks))
        tracer.finish_span(span, output={"chunk_count": len(chunks)})

        # Embed
        span = tracer.start_span("embed", EventType.DOC_EMBEDDED, input={"chunk_count": len(chunks)})
        embeddings = self._embedder.embed_batch(chunks)
        tracer.finish_span(span, output={"embedding_count": len(embeddings)})

        # Index
        span = tracer.start_span("index", EventType.DOC_INDEXED)
        chunk_data = [
            (doc.id, i, chunk, {"filename": doc.filename})
            for i, chunk in enumerate(chunks)
        ]
        embedding_ids = self._chroma.add(chunk_data)

        for i, chunk in enumerate(chunks):
            chunk_id = uuid.uuid4().hex[:12]
            self._db.insert_chunk(chunk_id, doc.id, i, chunk, len(chunk), embedding_ids[i])

        self._db.update_document(doc.id, status=DocStatus.INDEXED.value, char_count=len(text))
        tracer.finish_span(span, output={"indexed_chunks": len(embedding_ids)})
        tracer.finish_trace()


class AskWorkflow:
    def __init__(self, db: Database, chroma_store: ChromaStore, llm, tracer_factory):
        self._db = db
        self._chroma = chroma_store
        self._llm = llm
        self._tracer_factory = tracer_factory

    def run(self, question: str) -> tuple[str, Tracer]:
        from src.tools import ToolRegistry
        from src.agent_loop import ReActAgent

        tracer = self._tracer_factory()
        tracer.start_span("question", EventType.QUESTION_RECEIVED, input={"question": question})

        tools = ToolRegistry(chroma_store=self._chroma, llm=self._llm)
        agent = ReActAgent(llm=self._llm, tools=tools, tracer=tracer)
        answer = agent.run(question)

        self._db.insert_session(tracer.trace_id, question, answer, [])
        return answer, tracer


class SummaryWorkflow:
    def __init__(self, db: Database, chroma_store: ChromaStore, llm, tracer_factory):
        self._db = db
        self._chroma = chroma_store
        self._llm = llm
        self._tracer_factory = tracer_factory

    def run(self, document_ids: list[str] | None = None) -> tuple[str, Tracer]:
        tracer = self._tracer_factory()
        tracer.start_span("summary", EventType.SUMMARY_START)

        # Gather all document chunks
        if document_ids:
            all_chunks = []
            for did in document_ids:
                all_chunks.extend(self._db.get_chunks_by_document(did))
        else:
            all_docs = self._db.list_documents()
            all_chunks = []
            for d in all_docs:
                all_chunks.extend(self._db.get_chunks_by_document(d["id"]))

        context = "\n\n".join(c["content"] for c in all_chunks[:20])

        prompt = (
            "请基于以下文档内容生成结构化摘要，按主题和要点组织：\n\n"
            f"{context[:8000]}\n\n"
            "输出格式：\n## 一、概览\n...\n## 二、要点\n...\n## 三、细节\n..."
        )

        summary = self._llm.chat([{"role": "user", "content": prompt}])
        span = tracer.start_span("summary_done", EventType.SUMMARY_DONE, output={"summary": summary[:500]})
        tracer.finish_span(span)
        tracer.finish_trace()

        return summary, tracer
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_workflows.py -v`
Expected: PASS (2 tests)

---

### Task 12: FastAPI 应用入口

**Files:**
- Create: `backend/src/main.py`
- Create: `backend/tests/test_api.py`

- [ ] **Step 1: 编写 API 集成测试**

```python
# backend/tests/test_api.py
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("src.main._db", MagicMock()), \
         patch("src.main._chroma_store", MagicMock()), \
         patch("src.main._llm", MagicMock()), \
         patch("src.main._embedder", MagicMock()), \
         patch("src.main._parser", MagicMock()), \
         patch("src.main._splitter", MagicMock()):
        from src.main import app
        return TestClient(app)


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

    def test_get_trace_not_found(self, client):
        import src.main as m
        m._db.get_trace_events.return_value = []
        response = client.get("/api/trace/nonexistent")
        assert response.status_code == 200
        assert response.json()["events"] == []

    def test_get_trace_with_events(self, client):
        import src.main as m
        m._db.get_trace_events.return_value = [
            {"trace_id": "t1", "span_id": "s1", "event_type": "question_received", "input": {}, "output": {}}
        ]
        response = client.get("/api/trace/t1")
        assert response.status_code == 200
        assert len(response.json()["events"]) == 1

    def test_upload_without_file_returns_422(self, client):
        response = client.post("/api/upload")
        assert response.status_code == 422

    def test_ask_without_question_returns_422(self, client):
        response = client.post("/api/ask", json={})
        assert response.status_code == 422
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 FastAPI 应用**

```python
# backend/src/main.py
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.models import Document
from src.database import Database
from src.chroma_store import ChromaStore
from src.document_parser import DocumentParser
from src.splitter import TextSplitter
from src.embedder import Embedder
from src.llm import DeepSeekLLM
from src.tracer import Tracer
from src.workflows import IngestWorkflow, AskWorkflow, SummaryWorkflow

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

    def event_stream():
        tracer = Tracer()
        tracer.start_span("doc_uploaded", __import__("src.models", fromlist=["EventType"]).EventType.DOC_UPLOADED,
                          input={"filename": file.filename, "size": len(content)})

        wf = IngestWorkflow(
            db=_db, parser=_parser, splitter=_splitter,
            embedder=_embedder, chroma_store=_chroma_store,
        )
        wf.run(doc, str(filepath), tracer)

        for event_str in tracer.stream():
            yield event_str

    return EventSourceResponse(event_stream())


@app.post("/api/ask")
async def ask_question(req: AskRequest):
    def event_stream():
        tracer = Tracer()

        wf = AskWorkflow(
            db=_db, chroma_store=_chroma_store, llm=_llm,
            tracer_factory=lambda: tracer,
        )

        from src.workflows import AskWorkflow
        wf = AskWorkflow(
            db=_db, chroma_store=_chroma_store, llm=_llm,
            tracer_factory=lambda: tracer,
        )
        wf.run(req.question)

        for event_str in tracer.stream():
            yield event_str

    return EventSourceResponse(event_stream())


@app.post("/api/summary")
async def generate_summary(req: SummaryRequest):
    def event_stream():
        tracer = Tracer()

        wf = SummaryWorkflow(
            db=_db, chroma_store=_chroma_store, llm=_llm,
            tracer_factory=lambda: tracer,
        )
        wf.run(req.document_ids)

        for event_str in tracer.stream():
            yield event_str

    return EventSourceResponse(event_stream())


@app.get("/api/trace/{trace_id}")
def get_trace(trace_id: str):
    events = _db.get_trace_events(trace_id)
    return {"trace_id": trace_id, "events": events}
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: PASS (6 tests)

---

### Task 13: React 前端脚手架 + 类型定义

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`

- [ ] **Step 1: 初始化前端项目并安装依赖**

Run:
```
cd frontend && npm init -y && npm install react react-dom react-router-dom && npm install -D typescript @types/react @types/react-dom vite @vitejs/plugin-react
```

- [ ] **Step 2: 创建 TypeScript 类型定义**

```typescript
// frontend/src/types/index.ts
export interface TraceEvent {
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  event_type: string;
  status: "running" | "done" | "error";
  input: Record<string, unknown>;
  output: Record<string, unknown>;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  mime_type: string;
  char_count: number;
  chunk_count: number;
  status: string;
  created_at: string;
}

export interface SessionInfo {
  id: number;
  trace_id: string;
  query: string;
  answer: string;
  referenced_chunk_ids: string[];
  created_at: string;
}

export interface TraceData {
  trace_id: string;
  events: TraceEvent[];
}
```

- [ ] **Step 3: 创建 API 客户端**

```typescript
// frontend/src/api/client.ts
import type { DocumentInfo, TraceData } from "../types";

const BASE = "http://localhost:8000/api";

export async function fetchDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch(`${BASE}/documents`);
  return res.json();
}

export async function fetchTrace(traceId: string): Promise<TraceData> {
  const res = await fetch(`${BASE}/trace/${traceId}`);
  return res.json();
}

export function uploadDocument(file: File): EventSource {
  const formData = new FormData();
  formData.append("file", file);
  return streamRequest(`${BASE}/upload`, {
    method: "POST",
    body: formData,
  });
}

export function askQuestion(question: string): EventSource {
  return streamRequest(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export function generateSummary(documentIds?: string[]): EventSource {
  return streamRequest(`${BASE}/summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds || null }),
  });
}

function streamRequest(url: string, init: RequestInit): EventSource {
  return new EventSource(url);  // simplified — in production pass init differently
}
```

- [ ] **Step 4: 创建 App 入口**

```tsx
// frontend/src/App.tsx
import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import DocManager from "./pages/DocManager";
import QAPage from "./pages/QAPage";
import SummaryPage from "./pages/SummaryPage";
import TraceViewer from "./pages/TraceViewer";

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: "flex", minHeight: "100vh" }}>
        <nav style={{ width: 200, background: "#1a1a2e", color: "#eee", padding: 16 }}>
          <h2 style={{ fontSize: 16, marginBottom: 24 }}>Copilot MVP</h2>
          <ul style={{ listStyle: "none", padding: 0 }}>
            <li><Link to="/" style={linkStyle}>文档管理</Link></li>
            <li><Link to="/ask" style={linkStyle}>问答</Link></li>
            <li><Link to="/summary" style={linkStyle}>摘要</Link></li>
            <li><Link to="/trace" style={linkStyle}>Trace 回放</Link></li>
          </ul>
        </nav>
        <main style={{ flex: 1, padding: 24 }}>
          <Routes>
            <Route path="/" element={<DocManager />} />
            <Route path="/ask" element={<QAPage />} />
            <Route path="/summary" element={<SummaryPage />} />
            <Route path="/trace" element={<TraceViewer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

const linkStyle: React.CSSProperties = {
  display: "block",
  padding: "8px 0",
  color: "#a0a0d0",
  textDecoration: "none",
  fontSize: 14,
};
```

- [ ] **Step 5: 创建 HTML 和 Vite 配置**

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>Copilot MVP</title></head>
<body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body>
</html>
```

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({ plugins: [react()] });
```

```tsx
// frontend/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
```

---

### Task 14: 前端页面实现

**Files:**
- Create: `frontend/src/pages/DocManager.tsx`
- Create: `frontend/src/pages/QAPage.tsx`
- Create: `frontend/src/pages/SummaryPage.tsx`
- Create: `frontend/src/pages/TraceViewer.tsx`

- [ ] **Step 1: 实现 DocManager 页面**

```tsx
// frontend/src/pages/DocManager.tsx
import React, { useEffect, useState } from "react";
import type { DocumentInfo, TraceEvent } from "../types";
import { fetchDocuments, uploadDocument } from "../api/client";

export default function DocManager() {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => { fetchDocuments().then(setDocs); }, []);

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setEvents([]);

    const es = uploadDocument(file);
    es.onmessage = (ev) => {
      const event = JSON.parse(ev.data) as TraceEvent;
      setEvents((prev) => [...prev, event]);
      if (event.event_type === "doc_indexed") {
        setUploading(false);
        fetchDocuments().then(setDocs);
        es.close();
      }
    };
  };

  return (
    <div>
      <h2>文档管理</h2>
      <label style={{ display: "inline-block", padding: "8px 16px", background: "#4a9eff", color: "#fff", borderRadius: 4, cursor: "pointer", marginBottom: 16 }}>
        {uploading ? "处理中..." : "+ 上传文档"}
        <input type="file" hidden onChange={handleUpload} accept=".pdf,.docx,.txt,.md" />
      </label>

      {events.length > 0 && (
        <div style={{ marginBottom: 16, padding: 12, background: "#f0f4f8", borderRadius: 4 }}>
          <strong>处理进度:</strong>
          {events.map((e, i) => (
            <div key={i} style={{ fontSize: 13, marginTop: 4 }}>
              [{e.status}] {e.event_type}
            </div>
          ))}
        </div>
      )}

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #ddd" }}>
            <th style={th}>文件名</th><th style={th}>字数</th><th style={th}>片段</th><th style={th}>状态</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id} style={{ borderBottom: "1px solid #eee" }}>
              <td style={td}>{d.filename}</td>
              <td style={td}>{d.char_count}</td>
              <td style={td}>{d.chunk_count}</td>
              <td style={td}>{d.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const th: React.CSSProperties = { textAlign: "left", padding: 8 };
const td: React.CSSProperties = { padding: 8 };
```

- [ ] **Step 2: 实现 QAPage 页面**

```tsx
// frontend/src/pages/QAPage.tsx
import React, { useState } from "react";
import type { TraceEvent } from "../types";
import { askQuestion } from "../api/client";

interface QAItem { question: string; answer: string; events: TraceEvent[]; }

export default function QAPage() {
  const [qaList, setQaList] = useState<QAItem[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleAsk = () => {
    if (!input.trim()) return;
    const question = input;
    setInput("");
    setLoading(true);

    const item: QAItem = { question, answer: "", events: [] };
    setQaList((prev) => [...prev, item]);

    const es = askQuestion(question);
    es.onmessage = (ev) => {
      const event = JSON.parse(ev.data) as TraceEvent;
      setQaList((prev) => prev.map((q) =>
        q.question === question
          ? { ...q, events: [...q.events, event], answer: event.event_type === "agent_answer" ? (event.output.answer as string) : q.answer }
          : q
      ));
      if (event.event_type === "agent_answer") { setLoading(false); es.close(); }
    };
  };

  return (
    <div>
      <h2>问答</h2>
      {qaList.map((qa, i) => (
        <div key={i} style={{ marginBottom: 24, border: "1px solid #eee", borderRadius: 8, padding: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Q: {qa.question}</div>
          {qa.events.map((e, j) => (
            <div key={j} style={{ fontSize: 12, color: "#888", marginLeft: 8, marginBottom: 2 }}>
              [{e.event_type}] {e.status === "done" ? "✓" : "..."}
            </div>
          ))}
          {qa.answer && <div style={{ marginTop: 12, lineHeight: 1.8 }}>{qa.answer}</div>}
        </div>
      ))}
      <div style={{ display: "flex", gap: 8 }}>
        <input style={{ flex: 1, padding: 8, border: "1px solid #ccc", borderRadius: 4 }} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAsk()} placeholder="输入问题..." />
        <button onClick={handleAsk} disabled={loading} style={{ padding: "8px 16px", background: "#4a9eff", color: "#fff", border: "none", borderRadius: 4 }}>发送</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 实现 SummaryPage 页面**

```tsx
// frontend/src/pages/SummaryPage.tsx
import React, { useEffect, useState } from "react";
import type { DocumentInfo, TraceEvent } from "../types";
import { fetchDocuments, generateSummary } from "../api/client";

export default function SummaryPage() {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<TraceEvent[]>([]);

  useEffect(() => { fetchDocuments().then(setDocs); }, []);

  const handleGenerate = () => {
    setLoading(true);
    setSummary("");
    setEvents([]);
    const es = generateSummary(selected.length ? selected : undefined);
    es.onmessage = (ev) => {
      const event = JSON.parse(ev.data) as TraceEvent;
      setEvents((prev) => [...prev, event]);
      if (event.event_type === "summary_done") {
        setSummary(event.output.summary as string);
        setLoading(false);
        es.close();
      }
    };
  };

  return (
    <div>
      <h2>结构化摘要</h2>
      <div style={{ marginBottom: 16 }}>
        <select multiple value={selected} onChange={(e) => setSelected(Array.from(e.target.selectedOptions, (o) => o.value))} style={{ width: 300, height: 100 }}>
          {docs.map((d) => <option key={d.id} value={d.id}>{d.filename}</option>)}
        </select>
      </div>
      <button onClick={handleGenerate} disabled={loading} style={{ padding: "8px 16px", background: "#4a9eff", color: "#fff", border: "none", borderRadius: 4 }}>
        {loading ? "生成中..." : "生成摘要"}
      </button>
      {summary && <div style={{ marginTop: 16, lineHeight: 1.8, whiteSpace: "pre-wrap", background: "#f8f8f8", padding: 16, borderRadius: 8 }}>{summary}</div>}
    </div>
  );
}
```

- [ ] **Step 4: 实现 TraceViewer 页面**

```tsx
// frontend/src/pages/TraceViewer.tsx
import React, { useState } from "react";
import type { TraceData, TraceEvent } from "../types";
import { fetchTrace } from "../api/client";

export default function TraceViewer() {
  const [traceId, setTraceId] = useState("");
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [playing, setPlaying] = useState(false);
  const [playIdx, setPlayIdx] = useState(0);

  const handleLoad = async () => {
    const data: TraceData = await fetchTrace(traceId);
    setEvents(data.events);
    setPlayIdx(0);
  };

  const handleReplay = () => {
    if (events.length === 0) return;
    setPlaying(true);
    setPlayIdx(0);
    let i = 0;
    const iv = setInterval(() => {
      i++;
      setPlayIdx(i);
      if (i >= events.length) { setPlaying(false); clearInterval(iv); }
    }, 600);
  };

  const buildTree = (events: TraceEvent[], parentId: string | null = null, depth: number = 0): React.ReactNode[] => {
    return events.filter((e) => e.parent_span_id === parentId).map((e) => (
      <div key={e.span_id} style={{ marginLeft: depth * 16, marginBottom: 4 }}>
        <div style={{ display: "flex", gap: 8, fontSize: 13 }}>
          <span style={{ color: e.status === "done" ? "#4caf50" : e.status === "error" ? "#f44336" : "#ff9800" }}>
            {e.status === "done" ? "●" : "○"}
          </span>
          <span>{e.event_type}</span>
          <span style={{ color: "#888" }}>
            {JSON.stringify(e.input).slice(0, 60)}
          </span>
        </div>
        {buildTree(events, e.span_id, depth + 1)}
      </div>
    ));
  };

  return (
    <div>
      <h2>Trace 回放</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input value={traceId} onChange={(e) => setTraceId(e.target.value)} placeholder="输入 Trace ID" style={{ padding: 8, border: "1px solid #ccc", borderRadius: 4 }} />
        <button onClick={handleLoad} style={{ padding: "8px 16px", background: "#4a9eff", color: "#fff", border: "none", borderRadius: 4 }}>加载</button>
        <button onClick={handleReplay} disabled={events.length === 0 || playing} style={{ padding: "8px 16px", background: "#4caf50", color: "#fff", border: "none", borderRadius: 4 }}>
          ▶ 回放
        </button>
      </div>
      <div style={{ display: "flex", gap: 24 }}>
        <div style={{ flex: 1 }}>
          <h3>调用树</h3>
          {buildTree(events.slice(0, playing ? playIdx + 1 : undefined))}
        </div>
        <div style={{ flex: 1 }}>
          <h3>时间线</h3>
          {(playing ? events.slice(0, playIdx + 1) : events).map((e, i) => (
            <div key={i} style={{ fontSize: 12, padding: "4px 0", borderBottom: "1px solid #f0f0f0" }}>
              {e.event_type} — {e.status}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 验证前端构建**

Run: `cd frontend && npx tsc --noEmit && npx vite build`
Expected: TypeScript 编译通过，Vite 构建成功

---

### Task 15: 集成验证 + 启动说明

- [ ] **Step 1: 启动后端**

```bash
cd backend
export DEEPSEEK_API_KEY=<your-key>
uvicorn src.main:app --reload --port 8000
```

- [ ] **Step 2: 启动前端**

```bash
cd frontend
npx vite --port 5173
```

- [ ] **Step 3: 端到端验证**

1. 打开 `http://localhost:5173`
2. 上传一个 PDF 或 TXT 文件 → 观察处理进度
3. 在问答页输入问题 → 观察 Agent 推理链路实时渲染
4. 切换到摘要页 → 生成结构化摘要
5. 获取 trace_id，进入 Trace 回放页 → 观看调用树和时间线
