import customtkinter as ctk

from core.async_runner import run_async, run_sync_in_thread
from core.errors import humanize_error, log_exception, setup_logging
from data import database as db
from ui.error_ui import show_error
from ui.accounts_frame import AccountsFrame
from ui.contacts_frame import ContactsFrame
from ui.chats_frame import ChatsFrame
from ui.broadcast_frame import BroadcastFrame
from ui.parser_frame import ParserFrame
from ui.history_frame import HistoryFrame
from ui.lolz_frame import LolzFrame
from ui.clipboard import bind_clipboard

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

NAV_ITEMS = [
    ("👤", "Аккаунты"),
    ("👥", "Контакты"),
    ("💬", "Чаты"),
    ("📤", "Рассылка"),
    ("🔍", "Парсер"),
    ("📋", "История"),
    ("🛒", "Lolz.market"),
]


class App(ctk.CTk):
    def __init__(self):
        setup_logging()
        try:
            super().__init__()
            db.init_db()
        except Exception as exc:
            log_exception(exc, "App.__init__")
            raise

        self.title("TG Sender Pro")
        self.geometry("1340x860")
        self.minsize(1100, 720)
        self.configure(fg_color="#0d0f14")
        self.report_callback_exception = self._tk_callback_error

        self._build_ui()
        bind_clipboard(self)
        self._select_nav(0)

    def _tk_callback_error(self, exc, val, tb):
        import traceback as _tb
        log_exception(val, "tk_callback")
        try:
            show_error(self, "Ошибка интерфейса", val)
        except Exception:
            print(_tb.format_exception(exc, val, tb))

    def report_error(self, title: str, exc: BaseException):
        show_error(self, title, exc)

    def _build_ui(self):
        # ── Sidebar ──────────────────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=230, fg_color="#0a0c12", corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo area
        logo = ctk.CTkFrame(self.sidebar, fg_color="#13151c", corner_radius=12)
        logo.pack(fill="x", padx=12, pady=(18, 4))

        logo_inner = ctk.CTkFrame(logo, fg_color="transparent")
        logo_inner.pack(padx=16, pady=14)

        ctk.CTkLabel(logo_inner, text="✈",
            font=ctk.CTkFont("Helvetica", 28), text_color="#4fc3f7"
        ).pack(side="left", padx=(0, 10))

        txt = ctk.CTkFrame(logo_inner, fg_color="transparent")
        txt.pack(side="left")
        ctk.CTkLabel(txt, text="TG Sender",
            font=ctk.CTkFont("Helvetica", 18, "bold"), text_color="#e2e8f0"
        ).pack(anchor="w")
        ctk.CTkLabel(txt, text="Pro Edition",
            font=ctk.CTkFont("Helvetica", 10), text_color="#2563eb"
        ).pack(anchor="w")

        # Divider
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#1a1d27").pack(fill="x", padx=16, pady=10)

        # Nav
        self.nav_buttons = []
        for i, (icon, label) in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {icon}  {label}",
                anchor="w",
                height=46,
                corner_radius=10,
                font=ctk.CTkFont("Helvetica", 13),
                fg_color="transparent",
                hover_color="#1a1d27",
                text_color="#64748b",
                command=lambda idx=i: self._select_nav(idx),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons.append(btn)

        # Bottom status
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#1a1d27").pack(fill="x", padx=16, pady=6, side="bottom")

        self.acc_count_lbl = ctk.CTkLabel(self.sidebar,
            text="⚪  Аккаунты: 0 активных",
            font=ctk.CTkFont("Helvetica", 11),
            text_color="#4a5568")
        self.acc_count_lbl.pack(padx=14, pady=(0, 12), side="bottom", anchor="w")

        # Version
        ctk.CTkLabel(self.sidebar, text="v2.0  •  multi-account",
            font=ctk.CTkFont("Helvetica", 9), text_color="#1e2130"
        ).pack(side="bottom", pady=(0, 4))

        # ── Content ───────────────────────────────────────────────────────────
        self.content = ctk.CTkFrame(self, fg_color="#0d0f14", corner_radius=0)
        self.content.pack(side="right", fill="both", expand=True)

        self.frames = {
            0: AccountsFrame(self.content, self),
            1: ContactsFrame(self.content, self),
            2: ChatsFrame(self.content, self),
            3: BroadcastFrame(self.content, self),
            4: ParserFrame(self.content, self),
            5: HistoryFrame(self.content, self),
            6: LolzFrame(self.content, self),
        }
        for f in self.frames.values():
            f.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Refresh account counter every 5s
        self._refresh_status()

    def _select_nav(self, idx):
        try:
            self.active_nav = idx
            for i, btn in enumerate(self.nav_buttons):
                if i == idx:
                    btn.configure(
                        fg_color="#13151c",
                        text_color="#4fc3f7",
                    )
                else:
                    btn.configure(fg_color="transparent", text_color="#64748b")
            self.frames[idx].tkraise()
            if hasattr(self.frames[idx], "on_show"):
                self.frames[idx].on_show()
        except Exception as exc:
            log_exception(exc, f"nav:{idx}")
            show_error(self, "Ошибка навигации", exc)

    def _refresh_status(self):
        try:
            accounts = db.get_accounts(active_only=True)
            total = db.get_accounts()
            banned = sum(1 for a in total if a.get("is_banned"))
            muted = sum(1 for a in total if a.get("is_muted"))
            self.acc_count_lbl.configure(
                text=f"🟢 {len(accounts)} акт / 🟡 {muted} мут / ☠ {banned} бан",
                text_color="#4ade80" if accounts else "#4a5568"
            )
        except Exception as exc:
            log_exception(exc, "refresh_status")
        self.after(5000, self._refresh_status)

    def run_async(self, coro, callback=None):
        run_async(coro, callback, on_main=self.after)

    def run_sync(self, func, callback=None):
        run_sync_in_thread(func, callback, on_main=self.after)
