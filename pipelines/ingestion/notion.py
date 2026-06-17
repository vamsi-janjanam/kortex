"""Notion source connector — ingests a Notion page (and its child blocks).

Uses ``notion-client`` to page through a page/database's block children,
flattens supported block types to plain text, then chunks via the inherited
splitter. Emits one ``RawChunk`` per split. ``source`` is a Notion page or
database ID.
"""

from __future__ import annotations

from app.config import settings
from pipelines.ingestion.base import BaseConnector, RawChunk

# Block types whose ``rich_text`` we treat as readable content.
_TEXT_BLOCK_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "toggle",
    "quote",
    "callout",
    "code",
}


class NotionConnector(BaseConnector):
    """Ingest the text content of a Notion page."""

    def _client(self):
        """Instantiate the Notion client (isolated for test monkeypatching)."""
        token = settings.notion_token
        if not token:
            raise ValueError("NotionConnector requires settings.notion_token to be set")
        from notion_client import Client

        return Client(auth=token)

    @staticmethod
    def _block_text(block: dict) -> str:
        """Extract plain text from a single Notion block."""
        block_type = block.get("type")
        if block_type not in _TEXT_BLOCK_TYPES:
            return ""
        payload = block.get(block_type) or {}
        rich_text = payload.get("rich_text") or []
        return "".join(rt.get("plain_text", "") for rt in rich_text).strip()

    def _collect_text(self, client, block_id: str) -> list[str]:
        """Walk block children (paginated) and collect their plain text."""
        lines: list[str] = []
        cursor = None
        while True:
            resp = client.blocks.children.list(block_id=block_id, start_cursor=cursor)
            for block in resp.get("results", []):
                text = self._block_text(block)
                if text:
                    lines.append(text)
                # Recurse into nested blocks (toggles, list items, etc.).
                if block.get("has_children"):
                    child_id = block.get("id")
                    if child_id:
                        lines.extend(self._collect_text(client, child_id))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
            if not cursor:
                break
        return lines

    def ingest(self, source: str) -> list[RawChunk]:
        client = self._client()

        lines = self._collect_text(client, source)
        text = "\n".join(lines).strip()
        if not text:
            return []

        chunks: list[RawChunk] = []
        for piece in self._split_text(text):
            if not piece.strip():
                continue
            chunks.append(
                RawChunk(
                    text=piece,
                    metadata={
                        "source": source,
                        "page_id": source,
                    },
                )
            )
        return chunks
