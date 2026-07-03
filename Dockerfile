FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by MediaPipe and OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libegl1 \
    libgles2 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose port for Hugging Face Spaces (default 8501 for Streamlit)
EXPOSE 8501

# Launch Streamlit server
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
