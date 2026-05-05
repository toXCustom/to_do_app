"""
logic.py  —  Pure business logic extracted from app.py
=======================================================
No tkinter, no tkcalendar, no GUI imports whatsoever.
Import this from both app.py and test_todo.py.
"""

from datetime import datetime, date

# Pre-compute priority order once
_PRIO_ORDER = {"High": 1, "Medium": 2, "Low": 3}
_DATE_MAX   = date.max


def days_info(task) -> str:
    """Human-readable due-date distance string, or empty."""
    due = _as_date(task.due_date)
    if not due:
        return ""
    delta = (due - date.today()).days
    if delta > 0:   return f"{delta} days left"
    if delta == 0:  return "Due today"
    return f"{abs(delta)} days overdue"


def get_filtered_tasks(tasks, filter_by, search, calendar_date_filter=None):
    """
    Apply filter, search and optional calendar-day filter to a flat list of tasks.
    Returns a filtered list.
    """
    result = tasks   # avoid copying when no filter needed

    if filter_by == "Active":
        result = [t for t in result if not t.done]
    elif filter_by == "Completed":
        result = [t for t in result if t.done]
    elif filter_by == "Overdue":
        result = [t for t in result if t.is_overdue]
    else:
        result = list(result)   # copy so callers can mutate

    if search:
        s = search.lower().strip()
        result = [t for t in result
                  if s in t.name.lower() or s in t.description.lower()]

    if calendar_date_filter:
        result = [t for t in result
                  if _as_date(t.due_date) == calendar_date_filter]

    return result


def get_sorted_tasks(tasks, sort_by, reverse=False):
    """Sort a list of tasks by the given key."""
    if sort_by == "due_date":
        key = lambda t: _as_date(t.due_date) or _DATE_MAX   # noqa
    elif sort_by == "creation_date":
        key = lambda t: _as_datetime(t.created_at)          # noqa
    elif sort_by == "priority":
        key = lambda t: _PRIO_ORDER.get(t.priority, 2)      # noqa
    elif sort_by == "category":
        key = lambda t: getattr(t, "category", "General").lower()  # noqa
    else:   # alphabetical
        key = lambda t: t.name.lower()                       # noqa

    return sorted(tasks, key=key, reverse=reverse)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _as_date(value):
    if value is None:        return None
    if isinstance(value, date): return value
    try: return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError): return None


def _as_datetime(value):
    if isinstance(value, datetime): return value
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try: return datetime.strptime(value, fmt)
        except (ValueError, TypeError): pass
    return datetime.min
