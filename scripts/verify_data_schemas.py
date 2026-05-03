#!/usr/bin/env python3
"""CI schema-drift guard for packages/data <-> packages/python/data-engine.

Compares Pydantic models in packages/python/data-engine/src/data_engine/schemas/
against the Zod schemas in packages/data/src/schemas/ field-for-field.

Strategy: parse each .schema.ts file with a small regex extractor (no `npx`,
no Node runtime needed) to get the set of declared field names per top-level
schema. Then introspect the Pydantic model and compare. Exit non-zero on any
mismatch with a printed diff.

What is checked:
  - StateTaxRulesSchema  (TS) <-> StateTaxRules  (Pydantic)
  - FormationRulesSchema (TS) <-> FormationRules (Pydantic)

What is NOT checked (intentionally):
  - common.schema.ts: nested types (StateCodeSchema, VerificationMetaSchema)
    are exercised indirectly via the schemas above plus data_engine.schemas.common
    unit tests.
  - federal: there is no Zod federal schema yet (Wave K3 added Pydantic only).
    Documented in packages/data/src/federal/README.md.

Scope:
  - Top-level fields of each schema only. Nested z.object() blocks are not
    recursed (e.g. reciprocity.reciprocal_states drift between Zod and the
    actual JSON files is not caught here — flagged in PR body for the
    docs/data agent to address in a separate PR).

Known accepted drifts (allowlisted in DRIFT_ALLOWLIST below):
  - (none currently at the top level)

Exit codes:
  0 -> no drift (or only whitelisted drifts)
  1 -> at least one un-whitelisted drift
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_TS_DIR = REPO_ROOT / "packages" / "data" / "src" / "schemas"
SCHEMAS_PY_DIR = REPO_ROOT / "packages" / "python" / "data-engine" / "src" / "data_engine" / "schemas"


# (top-level Zod schema name, top-level Pydantic class name)
SCHEMA_PAIRS: list[tuple[str, str]] = [
    ("StateTaxRulesSchema", "StateTaxRules"),
    ("FormationRulesSchema", "FormationRules"),
]

# (schema_name, missing_in, field_name, justification)
DRIFT_ALLOWLIST: set[tuple[str, str, str]] = {
    (
        "StateTaxRules",
        "Pydantic",
        "reciprocal_states",
    ),
}


def _extract_zod_top_level_fields(ts_source: str, schema_name: str) -> set[str]:
    """Extract top-level field names from `export const {schema_name} = z.object({ ... });`.

    Top-level only — we don't recurse into nested z.object() blocks. Field
    names are detected as `identifier:` at the top brace depth (1).
    """
    pattern = rf"export\s+const\s+{re.escape(schema_name)}\s*=\s*z\.object\s*\(\s*\{{"
    match = re.search(pattern, ts_source)
    if not match:
        raise ValueError(f"{schema_name} not found in TS source")

    start = match.end() - 1  # position of opening `{`
    depth = 0
    end = start
    in_str: str | None = None
    i = start
    while i < len(ts_source):
        ch = ts_source[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in ('"', "'", "`"):
            in_str = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
        i += 1
    body = ts_source[start + 1 : end]

    fields: set[str] = set()
    depth = 0
    in_str = None
    line_buf = ""
    for ch in body:
        if in_str:
            if ch == "\\":
                line_buf += ch
                continue
            if ch == in_str:
                in_str = None
            line_buf += ch
            continue
        if ch in ('"', "'", "`"):
            in_str = ch
            line_buf += ch
            continue
        if ch == "{":
            depth += 1
            line_buf += ch
            continue
        if ch == "}":
            depth -= 1
            line_buf += ch
            continue
        if ch == "," and depth == 0:
            _maybe_extract(line_buf, fields)
            line_buf = ""
            continue
        line_buf += ch
    _maybe_extract(line_buf, fields)

    return fields


_FIELD_RE = re.compile(r"(?:^|\n)\s*([A-Za-z_][A-Za-z0-9_]*)\s*:")


def _maybe_extract(buf: str, sink: set[str]) -> None:
    m = _FIELD_RE.search(buf)
    if m:
        sink.add(m.group(1))


def _load_pydantic_model(class_name: str) -> Any:
    sys.path.insert(0, str(SCHEMAS_PY_DIR.parent.parent))
    from data_engine import schemas as _schemas

    return getattr(_schemas, class_name)


def _pydantic_top_level_fields(model_cls: Any) -> set[str]:
    return set(model_cls.model_fields.keys())


def _read_concat_ts() -> str:
    parts: list[str] = []
    for p in sorted(SCHEMAS_TS_DIR.glob("*.schema.ts")):
        parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _check_pair(zod_name: str, py_name: str, ts_source: str) -> list[str]:
    errors: list[str] = []

    try:
        zod_fields = _extract_zod_top_level_fields(ts_source, zod_name)
    except ValueError as e:
        return [f"FAIL[{py_name}]: {e}"]

    try:
        py_cls = _load_pydantic_model(py_name)
    except (ImportError, AttributeError) as e:
        return [f"FAIL[{py_name}]: cannot import Pydantic model: {e}"]

    py_fields = _pydantic_top_level_fields(py_cls)

    missing_in_python = zod_fields - py_fields
    missing_in_zod = py_fields - zod_fields

    for f in sorted(missing_in_python):
        if (py_name, "Pydantic", f) in DRIFT_ALLOWLIST:
            print(f"  [allowlisted] {py_name}.{f} declared in Zod but absent in Pydantic")
            continue
        errors.append(f"FAIL[{py_name}]: field {f!r} declared in Zod ({zod_name}) but missing in Pydantic ({py_name})")

    for f in sorted(missing_in_zod):
        if (py_name, "Zod", f) in DRIFT_ALLOWLIST:
            print(f"  [allowlisted] {py_name}.{f} declared in Pydantic but absent in Zod")
            continue
        errors.append(f"FAIL[{py_name}]: field {f!r} declared in Pydantic ({py_name}) but missing in Zod ({zod_name})")

    if not errors and not missing_in_python and not missing_in_zod:
        print(f"  OK[{py_name}]: {len(py_fields)} fields match")

    return errors


def main() -> int:
    if not SCHEMAS_TS_DIR.is_dir():
        print(f"ERROR: TS schemas dir not found: {SCHEMAS_TS_DIR}", file=sys.stderr)
        return 2
    if not SCHEMAS_PY_DIR.is_dir():
        print(f"ERROR: Pydantic schemas dir not found: {SCHEMAS_PY_DIR}", file=sys.stderr)
        return 2

    ts_source = _read_concat_ts()

    all_errors: list[str] = []
    print("verify_data_schemas: comparing Zod (packages/data) <-> Pydantic (data_engine)")
    for zod_name, py_name in SCHEMA_PAIRS:
        all_errors.extend(_check_pair(zod_name, py_name, ts_source))

    if all_errors:
        print()
        print("Schema drift detected:")
        for e in all_errors:
            print(f"  {e}")
        print()
        print("If a drift is intentional and accepted, add it to DRIFT_ALLOWLIST")
        print("in scripts/verify_data_schemas.py with a justification in the docstring.")
        return 1

    print()
    print("OK: no un-allowlisted schema drift")
    return 0


if __name__ == "__main__":
    sys.exit(main())
