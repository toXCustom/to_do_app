import json
from tasks import TaskManager, Task

FILENAME = "data.json"
CONFIG_FILE = "config.json"

def save_tasks(task_manager: TaskManager):
    data_list = [task.to_dict() for task in task_manager.tasks]
    with open(FILENAME, "w") as f:
        json.dump(data_list, f, indent=4)

def load_tasks(task_manager: TaskManager):
    try:
        with open(FILENAME, "r") as f:
            data_list = json.load(f)
        task_manager.tasks = [Task.from_dict(d) for d in data_list]
    except FileNotFoundError:
        task_manager.tasks = []
        
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