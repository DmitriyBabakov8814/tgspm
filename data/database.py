import sqlite3
import json
from functools import wraps
from pathlib import Path

from core.errors import DatabaseError, ValidationError, log_exception

DB_PATH = Path(__file__).parent / "tg_sender.db"


def db_operation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (DatabaseError, ValidationError):
            raise
        except sqlite3.Error as exc:
            log_exception(exc, f"db.{func.__name__}")
            raise DatabaseError(f"Ошибка базы данных при «{func.__name__}»", cause=exc) from exc
        except Exception as exc:
            log_exception(exc, f"db.{func.__name__}")
            raise DatabaseError(f"Не удалось выполнить «{func.__name__}»", cause=exc) from exc

    return wrapper


def get_conn():
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except sqlite3.Error as exc:
        log_exception(exc, "get_conn")
        raise DatabaseError("Не удалось подключиться к базе данных", cause=exc) from exc


@db_operation
def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            api_id TEXT NOT NULL,
            api_hash TEXT NOT NULL,
            session_path TEXT,
            session_string TEXT,
            proxy TEXT DEFAULT '',
            country TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            is_banned INTEGER DEFAULT 0,
            daily_sent INTEGER DEFAULT 0,
            total_sent INTEGER DEFAULT 0,
            last_used TEXT,
            last_reset TEXT DEFAULT (date('now')),
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            user_id TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            source TEXT,
            tags TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            username TEXT,
            title TEXT,
            chat_type TEXT DEFAULT 'group',
            members_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            campaign_type TEXT NOT NULL,
            message_text TEXT,
            media_path TEXT,
            status TEXT DEFAULT 'draft',
            total_targets INTEGER DEFAULT 0,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            delay_min INTEGER DEFAULT 5,
            delay_max INTEGER DEFAULT 15,
            rotate_accounts INTEGER DEFAULT 1,
            msgs_per_account INTEGER DEFAULT 30,
            created_at TEXT DEFAULT (datetime('now')),
            started_at TEXT,
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS campaign_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            account_phone TEXT,
            target TEXT,
            status TEXT,
            error_text TEXT,
            sent_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        );

        CREATE TABLE IF NOT EXISTS parsed_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            user_id TEXT,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            comment_text TEXT,
            post_id TEXT,
            status TEXT DEFAULT 'parsed',
            dm_status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
        """)
        _migrate_accounts(conn)


def _migrate_accounts(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    if "is_muted" not in cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN is_muted INTEGER DEFAULT 0")
    if "lolz_item_id" not in cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN lolz_item_id TEXT DEFAULT ''")


# ── Accounts ──────────────────────────────────────────────────────────────────

def account_has_session(acc: dict) -> bool:
    """True if account has a Telethon session on disk or as string."""
    ss = (acc.get("session_string") or "").strip()
    if len(ss) > 20:
        return True
    sp = (acc.get("session_path") or "").strip()
    if not sp:
        return False
    p = Path(sp)
    if p.suffix == ".session":
        return p.is_file()
    return p.with_suffix(".session").is_file()


def account_is_mailable(acc: dict) -> bool:
    if acc.get("is_banned") or acc.get("is_muted"):
        return False
    if acc.get("status") not in ("active", "cooldown"):
        return False
    return account_has_session(acc)


@db_operation
def get_accounts(active_only=False):
    with get_conn() as conn:
        q = "SELECT * FROM accounts"
        if active_only:
            q += (
                " WHERE is_banned=0 AND COALESCE(is_muted,0)=0"
                " AND status IN ('active', 'cooldown')"
            )
        q += " ORDER BY id ASC"
        rows = [dict(r) for r in conn.execute(q).fetchall()]
    if active_only:
        return [a for a in rows if account_is_mailable(a)]
    return rows

@db_operation
def add_account(api_id, api_hash, phone=None, session_path=None, session_string=None,
                proxy=None, country=None, notes=None, status=None):
    if status is None:
        status = "pending"
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO accounts
               (phone, api_id, api_hash, session_path, session_string, proxy, country, notes, status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (phone, str(api_id), api_hash, session_path, session_string,
             proxy or '', country or '', notes or '', status)
        )
        return cur.lastrowid

@db_operation
def update_account(acc_id, **kwargs):
    if not kwargs:
        return
    parts = [f"{k}=?" for k in kwargs]
    vals = list(kwargs.values()) + [acc_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE accounts SET {', '.join(parts)} WHERE id=?", vals)

@db_operation
def delete_account(acc_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM accounts WHERE id=?", (acc_id,))

@db_operation
def increment_account_sent(acc_id, count=1):
    with get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET daily_sent=daily_sent+?, total_sent=total_sent+?, last_used=datetime('now') WHERE id=?",
            (count, count, acc_id)
        )

@db_operation
def reset_daily_counts():
    with get_conn() as conn:
        conn.execute("UPDATE accounts SET daily_sent=0, last_reset=date('now') WHERE last_reset < date('now')")

@db_operation
def ban_account(acc_id):
    with get_conn() as conn:
        conn.execute("UPDATE accounts SET is_banned=1, status='banned' WHERE id=?", (acc_id,))


@db_operation
def mute_account(acc_id):
    with get_conn() as conn:
        conn.execute("UPDATE accounts SET is_muted=1, status='muted' WHERE id=?", (acc_id,))


@db_operation
def account_exists_by_lolz(item_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM accounts WHERE lolz_item_id=? LIMIT 1", (str(item_id),)
        ).fetchone()
        return row is not None


# ── Contacts ──────────────────────────────────────────────────────────────────

@db_operation
def get_contacts(search=""):
    with get_conn() as conn:
        if search:
            q = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM contacts WHERE username LIKE ? OR first_name LIKE ? OR phone LIKE ? ORDER BY id DESC",
                (q, q, q)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM contacts ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

@db_operation
def add_contact(username=None, user_id=None, first_name=None, last_name=None, phone=None, source=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO contacts (username, user_id, first_name, last_name, phone, source) VALUES (?,?,?,?,?,?)",
            (username, user_id, first_name, last_name, phone, source)
        )

@db_operation
def delete_contact(contact_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM contacts WHERE id=?", (contact_id,))

@db_operation
def delete_all_contacts():
    with get_conn() as conn:
        conn.execute("DELETE FROM contacts")


# ── Chats ─────────────────────────────────────────────────────────────────────

@db_operation
def get_chats(active_only=False):
    with get_conn() as conn:
        q = "SELECT * FROM chats"
        if active_only:
            q += " WHERE is_active=1"
        q += " ORDER BY id DESC"
        return [dict(r) for r in conn.execute(q).fetchall()]

@db_operation
def add_chat(chat_id=None, username=None, title=None, chat_type="group", members_count=0):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chats (chat_id, username, title, chat_type, members_count) VALUES (?,?,?,?,?)",
            (chat_id, username, title, chat_type, members_count)
        )

@db_operation
def toggle_chat(chat_id):
    with get_conn() as conn:
        conn.execute("UPDATE chats SET is_active = 1 - is_active WHERE id=?", (chat_id,))

@db_operation
def delete_chat(chat_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM chats WHERE id=?", (chat_id,))


# ── Campaigns ─────────────────────────────────────────────────────────────────

@db_operation
def create_campaign(name, campaign_type, message_text, delay_min=5, delay_max=15,
                    media_path=None, rotate_accounts=1, msgs_per_account=30):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO campaigns
               (name, campaign_type, message_text, delay_min, delay_max,
                media_path, rotate_accounts, msgs_per_account)
               VALUES (?,?,?,?,?,?,?,?)""",
            (name, campaign_type, message_text, delay_min, delay_max,
             media_path, rotate_accounts, msgs_per_account)
        )
        return cur.lastrowid

