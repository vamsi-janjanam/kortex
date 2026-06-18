"""GitHub source connector — ingests a repository's CODEBASE and DISCUSSION.

Uses PyGithub to fetch the default-branch git tree recursively and emits one
``RawChunk`` per split of each allowlisted text/code file. Binary, oversized,
and non-text files are skipped.

It also ingests the repository's issues and pull requests together with their
comment threads — the place where design decisions and the "why" get argued —
emitting one ``RawChunk`` per split of each combined discussion block.
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

# Caps to avoid runaway ingestion of issue/PR discussion threads.
_MAX_ISSUES = 100
_MAX_COMMENTS_PER_ISSUE = 50


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
        token = settings.github_token
        if not token:
            raise ValueError(
                "GitHubConnector requires settings.github_token to be set"
            )
        from github import Github

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

        chunks.extend(self._ingest_issues(repo, source, full_name))

        return chunks

    def _ingest_issues(
        self, repo, source: str, full_name: str
    ) -> list[RawChunk]:
        """Ingest issues and pull requests with their comment threads.

        In the GitHub API, pull requests are returned as issues; a PR is
        detected via a truthy ``pull_request`` attribute. Each issue/PR becomes
        one combined text block (title + body + comments) that is split into one
        ``RawChunk`` per piece.

        Defensive: if ``repo.get_issues`` is missing or raises, returns ``[]``
        so code-file ingestion is never broken.
        """
        chunks: list[RawChunk] = []
        try:
            issues = repo.get_issues(state="all")
        except Exception:
            return []

        try:
            for index, issue in enumerate(issues):
                if index >= _MAX_ISSUES:
                    break
                try:
                    is_pr = bool(getattr(issue, "pull_request", None))
                    title = issue.title or ""
                    body = issue.body or ""

                    comment_bodies = []
                    for comment_index, comment in enumerate(
                        issue.get_comments()
                    ):
                        if comment_index >= _MAX_COMMENTS_PER_ISSUE:
                            break
                        comment_body = comment.body or ""
                        if comment_body:
                            comment_bodies.append(comment_body)

                    if not title and not body and not comment_bodies:
                        continue

                    text = title + "\n\n" + body
                    for comment_body in comment_bodies:
                        text += "\n\n--- comment ---\n" + comment_body

                    for piece in self._split_text(text):
                        if not piece.strip():
                            continue
                        chunks.append(
                            RawChunk(
                                text=piece,
                                metadata={
                                    "source": source,
                                    "repo": full_name,
                                    "content_type": (
                                        "pull_request" if is_pr else "issue"
                                    ),
                                    "number": issue.number,
                                    "title": issue.title,
                                    "state": issue.state,
                                },
                            )
                        )
                except Exception:
                    # Skip a bad issue and continue with the rest.
                    continue
        except Exception:
            return chunks

        return chunks
