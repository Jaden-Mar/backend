# main.py
import eventlet
eventlet.monkey_patch()  # MUST be first - eventlet needs to monkey-patch before other imports

import os
import sqlite3
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room

# ----------------------------
# CONFIG
# ----------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "super_secret_key_change_this")
# DB path: use /data/database.db on Render for persistence, can override with env var DB_PATH
DB_PATH = os.environ.get("DB_PATH", "/data/database.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# SocketIO using eventlet
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

# ----------------------------
# DATABASE helpers
# ----------------------------
def init_db():
    """Create database and tables if they don't exist."""
    need_init = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    if need_init:
        print(f"[INIT] Creating new SQLite DB at {DB_PATH}")
    else:
        print(f"[INFO] Using existing DB at {DB_PATH}")
    # create users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            last_active TEXT
        );
    """)
    # create messages table (global chat + optional room field)
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            room TEXT,
            timestamp TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

def get_conn():
    """Return a new DB connection (threadsafe flag set to allow use under eventlet)."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def save_message(username: str, message: str, room: str | None = None):
    conn = get_conn()
    c = conn.cursor()
    ts = datetime.datetime.utcnow().isoformat()
    c.execute("INSERT INTO messages (username, message, room, timestamp) VALUES (?, ?, ?, ?)",
              (username, message, room, ts))
    conn.commit()
    conn.close()
    return ts

def load_messages(room: str | None = None, limit: int = 200):
    conn = get_conn()
    c = conn.cursor()
    if room:
        c.execute("SELECT username, message, room, timestamp FROM messages WHERE room=? ORDER BY id ASC LIMIT ?",
                  (room, limit))
    else:
        c.execute("SELECT username, message, room, timestamp FROM messages ORDER BY id ASC LIMIT ?",
                  (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def create_user(username: str, password: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, last_active) VALUES (?, ?, ?)",
                  (username, password, datetime.datetime.utcnow().isoformat()))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def authenticate(username: str, password: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
    return user

def update_last_active(user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET last_active=? WHERE id=?", (datetime.datetime.utcnow().isoformat(), user_id))
    conn.commit()
    conn.close()

# ----------------------------
# ROUTES
# ----------------------------
@app.route("/static/<path:filename>")
def static_proxy(filename):
    # Explicit static file serving (Flask already serves static, but explicit route helps in some environments)
    return send_from_directory(app.static_folder, filename)

@app.route("/")
def index():
    # if not logged, redirect to login
    if "user_id" not in session:
        return redirect(url_for("login"))
    # load last messages (global chat)
    rows = load_messages(room=None, limit=500)
    messages = [dict(username=r["username"], message=r["message"], room=r["room"], timestamp=r["timestamp"]) for r in rows]
    return render_template("index.html", username=session.get("username"), messages=messages)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("login.html", error="Podaj login i hasło")
        user = authenticate(username, password)
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            update_last_active(user["id"])
            return redirect(url_for("index"))
        return render_template("login.html", error="Niepoprawny login lub hasło")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("register.html", error="Podaj nazwę użytkownika i hasło")
        ok = create_user(username, password)
        if ok:
            return redirect(url_for("login"))
        else:
            return render_template("register.html", error="Nazwa użytkownika zajęta")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ----------------------------
# SOCKET.IO EVENTS
# ----------------------------
@socketio.on("join_room")
def on_join(data):
    """Join a specific room (optional: supports private/group rooms)"""
    room = data.get("room")
    join_room(room)
    # send last messages for that room
    rows = load_messages(room=room, limit=200)
    msgs = [dict(username=r["username"], message=r["message"], timestamp=r["timestamp"]) for r in rows]
    emit("load_messages", msgs)

@socketio.on("leave_room")
def on_leave(data):
    room = data.get("room")
    leave_room(room)

@socketio.on("send_message")
def on_send(data):
    """data: { message: str, room: optional str }"""
    username = session.get("username", "Anonim")
    message = (data.get("message") or "").strip()
    room = data.get("room")
    if not message:
        return
    ts = save_message(username, message, room)
    payload = {"username": username, "message": message, "timestamp": ts, "room": room}
    if room:
        emit("receive_message", payload, room=room)
    else:
        emit("receive_message", payload, broadcast=True)

# ----------------------------
# STARTUP
# ----------------------------
if __name__ == "__main__":
    init_db()
    print(f"[START] DB path: {DB_PATH}")
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
