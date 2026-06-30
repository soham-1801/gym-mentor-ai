"""
Calorie Estimator - MET-based formula for gym exercises.
MET (Metabolic Equivalent of Task) * weight_kg * time_hours = kcal burned
"""

# MET values per exercise (moderate intensity)
EXERCISE_MET = {
    "Squats":                  5.0,
    "Push-ups":                3.8,
    "Biceps Curls (Dumbbell)": 3.5,
    "Shoulder Press":          3.5,
    "Lunges":                  4.0,
}

# Average time per rep in seconds (used to estimate session time from reps)
SECS_PER_REP = {
    "Squats":                  3.0,
    "Push-ups":                2.5,
    "Biceps Curls (Dumbbell)": 3.0,
    "Shoulder Press":          3.5,
    "Lunges":                  3.0,
}

DEFAULT_WEIGHT_KG = 70.0


def estimate_calories(
    exercise_name: str,
    total_reps: int,
    body_weight_kg: float = DEFAULT_WEIGHT_KG,
) -> float:
    """
    Estimate kcal burned for a given exercise, rep count, and body weight.
    Returns calories (kcal) as a float rounded to 1 decimal.
    """
    if total_reps <= 0:
        return 0.0

    met = EXERCISE_MET.get(exercise_name, 4.0)
    secs_per_rep = SECS_PER_REP.get(exercise_name, 3.0)
    duration_hours = (total_reps * secs_per_rep) / 3600.0

    kcal = met * body_weight_kg * duration_hours
    return round(kcal, 1)


def estimate_calories_from_time(
    exercise_name: str,
    duration_seconds: float,
    body_weight_kg: float = DEFAULT_WEIGHT_KG,
) -> float:
    """Estimate kcal from actual time duration in seconds."""
    if duration_seconds <= 0:
        return 0.0
    met = EXERCISE_MET.get(exercise_name, 4.0)
    kcal = met * body_weight_kg * (duration_seconds / 3600.0)
    return round(kcal, 1)


def total_session_calories(exercise_calorie_map: dict) -> float:
    """Sum all calories across multiple exercises in a program session."""
    return round(sum(exercise_calorie_map.values()), 1)
