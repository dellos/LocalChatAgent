FROM python:3.11-slim

WORKDIR /app

# Required by soundfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
# Copy application
COPY stt_app.py .

EXPOSE 8900

CMD ["uvicorn", "stt_app:app", "--host", "0.0.0.0", "--port", "8900"]