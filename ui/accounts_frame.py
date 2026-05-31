"""
Accounts Frame — multi-account management
Supports: .session file import, session string paste, manual login
"""
import customtkinter as ctk
from tkinter import messagebox, filedialog
import shutil
import threading
from pathlib import Path

from data import database as db
from core.tg_client import TGClient
from core.my_telegram_api import MyTelegramOrgClient
from core.errors import humanize_error
from ui.widgets import card, lbl, ent, btn

SESSION_DIR = Path(__file__).parent.parent / "sessions"
SESSION_DIR.mkdir(exist_ok=True)

STATUS_COLORS = {
    "active": "#4ade80",
    "banned": "#f87171",
    "cooldown": "#f59e0b",
    "unauthorized": "#fb923c",
    "unknown": "#4a5568",
}

# ── Main frame ────────────────────────────────────────────────────────────────

class AccountsFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._verify_jobs = {}
        self._build()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=32, pady=(28, 0))
        lbl(hdr, "Аккаунты", size=22, bold=True, color="#e2e8f0").pack(anchor="w")
        lbl(hdr, "Управление пулом аккаунтов для рассылки", size=13, color="#4a5568").pack(anchor="w")

        # Tabs
        tab_row = ctk.CTkFrame(self, fg_color="transparent")
        tab_row.pack(fill="x", padx=32, pady=(16, 0))

        self.tabview = ctk.CTkTabview(self,
            fg_color="#13151c", segmented_button_fg_color="#1a1d27",
            segmented_button_selected_color="#2563eb",
            segmented_button_selected_hover_color="#1d4ed8",
            segmented_button_unselected_color="#1a1d27",
            segmented_button_unselected_hover_color="#2a2f45",
            text_color="#c9d1e0",
        )
        self.tabview.pack(fill="both", expand=True, padx=32, pady=(12, 20))
        self.tabview.add("📋  Все аккаунты")
        self.tabview.add("📥  Импорт .session")
        self.tabview.add("🔑  Session String")
        self.tabview.add("📲  Ручной вход")
        self.tabview.add("🌐  Прокси")

        self._build_list_tab(self.tabview.tab("📋  Все аккаунты"))
        self._build_session_import_tab(self.tabview.tab("📥  Импорт .session"))
        self._build_string_tab(self.tabview.tab("🔑  Session String"))
        self._build_manual_tab(self.tabview.tab("📲  Ручной вход"))
        self._build_proxy_tab(self.tabview.tab("🌐  Прокси"))

    # ── Tab: All accounts ─────────────────────────────────────────────────────

    def _build_list_tab(self, tab):
        tb = ctk.CTkFrame(tab, fg_color="transparent")
        tb.pack(fill="x", pady=(0, 8))

        self.stats_lbl = lbl(tb, "", size=12, color="#4a5568")
        self.stats_lbl.pack(side="left")

        btn(tb, "↻  Обновить", color="#1e2130", hover="#2a2f45", command=self._load_accounts
            ).pack(side="right", padx=(4, 0))
        btn(tb, "✅  Проверить все", color="#1e2130", hover="#2a2f45",
            command=self._verify_all).pack(side="right", padx=4)
        btn(tb, "🗑  Удалить забаненных", color="#7f1d1d", hover="#991b1b",
            command=self._delete_banned).pack(side="right", padx=4)

        # Table header
        hdr = ctk.CTkFrame(tab, fg_color="#1a1d27", corner_radius=8)
        hdr.pack(fill="x")
        for text, w in [("ID", 40), ("Телефон", 130), ("Страна", 70), ("Статус", 90),
                        ("День/Всего", 90), ("Последний сеанс", 130), ("Прокси", 120), ("", 100)]:
            ctk.CTkLabel(hdr, text=text, width=w, anchor="w",
                font=ctk.CTkFont("Helvetica", 11, "bold"), text_color="#4a5568"
            ).pack(side="left", padx=6, pady=6)

        self.acc_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.acc_scroll.pack(fill="both", expand=True, pady=(4, 0))

        self._load_accounts()

    def _load_accounts(self):
        try:
            for w in self.acc_scroll.winfo_children():
                w.destroy()
            accounts = db.get_accounts()
            active = sum(1 for a in accounts if not a.get("is_banned"))
            banned = sum(1 for a in accounts if a.get("is_banned"))
            total_sent = sum(a.get("total_sent", 0) for a in accounts)
            self.stats_lbl.configure(
                text=f"Всего: {len(accounts)}  |  Активных: {active}  |  Забаненных: {banned}  |  Отправлено всего: {total_sent}"
            )

            for acc in accounts:
                status = "banned" if acc.get("is_banned") else acc.get("status", "unknown")
                sc = STATUS_COLORS.get(status, "#4a5568")

                row = ctk.CTkFrame(self.acc_scroll,
                    fg_color="#13151c" if not acc.get("is_banned") else "#1a0a0a",
                    corner_radius=8)
                row.pack(fill="x", pady=2)

                lbl(row, str(acc["id"]), size=11, color="#4a5568", width=40).pack(side="left", padx=6, pady=8)
                phone = acc.get("phone") or "—"
                lbl(row, phone[:16], size=12, color="#e2e8f0" if not acc.get("is_banned") else "#6b7280",
                    width=130).pack(side="left", padx=4)
                lbl(row, (acc.get("country") or "—")[:8], size=11, color="#4a5568", width=70
                    ).pack(side="left", padx=4)
                lbl(row, status.upper(), size=11, bold=True, color=sc, width=90
                    ).pack(side="left", padx=4)
                day = acc.get("daily_sent", 0)
                total = acc.get("total_sent", 0)
                lbl(row, f"{day}/{total}", size=11, color="#4a5568", width=90
                    ).pack(side="left", padx=4)
                lu = (acc.get("last_used") or "—")[:16]
                lbl(row, lu, size=11, color="#4a5568", width=130).pack(side="left", padx=4)
                proxy = (acc.get("proxy") or "нет")[:18]
                lbl(row, proxy, size=10, color="#4a5568", width=120).pack(side="left", padx=4)
                acts = ctk.CTkFrame(row, fg_color="transparent", width=100)
                acts.pack(side="right", padx=6)
                btn(acts, "✓", color="#1e2130", hover="#2a2f45", h=28, width=32,
                    command=lambda a=acc: self._verify_one(a)).pack(side="left", padx=2)
                btn(acts, "✕", color="#7f1d1d", hover="#991b1b", h=28, width=32,
                    command=lambda a=acc: self._delete_acc(a)).pack(side="left", padx=2)
        except Exception as exc:
            self.app.report_error("Ошибка загрузки аккаунтов", exc)

    # ── Tab: .session import ──────────────────────────────────────────────────

    def _build_session_import_tab(self, tab):
        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        # Left: single import
        left = card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)

        lbl(left, "Импорт одного .session файла", size=14, bold=True, color="#4fc3f7"
            ).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkFrame(left, height=1, fg_color="#1e2130").pack(fill="x", padx=16, pady=8)

        f = ctk.CTkFrame(left, fg_color="transparent")
        f.pack(fill="x", padx=16)

        lbl(f, "API ID").pack(anchor="w", pady=(0, 2))
        self.s_api_id = ent(f, "12345678")
        self.s_api_id.pack(fill="x", pady=(0, 8))

        lbl(f, "API Hash").pack(anchor="w", pady=(0, 2))
        self.s_api_hash = ent(f, "abcdef1234567890...")
        self.s_api_hash.pack(fill="x", pady=(0, 8))

        lbl(f, "Страна (опционально)").pack(anchor="w", pady=(0, 2))
        self.s_country = ent(f, "RU / UA / KZ...")
        self.s_country.pack(fill="x", pady=(0, 8))

        lbl(f, "Прокси (опционально)").pack(anchor="w", pady=(0, 2))
        self.s_proxy = ent(f, "socks5://user:pass@host:port")
        self.s_proxy.pack(fill="x", pady=(0, 12))

        self.s_file_label = lbl(f, "📄  Файл не выбран", size=11, color="#4a5568")
        self.s_file_label.pack(anchor="w", pady=(0, 6))

        btn(f, "📂  Выбрать .session файл", color="#1e2130", hover="#2a2f45",
            command=self._pick_session_file).pack(fill="x", pady=(0, 6))
        btn(f, "✅  Добавить аккаунт", color="#059669", hover="#047857",
            command=self._import_session_file).pack(fill="x", pady=(0, 14))

        self._picked_session = None

        # Right: bulk import
        right = card(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=4)

        lbl(right, "Массовый импорт из папки", size=14, bold=True, color="#4fc3f7"
            ).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkFrame(right, height=1, fg_color="#1e2130").pack(fill="x", padx=16, pady=8)

        lbl(right,
            "Выберите папку с .session файлами.\nВ папке также может быть файл\naccounts.txt с форматом:\n\napi_id|api_hash|телефон|прокси\n(по одной строке на аккаунт)",
            size=12, color="#8892a4", justify="left").pack(anchor="w", padx=16)

        ctk.CTkFrame(right, height=1, fg_color="#1e2130").pack(fill="x", padx=16, pady=10)

        lbl(right, "API ID (общий для всех)").pack(anchor="w", padx=16, pady=(0, 2))
        self.bulk_api_id = ent(right, "12345678")
        self.bulk_api_id.pack(fill="x", padx=16, pady=(0, 8))

        lbl(right, "API Hash (общий для всех)").pack(anchor="w", padx=16, pady=(0, 2))
        self.bulk_api_hash = ent(right, "abcdef...")
        self.bulk_api_hash.pack(fill="x", padx=16, pady=(0, 12))

        self.bulk_status = lbl(right, "", size=11, color="#4ade80")
        self.bulk_status.pack(anchor="w", padx=16, pady=(0, 4))

        btn(right, "📁  Выбрать папку и импортировать",
            command=self._bulk_import_folder).pack(fill="x", padx=16, pady=(0, 14))

    def _pick_session_file(self):
        path = filedialog.askopenfilename(filetypes=[("Session", "*.session"), ("All", "*.*")])
        if path:
            self._picked_session = path
            import os
            self.s_file_label.configure(
                text=f"📄  {os.path.basename(path)}", text_color="#4fc3f7")

    def _import_session_file(self):
        try:
            if not self._picked_session:
                messagebox.showerror("Ошибка", "Выберите .session файл")
                return
            api_id = self.s_api_id.get().strip()
            api_hash = self.s_api_hash.get().strip()
            if not api_id or not api_hash:
                messagebox.showerror("Ошибка", "Введите API ID и API Hash")
                return

            dst = SESSION_DIR / Path(self._picked_session).name
            shutil.copy2(self._picked_session, dst)
            session_path = str(dst.with_suffix(""))

            acc_id = db.add_account(
                api_id=api_id, api_hash=api_hash,
                session_path=session_path,
                country=self.s_country.get().strip() or None,
                proxy=self.s_proxy.get().strip() or None,
            )
            self._verify_after_import(acc_id)
        except Exception as exc:
            self.app.report_error("Ошибка импорта session", exc)

    def _bulk_import_folder(self):
        folder = filedialog.askdirectory(title="Папка с .session файлами")
        if not folder:
            return
        folder = Path(folder)
        api_id = self.bulk_api_id.get().strip()
        api_hash = self.bulk_api_hash.get().strip()

        # Try to read accounts.txt
        acc_map = {}
        txt_file = folder / "accounts.txt"
        if txt_file.exists():
            for line in txt_file.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split("|")
                if len(parts) >= 2:
                    phone = parts[2] if len(parts) > 2 else None
                    proxy = parts[3] if len(parts) > 3 else None
                    acc_map[parts[0].strip()] = {
                        "api_id": parts[0].strip(),
                        "api_hash": parts[1].strip(),
                        "phone": phone,
                        "proxy": proxy,
                    }

        sessions = list(folder.glob("*.session"))
        if not sessions:
            messagebox.showwarning("Нет файлов", "В папке нет .session файлов")
            return

        count = 0
        for sf in sessions:
            dst = SESSION_DIR / sf.name
            shutil.copy2(sf, dst)
            sp = str(dst.with_suffix(""))
            # Match by filename stem (often the phone number)
            stem = sf.stem
            extra = acc_map.get(stem, {})
            db.add_account(
                api_id=extra.get("api_id") or api_id,
                api_hash=extra.get("api_hash") or api_hash,
                phone=extra.get("phone") or stem,
                session_path=sp,
                proxy=extra.get("proxy"),
            )
            count += 1

        self.bulk_status.configure(text=f"✅ Импортировано {count} аккаунтов")
        self._load_accounts()

    # ── Tab: Session string ───────────────────────────────────────────────────

    def _build_string_tab(self, tab):
        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=4, pady=4)

        lbl(body,
            "Вставьте Session String — строку авторизации Telethon.\nМожно получить из любого сервиса генерации сессий.",
            size=12, color="#8892a4", justify="left").pack(anchor="w", pady=(0, 12))

        # Bulk paste area
        lbl(body, "Session String (один или несколько, каждый с новой строки):",
            size=13, bold=True, color="#c9d1e0").pack(anchor="w", pady=(0, 4))
        self.str_strings = ctk.CTkTextbox(body, height=120, corner_radius=8,
            fg_color="#1a1d27", border_color="#2a2f45",
            text_color="#e2e8f0", font=ctk.CTkFont("Courier", 11))
        self.str_strings.pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))

        cf = ctk.CTkFrame(row, fg_color="transparent")
        cf.pack(side="left", fill="x", expand=True, padx=(0, 8))
        lbl(cf, "API ID").pack(anchor="w", pady=(0, 2))
        self.str_api_id = ent(cf, "12345678")
        self.str_api_id.pack(fill="x")

        hf = ctk.CTkFrame(row, fg_color="transparent")
        hf.pack(side="left", fill="x", expand=True)
        lbl(hf, "API Hash").pack(anchor="w", pady=(0, 2))
        self.str_api_hash = ent(hf, "abcdef...")
        self.str_api_hash.pack(fill="x")

        row2 = ctk.CTkFrame(body, fg_color="transparent")
        row2.pack(fill="x", pady=(8, 0))
        pf = ctk.CTkFrame(row2, fg_color="transparent")
        pf.pack(side="left", fill="x", expand=True, padx=(0, 8))
        lbl(pf, "Прокси (опционально)").pack(anchor="w", pady=(0, 2))
        self.str_proxy = ent(pf, "socks5://host:port")
        self.str_proxy.pack(fill="x")

        cof = ctk.CTkFrame(row2, fg_color="transparent")
        cof.pack(side="left", fill="x", expand=True)
        lbl(cof, "Страна").pack(anchor="w", pady=(0, 2))
        self.str_country = ent(cof, "RU / UA...")
        self.str_country.pack(fill="x")

        lbl(body,
            "💡 Для массового импорта: каждая строка = отдельный session string.\n   Все будут добавлены с одинаковыми API ID/Hash.",
            size=11, color="#4a5568").pack(anchor="w", pady=(12, 8))

        self.str_status = lbl(body, "", size=12, color="#4ade80")
        self.str_status.pack(anchor="w", pady=(0, 6))

        btn(body, "✅  Добавить аккаунт(ы)", color="#059669", hover="#047857",
            command=self._import_strings).pack(anchor="w")

    def _import_strings(self):
        raw = self.str_strings.get("1.0", "end").strip()
        api_id = self.str_api_id.get().strip()
        api_hash = self.str_api_hash.get().strip()
        if not raw or not api_id or not api_hash:
            messagebox.showerror("Ошибка", "Заполните все поля")
            return
        strings = [s.strip() for s in raw.splitlines() if s.strip()]
        count = 0
        for s in strings:
            db.add_account(
                api_id=api_id, api_hash=api_hash,
                session_string=s,
                proxy=self.str_proxy.get().strip() or None,
                country=self.str_country.get().strip() or None,
            )
            count += 1
        self.str_status.configure(text=f"✅ Добавлено {count} аккаунтов")
        self._load_accounts()
        if count == 1:
            accounts = db.get_accounts()
            last = accounts[-1] if accounts else None
            if last:
                self._verify_after_import(last["id"])

    # ── Tab: Manual login ─────────────────────────────────────────────────────

    def _build_manual_tab(self, tab):
        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.pack(fill="x", padx=4, pady=4)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        left = card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        lbl(left, "Авторизация по номеру", size=14, bold=True, color="#4fc3f7"
            ).pack(anchor="w", padx=16, pady=(14, 4))
        lbl(left,
            "API ID и Hash будут получены автоматически\nс my.telegram.org после ввода кода",
            size=11, color="#8892a4", justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 4))
        ctk.CTkFrame(left, height=1, fg_color="#1e2130").pack(fill="x", padx=16, pady=8)

        f = ctk.CTkFrame(left, fg_color="transparent")
        f.pack(fill="x", padx=16)

        lbl(f, "Телефон").pack(anchor="w", pady=(0, 2))
        self.m_phone = ent(f, "+79001234567")
        self.m_phone.pack(fill="x", pady=(0, 8))

        lbl(f, "Прокси (опционально)").pack(anchor="w", pady=(0, 2))
        self.m_proxy = ent(f, "socks5://host:port (опционально)")
        self.m_proxy.pack(fill="x", pady=(0, 8))

        api_box = ctk.CTkFrame(f, fg_color="#1a1d27", corner_radius=8)
        api_box.pack(fill="x", pady=(0, 12))
        lbl(api_box, "API credentials (авто)", size=11, bold=True, color="#4a5568"
            ).pack(anchor="w", padx=10, pady=(8, 2))
        self.m_api_id_lbl = lbl(api_box, "API ID:  —", size=12, color="#64748b")
        self.m_api_id_lbl.pack(anchor="w", padx=10)
        self.m_api_hash_lbl = lbl(api_box, "API Hash:  —", size=12, color="#64748b")
        self.m_api_hash_lbl.pack(anchor="w", padx=10, pady=(0, 8))

        btn(f, "📲  Отправить код", command=self._manual_send_code).pack(fill="x", pady=(4, 14))

        # Right: code entry
        right = card(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        lbl(right, "Ввод кода", size=14, bold=True, color="#4fc3f7"
            ).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkFrame(right, height=1, fg_color="#1e2130").pack(fill="x", padx=16, pady=8)

        g = ctk.CTkFrame(right, fg_color="transparent")
        g.pack(fill="x", padx=16)

        lbl(g, "Код из Telegram").pack(anchor="w", pady=(0, 2))
        self.m_code = ent(g, "12345")
        self.m_code.pack(fill="x", pady=(0, 8))

        lbl(g, "Пароль 2FA (если есть)").pack(anchor="w", pady=(0, 2))
        self.m_2fa = ent(g, "••••••", show="•")
        self.m_2fa.pack(fill="x", pady=(0, 12))

        self.m_status = lbl(g, "Введите телефон и нажмите «Отправить код»", size=11, color="#4a5568")
        self.m_status.pack(anchor="w", pady=(0, 8))

        btn(g, "✅  Войти", color="#059669", hover="#047857",
            command=self._manual_sign_in).pack(fill="x", pady=(0, 14))

        self._manual_step = 0       # 0=idle, 1=my.telegram code, 2=telethon code
        self._mytg_client = None
        self._mytg_hash = None
        self._manual_phone = None
        self._manual_proxy = None
        self._manual_client = None
        self._manual_hash = None
        self._manual_acc_id = None

    def _manual_send_code(self):
        phone = self.m_phone.get().strip()
        if not phone:
            messagebox.showerror("Ошибка", "Введите номер телефона")
            return

        proxy = self.m_proxy.get().strip() or None
        self._manual_phone = phone
        self._manual_proxy = proxy
        self._mytg_client = MyTelegramOrgClient(proxy=proxy)
        self._manual_client = None
        self._manual_hash = None
        self._manual_acc_id = None
        self.m_api_id_lbl.configure(text="API ID:  получаем...", text_color="#f59e0b")
        self.m_api_hash_lbl.configure(text="API Hash:  —", text_color="#64748b")
        self.m_status.configure(text="Запрос к my.telegram.org...", text_color="#f59e0b")

        def _thread():
            try:
                random_hash = self._mytg_client.send_password(phone)
                self.app.after(0, lambda: self._on_mytg_code_sent(random_hash, None))
            except Exception as exc:
                self.app.after(0, lambda err=humanize_error(exc): self._on_mytg_code_sent(None, err))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_mytg_code_sent(self, random_hash, err):
        if err:
            self.m_api_id_lbl.configure(text="API ID:  —", text_color="#64748b")
            self.m_status.configure(text=f"Ошибка: {err}", text_color="#f87171")
            return
        self._mytg_hash = random_hash
        self._manual_step = 1
        self.m_status.configure(
            text="✅ Код отправлен! Введите его и нажмите «Войти»",
            text_color="#4ade80",
        )

    def _manual_sign_in(self):
        code = self.m_code.get().strip()
        if not code:
            messagebox.showerror("Ошибка", "Введите код из Telegram")
            return

        if self._manual_step == 1:
            if not self._mytg_client or not self._mytg_hash:
                messagebox.showerror("Ошибка", "Сначала отправьте код")
                return
            self.m_status.configure(text="Получаем API ID/Hash...", text_color="#f59e0b")

            def _thread():
                try:
                    api_id, api_hash = self._mytg_client.login_and_get_credentials(
                        self._manual_phone, self._mytg_hash, code
                    )
                    self.app.after(0, lambda: self._on_api_fetched(api_id, api_hash, None))
                except Exception as exc:
                    self.app.after(0, lambda err=humanize_error(exc): self._on_api_fetched(None, None, err))

            threading.Thread(target=_thread, daemon=True).start()
            return

        if self._manual_step == 2:
            if not self._manual_client:
                messagebox.showerror("Ошибка", "Сессия не инициализирована")
                return
            pw = self.m_2fa.get().strip() or None

            def _cb(result, err):
                if err == "2FA_REQUIRED":
                    if not pw:
                        self.m_status.configure(text="Нужен пароль 2FA!", text_color="#f87171")
                        return
                elif err:
                    self.m_status.configure(text=f"Ошибка: {err}", text_color="#f87171")
                    return

                async def _save():
                    ss = await self._manual_client.get_session_string()
                    db.update_account(self._manual_acc_id, session_string=ss, status="active")

                self.app.run_async(_save(), None)
                self.m_status.configure(text="🎉 Аккаунт добавлен!", text_color="#4ade80")
                self._manual_step = 0
                self._verify_after_import(self._manual_acc_id)
                self._load_accounts()

            async def _go():
                await self._manual_client.sign_in(code, self._manual_hash, pw)

            self.app.run_async(_go(), _cb)
            return

        messagebox.showerror("Ошибка", "Сначала отправьте код")

    def _on_api_fetched(self, api_id, api_hash, err):
        if err:
            self.m_api_id_lbl.configure(text="API ID:  —", text_color="#64748b")
            self.m_status.configure(text=f"Ошибка: {err}", text_color="#f87171")
            return

        self.m_api_id_lbl.configure(text=f"API ID:  {api_id}", text_color="#4ade80")
        self.m_api_hash_lbl.configure(
            text=f"API Hash:  {api_hash[:8]}…{api_hash[-4:]}",
            text_color="#4ade80",
        )

        acc_id = db.add_account(
            api_id=api_id,
            api_hash=api_hash,
            phone=self._manual_phone,
            proxy=self._manual_proxy,
        )
        records = db.get_accounts()
        rec = next((r for r in records if r["id"] == acc_id), None)
        self._manual_client = TGClient(rec)
        self._manual_acc_id = acc_id
        self.m_status.configure(text="Отправляем код для входа в аккаунт...", text_color="#f59e0b")

        def _cb(result, send_err):
            if send_err:
                db.delete_account(acc_id)
                self._manual_client = None
                self.m_status.configure(text=f"Ошибка Telethon: {send_err}", text_color="#f87171")
                return
            self._manual_hash = result
            self._manual_step = 2
            self.m_code.delete(0, "end")
            self.m_status.configure(
                text="✅ API получен! Введите НОВЫЙ код из Telegram и нажмите «Войти»",
                text_color="#4ade80",
            )

        async def _go():
            await self._manual_client.connect()
            return await self._manual_client.send_code()

        self.app.run_async(_go(), _cb)

    # ── Tab: Proxy ────────────────────────────────────────────────────────────

    def _build_proxy_tab(self, tab):
        lbl(tab, "Массовое назначение прокси", size=14, bold=True, color="#4fc3f7"
            ).pack(anchor="w", pady=(4, 8))
        lbl(tab,
            "Формат списка: по одному прокси на строку.\nsocks5://user:pass@host:port\n\nСофт назначит прокси аккаунтам по порядку.",
            size=12, color="#8892a4", justify="left").pack(anchor="w", pady=(0, 10))

        self.proxy_txt = ctk.CTkTextbox(tab, height=200, corner_radius=8,
            fg_color="#1a1d27", border_color="#2a2f45",
            text_color="#e2e8f0", font=ctk.CTkFont("Courier", 11))
        self.proxy_txt.pack(fill="x", pady=(0, 10))

        self.proxy_status = lbl(tab, "", size=12, color="#4ade80")
        self.proxy_status.pack(anchor="w", pady=(0, 6))

        btn(tab, "💾  Назначить прокси аккаунтам", command=self._assign_proxies
            ).pack(anchor="w")

    def _assign_proxies(self):
        proxies = [l.strip() for l in self.proxy_txt.get("1.0", "end").splitlines() if l.strip()]
        if not proxies:
            return
        accounts = db.get_accounts()
        for i, acc in enumerate(accounts):
            if i < len(proxies):
                db.update_account(acc["id"], proxy=proxies[i])
        self.proxy_status.configure(text=f"✅ Назначено {min(len(proxies), len(accounts))} прокси")
        self._load_accounts()

    # ── Verify ────────────────────────────────────────────────────────────────

    def _verify_after_import(self, acc_id):
        """Quick auth check, update phone from Telegram."""
        records = db.get_accounts()
        rec = next((r for r in records if r["id"] == acc_id), None)
        if not rec:
            return
        client = TGClient(rec)

        def _cb(result, err):
            if err or not result:
                db.update_account(acc_id, status="unauthorized")
            else:
                me = result
                db.update_account(acc_id,
                    phone=me.get("phone") or rec.get("phone") or "",
                    status="active")
            self._load_accounts()
            async def _dc():
                await client.disconnect()
            self.app.run_async(_dc(), None)

        async def _go():
            ok = await client.connect()
            if not ok:
                return None
            return await client.get_me()

        self.app.run_async(_go(), _cb)

    def _verify_one(self, acc):
        self._verify_after_import(acc["id"])

    def _verify_all(self):
        accounts = db.get_accounts()
        for acc in accounts:
            self._verify_after_import(acc["id"])

    def _delete_acc(self, acc):
        try:
            db.delete_account(acc["id"])
            self._load_accounts()
        except Exception as exc:
            self.app.report_error("Ошибка удаления", exc)

    def _delete_banned(self):
        accounts = db.get_accounts()
        for acc in accounts:
            if acc.get("is_banned"):
                db.delete_account(acc["id"])
        self._load_accounts()

    def on_show(self):
        self._load_accounts()
