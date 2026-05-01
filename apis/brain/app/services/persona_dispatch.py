"""Persona dispatch domains and autonomy tiers for Brain Autopilot.

Defines which persona owns which file paths and task types,
with 4-tier autonomy levels controlling merge behaviour.

medallion: ops
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import TypedDict


class PersonaDispatchDomain(TypedDict):
    persona_id: str
    domain_patterns: list[str]
    autonomy_tier: int
    escalation_to: str


@dataclass(frozen=True, slots=True)
class DispatchResult:
    persona_id: str
    autonomy_tier: int
    escalation_to: str
    matched_pattern: str = ""


AUTONOMY_TIER_AUTO_MERGE = 1
AUTONOMY_TIER_AUTO_MERGE_WITH_REVIEW = 2
AUTONOMY_TIER_NEEDS_APPROVAL = 3
AUTONOMY_TIER_FOUNDER_ONLY = 4

DISPATCH_REGISTRY: dict[str, PersonaDispatchDomain] = {
    "engineer": PersonaDispatchDomain(
        persona_id="engineer",
        domain_patterns=[
            "apis/**",
            "packages/**",
            "apps/**",
            "infra/**",
            "Makefile",
            "docker-compose*.yml",
        ],
        autonomy_tier=AUTONOMY_TIER_NEEDS_APPROVAL,
        escalation_to="founder",
    ),
    "agent-ops": PersonaDispatchDomain(
        persona_id="agent-ops",
        domain_patterns=[
            "apis/brain/**",
            ".cursor/rules/**",
            "data/personas/**",
            "docs/skills/**",
        ],
        autonomy_tier=AUTONOMY_TIER_AUTO_MERGE_WITH_REVIEW,
        escalation_to="engineer",
    ),
    "ux-lead": PersonaDispatchDomain(
        persona_id="ux-lead",
        domain_patterns=[
            "apps/filefree/**",
            "apps/launchfree/**",
            "apps/distill/**",
            "apps/studio/**",
            "apps/trinkets/**",
            "packages/ui/**",
        ],
        autonomy_tier=AUTONOMY_TIER_NEEDS_APPROVAL,
        escalation_to="founder",
    ),
    "qa": PersonaDispatchDomain(
        persona_id="qa",
        domain_patterns=[
            "apis/*/tests/**",
            "apps/*/tests/**",
            "apps/**/*.test.ts",
            "apps/**/*.test.tsx",
            "packages/**/*.test.ts",
        ],
        autonomy_tier=AUTONOMY_TIER_AUTO_MERGE_WITH_REVIEW,
        escalation_to="engineer",
    ),
    "cfo": PersonaDispatchDomain(
        persona_id="cfo",
        domain_patterns=[
            "docs/finance/**",
            "docs/costs/**",
            "apis/brain/app/services/cost_*.py",
            "apis/brain/app/services/expense*.py",
            "apis/brain/app/services/bills.py",
            "apis/brain/app/services/vendors.py",
        ],
        autonomy_tier=AUTONOMY_TIER_NEEDS_APPROVAL,
        escalation_to="founder",
    ),
    "tax-domain": PersonaDispatchDomain(
        persona_id="tax-domain",
        domain_patterns=[
            "packages/data/tax/**",
            "packages/tax-engine/**",
            "apis/filefree/**",
        ],
        autonomy_tier=AUTONOMY_TIER_FOUNDER_ONLY,
        escalation_to="founder",
    ),
    "legal": PersonaDispatchDomain(
        persona_id="legal",
        domain_patterns=[
            "docs/legal/**",
            "docs/compliance/**",
            "packages/data/formation/**",
            "packages/data/compliance/**",
        ],
        autonomy_tier=AUTONOMY_TIER_FOUNDER_ONLY,
        escalation_to="founder",
    ),
    "growth": PersonaDispatchDomain(
        persona_id="growth",
        domain_patterns=[
            "docs/marketing/**",
            "docs/seo/**",
            "apps/*/src/app/(marketing)/**",
        ],
        autonomy_tier=AUTONOMY_TIER_NEEDS_APPROVAL,
        escalation_to="founder",
    ),
    "ops-engineer": PersonaDispatchDomain(
        persona_id="ops-engineer",
        domain_patterns=[
            "infra/**",
            ".github/**",
            "render.yaml",
            "vercel.json",
        ],
        autonomy_tier=AUTONOMY_TIER_AUTO_MERGE_WITH_REVIEW,
        escalation_to="engineer",
    ),
    "data-ops": PersonaDispatchDomain(
        persona_id="data-ops",
        domain_patterns=[
            "apis/brain/data/**",
            "docs/**",
            ".cursor/rules/**",
        ],
        autonomy_tier=AUTONOMY_TIER_AUTO_MERGE,
        escalation_to="agent-ops",
    ),
}

_TASK_TYPE_MAP: dict[str, str] = {
    "pr-review": "engineer",
    "cost-analysis": "cfo",
    "test-coverage": "qa",
    "ui-audit": "ux-lead",
    "tax-calculation": "tax-domain",
    "formation-filing": "legal",
    "seo-content": "growth",
    "deploy": "ops-engineer",
    "agent-config": "agent-ops",
    "data-update": "data-ops",
    "security-audit": "qa",
    "persona-tuning": "agent-ops",
}

_PRODUCT_PERSONA_MAP: dict[str, str] = {
    "filefree": "tax-domain",
    "launchfree": "legal",
    "distill": "engineer",
    "studio": "ux-lead",
    "trinkets": "ux-lead",
    "brain": "agent-ops",
}

_PRIORITY_ORDER: list[str] = [
    "tax-domain",
    "legal",
    "cfo",
    "qa",
    "data-ops",
    "agent-ops",
    "ops-engineer",
    "ux-lead",
    "growth",
    "engineer",
]

_DEFAULT_PERSONA = "engineer"


def _match_file_to_persona(
    filepath: str,
) -> DispatchResult | None:
    """Match a single file path against all registry patterns."""
    for persona_id in _PRIORITY_ORDER:
        domain: PersonaDispatchDomain | None = DISPATCH_REGISTRY.get(persona_id)
        if domain is None:
            continue
        for pattern in domain["domain_patterns"]:
            if fnmatch.fnmatch(filepath, pattern):
                return DispatchResult(
                    persona_id=domain["persona_id"],
                    autonomy_tier=domain["autonomy_tier"],
                    escalation_to=domain["escalation_to"],
                    matched_pattern=pattern,
                )
    return None


def select_persona_for_path(changed_files: list[str]) -> str:
    """Pick the best persona based on file path patterns.

    When multiple personas match different files, the highest-priority
    persona (earliest in _PRIORITY_ORDER) wins.
    """
    if not changed_files:
        return _DEFAULT_PERSONA

    best_priority = len(_PRIORITY_ORDER)
    best_persona = _DEFAULT_PERSONA

    for filepath in changed_files:
        result = _match_file_to_persona(filepath)
        if result is None:
            continue
        try:
            priority = _PRIORITY_ORDER.index(result.persona_id)
        except ValueError:
            continue
        if priority < best_priority:
            best_priority = priority
            best_persona = result.persona_id

    return best_persona


def select_persona_for_task(
    task_type: str,
    product: str | None = None,
) -> str:
    """Select persona based on task type and optional product context.

    Product-specific override takes precedence when task_type is
    generic (e.g. "pr-review" for filefree -> tax-domain).
    """
    task_persona: str = _TASK_TYPE_MAP.get(task_type, _DEFAULT_PERSONA)

    if product is not None and product in _PRODUCT_PERSONA_MAP:
        product_persona: str = _PRODUCT_PERSONA_MAP[product]
        product_domain: PersonaDispatchDomain | None = DISPATCH_REGISTRY.get(product_persona)
        if product_domain is not None:
            product_tier = product_domain["autonomy_tier"]
            task_domain: PersonaDispatchDomain | None = DISPATCH_REGISTRY.get(task_persona)
            task_tier = (
                task_domain["autonomy_tier"]
                if task_domain is not None
                else AUTONOMY_TIER_NEEDS_APPROVAL
            )
            if product_tier >= task_tier:
                return product_persona

    return task_persona


def get_autonomy_tier(persona_id: str) -> int:
    """Return the autonomy tier for a given persona."""
    domain: PersonaDispatchDomain | None = DISPATCH_REGISTRY.get(persona_id)
    if domain is None:
        return AUTONOMY_TIER_FOUNDER_ONLY
    return domain["autonomy_tier"]


def get_escalation_target(persona_id: str) -> str:
    """Return the escalation target for a given persona."""
    domain: PersonaDispatchDomain | None = DISPATCH_REGISTRY.get(persona_id)
    if domain is None:
        return "founder"
    return domain["escalation_to"]
