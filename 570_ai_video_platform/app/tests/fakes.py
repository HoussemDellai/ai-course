from __future__ import annotations

import re
import shutil
import subprocess
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from video_platform.agents import fit_shot_count
from video_platform.comfyui import ComfyUIClient, ComfyUIPool
from video_platform.schemas import CreativeBrief, Character, SceneOutline, Shot, StoryOutline
from video_platform.video_models import VideoModel

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
requires_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not on PATH")


def make_png(width: int = 64, height: int = 36, color=(200, 120, 40), fmt: str = "PNG", **save_args) -> bytes:
    out = BytesIO()
    Image.new("RGB", (width, height), color).save(out, format=fmt, **save_args)
    return out.getvalue()


def make_clip(path: Path, seconds: float, fps: int, width: int, height: int, audio: bool) -> Path:
    args = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
            f"testsrc2=size={width}x{height}:rate={fps}:duration={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "aac"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", str(path)]
    subprocess.run(args, check=True)
    return path


def make_wav(path: Path, seconds: float) -> Path:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=frequency=220:duration={seconds}", "-ar", "48000", "-ac", "1", str(path)], check=True)
    return path


class FakeComfy:
    """In-memory ComfyUI HTTP API (/prompt, /history, /view, /upload/image, /queue)."""

    def __init__(self, clip: Path | None = None, fail_first: int = 0):
        self.clip_bytes = clip.read_bytes() if clip else b"fake-mp4"
        self.image_bytes = make_png()
        self.submitted: list[dict] = []
        self.uploads: list[tuple[str, str, str]] = []  # (server, subfolder, filename)
        self.image_prompts: set[str] = set()
        self.fail_first = fail_first
        self.failed: set[str] = set()

    def handler(self, request: httpx.Request) -> httpx.Response:
        import json

        if request.method == "POST" and request.url.path == "/upload/image":
            body = request.content.decode("latin-1")
            filename = re.search(r'name="image"; filename="([^"]+)"', body).group(1)
            subfolder = re.search(r'name="subfolder"\r\n\r\n([^\r]*)\r\n', body).group(1)
            self.uploads.append((request.url.host, subfolder, filename))
            return httpx.Response(200, json={"name": filename, "subfolder": subfolder, "type": "input"})
        if request.method == "POST" and request.url.path == "/prompt":
            workflow = json.loads(request.content)["prompt"]
            self.submitted.append(workflow)
            pid = f"p{len(self.submitted)}"
            if any(n["class_type"] == "SaveImage" for n in workflow.values()):
                self.image_prompts.add(pid)
            return httpx.Response(200, json={"prompt_id": pid, "number": 1, "node_errors": {}})
        if request.method == "GET" and request.url.path.startswith("/history/"):
            pid = request.url.path.rsplit("/", 1)[1]
            if self.fail_first > 0 and pid not in self.failed and pid.startswith("p"):
                self.fail_first -= 1
                self.failed.add(pid)
            if pid in self.failed:  # like ComfyUI, failed prompts stay in the history as errors
                return httpx.Response(200, json={pid: {"outputs": {}, "status": {
                    "status_str": "error", "completed": False, "messages": [["execution_error", {"x": 1}]]}}})
            if pid in self.image_prompts:
                outputs = {"16": {"images": [{"filename": f"{pid}_00001_.png", "subfolder": "aivideo",
                                              "type": "output"}]}}
            else:
                outputs = {"16": {"images": [{"filename": f"{pid}.mp4", "subfolder": "aivideo", "type": "output"}],
                                  "animated": [True]}}
            return httpx.Response(200, json={pid: {
                "outputs": outputs, "status": {"status_str": "success", "completed": True, "messages": []}}})
        if request.method == "GET" and request.url.path == "/view":
            if request.url.params.get("filename", "").endswith(".png"):
                return httpx.Response(200, content=self.image_bytes)
            return httpx.Response(200, content=self.clip_bytes)
        if request.method == "GET" and request.url.path == "/queue":
            return httpx.Response(200, json={"queue_running": [], "queue_pending": []})
        if request.url.path == "/interrupt":
            return httpx.Response(200)
        return httpx.Response(404)

    def pool(self, servers: int = 1) -> ComfyUIPool:
        return ComfyUIPool([
            ComfyUIClient(f"http://comfy{i}:8188", http=httpx.AsyncClient(transport=httpx.MockTransport(self.handler)),
                          poll_interval=0.01)
            for i in range(servers)
        ])


class FakeTeam:
    """Deterministic stand-in for the gpt-6-astra creative agents."""

    def __init__(self):
        self.calls: list[str] = []
        self.images: list[bytes | None] = []

    async def enhance(self, prompt: str, duration_seconds: float, image: bytes | None = None) -> CreativeBrief:
        self.calls.append("enhance")
        self.images.append(image)
        return CreativeBrief(
            title="The Last Lighthouse", logline=prompt, visual_style="35mm film, teal and amber",
            setting="Breton island", tone="melancholic", narration_style="calm documentary",
            narration_language="en-US",
            characters=[Character(name="Yann", visual_description="70-year-old man, white beard, yellow raincoat")],
            reference_notes="An old man in a yellow raincoat on a pier" if image else "",
        )

    async def outline(self, brief: CreativeBrief, total_shots: int, clip_seconds: float) -> StoryOutline:
        self.calls.append("outline")
        first = total_shots // 2
        # Labelled like a screenplay on purpose, as real LLMs sometimes do: the pipeline must strip the labels.
        return StoryOutline(scenes=[
            SceneOutline(title="Dawn", summary="s1", narration="Narrator: The island wakes up.", shot_count=first),
            SceneOutline(title="Storm", summary="s2", narration="**Yann (V.O.):** \"The storm comes.\"",
                         shot_count=total_shots - first),
        ])

    async def write_shots(self, brief, scene, scene_index, total_scenes, model, keyframes=False) -> list[Shot]:
        self.calls.append(f"shots-{scene_index}" + ("-keyframes" if keyframes else ""))
        return fit_shot_count(
            [Shot(prompt=f"{scene.title} shot {i}",
                  keyframe_prompt=f"Keep the man from image 1, {scene.title} frame {i}" if keyframes else None)
             for i in range(scene.shot_count)],
            scene.shot_count)


class FakeNarrator:
    def __init__(self, seconds: float = 3.0):
        self.seconds = seconds
        self.texts: list[str] = []

    async def synthesize(self, text: str, dest: Path, voice: str | None = None, language: str = "en-US") -> Path:
        self.texts.append(text)
        dest.parent.mkdir(parents=True, exist_ok=True)
        return make_wav(dest, self.seconds)


def tiny_model(base: VideoModel, frames: int, fps: int) -> VideoModel:
    """Same model/workflow, but tiny clips so the tests run fast."""
    from dataclasses import replace

    return replace(base, frames=frames, fps=fps)
