import tkinter as tk
from tkinter import simpledialog, messagebox
from tasks import TaskManager
from storage import save_tasks, load_tasks, save_config, load_config
from datetime import datetime
from tkcalendar import Calendar

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
        use_due = messagebox.askyesno("Due Date", "Do you want to set a due date?")
        if use_due:
            due_date = self.open_calendar()
        else:
            due_date = None
        priority = simpledialog.askstring("Priority", "Enter priority (High/Medium/Low):", initialvalue="Medium") or "Medium"

        self.manager.add_task(name, description, due_date, priority)
        self.refresh_tasks()
        save_tasks(self.manager)

    def delete_task_gui(self):
        selected = self.task_listbox.curselection()

        if not selected:
            return  # nothing selected

        index = selected[0]

        # Get currently displayed tasks (filtered + sorted)
        visible_tasks = self.get_sorted_tasks()

        if index >= len(visible_tasks):
            return

        task_to_delete = visible_tasks[index]

        # Remove from real manager list
        self.manager.tasks.remove(task_to_delete)

        self.refresh_tasks()

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
                return task.due_date if task.due_date else datetime.max.date()

            elif sort_type == "creation_date":
                return task.created_at  # must already be datetime

            elif sort_type == "priority":
                mapping = {"High": 1, "Medium": 2, "Low": 3}
                return mapping.get(task.priority, 2)

            else:  # alphabetical
                return task.name.lower()

        return sorted(tasks, key=sort_key)
    
    # ---------- Calendar selector ----------
    def open_calendar(self):
        top = tk.Toplevel(self.root)
        top.title("Select Due Date")
        top.grab_set()  # make it modal

        cal = Calendar(top, selectmode="day", date_pattern="yyyy-mm-dd")
        cal.pack(pady=10)

        selected_date = tk.StringVar()

        def confirm_date():
            selected_date.set(cal.get_date())
            top.destroy()

        tk.Button(top, text="Select", command=confirm_date).pack(pady=5)

        self.root.wait_window(top)

        return selected_date.get()

    # ---------- Refresh List ----------
    def refresh_tasks(self):
        self.task_listbox.delete(0, tk.END)

        tasks = self.get_sorted_tasks()

        for index, task in enumerate(tasks):

            status = "✔" if task.done else "✘"

            # ---- Due Date Info ----
            if task.due_date:

                # Safety conversion (only if still string)
                if isinstance(task.due_date, str):
                    task.due_date = datetime.strptime(task.due_date, "%Y-%m-%d").date()

                due_str = f"Due: {task.due_date.strftime('%Y-%m-%d')}"

                days_left = (task.due_date - datetime.now().date()).days

                if task.done:
                    days_info = ""
                elif days_left > 0:
                    days_info = f" | {days_left} days left"
                elif days_left == 0:
                    days_info = " | Due today"
                else:
                    days_info = f" | {abs(days_left)} days overdue"
            else:
                due_str = "No due date"
                days_info = ""

            # ---- Full Display Text ----
            display_text = (
                f"[{status}] "
                f"{task.name} "
                f"(Priority: {task.priority})\n"
                f"   {task.description}\n"
                f"   {due_str}{days_info}"
            )

            self.task_listbox.insert(tk.END, display_text)

            # ---- Coloring ----
            if task.done:
                self.task_listbox.itemconfig(index, fg="gray")

            elif task.due_date and not task.done and task.due_date < datetime.now().date():
                self.task_listbox.itemconfig(index, fg="red")

            elif task.priority == "High":
                self.task_listbox.itemconfig(index, fg="#ff4d4d")

            elif task.priority == "Medium":
                self.task_listbox.itemconfig(index, fg="#ffaa00")

            elif task.priority == "Low":
                self.task_listbox.itemconfig(index, fg="#4caf50")


# ---------- Run App ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()