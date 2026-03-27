import os
import webbrowser
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
from core.tasks import TaskManager
from core.storage import save_tasks, load_tasks, save_config, load_config
from datetime import datetime
from tkcalendar import Calendar
from core import logic
from services import export as export_module
from services import importer as import_module
from services import share as share_module
from services.reminders import ReminderService, PLYER_AVAILABLE as REMINDERS_AVAILABLE, DEFAULT_CONFIG as REMINDER_DEFAULTS
from core import categories as cat_module
from core.categories import auto_fg
from core.commands import (
    CommandHistory, AddTaskCommand, DeleteTaskCommand,
    EditTaskCommand, MarkDoneCommand, ToggleDoneCommand, snapshot
)

# pystray — optional system tray support
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

PRIORITY_ICONS = {"High": "🔥 High", "Medium": "⚡ Medium", "Low": "🌿 Low"}

# ---------- Theme Constants ----------
LIGHT_THEME = {
    "bg":               "#FAF7F2",   # warm parchment
    "fg":               "#1C1917",   # near-black text
    "muted_fg":         "#78716C",   # secondary text
    "accent":           "#C2622D",   # terracotta
    "accent_hover":     "#A85226",
    "accent_fg":        "#FFFFFF",
    "surface":          "#F2EDE6",   # toolbar / footer surface
    "surface2":         "#FFFFFF",   # list row background
    "border":           "#E0D9CF",
    "list_fg":          "#1C1917",
    "heading_fg":       "#78716C",
    "secondary_btn_bg": "#EDE8E1",
    "secondary_btn_fg": "#1C1917",
    "entry_bg":         "#FFFFFF",
}

DARK_THEME = {
    "bg":               "#13151A",   # deep midnight
    "fg":               "#EDE9E3",   # warm off-white
    "muted_fg":         "#8A8E99",
    "accent":           "#E07A47",   # warm orange
    "accent_hover":     "#C86832",
    "accent_fg":        "#FFFFFF",
    "surface":          "#1C1F26",   # lifted surface
    "surface2":         "#22262F",   # toolbar / footer
    "border":           "#2E3340",
    "list_fg":          "#EDE9E3",
    "heading_fg":       "#8A8E99",
    "secondary_btn_bg": "#22262F",
    "secondary_btn_fg": "#EDE9E3",
    "entry_bg":         "#22262F",
}


