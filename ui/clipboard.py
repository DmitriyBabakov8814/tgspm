"""Global Ctrl+C/V/X/A for CustomTkinter entry and text widgets."""
import tkinter as tk
import customtkinter as ctk


def _focus_target(root: tk.Misc):
    w = root.focus_get()
    if w is None:
        return None, None
    cls = w.winfo_class()
    if cls == "Text":
        return w, "text"
    if cls == "Entry":
        return w, "entry"
    return None, None


def bind_clipboard(root: tk.Misc):
    def _copy(_event=None):
        w, kind = _focus_target(root)
        if not w:
            return
        try:
            if kind == "text":
                if w.tag_ranges("sel"):
                    data = w.selection_get()
                else:
                    data = w.get("1.0", "end-1c")
            else:
                if w.selection_present():
                    data = w.selection_get()
                else:
                    return
            root.clipboard_clear()
            root.clipboard_append(data)
        except tk.TclError:
            pass
        return "break"

    def _cut(_event=None):
        w, kind = _focus_target(root)
        if not w:
            return
        if str(w.cget("state")) == "disabled":
            return "break"
        try:
            if kind == "text":
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

    def _paste(_event=None):
        w, kind = _focus_target(root)
        if not w or str(w.cget("state")) == "disabled":
            return "break"
        try:
            data = root.clipboard_get()
        except tk.TclError:
            return "break"
        try:
            if kind == "text":
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

    def _select_all(_event=None):
        w, kind = _focus_target(root)
        if not w:
            return
        try:
            if kind == "text":
                w.tag_add("sel", "1.0", "end")
                w.mark_set("insert", "end")
            else:
                w.select_range(0, "end")
                w.icursor("end")
        except tk.TclError:
            pass
        return "break"

    for seq, handler in (
        ("<Control-c>", _copy),
        ("<Control-C>", _copy),
        ("<Control-x>", _cut),
        ("<Control-X>", _cut),
        ("<Control-v>", _paste),
        ("<Control-V>", _paste),
        ("<Control-a>", _select_all),
        ("<Control-A>", _select_all),
    ):
        root.bind_all(seq, handler, add="+")


def bind_readonly_log(textbox: ctk.CTkTextbox):
    """Allow selection and Ctrl+C in log areas that are updated programmatically."""
    inner = textbox._textbox

    def _on_key(event):
        if event.state & 0x4 and event.keysym.lower() in ("c", "a"):
            return
        if event.keysym in (
            "Control_L", "Control_R", "Shift_L", "Shift_R",
            "Alt_L", "Alt_R", "Caps_Lock",
        ):
            return
        return "break"

    inner.bind("<Key>", _on_key, add="+")
