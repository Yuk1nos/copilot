from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
from datetime import datetime, timezone


class DocStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    INDEXED = "indexed"
    ERROR = "error"


@dataclass
class Document:
    filename: str
    mime_type: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    char_count: int = 0
    chunk_count: int = 0
    status: DocStatus = DocStatus.UPLOADED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d
