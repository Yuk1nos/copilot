# Enterprise Copilot MVP

企业文档智能助手 — 上传文档、语义检索、Agent 问答、结构化摘要。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI |
| 前端 | React 18 + TypeScript / Vite |
| 向量存储 | ChromaDB |
| 元数据 | SQLite |
| 嵌入模型 | SentenceTransformer (paraphrase-multilingual-MiniLM-L12-v2) |
| 对话模型 | DeepSeek API (deepseek-chat) |
| 文档解析 | pdfplumber (PDF) + python-docx (Word) |

## 项目结构

```
Copilot/
├── backend/
│   ├── src/
│   │   ├── main.py           # FastAPI 入口，API 端点
│   │   ├── models.py         # Document、DocStatus 数据模型
│   │   ├── database.py       # SQLite 操作层
│   │   ├── chroma_store.py   # ChromaDB 向量存储封装
│   │   ├── llm.py            # DeepSeek Chat API 封装
│   │   ├── embedder.py       # SentenceTransformer 嵌入
│   │   ├── document_parser.py # PDF/Word/TXT 解析
│   │   ├── splitter.py       # 文本切片
│   │   ├── agent_loop.py     # ReAct Agent 循环
│   │   ├── tools.py          # 工具定义 + ToolRegistry
│   │   └── workflows.py      # 摄入/问答/摘要 Workflow
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # 路由 + 布局
│   │   ├── pages/
│   │   │   ├── DocManager.tsx # 文档管理 + 摘要
│   │   │   └── QAPage.tsx    # 智能问答
│   │   ├── api/client.ts     # API 客户端
│   │   └── types/index.ts    # TypeScript 类型
│   ├── vite.config.ts
│   └── package.json
└── docs/
```

## 快速启动

### 1. 环境准备

```bash
# Python 3.11+
python --version

# Node.js 18+
node --version
```

### 2. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# 安装依赖
pip install -e ".[dev]"

# 配置环境变量（复制并编辑）
cp .env.example .env
```

`.env` 文件内容：

```env
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
HF_ENDPOINT=https://hf-mirror.com
```

- `DEEPSEEK_API_KEY` — DeepSeek API 密钥（必填）
- `HF_ENDPOINT` — HuggingFace 镜像（国内用户建议设置）

首次启动时 SentenceTransformer 会自动下载嵌入模型（约 420MB）。

```bash
# 启动后端
uvicorn src.main:app --reload --port 8000
```

API 文档：http://localhost:8000/docs

### 3. 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

打开 http://localhost:5173

### 4. 运行测试

```bash
cd backend
python -m pytest tests/ -v
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/documents` | 文档列表 |
| POST | `/api/upload` | 上传文档（multipart/form-data） |
| POST | `/api/ask` | 问答 `{"question": "..."}` |
| POST | `/api/summary` | 摘要 `{"document_ids": [...]}` |
| GET | `/api/sessions` | 历史问答记录 |
| DELETE | `/api/documents/{id}` | 删除文档 |

## 核心链路

```
用户提问
  → POST /api/ask {"question":"xxx"}
    → AskWorkflow.run()
      → ToolRegistry(chroma_store, llm)      注册工具
      → ReActAgent(llm, tools)               Agent 实例
        → ReAct 循环:
          ① llm.chat_with_tools()            LLM 决策
          ② 返回 tool_calls → execute()      执行工具
             ├─ search_docs  → ChromaDB 语义检索
             ├─ search_more  → 二次检索
             └─ generate_summary → LLM 生成摘要
          ③ 工具结果追加到消息历史 → 回到①
          ④ 返回最终答案
```


## 文件限制

- 单文件上限 10MB
- 支持格式：PDF、Word (.docx)、TXT、Markdown
