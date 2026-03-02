import tkinter as tk
from tkinter import messagebox
from tasks import TaskManager
from storage import load_tasks, save_tasks


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
        
    def refresh_tasks(self):
        self.task_listbox.delete(0, tk.END)
        for task in self.manager.tasks:
            status = "✔" if task.done else "✘"
            due = task.due_date if task.due_date else "No due date"
            self.task_listbox.insert(
                tk.END,
                f"[{status}] {task.name} - {task.description} (Due: {due})"
            )

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