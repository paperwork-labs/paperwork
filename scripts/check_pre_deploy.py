#!/usr/bin/env python3
"""Pre-deploy guard: Brain Vercel quota snapshot + required Vercel env vars.

Exit codes:
  0  Success
  1  Unexpected error (network/parse)
  2  Deploy quota below threshold
  3  Required env var missing on target
  4  Missing BRAIN_ADMIN_TOKEN / VERCEL_API_TOKEN / Clerk+Cloudflare tokens when a step needs them
  5  --require-all-checks set but a skip flag was used
  6  Clerk↔Cloudflare DNS drift (``scripts/reconcile_clerk_dns.py --check-only`` failed)

Requires PyYAML (``pip install pyyaml``) — same as apis/brain.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML is required: pip install pyyaml\n")
    sys.exit(4)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = _REPO_ROOT / "apis" / "brain" / "data" / "required_env_vars.yaml"
_VERCEL_PROJECTS_JSON = _REPO_ROOT / "scripts" / "vercel-projects.json"

DEFAULT_BRAIN_BASE = os.environ.get("BRAIN_BASE_URL", "https://brain-api.onrender.com").rstrip("/")
DEFAULT_QUOTA_THRESHOLD = 5
DEFAULT_TEAM_ID = "team_RwfzJ9ySyLuVcoWdKJfXC7h5"
HOBBY_DEPLOY_DAILY_CAP = 100
VERCEL_API_ORIGIN = os.environ.get("VERCEL_API_BASE_URL", "https://api.vercel.com").rstrip("/")
# Clerk-backed Vercel apps: DNS must match Clerk ``cname_targets`` + paperworklabs ops rows.
_PROJECTS_CLERK_DNS_GUARD: frozenset[str] = frozenset({"studio", "axiomfolio", "filefree"})


def _eprint(*args: object) -> None:
    sys.stderr.write(" ".join(str(a) for a in args) + "\n")


def _brain_quota_path(base: str) -> str:
    return f"{base.rstrip('/')}/api/v1/admin/vercel-quota"


def _http_get_json(
    url: str, headers: dict[str, str], *, timeout: float = 60.0
) -> tuple[int, Any | None, str]:
    scheme = urlparse(url).scheme
    if scheme not in ("http", "https"):
        _eprint(f"disallowed URL scheme {scheme!r} for {url!r}")
        return 0, None, "bad scheme"
    req = Request(url, headers=headers, method="GET")  # noqa: S310
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
            try:
                return status, json.loads(raw), raw
            except json.JSONDecodeError:
                return status, None, raw
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except OSError:
            body = ""
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        return e.code, parsed, body
    except URLError as e:
        _eprint(f"HTTP error: {e.reason!s}")
        return 0, None, str(e.reason)


def _extract_outer_data(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("success") is True:
        inner = payload.get("data")
        if isinstance(inner, dict):
            return inner
    if isinstance(payload, dict):
        return payload
    return {}


def _remaining_deploys_from_snapshots(data: dict[str, Any]) -> tuple[int | None, str | None]:
    """Return (remaining deploys until daily cap, reset_at_iso_utc) or (None, None)."""
    if "remaining" in data:
        try:
            rem = int(data["remaining"])
        except (TypeError, ValueError):
            rem = None
        else:
            return rem, data.get("reset_at") or data.get("resets_at")

    total = data.get("total")
    used = data.get("used")
    if total is not None and used is not None:
        try:
            return max(0, int(total) - int(used)), data.get("reset_at") or data.get("resets_at")
        except (TypeError, ValueError):
            pass

    snapshots = data.get("snapshots")
    if not isinstance(snapshots, list):
        return None, None

    used_today = 0
    utc_date: str | None = None
    for s in snapshots:
        if not isinstance(s, dict):
            continue
        if s.get("window_days") != 1:
            continue
        if s.get("project_name") == "(team)" or s.get("project_id") in (None, ""):
            continue
        meta = s.get("meta") if isinstance(s.get("meta"), dict) else {}
        cal = meta.get("calendar_day_deploy_count_utc")
        if cal is not None:
            try:
                used_today += int(cal)
            except (TypeError, ValueError):
                continue
        if meta.get("utc_date") and isinstance(meta["utc_date"], str):
            utc_date = meta["utc_date"]

    remaining = max(0, HOBBY_DEPLOY_DAILY_CAP - used_today)

    now = datetime.now(UTC)
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    reset_iso = next_midnight.isoformat().replace("+00:00", "Z")
    if utc_date:
        try:
            y, m, d = (int(x) for x in utc_date.split("-")[:3])
            day = datetime(y, m, d, tzinfo=UTC) + timedelta(days=1)
            reset_iso = day.isoformat().replace("+00:00", "Z")
        except (ValueError, TypeError):
            pass

    return remaining, reset_iso


def _load_manifest(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a mapping")
    return data


def _slug_env_project_id(slug: str) -> str | None:
    env_name = f"VERCEL_PROJECT_ID_{slug.upper().replace('-', '_')}"
    override = (os.environ.get(env_name) or "").strip()
    if override and not override.upper().startswith("TBD"):
        return override

    if not _VERCEL_PROJECTS_JSON.is_file():
        return None
    blob = json.loads(_VERCEL_PROJECTS_JSON.read_text(encoding="utf-8"))
    for app in blob.get("apps") or []:
        if not isinstance(app, dict):
            continue
        if app.get("slug") != slug:
            continue
        pid = str(app.get("projectId") or "").strip()
        if pid.upper().startswith("TBD") or not pid:
            return None
        return pid
    return None


def _normalize_vercel_targets(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        out: list[str] = []
        for x in raw:
            if isinstance(x, str):
                out.append(x)
        return out
    return []


def _env_entry_covers_target(entry: dict[str, Any], target: str) -> bool:
    targets = _normalize_vercel_targets(entry.get("target"))
    return target in targets


def _fetch_vercel_envs(
    project_id: str, token: str, team_id: str
) -> tuple[list[dict[str, Any]] | None, str]:
    params = urlencode({"teamId": team_id})
    url = f"{VERCEL_API_ORIGIN}/v9/projects/{project_id}/env?{params}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    status, payload, raw = _http_get_json(url, headers)
    if status != 200:
        return None, f"Vercel env list HTTP {status}: {raw[:500]!s}"

    envs_raw: Any = payload
    if isinstance(payload, dict) and "envs" in payload:
        envs_raw = payload["envs"]
    if not isinstance(envs_raw, list):
        return None, "unexpected Vercel env response shape"

    out: list[dict[str, Any]] = []
    for e in envs_raw:
        if isinstance(e, dict):
            out.append(e)
    return out, ""


def _missing_required_keys(
    env_rows: list[dict[str, Any]], required: list[str], target: str
) -> list[str]:
    missing: list[str] = []
    for key in required:
        matched = False
        for row in env_rows:
            if row.get("key") != key:
                continue
            if _env_entry_covers_target(row, target):
                matched = True
                break
        if not matched:
            missing.append(key)
    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brain + Vercel pre-deploy guard.")
    parser.add_argument(
        "--project", required=True, help="Vercel project slug (see vercel-projects.json)."
    )
    parser.add_argument(
        "--target",
        required=True,
        choices=("production", "preview", "development"),
        help="Deployment target (Vercel env target).",
    )
    parser.add_argument(
        "--brain-base-url", default=DEFAULT_BRAIN_BASE, help="Brain API origin (no /api/v1 path)."
    )
    parser.add_argument("--quota-threshold", type=int, default=DEFAULT_QUOTA_THRESHOLD)
    parser.add_argument(
        "--skip-quota", action="store_true", help="Skip Brain quota check (emergency)."
    )
    parser.add_argument(
        "--skip-env-vars", action="store_true", help="Skip required env manifest check (emergency)."
    )
    parser.add_argument(
        "--skip-clerk-dns",
        action="store_true",
        help=(
            "Skip scripts/reconcile_clerk_dns.py --check-only "
            "(emergency; studio/axiomfolio/filefree only)."
        ),
    )
    parser.add_argument(
        "--require-all-checks",
        action="store_true",
        help="Fail if any skip flag is set (prevents silent bypass).",
    )
    args = parser.parse_args(argv)

    bypass_bits: list[str] = []
    if args.skip_quota:
        bypass_bits.append("skip-quota")
    if args.skip_env_vars:
        bypass_bits.append("skip-env-vars")
    if args.skip_clerk_dns:
        bypass_bits.append("skip-clerk-dns")
    if bypass_bits and args.require_all_checks:
        _eprint(
            "PRE_DEPLOY_GUARD_BYPASS_USED "
            + " ".join(f"{k}=true" for k in bypass_bits)
            + " — refused under --require-all-checks",
        )
        return 5

    if bypass_bits:
        _eprint(
            "WARNING: PRE_DEPLOY_GUARD_BYPASS_USED "
            + " ".join(b.replace("-", "_") + "=true" for b in bypass_bits)
            + " — emergency bypass; quota/env enforcement skipped.",
        )
        sys.stderr.write(
            "::warning::PRE_DEPLOY_GUARD_BYPASS_USED " + ",".join(bypass_bits) + "\n",
        )

    # --- Quota ---
    if not args.skip_quota:
        brain_tok = (os.environ.get("BRAIN_ADMIN_TOKEN") or "").strip()
        if not brain_tok:
            _eprint(
                "BRAIN_ADMIN_TOKEN is not set. Export the same value as Brain's BRAIN_API_SECRET "
                "(header X-Brain-Secret on /api/v1/admin/*).",
            )
            return 4

        quota_url = _brain_quota_path(args.brain_base_url)
        headers = {
            "X-Brain-Secret": brain_tok,
            "Accept": "application/json",
        }
        status, payload, raw = _http_get_json(quota_url, headers)
        if status != 200 or payload is None:
            _eprint(f"Brain quota HTTP {status}: {raw[:800]!s}")
            return 1

        outer = _extract_outer_data(payload)
        remaining, reset_iso = _remaining_deploys_from_snapshots(outer)
        if remaining is None:
            _eprint(
                "Could not derive remaining deploy quota from Brain /admin/vercel-quota payload."
            )
            return 1

        if remaining < args.quota_threshold:
            reset_s = reset_iso if reset_iso else "unknown"
            _eprint(
                f"QUOTA EXHAUSTED — {remaining} remaining, threshold {args.quota_threshold}. "
                f"Reset at {reset_s}. Wait or upgrade Vercel Pro.",
            )
            return 2
    else:
        remaining = None

    # --- Env vars ---
    if not args.skip_env_vars:
        vtok = (os.environ.get("VERCEL_API_TOKEN") or "").strip()
        if not vtok:
            _eprint("VERCEL_API_TOKEN is not set. Required for Vercel env verification.")
            return 4

        manifest = _load_manifest(_MANIFEST_PATH)
        proj_cfg = manifest.get(args.project)
        if not isinstance(proj_cfg, dict):
            _eprint(f"No manifest entry for project {args.project!r} in {_MANIFEST_PATH}")
            return 3

        required = proj_cfg.get(args.target)
        if required is None:
            _eprint(f"No required env list for {args.project}:{args.target} in manifest.")
            return 3
        if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
            _eprint(f"Invalid manifest shape for {args.project}:{args.target}")
            return 3

        project_id = _slug_env_project_id(args.project)
        if not project_id:
            _eprint(
                f"Could not resolve Vercel project id for slug {args.project!r}. "
                f"Set VERCEL_PROJECT_ID_{args.project.upper().replace('-', '_')} or update "
                f"{_VERCEL_PROJECTS_JSON} with a real prj_… id.",
            )
            return 4

        env_rows, err = _fetch_vercel_envs(project_id, vtok, DEFAULT_TEAM_ID)
        if env_rows is None:
            _eprint(err)
            return 1

        missing = _missing_required_keys(env_rows, required, args.target)
        if missing:
            _eprint(
                f"MISSING_ENV_VARS for {args.project} target={args.target}: " + ", ".join(missing),
            )
            return 3

    # --- Clerk ↔ Cloudflare DNS (Clerk ``cname_targets`` + paperworklabs ops rows) ---
    if args.project in _PROJECTS_CLERK_DNS_GUARD and not args.skip_clerk_dns:
        clerk = (os.environ.get("CLERK_SECRET_KEY") or "").strip()
        cf = (os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_TOKEN") or "").strip()
        if not clerk or not cf:
            _eprint(
                "CLERK_SECRET_KEY and CLOUDFLARE_API_TOKEN (or CF_TOKEN) are required for "
                f"Clerk DNS verification on project {args.project!r}. "
                "Configure GitHub Actions secrets / local env, or pass --skip-clerk-dns "
                "(emergency only).",
            )
            return 4
        script_path = _REPO_ROOT / "scripts" / "reconcile_clerk_dns.py"
        if not script_path.is_file():
            _eprint(f"Clerk DNS script missing: {script_path}")
            return 1
        try:
            proc = subprocess.run(
                [sys.executable, str(script_path), "--check-only"],
                cwd=str(_REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=180,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            _eprint("Clerk DNS check timed out after 180s.")
            return 1
        if proc.returncode != 0:
            _eprint(
                "CLERK_DNS_CHECK_FAILED — scripts/reconcile_clerk_dns.py --check-only "
                f"exited {proc.returncode}.\n--- stdout ---\n{proc.stdout}"
                f"\n--- stderr ---\n{proc.stderr}",
            )
            return 6 if proc.returncode == 2 else 1

    bits: list[str] = []
    if not args.skip_quota:
        bits.append(f"{remaining} quota remaining")
    else:
        bits.append("quota check skipped")
    if not args.skip_env_vars:
        bits.append("all required env vars present")
    else:
        bits.append("env var check skipped")
    if args.project in _PROJECTS_CLERK_DNS_GUARD:
        if args.skip_clerk_dns:
            bits.append("Clerk DNS check skipped")
        else:
            bits.append("Clerk DNS check passed")
    sys.stdout.write(f"OK — {', '.join(bits)} for {args.project}:{args.target}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception as e:
        _eprint(f"check_pre_deploy failed: {e}")
        raise SystemExit(1) from e