class TodoApp:
    def __init__(self, root, username: str = ""):
        self.root     = root
        self.username = username   # display name of logged-in user
        self.root.title(f"My Tasks — {username}" if username else "My Tasks")
        self.root.minsize(720, 480)
        config = load_config(username)
        self.root.geometry(config.get("geometry", "900x620"))
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self._tray_icon = None

        # Task manager
        self.manager = TaskManager()
        load_tasks(self.manager, username)

        # State
        config = load_config(username)
        self.dark_mode = config.get("dark_mode", False)
        self.minimize_to_tray = config.get("minimize_to_tray", True)
        self.sort_type = tk.StringVar(value=config.get("sort", "due_date"))
        self.sort_reverse = False          # ascending by default
        self.filter_type = tk.StringVar(value=config.get("filter", "All"))
        self._calendar_date_filter = None  # set when user clicks a calendar day
        self.categories      = cat_module.load_categories(config)
        self.category_colors = cat_module.load_category_colors(config)
        self._category_filter = None       # None = show all categories
        self.history = CommandHistory()
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh_tasks())

        # Reminder config
        self.reminder_cfg = {**REMINDER_DEFAULTS, **config.get("reminders", {})}

        self._build_ui()
        # ── Keyboard shortcuts ──────────────────────────
        kb = self.root.bind_all
        # Task actions
        kb("<Control-n>",        lambda e: self.add_task_gui())
        kb("<Control-e>",        lambda e: self.edit_task_gui())
        kb("<Delete>",           lambda e: self._shortcut_delete())
        kb("<Control-d>",        lambda e: self.mark_done_gui())
        # Undo / Redo
        kb("<Control-z>",        lambda e: self.undo_action())
        kb("<Control-y>",        lambda e: self.redo_action())
        kb("<Control-Z>",        lambda e: self.redo_action())   # Ctrl+Shift+Z
        # Navigation
        kb("<Control-f>",        lambda e: self._focus_search())
        kb("<Escape>",           lambda e: self._shortcut_escape())
        kb("<Control-Home>",     lambda e: self._select_first_task())
        kb("<Control-End>",      lambda e: self._select_last_task())
        # View
        kb("<Control-t>",        lambda e: self.toggle_theme())
        kb("<Control-comma>",    lambda e: self.open_settings_gui())
        # Help
        kb("<question>",         lambda e: self._show_shortcuts_help())
        self.apply_theme()
        self.refresh_tasks()
        self.auto_save()
        self.root.after(100, self._bind_cal_day_tooltips)
        self.root.after(300, self._start_tray)
        self.root.after(500, self._start_reminders)

    # ═══════════════════════════════════════════════
    #  UI BUILD
    # ═══════════════════════════════════════════════

    def _build_ui(self):
        # ── Header ──────────────────────────────────
        self.header_frame = tk.Frame(self.root)
        self.header_frame.pack(fill=tk.X, padx=18, pady=(14, 10))

        title_block = tk.Frame(self.header_frame)
        title_block.pack(side=tk.LEFT)
        self.title_label = tk.Label(
            title_block, text="My Tasks",
            font=("Georgia", 22, "bold")
        )
        self.title_label.pack(anchor="w")
        self.count_label = tk.Label(
            title_block, text="",
            font=("TkDefaultFont", 10)
        )
        self.count_label.pack(anchor="w")

        self.add_btn = tk.Button(
            self.header_frame, text="＋  Add Task",
            command=self.add_task_gui,
            font=("TkDefaultFont", 11, "bold"),
            relief="flat", cursor="hand2",
            padx=16, pady=8
        )
        self.add_btn.pack(side=tk.RIGHT, padx=(0, 2))

        # ── Header separator ────────────────────────
        self.sep1 = tk.Frame(self.root, height=1)
        self.sep1.pack(fill=tk.X)

        # ── Toolbar ─────────────────────────────────
        self.toolbar = tk.Frame(self.root)
        self.toolbar.pack(fill=tk.X)

        self.toolbar_inner = tk.Frame(self.toolbar)
        self.toolbar_inner.pack(fill=tk.X, padx=14, pady=8)

        # ── Single row: FILTER on left, SORT on right ────
        self.filter_row = self.toolbar_inner
        self.sort_row   = self.toolbar_inner

        # Left side — FILTER label + search + filter tabs
        self.filter_heading = tk.Label(
            self.toolbar_inner, text="FILTER",
            font=("TkDefaultFont", 8, "bold")
        )
        self.filter_heading.pack(side=tk.LEFT, padx=(0, 8))

        self.search_entry = tk.Entry(
            self.toolbar_inner,
            textvariable=self.search_var,
            width=18, relief="flat",
            font=("TkDefaultFont", 11)
        )
        self.search_entry.pack(side=tk.LEFT, ipady=5, padx=(0, 8))

        self.filter_buttons = {}
        for label in ["All", "Active", "Completed", "Overdue"]:
            btn = tk.Button(
                self.toolbar_inner, text=label,
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 10, "bold"),
                padx=10, pady=5,
                command=lambda v=label: self._set_filter(v)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.filter_buttons[label] = btn

        # Right side — SORT tabs then SORT label (packed right-to-left)
        sort_options = [
            ("due_date",      "Due Date"),
            ("priority",      "Priority"),
            ("alphabetical",  "A – Z"),
            ("creation_date", "Created"),
        ]
        self.sort_buttons = {}
        for value, label in reversed(sort_options):
            btn = tk.Button(
                self.toolbar_inner, text=label,
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 10, "bold"),
                padx=10, pady=5,
                command=lambda v=value: self._set_sort(v)
            )
            btn.pack(side=tk.RIGHT, padx=2)
            self.sort_buttons[value] = btn

        self.sort_heading = tk.Label(
            self.toolbar_inner, text="SORT",
            font=("TkDefaultFont", 8, "bold")
        )
        self.sort_heading.pack(side=tk.RIGHT, padx=(0, 8))

        # vertical separator between filter and sort groups
        self.toolbar_divider = tk.Frame(self.toolbar_inner, width=1)
        self.toolbar_divider.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=4)

        # ── Toolbar separator ────────────────────────
        self.sep2 = tk.Frame(self.root, height=1)
        self.sep2.pack(fill=tk.X)

        # ── Footer separator + footer are packed BEFORE the treeview ──
        # This ensures pack(expand=True) on the tree only fills the space
        # that remains after the footer is already reserved at the bottom.

        # ── Footer separator ─────────────────────────
        self.sep3 = tk.Frame(self.root, height=1)
        self.sep3.pack(side=tk.BOTTOM, fill=tk.X)

        # ── Footer ───────────────────────────────────
        self.footer_frame = tk.Frame(self.root)
        self.footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=8)

        # Secondary action buttons (left)
        self.action_frame = tk.Frame(self.footer_frame)
        self.action_frame.pack(side=tk.LEFT)

        # Undo / Redo buttons
        self.undo_btn = tk.Button(
            self.action_frame, text="↩  Undo",
            command=self.undo_action,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.undo_btn.pack(side=tk.LEFT, padx=(0, 3))

        self.redo_btn = tk.Button(
            self.action_frame, text="↪  Redo",
            command=self.redo_action,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.redo_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Divider between undo/redo and task actions
        self.undo_divider = tk.Frame(self.action_frame, width=1)
        self.undo_divider.pack(side=tk.LEFT, fill=tk.Y, pady=4, padx=(0, 10))

        self.action_buttons = []
        for label, cmd in [
            ("✎  Edit",       self.edit_task_gui),
            ("✕  Delete",     self.delete_task_gui),
            ("✔  Mark Done",  self.mark_done_gui),
        ]:
            btn = tk.Button(
                self.action_frame, text=label, command=cmd,
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 10),
                padx=11, pady=5
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.action_buttons.append(btn)

        # Right side: save indicator + theme toggle
        self.right_frame = tk.Frame(self.footer_frame)
        self.right_frame.pack(side=tk.RIGHT)

        self.save_dot = tk.Label(
            self.right_frame, text="●",
            font=("TkDefaultFont", 10),
            fg="#4ADE80"   # always green — dot colour doesn't change with theme
        )
        self.save_dot.pack(side=tk.LEFT, padx=(0, 4))

        self.save_label = tk.Label(
            self.right_frame, text="Auto-save on",
            font=("TkDefaultFont", 10)
        )
        self.save_label.pack(side=tk.LEFT, padx=(0, 14))

        self.help_btn = tk.Button(
            self.right_frame, text="?",
            command=self._show_shortcuts_help,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10, "bold"),
            width=2, padx=6, pady=5
        )
        self.help_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.import_btn = tk.Button(
            self.right_frame, text="⬇  Import",
            command=self.open_import_gui,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.import_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.export_btn = tk.Button(
            self.right_frame, text="⬆  Export",
            command=self.open_export_gui,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.export_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.settings_btn = tk.Button(
            self.right_frame, text="⚙  Settings",
            command=self.open_settings_gui,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.settings_btn.pack(side=tk.LEFT)

        # ── Main content: sidebar + task list side by side ──
        self.content_frame = tk.Frame(self.root)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # ── Sidebar ──────────────────────────────────
        self.sidebar = tk.Frame(self.content_frame, width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0), pady=10)
        self.sidebar.pack_propagate(False)

        # Scrollable canvas inside sidebar
        _sb_canvas = self._sb_canvas = tk.Canvas(self.sidebar, width=218, highlightthickness=0, bd=0)
        _sb_scroll  = ttk.Scrollbar(self.sidebar, orient="vertical", command=_sb_canvas.yview, style="Flat.Vertical.TScrollbar")
        _sb_canvas.configure(yscrollcommand=_sb_scroll.set)
        _sb_scroll.pack(side=tk.LEFT, fill=tk.Y)
        _sb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame — all sidebar widgets go here
        _sb_inner = self._sb_inner = tk.Frame(_sb_canvas)
        _sb_win   = _sb_canvas.create_window((0, 0), window=_sb_inner, anchor="nw")

        def _sb_on_inner_resize(e):
            _sb_canvas.configure(scrollregion=_sb_canvas.bbox("all"))
        def _sb_on_canvas_resize(e):
            _sb_canvas.itemconfig(_sb_win, width=e.width)
        _sb_inner.bind("<Configure>", _sb_on_inner_resize)
        _sb_canvas.bind("<Configure>", _sb_on_canvas_resize)

        def _sb_mousewheel(e):
            _sb_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        _sb_canvas.bind("<Enter>", lambda e: _sb_canvas.bind_all("<MouseWheel>", _sb_mousewheel))
        _sb_canvas.bind("<Leave>", lambda e: _sb_canvas.unbind_all("<MouseWheel>"))

        # Use _sb_inner as the parent for all sidebar content
        sb = _sb_inner

        self.cal_label = tk.Label(
            sb, text="📅  Calendar",
            font=("TkDefaultFont", 10, "bold")
        )
        self.cal_label.pack(anchor="w", padx=6, pady=(0, 6))

        self.mini_cal = Calendar(
            sb,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            showweeknumbers=False,
            font=("TkDefaultFont", 9),
        )
        self.mini_cal.pack(fill=tk.X, padx=4)
        self.mini_cal.bind("<<CalendarSelected>>", self._on_calendar_day_click)
        # Tooltip state
        self._cal_tooltip_win  = None
        self._cal_tooltip_date = None
        # Rebind tooltips when user navigates month or year (bind after build)
        self.mini_cal.after(200, self._bind_nav_buttons)

        # "Show all" link below the calendar
        self.cal_reset_btn = tk.Button(
            sb, text="Show all tasks",
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 9),
            command=self._calendar_reset
        )
        self.cal_reset_btn.pack(pady=(6, 0))

        # ── Dashboard Stats Panel ─────────────────────
        self.stats_sep = tk.Frame(sb, height=1)
        self.stats_sep.pack(fill=tk.X, padx=8, pady=(14, 0))

        self.stats_label = tk.Label(
            sb, text="📊  Stats",
            font=("TkDefaultFont", 10, "bold")
        )
        self.stats_label.pack(anchor="w", padx=10, pady=(8, 6))

        self.stats_frame = tk.Frame(sb)
        self.stats_frame.pack(fill=tk.X, padx=8)

        # Each stat row: icon + label on left, value on right
        self._stat_widgets = {}
        stat_rows = [
            ("total",   "📋", "Total"),
            ("active",  "⏳", "Active"),
            ("done",    "✅", "Done"),
            ("overdue", "🔴", "Overdue"),
            ("today",   "📅", "Due today"),
            ("week",    "📆", "This week"),
        ]
        for key, icon, label in stat_rows:
            row = tk.Frame(self.stats_frame)
            row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=f"{icon}  {label}",
                           font=("TkDefaultFont", 9), anchor="w")
            lbl.pack(side=tk.LEFT)
            val = tk.Label(row, text="—",
                           font=("TkDefaultFont", 9, "bold"), anchor="e")
            val.pack(side=tk.RIGHT)
            self._stat_widgets[key] = (row, lbl, val)

        # Completion progress bar (canvas-drawn)
        self.progress_frame = tk.Frame(sb)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=(10, 4))

        self.progress_header = tk.Frame(self.progress_frame)
        self.progress_header.pack(fill=tk.X)
        self.progress_title = tk.Label(
            self.progress_header, text="Completion",
            font=("TkDefaultFont", 8), anchor="w"
        )
        self.progress_title.pack(side=tk.LEFT)
        self.progress_pct_label = tk.Label(
            self.progress_header, text="0%",
            font=("TkDefaultFont", 8, "bold"), anchor="e"
        )
        self.progress_pct_label.pack(side=tk.RIGHT)

        self.progress_canvas = tk.Canvas(
            self.progress_frame, height=6, highlightthickness=0
        )
        self.progress_canvas.pack(fill=tk.X, pady=(3, 0))

        # ── Weekly Heatmap ────────────────────────────
        self.heatmap_sep = tk.Frame(sb, height=1)
        self.heatmap_sep.pack(fill=tk.X, padx=8, pady=(14, 0))

        heatmap_header = tk.Frame(sb)
        heatmap_header.pack(fill=tk.X, padx=10, pady=(8, 4))
        self.heatmap_label = tk.Label(
            heatmap_header, text="📊  Activity",
            font=("TkDefaultFont", 10, "bold")
        )
        self.heatmap_label.pack(side=tk.LEFT)
        self.heatmap_range_lbl = tk.Label(
            heatmap_header, text="",
            font=("TkDefaultFont", 8)
        )
        self.heatmap_range_lbl.pack(side=tk.RIGHT)

        # Canvas: 13 weeks (~3 months). LEFT_PAD=14 for day labels, CELL=11, GAP=1 → 14+13×12=170px
        _HM_CELL =  9
        _HM_GAP  =  1
        _HM_COLS = 17
        _HM_ROWS =  7
        _HM_LPAD = 14
        hm_w = _HM_LPAD + _HM_COLS * (_HM_CELL + _HM_GAP)   # 170px
        hm_h = _HM_ROWS * (_HM_CELL + _HM_GAP) + 14
        self.heatmap_canvas = tk.Canvas(
            sb, width=hm_w, height=hm_h,
            highlightthickness=0, bd=0
        )
        self.heatmap_canvas.pack(padx=2, pady=(0, 4), anchor="w")
        self._heatmap_tip = {"win": None}

        # ── Category Filter Panel ────────────────────
        self.cat_sep = tk.Frame(sb, height=1)
        self.cat_sep.pack(fill=tk.X, padx=8, pady=(12, 0))

        cat_header_row = tk.Frame(sb)
        cat_header_row.pack(fill=tk.X, padx=10, pady=(8, 4))

        self.cat_heading = tk.Label(
            cat_header_row, text="🏷  Categories",
            font=("TkDefaultFont", 10, "bold")
        )
        self.cat_heading.pack(side=tk.LEFT)

        self.cat_filter_frame = tk.Frame(sb)
        self.cat_filter_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._cat_filter_buttons = {}
        self._build_category_filter_buttons()


        # Vertical divider between sidebar and list
        self.sidebar_sep = tk.Frame(self.content_frame, width=1)
        self.sidebar_sep.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))

        # ── Task Treeview ────────────────────────────
        tree_frame = tk.Frame(self.content_frame)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # "Done" is the first column so the checkbox sits on the left edge
        columns = ("Done", "Name", "Category", "Priority", "Due", "DaysLeft", "Description")
        self.task_tree = ttk.Treeview(
            tree_frame, columns=columns,
            show="headings", height=15
        )

        col_config = {
            "Done":        (40,  "center"),
            "Name":        (180, "w"),
            "Category":    (100, "center"),
            "Priority":    (80,  "center"),
            "Due":         (100, "center"),
            "DaysLeft":    (120, "center"),
            "Description": (260, "w"),
        }
        for col, (width, anchor) in col_config.items():
            self.task_tree.heading(col, text="" if col == "Done" else col)
            self.task_tree.column(col, width=width, anchor=anchor,
                                  minwidth=width if col == "Done" else 40)

        # Map column names to sort keys and bind click handlers
        self._col_sort_map = {
            "Name":        "alphabetical",
            "Category":    "category",
            "Priority":    "priority",
            "Due":         "due_date",
            "DaysLeft":    "due_date",
            "Description": "alphabetical",
        }
        for col in self._col_sort_map:
            self.task_tree.heading(
                col, text=col,
                command=lambda c=col: self._sort_by_column(c)
            )

        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL,
            command=self.task_tree.yview,
            style="Flat.Vertical.TScrollbar",
        )
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.task_tree.pack(fill=tk.BOTH, expand=True)

        # Single click on the Done column toggles completion immediately
        self.task_tree.bind("<Button-1>", self._on_tree_click)
        # Double-click anywhere else opens edit
        self.task_tree.bind("<Double-1>", lambda e: self.edit_task_gui())
        # Hover highlight
        self._hovered_row = None
        self.task_tree.bind("<Motion>",  self._on_tree_hover)
        self.task_tree.bind("<Leave>",   self._on_tree_leave)

    # ═══════════════════════════════════════════════
    #  FILTER HELPER
    # ═══════════════════════════════════════════════

    def _set_filter(self, value):
        self.filter_type.set(value)
        self._update_filter_buttons()
        self.refresh_tasks()

    def _set_sort(self, value):
        self.sort_type.set(value)
        self._update_sort_buttons()
        self.refresh_tasks()

    def _bind_hover(self, btn, is_active_fn, rest_bg=None, hover_bg=None):
        """Attach Enter/Leave hover highlight to any pill/toolbar button."""
        def on_enter(e):
            t = DARK_THEME if self.dark_mode else LIGHT_THEME
            if is_active_fn():
                btn.configure(bg=t["accent_hover"])
            else:
                btn.configure(bg=hover_bg or t["border"])
        def on_leave(e):
            t = DARK_THEME if self.dark_mode else LIGHT_THEME
            if is_active_fn():
                btn.configure(bg=t["accent"])
            else:
                btn.configure(bg=rest_bg or t["surface2"])
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

    def _bind_tooltip(self, widget, text_fn):
        """
        Show a small tooltip above the widget on hover.
        text_fn is a callable so the label is evaluated at hover time (always fresh).
        """
        tip = {"win": None}

        def show(e):
            msg = text_fn()
            if not msg:
                return
            t   = DARK_THEME if self.dark_mode else LIGHT_THEME
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=t["border"])
            tk.Label(
                win, text=msg,
                bg=t["surface2"], fg=t["fg"],
                font=("TkDefaultFont", 9),
                padx=10, pady=5,
            ).pack(padx=1, pady=1)
            win.update_idletasks()
            wx = widget.winfo_rootx()
            wy = widget.winfo_rooty()
            ww = win.winfo_reqwidth()
            wh = win.winfo_reqheight()
            win.geometry(f"+{wx}+{wy - wh - 4}")
            tip["win"] = win

        def hide(e):
            if tip["win"]:
                try:
                    tip["win"].destroy()
                except Exception:
                    pass
                tip["win"] = None

        widget.bind("<Enter>", lambda e: (hide(e), show(e)), add="+")
        widget.bind("<Leave>", hide, add="+")

    def _update_filter_buttons(self):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        active = self.filter_type.get()
        for label, btn in self.filter_buttons.items():
            if label == active:
                btn.configure(
                    bg=t["accent"], fg=t["accent_fg"],
                    activebackground=t["accent_hover"],
                    activeforeground=t["accent_fg"]
                )
            else:
                btn.configure(
                    bg=t["surface2"], fg=t["muted_fg"],
                    activebackground=t["border"],
                    activeforeground=t["fg"]
                )
            self._bind_hover(btn, lambda lbl=label: self.filter_type.get() == lbl)

    def _update_sort_buttons(self):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        active = self.sort_type.get()
        for value, btn in self.sort_buttons.items():
            if value == active:
                btn.configure(
                    bg=t["accent"], fg=t["accent_fg"],
                    activebackground=t["accent_hover"],
                    activeforeground=t["accent_fg"]
                )
            else:
                btn.configure(
                    bg=t["surface2"], fg=t["muted_fg"],
                    activebackground=t["border"],
                    activeforeground=t["fg"]
                )
            self._bind_hover(btn, lambda val=value: self.sort_type.get() == val)

    # ═══════════════════════════════════════════════
    #  THEME
    # ═══════════════════════════════════════════════

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.save_ui_config()
        self.apply_theme()

    def apply_theme(self):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        self.root.configure(bg=t["bg"])

        # Header
        for w in [self.header_frame, self.title_label.master]:
            w.configure(bg=t["bg"])
        self.title_label.configure(bg=t["bg"], fg=t["fg"])
        self.count_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.add_btn.configure(
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"],
            activeforeground=t["accent_fg"]
        )
        self._bind_hover(self.add_btn, lambda: True)

        # Separators
        for sep in [self.sep1, self.sep2, self.sep3]:
            sep.configure(bg=t["border"])

        # Toolbar
        self.toolbar.configure(bg=t["surface2"])
        self.toolbar_inner.configure(bg=t["surface2"])
        self.toolbar_divider.configure(bg=t["border"])
        self.filter_heading.configure(bg=t["surface2"], fg=t["muted_fg"])
        self.sort_heading.configure(bg=t["surface2"], fg=t["muted_fg"])
        self.search_entry.configure(
            bg=t["entry_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            highlightthickness=1,
            highlightbackground=t["border"],
            highlightcolor=t["accent"]
        )
        self.sort_label = None  # removed — no longer used
        self._update_filter_buttons()
        self._update_sort_buttons()

        # Sidebar
        self.sidebar.configure(bg=t["bg"])
        self.sidebar_sep.configure(bg=t["border"])
        self.content_frame.configure(bg=t["bg"])
        # Theme the scrollable canvas and inner frame
        self._sb_canvas.configure(bg=t["bg"])
        self._sb_inner.configure(bg=t["bg"])
        self.cal_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.cal_reset_btn.configure(
            bg=t["bg"], fg=t["accent"],
            activebackground=t["bg"], activeforeground=t["accent_hover"]
        )
        self.mini_cal.configure(
            background=t["surface2"],
            foreground=t["fg"],
            headersbackground=t["surface"],
            headersforeground=t["muted_fg"],
            selectbackground=t["accent"],
            selectforeground=t["accent_fg"],
            normalbackground=t["surface2"],
            normalforeground=t["fg"],
            weekendbackground=t["surface"],
            weekendforeground=t["fg"],
            othermonthbackground=t["bg"],
            othermonthforeground=t["muted_fg"],
            bordercolor=t["border"],
            tooltipbackground=t["surface2"],
            tooltipforeground=t["fg"],
        )
        self.refresh_calendar()

        # Stats panel
        self.stats_sep.configure(bg=t["border"])
        self.stats_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.stats_frame.configure(bg=t["bg"])
        self.progress_frame.configure(bg=t["bg"])
        self.progress_header.configure(bg=t["bg"])
        self.progress_title.configure(bg=t["bg"], fg=t["muted_fg"])
        self.progress_pct_label.configure(bg=t["bg"], fg=t["fg"])
        self.progress_canvas.configure(bg=t["bg"])
        for key, (row, lbl, val) in self._stat_widgets.items():
            row.configure(bg=t["bg"])
            lbl.configure(bg=t["bg"], fg=t["muted_fg"])
            val.configure(bg=t["bg"], fg=t["fg"])
        self.refresh_stats()

        # Heatmap
        self.heatmap_sep.configure(bg=t["border"])
        self.heatmap_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.heatmap_range_lbl.configure(bg=t["bg"], fg=t["muted_fg"])
        self.heatmap_canvas.configure(bg=t["bg"])
        self.heatmap_canvas.master.configure(bg=t["bg"])

        # Category filter panel
        self.cat_sep.configure(bg=t["border"])
        self.cat_heading.configure(bg=t["bg"], fg=t["muted_fg"])
        cat_header_row = self.cat_heading.master
        cat_header_row.configure(bg=t["bg"])

        self.cat_filter_frame.configure(bg=t["bg"])
        self._build_category_filter_buttons()

        # Footer
        for w in [self.footer_frame, self.action_frame, self.right_frame]:
            w.configure(bg=t["bg"])
        self.undo_divider.configure(bg=t["border"])
        for btn in [self.undo_btn, self.redo_btn] + self.action_buttons:
            btn.configure(
                bg=t["secondary_btn_bg"], fg=t["secondary_btn_fg"],
                activebackground=t["border"],
                activeforeground=t["fg"]
            )
            self._bind_hover(btn, lambda: False,
                             rest_bg=t["secondary_btn_bg"], hover_bg=t["border"])
        self._update_undo_redo_buttons()
        self.save_dot.configure(bg=t["bg"])
        self.save_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.help_btn.configure(
            bg=t["surface2"], fg=t["accent"],
            activebackground=t["border"], activeforeground=t["accent"]
        )
        self._bind_hover(self.help_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])
        self.import_btn.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"],
            activeforeground=t["fg"]
        )
        self._bind_hover(self.import_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])
        self.export_btn.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"],
            activeforeground=t["fg"]
        )
        self._bind_hover(self.export_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])
        self.settings_btn.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"],
            activeforeground=t["fg"],
        )
        self._bind_hover(self.settings_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])

        # Treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background=t["surface"],
            foreground=t["list_fg"],
            fieldbackground=t["surface"],
            rowheight=30,
            font=("TkDefaultFont", 11),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=t["surface2"],
            foreground=t["heading_fg"],
            font=("TkDefaultFont", 10, "bold"),
            relief="flat",
            borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", t["accent"])],
            foreground=[("selected", t["accent_fg"])]
        )
        style.configure(
            "Vertical.TScrollbar",
            background=t["surface2"],
            troughcolor=t["bg"],
            arrowcolor=t["muted_fg"],
            relief="flat",
            borderwidth=0,
        )
        # Custom flat scrollbar — used by sidebar and Settings dialog
        # Explicit layout overrides any OS/maximize-triggered theme reset
        style.layout("Flat.Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {
                "sticky": "ns",
                "children": [
                    ("Vertical.Scrollbar.thumb", {"unit": "1", "sticky": "nswe"}),
                ],
            }),
        ])
        style.configure(
            "Flat.Vertical.TScrollbar",
            background=t["surface2"],
            troughcolor=t["bg"],
            bordercolor=t["bg"],
            darkcolor=t["surface2"],
            lightcolor=t["surface2"],
            arrowcolor=t["bg"],
            relief="flat",
            borderwidth=0,
            width=8,
        )
        style.map(
            "Flat.Vertical.TScrollbar",
            background=[
                ("pressed",  t["accent"]),
                ("active",   t["muted_fg"]),
                ("!active",  t["border"]),
            ],
        )
        self._configure_tags()

    def _configure_tags(self):
        if self.dark_mode:
            self.task_tree.tag_configure("hover",   background="#2C3240")
            self.task_tree.tag_configure("done",    foreground="#4A4E5A")
            self.task_tree.tag_configure("overdue", foreground="#F87171")
            self.task_tree.tag_configure("high",    foreground="#F87171")
            self.task_tree.tag_configure("medium",  foreground="#FCD34D")
            self.task_tree.tag_configure("low",     foreground="#6EE7A0")
        else:
            self.task_tree.tag_configure("hover",   background="#EDE8E1")
            self.task_tree.tag_configure("done",    foreground="#B0AAA4")
            self.task_tree.tag_configure("overdue", foreground="#DC2626")
            self.task_tree.tag_configure("high",    foreground="#B91C1C")
            self.task_tree.tag_configure("medium",  foreground="#B45309")
            self.task_tree.tag_configure("low",     foreground="#4D7C5F")

    def save_ui_config(self):
        save_config({
            "dark_mode":  self.dark_mode,
            "sort":       self.sort_type.get(),
            "filter":     self.filter_type.get(),
            "geometry":   self.root.geometry(),
            "categories":        self.categories,
            "category_colors":   self.category_colors,
            "minimize_to_tray":  self.minimize_to_tray,
            "reminders":         self.reminder_cfg,
        }, self.username)

    # ═══════════════════════════════════════════════
    #  CATEGORIES
    # ═══════════════════════════════════════════════

    def _build_category_filter_buttons(self):
        """(Re)build the category pill buttons in the sidebar."""
        for w in self.cat_filter_frame.winfo_children():
            w.destroy()
        self._cat_filter_buttons.clear()
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # "All" button
        all_btn = tk.Button(
            self.cat_filter_frame, text="All",
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 9, "bold"),
            padx=8, pady=3,
            command=lambda: self._set_category_filter(None)
        )
        all_btn.pack(fill=tk.X, pady=1)
        self._cat_filter_buttons[None] = all_btn

        for cat in self.categories:
            bg, fg = cat_module.get_color(cat, self.categories, self.dark_mode, self.category_colors)
            btn = tk.Button(
                self.cat_filter_frame, text=cat,
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 9),
                padx=8, pady=3,
                bg=bg, fg=fg,
                activebackground=bg, activeforeground=fg,
                command=lambda c=cat: self._set_category_filter(c)
            )
            btn.pack(fill=tk.X, pady=1)
            self._cat_filter_buttons[cat] = btn

        self._update_category_buttons()

    def _set_category_filter(self, cat):
        self._category_filter = cat
        self._update_category_buttons()
        self.refresh_tasks()

    def _update_category_buttons(self):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        active = self._category_filter
        for key, btn in self._cat_filter_buttons.items():
            if key == active:
                btn.configure(relief="solid", bd=2)
            else:
                btn.configure(relief="flat", bd=0)
        # "All" button colour
        all_btn = self._cat_filter_buttons.get(None)
        if all_btn:
            if active is None:
                all_btn.configure(bg=t["accent"], fg=t["accent_fg"])
            else:
                all_btn.configure(bg=t["surface2"], fg=t["muted_fg"])

    def open_import_gui(self):
        """Import tasks from CSV, TXT, or PDF."""
        from tkinter.filedialog import askopenfilename
        from core.tasks import Task

        top = self._make_dialog("Import Tasks")
        top.resizable(False, False)
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # Footer first
        tk.Frame(top, height=1, bg=t["border"]).pack(side=tk.BOTTOM, fill=tk.X)
        foot = tk.Frame(top, bg=t["surface"], height=64)
        foot.pack(side=tk.BOTTOM, fill=tk.X)
        foot.pack_propagate(False)

        # Header
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⬇  Import Tasks",
                 font=("Georgia", 13, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=18, pady=(14, 12))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        body = tk.Frame(top, bg=t["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=14)

        def section(text):
            tk.Label(body, text=text, font=("TkDefaultFont", 9, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(10, 3))
            tk.Frame(body, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))

        # ── File picker ───────────────────────────────────
        section("FILE")
        file_row = tk.Frame(body, bg=t["bg"])
        file_row.pack(fill=tk.X)

        file_var = tk.StringVar(value="No file selected")
        file_lbl = tk.Label(file_row, textvariable=file_var,
                            bg=t["surface2"], fg=t["muted_fg"],
                            font=("TkDefaultFont", 9),
                            anchor="w", padx=8,
                            highlightthickness=1,
                            highlightbackground=t["border"])
        file_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)

        chosen_path = {"v": None}

        def pick_file():
            path = askopenfilename(
                title="Choose file to import",
                filetypes=[
                    ("Supported files", "*.csv *.txt *.pdf"),
                    ("CSV files", "*.csv"),
                    ("Text files", "*.txt"),
                    ("PDF files", "*.pdf"),
                ],
                parent=top,
            )
            if path:
                chosen_path["v"] = path
                import os
                file_var.set(os.path.basename(path))
                file_lbl.configure(fg=t["fg"])
                status_lbl.configure(text="")
                _preview()

        self._btn(file_row, t, "Browse…", pick_file).pack(side=tk.LEFT, padx=(8, 0))

        # ── Duplicate handling ────────────────────────────
        section("DUPLICATES")
        dup_var = tk.StringVar(value="skip")
        for val, label, desc in [
            ("skip",    "Skip",    "Don't import tasks with the same name"),
            ("replace", "Replace", "Overwrite existing tasks with the same name"),
            ("keep",    "Keep all","Import all tasks even if names match"),
        ]:
            row = tk.Frame(body, bg=t["bg"])
            row.pack(fill=tk.X, pady=1)
            tk.Radiobutton(row, text=label, variable=dup_var, value=val,
                           bg=t["bg"], fg=t["fg"],
                           activebackground=t["bg"], selectcolor=t["surface2"],
                           relief="flat", cursor="hand2",
                           font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
            tk.Label(row, text=f"  — {desc}", bg=t["bg"], fg=t["muted_fg"],
                     font=("TkDefaultFont", 9)).pack(side=tk.LEFT)

        # ── Preview count ─────────────────────────────────
        preview_lbl = tk.Label(body, text="", bg=t["bg"], fg=t["muted_fg"],
                               font=("TkDefaultFont", 9, "italic"))
        preview_lbl.pack(anchor="w", pady=(10, 0))

        status_lbl = tk.Label(body, text="", bg=t["bg"],
                              font=("TkDefaultFont", 9))
        status_lbl.pack(anchor="w", pady=(4, 0))

        parsed_tasks = {"v": []}

        def _preview():
            path = chosen_path["v"]
            if not path:
                return
            try:
                ext = path.lower().rsplit(".", 1)[-1]
                if ext == "csv":
                    rows = import_module.import_csv(path)
                elif ext == "txt":
                    rows = import_module.import_txt(path)
                elif ext == "pdf":
                    rows = import_module.import_pdf(path)
                else:
                    rows = []
                parsed_tasks["v"] = rows
                preview_lbl.configure(
                    text=f"Found {len(rows)} task(s) in file.",
                    fg="#4ADE80" if rows else t["muted_fg"]
                )
            except ImportError as e:
                preview_lbl.configure(text=str(e), fg="#EF4444")
            except Exception as e:
                preview_lbl.configure(text=f"Parse error: {e}", fg="#EF4444")

        def do_import():
            rows = parsed_tasks["v"]
            if not rows:
                status_lbl.configure(text="No tasks to import. Pick a file first.",
                                     fg="#EF4444")
                return

            dup = dup_var.get()
            existing_names = {task.name.lower() for task in self.manager.tasks}
            added = skipped = replaced = 0

            for row in rows:
                name = row["name"].strip()
                if not name:
                    continue
                is_dup = name.lower() in existing_names

                if is_dup and dup == "skip":
                    skipped += 1
                    continue

                if is_dup and dup == "replace":
                    self.manager.tasks = [
                        tk_task for tk_task in self.manager.tasks
                        if tk_task.name.lower() != name.lower()
                    ]
                    replaced += 1

                new_task = Task(
                    name,
                    row.get("description", ""),
                    row.get("due_date"),
                    row.get("priority", "Medium"),
                )
                new_task.category = row.get("category", "General")
                new_task.done     = row.get("done", False)
                new_task.update_status()
                self.manager.tasks.append(new_task)
                existing_names.add(name.lower())
                added += 1

            save_tasks(self.manager, self.username)
            self.refresh_tasks()

            parts = [f"{added} imported"]
            if replaced: parts.append(f"{replaced} replaced")
            if skipped:  parts.append(f"{skipped} skipped")
            status_lbl.configure(text="Done — " + ", ".join(parts) + ".", fg="#4ADE80")

        tk.Button(
            foot, text="⬇  Import", command=do_import,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 12, "bold"),
        ).place(x=14, y=10, relwidth=1.0, width=-28, height=44)

        top.geometry("420x520")

    def open_export_gui(self):
        """Export dialog: choose format, scope, and destination file."""
        top = self._make_dialog("Export Tasks")
        top.resizable(False, False)
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # Footer first (pack before grid content)
        tk.Frame(top, height=1, bg=t["border"]).pack(side=tk.BOTTOM, fill=tk.X)
        foot = tk.Frame(top, bg=t["surface"], height=64)
        foot.pack(side=tk.BOTTOM, fill=tk.X)
        foot.pack_propagate(False)

        # Header
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⬆  Export Tasks",
                 font=("Georgia", 13, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=18, pady=(14, 12))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        body = tk.Frame(top, bg=t["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=14)

        def section(text):
            tk.Label(body, text=text, font=("TkDefaultFont", 9, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(10, 3))
            tk.Frame(body, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))

        # ── Format ────────────────────────────────────────
        section("FORMAT")
        fmt_var = tk.StringVar(value="CSV")
        fmt_row = tk.Frame(body, bg=t["bg"])
        fmt_row.pack(fill=tk.X)
        for fmt, desc in [("CSV", "Spreadsheet (.csv)"),
                          ("TXT", "Plain text (.txt)"),
                          ("PDF", "PDF report (.pdf)")]:
            col = tk.Frame(fmt_row, bg=t["bg"])
            col.pack(side=tk.LEFT, padx=(0, 16))
            tk.Radiobutton(
                col, text=fmt, variable=fmt_var, value=fmt,
                bg=t["bg"], fg=t["fg"],
                activebackground=t["bg"], selectcolor=t["surface2"],
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 11, "bold")
            ).pack(anchor="w")
            tk.Label(col, text=desc, bg=t["bg"], fg=t["muted_fg"],
                     font=("TkDefaultFont", 8)).pack(anchor="w")

        # ── Scope ─────────────────────────────────────────
        section("SCOPE")
        scope_var = tk.StringVar(value="all")
        for val, label in [
            ("all",    "All tasks"),
            ("active", "Active tasks only"),
            ("done",   "Done tasks only"),
        ]:
            tk.Radiobutton(
                body, text=label, variable=scope_var, value=val,
                bg=t["bg"], fg=t["fg"],
                activebackground=t["bg"], selectcolor=t["surface2"],
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 10)
            ).pack(anchor="w", pady=1)

        # ── Status label ──────────────────────────────────
        status_lbl = tk.Label(body, text="", bg=t["bg"],
                              font=("TkDefaultFont", 9))
        status_lbl.pack(anchor="w", pady=(12, 0))

        # Share panel (built after generating the temp file)
        share_frame = tk.Frame(body, bg=t["bg"])
        temp_files  = {"path": None}   # track temp file for cleanup on close

        def _build_share_panel(tmp_path, fmt, task_list):
            """Show all share destinations — no mandatory save-to-PC."""
            for w in share_frame.winfo_children():
                w.destroy()
            share_frame.pack(fill=tk.X, pady=(10, 0))

            tk.Frame(share_frame, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))
            tk.Label(share_frame, text="WHAT WOULD YOU LIKE TO DO?",
                     font=("TkDefaultFont", 8, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(0, 6))

            def _share_btn(parent, label, cmd):
                b = tk.Button(parent, text=label, command=cmd,
                              relief="flat", cursor="hand2",
                              bg=t["surface2"], fg=t["fg"],
                              activebackground=t["border"],
                              font=("TkDefaultFont", 9), padx=8, pady=5)
                b.pack(side=tk.LEFT, padx=(0, 6), pady=2)
                return b

            def _row():
                r = tk.Frame(share_frame, bg=t["bg"])
                r.pack(fill=tk.X)
                return r

            # ── Save to PC ───────────────────────────────────
            row_save = _row()
            def save_to_pc():
                from tkinter.filedialog import asksaveasfilename
                ext_map  = {"CSV": ".csv", "TXT": ".txt", "PDF": ".pdf"}
                type_map = {"CSV": [("CSV files", "*.csv")],
                            "TXT": [("Text files", "*.txt")],
                            "PDF": [("PDF files", "*.pdf")]}
                dest = asksaveasfilename(
                    initialfile=os.path.basename(tmp_path),
                    defaultextension=ext_map[fmt],
                    filetypes=type_map[fmt],
                    title="Save export file",
                    parent=top,
                )
                if dest:
                    import shutil
                    shutil.copy2(tmp_path, dest)
                    status_lbl.configure(
                        text=f"✓  Saved to {os.path.basename(dest)}",
                        fg="#4ADE80"
                    )

            _share_btn(row_save, "💾  Save to PC", save_to_pc)
            _share_btn(row_save, "📂  Open file",
                       lambda: share_module.open_file(tmp_path))
            _share_btn(row_save, "🗂  Show folder",
                       lambda: share_module.reveal_in_folder(tmp_path))

            # ── Clipboard ────────────────────────────────────
            row_clip = _row()
            clip_lbl = tk.Label(row_clip, text="", bg=t["bg"],
                                fg="#4ADE80", font=("TkDefaultFont", 8))
            def copy_path():
                share_module.copy_path_to_clipboard(tmp_path, self.root)
                clip_lbl.configure(text="Path copied!")
                top.after(2000, lambda: clip_lbl.configure(text=""))
            def copy_content():
                ok = share_module.copy_content_to_clipboard(tmp_path, self.root)
                clip_lbl.configure(text="Copied!" if ok else "Cannot copy PDF.")
                top.after(2000, lambda: clip_lbl.configure(text=""))

            _share_btn(row_clip, "📋  Copy path", copy_path)
            if fmt in ("CSV", "TXT"):
                _share_btn(row_clip, "📄  Copy content", copy_content)
            clip_lbl.pack(side=tk.LEFT, padx=(6, 0))

            # ── Email ────────────────────────────────────────
            row_mail = _row()
            def send_mail():
                fname = os.path.basename(tmp_path)
                if not share_module.send_email_outlook(tmp_path, f"Tasks export — {fname}"):
                    share_module.send_email(tmp_path, f"Tasks export — {fname}")

            _share_btn(row_mail, "✉️  Send by email", send_mail)
            if fmt == "PDF":
                tk.Label(row_mail,
                         text="(Outlook: attached automatically)",
                         bg=t["bg"], fg=t["muted_fg"],
                         font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(6, 0))

            # ── Messaging ────────────────────────────────────
            row_msg = _row()
            if fmt in ("TXT", "CSV"):
                share_text = share_module.tasks_to_share_text(task_list)
                for name, icon, fn in share_module.COMMUNICATORS:
                    _share_btn(row_msg, f"{icon}  {name}",
                               lambda f=fn: f(share_text))
            else:
                def _open_wa(): webbrowser.open("https://web.whatsapp.com")
                def _open_tg(): webbrowser.open("https://web.telegram.org")
                _share_btn(row_msg, "💬  WhatsApp Web", _open_wa)
                _share_btn(row_msg, "✈️  Telegram Web",  _open_tg)
                tk.Label(row_msg, text="— attach PDF manually",
                         bg=t["bg"], fg=t["muted_fg"],
                         font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(4, 0))

            # Resize to fit
            top.update_idletasks()
            new_h = min(top.winfo_reqheight() + 20, 700)
            top.geometry(f"420x{new_h}")

        def do_export():
            import tempfile
            fmt   = fmt_var.get()
            scope = scope_var.get()

            tasks = list(self.manager.tasks)
            if scope == "active":
                tasks = [tk_t for tk_t in tasks if not tk_t.done]
            elif scope == "done":
                tasks = [tk_t for tk_t in tasks if tk_t.done]

            if not tasks:
                status_lbl.configure(text="No tasks match the selected scope.",
                                     fg="#EF4444")
                return

            ext_map = {"CSV": ".csv", "TXT": ".txt", "PDF": ".pdf"}
            try:
                # Write to a named temp file that persists until dialog closes
                if temp_files["path"] and os.path.exists(temp_files["path"]):
                    try: os.unlink(temp_files["path"])
                    except: pass

                from datetime import datetime as dt
                stamp   = dt.now().strftime("%d%m%Y_%H%M")
                suffix  = ext_map[fmt]
                fname   = f"mytasks_{stamp}{suffix}"

                tmp_dir  = tempfile.gettempdir()
                tmp_path = os.path.join(tmp_dir, fname)
                temp_files["path"] = tmp_path

                if fmt == "CSV":
                    export_module.export_csv(tasks, tmp_path)
                elif fmt == "TXT":
                    export_module.export_txt(tasks, tmp_path)
                elif fmt == "PDF":
                    export_module.export_pdf(tasks, tmp_path)

                status_lbl.configure(
                    text=f"✓  {len(tasks)} tasks ready — choose what to do:",
                    fg="#4ADE80"
                )
                _build_share_panel(tmp_path, fmt, tasks)

            except ImportError as e:
                status_lbl.configure(text=str(e), fg="#EF4444")
            except Exception as e:
                status_lbl.configure(text=f"Error: {e}", fg="#EF4444")

        def _cleanup_temp():
            if temp_files["path"] and os.path.exists(temp_files["path"]):
                try: os.unlink(temp_files["path"])
                except: pass
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", _cleanup_temp)

        tk.Button(
            foot, text="⚡  Generate", command=do_export,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 12, "bold"),
        ).place(x=14, y=10, relwidth=1.0, width=-28, height=44)

        top.geometry("380x460")

    def open_settings_gui(self):
        """Full Settings dialog with tabbed sections."""
        top = self._make_dialog("Settings")
        top.resizable(True, True)
        top.minsize(460, 420)
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # ── Header ────────────────────────────────────────
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⚙  Settings", font=("Georgia", 14, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=18, pady=(14, 12))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        # ── Footer (packed before canvas so it's always visible) ──
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X, side=tk.BOTTOM)
        foot = tk.Frame(top, bg=t["surface"], height=70)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        tk.Button(
            foot, text="Close", command=top.destroy,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 13, "bold"),
        ).place(x=18, y=10, relwidth=1.0, width=-36, height=50)

        # ── Scrollable canvas body ─────────────────────────
        canvas_frame = tk.Frame(top, bg=t["bg"])
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, bg=t["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview, style="Flat.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        body = tk.Frame(canvas, bg=t["bg"])
        body_win = canvas.create_window((0, 0), window=body, anchor="nw")

        # Keep inner frame width in sync with canvas width
        def _on_canvas_resize(e):
            canvas.itemconfig(body_win, width=e.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        # Update scroll region whenever body content changes
        def _on_body_resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Auto-fit height up to 85% of screen
            content_h  = body.winfo_reqheight()
            screen_h   = top.winfo_screenheight()
            max_h      = int(screen_h * 0.85)
            header_h   = hdr.winfo_reqheight() + 2   # +border
            footer_h   = foot.winfo_reqheight() + 2
            dialog_h   = min(content_h + header_h + footer_h + 10, max_h)
            top.geometry(f"460x{dialog_h}")
        body.bind("<Configure>", _on_body_resize)

        # Mouse-wheel scroll
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        top.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # Inner padding wrapper
        pad = tk.Frame(body, bg=t["bg"])
        pad.pack(fill=tk.BOTH, expand=True, padx=18, pady=12)

        def section(parent, title):
            """Render a section heading."""
            tk.Label(parent, text=title, font=("TkDefaultFont", 9, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(14, 4))
            tk.Frame(parent, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))

        def row(parent, label_text, widget_fn):
            """Label on left, widget on right."""
            r = tk.Frame(parent, bg=t["bg"])
            r.pack(fill=tk.X, pady=4)
            tk.Label(r, text=label_text, bg=t["bg"], fg=t["fg"],
                     font=("TkDefaultFont", 10), anchor="w").pack(side=tk.LEFT)
            widget_fn(r)
            return r

        # ══ APPEARANCE ════════════════════════════════════
        section(pad, "APPEARANCE")

        # Dark mode toggle
        dark_var = tk.BooleanVar(value=self.dark_mode)
        def toggle_dark():
            self.dark_mode = dark_var.get()
            self.save_ui_config()
            self.apply_theme()

        def row_dark(parent):
            chk = tk.Checkbutton(parent, variable=dark_var, command=toggle_dark,
                                 bg=t["bg"], fg=t["fg"],
                                 activebackground=t["bg"],
                                 selectcolor=t["surface2"],
                                 relief="flat", cursor="hand2")
            chk.pack(side=tk.RIGHT)
        row(pad, "Dark mode", row_dark)

        # ══ BEHAVIOUR ═════════════════════════════════════
        section(pad, "BEHAVIOUR")

        tray_var = tk.BooleanVar(value=self.minimize_to_tray)
        tray_note = "(requires pystray)" if not TRAY_AVAILABLE else ""
        def toggle_tray():
            self.minimize_to_tray = tray_var.get()
            self.save_ui_config()

        def row_tray(parent):
            chk = tk.Checkbutton(parent, variable=tray_var, command=toggle_tray,
                                 bg=t["bg"], fg=t["fg"],
                                 activebackground=t["bg"],
                                 selectcolor=t["surface2"],
                                 relief="flat", cursor="hand2",
                                 state="normal" if TRAY_AVAILABLE else "disabled")
            chk.pack(side=tk.RIGHT)
        row(pad, f"Minimise to tray on close  {tray_note}", row_tray)

        # ══ REMINDERS ═════════════════════════════════════
        section(pad, "REMINDERS")

        rem_vars = {}
        remind_labels = [
            ("reminders_enabled", "Enable task reminders"),
            ("remind_overdue",    "Notify for overdue tasks"),
            ("remind_today",      "Notify for tasks due today"),
            ("remind_tomorrow",   "Notify for tasks due tomorrow"),
            ("remind_3days",      "Notify for tasks due within 3 days"),
        ]

        def make_toggle_rem(key, var):
            def _toggle():
                self.reminder_cfg[key] = var.get()
                self.save_ui_config()
                if hasattr(self, "_reminder_svc"):
                    self._reminder_svc.update_config(self.reminder_cfg)
                # Enable/disable sub-checkboxes when master toggle changes
                if key == "reminders_enabled":
                    state = "normal" if var.get() else "disabled"
                    for k, v in rem_vars.items():
                        if k != "reminders_enabled":
                            v["chk"].configure(state=state)
            return _toggle

        for key, label in remind_labels:
            var = tk.BooleanVar(value=self.reminder_cfg.get(key, True))
            enabled = self.reminder_cfg.get("reminders_enabled", True)
            state = "normal" if (key == "reminders_enabled" or enabled) else "disabled"

            def _row_rem(parent, v=var, k=key):
                chk = tk.Checkbutton(
                    parent, variable=v,
                    command=make_toggle_rem(k, v),
                    bg=t["bg"], fg=t["fg"],
                    activebackground=t["bg"],
                    selectcolor=t["surface2"],
                    relief="flat", cursor="hand2",
                    state=state,
                )
                chk.pack(side=tk.RIGHT)
                rem_vars[k] = {"chk": chk, "var": v}

            row(pad, label, _row_rem)

        if not REMINDERS_AVAILABLE:
            note = tk.Label(pad,
                            text="Install plyer for OS notifications:  pip install plyer\n"
                                 "Without it, in-app toasts are used.",
                            bg=t["bg"], fg=t["muted_fg"],
                            font=("TkDefaultFont", 8),
                            justify="left")
            note.pack(anchor="w", pady=(4, 0))
        section(pad, "CATEGORIES")

        cat_outer = tk.Frame(pad, bg=t["bg"])
        cat_outer.pack(fill=tk.X)

        # Scrollable list of categories
        list_frame = tk.Frame(cat_outer, bg=t["surface2"],
                              highlightthickness=1,
                              highlightbackground=t["border"])
        list_frame.pack(fill=tk.X, pady=(0, 8))

        def rebuild_cat_list():
            for w in list_frame.winfo_children():
                w.destroy()
            for cat in self.categories:
                r = tk.Frame(list_frame, bg=t["surface2"])
                r.pack(fill=tk.X, padx=6, pady=3)
                from core import categories as _cm
                bg_c, fg_c = _cm.get_color(cat, self.categories, self.dark_mode, self.category_colors)
                tk.Label(r, text=cat, bg=bg_c, fg=fg_c,
                         font=("TkDefaultFont", 9, "bold"),
                         padx=8, pady=2).pack(side=tk.LEFT)
                if cat != "General":
                    def _del(c=cat):
                        self.categories.remove(c)
                        self.category_colors.pop(c, None)   # remove custom colour
                        for task in self.manager.tasks:
                            if getattr(task, "category", "General") == c:
                                task.category = "General"
                        self.save_ui_config()
                        self._build_category_filter_buttons()
                        self.refresh_tasks()
                        rebuild_cat_list()
                    tk.Button(r, text="✕", relief="flat", cursor="hand2",
                              bg=t["surface2"], fg=t["muted_fg"],
                              activebackground=t["surface2"],
                              font=("TkDefaultFont", 8),
                              command=_del).pack(side=tk.RIGHT)

        rebuild_cat_list()

        # ── Add new category ──────────────────────────────
        # State: chosen custom colour for the new category (None = use palette)
        chosen_color = {"light": None, "dark": None}  # mutable dict for closure

        add_row = tk.Frame(cat_outer, bg=t["bg"])
        add_row.pack(fill=tk.X, pady=(4, 0))

        new_cat_entry = self._entry(add_row, t, width=16)
        new_cat_entry.pack(side=tk.LEFT, ipady=4, padx=(0, 6))

        # Colour swatch button — shows chosen colour, opens picker on click
        DEFAULT_SWATCH = t["surface2"]
        swatch_btn = tk.Button(
            add_row, text="  🎨  ", relief="flat", cursor="hand2",
            bg=DEFAULT_SWATCH, fg=t["fg"],
            activebackground=t["border"],
            font=("TkDefaultFont", 10),
            padx=4, pady=4
        )
        swatch_btn.pack(side=tk.LEFT, padx=(0, 6))

        def pick_color():
            from tkinter.colorchooser import askcolor
            # Start from current swatch colour or a default
            init = chosen_color["light"] or t["accent"]
            result = askcolor(color=init, title="Pick category colour", parent=top)
            if result and result[1]:
                bg_light = result[1]          # e.g. "#a855f7"
                fg_light = auto_fg(bg_light)
                # Derive a darker shade for dark mode (reduce brightness ~40%)
                r = int(bg_light[1:3], 16)
                g = int(bg_light[3:5], 16)
                b = int(bg_light[5:7], 16)
                bg_dark = "#{:02x}{:02x}{:02x}".format(
                    max(0, int(r * 0.45)),
                    max(0, int(g * 0.45)),
                    max(0, int(b * 0.45)),
                )
                fg_dark = "#{:02x}{:02x}{:02x}".format(
                    min(255, int(r * 1.7)),
                    min(255, int(g * 1.7)),
                    min(255, int(b * 1.7)),
                )
                chosen_color["light"] = (bg_light, fg_light)
                chosen_color["dark"]  = (bg_dark,  fg_dark)
                swatch_btn.configure(bg=bg_light, fg=fg_light,
                                     activebackground=bg_light)

        swatch_btn.configure(command=pick_color)

        def add_category():
            name = new_cat_entry.get().strip()
            if not name or name in self.categories:
                return
            self.categories.append(name)
            # Store custom colour if one was picked
            if chosen_color["light"]:
                self.category_colors[name] = {
                    "light": chosen_color["light"],
                    "dark":  chosen_color["dark"],
                }
                # Reset for next use
                chosen_color["light"] = None
                chosen_color["dark"]  = None
                swatch_btn.configure(bg=DEFAULT_SWATCH, fg=t["fg"],
                                     activebackground=t["border"])
            new_cat_entry.delete(0, tk.END)
            self.save_ui_config()
            self._build_category_filter_buttons()
            rebuild_cat_list()

        self._btn(add_row, t, "Add", add_category, primary=True).pack(side=tk.LEFT)
        new_cat_entry.bind("<Return>", lambda e: add_category())

    def _manage_categories_gui(self):
        """Dialog to add/remove custom categories."""
        top = self._make_dialog("Manage Categories")
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        top.geometry("320x420")

        tk.Label(top, text="Your categories:", **self._lbl(t)).pack(anchor="w", padx=14, pady=(12, 4))

        list_frame = tk.Frame(top, bg=t["surface2"], bd=1, relief="flat")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        def rebuild_list():
            for w in list_frame.winfo_children():
                w.destroy()
            for cat in self.categories:
                row = tk.Frame(list_frame, bg=t["surface2"])
                row.pack(fill=tk.X, padx=6, pady=2)
                bg, fg = cat_module.get_color(cat, self.categories, self.dark_mode, self.category_colors)
                tk.Label(row, text=cat, bg=bg, fg=fg,
                         font=("TkDefaultFont", 9, "bold"),
                         padx=8, pady=2).pack(side=tk.LEFT)
                if cat != "General":
                    def make_delete(c=cat):
                        def do():
                            self.categories.remove(c)
                            # Re-assign tasks in that category to General
                            for task in self.manager.tasks:
                                if getattr(task, "category", "General") == c:
                                    task.category = "General"
                            self.save_ui_config()
                            self._build_category_filter_buttons()
                            rebuild_list()
                            self.refresh_tasks()
                        return do
                    tk.Button(row, text="✕", relief="flat", cursor="hand2",
                              bg=t["surface2"], fg=t["muted_fg"],
                              font=("TkDefaultFont", 8),
                              command=make_delete()).pack(side=tk.RIGHT)

        rebuild_list()

        # Add new category
        add_frame = tk.Frame(top, bg=t["bg"])
        add_frame.pack(fill=tk.X, padx=14, pady=8)
        new_entry = self._entry(add_frame, t, width=20)
        new_entry.pack(side=tk.LEFT, padx=(0, 6), ipady=4)

        def add_category():
            name = new_entry.get().strip()
            if not name or name in self.categories:
                return
            self.categories.append(name)
            new_entry.delete(0, tk.END)
            self.save_ui_config()
            self._build_category_filter_buttons()
            rebuild_list()

        self._btn(add_frame, t, "Add", add_category, primary=True).pack(side=tk.LEFT)
        new_entry.bind("<Return>", lambda e: add_category())

        self._btn(top, t, "Done", top.destroy).pack(pady=(0, 12))

    # ═══════════════════════════════════════════════
    #  TASK ACTIONS
    # ═══════════════════════════════════════════════

    def add_task_gui(self):
        top = self._make_dialog("Add Task")
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # Footer MUST be packed before the form frame (pack reserves bottom space first)
        tk.Frame(top, height=1, bg=t["border"]).pack(side=tk.BOTTOM, fill=tk.X)
        foot_add = tk.Frame(top, bg=t["surface"], height=64)
        foot_add.pack(side=tk.BOTTOM, fill=tk.X)
        foot_add.pack_propagate(False)

        # Form in its own frame so grid and pack don't conflict on `top`
        form = tk.Frame(top, bg=t["bg"])
        form.pack(fill=tk.BOTH, expand=True)

        tk.Label(form, text="Task Name:", **self._lbl(t)).grid(row=0, column=0, sticky="e", padx=10, pady=8)
        name_entry = self._entry(form, t, width=38)
        name_entry.grid(row=0, column=1, padx=10, pady=8)
        name_entry.focus_set()

        tk.Label(form, text="Description:", **self._lbl(t)).grid(row=1, column=0, sticky="e", padx=10, pady=8)
        desc_entry = self._entry(form, t, width=38)
        desc_entry.grid(row=1, column=1, padx=10, pady=8)

        tk.Label(form, text="Category:", **self._lbl(t)).grid(row=2, column=0, sticky="e", padx=10, pady=8)
        cat_var = tk.StringVar(value=self._category_filter or "General")
        cat_menu = tk.OptionMenu(form, cat_var, *self.categories)
        cat_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        cat_menu.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        tk.Label(form, text="Priority:", **self._lbl(t)).grid(row=3, column=0, sticky="e", padx=10, pady=8)
        priority_var = tk.StringVar(value="⚡ Medium")
        priority_menu = tk.OptionMenu(form, priority_var, "🔥 High", "⚡ Medium", "🌿 Low")
        priority_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        priority_menu.grid(row=3, column=1, sticky="w", padx=10, pady=8)

        tk.Label(form, text="Due Date:", **self._lbl(t)).grid(row=4, column=0, sticky="ne", padx=10, pady=8)
        due_var = tk.StringVar()
        cal = Calendar(form, selectmode="day", date_pattern="yyyy-mm-dd")
        cal.grid(row=4, column=1, padx=10, pady=8)

        due_lbl = tk.Label(form, text="No date selected", font=("TkDefaultFont", 10), bg=t["bg"], fg=t["muted_fg"])
        due_lbl.grid(row=5, column=1, sticky="w", padx=10)

        def select_due():
            due_var.set(cal.get_date())
            due_lbl.configure(text=f"Selected: {due_var.get()}")

        self._btn(form, t, "Select Date", select_due).grid(row=5, column=0, sticky="e", padx=10, pady=4)

        def confirm():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Task must have a name!", parent=top)
                return
            task = self.manager.add_task(
                name,
                desc_entry.get().strip(),
                due_var.get() or None,
                priority_var.get().split()[-1]
            )
            if task:
                task.category = cat_var.get()
            elif self.manager.tasks:
                task = self.manager.tasks[-1]
                task.category = cat_var.get()
            if task and task in self.manager.tasks:
                self.manager.tasks.remove(task)
            if task:
                cmd = AddTaskCommand(self.manager, task)
                self.history.execute(cmd)
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            save_tasks(self.manager, self.username)
            top.destroy()

        tk.Button(
            foot_add, text="✚  Add Task", command=confirm,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 12, "bold"),
        ).place(x=14, y=10, relwidth=1.0, width=-28, height=44)

    def edit_task_gui(self):
        selected_item = self.task_tree.selection()
        if not selected_item:
            messagebox.showinfo("Edit Task", "Select a task to edit.")
            return

        task_index = self.task_tree.index(selected_item[0])
        task_to_edit = self.get_sorted_tasks()[task_index]

        top = self._make_dialog("Edit Task")
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # Footer MUST be packed before the form frame (pack reserves bottom space first)
        tk.Frame(top, height=1, bg=t["border"]).pack(side=tk.BOTTOM, fill=tk.X)
        foot = tk.Frame(top, bg=t["surface"], height=64)
        foot.pack(side=tk.BOTTOM, fill=tk.X)
        foot.pack_propagate(False)

        # Form in its own frame so grid and pack don't conflict on `top`
        form = tk.Frame(top, bg=t["bg"])
        form.pack(fill=tk.BOTH, expand=True)

        tk.Label(form, text="Task Name:", **self._lbl(t)).grid(row=0, column=0, sticky="e", padx=10, pady=8)
        name_entry = self._entry(form, t, width=38)
        name_entry.insert(0, task_to_edit.name)
        name_entry.grid(row=0, column=1, padx=10, pady=8)

        tk.Label(form, text="Description:", **self._lbl(t)).grid(row=1, column=0, sticky="e", padx=10, pady=8)
        desc_entry = self._entry(form, t, width=38)
        desc_entry.insert(0, task_to_edit.description)
        desc_entry.grid(row=1, column=1, padx=10, pady=8)

        tk.Label(form, text="Category:", **self._lbl(t)).grid(row=2, column=0, sticky="e", padx=10, pady=8)
        current_cat = getattr(task_to_edit, "category", "General")
        cat_var = tk.StringVar(value=current_cat)
        cat_menu = tk.OptionMenu(form, cat_var, *self.categories)
        cat_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        cat_menu.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        tk.Label(form, text="Priority:", **self._lbl(t)).grid(row=3, column=0, sticky="e", padx=10, pady=8)
        priority_var = tk.StringVar(value=PRIORITY_ICONS.get(task_to_edit.priority, task_to_edit.priority))
        priority_menu = tk.OptionMenu(form, priority_var, "🔥 High", "⚡ Medium", "🌿 Low")
        priority_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        priority_menu.grid(row=3, column=1, sticky="w", padx=10, pady=8)

        tk.Label(form, text="Due Date:", **self._lbl(t)).grid(row=4, column=0, sticky="ne", padx=10, pady=8)
        init_date = task_to_edit.due_date if task_to_edit.due_date else datetime.now().date()
        cal = Calendar(
            form, selectmode="day",
            year=init_date.year, month=init_date.month, day=init_date.day,
            date_pattern="yyyy-mm-dd"
        )
        cal.grid(row=4, column=1, padx=10, pady=8)

        due_var = tk.StringVar(value=task_to_edit.due_date.strftime("%Y-%m-%d") if task_to_edit.due_date else "")
        due_lbl = tk.Label(
            form,
            text=f"Selected: {due_var.get()}" if due_var.get() else "No date selected",
            font=("TkDefaultFont", 10), bg=t["bg"], fg=t["muted_fg"]
        )
        due_lbl.grid(row=5, column=1, sticky="w", padx=10)

        def select_due():
            due_var.set(cal.get_date())
            due_lbl.configure(text=f"Selected: {due_var.get()}")

        self._btn(form, t, "Select Date", select_due).grid(row=5, column=0, sticky="e", padx=10, pady=4)

        before_snap = snapshot(task_to_edit)

        def confirm():
            new_due_str = cal.get_date()
            after_snap = {
                "name":        name_entry.get().strip(),
                "description": desc_entry.get().strip(),
                "category":    cat_var.get(),
                "priority":    priority_var.get().split()[-1],
                "due_date":    datetime.strptime(new_due_str, "%Y-%m-%d").date() if new_due_str else None,
                "done":        task_to_edit.done,
            }
            cmd = EditTaskCommand(task_to_edit, before_snap, after_snap)
            self.history.execute(cmd)
            task_to_edit.update_status()
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            save_tasks(self.manager, self.username)
            top.destroy()

        tk.Button(
            foot, text="💾  Save Changes", command=confirm,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 12, "bold"),
        ).place(x=14, y=10, relwidth=1.0, width=-28, height=44)
        self.root.wait_window(top)

    def delete_task_gui(self):
        selected = self.task_tree.selection()
        if not selected:
            return
        task = self.get_task_from_selection(selected[0])
        if task:
            cmd = DeleteTaskCommand(self.manager, task)
            self.history.execute(cmd)
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            save_tasks(self.manager, self.username)

    def mark_done_gui(self):
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showinfo("Mark Done", "Select a task to mark done.")
            return
        task = self.get_task_from_selection(selected[0])
        if task:
            cmd = MarkDoneCommand(task, task.done)
            self.history.execute(cmd)
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            save_tasks(self.manager, self.username)

    # ═══════════════════════════════════════════════
    #  DIALOG WIDGET HELPERS
    # ═══════════════════════════════════════════════

    def _make_dialog(self, title):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        top = tk.Toplevel(self.root)
        top.title(title)
        top.configure(bg=t["bg"])
        top.grab_set()
        top.resizable(False, False)
        return top

    def _lbl(self, t):
        return {"bg": t["bg"], "fg": t["fg"], "font": ("TkDefaultFont", 11)}

    def _entry(self, parent, t, width=30):
        return tk.Entry(
            parent, width=width, relief="flat",
            bg=t["entry_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            font=("TkDefaultFont", 11),
            highlightthickness=1,
            highlightbackground=t["border"],
            highlightcolor=t["accent"]
        )

    def _btn(self, parent, t, text, cmd, primary=False):
        if primary:
            return tk.Button(
                parent, text=text, command=cmd, relief="flat", cursor="hand2",
                bg=t["accent"], fg=t["accent_fg"],
                activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
                font=("TkDefaultFont", 11, "bold"), padx=20, pady=8
            )
        return tk.Button(
            parent, text=text, command=cmd, relief="flat", cursor="hand2",
            bg=t["secondary_btn_bg"], fg=t["secondary_btn_fg"],
            activebackground=t["border"],
            font=("TkDefaultFont", 10), padx=12, pady=6
        )

    # ═══════════════════════════════════════════════
    #  FILTERING & SORTING
    # ═══════════════════════════════════════════════

    def _sort_by_column(self, col):
        """Called when a column header is clicked — toggles asc/desc."""
        sort_key = self._col_sort_map.get(col, "alphabetical")
        if self.sort_type.get() == sort_key:
            self.sort_reverse = not self.sort_reverse   # flip direction
        else:
            self.sort_type.set(sort_key)
            self.sort_reverse = False                   # reset to asc on new column
        self._update_sort_buttons()
        self.refresh_tasks()

    # ═══════════════════════════════════════════════
    #  CALENDAR SIDEBAR
    # ═══════════════════════════════════════════════

    def _on_calendar_day_click(self, event):
        """Filter task list to the selected day."""
        date_str = self.mini_cal.get_date()          # "yyyy-mm-dd"
        try:
            self._calendar_date_filter = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            self._calendar_date_filter = None
        self.refresh_tasks()

    def _calendar_reset(self):
        """Clear the calendar day filter and show all tasks."""
        self._calendar_date_filter = None
        self.refresh_tasks()

    def refresh_calendar(self):
        """Re-draw task-day markers on the mini calendar."""
        # Remove all existing events
        for ev_id in self.mini_cal.get_calevents():
            self.mini_cal.calevent_remove(ev_id)

        today = datetime.now().date()
        for task in self.manager.tasks:
            if not task.due_date:
                continue
            due = task.due_date if not isinstance(task.due_date, str) else \
                  datetime.strptime(task.due_date, "%Y-%m-%d").date()
            if task.done:
                tag = "done"
            elif due < today:
                tag = "overdue"
            elif task.priority == "High":
                tag = "high"
            else:
                tag = "normal"
            self.mini_cal.calevent_create(due, task.name, tag)

        # Style the tags on the calendar
        if self.dark_mode:
            self.mini_cal.tag_config("done",    background="#3A3F4B", foreground="#6EE7A0")
            self.mini_cal.tag_config("overdue", background="#3D1A1A", foreground="#F87171")
            self.mini_cal.tag_config("high",    background="#3D2A1A", foreground="#FCD34D")
            self.mini_cal.tag_config("normal",  background="#1A2E3D", foreground="#93C5FD")
        else:
            self.mini_cal.tag_config("done",    background="#D1FAE5", foreground="#065F46")
            self.mini_cal.tag_config("overdue", background="#FEE2E2", foreground="#991B1B")
            self.mini_cal.tag_config("high",    background="#FEF3C7", foreground="#92400E")
            self.mini_cal.tag_config("normal",  background="#DBEAFE", foreground="#1E40AF")
        # Re-bind tooltips after calendar redraws (150ms lets tkcalendar finish rendering)
        self.mini_cal.after(150, self._bind_cal_day_tooltips)

    # ═══════════════════════════════════════════════
    #  CALENDAR TOOLTIP
    # ═══════════════════════════════════════════════

    def _bind_nav_buttons(self):
        """Attach rebind triggers to the four month/year navigation buttons."""
        for btn in [self.mini_cal._l_month, self.mini_cal._r_month,
                    self.mini_cal._l_year,  self.mini_cal._r_year]:
            btn.bind("<ButtonRelease-1>",
                     lambda e: self.mini_cal.after(150, self._bind_cal_day_tooltips),
                     add="+")

    def _bind_cal_day_tooltips(self):
        """
        Bind <Enter>/<Leave> on each day cell in mini_cal._calendar (a 6x7 grid
        of ttk.Label widgets). Uses calendar.monthcalendar to map each cell to
        an exact date — cells that belong to prev/next month get 0 and are skipped.
        """
        import calendar as cal_lib
        from datetime import date as dt_date

        cal   = self.mini_cal
        year  = cal._date.year
        month = cal._date.month

        # monthcalendar: list of 6 (or 5) weeks; 0 means day is outside this month
        weeks = cal_lib.monthcalendar(year, month)
        while len(weeks) < 6:          # pad to 6 rows to match _calendar
            weeks.append([0] * 7)

        for row_idx, (row_labels, week_days) in enumerate(zip(cal._calendar, weeks)):
            for col_idx, (label, day_num) in enumerate(zip(row_labels, week_days)):
                # Remove any previous bindings first
                label.unbind("<Enter>")
                label.unbind("<Leave>")
                if day_num == 0:
                    continue           # other-month greyed cell — skip
                cell_date = dt_date(year, month, day_num)
                label.bind("<Enter>",
                           lambda e, d=cell_date: self._on_cal_day_enter(e, d))
                label.bind("<Leave>",
                           lambda e: self._on_cal_day_leave(e))

    def _on_cal_day_enter(self, event, cell_date):
        if cell_date == self._cal_tooltip_date:
            return                     # already showing this day
        self._hide_cal_tooltip()
        tasks_on_day = [
            t for t in self.manager.tasks
            if t.due_date and t.due_date == cell_date
        ]
        if not tasks_on_day:
            return
        self._cal_tooltip_date = cell_date
        self._show_cal_tooltip(event, tasks_on_day)

    def _on_cal_day_leave(self, event):
        self._hide_cal_tooltip()

    def _on_cal_hover(self, event):
        pass   # kept so old bind("<Motion>") call is harmless

    def _on_cal_leave(self, event):
        self._hide_cal_tooltip()

    def _show_cal_tooltip(self, event, tasks):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        win = tk.Toplevel(self.root)
        win.wm_overrideredirect(True)          # borderless
        win.attributes("-topmost", True)
        win.configure(bg=t["border"])          # 1px border via bg bleed

        inner = tk.Frame(win, bg=t["surface2"], padx=10, pady=8)
        inner.pack(padx=1, pady=1)             # 1px gap = border illusion

        for i, task in enumerate(tasks):
            if i > 0:
                tk.Frame(inner, height=1, bg=t["border"]).pack(fill=tk.X, pady=4)

            icon = {"High": "🔥", "Medium": "⚡", "Low": "🌿"}.get(task.priority, "•")
            cat  = getattr(task, "category", "General")
            done_prefix = "✅ " if task.done else ""

            # Task name row
            name_row = tk.Frame(inner, bg=t["surface2"])
            name_row.pack(fill=tk.X)
            tk.Label(
                name_row,
                text=f"{done_prefix}{icon}  {task.name}",
                bg=t["surface2"], fg=t["fg"],
                font=("TkDefaultFont", 9, "bold"),
                anchor="w"
            ).pack(side=tk.LEFT)

            # Category badge
            from core import categories as cat_module
            bg_cat, fg_cat = cat_module.get_color(cat, self.categories, self.dark_mode, self.category_colors)
            tk.Label(
                name_row,
                text=f" {cat} ",
                bg=bg_cat, fg=fg_cat,
                font=("TkDefaultFont", 7, "bold"),
                padx=3, pady=1
            ).pack(side=tk.RIGHT, padx=(6, 0))

            # Description (if any)
            if task.description:
                tk.Label(
                    inner,
                    text=task.description,
                    bg=t["surface2"], fg=t["muted_fg"],
                    font=("TkDefaultFont", 8),
                    anchor="w", justify="left",
                    wraplength=200
                ).pack(fill=tk.X, pady=(2, 0))

        # Give the window an off-screen position first, render it, then move it
        win.geometry("+9999+9999")
        win.update_idletasks()               # forces Tk to compute actual size

        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()

        x = event.x_root + 14
        y = event.y_root + 10
        if x + w > sw:
            x = event.x_root - w - 6
        if y + h > sh:
            y = event.y_root - h - 6

        win.geometry(f"+{x}+{y}")
        self._cal_tooltip_win = win

    def _hide_cal_tooltip(self):
        if self._cal_tooltip_win:
            try:
                self._cal_tooltip_win.destroy()
            except Exception:
                pass
            self._cal_tooltip_win = None
        self._cal_tooltip_date = None

    # ═══════════════════════════════════════════════
    #  HOVER
    # ═══════════════════════════════════════════════

    def _on_tree_hover(self, event):
        row_id = self.task_tree.identify_row(event.y)
        if row_id == self._hovered_row:
            return
        # Clear previous hover tag
        if self._hovered_row and self.task_tree.exists(self._hovered_row):
            current_tags = list(self.task_tree.item(self._hovered_row, "tags"))
            current_tags = [t for t in current_tags if t != "hover"]
            self.task_tree.item(self._hovered_row, tags=current_tags)
        # Apply hover tag to new row
        self._hovered_row = row_id
        if row_id:
            current_tags = list(self.task_tree.item(row_id, "tags"))
            if "hover" not in current_tags:
                self.task_tree.item(row_id, tags=current_tags + ["hover"])

    def _on_tree_leave(self, event):
        if self._hovered_row and self.task_tree.exists(self._hovered_row):
            current_tags = list(self.task_tree.item(self._hovered_row, "tags"))
            current_tags = [t for t in current_tags if t != "hover"]
            self.task_tree.item(self._hovered_row, tags=current_tags)
        self._hovered_row = None

    def _on_tree_click(self, event):
        """Toggle task done/undone when the checkbox (Done) column is clicked."""
        region = self.task_tree.identify_region(event.x, event.y)
        col    = self.task_tree.identify_column(event.x)
        row_id = self.task_tree.identify_row(event.y)

        if region == "cell" and col == "#1" and row_id:
            task = self.get_task_from_selection(row_id)
            if task:
                cmd = ToggleDoneCommand(task)
                self.history.execute(cmd)
                self.refresh_tasks()
                self._update_undo_redo_buttons()
                save_tasks(self.manager, self.username)
            return "break"   # prevent default selection behaviour on this column

    def get_task_from_selection(self, item_id):
        # Done is now col 0; Name is col 1
        name = self.task_tree.item(item_id, "values")[1]
        for task in self.manager.tasks:
            if task.name == name:
                return task
        return None

    def get_filtered_tasks(self):
        tasks = logic.get_filtered_tasks(
            self.manager.tasks,
            self.filter_type.get(),
            self.search_var.get(),
            self._calendar_date_filter,
        )
        if self._category_filter:
            tasks = [t for t in tasks if getattr(t, "category", "General") == self._category_filter]
        return tasks

    def get_sorted_tasks(self):
        return logic.get_sorted_tasks(
            self.get_filtered_tasks(),
            self.sort_type.get(),
            self.sort_reverse,
        )

    @staticmethod
    def _days_info(task):
        return logic.days_info(task)

    # ═══════════════════════════════════════════════
    #  REFRESH
    # ═══════════════════════════════════════════════

    def refresh_tasks(self):
        if hasattr(self, "_reminder_svc"):
            self._reminder_svc.reset_fired()
        for row in self.task_tree.get_children():
            self.task_tree.delete(row)

        tasks = self.get_sorted_tasks()
        total     = len(self.manager.tasks)
        done      = sum(1 for t in self.manager.tasks if t.done)
        remaining = total - done
        self.count_label.configure(text=f"{remaining} remaining · {done} done")

        for t in tasks:
            if isinstance(t.due_date, str):
                t.due_date = datetime.strptime(t.due_date, "%Y-%m-%d").date() if t.due_date else None

            due_str   = t.due_date.strftime("%Y-%m-%d") if t.due_date else "—"
            days_info = "" if t.done else self._days_info(t)
            checkbox  = "☑" if t.done else "☐"

            category = getattr(t, "category", "General")
            row_id = self.task_tree.insert(
                "", tk.END,
                values=(checkbox, t.name, category, PRIORITY_ICONS.get(t.priority, t.priority), due_str, days_info, t.description)
            )

            if t.done:
                self.task_tree.item(row_id, tags=("done",))
            elif t.due_date and t.due_date < datetime.now().date():
                self.task_tree.item(row_id, tags=("overdue",))
            elif t.priority == "High":
                self.task_tree.item(row_id, tags=("high",))
            elif t.priority == "Medium":
                self.task_tree.item(row_id, tags=("medium",))
            else:
                self.task_tree.item(row_id, tags=("low",))

        self._configure_tags()

        # Update column headers with sort direction arrow
        active_sort = self.sort_type.get()
        arrow = "  ▼" if self.sort_reverse else "  ▲"
        for col, sort_key in self._col_sort_map.items():
            label = col + (arrow if sort_key == active_sort else "")
            self.task_tree.heading(col, text=label,
                                   command=lambda c=col: self._sort_by_column(c))

        # Sync calendar markers, dashboard stats, and tray
        self.refresh_calendar()
        self.refresh_stats()
        self.root.after(0, self._refresh_tray)

    def refresh_stats(self):
        """Recalculate all dashboard stat values and redraw the progress bar."""
        from datetime import date, timedelta
        today = date.today()
        week_end = today + timedelta(days=7)
        all_tasks = self.manager.tasks

        total   = len(all_tasks)
        done    = sum(1 for t in all_tasks if t.done)
        active  = total - done
        overdue = sum(
            1 for t in all_tasks
            if not t.done and t.due_date and t.due_date < today
        )
        due_today = sum(
            1 for t in all_tasks
            if t.due_date and not t.done and t.due_date == today
        )
        due_week  = sum(
            1 for t in all_tasks
            if t.due_date and not t.done and today <= t.due_date <= week_end
        )
        pct = int(done / total * 100) if total else 0

        # Update stat value labels
        values = {
            "total":   str(total),
            "active":  str(active),
            "done":    str(done),
            "overdue": str(overdue) if overdue == 0 else f"⚠ {overdue}",
            "today":   str(due_today),
            "week":    str(due_week),
        }
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        for key, (row, lbl, val) in self._stat_widgets.items():
            val.configure(text=values[key])
            # Highlight overdue count in red if non-zero
            if key == "overdue" and overdue > 0:
                val.configure(fg="#F87171" if self.dark_mode else "#DC2626")
            elif key == "today" and due_today > 0:
                val.configure(fg=t["accent"])
            else:
                val.configure(fg=t["fg"])

        # Progress bar
        self.progress_pct_label.configure(text=f"{pct}%")
        self.progress_canvas.update_idletasks()
        w = self.progress_canvas.winfo_width() or 180
        self.progress_canvas.delete("all")
        # Track
        self.progress_canvas.create_rectangle(
            0, 0, w, 6, fill=t["border"], outline="", width=0
        )
        # Fill
        if pct > 0:
            fill_color = t["accent"] if pct < 100 else "#4ADE80"
            self.progress_canvas.create_rectangle(
                0, 0, int(w * pct / 100), 6,
                fill=fill_color, outline="", width=0
            )
        self.refresh_heatmap()

    def refresh_heatmap(self):
        """Redraw the GitHub-style activity heatmap (last ~3 months, by due date)."""
        from datetime import date, timedelta
        from collections import defaultdict

        WEEKS    = 17
        DAYS     =  7
        CELL     =  9
        GAP      =  1
        LEFT_PAD = 14
        TOP_PAD  = 14

        t      = DARK_THEME if self.dark_mode else LIGHT_THEME
        canvas = self.heatmap_canvas
        canvas.delete("all")

        today       = date.today()
        # Anchor: Monday of current week is the start of the last column
        this_monday = today - timedelta(days=today.weekday())
        grid_origin = this_monday - timedelta(weeks=WEEKS - 1)   # always exactly 13 cols
        start_date  = grid_origin
        total_cols  = WEEKS   # always exactly 13

        # ── Count tasks per due date ──────────────────
        day_counts: dict = defaultdict(int)
        for task in self.manager.tasks:
            if task.due_date:
                try:
                    d = task.due_date
                    if start_date <= d <= today:
                        day_counts[d] += 1
                except (TypeError, AttributeError):
                    pass

        max_count = max(day_counts.values(), default=1)

        # ── Colour scale (4 shades + empty) ──────────
        if self.dark_mode:
            EMPTY  = "#1C1F26"
            SHADES = ["#0F3D20", "#1A6B38", "#25A055", "#2ECC6B"]
        else:
            EMPTY  = "#ECEAE6"
            SHADES = ["#C6E9D4", "#7BC99A", "#3AA865", "#1E7D44"]

        def _shade(count):
            if count == 0:
                return EMPTY
            ratio = count / max_count
            idx   = min(int(ratio * len(SHADES)), len(SHADES) - 1)
            return SHADES[idx]

        # ── Day-of-week labels (Mon Wed Fri) ──────────
        DAY_LABELS = {0: "M", 2: "W", 4: "F"}
        for dow, lbl in DAY_LABELS.items():
            y = TOP_PAD + dow * (CELL + GAP) + CELL // 2
            canvas.create_text(
                LEFT_PAD - 4, y,
                text=lbl, anchor="e",
                font=("TkDefaultFont", 7),
                fill=t["muted_fg"]
            )

        # ── Draw cells ────────────────────────────────
        month_labels = {}
        cell_meta    = {}

        for week_idx in range(total_cols):
            for dow in range(DAYS):
                d = grid_origin + timedelta(weeks=week_idx, days=dow)
                if d < start_date or d > today:
                    continue   # skip days outside our window

                x1 = LEFT_PAD + week_idx * (CELL + GAP)
                y1 = TOP_PAD  + dow      * (CELL + GAP)
                x2, y2 = x1 + CELL, y1 + CELL

                color = _shade(day_counts.get(d, 0))
                item_id = canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=color, outline="", width=0,
                )
                cell_meta[item_id] = (d, day_counts.get(d, 0))

                # Month label on first Monday-ish of each month
                if dow == 0 and d.day <= 7:
                    month_labels[x1] = d.strftime("%b")

        # ── Month labels along the top ─────────────────
        for x, label in month_labels.items():
            canvas.create_text(
                x, TOP_PAD - 4,
                text=label, anchor="sw",
                font=("TkDefaultFont", 7),
                fill=t["muted_fg"]
            )

        # ── Date range label ──────────────────────────
        self.heatmap_range_lbl.configure(
            text=f"{start_date.strftime('%d %b')} – {today.strftime('%d %b %Y')}",
            bg=t["bg"], fg=t["muted_fg"]
        )

        # ── Tooltip: track current hovered item id ────
        tip      = self._heatmap_tip
        tip["last_id"] = None   # last item id that triggered a tooltip

        def _show_tip(item_id, ex, ey):
            """Destroy old tip, create new one for item_id."""
            if tip["win"]:
                try:    tip["win"].destroy()
                except: pass
                tip["win"] = None

            d, count = cell_meta[item_id]
            label = d.strftime("%d %B %Y")
            msg   = f"{label}\n{'No activity' if count == 0 else f'{count} task' + ('' if count == 1 else 's')}"

            th = DARK_THEME if self.dark_mode else LIGHT_THEME
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=th["border"])
            tk.Label(
                win, text=msg,
                bg=th["surface2"], fg=th["fg"],
                font=("TkDefaultFont", 9),
                justify="center", padx=10, pady=6
            ).pack(padx=1, pady=1)
            win.update_idletasks()
            wx = canvas.winfo_rootx() + ex + 12
            wy = canvas.winfo_rooty() + ey - win.winfo_reqheight() - 4
            win.geometry(f"+{wx}+{wy}")
            tip["win"] = win

        def _on_motion(e):
            item = canvas.find_closest(e.x, e.y)
            if not item:
                return
            iid = item[0]
            if iid not in cell_meta:
                # Hovering over a label/text — hide tip
                if tip["win"]:
                    try:    tip["win"].destroy()
                    except: pass
                    tip["win"] = None
                tip["last_id"] = None
                return
            if iid == tip["last_id"]:
                return   # same cell, don't recreate
            tip["last_id"] = iid
            _show_tip(iid, e.x, e.y)

        def _on_leave(e):
            if tip["win"]:
                try:    tip["win"].destroy()
                except: pass
                tip["win"] = None
            tip["last_id"] = None

        canvas.bind("<Motion>", _on_motion)
        canvas.bind("<Leave>",  _on_leave)

    def _shortcut_delete(self):
        """Delete only when the task tree has focus (not while typing)."""
        focused = self.root.focus_get()
        if focused == self.task_tree:
            self.delete_task_gui()

    def _shortcut_escape(self):
        """Escape: clear search, then clear category/calendar filters."""
        if self.search_var.get():
            self.search_var.set("")
            return
        if self._category_filter:
            self._set_category_filter(None)
            return
        if self._calendar_date_filter:
            self._calendar_reset()

    def _focus_search(self):
        """Ctrl+F: focus the search box and select all."""
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)

    def _select_first_task(self):
        children = self.task_tree.get_children()
        if children:
            self.task_tree.selection_set(children[0])
            self.task_tree.focus(children[0])
            self.task_tree.see(children[0])

    def _select_last_task(self):
        children = self.task_tree.get_children()
        if children:
            self.task_tree.selection_set(children[-1])
            self.task_tree.focus(children[-1])
            self.task_tree.see(children[-1])

    def _show_shortcuts_help(self):
        """Show a floating keyboard shortcuts reference card."""
        # Don't open if a dialog is already showing shortcuts
        for w in self.root.winfo_children():
            if isinstance(w, tk.Toplevel) and getattr(w, "_is_shortcuts_help", False):
                w.lift()
                return

        top = self._make_dialog("Keyboard Shortcuts")
        top._is_shortcuts_help = True
        top.resizable(False, False)
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        SHORTCUTS = [
            ("TASKS", [
                ("Ctrl + N",     "New task"),
                ("Ctrl + E",     "Edit selected task"),
                ("Delete",       "Delete selected task"),
                ("Ctrl + D",     "Mark selected task done"),
                ("Double-click", "Edit task"),
            ]),
            ("UNDO / REDO", [
                ("Ctrl + Z",     "Undo"),
                ("Ctrl + Y",     "Redo"),
                ("Ctrl + Shift + Z", "Redo"),
            ]),
            ("NAVIGATION", [
                ("Ctrl + F",     "Focus search box"),
                ("Escape",       "Clear search / filters"),
                ("Ctrl + Home",  "Select first task"),
                ("Ctrl + End",   "Select last task"),
            ]),
            ("VIEW", [
                ("Ctrl + T",     "Toggle dark / light mode"),
                ("Ctrl + ,",     "Open Settings"),
                ("?",            "Show this help"),
            ]),
        ]

        # ── Header ────────────────────────────────────────
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⌨️  Keyboard Shortcuts",
                 font=("Georgia", 13, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=18, pady=(14, 12))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        body = tk.Frame(top, bg=t["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=12)

        for section_title, rows in SHORTCUTS:
            # Section heading
            tk.Label(body, text=section_title,
                     font=("TkDefaultFont", 8, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(12, 3))
            tk.Frame(body, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 6))

            for keys, desc in rows:
                row = tk.Frame(body, bg=t["bg"])
                row.pack(fill=tk.X, pady=2)

                # Key badge(s)
                badge = tk.Label(
                    row, text=keys,
                    font=("TkDefaultFont", 9, "bold"),
                    bg=t["surface2"], fg=t["fg"],
                    padx=8, pady=3,
                    relief="flat",
                    highlightthickness=1,
                    highlightbackground=t["border"],
                )
                badge.pack(side=tk.LEFT)

                tk.Label(row, text=desc,
                         font=("TkDefaultFont", 10),
                         bg=t["bg"], fg=t["fg"],
                         anchor="w").pack(side=tk.LEFT, padx=(10, 0))

        # ── Footer ────────────────────────────────────────
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X, side=tk.BOTTOM)
        foot = tk.Frame(top, bg=t["surface"], height=56)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        tk.Button(
            foot, text="Close", command=top.destroy,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 11, "bold"),
        ).place(x=14, y=8, relwidth=1.0, width=-28, height=40)

        top.bind("<Escape>", lambda e: top.destroy())

        # Size to content
        top.update_idletasks()
        top.geometry(f"380x{top.winfo_reqheight() + 20}")

    # ═══════════════════════════════════════════════
    #  UNDO / REDO
    # ═══════════════════════════════════════════════

    def undo_action(self):
        desc = self.history.undo()
        if desc:
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            save_tasks(self.manager, self.username)

    def redo_action(self):
        desc = self.history.redo()
        if desc:
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            save_tasks(self.manager, self.username)

    def _update_undo_redo_buttons(self):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        can_undo = self.history.can_undo()
        can_redo = self.history.can_redo()

        self.undo_btn.configure(
            text="↩  Undo",
            state="normal" if can_undo else "disabled",
            fg=t["secondary_btn_fg"] if can_undo else t["muted_fg"],
        )
        self.redo_btn.configure(
            text="↪  Redo",
            state="normal" if can_redo else "disabled",
            fg=t["secondary_btn_fg"] if can_redo else t["muted_fg"],
        )
        # Bind live tooltips showing the exact action name
        self._bind_tooltip(self.undo_btn,
            lambda: self.history.undo_label() if self.history.can_undo() else "")
        self._bind_tooltip(self.redo_btn,
            lambda: self.history.redo_label() if self.history.can_redo() else "")

    def auto_save(self):
        save_tasks(self.manager, self.username)
        self.save_ui_config()   # persists geometry on every auto-save tick
        self.root.after(10000, self.auto_save)

    # ═══════════════════════════════════════════════
    #  SYSTEM TRAY
    # ═══════════════════════════════════════════════

    def _make_tray_image(self, size=64):
        """Draw a simple checklist icon as the tray image."""
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        t    = DARK_THEME if self.dark_mode else LIGHT_THEME

        # Background circle
        accent = t["accent"]
        r, g, b = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
        draw.ellipse([2, 2, size - 2, size - 2], fill=(r, g, b, 255))

        # Checkmark lines
        s = size / 64
        draw.line([(18*s, 34*s), (27*s, 44*s), (46*s, 20*s)],
                  fill=(255, 255, 255, 255), width=max(1, int(6*s)))
        return img

    def _build_tray_menu(self):
        """Build the right-click context menu shown on the tray icon."""
        from datetime import date as _date
        _today  = _date.today()
        total   = len(self.manager.tasks)
        done    = sum(1 for t in self.manager.tasks if t.done)
        overdue = sum(1 for t in self.manager.tasks
                      if not t.done and t.due_date and t.due_date < _today)
        label   = f"{total - done} active  •  {overdue} overdue"

        return pystray.Menu(
            pystray.MenuItem(label,           None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show window",   self._tray_show),
            pystray.MenuItem("Add task",      self._tray_add_task),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",          self._tray_quit),
        )

    def _start_tray(self):
        """Create and start the tray icon in a daemon thread."""
        if not TRAY_AVAILABLE or self._tray_icon:
            return
        import threading
        icon = pystray.Icon(
            "MyTasks",
            self._make_tray_image(),
            "My Tasks",
            menu=self._build_tray_menu(),
        )
        self._tray_icon = icon
        threading.Thread(target=icon.run, daemon=True).start()

    def _refresh_tray(self):
        """Rebuild tray menu and icon after task changes."""
        if not self._tray_icon:
            return
        self._tray_icon.menu  = self._build_tray_menu()
        self._tray_icon.icon  = self._make_tray_image()
        self._tray_icon.title = "My Tasks"

    def _tray_show(self, icon=None, item=None):
        """Restore the window from tray."""
        self.root.after(0, self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _tray_add_task(self, icon=None, item=None):
        """Open Add Task dialog from the tray menu."""
        self.root.after(0, lambda: (self._show_window(), self.add_task_gui()))

    def _tray_quit(self, icon=None, item=None):
        """Fully quit — save state, stop tray, destroy window."""
        self.root.after(0, self.on_close)

    def _start_reminders(self):
        self._reminder_svc = ReminderService(
            self.root,
            lambda: list(self.manager.tasks),
            self.reminder_cfg,
        )
        self._reminder_svc.start()

    def _on_window_close(self):
        """Minimise to tray or quit depending on user preference."""
        if TRAY_AVAILABLE and self._tray_icon and self.minimize_to_tray:
            self.root.withdraw()
            self._refresh_tray()
        else:
            self.on_close()

    def on_close(self):
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        if hasattr(self, "_reminder_svc"):
            self._reminder_svc.stop()
        save_tasks(self.manager, self.username)
        self.save_ui_config()
        self.root.destroy()