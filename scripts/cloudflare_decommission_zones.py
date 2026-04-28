#!/usr/bin/env python3
"""Delete migrated production zones from a *former* personal Cloudflare account.

Uses ``CLOUDFLARE_OLD_API_TOKEN`` (paste at runtime; do not store in vault).

Default mode is **dry-run** (prints preconditions + ``would delete``). Pass
``--apply`` to call ``DELETE /zones/{id}``.

Preconditions (per zone):

* ``dig @1.1.1.1``, ``@8.8.8.8``, ``@9.9.9.9`` for **NS** — delegated nameservers
  must not match the old zone's Cloudflare ``name_servers`` (migration complete).
* Same resolvers for **MX** and **TXT** at the apex — ``dig`` must exit 0
  (working resolution vs SERVFAIL during bad delegation).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

CF_V4 = "https://api.cloudflare.com/client/v4"

TARGET_ZONES: frozenset[str] = frozenset(
    {
        "paperworklabs.com",
        "axiomfolio.com",
        "filefree.ai",
        "launchfree.ai",
        "distill.tax",
    }
)

RESOLVERS: tuple[tuple[str, str], ...] = (
    ("1.1.1.1", "cloudflare"),
    ("8.8.8.8", "google"),
    ("9.9.9.9", "quad9"),
)


class DigRunner(Protocol):
    def __call__(self, resolver_ip: str, name: str, qtype: str) -> tuple[int, list[str]]: ...


def _eprint(*parts: object) -> None:
    sys.stderr.write(" ".join(str(p) for p in parts) + "\n")


def default_dig_runner(resolver_ip: str, name: str, qtype: str) -> tuple[int, list[str]]:
    """Run ``dig +short``; return (returncode, non-empty stripped lines)."""
    cmd = [
        "dig",
        "+time=5",
        "+tries=1",
        f"@{resolver_ip}",
        name,
        qtype,
        "+short",
    ]
    proc = subprocess.run(  # noqa: S603
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    return proc.returncode, lines


def cf_request_json(
    method: str,
    path: str,
    *,
    token: str,
    body: dict[str, Any] | None = None,
    opener: Callable[..., Any] | None = None,
    timeout: float = 60.0,
) -> tuple[int, Any | None, str]:
    """HTTP JSON helper (Cloudflare v4). ``opener`` defaults to :func:`urlopen`."""
    url = f"{CF_V4}{path}"
    scheme = urlparse(url).scheme
    if scheme not in ("http", "https"):
        return 0, None, f"bad scheme {scheme!r}"
    data_bytes: bytes | None = None
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if body is not None:
        data_bytes = json.dumps(body).encode("utf-8")
    req = Request(url, data=data_bytes, headers=headers, method=method)  # noqa: S310
    open_fn = opener or urlopen
    try:
        with open_fn(req, timeout=timeout) as resp:  # type: ignore[operator]
            raw = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
            try:
                return status, json.loads(raw), raw
            except json.JSONDecodeError:
                return status, None, raw
    except HTTPError as e:
        try:
            b = e.read().decode("utf-8")
        except OSError:
            b = ""
        try:
            parsed = json.loads(b) if b else None
        except json.JSONDecodeError:
            parsed = None
        return e.code, parsed, b
    except URLError as e:
        _eprint("URLError:", e.reason)
        return 0, None, str(e.reason)


def list_all_zones(*, token: str, opener: Callable[..., Any] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        path = f"/zones?status=active&page={page}&per_page=50"
        status, payload, _raw = cf_request_json("GET", path, token=token, opener=opener)
        if status != 200 or not isinstance(payload, dict):
            raise RuntimeError(f"list zones failed HTTP {status}: {payload!r}")
        if not payload.get("success"):
            raise RuntimeError(f"list zones API error: {payload!r}")
        result = payload.get("result")
        if not isinstance(result, list):
            break
        out.extend([z for z in result if isinstance(z, dict)])
        info = payload.get("result_info")
        total_pages = 1
        if isinstance(info, dict):
            try:
                total_pages = int(info.get("total_pages", 1))
            except (TypeError, ValueError):
                total_pages = 1
        if page >= total_pages:
            break
        page += 1
    return out


def delete_zone(
    zone_id: str, *, token: str, opener: Callable[..., Any] | None = None
) -> tuple[int, Any | None, str]:
    return cf_request_json("DELETE", f"/zones/{zone_id}", token=token, opener=opener)


def _norm_ns(hostname: str) -> str:
    return hostname.lower().rstrip(".")


def evaluate_ns_precondition(
    old_name_servers: list[str],
    zone_name: str,
    dig: DigRunner,
) -> tuple[bool, list[str]]:
    """Return (ok, human-readable log lines)."""
    lines: list[str] = []
    old_set = {_norm_ns(x) for x in old_name_servers}
    per: dict[str, frozenset[str]] = {}
    for ip, label in RESOLVERS:
        rc, nss = dig(ip, zone_name, "NS")
        if rc != 0:
            lines.append(f"  NS @{label} ({ip}): dig failed rc={rc}")
            return False, lines
        pub = frozenset({_norm_ns(n) for n in nss})
        per[label] = pub
        if not pub:
            lines.append(f"  NS @{label}: empty answer")
            return False, lines
        if pub == old_set:
            lines.append(f"  NS @{label}: still matches old zone name_servers {sorted(pub)}")
            return False, lines
        overlap = set(pub) & old_set
        if overlap:
            lines.append(f"  NS @{label}: overlap with old assignment: {sorted(overlap)}")
            return False, lines
        lines.append(f"  NS @{label}: ok ({', '.join(sorted(pub))})")

    unique = {frozenset(s) for s in per.values()}
    if len(unique) > 1:
        lines.append(f"  NS: resolver disagreement { {k: sorted(v) for k, v in per.items()} }")
        return False, lines
    return True, lines


def evaluate_mx_txt(
    zone_name: str,
    dig: DigRunner,
) -> tuple[bool, list[str]]:
    lines: list[str] = []
    for ip, label in RESOLVERS:
        for qtype in ("MX", "TXT"):
            rc, _rows = dig(ip, zone_name, qtype)
            if rc != 0:
                lines.append(f"  {qtype} @{label}: dig failed rc={rc}")
                return False, lines
            lines.append(f"  {qtype} @{label}: ok")
    return True, lines


@dataclass
class ZonePlan:
    zone_name: str
    zone_id: str
    old_name_servers: list[str]
    ns_ok: bool
    ns_detail: list[str]
    mx_txt_ok: bool
    mx_txt_detail: list[str]

    @property
    def preconditions_ok(self) -> bool:
        return self.ns_ok and self.mx_txt_ok


def build_plan_for_zone(
    zone: dict[str, Any],
    dig: DigRunner,
) -> ZonePlan | None:
    name = zone.get("name")
    zid = zone.get("id")
    ns = zone.get("name_servers")
    if not isinstance(name, str) or not isinstance(zid, str):
        return None
    if not isinstance(ns, list) or not all(isinstance(x, str) for x in ns):
        return None
    ns_ok, ns_lines = evaluate_ns_precondition(ns, name, dig)
    mx_ok, mx_lines = evaluate_mx_txt(name, dig)
    return ZonePlan(
        zone_name=name,
        zone_id=zid,
        old_name_servers=list(ns),
        ns_ok=ns_ok,
        ns_detail=ns_lines,
        mx_txt_ok=mx_ok,
        mx_txt_detail=mx_lines,
    )


def run(
    *,
    token: str,
    apply: bool,
    dig: DigRunner,
    opener: Callable[..., Any] | None,
) -> int:
    zones = list_all_zones(token=token, opener=opener)
    by_name = {z["name"]: z for z in zones if isinstance(z.get("name"), str)}
    plans: list[ZonePlan] = []
    missing: list[str] = []

    for apex in sorted(TARGET_ZONES):
        z = by_name.get(apex)
        if not z:
            missing.append(apex)
            continue
        plan = build_plan_for_zone(z, dig)
        if plan:
            plans.append(plan)

    print("=== Cloudflare zone decommission ===")
    print(f"Target zones: {', '.join(sorted(TARGET_ZONES))}")
    print(f"Mode: {'APPLY (destructive)' if apply else 'DRY-RUN'}")
    print()

    if missing:
        print("Zones not found on this account:")
        for m in missing:
            print(f"  - {m}")
        print()

    all_pre_ok = True
    for p in plans:
        print(f"--- {p.zone_name} (id={p.zone_id}) ---")
        for ln in p.ns_detail:
            print(ln)
        for ln in p.mx_txt_detail:
            print(ln)
        if not p.preconditions_ok:
            print("PRECONDITIONS: FAIL")
            all_pre_ok = False
        else:
            print("PRECONDITIONS: PASS")
            if not apply:
                print(f"Would delete zone {p.zone_name} (id={p.zone_id})")
        print()

    expected = len(TARGET_ZONES)
    have_all = not missing and len(plans) == expected and all_pre_ok

    if apply and have_all:
        deleted = 0
        delete_ok = True
        for p in plans:
            st, body, raw = delete_zone(p.zone_id, token=token, opener=opener)
            if st == 200 and isinstance(body, dict) and body.get("success"):
                print(f"DELETED zone {p.zone_name} (id={p.zone_id})")
                deleted += 1
            else:
                print(f"DELETE FAILED {p.zone_name} HTTP {st}: {raw[:500]}")
                delete_ok = False
        print()
        if delete_ok and deleted == expected:
            print("\033[92mall 5 zones decommissioned\033[0m")
            return 0
        print("\033[91mzone deletion failed (see HTTP errors above)\033[0m")
        return 1

    if not apply and have_all:
        print("\033[92mDRY-RUN: all 5 zones pass preconditions (no deletes performed)\033[0m")
        return 0

    if missing:
        print("\033[91mzone(s) missing on old account — cannot verify or decommission\033[0m")
        return 1
    if not all_pre_ok:
        print("\033[91mzone(s) failed precondition — do not override; investigate\033[0m")
        return 1
    print("\033[91munexpected state (incomplete zone list)\033[0m")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually DELETE zones (default is dry-run)",
    )
    args = parser.parse_args(argv)

    token = (sys.environ.get("CLOUDFLARE_OLD_API_TOKEN") or "").strip()
    if not token:
        _eprint("CLOUDFLARE_OLD_API_TOKEN is required")
        return 2

    return run(token=token, apply=args.apply, dig=default_dig_runner, opener=None)


if __name__ == "__main__":
    raise SystemExit(main())
