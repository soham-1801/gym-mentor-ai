import streamlit as st
import textwrap
import os
import platform
import time
import pandas as pd
from services.auth.login_wall import render_login_wall
from services.state.session_defaults import initial_session_defaults
from services.config.workout_config import EXERCISE_OPTIONS
from services.config.workout_program import PRESET_PROGRAMS, PROGRAM_NAMES, PROGRAM_EMOJIS, PROGRAM_DESCRIPTIONS, get_program, program_summary_text
from services.config.goal_config import GOALS, GOAL_NAMES, get_goal_config, get_recommended_rest
from services.ui.style_loader import load_css, inject_local_font, inject_webrtc_styles
from services.persistence.exercise_repository import init_db, update_user_profile, save_schedule, get_schedule
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from services.vision.exercise_video_processor import VideoProcessorClass, mp_solutions, _mp_import_error
from services.tracking.metrics import sync_metrics_update
from services.persistence.exercise_repository import get_users_exercises
from services.scheduling.workout_scheduler import check_today_schedule, format_schedule_summary, calculate_bmi, bmi_category, DAY_NAMES

from groq import Groq
from services.coaching.llm import LLMCoach
from services.coaching.tts import TextToSpeech
from services.coaching.voice_pipeline import VoicePipeline, autoplay_audio
from services.coaching.event_bus import VoiceEventBus
from services.tracking.progress_analytics import calculate_progress_stats, get_achievements, get_ai_insights
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def clean_html(html_content: str) -> str:
    """Helper to strip all leading/trailing whitespace from each line to prevent Streamlit from showing raw tags as code blocks."""
    if not html_content:
        return ""
    return "\n".join(line.strip() for line in html_content.splitlines())


