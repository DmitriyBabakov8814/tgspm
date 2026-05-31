"""Run asyncio coroutines in background threads (for Tkinter UI)."""
import asyncio
import threading

from core.errors import humanize_error, log_exception


def run_async(coro, callback=None, on_main=None):
    """Run *coro* in a daemon thread. *on_main(fn)* schedules UI updates on the main thread."""

    def _thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
            if callback and on_main:
                on_main(lambda: callback(result, None))
        except Exception as exc:
            log_exception(exc, "run_async")
            if callback and on_main:
                err = humanize_error(exc)
                on_main(lambda e=err: callback(None, e))
        finally:
            loop.close()

    threading.Thread(target=_thread, daemon=True).start()


def run_async_with_loop(coro, on_done=None):
    """Run *coro* in a thread; *on_done(result, error)* is called when finished."""

    def _thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
            if on_done:
                on_done(result, None)
        except Exception as exc:
            log_exception(exc, "run_async_with_loop")
            if on_done:
                on_done(None, humanize_error(exc))
        finally:
            loop.close()

    threading.Thread(target=_thread, daemon=True).start()


def run_sync_in_thread(func, callback=None, on_main=None):
    """Run blocking *func()* in a daemon thread."""

    def _thread():
        try:
            result = func()
            if callback and on_main:
                on_main(lambda: callback(result, None))
        except Exception as exc:
            log_exception(exc, getattr(func, "__name__", "sync"))
            if callback and on_main:
                on_main(lambda e=humanize_error(exc): callback(None, e))

    threading.Thread(target=_thread, daemon=True).start()
