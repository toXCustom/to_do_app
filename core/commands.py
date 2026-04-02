"""
commands.py — Command Pattern for Undo / Redo

Each Command captures enough state to both execute and reverse an action.
The CommandHistory manages two stacks: undo and redo.
"""
import copy
from datetime import datetime


# ── Base ──────────────────────────────────────────────────────────────────────

class Command:
    """Abstract base — subclasses implement execute() and undo()."""
    description = "Unknown action"

    def execute(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError


# ── Concrete commands ─────────────────────────────────────────────────────────

class AddTaskCommand(Command):
    def __init__(self, manager, task):
        self.manager = manager
        self.task    = task
        self.description = 'Add "' + task.name + '"'

    def execute(self):
        if self.task not in self.manager.tasks:
            self.manager.tasks.append(self.task)

    def undo(self):
        if self.task in self.manager.tasks:
            self.manager.tasks.remove(self.task)


class DeleteTaskCommand(Command):
    def __init__(self, manager, task):
        self.manager  = manager
        self.task     = task
        self.index    = manager.tasks.index(task)
        self.description = 'Delete "' + task.name + '"'

    def execute(self):
        if self.task in self.manager.tasks:
            self.manager.tasks.remove(self.task)

    def undo(self):
        if self.task not in self.manager.tasks:
            self.manager.tasks.insert(self.index, self.task)


class EditTaskCommand(Command):
    def __init__(self, task, before: dict, after: dict):
        self.task   = task
        self.before = before   # snapshot before edit
        self.after  = after    # snapshot after edit
        self.description = 'Edit "' + before.get('name', task.name) + '"'

    def execute(self):
        _apply_snapshot(self.task, self.after)

    def undo(self):
        _apply_snapshot(self.task, self.before)


class MarkDoneCommand(Command):
    def __init__(self, task, previous_done: bool):
        from datetime import datetime as _dt
        self.task          = task
        self.previous_done = previous_done
        self.prev_completed_at = task.completed_at
        self.description   = ('Mark "' + task.name + '" done') if not previous_done else ('Unmark "' + task.name + '"')
        self._now          = _dt.now().strftime("%Y-%m-%d %H:%M:%S")

    def execute(self):
        self.task.done = True
        self.task.completed_at = self._now
        self.task.update_status()

    def undo(self):
        self.task.done = self.previous_done
        self.task.completed_at = self.prev_completed_at
        self.task.update_status()


class ToggleDoneCommand(Command):
    def __init__(self, task):
        from datetime import datetime as _dt
        self.task          = task
        self.previous_done = task.done
        self.prev_completed_at = task.completed_at
        state = "done" if not task.done else "active"
        self.description   = 'Toggle "' + task.name + '" → ' + state
        self._now          = _dt.now().strftime("%Y-%m-%d %H:%M:%S")

    def execute(self):
        self.task.done = not self.previous_done
        self.task.completed_at = self._now if self.task.done else None
        self.task.update_status()

    def undo(self):
        self.task.done = self.previous_done
        self.task.completed_at = self.prev_completed_at
        self.task.update_status()


# ── Snapshot helpers ──────────────────────────────────────────────────────────

def snapshot(task) -> dict:
    """Capture all mutable fields of a task as a plain dict."""
    return {
        "name":         task.name,
        "description":  task.description,
        "priority":     task.priority,
        "due_date":     task.due_date,
        "done":         task.done,
        "category":     getattr(task, "category",   "General"),
        "completed_at": getattr(task, "completed_at", None),
        "recurrence":   getattr(task, "recurrence",  None),
    }


def _apply_snapshot(task, snap: dict):
    task.name         = snap["name"]
    task.description  = snap["description"]
    task.priority     = snap["priority"]
    task.due_date     = snap["due_date"]
    task.done         = snap["done"]
    task.category     = snap.get("category",   "General")
    task.completed_at = snap.get("completed_at", None)
    task.recurrence   = snap.get("recurrence",   None)
    task.update_status()


# ── History manager ───────────────────────────────────────────────────────────

class CommandHistory:
    MAX = 50   # maximum undo steps kept

    def __init__(self):
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []

    def execute(self, cmd: Command):
        """Run a command and push it onto the undo stack."""
        cmd.execute()
        self._undo_stack.append(cmd)
        if len(self._undo_stack) > self.MAX:
            self._undo_stack.pop(0)
        self._redo_stack.clear()   # new action breaks the redo chain

    def undo(self) -> str | None:
        """Undo the last command. Returns its description or None."""
        if not self._undo_stack:
            return None
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        return cmd.description

    def redo(self) -> str | None:
        """Redo the last undone command. Returns its description or None."""
        if not self._redo_stack:
            return None
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        return cmd.description

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo_label(self) -> str:
        return self._undo_stack[-1].description if self._undo_stack else ""

    def redo_label(self) -> str:
        return self._redo_stack[-1].description if self._redo_stack else ""