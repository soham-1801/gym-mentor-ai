def calculate_form_score(exercise_type: str, metrics: dict) -> tuple:
    """
    Calculate real-time Form Score (0-100) and identify strongest/weakest areas
    using existing exercise metrics.
    
    Returns:
        tuple: (overall_score, components_dict)
        where:
            overall_score (int): 0 to 100
            components_dict (dict): Map of component names to their score (0-100)
    """
    components = {}
    
    if exercise_type == "Squats":
        # 1. Depth Component
        knee_angle = metrics.get("knee_angle", 180)
        depth_status = metrics.get("depth_status", "Unknown")
        
        if knee_angle >= 140 or depth_status == "STANDING":
            # Neutral/Standing position, form depth is considered correct (rest phase)
            depth_score = 100
        else:
            if depth_status == "GOOD DEPTH" or knee_angle <= 100:
                depth_score = 100
            elif depth_status == "Shallow Squat" or (100 < knee_angle <= 130):
                depth_score = max(55, 100 - int((knee_angle - 95) * 1.5))
            else:  # TOO HIGH
                depth_score = max(35, 100 - int((knee_angle - 95) * 2.0))
                
        # 2. Torso Alignment Component
        back_angle = metrics.get("back_angle", 0)  # Leaning angle vs vertical
        if back_angle <= 18:
            posture_score = 100
        elif back_angle <= 28:
            posture_score = 80
        elif back_angle <= 35:
            posture_score = 60
        else:
            posture_score = max(30, 100 - int((back_angle - 18) * 2.5))
            
        components["Squat Depth"] = depth_score
        components["Torso Alignment"] = posture_score

    elif exercise_type == "Push-ups":
        # 1. Push-up Depth
        elbow_angle = metrics.get("elbow_angle", 180)
        if elbow_angle >= 135:
            depth_score = 100
        else:
            if elbow_angle <= 90:
                depth_score = 100
            else:
                depth_score = max(40, 100 - int((elbow_angle - 90) * 1.25))
                
        # 2. Body Alignment
        alignment_status = str(metrics.get("body_alignment", "Straight"))
        if "Straight" in alignment_status:
            alignment_score = 100
        elif "Slight Bend" in alignment_status:
            alignment_score = 75
        else:  # Poor Form
            alignment_score = 45
            
        # 3. Hip Position
        hip_status = str(metrics.get("hip_status", "LEVEL"))
        if "LEVEL" in hip_status:
            hip_score = 100
        elif "SAGGING" in hip_status or "Sagging" in alignment_status:
            hip_score = 50
        elif "PIKED UP" in hip_status or "High Hip" in alignment_status:
            hip_score = 65
        else:
            hip_score = 100
            
        components["Push-up Depth"] = depth_score
        components["Body Alignment"] = alignment_score
        components["Hip Position"] = hip_score

    elif exercise_type == "Biceps Curls (Dumbbell)":
        # 1. Shoulder/Elbow Stability
        shoulder_status = str(metrics.get("shoulder_status", "STABLE"))
        if "STABLE" in shoulder_status:
            stability_score = 100
        elif "ELBOW DRIFTING" in shoulder_status or "Unstable" in shoulder_status:
            stability_score = 50
        else:
            stability_score = 100
            
        # 2. Torso Stability (Swing)
        swing_status = str(metrics.get("swing_status", "NO SWING"))
        if "NO SWING" in swing_status:
            swing_score = 100
        elif "SWINGING" in swing_status or "Swing" in swing_status:
            swing_score = 45
        else:
            swing_score = 100
            
        # 3. Range of Motion (Curl completion)
        elbow_angle = metrics.get("elbow_angle", 160)
        # Check completion at top
        if elbow_angle < 75:
            rom_score = max(55, 100 - int(max(0, elbow_angle - 50) * 1.5))
        # Check extension at bottom
        elif elbow_angle > 135:
            rom_score = max(55, 100 - int(max(0, 160 - elbow_angle) * 1.5))
        else:
            rom_score = 100  # transition phase
            
        components["Shoulder Stability"] = stability_score
        components["Torso Stability"] = swing_score
        components["Range of Motion"] = rom_score

    elif exercise_type == "Shoulder Press":
        # 1. Back Posture (Arch)
        back_arch = str(metrics.get("back_arch_status", "Neutral"))
        if "Neutral" in back_arch:
            arch_score = 100
        elif "Slight" in back_arch:
            arch_score = 75
        else:  # Excessive Arch
            arch_score = 45
            
        # 2. Arm Extension
        extension_status = str(metrics.get("extension_status", "START POSITION"))
        elbow_angle = metrics.get("elbow_angle", 90)
        if elbow_angle > 120:
            if "FULL" in extension_status or elbow_angle >= 160:
                extension_score = 100
            elif "NEARLY" in extension_status or elbow_angle >= 135:
                extension_score = 80
            else:  # PRESSING / Incomplete
                extension_score = max(50, 100 - int((160 - elbow_angle) * 1.5))
        else:
            extension_score = 100  # neutral descent/starting position
            
        components["Back Posture"] = arch_score
        components["Arm Extension"] = extension_score

    elif exercise_type == "Lunges":
        # 1. Balance & Stability
        balance = str(metrics.get("balance_status", "BALANCED"))
        if "BALANCED" in balance:
            balance_score = 100
        elif "Knee Past Toes" in balance:
            balance_score = 40
        else:  # OFF BALANCE
            balance_score = 55
            
        # 2. Torso Posture
        torso_angle = metrics.get("torso_angle", 0)
        if torso_angle <= 15:
            torso_score = 100
        elif torso_angle <= 25:
            torso_score = 80
        else:
            torso_score = max(40, 100 - int((torso_angle - 15) * 2.5))
            
        # 3. Lunge Depth
        front_knee_angle = metrics.get("front_knee_angle", 180)
        if front_knee_angle >= 130:
            depth_score = 100  # neutral/standing
        else:
            if front_knee_angle <= 100:
                depth_score = 100
            else:
                depth_score = max(50, 100 - int((front_knee_angle - 100) * 1.5))
                
        components["Balance & Stability"] = balance_score
        components["Torso Posture"] = torso_score
        components["Lunge Depth"] = depth_score

    else:
        # Fallback for unsupported exercises
        components["General Posture"] = 100
        
    overall_score = int(sum(components.values()) / len(components)) if components else 100
    
    return overall_score, components


