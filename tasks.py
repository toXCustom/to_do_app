def add_task(tasks, task_name, task_description): #adding a new task
    if task_name in tasks:
        print("Task is already in the list!")
    else:
        tasks[task_name] = task_description
        print("Task has been added!")

def view_task(tasks): #showing on the screen all the tasks
    if not tasks:
        print("No tasks to view")
        return
    else:    
        for name, description in tasks.items():
            print(f"Task: {name}, description: {description}") 
        print("The list of tasks has been printed")

def delete_task(tasks, task_name): #delete a task from the dictionary
    if not tasks:
        print("No tasks to delete")
        return
    else:
        if task_name in tasks:
            del tasks[task_name]
            print(f"Task: {task_name} has been deleted.")
        else:
            print(f"No task names: {task_name} found")