"""
Prompt templates and JSON schema contract for the AnomalyExplainer.

Kept in their own module so reviewers can change the prompt language
without touching the orchestration logic, and so the JSON schema doubles
as machine-readable documentation of the LLM contract.

If you update :data:`SYSTEM_PROMPT` or :data:`OUTPUT_JSON_SCHEMA` and
the change is observable to consumers (changes step structure, renames
fields, etc.), bump :data:`SCHEMA_VERSION` in
``app.services.agent.anomaly_explainer.schemas``.

medallion: ops
"""

from __future__ import annotations

from typing import Any, Dict


SYSTEM_PROMPT = (
    "You are AxiomFolio AutoOps, an experienced site-reliability engineer "
    "for a quantitative trading platform. Your job is to read a single "
    "operations anomaly, propose a precise root-cause hypothesis, and "
    "draft a numbered remediation runbook.\n"
    "\n"
    "STRICT RULES:\n"
    "1. Reply with ONE JSON object and nothing else. No prose before or "
    "   after, no markdown fences, no comments.\n"
    "2. The JSON MUST conform exactly to the schema described in the user "
    "   message. Unknown fields will be rejected.\n"
    "3. Only suggest Celery task slugs the user has listed under "
    "   `available_tasks`. Never invent a task name. If no available task "
    "   fits a step, leave `proposed_task` null.\n"
    "4. Cite the runbook excerpts you used by their `reference` value in "
    "   each step's `runbook_section`. If you didn't use any excerpt, "
    "   leave `runbook_section` null.\n"
    "5. `confidence` is between 0.0 and 1.0. Use 0.5 if you are unsure; "
    "   never claim 1.0.\n"
    "6. Mark a step `requires_approval=true` whenever it would mutate "
    "   production state (writes, deletes, broker calls, restarts). "
    "   Read-only diagnostics may set it to false.\n"
    "7. Be terse. The narrative must be at most 4 short paragraphs.\n"
)


OUTPUT_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "title",
        "summary",
        "root_cause_hypothesis",
        "narrative",
        "steps",
        "confidence",
    ],
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 120},
        "summary": {"type": "string", "minLength": 1, "maxLength": 400},
        "root_cause_hypothesis": {"type": "string", "minLength": 1, "maxLength": 600},
        "narrative": {"type": "string", "minLength": 1, "maxLength": 4000},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["order", "description", "requires_approval"],
                "properties": {
                    "order": {"type": "integer", "minimum": 1},
                    "description": {"type": "string", "minLength": 1, "maxLength": 600},
                    "runbook_section": {"type": ["string", "null"]},
                    "proposed_task": {"type": ["string", "null"]},
                    "requires_approval": {"type": "boolean"},
                    "rationale": {"type": ["string", "null"]},
                },
            },
        },
    },
}


USER_PROMPT_TEMPLATE = (
    "Anomaly to analyse:\n"
    "```json\n{anomaly_json}\n```\n"
    "\n"
    "Available Celery tasks you may propose (slug -> description):\n"
    "```json\n{available_tasks_json}\n```\n"
    "\n"
    "Relevant runbook excerpts (use their `reference` field when citing):\n"
    "{runbook_block}\n"
    "\n"
    "Required output shape (JSON Schema):\n"
    "```json\n{schema_json}\n```\n"
    "\n"
    "Respond with one JSON object that satisfies the schema above."
)
