BASE_TRUST: dict[str, float] = {
    "github": 0.90,
    "pdf": 0.80,
    "confluence": 0.75,
    "notion": 0.75,
    "jira": 0.65,
    "markdown": 0.70,
    "slack": 0.55,
    "other": 0.50,
}


class TrustScorer:
    def score(self, source_type: str, consistency_multiplier: float = 1.0) -> float:
        base = BASE_TRUST.get(source_type, 0.50)
        return max(0.0, min(1.0, round(base * consistency_multiplier, 4)))
