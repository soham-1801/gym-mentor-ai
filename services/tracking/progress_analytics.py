import datetime
import calendar
import pandas as pd

def calculate_streaks(workout_dates):
    """
    Calculate streak stats from workout dates.
    Returns: (current_streak, longest_streak, active_days, monthly_consistency)
    """
    if not workout_dates:
        return 0, 0, 0, 0.0
        
    parsed_dates = set()
    for d in workout_dates:
        if isinstance(d, str):
            try:
                parsed_dates.add(datetime.datetime.strptime(d.split()[0], "%Y-%m-%d").date())
            except Exception:
                pass
        elif isinstance(d, datetime.date):
            parsed_dates.add(d)
        elif isinstance(d, datetime.datetime):
            parsed_dates.add(d.date())
            
    sorted_dates = sorted(list(parsed_dates), reverse=True)
    active_days = len(sorted_dates)
    if not sorted_dates:
        return 0, 0, 0, 0.0
        
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    # 1. Current Streak
    current_streak = 0
    check_date = today
    
    # If no workout today, check if yesterday is the start of the streak
    if sorted_dates[0] == yesterday:
        check_date = yesterday
    elif sorted_dates[0] < yesterday:
        check_date = None
        current_streak = 0
        
    if check_date is not None:
        for d in sorted_dates:
            if d == check_date:
                current_streak += 1
                check_date = check_date - datetime.timedelta(days=1)
            elif d < check_date:
                break
                
    # 2. Longest Streak
    longest_streak = 0
    temp_streak = 0
    all_sorted = sorted(list(parsed_dates))
    
    if all_sorted:
        temp_streak = 1
        longest_streak = 1
        for i in range(1, len(all_sorted)):
            diff = (all_sorted[i] - all_sorted[i-1]).days
            if diff == 1:
                temp_streak += 1
            elif diff > 1:
                longest_streak = max(longest_streak, temp_streak)
                temp_streak = 1
        longest_streak = max(longest_streak, temp_streak)
        
    # 3. Monthly Consistency %
    current_year = today.year
    current_month = today.month
    active_in_current_month = sum(1 for d in sorted_dates if d.year == current_year and d.month == current_month)
    _, total_days_in_month = calendar.monthrange(current_year, current_month)
    monthly_consistency = (active_in_current_month / total_days_in_month) * 100.0 if total_days_in_month > 0 else 0.0
    
    return current_streak, longest_streak, active_days, monthly_consistency


def calculate_progress_stats(history_rows):
    """
    Calculate summary stats for the dashboard from history rows.
    """
    if not history_rows:
        return {
            "total_workouts": 0,
            "total_reps": 0,
            "total_sets": 0,
            "avg_form_score": 0,
            "best_form_score": 0,
            "total_time_sec": 0.0,
            "current_streak": 0,
            "longest_streak": 0,
            "active_days": 0,
            "monthly_consistency": 0.0,
            "most_performed": "None",
            "strongest_exercise": "None",
            "weakest_exercise": "None",
            "unique_dates": []
        }
        
    df = pd.DataFrame(history_rows)
    
    total_workouts = len(df)
    total_reps = int(df["reps"].sum())
    total_sets = int(df["sets"].sum())
    total_time_sec = float(df["time"].sum())
    
    # Calculate form scores
    valid_scores = df["average_form_score"].dropna()
    avg_form_score = int(valid_scores.mean()) if not valid_scores.empty else 0
    
    best_scores = df["best_form_score"].dropna()
    best_form_score = int(best_scores.max()) if not best_scores.empty else 0
    
    # Streaks and active days
    unique_dates = df["created_at"].tolist()
    current_streak, longest_streak, active_days, monthly_consistency = calculate_streaks(unique_dates)
    
    # Unique dates formatted for history
    parsed_dates = set()
    for d in unique_dates:
        if isinstance(d, str):
            try:
                parsed_dates.add(datetime.datetime.strptime(d.split()[0], "%Y-%m-%d").date())
            except Exception:
                pass
    sorted_unique_dates = sorted(list(parsed_dates), reverse=True)
    unique_dates_str = [d.strftime("%Y-%m-%d") for d in sorted_unique_dates]
    
    # Exercise counts
    ex_counts = df["exercise_name"].value_counts()
    most_performed = ex_counts.index[0] if not ex_counts.empty else "None"
    
    # Strongest/Weakest exercise based on average form score
    ex_scores = df.groupby("exercise_name")["average_form_score"].mean().dropna()
    strongest_exercise = ex_scores.idxmax() if not ex_scores.empty else "None"
    weakest_exercise = ex_scores.idxmin() if not ex_scores.empty else "None"
    
    return {
        "total_workouts": total_workouts,
        "total_reps": total_reps,
        "total_sets": total_sets,
        "avg_form_score": avg_form_score,
        "best_form_score": best_form_score,
        "total_time_sec": total_time_sec,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "active_days": active_days,
        "monthly_consistency": monthly_consistency,
        "most_performed": most_performed,
        "strongest_exercise": strongest_exercise,
        "weakest_exercise": weakest_exercise,
        "unique_dates": unique_dates_str
    }


