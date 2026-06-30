import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), "gym_trainer.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL
    )
    """)
    
    # Create exercises table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        exercise_name TEXT NOT NULL,
        reps INTEGER NOT NULL,
        sets INTEGER NOT NULL,
        time REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # Perform column migration for average_form_score and best_form_score if missing
    cursor.execute("PRAGMA table_info(exercises)")
    columns = [col[1] for col in cursor.fetchall()]
    if "average_form_score" not in columns:
        cursor.execute("ALTER TABLE exercises ADD COLUMN average_form_score REAL")
    if "best_form_score" not in columns:
        cursor.execute("ALTER TABLE exercises ADD COLUMN best_form_score REAL")
    if "feedback_summary" not in columns:
        cursor.execute("ALTER TABLE exercises ADD COLUMN feedback_summary TEXT")
    if "strongest_area" not in columns:
        cursor.execute("ALTER TABLE exercises ADD COLUMN strongest_area TEXT")
    if "weakest_area" not in columns:
        cursor.execute("ALTER TABLE exercises ADD COLUMN weakest_area TEXT")
    if "improvement_percentage" not in columns:
        cursor.execute("ALTER TABLE exercises ADD COLUMN improvement_percentage REAL")
        
    # Perform column migrations on users table for streaks if missing
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [col[1] for col in cursor.fetchall()]
    if "current_streak" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN current_streak INTEGER DEFAULT 0")
    if "longest_streak" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN longest_streak INTEGER DEFAULT 0")
    if "last_workout_date" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_workout_date TEXT")
    # Phase 2: Goal system + Calorie estimator
    if "user_goal" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN user_goal TEXT DEFAULT 'General Fitness'")
    if "body_weight_kg" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN body_weight_kg REAL DEFAULT 70.0")
    # Phase 3: Body Metrics Profile
    if "height_cm" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN height_cm REAL DEFAULT 170.0")
    if "age" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN age INTEGER DEFAULT 25")

    # Phase 3: Workout Scheduler table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workout_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        day_of_week INTEGER NOT NULL,
        workout_time TEXT NOT NULL DEFAULT '07:00',
        program_name TEXT NOT NULL DEFAULT 'Full Body Blast',
        active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    conn.commit()
    conn.close()

def get_or_create_user(username):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute("""
                INSERT INTO users (username, current_streak, longest_streak, last_workout_date)
                VALUES (?, 0, 0, NULL)
            """, (username,))
            conn.commit()
            user_id = cursor.lastrowid
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()

        user_dict = dict(row) if row else None
        conn.close()
        return user_dict
    except Exception as e:
        import logging
        logging.error(f"[exercise_repository] get_or_create_user failed for '{username}': {e}", exc_info=True)
        return None

def update_user_streaks(user_id, current_streak, longest_streak, last_workout_date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET current_streak = ?, longest_streak = ?, last_workout_date = ? 
        WHERE id = ?
    """, (int(current_streak), int(longest_streak), last_workout_date, user_id))
    conn.commit()
    conn.close()


def update_user_profile(user_id, user_goal: str = None, body_weight_kg: float = None,
                        height_cm: float = None, age: int = None):
    """Update user profile fields in the DB."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        fields = []
        values = []
        if user_goal is not None:
            fields.append("user_goal = ?"); values.append(user_goal)
        if body_weight_kg is not None:
            fields.append("body_weight_kg = ?"); values.append(float(body_weight_kg))
        if height_cm is not None:
            fields.append("height_cm = ?"); values.append(float(height_cm))
        if age is not None:
            fields.append("age = ?"); values.append(int(age))
        if fields:
            values.append(user_id)
            cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
        conn.close()
    except Exception as e:
        import logging
        logging.error(f"[exercise_repository] update_user_profile failed: {e}")


# ─── Workout Scheduler ────────────────────────────────────────────────────────

def save_schedule(user_id: int, days: list, workout_time: str, program_name: str):
    """Save workout schedule for given days (0=Mon…6=Sun). Replaces existing."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Clear existing schedule for this user
        cursor.execute("DELETE FROM workout_schedule WHERE user_id = ?", (user_id,))
        # Insert one row per day
        for day in days:
            cursor.execute(
                "INSERT INTO workout_schedule (user_id, day_of_week, workout_time, program_name) VALUES (?, ?, ?, ?)",
                (user_id, int(day), workout_time, program_name)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        import logging
        logging.error(f"[exercise_repository] save_schedule failed: {e}")


def get_schedule(user_id: int) -> list:
    """Return list of schedule rows for a user."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM workout_schedule WHERE user_id = ? AND active = 1 ORDER BY day_of_week",
            (user_id,)
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        import logging
        logging.error(f"[exercise_repository] get_schedule failed: {e}")
        return []

def get_users_exercises(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT exercise_name, reps, sets, time, average_form_score, best_form_score, 
               feedback_summary, strongest_area, weakest_area, improvement_percentage, created_at 
        FROM exercises 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    
    exercises_list = [dict(row) for row in rows]
    conn.close()
    return exercises_list

def save_exercise(user_id, exercise_name, reps, sets, time_spent, average_form_score=None, best_form_score=None,
                  feedback_summary=None, strongest_area=None, weakest_area=None, improvement_percentage=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO exercises (user_id, exercise_name, reps, sets, time, average_form_score, best_form_score,
                               feedback_summary, strongest_area, weakest_area, improvement_percentage)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, exercise_name, reps, sets, float(time_spent), 
            float(average_form_score) if average_form_score is not None else None, 
            float(best_form_score) if best_form_score is not None else None,
            feedback_summary, strongest_area, weakest_area,
            float(improvement_percentage) if improvement_percentage is not None else None))
    
    conn.commit()
    conn.close()
