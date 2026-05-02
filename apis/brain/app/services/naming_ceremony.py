"""Naming ceremony service (WS-82 PR-2a).

medallion: ops

Called the FIRST time a persona is invoked and display_name IS NULL.
The persona picks its own name, tagline, and avatar emoji using its own
default_model. Result is written to the employees table immediately.

Flow:
  1. Build prompt from role_title
  2. Call default_model
  3. Parse "Name | tagline | emoji" response
  4. Validate against anti-cringe rules
  5. If invalid, re-prompt once with simpler instructions
  6. Write to DB and return NamingCeremonyResult
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.schemas.employee import NamingCeremonyResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.employee import Employee

logger = logging.getLogger(__name__)

NAMING_PROMPT = """You are about to start serving as {role_title}. Choose a display name for
yourself that the founder will actually call you in conversation. Reply with
exactly one line: Name | one-line tagline | single emoji.

NAMING RULES:
- Pick something that works as a first name you'd say out loud casually.
  ("Hey Mo, what's our burn?" sounds natural. "Hey Penny Pincher" does not.)
- Function-adjacent is good. Forced literal puns are cringe.
- Short. One word ideal, two max. Avoid titles or descriptors.

GOOD EXAMPLES (study these):
- Mo | Money moves, I track them | 💰
- Pixel | Every pixel is a decision | ✨
- Maverick | High conviction, tight stops | 🎯
- Sam | The forms file themselves eventually | 📋
- Banks | Three nines or I don't sleep | 📡
- Hedge | I stop the bleeding | 🛑
- Edge | Alpha is a verb | 📈
- Wire | Infrastructure is invisible until it isn't | ⚡

BAD EXAMPLES (do NOT pick names like these):
- Penny / Coin / Money Bags (forced literal puns)
- CFO Bob / Captain Code (title-as-name)
- Auntie Audit / Uncle Uptime (cringe alliterative)
- Anything you'd cringe to say to a real colleague out loud

Pick yours."""

RETRY_PROMPT = (
    "Your previous answer didn't pass the cringe filter — try again, simpler. One word ideal."
)

CRINGE_PATTERNS = [
    r"\b(captain|auntie|uncle|professor|doctor|dr\.)\b",
    r"\b(master|guru|wizard|ninja|rockstar)\b",
]


def validate_name(name: str, role_title: str) -> bool:
    """Return True if the name passes anti-cringe rules."""
    if len(name.split()) > 2:
        return False
    lower = name.lower()
    role_words = {w for w in role_title.lower().split() if len(w) > 3}
    if any(w in lower for w in role_words):
        return False
    return all(not re.search(pat, lower) for pat in CRINGE_PATTERNS)


def _parse_response(raw: str) -> NamingCeremonyResult | None:
    """Parse 'Name | tagline | emoji' format. Returns None if unparseable."""
    parts = [p.strip() for p in raw.strip().split("|")]
    if len(parts) != 3:
        return None
    name, tagline, emoji = parts
    if not name or not tagline or not emoji:
        return None
    return NamingCeremonyResult(display_name=name, tagline=tagline, avatar_emoji=emoji)


async def _call_model(model: str, prompt: str) -> str:
    """Call the LLM and return the raw text response."""
    import litellm  # type: ignore[import-untyped]

    response = await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=64,
        temperature=0.9,
    )
    content: str = response.choices[0].message.content or ""
    return content


async def run_naming_ceremony(
    employee: Employee,
    db: AsyncSession,
) -> NamingCeremonyResult:
    """Run the naming ceremony for a persona that has no display_name yet.

    Writes the result to the DB and returns a NamingCeremonyResult.
    Raises RuntimeError if both attempts fail validation.
    """
    prompt = NAMING_PROMPT.format(role_title=employee.role_title)

    raw = await _call_model(employee.default_model, prompt)
    result = _parse_response(raw)

    if result is None or not validate_name(result.display_name, employee.role_title):
        logger.warning(
            "Naming ceremony first attempt failed for %s (raw=%r). Re-prompting.",
            employee.slug,
            raw,
        )
        retry_raw = await _call_model(employee.default_model, RETRY_PROMPT)
        result = _parse_response(retry_raw)

        if result is None or not validate_name(result.display_name, employee.role_title):
            msg = (
                f"Naming ceremony failed for {employee.slug!r} after two attempts. "
                f"Last raw response: {retry_raw!r}"
            )
            raise RuntimeError(msg)

    # Persist to DB
    employee.display_name = result.display_name
    employee.tagline = result.tagline
    employee.avatar_emoji = result.avatar_emoji
    employee.named_at = datetime.now(UTC)
    employee.named_by_self = True
    await db.commit()
    await db.refresh(employee)

    logger.info(
        "Naming ceremony complete for %s: %s (%s) %s",
        employee.slug,
        result.display_name,
        result.tagline,
        result.avatar_emoji,
    )
    return result


async def get_or_name(slug: str, db: AsyncSession) -> Employee:
    """Return the Employee, running naming ceremony if display_name is not set."""
    from app.models.employee import Employee

    result = await db.execute(select(Employee).where(Employee.slug == slug))
    emp = result.scalar_one_or_none()
    if emp is None:
        msg = f"Employee '{slug}' not found"
        raise ValueError(msg)

    if emp.display_name is None:
        await run_naming_ceremony(emp, db)

    return emp
