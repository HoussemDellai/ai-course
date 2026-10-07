from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Environment variables set by Azure Container Apps take precedence over a local .env file.
load_dotenv(override=False)


def _list(value: str) -> list[str]:
    return [v.strip().rstrip("/") for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    foundry_project_endpoint: str = ""
    foundry_model: str = "gpt-6-astra"
    speech_endpoint: str = ""
    tts_voice: str = "en-US-AndrewMultilingualNeural"
    comfyui_urls: list[str] = field(default_factory=lambda: ["http://127.0.0.1:8188"])
    gpu_stats_urls: list[str] = field(default_factory=list)
    default_video_model: str = "wan22"
    storage_account_url: str = ""
    storage_container: str = "videos"
    local_output_dir: Path = Path("output")
    work_dir: Path = Path("/tmp/video-platform")
    api_key: str = ""
    clip_timeout_seconds: int = 1800
    clip_retries: int = 2
    max_concurrent_jobs: int = 1
    ffmpeg_concurrency: int = 2
    ambient_audio_volume: float = 0.25
    music_volume: float = 0.3
    music_fade_seconds: float = 1.0
    output_width: int = 1280
    output_height: int = 720
    output_fps: int = 24
    max_image_mb: int = 10

    @classmethod
    def from_env(cls) -> Settings:
        e = os.environ.get
        return cls(
            foundry_project_endpoint=e("FOUNDRY_PROJECT_ENDPOINT", ""),
            foundry_model=e("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-6-astra"),
            speech_endpoint=e("SPEECH_ENDPOINT", ""),
            tts_voice=e("TTS_VOICE", "en-US-AndrewMultilingualNeural"),
            comfyui_urls=_list(e("COMFYUI_URLS", "http://127.0.0.1:8188")),
            gpu_stats_urls=_list(e("GPU_STATS_URLS", "")),
            default_video_model=e("DEFAULT_VIDEO_MODEL", "wan22"),
            storage_account_url=e("STORAGE_ACCOUNT_URL", ""),
            storage_container=e("STORAGE_CONTAINER", "videos"),
            local_output_dir=Path(e("LOCAL_OUTPUT_DIR", "output")),
            work_dir=Path(e("WORK_DIR", str(Path(os.environ.get("TMPDIR", "/tmp")) / "video-platform"))),
            api_key=e("API_KEY", ""),
            clip_timeout_seconds=int(e("CLIP_TIMEOUT_SECONDS", "1800")),
            clip_retries=int(e("CLIP_RETRIES", "2")),
            max_concurrent_jobs=int(e("MAX_CONCURRENT_JOBS", "1")),
            ffmpeg_concurrency=int(e("FFMPEG_CONCURRENCY", "2")),
            ambient_audio_volume=float(e("AMBIENT_AUDIO_VOLUME", "0.25")),
            music_volume=float(e("MUSIC_VOLUME", "0.3")),
            music_fade_seconds=float(e("MUSIC_FADE_SECONDS", "1.0")),
            max_image_mb=int(e("MAX_IMAGE_MB", "10")),
        )

    @property
    def max_image_bytes(self) -> int:
        return self.max_image_mb * 1024 * 1024
