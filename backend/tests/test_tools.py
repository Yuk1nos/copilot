import pytest
from src.tools import build_tool_definitions, ToolRegistry
from src.chroma_store import ChromaStore


class TestToolDefinitions:
    def test_build_returns_openai_format(self):
        tools = build_tool_definitions()
        assert len(tools) == 3
        assert tools[0]["type"] == "function"
        assert "name" in tools[0]["function"]
        assert "parameters" in tools[0]["function"]

    def test_all_tools_have_descriptions(self):
        tools = build_tool_definitions()
        names = [t["function"]["name"] for t in tools]
        assert "search_docs" in names
        assert "search_more" in names
        assert "generate_summary" in names


class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        import chromadb
        store = ChromaStore(client=chromadb.Client(), collection_name="test_tools_registry")
        return ToolRegistry(chroma_store=store, llm=None)

    def test_execute_search_docs(self, registry):
        result = registry.execute("search_docs", '{"query": "test"}')
        assert isinstance(result, str)

    def test_execute_unknown_tool_returns_error(self, registry):
        result = registry.execute("nonexistent", "{}")
        result_lower = result.lower()
        assert "error" in result_lower or "unknown" in result_lower
