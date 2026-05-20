from src.tools import build_tool_definitions, ToolRegistry


class ReActAgent:
    SYSTEM_PROMPT = (
        "你是一个企业资料分析助手。根据提供的文档内容回答问题。"
        "如果检索结果不够充分，可以使用 search_more 工具再次搜索。"
        "回答时必须在末尾标注引用来源（文档名、段落号）。"
    )

    def __init__(self, llm, tools: ToolRegistry):
        self._llm = llm
        self._tools = tools

    def run(self, question: str, max_iterations: int = 5) -> str:
        messages = [{"role": "user", "content": question}]
        tool_defs = build_tool_definitions()

        for _ in range(max_iterations):
            response = self._llm.chat_with_tools(
                messages=messages,
                tools=tool_defs,
                system=self.SYSTEM_PROMPT,
            )

            if response.get("tool_calls"):
                for tc in response["tool_calls"]:
                    result = self._tools.execute(tc["name"], tc["arguments"])

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
                return response.get("content", "")

        return "抱歉，未能找到足够的信息来回答您的问题。"
