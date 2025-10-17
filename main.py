# main.py
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
import os, sqlite3, datetime
from database import init_db, get_db_connection

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['SECRET_KEY'] = 'supersecretkey'

# ZAMIANA eventleta na threading
socketio = SocketIO(app, async_mode='threading')

# inicjalizacja bazy
init_db()

@app.route('/')
def index():
    if 'user_id' in session:
        return render_template('index.html', username=session['username'])
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
            conn = get_db_connection()
            conn.execute("UPDATE users SET last_active=? WHERE id=?",
                         (datetime.datetime.now().isoformat(), user['id']))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Niepoprawny login lub hasło")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            conn = get_db_connection()
            conn.execute("INSERT INTO users (username, password, last_active) VALUES (?, ?, ?)",
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

@socketio.on('send_message')
def handle_message(data):
    username = session.get('username', 'Anonim')
    emit('receive_message', {'username': username, 'message': data.get('message', '')}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
