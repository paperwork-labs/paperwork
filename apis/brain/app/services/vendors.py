"""JSON-backed vendor catalog (WS-76).

medallion: ops

Source file defaults to ``apis/brain/data/vendors.json``. Override with
``BRAIN_VENDORS_JSON`` for tests or isolated stores.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from app.schemas.vendor import Vendor, VendorCreate, VendorsRoot, VendorUpdate

_ENV_STORE = "BRAIN_VENDORS_JSON"


def vendors_path() -> Path:
    env = os.environ.get(_ENV_STORE, "").strip()
    if env:
        return Path(env)
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data" / "vendors.json"
    return Path(__file__).resolve().parent.parent.parent / "data" / "vendors.json"


def _write_root_atomic(path: Path, root: VendorsRoot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        root.model_dump(by_alias=True, mode="json"),
        indent=2,
        ensure_ascii=False,
    )
    fd, tmppath = tempfile.mkstemp(
        suffix=".json",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmppath, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmppath)
        raise


def load_vendors() -> VendorsRoot:
    """Load and validate ``vendors.json``."""
    raw = vendors_path().read_text(encoding="utf-8")
    data = json.loads(raw)
    return VendorsRoot.model_validate(data)


def list_vendors(category: str | None = None) -> list[Vendor]:
    items = load_vendors().vendors
    if category is None or not (c := category.strip()):
        return list(items)
    return [v for v in items if v.category == c]


def get_vendor(vendor_id: str) -> Vendor | None:
    vid = vendor_id.strip()
    for v in load_vendors().vendors:
        if v.id == vid:
            return v
    return None


def create_vendor(body: VendorCreate) -> Vendor:
    path = vendors_path()
    root = load_vendors()
    if get_vendor(body.id):
        msg = "vendor id already exists"
        raise ValueError(msg)
    vendor = Vendor(**body.model_dump())
    root = VendorsRoot(
        schema_=root.schema_,
        vendors=[*root.vendors, vendor],
    )
    _write_root_atomic(path, root)
    return vendor


def update_vendor(vendor_id: str, body: VendorUpdate) -> Vendor:
    vid = vendor_id.strip()
    path = vendors_path()
    root = load_vendors()
    updated: Vendor | None = None
    new_list: list[Vendor] = []
    for v in root.vendors:
        if v.id == vid:
            updated = Vendor(
                id=vid,
                name=body.name,
                domain=body.domain,
                category=body.category,
                monthly_estimate_usd=body.monthly_estimate_usd,
                contract_url=body.contract_url,
                owner_persona=body.owner_persona,
                organization_id=body.organization_id,
            )
            new_list.append(updated)
        else:
            new_list.append(v)
    if updated is None:
        msg = "vendor not found"
        raise KeyError(msg)
    root_out = VendorsRoot(schema_=root.schema_, vendors=new_list)
    _write_root_atomic(path, root_out)
    return updated
