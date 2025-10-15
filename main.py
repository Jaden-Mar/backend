from flask import Flask, render_template, request, redirect, url_for, flash
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from flask_socketio import SocketIO, join_room, emit
import sqlite3, datetime

app = Flask(__name__)
app.secret_key = "tajny_klucz"
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
socketio = SocketIO(app)

DB_PATH = "users.db"


# === Inicjalizacja bazy danych ===
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # tabela użytkowników
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    last_active DATETIME
                )''')
    # tabela wiadomości
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER,
                    receiver_id INTEGER,
                    body TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()


# === Klasa użytkownika ===
class User(UserMixin):
    def __init__(self, id, username, password, last_active=None):
        self.id = id
        self.username = username
        self.password = password
        self.last_active = last_active


@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, password, last_active FROM users WHERE id = ?", (user_id,))
    u = c.fetchone()
    conn.close()
    if u:
        return User(*u)
    return None


# === Pomocnicza funkcja: aktualizacja aktywności ===
def update_last_active(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET last_active=? WHERE id=?", (datetime.datetime.now(), user_id))
    conn.commit()
    conn.close()


# === ROUTES ===
@app.route('/')
@login_required
def index():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, last_active FROM users WHERE id != ?", (current_user.id,))
    users = c.fetchall()
    conn.close()
    update_last_active(current_user.id)

    now = datetime.datetime.now()
    user_list = []
    for u in users:
        last_active = None
        if u[2]:
            try:
                last_active = datetime.datetime.fromisoformat(u[2])
            except:
                try:
                    last_active = datetime.datetime.strptime(u[2], "%Y-%m-%d %H:%M:%S.%f")
                except:
                    last_active = datetime.datetime.strptime(u[2], "%Y-%m-%d %H:%M:%S")
        online = last_active and (now - last_active).total_seconds() < 120
        user_list.append({"id": u[0], "username": u[1], "online": online})

    return render_template('index.html', username=current_user.username, users=user_list, my_id=current_user.id)


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, username, password, last_active FROM users WHERE username=?", (username,))
        u = c.fetchone()
        conn.close()
        if u and bcrypt.check_password_hash(u[2], password):
            login_user(User(*u))
            update_last_active(u[0])
            return redirect(url_for('index'))
        else:
            flash("Błędny login lub hasło")
    return render_template('login.html')


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password, last_active) VALUES (?, ?, ?)",
                      (username, password, datetime.datetime.now()))
            conn.commit()
            conn.close()
            flash("Rejestracja udana, możesz się zalogować!")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Użytkownik już istnieje!")
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Wylogowano")
    return redirect(url_for('login'))


# === SOCKETIO EVENTS ===
@socketio.on('join_chat')
def handle_join_chat(data):
    receiver_id = data['receiver_id']
    room = f"room_{min(current_user.id, receiver_id)}_{max(current_user.id, receiver_id)}"
    join_room(room)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT u.username, m.body
                 FROM messages m
                 JOIN users u ON m.sender_id = u.id
                 WHERE (m.sender_id=? AND m.receiver_id=?)
                    OR (m.sender_id=? AND m.receiver_id=?)
                 ORDER BY m.timestamp ASC''',
              (current_user.id, receiver_id, receiver_id, current_user.id))
    messages = [{"sender": row[0], "body": row[1]} for row in c.fetchall()]
    conn.close()
    emit('load_messages', messages)


@socketio.on('send_message')
def handle_send_message(data):
    receiver_id = data['receiver_id']
    body = data['body']
    room = f"room_{min(current_user.id, receiver_id)}_{max(current_user.id, receiver_id)}"

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO messages (sender_id, receiver_id, body) VALUES (?, ?, ?)",
              (current_user.id, receiver_id, body))
    conn.commit()
    conn.close()

    emit('receive_message', {
        'sender': current_user.username,
        'body': body,
        'room': room
    }, room=room)


if __name__=='__main__':
    init_db()
    socketio.run(app, debug=True)
