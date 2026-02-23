from tasks import add_task, view_task, delete_task
from storage import save_tasks, load_tasks

def menu():
    print("-- Choose menu --")
    print("1. Add task")
    print("2. Show task")
    print("3. Delete task")
    print("4. Exit")
    try:
        chosen = int(input("Please choose the menu: "))
        return chosen
    except ValueError:
        print("Please enter a number!")
        return 0

def main():    
    tasks = load_tasks()

    while True:
        chosen = menu()
        if chosen == 1:
            task_name = input("What is the task name?")
            task_description = input("What is the task? Describe what to do")
            add_task(tasks, task_name, task_description)
            save_tasks(tasks)
        elif chosen == 2:
            view_task(tasks)
        elif chosen == 3:
            task_name = input("What is the task to delete?")
            delete_task(tasks, task_name)
            save_tasks(tasks)
        elif chosen == 4:
            break
        else:
            print("Invalid chove,m  try again.")

if __name__ == '__main__':
    main()