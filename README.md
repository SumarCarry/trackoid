# TRACKOID — Daily Habit Tracker

TRACKOID is a small, self-hosted habit and task tracker. It runs with only the Python standard library and stores data in SQLite, so there are no third-party packages or separate database services to install.

## Requirements

- Python 3.10 or newer
- A writable application directory

## Start locally

```sh
python3 main.py
```

Open <http://127.0.0.1:8765>. The database is created automatically as `tracker.sqlite3` beside `main.py`.

The default server listens only on the local computer. To allow access from other computers on a trusted private network:

```sh
python3 main.py --host 0.0.0.0 --port 8765 --no-browser
```

Then open `http://<server-LAN-IP>:8765` from another computer. You may need to allow inbound TCP traffic on that port in the host computer's firewall. Do not expose this server directly to the public internet: it has no login system or HTTPS.

## Configuration

Command-line options:

```text
--host HOST       Interface to listen on (default: 127.0.0.1)
--port PORT       TCP port (default: 8765, or PORT environment variable)
--no-browser      Do not open a browser when the server starts
```

Set `TRACKER_DATABASE` to store the SQLite database somewhere else:

```sh
TRACKER_DATABASE=/path/to/tracker.sqlite3 python3 main.py
```

Back up the database while the server is stopped by copying `tracker.sqlite3`. SQLite write-ahead logging is enabled automatically for better reliability when multiple browsers use the app at the same time.

## Features

- Add, complete, and remove daily habits
- Track habits for different calendar days
- Add tasks with optional due dates
- Mark tasks complete or incomplete
- Review weekly and monthly habit progress
- SQLite persistence with foreign-key enforcement
- JSON API validation and useful HTTP error responses

## Troubleshooting

- If the port is busy, choose another one with `--port 9000`.
- If another computer cannot connect, use `--host 0.0.0.0`, confirm both devices are on the same trusted network, and check the host firewall.
- If the app cannot start, verify that the database directory is writable and that Python 3.10+ is installed.

## License

This project is open-source and available for personal use and modification.
