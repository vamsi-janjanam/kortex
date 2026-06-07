import json
import os

import anthropic

EXTRACTION_PROMPT = """Extract named entities from the following text. Return a JSON array of objects with:
- "name": entity name (string)
- "type": one of Service, API, Team, Person, Rule, Concept, Other
- "description": brief description (1 sentence max)

Text:
{text}

Return ONLY valid JSON. Example: [{{"name": "PaymentsAPI", "type": "API", "description": "REST API for processing payments"}}]"""


class EntityExtractor:
    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        self.model = model

    def extract(self, text: str) -> list[dict]:
        if not text.strip():
            return []

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(text=text[:3000])}],
            )
            raw = message.content[0].text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except (json.JSONDecodeError, IndexError, anthropic.APIError):
            return []
