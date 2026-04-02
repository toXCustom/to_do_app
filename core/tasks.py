from datetime import datetime

class Task:
    RECURRENCE_OPTIONS = [None, "Daily", "Weekly", "Monthly"]

    def __init__(self, name, description="", due_date=None, priority="Medium"):
        self.name        = name
        self.description = description
        self.done        = False
        self.due_date    = due_date
        self.priority    = priority
        self.category    = "General"
        self.recurrence  = None   # None | "Daily" | "Weekly" | "Monthly"
        self.created_at   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.completed_at = None
        self.update_status()

    def update_status(self):
        if self.due_date:
            self.is_overdue = datetime.now().date() > self.due_date
        else:
            self.is_overdue = False

    def next_due_date(self):
        """Return the next due date based on recurrence, or None."""
        from datetime import timedelta, date as _date
        import calendar as _cal
        if not self.due_date or not self.recurrence:
            return None
        d = self.due_date
        if self.recurrence == "Daily":
            return d + timedelta(days=1)
        elif self.recurrence == "Weekly":
            return d + timedelta(weeks=1)
        elif self.recurrence == "Monthly":
            month = d.month % 12 + 1
            year  = d.year + (1 if d.month == 12 else 0)
            day   = min(d.day, _cal.monthrange(year, month)[1])
            return _date(year, month, day)
        return None

    def to_dict(self):
        return {
            "name":         self.name,
            "description":  self.description,
            "done":         self.done,
            "due_date":     self.due_date,
            "priority":     self.priority,
            "category":     self.category,
            "recurrence":   self.recurrence,
            "created_at":   self.created_at,
            "completed_at": self.completed_at,
        }

    @staticmethod
    def from_dict(data):
        task = Task(
            data["name"],
            data.get("description", ""),
            data.get("due_date"),
            data.get("priority", "Medium"),
        )
        task.done         = data.get("done", False)
        task.category     = data.get("category", "General")
        task.recurrence   = data.get("recurrence", None)
        task.created_at   = data.get("created_at",   datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        task.completed_at = data.get("completed_at", None)
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
                task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                task.update_status()
                break

    def update_all(self):
        for task in self.tasks:
            task.update_status()