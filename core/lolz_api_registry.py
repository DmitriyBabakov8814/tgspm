"""
Реестр операций Lolzteam Market API для UI-эксплорера.
Документация: https://lzt-market.readme.io/
"""

MARKET_CATEGORIES = [
    ("steam", "Steam"),
    ("telegram", "Telegram"),
    ("discord", "Discord"),
    ("fortnite", "Fortnite"),
    ("vkontakte", "VKontakte"),
    ("instagram", "Instagram"),
    ("tiktok", "TikTok"),
    ("epicgames", "Epic Games"),
    ("valorant", "Valorant"),
    ("battlenet", "Battle.net"),
    ("uplay", "Uplay"),
    ("origin", "EA / Origin"),
    ("supercell", "Supercell"),
    ("genshin-impact", "Genshin Impact"),
    ("escape-from-tarkov", "Escape from Tarkov"),
    ("socialclub", "Social Club"),
    ("world-of-tanks", "World of Tanks"),
    ("wot-blitz", "WoT Blitz"),
    ("warface", "Warface"),
    ("war-thunder", "War Thunder"),
    ("vpn", "VPN"),
    ("youtube", "YouTube"),
    ("spotify", "Spotify"),
    ("roblox", "Roblox"),
    ("minecraft", "Minecraft"),
    ("mihoyo", "miHoYo"),
    ("riot", "Riot"),
    ("llm", "LLM"),
    ("gifts", "Gifts"),
    ("hytale", "Hytale"),
    ("cinema", "Online Cinema"),
]

# field: name, in (path|query|body), label, required=False, placeholder=""
def _f(name, where, label, required=False, ph=""):
    return {"name": name, "in": where, "label": label, "required": required, "placeholder": ph}


def _op(op_id, group, title, method, path, fields=None, search=False, desc=""):
    return {
        "id": op_id,
        "group": group,
        "title": title,
        "method": method,
        "path": path,
        "fields": fields or [],
        "search": search,
        "description": desc,
    }


_Q_SEARCH = [
    _f("pmin", "query", "Цена от (pmin)"),
    _f("pmax", "query", "Цена до (pmax)"),
    _f("title", "query", "В заголовке"),
    _f("page", "query", "Страница", ph="1"),
    _f("order_by", "query", "Сортировка", ph="price_to_up"),
]

