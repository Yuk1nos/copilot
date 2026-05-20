import pytest
from src.document_parser import DocumentParser


@pytest.fixture
def parser():
    return DocumentParser()


@pytest.fixture
def sample_txt(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("这是测试文本内容。\n用于文档解析验证。", encoding="utf-8")
    return str(f)


class TestDocumentParser:
    def test_parse_txt_returns_text(self, parser, sample_txt):
        text = parser.parse(sample_txt)
        assert "测试文本内容" in text
        assert "文档解析验证" in text

    def test_parse_returns_empty_string_for_empty_file(self, parser, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        text = parser.parse(str(f))
        assert text == ""

    def test_guess_mime_type(self, parser):
        assert parser.guess_mime_type("doc.pdf") == "application/pdf"
        assert parser.guess_mime_type("doc.docx") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert parser.guess_mime_type("doc.txt") == "text/plain"
