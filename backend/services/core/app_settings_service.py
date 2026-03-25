from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models.app_settings import AppSettings


def get_or_create_app_settings(db: Session) -> AppSettings:
    settings = db.query(AppSettings).first()
    if settings:
        return settings
    settings = AppSettings()
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings
