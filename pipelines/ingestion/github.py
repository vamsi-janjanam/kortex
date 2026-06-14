"""GitHub source connector — ingests a repository's CODEBASE (source files).

Uses PyGithub to fetch the default-branch git tree recursively and emits one
``RawChunk`` per split of each allowlisted text/code file. Binary, oversized,
and non-text files are skipped.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.config import settings
from pipelines.ingestion.base import BaseConnector, RawChunk

# Allowlisted code/text file extensions (lowercase, with leading dot).
_ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".md",
    ".mdx",
    ".txt",
    ".rst",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".rb",
    ".php",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cs",
    ".swift",
    ".sh",
    ".bash",
    ".sql",
    ".html",
    ".css",
    ".scss",
    ".xml",
    ".vue",
    ".svelte",
    ".dockerfile",
}

# Skip files larger than ~1MB (decoded git blobs).
_MAX_FILE_BYTES = 1_000_000


class GitHubConnector(BaseConnector):
    """Ingest the source files of a GitHub repository."""

    @staticmethod
    def _normalize_source(source: str) -> str:
        """Normalize ``source`` to ``owner/repo``.

        Accepts ``owner/repo`` directly or a GitHub URL such as
        ``https://github.com/owner/repo`` (optionally with ``.git`` suffix or
        trailing path segments).
        """
        candidate = source.strip()
        if "://" in candidate or candidate.startswith("git@"):
            if candidate.startswith("git@"):
                # git@github.com:owner/repo.git
                _, _, path = candidate.partition(":")
            else:
                path = urlparse(candidate).path
            parts = [p for p in path.split("/") if p]
        else:
            parts = [p for p in candidate.split("/") if p]

        if len(parts) < 2:
            raise ValueError(
                f"Invalid GitHub source '{source}': expected 'owner/repo' or a "
                "GitHub repository URL"
            )

        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[: -len(".git")]
        return f"{owner}/{repo}"

    @staticmethod
    def _is_allowed_path(path: str) -> bool:
        lower = path.lower()
        # Dotfiles / special names without an extension we still want.
        basename = lower.rsplit("/", 1)[-1]
        if basename in {"dockerfile", "makefile"}:
            return True
        dot = lower.rfind(".")
        if dot == -1:
            return False
        return lower[dot:] in _ALLOWED_EXTENSIONS

    def _client(self):
        """Instantiate the PyGithub client (isolated for test monkeypatching)."""
        from github import Github

        token = settings.github_token
        if not token:
            raise ValueError(
                "GitHubConnector requires settings.github_token to be set"
            )
        return Github(token)

    def ingest(self, source: str) -> list[RawChunk]:
        full_name = self._normalize_source(source)

        client = self._client()
        repo = client.get_repo(full_name)
        default_branch = repo.default_branch

        tree = repo.get_git_tree(default_branch, recursive=True)

        chunks: list[RawChunk] = []
        for element in tree.tree:
            if getattr(element, "type", None) != "blob":
                continue
            path = element.path
            if not self._is_allowed_path(path):
                continue
            if (element.size or 0) > _MAX_FILE_BYTES:
                continue

            try:
                blob = repo.get_contents(path, ref=default_branch)
            except Exception:
                continue

            raw = getattr(blob, "decoded_content", None)
            if raw is None:
                continue
            if len(raw) > _MAX_FILE_BYTES:
                continue

            try:
                text = raw.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                # Binary / non-UTF-8 content — skip.
                continue

            if not text.strip():
                continue

            for piece in self._split_text(text):
                if not piece.strip():
                    continue
                chunks.append(
                    RawChunk(
                        text=piece,
                        metadata={
                            "source": source,
                            "repo": full_name,
                            "file_path": path,
                            "ref": default_branch,
                        },
                    )
                )

        return chunks
