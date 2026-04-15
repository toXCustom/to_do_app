from datetime import datetime

class Task:
    RECURRENCE_OPTIONS = [None, "Daily", "Weekly", "Monthly"]

    def __init__(self, name, description="", due_date=None, priority="Medium"):
        self.name         = name
        self.description  = description
        self.done         = False
        self.due_date     = due_date
        self.priority     = priority
        self.category     = "General"
        self.recurrence   = None
        self.attachments  = []
        self.subtasks     = []      # list of Task objects (one level deep)
        self.created_at   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.completed_at = None
        self.update_status()

    def update_status(self):
        if self.due_date:
            self.is_overdue = datetime.now().date() > self.due_date
        else:
            self.is_overdue = False

    # ── Subtask helpers ───────────────────────────────────────────────────────

    def add_subtask(self, name, description="", due_date=None, priority="Medium") -> "Task":
        sub = Task(name, description, due_date, priority)
        sub.category = self.category   # inherit parent category
        self.subtasks.append(sub)
        return sub

    def remove_subtask(self, subtask: "Task"):
        self.subtasks = [s for s in self.subtasks if s is not subtask]

    @property
    def subtask_progress(self) -> tuple:
        """Return (done_count, total_count) of subtasks."""
        if not self.subtasks:
            return (0, 0)
        done = sum(1 for s in self.subtasks if s.done)
        return (done, len(self.subtasks))

    @property
    def all_subtasks_done(self) -> bool:
        return bool(self.subtasks) and all(s.done for s in self.subtasks)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def next_due_date(self):
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
            "due_date":     self.due_date.strftime("%Y-%m-%d") if hasattr(self.due_date, "strftime") else self.due_date,
            "priority":     self.priority,
            "category":     self.category,
            "recurrence":   self.recurrence,
            "attachments":  self.attachments,
            "subtasks":     [s.to_dict() for s in self.subtasks],
            "created_at":   self.created_at,
            "completed_at": self.completed_at,
        }

    @staticmethod
    def from_dict(data):
        from datetime import datetime as _dt
        due_raw = data.get("due_date")
        if isinstance(due_raw, str) and due_raw:
            try:
                due_date = _dt.strptime(due_raw, "%Y-%m-%d").date()
            except ValueError:
                due_date = None
        else:
            due_date = due_raw   # None or already a date object

        task = Task(
            data["name"],
            data.get("description", ""),
            due_date,
            data.get("priority", "Medium"),
        )
        task.done         = data.get("done", False)
        task.category     = data.get("category", "General")
        task.recurrence   = data.get("recurrence", None)
        task.attachments  = data.get("attachments", [])
        task.subtasks     = [Task.from_dict(s) for s in data.get("subtasks", [])]
        task.created_at   = data.get("created_at",   _dt.now().strftime("%Y-%m-%d %H:%M:%S"))
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