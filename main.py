#!/usr/bin/env python3
"""
TG Sender Pro — Telegram broadcast & parser tool
Run: python main.py
"""
import sys
import os
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

REQUIRED = (
    ("customtkinter", "customtkinter>=5.2.0"),
    ("telethon", "telethon>=1.36.0"),
    ("PIL", "Pillow>=10.0.0"),
    ("socks", "PySocks>=1.7.1"),
    ("requests", "requests>=2.31.0"),
)


def _check_dependencies():
    missing = [pip_name for mod, pip_name in REQUIRED if not _can_import(mod)]
    if not missing:
        return
    print("Не установлены зависимости Python:\n")
    for pkg in missing:
        print(f"  - {pkg}")
    print("\nУстановите командой:")
    print(f"  pip install -r requirements.txt")
    print("\nили:")
    print(f"  pip install {' '.join(missing)}")
    sys.exit(1)


def _can_import(module_name):
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def _install_excepthook():
    from core.errors import setup_logging, log_exception, humanize_error

    setup_logging()

    def _hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log_exception(exc, "uncaught")
        try:
            from tkinter import messagebox
            messagebox.showerror(
                "Критическая ошибка",
                humanize_error(exc) + "\n\nПодробности в data/app.log",
            )
        except Exception:
            print(humanize_error(exc), file=sys.stderr)
            traceback.print_exception(exc_type, exc, tb)

    sys.excepthook = _hook


if __name__ == "__main__":
    _check_dependencies()
    _install_excepthook()

    from ui.app import App

    try:
        app = App()
        app.mainloop()
    except Exception as exc:
        from core.errors import log_exception, humanize_error
        log_exception(exc, "main")
        print(f"Ошибка запуска: {humanize_error(exc)}", file=sys.stderr)
        sys.exit(1)
