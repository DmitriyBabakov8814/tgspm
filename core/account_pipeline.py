"""
Полный цикл подготовки аккаунта к рассылке:
1) Вход через Telethon (session / код)
2) Проверка статуса (актив / мут / бан)
3) Получение API ID/Hash с my.telegram.org (после авторизации)
"""
import asyncio
from typing import Callable

from core.errors import AuthError, ValidationError, humanize_error, log_exception
from core.my_telegram_api import MyTelegramOrgClient
from core.tg_client import TGClient
from data import database as db

ProgressCb = Callable[[str], None]


def get_bootstrap_credentials() -> tuple[str, str]:
    from core.bootstrap import get_bootstrap_credentials as _get
    return _get()


async def detect_account_health(client: TGClient) -> str:
    """Return status: active | muted | banned | unauthorized"""
    try:
        if not await client.connect():
            return "unauthorized"
        me = await client.get_me()
        if not me:
            return "unauthorized"

        from telethon.tl.functions.account import GetAccountTTLRequest
        try:
            await client.client(GetAccountTTLRequest())
        except Exception as exc:
            name = type(exc).__name__.lower()
            msg = str(exc).lower()
            if "deactivated" in name or "banned" in name or "userdeactivated" in name:
                return "banned"
            if "peer_flood" in name or "spam" in msg or "muted" in msg:
                return "muted"

        return "active"
    except Exception as exc:
        log_exception(exc, "detect_account_health")
        name = type(exc).__name__.lower()
        if "ban" in name or "deactivated" in name:
            return "banned"
        if "flood" in name or "spam" in name:
            return "muted"
        return "unauthorized"




async def charge_with_session(
    session_string: str,
    *,
    phone: str | None = None,
    proxy: str | None = None,
    bootstrap_api_id: str | None = None,
    bootstrap_api_hash: str | None = None,
    lolz_item_id: str | None = None,
    notes: str = "",
    progress: ProgressCb | None = None,
) -> int:
    """Import session, verify, return account id."""
    api_id, api_hash = bootstrap_api_id or "", bootstrap_api_hash or ""
    if not api_id or not api_hash:
        api_id, api_hash = get_bootstrap_credentials()

    if progress:
        progress("Подключение Telethon...")

    rec = {
        "id": 0,
        "phone": phone or "",
        "api_id": api_id,
        "api_hash": api_hash,
        "session_string": session_string,
        "proxy": proxy or "",
    }
    client = TGClient(rec)
    status = await detect_account_health(client)
    me = await client.get_me()
    phone = (me or {}).get("phone") or phone or ""
    session_string = await client.get_session_string()
    await client.disconnect()

    acc_id = db.add_account(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        session_string=session_string,
        proxy=proxy,
        notes=notes or "",
    )
    if lolz_item_id:
        db.update_account(acc_id, lolz_item_id=str(lolz_item_id))

    is_banned = 1 if status == "banned" else 0
    is_muted = 1 if status == "muted" else 0
    db.update_account(
        acc_id,
        status=status,
        is_banned=is_banned,
        is_muted=is_muted,
    )
    return acc_id


def apply_mytg_credentials_sync(acc_id: int, phone: str, code: str, random_hash: str, proxy: str | None):
    client = MyTelegramOrgClient(proxy=proxy)
    api_id, api_hash = client.login_and_get_credentials(phone, random_hash, code)
    db.update_account(acc_id, api_id=api_id, api_hash=api_hash)


async def send_mytg_code(phone: str, proxy: str | None) -> tuple[MyTelegramOrgClient, str]:
    client = MyTelegramOrgClient(proxy=proxy)
    random_hash = client.send_password(phone)
    return client, random_hash


async def telethon_send_code(phone: str, proxy: str | None, bootstrap_api_id: str, bootstrap_api_hash: str):
    rec = {"id": 0, "phone": phone, "api_id": bootstrap_api_id, "api_hash": bootstrap_api_hash, "proxy": proxy or ""}
    client = TGClient(rec)
    await client.connect()
    return client, await client.send_code()


async def telethon_sign_in(client: TGClient, code: str, phone_hash: str, password: str | None = None):
    await client.sign_in(code, phone_hash, password)
    return await client.get_session_string(), await client.get_me()
