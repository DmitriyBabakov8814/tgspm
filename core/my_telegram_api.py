"""Automate login to my.telegram.org and fetch (or create) API credentials."""
import random
import re
import string

import requests

from core.errors import NetworkError, AuthError, ValidationError, humanize_error, log_exception

BASE_URL = "https://my.telegram.org"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class MyTelegramOrgError(AuthError):
    """Backward-compatible alias for my.telegram.org failures."""


class MyTelegramOrgClient:
    """HTTP client for my.telegram.org auth and /apps API credentials."""

    def __init__(self, proxy: str | None = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/auth",
        })
        if proxy:
            self._apply_proxy(proxy.strip())

    def _apply_proxy(self, proxy_str: str):
        try:
            proxy_str = proxy_str.strip()
            if "://" not in proxy_str:
                parts = proxy_str.split(":")
                if len(parts) >= 2:
                    proxy_str = f"socks5://{parts[0]}:{parts[1]}"
            self.session.proxies = {"http": proxy_str, "https": proxy_str}
        except Exception as exc:
            log_exception(exc, "MyTelegramOrgClient._apply_proxy")
            raise ValidationError("Некорректный формат прокси") from exc

    def _post(self, path: str, data: dict) -> requests.Response:
        try:
            return self.session.post(f"{BASE_URL}{path}", data=data, timeout=30)
        except requests.exceptions.RequestException as exc:
            log_exception(exc, f"my.telegram.org POST {path}")
            raise NetworkError(humanize_error(exc), cause=exc) from exc

    def _get(self, path: str) -> requests.Response:
        try:
            return self.session.get(f"{BASE_URL}{path}", timeout=30)
        except requests.exceptions.RequestException as exc:
            log_exception(exc, f"my.telegram.org GET {path}")
            raise NetworkError(humanize_error(exc), cause=exc) from exc

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        phone = phone.strip()
        if not phone:
            raise ValidationError("Введите номер телефона")
        if not phone.startswith("+"):
            phone = f"+{phone.lstrip('+')}"
        if len(re.sub(r"\D", "", phone)) < 10:
            raise ValidationError("Некорректный номер телефона")
        return phone

    def send_password(self, phone: str) -> str:
        phone = self._normalize_phone(phone)
        resp = self._post("/auth/send_password", {"phone": phone})
        self._check_rate_limit(resp.text)

        if resp.status_code != 200:
            raise MyTelegramOrgError(f"Не удалось отправить код (HTTP {resp.status_code})")

        try:
            data = resp.json()
        except ValueError as exc:
            raise MyTelegramOrgError("Неверный ответ my.telegram.org") from exc

        random_hash = data.get("random_hash")
        if not random_hash:
            raise MyTelegramOrgError(data.get("error") or "Не получен random_hash")
        return random_hash

    def login(self, phone: str, random_hash: str, code: str):
        phone = self._normalize_phone(phone)
        if not code.strip():
            raise ValidationError("Введите код из Telegram")

        resp = self._post("/auth/login", {
            "phone": phone,
            "random_hash": random_hash,
            "password": code.strip(),
            "remember": "1",
        })
        self._check_rate_limit(resp.text)

        if resp.status_code != 200:
            raise MyTelegramOrgError(f"Ошибка входа (HTTP {resp.status_code})")

        if resp.text.strip() != "true":
            raise MyTelegramOrgError("Неверный код подтверждения")

    def get_or_create_app(self, phone: str) -> tuple[str, str]:
        resp = self._get("/apps")
        if resp.status_code != 200:
            raise MyTelegramOrgError(f"Не удалось открыть /apps (HTTP {resp.status_code})")

        html = resp.text
        creds = self._parse_credentials(html)
        if creds:
            return creds

        page_hash = self._parse_form_hash(html)
        if not page_hash:
            raise MyTelegramOrgError("Не найден hash формы на my.telegram.org/apps")

        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        digits = re.sub(r"\D", "", phone)[-6:] or suffix[:6]

        create_resp = self._post("/apps/create", {
            "hash": page_hash,
            "app_title": "TG Sender Pro",
            "app_shortname": f"tgs{digits}{suffix[:4]}",
            "app_url": "",
            "app_platform": "desktop",
            "app_desc": "Telegram automation tool",
        })

        if create_resp.status_code != 200:
            raise MyTelegramOrgError(f"Не удалось создать приложение (HTTP {create_resp.status_code})")

        if "error" in create_resp.text.lower() and "api_id" not in create_resp.text.lower():
            err = self._extract_error(create_resp.text)
            if err:
                raise MyTelegramOrgError(err)

        apps_resp = self._get("/apps")
        creds = self._parse_credentials(apps_resp.text)
        if creds:
            return creds

        raise MyTelegramOrgError("Приложение создано, но API ID/Hash не найдены на странице")

    def login_and_get_credentials(
        self, phone: str, random_hash: str, code: str
    ) -> tuple[str, str]:
        self.login(phone, random_hash, code)
        return self.get_or_create_app(phone)

    @staticmethod
    def _check_rate_limit(text: str):
        if "too many tries" in text.lower():
            raise MyTelegramOrgError("Слишком много попыток. Попробуйте позже.")

    @staticmethod
    def _parse_credentials(html: str) -> tuple[str, str] | None:
        patterns_id = [
            r'for="app_id"[^>]*>[\s\S]*?<strong>\s*(\d+)\s*</strong>',
            r'App api_id:[\s\S]*?<strong>\s*(\d+)\s*</strong>',
            r'"api_id"\s*:\s*"?(\d+)"?',
        ]
        patterns_hash = [
            r'for="app_hash"[^>]*>[\s\S]*?<span[^>]*>\s*([a-f0-9]{32})\s*</span>',
            r'App api_hash:[\s\S]*?<span[^>]*>\s*([a-f0-9]{32})\s*</span>',
            r'"api_hash"\s*:\s*"([a-f0-9]{32})"',
        ]

        api_id = api_hash = None
        for pat in patterns_id:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                api_id = m.group(1)
                break
        for pat in patterns_hash:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                api_hash = m.group(1)
                break

        if api_id and api_hash:
            return api_id, api_hash
        return None

    @staticmethod
    def _parse_form_hash(html: str) -> str | None:
        m = re.search(r'name="hash"\s+value="([^"]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'"hash"\s*:\s*"([^"]+)"', html)
        return m.group(1) if m else None

    @staticmethod
    def _extract_error(text: str) -> str | None:
        m = re.search(r'class="[^"]*alert[^"]*"[^>]*>([^<]+)', text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        if len(text) < 200 and text.strip():
            return text.strip()
        return None
