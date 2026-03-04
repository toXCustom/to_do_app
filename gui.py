import tkinter as tk
from tkinter import simpledialog, messagebox
from tasks import TaskManager
from storage import save_tasks, load_tasks, save_config, load_config
from datetime import datetime

class TodoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("To-Do App")
        self.manager = TaskManager()
        load_tasks(self.manager)
        
        self.dark_mode = load_config()

        self.light_theme = {
            "bg": "#f0f0f0",
            "fg": "#000000",
            "button_bg": "#e0e0e0",
            "list_bg": "#ffffff",
            "list_fg": "#000000"
        }

        self.dark_theme = {
            "bg": "#1e1e1e",
            "fg": "#ffffff",
            "button_bg": "#2d2d2d",
            "list_bg": "#252526",
            "list_fg": "#ffffff"
        }

        # Sorting
        self.sort_type = tk.StringVar(value="due_date")  # due_date, creation, priority, alphabetical
        sort_options = ["due_date", "creation_date", "priority", "alphabetical"]
        tk.Label(root, text="Sort by:").pack()
        self.sort_menu = tk.OptionMenu(root, self.sort_type, *sort_options, command=lambda _: self.refresh_tasks())
        self.sort_menu.pack()

        # Filtering
        self.filter_type = tk.StringVar(value="All")
        filter_options = ["All", "Active", "Completed", "Overdue"]
        tk.Label(root, text="Show:").pack()
        self.filter_menu = tk.OptionMenu(root, self.filter_type, *filter_options, command=lambda _: self.refresh_tasks())
        self.filter_menu.pack()
        
        # Light/Dark Mode
        self.theme_button = tk.Button(root, text="🌙 Dark Mode", command=self.toggle_theme)
        if self.dark_mode:
            self.theme_button.config(text="☀ Light Mode")
        self.theme_button.pack(pady=5)

        # Task List
        self.task_listbox = tk.Listbox(root, width=100)
        self.task_listbox.pack(pady=10)

        # Buttons
        tk.Button(root, text="Add Task", command=self.add_task_gui).pack(side=tk.LEFT, padx=5)
        tk.Button(root, text="Delete Task", command=self.delete_task_gui).pack(side=tk.LEFT, padx=5)
        tk.Button(root, text="Mark Done", command=self.mark_done_gui).pack(side=tk.LEFT, padx=5)

        self.apply_theme()
        self.refresh_tasks()

    # ---------- GUI Methods ----------
    def add_task_gui(self):
        name = simpledialog.askstring("Task Name", "Enter task name:")
        if not name:
            return
        description = simpledialog.askstring("Task Description", "Enter task description:") or ""
        due_date = simpledialog.askstring("Due Date", "Enter due date YYYY-MM-DD (optional):") or None
        priority = simpledialog.askstring("Priority", "Enter priority (High/Medium/Low):", initialvalue="Medium") or "Medium"

        self.manager.add_task(name, description, due_date, priority)
        self.refresh_tasks()
        save_tasks(self.manager)

    def delete_task_gui(self):
        selected_index = self.task_listbox.curselection()
        if not selected_index:
            messagebox.showinfo("Delete Task", "Select a task to delete.")
            return
        task_text = self.task_listbox.get(selected_index[0])
        task_name = task_text.split("] ")[1].split(" - ")[0]
        self.manager.delete_task(task_name)
        self.refresh_tasks()
        save_tasks(self.manager)

    def mark_done_gui(self):
        selected_index = self.task_listbox.curselection()
        if not selected_index:
            messagebox.showinfo("Mark Done", "Select a task to mark done.")
            return
        task_text = self.task_listbox.get(selected_index[0])
        task_name = task_text.split("] ")[1].split(" - ")[0]
        self.manager.mark_done(task_name)
        self.refresh_tasks()
        save_tasks(self.manager)

    # ---------- Toggle Light/Dark Theme ----------
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        save_config(self.dark_mode)  # 💾 SAVE HERE

        if self.dark_mode:
            self.theme_button.config(text="☀ Light Mode")
        else:
            self.theme_button.config(text="🌙 Dark Mode")

        self.apply_theme()


    def apply_theme(self):
        theme = self.dark_theme if self.dark_mode else self.light_theme

        # Root window
        self.root.configure(bg=theme["bg"])

        # Update all children widgets
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Label):
                widget.config(bg=theme["bg"], fg=theme["fg"])
            elif isinstance(widget, tk.Button):
                widget.config(bg=theme["button_bg"], fg=theme["fg"],
                            activebackground=theme["button_bg"])
            elif isinstance(widget, tk.OptionMenu):
                widget.config(bg=theme["button_bg"], fg=theme["fg"])
            elif isinstance(widget, tk.Listbox):
                widget.config(bg=theme["list_bg"], fg=theme["list_fg"])

    # ---------- Filtering & Sorting ----------
    def get_filtered_tasks(self):
        value = self.filter_type.get()
        if value == "Active":
            return [t for t in self.manager.tasks if not t.done]
        if value == "Completed":
            return [t for t in self.manager.tasks if t.done]
        if value == "Overdue":
            return [t for t in self.manager.tasks if t.is_overdue]
        return self.manager.tasks

    def get_sorted_tasks(self):
        tasks = self.get_filtered_tasks()
        sort_type = self.sort_type.get()

        def sort_key(task):
            if sort_type == "due_date":
                if task.due_date:
                    return datetime.strptime(task.due_date, "%Y-%m-%d")
                return datetime.max
            elif sort_type == "creation_date":
                return datetime.strptime(task.created_at, "%Y-%m-%d %H:%M:%S")
            elif sort_type == "priority":
                mapping = {"High": 1, "Medium": 2, "Low": 3}
                return mapping.get(task.priority, 2)
            else:  # alphabetical
                return task.name.lower()

        return sorted(tasks, key=sort_key)

    # ---------- Refresh List ----------
    def refresh_tasks(self):
        self.manager.update_all()
        self.task_listbox.delete(0, tk.END)
        for task in self.get_sorted_tasks():
            status = "✔" if task.done else "✘"
            due = task.due_date or "No due date"
            days_rem = f"({task.days_remaining} days left)" if task.days_remaining is not None else ""
            overdue = " 🔴 OVERDUE" if task.is_overdue else ""
            self.task_listbox.insert(
                tk.END,
                f"[{status}] {task.name} - {task.description} {days_rem} {due} {overdue}"
            )


# ---------- Run App ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()