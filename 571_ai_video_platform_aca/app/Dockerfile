FROM python:3.12-slim-bookworm

# ffmpeg for assembling the video; libssl/libasound2 are runtime dependencies of the Azure Speech SDK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates libssl3 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py generate.py ./
COPY video_platform ./video_platform

ENV PYTHONUNBUFFERED=1 \
    WORK_DIR=/tmp/video-platform

EXPOSE 8000
CMD ["python", "main.py"]
