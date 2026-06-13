"""Shared CustomTkinter UI helpers."""
import customtkinter as ctk

from ui.clipboard import bind_editable, bind_readonly_log
from ui.scroll import scrollable, enable_mousewheel


def card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color="#13151c", corner_radius=14, **kw)


def lbl(parent, text, size=13, bold=False, color="#c9d1e0", **kw):
    return ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont("Helvetica", size, "bold" if bold else "normal"),
        text_color=color,
        **kw,
    )


def ent(parent, placeholder="", show="", width=0, height=36, **kw):
    e = ctk.CTkEntry(
        parent,
        placeholder_text=placeholder,
        show=show,
        height=height,
        corner_radius=8,
        fg_color="#1a1d27",
        border_color="#2a2f45",
        text_color="#e2e8f0",
        placeholder_text_color="#4a5568",
        **kw,
    )
    if width:
        e.configure(width=width)
    bind_editable(e)
    return e


def txt(parent, height=120, readonly=False, font=None, **kw):
    defaults = {
        "height": height,
        "corner_radius": 8,
        "fg_color": "#1a1d27",
        "border_color": "#2a2f45",
        "text_color": "#e2e8f0",
        "font": font or ctk.CTkFont("Courier", 11),
    }
    defaults.update(kw)
    tb = ctk.CTkTextbox(parent, **defaults)
    if readonly:
        bind_readonly_log(tb)
    else:
        bind_editable(tb)
    return tb


def btn(parent, text, color="#2563eb", hover="#1d4ed8", h=36, **kw):
    return ctk.CTkButton(
        parent,
        text=text,
        height=h,
        corner_radius=8,
        fg_color=color,
        hover_color=hover,
        font=ctk.CTkFont("Helvetica", 12, "bold"),
        **kw,
    )


def sep(parent, padx=16, pady=8):
    ctk.CTkFrame(parent, height=1, fg_color="#1e2130").pack(fill="x", padx=padx, pady=pady)


def page_scroll(parent, **kw):
    """Scrollable page area with mouse wheel."""
    return scrollable(parent, **kw)


def enable_scroll(frame: ctk.CTkScrollableFrame):
    enable_mousewheel(frame)
