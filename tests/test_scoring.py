"""Unit tests for scoring pipeline — no external services needed."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_freshness_score_new_document():
    from pipelines.scoring.freshness import FreshnessScorer
    scorer = FreshnessScorer()
    now = datetime.now(timezone.utc)
    score = scorer.score(now, "pdf")
    assert score == pytest.approx(1.0, abs=0.01)


def test_freshness_score_old_document():
    from pipelines.scoring.freshness import FreshnessScorer
    scorer = FreshnessScorer()
    two_years_ago = datetime.now(timezone.utc) - timedelta(days=730)
    score = scorer.score(two_years_ago, "pdf")
    assert score == 0.0


def test_freshness_score_half_decay():
    from pipelines.scoring.freshness import FreshnessScorer
    scorer = FreshnessScorer()
    # pdf decay = 365 days; half = 182.5 days old → score ~0.5
    half_life = datetime.now(timezone.utc) - timedelta(days=182)
    score = scorer.score(half_life, "pdf")
    assert 0.45 < score < 0.55


def test_freshness_slack_decays_faster():
    from pipelines.scoring.freshness import FreshnessScorer
    scorer = FreshnessScorer()
    two_months_ago = datetime.now(timezone.utc) - timedelta(days=60)
    slack_score = scorer.score(two_months_ago, "slack")
    pdf_score = scorer.score(two_months_ago, "pdf")
    assert slack_score < pdf_score


def test_trust_score_github_highest():
    from pipelines.scoring.trust import TrustScorer
    scorer = TrustScorer()
    assert scorer.score("github") > scorer.score("slack")
    assert scorer.score("github") > scorer.score("pdf")


def test_trust_score_clamped():
    from pipelines.scoring.trust import TrustScorer
    scorer = TrustScorer()
    for source_type in ["github", "pdf", "slack", "confluence", "other"]:
        score = scorer.score(source_type)
        assert 0.0 <= score <= 1.0

