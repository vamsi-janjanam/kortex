"""Unit tests for the GitHub source connector.

PyGithub is fully mocked — no live credentials and no network access. The
``settings.github_token`` attribute is set via monkeypatch.
"""

import pytest

from app.config import settings
from pipelines.ingestion.github import GitHubConnector


class _FakeTreeElement:
    def __init__(self, path, *, type="blob", size=100):
        self.path = path
        self.type = type
        self.size = size


class _FakeTree:
    def __init__(self, elements):
        self.tree = elements


class _FakeContent:
    def __init__(self, decoded_content):
        self.decoded_content = decoded_content


class _FakeRepo:
    def __init__(self, contents):
        self.default_branch = "main"
        self._contents = contents
        self._tree_elements = [
            _FakeTreeElement("app/main.py"),
            _FakeTreeElement("README.md"),
            _FakeTreeElement("logo.png"),  # disallowed extension
            _FakeTreeElement("assets/blob.bin", size=10),  # disallowed extension
            _FakeTreeElement("big.py", size=5_000_000),  # oversized
            _FakeTreeElement("subdir", type="tree"),  # not a blob
            _FakeTreeElement("data/binary.json"),  # decodes to non-utf8 -> skip
        ]

    def get_git_tree(self, ref, recursive=False):
        return _FakeTree(self._tree_elements)

    def get_contents(self, path, ref=None):
        return self._contents[path]


def _install_fake_github(monkeypatch, repo):
    """Monkeypatch GitHubConnector._client to return a fake client."""

    class _FakeClient:
        def get_repo(self, full_name):
            assert full_name == "octocat/hello"
            return repo

    monkeypatch.setattr(GitHubConnector, "_client", lambda self: _FakeClient())


@pytest.fixture
def fake_repo():
    return _FakeRepo(
        {
            "app/main.py": _FakeContent(b"print('hello world')\n"),
            "README.md": _FakeContent(b"# Title\n\nSome documentation body.\n"),
            "data/binary.json": _FakeContent(b"\xff\xfe\x00\x01"),  # invalid utf-8
        }
    )


def test_returns_list_of_rawchunks(monkeypatch, fake_repo):
    monkeypatch.setattr(settings, "github_token", "ghp_fake", raising=False)
    _install_fake_github(monkeypatch, fake_repo)

    chunks = GitHubConnector().ingest("octocat/hello")

    assert isinstance(chunks, list)
    assert chunks
    for chunk in chunks:
        assert set(chunk["metadata"].keys()) == {
            "source",
            "repo",
            "file_path",
            "ref",
        }
        assert chunk["text"].strip()
        assert chunk["metadata"]["repo"] == "octocat/hello"
        assert chunk["metadata"]["ref"] == "main"


def test_skips_binary_oversized_and_disallowed_files(monkeypatch, fake_repo):
    monkeypatch.setattr(settings, "github_token", "ghp_fake", raising=False)
    _install_fake_github(monkeypatch, fake_repo)

    chunks = GitHubConnector().ingest("octocat/hello")
    paths = {c["metadata"]["file_path"] for c in chunks}

    # Only the two valid allowlisted, utf-8, in-size-limit files survive.
    assert paths == {"app/main.py", "README.md"}
    assert "logo.png" not in paths
    assert "assets/blob.bin" not in paths
    assert "big.py" not in paths
    assert "data/binary.json" not in paths  # invalid utf-8 -> skipped


def test_empty_token_raises(monkeypatch):
    monkeypatch.setattr(settings, "github_token", "", raising=False)
    with pytest.raises(ValueError):
        GitHubConnector().ingest("octocat/hello")


def test_normalizes_github_url(monkeypatch, fake_repo):
    monkeypatch.setattr(settings, "github_token", "ghp_fake", raising=False)
    _install_fake_github(monkeypatch, fake_repo)

    chunks = GitHubConnector().ingest("https://github.com/octocat/hello.git")
    assert chunks
    assert chunks[0]["metadata"]["repo"] == "octocat/hello"


def test_invalid_source_raises():
    with pytest.raises(ValueError):
        GitHubConnector._normalize_source("not-a-repo")
