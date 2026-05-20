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

    def test_chat_with_tools_returns_tool_calls(self):
        with patch("src.llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_msg = MagicMock()
            mock_msg.content = None
            mock_tc = MagicMock()
            mock_tc.id = "call_1"
            mock_tc.function.name = "search_docs"
            mock_tc.function.arguments = '{"query":"test"}'
            mock_msg.tool_calls = [mock_tc]
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=mock_msg)]
            )
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(api_key="sk-test")
            result = llm.chat_with_tools(
                [{"role": "user", "content": "search"}],
                tools=[{"type": "function", "function": {"name": "search_docs", "parameters": {}}}],
            )
            assert result["tool_calls"][0]["name"] == "search_docs"
            assert result["tool_calls"][0]["arguments"] == '{"query":"test"}'
