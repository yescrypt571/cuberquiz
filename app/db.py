import sqlite3
import os

DB_FILE = "cyberquiz.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # user_groups jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_groups (
            user_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            group_title TEXT,
            PRIMARY KEY (user_id, group_id)
        )
    """)

    # quiz_results jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            correct_answers INTEGER DEFAULT 0,
            total_answers INTEGER DEFAULT 0,
            CONSTRAINT unique_quiz_user_group UNIQUE (quiz_id, user_id, group_id)
        )
    """)

    # quizzes jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY,
            title TEXT,
            group_id INTEGER NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("DB initialized successfully!")


# --------------------------
# Guruhlar bilan ishlash
# --------------------------

def save_group(user_id: int, group_id: int, group_title: str = None):
    """Foydalanuvchiga tegishli guruhni saqlaydi."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO user_groups (user_id, group_id, group_title)
            VALUES (?, ?, ?)
        """, (user_id, group_id, group_title))
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB.save_group xato: {e}")
    finally:
        conn.close()

def get_groups(user_id: int):
    """Foydalanuvchiga tegishli barcha guruhlarni (id + title) qaytaradi."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT group_id, group_title FROM user_groups WHERE user_id = ?", (user_id,))
        rows = cur.fetchall()
        return rows if rows else []
    except sqlite3.Error as e:
        print(f"DB.get_groups xato: {e}")
        return []
    finally:
        conn.close()

def get_group(user_id: int):
    """Eski moslik uchun — faqat oxirgi qo‘shilgan guruhni qaytaradi."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT group_id, group_title FROM user_groups WHERE user_id = ? ORDER BY rowid DESC LIMIT 1", (user_id,))
        row = cur.fetchone()
        return row if row else None
    except sqlite3.Error as e:
        print(f"DB.get_group xato: {e}")
        return None
    finally:
        conn.close()


# --------------------------
# Natijalar bilan ishlash
# --------------------------

def add_result(quiz_id: int, user_id: int, group_id: int, is_correct: bool):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        # Avval foydalanuvchi uchun yozuv yo‘q bo‘lsa, qo‘shib qo‘yamiz
        cur.execute("""
            INSERT OR IGNORE INTO quiz_results 
            (quiz_id, user_id, group_id, correct_answers, total_answers)
            VALUES (?, ?, ?, 0, 0)
        """, (quiz_id, user_id, group_id))

        # Har bir javobda total +1, agar to‘g‘ri bo‘lsa correct +1
        cur.execute("""
            UPDATE quiz_results
            SET correct_answers = correct_answers + ?,
                total_answers   = total_answers + 1
            WHERE quiz_id = ? AND user_id = ? AND group_id = ?
        """, (1 if is_correct else 0, quiz_id, user_id, group_id))

        conn.commit()
        return True

    except sqlite3.Error as e:
        print(f"DB.add_result xato: {e}")
        return False

    finally:
        conn.close()


def get_leaderboard(quiz_id: int, group_id: int, limit: int = 10):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, correct_answers, total_answers
            FROM quiz_results
            WHERE quiz_id = ? AND group_id = ?
            ORDER BY correct_answers DESC, total_answers ASC
            LIMIT ?
        """, (quiz_id, group_id, limit))
        rows = cur.fetchall()
        return rows
    except sqlite3.Error as e:
        print(f"DB.get_leaderboard xato: {e}")
        return []
    finally:
        conn.close()

def migrate_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE user_groups ADD COLUMN group_title TEXT")
        conn.commit()
        print("Migration: group_title ustuni qo'shildi ✅")
    except sqlite3.OperationalError as e:
        print("Migration xato yoki allaqachon mavjud:", e)
    finally:
        conn.close()



if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        init_db()
