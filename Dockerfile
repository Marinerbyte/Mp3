FROM python:3.9-slim

# Install FFmpeg and system fonts
RUN apt-get update && \
    apt-get install -y ffmpeg fontconfig fonts-dejavu && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--timeout", "120"]
