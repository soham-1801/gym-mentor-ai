import streamlit as st

def initial_session_defaults():

    defaults = {
        "username": None,
        "user_id": None,
        "workout_started": False,
        "exercise_type": "Squats",
        "target_sets": 0,
        "reps_per_set": 0,
        "reps": 0,
        "current_set_reps": 0,
        "sets_completed": 0,
        "knee_angle": 0,
        "back_angle": 0,
        "depth_status": "Unknown",
        "elbow_angle": 0,
        "body_alignment": "Unknown",
        "hip_status": "Unknown",
        "shoulder_status": "Unknown",
        "swing_status": "Unknown",
        "extension_status": "Unknown",
        "back_arch_status": "Unknown",
        "front_knee_angle": 0,
        "torso_angle": 0,
        "balance_status": "Unknown",
        "audio_to_play": None,
        "audio_play_start": 0.0,
        "audio_duration": 0.0,
        "coach_feedback": None,
        "last_saved_sets_completed": 0,
        "last_notified_sets_completed": 0,
        "last_notified_workout_complete": False,
        "last_form_feedback_at": 0.0,
        "set_cycle_started_at": 0.0,
        "needs_reset": False,
        "voice_enabled": True,
        "voice_volume": 1.0,
        "voice_gender": "Female",
        "voice_engine": "pyttsx3 / gTTS",
        "greeting_played": False,
        "last_rep_count": 0,
        "browser_speech": None,
        "browser_speech_queue": [],
        "speech_feedback": "",
        "last_announced_rep": 0,
        "voice_event_bus": None,
        "last_event_info": "None",
        "developer_mode": False,
        "form_score": 100,
        "strongest_area": "N/A",
        "weakest_area": "N/A",
        "average_form_score": 0.0,
        "best_form_score": 0.0,
        "form_scores_history": [],
        "component_sums": {},
        "component_counts": {},
        "last_score_update_time": 0.0,
        "last_score_voice_time": 0.0,
        "overall_rating": 0.0,
        "improvement_percentage": 0.0,
        "feedback_summary": "",
        "recommendation": "",
        "last_spoken_weakest_area": "",
        "last_weakest_voice_time": 0.0,
        # ── Phase 1: Rest Timer ──────────────────────────────────────────
        "rest_timer_active": False,
        "rest_timer_end": 0.0,
        "rest_duration": 60,           # configurable seconds
        "last_rest_countdown_spoken": -1,
        # ── Phase 1: Injury Warning ──────────────────────────────────────
        "injury_warning_active": False,
        "injury_warning_shown_at": 0.0,
        # ── Phase 1: Breathing Cues ──────────────────────────────────────
        "last_breathing_cue_time": 0.0,
        "last_breathing_cue_set": -1,
        # ── Phase 2: Workout Program Builder ────────────────────────────
        "program_mode": False,
        "active_program_name": "",
        "active_program": [],          # list of {name, sets, reps, rest_seconds}
        "program_exercise_index": 0,
        "program_transitioning": False,
        "program_transition_at": 0.0,
        # ── Phase 2: Goal System ─────────────────────────────────────────
        "user_goal": "General Fitness",
        "body_weight_kg": 70.0,
        # ── Phase 2: Calorie Estimator ───────────────────────────────────
        "calories_burned": 0.0,
        "session_calories_by_exercise": {},
        "workout_start_time": 0.0,
        # ── Phase 3: Body Metrics Profile ───────────────────────────────
        "height_cm": 170.0,
        "age": 25,
        # ── Phase 3: Symmetry Detection ─────────────────────────────────
        "left_elbow_angle": 0,
        "right_elbow_angle": 0,
        "left_knee_angle": 0,
        "right_knee_angle": 0,
        # ── Phase 3: Workout Scheduler ───────────────────────────────────
        "schedule_loaded": False,
        "schedule_rows": [],
        "today_schedule": {},
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
