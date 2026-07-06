import logging
import pandas as pd

# Tailored corrective recommendations for components
CORRECTIVE_RECOMMENDATIONS = {
    # Squats
    "Squat Depth": "Focus on going deeper. Ensure thighs are parallel to the ground at the bottom of the squat.",
    "Torso Alignment": "Focus on keeping your chest upright during squats. Avoid leaning forward excessively.",
    # Push-ups
    "Push-up Depth": "Focus on lowering your body more. Try to get your chest closer to the floor.",
    "Body Alignment": "Keep your body in a straight line from head to heels. Avoid curving your spine or saggy core.",
    "Hip Position": "Focus on keeping your hips level. Avoid sagging or piking them up.",
    # Biceps Curls
    "Shoulder Stability": "Keep your elbows locked at your sides. Avoid drifting your shoulders forward.",
    "Torso Stability": "Avoid using torso momentum or swinging to lift the weight. Stand tall.",
    "Range of Motion": "Focus on full range of motion. Squeeze at the top and extend completely at the bottom.",
    # Shoulder Press
    "Back Posture": "Maintain a neutral spine. Avoid excessive arching of the lower back.",
    "Arm Extension": "Focus on full arm extension. Push the weights straight up overhead.",
    # Lunges
    "Balance & Stability": "Focus on your balance and stability. Make sure your knee does not wobble or push past your toes.",
    "Torso Posture": "Keep your torso upright and back straight throughout the movement.",
    "Lunge Depth": "Try to lower your hips further until your back knee is just above the floor.",
    # Fallback
    "General Posture": "Focus on steady movements and control your posture throughout."
}

def get_recommendation_by_weakest_area(weakest_area: str) -> str:
    return CORRECTIVE_RECOMMENDATIONS.get(weakest_area, "Keep focusing on maintaining excellent posture throughout your reps.")

def generate_personalized_feedback(exercise_type, current_session_metrics, history_rows, user_streaks=None, llm_coach=None):
    """
    Generate post-workout personalized feedback, calculating rating, strongest/weakest areas,
    improvement percentage, and recommendations.
    
    current_session_metrics: dict with:
        - average_form_score (float)
        - best_form_score (float)
        - total_reps (int)
        - total_sets (int)
        - component_sums (dict)
        - component_counts (dict)
    
    history_rows: list of dicts of past exercise rows
    user_streaks: dict of user streak metrics (current_streak, longest_streak, etc.)
    llm_coach: LLMCoach instance or None
    
    Returns: dict with:
        - rating (float): 1.0 to 10.0
        - strongest_area (str)
        - weakest_area (str)
        - improvement_percentage (float)
        - feedback_summary (str)
        - recommendation (str)
        - voice_cue (str)
    """
    avg_score = current_session_metrics.get("average_form_score", 0.0)
    best_score = current_session_metrics.get("best_form_score", 0.0)
    total_reps = current_session_metrics.get("total_reps", 0)
    total_sets = current_session_metrics.get("total_sets", 0)
    
    # 1. Performance Rating (1.0 to 10.0)
    rating = max(1.0, min(10.0, avg_score / 10.0))
    rating = round(rating, 1)
    
    # 2. Strongest and Weakest posture components from session tracking
    comp_sums = current_session_metrics.get("component_sums", {})
    comp_counts = current_session_metrics.get("component_counts", {})
    
    comp_averages = {}
    for key in comp_sums:
        if comp_counts.get(key, 0) > 0:
            comp_averages[key] = comp_sums[key] / comp_counts[key]
            
    strongest_area = "General Posture"
    weakest_area = "General Posture"
    
    if comp_averages:
        sorted_comps = sorted(comp_averages.items(), key=lambda x: x[1])
        weakest_area = sorted_comps[0][0]
        strongest_area = sorted_comps[-1][0]
        
    # 3. Improvement Percentage compared to last session of same exercise
    improvement_percentage = 0.0
    previous_avg_score = 0.0
    previous_reps = 0
    
    if history_rows:
        df_hist = pd.DataFrame(history_rows)
        if not df_hist.empty and "exercise_name" in df_hist.columns:
            df_same = df_hist[df_hist["exercise_name"] == exercise_type]
            if not df_same.empty:
                # history is sorted DESC by created_at. Take the first row.
                last_session_row = df_same.iloc[0]
                previous_avg_score = last_session_row.get("average_form_score", 0.0)
                previous_reps = last_session_row.get("reps", 0)
                
                # Check for nan
                if pd.isna(previous_avg_score):
                    previous_avg_score = 0.0
                if pd.isna(previous_reps):
                    previous_reps = 0
                    
                if previous_avg_score > 0:
                    diff = avg_score - previous_avg_score
                    improvement_percentage = round((diff / previous_avg_score) * 100.0, 1)

    # 4. Generate Recommendation
    recommendation = get_recommendation_by_weakest_area(weakest_area)
    
    # 5. Generate Feedback Summary
    summary_parts = []
    
    # Good Progress / Performance Insights
    if improvement_percentage > 0:
        summary_parts.append(f"Your {exercise_type.lower()} form improved by {improvement_percentage:.1f}% compared to your last session.")
    elif improvement_percentage < 0:
        summary_parts.append(f"Your form score dropped by {abs(improvement_percentage):.1f}% compared to your last session. Focus on maintaining quality.")
    else:
        summary_parts.append(f"You maintained a steady form score of {avg_score:.1f} on {exercise_type}.")
        
    if best_score > avg_score and total_sets > 0:
        summary_parts.append(f"Your peak set reached a form score of {best_score:.1f} across {total_sets} sets!")
        
    if previous_reps > 0 and total_reps > previous_reps:
        rep_pct = int(((total_reps - previous_reps) / previous_reps) * 100)
        summary_parts.append(f"You completed {rep_pct}% more reps than your previous session.")
        
    # Weak areas
    if weakest_area in CORRECTIVE_RECOMMENDATIONS:
        if "Depth" in weakest_area:
            summary_parts.append(f"Your depth needs some focus during {exercise_type.lower()}.")
        elif "Alignment" in weakest_area or "Posture" in weakest_area:
            summary_parts.append("Focus on maintaining a straighter back and proper alignment.")
        elif "Balance" in weakest_area:
            summary_parts.append("Your balance needs improvement during execution.")
        elif "Stability" in weakest_area:
            summary_parts.append("Try to stabilize your elbow/shoulder joints during curls.")
            
    # Consistency
    if user_streaks:
        curr_streak = user_streaks.get("current_streak", 0)
        if curr_streak >= 3:
            summary_parts.append(f"You completed workouts on {curr_streak} consecutive days!")
            
    feedback_summary = " ".join(summary_parts)
    
    # 6. Voice Coach integration response
    voice_parts = []
    if rating >= 9.0:
        voice_parts.append("Outstanding performance today! Your form was absolutely excellent.")
    elif rating >= 7.5:
        voice_parts.append("Great effort today. Good form overall.")
    elif rating >= 6.0:
        voice_parts.append("Workout complete. Your form was decent, but let's really focus on technique next time.")
    else:
        voice_parts.append("Workout finished. Your form needs serious improvement. Please lower the intensity and prioritize your posture to avoid injuries.")

        
    if improvement_percentage > 0:
        voice_parts.append("Your form score improved compared to your last session.")
    elif user_streaks and user_streaks.get("current_streak", 0) >= 3:
        voice_parts.append("Great consistency. Keep maintaining your workout streak.")
    else:
        voice_parts.append(f"Keep focusing on your {weakest_area.lower()} next time.")
        
    voice_cue = " ".join(voice_parts)
    
    # 7. Optional LLM Enhancement
    if llm_coach and getattr(llm_coach, "client", None) and getattr(llm_coach.client, "api_key", None):
        try:
            system_prompt = (
                "You are Apna AI Coach, a supportive, energetic personal trainer. "
                "Write a highly personalized, motivating workout completion summary in Hinglish/English (max 2-3 sentences). "
                "Include the metrics, mention progress if any, and suggest correcting the weakest area. Keep it positive!"
            )
            prompt = (
                f"Exercise: {exercise_type}\n"
                f"Form Score: {avg_score:.1f}/100\n"
                f"Reps completed: {total_reps}\n"
                f"Improvement: {improvement_percentage:.1f}%\n"
                f"Strongest area: {strongest_area}\n"
                f"Weakest area: {weakest_area}\n"
                f"Current Streak: {user_streaks.get('current_streak', 0) if user_streaks else 0} days\n"
            )
            response = llm_coach.client.chat.completions.create(
                model=llm_coach.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )
            llm_text = response.choices[0].message.content.strip()
            if llm_text:
                feedback_summary = llm_text
                recommendation = f"Focus on {weakest_area.lower()}: {CORRECTIVE_RECOMMENDATIONS.get(weakest_area, '')}"
        except Exception as e:
            logging.error(f"Error enhancing post-workout feedback via LLM: {e}")
            
    return {
        "rating": rating,
        "strongest_area": strongest_area,
        "weakest_area": weakest_area,
        "improvement_percentage": improvement_percentage,
        "feedback_summary": feedback_summary,
        "recommendation": recommendation,
        "voice_cue": voice_cue
    }


