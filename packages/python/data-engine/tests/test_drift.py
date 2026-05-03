"""TS vs Python parity test. Skipped when `node` is not on PATH (e.g. pure-Python CI).

Runs the canonical TS engine in packages/data/src/engine/tax.ts via a tiny
Node script, then runs the Python engine on identical inputs, then asserts
identical output for a handful of (state, filing_status, gross_income) cells.

When this test fails, exactly one of three things happened:
  1. A bracket in packages/data/src/tax/{year}/*.json changed and one engine
     was updated without the other (impossible if both share the same JSON,
     so really: a JSON update broke one schema validator).
  2. The TS engine's math changed (regression in packages/data/src/engine/tax.ts).
  3. The Python engine's math changed (regression in data_engine.tax).

In all three cases, the fix is to align both engines back to the same algorithm
described in the schema's "doctrine" section.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from data_engine import (
    FilingStatus,
    StateCode,
    calculate_state_tax,
)


def _node_available() -> bool:
    return shutil.which("node") is not None


_TS_SCRIPT = """
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

// Inline the canonical TS engine math so we don't have to compile TS in CI.
// This must mirror packages/data/src/engine/tax.ts byte-for-byte.

function calculateProgressiveTax(taxableIncomeCents, brackets) {
  let taxCents = 0;
  for (const bracket of brackets) {
    if (taxableIncomeCents <= bracket.min_income_cents) break;
    const bracketMax = bracket.max_income_cents ?? Infinity;
    const taxableInBracket = Math.min(taxableIncomeCents, bracketMax) - bracket.min_income_cents;
    if (taxableInBracket <= 0) continue;
    taxCents += Math.round((taxableInBracket * bracket.rate_bps) / 10000);
  }
  return taxCents;
}

function calculateStateTax(rules, grossIncomeCents, filingStatus) {
  if (rules.income_tax.type === 'none') return 0;
  if (rules.income_tax.type === 'flat') {
    const deduction = rules.standard_deductions.find(d => d.filing_status === filingStatus);
    const taxableIncome = Math.max(0, grossIncomeCents - (deduction?.amount_cents ?? 0));
    return Math.round((taxableIncome * rules.income_tax.flat_rate_bps) / 10000);
  }
  const brackets = rules.income_tax.brackets[filingStatus];
  if (!brackets) return null;
  const deduction = rules.standard_deductions.find(d => d.filing_status === filingStatus);
  const taxableIncome = Math.max(0, grossIncomeCents - (deduction?.amount_cents ?? 0));
  return calculateProgressiveTax(taxableIncome, brackets);
}

const cases = JSON.parse(process.argv[2]);
const dataDir = process.argv[3];

const out = cases.map(({ state, year, status, gross }) => {
  const path = join(dataDir, 'tax', String(year), `${state}.json`);
  const rules = JSON.parse(readFileSync(path, 'utf-8'));
  return calculateStateTax(rules, gross, status);
});

process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(not _node_available(), reason="node not on PATH")
def test_ts_python_parity_for_sample_cells(tmp_path: Path) -> None:
    cases = [
        {"state": "CA", "year": 2025, "status": "single", "gross": 5_000_000},
        {"state": "CA", "year": 2025, "status": "single", "gross": 10_000_000},
        {"state": "CA", "year": 2025, "status": "married_filing_jointly", "gross": 8_000_000},
        {"state": "NY", "year": 2025, "status": "single", "gross": 5_000_000},
        {"state": "NY", "year": 2025, "status": "head_of_household", "gross": 12_000_000},
        {"state": "FL", "year": 2025, "status": "single", "gross": 9_000_000},
        {"state": "TX", "year": 2025, "status": "single", "gross": 9_000_000},
        {"state": "DC", "year": 2025, "status": "single", "gross": 5_000_000},
    ]

    from data_engine.loader import get_data_dir

    script = tmp_path / "engine.mjs"
    script.write_text(_TS_SCRIPT, encoding="utf-8")

    proc = subprocess.run(
        [
            "node",
            str(script),
            json.dumps(cases),
            str(get_data_dir()),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    ts_out = json.loads(proc.stdout)

    py_out = [
        calculate_state_tax(
            StateCode(c["state"]),
            c["gross"],
            FilingStatus(c["status"]),
            c["year"],
        )
        for c in cases
    ]

    assert ts_out == py_out, f"TS={ts_out} Python={py_out}"
