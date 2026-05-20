from unittest.mock import MagicMock
from src.workflows import IngestWorkflow
from src.models import Document


class TestIngestWorkflow:
    def _make_workflow(self):
        db = MagicMock()
        parser = MagicMock()
        parser.parse.return_value = "这是解析后的文本内容"
        splitter = MagicMock()
        splitter.split.return_value = ["chunk1", "chunk2"]
        embedder = MagicMock()
        embedder.embed_batch.return_value = [[0.1] * 384, [0.2] * 384]
        chroma = MagicMock()
        chroma.add.return_value = ["emb1", "emb2"]

        return IngestWorkflow(db=db, parser=parser, splitter=splitter, embedder=embedder, chroma_store=chroma)

    def test_ingest_processes_document(self):
        wf = self._make_workflow()
        doc = Document(filename="test.txt", mime_type="text/plain")
        wf.run(doc, "/tmp/test.txt")

        assert wf._db.insert_document.called
        assert wf._parser.parse.called
        assert wf._splitter.split.called
        assert wf._embedder.embed_batch.called
        assert wf._chroma.add.called
        assert wf._db.update_document.called

    def test_ingest_returns_document(self):
        wf = self._make_workflow()
        doc = Document(filename="t.txt", mime_type="text/plain")
        result = wf.run(doc, "/tmp/t.txt")
        assert result == doc

    def test_ingest_raises_on_parse_error(self):
        wf = self._make_workflow()
        wf._parser.parse.side_effect = Exception("parse failed")
        doc = Document(filename="bad.pdf", mime_type="application/pdf")
        try:
            wf.run(doc, "/tmp/bad.pdf")
        except Exception as e:
            assert "parse failed" in str(e)
        assert wf._db.insert_document.called
