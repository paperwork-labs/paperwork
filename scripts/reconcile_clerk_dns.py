#!/usr/bin/env python3
"""Reconcile Cloudflare DNS against Clerk Backend API ``cname_targets``.

Idempotent: lists existing records per zone, creates missing, PATCHes mismatched
``content`` / ``proxied`` / ``ttl``, leaves correct rows untouched.

Also optionally enforces **ops** records on ``paperworklabs.com`` (Brain Render
CNAME + social landing A) that Cloudflare auto-import can drop alongside Clerk
CNAMEs — see ``docs/runbooks/CLERK_DNS_INCIDENT_2026-04-28.md``.

Secrets: ``CLERK_SECRET_KEY``, ``CLOUDFLARE_API_TOKEN`` (or legacy ``CF_TOKEN``).
Fallback: ``scripts/vault-get.sh <NAME>`` when env vars are empty.

Exit codes:
  0  All required records match (or were reconciled successfully).
  1  Auth/network/API failure or could not resolve a hostname to a zone.
  2  One or more required records missing or wrong (check-only or failed write).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CLERK_API_BASE = (os.environ.get("CLERK_API_URL") or "https://api.clerk.com").rstrip("/")
CLERK_DOMAINS_PATH = "/v1/domains"
CF_API_BASE = "https://api.cloudflare.com/client/v4"

# DNS-only for Clerk + Brain on Render; social uses Cloudflare proxy per ops.
PAPERWORKLABS_OPS: tuple[tuple[str, str, str, bool, int], ...] = (
    ("brain.paperworklabs.com", "CNAME", "brain-api-zo5t.onrender.com", False, 1),
    ("social.paperworklabs.com", "A", "204.168.147.100", True, 1),
)


@dataclass(frozen=True)
class DesiredRecord:
    """A single DNS row we expect in Cloudflare."""

    fqdn: str
    rtype: str
    content: str
    proxied: bool
    ttl: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _dns_norm(value: str) -> str:
    return str(value or "").strip().lower().rstrip(".")


def _secret_from_env_or_vault(name: str) -> str:
    raw = (os.environ.get(name) or "").strip()
    if raw:
        return raw
    if name == "CLOUDFLARE_API_TOKEN":
        raw = (os.environ.get("CF_TOKEN") or "").strip()
        if raw:
            return raw
    repo = _repo_root()
    vault = repo / "scripts" / "vault-get.sh"
    if not vault.is_file():
        return ""
    try:
        proc = subprocess.run(
            [str(vault), name],
            capture_output=True,
            text=True,
            timeout=45,
            cwd=str(repo),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any] | list[Any] | None, str]:
    data_bytes = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data_bytes, method=method)  # noqa: S310
    for k, v in headers.items():
        req.add_header(k, v)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
            try:
                parsed: dict[str, Any] | list[Any] | None = json.loads(raw)
            except json.JSONDecodeError:
                return status, None, raw
            return status, parsed, raw
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except OSError:
            err_body = ""
        try:
            parsed_err: dict[str, Any] | list[Any] | None
            parsed_err = json.loads(err_body) if err_body else None
        except json.JSONDecodeError:
            parsed_err = None
        return e.code, parsed_err, err_body or str(e)
    except urllib.error.URLError as e:
        return 0, None, str(e.reason)


def _clerk_list_domains(secret: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    offset = 0
    limit = 20
    while True:
        qs = urllib.parse.urlencode({"limit": limit, "offset": offset})
        url = f"{CLERK_API_BASE}{CLERK_DOMAINS_PATH}?{qs}"
        status, payload, raw = _http_json(
            "GET",
            url,
            headers={"Authorization": f"Bearer {secret}", "Accept": "application/json"},
        )
        if status != 200 or not isinstance(payload, dict):
            raise RuntimeError(f"Clerk domains HTTP {status}: {raw[:800]!s}")
        batch = payload.get("data")
        if not isinstance(batch, list):
            raise RuntimeError(f"Clerk domains unexpected JSON shape: {raw[:400]!s}")
        for row in batch:
            if isinstance(row, dict):
                out.append(row)
        if len(batch) < limit:
            break
        offset += limit
        if offset > 10_000:
            raise RuntimeError("Clerk domains pagination exceeded safety cap")
    return out


def _cf_list_zones(token: str) -> dict[str, str]:
    """Map zone name (apex) -> zone id."""
    zones: dict[str, str] = {}
    page = 1
    while True:
        qs = urllib.parse.urlencode({"page": page, "per_page": 50})
        status, payload, raw = _http_json(
            "GET",
            f"{CF_API_BASE}/zones?{qs}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        if status != 200 or not isinstance(payload, dict):
            raise RuntimeError(f"Cloudflare zones HTTP {status}: {raw[:800]!s}")
        if not payload.get("success"):
            raise RuntimeError(f"Cloudflare zones error: {payload!s}")
        result = payload.get("result")
        if not isinstance(result, list):
            break
        for z in result:
            if not isinstance(z, dict):
                continue
            name = str(z.get("name") or "").strip().lower()
            zid = str(z.get("id") or "").strip()
            if name and zid:
                zones[name] = zid
        info = payload.get("result_info")
        total_pages = 1
        if isinstance(info, dict):
            try:
                total_pages = max(1, int(info.get("total_pages") or 1))
            except (TypeError, ValueError):
                total_pages = 1
        if page >= total_pages:
            break
        page += 1
        if page > 200:
            raise RuntimeError("Cloudflare zone pagination exceeded safety cap")
    return zones


def _pick_zone_for_host(hostname: str, zone_name_to_id: dict[str, str]) -> tuple[str, str] | None:
    h = _dns_norm(hostname)
    candidates = sorted(zone_name_to_id.keys(), key=len, reverse=True)
    for zn in candidates:
        if h == zn or h.endswith("." + zn):
            return zn, zone_name_to_id[zn]
    return None


def _desired_from_clerk(domains: Iterable[dict[str, Any]]) -> list[DesiredRecord]:
    seen: set[tuple[str, str]] = set()
    rows: list[DesiredRecord] = []
    for d in domains:
        targets = d.get("cname_targets")
        if not isinstance(targets, list):
            continue
        for t in targets:
            if not isinstance(t, dict):
                continue
            if not bool(t.get("required")):
                continue
            host = str(t.get("host") or "").strip()
            value = str(t.get("value") or "").strip()
            if not host or not value:
                continue
            key = (_dns_norm(host), "CNAME")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                DesiredRecord(
                    fqdn=host,
                    rtype="CNAME",
                    content=value,
                    proxied=False,
                    ttl=1,
                )
            )
    return rows


def _merge_ops(desired: list[DesiredRecord], *, include_ops: bool) -> list[DesiredRecord]:
    if not include_ops:
        return desired
    by_key = {(_dns_norm(r.fqdn), r.rtype.upper()): r for r in desired}
    for name, rtype, content, proxied, ttl in PAPERWORKLABS_OPS:
        key = (_dns_norm(name), rtype.upper())
        by_key[key] = DesiredRecord(
            fqdn=name,
            rtype=rtype.upper(),
            content=content,
            proxied=proxied,
            ttl=ttl,
        )
    return list(by_key.values())


def _cf_list_dns(token: str, zone_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        qs = urllib.parse.urlencode({"page": page, "per_page": 100})
        status, payload, raw = _http_json(
            "GET",
            f"{CF_API_BASE}/zones/{zone_id}/dns_records?{qs}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        if status != 200 or not isinstance(payload, dict):
            raise RuntimeError(f"Cloudflare dns_records HTTP {status}: {raw[:800]!s}")
        if not payload.get("success"):
            raise RuntimeError(f"Cloudflare dns_records error: {payload!s}")
        chunk = payload.get("result")
        if not isinstance(chunk, list):
            break
        for r in chunk:
            if isinstance(r, dict):
                out.append(r)
        info = payload.get("result_info")
        total_pages = 1
        if isinstance(info, dict):
            try:
                total_pages = max(1, int(info.get("total_pages") or 1))
            except (TypeError, ValueError):
                total_pages = 1
        if page >= total_pages:
            break
        page += 1
        if page > 500:
            raise RuntimeError("Cloudflare dns pagination exceeded safety cap")
    return out


def _find_matching(existing: list[dict[str, Any]], name: str, rtype: str) -> dict[str, Any] | None:
    want_name = _dns_norm(name)
    want_type = rtype.upper()
    for r in existing:
        if str(r.get("type") or "").upper() != want_type:
            continue
        if _dns_norm(str(r.get("name") or "")) != want_name:
            continue
        return r
    return None


def _row_ok(match: dict[str, Any], want: DesiredRecord) -> bool:
    return (
        _dns_norm(str(match.get("content") or "")) == _dns_norm(want.content)
        and bool(match.get("proxied")) == want.proxied
        and int(match.get("ttl") or 0) == int(want.ttl)
    )


def _cf_write(
    method: str,
    token: str,
    zone_id: str,
    rec_id: str | None,
    body: dict[str, Any],
) -> dict[str, Any]:
    if method == "POST":
        url = f"{CF_API_BASE}/zones/{zone_id}/dns_records"
    elif method == "PATCH" and rec_id:
        url = f"{CF_API_BASE}/zones/{zone_id}/dns_records/{rec_id}"
    else:
        raise ValueError("bad cf write")
    status, payload, raw = _http_json(
        method,
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        body=body,
    )
    if status not in (200, 304) or not isinstance(payload, dict):
        raise RuntimeError(f"Cloudflare write HTTP {status}: {raw[:800]!s}")
    return payload


def run_reconcile(*, check_only: bool, include_ops: bool) -> tuple[int, list[dict[str, Any]]]:
    clerk_key = _secret_from_env_or_vault("CLERK_SECRET_KEY")
    cf_token = _secret_from_env_or_vault("CLOUDFLARE_API_TOKEN")
    if not clerk_key:
        print("ERROR: CLERK_SECRET_KEY is not set and vault lookup failed.", file=sys.stderr)
        return 1, []
    if not cf_token:
        print(
            "ERROR: CLOUDFLARE_API_TOKEN (or CF_TOKEN) is not set and vault lookup failed.",
            file=sys.stderr,
        )
        return 1, []

    try:
        domains = _clerk_list_domains(clerk_key)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1, []

    desired = _merge_ops(_desired_from_clerk(domains), include_ops=include_ops)
    if not desired:
        print(
            "ERROR: Clerk returned zero required cname_targets — nothing to reconcile.",
            file=sys.stderr,
        )
        return 1, []

    try:
        zone_map = _cf_list_zones(cf_token)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1, []

    by_zone: dict[str, list[DesiredRecord]] = {}
    for rec in desired:
        picked = _pick_zone_for_host(rec.fqdn, zone_map)
        if picked is None:
            print(f"ERROR: No Cloudflare zone owns hostname {rec.fqdn!r}", file=sys.stderr)
            return 1, []
        _zn, zid = picked
        by_zone.setdefault(zid, []).append(rec)

    summary: list[dict[str, Any]] = []

    for zone_id, wants in sorted(by_zone.items(), key=lambda x: x[0]):
        existing = _cf_list_dns(cf_token, zone_id)
        for want in sorted(wants, key=lambda r: r.fqdn):
            match = _find_matching(existing, want.fqdn, want.rtype)
            zone_name = next((n for n, i in zone_map.items() if i == zone_id), zone_id)
            base_row: dict[str, Any] = {
                "zone": zone_name,
                "name": want.fqdn,
                "type": want.rtype,
                "expected": want.content,
                "proxied": want.proxied,
                "ttl": want.ttl,
            }
            if match is None:
                base_row["status"] = "MISSING"
                base_row["actual"] = ""
                summary.append(base_row)
                if not check_only:
                    payload = {
                        "type": want.rtype,
                        "name": want.fqdn,
                        "content": want.content,
                        "ttl": want.ttl,
                        "proxied": want.proxied,
                    }
                    try:
                        res = _cf_write("POST", cf_token, zone_id, None, payload)
                        ok = bool(res.get("success"))
                        base_row["status"] = "CREATED" if ok else "CREATE_FAILED"
                        if ok:
                            created = res.get("result")
                            if isinstance(created, dict) and created.get("id"):
                                existing.append(created)
                    except RuntimeError as e:
                        base_row["status"] = "CREATE_FAILED"
                        base_row["error"] = str(e)
                continue

            base_row["actual"] = str(match.get("content") or "")
            base_row["record_id"] = str(match.get("id") or "")
            if _row_ok(match, want):
                base_row["status"] = "OK"
                summary.append(base_row)
                continue

            base_row["status"] = "WRONG"
            summary.append(base_row)
            if not check_only:
                payload = {
                    "type": want.rtype,
                    "name": want.fqdn,
                    "content": want.content,
                    "ttl": want.ttl,
                    "proxied": want.proxied,
                }
                try:
                    rid = str(match.get("id") or "")
                    res = _cf_write("PATCH", cf_token, zone_id, rid, payload)
                    ok = bool(res.get("success"))
                    base_row["status"] = "UPDATED" if ok else "UPDATE_FAILED"
                    if not ok:
                        base_row["error"] = str(res.get("errors"))
                except RuntimeError as e:
                    base_row["status"] = "UPDATE_FAILED"
                    base_row["error"] = str(e)

    bad = [r for r in summary if str(r.get("status")) not in ("OK", "CREATED", "UPDATED")]
    return (0 if not bad else 2), summary


def _print_table(rows: list[dict[str, Any]]) -> None:
    headers = ("zone", "name", "type", "status", "expected", "actual")
    widths = {h: len(h) for h in headers}
    for r in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(r.get(h) or "")))
    line = "  ".join(h.ljust(widths[h]) for h in headers)
    print(line)
    print("  ".join("-" * widths[h] for h in headers))
    for r in rows:
        print("  ".join(str(r.get(h) or "").ljust(widths[h]) for h in headers))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Do not create or update Cloudflare records; exit non-zero on drift.",
    )
    parser.add_argument(
        "--no-ops-dns",
        action="store_true",
        help=f"Skip non-Clerk ops rows ({len(PAPERWORKLABS_OPS)} records on paperworklabs.com).",
    )
    args = parser.parse_args(argv)

    mode = "check-only" if args.check_only else "reconcile"
    print(f"=== reconcile_clerk_dns ({mode}) ===\n")

    code, summary = run_reconcile(check_only=args.check_only, include_ops=not args.no_ops_dns)
    if summary:
        _print_table(summary)
        print()
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
