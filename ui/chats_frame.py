import customtkinter as ctk
from tkinter import messagebox

from data import database as db
from core.tg_client import TGClient
from ui.widgets import card as _card, lbl as _label, ent as _entry, btn as _btn


class ChatsFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))
        _label(header, "База чатов", size=22, bold=True, color="#e2e8f0").pack(anchor="w")
        _label(header, "Группы и каналы для рассылки", size=13, color="#4a5568").pack(anchor="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=20)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1)

        # ── Left: list ────────────────────────────────────────────────────
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        tb = ctk.CTkFrame(left, fg_color="transparent")
        tb.pack(fill="x", pady=(0, 12))
        _btn(tb, "↻  Обновить", color="#1e2130", hover="#2a2f45", command=self._load).pack(side="left")
        _btn(tb, "🗑  Удалить выбранные", color="#7f1d1d", hover="#991b1b",
             command=self._delete_selected).pack(side="right")

        self.stats = _label(left, "", size=12, color="#4a5568")
        self.stats.pack(anchor="w", pady=(0, 8))

        # table header
        hdr = ctk.CTkFrame(left, fg_color="#1a1d27", corner_radius=8)
        hdr.pack(fill="x")
        for text, w in [("", 30), ("Название", 200), ("Username", 160), ("Тип", 80), ("Участников", 100), ("", 80)]:
            ctk.CTkLabel(hdr, text=text, width=w,
                font=ctk.CTkFont("Helvetica", 11, "bold"), text_color="#4a5568"
            ).pack(side="left", padx=6, pady=6)

        self.scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, pady=(4, 0))

        # ── Right: add chat ───────────────────────────────────────────────
        right = _card(body)
        right.grid(row=0, column=1, sticky="nsew")

        _label(right, "Добавить чат", size=14, bold=True, color="#4fc3f7").pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkFrame(right, height=1, fg_color="#1e2130").pack(fill="x", padx=16, pady=8)

        form = ctk.CTkFrame(right, fg_color="transparent")
        form.pack(fill="x", padx=16)

        _label(form, "Username или ID чата").pack(anchor="w", pady=(0, 2))
        self.e_username = _entry(form, "@group_name")
        self.e_username.pack(fill="x", pady=(0, 10))

        _label(form, "Название (опционально)").pack(anchor="w", pady=(0, 2))
        self.e_title = _entry(form, "Мой чат")
        self.e_title.pack(fill="x", pady=(0, 10))

        _label(form, "Тип").pack(anchor="w", pady=(0, 2))
        self.type_var = ctk.StringVar(value="group")
        ctk.CTkOptionMenu(
            form, variable=self.type_var,
            values=["group", "channel", "supergroup"],
            fg_color="#1a1d27", button_color="#2a2f45",
            dropdown_fg_color="#1a1d27", text_color="#e2e8f0"
        ).pack(fill="x", pady=(0, 12))

        _btn(form, "Добавить", command=self._add).pack(fill="x", pady=(0, 8))

        ctk.CTkFrame(right, height=1, fg_color="#1e2130").pack(fill="x", padx=16, pady=8)
        _label(right, "Авто-поиск чатов", size=13, bold=True, color="#c9d1e0").pack(anchor="w", padx=16, pady=(0, 4))

        self.e_search_tg = _entry(right, "Ключевое слово...")
        self.e_search_tg.pack(fill="x", padx=16, pady=(0, 8))
        _btn(right, "🔍  Найти и добавить", color="#1e2130", hover="#2a2f45",
             command=self._search_tg).pack(fill="x", padx=16, pady=(0, 16))

        self._load()

    def _load(self):
        try:
            for w in self.scroll.winfo_children():
                w.destroy()
            self._checks = {}
            chats = db.get_chats()
        active = sum(1 for c in chats if c["is_active"])
        self.stats.configure(text=f"Всего: {len(chats)}  |  Активных: {active}")
        for c in chats:
            row = ctk.CTkFrame(self.scroll,
                fg_color="#13151c" if c["is_active"] else "#0f1117",
                corner_radius=8)
            row.pack(fill="x", pady=2)
            var = ctk.BooleanVar()
            self._checks[c["id"]] = var
            ctk.CTkCheckBox(row, text="", variable=var, width=30,
                checkbox_width=18, checkbox_height=18,
                fg_color="#2563eb", hover_color="#1d4ed8"
            ).pack(side="left", padx=6, pady=8)

            title = c.get("title") or "—"
            for text, w in [
                (title[:28], 200),
                (f"@{c['username']}" if c.get("username") else str(c.get("chat_id") or "—"), 160),
                (c.get("chat_type") or "—", 80),
                (str(c.get("members_count") or 0), 100),
            ]:
                ctk.CTkLabel(row, text=text, width=w, anchor="w",
                    font=ctk.CTkFont("Helvetica", 12),
                    text_color="#c9d1e0" if c["is_active"] else "#4a5568"
                ).pack(side="left", padx=4, pady=8)

            tog_text = "Вкл" if c["is_active"] else "Выкл"
            tog_color = "#1a3a1a" if c["is_active"] else "#1e2130"
            _btn(row, tog_text, color=tog_color, hover="#2a2f45", width=50, h=28,
                 command=lambda cid=c["id"]: self._toggle(cid)).pack(side="left", padx=4)
            _btn(row, "✕", color="#7f1d1d", hover="#991b1b", width=32, h=28,
                 command=lambda cid=c["id"]: self._delete(cid)).pack(side="left", padx=2)

    def _add(self):
        username = self.e_username.get().strip().lstrip("@")
        title = self.e_title.get().strip()
        if not username:
            messagebox.showerror("Ошибка", "Введите username или ID")
            return
        db.add_chat(username=username, title=title or username, chat_type=self.type_var.get())
        self.e_username.delete(0, "end")
        self.e_title.delete(0, "end")
        self._load()

    def _search_tg(self):
        accounts = db.get_accounts(active_only=True)
        if not accounts:
            messagebox.showwarning("Нет аккаунта", "Сначала добавьте и авторизуйте аккаунт")
            return
        kw = self.e_search_tg.get().strip()
        if not kw:
            return

        acc = accounts[0]
        client = TGClient(acc)

        async def _go():
            ok = await client.connect()
            if not ok:
                raise Exception("Аккаунт не авторизован")
            try:
                return await client.search_chats(kw, limit=20)
            finally:
                await client.disconnect()

        def _cb(found, err):
            if err:
                messagebox.showerror("Ошибка", err)
                return
            for c in (found or []):
                db.add_chat(**c)
            self._load()
            messagebox.showinfo("Поиск", f"Добавлено {len(found or [])} чатов")

        self.app.run_async(_go(), _cb)

    def _toggle(self, cid):
        db.toggle_chat(cid)
        self._load()

    def _delete(self, cid):
        db.delete_chat(cid)
        self._load()

    def _delete_selected(self):
        selected = [cid for cid, var in self._checks.items() if var.get()]
        if not selected:
            return
        if messagebox.askyesno("Удалить", f"Удалить {len(selected)} чатов?"):
            for cid in selected:
                db.delete_chat(cid)
            self._load()

    def on_show(self):
        self._load()
