import json
import argparse
import os
import sqlite3
import webbrowser
from calendar import monthrange
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


APP_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("TRACKER_DATABASE", str(APP_DIR / "tracker.sqlite3")))
DEFAULT_HOST = os.environ.get("HOST", "0.0.0.0")
try:
	DEFAULT_PORT = int(os.environ.get("PORT", "8765"))
except ValueError:
	DEFAULT_PORT = 8765
MAX_REQUEST_BODY = 1024 * 1024


def connect_db():
	connection = sqlite3.connect(DATABASE, timeout=10)
	connection.row_factory = sqlite3.Row
	connection.execute("PRAGMA foreign_keys = ON")
	connection.execute("PRAGMA busy_timeout = 10000")
	connection.execute("PRAGMA journal_mode = WAL")
	return connection

def initialize_db():
	DATABASE.parent.mkdir(parents=True, exist_ok=True)
	with connect_db() as connection:
		connection.executescript(
			"""
			CREATE TABLE IF NOT EXISTS habits (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
			);
			CREATE TABLE IF NOT EXISTS habit_logs (
				habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
				day TEXT NOT NULL,
				completed INTEGER NOT NULL DEFAULT 0,
				PRIMARY KEY (habit_id, day)
			);
			CREATE TABLE IF NOT EXISTS tasks (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				title TEXT NOT NULL,
				due_date TEXT,
				completed INTEGER NOT NULL DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
			);
			"""
		)


