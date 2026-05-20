from src.models import Document, DocStatus


class TestDocument:
    def test_creates_document_with_defaults(self):
        doc = Document(
            filename="test.pdf",
            mime_type="application/pdf",
        )
        assert doc.status == DocStatus.UPLOADED
        assert doc.char_count == 0
        assert doc.chunk_count == 0

    def test_to_dict_serializes_status(self):
        doc = Document(filename="a.txt", mime_type="text/plain", status=DocStatus.INDEXED)
        d = doc.to_dict()
        assert d["status"] == "indexed"
