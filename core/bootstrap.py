"""Resolve Telethon API credentials without manual UI input."""
import os

from core.errors import ValidationError
from data import database as db


def resolve_bootstrap_credentials() -> tuple[str, str] | tuple[None, None]:
    """Return (api_id, api_hash) or (None, None) if my.telegram.org pre-step is needed."""
    for acc in db.get_accounts():
        api_id = str(acc.get("api_id") or "").strip()
        api_hash = str(acc.get("api_hash") or "").strip()
        if api_id and api_hash and len(api_hash) >= 16:
            db.set_setting("bootstrap_api_id", api_id)
            db.set_setting("bootstrap_api_hash", api_hash)
            return api_id, api_hash

    api_id = (db.get_setting("bootstrap_api_id") or "").strip()
    api_hash = (db.get_setting("bootstrap_api_hash") or "").strip()
    if api_id and api_hash:
        return api_id, api_hash

    api_id = os.environ.get("TG_BOOTSTRAP_API_ID", "").strip()
    api_hash = os.environ.get("TG_BOOTSTRAP_API_HASH", "").strip()
    if api_id and api_hash:
        db.set_setting("bootstrap_api_id", api_id)
        db.set_setting("bootstrap_api_hash", api_hash)
        return api_id, api_hash

    return None, None


def get_bootstrap_credentials() -> tuple[str, str]:
    api_id, api_hash = resolve_bootstrap_credentials()
    if not api_id or not api_hash:
        raise ValidationError(
            "Для первого аккаунта сначала отправьте код — API ID/Hash подтянутся автоматически "
            "с my.telegram.org."
        )
    return api_id, api_hash


def save_bootstrap(api_id: str, api_hash: str):
    db.set_setting("bootstrap_api_id", str(api_id).strip())
    db.set_setting("bootstrap_api_hash", str(api_hash).strip())
