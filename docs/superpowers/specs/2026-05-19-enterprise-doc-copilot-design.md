# 企业资料处理 Copilot MVP — 设计文档

**日期:** 2026-05-19
**状态:** 已确认

## 1. 目标

做一个能读取少量企业资料、进行问答引用和结构化摘要的 MVP，展示 Agent / Workflow / Tool 调用链路。Web UI 可调用入口，保留关键日志和中间过程。

## 2. 技术选型

| 维度 | 选择 |
|------|------|
| 后端语言 | Python 3.11+ |
| Web 框架 | FastAPI（SSE 流式响应） |
| LLM | DeepSeek API（Chat Completion + Embedding） |
| 前端 | React SPA |
| 向量存储 | ChromaDB |
| 元数据 + Trace 存储 | SQLite |
| 文档解析 | pdfplumber (PDF) + python-docx (Word) + 纯文本 |

## 3. 架构方案

方案 B：**FastAPI + 自定义 Workflow 引擎 + 结构化 Trace 系统**

### 3.1 分层架构

```
┌─────────────────────────────────────────┐
│  React 前端 (SPA)                        │
│  文档管理 | 问答 | 摘要 | Trace 回放      │
│  HTTP + SSE (流式)                       │
└──────────────┬──────────────────────────┘
               ↓
┌──────────────────────────────────────────┐
│  FastAPI API 层                           │
│  /upload | /ask | /summary | /trace/{id} │
│  请求校验 | SSE 推送 TraceEvent           │
└──────────────┬──────────────────────────┘
               ↓
┌──────────────────────────────────────────┐
│  Workflow 引擎                            │
│  摄入管线: Doc→Parse→Split→Embed→Index   │
│  问答管线: Query→Retrieve→Agent→Answer   │
│  每步产出 TraceEvent                     │
└──┬────────────┬──────────────┬──────────┘
   ↓            ↓              ↓
┌───────┐ ┌─────────┐ ┌──────────────┐
│ChromaDB│ │ SQLite  │ │ 本地文件系统 │
│向量检索│ │元数据    │ │ 上传文档原件 │
│       │ │Trace记录│ │              │
└───────┘ └─────────┘ └──────────────┘
               ↓
┌──────────────────────────────────────────┐
│  DeepSeek API                             │
│  Chat Completion | Embedding              │
└──────────────────────────────────────────┘
```

### 3.2 核心设计决策

- **为何不自建 Agent 循环？** 自己实现 ReAct 循环以保持对 Tool Calling 和 Trace 的完全控制。TraceEvent 作为一等公民贯穿全链路
- **为何不用 LangChain？** 避免框架的黑盒和版本变动。核心功能（Tool Calling 循环、检索）逻辑量不大，自己写更可控、可追踪
- **Trace 回放原理**：每个步骤产出一个 TraceEvent（含 trace_id/span_id/parent_span_id），存入 SQLite。前端通过 SSE 流式消费实时事件，或从 SQLite 读取历史 trace 回放

## 4. Workflow 设计

### 4.1 文档摄入 Workflow

```
[doc_uploaded] → Parse → [doc_parsed]
  → Split → [doc_chunked]
  → Embed → [doc_embedded]
  → Index → [doc_indexed]
```

### 4.2 Agent 问答 Workflow

```
[question_received] → Embed Query
  → [retrieval_done] (top-K chunks + scores)
  → [agent_think] (模型判断信息是否充分)
     ├─ [tool_call] → search_docs / search_more
     └─ [tool_result]
  → [agent_answer] (最终答案 + 引用)
```

### 4.3 Agent 可用工具

| 工具 | 功能 |
|------|------|
| `search_docs` | 语义检索已索引文档，返回 top-K chunks + 相似度 + 来源 |
| `search_more` | 改写 query 二次检索，用于首次召回不足时 |
| `generate_summary` | 对指定文档/片段生成结构化摘要 |

## 5. 数据模型

### 5.1 SQLite 表

```sql
documents (id, filename, mime_type, char_count, chunk_count, status, created_at)
chunks (id, document_id, chunk_index, content, token_count, embedding_id)
trace_events (id, trace_id, span_id, parent_span_id, event_type, status,
              input_json, output_json, duration_ms, created_at)
sessions (id, trace_id, query, answer, referenced_chunk_ids, created_at)
```

### 5.2 ChromaDB Collection

- `doc_chunks`: id, embedding(1536d), metadata={doc_id, chunk_index, filename}

## 6. API 端点

| 方法 | 路径 | 说明 | 响应 |
|------|------|------|------|
| POST | /api/upload | 上传文档，触发摄入 Workflow | SSE (进度事件流) |
| POST | /api/ask | 问答请求，触发 Agent Workflow | SSE (TraceEvent 流 + 最终答案) |
| POST | /api/summary | 生成结构化摘要 | SSE (TraceEvent 流 + 摘要) |
| GET | /api/trace/{trace_id} | 获取完整 trace 事件列表（回放） | JSON |
| GET | /api/documents | 列出已上传文档及状态 | JSON |

所有核心端点使用 SSE (Server-Sent Events) 流式响应，每个步骤的 TraceEvent 即时推送至前端。

## 7. TraceEvent 协议

```python
TraceEvent {
    trace_id: str        # 请求唯一 ID
    span_id: str         # 步骤唯一 ID
    parent_span_id: str  # 父步骤 ID（None = 根）
    event_type: str      # doc_uploaded | agent_think | tool_call | ...
    status: str          # running | done | error
    input: dict          # 入参
    output: dict         # 出参
    metadata: dict       # 可选：耗时、token 数等
}
```

前端通过 SSE 流式接收 TraceEvent，逐步骤渲染调用树和中间结果。回放时从 SQLite 读取完整 trace。

## 8. 前端页面

### 8.1 文档管理
- 文档列表（文件名、字数、chunk 数、索引状态）
- 上传按钮，上传后 SSE 实时显示处理进度

### 8.2 问答
- 输入框 + 对话历史
- 流式展示 Agent 推理过程（思考→检索→工具调用→回答）
- 答案底部自动标注引用来源（文件名 + 段落号）

### 8.3 结构化摘要
- 选择文档范围（单选/全选）
- 流式生成结构化摘要（按主题/要点组织）
- 结果可展开/折叠

### 8.4 Trace 链路回放
- 调用树视图（span 层级关系）
- 时间线视图（按时间先后排列步骤）
- 支持逐步骤回放
- 显示每步耗时、输入输出摘要

## 9. 非功能性需求

- **错误处理**: 文档解析失败不阻断流程，标记状态并在前端展示；LLM 调用失败自动重试一次
- **文件限制**: 单文件上限 10MB，单次上传最多 5 个文件
- **性能目标**: 文档处理 < 30s/MB，问答首 token < 3s
