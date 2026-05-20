# 排错记录

## 排错 1：DeepSeek Embedding 返回 404 → HuggingFace 被墙连环坑

**日期：** 2026-05-19

**现象：** 上传文档后点击问答，后端直接崩溃。

**调用栈追踪：**

```
ERROR: Exception in ASGI application
...
File "src\tools.py", line 64, in execute
    results = self._store.query(args.get("query", ""), top_k=5)
File "src\chroma_store.py", line 30, in query
    query_embedding = self._embed_fn(query_text)
File "src\embedder.py", line 13, in embed
    response = self._client.embeddings.create(...)
openai.NotFoundError: Error code: 404
```

调用栈清晰：问答 → Agent 调用 search_docs → ChromaStore.query → Embedder.embed → DeepSeek API → **404**。

**根因：** DeepSeek 只有 Chat Completion，没有 `/v1/embeddings` 端点。代码里 `model="deepseek-embedding"` 是拍脑袋编的，根本不存在。这是典型的"假设 API 完备"——因为 DeepSeek Chat API 与 OpenAI SDK 兼容，就想当然认为 embedding 也存在。

**修复第一步 — 切 sentence-transformers：**

`embedder.py` 从 OpenAI SDK 调用改为 HuggingFace 的 `sentence-transformers`：

```python
# 之前
from openai import OpenAI
class Embedder:
    def __init__(self, api_key=..., base_url=...):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
    def embed(self, text):
        return self._client.embeddings.create(
            model="deepseek-embedding", input=text
        ).data[0].embedding

# 之后
from sentence_transformers import SentenceTransformer
class Embedder:
    def __init__(self, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        self._model = SentenceTransformer(model_name)
    def embed(self, text):
        return self._model.encode(text).tolist()
```

模型选 `paraphrase-multilingual-MiniLM-L12-v2`：384 维、80MB、支持中文、本地运行。连带改了 6 个文件——向量维度 1536→384、测试 mock 结构全换。

**修复第二步 — HuggingFace 被墙：**

改完重启，控制台卡住：

```
thrown while requesting HEAD https://huggingface.co/.../paraphrase-multilingual-MiniLM-L12-v2/...
'[WinError 10060] 连接尝试失败'
Retrying in 1s [Retry 1/5].
```

SentenceTransformer 首次加载要从 huggingface.co 下载模型文件，国内直连不通。

修法：`.env` 加 `HF_ENDPOINT=https://hf-mirror.com`，走国内镜像。模型缓存到 `~/.cache/huggingface/` 后就不再请求网络。

**教训：**
- 别假设任何 LLM 厂商的 API 和 OpenAI 1:1 对齐。查文档，先确认端点是否存在
- 国内环境提前考虑 HuggingFace 下载问题

---

## 排错 2：npx 自动安装 vite v8 原生 binding 崩溃

**现象：**

```powershell
PS> npx vite --port 5173

Need to install the following packages:
vite@8.0.13
Ok to proceed? (y) y

Error: Cannot find native binding.
  [cause]: rolldown-binding.win32-x64-msvc.node is not a valid Win32 application.
```

**根因：** 项目已 `npm install`，vite 5.4 在 `node_modules` 里。但 `npx vite` 的行为是：
1. 先在 `node_modules/.bin/` 找 vite
2. 找不到就从 npm registry 拉最新版
3. npx 用的是全局缓存（`%LOCALAPPDATA%\npm-cache\_npx\`），不读本地 `package.json`

npx 拉的最新版是 vite 8.0.13，它用 Rust 写的 rolldown 替换了 esbuild。rolldown 靠 `.node` 原生二进制加载 Rust 代码，当前机器的 DLL 环境不匹配，报 `is not a valid Win32 application`。

**解决：**

```powershell
.\node_modules\.bin\vite --port 5173
```

直接用项目安装的 vite 5.4（esbuild，纯 Go 编译的单一 exe，无原生 binding 依赖）。

**教训：** `npm install` 过的项目别用 `npx xyz`，用 `node_modules/.bin/xyz`。npx 的"自动安装最新版"是双刃剑——它在解决"工具没装"问题时可能引入版本兼容问题。
