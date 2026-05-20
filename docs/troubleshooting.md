# 排错记录

## 删除 Tracer 后的连环故障：SQLite 锁表 + 协议断裂 + 变量名错误

### 现象

删除 Tracer 功能后，前端三个核心功能全部异常：

1. **智能问答** — 点击发送后报"请求失败"，后端日志 `sqlite3.OperationalError: database is locked`
2. **生成摘要** — 按钮点击后无响应，摘要区域始终为空
3. **上传文档** — 文件上传成功但前端不显示进度，必须手动刷新浏览器

### 排查过程

**第一层：SQLite 锁表**

问答请求进入 `AskWorkflow.run()` → `Database.insert_session()` 时抛出 `database is locked`。日志显示同一个 `copilot.db` 被多个协程并发写入。

Uvicorn 默认多 worker，FastAPI 的 async endpoint 在事件循环中调度，而 SQLite 默认不支持并发写——一个连接持有写锁时，其他连接的写入操作立即失败，不排队等待。

两个修复同时生效：

- 连接串加 `timeout=10`：`sqlite3.connect(db_path, timeout=10)`。SQLite 会在 10 秒内不断重试获取锁，而不是立即报错
- 启用 WAL 模式：`PRAGMA journal_mode=WAL`。Write-Ahead Logging 允许一个写者和多个读者同时操作，写操作追加到 WAL 文件而不是直接锁表

注意：WAL 的 PRAGMA 必须放在 `initialize()` 方法里，不能放在 `__init__`。如果在 `__init__` 里执行，模块 `import` 时就触发，此时若有其他进程也在初始化同一个数据库就会死锁。

**第二层：前后端协议断裂**

锁表修好后，问答和摘要仍然异常。curl 抓包发现后端返回的是纯 JSON：

```json
{"question": "测试", "answer": "..."}
```

但前端 `QAPage.tsx` 和 `DocManager.tsx` 仍使用 SSE（Server-Sent Events）的 `response.body.getReader()` 逐行读取方式解析。`JSON.parse()` 拿到一个完整的 JSON 对象，不是 `data:` 前缀的 SSE 事件流，解析逻辑完全不匹配。

原因：删除 Tracer 时，所有 workflow 的返回值从 SSE TraceEvent 流改成了普通 Python 字符串/字典，FastAPI 自动序列化为 JSON。但前端没有同步更新。

修复前端三处：

- `DocManager.tsx` — 上传改用 NDJSON 流式读取（见第三层），摘要改用 `await response.json()`
- `QAPage.tsx` — 问答改用 `await response.json()`

**第三层：上传流式进度消失**

上传的修复更复杂——用户要求"实时显示，不自己刷新"。简单返回 JSON 会让前端在上传完成前完全无反馈。

最终方案：后端 `main.py` 的 `upload_document` 改为 `StreamingResponse`，用 NDJSON（Newline-Delimited JSON）格式逐行推送进度：

```python
def generate():
    _db.insert_document(doc)
    yield json.dumps({"step": "parsing", ...}) + "\n"
    text = _parser.parse(str(filepath))
    yield json.dumps({"step": "chunking", ...}) + "\n"
    chunks = _splitter.split(text)
    yield json.dumps({"step": "embedding", ...}) + "\n"
    ...
    yield json.dumps({"step": "done", ...}) + "\n"

return StreamingResponse(generate(), media_type="application/x-ndjson")
```

前端逐行解析 NDJSON 流，每收到一行立即更新 UI 进度条。比旧 Tracer 的 SSE 方案更简单——不需要定义 TraceEvent 类型，不需要 span_id/trace_id，纯 JSON 行。

**第四层：变量名错误**

NDJSON 流调通后，进度到 `indexing` 步骤就报错：

```
{"step": "error", "error": "name '_chroma' is not defined"}
```

`generate()` 函数内写的是 `_chroma.add(chunk_data)`，但模块级全局变量定义是 `_chroma_store = ChromaStore(...)`。代码里其他位置（AskWorkflow、SummaryWorkflow、delete_document）都正确引用 `_chroma_store`，唯独 generate() 内仍用旧变量名。

这是因为最初 Tracer 版本中变量就叫 `_chroma`，删除 Tracer 时重命名了全局变量但遗漏了 generate() 内部。generate() 是嵌套在 upload_document 里的闭包函数，IDE 的"查找引用"不会跨越闭包边界索引，人工检查时也容易被嵌套结构掩盖。

修了这条之后上传全链路跑通，5 步进度（parsing → chunking → embedding → indexing → done）正常推送。

### 教训

- **SQLite 并发**：FastAPI + SQLite 必须配 WAL + timeout，否则多协程一撞就死。PRAGMA 放 initialize() 不放 **init**，避免 import 时副作用
- **删除功能要全量 grep**：删 Tracer 时只改了后端 API 返回格式，没同步改前端消费端。做"删除一个类型/模块"这种重构时，要先 `rg` 所有引用点，确保没有遗漏
- **闭包内的变量 rename 不会触发 IDE 报错**：`generate()` 是 `upload_document()` 内部的闭包，外层变量重命名时 IDE 的 rename refactor 不一定覆盖到闭包内部。靠测试覆盖比靠 IDE 更可靠
- **NDJSON 比 SSE 更适合"一次性"的进度推送**：不需要维护事件类型枚举，不需要 trace/span 概念。一行 JSON = 一步进度，前端解析也简单