def get_achievements(stats):
    """
    Get a list of streak-focused achievements with unlock status and progress string.
    """
    longest = stats["longest_streak"]
    return [
        {
            "name": "🥉 3-Day Streak",
            "desc": "Great start! Keep your streak alive.",
            "unlocked": longest >= 3,
            "progress": f"{min(3, longest)}/3 days"
        },
        {
            "name": "🥈 7-Day Streak",
            "desc": "One week strong! Excellent consistency.",
            "unlocked": longest >= 7,
            "progress": f"{min(7, longest)}/7 days"
        },
        {
            "name": "🥇 14-Day Streak",
            "desc": "Two weeks strong! Keep up the momentum.",
            "unlocked": longest >= 14,
            "progress": f"{min(14, longest)}/14 days"
        },
        {
            "name": "🔥 30-Day Streak",
            "desc": "Outstanding! You have built a powerful habit.",
            "unlocked": longest >= 30,
            "progress": f"{min(30, longest)}/30 days"
        },
        {
            "name": "👑 100-Day Streak",
            "desc": "Elite consistency! You are unstoppable.",
            "unlocked": longest >= 100,
            "progress": f"{min(100, longest)}/100 days"
        }
    ]


def get_ai_insights(history_rows, stats):
    """
    Generate heuristic-based AI coaching insights.
    """
    if not history_rows or stats["total_workouts"] == 0:
        return [
            "Start your first workout to generate AI coaching insights!",
            "Consistent workouts help trace form improvement curves.",
            "Our AI posture coach will evaluate your weakest areas as you train."
        ]
        
    df = pd.DataFrame(history_rows)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values("created_at")
    
    insights = []
    
    # 1. Form Improvement Insight
    most_perf = stats["most_performed"]
    if most_perf != "None":
        ex_df = df[df["exercise_name"] == most_perf]
        if len(ex_df) >= 2:
            mid = len(ex_df) // 2
            first_half = ex_df.iloc[:mid]["average_form_score"].dropna().mean()
            second_half = ex_df.iloc[mid:]["average_form_score"].dropna().mean()
            
            if pd.notna(first_half) and pd.notna(second_half):
                if second_half > first_half:
                    diff = int(((second_half - first_half) / (first_half if first_half > 0 else 1)) * 100)
                    if diff > 0:
                        insights.append(f"📈 Your **{most_perf}** form has improved by **{diff}%** this month! Excellent adjustment.")
                    else:
                        insights.append(f"💪 You are doing great with **{most_perf}**. Focus on controlled, slow movements to keep your form perfect.")
                else:
                    insights.append(f"⚡ Try slowing down your **{most_perf}** reps to focus on complete extension and correct depth.")
            else:
                insights.append(f"📈 Form score curves will show improvement analytics once you complete more **{most_perf}** sessions.")
        else:
            insights.append(f"📈 Form score curves will show improvement analytics once you complete more **{most_perf}** sessions.")
            
    # 2. Consistency Insight
    if most_perf != "None":
        count = len(df[df["exercise_name"] == most_perf])
        insights.append(f"🎯 You are most consistent with **{most_perf}** (**{count}** sessions completed). Try adding variety to stay balanced!")
        
    # 3. Weakest Exercise / Area Insight
    weak_ex = stats["weakest_exercise"]
    if weak_ex != "None" and pd.notna(weak_ex):
        if "Squat" in weak_ex:
            insights.append("⚠️ **Form Tip**: Keep your chest up and weight on your heels during squats to avoid leaning forward too much.")
        elif "Push-up" in weak_ex:
            insights.append("⚠️ **Form Tip**: Tighten your core and glutes to prevent your hips from sagging or piking up in push-ups.")
        elif "Curl" in weak_ex:
            insights.append("⚠️ **Form Tip**: Keep your elbows locked by your sides and avoid using torso momentum to swing the weight.")
        elif "Press" in weak_ex:
            insights.append("⚠️ **Form Tip**: Focus on full range of motion. Extend your arms completely overhead at the peak.")
        elif "Lunge" in weak_ex:
            insights.append("⚠️ **Form Tip**: Watch your knee alignment during lunges; ensure it does not push forward past your toes.")
        else:
            insights.append(f"⚠️ Your average score on **{weak_ex}** is lower. Try focusing on the visual posture suggestions during your next set.")
    else:
        insights.append("🌟 Keep maintaining level hips and stable joints to score high across all exercises!")
        
    return insights[:3]


