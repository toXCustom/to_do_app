import json

FILENAME = "data.json"

def save_tasks(tasks):
    with open(FILENAME, "w") as f:
        json.dump(tasks, f, indent=4)
    print("Tasks have been saved.")

def load_tasks():
    try:
        with open(FILENAME, "r") as f:
            tasks = json.load(f)
        return tasks
    except FileNotFoundError:
        return {}