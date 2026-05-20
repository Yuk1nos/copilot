# 架构与关键文件

## 分层架构

```
┌─────────────────────────────────────┐
│  React 前端                          │
│  DocManager | QAPage                 │
│  HTTP + JSON                         │
└──────────────┬──────────────────────┘
               ↓
┌──────────────────────────────────────┐
│  FastAPI API 层                       │
│  /upload | /ask | /summary | /docs   │
│  请求校验 | JSON 响应                 │
└──────────────┬──────────────────────┘
               ↓
┌──────────────────────────────────────┐
│  Workflow 引擎                        │
│  摄入: Doc→Parse→Split→Embed→Index   │
│  问答: Query→Retrieve→Agent→Answer   │
│  摘要: Chunks→Aggregate→LLM          │
└──┬────────────┬──────────────┬───────┘
   ↓            ↓              ↓
┌───────┐ ┌─────────┐ ┌──────────────┐
│ChromaDB│ │ SQLite  │ │ 本地文件系统 │
│向量检索│ │元数据    │ │ 上传文档原件 │
└───────┘ └─────────┘ └──────────────┘
               ↓
┌──────────────────────────────────────┐
│  DeepSeek API (Chat)                  │
│  SentenceTransformer (Embedding)      │
└──────────────────────────────────────┘
```

## 核心链路：Agent / Workflow / Tool 调用

```
POST /api/ask {"question":"xxx"}
  │
  ├─ main.py:90  ask_question()
  └─ AskWorkflow.run(question)
       │
       ├─ ToolRegistry(chroma_store, llm)     ← 注册 3 个工具
       ├─ ReActAgent(llm, tools)              ← Agent 实例
       │
       └─ ReActAgent.run(question)            ← ReAct 循环 (max 5 轮)
            │
            ├─ llm.chat_with_tools(msgs, tools, system)
            │   └─ DeepSeek API 返回 {content, tool_calls}
            │
            ├─ if tool_calls:
            │   └─ ToolRegistry.execute(name, args)
            │        ├─ search_docs     → ChromaStore.query()
            │        ├─ search_more     → ChromaStore.query()
            │        └─ generate_summary → llm.chat()
            │   └─ 结果追加到 messages → 回到循环
            │
            └─ else: return answer.content
```

## 关键文件

| 文件 | 行数 | 职责 | 为什么这样设计 |
|------|------|------|----------------|
| `agent_loop.py` | 47 | ReAct Agent 循环 | 自己实现而非 LangChain，消息构造和工具分发完全透明 |
| `tools.py` | 88 | 工具定义 + ToolRegistry | `build_tool_definitions()` 生成 OpenAI 兼容 schema；`execute()` 用 if/elif 分发，简单直接 |
| `workflows.py` | 73 | 三条业务管线 | Ingest（解析→切片→嵌入→索引）、Ask（编排 Agent）、Summary（聚合→LLM） |
| `llm.py` | 71 | DeepSeek Chat API | `chat_with_tools()` 返回 dict（非 SDK 对象），方便 Agent 消费 |
| `embedder.py` | 12 | 本地嵌入 | SentenceTransformer 384 维，不调远程 API |
| `chroma_store.py` | 44 | 向量存储封装 | query 返回带 metadata、score、content 的结构化结果 |
| `database.py` | 92 | SQLite | documents + chunks + sessions 三张表 |
| `main.py` | 101 | FastAPI 入口 | 6 个端点，JSON 响应，无 SSE |

## 测试

38 个测试覆盖全部模块：

```bash
$ cd backend && python -m pytest tests/ -v

tests/test_models.py          — 2 passed  (Document, DocStatus)
tests/test_database.py        — 6 passed  (CRUD, sessions)
tests/test_chroma_store.py    — 2 passed  (add, query)
tests/test_embedder.py        — 2 passed  (embed, embed_batch)
tests/test_llm.py             — 4 passed  (chat, system, stream, tools)
tests/test_document_parser.py — 3 passed  (parse, empty, mime)
tests/test_splitter.py        — 4 passed  (chunk, size, empty, short)
tests/test_tools.py           — 4 passed  (definitions, registry)
tests/test_agent_loop.py      — 3 passed  (answer, tool_call, max_iter)
tests/test_workflows.py       — 3 passed  (ingest, return, error)
tests/test_api.py             — 5 passed  (list, sessions, validation)
============================= 38 passed =============================
```

### 关键测试用例

**test_run_calls_tool_when_model_requests** — 验证核心链路：

```python
# LLM 第一轮返回 tool_call，第二轮返回 answer
agent = self._make_agent(llm_responses=[
    {"content": None,
     "tool_calls": [{"id":"c1", "name":"search_docs", "arguments": '{"query":"答案"}'}]},
    {"content": "根据检索结果，答案是42。", "tool_calls": None},
])
answer = agent.run("答案是多少？")
assert agent._tools.execute.called   # ToolRegistry 被调用了
assert "42" in answer                # 最终答案包含检索结果
```

**test_ingest_raises_on_parse_error** — 验证异常传播：

```python
wf._parser.parse.side_effect = Exception("parse failed")
with pytest.raises(Exception, match="parse failed"):
    wf.run(doc, "/tmp/bad.pdf")
assert wf._db.insert_document.called  # 文档仍然入库
```

## API 调用示例

```bash
# 上传文档
curl -X POST http://localhost:8000/api/upload -F "file=@test.txt"
# → {"doc_id":"abc123","filename":"test.txt","status":"indexed"}

# 问答
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"文档主要内容是什么？"}'
# → {"question":"文档主要内容是什么？","answer":"根据文档内容，..."}

# 历史记录
curl http://localhost:8000/api/sessions
# → [{"id":1,"query":"...","answer":"...","created_at":"..."}]
```
