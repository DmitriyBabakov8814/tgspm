"""Safe execution wrappers for UI event handlers."""
from core.errors import humanize_error, log_exception
from ui.error_ui import show_error


def safe_ui(app, title: str):
    """Decorator: catch exceptions in UI handlers and show a dialog."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                log_exception(exc, func.__name__)
                show_error(app, title, exc)

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator


def run_safe(app, title: str, func, on_success=None):
    """Run *func*; on failure show error dialog."""
    try:
        result = func()
        if on_success:
            on_success(result)
        return result
    except Exception as exc:
        log_exception(exc, func.__name__)
        show_error(app, title, exc)
        return None
