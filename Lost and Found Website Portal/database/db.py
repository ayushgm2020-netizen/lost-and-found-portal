import os
import sqlite3
import pymysql
import pymysql.cursors
from config import Config, BASE_DIR

_is_mysql = None
_db_status_message = ""

def get_db_status():
    global _is_mysql, _db_status_message
    return {
        "is_mysql": bool(_is_mysql),
        "engine": "MySQL" if _is_mysql else "SQLite (Fallback)",
        "message": _db_status_message
    }

def get_db():
    """
    Connect to MySQL if available, otherwise fallback gracefully to SQLite.
    Returns a unified connection object.
    """
    global _is_mysql, _db_status_message
    
    # Try MySQL first
    if _is_mysql is not False:
        try:
            conn = pymysql.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                charset='utf8mb4'
            )
            _is_mysql = True
            _db_status_message = f"Connected to MySQL on {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"
            return conn, "mysql"
        except Exception as e:
            if _is_mysql is True:
                # Was previously connected to MySQL, connection lost
                pass
            _is_mysql = False
            _db_status_message = f"MySQL unavailable ({str(e)}). Using local SQLite fallback for seamless execution."
            
    # SQLite fallback
    sqlite_path = os.path.join(BASE_DIR, 'database', 'smartrecover.db')
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def query_db(query, args=(), one=False):
    """
    Execute a SELECT query and return list of dicts (or single dict).
    Automatically adapts placeholders (%s for MySQL, ? for SQLite).
    """
    conn, engine = get_db()
    cursor = None
    try:
        if engine == "mysql":
            cursor = conn.cursor()
            cursor.execute(query, args)
            rv = cursor.fetchall()
            return (rv[0] if rv else None) if one else rv
        else:
            # SQLite uses ? instead of %s
            sqlite_query = query.replace("%s", "?")
            cursor = conn.cursor()
            cursor.execute(sqlite_query, args)
            rv = cursor.fetchall()
            # Convert sqlite3.Row to dict
            result = [dict(row) for row in rv]
            return (result[0] if result else None) if one else result
    finally:
        if cursor:
            cursor.close()
        conn.close()

def execute_db(query, args=(), commit=True):
    """
    Execute an INSERT, UPDATE, or DELETE query.
    Returns the last inserted id or rowcount.
    """
    conn, engine = get_db()
    cursor = None
    try:
        if engine == "mysql":
            cursor = conn.cursor()
            cursor.execute(query, args)
            if commit:
                conn.commit()
            last_id = cursor.lastrowid
            return last_id
        else:
            sqlite_query = query.replace("%s", "?")
            cursor = conn.cursor()
            cursor.execute(sqlite_query, args)
            if commit:
                conn.commit()
            last_id = cursor.lastrowid
            return last_id
    finally:
        if cursor:
            cursor.close()
        conn.close()

from werkzeug.security import generate_password_hash

def init_db():
    """
    Initializes database schema and default records if not present.
    """
    conn, engine = get_db()
    cursor = conn.cursor()
    
    # Generate fresh secure hash for 'password123'
    default_hash = generate_password_hash('password123')
    
    if engine == "sqlite":
        # SQLite schema definition
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS institutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            domain TEXT,
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            contact_number TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (institution_id) REFERENCES institutions(id)
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            date_event DATE NOT NULL,
            location TEXT NOT NULL,
            photo_filename TEXT,
            private_details TEXT,
            status TEXT DEFAULT 'reported',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (institution_id) REFERENCES institutions(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_id INTEGER NOT NULL,
            lost_item_id INTEGER NOT NULL,
            found_item_id INTEGER NOT NULL,
            score REAL NOT NULL,
            factor_name REAL DEFAULT 0,
            factor_category REAL DEFAULT 0,
            factor_description REAL DEFAULT 0,
            factor_location REAL DEFAULT 0,
            factor_date REAL DEFAULT 0,
            status TEXT DEFAULT 'suggested',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (institution_id) REFERENCES institutions(id),
            FOREIGN KEY (lost_item_id) REFERENCES items(id),
            FOREIGN KEY (found_item_id) REFERENCES items(id),
            UNIQUE(lost_item_id, found_item_id)
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            claimant_id INTEGER NOT NULL,
            proof_details TEXT NOT NULL,
            contact_phone TEXT,
            status TEXT DEFAULT 'pending',
            reviewer_id INTEGER,
            review_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items(id),
            FOREIGN KEY (claimant_id) REFERENCES users(id),
            FOREIGN KEY (reviewer_id) REFERENCES users(id)
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            link TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )''')
        
        # Seed default institutions
        cursor.execute("SELECT COUNT(*) as count FROM institutions")
        count = cursor.fetchone()['count']
        if count == 0:
            institutions_seed = [
                (1, 'Apex Institute of Engineering & Technology', 'AIET', 'aiet.edu', 'North Campus, Building 4'),
                (2, 'Metro State University', 'MSU', 'metrostate.edu', 'Downtown Campus, Academic Block A'),
                (3, 'City Polytechnic College', 'CPC', 'citypoly.edu', 'West Bay Wing')
            ]
            cursor.executemany("INSERT INTO institutions (id, name, code, domain, location) VALUES (?, ?, ?, ?, ?)", institutions_seed)
            
            # Seed users
            users_seed = [
                (1, 1, 'Prof. Sharma (Admin)', 'admin@aiet.edu', default_hash, '+91 9876543210', 'admin'),
                (2, 1, 'Ayush Sharma', 'ayush@aiet.edu', default_hash, '+91 9123456780', 'user'),
                (3, 1, 'Rahul Verma', 'rahul@aiet.edu', default_hash, '+91 9234567891', 'user')
            ]
            cursor.executemany("INSERT INTO users (id, institution_id, full_name, email, password_hash, contact_number, role) VALUES (?, ?, ?, ?, ?, ?, ?)", users_seed)
            conn.commit()
    else:
        # MySQL initialization: schema.sql will usually be executed or can be executed here
        schema_file = os.path.join(BASE_DIR, 'database', 'schema.sql')
        if os.path.exists(schema_file):
            with open(schema_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            # Split commands by semicolon
            commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip() and not cmd.strip().startswith('--')]
            for cmd in commands:
                try:
                    cursor.execute(cmd)
                except Exception as err:
                    pass
            conn.commit()

    cursor.close()
    conn.close()
