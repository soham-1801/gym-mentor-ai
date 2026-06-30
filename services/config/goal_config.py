"""
Goal System - User fitness goals that adapt coaching, rest times, and rep targets.
"""

GOALS = {
    "Fat Loss": {
        "emoji": "🔥",
        "description": "Burn calories with higher reps and shorter rest",
        "rest_seconds": 30,
        "rep_multiplier": 1.2,   # suggest 20% more reps
        "coaching_style": "high-energy cardio",
        "voice_intro": "Fat loss mode! Keep the intensity high and rest short.",
        "color": "#EF4444",
    },
    "Muscle Gain": {
        "emoji": "💪",
        "description": "Build strength with heavier sets and longer rest",
        "rest_seconds": 90,
        "rep_multiplier": 0.8,   # fewer reps, heavier weight implied
        "coaching_style": "strength focused",
        "voice_intro": "Muscle gain mode! Focus on controlled, heavy reps.",
        "color": "#3B82F6",
    },
    "Endurance": {
        "emoji": "🏃",
        "description": "Build stamina with moderate reps and minimal rest",
        "rest_seconds": 20,
        "rep_multiplier": 1.5,
        "coaching_style": "endurance pacing",
        "voice_intro": "Endurance mode! Keep a steady pace and push through fatigue.",
        "color": "#10B981",
    },
    "Flexibility & Tone": {
        "emoji": "🧘",
        "description": "Light reps with controlled movement and moderate rest",
        "rest_seconds": 45,
        "rep_multiplier": 1.0,
        "coaching_style": "form and control",
        "voice_intro": "Flexibility mode! Focus on full range of motion and perfect form.",
        "color": "#A855F7",
    },
    "General Fitness": {
        "emoji": "⚖️",
        "description": "Balanced approach for overall health",
        "rest_seconds": 60,
        "rep_multiplier": 1.0,
        "coaching_style": "balanced",
        "voice_intro": "General fitness mode! Let us build a solid, healthy base.",
        "color": "#F59E0B",
    },
}

GOAL_NAMES = list(GOALS.keys())


def get_goal_config(goal_name: str) -> dict:
    return GOALS.get(goal_name, GOALS["General Fitness"])


def get_recommended_rest(goal_name: str, base_rest: int = 60) -> int:
    """Return goal-adjusted rest time."""
    config = get_goal_config(goal_name)
    return config["rest_seconds"]


def get_recommended_reps(goal_name: str, base_reps: int) -> int:
    """Return goal-adjusted rep count."""
    config = get_goal_config(goal_name)
    return max(5, int(base_reps * config["rep_multiplier"]))