@db_operation
def get_campaigns():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()]

@db_operation
def update_campaign_status(campaign_id, status, sent=None, failed=None, total=None):
    with get_conn() as conn:
        parts = ["status=?"]
        vals = [status]
        if sent is not None:
            parts.append("sent_count=?"); vals.append(sent)
        if failed is not None:
            parts.append("failed_count=?"); vals.append(failed)
        if total is not None:
            parts.append("total_targets=?"); vals.append(total)
        if status == "running":
            parts.append("started_at=datetime('now')")
        if status in ("finished", "stopped"):
            parts.append("finished_at=datetime('now')")
        vals.append(campaign_id)
        conn.execute(f"UPDATE campaigns SET {', '.join(parts)} WHERE id=?", vals)

@db_operation
def log_send(campaign_id, target, status, error_text=None, account_phone=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO campaign_logs (campaign_id, account_phone, target, status, error_text) VALUES (?,?,?,?,?)",
            (campaign_id, account_phone, target, status, error_text)
        )

@db_operation
def get_campaign_logs(campaign_id):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM campaign_logs WHERE campaign_id=? ORDER BY id DESC LIMIT 500",
            (campaign_id,)
        ).fetchall()]


# ── Parsed users ──────────────────────────────────────────────────────────────

@db_operation
def save_parsed_users(channel, users):
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO parsed_users
               (channel, user_id, username, first_name, last_name, comment_text, post_id)
               VALUES (?,?,?,?,?,?,?)""",
            [(channel, u.get("user_id"), u.get("username"), u.get("first_name"),
              u.get("last_name"), u.get("comment_text"), u.get("post_id")) for u in users]
        )

@db_operation
def get_parsed_users(channel=None):
    with get_conn() as conn:
        if channel:
            rows = conn.execute("SELECT * FROM parsed_users WHERE channel=? ORDER BY id DESC", (channel,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM parsed_users ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

@db_operation
def update_parsed_user_status(user_id_db, status=None, dm_status=None):
    with get_conn() as conn:
        if status:
            conn.execute("UPDATE parsed_users SET status=? WHERE id=?", (status, user_id_db))
        if dm_status:
            conn.execute("UPDATE parsed_users SET dm_status=? WHERE id=?", (dm_status, user_id_db))


@db_operation
def delete_all_parsed_users():
    with get_conn() as conn:
        conn.execute("DELETE FROM parsed_users")


# ── Settings ──────────────────────────────────────────────────────────────────

@db_operation
def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


@db_operation
def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value or ""),
        )
