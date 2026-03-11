import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
from tasks import TaskManager
from storage import save_tasks, load_tasks, save_config, load_config
from datetime import datetime
from tkcalendar import Calendar

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
        self.filter_type = tk.StringVar(value=config.get("filter", "All"))
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
        self.toolbar_inner.pack(fill=tk.X, padx=14, pady=(10, 0))

        # ── Filter row ───────────────────────────────
        self.filter_row = tk.Frame(self.toolbar_inner)
        self.filter_row.pack(fill=tk.X, pady=(0, 6))

        self.filter_heading = tk.Label(
            self.filter_row, text="FILTER",
            font=("TkDefaultFont", 8, "bold")
        )
        self.filter_heading.pack(side=tk.LEFT, padx=(0, 10))

        # Search entry
        self.search_entry = tk.Entry(
            self.filter_row,
            textvariable=self.search_var,
            width=22, relief="flat",
            font=("TkDefaultFont", 11)
        )
        self.search_entry.pack(side=tk.LEFT, ipady=5, padx=(0, 10))

        # Filter tab buttons
        self.filter_buttons = {}
        for label in ["All", "Active", "Completed", "Overdue"]:
            btn = tk.Button(
                self.filter_row, text=label,
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 10, "bold"),
                padx=11, pady=5,
                command=lambda v=label: self._set_filter(v)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.filter_buttons[label] = btn

        # ── Thin divider between rows ─────────────────
        self.toolbar_divider = tk.Frame(self.toolbar_inner, height=1)
        self.toolbar_divider.pack(fill=tk.X, pady=4)

        # ── Sort row ─────────────────────────────────
        self.sort_row = tk.Frame(self.toolbar_inner)
        self.sort_row.pack(fill=tk.X, pady=(0, 10))

        self.sort_heading = tk.Label(
            self.sort_row, text="SORT",
            font=("TkDefaultFont", 8, "bold")
        )
        self.sort_heading.pack(side=tk.LEFT, padx=(0, 10))

        # Sort tab buttons
        self.sort_buttons = {}
        sort_options = [
            ("due_date",      "Due Date"),
            ("priority",      "Priority"),
            ("alphabetical",  "A – Z"),
            ("creation_date", "Created"),
        ]
        for value, label in sort_options:
            btn = tk.Button(
                self.sort_row, text=label,
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 10, "bold"),
                padx=11, pady=5,
                command=lambda v=value: self._set_sort(v)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.sort_buttons[value] = btn

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

        # ── Task Treeview (packed last so expand fills remaining space) ──
        tree_frame = tk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # "Done" is the first column so the checkbox sits on the left edge
        columns = ("Done", "Name", "Priority", "Due", "DaysLeft", "Description")
        self.task_tree = ttk.Treeview(
            tree_frame, columns=columns,
            show="headings", height=15
        )

        col_config = {
            "Done":        (40,  "center"),
            "Name":        (200, "w"),
            "Priority":    (80,  "center"),
            "Due":         (100, "center"),
            "DaysLeft":    (130, "center"),
            "Description": (300, "w"),
        }
        for col, (width, anchor) in col_config.items():
            self.task_tree.heading(col, text="" if col == "Done" else col)
            self.task_tree.column(col, width=width, anchor=anchor,
                                  minwidth=width if col == "Done" else 40)

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

        # Separators
        for sep in [self.sep1, self.sep2, self.sep3]:
            sep.configure(bg=t["border"])

        # Toolbar
        self.toolbar.configure(bg=t["surface2"])
        self.toolbar_inner.configure(bg=t["surface2"])
        self.filter_row.configure(bg=t["surface2"])
        self.sort_row.configure(bg=t["surface2"])
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

        # Footer
        for w in [self.footer_frame, self.action_frame, self.right_frame]:
            w.configure(bg=t["bg"])
        for btn in self.action_buttons:
            btn.configure(
                bg=t["secondary_btn_bg"], fg=t["secondary_btn_fg"],
                activebackground=t["border"],
                activeforeground=t["fg"]
            )
        self.save_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.theme_button.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"],
            activeforeground=t["fg"],
            text="☀  Light" if self.dark_mode else "🌙  Dark"
        )

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
            self.task_tree.tag_configure("done",    foreground="#4A4E5A")
            self.task_tree.tag_configure("overdue", foreground="#F87171")
            self.task_tree.tag_configure("high",    foreground="#F87171")
            self.task_tree.tag_configure("medium",  foreground="#FCD34D")
            self.task_tree.tag_configure("low",     foreground="#6EE7A0")
        else:
            self.task_tree.tag_configure("done",    foreground="#B0AAA4")
            self.task_tree.tag_configure("overdue", foreground="#DC2626")
            self.task_tree.tag_configure("high",    foreground="#B91C1C")
            self.task_tree.tag_configure("medium",  foreground="#B45309")
            self.task_tree.tag_configure("low",     foreground="#4D7C5F")

    def save_ui_config(self):
        save_config({
            "dark_mode": self.dark_mode,
            "sort": self.sort_type.get(),
            "filter": self.filter_type.get(),
            "geometry": self.root.geometry(),
        })

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

        tk.Label(top, text="Priority:", **self._lbl(t)).grid(row=2, column=0, sticky="e", padx=10, pady=8)
        priority_var = tk.StringVar(value="Medium")
        priority_menu = tk.OptionMenu(top, priority_var, "High", "Medium", "Low")
        priority_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        priority_menu.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        tk.Label(top, text="Due Date:", **self._lbl(t)).grid(row=3, column=0, sticky="ne", padx=10, pady=8)
        due_var = tk.StringVar()
        cal = Calendar(top, selectmode="day", date_pattern="yyyy-mm-dd")
        cal.grid(row=3, column=1, padx=10, pady=8)

        due_lbl = tk.Label(top, text="No date selected", font=("TkDefaultFont", 10), bg=t["bg"], fg=t["muted_fg"])
        due_lbl.grid(row=4, column=1, sticky="w", padx=10)

        def select_due():
            due_var.set(cal.get_date())
            due_lbl.configure(text=f"Selected: {due_var.get()}")

        self._btn(top, t, "Select Date", select_due).grid(row=4, column=0, sticky="e", padx=10, pady=4)

        def confirm():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Task must have a name!", parent=top)
                return
            self.manager.add_task(
                name,
                desc_entry.get().strip(),
                due_var.get() or None,
                priority_var.get()
            )
            self.refresh_tasks()
            save_tasks(self.manager)
            top.destroy()

        self._btn(top, t, "Add Task", confirm, primary=True).grid(row=5, column=0, columnspan=2, pady=14)

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

        tk.Label(top, text="Priority:", **self._lbl(t)).grid(row=2, column=0, sticky="e", padx=10, pady=8)
        priority_var = tk.StringVar(value=task_to_edit.priority)
        priority_menu = tk.OptionMenu(top, priority_var, "High", "Medium", "Low")
        priority_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        priority_menu.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        tk.Label(top, text="Due Date:", **self._lbl(t)).grid(row=3, column=0, sticky="ne", padx=10, pady=8)
        init_date = task_to_edit.due_date if task_to_edit.due_date else datetime.now().date()
        cal = Calendar(
            top, selectmode="day",
            year=init_date.year, month=init_date.month, day=init_date.day,
            date_pattern="yyyy-mm-dd"
        )
        cal.grid(row=3, column=1, padx=10, pady=8)

        due_var = tk.StringVar(value=task_to_edit.due_date.strftime("%Y-%m-%d") if task_to_edit.due_date else "")
        due_lbl = tk.Label(
            top,
            text=f"Selected: {due_var.get()}" if due_var.get() else "No date selected",
            font=("TkDefaultFont", 10), bg=t["bg"], fg=t["muted_fg"]
        )
        due_lbl.grid(row=4, column=1, sticky="w", padx=10)

        def select_due():
            due_var.set(cal.get_date())
            due_lbl.configure(text=f"Selected: {due_var.get()}")

        self._btn(top, t, "Select Date", select_due).grid(row=4, column=0, sticky="e", padx=10, pady=4)

        def confirm():
            new_due_str = cal.get_date()
            task_to_edit.name = name_entry.get().strip()
            task_to_edit.description = desc_entry.get().strip()
            task_to_edit.priority = priority_var.get()
            task_to_edit.due_date = datetime.strptime(new_due_str, "%Y-%m-%d").date() if new_due_str else None
            task_to_edit.update_status()
            self.refresh_tasks()
            save_tasks(self.manager)
            top.destroy()

        self._btn(top, t, "Save Changes", confirm, primary=True).grid(row=5, column=0, columnspan=2, pady=14)
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
        tasks = self.manager.tasks
        filter_by = self.filter_type.get()
        if filter_by == "Active":
            tasks = [t for t in tasks if not t.done]
        elif filter_by == "Completed":
            tasks = [t for t in tasks if t.done]
        elif filter_by == "Overdue":
            tasks = [t for t in tasks if t.is_overdue]
        search = self.search_var.get().lower().strip()
        if search:
            tasks = [t for t in tasks if search in t.name.lower() or search in t.description.lower()]
        return tasks

    def get_sorted_tasks(self):
        tasks = self.get_filtered_tasks()
        sort_by = self.sort_type.get()
        def sort_key(task):
            if sort_by == "due_date":
                return task.due_date if task.due_date else datetime.max.date()
            elif sort_by == "creation_date":
                return task.created_at
            elif sort_by == "priority":
                return {"High": 1, "Medium": 2, "Low": 3}.get(task.priority, 2)
            else:
                return task.name.lower()
        return sorted(tasks, key=sort_key)

    @staticmethod
    def _days_info(task):
        """Human-readable days until/since due date."""
        if not task.due_date:
            return ""
        days_left = (task.due_date - datetime.now().date()).days
        if days_left > 0:
            return f"{days_left} days left"
        if days_left == 0:
            return "Due today"
        return f"{abs(days_left)} days overdue"

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

            row_id = self.task_tree.insert(
                "", tk.END,
                values=(checkbox, t.name, t.priority, due_str, days_info, t.description)
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

    # ═══════════════════════════════════════════════
    #  AUTO-SAVE / CLOSE
    # ═══════════════════════════════════════════════

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