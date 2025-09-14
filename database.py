import sqlite3
import re

DATABASE_FILE = 'movies.db'

def get_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates the necessary tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            title TEXT PRIMARY KEY, release_date TEXT, cinemark_url TEXT,
            poster_url TEXT, is_anime INTEGER, showtimes TEXT, overview TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            user_id INTEGER NOT NULL,
            pattern TEXT NOT NULL,
            is_regex INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(user_id, pattern)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ignore_list (
            user_id INTEGER NOT NULL,
            pattern TEXT NOT NULL,
            is_regex INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(user_id, pattern)
        )
    ''')
    
    # Migration: Add is_regex column to ignore_list if it doesn't exist
    cursor.execute("PRAGMA table_info(ignore_list)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'is_regex' not in columns:
        cursor.execute("ALTER TABLE ignore_list ADD COLUMN is_regex INTEGER NOT NULL DEFAULT 0")
        # Rename movie_title column to pattern for consistency
        cursor.execute("ALTER TABLE ignore_list RENAME COLUMN movie_title TO pattern")
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

# --- Movie Table Functions (Unchanged) ---
def get_movie(conn, title):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM movies WHERE title = ?", (title,))
    return cursor.fetchone()

def add_or_update_movie(conn, movie, showtimes_str, is_anime_flag, overview):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO movies (title, release_date, cinemark_url, poster_url, is_anime, showtimes, overview)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(title) DO UPDATE SET
            release_date=excluded.release_date, cinemark_url=excluded.cinemark_url,
            poster_url=excluded.poster_url, is_anime=excluded.is_anime,
            showtimes=excluded.showtimes, overview=excluded.overview
    ''', (movie['title'], movie['release_date'], movie['cinemark_url'], movie['poster_url'], is_anime_flag, showtimes_str, overview))
    conn.commit()

def update_showtimes(conn, title, new_showtimes_str):
    cursor = conn.cursor()
    cursor.execute("UPDATE movies SET showtimes = ? WHERE title = ?", (new_showtimes_str, title))
    conn.commit()

def get_all_movie_titles(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM movies ORDER BY title ASC")
    return [row['title'] for row in cursor.fetchall()]

# --- Watchlist Table Functions (Unchanged) ---
def add_to_watchlist(conn, user_id, pattern, is_regex=False):
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO watchlist (user_id, pattern, is_regex) VALUES (?, ?, ?)", (user_id, pattern, 1 if is_regex else 0))
        conn.commit()
        return True
    except sqlite3.IntegrityError: return False

def remove_from_watchlist(conn, user_id, pattern):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE user_id = ? AND pattern = ?", (user_id, pattern))
    conn.commit()
    return cursor.rowcount > 0

def get_user_watchlist(conn, user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT pattern, is_regex FROM watchlist WHERE user_id = ?", (user_id,))
    return cursor.fetchall()

def get_watchers_for_movie(conn, movie_title):
    watchers = set()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM watchlist WHERE pattern = ? AND is_regex = 0", (movie_title,))
    for row in cursor.fetchall():
        watchers.add(row['user_id'])
    cursor.execute("SELECT user_id, pattern FROM watchlist WHERE is_regex = 1")
    for row in cursor.fetchall():
        try:
            if re.search(row['pattern'], movie_title, re.IGNORECASE):
                watchers.add(row['user_id'])
        except re.error:
            continue
    return list(watchers)

# --- Ignore List Functions ---
def add_to_ignore_list(conn, user_id, pattern, is_regex=False):
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO ignore_list (user_id, pattern, is_regex) VALUES (?, ?, ?)", (user_id, pattern, 1 if is_regex else 0))
        conn.commit()
        return True
    except sqlite3.IntegrityError: return False

def remove_from_ignore_list(conn, user_id, pattern):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ignore_list WHERE user_id = ? AND pattern = ?", (user_id, pattern))
    conn.commit()
    return cursor.rowcount > 0

def get_user_ignore_list(conn, user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT pattern, is_regex FROM ignore_list WHERE user_id = ?", (user_id,))
    return cursor.fetchall()

def is_movie_ignored_by_any_user(conn, movie_title):
    """Checks if a movie is ignored by ANY user (including regex patterns)."""
    cursor = conn.cursor()
    
    # Check exact title matches
    cursor.execute("SELECT 1 FROM ignore_list WHERE pattern = ? AND is_regex = 0", (movie_title,))
    if cursor.fetchone():
        return True
    
    # Check regex patterns
    cursor.execute("SELECT pattern FROM ignore_list WHERE is_regex = 1")
    for row in cursor.fetchall():
        try:
            if re.search(row['pattern'], movie_title, re.IGNORECASE):
                return True
        except re.error:
            continue
    
    return False