class TrackerHandler(BaseHTTPRequestHandler):
	def send_json(self, payload, status=200):
		body = json.dumps(payload).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json; charset=utf-8")
		self.send_header("Cache-Control", "no-store")
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		try:
			self.wfile.write(body)
		except BrokenPipeError:
			pass

	def read_json(self):
		try:
			length = int(self.headers.get("Content-Length", "0"))
		except ValueError as error:
			raise ValueError("Invalid Content-Length") from error
		if length < 0 or length > MAX_REQUEST_BODY:
			raise ValueError("Request body is too large")
		return json.loads(self.rfile.read(length) or b"{}")

	def read_object(self):
		payload = self.read_json()
		if not isinstance(payload, dict):
			raise ValueError("JSON body must be an object")
		return payload

	def send_not_found(self):
		self.send_json({"error": "Not found"}, 404)

	def do_GET(self):
		parsed = urlparse(self.path)
		if parsed.path == "/api/state":
			selected_day = parse_qs(parsed.query).get("date", [date.today().isoformat()])[0]
			try:
				date.fromisoformat(selected_day)
			except ValueError:
				self.send_json({"error": "Invalid date"}, 400)
				return

			with connect_db() as connection:
				habits = connection.execute(
					"""
					SELECT habits.id, habits.name, COALESCE(habit_logs.completed, 0) AS completed
					FROM habits
					LEFT JOIN habit_logs ON habit_logs.habit_id = habits.id AND habit_logs.day = ?
					ORDER BY habits.id
					""",
					(selected_day,),
				).fetchall()
				tasks = connection.execute(
					"SELECT id, title, due_date, completed FROM tasks ORDER BY completed, due_date IS NULL, due_date, id"
				).fetchall()
			self.send_json(
				{
					"date": selected_day,
					"habits": [dict(row) for row in habits],
					"tasks": [dict(row) for row in tasks],
				}
			)
			return

		if parsed.path == "/api/progress":
			query = parse_qs(parsed.query)
			period = query.get("period", ["week"])[0]
			anchor_value = query.get("date", [date.today().isoformat()])[0]
			if period not in ("week", "month"):
				self.send_json({"error": "Period must be week or month"}, 400)
				return
			try:
				anchor = date.fromisoformat(anchor_value)
			except ValueError:
				self.send_json({"error": "Invalid date"}, 400)
				return

			if period == "week":
				start = anchor - timedelta(days=anchor.weekday())
				end = start + timedelta(days=6)
			else:
				start = anchor.replace(day=1)
				end = anchor.replace(day=monthrange(anchor.year, anchor.month)[1])
			today = date.today()
			with connect_db() as connection:
				habit_dates = connection.execute("SELECT date(created_at, 'localtime') AS created_day FROM habits").fetchall()
				logs = connection.execute(
					"SELECT habit_logs.day, COUNT(*) AS completed FROM habit_logs "
					"JOIN habits ON habits.id = habit_logs.habit_id "
					"AND date(habits.created_at, 'localtime') <= habit_logs.day "
					"WHERE habit_logs.completed = 1 AND habit_logs.day BETWEEN ? AND ? "
					"GROUP BY habit_logs.day",
					(start.isoformat(), end.isoformat()),
				).fetchall()
			created_days = [date.fromisoformat(row["created_day"]) for row in habit_dates]
			completed_by_day = {row["day"]: row["completed"] for row in logs}
			days = []
			completed_total = 0
			possible_total = 0
			active_days = 0
			perfect_days = 0
			for offset in range((end - start).days + 1):
				day = start + timedelta(days=offset)
				is_future = day > today
				total = sum(created_day <= day for created_day in created_days)
				completed = completed_by_day.get(day.isoformat(), 0)
				days.append(
					{
						"date": day.isoformat(),
						"completed": completed,
						"total": total,
						"rate": round(completed / total * 100) if total else 0,
						"future": is_future,
					}
				)
				if not is_future:
					completed_total += completed
					possible_total += total
					active_days += completed > 0
					perfect_days += total > 0 and completed == total
			self.send_json(
				{
					"period": period,
					"start": start.isoformat(),
					"end": end.isoformat(),
					"days": days,
					"completed": completed_total,
					"possible": possible_total,
					"rate": round(completed_total / possible_total * 100) if possible_total else 0,
					"active_days": active_days,
					"perfect_days": perfect_days,
				}
			)
			return

		if parsed.path in ("/", "/index.html"):
			page = (APP_DIR / "index.html").read_bytes()
			self.send_response(200)
			self.send_header("Content-Type", "text/html; charset=utf-8")
			self.send_header("Cache-Control", "no-store")
			self.send_header("Content-Length", str(len(page)))
			self.end_headers()
			self.wfile.write(page)
			return

		self.send_not_found()

	def do_POST(self):
		parsed = urlparse(self.path)
		try:
			payload = self.read_object()
		except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
			self.send_json({"error": "Invalid JSON"}, 400)
			return

		if parsed.path == "/api/habits":
			name = payload.get("name")
			if not isinstance(name, str):
				self.send_json({"error": "Habit name must be a string"}, 400)
				return
			name = name.strip()
			if not name or len(name) > 80:
				self.send_json({"error": "Habit names must be 1 to 80 characters"}, 400)
				return
			with connect_db() as connection:
				cursor = connection.execute("INSERT INTO habits (name) VALUES (?)", (name,))
				habit_id = cursor.lastrowid
			self.send_json({"id": habit_id, "name": name}, 201)
			return

		if parsed.path == "/api/tasks":
			title = payload.get("title")
			if not isinstance(title, str):
				self.send_json({"error": "Task title must be a string"}, 400)
				return
			title = title.strip()
			due_date = payload.get("due_date")
			if not title or len(title) > 160:
				self.send_json({"error": "Tasks must be 1 to 160 characters"}, 400)
				return
			if due_date == "":
				due_date = None
			if due_date is not None and not isinstance(due_date, str):
				self.send_json({"error": "Invalid due date"}, 400)
				return
			if due_date:
				try:
					date.fromisoformat(due_date)
				except (TypeError, ValueError):
					self.send_json({"error": "Invalid due date"}, 400)
					return
			with connect_db() as connection:
				cursor = connection.execute(
					"INSERT INTO tasks (title, due_date) VALUES (?, ?)", (title, due_date)
				)
				task_id = cursor.lastrowid
			self.send_json({"id": task_id, "title": title, "due_date": due_date}, 201)
			return

		parts = parsed.path.strip("/").split("/")
		if len(parts) == 4 and parts[0] == "api" and parts[1] in ("habits", "tasks") and parts[3] == "toggle":
			entity, identifier = parts[1], parts[2]
			table = "habits" if entity == "habits" else "tasks" if entity == "tasks" else None
			try:
				item_id = int(identifier)
			except ValueError:
				self.send_not_found()
				return
			if type(payload.get("completed")) is not bool:
				self.send_json({"error": "completed must be a boolean"}, 400)
				return
			completed = int(payload["completed"])
			if table == "habits":
				selected_day = payload.get("date", date.today().isoformat())
				try:
					date.fromisoformat(selected_day)
				except (TypeError, ValueError):
					self.send_json({"error": "Invalid date"}, 400)
					return
				with connect_db() as connection:
					if connection.execute("SELECT 1 FROM habits WHERE id = ?", (item_id,)).fetchone() is None:
						self.send_json({"error": "Habit not found"}, 404)
						return
					connection.execute(
						"INSERT INTO habit_logs (habit_id, day, completed) VALUES (?, ?, ?) "
						"ON CONFLICT(habit_id, day) DO UPDATE SET completed = excluded.completed",
						(item_id, selected_day, completed),
					)
			elif table == "tasks":
				with connect_db() as connection:
					cursor = connection.execute("UPDATE tasks SET completed = ? WHERE id = ?", (completed, item_id))
					if cursor.rowcount == 0:
						self.send_json({"error": "Task not found"}, 404)
						return
			else:
				self.send_not_found()
				return
			self.send_json({"ok": True})
			return

		self.send_not_found()

	def do_DELETE(self):
		parts = urlparse(self.path).path.strip("/").split("/")
		if len(parts) != 3 or parts[0] != "api" or parts[1] not in ("habits", "tasks"):
			self.send_not_found()
			return
		try:
			item_id = int(parts[2])
		except ValueError:
			self.send_not_found()
			return
		table = "habits" if parts[1] == "habits" else "tasks"
		with connect_db() as connection:
			cursor = connection.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
			if cursor.rowcount == 0:
				self.send_json({"error": f"{parts[1][:-1].capitalize()} not found"}, 404)
				return
		self.send_json({"ok": True})

	def log_message(self, format_string, *args):
		pass


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Run the TRACKOID habit tracker web app.")
	parser.add_argument("--host", default=DEFAULT_HOST, help="Interface to listen on (default: all network interfaces)")
	parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
	parser.add_argument("--no-browser", action="store_true", default=bool(os.environ.get("PORT")), help="Do not open a browser on the server machine")
	args = parser.parse_args()

	initialize_db()
	local_address = f"http://127.0.0.1:{args.port}"
	print(f"TRACKOID is listening on {args.host}:{args.port}")
	print(f"On this computer, open {local_address}")
	print("On another computer on the same network, open http://<server-LAN-IP>:" + str(args.port))
	if not args.no_browser:
		webbrowser.open(local_address)
	class ReusableHTTPServer(ThreadingHTTPServer):
		allow_reuse_address = True

	try:
		ReusableHTTPServer((args.host, args.port), TrackerHandler).serve_forever()
	except KeyboardInterrupt:
		print("\nTracker stopped.")
	except OSError as error:
		print(f"Could not start TRACKOID on {args.host}:{args.port}: {error}")
		raise SystemExit(1)
