"""Unit tests for the hallucination risk scorer — no external services needed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_hallucination_risk_low_for_fresh_trusted_no_conflict():
    from pipelines.scoring.hallucination_risk import HallucinationRiskScorer

    scorer = HallucinationRiskScorer()
    score = scorer.score(freshness_score=1.0, trust_score=1.0, conflict_risk=0.0)
    assert score == 0.0


def test_hallucination_risk_high_for_stale_untrusted_conflicting():
    from pipelines.scoring.hallucination_risk import HallucinationRiskScorer

    scorer = HallucinationRiskScorer()
    score = scorer.score(freshness_score=0.0, trust_score=0.0, conflict_risk=1.0)
    assert score == 1.0


def test_hallucination_risk_clamped_to_unit_range():
    from pipelines.scoring.hallucination_risk import HallucinationRiskScorer

    scorer = HallucinationRiskScorer()
    for freshness, trust, conflict in [
        (1.0, 1.0, 1.0),
        (0.0, 0.0, 0.0),
        (0.5, 0.5, 0.5),
        (2.0, -1.0, 0.5),
    ]:
        score = scorer.score(freshness, trust, conflict)
        assert 0.0 <= score <= 1.0


def test_hallucination_risk_monotonic_in_freshness():
    from pipelines.scoring.hallucination_risk import HallucinationRiskScorer

    scorer = HallucinationRiskScorer()
    high_freshness = scorer.score(
        freshness_score=1.0, trust_score=0.8, conflict_risk=0.2
    )
    low_freshness = scorer.score(
        freshness_score=0.0, trust_score=0.8, conflict_risk=0.2
    )
    assert low_freshness > high_freshness


def test_hallucination_risk_monotonic_in_trust():
    from pipelines.scoring.hallucination_risk import HallucinationRiskScorer

    scorer = HallucinationRiskScorer()
    high_trust = scorer.score(freshness_score=0.8, trust_score=1.0, conflict_risk=0.2)
    low_trust = scorer.score(freshness_score=0.8, trust_score=0.0, conflict_risk=0.2)
    assert low_trust > high_trust


def test_hallucination_risk_monotonic_in_conflict_risk():
    from pipelines.scoring.hallucination_risk import HallucinationRiskScorer

    scorer = HallucinationRiskScorer()
    low_conflict = scorer.score(freshness_score=0.8, trust_score=0.8, conflict_risk=0.0)
    high_conflict = scorer.score(
        freshness_score=0.8, trust_score=0.8, conflict_risk=1.0
    )
    assert high_conflict > low_conflict


def test_hallucination_risk_weighted_formula():
    from pipelines.scoring.hallucination_risk import HallucinationRiskScorer

    scorer = HallucinationRiskScorer()
    # 0.4 * (1 - 0.5) + 0.3 * (1 - 0.5) + 0.3 * 0.5 = 0.2 + 0.15 + 0.15 = 0.5
    score = scorer.score(freshness_score=0.5, trust_score=0.5, conflict_risk=0.5)
    assert score == 0.5
