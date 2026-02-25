from tasks import TaskManager
from storage import save_tasks, load_tasks
from datetime import datetime, date

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
            description = input("Description: ")
            due_date = input("Due date (YYYY-MM-DD) or leave empty: ")
            
            if due_date == "":
                due_date = None
            
            try: #validate date format
                if due_date:
                    datetime.strptime(due_date, "%Y-%m-%d")
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD.")
                continue #stops this function and goes back to menu

            manager.add_task(name, description, due_date)
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