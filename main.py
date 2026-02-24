from tasks import TaskManager
from storage import save_tasks, load_tasks

def menu(): #calling the menu
    print("\n--- TO DO MENU ---")
    print("1. Add task")
    print("2. Show tasks")
    print("3. Delete task")
    print("4. Mark task as done")
    print("5. Exit")
    try:
        return int(input("Choose option: "))
    except ValueError:
        return 0

def main():
    manager = TaskManager()
    load_tasks(manager)

    while True:
        choice = menu()

        if choice == 1:
            name = input("Task name: ")
            desc = input("Description: ")
            manager.add_task(name, desc)
            save_tasks(manager)

        elif choice == 2:
            manager.view_tasks()

        elif choice == 3:
            name = input("Task name to delete: ")
            manager.delete_task(name)
            save_tasks(manager)

        elif choice == 4:
            name = input("Task name to mark as done: ")
            manager.mark_done(name)
            save_tasks(manager)

        elif choice == 5:
            save_tasks(manager)
            print("Goodbye!")
            break

        else:
            print("Invalid option.")

if __name__ == "__main__": #execyte main only when opened directly
    main()