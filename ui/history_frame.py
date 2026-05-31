import customtkinter as ctk

from data import database as db
from ui.widgets import lbl as _label, btn as _btn


STATUS_COLORS = {
    "draft": "#4a5568",
    "running": "#f59e0b",
    "finished": "#4ade80",
    "stopped": "#f87171",
}

TYPE_LABELS = {
    "contacts": "👥 Контакты",
    "chats": "💬 Чаты",
    "dm": "📩 ЛС",
    "dm_parsed": "🔍 ЛС парсер",
    "invite": "📨 Инвайт",
}


class HistoryFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._selected_campaign = None
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))
        _label(header, "История кампаний", size=22, bold=True, color="#e2e8f0").pack(anchor="w")
        _label(header, "Журнал всех запущенных рассылок", size=13, color="#4a5568").pack(anchor="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=20)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        # ── Left: campaigns list ──────────────────────────────────────────
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        top = ctk.CTkFrame(left, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        _label(top, "Кампании", size=15, bold=True, color="#e2e8f0").pack(side="left")
        _btn(top, "↻", color="#1e2130", hover="#2a2f45", width=36, command=self._load_campaigns
             ).pack(side="right")

        hdr = ctk.CTkFrame(left, fg_color="#1a1d27", corner_radius=8)
        hdr.pack(fill="x")
        for text, w in [("Название", 140), ("Тип", 90), ("Статус", 80), ("✓/✗", 70)]:
            ctk.CTkLabel(hdr, text=text, width=w,
                font=ctk.CTkFont("Helvetica", 11, "bold"), text_color="#4a5568"
            ).pack(side="left", padx=8, pady=6)

        self.camp_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.camp_scroll.pack(fill="both", expand=True, pady=(4, 0))

        # ── Right: logs ───────────────────────────────────────────────────
        right = ctk.CTkFrame(body, fg_color="#13151c", corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew")

        _label(right, "Детальный лог", size=15, bold=True, color="#4fc3f7"
               ).pack(anchor="w", padx=20, pady=(18, 4))
        ctk.CTkFrame(right, height=1, fg_color="#1e2130").pack(fill="x", padx=20, pady=8)

        # campaign info
        self.info_frame = ctk.CTkFrame(right, fg_color="#1a1d27", corner_radius=10)
        self.info_frame.pack(fill="x", padx=20, pady=(0, 12))

        self.info_name = _label(self.info_frame, "Выберите кампанию", size=14, bold=True, color="#e2e8f0")
        self.info_name.pack(anchor="w", padx=12, pady=(10, 2))

        stats_row = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=12, pady=(0, 10))
        self.info_stats = _label(stats_row, "", size=12, color="#4a5568")
        self.info_stats.pack(side="left")

        # log box
        self.log_box = ctk.CTkTextbox(
            right, corner_radius=8,
            fg_color="#0d0f14", border_color="#1e2130",
            text_color="#6b7280", font=ctk.CTkFont("Courier", 11),
            state="disabled"
        )
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self._load_campaigns()

    def _load_campaigns(self):
        for w in self.camp_scroll.winfo_children():
            w.destroy()
        campaigns = db.get_campaigns()
        for c in campaigns:
            row = ctk.CTkFrame(self.camp_scroll, fg_color="#13151c", corner_radius=8)
            row.pack(fill="x", pady=2)
            row.bind("<Button-1>", lambda e, cid=c["id"], cn=c: self._show_logs(cn))

            _label(row, (c.get("name") or "—")[:18], size=12, color="#c9d1e0"
                   ).pack(side="left", padx=8, pady=8)

            type_text = TYPE_LABELS.get(c.get("campaign_type") or "", c.get("campaign_type") or "—")
            _label(row, type_text, size=11, color="#4a5568"
                   ).pack(side="left", padx=4)

            status = c.get("status") or "draft"
            _label(row, status, size=11, color=STATUS_COLORS.get(status, "#4a5568")
                   ).pack(side="left", padx=8)

            sent = c.get("sent_count") or 0
            failed = c.get("failed_count") or 0
            _label(row, f"{sent}/{failed}", size=11, color="#4a5568"
                   ).pack(side="left", padx=4)

            _btn(row, "▶", color="#1e2130", hover="#2a2f45", width=32, h=28,
                 command=lambda cn=c: self._show_logs(cn)
                 ).pack(side="right", padx=4, pady=4)

    def _show_logs(self, campaign):
        self._selected_campaign = campaign
        name = campaign.get("name") or "—"
        status = campaign.get("status") or "—"
        sent = campaign.get("sent_count") or 0
        failed = campaign.get("failed_count") or 0
        total = campaign.get("total_targets") or 0
        ctype = TYPE_LABELS.get(campaign.get("campaign_type") or "", "—")
        created = (campaign.get("created_at") or "")[:16]

        self.info_name.configure(text=f"{name}  [{status.upper()}]",
                                  text_color=STATUS_COLORS.get(status, "#e2e8f0"))
        self.info_stats.configure(
            text=f"{ctype}  |  Всего: {total}  |  ✓ {sent}  |  ✗ {failed}  |  {created}"
        )

        logs = db.get_campaign_logs(campaign["id"])
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        for log in logs:
            ts = (log.get("sent_at") or "")[:19]
            target = log.get("target") or "—"
            s = log.get("status") or "—"
            err = log.get("error_text") or ""
            icon = "✓" if s == "ok" else "✗"
            line = f"{ts}  {icon}  {target}"
            if err:
                line += f"  →  {err}"
            self.log_box.insert("end", line + "\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def on_show(self):
        self._load_campaigns()
