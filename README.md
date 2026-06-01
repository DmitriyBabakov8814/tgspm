# TG Sender Pro v2.0 — Multi-Account Edition

Мощный инструмент Telegram-маркетинга с поддержкой 100+ аккаунтов.

## Установка

```bash
pip install -r requirements.txt
python main.py
```

## Форматы импорта аккаунтов

### 1. .session файлы (Telethon)
- Одиночный: выберите .session файл + введите API ID/Hash
- Массовый: папка с .session файлами + опциональный accounts.txt:
  ```
  api_id|api_hash|телефон|socks5://proxy
  ```

### 2. Session String
- Вставьте строку Telethon session string (одну или несколько)
- Можно получить из: Fragment, SMS-Activate, других сервисов

### 3. Ручной вход
- Телефон + API ID + API Hash → отправить SMS → ввести код

## Антибан система
- Случайные задержки между сообщениями
- Ротация аккаунтов каждые N сообщений
- Автоматический cooldown при FloodWait
- Длительный cooldown при PeerFlood (5 мин)
- Автоматическое определение и пометка забаненных аккаунтов
- Ежедневный счётчик сброса

## Рекомендуемые настройки
| Режим | Задержка мин | Задержка макс | Сообщ/акк |
|-------|-------------|---------------|-----------|
| Безопасный | 15 | 45 | 20 |
| Умеренный | 8 | 20 | 30 |
| Агрессивный | 4 | 10 | 50 |

## Lolzteam Market API
В боковом меню: **🛒 Lolz.market** — полный эксплорер API (80+ методов): профиль, поиск, покупка, управление товарами, Steam/Telegram, платежи, корзина, публикация и др.

Токен: [lolz.live → API](https://lolz.live/account/api) со scope `market`. Вкладка **✈ TG импорт** — загрузка купленных Telegram-аккаунтов в пул.

## Прокси
Поддерживаемые форматы:
- `socks5://user:pass@host:port`
- `socks4://host:port`
- `http://host:port`
- `host:port:user:pass`
