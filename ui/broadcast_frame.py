import customtkinter as ctk
from tkinter import messagebox, filedialog
import asyncio
import random
import threading

from core.errors import humanize_error, log_exception
from data import database as db
from core.account_pool import AccountPool, MultiAccountSender
from ui.widgets import card, lbl, ent, btn, sep, txt, enable_scroll


class BroadcastFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._sender = None
        self._running = False
        self._pool = AccountPool()
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=32, pady=(28, 0))
        lbl(hdr, "Рассылка", size=22, bold=True, color="#e2e8f0").pack(anchor="w")
        lbl(hdr, "Многоаккаунтная рассылка с автоматической ротацией", size=13, color="#4a5568").pack(anchor="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=16)
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        # ── Left: settings ────────────────────────────────────────────────
        left = ctk.CTkScrollableFrame(body, fg_color="transparent", label_text="")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Campaign name
        lbl(left, "Название кампании (пример: Рассылка июнь)").pack(anchor="w", pady=(0, 2))
        self.e_name = ent(left, "Моя кампания")
        self.e_name.pack(fill="x", pady=(0, 12))

        # Mode selection
        mode_card = card(left)
        mode_card.pack(fill="x", pady=(0, 10))
        lbl(mode_card, "📌  Тип рассылки", size=13, bold=True, color="#4fc3f7"
            ).pack(anchor="w", padx=14, pady=(12, 6))
        self.mode_var = ctk.StringVar(value="contacts")
        modes = [
            ("contacts", "👥  По контактам", "Личные сообщения контактам из базы"),
            ("chats", "💬  По чатам", "Отправка в группы и каналы"),
            ("dm_parsed", "🔍  ЛС спарсенным", "Личные сообщения комментаторам"),
            ("single_blast", "🎯  Всеми аккаунтами → 1 юзер", "Каждый активный акк пишет одному"),
        ]
        for val, label, hint in modes:
            row = ctk.CTkFrame(mode_card, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=2)
            ctk.CTkRadioButton(row, text=label, variable=self.mode_var, value=val,
                fg_color="#2563eb", hover_color="#1d4ed8",
                text_color="#e2e8f0", font=ctk.CTkFont("Helvetica", 13)
            ).pack(side="left")
            lbl(row, hint, size=10, color="#4a5568").pack(side="left", padx=8)
        ctk.CTkFrame(mode_card, fg_color="transparent", height=8).pack()

        blast_row = ctk.CTkFrame(mode_card, fg_color="transparent")
        blast_row.pack(fill="x", padx=14, pady=(0, 8))
        lbl(blast_row, "Получатель для режима «1 юзер» (пример: @username)", size=11, color="#8892a4"
            ).pack(anchor="w")
        self.e_single_user = ent(blast_row, "@durov")
        self.e_single_user.pack(fill="x", pady=(2, 0))

        # Message text
        lbl(left, "Текст сообщения").pack(anchor="w", pady=(0, 2))
        self.txt_msg = txt(left, height=130, font=ctk.CTkFont("Helvetica", 13))
        self.txt_msg.pack(fill="x", pady=(0, 6))

        lbl(left,
            "💡 Переменные: {first_name} {last_name} {username}  |  Используйте для персонализации",
            size=10, color="#4a5568").pack(anchor="w", pady=(0, 10))

        # Spin-text (anti-spam variation)
        spin_card = card(left)
        spin_card.pack(fill="x", pady=(0, 10))
        spin_hdr = ctk.CTkFrame(spin_card, fg_color="transparent")
        spin_hdr.pack(fill="x", padx=14, pady=(10, 4))
        lbl(spin_hdr, "🔄  Спин-текст (вариации сообщений)", size=12, bold=True, color="#c9d1e0"
            ).pack(side="left")
        self.spin_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(spin_hdr, text="", variable=self.spin_var,
            fg_color="#1a1d27", progress_color="#2563eb",
            button_color="#4fc3f7", button_hover_color="#38bdf8"
        ).pack(side="right")
        lbl(spin_card,
            "Добавьте варианты через {вариант1|вариант2|вариант3}\nПример: {Привет|Здравствуйте|Добрый день}, как дела?",
            size=11, color="#4a5568", justify="left").pack(anchor="w", padx=14, pady=(0, 10))

        # Media
        media_row = ctk.CTkFrame(left, fg_color="transparent")
        media_row.pack(fill="x", pady=(0, 10))
        self.media_lbl = lbl(media_row, "📎  Без медиа", size=11, color="#4a5568")
        self.media_lbl.pack(side="left")
        btn(media_row, "Прикрепить", color="#1e2130", hover="#2a2f45", h=30,
            command=self._pick_media).pack(side="right")
        btn(media_row, "✕", color="#1e2130", hover="#7f1d1d", h=30, width=30,
            command=self._clear_media).pack(side="right", padx=4)
        self._media_path = None

        # Anti-ban settings
        ab_card = card(left)
        ab_card.pack(fill="x", pady=(0, 10))
        lbl(ab_card, "🛡  Антибан настройки", size=13, bold=True, color="#4fc3f7"
            ).pack(anchor="w", padx=14, pady=(12, 6))

        grid = ctk.CTkFrame(ab_card, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(0, 10))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(2, weight=1)

        for col, (label, attr, default) in enumerate([
            ("Задержка мин (сек)", "e_delay_min", "5"),
            ("Задержка макс (сек)", "e_delay_max", "15"),
            ("Сообщ/аккаунт", "e_msgs_per", "30"),
        ]):
            f = ctk.CTkFrame(grid, fg_color="transparent")
            f.grid(row=0, column=col, sticky="ew", padx=4)
            lbl(f, label, size=11, color="#8892a4").pack(anchor="w", pady=(0, 2))
            e = ent(f, default)
            e.pack(fill="x")
            setattr(self, attr, e)

        self.rotate_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(ab_card, text="Ротация аккаунтов (рекомендуется)",
            variable=self.rotate_var, fg_color="#2563eb",
            text_color="#c9d1e0", font=ctk.CTkFont("Helvetica", 12)
        ).pack(anchor="w", padx=14, pady=(0, 10))

        # Account selection
        acc_card = card(left)
        acc_card.pack(fill="x", pady=(0, 10))
        acc_hdr = ctk.CTkFrame(acc_card, fg_color="transparent")
        acc_hdr.pack(fill="x", padx=14, pady=(12, 4))
        lbl(acc_hdr, "👤  Аккаунты для рассылки", size=13, bold=True, color="#c9d1e0").pack(side="left")
        btn(acc_hdr, "↻", color="#1e2130", hover="#2a2f45", h=28, width=32,
            command=self._load_account_list).pack(side="right")

        self.acc_all_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(acc_card, text="Использовать все активные аккаунты",
            variable=self.acc_all_var,
            fg_color="#2563eb", text_color="#c9d1e0",
            font=ctk.CTkFont("Helvetica", 12),
            command=self._toggle_acc_list
        ).pack(anchor="w", padx=14, pady=(0, 6))

        self.acc_list_frame = ctk.CTkScrollableFrame(acc_card, height=120, fg_color="transparent")
        self.acc_list_frame.pack(fill="x", padx=14, pady=(0, 10))
        enable_scroll(self.acc_list_frame)
        self._acc_checks = {}
        self._load_account_list()

        # Start / Stop buttons
        action_row = ctk.CTkFrame(left, fg_color="transparent")
        action_row.pack(fill="x", pady=(4, 16))
        self.btn_start = btn(action_row, "▶  Запустить рассылку",
            color="#059669", hover="#047857", h=44,
            command=self._start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.btn_stop = btn(action_row, "⏹  Стоп",
            color="#7f1d1d", hover="#991b1b", h=44,
            state="disabled", command=self._stop)
        self.btn_stop.pack(side="right", expand=True, fill="x")

        # ── Right: live progress ──────────────────────────────────────────
        right = card(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        lbl(right, "📊  Прогресс", size=15, bold=True, color="#4fc3f7"
            ).pack(anchor="w", padx=16, pady=(16, 4))
        sep(right)

        # Big stats
        stats_grid = ctk.CTkFrame(right, fg_color="transparent")
        stats_grid.pack(fill="x", padx=14, pady=(0, 10))
        self._stats = {}
        for i, (key, label, color) in enumerate([
            ("total",  "Всего",      "#4a5568"),
            ("sent",   "Отправлено", "#4ade80"),
            ("failed", "Ошибок",     "#f87171"),
        ]):
            box = ctk.CTkFrame(stats_grid, fg_color="#1a1d27", corner_radius=10)
            box.grid(row=0, column=i, sticky="ew", padx=3)
            stats_grid.columnconfigure(i, weight=1)
            num = lbl(box, "0", size=28, bold=True, color=color)
            num.pack(pady=(10, 2))
            lbl(box, label, size=10, color="#4a5568").pack(pady=(0, 10))
            self._stats[key] = num

        # Progress bar
        self.prog_bar = ctk.CTkProgressBar(right, height=8, corner_radius=4,
            fg_color="#1a1d27", progress_color="#2563eb")
        self.prog_bar.pack(fill="x", padx=14, pady=(0, 4))
        self.prog_bar.set(0)

        self.prog_label = lbl(right, "Готов к отправке", size=11, color="#4a5568")
        self.prog_label.pack(anchor="w", padx=14, pady=(0, 4))

        self.acc_label = lbl(right, "", size=11, color="#60a5fa")
        self.acc_label.pack(anchor="w", padx=14, pady=(0, 10))

        # Account mini status
        sep(right)
        lbl(right, "Состояние аккаунтов", size=12, bold=True, color="#c9d1e0"
            ).pack(anchor="w", padx=14, pady=(0, 4))
        self.acc_status_scroll = ctk.CTkScrollableFrame(right, height=100, fg_color="transparent")
        self.acc_status_scroll.pack(fill="x", padx=10)
        enable_scroll(self.acc_status_scroll)

        sep(right)

        # Log
        lbl(right, "Лог", size=12, bold=True, color="#c9d1e0"
            ).pack(anchor="w", padx=14, pady=(0, 4))
        self.log_box = txt(right, readonly=True, fg_color="#0d0f14", border_color="#1e2130",
            text_color="#6b7280")
        self.log_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.tag_colors = {"ok": "#4ade80", "err": "#f87171", "warn": "#f59e0b", "info": "#60a5fa"}

    def _load_account_list(self):
        for w in self.acc_list_frame.winfo_children():
            w.destroy()
        self._acc_checks = {}
        accounts = db.get_accounts(active_only=True)
        if not accounts:
            lbl(self.acc_list_frame, "Нет активных аккаунтов", color="#4a5568", size=11
                ).pack(pady=4)
            return
        for acc in accounts:
            var = ctk.BooleanVar(value=True)
            self._acc_checks[acc["id"]] = var
            ctk.CTkCheckBox(self.acc_list_frame,
                text=f"{acc.get('phone') or 'ID:'+str(acc['id'])}  [{acc.get('country') or '?'}]  день: {acc.get('daily_sent',0)}",
                variable=var,
                fg_color="#2563eb", hover_color="#1d4ed8",
                text_color="#c9d1e0", font=ctk.CTkFont("Helvetica", 11)
            ).pack(anchor="w", pady=2)

    def _toggle_acc_list(self):
        show = not self.acc_all_var.get()
        # just re-render
        self._load_account_list()

    def _get_selected_accounts(self):
        all_accs = db.get_accounts(active_only=True)
        if self.acc_all_var.get():
            return all_accs
        return [a for a in all_accs if self._acc_checks.get(a["id"], ctk.BooleanVar(value=False)).get()]

    def _pick_media(self):
        path = filedialog.askopenfilename(
            filetypes=[("Медиа", "*.jpg *.jpeg *.png *.gif *.mp4 *.mp3 *.pdf"), ("Все", "*.*")]
        )
        if path:
            import os
            self._media_path = path
            self.media_lbl.configure(text=f"📎  {os.path.basename(path)}", text_color="#4fc3f7")

    def _clear_media(self):
        self._media_path = None
        self.media_lbl.configure(text="📎  Без медиа", text_color="#4a5568")

    def _log(self, text, kind="info"):
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")

    def _set_stats(self, total=None, sent=None, failed=None):
        if total is not None: self._stats["total"].configure(text=str(total))
        if sent is not None:  self._stats["sent"].configure(text=str(sent))
        if failed is not None: self._stats["failed"].configure(text=str(failed))
        self._update_acc_status()

    def _update_acc_status(self):
        for w in self.acc_status_scroll.winfo_children():
            w.destroy()
        accounts = db.get_accounts()
        for acc in accounts[:20]:  # show max 20
            status = "banned" if acc.get("is_banned") else "active"
            color = "#4ade80" if status == "active" else "#f87171"
            phone = acc.get("phone") or f"ID:{acc['id']}"
            text = f"{phone}  d:{acc.get('daily_sent',0)}  t:{acc.get('total_sent',0)}"
            if self._pool.is_on_cooldown(acc["id"]):
                cd = self._pool.cooldown_remaining(acc["id"])
                text += f"  ⏳{cd}s"
                color = "#f59e0b"
            lbl(self.acc_status_scroll, text, size=10, color=color).pack(anchor="w", pady=1)

    def _resolve_spintext(self, text):
        """Process {a|b|c} spin syntax."""
        import re
        def pick(m):
            opts = m.group(1).split("|")
            return random.choice(opts)
        return re.sub(r'\{([^}]+)\}', pick, text)

    def _personalize(self, text, target):
        """Replace {first_name} etc."""
        return (text
            .replace("{first_name}", target.get("first_name") or "")
            .replace("{last_name}", target.get("last_name") or "")
            .replace("{username}", f"@{target.get('username')}" if target.get("username") else "")
        )

    def _start(self):
        try:
            base_text = self.txt_msg.get("1.0", "end").strip()
            if not base_text:
                messagebox.showerror("Ошибка", "Введите текст сообщения")
                return

            accounts = self._get_selected_accounts()
            if not accounts:
                messagebox.showwarning("Нет аккаунтов", "Добавьте и активируйте аккаунты во вкладке Аккаунты")
                return

            mode = self.mode_var.get()
            if mode == "contacts":
                targets = db.get_contacts()
                t_list = [{"identifier": c.get("username") or c.get("phone") or c.get("user_id"),
                           **c} for c in targets if c.get("username") or c.get("phone")]
            elif mode == "chats":
                chats = db.get_chats(active_only=True)
                t_list = [{"identifier": c.get("username") or c.get("chat_id"), **c} for c in chats]
            elif mode == "single_blast":
                target = self.e_single_user.get().strip().lstrip("@")
                if not target:
                    messagebox.showerror("Ошибка", "Укажите username получателя (пример: @durov)")
                    return
                t_list = [{"identifier": target, "username": target} for _ in accounts]
            else:
                parsed = db.get_parsed_users()
                t_list = [{"identifier": u.get("username"), **u} for u in parsed if u.get("username")]

            if not t_list:
                messagebox.showwarning("Нет целей", "База целей пуста для выбранного режима")
                return

            if self._media_path and not __import__("pathlib").Path(self._media_path).is_file():
                messagebox.showerror("Ошибка", "Прикреплённый медиафайл не найден")
                return

            name = self.e_name.get().strip() or "Кампания"
            try:
                dmin = int(self.e_delay_min.get())
                dmax = int(self.e_delay_max.get())
                mpa = int(self.e_msgs_per.get())
                if dmin < 0 or dmax < 0 or mpa < 1 or dmin > dmax:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Настройки", "Некорректные задержки. Используются 5/15/30 сек.")
                dmin, dmax, mpa = 5, 15, 30

            campaign_id = db.create_campaign(
                name=name, campaign_type=mode, message_text=base_text,
                delay_min=dmin, delay_max=dmax, media_path=self._media_path,
                rotate_accounts=int(self.rotate_var.get()), msgs_per_account=mpa
            )
        except Exception as exc:
            log_exception(exc, "broadcast._start")
            self.app.report_error("Ошибка запуска рассылки", exc)
            return

        # Reset UI
        self.log_box.delete("1.0", "end")
        self.prog_bar.set(0)
        self._set_stats(total=len(t_list), sent=0, failed=0)
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._running = True

        spin = self.spin_var.get()
        pool = self._pool
        sender = MultiAccountSender(pool)
        self._sender = sender

        prepared = []
        for t in t_list:
            txt = self._resolve_spintext(base_text) if spin else base_text
            txt = self._personalize(txt, t)
            prepared.append({**t, "_text": txt})

        def _progress(current, total, target_name, sent, failed, acc_phone):
            pct = current / total if total else 0
            self.app.after(0, lambda: self.prog_bar.set(pct))
            self.app.after(0, lambda: self.prog_label.configure(
                text=f"{current}/{total}  —  {target_name}"
            ))
            self.app.after(0, lambda: self.acc_label.configure(
                text=f"Текущий аккаунт: {acc_phone}"
            ))
            self.app.after(0, lambda: self._set_stats(sent=sent, failed=failed))

        def _log_cb(text, kind="info"):
            self.app.after(0, lambda: self._log(text, kind))

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    sender.run_campaign(
                        campaign_id=campaign_id,
                        accounts=accounts,
                        targets=prepared,
                        text=base_text,
                        campaign_type=mode,
                        delay_min=dmin,
                        delay_max=dmax,
                        msgs_per_account=mpa,
                        media_path=self._media_path,
                        rotate_accounts=self.rotate_var.get(),
                        progress_cb=_progress,
                        log_cb=_log_cb,
                    )
                )
                sent, failed = result
                self.app.after(0, lambda: self._on_done(sent, failed))
            except Exception as e:
                log_exception(e, "broadcast._run")
                self.app.after(0, lambda err=humanize_error(e): self._on_error(err))
            finally:
                loop.run_until_complete(pool.disconnect_all())
                loop.close()

        threading.Thread(target=_run, daemon=True).start()

    def _stop(self):
        if self._sender:
            self._sender.stop()
        self._running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self._log("⏹  Остановлено пользователем", "warn")

    def _on_done(self, sent, failed):
        self._running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.prog_bar.set(1)
        self._set_stats(sent=sent, failed=failed)
        self._log(f"✅  Завершено! Отправлено: {sent}, ошибок: {failed}", "ok")
        self.prog_label.configure(text="✅  Рассылка завершена", text_color="#4ade80")

    def _on_error(self, err):
        self._running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self._log(f"❌  Критическая ошибка: {err}", "err")

    def on_show(self):
        self._load_account_list()
        self._update_acc_status()
