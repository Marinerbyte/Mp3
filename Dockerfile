# Render ab Python 3.9 support nahi karta, isliye 3.11 use kar rahe hain
FROM python:3.11-slim

# System updates aur FFmpeg install karna zaroori hai
RUN apt-get update && \
    apt-get install -y ffmpeg fontconfig fonts-dejavu && \
    rm -rf /var/lib/apt/lists/*

# Work directory set karo
WORKDIR /app

# Pehle requirements copy karo taaki cache use ho sake
COPY requirements.txt .

# Install dependencies (No Cache taaki latest yt-dlp mile)
RUN pip install --no-cache-dir -r requirements.txt

# Baaki code copy karo
COPY . .

# Gunicorn start karo (Timeout 300s = 5 Minute kar diya hai)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--timeout", "300"]
