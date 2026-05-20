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
