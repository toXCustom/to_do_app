import json
from datetime import datetime
from tasks import Task

TASKS_FILE = "tasks.json"
CONFIG_FILE = "config.json"


# -----------------------------
# Save tasks
# -----------------------------
def save_tasks(manager):
    data = []

    for task in manager.tasks:
        data.append({
            "name": task.name,
            "description": task.description,
            "due_date": task.due_date.strftime("%Y-%m-%d") if task.due_date else None,
            "priority": task.priority,
            "category": getattr(task, "category", "General"),
            "done": task.done
        })

    with open(TASKS_FILE, "w") as file:
        json.dump(data, file, indent=4)


# -----------------------------
# Load tasks
# -----------------------------
def load_tasks(manager):
    try:
        with open(TASKS_FILE, "r") as file:
            data = json.load(file)

        for task_data in data:

            due = task_data.get("due_date")

            # convert string → date
            if due:
                due = datetime.strptime(due, "%Y-%m-%d").date()

            task = Task(
                task_data["name"],
                task_data.get("description", ""),
                due,
                task_data.get("priority", "Medium")
            )

            task.done = task_data.get("done", False)
            task.category = task_data.get("category", "General")

            manager.tasks.append(task)

    except (FileNotFoundError, json.JSONDecodeError):
        pass


# -----------------------------
# Save GUI config
# -----------------------------
def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


# -----------------------------
# Load GUI config
# -----------------------------
def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)

        # If old version stored just True/False
        if isinstance(config, bool):
            return {
                "dark_mode": config,
                "sort_type": "due_date",
                "filter_type": "All"
            }

        return config

    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "dark_mode": False,
            "sort_type": "due_date",
            "filter_type": "All"
        }