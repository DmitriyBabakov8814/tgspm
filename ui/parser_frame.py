import customtkinter as ctk
from tkinter import messagebox
import threading
import asyncio

from core.errors import humanize_error, log_exception
from data import database as db
from core.tg_client import TGClient
from core.account_pool import AccountPool, MultiAccountSender
from ui.widgets import card, lbl, ent, btn, sep, txt, enable_scroll


class ParserFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=32, pady=(28, 0))
        lbl(hdr, "Парсер каналов", size=22, bold=True, color="#e2e8f0").pack(anchor="w")
        lbl(hdr, "Сбор комментаторов → Рассылка в ЛС → Приглашение в канал",
            size=13, color="#4a5568").pack(anchor="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=16)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # ── Left panel ────────────────────────────────────────────────────
        left = ctk.CTkScrollableFrame(body, fg_color="transparent", label_text="")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Parse settings
        pc = card(left)
        pc.pack(fill="x", pady=(0, 10))
        lbl(pc, "🔍  Парсинг канала", size=14, bold=True, color="#4fc3f7"
            ).pack(anchor="w", padx=14, pady=(12, 4))
        sep(pc)

        f = ctk.CTkFrame(pc, fg_color="transparent")
        f.pack(fill="x", padx=14)

        lbl(f, "Канал-источник").pack(anchor="w", pady=(0, 2))
        self.e_source = ent(f, "@channel или t.me/channel")
        self.e_source.pack(fill="x", pady=(0, 8))

        lbl(f, "Кол-во постов для парсинга").pack(anchor="w", pady=(0, 2))
        self.e_posts = ent(f, "30")
        self.e_posts.pack(fill="x", pady=(0, 8))

        self.bots_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(f, text="Пропускать ботов",
            variable=self.bots_var, fg_color="#2563eb",
            text_color="#c9d1e0", font=ctk.CTkFont("Helvetica", 12)
        ).pack(anchor="w", pady=(0, 6))

        self.add_contacts_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(f, text="Добавить в контакты",
            variable=self.add_contacts_var, fg_color="#2563eb",
            text_color="#c9d1e0", font=ctk.CTkFont("Helvetica", 12)
        ).pack(anchor="w", pady=(0, 12))

        self.parse_prog = ctk.CTkProgressBar(pc, height=6, corner_radius=3,
            fg_color="#1a1d27", progress_color="#f59e0b")
        self.parse_prog.pack(fill="x", padx=14, pady=(0, 4))
        self.parse_prog.set(0)
        self.parse_status = lbl(pc, "Ожидание...", size=11, color="#4a5568")
        self.parse_status.pack(anchor="w", padx=14, pady=(0, 4))

        self.btn_parse = btn(pc, "🔍  Начать парсинг",
            color="#7c3aed", hover="#6d28d9", command=self._start_parse)
        self.btn_parse.pack(fill="x", padx=14, pady=(0, 14))

        # ── DM action ─────────────────────────────────────────────────────
        dc = card(left)
        dc.pack(fill="x", pady=(0, 10))
        lbl(dc, "📩  Рассылка в личные сообщения", size=14, bold=True, color="#4fc3f7"
            ).pack(anchor="w", padx=14, pady=(12, 4))
        sep(dc)

        df = ctk.CTkFrame(dc, fg_color="transparent")
        df.pack(fill="x", padx=14)

        lbl(df, "Текст сообщения в ЛС").pack(anchor="w", pady=(0, 2))
        self.txt_dm = txt(df, height=90, font=ctk.CTkFont("Helvetica", 12))
        self.txt_dm.pack(fill="x", pady=(0, 8))

        row = ctk.CTkFrame(df, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        lbl(row, "Задержка мин").pack(side="left")
        self.dm_dmin = ent(row, "8", width=60)
        self.dm_dmin.pack(side="left", padx=6)
        lbl(row, "макс").pack(side="left")
        self.dm_dmax = ent(row, "20", width=60)
        self.dm_dmax.pack(side="left", padx=6)

        lbl(df, "Сообщ/аккаунт (лимит)").pack(anchor="w", pady=(0, 2))
        self.dm_per_acc = ent(df, "20")
        self.dm_per_acc.pack(fill="x", pady=(0, 8))

        self.dm_selected_only = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(df, text="Только выбранные (галочки в таблице)",
            variable=self.dm_selected_only, fg_color="#2563eb",
            text_color="#c9d1e0", font=ctk.CTkFont("Helvetica", 12)
        ).pack(anchor="w", pady=(0, 8))

        self.dm_prog = ctk.CTkProgressBar(dc, height=6, corner_radius=3,
            fg_color="#1a1d27", progress_color="#2563eb")
        self.dm_prog.pack(fill="x", padx=14, pady=(0, 4))
        self.dm_prog.set(0)
        self.dm_status = lbl(dc, "", size=11, color="#4a5568")
        self.dm_status.pack(anchor="w", padx=14, pady=(0, 4))

        btn_row = ctk.CTkFrame(dc, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 8))
        self.btn_dm = btn(btn_row, "📩  Разослать в ЛС", color="#059669", hover="#047857",
            command=self._start_dm)
        self.btn_dm.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.btn_dm_stop = btn(btn_row, "⏹", color="#7f1d1d", hover="#991b1b",
            width=44, state="disabled", command=self._stop_dm)
        self.btn_dm_stop.pack(side="left")

        # DM stats
        dm_stats = ctk.CTkFrame(dc, fg_color="transparent")
        dm_stats.pack(fill="x", padx=14, pady=(0, 14))
        self._dm_stats = {}
        for i, (key, label, color) in enumerate([
            ("sent", "Отправлено", "#4ade80"),
            ("failed", "Ошибок", "#f87171"),
        ]):
            b = ctk.CTkFrame(dm_stats, fg_color="#1a1d27", corner_radius=8)
            b.pack(side="left", expand=True, fill="x", padx=3)
            n = lbl(b, "0", size=22, bold=True, color=color)
            n.pack(pady=(8, 2))
            lbl(b, label, size=10, color="#4a5568").pack(pady=(0, 8))
            self._dm_stats[key] = n

        # ── Invite action ─────────────────────────────────────────────────
        ic = card(left)
        ic.pack(fill="x", pady=(0, 10))
        lbl(ic, "➕  Пригласить в канал", size=14, bold=True, color="#4fc3f7"
            ).pack(anchor="w", padx=14, pady=(12, 4))
        sep(ic)

        ig = ctk.CTkFrame(ic, fg_color="transparent")
        ig.pack(fill="x", padx=14)

        lbl(ig, "Ваш канал (куда приглашать)").pack(anchor="w", pady=(0, 2))
        self.e_my_ch = ent(ig, "@my_channel")
        self.e_my_ch.pack(fill="x", pady=(0, 8))

        lbl(ig, "Задержка (сек)").pack(anchor="w", pady=(0, 2))
        self.e_inv_delay = ent(ig, "10")
        self.e_inv_delay.pack(fill="x", pady=(0, 12))

        btn(ig, "➕  Пригласить выбранных",
            color="#1d4ed8", hover="#1e40af", command=self._invite_selected
            ).pack(fill="x", pady=(0, 4))
        btn(ig, "💾  Сохранить всех в контакты",
            color="#1e2130", hover="#2a2f45", command=self._save_all_contacts
            ).pack(fill="x", pady=(0, 14))

        # ── Right: results table ──────────────────────────────────────────
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        top = ctk.CTkFrame(right, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        lbl(top, "Спарсенные пользователи", size=15, bold=True, color="#e2e8f0").pack(side="left")
        self.parsed_count = lbl(top, "", size=12, color="#4a5568")
        self.parsed_count.pack(side="left", padx=8)

        actions = ctk.CTkFrame(top, fg_color="transparent")
        actions.pack(side="right")
        btn(actions, "Все ✓", color="#1e2130", hover="#2a2f45", h=28, width=60,
            command=self._select_all).pack(side="left", padx=2)
        btn(actions, "Все ✗", color="#1e2130", hover="#2a2f45", h=28, width=60,
            command=self._deselect_all).pack(side="left", padx=2)
        btn(actions, "🗑", color="#7f1d1d", hover="#991b1b", h=28, width=40,
            command=self._clear_parsed).pack(side="left", padx=2)

        # Filter
        filter_row = ctk.CTkFrame(right, fg_color="transparent")
        filter_row.pack(fill="x", pady=(0, 8))
        self.filter_var = ctk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._load_parsed())
        ent(filter_row, "🔍  Фильтр по каналу или имени...", textvariable=self.filter_var, height=34
            ).pack(fill="x")

        # Table header
        hdr = ctk.CTkFrame(right, fg_color="#1a1d27", corner_radius=8)
        hdr.pack(fill="x")
        for text, w in [("✓", 28), ("Имя", 130), ("Username", 120),
                        ("Канал", 110), ("Инвайт", 70), ("ЛС", 70), ("Коммент", 160)]:
            ctk.CTkLabel(hdr, text=text, width=w, anchor="w",
                font=ctk.CTkFont("Helvetica", 11, "bold"), text_color="#4a5568"
            ).pack(side="left", padx=5, pady=6)

        self.scroll = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, pady=(4, 0))
        enable_scroll(self.scroll)
        self._checks = {}

        self._dm_sender = None
        self._load_parsed()

    def _load_parsed(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self._checks = {}
        flt = self.filter_var.get().strip().lower()
        users = db.get_parsed_users()
        if flt:
            users = [u for u in users if
                     flt in (u.get("channel") or "").lower() or
                     flt in (u.get("first_name") or "").lower() or
                     flt in (u.get("username") or "").lower()]
        self.parsed_count.configure(text=f"({len(users)} чел.)")

        STATUS_C = {
            "parsed": "#4a5568", "invited": "#4ade80",
            "failed": "#f87171", "added": "#60a5fa"
        }
        DM_C = {
            "pending": "#4a5568", "sent": "#4ade80",
            "failed": "#f87171", "skip": "#f59e0b"
        }

        for u in users:
            row = ctk.CTkFrame(self.scroll, fg_color="#13151c", corner_radius=8)
            row.pack(fill="x", pady=2)
            var = ctk.BooleanVar()
            self._checks[u["id"]] = (var, u)
            ctk.CTkCheckBox(row, text="", variable=var, width=28,
                checkbox_width=16, checkbox_height=16,
                fg_color="#2563eb", hover_color="#1d4ed8"
            ).pack(side="left", padx=4, pady=6)

            name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or "—"
            for text, w in [
                (name[:16], 130),
                (f"@{u['username']}" if u.get("username") else "—", 120),
                ((u.get("channel") or "")[:14], 110),
            ]:
                ctk.CTkLabel(row, text=text, width=w, anchor="w",
                    font=ctk.CTkFont("Helvetica", 11), text_color="#c9d1e0"
                ).pack(side="left", padx=3, pady=6)

            # Invite status
            inv_status = u.get("status") or "parsed"
            ctk.CTkLabel(row, text=inv_status[:8], width=70,
                font=ctk.CTkFont("Helvetica", 10),
                text_color=STATUS_C.get(inv_status, "#4a5568")
            ).pack(side="left", padx=3)

            # DM status
            dm_status = u.get("dm_status") or "pending"
            ctk.CTkLabel(row, text=dm_status[:8], width=70,
                font=ctk.CTkFont("Helvetica", 10),
                text_color=DM_C.get(dm_status, "#4a5568")
            ).pack(side="left", padx=3)

            comment = (u.get("comment_text") or "")[:28]
            if len(u.get("comment_text") or "") > 28:
                comment += "…"
            ctk.CTkLabel(row, text=comment, width=160, anchor="w",
                font=ctk.CTkFont("Helvetica", 10), text_color="#4a5568"
            ).pack(side="left", padx=3)

    def _select_all(self):
        for var, _ in self._checks.values():
            var.set(True)

    def _deselect_all(self):
        for var, _ in self._checks.values():
            var.set(False)

    # ── Parse ─────────────────────────────────────────────────────────────────

    def _start_parse(self):
        accounts = db.get_accounts(active_only=True)
        if not accounts:
            messagebox.showwarning("Нет аккаунтов", "Добавьте аккаунты во вкладке Аккаунты")
            return
        channel = self.e_source.get().strip().lstrip("@").lstrip("https://t.me/").lstrip("t.me/")
        if not channel:
            messagebox.showerror("Ошибка", "Введите канал")
            return
        try:
            limit = int(self.e_posts.get().strip() or "30")
        except ValueError:
            limit = 30

        self.btn_parse.configure(state="disabled", text="Парсинг...")
        self.parse_prog.set(0)

        # Use first active account for parsing
        acc = accounts[0]
        client = TGClient(acc)

        def _progress(current, total, msg):
            pct = current / total if total else 0
            self.app.after(0, lambda: self.parse_prog.set(pct))
            self.app.after(0, lambda: self.parse_status.configure(text=msg))

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                ok = loop.run_until_complete(client.connect())
                if not ok:
                    raise Exception("Аккаунт не авторизован")
                users = loop.run_until_complete(
                    client.parse_channel_commenters(channel, limit, _progress)
                )
                loop.run_until_complete(client.disconnect())
                self.app.after(0, lambda: self._on_parsed(channel, users))
            except Exception as e:
                log_exception(e, "parser._start_parse")
                self.app.after(0, lambda err=humanize_error(e): self._on_parse_err(err))
            finally:
                loop.close()

        threading.Thread(target=_run, daemon=True).start()

    def _on_parsed(self, channel, users):
        self.btn_parse.configure(state="normal", text="🔍  Начать парсинг")
        self.parse_prog.set(1)
        self.parse_status.configure(text=f"✅ {len(users)} пользователей", text_color="#4ade80")
        db.save_parsed_users(channel, users)
        if self.add_contacts_var.get():
            for u in users:
                db.add_contact(username=u.get("username") or None,
                    user_id=u.get("user_id"), first_name=u.get("first_name"),
                    last_name=u.get("last_name"), source=f"parsed:{channel}")
        self._load_parsed()
        messagebox.showinfo("Парсинг", f"Найдено {len(users)} комментаторов из @{channel}")

    def _on_parse_err(self, err):
        self.btn_parse.configure(state="normal", text="🔍  Начать парсинг")
        self.parse_status.configure(text=f"Ошибка: {err[:60]}", text_color="#f87171")

    # ── DM send ───────────────────────────────────────────────────────────────

    def _start_dm(self):
        text = self.txt_dm.get("1.0", "end").strip()
        if not text:
            messagebox.showerror("Ошибка", "Введите текст сообщения")
            return
        accounts = db.get_accounts(active_only=True)
        if not accounts:
            messagebox.showwarning("Нет аккаунтов", "Добавьте аккаунты")
            return

        if self.dm_selected_only.get():
            targets_raw = [u for uid, (var, u) in self._checks.items() if var.get()]
        else:
            targets_raw = db.get_parsed_users()

        targets = [{"identifier": u.get("username"), **u}
                   for u in targets_raw if u.get("username")]
        if not targets:
            messagebox.showwarning("Нет целей", "Нет пользователей с username")
            return

        try:
            dmin = int(self.dm_dmin.get())
            dmax = int(self.dm_dmax.get())
            mpa = int(self.dm_per_acc.get())
        except ValueError:
            dmin, dmax, mpa = 8, 20, 20

        self.btn_dm.configure(state="disabled")
        self.btn_dm_stop.configure(state="normal")
        self.dm_prog.set(0)
        self._dm_stats["sent"].configure(text="0")
        self._dm_stats["failed"].configure(text="0")

        pool = AccountPool()
        sender = MultiAccountSender(pool)
        self._dm_sender = sender

        campaign_id = db.create_campaign(
            name="ЛС парсер", campaign_type="dm",
            message_text=text, delay_min=dmin, delay_max=dmax,
            msgs_per_account=mpa
        )

        def _progress(current, total, name, sent, failed, acc_phone):
            pct = current / total if total else 0
            self.app.after(0, lambda: self.dm_prog.set(pct))
            self.app.after(0, lambda: self.dm_status.configure(
                text=f"{current}/{total}  {name}  [{acc_phone}]"))
            self.app.after(0, lambda: self._dm_stats["sent"].configure(text=str(sent)))
            self.app.after(0, lambda: self._dm_stats["failed"].configure(text=str(failed)))

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    sender.run_campaign(
                        campaign_id=campaign_id, accounts=accounts,
                        targets=targets, text=text,
                        campaign_type="dm", delay_min=dmin, delay_max=dmax,
                        msgs_per_account=mpa, rotate_accounts=True,
                        progress_cb=_progress,
                    )
                )
                sent, failed = result
                self.app.after(0, lambda: self._on_dm_done(sent, failed))
            except Exception as e:
                log_exception(e, "parser._start_dm")
                self.app.after(0, lambda err=humanize_error(e): self._on_dm_err(err))
            finally:
                loop.run_until_complete(pool.disconnect_all())
                loop.close()

        threading.Thread(target=_run, daemon=True).start()

    def _stop_dm(self):
        if self._dm_sender:
            self._dm_sender.stop()
        self.btn_dm.configure(state="normal")
        self.btn_dm_stop.configure(state="disabled")
        self.dm_status.configure(text="⏹ Остановлено", text_color="#f59e0b")

    def _on_dm_done(self, sent, failed):
        self.btn_dm.configure(state="normal")
        self.btn_dm_stop.configure(state="disabled")
        self.dm_prog.set(1)
        self.dm_status.configure(text=f"✅ Готово: {sent} отправлено, {failed} ошибок",
                                  text_color="#4ade80")
        self._load_parsed()

    def _on_dm_err(self, err):
        self.btn_dm.configure(state="normal")
        self.btn_dm_stop.configure(state="disabled")
        self.dm_status.configure(text=f"❌ {err[:60]}", text_color="#f87171")

    # ── Invite ────────────────────────────────────────────────────────────────

    def _invite_selected(self):
        accounts = db.get_accounts(active_only=True)
        if not accounts:
            messagebox.showwarning("Нет аккаунтов", "Добавьте аккаунты")
            return
        my_channel = self.e_my_ch.get().strip().lstrip("@")
        if not my_channel:
            messagebox.showerror("Ошибка", "Введите ваш канал")
            return

        selected = [u for uid, (var, u) in self._checks.items() if var.get()]
        if not selected:
            messagebox.showinfo("Нет выбранных", "Отметьте пользователей галочкой")
            return

        try:
            delay = int(self.e_inv_delay.get())
        except ValueError:
            delay = 10

        usernames = [u["username"] for u in selected if u.get("username")]
        acc = accounts[0]
        client = TGClient(acc)

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(client.connect())
                results = loop.run_until_complete(
                    client.invite_users_to_channel(my_channel, usernames, delay, None)
                )
                ok = sum(1 for _, s, _ in results if s)
                for uid, (var, u) in self._checks.items():
                    if var.get():
                        db.update_parsed_user_status(uid, status="invited")
                self.app.after(0, lambda: messagebox.showinfo(
                    "Инвайт", f"Приглашено: {ok}/{len(usernames)}"))
                self.app.after(0, self._load_parsed)
                loop.run_until_complete(client.disconnect())
            except Exception as e:
                log_exception(e, "parser._invite")
                self.app.after(0, lambda err=humanize_error(e): messagebox.showerror("Ошибка", err))
            finally:
                loop.close()

        threading.Thread(target=_run, daemon=True).start()

    def _save_all_contacts(self):
        users = db.get_parsed_users()
        for u in users:
            db.add_contact(username=u.get("username") or None,
                user_id=u.get("user_id"), first_name=u.get("first_name"),
                last_name=u.get("last_name"), source=f"parsed:{u.get('channel')}")
        messagebox.showinfo("Сохранено", f"Добавлено {len(users)} контактов")

    def _clear_parsed(self):
        if messagebox.askyesno("Очистить", "Удалить все спарсенные данные?"):
            db.delete_all_parsed_users()
            self._load_parsed()

    def on_show(self):
        self._load_parsed()
