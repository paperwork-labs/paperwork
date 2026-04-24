#!/usr/bin/env python3
"""
Bump pinned requirements.txt entries (pkg==x.y.z) to latest stable versions from PyPI.

Notes:
- Skips prereleases/dev releases.
- Skips yanked releases (requires at least one non-yanked file).
- Preserves extras, e.g. uvicorn[standard]==...
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from packaging.version import Version


PIN_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)(\[[^\]]+\])?==([^\s#]+)")


def latest_stable(name: str) -> str:
    url = f"https://pypi.org/pypi/{name}/json"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()

    versions: list[Version] = []
    for v, files in (data.get("releases") or {}).items():
        try:
            ver = Version(v)
        except Exception:
            continue
        if ver.is_prerelease or ver.is_devrelease:
            continue
        ok = False
        for f in files or []:
            if not f.get("yanked", False):
                ok = True
                break
        if ok:
            versions.append(ver)

    if not versions:
        return data["info"]["version"]
    return str(sorted(versions)[-1])


def main() -> None:
    req_path = Path(__file__).resolve().parents[1] / "requirements.txt"
    lines = req_path.read_text().splitlines()

    out: list[str] = []
    changes: list[tuple[str, str, str]] = []

    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            out.append(line)
            continue
        m = PIN_RE.match(line)
        if not m:
            out.append(line)
            continue
        name, extras, old = m.group(1), m.group(2) or "", m.group(3)
        new = latest_stable(name)
        if new != old:
            out.append(line.replace(f"{name}{extras}=={old}", f"{name}{extras}=={new}"))
            changes.append((name, old, new))
        else:
            out.append(line)

    req_path.write_text("\n".join(out) + "\n")
    print(json.dumps({"changed": len(changes), "changes": changes}, indent=2))


if __name__ == "__main__":
    main()


