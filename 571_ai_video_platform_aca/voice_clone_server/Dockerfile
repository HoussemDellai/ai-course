FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates build-essential portaudio19-dev \
       libsndfile1 sox libsox-fmt-all ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.8.17

ARG FISH_SPEECH_COMMIT=541566932abbaebcb0a40e562a1f846738383f38
ENV FISH_SPEECH_COMMIT=${FISH_SPEECH_COMMIT}
COPY build_venvs.sh /tmp/build_venvs.sh
RUN sed -i 's/\r$//' /tmp/build_venvs.sh && bash /tmp/build_venvs.sh && rm /tmp/build_venvs.sh

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway.py ./
COPY workers ./workers

ENV PYTHONUNBUFFERED=1 \
    NLTK_DATA=/opt/nltk_data \
    MODEL_CACHE=/cache/voice-clone \
    HF_HOME=/cache/voice-clone/hf

EXPOSE 8000
CMD ["uvicorn", "gateway:app", "--host", "0.0.0.0", "--port", "8000"]