def calculate_weekly_monthly_progress(history_rows):
    """
    Calculate progress summaries for weekly and monthly workouts.
    Compare averages and totals for current week vs last week,
    and current month vs last month.
    """
    if not history_rows:
        return {
            "weekly_workouts_change": 0,
            "weekly_reps_change": 0,
            "weekly_form_change": 0.0,
            "monthly_workouts_change": 0,
            "monthly_reps_change": 0,
            "monthly_form_change": 0.0,
            "weekly_summary": "No workout history available.",
            "monthly_summary": "No workout history available."
        }
        
    df = pd.DataFrame(history_rows)
    df["created_at"] = pd.to_datetime(df["created_at"])
    today = datetime.datetime.now()
    
    current_year_week = today.isocalendar()[:2]
    last_week_date = today - datetime.timedelta(days=7)
    last_year_week = last_week_date.isocalendar()[:2]
    
    df["year"] = df["created_at"].dt.isocalendar().year
    df["week"] = df["created_at"].dt.isocalendar().week
    df["month"] = df["created_at"].dt.month
    df["year_month"] = df["created_at"].dt.to_period('M')
    
    curr_week_df = df[(df["year"] == current_year_week[0]) & (df["week"] == current_year_week[1])]
    last_week_df = df[(df["year"] == last_year_week[0]) & (df["week"] == last_year_week[1])]
    
    curr_week_workouts = len(curr_week_df)
    last_week_workouts = len(last_week_df)
    weekly_workouts_change = curr_week_workouts - last_week_workouts
    
    curr_week_reps = int(curr_week_df["reps"].sum()) if not curr_week_df.empty else 0
    last_week_reps = int(last_week_df["reps"].sum()) if not last_week_df.empty else 0
    weekly_reps_change = curr_week_reps - last_week_reps
    
    curr_week_form_avg = curr_week_df["average_form_score"].dropna().mean()
    last_week_form_avg = last_week_df["average_form_score"].dropna().mean()
    
    if pd.isna(curr_week_form_avg):
        curr_week_form_avg = 0.0
    if pd.isna(last_week_form_avg):
        last_week_form_avg = 0.0
        
    weekly_form_change = curr_week_form_avg - last_week_form_avg
    
    weekly_summary_parts = []
    if curr_week_workouts > 0:
        if last_week_workouts > 0:
            pct_w = int((weekly_workouts_change / last_week_workouts) * 100) if last_week_workouts > 0 else 100
            if weekly_workouts_change > 0:
                weekly_summary_parts.append(f"You did {weekly_workouts_change} more workout(s) (+{pct_w}%) compared to last week.")
            elif weekly_workouts_change < 0:
                weekly_summary_parts.append(f"You completed {abs(weekly_workouts_change)} fewer workout(s) ({pct_w}%) than last week.")
            else:
                weekly_summary_parts.append("You completed the same number of workouts as last week.")
        else:
            weekly_summary_parts.append(f"Great start! You completed {curr_week_workouts} workout(s) this week.")
            
        if curr_week_reps > 0 and last_week_reps > 0:
            if weekly_reps_change > 0:
                weekly_summary_parts.append(f"Rep count increased by {weekly_reps_change} reps (+{int((weekly_reps_change/last_week_reps)*100)}%).")
            elif weekly_reps_change < 0:
                weekly_summary_parts.append(f"Rep count decreased by {abs(weekly_reps_change)} reps ({int((weekly_reps_change/last_week_reps)*100)}%).")
        
        if curr_week_form_avg > 0 and last_week_form_avg > 0:
            if weekly_form_change > 0:
                weekly_summary_parts.append(f"Your average form score improved by {weekly_form_change:.1f} points.")
            elif weekly_form_change < 0:
                weekly_summary_parts.append(f"Average form score decreased by {abs(weekly_form_change):.1f} points. Focus on correct depth/alignment next week.")
    else:
        weekly_summary_parts.append("No workouts logged yet for the current calendar week.")
        
    weekly_summary = " ".join(weekly_summary_parts)
    
    curr_month = today.month
    curr_year = today.year
    
    last_month_date = today.replace(day=1) - datetime.timedelta(days=1)
    last_month = last_month_date.month
    last_month_year = last_month_date.year
    
    curr_month_df = df[(df["created_at"].dt.month == curr_month) & (df["created_at"].dt.year == curr_year)]
    last_month_df = df[(df["created_at"].dt.month == last_month) & (df["created_at"].dt.year == last_month_year)]
    
    curr_month_workouts = len(curr_month_df)
    last_month_workouts = len(last_month_df)
    monthly_workouts_change = curr_month_workouts - last_month_workouts
    
    curr_month_reps = int(curr_month_df["reps"].sum()) if not curr_month_df.empty else 0
    last_month_reps = int(last_month_df["reps"].sum()) if not last_month_df.empty else 0
    monthly_reps_change = curr_month_reps - last_month_reps
    
    curr_month_form_avg = curr_month_df["average_form_score"].dropna().mean()
    last_month_form_avg = last_month_df["average_form_score"].dropna().mean()
    
    if pd.isna(curr_month_form_avg):
        curr_month_form_avg = 0.0
    if pd.isna(last_month_form_avg):
        last_month_form_avg = 0.0
        
    monthly_form_change = curr_month_form_avg - last_month_form_avg
    
    monthly_summary_parts = []
    if curr_month_workouts > 0:
        if last_month_workouts > 0:
            pct_m = int((monthly_workouts_change / last_month_workouts) * 100) if last_month_workouts > 0 else 100
            if monthly_workouts_change > 0:
                monthly_summary_parts.append(f"Monthly workouts increased by {monthly_workouts_change} (+{pct_m}%).")
            elif monthly_workouts_change < 0:
                monthly_summary_parts.append(f"Workout volume decreased by {abs(monthly_workouts_change)} ({pct_m}%).")
            else:
                monthly_summary_parts.append("Monthly workouts count is holding steady.")
        else:
            monthly_summary_parts.append(f"Completed {curr_month_workouts} workout(s) in the current month.")
            
        if curr_month_reps > 0 and last_month_reps > 0:
            if monthly_reps_change > 0:
                monthly_summary_parts.append(f"Rep volume increased by {monthly_reps_change} reps (+{int((monthly_reps_change/last_month_reps)*100)}%).")
            elif monthly_reps_change < 0:
                monthly_summary_parts.append(f"Rep volume decreased by {abs(monthly_reps_change)} reps ({int((monthly_reps_change/last_month_reps)*100)}%).")
                
        if curr_month_form_avg > 0 and last_month_form_avg > 0:
            if monthly_form_change > 0:
                monthly_summary_parts.append(f"Form score average increased from {last_month_form_avg:.1f} to {curr_month_form_avg:.1f} (+{monthly_form_change:.1f} points).")
            elif monthly_form_change < 0:
                monthly_summary_parts.append(f"Form score average dropped by {abs(monthly_form_change):.1f} points. Focus on technique.")
    else:
        monthly_summary_parts.append("No workouts logged yet for the current month.")
        
    monthly_summary = " ".join(monthly_summary_parts)
    
    return {
        "weekly_workouts_change": weekly_workouts_change,
        "weekly_reps_change": weekly_reps_change,
        "weekly_form_change": float(weekly_form_change),
        "monthly_workouts_change": monthly_workouts_change,
        "monthly_reps_change": monthly_reps_change,
        "monthly_form_change": float(monthly_form_change),
        "weekly_summary": weekly_summary,
        "monthly_summary": monthly_summary
    }
