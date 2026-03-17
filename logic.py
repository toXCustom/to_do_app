"""
No tkinter, no tkcalendar, no GUI imports whatsoever.
Import this from both app.py and test_todo.py.
"""

from datetime import datetime, date


def days_info(task):
    """
    Return a human-readable string describing how far away a task's due date is.
    Returns "" if the task has no due date.
    """
    if not task.due_date:
        return ""
    due = _as_date(task.due_date)
    days_left = (due - date.today()).days
    if days_left > 0:
        return f"{days_left} days left"
    if days_left == 0:
        return "Due today"
    return f"{abs(days_left)} days overdue"


def get_filtered_tasks(tasks, filter_by, search, calendar_date_filter=None):
    """
    Apply filter, search and optional calendar-day filter to a flat list of tasks.

    Args:
        tasks:                  list of Task objects
        filter_by:              "All" | "Active" | "Completed" | "Overdue"
        search:                 lowercase search string (empty = no filter)
        calendar_date_filter:   datetime.date or None

    Returns:
        filtered list of Task objects
    """
    result = list(tasks)

    if filter_by == "Active":
        result = [t for t in result if not t.done]
    elif filter_by == "Completed":
        result = [t for t in result if t.done]
    elif filter_by == "Overdue":
        result = [t for t in result if t.is_overdue]

    if search:
        s = search.lower().strip()
        result = [t for t in result
                  if s in t.name.lower() or s in t.description.lower()]

    if calendar_date_filter:
        result = [t for t in result
                  if _as_date(t.due_date) == calendar_date_filter]

    return result


def get_sorted_tasks(tasks, sort_by, reverse=False):
    """
    Sort a list of tasks.

    Args:
        tasks:    list of Task objects
        sort_by:  "due_date" | "creation_date" | "priority" | "alphabetical"
        reverse:  True = descending

    Returns:
        new sorted list
    """
    def sort_key(task):
        if sort_by == "due_date":
            d = _as_date(task.due_date)
            return d if d else date.max
        elif sort_by == "creation_date":
            return _as_datetime(task.created_at)
        elif sort_by == "priority":
            return {"High": 1, "Medium": 2, "Low": 3}.get(task.priority, 2)
        elif sort_by == "category":
            return getattr(task, "category", "General").lower()
        else:   # alphabetical
            return task.name.lower()

    return sorted(tasks, key=sort_key, reverse=reverse)


# ── Internal helpers ────────────────────────────────────────────────────────

def _as_date(value):
    # Coerce a str | date | None to a date object (or None).
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def _as_datetime(value):
    """Coerce a str | datetime to a datetime object."""
    if isinstance(value, datetime):
        return value
    # Try common serialisation formats
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            pass
    return datetime.min   # fallback — keeps sorting stable