from datetime import datetime, timezone


# Days until score hits 0 by source type
DECAY_DAYS: dict[str, float] = {
    "slack": 30,
    "jira": 90,
    "confluence": 180,
    "markdown": 365,
    "pdf": 365,
    "github": 365,
    "notion": 180,
    "other": 180,
}


class FreshnessScorer:
    def score(self, ingested_at: datetime, source_type: str) -> float:
        decay = DECAY_DAYS.get(source_type, 180)
        now = datetime.now(timezone.utc)
        if ingested_at.tzinfo is None:
            ingested_at = ingested_at.replace(tzinfo=timezone.utc)
        age_days = (now - ingested_at).days
        raw = 1.0 - (age_days / decay)
        return max(0.0, min(1.0, round(raw, 4)))
