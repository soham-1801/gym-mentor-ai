import time
import streamlit as st
import queue
import threading
import os
import logging

try:
    import pyttsx3
    import pythoncom
    _PYTTSX3_AVAILABLE = True
except ImportError:
    _PYTTSX3_AVAILABLE = False
    pythoncom = None

class BackgroundVoiceCoach:
    def __init__(self):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def speak(self, text, volume=1.0, gender="female"):
        self.queue.put((text, volume, gender))

    def _worker(self):
        if os.name == 'nt' and _PYTTSX3_AVAILABLE and pythoncom:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

        if not _PYTTSX3_AVAILABLE:
            logging.warning("[BackgroundVoiceCoach] pyttsx3 not available, worker will not run.")
            return

        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        
        while True:
            try:
                item = self.queue.get()
                if item is None:
                    break
                text, volume, gender = item
                
                # Apply settings
                engine.setProperty("volume", volume)
                voices = engine.getProperty("voices")
                for voice in voices:
                    v_name = voice.name.lower()
                    if gender.lower() == "female" and any(x in v_name for x in ["female", "zira", "hazel", "heera", "samantha"]):
                        engine.setProperty("voice", voice.id)
                        break
                    elif gender.lower() == "male" and any(x in v_name for x in ["male", "david", "ravi"]):
                        engine.setProperty("voice", voice.id)
                        break
                
                engine.say(text)
                engine.runAndWait()
                self.queue.task_done()
            except Exception as e:
                print(f"[BackgroundVoiceCoach] Error in worker thread: {e}")
                
        if os.name == 'nt' and _PYTTSX3_AVAILABLE and pythoncom:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


