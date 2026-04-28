#!/usr/bin/env python3
"""Idempotently set SPF (apex) and DMARC TXT records for paperworklabs.com via Cloudflare API.

Reads ``CLOUDFLARE_API_TOKEN`` from the environment, or falls back to::

    scripts/vault-get.sh CLOUDFLARE_API_TOKEN

Exit codes:
  0  Success (or --check-only: records match desired state)
  1  Drift / missing records (--check-only), API error, or missing token
  2  Usage error
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

# Production zone: paperworklabs.com on Cloudflare work account (see WS-33 notes).
ZONE_ID_PAPERWORKLABS = "6efe0c9f87c80a21617ff040fa2e55dd"
DOMAIN = "paperworklabs.com"
DMARC_NAME = f"_dmarc.{DOMAIN}"

SPF_CONTENT = "v=spf1 include:_spf.google.com include:spf.mtasv.net -all"
DMARC_CONTENT = (
    "v=DMARC1; p=quarantine; rua=mailto:dmarc@paperworklabs.com; "
    "ruf=mailto:dmarc@paperworklabs.com; fo=1; pct=100"
)

CF_API = "https://api.cloudflare.com/client/v4"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _eprint(*args: object) -> None:
    sys.stderr.write(" ".join(str(a) for a in args) + "\n")


def _resolve_token() -> str:
    raw = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if raw:
        return raw
    vault_script = _REPO_ROOT / "scripts" / "vault-get.sh"
    if not vault_script.is_file():
        _eprint("CLOUDFLARE_API_TOKEN unset and scripts/vault-get.sh not found.")
        sys.exit(1)
    proc = subprocess.run(  # noqa: S603
        [str(vault_script), "CLOUDFLARE_API_TOKEN"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        _eprint(proc.stderr.strip() or "vault-get.sh failed")
        sys.exit(1)
    out = proc.stdout.strip()
    if not out:
        _eprint("CLOUDFLARE_API_TOKEN empty after vault-get.sh")
        sys.exit(1)
    return out


def _cf_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _http_json(
    method: str,
    path: str,
    token: str,
    body: dict[str, Any] | None = None,
    *,
    timeout: float = 60.0,
) -> tuple[int, dict[str, Any]]:
    """Call Cloudflare v4 API. ``path`` must start with ``/``."""
    if not path.startswith("/"):
        raise ValueError("path must start with /")
    url = f"{CF_API}{path}"
    data_bytes = None
    if body is not None:
        data_bytes = json.dumps(body).encode("utf-8")
    req = Request(url, data=data_bytes, headers=_cf_headers(token), method=method)  # noqa: S310
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return status, {}
            return status, cast(dict[str, Any], parsed)
    except HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except OSError:
            err_body = ""
        try:
            parsed_err = json.loads(err_body) if err_body else {}
        except json.JSONDecodeError:
            parsed_err = {"raw": err_body}
        _eprint(f"HTTP {e.code}: {parsed_err}")
        return e.code, cast(dict[str, Any], parsed_err) if isinstance(parsed_err, dict) else {}
    except URLError as e:
        _eprint(f"Request failed: {e.reason!s}")
        return 0, {}


def _list_txt_for_name(zone_id: str, token: str, name: str) -> list[dict[str, Any]]:
    """Return TXT ``result`` rows for exact DNS name (paginated)."""
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        enc = quote(name, safe=".")
        q = f"/zones/{zone_id}/dns_records?type=TXT&name={enc}&page={page}&per_page=100"
        _status, payload = _http_json("GET", q, token)
        if not payload.get("success"):
            errs = payload.get("errors", [])
            _eprint("List DNS failed:", errs)
            sys.exit(1)
        batch = payload.get("result", [])
        if not isinstance(batch, list):
            break
        for row in batch:
            if isinstance(row, dict):
                out.append(row)
        info = payload.get("result_info", {})
        total_pages = 1
        if isinstance(info, dict):
            total_pages = int(info.get("total_pages", 1) or 1)
        if page >= total_pages:
            break
        page += 1
    return out


def _find_by_content_prefix(records: list[dict[str, Any]], prefix: str) -> dict[str, Any] | None:
    prefix_l = prefix.lower()
    for r in records:
        content = str(r.get("content", ""))
        if content.lower().startswith(prefix_l):
            return r
    return None


def _ensure_txt(
    zone_id: str,
    token: str,
    name: str,
    desired_content: str,
    *,
    match_prefix: str,
    check_only: bool,
) -> str:
    """Return ``unchanged`` | ``created`` | ``updated``."""
    rows = _list_txt_for_name(zone_id, token, name)
    existing = _find_by_content_prefix(rows, match_prefix)
    if existing is None:
        if check_only:
            _eprint(f"[check-only] missing {match_prefix}* TXT at {name!r}")
            return "missing"
        _status, payload = _http_json(
            "POST",
            f"/zones/{zone_id}/dns_records",
            token,
            {
                "type": "TXT",
                "name": name,
                "content": desired_content,
                "ttl": 1,
                "proxied": False,
            },
        )
        if not payload.get("success"):
            _eprint("Create failed:", payload.get("errors"))
            sys.exit(1)
        return "created"
    cur = str(existing.get("content", ""))
    rid = str(existing.get("id", ""))
    if cur == desired_content:
        return "unchanged"
    if check_only:
        _eprint(f"[check-only] drift at {name!r}: have {cur!r} want {desired_content!r}")
        return "drift"
    _status, payload = _http_json(
        "PUT",
        f"/zones/{zone_id}/dns_records/{rid}",
        token,
        {
            "type": "TXT",
            "name": name,
            "content": desired_content,
            "ttl": existing.get("ttl", 1),
            "proxied": False,
        },
    )
    if not payload.get("success"):
        _eprint("Update failed:", payload.get("errors"))
        sys.exit(1)
    return "updated"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify apex SPF and _dmarc TXT match desired strings; do not write.",
    )
    args = parser.parse_args()

    token = _resolve_token()
    zone_id = ZONE_ID_PAPERWORKLABS

    spf_result = _ensure_txt(
        zone_id,
        token,
        DOMAIN,
        SPF_CONTENT,
        match_prefix="v=spf1",
        check_only=args.check_only,
    )
    dmarc_result = _ensure_txt(
        zone_id,
        token,
        DMARC_NAME,
        DMARC_CONTENT,
        match_prefix="v=DMARC1",
        check_only=args.check_only,
    )

    if args.check_only:
        bad = {r for r in (spf_result, dmarc_result) if r not in {"unchanged"}}
        if bad:
            sys.exit(1)
        sys.stdout.write("check-only OK: SPF and DMARC TXT match desired policy.\n")
        return

    sys.stdout.write(f"SPF @ {DOMAIN}: {spf_result}\nDMARC @ {DMARC_NAME}: {dmarc_result}\n")


if __name__ == "__main__":
    main()
