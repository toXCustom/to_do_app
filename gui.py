import tkinter as tk
from tkinter import messagebox
from tasks import TaskManager
from storage import load_tasks, save_tasks
from datetime import datetime, date


class TodoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("To-Do App")

        self.manager = TaskManager()
        load_tasks(self.manager)

        # --- UI ELEMENTS ---

        self.frame = tk.Frame(root)
        self.frame.pack(pady=10)

        self.task_listbox = tk.Listbox(self.frame, width=60, height=15)
        self.task_listbox.pack()

        self.refresh_tasks()

        # Buttons
        self.add_button = tk.Button(root, text="Add Task", command=self.add_task)
        self.add_button.pack(pady=5)

        self.delete_button = tk.Button(root, text="Delete Task", command=self.delete_task)
        self.delete_button.pack(pady=5)

        self.done_button = tk.Button(root, text="Mark as Done", command=self.mark_done)
        self.done_button.pack(pady=5)
        
    def get_sorted_tasks(self):
        def sort_key(task):
            # Completed tasks go last
            if task.done:
                return (3, datetime.max)

            # Tasks without due date
            if not task.due_date:
                return (2, datetime.max)

            # Tasks with due date
            try:
                due = datetime.strptime(task.due_date, "%Y-%m-%d")
            except ValueError:
                return (2, datetime.max)

            # Overdue tasks first
            if task.days_remaining is not None and task.days_remaining < 0:
                return (0, due)

            # Upcoming tasks
            return (1, due)

        return sorted(self.manager.tasks, key=sort_key)
        
    def refresh_tasks(self):
        self.task_listbox.delete(0, tk.END)

        sorted_tasks = self.get_sorted_tasks()

        for task in sorted_tasks:
            status = "✔" if task.done else "✘"
            due = task.due_date if task.due_date else "No due date"

            days_info = ""
            if not task.done and task.days_remaining is not None:
                if task.days_remaining < 0:
                    days_info = f" ({-task.days_remaining} days overdue 🔴)"
                elif task.days_remaining == 0:
                    days_info = " (Due today)"
                else:
                    days_info = f" ({task.days_remaining} days remaining)"

            display_text = (
                f"[{status}] {task.name} - {task.description} "
                f"(Due: {due}){days_info}"
            )

            self.task_listbox.insert(tk.END, display_text)

            # Color overdue tasks red
            index = self.task_listbox.size() - 1
            if not task.done and task.days_remaining is not None:
                if task.days_remaining < 0:
                    self.task_listbox.itemconfig(index, fg="red")

    def add_task(self):
        self.new_window = tk.Toplevel(self.root)
        self.new_window.title("Add Task")

        tk.Label(self.new_window, text="Name").pack()
        name_entry = tk.Entry(self.new_window)
        name_entry.pack()

        tk.Label(self.new_window, text="Description").pack()
        desc_entry = tk.Entry(self.new_window)
        desc_entry.pack()

        tk.Label(self.new_window, text="Due Date (YYYY-MM-DD)").pack()
        due_entry = tk.Entry(self.new_window)
        due_entry.pack()

        def save():
            name = name_entry.get()
            description = desc_entry.get()
            due_date = due_entry.get() or None

            if not name:
                messagebox.showerror("Error", "Task name is required")
                return

            self.manager.add_task(name, description, due_date)
            save_tasks(self.manager)
            self.refresh_tasks()
            self.new_window.destroy()

        tk.Button(self.new_window, text="Save", command=save).pack(pady=5)

    def delete_task(self):
        selected = self.task_listbox.curselection()
        if not selected:
            messagebox.showwarning("Warning", "Select a task first")
            return

        index = selected[0]
        self.manager.tasks.pop(index)
        save_tasks(self.manager)
        self.refresh_tasks()

    def mark_done(self):
        selected = self.task_listbox.curselection()
        if not selected:
            messagebox.showwarning("Warning", "Select a task first")
            return

        index = selected[0]
        self.manager.tasks[index].done = True
        save_tasks(self.manager)
        self.refresh_tasks()


if __name__ == "__main__":
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()