OPERATIONS = [
    # ── Профиль ───────────────────────────────────────────────────────────────
    _op("profile_get", "profile", "Профиль /me", "GET", "/me"),
    _op("profile_edit", "profile", "Настройки профиля", "PUT", "/me", [
        _f("disable_steam_guard", "body", "disable_steam_guard (0/1)"),
        _f("user_allow_ask_discount", "body", "user_allow_ask_discount"),
        _f("max_discount_percent", "body", "max_discount_percent"),
        _f("hide_favourites", "body", "hide_favourites"),
    ]),
    _op("claims_get", "profile", "Претензии", "GET", "/claims"),

    # ── Баланс и платежи ────────────────────────────────────────────────────
    _op("balance_list", "payments", "Список балансов", "GET", "/balance"),
    _op("balance_exchange", "payments", "Обмен баланса", "POST", "/balance/exchange", [
        _f("from", "body", "from (валюта)", True),
        _f("to", "body", "to (валюта)", True),
        _f("amount", "body", "amount", True),
    ]),
    _op("payments_history", "payments", "История платежей", "GET", "/payments/history", [
        _f("type", "query", "type (income/cost/...)"),
        _f("pmin", "query", "pmin"),
        _f("pmax", "query", "pmax"),
        _f("startDate", "query", "startDate (RFC3339)"),
        _f("endDate", "query", "endDate"),
    ]),
    _op("payments_transfer", "payments", "Перевод пользователю", "POST", "/payments/transfer", [
        _f("user_id", "body", "user_id получателя"),
        _f("username", "body", "username получателя"),
        _f("amount", "body", "amount", True),
        _f("currency", "body", "currency", True, "rub"),
        _f("secret_answer", "body", "secret_answer", True),
        _f("comment", "body", "comment"),
    ]),
    _op("payments_currency", "payments", "Список валют", "GET", "/payments/currency"),
    _op("payments_fee", "payments", "Комиссия перевода", "GET", "/payments/fee", [
        _f("amount", "query", "amount", True),
        _f("currency", "query", "currency", True),
    ]),
    _op("payments_cancel", "payments", "Отмена холда перевода", "POST", "/payments/cancel", [
        _f("payment_id", "body", "payment_id", True),
    ]),
    _op("payout_services", "payments", "Сервисы вывода", "GET", "/payments/payout/services"),
    _op("payout_create", "payments", "Заявка на вывод", "POST", "/payments/payout", [
        _f("service_id", "body", "service_id", True),
        _f("amount", "body", "amount", True),
        _f("wallet", "body", "wallet", True),
    ]),

    # ── Инвойсы ───────────────────────────────────────────────────────────────
    _op("invoice_list", "invoices", "Список инвойсов", "GET", "/invoice/list"),
    _op("invoice_get", "invoices", "Инвойс по ID", "GET", "/invoice/{invoice_id}", [
        _f("invoice_id", "path", "invoice_id", True),
    ]),
    _op("invoice_create", "invoices", "Создать инвойс", "POST", "/invoice", [
        _f("amount", "body", "amount", True),
        _f("currency", "body", "currency", True),
        _f("comment", "body", "comment"),
    ]),

    # ── Прокси ────────────────────────────────────────────────────────────────
    _op("proxy_list", "proxy", "Список прокси", "GET", "/proxy"),
    _op("proxy_add", "proxy", "Добавить прокси", "POST", "/proxy", [
        _f("proxy_ip", "body", "proxy_ip"),
        _f("proxy_port", "body", "proxy_port"),
        _f("proxy_user", "body", "proxy_user"),
        _f("proxy_pass", "body", "proxy_pass"),
        _f("proxy_row", "body", "proxy_row (список ip:port:user:pass)"),
    ]),
    _op("proxy_delete", "proxy", "Удалить прокси", "DELETE", "/proxy", [
        _f("proxy_id", "query", "proxy_id"),
        _f("delete_all", "query", "delete_all (1)"),
    ]),

    # ── Каталог / поиск ───────────────────────────────────────────────────────
    _op("list_latest", "search", "Последние аккаунты", "GET", "/", _Q_SEARCH, search=True),
    _op("category_list", "search", "Список категорий", "GET", "/category"),
    _op("category_search", "search", "Поиск в категории", "GET", "/{category}", [
        _f("category", "path", "Категория", True, "telegram"),
        *_Q_SEARCH,
    ], search=True),
    _op("category_params", "search", "Параметры категории", "GET", "/{category}/params", [
        _f("category", "path", "Категория", True, "telegram"),
    ]),
    _op("category_games", "search", "Игры категории", "GET", "/{category}/games", [
        _f("category", "path", "Категория", True, "steam"),
    ]),

    # ── Списки ────────────────────────────────────────────────────────────────
    _op("user_items", "lists", "Мои товары", "GET", "/user/items", [
        _f("category_id", "query", "category_id"),
        *_Q_SEARCH,
    ]),
    _op("user_orders", "lists", "Мои покупки", "GET", "/user/orders", [
        _f("category_id", "query", "category_id"),
        *_Q_SEARCH,
    ]),
    _op("user_states", "lists", "Статусы товаров", "GET", "/user/item-states"),
    _op("favorites", "lists", "Избранное", "GET", "/fave"),
    _op("viewed", "lists", "Просмотренные", "GET", "/viewed"),
    _op("download_list", "lists", "Скачать данные", "GET", "/user/{dtype}/download", [
        _f("dtype", "path", "Тип (orders/items)", True, "orders"),
        _f("format", "query", "format"),
    ]),

    # ── Корзина ───────────────────────────────────────────────────────────────
    _op("cart_get", "cart", "Корзина", "GET", "/cart"),
    _op("cart_add", "cart", "В корзину", "POST", "/cart", [
        _f("item_id", "body", "item_id", True),
    ]),
    _op("cart_delete", "cart", "Из корзины", "DELETE", "/cart", [
        _f("item_id", "query", "item_id", True),
    ]),

    # ── Товар: просмотр ───────────────────────────────────────────────────────
    _op("item_get", "item", "Информация о товаре", "GET", "/{item_id}", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_image", "item", "Изображение товара", "GET", "/{item_id}/image", [
        _f("item_id", "path", "item_id", True),
    ]),

    # ── Покупка ───────────────────────────────────────────────────────────────
    _op("buy_fast", "purchase", "Быстрая покупка", "POST", "/{item_id}/fast-buy", [
        _f("item_id", "path", "item_id", True),
        _f("price", "body", "price", True),
        _f("buy_without_validation", "body", "buy_without_validation (1)"),
    ]),
    _op("buy_reserve", "purchase", "Резерв", "POST", "/{item_id}/reserve", [
        _f("item_id", "path", "item_id", True),
        _f("price", "body", "price", True),
    ]),
    _op("buy_cancel_reserve", "purchase", "Отмена резерва", "POST", "/{item_id}/cancel-reserve", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("buy_check", "purchase", "Проверка аккаунта", "POST", "/{item_id}/check-account", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("buy_confirm", "purchase", "Подтвердить покупку", "POST", "/{item_id}/confirm-buy", [
        _f("item_id", "path", "item_id", True),
        _f("buy_without_validation", "body", "buy_without_validation (1)"),
    ]),
    _op("discount_request", "purchase", "Запрос скидки", "POST", "/{item_id}/discount-request", [
        _f("item_id", "path", "item_id", True),
        _f("price", "body", "price", True),
    ]),
    _op("discount_cancel", "purchase", "Отмена скидки", "POST", "/{item_id}/discount-cancel", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("discount_review", "purchase", "Ответ на скидку", "POST", "/{item_id}/discount-review", [
        _f("item_id", "path", "item_id", True),
        _f("action", "body", "action (approve/decline)", True),
    ]),

    # ── Управление товаром ────────────────────────────────────────────────────
    _op("item_edit", "manage", "Редактировать", "PUT", "/{item_id}/edit", [
        _f("item_id", "path", "item_id", True),
        _f("key", "body", "key (price/title/...)"),
        _f("value", "body", "value"),
        _f("currency", "body", "currency (при смене price)"),
    ]),
    _op("item_delete", "manage", "Удалить с витрины", "DELETE", "/{item_id}", [
        _f("item_id", "path", "item_id", True),
        _f("reason", "body", "reason", True),
    ]),
    _op("item_bump", "manage", "Поднять (bump)", "POST", "/{item_id}/bump", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_stick", "manage", "Закрепить", "POST", "/{item_id}/stick", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_unstick", "manage", "Открепить", "DELETE", "/{item_id}/stick", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_favorite", "manage", "В избранное", "POST", "/{item_id}/star", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_unfavorite", "manage", "Из избранного", "DELETE", "/{item_id}/star", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_tag_add", "manage", "Добавить тег", "POST", "/{item_id}/tag", [
        _f("item_id", "path", "item_id", True),
        _f("tag_id", "body", "tag_id", True),
    ]),
    _op("item_tag_del", "manage", "Удалить тег", "DELETE", "/{item_id}/tag", [
        _f("item_id", "path", "item_id", True),
        _f("tag_id", "body", "tag_id", True),
    ]),
    _op("item_open", "manage", "Открыть продажу", "POST", "/{item_id}/open", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_close", "manage", "Закрыть продажу", "POST", "/{item_id}/close", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_change_owner", "manage", "Передать владельца", "POST", "/{item_id}/change-owner", [
        _f("item_id", "path", "item_id", True),
        _f("username", "body", "username", True),
        _f("secret_answer", "body", "secret_answer", True),
    ]),
    _op("item_refuse_guarantee", "manage", "Отказ от гарантии", "POST", "/{item_id}/refuse-guarantee", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_change_password", "manage", "Сменить пароль", "POST", "/{item_id}/change-password", [
        _f("item_id", "path", "item_id", True),
        _f("_cancel", "body", "_cancel (1 — не менять)"),
    ]),
    _op("item_note", "manage", "Заметка", "POST", "/{item_id}/note", [
        _f("item_id", "path", "item_id", True),
        _f("note", "body", "note"),
    ]),
    _op("item_autobump", "manage", "Автобамп", "POST", "/{item_id}/auto-bump", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_autobump_off", "manage", "Выключить автобамп", "POST", "/{item_id}/auto-bump/disable", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_ai_price", "manage", "AI-цена", "GET", "/{item_id}/ai-price", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_claim", "manage", "Создать претензию", "POST", "/{item_id}/claim", [
        _f("item_id", "path", "item_id", True),
    ]),

    # ── Данные аккаунта ───────────────────────────────────────────────────────
    _op("item_email_code", "account_data", "Код с email", "GET", "/{item_id}/email-code", [
        _f("item_id", "path", "item_id", True),
        _f("email", "query", "email", True),
    ]),
    _op("item_temp_email_pass", "account_data", "Пароль temp email", "GET", "/{item_id}/temp-email-password", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("item_letters", "account_data", "Письма email", "GET", "/{item_id}/letters", [
        _f("item_id", "path", "item_id", True),
    ]),

    # ── Steam ─────────────────────────────────────────────────────────────────
    _op("steam_preview", "steam", "HTML превью Steam", "GET", "/{item_id}/steam-preview", [
        _f("item_id", "path", "item_id", True),
        _f("type", "query", "type (profile/games)"),
    ]),
    _op("steam_mafile_get", "steam", "Получить maFile", "GET", "/{item_id}/mafile", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("steam_mafile_add", "steam", "Добавить maFile", "POST", "/{item_id}/mafile", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("steam_mafile_del", "steam", "Удалить maFile", "DELETE", "/{item_id}/mafile", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("steam_guard_code", "steam", "Код Steam Guard", "GET", "/{item_id}/guard-code", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("steam_sda", "steam", "Подтвердить SDA", "POST", "/{item_id}/sda", [
        _f("item_id", "path", "item_id", True),
        _f("id", "body", "id"),
        _f("nonce", "body", "nonce"),
    ]),
    _op("steam_inventory", "steam", "Стоимость инвентаря", "GET", "/{item_id}/inventory-value", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("steam_inv_update", "steam", "Обновить инвентарь", "POST", "/{item_id}/inventory-value", [
        _f("item_id", "path", "item_id", True),
    ]),

    # ── Telegram ──────────────────────────────────────────────────────────────
    _op("tg_code", "telegram", "Код Telegram", "GET", "/{item_id}/telegram-code", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("tg_reset_auth", "telegram", "Сброс сессий TG", "POST", "/{item_id}/telegram-reset-auth", [
        _f("item_id", "path", "item_id", True),
    ]),

    # ── Публикация ────────────────────────────────────────────────────────────
    _op("publish_add", "publish", "Добавить товар", "POST", "/item/add", [
        _f("title", "body", "title", True),
        _f("price", "body", "price", True),
        _f("category_id", "body", "category_id", True, "24"),
        _f("currency", "body", "currency", True, "rub"),
        _f("item_origin", "body", "item_origin", True),
        _f("extended_guarantee", "body", "extended_guarantee", True, "0"),
        _f("description", "body", "description"),
    ]),
    _op("publish_fast", "publish", "Быстрая продажа", "POST", "/item/fast-sell", [
        _f("title", "body", "title", True),
        _f("price", "body", "price", True),
        _f("category_id", "body", "category_id", True),
        _f("currency", "body", "currency", True, "rub"),
        _f("item_origin", "body", "item_origin", True),
    ]),
    _op("publish_goods_add", "publish", "Данные неопубликованного", "GET", "/{item_id}/goods/add", [
        _f("item_id", "path", "item_id", True),
    ]),
    _op("publish_goods_check", "publish", "Проверить и опубликовать", "POST", "/{item_id}/goods/check", [
        _f("item_id", "path", "item_id", True),
        _f("login", "body", "login"),
        _f("password", "body", "password"),
        _f("login_password", "body", "login_password"),
    ]),

    # ── Массовые операции ─────────────────────────────────────────────────────
    _op("bulk_get", "bulk", "Массово получить", "POST", "/bulk/items", [
        _f("item_ids", "body", "item_ids (через запятую)"),
    ]),
    _op("bulk_action", "bulk", "Массовое действие", "POST", "/items/bulk-action", [
        _f("action", "body", "action", True),
        _f("item_ids", "body", "item_ids"),
    ]),
    _op("batch", "bulk", "Batch (до 10 запросов)", "POST", "/batch", [
        _f("requests", "body", "requests (JSON массив)", True),
    ]),

    # ── Скидки продавца ───────────────────────────────────────────────────────
    _op("discounts_list", "discounts", "Кастомные скидки", "GET", "/custom-discounts"),
    _op("discounts_create", "discounts", "Создать скидку", "POST", "/custom-discounts", [
        _f("name", "body", "name", True),
        _f("percent", "body", "percent", True),
    ]),
    _op("discounts_edit", "discounts", "Изменить скидку", "PUT", "/custom-discounts/{discount_id}", [
        _f("discount_id", "path", "discount_id", True),
    ]),
    _op("discounts_delete", "discounts", "Удалить скидку", "DELETE", "/custom-discounts/{discount_id}", [
        _f("discount_id", "path", "discount_id", True),
    ]),
]

OPERATIONS_BY_ID = {o["id"]: o for o in OPERATIONS}

GROUPS_RU = {
    "profile": "Профиль",
    "payments": "Платежи и баланс",
    "invoices": "Инвойсы",
    "proxy": "Прокси маркета",
    "search": "Поиск и каталог",
    "lists": "Списки",
    "cart": "Корзина",
    "item": "Товар",
    "purchase": "Покупка",
    "manage": "Управление товаром",
    "account_data": "Данные аккаунта",
    "steam": "Steam",
    "telegram": "Telegram",
    "publish": "Публикация",
    "bulk": "Массовые операции",
    "discounts": "Скидки",
}
