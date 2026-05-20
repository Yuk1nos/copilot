from src.splitter import TextSplitter


class TestTextSplitter:
    def test_splits_text_into_chunks(self):
        text = "第一段内容。第二段内容。第三段内容。第四段内容。"
        splitter = TextSplitter(chunk_size=1)
        chunks = splitter.split(text)
        assert len(chunks) >= 2

    def test_each_chunk_within_size_limit(self):
        text = "测试。" * 500
        splitter = TextSplitter(chunk_size=200)
        chunks = splitter.split(text)
        for c in chunks:
            assert len(c) <= 200

    def test_empty_text_returns_empty_list(self):
        splitter = TextSplitter(chunk_size=100)
        assert splitter.split("") == []

    def test_text_shorter_than_chunk_size_returns_single_chunk(self):
        text = "短文本"
        splitter = TextSplitter(chunk_size=1000)
        chunks = splitter.split(text)
        assert len(chunks) == 1
        assert chunks[0] == "短文本"
