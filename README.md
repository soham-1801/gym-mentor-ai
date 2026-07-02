# 🏋️‍♂️ GymMentor AI — Real-Time AI Gym Trainer & Form Coach

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.54.0-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.14-00B2FF?style=for-the-badge&logo=google&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.10.0-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Next-Generation AI Fitness Mentor powered by Computer Vision, Real-Time Landmark Tracking, and Voice Coaching.**

</div>

---

## 🌟 Overview

**GymMentor AI** is an advanced, real-time AI workout assistant that turns your webcam into an intelligent personal fitness coach. Utilizing state-of-the-art computer vision (Google MediaPipe & OpenCV) and interactive voice feedback, it tracks your joint angles, counts your repetitions, evaluates exercise form, and provides instant audio-visual guidance to prevent injuries and maximize workout efficiency.

---

## ✨ Key Features

- **🦾 Real-Time 3D Form & Posture Tracking**: Detects 33 body landmarks in real time with high precision to analyze body mechanics and joint angles.
- **🏋️ Multiple Exercise Support**:
  - **Squats**: Tracks knee flexion and hip depth.
  - **Push-ups**: Monitors elbow angle and back alignment.
  - **Biceps Curls**: Evaluates range of motion and form stability.
  - **Shoulder Press**: Assesses arm extension and symmetry.
  - **Lunges**: Checks front/back leg angles and balance.
- **🗣️ Interactive Voice Coaching**: Integrated TTS pipeline that delivers instant, real-time audio cues ("Lower your hips", "Straighten your back", "Great rep!").
- **📊 Progress Analytics & Calorie Tracking**: Advanced workout metrics, rep counting, set tracking, and real-time calorie burn estimation.
- **🎨 Premium UI/UX Design**: Sleek glassmorphic interface built with customized Streamlit themes, dynamic animations, and responsive layouts.

---

## 🏗️ Architecture & Project Structure

```text
gym-mentor-ai/
│
├── core/                  # Core exercise base classes and data structures
├── detectors/             # Exercise-specific landmark logic & angle calculators
│   ├── biceps_curl.py
│   ├── lunges.py
│   ├── pushups.py
│   ├── shoulder_press.py
│   └── squat.py
├── ml_models/             # Machine learning models and weights
├── services/              # Application services & background pipelines
│   ├── auth/              # Authentication & login wall
│   ├── coaching/          # LLM coaching, event bus, TTS & voice pipeline
│   ├── config/            # Goal configuration & workout programs
│   ├── persistence/       # Database exercise repositories
│   ├── scheduling/        # Workout scheduler
│   ├── state/             # Session state & default initialization
│   ├── tracking/          # Metrics, analytics & calorie estimation
│   ├── ui/                # Style loaders & UI components
│   └── vision/            # Video processor & MediaPipe integration
├── static/                # Custom fonts, CSS design tokens & demo assets
├── main.py                # Main application entry point
└── requirements.txt       # Python dependency list
```

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/soham-1801/gym-mentor-ai.git
cd gym-mentor-ai
```

### 2. Create a Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
streamlit run main.py
```

---

## 🛡️ Best Practices & Guidelines

- **Lighting**: Ensure your workout area is well-lit for optimal webcam tracking.
- **Camera Placement**: Place your camera at waist-to-chest height, 6–8 feet away, ensuring your full body is visible in the frame.
- **Audio**: Turn on your speakers or headphones to hear real-time AI voice coaching cues.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](file:///c:/Users/SOHAM%20MANGROLIYA/OneDrive/Desktop/Real-Time%20AI%20Gym%20Trainer/LICENSE) file for details.

---

<div align="center">
  <b>Built with ❤️ for smarter and safer fitness training.</b>
</div>
