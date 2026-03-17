from datetime import datetime

class Task:
    def __init__(self, name, description="", due_date=None, priority="Medium"):
        self.name = name
        self.description = description
        self.done = False
        self.due_date = due_date  # format YYYY-MM-DD
        self.priority = priority  # High / Medium / Low
        self.category = "General"
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.update_status()

    def update_status(self):
        if self.due_date:
            self.is_overdue = datetime.now().date() > self.due_date
        else:
            self.is_overdue = False

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "done": self.done,
            "due_date": self.due_date,
            "priority": self.priority,
            "category": self.category,
            "created_at": self.created_at
        }

    @staticmethod
    def from_dict(data):
        task = Task(
            data["name"],
            data.get("description", ""),
            data.get("due_date"),
            data.get("priority", "Medium")
        )
        task.done = data.get("done", False)
        task.category = data.get("category", "General")
        task.created_at = data.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        task.update_status()
        return task


class TaskManager:
    def __init__(self):
        self.tasks = []

    def add_task(self, name, description, due_date=None, priority="Medium"):
        if due_date:
            due_date = datetime.strptime(due_date, "%Y-%m-%d").date()

        task = Task(name, description, due_date, priority)
        self.tasks.append(task)
        return task

    def delete_task(self, name):
        self.tasks = [t for t in self.tasks if t.name != name]

    def mark_done(self, name):
        for task in self.tasks:
            if task.name == name:
                task.done = True
                task.update_status()
                break

    def update_all(self):
        for task in self.tasks:
            task.update_status()