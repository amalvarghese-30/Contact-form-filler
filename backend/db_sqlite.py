import sqlite3

DB_PATH = r"C:\xampp\htdocs\contact-form-filler\data\forms_insights.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
