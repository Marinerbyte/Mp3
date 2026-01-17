# Sabse chhota Python version
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Timeout 60s kaafi hai kyunki hum sirf link copy kar rahe hain
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--timeout", "60"]
