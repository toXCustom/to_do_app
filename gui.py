import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
from tasks import TaskManager
from storage import save_tasks, load_tasks, save_config, load_config
from datetime import datetime
from tkcalendar import Calendar
import logic
import categories as cat_module

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
    def __init__(self, root):
        self.root = root
        self.root.title("My Tasks")
        self.root.minsize(720, 480)
        # Restore last window size/position, or use the default
        config = load_config()
        self.root.geometry(config.get("geometry", "900x620"))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Task manager
        self.manager = TaskManager()
        load_tasks(self.manager)

        # State
        config = load_config()
        self.dark_mode = config.get("dark_mode", False)
        self.sort_type = tk.StringVar(value=config.get("sort", "due_date"))
        self.sort_reverse = False          # ascending by default
        self.filter_type = tk.StringVar(value=config.get("filter", "All"))
        self._calendar_date_filter = None  # set when user clicks a calendar day
        self.categories = cat_module.load_categories(config)
        self._category_filter = None       # None = show all categories
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh_tasks())

        self._build_ui()
        self.apply_theme()
        self.refresh_tasks()
        self.auto_save()

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

        self.save_label = tk.Label(
            self.right_frame, text="● Auto-save on",
            font=("TkDefaultFont", 10)
        )
        self.save_label.pack(side=tk.LEFT, padx=(0, 14))

        self.theme_button = tk.Button(
            self.right_frame, text="🌙  Dark",
            command=self.toggle_theme,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.theme_button.pack(side=tk.LEFT)

        # ── Main content: sidebar + task list side by side ──
        self.content_frame = tk.Frame(self.root)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # ── Sidebar ──────────────────────────────────
        self.sidebar = tk.Frame(self.content_frame, width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0), pady=10)
        self.sidebar.pack_propagate(False)

        self.cal_label = tk.Label(
            self.sidebar, text="📅  Calendar",
            font=("TkDefaultFont", 10, "bold")
        )
        self.cal_label.pack(anchor="w", padx=6, pady=(0, 6))

        self.mini_cal = Calendar(
            self.sidebar,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            showweeknumbers=False,
            font=("TkDefaultFont", 9),
        )
        self.mini_cal.pack(fill=tk.X, padx=4)
        self.mini_cal.bind("<<CalendarSelected>>", self._on_calendar_day_click)

        # "Show all" link below the calendar
        self.cal_reset_btn = tk.Button(
            self.sidebar, text="Show all tasks",
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 9),
            command=self._calendar_reset
        )
        self.cal_reset_btn.pack(pady=(6, 0))

        # ── Dashboard Stats Panel ─────────────────────
        self.stats_sep = tk.Frame(self.sidebar, height=1)
        self.stats_sep.pack(fill=tk.X, padx=8, pady=(14, 0))

        self.stats_label = tk.Label(
            self.sidebar, text="📊  Stats",
            font=("TkDefaultFont", 10, "bold")
        )
        self.stats_label.pack(anchor="w", padx=10, pady=(8, 6))

        self.stats_frame = tk.Frame(self.sidebar)
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
        self.progress_frame = tk.Frame(self.sidebar)
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


        # ── Category Filter Panel ────────────────────
        self.cat_sep = tk.Frame(self.sidebar, height=1)
        self.cat_sep.pack(fill=tk.X, padx=8, pady=(12, 0))

        cat_header_row = tk.Frame(self.sidebar)
        cat_header_row.pack(fill=tk.X, padx=10, pady=(8, 4))

        self.cat_heading = tk.Label(
            cat_header_row, text="🏷  Categories",
            font=("TkDefaultFont", 10, "bold")
        )
        self.cat_heading.pack(side=tk.LEFT)

        self.manage_cat_btn = tk.Button(
            cat_header_row, text="＋ Manage",
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 8),
            command=self._manage_categories_gui
        )
        self.manage_cat_btn.pack(side=tk.RIGHT)

        self.cat_filter_frame = tk.Frame(self.sidebar)
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
            command=self.task_tree.yview
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

        # Category filter panel
        self.cat_sep.configure(bg=t["border"])
        self.cat_heading.configure(bg=t["bg"], fg=t["muted_fg"])
        cat_header_row = self.cat_heading.master
        cat_header_row.configure(bg=t["bg"])
        self.manage_cat_btn.configure(
            bg=t["bg"], fg=t["accent"],
            activebackground=t["bg"], activeforeground=t["accent_hover"]
        )
        self.cat_filter_frame.configure(bg=t["bg"])
        self._build_category_filter_buttons()

        # Footer
        for w in [self.footer_frame, self.action_frame, self.right_frame]:
            w.configure(bg=t["bg"])
        for btn in self.action_buttons:
            btn.configure(
                bg=t["secondary_btn_bg"], fg=t["secondary_btn_fg"],
                activebackground=t["border"],
                activeforeground=t["fg"]
            )
            self._bind_hover(btn, lambda: False,
                             rest_bg=t["secondary_btn_bg"], hover_bg=t["border"])
        self.save_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.theme_button.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"],
            activeforeground=t["fg"],
            text="☀  Light" if self.dark_mode else "🌙  Dark"
        )
        self._bind_hover(self.theme_button, lambda: False,
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
            arrowcolor=t["muted_fg"]
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
            "categories": self.categories,
        })

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
            bg, fg = cat_module.get_color(cat, self.categories, self.dark_mode)
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
                bg, fg = cat_module.get_color(cat, self.categories, self.dark_mode)
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

        tk.Label(top, text="Task Name:", **self._lbl(t)).grid(row=0, column=0, sticky="e", padx=10, pady=8)
        name_entry = self._entry(top, t, width=38)
        name_entry.grid(row=0, column=1, padx=10, pady=8)
        name_entry.focus_set()

        tk.Label(top, text="Description:", **self._lbl(t)).grid(row=1, column=0, sticky="e", padx=10, pady=8)
        desc_entry = self._entry(top, t, width=38)
        desc_entry.grid(row=1, column=1, padx=10, pady=8)

        tk.Label(top, text="Category:", **self._lbl(t)).grid(row=2, column=0, sticky="e", padx=10, pady=8)
        cat_var = tk.StringVar(value=self._category_filter or "General")
        cat_menu = tk.OptionMenu(top, cat_var, *self.categories)
        cat_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        cat_menu.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        tk.Label(top, text="Priority:", **self._lbl(t)).grid(row=3, column=0, sticky="e", padx=10, pady=8)
        priority_var = tk.StringVar(value="Medium")
        priority_menu = tk.OptionMenu(top, priority_var, "High", "Medium", "Low")
        priority_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        priority_menu.grid(row=3, column=1, sticky="w", padx=10, pady=8)

        tk.Label(top, text="Due Date:", **self._lbl(t)).grid(row=4, column=0, sticky="ne", padx=10, pady=8)
        due_var = tk.StringVar()
        cal = Calendar(top, selectmode="day", date_pattern="yyyy-mm-dd")
        cal.grid(row=4, column=1, padx=10, pady=8)

        due_lbl = tk.Label(top, text="No date selected", font=("TkDefaultFont", 10), bg=t["bg"], fg=t["muted_fg"])
        due_lbl.grid(row=5, column=1, sticky="w", padx=10)

        def select_due():
            due_var.set(cal.get_date())
            due_lbl.configure(text=f"Selected: {due_var.get()}")

        self._btn(top, t, "Select Date", select_due).grid(row=5, column=0, sticky="e", padx=10, pady=4)

        def confirm():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Task must have a name!", parent=top)
                return
            task = self.manager.add_task(
                name,
                desc_entry.get().strip(),
                due_var.get() or None,
                priority_var.get()
            )
            if task:
                task.category = cat_var.get()
            else:
                # Fallback: set on last added task
                if self.manager.tasks:
                    self.manager.tasks[-1].category = cat_var.get()
            self.refresh_tasks()
            save_tasks(self.manager)
            top.destroy()

        self._btn(top, t, "Add Task", confirm, primary=True).grid(row=6, column=0, columnspan=2, pady=14)

    def edit_task_gui(self):
        selected_item = self.task_tree.selection()
        if not selected_item:
            messagebox.showinfo("Edit Task", "Select a task to edit.")
            return

        task_index = self.task_tree.index(selected_item[0])
        task_to_edit = self.get_sorted_tasks()[task_index]

        top = self._make_dialog("Edit Task")
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        tk.Label(top, text="Task Name:", **self._lbl(t)).grid(row=0, column=0, sticky="e", padx=10, pady=8)
        name_entry = self._entry(top, t, width=38)
        name_entry.insert(0, task_to_edit.name)
        name_entry.grid(row=0, column=1, padx=10, pady=8)

        tk.Label(top, text="Description:", **self._lbl(t)).grid(row=1, column=0, sticky="e", padx=10, pady=8)
        desc_entry = self._entry(top, t, width=38)
        desc_entry.insert(0, task_to_edit.description)
        desc_entry.grid(row=1, column=1, padx=10, pady=8)

        tk.Label(top, text="Category:", **self._lbl(t)).grid(row=2, column=0, sticky="e", padx=10, pady=8)
        current_cat = getattr(task_to_edit, "category", "General")
        cat_var = tk.StringVar(value=current_cat)
        cat_menu = tk.OptionMenu(top, cat_var, *self.categories)
        cat_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        cat_menu.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        tk.Label(top, text="Priority:", **self._lbl(t)).grid(row=3, column=0, sticky="e", padx=10, pady=8)
        priority_var = tk.StringVar(value=task_to_edit.priority)
        priority_menu = tk.OptionMenu(top, priority_var, "High", "Medium", "Low")
        priority_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        priority_menu.grid(row=3, column=1, sticky="w", padx=10, pady=8)

        tk.Label(top, text="Due Date:", **self._lbl(t)).grid(row=4, column=0, sticky="ne", padx=10, pady=8)
        init_date = task_to_edit.due_date if task_to_edit.due_date else datetime.now().date()
        cal = Calendar(
            top, selectmode="day",
            year=init_date.year, month=init_date.month, day=init_date.day,
            date_pattern="yyyy-mm-dd"
        )
        cal.grid(row=4, column=1, padx=10, pady=8)

        due_var = tk.StringVar(value=task_to_edit.due_date.strftime("%Y-%m-%d") if task_to_edit.due_date else "")
        due_lbl = tk.Label(
            top,
            text=f"Selected: {due_var.get()}" if due_var.get() else "No date selected",
            font=("TkDefaultFont", 10), bg=t["bg"], fg=t["muted_fg"]
        )
        due_lbl.grid(row=5, column=1, sticky="w", padx=10)

        def select_due():
            due_var.set(cal.get_date())
            due_lbl.configure(text=f"Selected: {due_var.get()}")

        self._btn(top, t, "Select Date", select_due).grid(row=5, column=0, sticky="e", padx=10, pady=4)

        def confirm():
            new_due_str = cal.get_date()
            task_to_edit.name = name_entry.get().strip()
            task_to_edit.description = desc_entry.get().strip()
            task_to_edit.category = cat_var.get()
            task_to_edit.priority = priority_var.get()
            task_to_edit.due_date = datetime.strptime(new_due_str, "%Y-%m-%d").date() if new_due_str else None
            task_to_edit.update_status()
            self.refresh_tasks()
            save_tasks(self.manager)
            top.destroy()

        self._btn(top, t, "Save Changes", confirm, primary=True).grid(row=6, column=0, columnspan=2, pady=14)
        self.root.wait_window(top)

    def delete_task_gui(self):
        selected = self.task_tree.selection()
        if not selected:
            return
        task = self.get_task_from_selection(selected[0])
        if task:
            self.manager.tasks.remove(task)
            self.refresh_tasks()
            save_tasks(self.manager)

    def mark_done_gui(self):
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showinfo("Mark Done", "Select a task to mark done.")
            return
        task = self.get_task_from_selection(selected[0])
        if task:
            task.done = True
            task.update_status()
            self.refresh_tasks()
            save_tasks(self.manager)

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
                task.done = not task.done
                task.update_status()
                self.refresh_tasks()
                save_tasks(self.manager)
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
                values=(checkbox, t.name, category, t.priority, due_str, days_info, t.description)
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

        # Sync calendar markers and dashboard stats
        self.refresh_calendar()
        self.refresh_stats()

    def refresh_stats(self):
        """Recalculate all dashboard stat values and redraw the progress bar."""
        from datetime import date, timedelta
        today = date.today()
        week_end = today + timedelta(days=7)
        all_tasks = self.manager.tasks

        total   = len(all_tasks)
        done    = sum(1 for t in all_tasks if t.done)
        active  = total - done
        overdue = sum(1 for t in all_tasks if t.is_overdue)
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

    def auto_save(self):
        save_tasks(self.manager)
        self.save_ui_config()   # persists geometry on every auto-save tick
        self.root.after(10000, self.auto_save)

    def on_close(self):
        save_tasks(self.manager)
        self.save_ui_config()
        self.root.destroy()


# ── Run ─────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()