def is_active_exercise_frame(exercise_type: str, metrics: dict) -> bool:
    """
    Determine if the user is actively exercising (in the middle of a rep or movement)
    rather than resting, standing idle, or holding the start position.
    This prevents resting 100s from inflating the average workout score.
    """
    if exercise_type == "Squats":
        knee_angle = metrics.get("knee_angle", 180)
        depth_status = str(metrics.get("depth_status", "STANDING"))
        return knee_angle < 145 and depth_status != "STANDING"
        
    elif exercise_type == "Push-ups":
        elbow_angle = metrics.get("elbow_angle", 180)
        return elbow_angle < 150
        
    elif exercise_type == "Biceps Curls (Dumbbell)":
        elbow_angle = metrics.get("elbow_angle", 180)
        shoulder_status = str(metrics.get("shoulder_status", "STABLE"))
        swing_status = str(metrics.get("swing_status", "NO SWING"))
        return elbow_angle < 145 or "SWINGING" in swing_status or "DRIFTING" in shoulder_status
        
    elif exercise_type == "Shoulder Press":
        elbow_angle = metrics.get("elbow_angle", 90)
        extension_status = str(metrics.get("extension_status", "START POSITION"))
        return elbow_angle > 105 or extension_status != "START POSITION"
        
    elif exercise_type == "Lunges":
        front_knee_angle = metrics.get("front_knee_angle", 180)
        return front_knee_angle < 145
        
    return True

