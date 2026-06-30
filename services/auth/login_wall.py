import streamlit as st
from services.persistence.exercise_repository import get_or_create_user


def render_login_wall():
    if st.session_state.get("user_id") is not None:
        return True
    
    st.markdown(
        """
        <style>
        /* Hide sidebar and header on login page */
        [data-testid="stSidebar"] { display: none; }
        header { display: none !important; }

        /* Real Gym App Background */
        .stApp {
            background-color: #000 !important;
            background-image: 
                linear-gradient(to bottom, rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.9)),
                url('https://images.unsplash.com/photo-1534438327276-14e5300c3a48?q=80&w=1920&auto=format&fit=crop');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            overflow: hidden;
        }

        /* Gym App Card styling */
        [data-testid="stForm"] {
            position: relative;
            z-index: 10;
            padding: 50px 45px !important;
            background: rgba(18, 18, 18, 0.85) !important;
            border-radius: 20px !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.9) !important;
            backdrop-filter: blur(16px) !important;
            -webkit-backdrop-filter: blur(16px) !important;
            animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes slideUp {
            0% { transform: translateY(30px); opacity: 0; }
            100% { transform: translateY(0); opacity: 1; }
        }

        /* Input field container to ensure full width */
        [data-testid="stForm"] [data-testid="stTextInput"] {
            margin-bottom: 5px !important;
        }

        /* Input field styling */
        [data-testid="stForm"] [data-testid="stTextInput"] input {
            background: rgba(0, 0, 0, 0.4) !important;
            border: 2px solid rgba(255, 255, 255, 0.1) !important;
            color: #fff !important;
            border-radius: 12px !important;
            padding: 16px 20px !important;
            font-size: 1.1rem !important;
            transition: all 0.3s ease !important;
        }

        [data-testid="stForm"] [data-testid="stTextInput"] input:focus {
            border-color: #10B981 !important;
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.2) !important;
            background: rgba(0, 0, 0, 0.6) !important;
        }

        /* Submit Button Styling (Energetic Gym Vibe) */
        [data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
            background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 16px !important;
            font-weight: 800 !important;
            font-size: 1.15rem !important;
            text-transform: uppercase !important;
            letter-spacing: 1.5px !important;
            width: 100% !important;
            margin-top: 15px !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 8px 25px rgba(16, 185, 129, 0.3) !important;
        }

        [data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
            transform: translateY(-3px) !important;
            background: linear-gradient(135deg, #34D399 0%, #10B981 100%) !important;
            box-shadow: 0 12px 30px rgba(16, 185, 129, 0.5) !important;
        }
        
        /* Typography */
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;800;900&display=swap');

        .login-title {
            font-family: 'Montserrat', sans-serif;
            font-size: 2.2rem;
            font-weight: 900;
            color: #ffffff;
            margin-bottom: 6px;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: -1.5px;
            text-shadow: 0 4px 15px rgba(0,0,0,0.8);
            line-height: 1.1;
        }
        
        .login-title .highlight {
            color: transparent;
            background: linear-gradient(135deg, #34D399 0%, #10B981 100%);
            -webkit-background-clip: text;
            display: inline-block;
        }
        
        .login-title .brand {
            font-weight: 400;
            letter-spacing: 3px;
            font-size: 1rem;
            display: block;
            color: #9CA3AF;
            margin-bottom: 4px;
        }

        .login-subtitle {
            font-family: 'Montserrat', sans-serif;
            color: #9CA3AF;
            font-size: 1rem;
            margin-bottom: 35px;
            text-align: center;
            font-weight: 500;
            letter-spacing: 0.5px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Empty columns to center the form vertically and horizontally
    st.write("<br><br><br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.3, 1])
    
    with col2:
        with st.form("login_form", clear_on_submit=False):
            st.markdown(
                '<div class="login-title"><span class="brand">WELCOME TO</span>GYM<span class="highlight">MENTOR</span> AI</div>', 
                unsafe_allow_html=True
            )
            st.markdown('<div class="login-subtitle">Your personal AI trainer. Enter your ID to start pushing your limits.</div>', unsafe_allow_html=True)
            
            username = st.text_input("Username", placeholder="e.g. fitness_freak", label_visibility="collapsed")
            submit_button = st.form_submit_button("Start Workout", use_container_width=True)

            if submit_button:
                if not username.strip():
                    st.error("Username cannot be empty.")
                else:
                    user = get_or_create_user(username.strip())
                    if user is None:
                        st.error("Could not create or find user. Please try again.")
                    else:
                        st.session_state["user_id"] = user["id"]
                        st.session_state["username"] = user["username"]
                        st.rerun()

    return False

