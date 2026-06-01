"""
Полноценная вкладка Lolzteam Market API — эксплорер всех методов + быстрые действия.
"""
import json
import threading

import customtkinter as ctk
from tkinter import messagebox

from core.errors import humanize_error, log_exception
from core.lolzteam_api import LolzMarketClient
from core.lolz_api_registry import (
    OPERATIONS,
    OPERATIONS_BY_ID,
    GROUPS_RU,
    MARKET_CATEGORIES,
)
from data import database as db
from ui.widgets import card, lbl, ent, btn


class LolzFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._param_widgets: dict[str, ctk.CTkEntry] = {}
        self._current_op_id: str | None = None
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=32, pady=(28, 0))
        lbl(hdr, "Lolzteam Market API", size=22, bold=True, color="#e2e8f0").pack(anchor="w")
        lbl(hdr, "Все методы api.lzt.market — документация: lzt-market.readme.io",
            size=12, color="#4a5568").pack(anchor="w")

        # Token bar
        tok = card(self)
        tok.pack(fill="x", padx=32, pady=(12, 0))
        tr = ctk.CTkFrame(tok, fg_color="transparent")
        tr.pack(fill="x", padx=14, pady=10)
        lbl(tr, "API Token (scope: market)", size=11, color="#8892a4").pack(anchor="w")
        row = ctk.CTkFrame(tr, fg_color="transparent")
        row.pack(fill="x", pady=4)
        self.token_entry = ent(row, "Bearer token")
        saved = db.get_setting("lolz_api_token")
        if saved:
            self.token_entry.insert(0, saved)
        self.token_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn(row, "💾", color="#1e2130", hover="#2a2f45", width=40,
            command=self._save_token).pack(side="left", padx=2)
        btn(row, "🔗", color="#2563eb", hover="#1d4ed8", width=40,
            command=lambda: self._run(lambda: self._client().get_profile(), self._on_profile)).pack(side="left")
        self.profile_lbl = lbl(tr, "", size=11, color="#4ade80")
        self.profile_lbl.pack(anchor="w", pady=(4, 0))

        # Main tabs: Explorer | Quick search | TG import
        self.main_tabs = ctk.CTkTabview(
            self,
            fg_color="#13151c",
            segmented_button_fg_color="#1a1d27",
            segmented_button_selected_color="#7c3aed",
            segmented_button_unselected_color="#1a1d27",
        )
        self.main_tabs.pack(fill="both", expand=True, padx=32, pady=12)
        self.main_tabs.add("🔧  API Explorer")
        self.main_tabs.add("🔍  Быстрый поиск")
        self.main_tabs.add("✈  TG импорт")

        self._build_explorer(self.main_tabs.tab("🔧  API Explorer"))
        self._build_quick_search(self.main_tabs.tab("🔍  Быстрый поиск"))
        self._build_tg_import(self.main_tabs.tab("✈  TG импорт"))

    # ── API Explorer ──────────────────────────────────────────────────────────

    def _build_explorer(self, tab):
        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=260)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Left: group + operations
        left = ctk.CTkFrame(body, fg_color="#0d0f14", corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        lbl(left, "Раздел", size=11, color="#8892a4").pack(anchor="w", padx=10, pady=(10, 2))
        self._group_keys = ["all"] + sorted(set(o["group"] for o in OPERATIONS))
        group_labels = ["— Все методы —"] + [
            GROUPS_RU.get(g, g) for g in self._group_keys[1:]
        ]
        self.group_var = ctk.StringVar(value=group_labels[0])
        self._group_label_to_key = dict(zip(group_labels, self._group_keys))
        self.group_menu = ctk.CTkOptionMenu(
            left, variable=self.group_var, values=group_labels,
            command=self._filter_operations,
            fg_color="#1a1d27", button_color="#2a2f45",
        )
        self.group_menu.pack(fill="x", padx=10, pady=(0, 4))
        lbl(left, f"{len(OPERATIONS)} методов API", size=9, color="#4a5568").pack(
            anchor="w", padx=10, pady=(0, 6),
        )

        self.op_list = ctk.CTkScrollableFrame(left, fg_color="transparent", width=240)
        self.op_list.pack(fill="both", expand=True, padx=6, pady=(0, 10))
        self._op_buttons: list[ctk.CTkButton] = []
        self._render_operation_list()

        # Right: params + response
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        top = ctk.CTkFrame(right, fg_color="#13151c", corner_radius=10)
        top.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        top.columnconfigure(0, weight=1)

        self.op_title = lbl(top, "Выберите операцию слева", size=14, bold=True, color="#4fc3f7")
        self.op_title.pack(anchor="w", padx=12, pady=(10, 2))
        self.op_desc = lbl(top, "", size=10, color="#4a5568")
        self.op_desc.pack(anchor="w", padx=12)

        self.params_scroll = ctk.CTkScrollableFrame(top, height=140, fg_color="transparent")
        self.params_scroll.pack(fill="x", padx=8, pady=6)

        brow = ctk.CTkFrame(top, fg_color="transparent")
        brow.pack(fill="x", padx=12, pady=(0, 10))
        self.method_lbl = lbl(brow, "", size=11, color="#f59e0b")
        self.method_lbl.pack(side="left")
        btn(brow, "▶  Выполнить", color="#059669", hover="#047857",
            command=self._execute_selected).pack(side="right")

        bottom = ctk.CTkFrame(right, fg_color="#13151c", corner_radius=10)
        bottom.grid(row=1, column=0, sticky="nsew")
        bottom.rowconfigure(1, weight=1)
        bottom.columnconfigure(0, weight=1)
        rh = ctk.CTkFrame(bottom, fg_color="transparent")
        rh.pack(fill="x", padx=12, pady=(8, 4))
        lbl(rh, "Ответ JSON", size=12, bold=True, color="#c9d1e0").pack(side="left")
        btn(rh, "Копировать", color="#1e2130", hover="#2a2f45", h=28,
            command=self._copy_response).pack(side="right")
        self.response_box = ctk.CTkTextbox(
            bottom, corner_radius=8, fg_color="#1a1d27", border_color="#2a2f45",
            font=ctk.CTkFont("Courier", 11), text_color="#a5f3fc",
        )
        self.response_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.response_box.insert("1.0", "{\n  \"hint\": \"Выберите метод и нажмите Выполнить\"\n}")

        # Произвольный запрос (любой путь API)
        custom = ctk.CTkFrame(right, fg_color="#13151c", corner_radius=10)
        custom.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        lbl(custom, "Произвольный запрос", size=11, bold=True, color="#8892a4").pack(
            anchor="w", padx=12, pady=(8, 4),
        )
        cr = ctk.CTkFrame(custom, fg_color="transparent")
        cr.pack(fill="x", padx=12, pady=(0, 8))
        self.custom_method = ctk.CTkOptionMenu(
            cr, values=["GET", "POST", "PUT", "DELETE"], width=90,
            fg_color="#1a1d27", button_color="#2a2f45",
        )
        self.custom_method.pack(side="left", padx=(0, 6))
        self.custom_path = ent(cr, "/telegram?pmax=100")
        self.custom_path.pack(side="left", fill="x", expand=True, padx=(0, 6))
        btn(cr, "▶", width=40, color="#059669", hover="#047857",
            command=self._custom_request).pack(side="left")

    def _render_operation_list(self, filter_group: str = "all"):
        for w in self.op_list.winfo_children():
            w.destroy()
        self._op_buttons.clear()
        for op in OPERATIONS:
            if filter_group != "all" and op["group"] != filter_group:
                continue
            title = op["title"]
            method = op["method"]
            b = ctk.CTkButton(
                self.op_list,
                text=f"{method}  {title}",
                anchor="w",
                height=32,
                fg_color="transparent",
                hover_color="#1a1d27",
                text_color="#94a3b8",
                font=ctk.CTkFont("Helvetica", 11),
                command=lambda oid=op["id"]: self._select_operation(oid),
            )
            b.pack(fill="x", pady=1)
            self._op_buttons.append(b)

    def _filter_operations(self, _label: str = ""):
        key = self._group_label_to_key.get(self.group_var.get(), "all")
        self._render_operation_list(key)

    def _select_operation(self, op_id: str):
        self._current_op_id = op_id
        op = OPERATIONS_BY_ID[op_id]
        for b in self._op_buttons:
            b.configure(fg_color="transparent", text_color="#94a3b8")
        self.op_title.configure(
            text=f"{op['method']}  {op['title']}",
        )
        self.op_desc.configure(
            text=GROUPS_RU.get(op["group"], op["group"]) + "  •  " + op["path"]
            + (f"\n{op['description']}" if op.get("description") else ""),
        )
        self.method_lbl.configure(text=op["path"])
        for w in self.params_scroll.winfo_children():
            w.destroy()
        self._param_widgets.clear()
        for field in op.get("fields", []):
            row = ctk.CTkFrame(self.params_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            req = " *" if field.get("required") else ""
            lbl(row, field.get("label", field["name"]) + req, size=10,
                color="#8892a4").pack(anchor="w")
            e = ent(row, field.get("placeholder", ""))
            e.pack(fill="x")
            self._param_widgets[field["name"]] = e
        if not op.get("fields"):
            lbl(self.params_scroll, "Без параметров", size=11, color="#4a5568").pack(anchor="w")

    def _execute_selected(self):
        if not self._current_op_id:
            messagebox.showwarning("API", "Выберите операцию в списке слева")
            return
        values = {k: w.get() for k, w in self._param_widgets.items()}
        op_id = self._current_op_id

        def _call():
            return self._client().execute_operation(op_id, values)

        self._set_response("⏳ Запрос...", loading=True)
        self._run(_call, self._on_api_response)

    def _on_api_response(self, data, err):
        if err:
            self._set_response(json.dumps({"error": err}, ensure_ascii=False, indent=2))
            return
        self._set_response(LolzMarketClient.format_json(data))

    def _set_response(self, text: str, loading: bool = False):
        self.response_box.configure(state="normal")
        self.response_box.delete("1.0", "end")
        self.response_box.insert("1.0", text)

    def _copy_response(self):
        text = self.response_box.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(text)

    def _custom_request(self):
        method = self.custom_method.get()
        raw = self.custom_path.get().strip()
        if not raw:
            return
        path = raw
        params = None
        if "?" in raw:
            path, qs = raw.split("?", 1)
            params = {}
            for part in qs.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k] = v
        search = method == "GET" and path.strip("/").split("/")[0] in {
            c[0] for c in MARKET_CATEGORIES
        }

        def _go():
            return self._client().request(method, path, params=params, search=search)

        self._set_response("⏳ ...", loading=True)
        self._run(_go, self._on_api_response)

    # ── Quick search ──────────────────────────────────────────────────────────

    def _build_quick_search(self, tab):
        body = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)

        f = card(body)
        f.pack(fill="x", pady=8)
        inner = ctk.CTkFrame(f, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        lbl(inner, "Категория", size=11, color="#8892a4").pack(anchor="w")
        self.q_category = ctk.CTkOptionMenu(
            inner,
            values=[c[0] for c in MARKET_CATEGORIES],
            fg_color="#1a1d27", button_color="#2a2f45",
        )
        self.q_category.set("telegram")
        self.q_category.pack(fill="x", pady=(0, 8))
        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x")
        grid.columnconfigure((0, 1, 2), weight=1)
        self.q_pmin = ent(grid, "0")
        self.q_pmax = ent(grid, "500")
        self.q_page = ent(grid, "1")
        for col, (lab, w) in enumerate([
            ("Цена от", self.q_pmin), ("Цена до", self.q_pmax), ("Стр.", self.q_page),
        ]):
            c = ctk.CTkFrame(grid, fg_color="transparent")
            c.grid(row=0, column=col, sticky="ew", padx=3)
            lbl(c, lab, size=10, color="#8892a4").pack(anchor="w")
            w.pack(fill="x")
        btn(inner, "🔍  Поиск", color="#7c3aed", hover="#6d28d9",
            command=self._quick_search).pack(fill="x", pady=(10, 0))

        self.q_results = ctk.CTkScrollableFrame(body, fg_color="#13151c", height=320)
        self.q_results.pack(fill="both", expand=True, pady=8)

    def _quick_search(self):
        cat = self.q_category.get()
        params = {"order_by": "price_to_up"}
        try:
            if self.q_pmin.get().strip():
                params["pmin"] = int(self.q_pmin.get())
            if self.q_pmax.get().strip():
                params["pmax"] = int(self.q_pmax.get())
            if self.q_page.get().strip():
                params["page"] = int(self.q_page.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректные числа")
            return

        def _go():
            return self._client().search_category(cat, **params)

        self._run(_go, self._on_quick_search)

    def _on_quick_search(self, data, err):
        for w in self.q_results.winfo_children():
            w.destroy()
        if err:
            lbl(self.q_results, f"Ошибка: {err}", color="#f87171").pack(anchor="w", padx=8, pady=8)
            return
        items = (data or {}).get("items") or []
        lbl(self.q_results, f"Найдено: {len(items)}", size=12, color="#4ade80").pack(
            anchor="w", padx=8, pady=4,
        )
        for it in items[:40]:
            iid = it.get("item_id")
            price = it.get("price")
            title = (it.get("title") or "")[:55]
            row = ctk.CTkFrame(self.q_results, fg_color="#1a1d27", corner_radius=6)
            row.pack(fill="x", pady=2, padx=6)
            lbl(row, f"#{iid}  {price}₽  {title}", size=11).pack(side="left", padx=8, pady=6)
            acts = ctk.CTkFrame(row, fg_color="transparent")
            acts.pack(side="right", padx=4)
            btn(acts, "ℹ", width=32, h=28, color="#1e2130", hover="#2a2f45",
                command=lambda i=iid: self._show_item_json(i)).pack(side="left", padx=2)
            btn(acts, "🛒", width=32, h=28, color="#059669", hover="#047857",
                command=lambda i=iid, p=price: self._quick_buy(i, p)).pack(side="left", padx=2)

    def _show_item_json(self, item_id):
        self._run(
            lambda: self._client().get_item(item_id),
            lambda d, e: self._open_json_window(f"Item #{item_id}", d, e),
        )

    def _quick_buy(self, item_id, price):
        if not messagebox.askyesno("Покупка", f"Купить товар #{item_id} за {price}₽?"):
            return
        self._run(
            lambda: self._client().fast_buy(item_id, price),
            lambda d, e: messagebox.showinfo("Результат", e or "Покупка выполнена"),
        )

    def _open_json_window(self, title, data, err):
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry("700x500")
        tb = ctk.CTkTextbox(win, font=ctk.CTkFont("Courier", 11))
        tb.pack(fill="both", expand=True, padx=10, pady=10)
        text = err or LolzMarketClient.format_json(data)
        tb.insert("1.0", text)

    # ── TG import ─────────────────────────────────────────────────────────────

    def _build_tg_import(self, tab):
        body = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)

        imp = card(body)
        imp.pack(fill="x", pady=8)
        inner = ctk.CTkFrame(imp, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        lbl(inner, "Импорт Telegram session в TG Sender", size=13, bold=True, color="#4fc3f7").pack(anchor="w")
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=8)
        row.columnconfigure((0, 1), weight=1)
        c1 = ctk.CTkFrame(row, fg_color="transparent")
        c1.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        lbl(c1, "API ID").pack(anchor="w")
        self.tg_api_id = ent(c1, db.get_setting("lolz_default_api_id") or "")
        self.tg_api_id.pack(fill="x")
        c2 = ctk.CTkFrame(row, fg_color="transparent")
        c2.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        lbl(c2, "API Hash").pack(anchor="w")
        self.tg_api_hash = ent(c2, db.get_setting("lolz_default_api_hash") or "")
        self.tg_api_hash.pack(fill="x")
        btn(inner, "📦  Загрузить покупки (Telegram)", color="#059669", hover="#047857",
            command=self._load_tg_orders).pack(fill="x")

        self.tg_orders = ctk.CTkScrollableFrame(body, fg_color="#13151c", height=400)
        self.tg_orders.pack(fill="both", expand=True, pady=8)
        self.tg_status = lbl(body, "", size=11, color="#4a5568")
        self.tg_status.pack(anchor="w", padx=4)

    def _load_tg_orders(self):
        self.tg_status.configure(text="Загрузка...", text_color="#f59e0b")

        def _go():
            return self._client().get_orders(category_id=24)

        self._run(_go, self._on_tg_orders)

    def _on_tg_orders(self, data, err):
        for w in self.tg_orders.winfo_children():
            w.destroy()
        if err:
            self.tg_status.configure(text=f"Ошибка: {err}", text_color="#f87171")
            return
        items = (data or {}).get("items") or []
        self.tg_status.configure(text=f"Покупок: {len(items)}", text_color="#4ade80")
        for it in items[:50]:
            iid = it.get("item_id")
            title = (it.get("title") or str(iid))[:48]
            row = ctk.CTkFrame(self.tg_orders, fg_color="#1a1d27", corner_radius=6)
            row.pack(fill="x", pady=2, padx=6)
            lbl(row, f"#{iid}  {title}", size=11).pack(side="left", padx=8, pady=6)
            btn(row, "Импорт в TG Sender", h=28, color="#2563eb", hover="#1d4ed8",
                command=lambda item=it: self._import_tg(item)).pack(side="right", padx=6)

    def _import_tg(self, item_summary: dict):
        api_id = self.tg_api_id.get().strip()
        api_hash = self.tg_api_hash.get().strip()
        if not api_id or not api_hash:
            messagebox.showerror("Ошибка", "Укажите API ID и API Hash")
            return
        item_id = item_summary.get("item_id")
        self.tg_status.configure(text=f"Импорт #{item_id}...", text_color="#f59e0b")

        def _fetch():
            full = self._client().get_item(item_id)
            item = full.get("item") or full
            session = LolzMarketClient.extract_telegram_session(item)
            if not session:
                raise ValueError(
                    "Session string не найден в ответе API. "
                    "Откройте товар на lzt.market и импортируйте вручную (Session String)."
                )
            return session, item

        def _done(result, err):
            if err:
                self.tg_status.configure(text=err, text_color="#f87171")
                return
            session, item = result
            phone = item.get("telegram_phone") or item.get("login") or ""
            acc_id = db.add_account(
                api_id=api_id, api_hash=api_hash,
                session_string=session,
                phone=str(phone) if phone else None,
                notes="lolz.market",
            )
            db.set_setting("lolz_default_api_id", api_id)
            db.set_setting("lolz_default_api_hash", api_hash)
            self.tg_status.configure(text=f"✅ Аккаунт #{acc_id} добавлен", text_color="#4ade80")
            messagebox.showinfo("Готово", f"Аккаунт #{acc_id} добавлен в пул")

        self._run(_fetch, _done)

    # ── Shared ────────────────────────────────────────────────────────────────

    def _client(self) -> LolzMarketClient:
        token = self.token_entry.get().strip() or db.get_setting("lolz_api_token")
        return LolzMarketClient(token)

    def _save_token(self):
        db.set_setting("lolz_api_token", self.token_entry.get().strip())
        messagebox.showinfo("Сохранено", "Токен сохранён")

    def _run(self, func, callback):
        def _thread():
            try:
                result = func()
                self.app.after(0, lambda: callback(result, None))
            except Exception as exc:
                log_exception(exc, "lolz_frame")
                self.app.after(0, lambda e=humanize_error(exc): callback(None, e))
        threading.Thread(target=_thread, daemon=True).start()

    def _on_profile(self, data, err):
        if err:
            self.profile_lbl.configure(text=f"❌ {err}", text_color="#f87171")
        else:
            self.profile_lbl.configure(
                text="✅ " + LolzMarketClient.format_profile_summary(data),
                text_color="#4ade80",
            )

    def on_show(self):
        pass
