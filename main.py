def menu():
    print("1. Add task")
    print("2. Show task")
    print("3. Delete task")
    print("4. Exit")
    chosen = int(input("Please choose the menu!"))
    return chosen

def add_task(tasks):
    task_name = input("What is the task name?")
    if task_name in tasks:
        print("Task is already in the list!")
    else:
        task_description = input("What is the task? Describe what to do")
        tasks[task_name] = task_description
        print("Task has been added!")

def view_task(tasks):
    if not tasks:
        print("No tasks to view")
        return
    else:    
        for name, description in tasks.items():
            print(f"Task: {name}, description: {description}")
            
        print("The list of tasks has been printed")

def delete_task(tasks):
    if not tasks:
        print("No tasks to delete")
        return
    else:
        print("Current tasks:")
        for name, description in tasks.items():
            print(f"Task: {name}, description: {description}")
            
        task_to_delete = input("Which task do you want to delete? ")
        if task_to_delete in tasks:
            del tasks[task_to_delete]
            print(f"Task: {task_to_delete} has been deleted.")
        else:
            print(f"No task names: {task_to_delete} found")

tasks = dict()

while True:
    chosen = menu()
    if chosen == 1:
        add_task(tasks)
    elif chosen == 2:
        view_task(tasks)
    elif chosen == 3:
        delete_task(tasks)
    elif chosen == 4:
        break