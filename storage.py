import json
from datetime import datetime
from tasks import Task

FILENAME = "data.json"
CONFIG_FILE = "config.json"

def save_tasks(manager):
    data = []

    for task in manager.tasks:
        data.append({
            "name": task.name,
            "description": task.description,
            "due_date": task.due_date.strftime("%Y-%m-%d") if task.due_date else None,
            "priority": task.priority,
            "done": task.done
        })

    with open("tasks.json", "w") as file:
        json.dump(data, file, indent=4)

def load_tasks(manager):
    try:
        with open("tasks.json", "r") as file:
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

            manager.tasks.append(task)

    except FileNotFoundError:
        pass
        
def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "dark_mode": False,
            "sort": "due_date",
            "filter": "All"
        }