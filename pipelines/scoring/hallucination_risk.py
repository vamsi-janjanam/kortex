class HallucinationRiskScorer:
    """Rule-based hallucination risk score combining existing quality signals.

    This is intentionally simple — a weighted heuristic, not an ML model.
    The weights reflect how directly each signal predicts hallucination risk:
      - freshness (0.4): stale content is the leading indicator that an LLM may
        answer with outdated facts, since the model has no way to know the
        information has changed.
      - trust (0.3): low-trust sources (e.g. Slack chatter) are more likely to
        contain unverified or informal claims that don't hold up.
      - conflict_risk (0.3): a direct signal — if this chunk already conflicts
        with another chunk, answers grounded in it are likely to be wrong for
        at least one of the conflicting claims.
    """

    FRESHNESS_WEIGHT = 0.4
    TRUST_WEIGHT = 0.3
    CONFLICT_WEIGHT = 0.3

    def score(
        self, freshness_score: float, trust_score: float, conflict_risk: float
    ) -> float:
        risk = (
            self.FRESHNESS_WEIGHT * (1 - freshness_score)
            + self.TRUST_WEIGHT * (1 - trust_score)
            + self.CONFLICT_WEIGHT * conflict_risk
        )
        return max(0.0, min(1.0, round(risk, 4)))
