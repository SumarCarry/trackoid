Daily Habit Tracker
A lightweight Python application designed to help you build better routines by tracking your daily habits.

Features
Add New Habits: Easily define new habits you want to incorporate into your daily life.
Track Daily Progress: Log your daily activities and mark habits as completed.
Local Database Storage: Uses a lightweight SQLite database to securely store your habit data directly on your machine.

Prerequisites
Before running this application, make sure you have the following installed:
Python 3.x (You can download it from python.org)

Installation
1. Clone this repository to your local machine:

git clone https://github.com/SumarCarry/my_first_python_app.git

2. Navigate into the project directory:

cd my_first_python_app

3. Usage
Start the tracker on the computer that will host it:

```sh
python3 main.py
```

By default, the server listens on all network interfaces at port `8765`. Open
`http://127.0.0.1:8765` on the host computer. To use it from another computer
on the same local network, open `http://<host-computer-LAN-IP>:8765` in that
computer's browser. Find the host's LAN IP in its network settings (for example,
an address beginning with `192.168.` or `10.`).

If the other computer cannot connect, allow inbound TCP traffic on port `8765`
in the host computer's firewall and make sure both computers are on the same
trusted network. The app stores its SQLite database beside `main.py`; keep that
directory writable and back up `tracker.sqlite3` to preserve the data.

To choose a different port or bind only to a specific interface:

```sh
python3 main.py --host 0.0.0.0 --port 9000
```

Use `--no-browser` when running on a headless host. This built-in server has no
login or encryption, so use it only on a trusted private network; do not expose
it directly to the public internet.

(Note: If you are using a Mac or Linux environment, you might need to use python3 main.py)

Technologies Used
1. Python 3: The core programming language used to build the application logic.
2. SQLite3: A built-in Python library used to handle the database creation and data management locally.

License
This project is open-source and available for personal use and modification.
