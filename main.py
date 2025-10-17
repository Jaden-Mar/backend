# main.py
import eventlet
eventlet.monkey_patch()  # musi być pierwsze

import os
import sqlite3
import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit

# ------------------------------------------------------------
# KONFIGURACJA
# ------------------------------------------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = "super_secret_key"

socketio = SocketIO(app, async_mode="eventlet")

# ------------------------------------------------------------
# BAZA DANYCH — trwała lokalizacja na Renderze
# ------------------------------------------------------------
DB_PATH = os.environ.get("DB_PATH", "/data/database.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def init_db():
    """Inicjalizacja bazy danych, jeśli nie istnieje."""
    if not os.path.exists(DB_PATH):
        print(f"[INIT] Tworzę bazę danych w {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                last_active TEXT
            )
        """)
        c.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    else:
        print(f"[INFO] Używam istniejącej bazy danych: {DB_PATH}")


def get_db_connection():
    """Zwraca nowe połączenie do bazy."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def update_last_active(user_id):
    """Aktualizuje czas ostatniej aktywności użytkownika."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET last_active=? WHERE id=?",
        (datetime.datetime.now().isoformat(), user_id),
    )
    conn.commit()
    conn.close()


# ------------------------------------------------------------
# ROUTES (Flask)
# ------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    messages = conn.execute("SELECT username, message, timestamp FROM messages ORDER BY id ASC").fetchall()
    conn.close()

    return render_template("index.html", username=session["username"], messages=messages)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            update_last_active(user["id"])
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Niepoprawny login lub hasło")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password, last_active) VALUES (?, ?, ?)",
                (username, password, datetime.datetime.now().isoformat()),
            )
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Użytkownik już istnieje")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------
# SOCKET.IO
# ------------------------------------------------------------
@socketio.on("send_message")
def handle_send_message(data):
    username = session.get("username", "Anonim")
    message = data.get("message", "").strip()

    if not message:
        return

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # zapis do bazy
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO messages (username, message, timestamp) VALUES (?, ?, ?)",
        (username, message, timestamp),
    )
    conn.commit()
    conn.close()

    emit("receive_message", {"username": username, "message": message, "timestamp": timestamp}, broadcast=True)


# ------------------------------------------------------------
# START SERWERA
# ------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    print(f"[RUN] Aplikacja wystartowała na porcie {os.environ.get('PORT', 10000)}")
    print(f"[DB] Ścieżka bazy danych: {DB_PATH}")
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
