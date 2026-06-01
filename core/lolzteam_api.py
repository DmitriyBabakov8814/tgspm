"""HTTP client for Lolzteam Market API (api.lzt.market)."""
import json
import re
import time
from typing import Any

import requests

from core.errors import NetworkError, ValidationError, humanize_error, log_exception
from core.lolz_api_registry import OPERATIONS_BY_ID

BASE_URL = "https://api.lzt.market"
MIN_REQUEST_INTERVAL = 0.55
MIN_SEARCH_INTERVAL = 3.1

_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")


class LolzMarketError(NetworkError):
    """Lolz.market API error with a user-friendly message."""


class LolzMarketClient:
    """
    Market API client. Token: OAuth with scope ``market``.
    Docs: https://lzt-market.readme.io/
    """

    def __init__(self, token: str, proxy: str | None = None):
        token = (token or "").strip()
        if not token:
            raise ValidationError("Укажите API-токен Lolz.market")
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        if proxy:
            self._apply_proxy(proxy)
        self._last_request = 0.0
        self._last_search = 0.0

    def _apply_proxy(self, proxy_str: str):
        proxy_str = proxy_str.strip()
        if "://" not in proxy_str:
            parts = proxy_str.split(":")
            if len(parts) >= 2:
                proxy_str = f"socks5://{parts[0]}:{parts[1]}"
        self.session.proxies = {"http": proxy_str, "https": proxy_str}

    def _throttle(self, search: bool = False):
        now = time.monotonic()
        delay = MIN_SEARCH_INTERVAL if search else MIN_REQUEST_INTERVAL
        last = self._last_search if search else self._last_request
        wait = delay - (now - last)
        if wait > 0:
            time.sleep(wait)
        now = time.monotonic()
        if search:
            self._last_search = now
        self._last_request = now

    @staticmethod
    def _error_message(resp: requests.Response) -> str:
        try:
            data = resp.json()
        except ValueError:
            return resp.text[:300] if resp.text else ""
        if isinstance(data, dict):
            for key in ("errors", "error", "message"):
                val = data.get(key)
                if isinstance(val, list) and val:
                    return str(val[0])
                if isinstance(val, str) and val:
                    return val
        return ""

    def _build_path(self, template: str, path_values: dict[str, Any]) -> str:
        path = template
        for key in _PATH_PARAM_RE.findall(template):
            val = path_values.get(key)
            if val is None or str(val).strip() == "":
                raise ValidationError(f"Не указан параметр пути: {key}")
            path = path.replace("{" + key + "}", str(val).strip())
        return path if path.startswith("/") else f"/{path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        json_body: dict | None = None,
        search: bool = False,
        path_values: dict | None = None,
    ) -> Any:
        if path_values:
            path = self._build_path(path, path_values)
        elif "{" in path:
            path = self._build_path(path, {})
        if not path.startswith("/"):
            path = f"/{path}"
        self._throttle(search=search)
        try:
            resp = self.session.request(
                method.upper(),
                f"{BASE_URL}{path}",
                params=params or None,
                json=json_body,
                data=data,
                timeout=60,
            )
        except requests.exceptions.RequestException as exc:
            log_exception(exc, f"lolz {method} {path}")
            raise LolzMarketError(humanize_error(exc), cause=exc) from exc

        if resp.status_code == 429:
            raise LolzMarketError(
                "Превышен лимит запросов Lolz.market. Подождите и повторите."
            )
        if resp.status_code == 401:
            raise LolzMarketError("Неверный или просроченный API-токен Lolz.market")
        if resp.status_code >= 400:
            msg = self._error_message(resp)
            raise LolzMarketError(msg or f"HTTP {resp.status_code}")

        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "application/json" in ctype or resp.text[:1] in ("{", "["):
            if not resp.content:
                return {}
            try:
                return resp.json()
            except ValueError as exc:
                raise LolzMarketError("Некорректный JSON в ответе") from exc
        return {"_raw": resp.text, "_content_type": ctype}

    def execute_operation(
        self,
        operation_id: str,
        field_values: dict[str, str],
    ) -> Any:
        """Run a registered API operation from lolz_api_registry."""
        op = OPERATIONS_BY_ID.get(operation_id)
        if not op:
            raise ValidationError(f"Неизвестная операция: {operation_id}")

        path_values: dict[str, str] = {}
        query: dict[str, str] = {}
        body: dict[str, str] = {}

        for field in op.get("fields", []):
            name = field["name"]
            raw = field_values.get(name, "")
            if raw is None:
                continue
            val = str(raw).strip()
            if not val:
                if field.get("required"):
                    raise ValidationError(f"Заполните поле: {field.get('label', name)}")
                continue
            where = field.get("in", "query")
            if where == "path":
                path_values[name] = val
            elif where == "body":
                body[name] = val
            else:
                query[name] = val

        path = self._build_path(op["path"], path_values)
        method = op["method"]
        search = bool(op.get("search"))

        # batch / bulk: parse JSON body fields
        json_body = None
        data = None
        if body:
            if operation_id == "batch" and "requests" in body:
                try:
                    json_body = {"requests": json.loads(body["requests"])}
                except json.JSONDecodeError as exc:
                    raise ValidationError("requests: невалидный JSON") from exc
            elif operation_id == "bulk_get" and "item_ids" in body:
                ids = [x.strip() for x in body["item_ids"].replace(" ", "").split(",") if x.strip()]
                json_body = {"item_ids": ids}
            else:
                data = body

        self._throttle(search=search)
        try:
            resp = self.session.request(
                method.upper(),
                f"{BASE_URL}{path}",
                params=query or None,
                json=json_body,
                data=data,
                timeout=90,
            )
        except requests.exceptions.RequestException as exc:
            log_exception(exc, f"lolz {method} {path}")
            raise LolzMarketError(humanize_error(exc), cause=exc) from exc

        if resp.status_code == 429:
            raise LolzMarketError("Превышен лимит запросов Lolz.market")
        if resp.status_code == 401:
            raise LolzMarketError("Неверный API-токен")
        if resp.status_code >= 400:
            raise LolzMarketError(self._error_message(resp) or f"HTTP {resp.status_code}")

        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {"_raw": resp.text}

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def get_profile(self) -> dict:
        return self.execute_operation("profile_get", {})

    def get_balances(self) -> dict:
        return self.execute_operation("balance_list", {})

    def search_category(self, category: str, **params) -> dict:
        vals = {"category": category}
        for k, v in params.items():
            if v is not None and v != "":
                vals[k] = str(v)
        return self.execute_operation("category_search", vals)

    def search_telegram(self, **params) -> dict:
        return self.search_category("telegram", **params)

    def get_item(self, item_id: int | str) -> dict:
        return self.execute_operation("item_get", {"item_id": str(item_id)})

    def get_orders(self, **params) -> dict:
        vals = {k: str(v) for k, v in params.items() if v not in (None, "")}
        return self.execute_operation("user_orders", vals)

    def fast_buy(self, item_id: int | str, price: int | float) -> dict:
        return self.execute_operation("buy_fast", {
            "item_id": str(item_id),
            "price": str(int(price)),
        })

    @staticmethod
    def extract_telegram_session(item: dict) -> str | None:
        if not item:
            return None
        login = item.get("loginData") or {}
        if isinstance(login, dict):
            raw = login.get("raw") or login.get("session") or login.get("auth_key")
            if raw and isinstance(raw, str) and len(raw) > 20:
                return raw.strip()
        for key in ("telegram_session", "session_string", "auth_key"):
            val = item.get(key)
            if val and isinstance(val, str) and len(val) > 20:
                return val.strip()
        sessions = item.get("sessionLoginData")
        if isinstance(sessions, list) and sessions:
            first = sessions[0]
            if isinstance(first, str) and len(first) > 20:
                return first.strip()
            if isinstance(first, dict):
                raw = first.get("raw") or first.get("session")
                if raw:
                    return str(raw).strip()
        return None

    @staticmethod
    def format_profile_summary(data: dict) -> str:
        user = data.get("user") or {}
        name = user.get("username") or user.get("user_id") or "?"
        balance = user.get("balance") or user.get("balance_rub") or "—"
        return f"@{name}  |  баланс: {balance} ₽  |  id: {user.get('user_id', '?')}"

    @staticmethod
    def format_json(data: Any) -> str:
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except TypeError:
            return str(data)
