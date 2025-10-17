import sqlite3
import os

DB_NAME = 'database.db'

def init_db():
    """Tworzy plik bazy, jeśli nie istnieje"""
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_tables_exist():
    """Tworzy wymagane tabele jeśli nie istnieją"""
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
