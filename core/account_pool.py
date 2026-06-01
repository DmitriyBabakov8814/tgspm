"""
AccountPool — manages a pool of TG accounts for multi-account broadcasting.

Anti-ban strategy:
- Random delays (configurable range)
- Per-account daily send limit (configurable)
- Account rotation after N messages
- Cooldown after PeerFlood
- Auto-skip banned accounts
- Per-account flood wait handling
- Randomize message text slightly (optional)
"""
import asyncio
import random
import time
from datetime import datetime
from core.tg_client import TGClient
from core.errors import CampaignError, humanize_error, log_exception
from data import database as db


class AccountPool:
    def __init__(self):
        self._clients = {}   # acc_id -> TGClient
        self._locks = {}     # acc_id -> asyncio.Lock
        self._cooldowns = {} # acc_id -> timestamp when available again

    async def get_client(self, acc_id) -> TGClient:
        if acc_id not in self._clients:
            records = db.get_accounts()
            rec = next((r for r in records if r["id"] == acc_id), None)
            if not rec:
                raise CampaignError(f"Аккаунт #{acc_id} не найден")
            try:
                client = TGClient(rec)
                ok = await client.connect()
            except Exception as exc:
                log_exception(exc, f"get_client:{acc_id}")
                raise CampaignError(humanize_error(exc), cause=exc) from exc
            if not ok:
                raise CampaignError(f"Аккаунт {rec.get('phone')} не авторизован")
            self._clients[acc_id] = client
        return self._clients[acc_id]

    def set_cooldown(self, acc_id, seconds):
        self._cooldowns[acc_id] = time.time() + seconds

    def is_on_cooldown(self, acc_id):
        ts = self._cooldowns.get(acc_id, 0)
        return time.time() < ts

    def cooldown_remaining(self, acc_id):
        ts = self._cooldowns.get(acc_id, 0)
        return max(0, int(ts - time.time()))

    async def disconnect_all(self):
        for c in self._clients.values():
            try:
                await c.disconnect()
            except Exception:
                pass
        self._clients.clear()

    def remove(self, acc_id):
        self._clients.pop(acc_id, None)


# ── Multi-account sender ──────────────────────────────────────────────────────

