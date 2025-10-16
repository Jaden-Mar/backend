import os
import sqlite3
import datetime

from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit

# -----------------------
# CONFIG
# -----------------------
app = Flask(__name__)
app.secret_key = "supersecretkey"

# folder na bazę danych
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "chat.db")

socketio = SocketIO(app, async_mode='eventlet')

# -----------------------
# DATABASE
# -----------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# tabela users
c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                last_active TEXT
            )''')

# tabela wiadomości
c.execute('''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                message TEXT,
                timestamp TEXT
            )''')
conn.commit()

# -----------------------
# HELPERS
# -----------------------
def update_last_active(user_id):
    c.execute("UPDATE users SET last_active=? WHERE id=?", (datetime.datetime.now().isoformat(), user_id))
    conn.commit()

# -----------------------
# ROUTES
# -----------------------
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # pobierz wiadomości
    c.execute("SELECT user, message, timestamp FROM messages ORDER BY id ASC")
    messages = c.fetchall()
    return render_template('index.html', messages=messages, username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
        u = c.fetchone()
        if u:
            session['username'] = username
            update_last_active(u[0])
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Błędny login lub hasło")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            c.execute("INSERT INTO users (username, password, last_active) VALUES (?, ?, ?)",
                      (username, password, datetime.datetime.now().isoformat()))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('login.html', error="Użytkownik już istnieje")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# -----------------------
# SOCKET.IO
# -----------------------
@socketio.on('send_message')
def handle_message(data):
    user = session.get('username')
    if not user:
        return
    msg = data['msg']
    timestamp = datetime.datetime.now().isoformat()
    
    # zapisz w bazie
    c.execute("INSERT INTO messages (user, message, timestamp) VALUES (?, ?, ?)", (user, msg, timestamp))
    conn.commit()
    
    # wyślij do wszystkich
    emit('receive_message', {'user': user, 'msg': msg, 'timestamp': timestamp}, broadcast=True)

# -----------------------
# MAIN
# -----------------------
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
