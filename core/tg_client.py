import asyncio
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.contacts import SearchRequest
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, PeerFloodError,
    ChatWriteForbiddenError, UserBannedInChannelError,
    UserNotMutualContactError, InputUserDeactivatedError,
    UserDeactivatedBanError, PhoneNumberBannedError,
    SessionPasswordNeededError, AuthKeyError,
    PhoneCodeInvalidError, PhoneCodeExpiredError,
    PasswordHashInvalidError, PhoneNumberInvalidError,
    ApiIdInvalidError,
)

from core.errors import (
    AuthError, MediaError, NetworkError, TelegramError,
    ValidationError, humanize_error, log_exception,
)

SESSION_DIR = Path(__file__).parent.parent / "sessions"
SESSION_DIR.mkdir(exist_ok=True)

HARD_BAN_ERRORS = (UserDeactivatedBanError, PhoneNumberBannedError, AuthKeyError)
SKIP_ERRORS = (
    UserPrivacyRestrictedError, UserNotMutualContactError,
    InputUserDeactivatedError, ChatWriteForbiddenError, UserBannedInChannelError,
)
AUTH_ERRORS = (
    PhoneCodeInvalidError, PhoneCodeExpiredError, PasswordHashInvalidError,
    PhoneNumberInvalidError, ApiIdInvalidError, SessionPasswordNeededError,
)


