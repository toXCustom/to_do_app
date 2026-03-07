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

        # --- Buttons ---
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Add Task", command=self.add_task_gui).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Delete Task", command=self.delete_task_gui).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Mark Done", command=self.mark_done_gui).pack(side=tk.LEFT, padx=5)

        # Apply theme and show tasks
        self.apply_theme()
        self.refresh_tasks()

        # Auto-save every 10 sec
        self.auto_save()

    # ---------- GUI Actions ----------
    def add_task_gui(self):
        name = simpledialog.askstring("Task Name", "Enter task name:")
        if not name:
            return
        description = simpledialog.askstring("Task Description", "Enter task description:") or ""
        if messagebox.askyesno("Due Date", "Do you want to set a due date?"):
            due_date = self.open_calendar()
        else:
            due_date = None
        priority = simpledialog.askstring("Priority", "High/Medium/Low:", initialvalue="Medium") or "Medium"

        self.manager.add_task(name, description, due_date, priority)
        self.refresh_tasks()
        save_tasks(self.manager)

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