import tkinter as tk
import tkinter.ttk as ttk
from tkinter import simpledialog, messagebox
from tasks import TaskManager
from storage import save_tasks, load_tasks, save_config, load_config
from datetime import datetime
from tkcalendar import Calendar

class TodoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("To-Do App")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Task manager
        self.manager = TaskManager()
        load_tasks(self.manager)

        # Config
        config = load_config()
        self.dark_mode = config.get("dark_mode", False)
        self.sort_type = tk.StringVar(value=config.get("sort", "due_date"))
        self.filter_type = tk.StringVar(value=config.get("filter", "All"))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh_tasks())

        # Themes
        self.light_theme = {
            "bg": "#f7f7f7",
            "fg": "#1c1c1c",
            "button_bg": "#e0e0e0",
            "button_fg": "#1c1c1c",
            "list_bg": "#ffffff",
            "list_fg": "#1c1c1c",
            "heading_bg": "#dcdcdc",
            "heading_fg": "#1c1c1c"
        }

        self.dark_theme = {
            "bg": "#181818",
            "fg": "#f5f5f5",
            "button_bg": "#2c2c2c",
            "button_fg": "#f5f5f5",
            "list_bg": "#212121",
            "list_fg": "#f5f5f5",
            "heading_bg": "#2c2c2c",
            "heading_fg": "#f5f5f5"
        }

        # --- Search ---
        search_frame = tk.Frame(root)
        search_frame.pack(pady=5)
        tk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        tk.Entry(search_frame, textvariable=self.search_var, width=40).pack(side=tk.LEFT)

        # --- Sorting ---
        sort_frame = tk.Frame(root)
        sort_frame.pack(pady=5)
        tk.Label(sort_frame, text="Sort by:").pack(side=tk.LEFT, padx=5)
        sort_options = ["due_date", "creation_date", "priority", "alphabetical"]
        self.sort_menu = tk.OptionMenu(sort_frame, self.sort_type, *sort_options, command=lambda _: self.refresh_tasks())
        self.sort_menu.pack(side=tk.LEFT)

        # --- Filtering ---
        filter_frame = tk.Frame(root)
        filter_frame.pack(pady=5)
        tk.Label(filter_frame, text="Show:").pack(side=tk.LEFT, padx=5)
        filter_options = ["All", "Active", "Completed", "Overdue"]
        self.filter_menu = tk.OptionMenu(filter_frame, self.filter_type, *filter_options, command=lambda _: self.refresh_tasks())
        self.filter_menu.pack(side=tk.LEFT)

        # --- Theme Toggle ---
        self.theme_button = tk.Button(root, text="🌙 Dark Mode", command=self.toggle_theme)
        if self.dark_mode:
            self.theme_button.config(text="☀ Light Mode")
        self.theme_button.pack(pady=5)

        # --- Task Treeview ---
        columns = ("Name", "Priority", "Due", "DaysLeft", "Description", "Status")
        self.task_tree = ttk.Treeview(root, columns=columns, show="headings", height=15)
        for col in columns:
            self.task_tree.heading(col, text=col)
            if col == "Description":
                self.task_tree.column(col, width=400)
            else:
                self.task_tree.column(col, width=100, anchor="center")
        self.task_tree.pack(pady=10, fill=tk.BOTH, expand=True)

        # ---------- Buttons ----------
        button_frame = tk.Frame(root)
        button_frame.pack(pady=10)

        # Add Task
        tk.Button(button_frame, text="Add Task", command=self.add_task_gui).pack(side=tk.LEFT, padx=5)

        # Edit Task
        tk.Button(button_frame, text="Edit Task", command=self.edit_task_gui).pack(side=tk.LEFT, padx=5)

        # Delete Task
        tk.Button(button_frame, text="Delete Task", command=self.delete_task_gui).pack(side=tk.LEFT, padx=5)

        # Mark Done
        tk.Button(button_frame, text="Mark Done", command=self.mark_done_gui).pack(side=tk.LEFT, padx=5)

        # Apply theme and show tasks
        self.apply_theme()
        self.refresh_tasks()

        # Auto-save every 10 sec
        self.auto_save()

    # ---------- GUI Actions ----------
    def add_task_gui(self):
        # Create a single modal window
        top = tk.Toplevel(self.root)
        top.title("Add Task")
        top.grab_set()  # make modal

        # Task Name
        tk.Label(top, text="Task Name:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        name_entry = tk.Entry(top, width=40)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        # Description
        tk.Label(top, text="Description:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        desc_entry = tk.Entry(top, width=40)
        desc_entry.grid(row=1, column=1, padx=5, pady=5)

        # Priority
        tk.Label(top, text="Priority:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        priority_var = tk.StringVar(value="Medium")
        priority_menu = tk.OptionMenu(top, priority_var, "High", "Medium", "Low")
        priority_menu.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # Due Date
        tk.Label(top, text="Due Date:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        due_var = tk.StringVar()
        cal = Calendar(top, selectmode="day", date_pattern="yyyy-mm-dd")
        cal.grid(row=3, column=1, padx=5, pady=5)

        def select_due():
            due_var.set(cal.get_date())

        tk.Button(top, text="Select Date", command=select_due).grid(row=4, column=1, sticky="w", padx=5, pady=5)

        # Add Task Button
        def confirm_task():
            name = name_entry.get().strip()
            description = desc_entry.get().strip()
            due_date = due_var.get() if due_var.get() else None
            priority = priority_var.get()

            if not name:
                messagebox.showerror("Error", "Task must have a name!")
                return

            self.manager.add_task(name, description, due_date, priority)
            self.refresh_tasks()
            save_tasks(self.manager)
            top.destroy()

        tk.Button(top, text="Add Task", command=confirm_task).grid(row=5, column=0, columnspan=2, pady=10)

        top.mainloop()
        
    def edit_task_gui(self):
        selected_item = self.task_tree.selection()
        if not selected_item:
            messagebox.showinfo("Edit Task", "Select a task to edit.")
            return

        task_index = self.task_tree.index(selected_item[0])
        visible_tasks = self.get_sorted_tasks()
        task_to_edit = visible_tasks[task_index]

        # Create modal window
        top = tk.Toplevel(self.root)
        top.title("Edit Task")
        top.grab_set()  # modal

        # Task Name
        tk.Label(top, text="Task Name:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        name_entry = tk.Entry(top, width=40)
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        name_entry.insert(0, task_to_edit.name) 

        # Description
        tk.Label(top, text="Description:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        desc_entry = tk.Entry(top, width=40)
        desc_entry.grid(row=1, column=1, padx=5, pady=5)
        desc_entry.insert(0, task_to_edit.description)

        # Priority
        tk.Label(top, text="Priority:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        priority_var = tk.StringVar(value=task_to_edit.priority)
        priority_menu = tk.OptionMenu(top, priority_var, "High", "Medium", "Low")
        priority_menu.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # Due Date
        tk.Label(top, text="Due Date:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        due_var = tk.StringVar(value=task_to_edit.due_date.strftime("%Y-%m-%d") if task_to_edit.due_date else "")
        cal = Calendar(top, selectmode="day", date_pattern="yyyy-mm-dd")
        if task_to_edit.due_date:
            init_date = task_to_edit.due_date
        else:
            init_date = datetime.now().date()

        cal = Calendar(
            top,
            selectmode="day",
            year=init_date.year,
            month=init_date.month,
            day=init_date.day,
            date_pattern="yyyy-mm-dd"
        )
        cal.grid(row=3, column=1, padx=5, pady=5)

        def select_due():
            due_var.set(cal.get_date())

        tk.Button(top, text="Select Date", command=select_due).grid(row=4, column=1, sticky="w", padx=5, pady=5)

        # Confirm Edit Button
        def confirm_edit():
            new_name = name_entry.get().strip()
            new_desc = desc_entry.get().strip()
            new_priority = priority_var.get()
            new_due_date_str = cal.get_date()  # always a string in yyyy-mm-dd
            new_due_date = datetime.strptime(new_due_date_str, "%Y-%m-%d").date() if new_due_date_str else None

            # Use task_to_edit instead of task
            task_to_edit.name = new_name
            task_to_edit.description = new_desc
            task_to_edit.priority = new_priority
            task_to_edit.due_date = new_due_date
            task_to_edit.update_status()

            self.refresh_tasks()
            save_tasks(self.manager)
            top.destroy()

        tk.Button(top, text="Save Changes", command=confirm_edit).grid(row=5, column=0, columnspan=2, pady=10)

        top.mainloop()

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
            self.refresh_tasks()
            save_tasks(self.manager)
            
    # Helper method
    def find_task_by_values(self, values):
        for task in self.manager.tasks:
            due_str = task.due_date.strftime("%Y-%m-%d") if task.due_date else "No due date"
            days_left = (task.due_date - datetime.now().date()).days if task.due_date else ""
            days_info = f"{days_left} days left" if days_left > 0 else "Due today" if days_left == 0 else f"{abs(days_left)} days overdue" if days_left < 0 else ""
            if (
                task.priority == values[0] and
                due_str == values[1] and
                days_info == values[2] and
                task.description == values[3]
            ):
                return task
        return None

    # ---------- Helper ----------
    def get_task_from_selection(self, item_id):
        values = self.task_tree.item(item_id, "values")
        name = values[0]
        for t in self.manager.tasks:
            if t.name == name:
                return t
        return None

    # ---------- Toggle theme ----------
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.save_ui_config()
        self.apply_theme()
        self.theme_button.config(text="☀ Light Mode" if self.dark_mode else "🌙 Dark Mode")

    def apply_theme(self):
        theme = self.dark_theme if self.dark_mode else self.light_theme
        self.root.configure(bg=theme["bg"])
        
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Label):
                widget.config(bg=theme["bg"], fg=theme["fg"])
            elif isinstance(widget, tk.Button) or isinstance(widget, tk.OptionMenu):
                widget.config(bg=theme["button_bg"], fg=theme["button_fg"], activebackground=theme["button_bg"])
            elif isinstance(widget, tk.Frame):
                widget.config(bg=theme["bg"])
        
        # Treeview colors
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=theme["list_bg"],
                        foreground=theme["list_fg"],
                        fieldbackground=theme["list_bg"])
        style.configure("Treeview.Heading",
                        background=theme["heading_bg"],
                        foreground=theme["heading_fg"])

    def save_ui_config(self):
        config = {"dark_mode": self.dark_mode, "sort": self.sort_type.get(), "filter": self.filter_type.get()}
        save_config(config)

    # ---------- Filtering & Sorting ----------
    def get_filtered_tasks(self):
        tasks = self.manager.tasks
        f = self.filter_type.get()
        if f == "Active":
            tasks = [t for t in tasks if not t.done]
        elif f == "Completed":
            tasks = [t for t in tasks if t.done]
        elif f == "Overdue":
            tasks = [t for t in tasks if t.is_overdue]

        search = self.search_var.get().lower().strip()
        if search:
            tasks = [t for t in tasks if search in t.name.lower() or search in t.description.lower()]
        return tasks

    def get_sorted_tasks(self):
        tasks = self.get_filtered_tasks()
        s = self.sort_type.get()
        def key(t):
            if s == "due_date":
                return t.due_date if t.due_date else datetime.max.date()
            elif s == "creation_date":
                return t.created_at
            elif s == "priority":
                mapping = {"High":1,"Medium":2,"Low":3}
                return mapping.get(t.priority, 2)
            else:
                return t.name.lower()
        return sorted(tasks, key=key)

    # ---------- Calendar ----------
    def open_calendar(self):
        top = tk.Toplevel(self.root)
        top.title("Select Due Date")
        top.grab_set()
        cal = Calendar(top, selectmode="day", date_pattern="yyyy-mm-dd")
        cal.pack(pady=10)
        sel = tk.StringVar()
        tk.Button(top, text="Select", command=lambda: (sel.set(cal.get_date()), top.destroy())).pack(pady=5)
        self.root.wait_window(top)
        return sel.get()

    # ---------- Refresh ----------
    def refresh_tasks(self):
        for row in self.task_tree.get_children():
            self.task_tree.delete(row)

        tasks = self.get_sorted_tasks()
        for t in tasks:
            if isinstance(t.due_date, str):
                t.due_date = datetime.strptime(t.due_date, "%Y-%m-%d").date() if t.due_date else None
            due_str = t.due_date.strftime("%Y-%m-%d") if t.due_date else "No due date"
            days_left = (t.due_date - datetime.now().date()).days if t.due_date else ""
            if t.done:
                status = "✔"
                days_info = ""
            else:
                status = "✘"
                if t.due_date:
                    if days_left > 0: days_info = f"{days_left} days left"
                    elif days_left == 0: days_info = "Due today"
                    else: days_info = f"{abs(days_left)} days overdue"
                else:
                    days_info = ""
            row_id = self.task_tree.insert("", tk.END, values=(t.name, t.priority, due_str, days_info, t.description, status))
            # Coloring
            if t.done:
                self.task_tree.item(row_id, tags=("done",))
            elif t.due_date and not t.done and t.due_date < datetime.now().date():
                self.task_tree.item(row_id, tags=("overdue",))
            elif t.priority == "High":
                self.task_tree.item(row_id, tags=("high",))
            elif t.priority == "Medium":
                self.task_tree.item(row_id, tags=("medium",))
            elif t.priority == "Low":
                self.task_tree.item(row_id, tags=("low",))
        self.task_tree.tag_configure("done", foreground="gray")
        self.task_tree.tag_configure("overdue", foreground="red")
        self.task_tree.tag_configure("high", foreground="#ff4d4d")
        self.task_tree.tag_configure("medium", foreground="#ffaa00")
        self.task_tree.tag_configure("low", foreground="#4caf50")

    # ---------- Auto-save ----------
    def auto_save(self):
        save_tasks(self.manager)
        self.root.after(10000, self.auto_save)

    # ---------- Close ----------
    def on_close(self):
        save_tasks(self.manager)
        self.save_ui_config()
        self.root.destroy()


# ---------- Run ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()