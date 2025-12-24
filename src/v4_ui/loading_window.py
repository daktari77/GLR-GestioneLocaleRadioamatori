# -*- coding: utf-8 -*-
"""Brandable splash/loading window with live log feed."""

from __future__ import annotations

import logging
import time
import tkinter as tk
from collections import deque
from queue import Empty, Queue


class LoadingWindow:
    """Simple splash window showing app metadata during startup."""

    def __init__(
        self,
        *,
        app_name: str,
        version: str,
        author: str,
        message: str | None = None,
        min_duration: float = 1.5,
        activity_logger: logging.Logger | None = None,
        max_log_lines: int = 6,
    ):
        self._app_name = app_name
        self._version = version
        self._author = author
        self._min_duration = max(0.0, float(min_duration))
        self._shown_at: float | None = None
        self._root = tk.Tk()
        self._status_var = tk.StringVar(master=self._root, value=message or "Avvio in corso...")
        self._log_lines = deque(maxlen=max(1, int(max_log_lines)))
        self._log_queue: Queue[str] = Queue()
        self._log_handler: logging.Handler | None = None
        self._attached_logger = activity_logger
        self._after_id: str | None = None
        self._configure_root()
        self._build_contents()
        self._attach_logger(activity_logger)
        self._schedule_log_pump()

    def _configure_root(self):
        root = self._root
        if root is None:
            return

        root.withdraw()
        root.title(self._app_name)
        root.overrideredirect(True)
        root.configure(bg="#040711")
        root.attributes("-topmost", True)
        width, height = 540, 260
        root.update_idletasks()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        pos_x = (screen_w - width) // 2
        pos_y = (screen_h - height) // 3
        root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def _build_contents(self):
        outer = tk.Frame(self._root, bg="#0f1b2c", bd=0, relief=tk.FLAT)
        outer.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        hero = tk.Frame(outer, bg="#0f1b2c")
        hero.pack(fill=tk.X, padx=24, pady=(24, 8))

        tk.Label(
            hero,
            text=self._app_name,
            fg="#f4f9ff",
            bg="#0f1b2c",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")

        tk.Label(
            hero,
            text="Il gestionale Soci di Sezione",
            fg="#d6e5ff",
            bg="#0f1b2c",
            font=("Segoe UI", 13),
        ).pack(anchor="w", pady=(2, 10))

        meta = tk.Frame(hero, bg="#0f1b2c")
        meta.pack(anchor="w", pady=(4, 0))
        tk.Label(
            meta,
            text=f"Autore: {self._author}",
            fg="#a7bff1",
            bg="#0f1b2c",
            font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, padx=(0, 18))
        tk.Label(
            meta,
            text=f"Revisione: {self._version}",
            fg="#a7bff1",
            bg="#0f1b2c",
            font=("Segoe UI", 10),
        ).pack(side=tk.LEFT)

        status_frame = tk.Frame(outer, bg="#111b2c")
        status_frame.pack(fill=tk.X, padx=20, pady=(0, 12))
        tk.Label(
            status_frame,
            textvariable=self._status_var,
            fg="#fefefe",
            bg="#111b2c",
            font=("Segoe UI", 11),
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=10)

        log_container = tk.Frame(outer, bg="#050a13", bd=1, relief=tk.SOLID)
        log_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        tk.Label(
            log_container,
            text="Log di avvio",
            fg="#7fa7ff",
            bg="#050a13",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=10, pady=(6, 0))

        self._log_box = tk.Text(
            log_container,
            height=4,
            bg="#050a13",
            fg="#d8e4ff",
            insertbackground="#d8e4ff",
            relief=tk.FLAT,
            font=("Cascadia Code", 9),
            state=tk.DISABLED,
            wrap=tk.NONE,
        )
        self._log_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))

    def show(self):
        """Display the window and process pending draw events."""
        if self._root is None:
            return
        self._root.deiconify()
        self._root.update_idletasks()
        self._root.update()
        self._shown_at = time.perf_counter()

    def set_status(self, text: str):
        """Update the status message shown to the user."""
        if self._root is None:
            return
        self._status_var.set(text or "")
        self._root.update_idletasks()
        self._root.update()

    def close(self):
        """Destroy the splash window."""
        if self._root is None:
            return
        if self._shown_at is not None:
            elapsed = time.perf_counter() - self._shown_at
            remaining = self._min_duration - elapsed
            if remaining > 0:
                time.sleep(remaining)
        try:
            self._cancel_log_pump()
            if self._attached_logger and self._log_handler:
                self._attached_logger.removeHandler(self._log_handler)
            self._root.destroy()
        except tk.TclError:
            pass
        finally:
            self._root = None
            self._log_handler = None

    def _attach_logger(self, logger_obj: logging.Logger | None):
        if logger_obj is None:
            return

        class _QueueHandler(logging.Handler):
            def __init__(self, sink):
                super().__init__()
                self._sink = sink

            def emit(self, record):
                try:
                    msg = self.format(record)
                except Exception:
                    msg = record.getMessage()
                self._sink(msg)

        handler = _QueueHandler(self._log_queue.put)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger_obj.addHandler(handler)
        self._log_handler = handler

    def _schedule_log_pump(self):
        if self._root is None:
            return
        try:
            self._after_id = self._root.after(200, self._drain_log_queue)
        except tk.TclError:
            pass

    def _cancel_log_pump(self):
        if self._root is None or self._after_id is None:
            return
        try:
            self._root.after_cancel(self._after_id)
        except tk.TclError:
            pass
        finally:
            self._after_id = None

    def _drain_log_queue(self):
        if self._root is None:
            return
        self._after_id = None
        updated = False
        while True:
            try:
                line = self._log_queue.get_nowait()
            except Empty:
                break
            else:
                updated = True
                self._log_lines.append(line)
        if updated:
            self._render_log_lines()
        self._schedule_log_pump()

    def _render_log_lines(self):
        if self._root is None:
            return
        try:
            self._log_box.configure(state=tk.NORMAL)
            self._log_box.delete("1.0", tk.END)
            self._log_box.insert(tk.END, "\n".join(self._log_lines))
            self._log_box.see(tk.END)
            self._log_box.configure(state=tk.DISABLED)
        except tk.TclError:
            pass


__all__ = ["LoadingWindow"]
