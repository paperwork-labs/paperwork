"""Self-checks for ``scripts/check_parents_import_safety.py`` using tiny fixtures."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "scripts" / "check_parents_import_safety.py"


def _run(*roots: str) -> int:
    proc = subprocess.run(
        [sys.executable, str(CHECKER), "--roots", *roots],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return int(proc.returncode)


class ParentsImportSafetyExamplesTest(unittest.TestCase):
    def test_pass_fixture_exits_zero(self) -> None:
        code = _run("scripts/test_inputs/parents_import_safety/pass_case")
        self.assertEqual(code, 0, msg="expected pass_case fixture to satisfy the guard")

    def test_fail_fixture_exits_nonzero(self) -> None:
        code = _run("scripts/test_inputs/parents_import_safety/fail_case")
        self.assertNotEqual(code, 0, msg="expected fail_case fixture to trip the guard")


if __name__ == "__main__":
    unittest.main()
