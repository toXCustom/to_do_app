import json

FILENAME = "data.json"

def save_tasks(tasks): #save a new task to the dictionary
    with open(FILENAME, "w") as f:
        json.dump(tasks, f, indent=4)
    print("Tasks have been saved.")

def load_tasks(): #load all the tasks from the data.json
    try:
        with open(FILENAME, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): #when the file is empty
        return {}