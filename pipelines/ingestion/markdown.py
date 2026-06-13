from pathlib import Path

from pipelines.ingestion.base import BaseConnector, RawChunk
from pipelines.ingestion.security import validate_file_path, validate_url


class MarkdownConnector(BaseConnector):
    def ingest(self, source: str) -> list[RawChunk]:
        if source.startswith("http"):
            import httpx

            validate_url(source)
            response = httpx.get(source, timeout=30)
            response.raise_for_status()
            text = response.text
        elif Path(source).exists():
            path = validate_file_path(source)
            text = path.read_text(encoding="utf-8")
        else:
            text = source  # treat as raw text

        chunks = self._split_text(text)
        return [
            RawChunk(text=chunk, metadata={"source": source})
            for chunk in chunks
            if chunk.strip()
        ]
