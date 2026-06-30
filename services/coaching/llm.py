import logging

class LLMCoach:
    def __init__(self, groq_client):
        self.client = groq_client
        self.model = "llama-3.3-70b-versatile"
        
    def generate_feedback(self, event, exercise, metrics):
        # Fallback messages in case Groq is unavailable or key is missing
        fallback_messages = {
            "workout_started": f"Chalo shuru karte hain! Let's start with {exercise}. Keep your form tight!",
            "workout_completed": f"Shabash! You've completed your {exercise} session. Great effort today!",
            "set_completed": f"Set completed! Bahut badhiya. Catch your breath for a bit.",
            "form_feedback": "Check your posture. Keep your core engaged and movements controlled!"
        }
        
        # Parse metrics if any
        metrics_str = ", ".join([f"{k}: {v}" for k, v in metrics.items()]) if metrics else "Good form"
        
        # Check if the client is valid or if api_key is empty
        if not self.client or not getattr(self.client, "api_key", None):
            # Safe fallback
            if event == "form_feedback":
                return metrics.get("feedback_suggestion", fallback_messages["form_feedback"])
            return fallback_messages.get(event, "Keep going! Great work.")
            
        system_prompt = (
            "You are a professional, highly energetic, and encouraging AI Gym Coach named 'Apna AI Coach'. "
            "Your job is to provide short, high-energy coaching cues to the user during their workout. "
            "Guidelines:\n"
            "1. Keep responses extremely short (1-2 sentences maximum, under 25 words) so it can be converted to speech quickly.\n"
            "2. Use a natural, motivating mix of Hindi and English (Hinglish/Indian English) like a friendly trainer at the gym.\n"
            "3. Be specific to the exercise and current event/metrics."
        )
        
        user_prompts = {
            "workout_started": f"The user is starting a session of {exercise}. Give them a brief, motivating start message.",
            "workout_completed": f"The user completed their entire workout of {exercise}. Congratulate them on finishing!",
            "set_completed": f"The user finished a set of {exercise}. Metrics: {metrics_str}. Congratulate them and tell them to rest briefly.",
            "form_feedback": f"The user is doing {exercise} but their form needs correction. Issue: {metrics_str}. Give a quick form tip."
        }
        
        prompt = user_prompts.get(event, f"The user is working out on {exercise} with metrics {metrics_str}. Keep motivating them!")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=60,
                temperature=0.7
            )
            feedback = response.choices[0].message.content.strip()
            return feedback
        except Exception as e:
            logging.error(f"Error calling Groq API: {e}")
            # Try a smaller model before falling back to static
            try:
                response = self.client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=60,
                    temperature=0.7
                )
                return response.choices[0].message.content.strip()
            except Exception:
                if event == "form_feedback":
                    return metrics.get("feedback_suggestion", fallback_messages["form_feedback"])
                return fallback_messages.get(event, "Looking good! Keep pushing.")
