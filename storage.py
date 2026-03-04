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

                due_date = task_data.get("due_date")

                # 🔥 CONVERT STRING → DATE HERE
                if due_date:
                    due_date = datetime.strptime(due_date, "%Y-%m-%d").date()

                task = Task(
                    task_data["name"],
                    task_data["description"],
                    due_date,
                    task_data["priority"],
                    task_data["done"]
                )

                manager.tasks.append(task)

    except FileNotFoundError:
        pass
        
def save_config(dark_mode: bool):
    import json
    with open(CONFIG_FILE, "w") as f:
        json.dump({"dark_mode": dark_mode}, f, indent=4)


def load_config():
    import json
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return data.get("dark_mode", False)
    except FileNotFoundError:
        return False