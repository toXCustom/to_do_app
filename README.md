📝 To-Do App (Python)

A modular To-Do application built in Python to practice clean architecture, OOP principles, file persistence, and scalable project structure.

This project evolves step-by-step from a simple console application to more advanced versions (GUI, Web, or Mobile).

🚀 Project Goals

Practice Python fundamentals

Implement Object-Oriented Programming (OOP)

Work with JSON file storage

Design clean project architecture

Prepare a scalable base for future expansion (GUI, Web, Mobile)

🛠 Tech Stack

Python 3.10+

JSON (data storage)

Optional extensions:

tkinter (Desktop GUI)

Flask / Django (Web version)

Kivy / BeeWare (Mobile version)

📂 Project Structure

todo_app/
│
├── main.py        # Application entry point
├── tasks.py       # Task and TaskManager logic
├── storage.py     # Save / load logic (JSON)
├── data.json      # Persistent storage

✅ Features (Current Version)
Core (MVP)

➕ Add a task

📋 View tasks

❌ Delete a task

✔ Mark task as completed

💾 Automatic saving to JSON

🔄 Application Flow
START
 ↓
Load tasks from file
 ↓
Display menu
 ↓
User selects option
 ↓
Execute action
 ↓
Save changes
 ↓
Return to menu
🧠 Concepts Practiced
🟢 Fundamentals

Variables

Lists & dictionaries

Functions

Loops

Conditionals

File handling

🟡 Intermediate

Classes (OOP)

Data serialization (JSON)

Project modularization

Clean architecture separation

🏗 Development Roadmap
Phase 1 – Console Version (Current)

Fully working CLI application

JSON persistence

OOP architecture

Phase 2 – Extended Features

📅 Due dates

⭐ Priority levels

🔍 Filtering tasks

📂 Categories

Phase 3 – GUI Version

Desktop app using tkinter

Phase 4 – Web Version

Backend: Flask

Frontend: HTML + CSS

Phase 5 – Mobile Version

Kivy → Generate Android APK

📦 Installation
git clone https://github.com/your-username/todo-app.git
cd todo-app
python main.py
📈 Future Improvements

User authentication

SQLite database integration

REST API

Online synchronization

Cloud deployment

🎯 Why This Project Matters

This project demonstrates:

Clean separation of concerns

Scalable architecture

Understanding of persistence

Transition from procedural programming to OOP

Readiness to expand into real-world applications

📸 Screenshots

(Add screenshots here when GUI version is ready)

👨‍💻 Author

Paweł Mróz
Python Developer (learning path → Desktop → Web → Mobile)

-----

🎯 What You Now Have

You can:

Sort by:
- Due date (smart grouping)
- Creation date
- Priority
- Alphabetical

Filter:
- All tasks
- Active
- Completed
- Overdue

🚀 Your App Is Now:
✔ Multi-criteria sorting
✔ Multi-filter system
✔ Priority system
✔ Creation timestamps
✔ GUI controls
✔ Smart overdue logic


--- version 0.1.100 ---
Changes:
- from writing the date to pick it up from the calendar directly
- the priority is shown in the list of the tasks
- priority right now will determine the color on how the task will be shown (Overdue always red)

Bug fixed:
- delete task button was not working, right now it's back and working again



--- version 0.1.103 ---
Changes:
- remember last sorting & filter choice
- added the search bar at the top
- better UI for the search bar, sorting and filtering

Bug fixed:
n/a



--- version 0.1.107 ---
Changes:
- automatically saves after deletion of a task
- automatically saves after closing the application
- automatically saves after marking task as done
- automatically saves every 10 seconds

Bug fixed:
- Mark Done button was not working, fixed



--- version 0.1.109 ---
Changes:
- the view of the task right now in a table not just plain text
- changed a little bit the colorign for Light/Dark mode

Bug fixed:
n/a



--- version 0.2.101 ---
Changes:
- when adding a new task, right now you have only one window where you can add all the necessary information
- added the button and the possibility to edit the tasks

Bug fixed:
-



--- version 0.2.105 --- 09.03.2026
Changes:
- module-level theme constants — LIGHT_THEME and DARK_THEME
- recursive theming — A new _apply_theme_to_widget(widget, theme) helper walks each widget and all its descendants
- _days_info() helper — the duplicated days calculation is now a single @staticmethod
- changed the coloring of the LIGHT_THEME and DARK_THEME

Bug fixed:
- top.mainloop() removed from both dialogs
- duplicate Calendar in edit_task_gui removed


--- version 0.3.101 --- 10.03.2026
Changes:
- complete rework of the UI of the application
- double click on the Task right now open the Edit Task

Bug fixed:
-


--- version 0.3.103 ---
Changes:
- checkbox column — a new unlabelled first column shows ☐ for incomplete and ☑ for done
- better sorting UI, different button for every single sort possibility
- autosave feature right now saves the size of the window the user had before closing

Bug fixed:
-


--- version 0.3.102 ---
Changes:
- 

Bug fixed:
-


--- version 0.3.102 ---
Changes:
- 

Bug fixed:
-


--- version 0.3.102 ---
Changes:
- 

Bug fixed:
-


--- version 0.3.102 ---
Changes:
- 

Bug fixed:
-


--- version 0.3.102 ---
Changes:
- 

Bug fixed:
-