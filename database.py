import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, 'database.db')

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Tworzy bazę i tabele, jeśli nie istnieją."""
    if not os.path.exists(DB_NAME):
        print("[INFO] Tworzę bazę danych:", DB_NAME)
    else:
        print("[INFO] Baza danych już istnieje:", DB_NAME)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    last_active TEXT
                )''')
    conn.commit()
    conn.close()
    print("[INFO] Tabela 'users' gotowa.")
