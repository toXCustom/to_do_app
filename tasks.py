class Task:
    def __init__(self, name, description, done=False):
        self.name = name
        self.description = description
        self.done = done
        
    def mark_done(self):
        self.done = True
        
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description
        }
        
    @staticmethod
    def from_dict(data):
        return Task(
            data["name"],
            data["description"],
            data.get("done", False)
        )
        
class TaskManager: #clearing a class TaskManager, to manage all the tasks in the dictionary
    def __init__(self):
        self.tasks = []
        
    def add_task(self, name, description):
        if any(task.name == name for task in self.tasks):
            print("Task already exists!")
            return
        self.tasks.append(Task(name, description))
        print("Task added!")
    
    def view_tasks(self): #view all the tasks
        if not self.tasks:
            print("No tasks available.")
            return
        for i, task in enumerate(self.tasks, 1):
            status = "✔" if task.done else "✘"
            print(f"{i}. {task.name} - {task.description} [{status}]")
        
    def delete_task(self, name): #delete a task
        for task in self.tasks:
            if task.name == name:
                self.tasks.remove(task)
                print("Task deleted!")
                return
        print("Task not found.")

    def mark_done(self, name): #mark one of the task as done
        for task in self.tasks:
            if task.name == name:
                task.mark_done()
                print("Task marked as done!")
                return
        print("Task not found.")

    def to_list(self):
        return [task.to_dict() for task in self.tasks]

    def load_from_list(self, data_list): #loading the dictionary from the data.json
        self.tasks = [Task.from_dict(data) for data in data_list]