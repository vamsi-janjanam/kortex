"""Slack source connector — ingests a channel's message history.

Uses ``slack_sdk.WebClient`` to page through ``conversations_history`` and pull
``conversations_replies`` for threaded messages. Emits one ``RawChunk`` per
non-empty message.
"""

from __future__ import annotations

from app.config import settings
from pipelines.ingestion.base import BaseConnector, RawChunk


class SlackConnector(BaseConnector):
    """Ingest the message history of a Slack channel."""

    def _client(self):
        """Instantiate the Slack WebClient (isolated for test monkeypatching)."""
        token = settings.slack_bot_token
        if not token:
            raise ValueError(
                "SlackConnector requires settings.slack_bot_token to be set"
            )
        from slack_sdk import WebClient

        return WebClient(token=token)

    @staticmethod
    def _resolve_channel_id(client, source: str) -> str:
        """Resolve ``source`` to a channel ID.

        A leading ``#`` (or a plain name) is looked up via
        ``conversations_list``; anything else is treated as an ID already.
        """
        if not source.startswith("#"):
            return source

        name = source[1:]
        cursor = None
        while True:
            resp = client.conversations_list(
                cursor=cursor, limit=200, types="public_channel,private_channel"
            )
            for channel in resp.get("channels", []):
                if channel.get("name") == name:
                    return channel["id"]
            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break

        raise ValueError(f"Slack channel not found: {source}")

    @staticmethod
    def _is_noise(msg: dict) -> bool:
        """True for messages we should skip (join/leave noise, empty text)."""
        if msg.get("subtype") in {
            "channel_join",
            "channel_leave",
            "channel_topic",
            "channel_purpose",
            "channel_name",
            "bot_add",
            "bot_remove",
        }:
            return True
        return not (msg.get("text") or "").strip()

    def _emit(self, source: str, channel_id: str, msg: dict) -> list[RawChunk]:
        text = msg["text"]
        metadata = {
            "source": source,
            "channel": channel_id,
            "user": msg.get("user") or msg.get("bot_id"),
            "ts": msg.get("ts"),
            "thread_ts": msg.get("thread_ts"),
        }
        pieces = self._split_text(text) if len(text) > 512 else [text]
        return [
            RawChunk(text=piece, metadata=dict(metadata))
            for piece in pieces
            if piece.strip()
        ]

    def ingest(self, source: str) -> list[RawChunk]:
        client = self._client()
        channel_id = self._resolve_channel_id(client, source)

        chunks: list[RawChunk] = []
        seen_ts: set = set()

        cursor = None
        while True:
            resp = client.conversations_history(
                channel=channel_id, cursor=cursor, limit=200
            )
            for msg in resp.get("messages", []):
                ts = msg.get("ts")
                if ts and ts not in seen_ts and not self._is_noise(msg):
                    seen_ts.add(ts)
                    chunks.extend(self._emit(source, channel_id, msg))

                # Pull thread replies for the thread parent.
                thread_ts = msg.get("thread_ts")
                reply_count = msg.get("reply_count", 0)
                if thread_ts and (reply_count or msg.get("reply_users_count")):
                    rcursor = None
                    while True:
                        rresp = client.conversations_replies(
                            channel=channel_id,
                            ts=thread_ts,
                            cursor=rcursor,
                            limit=200,
                        )
                        for reply in rresp.get("messages", []):
                            rts = reply.get("ts")
                            if (
                                rts
                                and rts not in seen_ts
                                and not self._is_noise(reply)
                            ):
                                seen_ts.add(rts)
                                chunks.extend(
                                    self._emit(source, channel_id, reply)
                                )
                        rcursor = (
                            rresp.get("response_metadata") or {}
                        ).get("next_cursor")
                        if not rcursor:
                            break

            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break

        return chunks