def main():
    st.set_page_config(
        page_icon="🏋️‍♀️",
        page_title="Apna AI Gym Coach",
        initial_sidebar_state="expanded",
        layout="wide"
    )

    load_css(os.path.join(os.getcwd(), "static", "style.css"))
    inject_local_font(os.path.join(os.getcwd(), "static", "AdobeClean.otf"), "AdobeClean")

    init_db()

    if not render_login_wall():
        return 

    initial_session_defaults()

    if st.session_state.get("voice_event_bus") is None:
        st.session_state.voice_event_bus = VoiceEventBus()

    # Process speech feedback from browser JS
    if "browser_speech_queue" not in st.session_state:
        st.session_state.browser_speech_queue = []
        
    feedback = st.session_state.get("speech_feedback", "")
    if feedback:
        logging.info(f"[main.py] Received speech_feedback from browser: '{feedback}'")
        
    if feedback.startswith("spoken:"):
        spoken_id_str = feedback.split(":")[1]
        try:
            spoken_id = float(spoken_id_str)
            # Remove this item and any older/equal items from the queue
            st.session_state.browser_speech_queue = [
                item for item in st.session_state.browser_speech_queue if item["id"] > spoken_id
            ]
            logging.info(f"[main.py] Speech success confirmation for ID: {spoken_id}. Remaining browser speech queue size: {len(st.session_state.browser_speech_queue)}")
        except ValueError:
            pass
        # Clear the feedback value so it doesn't trigger again
        st.session_state.speech_feedback = ""
        
    elif feedback.startswith("failed:"):
        failed_id_str = feedback.split(":")[1]
        try:
            failed_id = float(failed_id_str)
            # Find the failed item in the queue
            failed_item = next((item for item in st.session_state.browser_speech_queue if abs(item["id"] - failed_id) < 0.001), None)
            if failed_item:
                logging.warning(f"[main.py] Speech failed for ID: {failed_id}. Text: '{failed_item['text']}'. Automatically falling back to pyttsx3 / gTTS.")
                # Switch voice engine to pyttsx3 / gTTS
                st.session_state.voice_engine = "pyttsx3 / gTTS"
                # Speak using the fallback engine
                if st.session_state.voice_pipeline:
                    st.session_state.voice_pipeline.speak(failed_item["text"], priority="high")
                # Remove from browser speech queue
                st.session_state.browser_speech_queue = [
                    item for item in st.session_state.browser_speech_queue if item["id"] != failed_item["id"]
                ]
        except ValueError:
            pass
        # Clear the feedback value so it doesn't trigger again
        st.session_state.speech_feedback = ""

    if st.session_state.get("voice_pipeline") is None:
        try:
            api_key = os.environ.get("GROQ_API_KEY", "")

            if not api_key:
                try:
                    if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
                        api_key = st.secrets["GROQ_API_KEY"]
                except Exception:
                    pass
            
            if api_key:
                groq_client = Groq(api_key=api_key)
            else:
                groq_client = None
            llm_coach = LLMCoach(groq_client)
            tts = TextToSpeech()
            st.session_state.voice_pipeline = VoicePipeline(llm_coach, tts)
            logging.info("[main.py] VoicePipeline successfully initialized.")
        except Exception as e:
            import traceback
            logging.error(f"[main.py] Error initializing VoicePipeline:\n{traceback.format_exc()}")
            st.session_state.voice_pipeline = None

    # Trigger Greeting when application starts
    if st.session_state.get("voice_pipeline") and not st.session_state.get("greeting_played", False):
        st.session_state.voice_pipeline.speak("Hello! Welcome to AI Gym Trainer.")
        st.session_state.greeting_played = True

    workout_started = st.session_state.get("workout_started", False)
    
    with st.sidebar:
        st.title("🏋️‍♂️ Setup Panel")

        if st.session_state.username:
            st.caption(f"👤 Login as {st.session_state.username}")

        st.divider()
        st.subheader("Workout Plan")

        if not workout_started:
            # ── GOAL SYSTEM ─────────────────────────────────────────────────
            st.markdown("**🎯 Your Goal**")
            selected_goal = st.selectbox(
                "Fitness Goal",
                options=GOAL_NAMES,
                index=GOAL_NAMES.index(st.session_state.get("user_goal", "General Fitness")),
                key="goal_selector",
                label_visibility="collapsed"
            )
            if selected_goal != st.session_state.get("user_goal"):
                st.session_state.user_goal = selected_goal
                # Apply goal's recommended rest time
                st.session_state.rest_duration = get_recommended_rest(selected_goal)
                # Persist to DB
                if st.session_state.get("user_id"):
                    update_user_profile(st.session_state.user_id, user_goal=selected_goal)

            goal_cfg = get_goal_config(selected_goal)
            st.markdown(
                f"<div style='background:{goal_cfg['color']}18;border-left:3px solid {goal_cfg['color']};border-radius:8px;padding:8px 12px;font-size:0.8rem;color:#CBD5E1;margin-bottom:10px;'>"
                f"{goal_cfg['emoji']} {goal_cfg['description']}</div>",
                unsafe_allow_html=True
            )

            # ── BODY METRICS PROFILE ─────────────────────────────────────────
            st.markdown("**⚖️ Body Metrics Profile**")
            mcol1, mcol2, mcol3 = st.columns(3)
            with mcol1:
                body_weight = st.number_input(
                    "Weight(kg)", min_value=30.0, max_value=200.0,
                    value=float(st.session_state.get("body_weight_kg", 70.0)),
                    step=0.5, key="body_weight_input"
                )
            with mcol2:
                height_cm = st.number_input(
                    "Height(cm)", min_value=100.0, max_value=250.0,
                    value=float(st.session_state.get("height_cm", 170.0)),
                    step=1.0, key="height_input"
                )
            with mcol3:
                age = st.number_input(
                    "Age", min_value=10, max_value=100,
                    value=int(st.session_state.get("age", 25)),
                    step=1, key="age_input"
                )

            if (body_weight != st.session_state.get("body_weight_kg") or
                height_cm != st.session_state.get("height_cm") or
                age != st.session_state.get("age")):
                
                st.session_state.body_weight_kg = body_weight
                st.session_state.height_cm = height_cm
                st.session_state.age = age
                if st.session_state.get("user_id"):
                    update_user_profile(
                        st.session_state.user_id,
                        body_weight_kg=body_weight,
                        height_cm=height_cm,
                        age=age
                    )
            
            # Show BMI
            bmi = calculate_bmi(body_weight, height_cm)
            bmi_cat, bmi_color = bmi_category(bmi)
            st.markdown(
                f"<div style='background:{bmi_color}18; border:1px solid {bmi_color}40; border-radius:8px; padding:6px 12px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;'>"
                f"<span style='font-size:0.8rem;color:#CBD5E1;'><b>BMI:</b> {bmi}</span>"
                f"<span style='background:{bmi_color};color:#FFF;font-size:0.7rem;padding:2px 8px;border-radius:12px;font-weight:bold;'>{bmi_cat}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

            st.divider()

            # ── WORKOUT SCHEDULER ───────────────────────────────────────────
            st.markdown("**📅 Workout Schedule**")
            with st.expander("Set Schedule", expanded=False):
                # Load schedule on first render
                if not st.session_state.get("schedule_loaded") and st.session_state.get("user_id"):
                    rows = get_schedule(st.session_state.user_id)
                    st.session_state.schedule_rows = rows
                    st.session_state.schedule_loaded = True
                
                sched_rows = st.session_state.get("schedule_rows", [])
                curr_days = [r["day_of_week"] for r in sched_rows]
                curr_time = sched_rows[0]["workout_time"] if sched_rows else "07:00"
                curr_prog = sched_rows[0]["program_name"] if sched_rows else "Full Body Blast"

                import datetime
                try:
                    time_obj = datetime.datetime.strptime(curr_time, "%H:%M").time()
                except ValueError:
                    time_obj = datetime.time(7, 0)

                selected_days = st.multiselect("Days", options=range(7), format_func=lambda x: DAY_NAMES[x], default=curr_days)
                selected_time = st.time_input("Time", value=time_obj)
                sched_prog = st.selectbox("Program", options=PROGRAM_NAMES, index=PROGRAM_NAMES.index(curr_prog) if curr_prog in PROGRAM_NAMES else 0)

                if st.button("Save Schedule"):
                    time_str = selected_time.strftime("%H:%M")
                    if st.session_state.get("user_id"):
                        save_schedule(st.session_state.user_id, selected_days, time_str, sched_prog)
                        st.session_state.schedule_rows = get_schedule(st.session_state.user_id)
                        st.success("Schedule saved!")
            
            # Show summary
            sched_summary = format_schedule_summary(st.session_state.get("schedule_rows", []))
            st.caption(f"🗓️ {sched_summary}")

            st.divider()

            # ── PROGRAM / SINGLE EXERCISE TABS ──────────────────────────────
            tab_program, tab_single = st.tabs(["📋 Program", "🎯 Single Exercise"])

            with tab_program:
                prog_name = st.selectbox(
                    "Select Program",
                    options=PROGRAM_NAMES,
                    key="program_selector"
                )
                prog_emoji = PROGRAM_EMOJIS.get(prog_name, "🏋️")
                prog_desc  = PROGRAM_DESCRIPTIONS.get(prog_name, "")
                prog_exercises = get_program(prog_name)

                # Show program card
                if prog_exercises:
                    ex_lines = "".join(
                        f"<div style='padding:3px 0;font-size:0.82rem;color:#CBD5E1;'>"
                        f"{'🦵' if e['name']=='Squats' else '💪' if e['name']=='Push-ups' else '🦾' if 'Curl' in e['name'] else '🏆' if 'Press' in e['name'] else '🔥'} "
                        f"<b>{e['name']}</b> — {e['sets']} sets × {e['reps']} reps</div>"
                        for e in prog_exercises
                    )
                    st.markdown(
                        f"<div style='background:rgba(15,23,42,0.5);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:12px 14px;margin-bottom:10px;'>"
                        f"<div style='font-size:1rem;font-weight:700;color:#F1F5F9;margin-bottom:6px;'>{prog_emoji} {prog_name}</div>"
                        f"<div style='font-size:0.78rem;color:#64748B;margin-bottom:8px;'>{prog_desc}</div>"
                        f"{ex_lines}</div>",
                        unsafe_allow_html=True
                    )

                start_program_btn = st.button("🚀 Start Program", use_container_width=True, key="start_program_btn",
                                              disabled=not bool(prog_exercises))
                if start_program_btn and prog_exercises:
                    first = prog_exercises[0]
                    st.session_state.program_mode = True
                    st.session_state.active_program_name = prog_name
                    st.session_state.active_program = prog_exercises
                    st.session_state.program_exercise_index = 0
                    st.session_state.program_transitioning = False
                    st.session_state.exercise_type = first["name"]
                    st.session_state.target_sets = first["sets"]
                    st.session_state.reps_per_set = first["reps"]
                    st.session_state.rest_duration = first.get("rest_seconds", get_recommended_rest(selected_goal))
                    st.session_state.reps = 0
                    st.session_state.current_set_reps = 0
                    st.session_state.sets_completed = 0
                    st.session_state.workout_started = True
                    st.session_state.workout_start_time = time.time()
                    st.session_state.calories_burned = 0.0
                    st.session_state.set_cycle_started_at = time.time()
                    st.session_state.last_saved_sets_completed = 0
                    st.session_state.form_score = 100
                    st.session_state.strongest_area = "N/A"
                    st.session_state.weakest_area = "N/A"
                    st.session_state.average_form_score = 0.0
                    st.session_state.best_form_score = 0.0
                    st.session_state.form_scores_history = []
                    st.session_state.component_sums = {}
                    st.session_state.component_counts = {}
                    st.session_state.last_score_update_time = time.time()
                    st.session_state.last_score_voice_time = time.time()
                    st.session_state.last_notified_sets_completed = 0
                    st.session_state.last_notified_workout_complete = False
                    st.session_state.needs_reset = True
                    if st.session_state.voice_pipeline:
                        goal_cfg_inner = get_goal_config(selected_goal)
                        intro = goal_cfg_inner["voice_intro"]
                        result = st.session_state.voice_pipeline.speak(
                            f"{intro} Starting {prog_name}: {first['name']}, {first['sets']} sets of {first['reps']} reps.",
                            priority="high"
                        )
                        if result:
                            st.session_state.audio_to_play, st.session_state.coach_feedback, st.session_state.audio_duration = result
                            st.session_state.audio_play_start = time.time()
                    st.rerun()

            with tab_single:
                plan_exercise = st.selectbox("Exercise", options=EXERCISE_OPTIONS, key="plan_exercise")
                plan_sets = st.number_input("Sets", min_value=1, max_value=50, key="plan_sets", step=1, value=3)
                plan_reps = st.number_input("Reps per Set", min_value=1, max_value=50, key="plan_reps", step=1, value=12)
                st.markdown("")
                start_session_button = st.button("▶ Start Workout", use_container_width=True, key="start_session_button")

                if start_session_button:
                    st.session_state.program_mode = False
                    st.session_state.active_program = []
                    st.session_state.exercise_type = plan_exercise
                    st.session_state.target_sets = int(plan_sets)
                    st.session_state.reps_per_set = int(plan_reps)
                    st.session_state.rest_duration = get_recommended_rest(selected_goal)
                    st.session_state.reps = 0
                    st.session_state.current_set_reps = 0
                    st.session_state.sets_completed = 0
                    st.session_state.workout_started = True
                    st.session_state.workout_start_time = time.time()
                    st.session_state.calories_burned = 0.0
                    st.session_state.set_cycle_started_at = time.time()
                    st.session_state.last_saved_sets_completed = 0
                    st.session_state.form_score = 100
                    st.session_state.strongest_area = "N/A"
                    st.session_state.weakest_area = "N/A"
                    st.session_state.average_form_score = 0.0
                    st.session_state.best_form_score = 0.0
                    st.session_state.form_scores_history = []
                    st.session_state.component_sums = {}
                    st.session_state.component_counts = {}
                    st.session_state.last_score_update_time = time.time()
                    st.session_state.last_score_voice_time = time.time()
                    st.session_state.needs_reset = True
                    if st.session_state.voice_pipeline:
                        goal_cfg_inner = get_goal_config(selected_goal)
                        result = st.session_state.voice_pipeline.process_event(
                            event="workout_started", exercise=plan_exercise, metrics={}
                        )
                        if result:
                            st.session_state.audio_to_play, st.session_state.coach_feedback, st.session_state.audio_duration = result
                            st.session_state.audio_play_start = time.time()
                    st.session_state.last_notified_sets_completed = 0
                    st.session_state.last_notified_workout_complete = False
                    st.rerun()

        else:
            exercise = st.session_state.get("exercise_type")
            sets = st.session_state.get("target_sets")
            reps = st.session_state.get("reps_per_set")

            # Show program progress if in program mode
            if st.session_state.get("program_mode", False):
                prog = st.session_state.get("active_program", [])
                idx = st.session_state.get("program_exercise_index", 0)
                prog_name = st.session_state.get("active_program_name", "")
                st.markdown(f"**📋 {prog_name}**")
                for i, ex in enumerate(prog):
                    if i < idx:
                        icon = "✅"
                    elif i == idx:
                        icon = "▶️"
                    else:
                        icon = "⬜"
                    st.markdown(f"{icon} {ex['name']} {ex['sets']}×{ex['reps']}")
                st.divider()

            st.info(f"🎯 **{exercise}**\n\nGoal: {sets} Sets of {reps} Reps")

            end_session_button = st.button("End Workout", key="end_session_button", use_container_width=True)
            if end_session_button:
                st.session_state.workout_started = False
                st.session_state.program_mode = False
                from services.coaching.feedback_manager import finalize_workout_feedback
                feedback = finalize_workout_feedback()
                if st.session_state.voice_pipeline and feedback.get("voice_cue"):
                    result = st.session_state.voice_pipeline.speak(feedback["voice_cue"], priority="high")
                    if result:
                        st.session_state.audio_to_play, st.session_state.coach_feedback, st.session_state.audio_duration = result
                        st.session_state.audio_play_start = time.time()
                st.rerun()

        st.divider()
        st.subheader("🎙️ Voice Coach Settings")
        voice_enabled = st.toggle("Voice Coach", value=st.session_state.get("voice_enabled", True), key="voice_enabled_toggle")
        st.session_state.voice_enabled = voice_enabled
        
        if voice_enabled:
            voice_engine = st.selectbox(
                "Voice Engine",
                options=["Web Speech API", "pyttsx3 / gTTS"],
                index=0 if st.session_state.get("voice_engine", "pyttsx3 / gTTS") == "Web Speech API" else 1,
                key="voice_engine_select",
                help="Web Speech API plays in browser. pyttsx3/gTTS runs on the server."
            )
            st.session_state.voice_engine = voice_engine
            
            voice_gender = st.radio(
                "Voice Gender",
                options=["Female", "Male"],
                index=0 if st.session_state.get("voice_gender", "Female") == "Female" else 1,
                horizontal=True,
                key="voice_gender_radio"
            )
            st.session_state.voice_gender = voice_gender
            
            voice_volume = st.slider(
                "Volume",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.get("voice_volume", 1.0),
                step=0.1,
                key="voice_volume_slider"
            )
            st.session_state.voice_volume = voice_volume

            # Rest Duration Slider
            rest_duration = st.slider(
                "⏱️ Rest Between Sets (sec)",
                min_value=15,
                max_value=120,
                value=st.session_state.get("rest_duration", 60),
                step=5,
                key="rest_duration_slider"
            )
            st.session_state.rest_duration = rest_duration

            # Phase 5: Test Voice Button
            st.markdown("")
            if st.button("🔊 Test Voice", use_container_width=True, key="test_voice_button"):
                if st.session_state.voice_pipeline:
                    st.session_state.voice_pipeline.speak("Voice system test successful", priority="high")
                else:
                    st.error("Voice pipeline not initialized!")

        st.markdown("")
        dev_mode = st.checkbox("Developer Mode", value=st.session_state.get("developer_mode", False), key="developer_mode")

        # Phase 10 Diagnostics: Raw Audio Test Button (Only in Developer Mode)
        if dev_mode:
            raw_audio = st.session_state.get("audio_to_play")
            if raw_audio is not None:
                st.markdown("")
                if st.button("🔊 RAW AUDIO TEST", use_container_width=True, key="raw_audio_test_button"):
                    st.sidebar.write("Playing raw audio bytes directly...")
                    st.audio(raw_audio, autoplay=True)

        # Phase 9: Debug Panel (Only in Developer Mode)
        if st.session_state.get("developer_mode", False):
            st.divider()
            st.subheader("🛠️ Voice Debug Panel")
            
            pipeline_exists = st.session_state.get("voice_pipeline") is not None
            st.markdown(f"**Voice Pipeline Exists:** `{pipeline_exists}`")
            
            bus_init = st.session_state.get("voice_event_bus") is not None
            st.markdown(f"**Event Bus Initialized:** {'✅ Yes' if bus_init else '❌ No'}")
            
            if bus_init:
                st.markdown(f"**Events Published:** `{st.session_state.voice_event_bus.published_count}`")
                st.markdown(f"**Events Consumed:** `{st.session_state.voice_event_bus.consumed_count}`")
                
            pipeline = st.session_state.get("voice_pipeline")
            if pipeline:
                st.markdown(f"**Speak Called Count:** `{pipeline.speak_called_count}`")
                st.markdown(f"**Last Spoken Text:** *\"{pipeline.last_spoken_text}\"*")
            else:
                st.markdown("**Speak Called Count:** `0`")
                
            st.markdown(f"**Voice Enabled:** `{st.session_state.get('voice_enabled', True)}`")
            st.markdown(f"**Active Engine:** `{st.session_state.get('voice_engine', 'pyttsx3 / gTTS')}`")
            st.markdown(f"**Browser Queue Size:** `{len(st.session_state.get('browser_speech_queue', []))}`")
            st.markdown(f"**Last Event:** `{st.session_state.get('last_event_info', 'None')}`")

    # Title & Header
    title_col1, title_col2 = st.columns([4, 1])
    with title_col1:
        st.title("🏋️‍♂️ Apna AI Gym Coach")
        st.markdown("##### Real-time pose correction and high-energy AI audio training")
    with title_col2:
        if workout_started:
            st.markdown(
                clean_html('<div style="margin-top: 25px;"><span class="pulse-indicator"></span><strong style="color: #10B981; text-transform: uppercase; letter-spacing: 0.05em; font-size: 14px;">Session Active</strong></div>'),
                unsafe_allow_html=True
            )
 
    # Hidden text input for speech confirmation/feedback
    st.text_input("Speech Feedback Link", key="speech_feedback", value="", label_visibility="collapsed")
    st.markdown(
        clean_html("""
        <style>
        div[data-testid="stTextInput"]:has(input[aria-label="Speech Feedback Link"]) {
            display: none !important;
        }
        </style>
        """).strip(),
        unsafe_allow_html=True
    )
 
    # Render the audio player if using backend engine and audio is available.
    audio_to_play = st.session_state.get("audio_to_play")
    logging.debug(f"[main.py] Rerun diagnostics: audio_to_play is {'None' if audio_to_play is None else f'{len(audio_to_play)} bytes'}")
    
    if audio_to_play and st.session_state.get("voice_enabled", True) and st.session_state.get("voice_engine", "pyttsx3 / gTTS") == "pyttsx3 / gTTS":
        autoplay_audio(audio_to_play)

    # Render the Web Speech API player if active
    if st.session_state.get("voice_enabled", True) and st.session_state.get("voice_engine", "pyttsx3 / gTTS") == "Web Speech API":
        speech_queue = st.session_state.get("browser_speech_queue", [])
        if speech_queue:
            import json
            queue_json = json.dumps(speech_queue)
            
            st.markdown(
                clean_html(f"""
                <div id="speech-queue-trigger" data-queue='{queue_json}' style="display:none;"></div>
                <script>
                    (function() {{
                        const trigger = document.getElementById("speech-queue-trigger");
                        if (!trigger) return;
                        
                        let queue = [];
                        try {{
                            queue = JSON.parse(trigger.getAttribute("data-queue") || "[]");
                        }} catch (e) {{
                            console.error("[WebSpeech] Failed to parse queue:", e);
                            return;
                        }}
                        
                        if (queue.length === 0) return;
                        
                        if (!window.spokenSpeechIds) {{
                            window.spokenSpeechIds = new Set();
                        }}
                        
                        const setInputValue = (inputLabel, value) => {{
                            let helper = document.querySelector('input[aria-label="' + inputLabel + '"]');
                            if (!helper && window.parent) {{
                                try {{
                                    helper = window.parent.document.querySelector('input[aria-label="' + inputLabel + '"]');
                                }} catch (e) {{
                                    console.warn("[WebSpeech] Could not access parent document:", e);
                                }}
                            }}
                            if (helper) {{
                                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                nativeInputValueSetter.call(helper, value);
                                helper.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                helper.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                console.log("[WebSpeech] Sent status to Streamlit:", inputLabel, "=", value);
                            }} else {{
                                console.warn("[WebSpeech] Helper input not found:", inputLabel);
                            }}
                        }};
                        
                        // Process the queue
                        queue.forEach(item => {{
                            if (!window.spokenSpeechIds.has(item.id)) {{
                                window.spokenSpeechIds.add(item.id);
                                console.log("[WebSpeech] Speaking item:", item.text, "(ID:", item.id, ")");
                                
                                if (!window.speechSynthesis) {{
                                    console.error("[WebSpeech] speechSynthesis not supported. Triggering fallback.");
                                    setInputValue("Speech Feedback Link", "failed:" + item.id);
                                    return;
                                }}
                                
                                // For high priority, cancel active speech to keep it responsive
                                if (item.priority === "high") {{
                                    window.speechSynthesis.cancel();
                                }}
                                
                                const utterance = new SpeechSynthesisUtterance(item.text);
                                utterance.volume = item.volume;
                                
                                const voices = window.speechSynthesis.getVoices();
                                let voice = null;
                                if (item.gender === 'female') {{
                                    voice = voices.find(v => {{
                                        const name = v.name.toLowerCase();
                                        return name.includes('female') || name.includes('zira') || name.includes('samantha') || name.includes('google us english') || name.includes('hazel');
                                    }});
                                }} else {{
                                    voice = voices.find(v => {{
                                        const name = v.name.toLowerCase();
                                        return name.includes('male') || name.includes('david') || name.includes('microsoft david') || name.includes('google uk english male');
                                    }});
                                }}
                                if (voice) {{
                                    utterance.voice = voice;
                                }}
                                
                                utterance.onend = () => {{
                                    console.log("[WebSpeech] Successfully spoke item:", item.id);
                                    setInputValue("Speech Feedback Link", "spoken:" + item.id);
                                }};
                                
                                utterance.onerror = (event) => {{
                                    console.error("[WebSpeech] Speech error:", event);
                                    if (event.error === 'interrupted' || event.error === 'canceled') {{
                                        // Cleared from queue as it was cut off intentionally
                                        setInputValue("Speech Feedback Link", "spoken:" + item.id);
                                    }} else {{
                                        // Actual failure (e.g. autoplay blocked)
                                        setInputValue("Speech Feedback Link", "failed:" + item.id);
                                    }}
                                }};
                                
                                window.speechSynthesis.speak(utterance);
                            }}
                        }});
                    }})();
                </script>
                """).strip(),
                unsafe_allow_html=True
            )

    st.markdown("")

    tab_session, tab_dashboard = st.tabs(["🏋️ Workout Session", "📊 Progress Dashboard"])
    
    with tab_session:
        if not workout_started:
            # Show Workout Summary if a workout was just completed
            history = st.session_state.get("form_scores_history", [])
            if len(history) > 0:
                avg_score = int(st.session_state.get("average_form_score", 0))
                best_score = int(st.session_state.get("best_form_score", 0))
                
                # Make sure workout feedback is generated & cached in session state
                if not st.session_state.get("feedback_summary"):
                    from services.coaching.feedback_manager import finalize_workout_feedback
                    finalize_workout_feedback()
                    
                rating = st.session_state.get("overall_rating", 0.0)
                strongest_metric = st.session_state.get("strongest_area", "General Posture")
                weakest_metric = st.session_state.get("weakest_area", "General Posture")
                feedback_summary = st.session_state.get("feedback_summary", "")
                recommendation = st.session_state.get("recommendation", "Focus on maintaining your workout streak.")
                imp_pct = st.session_state.get("improvement_percentage", 0.0)
                
                if rating >= 8.0:
                    rating_color = "#10B981"
                    rating_glow = "rgba(16, 185, 129, 0.2)"
                elif rating >= 6.0:
                    rating_color = "#F59E0B"
                    rating_glow = "rgba(245, 158, 11, 0.2)"
                else:
                    rating_color = "#EF4444"
                    rating_glow = "rgba(239, 68, 68, 0.2)"
                    
                if imp_pct > 0:
                    improvement_badge = f"""<span style="background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.3); color: #60A5FA; padding: 6px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem;">📈 Form improved by {imp_pct:.1f}%</span>"""
                elif imp_pct < 0:
                    improvement_badge = f"""<span style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); color: #F87171; padding: 6px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem;">📉 Form score change: {imp_pct:.1f}%</span>"""
                else:
                    improvement_badge = """<span style="background: rgba(148, 163, 184, 0.12); border: 1px solid rgba(148, 163, 184, 0.3); color: #CBD5E1; padding: 6px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem;">💪 Steady Form</span>"""
                    
                summary_paragraph = ""
                if feedback_summary:
                    summary_paragraph = f"""<div style="font-size: 1.05rem; color: #E2E8F0; line-height: 1.6; font-style: italic; margin-bottom: 16px;">"{feedback_summary}"</div>"""
                
                st.markdown(
                    clean_html(f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(30, 41, 59, 0.45) 0%, rgba(15, 23, 42, 0.65) 100%);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 20px;
                        padding: 28px;
                        margin-top: 24px;
                        margin-bottom: 24px;
                        backdrop-filter: blur(16px);
                        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
                    ">
                        <h3 style="color: #FFF; margin-top: 0; margin-bottom: 20px; font-weight: 800; font-size: 1.35rem; display: flex; align-items: center; gap: 10px;">
                            🏆 AI Post-Workout Summary
                        </h3>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 24px;">
                            <div style="background: rgba(15, 23, 42, 0.5); padding: 16px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); text-align: center;">
                                <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Performance Rating</div>
                                <div style="font-size: 2.2rem; font-weight: 900; color: {rating_color}; margin-top: 4px; text-shadow: 0 0 8px {rating_glow};">
                                    {rating}/10
                                </div>
                            </div>
                            <div style="background: rgba(15, 23, 42, 0.5); padding: 16px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); display: flex; flex-direction: column; justify-content: center; gap: 8px;">
                                <div style="display: flex; justify-content: space-between; font-size: 0.9rem;">
                                    <span style="color: #94A3B8; font-weight: 600;">Total Reps:</span>
                                    <span style="color: #3B82F6; font-weight: 800; font-size: 1.05rem;">{st.session_state.get("reps", 0)}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; font-size: 0.9rem;">
                                    <span style="color: #94A3B8; font-weight: 600;">Sets Completed:</span>
                                    <span style="color: #A855F7; font-weight: 800; font-size: 1.05rem;">{st.session_state.get("sets_completed", 0)}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; font-size: 0.9rem;">
                                    <span style="color: #94A3B8; font-weight: 600;">Avg Form:</span>
                                    <span style="color: #10B981; font-weight: 800; font-size: 1.05rem;">{avg_score}%</span>
                                </div>
                            </div>
                        </div>
                        <div style="border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px;">
                            <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px;">
                                <span style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); color: #34D399; padding: 6px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem;">🌟 Strongest: {strongest_metric}</span>
                                <span style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); color: #F87171; padding: 6px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem;">⚠️ Weakest: {weakest_metric}</span>
                                {improvement_badge}
                            </div>
                            
                            {summary_paragraph}
                            
                            <div style="background: rgba(245, 158, 11, 0.06); border-left: 4px solid #F59E0B; padding: 14px 16px; border-radius: 0 10px 10px 0; margin-top: 12px;">
                                <div style="font-size: 0.8rem; color: #F59E0B; font-weight: 700; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.05em;">Recommendation</div>
                                <div style="font-size: 0.95rem; color: #FBBF24; font-weight: 600; line-height: 1.45;">
                                    {recommendation}
                                </div>
                            </div>
                        </div>
                    </div>
                    """).strip(),
                    unsafe_allow_html=True
                )

            st.markdown(
                clean_html("""
                <div style="
                    border: 2px dashed rgba(255, 255, 255, 0.15);
                    border-radius: 16px;
                    padding: 40px;
                    text-align: center;
                    color: #94A3B8;
                    margin-top: 32px;
                    margin-bottom: 32px;
                    background-color: rgba(15, 23, 42, 0.2);
                    backdrop-filter: blur(8px);
                ">
                    <h2 style="color:#FFF; margin-bottom:12px; font-weight: 700;">👈 Set your workout plan in the sidebar</h2>
                    <p style="font-size:1.05rem; color:#94A3B8;">
                        Choose your goal, exercise program and click <strong>Start Workout</strong><br>
                        to activate the camera feed and AI coach.
                    </p>
                </div>
                """).strip(),
                unsafe_allow_html=True,
            )

            # ── 📹 Exercise Demo Section ─────────────────────────────────────────
            DEMO_IMAGES = {
                "Squats":                  "static/demos/squat.png",
                "Push-ups":                "static/demos/pushup.png",
                "Biceps Curls (Dumbbell)": "static/demos/bicep_curl.png",
                "Shoulder Press":          "static/demos/shoulder_press.png",
                "Lunges":                  "static/demos/lunge.png",
            }
            DEMO_TIPS = {
                "Squats":                  ["Feet shoulder-width apart", "Knees track over toes", "Back stays straight", "Thighs parallel to floor"],
                "Push-ups":                ["Body in a straight line", "Hands shoulder-width apart", "Core tight throughout", "Chest touches the floor"],
                "Biceps Curls (Dumbbell)": ["Elbows pinned to sides", "Full range of motion", "Controlled on the way down", "No swinging"],
                "Shoulder Press":          ["Press straight overhead", "Full extension at top", "Core braced", "Controlled descent"],
                "Lunges":                  ["Front knee 90 degrees", "Back knee near floor", "Torso upright", "Push back through front heel"],
            }
            BREATHING_TIPS = {
                "Squats":                  "Inhale going down → Exhale coming up",
                "Push-ups":                "Inhale lowering → Exhale on the push",
                "Biceps Curls (Dumbbell)": "Exhale curling up → Inhale lowering",
                "Shoulder Press":          "Exhale pressing up → Inhale lowering",
                "Lunges":                  "Inhale stepping down → Exhale pushing up",
            }

            st.markdown("---")
            st.markdown("### 📹 Exercise Form Guide")

            # Show selector for which exercise to preview
            demo_choices = list(DEMO_IMAGES.keys())
            demo_exercise = st.selectbox(
                "Preview exercise form:",
                options=demo_choices,
                key="demo_exercise_selector"
            )

            demo_col1, demo_col2 = st.columns([1, 1], gap="large")
            with demo_col1:
                img_path = DEMO_IMAGES.get(demo_exercise)
                if img_path and os.path.exists(img_path):
                    st.image(img_path, caption=f"{demo_exercise} — Correct Form", use_container_width=True)
            with demo_col2:
                st.markdown(f"**✅ Key Form Points**")
                for tip in DEMO_TIPS.get(demo_exercise, []):
                    st.markdown(f"- {tip}")
                st.markdown("")
                breath = BREATHING_TIPS.get(demo_exercise, "")
                st.markdown(
                    f"<div style='background:rgba(16,185,129,0.1);border-left:3px solid #10B981;border-radius:8px;padding:10px 14px;font-size:0.88rem;color:#6EE7B7;margin-top:8px;'>"
                    f"🫁 <b>Breathing:</b> {breath}</div>",
                    unsafe_allow_html=True
                )
        else:
            # Wide dashboard split — camera gets much more space
            col1, col2 = st.columns([2.2, 1.0], gap="large")

            # ── 🛑 Injury Warning Banner ──────────────────────────────────────
            if st.session_state.get("injury_warning_active", False):
                st.markdown(
                    clean_html("""
                    <div style="
                        background: rgba(239, 68, 68, 0.18);
                        border: 2px solid #EF4444;
                        border-radius: 14px;
                        padding: 16px 20px;
                        margin-bottom: 14px;
                        display: flex;
                        align-items: center;
                        gap: 14px;
                        animation: pulse-red 1s ease-in-out infinite alternate;
                    ">
                        <div style="font-size: 2rem;">🛑</div>
                        <div>
                            <div style="font-size: 1rem; font-weight: 800; color: #FCA5A5; text-transform: uppercase; letter-spacing: 0.05em;">Dangerous Form Detected!</div>
                            <div style="font-size: 0.88rem; color: #FCA5A5; margin-top: 2px;">Please STOP and correct your posture before continuing. 3+ consecutive bad reps detected.</div>
                        </div>
                    </div>
                    <style>
                    @keyframes pulse-red {
                        from { box-shadow: 0 0 0px rgba(239,68,68,0.0); }
                        to   { box-shadow: 0 0 20px rgba(239,68,68,0.5); }
                    }
                    </style>
                    """).strip(),
                    unsafe_allow_html=True
                )

            # ── ⏱️ Rest Timer Banner ──────────────────────────────────────────
            if st.session_state.get("rest_timer_active", False):
                remaining = st.session_state.rest_timer_end - time.time()
                if remaining > 0:
                    rem_int = int(remaining)
                    mins = rem_int // 60
                    secs = rem_int % 60
                    time_display = f"{mins}:{secs:02d}" if mins > 0 else f"{secs}s"
                    rest_total = st.session_state.get("rest_duration", 60)
                    progress_val = max(0.0, min(1.0, remaining / rest_total))

                    if rem_int <= 10:
                        timer_color = "#EF4444"
                        timer_bg = "rgba(239, 68, 68, 0.12)"
                        timer_border = "rgba(239, 68, 68, 0.4)"
                    elif rem_int <= 30:
                        timer_color = "#F59E0B"
                        timer_bg = "rgba(245, 158, 11, 0.10)"
                        timer_border = "rgba(245, 158, 11, 0.35)"
                    else:
                        timer_color = "#10B981"
                        timer_bg = "rgba(16, 185, 129, 0.10)"
                        timer_border = "rgba(16, 185, 129, 0.35)"

                    st.markdown(
                        clean_html(f"""
                        <div style="
                            background: {timer_bg};
                            border: 2px solid {timer_border};
                            border-radius: 14px;
                            padding: 14px 20px;
                            margin-bottom: 14px;
                            display: flex;
                            align-items: center;
                            justify-content: space-between;
                            gap: 16px;
                        ">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <div style="font-size: 1.8rem;">⏱️</div>
                                <div>
                                    <div style="font-size: 0.75rem; color: #94A3B8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;">Rest Timer</div>
                                    <div style="font-size: 0.88rem; color: #CBD5E1; margin-top: 1px;">Next set starts soon. Catch your breath!</div>
                                </div>
                            </div>
                            <div style="font-size: 2.8rem; font-weight: 900; color: {timer_color}; letter-spacing: -0.02em; min-width: 80px; text-align: right;">
                                {time_display}
                            </div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )
                    st.progress(progress_val)


            with col1:
                st.markdown("#### 📷 Video Analysis")

                # Force the WebRTC iframe to be tall so the camera feed is large
                st.markdown(
                    """
                    <style>
                    div[data-testid="stIFrame"] iframe,
                    div[data-st-key="exercise-analysis"] iframe {
                        min-height: 520px !important;
                        height: 520px !important;
                        border-radius: 16px !important;
                        border: 2px solid rgba(0, 210, 255, 0.25) !important;
                        box-shadow: 0 0 40px rgba(0, 210, 255, 0.08) !important;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )

                if mp_solutions is None:
                    st.error(f"🚨 **MediaPipe Failed to Load!**\n\n**Exact Error:** `{_mp_import_error}`\n\n**How to fix:** This is usually due to NumPy 2.x or missing Linux GLib libraries. We have updated requirements.txt and packages.txt — please click **Manage App** -> **⋮** -> **Clear cache and deploy**!")
                    return

                is_cloud = ("/mount/src" in __file__ or "/home/adminuser" in __file__ or "/app" in __file__ or bool(os.environ.get("SPACE_ID")))
                context = webrtc_streamer(
                    key="exercise-analysis",
                    mode=WebRtcMode.SENDRECV,
                    video_processor_factory=VideoProcessorClass,
                    rtc_configuration={
                        "iceServers": [
                            {"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302", "stun:stun2.l.google.com:19302", "stun:stun3.l.google.com:19302"]},
                            {"urls": ["stun:stun.services.mozilla.com"]},
                            {"urls": ["stun:global.stun.twilio.com:3478"]},
                            {"urls": ["stun:stun.cloudflare.com:3478"]},
                            {
                                "urls": [
                                    "turn:openrelay.metered.ca:80",
                                    "turn:openrelay.metered.ca:443",
                                    "turn:openrelay.metered.ca:3478",
                                    "turns:openrelay.metered.ca:443"
                                ],
                                "username": "openrelayproject",
                                "credential": "openrelayproject"
                            }
                        ]
                    },
                    media_stream_constraints={
                        "video": {
                            "width": {"ideal": 640},
                            "height": {"ideal": 480},
                            "frameRate": {"ideal": 15 if is_cloud else 30}
                        },
                        "audio": False
                    },
                    async_processing=True
                )

                sync_metrics_update(context)

                if st.session_state.get("coach_feedback"):
                    st.markdown("")
                    st.success(f"🤖 **Coach:** {st.session_state.coach_feedback}")

            with col2:
                st.markdown("#### 📊 Progress Tracker")

                exercise = st.session_state.get("exercise_type")
                total_reps = st.session_state.get("reps")
                current_set_reps = st.session_state.get("current_set_reps")
                reps_per_set = st.session_state.get("reps_per_set")
                sets_completed = st.session_state.get("sets_completed")
                target_sets = st.session_state.get("target_sets")

                # ── Goal Badge ─────────────────────────────────────────
                user_goal = st.session_state.get("user_goal", "General Fitness")
                goal_cfg_live = get_goal_config(user_goal)
                st.markdown(
                    f"<div style='background:{goal_cfg_live['color']}18;border:1px solid {goal_cfg_live['color']}40;"
                    f"border-radius:8px;padding:6px 12px;font-size:0.78rem;color:{goal_cfg_live['color']};"
                    f"font-weight:700;margin-bottom:10px;display:inline-block;'>"
                    f"{goal_cfg_live['emoji']} {user_goal}</div>",
                    unsafe_allow_html=True
                )

                # Progress metrics displayed in structured cards
                pcol1, pcol2 = st.columns(2)
                with pcol1:
                    st.metric("Total Reps Done", f"{total_reps}")
                with pcol2:
                    st.metric("Set Reps Completed", f"{current_set_reps} / {reps_per_set}")
                st.metric("Sets Completed", f"{sets_completed} / {target_sets}")

                # ── 🔥 Live Calorie Counter ────────────────────────────
                kcal = st.session_state.get("calories_burned", 0.0)
                weight_kg = st.session_state.get("body_weight_kg", 70.0)
                st.markdown(
                    clean_html(f"""
                    <div style="
                        background: rgba(239, 68, 68, 0.08);
                        border: 1px solid rgba(239, 68, 68, 0.25);
                        border-radius: 10px;
                        padding: 10px 14px;
                        margin-bottom: 10px;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    ">
                        <div>
                            <div style="font-size: 0.7rem; color: #94A3B8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em;">🔥 Calories Burned</div>
                            <div style="font-size: 0.72rem; color: #64748B; margin-top: 1px;">{weight_kg} kg · {exercise}</div>
                        </div>
                        <div style="font-size: 1.9rem; font-weight: 900; color: #F87171;">
                            {kcal} <span style="font-size: 0.9rem; color: #94A3B8; font-weight: 500;">kcal</span>
                        </div>
                    </div>
                    """).strip(),
                    unsafe_allow_html=True
                )

                # AI Form Score Card
                from services.coaching.feedback_manager import get_recommendation_by_weakest_area
                form_score = st.session_state.get("form_score", 100)
                strongest = st.session_state.get("strongest_area", "N/A")
                weakest = st.session_state.get("weakest_area", "N/A")

                # --- Speak recommendation when weakest area changes or every 20s ---
                if st.session_state.get("workout_started", False) and weakest not in ("N/A", "General Posture"):
                    last_spoken_weakest = st.session_state.get("last_spoken_weakest_area", "")
                    last_weakest_voice_time = st.session_state.get("last_weakest_voice_time", 0.0)
                    now_w = time.time()
                    area_changed = (weakest != last_spoken_weakest)
                    cooldown_passed = (now_w - last_weakest_voice_time >= 20.0)

                    if (area_changed or cooldown_passed) and st.session_state.get("voice_pipeline"):
                        rec_text = get_recommendation_by_weakest_area(weakest)
                        # Shorten to a voice-friendly cue
                        voice_rec = f"Focus on {weakest}: {rec_text}"
                        result = st.session_state.voice_pipeline.speak(voice_rec, priority="normal")
                        if result:
                            st.session_state.audio_to_play, st.session_state.coach_feedback, st.session_state.audio_duration = result
                            st.session_state.audio_play_start = time.time()
                        st.session_state.last_spoken_weakest_area = weakest
                        st.session_state.last_weakest_voice_time = now_w

                if form_score >= 90:
                    color = "#10B981"  # Green
                    label = "Excellent"
                elif form_score >= 75:
                    color = "#3B82F6"  # Blue/Good
                    label = "Good"
                elif form_score >= 60:
                    color = "#F59E0B"  # Yellow/Orange
                    label = "Average"
                else:
                    color = "#EF4444"  # Red
                    label = "Needs Improvement"
                
                st.markdown(
                    clean_html(f"""
                    <div style="
                        background: rgba(15, 23, 42, 0.4);
                        border: 1px solid {color}40;
                        border-left: 5px solid {color};
                        border-radius: 12px;
                        padding: 16px;
                        margin-top: 15px;
                        margin-bottom: 15px;
                        backdrop-filter: blur(8px);
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 0.9rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">AI Form Score</span>
                            <span style="background: {color}20; color: {color}; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 9999px; text-transform: uppercase;">{label}</span>
                        </div>
                        <div style="font-size: 2.2rem; font-weight: 800; color: #FFFFFF; margin-top: 4px; margin-bottom: 4px;">
                            {form_score} <span style="font-size: 1.1rem; color: #64748B; font-weight: 500;">/ 100</span>
                        </div>
                        <div style="display: flex; gap: 16px; font-size: 0.85rem; margin-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.05); padding-top: 8px;">
                            <div><strong style="color: #94A3B8;">Strongest:</strong> <span style="color: #10B981; font-weight: 600;">{strongest}</span></div>
                            <div><strong style="color: #94A3B8;">Weakest:</strong> <span style="color: #EF4444; font-weight: 600;">{weakest}</span></div>
                        </div>
                    </div>
                    """).strip(),
                    unsafe_allow_html=True
                )

                # Live Recommendation Card — shown when weakest area is known
                if weakest not in ("N/A", "General Posture"):
                    from services.coaching.feedback_manager import get_recommendation_by_weakest_area
                    live_rec = get_recommendation_by_weakest_area(weakest)
                    st.markdown(
                        clean_html(f"""
                        <div style="
                            background: rgba(239, 68, 68, 0.07);
                            border: 1px solid rgba(239, 68, 68, 0.25);
                            border-left: 4px solid #EF4444;
                            border-radius: 10px;
                            padding: 12px 14px;
                            margin-bottom: 14px;
                        ">
                            <div style="font-size: 0.72rem; color: #F87171; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px;">
                                👁️ Coach Tip — Improve {weakest}
                            </div>
                            <div style="font-size: 0.88rem; color: #FCA5A5; line-height: 1.45; font-weight: 500;">
                                {live_rec}
                            </div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )

                st.divider()
                st.markdown("#### 🏋️ Live Exercise Metrics")

                if exercise == "Squats":
                    mcol1, mcol2 = st.columns(2)
                    with mcol1:
                        st.metric("Knee Angle", f"{st.session_state.knee_angle}°")
                    with mcol2:
                        st.metric("Back Angle", f"{st.session_state.back_angle}°")
                    st.markdown(f"**Depth Evaluation:** {st.session_state.depth_status}")

                elif exercise == "Push-ups":
                    mcol1, mcol2 = st.columns(2)
                    with mcol1:
                        st.metric("Elbow Angle", f"{st.session_state.elbow_angle}°")
                    with mcol2:
                        st.metric("Body Alignment", st.session_state.body_alignment)

                elif exercise == "Biceps Curls (Dumbbell)":
                    mcol1, mcol2 = st.columns(2)
                    with mcol1:
                        st.metric("Elbow Angle", f"{st.session_state.elbow_angle}°")
                    with mcol2:
                        st.metric("Shoulder Stability", st.session_state.shoulder_status)
                    
                    # ── Symmetry Detection (Biceps Curls) ───────────────────
                    left_ang = st.session_state.get("left_elbow_angle", 0)
                    right_ang = st.session_state.get("right_elbow_angle", 0)
                    if left_ang > 0 and right_ang > 0:
                        diff = abs(left_ang - right_ang)
                        sym_color = "#10B981" if diff <= 15 else "#F59E0B" if diff <= 30 else "#EF4444"
                        weaker_side = "Left arm" if left_ang > right_ang + 5 else "Right arm" if right_ang > left_ang + 5 else "Balanced"
                        sym_text = "Good Symmetry" if weaker_side == "Balanced" else f"{weaker_side} is lagging ({diff}° diff)"
                        
                        st.markdown(
                            f"<div style='background:{sym_color}10;border:1px solid {sym_color}40;border-radius:8px;padding:10px;margin-top:10px;'>"
                            f"<div style='font-size:0.75rem;color:#94A3B8;text-transform:uppercase;font-weight:700;'>⚖️ Left vs Right Symmetry</div>"
                            f"<div style='display:flex;justify-content:space-between;margin-top:6px;'>"
                            f"<div><span style='color:#CBD5E1;font-size:0.85rem;'>Left:</span> <strong style='color:#FFF;'>{left_ang}°</strong></div>"
                            f"<div><span style='color:#CBD5E1;font-size:0.85rem;'>Right:</span> <strong style='color:#FFF;'>{right_ang}°</strong></div>"
                            f"</div>"
                            f"<div style='color:{sym_color};font-size:0.85rem;font-weight:600;margin-top:4px;'>{sym_text}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

                elif exercise == "Shoulder Press":
                    mcol1, mcol2 = st.columns(2)
                    with mcol1:
                        st.metric("Elbow Angle", f"{st.session_state.elbow_angle}°")
                    with mcol2:
                        st.metric("Arm Extension", st.session_state.extension_status)

                elif exercise == "Lunges":
                    mcol1, mcol2 = st.columns(2)
                    with mcol1:
                        st.metric("Front Knee Angle", f"{st.session_state.front_knee_angle}°")
                    with mcol2:
                        st.metric("Torso Angle", f"{st.session_state.torso_angle}°")
                    st.markdown(f"**Balance Evaluation:** {st.session_state.balance_status}")

                    # ── Symmetry Detection (Lunges) ─────────────────────────
                    left_ang = st.session_state.get("left_knee_angle", 0)
                    right_ang = st.session_state.get("right_knee_angle", 0)
                    if left_ang > 0 and right_ang > 0:
                        diff = abs(left_ang - right_ang)
                        sym_color = "#10B981" if diff <= 15 else "#F59E0B" if diff <= 30 else "#EF4444"
                        weaker_side = "Left leg" if left_ang > right_ang + 5 else "Right leg" if right_ang > left_ang + 5 else "Balanced"
                        sym_text = "Good Symmetry" if weaker_side == "Balanced" else f"{weaker_side} is lagging ({diff}° diff)"
                        
                        st.markdown(
                            f"<div style='background:{sym_color}10;border:1px solid {sym_color}40;border-radius:8px;padding:10px;margin-top:10px;'>"
                            f"<div style='font-size:0.75rem;color:#94A3B8;text-transform:uppercase;font-weight:700;'>⚖️ Left vs Right Symmetry</div>"
                            f"<div style='display:flex;justify-content:space-between;margin-top:6px;'>"
                            f"<div><span style='color:#CBD5E1;font-size:0.85rem;'>Left Knee:</span> <strong style='color:#FFF;'>{left_ang}°</strong></div>"
                            f"<div><span style='color:#CBD5E1;font-size:0.85rem;'>Right Knee:</span> <strong style='color:#FFF;'>{right_ang}°</strong></div>"
                            f"</div>"
                            f"<div style='color:{sym_color};font-size:0.85rem;font-weight:600;margin-top:4px;'>{sym_text}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

            # ── Program Transition Banner ──────────────────────────────────
            if st.session_state.get("program_transitioning", False):
                next_idx = st.session_state.get("program_exercise_index", 0) + 1
                prog = st.session_state.get("active_program", [])
                if next_idx < len(prog):
                    next_ex = prog[next_idx]
                    st.markdown(
                        clean_html(f"""
                        <div style="
                            background: rgba(59, 130, 246, 0.15);
                            border: 2px solid rgba(59, 130, 246, 0.5);
                            border-radius: 14px;
                            padding: 16px 20px;
                            margin-top: 12px;
                            text-align: center;
                        ">
                            <div style="font-size: 1.1rem; font-weight: 800; color: #93C5FD;">⏭️ Next Up</div>
                            <div style="font-size: 1.4rem; font-weight: 900; color: #DBEAFE; margin: 4px 0;">{next_ex['name']}</div>
                            <div style="font-size: 0.85rem; color: #94A3B8;">{next_ex['sets']} sets × {next_ex['reps']} reps · Starting in 3 seconds...</div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )

            if context.video_processor is not None and context.state.playing:
                time.sleep(0.25)
                st.rerun()

            inject_webrtc_styles()

        st.divider()

        st.markdown("#### Workout History")

        user_id = st.session_state.get("user_id", 0)

        if isinstance(user_id, int):
            history_rows = get_users_exercises(user_id)

            arr = [
                {
                    "Exercise": row['exercise_name'],
                    "Reps": row['reps'],
                    "Sets": row['sets'],
                    "Time (sec)": row['time'],
                    "Avg Form Score": int(row['average_form_score']) if row.get('average_form_score') is not None else 0,
                    "Best Form Score": int(row['best_form_score']) if row.get('best_form_score') is not None else 0,
                    "Date": row['created_at']
                }
                for row in history_rows
            ]

            df = pd.DataFrame(arr)

            if not df.empty:
                df["Date"] = pd.to_datetime(df["Date"])
                # Table visualization
                table_df = df.copy()
                table_df["Date"] = table_df["Date"].dt.date
                agg_df = table_df.groupby(["Exercise", "Date"]).agg({
                    "Reps": 'sum',
                    "Sets": "sum",
                    "Time (sec)": "sum",
                    "Avg Form Score": "mean",
                    "Best Form Score": "max"
                }).reset_index()
                # Clean up floats to integers for clean display
                agg_df["Avg Form Score"] = agg_df["Avg Form Score"].round().astype(int)
                agg_df["Best Form Score"] = agg_df["Best Form Score"].round().astype(int)
                agg_df.index += 1
                st.table(agg_df)
            
                # Analytics Trend Line Chart
                st.markdown("##### 📈 Form Score Trend Over Time")
                # Sort workouts chronologically for trend analysis
                trend_df = df.sort_values("Date")
                trend_df["Session"] = trend_df["Date"].dt.strftime("%b %d, %H:%M") + " (" + trend_df["Exercise"] + ")"
                # Plot
                chart_data = trend_df[["Session", "Avg Form Score", "Best Form Score"]].set_index("Session")
                st.line_chart(chart_data)
            else:
                st.info("No workout history found.")

    with tab_dashboard:
        st.markdown("### 📊 Long-Term Progress Dashboard")
        
        user_id = st.session_state.get("user_id", 0)
        if isinstance(user_id, int):
            history_rows = get_users_exercises(user_id)
            stats = calculate_progress_stats(history_rows)
            
            # Format time spent
            total_sec = stats["total_time_sec"]
            h = int(total_sec // 3600)
            m = int((total_sec % 3600) // 60)
            s = int(total_sec % 60)
            if h > 0:
                time_str = f"{h}h {m}m"
            elif m > 0:
                time_str = f"{m}m {s}s"
            else:
                time_str = f"{s}s"
                
            # Consistency & Habits Row (3 columns)
            st.markdown("##### 📅 Consistency & Habits")
            with st.container():
                con_col1, con_col2, con_col3 = st.columns(3)
                
                with con_col1:
                    st.markdown(
                        clean_html(f"""
                        <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); border-top: 4px solid #EF4444; border-radius: 12px; padding: 20px; text-align: center; backdrop-filter: blur(8px); margin-bottom: 15px;">
                            <div style="font-size: 1.8rem; margin-bottom: 2px;">🔥</div>
                            <div style="font-size: 0.85rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Current Streak</div>
                            <div style="font-size: 2.2rem; font-weight: 800; color: #EF4444; margin-top: 4px;">{stats['current_streak']} <span style="font-size: 1.1rem; color: #94A3B8; font-weight: 500;">Days</span></div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )
                    
                with con_col2:
                    st.markdown(
                        clean_html(f"""
                        <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.2); border-top: 4px solid #F59E0B; border-radius: 12px; padding: 20px; text-align: center; backdrop-filter: blur(8px); margin-bottom: 15px;">
                            <div style="font-size: 1.8rem; margin-bottom: 2px;">🏆</div>
                            <div style="font-size: 0.85rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Longest Streak</div>
                            <div style="font-size: 2.2rem; font-weight: 800; color: #F59E0B; margin-top: 4px;">{stats['longest_streak']} <span style="font-size: 1.1rem; color: #94A3B8; font-weight: 500;">Days</span></div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )
                    
                with con_col3:
                    st.markdown(
                        clean_html(f"""
                        <div style="background: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.2); border-top: 4px solid #3B82F6; border-radius: 12px; padding: 20px; text-align: center; backdrop-filter: blur(8px); margin-bottom: 15px;">
                            <div style="font-size: 1.8rem; margin-bottom: 2px;">📅</div>
                            <div style="font-size: 0.85rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Active Days</div>
                            <div style="font-size: 2.2rem; font-weight: 800; color: #3B82F6; margin-top: 4px;">{stats['active_days']} <span style="font-size: 1.1rem; color: #94A3B8; font-weight: 500;">Days</span></div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )
            
            st.markdown("<div style='clear: both; margin-top: 15px;'></div>", unsafe_allow_html=True)
            
            # Monthly Consistency & Streak History Timeline
            with st.container():
                mcol_left, mcol_right = st.columns([1.2, 1.0])
                with mcol_left:
                    st.markdown(f"**Monthly Consistency:** `{stats['monthly_consistency']:.1f}%` of days active this month")
                    st.progress(stats["monthly_consistency"] / 100.0)
                with mcol_right:
                    with st.expander("📅 View Workout Streak History", expanded=False):
                        if stats["unique_dates"]:
                            st.write("Dates you completed at least one workout:")
                            for idx, date_str in enumerate(stats["unique_dates"]):
                                st.markdown(f"{idx+1}. 🗓️ **{date_str}**")
                        else:
                            st.write("No workouts recorded yet.")
            
            st.markdown("<div style='clear: both; margin-top: 25px;'></div>", unsafe_allow_html=True)
            
            # Workout Performance Row (4 columns)
            st.markdown("##### 📊 Workout Performance")
            with st.container():
                perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
                
                with perf_col1:
                    st.markdown(
                        clean_html(f"""
                        <div style="background: rgba(30, 41, 59, 0.35); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 16px; text-align: center; backdrop-filter: blur(8px); margin-bottom: 15px;">
                            <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Total Workouts</div>
                            <div style="font-size: 1.8rem; font-weight: 800; color: #FFFFFF; margin-top: 6px;">{stats['total_workouts']}</div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )
                    
                with perf_col2:
                    st.markdown(
                        clean_html(f"""
                        <div style="background: rgba(30, 41, 59, 0.35); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 16px; text-align: center; backdrop-filter: blur(8px); margin-bottom: 15px;">
                            <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Total Volume</div>
                            <div style="font-size: 1.8rem; font-weight: 800; color: #FFFFFF; margin-top: 6px;">{stats['total_reps']} <span style="font-size: 0.95rem; color: #64748B; font-weight: 500;">reps</span></div>
                            <div style="font-size: 0.72rem; color: #64748B; margin-top: 2px;">Sets: {stats['total_sets']}</div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )
                    
                with perf_col3:
                    st.markdown(
                        clean_html(f"""
                        <div style="background: rgba(30, 41, 59, 0.35); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 16px; text-align: center; backdrop-filter: blur(8px); margin-bottom: 15px;">
                            <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Avg Form Score</div>
                            <div style="font-size: 1.8rem; font-weight: 800; color: #FFFFFF; margin-top: 6px;">{stats['avg_form_score']} <span style="font-size: 0.95rem; color: #64748B; font-weight: 500;">/100</span></div>
                            <div style="font-size: 0.72rem; color: #64748B; margin-top: 2px;">Best: {stats['best_form_score']}</div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )
                    
                with perf_col4:
                    st.markdown(
                        clean_html(f"""
                        <div style="background: rgba(30, 41, 59, 0.35); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 16px; text-align: center; backdrop-filter: blur(8px); margin-bottom: 15px;">
                            <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Active Time</div>
                            <div style="font-size: 1.8rem; font-weight: 800; color: #FFFFFF; margin-top: 6px;">{time_str}</div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )
            
            st.markdown("<div style='clear: both; margin-top: 20px;'></div>", unsafe_allow_html=True)
            
            # AI Insights Section
            insights = get_ai_insights(history_rows, stats)
            insights_html = "".join([f"<li style='margin-bottom: 8px; color: #E2E8F0; font-size: 0.95rem;'>{ins}</li>" for ins in insights])
            
            # Find last feedback
            last_feedback_text = None
            if history_rows:
                for row in history_rows:
                    if row.get("feedback_summary"):
                        last_feedback_text = row["feedback_summary"]
                        break
                        
            last_session_feedback_html = ""
            if last_feedback_text:
                last_session_feedback_html = clean_html(f"""
                <div style="margin-top: 14px; padding-top: 14px; border-top: 1px solid rgba(245, 158, 11, 0.18); font-style: italic; color: #FFE3B3; font-size: 0.95rem;">
                    <strong>Latest Coach Feedback:</strong> "{last_feedback_text}"
                </div>
                """)
                
            st.markdown(
                clean_html(f"""
                <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.18); border-left: 5px solid #F59E0B; border-radius: 12px; padding: 20px; margin-top: 16px; margin-bottom: 24px; backdrop-filter: blur(8px);">
                    <h4 style="color: #F59E0B; margin-top: 0; margin-bottom: 12px; font-weight: 700; display: flex; align-items: center; gap: 8px;">
                        💡 Personal AI Coaching Insights
                    </h4>
                    <ul style="margin: 0; padding-left: 20px;">
                        {insights_html}
                    </ul>
                    {last_session_feedback_html}
                </div>
                """).strip(),
                unsafe_allow_html=True
            )
            
            # Weekly & Monthly Progress Summaries
            from services.tracking.progress_analytics import calculate_weekly_monthly_progress
            progress_trends = calculate_weekly_monthly_progress(history_rows)
            
            st.markdown("##### 📈 Weekly & Monthly Coach Summaries")
            trend_col1, trend_col2 = st.columns(2)
            
            with trend_col1:
                weekly_form = progress_trends["weekly_form_change"]
                weekly_form_str = f"+{weekly_form:.1f}" if weekly_form > 0 else f"{weekly_form:.1f}"
                weekly_reps = progress_trends["weekly_reps_change"]
                weekly_reps_str = f"+{weekly_reps}" if weekly_reps > 0 else f"{weekly_reps}"
                
                st.markdown(
                    clean_html(f"""
                    <div style="background: rgba(59, 130, 246, 0.04); border: 1px solid rgba(59, 130, 246, 0.15); border-radius: 12px; padding: 18px; height: 100%; backdrop-filter: blur(8px);">
                        <h5 style="color: #60A5FA; margin-top: 0; margin-bottom: 12px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
                            🗓️ Weekly Improvement Summary
                        </h5>
                        <div style="display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap;">
                            <span style="background: rgba(59, 130, 246, 0.1); color: #60A5FA; padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700;">
                                Reps: {weekly_reps_str}
                            </span>
                            <span style="background: rgba(16, 185, 129, 0.1); color: #34D399; padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700;">
                                Form: {weekly_form_str} pts
                            </span>
                        </div>
                        <p style="font-size: 0.9rem; color: #CBD5E1; line-height: 1.45; margin: 0;">
                            {progress_trends['weekly_summary']}
                        </p>
                    </div>
                    """).strip(),
                    unsafe_allow_html=True
                )
                
            with trend_col2:
                monthly_form = progress_trends["monthly_form_change"]
                monthly_form_str = f"+{monthly_form:.1f}" if monthly_form > 0 else f"{monthly_form:.1f}"
                monthly_reps = progress_trends["monthly_reps_change"]
                monthly_reps_str = f"+{monthly_reps}" if monthly_reps > 0 else f"{monthly_reps}"
                
                st.markdown(
                    clean_html(f"""
                    <div style="background: rgba(168, 85, 247, 0.04); border: 1px solid rgba(168, 85, 247, 0.15); border-radius: 12px; padding: 18px; height: 100%; backdrop-filter: blur(8px);">
                        <h5 style="color: #C084FC; margin-top: 0; margin-bottom: 12px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
                            📅 Monthly Progress Summary
                        </h5>
                        <div style="display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap;">
                            <span style="background: rgba(168, 85, 247, 0.1); color: #C084FC; padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700;">
                                Reps: {monthly_reps_str}
                            </span>
                            <span style="background: rgba(16, 185, 129, 0.1); color: #34D399; padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700;">
                                Form: {monthly_form_str} pts
                            </span>
                        </div>
                        <p style="font-size: 0.9rem; color: #CBD5E1; line-height: 1.45; margin: 0;">
                            {progress_trends['monthly_summary']}
                        </p>
                    </div>
                    """).strip(),
                    unsafe_allow_html=True
                )
            
            st.markdown("")
            
            # Exercise Analytics Details
            st.markdown("##### 🏋️ Exercise Analytics")
            ex_col1, ex_col2 = st.columns([1, 1])
            with ex_col1:
                st.markdown(
                    clean_html(f"""
                    <div style="background: rgba(30, 41, 59, 0.25); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 16px; height: 100%;">
                        <div style="font-size: 0.85rem; color: #94A3B8; font-weight: 600; text-transform: uppercase;">Most Performed Exercise</div>
                        <div style="font-size: 1.4rem; font-weight: 700; color: #3B82F6; margin-top: 4px;">{stats['most_performed']}</div>
                        
                        <div style="font-size: 0.85rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; margin-top: 16px;">Strongest Exercise (Avg Form)</div>
                        <div style="font-size: 1.4rem; font-weight: 700; color: #10B981; margin-top: 4px;">{stats['strongest_exercise']}</div>
                        
                        <div style="font-size: 0.85rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; margin-top: 16px;">Weakest Exercise (Avg Form)</div>
                        <div style="font-size: 1.4rem; font-weight: 700; color: #EF4444; margin-top: 4px;">{stats['weakest_exercise']}</div>
                    </div>
                    """).strip(),
                    unsafe_allow_html=True
                )
            
            with ex_col2:
                if history_rows:
                    df = pd.DataFrame(history_rows)
                    ex_counts = df.groupby("exercise_name")["reps"].agg(["count", "sum"]).reset_index()
                    ex_counts.columns = ["Exercise", "Sessions", "Total Reps"]
                    st.dataframe(ex_counts.set_index("Exercise"), use_container_width=True)
                else:
                    st.info("No exercise details available.")
                    
            st.markdown("")
            
            # Visual Analytics Charts
            if history_rows:
                st.markdown("##### 📈 Activity & Volume Trends")
                chart_tab1, chart_tab2, chart_tab3 = st.tabs(["Activity Trends", "Volume & Performance", "Weekly & Monthly Performance"])
                
                df = pd.DataFrame(history_rows)
                df["created_at"] = pd.to_datetime(df["created_at"])
                
                with chart_tab1:
                    df["DateOnly"] = df["created_at"].dt.date
                    activity_df = df.groupby("DateOnly").size().reset_index(name="Workouts")
                    activity_df["DateOnly"] = activity_df["DateOnly"].astype(str)
                    st.area_chart(activity_df.set_index("DateOnly"))
                    
                with chart_tab2:
                    df_sorted = df.sort_values("created_at")
                    df_sorted["Session"] = df_sorted["created_at"].dt.strftime("%b %d, %H:%M") + " (" + df_sorted["exercise_name"] + ")"
                    reps_score_df = df_sorted[["Session", "reps", "average_form_score"]].set_index("Session")
                    reps_score_df.columns = ["Reps Completed", "Average Form Score"]
                    st.line_chart(reps_score_df)
                    
                with chart_tab3:
                    df["Week"] = df["created_at"].dt.to_period("W").astype(str)
                    df["Month"] = df["created_at"].dt.to_period("M").astype(str)
                    
                    week_df = df.groupby("Week")["reps"].sum().reset_index()
                    month_df = df.groupby("Month")["reps"].sum().reset_index()
                    
                    w_col, m_col = st.columns(2)
                    with w_col:
                        st.markdown("**Weekly Volume (Reps)**")
                        st.bar_chart(week_df.set_index("Week"))
                    with m_col:
                        st.markdown("**Monthly Volume (Reps)**")
                        st.bar_chart(month_df.set_index("Month"))
            
            st.markdown("")
            
            # Achievements Grid
            st.markdown("##### 🏆 Unlocked Achievements")
            achievements = get_achievements(stats)
            
            ach_cols = st.columns(5)
            for idx, ach in enumerate(achievements):
                with ach_cols[idx % 5]:
                    if ach["unlocked"]:
                        bg = "rgba(16, 185, 129, 0.12)"
                        border = "1px solid rgba(16, 185, 129, 0.3)"
                        text_color = "#10B981"
                        badge_symbol = "🏆"
                    else:
                        bg = "rgba(100, 116, 139, 0.05)"
                        border = "1px solid rgba(100, 116, 139, 0.15)"
                        text_color = "#64748B"
                        badge_symbol = "🔒"
                        
                    st.markdown(
                        clean_html(f"""
                        <div style="
                            background: {bg};
                            border: {border};
                            border-radius: 12px;
                            padding: 12px;
                            text-align: center;
                            min-height: 150px;
                            display: flex;
                            flex-direction: column;
                            justify-content: space-between;
                            backdrop-filter: blur(8px);
                        ">
                            <div style="font-size: 1.8rem; margin-bottom: 6px;">{badge_symbol}</div>
                            <div style="font-size: 0.85rem; font-weight: 700; color: #FFF; line-height: 1.2;">{ach['name']}</div>
                            <div style="font-size: 0.7rem; color: #94A3B8; margin-top: 4px; line-height: 1.2; flex-grow: 1;">{ach['desc']}</div>
                            <div style="font-size: 0.75rem; font-weight: 700; color: {text_color}; margin-top: 8px; background: rgba(0,0,0,0.2); border-radius: 9999px; padding: 2px 4px;">{ach['progress']}</div>
                        </div>
                        """).strip(),
                        unsafe_allow_html=True
                    )
        else:
            st.info("Log in to see your Progress Dashboard.")



if __name__ == "__main__":
    main()
    