"""
Workout Program Builder - Pre-built programs + custom program support.
Each program is a list of exercise dicts: {name, sets, reps, rest_seconds}
"""

PRESET_PROGRAMS = {
    "Push Day": [
        {"name": "Push-ups",       "sets": 3, "reps": 15, "rest_seconds": 60},
        {"name": "Shoulder Press", "sets": 3, "reps": 12, "rest_seconds": 60},
    ],
    "Pull Day": [
        {"name": "Biceps Curls (Dumbbell)", "sets": 3, "reps": 12, "rest_seconds": 60},
        {"name": "Shoulder Press",          "sets": 3, "reps": 10, "rest_seconds": 60},
    ],
    "Leg Day": [
        {"name": "Squats", "sets": 4, "reps": 15, "rest_seconds": 60},
        {"name": "Lunges", "sets": 3, "reps": 12, "rest_seconds": 60},
    ],
    "Full Body Blast": [
        {"name": "Squats",                  "sets": 3, "reps": 15, "rest_seconds": 45},
        {"name": "Push-ups",                "sets": 3, "reps": 12, "rest_seconds": 45},
        {"name": "Lunges",                  "sets": 2, "reps": 10, "rest_seconds": 45},
        {"name": "Biceps Curls (Dumbbell)", "sets": 2, "reps": 12, "rest_seconds": 45},
        {"name": "Shoulder Press",          "sets": 2, "reps": 10, "rest_seconds": 45},
    ],
    "Quick Burn": [
        {"name": "Squats",   "sets": 2, "reps": 20, "rest_seconds": 30},
        {"name": "Push-ups", "sets": 2, "reps": 15, "rest_seconds": 30},
        {"name": "Lunges",   "sets": 2, "reps": 15, "rest_seconds": 30},
    ],
}

PROGRAM_EMOJIS = {
    "Push Day": "💪",
    "Pull Day": "🦾",
    "Leg Day": "🦵",
    "Full Body Blast": "🔥",
    "Quick Burn": "⚡",
}

PROGRAM_DESCRIPTIONS = {
    "Push Day": "Chest & shoulders - Push-ups + Shoulder Press",
    "Pull Day": "Biceps & back - Curls + Shoulder Press",
    "Leg Day": "Lower body power - Squats + Lunges",
    "Full Body Blast": "All muscle groups in one session",
    "Quick Burn": "Fast cardio-style circuit, 15 mins",
}

PROGRAM_NAMES = list(PRESET_PROGRAMS.keys())


def get_program(name: str) -> list:
    """Return the exercise list for a given program name."""
    return PRESET_PROGRAMS.get(name, [])


def program_total_sets(program: list) -> int:
    return sum(ex["sets"] for ex in program)


def program_summary_text(program: list) -> str:
    """Short summary of exercises in program."""
    ex_emojis = {
        "Squats": "🦵", "Push-ups": "💪",
        "Biceps Curls (Dumbbell)": "🦾",
        "Shoulder Press": "🏆", "Lunges": "🔥"
    }
    parts = []
    for ex in program:
        emoji = ex_emojis.get(ex["name"], "•")
        parts.append(f"{emoji} {ex['name']} {ex['sets']}x{ex['reps']}")
    return "  →  ".join(parts) if parts else "No exercises"
