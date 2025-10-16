# main.py
import eventlet
eventlet.monkey_patch()  # MUSI BYĆ PIERWSZE

from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
import sqlite3
import datetime
import os

# Flask app
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='eventlet')

# Baza danych
DB_NAME = 'database.db'

def init_db():
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        last_active TEXT
                    )''')
        conn.commit()
        conn.close()

init_db()

# Funkcje pomocnicze
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def update_last_active(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET last_active=? WHERE id=?", (datetime.datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

# Strony
@app.route('/')
def index():
    if 'user_id' in session:
        return render_template('index.html', username=session.get('username'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            update_last_active(user['id'])
            return redirect(url_for('index'))
        return render_template('login.html', error="Niepoprawny login lub hasło")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password, last_active) VALUES (?, ?, ?)",
                      (username, password, datetime.datetime.now().isoformat()))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error="Użytkownik już istnieje")
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# SocketIO
@socketio.on('send_message')
def handle_send_message(data):
    username = session.get('username', 'Anonim')
    message = data['message']
    emit('receive_message', {'username': username, 'message': message}, broadcast=True)

# Uruchomienie
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
