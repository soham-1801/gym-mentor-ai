import cv2
import mediapipe as mp
_mp_import_error = ""
try:
    import mediapipe.python.solutions as mp_solutions
except Exception as e1:
    _mp_import_error = f"mediapipe.python.solutions failed: {e1}"
    try:
        import mediapipe.solutions as mp_solutions
    except Exception as e2:
        _mp_import_error += f" | mediapipe.solutions failed: {e2}"
        mp_solutions = getattr(mp, "solutions", None)
        if mp_solutions is None:
            _mp_import_error += f" | getattr(mp, 'solutions') is None"

import numpy as np
import logging
from typing import Optional
from streamlit_webrtc import VideoProcessorBase
import av

from detectors.squat import SquatDetector
from detectors.pushups import PushUpDetector
from detectors.biceps_curl import BicepsCurlDetector
from detectors.shoulder_press import ShoulderPressDetector
from detectors.lunges import LungesDetector

# Map exercise names to their detector classes
EXERCISE_DETECTOR_MAP = {
    "Squats": SquatDetector,
    "Push-ups": PushUpDetector,
    "Biceps Curls (Dumbbell)": BicepsCurlDetector,
    "Shoulder Press": ShoulderPressDetector,
    "Lunges": LungesDetector,
}


class VideoProcessorClass(VideoProcessorBase):
    def __init__(self):
        # Initialize MediaPipe Pose
        if mp_solutions is None:
            raise RuntimeError(f"MediaPipe solutions could not be imported. Details: {_mp_import_error}. Please ensure Python 3.11/3.12 is selected in Streamlit Cloud settings and system GL libraries are present.")
        self.mp_pose = mp_solutions.pose
        self.pose = self.mp_pose.Pose(
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp_solutions.drawing_utils

        # State & Settings
        self.exercise_type = "Squats"
        self.target_sets = 0
        self.reps_per_set = 0

        # Active detector instance
        self._current_exercise_type = None
        self._detector = None
        self._init_detector("Squats")

        # Tracking metrics (pulled from detector each frame)
        self.reps = 0
        self.current_set_reps = 0
        self.sets_completed = 0
        self.stage = None

        # Joint Angles & Statuses (exercise-specific, defaults for UI safety)
        self.knee_angle = 0
        self.back_angle = 0
        self.depth_status = "Unknown"
        self.elbow_angle = 0
        self.body_alignment = "Unknown"
        self.hip_status = "Unknown"
        self.shoulder_status = "Unknown"
        self.swing_status = "Unknown"
        self.extension_status = "Unknown"
        self.back_arch_status = "Unknown"
        self.front_knee_angle = 0
        self.torso_angle = 0
        self.balance_status = "Unknown"
        self.form_feedback = None
        # ── Bilateral Symmetry Angles ───────────────────────────────────
        self.left_elbow_angle = 0
        self.right_elbow_angle = 0
        self.left_knee_angle = 0
        self.right_knee_angle = 0

        # Voice Coach Settings & Thread-safe Tracking Properties
        self.voice_pipeline = None
        self.voice_enabled = True
        self.voice_volume = 1.0
        self.voice_gender = "Female"
        self.voice_engine = "Web Speech API"
        self.voice_event_bus = None
        self.last_announced_rep = 0
        self.last_announced_form_feedback = None
        self.last_form_feedback_time = 0.0
        self.pending_browser_speech = None

        # Phase 1 — Injury Warning System
        self.consecutive_bad_reps = 0          # reps where form score < 50
        self.last_injury_warning_time = 0.0
        self.last_rep_form_score = 100

        # Phase 1 — Breathing Cues
        self.last_breathing_cue_set = -1       # which set index breathing was last cued
        self.frame_counter = 0
        self.last_results = None

    def _init_detector(self, exercise_type):
        """Instantiate the correct detector for the given exercise type."""
        detector_cls = EXERCISE_DETECTOR_MAP.get(exercise_type)
        if detector_cls:
            self._detector = detector_cls()
            self._current_exercise_type = exercise_type
        else:
            logging.warning(f"No detector found for exercise: {exercise_type}")
            self._detector = None
            self._current_exercise_type = exercise_type

    def _maybe_switch_detector(self):
        """Switch detector if the exercise type has changed."""
        if self.exercise_type != self._current_exercise_type:
            self._init_detector(self.exercise_type)
            # Reset set/rep tracking when exercise changes
            self.reps = 0
            self.current_set_reps = 0
            self.sets_completed = 0
            self.stage = None
            self.last_announced_rep = 0
            self.last_announced_form_feedback = None
            self.last_form_feedback_time = 0.0

    def increment_rep(self):
        self.reps += 1
        self.current_set_reps += 1

        logging.info(f"[VideoProcessor] Rep incremented. reps={self.reps}, current_set_reps={self.current_set_reps}")

        # ── Injury Warning: track consecutive bad-form reps ───────────────
        from services.coaching.form_analyzer import calculate_form_score
        import time as _time
        cur_metrics = {
            "knee_angle": self.knee_angle, "back_angle": self.back_angle,
            "depth_status": self.depth_status, "elbow_angle": self.elbow_angle,
            "body_alignment": self.body_alignment, "hip_status": self.hip_status,
            "shoulder_status": self.shoulder_status, "swing_status": self.swing_status,
            "extension_status": self.extension_status, "back_arch_status": self.back_arch_status,
            "front_knee_angle": self.front_knee_angle, "torso_angle": self.torso_angle,
            "balance_status": self.balance_status,
        }
        rep_score, _ = calculate_form_score(self.exercise_type, cur_metrics)
        self.last_rep_form_score = rep_score

        if rep_score < 50:
            self.consecutive_bad_reps += 1
        else:
            self.consecutive_bad_reps = 0

        # Trigger injury warning if 3+ consecutive bad reps and 10s cooldown passed
        if self.consecutive_bad_reps >= 3 and self.voice_event_bus and self.voice_enabled:
            now_t = _time.time()
            if now_t - self.last_injury_warning_time >= 10.0:
                logging.warning(f"[VideoProcessor] INJURY WARNING: {self.consecutive_bad_reps} consecutive bad reps (score={rep_score})")
                self.voice_event_bus.publish("injury_warning", {"consecutive_bad_reps": self.consecutive_bad_reps, "form_score": rep_score})
                self.last_injury_warning_time = now_t

        # Publish rep completed event to the VoiceEventBus
        if self.voice_event_bus and self.voice_enabled:
            logging.info(f"[VideoProcessor] Publishing rep_completed event to event bus: reps={self.reps}")
            self.voice_event_bus.publish("rep_completed", {"reps": self.reps})
        else:
            logging.warning(f"[VideoProcessor] Event bus or voice enabled check failed: bus={self.voice_event_bus is not None}, enabled={self.voice_enabled}")

        if self.reps_per_set > 0 and self.current_set_reps >= self.reps_per_set:
            self.sets_completed += 1
            self.current_set_reps = 0
            # ── Breathing Cue: publish once per new set ───────────────────
            if self.voice_event_bus and self.voice_enabled:
                self.voice_event_bus.publish("breathing_cue", {"exercise": self.exercise_type, "set_num": self.sets_completed})
                self.last_breathing_cue_set = self.sets_completed


    def _sync_from_detector(self, result: dict):
        """Pull rep count and metrics from the detector result dict into self."""
        # Sync rep counts — increment_rep handles set logic, so just mirror reps
        new_reps = result.get("reps", 0)
        if new_reps > self.reps:
            # Detector registered new reps since last frame
            diff = new_reps - self.reps
            for _ in range(diff):
                self.increment_rep()

        # Squats
        self.knee_angle = result.get("knee_angle", self.knee_angle)
        self.back_angle = result.get("back_angle", self.back_angle)
        self.depth_status = result.get("depth_status", self.depth_status)

        # Push-ups / Biceps / Shoulder Press
        self.elbow_angle = result.get("elbow_angle", self.elbow_angle)
        self.body_alignment = result.get("body_alignment", self.body_alignment)
        self.hip_status = result.get("hip_status", self.hip_status)
        self.shoulder_status = result.get("shoulder_status", self.shoulder_status)
        self.swing_status = result.get("swing_status", self.swing_status)
        self.extension_status = result.get("extension_status", self.extension_status)
        self.back_arch_status = result.get("back_arch_status", self.back_arch_status)

        # Lunges
        self.front_knee_angle = result.get("front_knee_angle", self.front_knee_angle)
        self.torso_angle = result.get("torso_angle", self.torso_angle)
        self.balance_status = result.get("balance_status", self.balance_status)

        # Bilateral symmetry
        self.left_elbow_angle  = result.get("left_elbow_angle",  self.left_elbow_angle)
        self.right_elbow_angle = result.get("right_elbow_angle", self.right_elbow_angle)
        self.left_knee_angle   = result.get("left_knee_angle",   self.left_knee_angle)
        self.right_knee_angle  = result.get("right_knee_angle",  self.right_knee_angle)

    def _get_form_feedback(self, result: dict) -> Optional[str]:
        """Derive human-readable form feedback from detector output."""
        exercise = self.exercise_type

        if exercise == "Squats":
            depth = result.get("depth_status", "")
            back = result.get("back_angle", 0)
            if isinstance(back, (int, float)) and back > 35:
                return "Don't lean forward too much. Keep chest up."
            if depth == "Shallow Squat":
                return "Squat deeper. Lower your hips."

        elif exercise == "Push-ups":
            alignment = result.get("body_alignment", "")
            if alignment == "Sagging Hip":
                return "Hips are sagging. Tighten your core."
            if alignment == "High Hip":
                return "Lower your hips to keep body straight."

        elif exercise == "Biceps Curls (Dumbbell)":
            if result.get("shoulder_status") == "Unstable Elbow":
                return "Keep elbows locked by your side."

        elif exercise == "Shoulder Press":
            if result.get("extension_status") == "Incomplete Press":
                return "Extend your arms fully overhead."

        elif exercise == "Lunges":
            if result.get("balance_status") == "Knee Past Toes":
                return "Don't let your knee push past your toes."

        return None

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")

        # Mirror image horizontally
        img = cv2.flip(img, 1)
        h, w, _ = img.shape

        # Switch detector if exercise changed
        self._maybe_switch_detector()

        self.frame_counter += 1
        import platform, os
        is_weak_cloud = ("/mount/src" in __file__ or "/home/adminuser" in __file__) and not os.environ.get("SPACE_ID")
        if is_weak_cloud:
            scale_w = 240
            should_process_ai = (self.frame_counter % 2 != 0 or self.last_results is None)
        else:
            scale_w = 480
            should_process_ai = True

        if should_process_ai:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            if w > scale_w:
                scale_h = int(h * (scale_w / w))
                img_small = cv2.resize(img_rgb, (scale_w, scale_h), interpolation=cv2.INTER_LINEAR)
                results = self.pose.process(img_small)
            else:
                results = self.pose.process(img_rgb)
            self.last_results = results
        else:
            results = self.last_results

        if results.pose_landmarks:
            # Draw skeleton on video
            self.mp_drawing.draw_landmarks(
                img, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS,
                self.mp_drawing.DrawingSpec(color=(80, 220, 100), thickness=2, circle_radius=2),
                self.mp_drawing.DrawingSpec(color=(80, 100, 220), thickness=2, circle_radius=2)
            )

            landmarks = results.pose_landmarks.landmark

            try:
                if self._detector and should_process_ai:
                    result = self._detector.process(landmarks)
                    self._sync_from_detector(result)
                    self.form_feedback = self._get_form_feedback(result)

                    # Real-time posture feedback triggering inside processor frame loop
                    if self.form_feedback:
                        import time
                        if self.voice_enabled and self.voice_event_bus:
                            now = time.time()
                            if now - self.last_form_feedback_time > 2.5:
                                logging.info(f"[VideoProcessor] Publishing posture_warning event: feedback='{self.form_feedback}'")
                                self.voice_event_bus.publish("posture_warning", {"feedback": self.form_feedback})
                                self.last_form_feedback_time = now

                    # Render exercise-specific angle overlays
                    left_vis = sum(landmarks[idx].visibility for idx in [11, 13, 15, 23, 25, 27]) / 6.0
                    right_vis = sum(landmarks[idx].visibility for idx in [12, 14, 16, 24, 26, 28]) / 6.0
                    side = "left" if left_vis > right_vis else "right"

                    if side == "left":
                        elbow = [landmarks[13].x * w, landmarks[13].y * h]
                        knee  = [landmarks[25].x * w, landmarks[25].y * h]
                    else:
                        elbow = [landmarks[14].x * w, landmarks[14].y * h]
                        knee  = [landmarks[26].x * w, landmarks[26].y * h]

                    if self.exercise_type == "Squats":
                        cv2.putText(img, f"Knee: {self.knee_angle} deg", (int(knee[0]) + 10, int(knee[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        cv2.putText(img, f"Back: {self.back_angle} deg", (int(knee[0]) + 10, int(knee[1]) + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    elif self.exercise_type in ("Push-ups", "Biceps Curls (Dumbbell)", "Shoulder Press"):
                        cv2.putText(img, f"Elbow: {self.elbow_angle} deg", (int(elbow[0]) + 10, int(elbow[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    elif self.exercise_type == "Lunges":
                        cv2.putText(img, f"Knee: {self.front_knee_angle} deg", (int(knee[0]) + 10, int(knee[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            except Exception as ex:
                logging.debug(f"Pose tracking calculation skip: {ex}")

        # Draw on-screen HUD
        overlay = img.copy()
        cv2.rectangle(overlay, (5, 5), (320, 110), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, img, 0.5, 0, img)

        cv2.putText(img, f"Exercise: {self.exercise_type}", (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(img, f"Current Set Reps: {self.current_set_reps} / {self.reps_per_set}", (12, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(img, f"Sets Done: {self.sets_completed} / {self.target_sets}", (12, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(img, f"Total Reps: {self.reps}", (12, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        if self.form_feedback:
            cv2.rectangle(img, (0, h - 45), (w, h), (0, 0, 180), -1)
            cv2.putText(img, f"Form Tip: {self.form_feedback}", (20, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return av.VideoFrame.from_ndarray(img, format="bgr24")
