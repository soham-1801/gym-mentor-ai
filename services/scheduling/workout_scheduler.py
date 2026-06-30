"""
Workout Scheduler Service
Checks today schedule and returns reminder info.
"""
import datetime

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBR  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def get_today_weekday() -> int:
    """Return 0=Monday ... 6=Sunday (Python weekday standard)."""
    return datetime.datetime.now().weekday()


def get_current_time_str() -> str:
    """Return current time as HH:MM string."""
    return datetime.datetime.now().strftime("%H:%M")


def check_today_schedule(schedule_rows: list) -> dict:
    """
    Given DB rows from get_schedule(), check if there is a workout due today.
    Returns dict with keys: has_workout, program_name, workout_time, is_due_now
    """
    today = get_today_weekday()
    now_str = get_current_time_str()

    for row in schedule_rows:
        if row["day_of_week"] == today:
            sched_time = row.get("workout_time", "07:00")
            is_due = now_str >= sched_time
            return {
                "has_workout": True,
                "program_name": row.get("program_name", "Full Body Blast"),
                "workout_time": sched_time,
                "is_due_now": is_due,
                "day_name": DAY_NAMES[today],
            }
    return {"has_workout": False, "program_name": "", "workout_time": "", "is_due_now": False}


def format_schedule_summary(schedule_rows: list) -> str:
    """Return a readable summary like 'Mon, Wed, Fri at 07:00'."""
    if not schedule_rows:
        return "No schedule set"
    days = sorted(set(r["day_of_week"] for r in schedule_rows))
    day_labels = ", ".join(DAY_ABBR[d] for d in days)
    time_str = schedule_rows[0].get("workout_time", "07:00")
    return f"{day_labels} at {time_str}"


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """Calculate BMI from weight (kg) and height (cm)."""
    if height_cm <= 0:
        return 0.0
    h_m = height_cm / 100.0
    return round(weight_kg / (h_m * h_m), 1)


def bmi_category(bmi: float) -> tuple:
    """Return (category_str, color_hex) for a BMI value."""
    if bmi < 18.5:
        return "Underweight", "#3B82F6"
    elif bmi < 25.0:
        return "Normal", "#10B981"
    elif bmi < 30.0:
        return "Overweight", "#F59E0B"
    else:
        return "Obese", "#EF4444"
