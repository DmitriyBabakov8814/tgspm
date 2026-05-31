import customtkinter as ctk
from tkinter import messagebox, filedialog
import csv

from data import database as db
from ui.widgets import lbl as _label, ent as _entry, btn as _btn


class ContactsFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))
        _label(header, "Контакты", size=22, bold=True, color="#e2e8f0").pack(anchor="w")
        _label(header, "База контактов для рассылки", size=13, color="#4a5568").pack(anchor="w")

        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.pack(fill="x", padx=32, pady=(16, 0))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._load())
        e = _entry(tb, "🔍  Поиск...", textvariable=self.search_var, width=280, height=38)
        e.pack(side="left")

        _btn(tb, "＋  Добавить", command=self._add_dialog).pack(side="left", padx=(10, 4))
        _btn(tb, "📥  Импорт CSV", color="#1e2130", hover="#2a2f45", command=self._import_csv).pack(side="left", padx=4)
        _btn(tb, "📤  Экспорт CSV", color="#1e2130", hover="#2a2f45", command=self._export_csv).pack(side="left", padx=4)
        _btn(tb, "🗑  Очистить всё", color="#7f1d1d", hover="#991b1b", command=self._clear_all).pack(side="right")

        self.stats_label = _label(self, "", size=12, color="#4a5568")
        self.stats_label.pack(anchor="w", padx=32, pady=(8, 0))

        hdr = ctk.CTkFrame(self, fg_color="#1a1d27", corner_radius=8)
        hdr.pack(fill="x", padx=32, pady=(12, 0))
        for text, w in [("Имя", 160), ("Username", 150), ("Телефон", 130), ("Источник", 120), ("", 60)]:
            ctk.CTkLabel(hdr, text=text, width=w,
                font=ctk.CTkFont("Helvetica", 11, "bold"),
                text_color="#4a5568").pack(side="left", padx=8, pady=6)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=32, pady=(4, 20))

        self._load()

    def _load(self):
        try:
            for w in self.scroll.winfo_children():
                w.destroy()
            contacts = db.get_contacts(self.search_var.get())
            self.stats_label.configure(text=f"Всего контактов: {len(contacts)}")
            for c in contacts:
                row = ctk.CTkFrame(self.scroll, fg_color="#13151c", corner_radius=8)
                row.pack(fill="x", pady=2)
                name = f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip() or "—"
                for text, w in [
                    (name, 160),
                    (f"@{c['username']}" if c.get("username") else "—", 150),
                    (c.get("phone") or "—", 130),
                    (c.get("source") or "—", 120),
                ]:
                    ctk.CTkLabel(row, text=text, width=w, anchor="w",
                        font=ctk.CTkFont("Helvetica", 12), text_color="#c9d1e0"
                    ).pack(side="left", padx=8, pady=7)
                _btn(row, "✕", color="#7f1d1d", hover="#991b1b", width=32, h=28,
                     command=lambda cid=c["id"]: self._delete(cid)).pack(side="left", padx=4)
        except Exception as exc:
            self.app.report_error("Ошибка загрузки контактов", exc)

    def _add_dialog(self):
        win = ctk.CTkToplevel(self)
        win.title("Добавить контакт")
        win.geometry("400x340")
        win.configure(fg_color="#13151c")
        win.grab_set()

        _label(win, "Новый контакт", size=15, bold=True).pack(pady=(16, 8))

        fields = {}
        for label, key in [("Имя", "first_name"), ("Фамилия", "last_name"),
                            ("Username", "username"), ("Телефон", "phone")]:
            f = ctk.CTkFrame(win, fg_color="transparent")
            f.pack(fill="x", padx=20, pady=3)
            _label(f, label, size=12).pack(anchor="w")
            e = _entry(f, height=38)
            e.pack(fill="x")
            fields[key] = e

        def _save():
            try:
                db.add_contact(
                    username=fields["username"].get().strip().lstrip("@") or None,
                    first_name=fields["first_name"].get().strip() or None,
                    last_name=fields["last_name"].get().strip() or None,
                    phone=fields["phone"].get().strip() or None,
                    source="manual"
                )
                self._load()
                win.destroy()
            except Exception as exc:
                self.app.report_error("Ошибка сохранения контакта", exc)

        _btn(win, "Сохранить", command=_save).pack(fill="x", padx=20, pady=16)

    def _import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        count = 0
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    db.add_contact(
                        username=row.get("username") or row.get("Username") or None,
                        first_name=row.get("first_name") or row.get("name") or None,
                        last_name=row.get("last_name") or None,
                        phone=row.get("phone") or None,
                        source="csv_import"
                    )
                    count += 1
            self._load()
            messagebox.showinfo("Импорт", f"Добавлено {count} контактов")
        except Exception as e:
            self.app.report_error("Ошибка импорта CSV", e)

    def _export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        contacts = db.get_contacts()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id","first_name","last_name","username","phone","source","created_at"])
            writer.writeheader()
            writer.writerows(contacts)
        messagebox.showinfo("Экспорт", f"Экспортировано {len(contacts)} контактов")

    def _delete(self, cid):
        db.delete_contact(cid)
        self._load()

    def _clear_all(self):
        if messagebox.askyesno("Очистить", "Удалить все контакты?"):
            db.delete_all_contacts()
            self._load()

    def on_show(self):
        self._load()