def finalize_workout_feedback():
    import streamlit as st
    from services.persistence.exercise_repository import get_users_exercises
    
    history_rows = get_users_exercises(st.session_state.user_id)
    
    current_session_metrics = {
        "average_form_score": st.session_state.get("average_form_score", 0.0),
        "best_form_score": st.session_state.get("best_form_score", 0.0),
        "total_reps": st.session_state.get("reps", 0),
        "total_sets": st.session_state.get("sets_completed", 0),
        "component_sums": st.session_state.get("component_sums", {}),
        "component_counts": st.session_state.get("component_counts", {})
    }
    
    from services.persistence.exercise_repository import get_or_create_user
    user_profile = get_or_create_user(st.session_state.username)
    user_streaks = {
        "current_streak": user_profile.get("current_streak", 0) if user_profile else 0,
        "longest_streak": user_profile.get("longest_streak", 0) if user_profile else 0
    }
    
    llm_coach = None
    if st.session_state.get("voice_pipeline") and hasattr(st.session_state.voice_pipeline, "llm"):
        llm_coach = st.session_state.voice_pipeline.llm
        
    feedback = generate_personalized_feedback(
        exercise_type=st.session_state.exercise_type,
        current_session_metrics=current_session_metrics,
        history_rows=history_rows,
        user_streaks=user_streaks,
        llm_coach=llm_coach
    )
    
    st.session_state.overall_rating = feedback["rating"]
    st.session_state.strongest_area = feedback["strongest_area"]
    st.session_state.weakest_area = feedback["weakest_area"]
    st.session_state.improvement_percentage = feedback["improvement_percentage"]
    st.session_state.feedback_summary = feedback["feedback_summary"]
    st.session_state.recommendation = feedback["recommendation"]
    
    if st.session_state.get("sets_completed", 0) > 0:
        from services.persistence.exercise_repository import update_latest_exercise_feedback
        update_latest_exercise_feedback(
            st.session_state.get("user_id", 0),
            st.session_state.get("exercise_type", "Squats"),
            feedback["feedback_summary"],
            feedback["strongest_area"],
            feedback["weakest_area"],
            feedback["improvement_percentage"]
        )
            
    return feedback

