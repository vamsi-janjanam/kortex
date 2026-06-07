from pathlib import Path

from pipelines.ingestion.base import BaseConnector, RawChunk


class PDFConnector(BaseConnector):
    def ingest(self, source: str) -> list[RawChunk]:
        from pypdf import PdfReader

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {source}")

        reader = PdfReader(str(path))
        full_text = "\n\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()

        if not full_text:
            return []

        chunks = self._split_text(full_text)
        return [
            RawChunk(text=chunk, metadata={"source": source, "page_count": len(reader.pages)})
            for chunk in chunks
            if chunk.strip()
        ]
