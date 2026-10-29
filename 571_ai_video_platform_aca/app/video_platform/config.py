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
    # False when the GPU servers scale to zero: live stats then never wake an idle server.
    gpu_stats_when_idle: bool = True
    # How long a render waits for a ComfyUI worker scaled to zero to start (its startup probe allows 40 minutes).
    comfyui_warmup_timeout_seconds: int = 2400
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
    output_fps: int = 24
    max_image_mb: int = 50
    max_document_mb: int = 100
    libreoffice_path: str = "soffice"
    education_text_models: list[str] = field(default_factory=list)
    education_search_model: str = ""
    foundry_image_endpoint: str = ""
    foundry_image_model: str = ""
    foundry_video_endpoint: str = ""
    foundry_video_model: str = ""
    drawio_mcp_url: str = ""
    drawio_export_command: str = ""
    comfy_image_workflow: str = ""
    education_font: str = ""
    voice_clone_url: str = ""
    # Second deployment of the voice-clone service on an A100, for engines that don't fit the default GPU.
    voice_clone_a100_url: str = ""
    voice_clone_api_key: str = ""
    max_voice_sample_mb: int = 25
    voice_clone_load_timeout_seconds: int = 1800

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
            gpu_stats_when_idle=e("GPU_STATS_WHEN_IDLE", "true").strip().lower() in {"1", "true", "yes", "on"},
            comfyui_warmup_timeout_seconds=int(e("COMFYUI_WARMUP_TIMEOUT_SECONDS", "2400")),
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
            max_image_mb=int(e("MAX_IMAGE_MB", "50")),
            max_document_mb=int(e("MAX_DOCUMENT_MB", "100")),
            libreoffice_path=e("LIBREOFFICE_PATH", "soffice"),
            education_text_models=_list(e("EDUCATION_TEXT_MODELS", "")),
            education_search_model=e("EDUCATION_SEARCH_MODEL", ""),
            foundry_image_endpoint=e("FOUNDRY_IMAGE_ENDPOINT", ""),
            foundry_image_model=e("FOUNDRY_IMAGE_MODEL", ""),
            foundry_video_endpoint=e("FOUNDRY_VIDEO_ENDPOINT", ""),
            foundry_video_model=e("FOUNDRY_VIDEO_MODEL", ""),
            drawio_mcp_url=e("DRAWIO_MCP_URL", ""),
            drawio_export_command=e("DRAWIO_EXPORT_COMMAND", ""),
            comfy_image_workflow=e("COMFY_IMAGE_WORKFLOW", ""),
            education_font=e("EDUCATION_FONT", ""),
            voice_clone_url=e("VOICE_CLONE_URL", "").rstrip("/"),
            voice_clone_a100_url=e("VOICE_CLONE_A100_URL", "").rstrip("/"),
            voice_clone_api_key=e("VOICE_CLONE_API_KEY", ""),
            max_voice_sample_mb=int(e("MAX_VOICE_SAMPLE_MB", "25")),
            voice_clone_load_timeout_seconds=int(e("VOICE_CLONE_LOAD_TIMEOUT_SECONDS", "1800")),
        )

    @property
    def batch_parallel_capacity(self) -> int:
        workers = len({url.strip().rstrip("/") for url in self.comfyui_urls if url.strip()})
        return max(1, min(self.max_concurrent_jobs, workers))

    @property
    def max_voice_sample_bytes(self) -> int:
        return self.max_voice_sample_mb * 1024 * 1024

    @property
    def max_image_bytes(self) -> int:
        return self.max_image_mb * 1024 * 1024

    @property
    def max_document_bytes(self) -> int:
        return self.max_document_mb * 1024 * 1024
