"""Centralized exceptions, logging, and user-friendly error messages."""
import logging
import sqlite3
import traceback
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "data"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

_logger = logging.getLogger("tgsender")


class TGSenderError(Exception):
    """Base exception with a message safe to show in the UI."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.user_message = message
        self.cause = cause


class ValidationError(TGSenderError):
    """Invalid user input or configuration."""


class DatabaseError(TGSenderError):
    """SQLite / persistence failures."""


class NetworkError(TGSenderError):
    """Connection, timeout, proxy, DNS issues."""


class AuthError(TGSenderError):
    """Telegram / my.telegram.org authentication failures."""


class TelegramError(TGSenderError):
    """Telegram API operational errors."""


class MediaError(TGSenderError):
    """Missing or unreadable media files."""


class CampaignError(TGSenderError):
    """Broadcast / parser campaign failures."""


def setup_logging() -> None:
    if _logger.handlers:
        return
    _logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    _logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(fmt)
    _logger.addHandler(sh)


def log_exception(exc: BaseException, context: str = "") -> None:
    setup_logging()
    prefix = f"{context}: " if context else ""
    _logger.error("%s%s\n%s", prefix, exc, traceback.format_exc())


def humanize_error(exc: BaseException) -> str:
    """Convert any exception into a short Russian message for the UI."""
    if isinstance(exc, TGSenderError):
        return exc.user_message

    msg = str(exc).strip()

    # ── Telethon ──────────────────────────────────────────────────────────────
    try:
        from telethon.errors import (
            ApiIdInvalidError,
            AuthKeyError,
            FloodWaitError,
            PasswordHashInvalidError,
            PhoneCodeExpiredError,
            PhoneCodeInvalidError,
            PhoneNumberBannedError,
            PhoneNumberFloodError,
            PhoneNumberInvalidError,
            SessionPasswordNeededError,
            UserDeactivatedBanError,
        )

        if isinstance(exc, PhoneNumberInvalidError):
            return "Неверный формат номера телефона. Используйте +код_страны."
        if isinstance(exc, PhoneCodeInvalidError):
            return "Неверный код подтверждения."
        if isinstance(exc, PhoneCodeExpiredError):
            return "Код истёк. Запросите новый код."
        if isinstance(exc, SessionPasswordNeededError):
            return "2FA_REQUIRED"
        if isinstance(exc, PasswordHashInvalidError):
            return "Неверный пароль двухфакторной аутентификации."
        if isinstance(exc, PhoneNumberBannedError):
            return "Номер телефона заблокирован в Telegram."
        if isinstance(exc, UserDeactivatedBanError):
            return "Аккаунт деактивирован или заблокирован."
        if isinstance(exc, AuthKeyError):
            return "Сессия недействительна. Переавторизуйте аккаунт."
        if isinstance(exc, ApiIdInvalidError):
            return "Неверные API ID / API Hash."
        if isinstance(exc, FloodWaitError):
            return f"FloodWait: подождите {exc.seconds} сек."
        if isinstance(exc, PhoneNumberFloodError):
            return "Слишком много попыток входа. Подождите и попробуйте снова."
    except ImportError:
        pass

    # ── requests / network ────────────────────────────────────────────────────
    try:
        import requests

        if isinstance(exc, requests.exceptions.Timeout):
            return "Превышено время ожидания ответа сервера."
        if isinstance(exc, requests.exceptions.ProxyError):
            return "Ошибка прокси. Проверьте настройки прокси."
        if isinstance(exc, requests.exceptions.SSLError):
            return "Ошибка SSL-соединения."
        if isinstance(exc, requests.exceptions.ConnectionError):
            return "Нет соединения с сервером. Проверьте интернет или прокси."
        if isinstance(exc, requests.exceptions.HTTPError):
            return f"HTTP-ошибка: {exc}"
        if isinstance(exc, requests.exceptions.RequestException):
            return f"Сетевая ошибка: {msg or type(exc).__name__}"
    except ImportError:
        pass

    # ── SQLite ──────────────────────────────────────────────────────────────────
    if isinstance(exc, sqlite3.IntegrityError):
        return "Нарушение целостности данных (дубликат или некорректные данные)."
    if isinstance(exc, sqlite3.OperationalError):
        if "locked" in msg.lower():
            return "База данных занята. Повторите операцию."
        return f"Ошибка базы данных: {msg or 'операция не выполнена'}"
    if isinstance(exc, sqlite3.Error):
        return f"Ошибка базы данных: {msg or type(exc).__name__}"

    # ── Built-in / OS ─────────────────────────────────────────────────────────
    if isinstance(exc, FileNotFoundError):
        return f"Файл не найден: {getattr(exc, 'filename', msg)}"
    if isinstance(exc, PermissionError):
        return f"Нет доступа к файлу: {msg}"
    if isinstance(exc, ValueError):
        return msg or "Некорректное значение."
    if isinstance(exc, KeyError):
        return f"Отсутствует обязательное поле: {exc}"
    if isinstance(exc, asyncio.TimeoutError):
        return "Превышено время ожидания операции."
    if isinstance(exc, ConnectionRefusedError):
        return "Соединение отклонено сервером."
    if isinstance(exc, ConnectionResetError):
        return "Соединение разорвано."
    if isinstance(exc, OSError):
        if "getaddrinfo failed" in msg.lower() or "11001" in msg or "11002" in msg:
            return "Не удалось разрешить адрес сервера. Проверьте интернет/DNS."
        return msg or "Сетевая ошибка."

    # ── App-specific string markers ───────────────────────────────────────────
    if msg == "2FA_REQUIRED":
        return "2FA_REQUIRED"

    lowered = msg.lower()
    if "too many tries" in lowered:
        return "Слишком много попыток. Подождите и попробуйте позже."
    if "username not occupied" in lowered or "nobody is using" in lowered:
        return "Пользователь или канал не найден."
    if "channel private" in lowered:
        return "Канал закрыт или недоступен."
    if "chat write forbidden" in lowered:
        return "Нет прав на отправку сообщений в этот чат."

    return msg or f"Неизвестная ошибка: {type(exc).__name__}"


# Late import to avoid circular dependency at module level for asyncio check
import asyncio  # noqa: E402
