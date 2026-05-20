# AI 协作约定

本项目可在 Claude Code、Copilot CLI 等 AI 编程工具中协作开发。以下是在本项目中使用 AI 协作的行为约定。

## 技术背景

- Python 3.11+ / FastAPI 后端，React 18 + TypeScript 前端
- 向量存储 ChromaDB，元数据 SQLite
- 嵌入模型 SentenceTransformer（本地，不调 API），对话模型 DeepSeek API
- 包管理：后端 `pyproject.toml` (pip)，前端 `package.json` (npm)
- 测试框架：pytest，38 个测试覆盖全部模块

## 协作规则

### 测试驱动

- 先写测试再写实现代码
- 任何功能性变更完成后立即运行 `cd backend && python -m pytest tests/ -v`
- 破坏现有测试的变更必须同步修复测试

### 核心链路不许动

Agent 问答链路是项目的命脉：

```
main.py → AskWorkflow → ReActAgent → ToolRegistry → ChromaStore/LLM
```

这个链路涉及 `agent_loop.py`、`workflows.py`、`tools.py`、`llm.py`、`chroma_store.py`。修改任何一个文件，都必须跑对应的测试文件。特别是：

- `test_agent_loop.py` — 覆盖 Agent 无工具调用、单次工具调用、循环上限
- `test_workflows.py` — 覆盖摄入成功、解析失败、返回文档对象
- `test_tools.py` — 覆盖工具定义格式、ToolRegistry 分发

### Embedding 是本地模型

`embedder.py` 使用 `sentence-transformers`，不调 DeepSeek API。首次启动会从 HuggingFace 下载 `paraphrase-multilingual-MiniLM-L12-v2` 模型（约 80MB）。国内环境必须配置 `HF_ENDPOINT=https://hf-mirror.com`，否则下载超时。

测试中 mock SentenceTransformer 时必须模拟 numpy array 的 `.tolist()` 行为：
```python
mock_model = MagicMock()
mock_model.encode.return_value = mock_embedding  # mock_embedding 也必须是 MagicMock
mock_embedding.tolist.return_value = [0.1] * 384
```

### 前端和后端签名一致

前端 `frontend/src/api/client.ts` 中的 API 调用签名必须与后端 `main.py` 中的端点保持一致。当前后端返回纯 JSON（非 SSE），前端 API 客户端已同步更新。

### 文件结构约定

- 源代码：`backend/src/`，前端：`frontend/src/`
- 测试：`backend/tests/`，文件名对应 `test_<module>.py`
- 文档：`docs/`
- 环境变量：`backend/.env`（不提交），模板 `backend/.env.example`
