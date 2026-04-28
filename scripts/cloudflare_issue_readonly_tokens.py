#!/usr/bin/env python3
"""Issue per-zone **DNS Read** Cloudflare API tokens and store them in the Studio vault.

Uses the account-wide ``CLOUDFLARE_API_TOKEN`` (must include permission to create
user tokens — typically Account / User / API Tokens / Edit).

* Creates one token per production apex zone with **Zone → DNS → Read** on that
  zone only (no account-wide permissions, no edit scopes).
* Vault keys: ``CLOUDFLARE_READONLY_TOKEN_PAPERWORKLABS``,
  ``CLOUDFLARE_READONLY_TOKEN_AXIOMFOLIO``, ``CLOUDFLARE_READONLY_TOKEN_FILEFREE``,
  ``CLOUDFLARE_READONLY_TOKEN_LAUNCHFREE``, ``CLOUDFLARE_READONLY_TOKEN_DISTILL_TAX``.

Idempotent by token **name**. Use ``--rotate`` to revoke an existing token with
the same name and issue a fresh one.

**Do not run in CI** — this creates real Cloudflare artifacts. Founder runs
manually after merge with ``SECRETS_API_KEY`` (or admin basic auth) for vault writes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from base64 import b64encode
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

CF_V4 = "https://api.cloudflare.com/client/v4"

# Stable display names so LIST /user/tokens can detect duplicates.
TOKEN_NAME_PREFIX = "brain-readonly-dns"


@dataclass(frozen=True)
class ZoneVault:
    apex: str
    vault_key: str

    @property
    def token_name(self) -> str:
        safe = self.apex.replace(".", "-")
        return f"{TOKEN_NAME_PREFIX}-{safe}"


ZONES: tuple[ZoneVault, ...] = (
    ZoneVault("paperworklabs.com", "CLOUDFLARE_READONLY_TOKEN_PAPERWORKLABS"),
    ZoneVault("axiomfolio.com", "CLOUDFLARE_READONLY_TOKEN_AXIOMFOLIO"),
    ZoneVault("filefree.ai", "CLOUDFLARE_READONLY_TOKEN_FILEFREE"),
    ZoneVault("launchfree.ai", "CLOUDFLARE_READONLY_TOKEN_LAUNCHFREE"),
    ZoneVault("distill.tax", "CLOUDFLARE_READONLY_TOKEN_DISTILL_TAX"),
)


def _eprint(*parts: object) -> None:
    sys.stderr.write(" ".join(str(p) for p in parts) + "\n")


def cf_request_json(
    method: str,
    path: str,
    *,
    token: str,
    body: dict[str, Any] | None = None,
    opener: Callable[..., Any] | None = None,
    timeout: float = 60.0,
) -> tuple[int, Any | None, str]:
    url = f"{CF_V4}{path}"
    if urlparse(url).scheme not in ("https",):
        return 0, None, "only https supported"
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


def fetch_dns_read_permission_group_id(
    *, admin_token: str, opener: Callable[..., Any] | None = None
) -> str:
    st, payload, raw = cf_request_json(
        "GET", "/user/tokens/permission_groups", token=admin_token, opener=opener
    )
    if st != 200 or not isinstance(payload, dict) or not payload.get("success"):
        raise RuntimeError(f"permission_groups failed: HTTP {st} {raw[:400]}")
    groups = payload.get("result")
    if not isinstance(groups, list):
        raise RuntimeError("permission_groups: unexpected shape")
    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        name = g.get("name")
        if not isinstance(gid, str) or not isinstance(name, str):
            continue
        if name.strip().lower() == "dns read":
            return gid
    raise RuntimeError("could not find permission group named 'DNS Read'")


def resolve_zone_id(
    apex: str, *, admin_token: str, opener: Callable[..., Any] | None = None
) -> str:
    q = quote(apex)
    st, payload, raw = cf_request_json("GET", f"/zones?name={q}", token=admin_token, opener=opener)
    if st != 200 or not isinstance(payload, dict) or not payload.get("success"):
        raise RuntimeError(f"zones?name= failed for {apex}: HTTP {st} {raw[:400]}")
    result = payload.get("result")
    if not isinstance(result, list) or not result:
        raise RuntimeError(f"zone not found for name={apex!r}")
    for z in result:
        if not isinstance(z, dict):
            continue
        if z.get("name") == apex:
            zid = z.get("id")
            if isinstance(zid, str):
                return zid
    raise RuntimeError(f"zone list for name={apex!r} did not contain an exact name match")


def list_user_tokens(
    *, admin_token: str, opener: Callable[..., Any] | None = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        st, payload, raw = cf_request_json(
            "GET", f"/user/tokens?page={page}&per_page=50", token=admin_token, opener=opener
        )
        if st != 200 or not isinstance(payload, dict) or not payload.get("success"):
            raise RuntimeError(f"list tokens failed HTTP {st}: {raw[:400]}")
        result = payload.get("result")
        if not isinstance(result, list):
            break
        out.extend([t for t in result if isinstance(t, dict)])
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


def revoke_token_by_id(
    token_id: str, *, admin_token: str, opener: Callable[..., Any] | None = None
) -> tuple[int, Any | None, str]:
    return cf_request_json("DELETE", f"/user/tokens/{token_id}", token=admin_token, opener=opener)


def find_token_id_by_name(
    name: str, *, admin_token: str, opener: Callable[..., Any] | None = None
) -> str | None:
    for row in list_user_tokens(admin_token=admin_token, opener=opener):
        if row.get("name") == name and isinstance(row.get("id"), str):
            return str(row["id"])
    return None


def create_readonly_zone_token(
    *,
    zone_id: str,
    token_name: str,
    permission_group_id: str,
    admin_token: str,
    opener: Callable[..., Any] | None = None,
) -> str:
    body: dict[str, Any] = {
        "name": token_name,
        "policies": [
            {
                "effect": "allow",
                "resources": {
                    "com.cloudflare.api.account.zone.*": {
                        f"com.cloudflare.api.account.zone.{zone_id}": "*",
                    }
                },
                "permission_groups": [{"id": permission_group_id}],
            }
        ],
    }
    st, payload, raw = cf_request_json(
        "POST", "/user/tokens", token=admin_token, body=body, opener=opener
    )
    if st != 200 or not isinstance(payload, dict) or not payload.get("success"):
        raise RuntimeError(f"create token failed HTTP {st}: {raw[:600]}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("create token: missing result")
    value = result.get("value")
    if not isinstance(value, str) or not value:
        raise RuntimeError("create token: API did not return secret value (show once)")
    return value


def vault_upsert_secret(
    *,
    name: str,
    value: str,
    studio_url: str,
    opener: Callable[..., Any] | None = None,
) -> None:
    """POST ``/api/secrets`` like ``scripts/vault-set.sh`` (Bearer or basic)."""
    secrets_key = (os.environ.get("SECRETS_API_KEY") or "").strip()
    admin_email = (os.environ.get("ADMIN_EMAILS") or "").split(",")[0].strip().strip('"').strip("'")
    admin_pass = (os.environ.get("ADMIN_ACCESS_PASSWORD") or "").strip()
    url = f"{studio_url.rstrip('/')}/api/secrets"
    payload_obj: dict[str, Any] = {
        "name": name,
        "value": value,
        "service": "cloudflare",
        "location": "",
        "description": (
            "Per-zone Cloudflare DNS read token "
            "(issued by scripts/cloudflare_issue_readonly_tokens.py)"
        ),
        "expires_at": None,
    }
    data = json.dumps(payload_obj).encode("utf-8")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if secrets_key:
        headers["Authorization"] = f"Bearer {secrets_key}"
    elif admin_email and admin_pass:
        token = b64encode(f"{admin_email}:{admin_pass}".encode()).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    else:
        raise RuntimeError(
            "Set SECRETS_API_KEY or ADMIN_EMAILS + ADMIN_ACCESS_PASSWORD for vault writes"
        )

    req = Request(url, data=data, headers=headers, method="POST")  # noqa: S310
    open_fn = opener or urlopen
    try:
        with open_fn(req, timeout=90) as resp:  # type: ignore[operator]
            code = getattr(resp, "status", 200)
            _ = resp.read()
    except HTTPError as e:
        code = e.code
        try:
            detail = e.read().decode("utf-8")
        except OSError:
            detail = ""
        raise RuntimeError(f"vault upsert HTTP {code}: {detail[:800]}") from e
    except URLError as e:
        raise RuntimeError(f"vault upsert URL error: {e.reason!s}") from e
    if code not in (200, 201):
        raise RuntimeError(f"vault upsert unexpected HTTP {code}")


def run_issue(
    *,
    admin_token: str,
    rotate: bool,
    studio_url: str,
    dry_run_vault: bool,
    opener: Callable[..., Any] | None,
) -> int:
    perm_id = fetch_dns_read_permission_group_id(admin_token=admin_token, opener=opener)
    print(f"Using DNS Read permission group id={perm_id}")
    for zv in ZONES:
        zid = resolve_zone_id(zv.apex, admin_token=admin_token, opener=opener)
        existing_id = find_token_id_by_name(zv.token_name, admin_token=admin_token, opener=opener)
        if existing_id and not rotate:
            print(f"{zv.apex}: already issued (token name {zv.token_name!r}, id={existing_id})")
            continue
        if existing_id and rotate:
            st, body, raw = revoke_token_by_id(existing_id, admin_token=admin_token, opener=opener)
            if st == 200 and isinstance(body, dict) and body.get("success"):
                print(f"{zv.apex}: revoked old token id={existing_id}")
            else:
                raise RuntimeError(f"revoke failed HTTP {st}: {raw[:400]}")
        secret = create_readonly_zone_token(
            zone_id=zid,
            token_name=zv.token_name,
            permission_group_id=perm_id,
            admin_token=admin_token,
            opener=opener,
        )
        print(f"{zv.apex}: issued new token for zone_id={zid}")
        if dry_run_vault:
            print(f"  (dry-run) would vault-set {zv.vault_key}")
        else:
            vault_upsert_secret(
                name=zv.vault_key,
                value=secret,
                studio_url=studio_url,
                opener=opener,
            )
            print(f"  stored in vault as {zv.vault_key}")
    print("done.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--rotate",
        action="store_true",
        help="Revoke existing token with the same name (if any), then create + vault-store",
    )
    p.add_argument(
        "--dry-run-vault",
        action="store_true",
        help="Create Cloudflare tokens but skip Studio vault POST (for local testing)",
    )
    args = p.parse_args(argv)

    admin = (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()
    if not admin:
        _eprint("CLOUDFLARE_API_TOKEN is required")
        return 2
    studio = (os.environ.get("STUDIO_URL") or "https://paperworklabs.com").strip()

    try:
        return run_issue(
            admin_token=admin,
            rotate=args.rotate,
            studio_url=studio,
            dry_run_vault=args.dry_run_vault,
            opener=None,
        )
    except RuntimeError as e:
        _eprint("error:", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
