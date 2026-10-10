"""
Tkinter GUI for File2MD.

Design goals:
  - Modern flat look (custom ttk styling, Segoe UI, #2563eb accent)
  - Compact layout, single window
  - Drag-and-drop via tkinterdnd2 (graceful fallback if unavailable)
  - Single worker thread (see queue_manager) — UI never freezes
  - All UI mutations happen on the Tkinter main thread via ``after``
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from .config import APP_NAME, APP_VERSION, ConfigManager, Settings
from .file_manager import discover_files, discover_supported_extensions
from .logger import get_log_dir, get_logger
from .queue_manager import Job, JobStatus, QueueManager
from .utils import truncate_middle


log = get_logger("gui")


# ---------------------------------------------------------------------- #
# Visual constants
# ---------------------------------------------------------------------- #
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_DANGER = "#dc2626"
BG = "#f8fafc"
PANEL_BG = "#ffffff"
BORDER = "#e2e8f0"
TEXT = "#0f172a"
MUTED = "#64748b"
SUCCESS = "#16a34a"
WARNING = "#d97706"
DANGER = "#dc2626"

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_FALLBACK = "TkDefaultFont"


def _resolve_font(size: int, weight: str = "normal") -> tuple:
    return (FONT_FAMILY, size, weight)


# ---------------------------------------------------------------------- #
# Optional drag & drop
# ---------------------------------------------------------------------- #
try:
    import tkinterdnd2  # type: ignore

    HAS_DND = True
    _DnDRoot = tkinterdnd2.Tk  # type: ignore
except Exception:
    HAS_DND = False
    _DnDRoot = tk.Tk


# ---------------------------------------------------------------------- #
# Theme / styling
# ---------------------------------------------------------------------- #
def apply_theme(style: ttk.Style) -> None:
    """Apply a modern flat theme to a ttk.Style."""
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=TEXT, font=_resolve_font(10))
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL_BG)
    style.configure("TLabel", background=BG, foreground=TEXT, font=_resolve_font(10))
    style.configure("Panel.TLabel", background=PANEL_BG, foreground=TEXT, font=_resolve_font(10))
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=_resolve_font(9))
    style.configure("PanelMuted.TLabel", background=PANEL_BG, foreground=MUTED, font=_resolve_font(9))
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=_resolve_font(18, "bold"))
    style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=_resolve_font(10))
    style.configure("Section.TLabel", background=PANEL_BG, foreground=TEXT, font=_resolve_font(10, "bold"))
    style.configure("Status.TLabel", background=PANEL_BG, foreground=TEXT, font=_resolve_font(9))

    # Buttons — flat with accent
    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground="#ffffff",
        font=_resolve_font(10, "bold"),
        borderwidth=0,
        focusradius=0,
        padding=(16, 8),
    )
    style.map(
        "Accent.TButton",
        background=[("active", ACCENT_HOVER), ("disabled", "#94a3b8")],
        foreground=[("disabled", "#e2e8f0")],
    )
    style.configure(
        "TButton",
        background=PANEL_BG,
        foreground=TEXT,
        font=_resolve_font(10),
        borderwidth=1,
        focusradius=0,
        padding=(14, 7),
    )
    style.map(
        "TButton",
        background=[("active", "#f1f5f9"), ("disabled", BG)],
        foreground=[("disabled", MUTED)],
    )
    style.configure(
        "Danger.TButton",
        background=DANGER,
        foreground="#ffffff",
        font=_resolve_font(10),
        borderwidth=0,
        padding=(14, 7),
    )
    style.map("Danger.TButton", background=[("active", "#b91c1c")])

    # Entry
    style.configure(
        "TEntry",
        fieldbackground=PANEL_BG,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=6,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
        darkcolor=[("focus", ACCENT)],
    )

    # Checkbutton
    style.configure("TCheckbutton", background=BG, foreground=TEXT, font=_resolve_font(10))
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure("Panel.TCheckbutton", background=PANEL_BG, foreground=TEXT, font=_resolve_font(10))
    style.map("Panel.TCheckbutton", background=[("active", PANEL_BG)])

    # Progressbar
    style.configure(
        "Accent.Horizontal.TProgressbar",
        background=ACCENT,
        troughcolor="#e2e8f0",
        borderwidth=0,
        thickness=12,
    )

    # Treeview (used as the file queue list)
    style.configure(
        "Treeview",
        background=PANEL_BG,
        fieldbackground=PANEL_BG,
        foreground=TEXT,
        bordercolor=BORDER,
        rowheight=28,
        font=_resolve_font(10),
    )
    style.configure("Treeview.Heading", background="#f1f5f9", foreground=TEXT, font=_resolve_font(9, "bold"))
    style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", TEXT)])


# ---------------------------------------------------------------------- #
# Status -> color
# ---------------------------------------------------------------------- #
STATUS_COLORS = {
    JobStatus.READY: MUTED,
    JobStatus.CONVERTING: ACCENT,
    JobStatus.CONVERTED: SUCCESS,
    JobStatus.FAILED: DANGER,
    JobStatus.SKIPPED: WARNING,
    JobStatus.CANCELLED: MUTED,
}


# ---------------------------------------------------------------------- #
# Main application window
# ---------------------------------------------------------------------- #
class File2MDApp(_DnDRoot):  # type: ignore[misc, valid-type]
    """The main File2MD application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} — Convert documents to Markdown")
        self.geometry(f"{760}x{720}")
        self.minsize(680, 680)
        self.configure(background=BG)

        self._config = ConfigManager()
        self._settings = self._config.load()
        self.geometry(f"{self._settings.window_width}x{self._settings.window_height}")

        self._queue_manager = QueueManager(
            settings=self._settings,
            on_progress=self._on_progress_threadsafe,
            on_job_updated=self._on_job_updated_threadsafe,
            on_batch_complete=self._on_batch_complete_threadsafe,
        )

        self._build_style()
        self._build_menu()
        self._build_layout()

        # Drag and drop registration (if available)
        if HAS_DND:
            self._register_dnd()

        self._update_convert_state()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def _build_style(self) -> None:
        self._style = ttk.Style(self)
        apply_theme(self._style)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self, background=PANEL_BG, foreground=TEXT, borderwidth=0)
        app_menu = tk.Menu(menubar, tearoff=False, background=PANEL_BG, foreground=TEXT)
        app_menu.add_command(label="Settings…", command=self._open_settings)
        app_menu.add_separator()
        app_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=app_menu)

        help_menu = tk.Menu(menubar, tearoff=False, background=PANEL_BG, foreground=TEXT)
        help_menu.add_command(label="About", command=self._open_about)
        help_menu.add_command(label="View Log File", command=self._open_log)
        help_menu.add_command(label="Open MarkItDown Project", command=self._open_markitdown_link)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _build_layout(self) -> None:
        # Root container with padding.
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True, padx=14, pady=10)

        # Header
        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Convert documents to Markdown locally. Powered by Microsoft MarkItDown.",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

        # Drop / select panel
        self._build_drop_panel(root)

        # File queue panel
        self._build_queue_panel(root)

        # Output panel
        self._build_output_panel(root)

        # Progress + actions
        self._build_progress_panel(root)
        self._build_action_bar(root)

    def _build_drop_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame")
        panel.pack(fill="x", pady=(0, 8))

        inner = ttk.Frame(panel, style="Panel.TFrame")
        inner.pack(padx=14, pady=10, fill="x")

        self._drop_label = ttk.Label(
            inner,
            text=(
                "Drop files or folders here\n"
                + ("(or use the buttons below)" if HAS_DND else "(use the buttons below — drag & drop unavailable)")
            ),
            style="Panel.TLabel",
            justify="center",
            font=_resolve_font(10),
        )
        self._drop_label.pack(pady=(2, 6))

        buttons = ttk.Frame(inner, style="Panel.TFrame")
        buttons.pack()
        ttk.Button(
            buttons, text="Select Files", style="Accent.TButton", command=self._on_select_files
        ).pack(side="left", padx=4)
        ttk.Button(
            buttons, text="Select Folder", command=self._on_select_folder
        ).pack(side="left", padx=4)

    def _build_queue_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame")
        panel.pack(fill="both", expand=True, pady=(0, 8))

        header = ttk.Frame(panel, style="Panel.TFrame")
        header.pack(fill="x", padx=10, pady=(6, 2))
        ttk.Label(header, text="Files", style="Section.TLabel").pack(side="left")
        self._count_label = ttk.Label(
            header, text="0 files", style="PanelMuted.TLabel"
        )
        self._count_label.pack(side="right")

        # Treeview as the file list
        tree_frame = ttk.Frame(panel, style="Panel.TFrame")
        tree_frame.pack(fill="both", expand=True, padx=6, pady=(0, 2))

        self._tree = ttk.Treeview(
            tree_frame,
            columns=("status", "path"),
            show="headings",
            selectmode="extended",
            style="Treeview",
        )
        self._tree.heading("status", text="Status")
        self._tree.heading("path", text="File")
        self._tree.column("status", width=110, anchor="w", stretch=False)
        self._tree.column("path", width=520, anchor="w", stretch=True)

        # Tag colors per status
        for status, color in STATUS_COLORS.items():
            self._tree.tag_configure(status.value, foreground=color)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Right-click to remove
        self._tree.bind("<Delete>", lambda _e: self._remove_selected())
        self._tree.bind("<BackSpace>", lambda _e: self._remove_selected())

        # Queue toolbar
        toolbar = ttk.Frame(panel, style="Panel.TFrame")
        toolbar.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Button(toolbar, text="Remove Selected", command=self._remove_selected).pack(side="left")
        ttk.Button(toolbar, text="Clear All", command=self._clear_all).pack(side="left", padx=4)

    def _build_output_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame")
        panel.pack(fill="x", pady=(0, 8))

        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill="x", padx=10, pady=8)

        ttk.Label(row, text="Output folder:", style="Panel.TLabel").pack(side="left")
        self._output_var = tk.StringVar()
        self._output_var.set(str(self._settings.resolve_output_dir()))
        entry = ttk.Entry(row, textvariable=self._output_var)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row, text="Browse", command=self._on_browse_output).pack(side="left")

    def _build_progress_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame")
        panel.pack(fill="x", pady=(0, 8))

        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill="x", padx=10, pady=(8, 2))

        self._progress_label = ttk.Label(row, text="Progress: 0 / 0", style="Panel.TLabel")
        self._progress_label.pack(side="left")

        self._current_file_label = ttk.Label(
            row, text="", style="PanelMuted.TLabel"
        )
        self._current_file_label.pack(side="right")

        self._progress = ttk.Progressbar(
            panel, style="Accent.Horizontal.TProgressbar", mode="determinate"
        )
        self._progress.pack(fill="x", padx=10, pady=(0, 8))

    def _build_action_bar(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(2, 0))

        self._cancel_btn = ttk.Button(
            bar, text="Cancel", command=self._on_cancel, state="disabled"
        )
        self._cancel_btn.pack(side="left")

        self._convert_btn = ttk.Button(
            bar, text="Convert", style="Accent.TButton", command=self._on_convert
        )
        self._convert_btn.pack(side="right")

    # ------------------------------------------------------------------ #
    # Drag & drop
    # ------------------------------------------------------------------ #
    def _register_dnd(self) -> None:
        # Register the whole window so drops anywhere are accepted.
        try:
            self.drop_target_register("DND_Files")  # type: ignore[attr-defined]
            self.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
            self.dnd_bind("<<DropEnter>>", self._on_drop_enter)  # type: ignore[attr-defined]
            self.dnd_bind("<<DropLeave>>", self._on_drop_leave)  # type: ignore[attr-defined]
        except Exception:
            log.warning("Drag-and-drop registration failed", exc_info=True)

    def _on_drop(self, event):  # type: ignore[no-untyped-def]
        paths = self._parse_dropped(event.data)
        if not paths:
            return
        folders = [p for p in paths if p.is_dir()]
        files = [p for p in paths if p.is_file()]
        for folder in folders:
            self._add_files_from_folder(folder, recursive=self._settings.include_subfolders)
        if files:
            self._add_files(files)
        self._update_convert_state()

    def _on_drop_enter(self, event):  # type: ignore[no-untyped-def]
        try:
            self._drop_label.configure(foreground=ACCENT)
        except Exception:
            pass

    def _on_drop_leave(self, event):  # type: ignore[no-untyped-def]
        try:
            self._drop_label.configure(foreground=TEXT)
        except Exception:
            pass

    @staticmethod
    def _parse_dropped(data: str) -> list[Path]:
        """Parse the DnD payload into a list of Paths.

        tkinterdnd2 returns paths in a curly-braced or quoted format on
        Windows. We split carefully to support multiple selections and
        Unicode filenames.
        """
        if not data:
            return []
        # Each path may be wrapped in {…} or "…". Split accordingly.
        paths: list[Path] = []
        i = 0
        n = len(data)
        while i < n:
            while i < n and data[i] in (" ", "\n", "\t"):
                i += 1
            if i >= n:
                break
            if data[i] == "{":
                end = data.find("}", i + 1)
                if end == -1:
                    break
                paths.append(Path(data[i + 1 : end]))
                i = end + 1
            elif data[i] == '"':
                end = data.find('"', i + 1)
                if end == -1:
                    break
                paths.append(Path(data[i + 1 : end]))
                i = end + 1
            else:
                # Bare path — read until whitespace.
                end = i
                while end < n and data[end] not in (" ", "\n", "\t"):
                    end += 1
                paths.append(Path(data[i:end]))
                i = end
        return paths

    # ------------------------------------------------------------------ #
    # File selection
    # ------------------------------------------------------------------ #
    def _on_select_files(self) -> None:
        exts = discover_supported_extensions()
        filetypes = [("Supported documents", " ".join(f"*{e}" for e in sorted(exts)))]
        filetypes.append(("All files", "*.*"))
        initial = self._settings.last_input_dir or str(Path.home())
        paths = filedialog.askopenfilenames(
            parent=self, title="Select files to convert", filetypes=filetypes,
            initialdir=initial,
        )
        if not paths:
            return
        self._add_files([Path(p) for p in paths])
        self._settings.last_input_dir = str(Path(paths[0]).parent)
        self._save_settings()
        self._update_convert_state()

    def _on_select_folder(self) -> None:
        initial = self._settings.last_input_dir or str(Path.home())
        folder = filedialog.askdirectory(
            parent=self, title="Select a folder to convert", initialdir=initial
        )
        if not folder:
            return
        self._add_files_from_folder(Path(folder), recursive=self._settings.include_subfolders)
        self._settings.last_input_dir = folder
        self._save_settings()
        self._update_convert_state()

    def _add_files_from_folder(self, folder: Path, *, recursive: bool) -> None:
        files = discover_files(folder, recursive=recursive)
        if not files:
            messagebox.showinfo(
                APP_NAME,
                f"No supported files were found in:\n{folder}",
                parent=self,
            )
            return
        self._add_files(files, input_root=folder)

    def _add_files(self, files: list[Path], *, input_root: Optional[Path] = None) -> None:
        added = 0
        for f in files:
            job = Job(input_path=f, input_root=input_root)
            if self._queue_manager.enqueue(job):
                self._insert_job_row(job)
                added += 1
        if added:
            self._refresh_count()

    # ------------------------------------------------------------------ #
    # Queue manipulation
    # ------------------------------------------------------------------ #
    def _insert_job_row(self, job: Job) -> None:
        self._tree.insert(
            "",
            "end",
            iid=str(id(job)),
            values=(job.status.value, str(job.input_path)),
            tags=(job.status.value,),
        )

    def _refresh_job_row(self, job: Job) -> None:
        iid = str(id(job))
        try:
            self._tree.item(
                iid,
                values=(job.status.value, str(job.input_path)),
                tags=(job.status.value,),
            )
        except tk.TclError:
            # Row was removed — ignore.
            pass

    def _remove_selected(self) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        for iid in selection:
            for job in self._queue_manager.jobs:
                if str(id(job)) == iid:
                    if self._queue_manager.remove_job(job):
                        try:
                            self._tree.delete(iid)
                        except tk.TclError:
                            pass
                    break
        self._refresh_count()
        self._update_convert_state()

    def _clear_all(self) -> None:
        if not self._queue_manager.jobs:
            return
        if not messagebox.askyesno(
            APP_NAME, "Remove all files from the queue?", parent=self
        ):
            return
        self._queue_manager.clear_all()
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._refresh_count()
        self._update_convert_state()

    def _refresh_count(self) -> None:
        n = len(self._queue_manager.jobs)
        self._count_label.configure(text=f"{n} file" + ("" if n == 1 else "s"))

    # ------------------------------------------------------------------ #
    # Output folder
    # ------------------------------------------------------------------ #
    def _on_browse_output(self) -> None:
        current = self._output_var.get() or str(Path.home())
        folder = filedialog.askdirectory(
            parent=self, title="Select output folder", initialdir=current
        )
        if folder:
            self._output_var.set(folder)
            self._settings.output_directory = folder
            self._save_settings()

    # ------------------------------------------------------------------ #
    # Convert / cancel
    # ------------------------------------------------------------------ #
    def _on_convert(self) -> None:
        # Apply current UI settings to the manager.
        self._apply_output_setting()
        ready = [j for j in self._queue_manager.jobs if j.status == JobStatus.READY]
        if not ready:
            messagebox.showinfo(APP_NAME, "No files to convert.", parent=self)
            return

        # Reset progress UI.
        self._progress["maximum"] = len(ready)
        self._progress["value"] = 0
        self._progress_label.configure(text=f"Progress: 0 / {len(ready)}")
        self._convert_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")

        self._queue_manager.update_settings(self._settings)
        if not self._queue_manager.start():
            self._convert_btn.configure(state="normal")
            self._cancel_btn.configure(state="disabled")

    def _on_cancel(self) -> None:
        self._queue_manager.cancel_pending()
        self._cancel_btn.configure(state="disabled")

    def _apply_output_setting(self) -> None:
        out = self._output_var.get().strip()
        if out:
            self._settings.output_directory = out
        # Make sure the manager uses the freshest settings.
        self._queue_manager.update_settings(self._settings)
        self._save_settings()

    def _update_convert_state(self) -> None:
        has_ready = any(j.status == JobStatus.READY for j in self._queue_manager.jobs)
        if self._queue_manager.is_running:
            self._convert_btn.configure(state="disabled")
            self._cancel_btn.configure(state="normal")
        else:
            self._convert_btn.configure(state="normal" if has_ready else "disabled")
            self._cancel_btn.configure(state="disabled")

    # ------------------------------------------------------------------ #
    # Threadsafe callbacks (worker -> UI thread)
    # ------------------------------------------------------------------ #
    def _on_progress_threadsafe(self, done: int, total: int, current_name: str) -> None:
        self.after(0, lambda: self._on_progress(done, total, current_name))

    def _on_job_updated_threadsafe(self, job: Job) -> None:
        self.after(0, lambda: self._on_job_updated(job))

    def _on_batch_complete_threadsafe(self, summary) -> None:  # type: ignore[no-untyped-def]
        self.after(0, lambda: self._on_batch_complete(summary))

    def _on_progress(self, done: int, total: int, current_name: str) -> None:
        self._progress["maximum"] = total if total else 1
        self._progress["value"] = done
        self._progress_label.configure(text=f"Progress: {done} / {total}")
        if current_name:
            self._current_file_label.configure(text=truncate_middle(current_name, 50))
        else:
            self._current_file_label.configure(text="")

    def _on_job_updated(self, job: Job) -> None:
        self._refresh_job_row(job)
        self._update_convert_state()

    def _on_batch_complete(self, summary) -> None:  # type: ignore[no-untyped-def]
        self._convert_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._current_file_label.configure(text="")
        msg = (
            f"Completed: {summary.converted}\n"
            f"Failed: {summary.failed}\n"
            f"Skipped: {summary.skipped}\n"
            f"Cancelled: {summary.cancelled}"
        )
        if summary.failed:
            details = "\n".join(
                f"• {name}: {truncate_middle(reason, 80)}"
                for name, reason in summary.failures[:8]
            )
            if len(summary.failures) > 8:
                details += f"\n… and {len(summary.failures) - 8} more (see log)"
            msg += "\n\nFailed files:\n" + details
        messagebox.showinfo(APP_NAME, msg, parent=self)
        self._progress["value"] = 0
        self._progress_label.configure(text="Progress: 0 / 0")

    # ------------------------------------------------------------------ #
    # Settings, About, Log
    # ------------------------------------------------------------------ #
    def _open_settings(self) -> None:
        dialog = SettingsDialog(self, self._settings)
        self.wait_window(dialog)
        if dialog.result:
            self._settings = dialog.result
            self._queue_manager.update_settings(self._settings)
            self._output_var.set(str(self._settings.resolve_output_dir()))
            self._save_settings()

    def _open_about(self) -> None:
        AboutDialog(self)

    def _open_log(self) -> None:
        log_path = get_log_dir() / "file2md.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            if not log_path.exists():
                log_path.write_text("", encoding="utf-8")
        except OSError:
            pass
        self._open_path_in_os(log_path)

    def _open_markitdown_link(self) -> None:
        try:
            webbrowser.open("https://github.com/microsoft/markitdown")
        except Exception:
            log.exception("Could not open browser")

    def _open_path_in_os(self, path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception:
            log.exception("Could not open path: %s", path)

    # ------------------------------------------------------------------ #
    # Persistence & shutdown
    # ------------------------------------------------------------------ #
    def _save_settings(self) -> None:
        try:
            self._settings.window_width = self.winfo_width()
            self._settings.window_height = self.winfo_height()
        except tk.TclError:
            pass
        self._config.save(self._settings)

    def _on_close(self) -> None:
        if self._queue_manager.is_running:
            if not messagebox.askyesno(
                APP_NAME,
                "Conversion is still running. Cancel and quit?",
                parent=self,
            ):
                return
            self._queue_manager.cancel_pending()
            self._queue_manager.wait_until_idle(timeout=2.0)
        self._save_settings()
        self.destroy()


# ---------------------------------------------------------------------- #
# Settings dialog
# ---------------------------------------------------------------------- #
class SettingsDialog(tk.Toplevel):
    """A small modal dialog for editing persistent settings."""

    def __init__(self, parent: tk.Misc, settings: Settings) -> None:
        super().__init__(parent)
        self.title("File2MD Settings")
        self.configure(background=BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._settings = Settings(**settings.to_dict())
        self.result: Optional[Settings] = None

        frame = ttk.Frame(self)
        frame.pack(padx=20, pady=16, fill="both", expand=True)

        ttk.Label(frame, text="Output directory", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        out_var = tk.StringVar(value=self._settings.output_directory)
        ttk.Entry(frame, textvariable=out_var, width=44).grid(
            row=1, column=0, sticky="ew", pady=(0, 12)
        )

        inc_sub_var = tk.BooleanVar(value=self._settings.include_subfolders)
        ttk.Checkbutton(
            frame, text="Include subfolders when selecting a folder",
            variable=inc_sub_var,
        ).grid(row=2, column=0, sticky="w", pady=2)

        preserve_var = tk.BooleanVar(value=self._settings.preserve_structure)
        ttk.Checkbutton(
            frame, text="Preserve folder structure in output",
            variable=preserve_var,
        ).grid(row=3, column=0, sticky="w", pady=2)

        overwrite_var = tk.BooleanVar(value=self._settings.overwrite_existing)
        ttk.Checkbutton(
            frame, text="Overwrite existing Markdown files",
            variable=overwrite_var,
        ).grid(row=4, column=0, sticky="w", pady=2)

        unique_var = tk.BooleanVar(value=self._settings.create_unique_filenames)
        ttk.Checkbutton(
            frame, text="Create unique filenames (report (1).md, …) when not overwriting",
            variable=unique_var,
        ).grid(row=5, column=0, sticky="w", pady=2)

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self._on_cancel).pack(side="left", padx=4)
        ttk.Button(
            buttons, text="Save", style="Accent.TButton", command=self._on_save
        ).pack(side="left", padx=4)

        self._out_var = out_var
        self._inc_sub_var = inc_sub_var
        self._preserve_var = preserve_var
        self._overwrite_var = overwrite_var
        self._unique_var = unique_var

        self.update_idletasks()
        self.geometry(
            f"+{parent.winfo_rootx() + 80}+{parent.winfo_rooty() + 80}"
        )

    def _on_save(self) -> None:
        self._settings.output_directory = self._out_var.get().strip()
        self._settings.include_subfolders = self._inc_sub_var.get()
        self._settings.preserve_structure = self._preserve_var.get()
        self._settings.overwrite_existing = self._overwrite_var.get()
        self._settings.create_unique_filenames = self._unique_var.get()
        self.result = self._settings
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


# ---------------------------------------------------------------------- #
# About dialog
# ---------------------------------------------------------------------- #
class AboutDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title(f"About {APP_NAME}")
        self.configure(background=BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self)
        frame.pack(padx=28, pady=22)

        ttk.Label(frame, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Lightweight local document-to-Markdown converter.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 12))

        info = (
            f"Version: {APP_VERSION}\n"
            "Engine: Microsoft MarkItDown\n\n"
            "File2MD processes your files locally on your computer.\n"
            "Your documents are not uploaded to a server."
        )
        ttk.Label(frame, text=info, style="Muted.TLabel", justify="left").pack(anchor="w")

        link = ttk.Label(
            frame,
            text="github.com/microsoft/markitdown",
            style="Muted.TLabel",
            foreground=ACCENT,
            cursor="hand2",
        )
        link.pack(anchor="w", pady=(12, 0))
        link.bind("<Button-1>", lambda _e: webbrowser.open("https://github.com/microsoft/markitdown"))

        ttk.Button(
            frame, text="Close", style="Accent.TButton", command=self.destroy
        ).pack(anchor="e", pady=(16, 0))

        self.update_idletasks()
        self.geometry(
            f"+{parent.winfo_rootx() + 80}+{parent.winfo_rooty() + 80}"
        )


# ---------------------------------------------------------------------- #
# Entry point
# ---------------------------------------------------------------------- #
def launch() -> int:
    """Construct the app, run the Tk mainloop, return exit code."""
    try:
        app = File2MDApp()
    except Exception:
        log.exception("Failed to start File2MD GUI")
        raise
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()
    return 0
