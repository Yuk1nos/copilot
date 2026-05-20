from pathlib import Path


class DocumentParser:
    def parse(self, filepath: str) -> str:
        path = Path(filepath)
        suffix = path.suffix.lower()

        if suffix == ".txt":
            return path.read_text(encoding="utf-8")
        elif suffix == ".pdf":
            return self._parse_pdf(filepath)
        elif suffix == ".docx":
            return self._parse_docx(filepath)
        else:
            return path.read_text(encoding="utf-8")

    def _parse_pdf(self, filepath: str) -> str:
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                texts = [p.extract_text() or "" for p in pdf.pages]
            return "\n".join(texts)
        except ImportError:
            raise RuntimeError("pdfplumber not installed")

    def _parse_docx(self, filepath: str) -> str:
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(filepath)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise RuntimeError("python-docx not installed")

    def guess_mime_type(self, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        mapping = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain",
            ".md": "text/markdown",
        }
        return mapping.get(suffix, "application/octet-stream")
