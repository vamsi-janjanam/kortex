from abc import ABC, abstractmethod
from typing import TypedDict


class RawChunk(TypedDict):
    text: str
    metadata: dict


class BaseConnector(ABC):
    """Base class for all source connectors."""

    @abstractmethod
    def ingest(self, source: str) -> list[RawChunk]:
        """Parse source and return a list of text chunks with metadata."""
        ...

    def _split_text(self, text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> list[str]:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_text(text)
