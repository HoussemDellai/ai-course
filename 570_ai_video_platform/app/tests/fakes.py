from __future__ import annotations

import re
import shutil
import subprocess
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from video_platform.agents import fit_music_cues, fit_shot_count
from video_platform.comfyui import ComfyUIClient, ComfyUIPool
from video_platform.schemas import (
    CreativeBrief, Character, Continuity, MusicCue, MusicPlan, NaturalSceneOutline, SceneOutline, Shot, StoryOutline,
)
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


def make_flac(path: Path, seconds: float) -> Path:
    """Stereo 32 kHz FLAC, like MiniMax Music 3's SaveAudio output."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=frequency=330:duration={seconds}", "-ar", "32000", "-ac", "2", str(path)], check=True)
    return path


class FakeComfy:
    """In-memory ComfyUI HTTP API (/prompt, /history, /view, /upload/image, /queue).

    SeedVR2 prompts are rendered for real with ffmpeg (the uploaded clip scaled by the workflow's multiplier,
    keeping its frames, fps and audio), so the tests check actual output sizes and durations."""

    def __init__(self, clip: Path | None = None, fail_first: int = 0, music: Path | None = None,
                 fail_upscale: bool = False):
        self.clip_bytes = clip.read_bytes() if clip else b"fake-mp4"
        self.image_bytes = make_png()
        self.music_bytes = music.read_bytes() if music else b"fake-flac"
        self.submitted: list[dict] = []
        self.uploads: list[tuple[str, str, str]] = []  # (server, subfolder, filename)
        self.uploaded: dict[str, bytes] = {}  # "subfolder/filename" -> content
        self.image_prompts: set[str] = set()
        self.audio_prompts: set[str] = set()
        self.upscale_prompts: dict[str, tuple[str, float]] = {}  # prompt id -> (input file, scale)
        self.upscaled: dict[str, bytes] = {}
        self.fail_first = fail_first
        self.fail_upscale = fail_upscale
        self.failed: set[str] = set()

    def _upscale(self, pid: str) -> bytes:
        if pid not in self.upscaled:
            import tempfile

            name, scale = self.upscale_prompts[pid]
            with tempfile.TemporaryDirectory() as tmp:
                src, dest = Path(tmp) / "in.mp4", Path(tmp) / "out.mp4"
                src.write_bytes(self.uploaded[name])
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf",
                                f"scale=trunc(iw*{scale}/2)*2:trunc(ih*{scale}/2)*2", "-c:v", "libx264",
                                "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dest)], check=True)
                self.upscaled[pid] = dest.read_bytes()
        return self.upscaled[pid]

    def handler(self, request: httpx.Request) -> httpx.Response:
        import json

        if request.method == "POST" and request.url.path == "/upload/image":
            body = request.content.decode("latin-1")
            filename = re.search(r'name="image"; filename="([^"]+)"', body).group(1)
            subfolder = re.search(r'name="subfolder"\r\n\r\n([^\r]*)\r\n', body).group(1)
            self.uploads.append((request.url.host, subfolder, filename))
            boundary = request.headers["content-type"].split("boundary=", 1)[1].encode()
            part = next(p for p in request.content.split(b"--" + boundary) if b'name="image"' in p.split(b"\r\n\r\n")[0])
            self.uploaded[f"{subfolder}/{filename}"] = part.split(b"\r\n\r\n", 1)[1].removesuffix(b"\r\n")
            return httpx.Response(200, json={"name": filename, "subfolder": subfolder, "type": "input"})
        if request.method == "POST" and request.url.path == "/prompt":
            workflow = json.loads(request.content)["prompt"]
            self.submitted.append(workflow)
            pid = f"p{len(self.submitted)}"
            if any(n["class_type"] == "SaveImage" for n in workflow.values()):
                self.image_prompts.add(pid)
            if any(n["class_type"] == "SaveAudio" for n in workflow.values()):
                self.audio_prompts.add(pid)
            if any(n["class_type"] == "SeedVR2Preprocess" for n in workflow.values()):
                video = next(n["inputs"]["file"] for n in workflow.values() if n["class_type"] == "LoadVideo")
                scale = next(n["inputs"]["resize_type.multiplier"] for n in workflow.values()
                             if n["class_type"] == "ResizeImageMaskNode")
                self.upscale_prompts[pid] = (video, scale)
                if self.fail_upscale:
                    self.failed.add(pid)
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
            elif pid in self.audio_prompts:
                outputs = {"9": {"audio": [{"filename": f"{pid}_00001_.flac", "subfolder": "aivideo",
                                            "type": "output"}]}}
            elif pid in self.upscale_prompts:
                # Like ComfyUI: LoadVideo previews its input (type "input"), listed before SaveVideo's output.
                subfolder, _, name = self.upscale_prompts[pid][0].rpartition("/")
                outputs = {"1": {"images": [{"filename": name, "subfolder": subfolder, "type": "input"}],
                                 "animated": [True]},
                           "15": {"images": [{"filename": f"{pid}.mp4", "subfolder": "aivideo", "type": "output"}],
                                  "animated": [True]}}
            else:
                outputs = {"16": {"images": [{"filename": f"{pid}.mp4", "subfolder": "aivideo", "type": "output"}],
                                  "animated": [True]}}
            return httpx.Response(200, json={pid: {
                "outputs": outputs, "status": {"status_str": "success", "completed": True, "messages": []}}})
        if request.method == "GET" and request.url.path == "/view":
            if request.url.params.get("filename", "").endswith(".png"):
                return httpx.Response(200, content=self.image_bytes)
            if request.url.params.get("filename", "").endswith(".flac"):
                return httpx.Response(200, content=self.music_bytes)
            pid = request.url.params.get("filename", "").removesuffix(".mp4")
            if request.url.params.get("type") == "input":
                key = f"{request.url.params.get('subfolder', '')}/{request.url.params.get('filename', '')}"
                return httpx.Response(200, content=self.uploaded[key])
            if pid in self.upscale_prompts:
                return httpx.Response(200, content=self._upscale(pid))
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
        self.neighbors: list[str] = []
        self.music_durations: list[float] = []

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

    async def outline(self, brief: CreativeBrief, total_shots: int, clip_seconds: float,
                      naturalistic: bool = False) -> StoryOutline:
        self.calls.append("outline")
        first = total_shots // 2
        # Labelled like a screenplay on purpose, as real LLMs sometimes do: the pipeline must strip the labels.
        outline = StoryOutline(scenes=[
            SceneOutline(title="Dawn", summary="s1", narration="Narrator: The island wakes up.", shot_count=first),
            SceneOutline(title="Storm", summary="s2", narration="**Yann (V.O.):** \"The storm comes.\"",
                         shot_count=total_shots - first),
        ])
        if naturalistic:
            outline.scenes = [NaturalSceneOutline(
                **s.model_dump(), continuity=Continuity(
                    wardrobe_and_props="yellow raincoat, lantern", lighting_and_location="dawn, pier",
                    screen_direction="left to right", start_state="standing", end_state="walking",
                ),
            ) for s in outline.scenes]
        return outline

    async def write_shots(self, brief, scene, scene_index, total_scenes, model, keyframes=False,
                          naturalistic=False, neighbors="", vertical=False) -> list[Shot]:
        self.calls.append(f"shots-{scene_index}" + ("-keyframes" if keyframes else "")
                          + ("-vertical" if vertical else ""))
        self.neighbors.append(neighbors)
        return fit_shot_count(
            [Shot(prompt=f"{scene.title} shot {i}",
                  keyframe_prompt=f"Keep the man from image 1, {scene.title} frame {i}" if keyframes else None)
             for i in range(scene.shot_count)],
            scene.shot_count)

    async def shorten_narration(self, brief, text, measured_seconds, target_seconds) -> str:
        self.calls.append("shorten")
        return "The island wakes." if "island" in text else "A storm comes."

    async def score(self, brief, scenes, durations) -> MusicPlan:
        self.calls.append("score")
        self.music_durations = list(durations)
        return fit_music_cues(MusicPlan(theme="solo cello and soft piano, D minor, 60-70 BPM", scenes=[
            MusicCue(caption=f"Global Metadata: ambient score for {s.title}.\nArrangement: cello, piano.")
            for s in scenes
        ]), len(scenes))


class FakeNarrator:
    def __init__(self, seconds: float = 3.0):
        self.seconds = seconds
        self.texts: list[str] = []
        self.deliveries: list = []

    async def validate(self, voice, language, delivery) -> None:
        pass

    async def synthesize(self, text: str, dest: Path, voice: str | None = None, language: str = "en-US",
                          delivery=None) -> Path:
        self.texts.append(text)
        self.deliveries.append(delivery)
        dest.parent.mkdir(parents=True, exist_ok=True)
        return make_wav(dest, self.seconds)


def tiny_model(base: VideoModel, frames: int, fps: int) -> VideoModel:
    """Same model/workflow, but tiny clips so the tests run fast."""
    from dataclasses import replace

    return replace(base, frames=frames, fps=fps)