class TGClient:
    def __init__(self, acc_record):
        """acc_record: dict from DB accounts table"""
        if not acc_record:
            raise ValidationError("Запись аккаунта не найдена")

        self.acc = acc_record
        self.acc_id = acc_record.get("id")
        self.phone = acc_record.get("phone") or "unknown"

        try:
            api_id = int(acc_record["api_id"])
            api_hash = str(acc_record["api_hash"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("Некорректные API ID / API Hash") from exc

        if not api_hash:
            raise ValidationError("API Hash не может быть пустым")

        proxy = self._parse_proxy(acc_record.get("proxy") or "")

        if acc_record.get("session_string"):
            session = StringSession(acc_record["session_string"])
        elif acc_record.get("session_path"):
            session = acc_record["session_path"]
        else:
            session = str(SESSION_DIR / f"acc_{acc_record['id']}")

        try:
            self.client = TelegramClient(
                session, api_id, api_hash,
                proxy=proxy or None,
                connection_retries=3,
                retry_delay=5,
                flood_sleep_threshold=60,
            )
        except Exception as exc:
            log_exception(exc, "TGClient.__init__")
            raise ValidationError("Не удалось создать Telegram-клиент") from exc

        self.connected = False

    def _parse_proxy(self, proxy_str):
        if not proxy_str:
            return None
        try:
            import socks
            proxy_str = proxy_str.strip()
            if "://" in proxy_str:
                from urllib.parse import urlparse
                p = urlparse(proxy_str)
                if not p.hostname or not p.port:
                    raise ValidationError("Некорректный формат прокси")
                ptype = socks.SOCKS5 if "socks5" in p.scheme else (
                    socks.SOCKS4 if "socks4" in p.scheme else socks.HTTP)
                return (ptype, p.hostname, p.port, True, p.username, p.password)
            parts = proxy_str.split(":")
            if len(parts) >= 2:
                return (socks.SOCKS5, parts[0], int(parts[1]),
                        True, parts[2] if len(parts) > 2 else None,
                        parts[3] if len(parts) > 3 else None)
            raise ValidationError("Некорректный формат прокси")
        except ValidationError:
            raise
        except Exception as exc:
            log_exception(exc, "parse_proxy")
            raise ValidationError("Не удалось разобрать прокси") from exc

    async def connect(self):
        try:
            await self.client.connect()
            self.connected = True
            return await self.client.is_user_authorized()
        except OSError as exc:
            self.connected = False
            log_exception(exc, "TGClient.connect")
            raise NetworkError(humanize_error(exc), cause=exc) from exc
        except Exception as exc:
            self.connected = False
            log_exception(exc, "TGClient.connect")
            raise TelegramError(humanize_error(exc), cause=exc) from exc

    async def disconnect(self):
        try:
            await self.client.disconnect()
        except Exception as exc:
            log_exception(exc, "TGClient.disconnect")
        finally:
            self.connected = False

    async def get_me(self):
        try:
            me = await self.client.get_me()
            if me:
                return {
                    "id": me.id,
                    "first_name": me.first_name or "",
                    "username": me.username or "",
                    "phone": me.phone or self.phone,
                }
            return None
        except Exception as exc:
            log_exception(exc, "TGClient.get_me")
            raise TelegramError(humanize_error(exc), cause=exc) from exc

    async def send_code(self):
        try:
            result = await self.client.send_code_request(self.phone)
            return result.phone_code_hash
        except AUTH_ERRORS as exc:
            log_exception(exc, "TGClient.send_code")
            if isinstance(exc, SessionPasswordNeededError):
                raise AuthError("2FA_REQUIRED", cause=exc) from exc
            raise AuthError(humanize_error(exc), cause=exc) from exc
        except Exception as exc:
            log_exception(exc, "TGClient.send_code")
            raise TelegramError(humanize_error(exc), cause=exc) from exc

    async def sign_in(self, code, phone_code_hash, password=None):
        try:
            await self.client.sign_in(self.phone, code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if password:
                try:
                    await self.client.sign_in(password=password)
                except PasswordHashInvalidError as exc:
                    raise AuthError("Неверный пароль 2FA", cause=exc) from exc
            else:
                raise AuthError("2FA_REQUIRED")
        except AUTH_ERRORS as exc:
            log_exception(exc, "TGClient.sign_in")
            raise AuthError(humanize_error(exc), cause=exc) from exc
        except Exception as exc:
            log_exception(exc, "TGClient.sign_in")
            raise AuthError(humanize_error(exc), cause=exc) from exc

    async def get_session_string(self):
        try:
            return StringSession.save(self.client.session)
        except Exception as exc:
            log_exception(exc, "TGClient.get_session_string")
            raise TelegramError("Не удалось сохранить сессию", cause=exc) from exc

    async def send_message_safe(self, target, text, media_path=None):
        """Returns (ok, error_type, wait_seconds, error_msg)"""
        if media_path and not Path(media_path).is_file():
            return False, "error", 0, "Файл медиа не найден"

        try:
            entity = await self.client.get_entity(target)
            if media_path:
                await self.client.send_file(entity, media_path, caption=text)
            else:
                await self.client.send_message(entity, text)
            return True, None, 0, None
        except FloodWaitError as exc:
            return False, "flood", exc.seconds, humanize_error(exc)
        except PeerFloodError as exc:
            return False, "peer_flood", 300, humanize_error(exc)
        except SKIP_ERRORS as exc:
            return False, "skip", 0, humanize_error(exc)
        except HARD_BAN_ERRORS as exc:
            return False, "ban", 0, humanize_error(exc)
        except Exception as exc:
            log_exception(exc, f"send_message_safe:{target}")
            return False, "error", 0, humanize_error(exc)

    async def parse_channel_commenters(self, channel_username, limit_posts=30, progress_cb=None):
        users = {}
        try:
            channel = await self.client.get_entity(channel_username)
            posts = await self.client.get_messages(channel, limit=limit_posts)
        except Exception as exc:
            log_exception(exc, "parse_channel_commenters")
            raise TelegramError(humanize_error(exc), cause=exc) from exc

        total = len(posts)
        for idx, post in enumerate(posts):
            if progress_cb:
                progress_cb(idx + 1, total, f"Пост {post.id}")
            try:
                comments = await self.client.get_messages(channel, reply_to=post.id, limit=200)
                for c in comments:
                    if c.sender_id and c.sender_id not in users:
                        sender = c.sender
                        if sender and not getattr(sender, "bot", False):
                            users[c.sender_id] = {
                                "user_id": str(c.sender_id),
                                "username": getattr(sender, "username", None) or "",
                                "first_name": getattr(sender, "first_name", None) or "",
                                "last_name": getattr(sender, "last_name", None) or "",
                                "comment_text": (c.text or "")[:200],
                                "post_id": str(post.id),
                            }
            except Exception as exc:
                log_exception(exc, f"parse_post:{post.id}")
            await asyncio.sleep(0.5)
        return list(users.values())

    async def invite_to_channel(self, my_channel, username):
        try:
            channel = await self.client.get_entity(my_channel)
            user = await self.client.get_entity(username)
            await self.client(InviteToChannelRequest(channel, [user]))
            return True, None
        except FloodWaitError as exc:
            return False, f"flood:{exc.seconds}"
        except SKIP_ERRORS as exc:
            return False, f"skip:{type(exc).__name__}"
        except HARD_BAN_ERRORS as exc:
            return False, f"ban:{type(exc).__name__}"
        except Exception as exc:
            log_exception(exc, f"invite:{username}")
            return False, humanize_error(exc)[:80]

    async def search_chats(self, query, limit=20):
        try:
            result = await self.client(SearchRequest(q=query, limit=limit))
            found = []
            for c in result.chats:
                found.append({
                    "chat_id": str(c.id),
                    "username": getattr(c, "username", None) or "",
                    "title": getattr(c, "title", ""),
                    "chat_type": type(c).__name__.lower(),
                    "members_count": getattr(c, "participants_count", 0) or 0,
                })
            return found
        except Exception as exc:
            log_exception(exc, "search_chats")
            raise TelegramError(humanize_error(exc), cause=exc) from exc

    async def invite_users_to_channel(self, my_channel, usernames, delay=10, progress_cb=None):
        results = []
        for idx, username in enumerate(usernames):
            if progress_cb:
                progress_cb(idx + 1, len(usernames), username)
            ok, err = await self.invite_to_channel(my_channel, username)
            results.append((username, ok, err))
            if ok:
                await asyncio.sleep(delay)
            elif err and err.startswith("flood:"):
                wait = int(err.split(":")[1])
                await asyncio.sleep(wait + 5)
            else:
                await asyncio.sleep(2)
        return results