class MultiAccountSender:
    def __init__(self, pool: AccountPool):
        self.pool = pool
        self._stop = False

    def stop(self):
        self._stop = True

    async def run_campaign(
        self,
        campaign_id: int,
        accounts: list,      # list of account dicts from DB
        targets: list,       # list of dicts with 'identifier' key
        text: str,
        campaign_type: str,  # 'contacts' | 'chats' | 'dm'
        delay_min: int = 5,
        delay_max: int = 15,
        msgs_per_account: int = 30,
        media_path: str = None,
        rotate_accounts: bool = True,
        progress_cb=None,
        log_cb=None,
    ):
        self._stop = False
        try:
            db.reset_daily_counts()
        except Exception as exc:
            log_exception(exc, "run_campaign.reset_daily_counts")

        active_accounts = [a for a in accounts if db.account_is_mailable(a)]
        if not active_accounts:
            raise CampaignError(
                "Нет готовых аккаунтов для рассылки. "
                "Завершите вход по телефону или проверьте аккаунты во вкладке «Аккаунты»."
            )

        try:
            db.update_campaign_status(campaign_id, "running", total=len(targets))
        except Exception as exc:
            log_exception(exc, "run_campaign.start")
            raise CampaignError(humanize_error(exc), cause=exc) from exc
        total = len(targets)
        sent = 0
        failed = 0
        acc_idx = 0
        acc_msg_count = 0  # messages sent from current account this rotation

        target_queue = list(targets)
        i = 0

        while i < len(target_queue) and not self._stop:
            target = target_queue[i]
            identifier = (
                target.get("identifier")
                or target.get("username")
                or target.get("phone")
                or target.get("user_id")
                or target.get("chat_id")
            )
            if not identifier:
                i += 1
                continue

            # Pick account
            attempts = 0
            client = None
            acc = None
            while attempts < len(active_accounts):
                candidate = active_accounts[acc_idx % len(active_accounts)]
                acc_id = candidate["id"]

                if candidate.get("is_banned") or candidate.get("is_muted"):
                    acc_idx += 1
                    attempts += 1
                    continue
                if candidate.get("status") not in ("active", "cooldown", None):
                    acc_idx += 1
                    attempts += 1
                    continue

                if self.pool.is_on_cooldown(acc_id):
                    remaining = self.pool.cooldown_remaining(acc_id)
                    if log_cb:
                        log_cb(f"⏳ Акк {candidate.get('phone','?')} на cooldown {remaining}s", "warn")
                    acc_idx += 1
                    attempts += 1
                    # check if ALL accounts are on cooldown
                    all_cd = all(self.pool.is_on_cooldown(a["id"]) for a in active_accounts if not a.get("is_banned"))
                    if all_cd:
                        min_cd = min(self.pool.cooldown_remaining(a["id"]) for a in active_accounts if not a.get("is_banned"))
                        if log_cb:
                            log_cb(f"⏸ Все аккаунты на cooldown. Ждём {min_cd}s...", "warn")
                        await asyncio.sleep(min(min_cd, 60))
                    continue

                # daily limit check
                daily_sent = candidate.get("daily_sent", 0)
                if daily_sent >= msgs_per_account and rotate_accounts:
                    acc_idx += 1
                    attempts += 1
                    continue

                try:
                    client = await self.pool.get_client(acc_id)
                    acc = candidate
                    break
                except Exception as exc:
                    if log_cb:
                        log_cb(f"❌ Не удалось подключить {candidate.get('phone','?')}: {humanize_error(exc)}", "err")
                    acc_idx += 1
                    attempts += 1
                    continue

            if client is None or acc is None:
                if log_cb:
                    log_cb("❌ Нет доступных аккаунтов для отправки", "err")
                break

            # Send
            display = str(identifier)[:30]
            if progress_cb:
                progress_cb(i + 1, total, display, sent, failed, acc.get("phone", "?"))

            msg_text = target.get("_text") or text
            ok, err_type, wait_sec, err_msg = await client.send_message_safe(identifier, msg_text, media_path)

            if ok:
                sent += 1
                db.log_send(campaign_id, identifier, "ok", account_phone=acc.get("phone"))
                db.increment_account_sent(acc["id"])
                acc["daily_sent"] = acc.get("daily_sent", 0) + 1
                acc_msg_count += 1
                if log_cb:
                    log_cb(f"✓ [{acc.get('phone','?')}] → {display}", "ok")
                i += 1

                # Rotate account after N messages
                if rotate_accounts and acc_msg_count >= msgs_per_account:
                    acc_idx += 1
                    acc_msg_count = 0
                    if log_cb:
                        log_cb(f"🔄 Смена аккаунта после {msgs_per_account} сообщений", "info")

                # Random delay
                delay = random.uniform(delay_min, delay_max)
                await asyncio.sleep(delay)

            elif err_type == "flood":
                if log_cb:
                    log_cb(f"🌊 FloodWait {wait_sec}s на {acc.get('phone','?')}", "warn")
                self.pool.set_cooldown(acc["id"], wait_sec + 10)
                # don't increment i, retry with next account

            elif err_type == "peer_flood":
                if log_cb:
                    log_cb(f"🚫 PeerFlood/мут на {acc.get('phone','?')} — смена аккаунта", "warn")
                db.mute_account(acc["id"])
                acc["is_muted"] = 1
                acc["status"] = "muted"
                self.pool.set_cooldown(acc["id"], 300)
                self.pool.remove(acc["id"])
                acc_idx += 1
                acc_msg_count = 0

            elif err_type == "ban":
                if log_cb:
                    log_cb(f"☠️ Аккаунт {acc.get('phone','?')} ЗАБЛОКИРОВАН", "err")
                db.ban_account(acc["id"])
                acc["is_banned"] = 1
                self.pool.remove(acc["id"])
                acc_idx += 1
                acc_msg_count = 0
                failed += 1
                db.log_send(campaign_id, identifier, "ban", "Account banned", acc.get("phone"))
                i += 1  # skip this target

            elif err_type == "skip":
                failed += 1
                db.log_send(campaign_id, identifier, "skip", "Privacy/unavailable", acc.get("phone"))
                if log_cb:
                    log_cb(f"⚠ Пропуск {display} (приватность/недоступен)", "warn")
                i += 1

            else:
                failed += 1
                db.log_send(campaign_id, identifier, "fail", err_msg, acc.get("phone"))
                if log_cb:
                    log_cb(f"✗ [{acc.get('phone','?')}] {err_msg or 'ошибка'} → {display}", "err")
                i += 1

            try:
                db.update_campaign_status(campaign_id, "running", sent=sent, failed=failed)
            except Exception as exc:
                log_exception(exc, "run_campaign.update_status")

        status = "stopped" if self._stop else "finished"
        try:
            db.update_campaign_status(campaign_id, status, sent=sent, failed=failed)
        except Exception as exc:
            log_exception(exc, "run_campaign.finish")
        return sent, failed
