import tkinter as tk
from tkinter import simpledialog, messagebox
from tasks import TaskManager
from storage import save_tasks, load_tasks
from datetime import datetime

class TodoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("To-Do App")
        self.manager = TaskManager()
        load_tasks(self.manager)

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

        # Task List
        self.task_listbox = tk.Listbox(root, width=100)
        self.task_listbox.pack(pady=10)

        # Buttons
        tk.Button(root, text="Add Task", command=self.add_task_gui).pack(side=tk.LEFT, padx=5)
        tk.Button(root, text="Delete Task", command=self.delete_task_gui).pack(side=tk.LEFT, padx=5)
        tk.Button(root, text="Mark Done", command=self.mark_done_gui).pack(side=tk.LEFT, padx=5)

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