class VoicePipeline:
    def __init__(self, llm, tts):
        self.llm = llm
        self.tts = tts
        self.last_spoken_at = 0.0
        self.last_spoken_text = ""
        self.last_spoken_duration = 0.0
        self.cooldown = 2.5  # Cooldown between voice cues (seconds)
        self.last_announced_rep = 0
        self.last_warning_times = {}  # Tracks last spoken time for each posture warning message
        self.speak_called_count = 0
        logging.info("[VoicePipeline] Initialized VoicePipeline.")
        
        # Initialize background voice coach if not already in session state
        if "bg_voice_coach" not in st.session_state:
            st.session_state.bg_voice_coach = BackgroundVoiceCoach()
        self.bg_voice_coach = st.session_state.bg_voice_coach

    def speak(self, text, priority="high"):
        """Unified speak method that enforces settings, cooldown, priority, and repetition check."""
        if not text:
            return None

        self.speak_called_count += 1
        logging.debug(f"[VoicePipeline] speak() called: text='{text}', priority='{priority}' (Total speak calls: {self.speak_called_count})")

        # Check if voice is enabled in session state (default to True)
        enabled = st.session_state.get("voice_enabled", True)
        if not enabled:
            logging.info("[VoicePipeline] Voice disabled in session state. Skipping speak.")
            return None

        now = time.time()
        is_currently_speaking = (now - self.last_spoken_at < self.last_spoken_duration)

        # Overlap Protection: Normal priority cues cannot cut off active speech.
        if is_currently_speaking and priority == "normal":
            logging.debug(f"[VoicePipeline] Overlap protection active. Skipping normal priority text: '{text}'")
            return None

        # Cooldown & Repetition filters for Normal Priority cues
        if priority == "normal":
            # Cooldown check
            if now - self.last_spoken_at < self.cooldown:
                logging.debug(f"[VoicePipeline] General posture cooldown active. Skipping text: '{text}'")
                return None
            # Repetition check (avoid repeating the exact same message within 5 seconds)
            last_warn_time = self.last_warning_times.get(text, 0.0)
            if now - last_warn_time < 5.0:
                logging.debug(f"[VoicePipeline] Duplicate posture warning cooldown active (5s limit). Skipping text: '{text}'")
                return None

        self.last_spoken_at = now
        self.last_spoken_text = text
        if priority == "normal":
            self.last_warning_times[text] = now

        # Estimate speech duration based on word count (~2.5 words/sec + 1.5s buffer)
        words = len(text.split())
        duration = max((words / 2.5) + 1.5, 3.0)
        self.last_spoken_duration = duration

        volume = st.session_state.get("voice_volume", 1.0)
        gender = st.session_state.get("voice_gender", "Female")
        engine = st.session_state.get("voice_engine", "Web Speech API")

        logging.debug(f"[VoicePipeline] Proceeding to speak: text='{text}', engine='{engine}', volume={volume}, gender='{gender}', priority='{priority}'")

        if engine == "Web Speech API":
            # Append to browser speech queue
            if "browser_speech_queue" not in st.session_state:
                st.session_state.browser_speech_queue = []
            
            speech_item = {
                "id": now,
                "text": text,
                "volume": volume,
                "gender": gender.lower(),
                "priority": priority,
                "timestamp": time.strftime("%H:%M:%S")
            }
            st.session_state.browser_speech_queue.append(speech_item)
            logging.debug(f"[VoicePipeline] Appended speech item to browser_speech_queue (New queue size: {len(st.session_state.browser_speech_queue)})")
            
            st.session_state.browser_speech = speech_item
            st.session_state.coach_feedback = text
            return None
        else:
            # Generate offline / online audio bytes
            audio_bytes = self.tts.text_to_speech(text, gender=gender, volume=volume)
            
            # Log diagnostics
            bytes_len = len(audio_bytes) if audio_bytes else 0
            logging.debug(f"[VoicePipeline] Audio Generated: {audio_bytes is not None}, Size: {bytes_len} bytes")
            
            st.session_state.coach_feedback = text
            if audio_bytes:
                return audio_bytes, text, duration
            return None

    def speak_via_bg_coach(self, text, volume, gender):
        """Helper to speak directly via the background worker, bypassing st.session_state (safe for bg threads)."""
        self.bg_voice_coach.speak(text, volume=volume, gender=gender)

    def process_event(self, event, exercise, metrics):
        """Process workout coaching events and generate appropriate voice prompts."""
        text = ""
        priority = "high"
        
        if event == "workout_started":
            # Exercise Guidance Explanation
            explanations = {
                "Squats": "Let's start squats. Keep your back straight and lower slowly.",
                "Push-ups": "Let's start push-ups. Keep your body straight and lower your chest close to the floor.",
                "Biceps Curls (Dumbbell)": "Let's start biceps curls. Keep your elbows tucked to your sides and curl the weight up.",
                "Shoulder Press": "Let's start shoulder press. Keep your core tight and press the weight straight overhead.",
                "Lunges": "Let's start lunges. Step forward, keep your torso upright, and lower your hips until both knees are bent at about 90 degrees."
            }
            text = explanations.get(exercise, f"Let's start {exercise}.")
            priority = "high"
            
        elif event == "workout_completed":
            text = "Congratulations! Workout completed."
            priority = "high"
            
        elif event == "rep_completed":
            reps = metrics.get("reps", 0)
            if reps == 1:
                text = "1 rep completed"
            else:
                text = f"{reps} reps completed"
            priority = "high"

        elif event == "rep_milestone":
            reps = metrics.get("reps", 0)
            milestones = {
                5: "Great job! 5 reps completed.",
                10: "Excellent work! 10 reps completed.",
                15: "Keep going! 15 reps completed.",
                20: "Workout completed successfully."
            }
            text = milestones.get(reps, f"{reps} reps completed.")
            priority = "high"
            
        elif event == "form_feedback":
            # Map dynamic feedback suggestion to one of the 4 exact requirements
            suggestion = metrics.get("feedback_suggestion", "")
            text = self._map_incorrect_form_feedback(suggestion)
            priority = "normal"
            
        elif event == "set_completed":
            text = "Set completed! Excellent job. Take a short rest."
            priority = "high"

        elif event == "app_start":
            text = "Hello! Welcome to AI Gym Trainer."
            priority = "high"

        else:
            return None

        # Call unified speak method
        return self.speak(text, priority=priority)

    def consume_event(self, event_type, payload):
        """Consume event published from the video processor background thread or main flow."""
        logging.info(f"[VoicePipeline] consume_event() received: event_type='{event_type}', payload={payload}")
        
        # Update last event info for debugging/HUD
        st.session_state.last_event_info = f"{event_type} (payload={payload}) at {time.strftime('%H:%M:%S')}"
        
        text = ""
        priority = "high"
        
        if event_type == "rep_completed":
            reps = payload.get("reps", 0)
            if reps <= self.last_announced_rep:
                logging.info(f"[VoicePipeline] Duplicate rep completion skipped: reps={reps}, last_announced={self.last_announced_rep}")
                return None
            self.last_announced_rep = reps
            # Check milestone or standard rep counting
            if reps == 5:
                text = "Great job! 5 reps completed."
            elif reps == 10:
                text = "Excellent work! 10 reps completed."
            elif reps == 15:
                text = "Keep going! 15 reps completed."
            elif reps == 20:
                text = "Workout completed successfully."
            else:
                text = "1 rep completed" if reps == 1 else f"{reps} reps completed"
            priority = "high"
            
        elif event_type == "posture_warning":
            suggestion = payload.get("feedback", "")
            text = self._map_incorrect_form_feedback(suggestion)
            priority = "normal"
            
        elif event_type == "workout_completed":
            text = "Congratulations! Workout completed."
            priority = "high"

        elif event_type == "workout_started":
            self.last_announced_rep = 0
            exercise = payload.get("exercise", "Squats")
            # Delegate to process_event to keep existing startup guidance flow
            return self.process_event("workout_started", exercise, {})

        elif event_type == "app_start":
            text = "Hello! Welcome to AI Gym Trainer."
            priority = "high"
            
        elif event_type == "injury_warning":
            form_score = payload.get("form_score", 0)
            text = f"Warning! Your form is dangerous with a score of {form_score}. Please stop and correct your posture before continuing."
            priority = "high"

        elif event_type == "breathing_cue":
            exercise = payload.get("exercise", "")
            breathing_map = {
                "Squats":                    "Breathe in going down, breathe out coming up.",
                "Push-ups":                  "Exhale as you push up. Inhale as you lower down.",
                "Biceps Curls (Dumbbell)":   "Exhale as you curl up. Inhale as you lower the weight.",
                "Shoulder Press":            "Exhale as you press overhead. Inhale as you lower.",
                "Lunges":                    "Inhale as you step forward and lower. Exhale as you push back up.",
            }
            text = breathing_map.get(exercise, "Remember to breathe steadily throughout the exercise.")
            priority = "normal"

        elif event_type == "rest_timer_start":
            rest_secs = payload.get("rest_seconds", 60)
            set_num = payload.get("set_num", 1)
            text = f"Set {set_num} completed! Great work. Rest for {rest_secs} seconds."
            priority = "high"

        else:
            logging.warning(f"[VoicePipeline] Unhandled event_type: '{event_type}'")
            return None

        # Call speak
        return self.speak(text, priority=priority)

    def _map_incorrect_form_feedback(self, suggestion):
        """Map raw visual feedback suggestions to the 4 required incorrect form phrases."""
        if not suggestion:
            return "Correct your posture."
            
        fs = suggestion.lower()
        if "back" in fs or "lean" in fs or "chest" in fs:
            return "Keep your back straight."
        elif "lower" in fs or "deep" in fs or "depth" in fs:
            return "Lower a little more."
        elif "elbow" in fs or "arm" in fs or "extend" in fs:
            # Biceps Curl "Keep elbows locked by your side" -> Correct your posture
            # Shoulder Press "Extend your arms fully overhead" -> Raise your elbows
            if "lock" in fs or "side" in fs or "curl" in fs:
                return "Correct your posture."
            else:
                return "Raise your elbows."
        elif "posture" in fs or "hip" in fs or "alignment" in fs or "knee" in fs or "balance" in fs:
            return "Correct your posture."
            
        return "Correct your posture."

    

def autoplay_audio(audio_bytes):
    """
    Play audio using Streamlit's native st.audio component.
    To prevent the audio from restarting or stuttering during periodic reruns
    of the page, we use a stable key hashed from the audio content.
    We also detect the MIME type dynamically since pyttsx3 output on Windows
    is actually WAV despite having a temporary .mp3 extension.
    """
    if not audio_bytes:
        return

    if st.session_state.get("developer_mode", False):
        st.sidebar.write(f"📢 Audio Bytes Size: {len(audio_bytes)}")

    import hashlib

    # Generate a unique key based on the audio bytes hash.
    # This keeps the key identical during page reruns of the same sound track.
    audio_hash = hashlib.md5(audio_bytes).hexdigest()

    # Detect format dynamically (WAV starts with RIFF, gTTS generates MP3)
    if audio_bytes.startswith(b'RIFF'):
        mime_type = "audio/wav"
    else:
        mime_type = "audio/mp3"

    # Play natively using Streamlit.
    st.audio(
        audio_bytes,
        format=mime_type,
        autoplay=True
    )