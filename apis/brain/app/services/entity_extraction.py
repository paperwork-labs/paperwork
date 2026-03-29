"""Entity extraction — extract named entities from text using GPT-4o-mini.

D5: Entity graph provides the 4th retrieval path (weight 0.15).
Entities include: people, organizations, products, decisions (D##), tasks (P#.#).
"""

import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


@dataclass
class ExtractedEntity:
    """A single extracted entity."""

    name: str
    entity_type: str
    properties: dict


EXTRACTION_PROMPT = """Extract named entities from the text below. Return a JSON array.

Entity types to extract:
- person: People mentioned by name
- organization: Companies, teams, agencies (e.g., IRS, Paperwork Labs)
- product: Products or services (e.g., FileFree, LaunchFree, TurboTax)
- decision: Design decisions in D## format (e.g., D1, D47)
- task: Task references in P#.# format (e.g., P11.4, P7.12)
- technology: Technologies, frameworks, tools (e.g., FastAPI, PostgreSQL, n8n)
- concept: Key concepts or terms (e.g., MeF transmitter, hybrid retrieval)

For each entity, provide:
- name: The entity name as it appears in the text
- entity_type: One of the types above
- properties: Additional context (optional)

Text to analyze:
{text}

Return ONLY a JSON array, no other text. Example:
[
  {"name": "FileFree", "entity_type": "product", "properties": {"domain": "filefree.ai"}},
  {"name": "D47", "entity_type": "decision", "properties": {"topic": "Community Growth Flywheel"}}
]
"""


async def extract_entities(text: str) -> list[ExtractedEntity]:
    """Extract entities from text using GPT-4o-mini.

    Cost: ~$0.0003 per extraction (150 input + 100 output tokens avg).
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.debug("OPENAI_API_KEY not set, using regex fallback")
        return _regex_extract_entities(text)

    if len(text) > 4000:
        text = text[:4000]

    try:
        client = _get_http_client()
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": EXTRACTION_PROMPT.format(text=text)}],
                "temperature": 0.1,
                "max_tokens": 500,
            },
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]

        entities_data = json.loads(content)
        entities = [
            ExtractedEntity(
                name=e["name"],
                entity_type=e["entity_type"],
                properties=e.get("properties", {}),
            )
            for e in entities_data
        ]
        logger.debug("Extracted %d entities via GPT-4o-mini", len(entities))
        return entities
    except json.JSONDecodeError:
        logger.warning("Failed to parse entity extraction response as JSON")
        return _regex_extract_entities(text)
    except Exception:
        logger.warning("Entity extraction failed", exc_info=True)
        return _regex_extract_entities(text)


def _regex_extract_entities(text: str) -> list[ExtractedEntity]:
    """Fallback: extract entities using regex patterns.

    Extracts:
    - D## decision references
    - P#.# task references
    - Known product names
    """
    entities: list[ExtractedEntity] = []

    decision_pattern = r"\bD(\d{1,3})\b"
    for match in re.finditer(decision_pattern, text):
        entities.append(
            ExtractedEntity(
                name=f"D{match.group(1)}",
                entity_type="decision",
                properties={},
            )
        )

    task_pattern = r"\bP(\d{1,2})\.(\d{1,2}[a-z]?)\b"
    for match in re.finditer(task_pattern, text):
        entities.append(
            ExtractedEntity(
                name=f"P{match.group(1)}.{match.group(2)}",
                entity_type="task",
                properties={},
            )
        )

    known_products = ["FileFree", "LaunchFree", "Distill", "Trinkets", "Brain"]
    for product in known_products:
        if product in text:
            entities.append(
                ExtractedEntity(
                    name=product,
                    entity_type="product",
                    properties={},
                )
            )

    known_orgs = ["Paperwork Labs", "IRS", "Column Tax", "TaxAudit"]
    for org in known_orgs:
        if org in text:
            entities.append(
                ExtractedEntity(
                    name=org,
                    entity_type="organization",
                    properties={},
                )
            )

    seen = set()
    unique_entities = []
    for e in entities:
        key = (e.name, e.entity_type)
        if key not in seen:
            seen.add(key)
            unique_entities.append(e)

    return unique_entities


async def upsert_entity(
    db,
    organization_id: str,
    entity: ExtractedEntity,
) -> int | None:
    """Upsert an entity into the database.

    Returns the entity ID.
    """
    from sqlalchemy import text as sql_text

    try:
        result = await db.execute(
            sql_text("""
                INSERT INTO agent_entities (organization_id, name, entity_type, properties)
                VALUES (:org_id, :name, :entity_type, :properties)
                ON CONFLICT (organization_id, name, entity_type)
                DO UPDATE SET
                    mention_count = agent_entities.mention_count + 1,
                    last_seen = NOW()
                RETURNING id
            """),
            {
                "org_id": organization_id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "properties": json.dumps(entity.properties),
            },
        )
        row = result.fetchone()
        return row[0] if row else None
    except Exception:
        logger.warning("Failed to upsert entity %s", entity.name, exc_info=True)
        return None


async def link_entity_to_episode(
    db,
    episode_id: int,
    entity_id: int,
) -> None:
    """Create a link between an episode and an entity.

    Note: Requires episode_entities junction table (add in migration).
    For now, store in episode metadata.
    """
    pass
