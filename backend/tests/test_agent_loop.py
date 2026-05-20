from unittest.mock import MagicMock
from src.agent_loop import ReActAgent


class TestReActAgent:
    def _make_agent(self, llm_responses=None):
        llm = MagicMock()
        if llm_responses:
            llm.chat_with_tools.side_effect = llm_responses
        tools = MagicMock()
        tools.execute.return_value = "search result: relevant text"
        return ReActAgent(llm=llm, tools=tools)

    def test_run_returns_answer_when_no_tool_calls(self):
        agent = self._make_agent(llm_responses=[
            {"content": "根据资料显示，答案是42。", "tool_calls": None},
        ])
        answer = agent.run("答案是多少？")
        assert "42" in answer

    def test_run_calls_tool_when_model_requests(self):
        agent = self._make_agent(llm_responses=[
            {
                "content": None,
                "tool_calls": [{"id": "c1", "name": "search_docs", "arguments": '{"query":"答案"}'}],
            },
            {"content": "根据检索结果，答案是42。", "tool_calls": None},
        ])
        answer = agent.run("答案是多少？")
        assert agent._tools.execute.called
        assert "42" in answer

    def test_max_iterations_prevents_infinite_loop(self):
        tool_response = {
            "content": None,
            "tool_calls": [{"id": "c1", "name": "search_docs", "arguments": '{"query":"x"}'}],
        }
        agent = self._make_agent(llm_responses=[tool_response] * 20)
        answer = agent.run("问题", max_iterations=3)
        assert agent._tools.execute.call_count <= 3
