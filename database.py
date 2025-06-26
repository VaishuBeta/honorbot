import sqlite3

def init_db():
    conn = sqlite3.connect("honor.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS honor (
            user_id INTEGER PRIMARY KEY,
            honor INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def get_honor(user_id):
    conn = sqlite3.connect("honor.db")
    cursor = conn.cursor()
    cursor.execute("SELECT honor FROM honor WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def set_honor(user_id, amount):
    conn = sqlite3.connect("honor.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO honor (user_id, honor) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET honor=?", (user_id, amount, amount))
    conn.commit()
    conn.close()

def get_all_honor():
    conn = sqlite3.connect("honor.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, honor FROM honor")
    rows = cursor.fetchall()
    conn.close()
    return rows

def reset_all():
    conn = sqlite3.connect("honor.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM honor")
    conn.commit()
    conn.close()
