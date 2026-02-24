
🔧 1. Czego potrzebujesz
📦 Podstawy techniczne
📦 Python 3.10+

Edytor kodu:
🟢 Visual Studio Code

📚 Biblioteki (zależnie od wersji aplikacji)
🔹 Wersja 1 – Konsolowa Nie potrzebujesz żadnych dodatkowych bibliotek.
🔹 Wersja 2 – Okienkowa (GUI) tkinter (wbudowane w Python)
🔹 Wersja 3 – Webowa | Flask lub Django
🔹 Wersja 4 – Mobilna | Kivy lub BeeWare

📖 2. Czego musisz się nauczyć
🟢 Absolutne podstawy
zmienne
listy i słowniki
funkcje
pętle
instrukcje warunkowe
obsługa plików (zapisywanie zadań)

🟡 Poziom średni
klasy (OOP)
JSON
podstawy UI (jeśli GUI)
podstawy pracy z bazą danych (SQLite)

🧠 3. Zaplanowanie funkcji aplikacji

Minimalna wersja To-Do:
➕ dodawanie zadania
📋 wyświetlanie zadań
❌ usuwanie zadania
✔ oznaczanie jako wykonane
💾 zapisywanie do pliku

Rozszerzona wersja:
📅 termin wykonania
⭐ priorytet
🔍 filtrowanie
📂 kategorie
👤 logowanie użytkownika

🏗 4. Architektura projektu
Przykładowa struktura:

todo_app/
│
├── main.py
├── tasks.py
├── storage.py
├── data.json

Co robi każdy plik?
main.py → uruchamia aplikację
tasks.py → logika zadań
storage.py → zapis/odczyt danych
data.json → przechowywanie zadań

🔄 5. WORKFLOW (jak pracować nad projektem)
🔹 Etap 1 – Plan
Spisz funkcje aplikacji
Zrób szkic jak ma działać
Zdecyduj: konsola czy GUI?

🔹 Etap 2 – MVP (Minimum Viable Product)
Zrób najprostszą wersję:
Lista w Pythonie jako baza danych
Menu tekstowe:
1. Dodaj zadanie
2. Pokaż zadania
3. Usuń zadanie
4. Wyjście
Nie przejmuj się wyglądem.

🔹 Etap 3 – Zapis do pliku
Dodaj:
zapis do JSON
odczyt przy starcie programu

🔹 Etap 4 – Refaktoryzacja
podziel kod na funkcje
potem na klasy
popraw czytelność

🔹 Etap 5 – Rozbudowa
Dodaj:
priorytety
daty
filtrowanie
GUI

🗂 6. Schemat działania aplikacji
START
 ↓
Wczytaj dane z pliku
 ↓
Pokaż menu
 ↓
Użytkownik wybiera opcję
 ↓
Wykonaj akcję
 ↓
Zapisz zmiany
 ↓
Powrót do menu

🚀 7. Jak możesz to rozwinąć później
Skoro interesują Cię aplikacje mobilne:
🔹 Opcja 1 – Desktop
GUI w tkinter

🔹 Opcja 2 – Web
Backend: Flask
Frontend: HTML + CSS

🔹 Opcja 3 – Android
Użyj:
Kivy → generuje APK

📈 8. Jak zrobić z tego projekt do portfolio
Dodaj:
README
screenshoty
instrukcję instalacji
wrzuć na GitHub

Możesz potem zrobić:
synchronizację online
konto użytkownika
API

🎯 Plan nauki dla Ciebie (realny)

Tydzień 1 → konsolowa wersja
Tydzień 2 → zapis do JSON
Tydzień 3 → GUI
Tydzień 4 → wersja mobilna
