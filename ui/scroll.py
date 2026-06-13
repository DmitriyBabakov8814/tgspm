"""Mouse-wheel scrolling for CustomTkinter scroll areas (browser-like)."""
import customtkinter as ctk


def _canvas_of(scroll: ctk.CTkScrollableFrame):
    return scroll._parent_canvas


def _scroll_units(scroll: ctk.CTkScrollableFrame, delta: int):
    canvas = _canvas_of(scroll)
    steps = int(-delta / 120) if delta else 0
    if steps:
        canvas.yview_scroll(steps, "units")


def _bind_wheel_recursive(widget, scroll: ctk.CTkScrollableFrame):
    def on_wheel(event):
        if event.delta:
            _scroll_units(scroll, event.delta)
        elif getattr(event, "num", None) == 4:
            _scroll_units(scroll, 120)
        elif getattr(event, "num", None) == 5:
            _scroll_units(scroll, -120)
        return "break"

    try:
        widget.bind("<MouseWheel>", on_wheel, add="+")
        widget.bind("<Button-4>", on_wheel, add="+")
        widget.bind("<Button-5>", on_wheel, add="+")
    except Exception:
        pass
    for child in widget.winfo_children():
        _bind_wheel_recursive(child, scroll)


def enable_mousewheel(scroll: ctk.CTkScrollableFrame):
    """Bind wheel events on the scroll frame and all nested widgets."""
    _bind_wheel_recursive(scroll, scroll)

    def _rebind(_event=None):
        _bind_wheel_recursive(scroll, scroll)

    scroll.bind("<Map>", _rebind, add="+")
    scroll.bind("<Configure>", _rebind, add="+")


def scrollable(parent, **kw) -> ctk.CTkScrollableFrame:
    """Create a CTkScrollableFrame with browser-like mouse wheel support."""
    defaults = {
        "fg_color": "transparent",
        "scrollbar_button_color": "#2a2f45",
        "scrollbar_button_hover_color": "#3a4055",
    }
    defaults.update(kw)
    frame = ctk.CTkScrollableFrame(parent, **defaults)
    enable_mousewheel(frame)
    return frame
