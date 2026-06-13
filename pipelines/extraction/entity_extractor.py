import json
import os

import anthropic

EXTRACTION_PROMPT = """Extract named entities and relationships between them from the following text.

Return a JSON object with two keys:
- "entities": a JSON array of objects with:
  - "name": entity name (string)
  - "type": one of Service, API, Team, Person, Rule, Concept, Other
  - "description": brief description (1 sentence max)
- "relationships": a JSON array of objects describing relationships between the extracted entities, with:
  - "from": the "name" of the source entity (must match an entity in "entities")
  - "to": the "name" of the target entity (must match an entity in "entities")
  - "type": one of owns, uses, depends_on, calls, inherits, references, other
  - "confidence": a number between 0.0 and 1.0 indicating confidence in this relationship

Text:
{text}

Return ONLY valid JSON. Example:
{{"entities": [{{"name": "PaymentsAPI", "type": "API", "description": "REST API for processing payments"}}, {{"name": "Payments Team", "type": "Team", "description": "Team that owns the Payments API"}}], "relationships": [{{"from": "Payments Team", "to": "PaymentsAPI", "type": "owns", "confidence": 0.9}}]}}"""


class EntityExtractor:
    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        self.model = model

    def extract(self, text: str) -> dict:
        empty: dict = {"entities": [], "relationships": []}

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
            return {
                "entities": parsed.get("entities", []) or [],
                "relationships": parsed.get("relationships", []) or [],
            }
        except (json.JSONDecodeError, IndexError, anthropic.APIError, AttributeError):
            return empty
