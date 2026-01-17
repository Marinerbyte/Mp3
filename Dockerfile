# Python 3.11 ka sabse chhota version
FROM python:3.11-slim

WORKDIR /app

# Requirements install karo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pura code copy karo
COPY . .

# Timeout 60s rakha hai kyunki conversion Cobalt server par ho raha hai
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--timeout", "60"]
