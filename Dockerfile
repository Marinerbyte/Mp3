# Python 3.11 Slim (Sabse chhota aur fast)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Timeout 120s kaafi hai kyunki conversion nahi karna
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--timeout", "120"]
