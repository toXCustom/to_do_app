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