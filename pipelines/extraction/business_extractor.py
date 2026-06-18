import json
import os

import anthropic

EXTRACTION_PROMPT = """Extract first-class business logic (decisions, policies, processes, constraints, metrics) from the following text, together with the rationale (the "why") behind each.

Return a JSON object with one key:
- "rules": a JSON array of objects with:
  - "name": a short human title for the rule (string)
  - "type": one of decision, policy, process, constraint, metric
  - "statement": what the rule/decision IS (string)
  - "rationale": the WHY — the business reasoning behind it ("" if not stated)
  - "confidence": a number between 0.0 and 1.0 indicating confidence in this rule

Text:
{text}

Return ONLY valid JSON. Example:
{{"rules": [{{"name": "Auth uses OAuth 2.0 JWT", "type": "decision", "statement": "All API authentication uses OAuth 2.0 JWT tokens.", "rationale": "API keys were too hard to rotate and revoke.", "confidence": 0.9}}]}}"""


class BusinessRuleExtractor:
    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        self.model = model

    def extract(self, text: str) -> dict:
        empty: dict = {"rules": []}

        if not text.strip():
            return empty

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": EXTRACTION_PROMPT.format(text=text[:3000]),
                    }
                ],
            )
            raw = message.content[0].text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return empty
            return {"rules": parsed.get("rules", []) or []}
        except (json.JSONDecodeError, IndexError, anthropic.APIError, AttributeError):
            return empty
