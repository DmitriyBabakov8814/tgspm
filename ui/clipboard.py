"""Clipboard shortcuts (Ctrl+C/V/X/A) for CustomTkinter widgets."""
import tkinter as tk
import customtkinter as ctk

_HANDLER_CACHE: dict[int, tuple] = {}


def _resolve_inner(widget):
    if widget is None:
        return None
    if isinstance(widget, ctk.CTkEntry):
        return widget._entry
    if isinstance(widget, ctk.CTkTextbox):
        return widget._textbox
    cls = widget.winfo_class()
    if cls in ("Entry", "Text"):
        return widget
    parent = widget.master
    depth = 0
    while parent and depth < 8:
        if isinstance(parent, ctk.CTkEntry):
            return parent._entry
        if isinstance(parent, ctk.CTkTextbox):
            return parent._textbox
        parent = getattr(parent, "master", None)
        depth += 1
    return None


def _handlers(root: tk.Misc):
    key = id(root)
    if key in _HANDLER_CACHE:
        return _HANDLER_CACHE[key]

    def _copy(event=None):
        w = event.widget if event else _resolve_inner(root.focus_get())
        if w is None and event is None:
            w = _resolve_inner(root.focus_get())
        if w is None:
            return "break"
        try:
            if w.winfo_class() == "Text":
                data = w.selection_get() if w.tag_ranges("sel") else w.get("1.0", "end-1c")
            elif w.selection_present():
                data = w.selection_get()
            else:
                return "break"
            root.clipboard_clear()
            root.clipboard_append(data)
        except tk.TclError:
            pass
        return "break"

    def _cut(event=None):
        w = event.widget if event else _resolve_inner(root.focus_get())
        if w is None:
            return "break"
        if str(w.cget("state")) == "disabled":
            return "break"
        try:
            if w.winfo_class() == "Text":
                if not w.tag_ranges("sel"):
                    return "break"
                data = w.selection_get()
                w.delete("sel.first", "sel.last")
            else:
                if not w.selection_present():
                    return "break"
                data = w.selection_get()
                w.delete("sel.first", "sel.last")
            root.clipboard_clear()
            root.clipboard_append(data)
        except tk.TclError:
            pass
        return "break"

    def _paste(event=None):
        w = event.widget if event else _resolve_inner(root.focus_get())
        if w is None:
            return "break"
        if str(w.cget("state")) == "disabled":
            return "break"
        try:
            data = root.clipboard_get()
        except tk.TclError:
            return "break"
        try:
            if w.winfo_class() == "Text":
                if w.tag_ranges("sel"):
                    w.delete("sel.first", "sel.last")
                w.insert("insert", data)
            else:
                if w.selection_present():
                    w.delete("sel.first", "sel.last")
                w.insert("insert", data)
        except tk.TclError:
            pass
        return "break"

    def _select_all(event=None):
        w = event.widget if event else _resolve_inner(root.focus_get())
        if w is None:
            return "break"
        try:
            if w.winfo_class() == "Text":
                w.tag_add("sel", "1.0", "end")
                w.mark_set("insert", "end")
            else:
                w.select_range(0, "end")
                w.icursor("end")
        except tk.TclError:
            pass
        return "break"

    handlers = (_copy, _cut, _paste, _select_all)
    _HANDLER_CACHE[key] = handlers
    return handlers


def bind_editable(widget):
    """Bind Ctrl+C/V/X/A directly on CTkEntry / CTkTextbox inner widgets."""
    if isinstance(widget, ctk.CTkEntry):
        inner = widget._entry
    elif isinstance(widget, ctk.CTkTextbox):
        inner = widget._textbox
    else:
        return

    root = widget.winfo_toplevel()
    copy_fn, cut_fn, paste_fn, select_all_fn = _handlers(root)
    bindings = (
        ("<Control-c>", copy_fn),
        ("<Control-C>", copy_fn),
        ("<Control-x>", cut_fn),
        ("<Control-X>", cut_fn),
        ("<Control-v>", paste_fn),
        ("<Control-V>", paste_fn),
        ("<Control-a>", select_all_fn),
        ("<Control-A>", select_all_fn),
        ("<Control-Insert>", copy_fn),
        ("<Shift-Insert>", paste_fn),
    )
    for seq, fn in bindings:
        inner.bind(seq, fn, add="+")


def bind_clipboard(root: tk.Misc):
    """Global fallback for focused editable widgets."""
    copy_fn, cut_fn, paste_fn, select_all_fn = _handlers(root)

    def _wrap(fn):
        def handler(_event=None):
            w = _resolve_inner(root.focus_get())
            if not w:
                return
            fn(type("Ev", (), {"widget": w})())
            return "break"
        return handler

    for seq, fn in (
        ("<Control-c>", copy_fn),
        ("<Control-C>", copy_fn),
        ("<Control-x>", cut_fn),
        ("<Control-X>", cut_fn),
        ("<Control-v>", paste_fn),
        ("<Control-V>", paste_fn),
        ("<Control-a>", select_all_fn),
        ("<Control-A>", select_all_fn),
        ("<Control-Insert>", copy_fn),
        ("<Shift-Insert>", paste_fn),
    ):
        root.bind_all(seq, _wrap(fn), add="+")


def bind_readonly_log(textbox: ctk.CTkTextbox):
    """Log viewer: allow select/copy, block typing."""
    bind_editable(textbox)
    inner = textbox._textbox

    def _on_key(event):
        if event.state & 0x4 and event.keysym.lower() in ("c", "a", "v", "x"):
            return
        if event.keysym in (
            "Control_L", "Control_R", "Shift_L", "Shift_R",
            "Alt_L", "Alt_R", "Caps_Lock", "Insert",
        ):
            return
        return "break"

    inner.bind("<Key>", _on_key, add="+")


def bind_all_editables(root: tk.Misc):
    """Walk widget tree and bind clipboard on all CTk entry/text widgets."""

    def walk(w):
        if isinstance(w, (ctk.CTkEntry, ctk.CTkTextbox)):
            bind_editable(w)
        for child in w.winfo_children():
            walk(child)

    walk(root)
