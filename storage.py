import json

FILENAME = "data.json"

def save_tasks(task_manager): #save a new task to the dictionary
    with open(FILENAME, "w") as f:
        json.dump(task_manager.to_list(), f, indent=4)

def load_tasks(task_manager): #load all the tasks from the data.json
    try:
        with open(FILENAME, "r") as f:
            data = json.load(f)
            task_manager.load_from_list(data)
    except (FileNotFoundError, json.JSONDecodeError):
        pass