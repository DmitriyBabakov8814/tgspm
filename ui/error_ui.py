"""UI helpers for displaying errors to the user."""
from tkinter import messagebox

from core.errors import TGSenderError, humanize_error, log_exception


def show_error(parent, title: str, exc: BaseException) -> None:
    log_exception(exc, title)
    messagebox.showerror(title, humanize_error(exc), parent=parent)


def show_warning(parent, title: str, message: str) -> None:
    messagebox.showwarning(title, message, parent=parent)


def show_info(parent, title: str, message: str) -> None:
    messagebox.showinfo(title, message, parent=parent)


def format_callback_error(err) -> str:
    """Normalize error passed to async callbacks (str or Exception)."""
    if err is None:
        return ""
    if isinstance(err, BaseException):
        return humanize_error(err)
    return humanize_error(Exception(str(err)))


def guard_ui(parent, title: str = "Ошибка"):
    """Decorator for UI event handlers — catches and shows errors."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except TGSenderError as exc:
                show_error(parent, title, exc)
            except Exception as exc:
                show_error(parent, title, exc)

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator
