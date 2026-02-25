from datetime import datetime, date

class Task:
    def __init__(self, name, description, done=False, due_date=None):
        self.name = name
        self.description = description
        self.done = done
        self.due_date = due_date
        
    def mark_done(self):
        self.done = True
        
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "done": self.done,
            "due_date": self.due_date
        }

    @property
    def is_overdue(self):
        if self.due_date is None:
            return False
        try:
            due = datetime.strptime(self.due_date, "%Y-%m-%d").date()
            return date.today() > due and not self.done
        except ValueError:
            # Invalid date format, treat as not overdue
            return False
        
    @property
    def days_remaining(self):
        if self.due_date is None:
            return None
        try:
            due = datetime.strptime(self.due_date, "%Y-%m-%d").date()
            delta = (due - date.today()).days
            return delta
        except ValueError:
            # Invalid date format, treat as not overdue
            return None
            
    @staticmethod
    def from_dict(data):
        return Task(
            data["name"],
            data["description"],
            data.get("done", False),
            data.get("due_date", None)
        )
        
class TaskManager: #clearing a class TaskManager, to manage all the tasks in the dictionary
    def __init__(self):
        self.tasks = []
        
    def add_task(self, name, description, due_date=None):
        if any(task.name == name for task in self.tasks):
            print("Task already exists!")
            return
        task = Task(name, description, False, due_date)
        self.tasks.append(task)
        print("Task added!")
    
    def view_tasks(self): #view all the tasks
        if not self.tasks:
            print("No tasks available.")
            return
        
        #Sort tasks: overdue first, then by due date (earliest first), then tasks without due date
        def sort_key(task):
            if task.due_date is None:
                # Tasks without due date go last
                return (1, datetime.max)
            try:
                due = datetime.strptime(task.due_date, "%Y-%m-%d").date()
            except ValueError:
                due = datetime.max  # invalid date → put last
            #Overdue tasks get priority
            overdue_priority = 0 if task.is_overdue else 1
            return (overdue_priority, due)
        sorted_tasks = sorted(self.tasks, key=sort_key)
        
        for i, task in enumerate(sorted_tasks, 1):
            status = "✔" if task.done else "✘"
            if task.done:
                it_is_done = "Done:"
                overdue = ""
                days_remain_str = ""
            else:
                it_is_done = "Due:"
                overdue = " 🔴 OVERDUE" if task.is_overdue else ""
                if task.days_remaining is not None:
                    if task.days_remaining < 0:
                        days_remain_str = f" ({-task.days_remaining} days overdue)"
                    elif task.days_remaining == 0:
                        days_remain_str = " (Due today)"
                    else:
                        days_remain_str = f" ({task.days_remaining} days remaining)"
                else:
                    days_remain_str = ""
            due = task.due_date if task.due_date else "No due date"
            print(f"{i}. [{status}] {task.name} - {task.description} ({it_is_done} {due}{days_remain_str}{overdue})")
        
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