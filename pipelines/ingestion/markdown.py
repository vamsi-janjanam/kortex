from pathlib import Path

from pipelines.ingestion.base import BaseConnector, RawChunk


class MarkdownConnector(BaseConnector):
    def ingest(self, source: str) -> list[RawChunk]:
        path = Path(source)
        if path.exists():
            text = path.read_text(encoding="utf-8")
        elif source.startswith("http"):
            import httpx
            response = httpx.get(source, timeout=30)
            response.raise_for_status()
            text = response.text
        else:
            text = source  # treat as raw text

        chunks = self._split_text(text)
        return [
            RawChunk(text=chunk, metadata={"source": source})
            for chunk in chunks
            if chunk.strip()
        ]
