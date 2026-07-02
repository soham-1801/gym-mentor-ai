import io
import logging
from gtts import gTTS

try:
    import pyttsx3 as _pyttsx3_module
    _PYTTSX3_AVAILABLE = True
except ImportError:
    _pyttsx3_module = None
    _PYTTSX3_AVAILABLE = False

try:
    import pythoncom as _pythoncom_module
    _PYTHONCOM_AVAILABLE = True
except ImportError:
    _pythoncom_module = None
    _PYTHONCOM_AVAILABLE = False

class TextToSpeech:
    def __init__(self, lang="en"):
        self.lang = lang

    def text_to_speech(self, text, gender="Female", volume=1.0):
        if not text:
            return None
        # Try gTTS (online) first
        try:
            logging.info(f"[TextToSpeech] Generating speech via gTTS for text: '{text}'")
            tts = gTTS(text=text, lang=self.lang, slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            data = fp.read()
            if data:
                logging.info(f"[TextToSpeech] gTTS succeeded. Generated {len(data)} bytes.")
                return data
        except Exception as e:
            logging.warning(f"[TextToSpeech] gTTS failed, trying offline fallback: {e}")

        # Fallback: pyttsx3 (offline TTS) → write to a temp file → read bytes
        if not _PYTTSX3_AVAILABLE:
            logging.warning("[TextToSpeech] pyttsx3 not available for offline fallback.")
            return None

        try:
            import os
            # On Windows, pyttsx3/SAPI5 requires COM initialization on the current thread
            if os.name == 'nt' and _PYTHONCOM_AVAILABLE:
                try:
                    _pythoncom_module.CoInitialize()
                except Exception as ce:
                    logging.warning(f"[TextToSpeech] Could not initialize COM: {ce}")

            import tempfile

            logging.info(f"[TextToSpeech] Generating offline speech via pyttsx3 for text: '{text}'")
            engine = _pyttsx3_module.init()
            engine.setProperty("rate", 165)
            engine.setProperty("volume", volume)

            # Select voice by gender
            voices = engine.getProperty("voices")
            for voice in voices:
                v_name = voice.name.lower()
                if gender.lower() == "female" and any(x in v_name for x in ["female", "zira", "hazel", "heera", "samantha"]):
                    engine.setProperty("voice", voice.id)
                    break
                elif gender.lower() == "male" and any(x in v_name for x in ["male", "david", "ravi"]):
                    engine.setProperty("voice", voice.id)
                    break

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            logging.info(f"[TextToSpeech] Saving offline speech to temp file: {tmp_path}")
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()

            # Diagnostic logs
            file_exists = os.path.exists(tmp_path)
            file_size = os.path.getsize(tmp_path) if file_exists else 0
            logging.info(f"[TextToSpeech] pyttsx3 temp file status: exists={file_exists}, size={file_size} bytes")

            data = None
            if file_exists:
                with open(tmp_path, "rb") as f:
                    data = f.read()
                os.remove(tmp_path)
                logging.info(f"[TextToSpeech] Successfully read pyttsx3 data from temp file. Data size={len(data) if data else 0} bytes")

            # On Windows, clean up COM to prevent leaks
            if os.name == 'nt' and _PYTHONCOM_AVAILABLE:
                try:
                    _pythoncom_module.CoUninitialize()
                except Exception:
                    pass

            if data:
                return data
        except Exception as e:
            logging.error(f"[TextToSpeech] pyttsx3 fallback also failed: {e}", exc_info=True)

        return None
