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
        {
            "type": "function",
            "function": {
                "name": "generate_summary",
                "description": "对指定的文档或检索到的文本片段生成结构化摘要",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "需要生成摘要的文本内容"},
                    },
                    "required": ["text"],
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

        if tool_name == "generate_summary" and self._llm:
            text = args.get("text", "")
            prompt = f"请对以下内容生成结构化摘要：\n\n{text[:4000]}"
            return self._llm.chat([{"role": "user", "content": prompt}])

        return f"Unknown tool: {tool_name}"
