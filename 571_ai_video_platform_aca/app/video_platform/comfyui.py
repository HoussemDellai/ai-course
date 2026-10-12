from __future__ import annotations

import asyncio
import copy
import json
import logging
import mimetypes
import random
import re
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx

from .video_models import KEYFRAME_WORKFLOW, MUSIC_WORKFLOW, UPSCALE_WORKFLOW, VideoModel

log = logging.getLogger(__name__)

_PLACEHOLDER = re.compile(r"^\{\{(\w+)\}\}$")
VIDEO_EXTENSIONS = (".mp4", ".webm", ".mkv", ".mov")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
AUDIO_EXTENSIONS = (".flac", ".wav", ".mp3", ".opus")

SubmittedCallback = Callable[[str, str], Awaitable[None]]  # (server base URL, prompt_id)


class ComfyUIError(RuntimeError):
    pass


def load_workflow(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fill_workflow(template: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Replaces every input value of the form "{{name}}" with params[name], keeping the param's JSON type."""
    workflow = copy.deepcopy(template)
    missing: set[str] = set()
    for node in workflow.values():
        inputs = node.get("inputs", {})
        for key, value in inputs.items():
            if isinstance(value, str) and (m := _PLACEHOLDER.match(value)):
                name = m.group(1)
                if name in params:
                    inputs[key] = params[name]
                else:
                    missing.add(name)
    if missing:
        raise ValueError(f"Missing workflow parameters: {sorted(missing)}")
    return workflow


def find_outputs(history_entry: dict[str, Any], extensions: tuple[str, ...]) -> list[dict[str, str]]:
    """Returns the saved files ({filename, subfolder, type}) with one of the extensions listed in a /history entry.

    Files the workflow saved (type "output") come first: loader nodes such as LoadVideo also report a preview of
    their input file (type "input"), which must never be taken for the result."""
    files: list[dict[str, str]] = []
    for node_output in history_entry.get("outputs", {}).values():
        for items in node_output.values():
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and str(item.get("filename", "")).lower().endswith(extensions):
                    files.append(item)
    return sorted(files, key=lambda f: f.get("type", "output") != "output")


def find_video_outputs(history_entry: dict[str, Any]) -> list[dict[str, str]]:
    return find_outputs(history_entry, VIDEO_EXTENSIONS)


class ComfyUIClient:
    def __init__(self, base_url: str, http: httpx.AsyncClient | None = None, poll_interval: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=300.0))
        self.poll_interval = poll_interval
        self.client_id = str(uuid.uuid4())

    async def aclose(self) -> None:
        await self._http.aclose()

    async def submit(self, workflow: dict[str, Any]) -> str:
        r = await self._http.post(f"{self.base_url}/prompt", json={"prompt": workflow, "client_id": self.client_id})
        if r.status_code != 200:
            raise ComfyUIError(f"ComfyUI rejected the workflow ({r.status_code}): {r.text[:2000]}")
        body = r.json()
        if body.get("node_errors"):
            raise ComfyUIError(f"ComfyUI node errors: {json.dumps(body['node_errors'])[:2000]}")
        return body["prompt_id"]

    async def wait(self, prompt_id: str, timeout: float) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            r = await self._http.get(f"{self.base_url}/history/{prompt_id}")
            r.raise_for_status()
            entry = r.json().get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ComfyUIError(f"ComfyUI execution failed: {json.dumps(status.get('messages', []))[:2000]}")
                if status.get("completed", True) and entry.get("outputs"):
                    return entry
            if loop.time() > deadline:
                await self.interrupt()
                raise ComfyUIError(f"Timed out after {timeout:.0f}s waiting for prompt {prompt_id}")
            await asyncio.sleep(self.poll_interval)

    async def interrupt(self) -> None:
        try:
            await self._http.post(f"{self.base_url}/interrupt")
        except httpx.HTTPError:
            pass

    async def download(self, file: dict[str, str], dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        params = {"filename": file["filename"], "subfolder": file.get("subfolder", ""), "type": file.get("type", "output")}
        tmp = dest.with_suffix(dest.suffix + ".part")
        async with self._http.stream("GET", f"{self.base_url}/view", params=params) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                async for chunk in r.aiter_bytes(1 << 20):
                    f.write(chunk)
        tmp.replace(dest)
        return dest

    async def upload_image(self, path: Path, subfolder: str) -> str:
        """Uploads an input file (POST /upload/image, also used for videos) and returns the value for a
        LoadImage / LoadVideo node."""
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        files = {"image": (path.name, path.read_bytes(), media_type)}
        data = {"type": "input", "subfolder": subfolder, "overwrite": "true"}
        r = await self._http.post(f"{self.base_url}/upload/image", files=files, data=data)
        if r.status_code != 200:
            raise ComfyUIError(f"ComfyUI rejected the upload of {path.name} ({r.status_code}): {r.text[:500]}")
        body = r.json()
        return f"{body['subfolder']}/{body['name']}" if body.get("subfolder") else body["name"]

    async def prompt_state(self, prompt_id: str) -> str:
        """'done' (in history), 'queued' (pending or running) or 'unknown' (e.g. ComfyUI restarted)."""
        r = await self._http.get(f"{self.base_url}/history/{prompt_id}")
        r.raise_for_status()
        if r.json().get(prompt_id):
            return "done"
        r = await self._http.get(f"{self.base_url}/queue")
        r.raise_for_status()
        queue = r.json()
        for item in queue.get("queue_running", []) + queue.get("queue_pending", []):
            if len(item) > 1 and item[1] == prompt_id:
                return "queued"
        return "unknown"

    async def collect(self, prompt_id: str, dest: Path, timeout: float,
                      extensions: tuple[str, ...] = VIDEO_EXTENSIONS) -> Path:
        entry = await self.wait(prompt_id, timeout)
        outputs = find_outputs(entry, extensions)
        if not outputs:
            kind = "a video" if extensions == VIDEO_EXTENSIONS else "an image"
            raise ComfyUIError(f"Prompt {prompt_id} finished without {kind} output")
        return await self.download(outputs[0], dest)

    async def generate(
        self, workflow: dict[str, Any], dest: Path, timeout: float, on_submitted: SubmittedCallback | None = None,
        extensions: tuple[str, ...] = VIDEO_EXTENSIONS,
    ) -> Path:
        prompt_id = await self.submit(workflow)
        if on_submitted:
            await on_submitted(self.base_url, prompt_id)
        return await self.collect(prompt_id, dest, timeout, extensions)


class ComfyUIPool:
    """Spreads clips over one or more ComfyUI servers (each server renders one clip at a time)."""

    def __init__(self, clients: list[ComfyUIClient]):
        if not clients:
            raise ValueError("At least one ComfyUI server is required")
        self._clients = clients
        self._busy: set[str] = set()
        self._cond = asyncio.Condition()

    @classmethod
    def from_urls(cls, urls: list[str]) -> ComfyUIPool:
        return cls([ComfyUIClient(u) for u in urls])

    @property
    def size(self) -> int:
        return len(self._clients)

    def _pick(self, preferred: str | None) -> ComfyUIClient | None:
        if preferred and any(c.base_url == preferred for c in self._clients):
            return next((c for c in self._clients if c.base_url == preferred and c.base_url not in self._busy), None)
        return next((c for c in self._clients if c.base_url not in self._busy), None)

    @asynccontextmanager
    async def acquire(self, preferred: str | None = None):
        async with self._cond:
            await self._cond.wait_for(lambda: self._pick(preferred) is not None)
            client = self._pick(preferred)
            self._busy.add(client.base_url)
        try:
            yield client
        finally:
            async with self._cond:
                self._busy.discard(client.base_url)
                self._cond.notify_all()

    async def aclose(self) -> None:
        for c in self._clients:
            await c.aclose()

    async def generate_clip(
        self,
        model: VideoModel,
        prompt: str,
        seed: int,
        dest: Path,
        filename_prefix: str,
        timeout: float,
        retries: int,
        resume: dict[str, str] | None = None,
        on_submitted: SubmittedCallback | None = None,
        start_image: Path | None = None,
        upload_subfolder: str = "aivideo",
        width: int | None = None,
        height: int | None = None,
    ) -> Path:
        """Text-to-video, or image-to-video from start_image (a keyframe) when given.

        width/height default to the model's native landscape size (vertical videos pass it swapped)."""
        params = {
            "prompt": prompt,
            "negative_prompt": model.negative_prompt,
            "width": width or model.width,
            "height": height or model.height,
            "length": model.frames,
            "fps": float(model.fps),
            "filename_prefix": filename_prefix,
        }
        template = model.i2v_workflow_path if start_image else model.workflow_path
        return await self._render(template, params, seed, dest, timeout, retries, resume, on_submitted,
                                  VIDEO_EXTENSIONS, start_image, upload_subfolder, "Clip")

    async def generate_keyframe(
        self,
        reference: Path,
        prompt: str,
        seed: int,
        width: int,
        height: int,
        dest: Path,
        filename_prefix: str,
        timeout: float,
        retries: int,
        resume: dict[str, str] | None = None,
        on_submitted: SubmittedCallback | None = None,
        upload_subfolder: str = "aivideo",
    ) -> Path:
        """Redraws the reference photo into a shot's first frame with Qwen-Image-Edit."""
        params = {"prompt": prompt, "width": width, "height": height, "filename_prefix": filename_prefix}
        return await self._render(KEYFRAME_WORKFLOW, params, seed, dest, timeout, retries, resume, on_submitted,
                                  IMAGE_EXTENSIONS, reference, upload_subfolder, "Keyframe")

    async def generate_music(
        self,
        caption: str,
        lyrics: str,
        seconds: float,
        seed: int,
        dest: Path,
        filename_prefix: str,
        timeout: float,
        retries: int,
        resume: dict[str, str] | None = None,
        on_submitted: SubmittedCallback | None = None,
    ) -> Path:
        """Renders a piece of music (MiniMax Music 3) of at most `seconds` seconds."""
        params = {"caption": caption, "lyrics": lyrics, "seconds": float(seconds), "filename_prefix": filename_prefix}
        return await self._render(MUSIC_WORKFLOW, params, seed, dest, timeout, retries, resume, on_submitted,
                                  AUDIO_EXTENSIONS, None, "aivideo", "Music")

    async def upscale_video(
        self,
        source: Path,
        scale: float,
        seed: int,
        dest: Path,
        filename_prefix: str,
        timeout: float,
        retries: int,
        resume: dict[str, str] | None = None,
        on_submitted: SubmittedCallback | None = None,
        upload_subfolder: str = "aivideo",
    ) -> Path:
        """Upscales a clip by `scale` with SeedVR2, keeping its frames, fps and audio."""
        params = {"scale": float(scale), "filename_prefix": filename_prefix}
        return await self._render(UPSCALE_WORKFLOW, params, seed, dest, timeout, retries, resume, on_submitted,
                                  VIDEO_EXTENSIONS, source, upload_subfolder, "SeedVR2 upscale", input_key="video")

    async def _render(
        self,
        template_path: Path,
        params: dict[str, Any],
        seed: int,
        dest: Path,
        timeout: float,
        retries: int,
        resume: dict[str, str] | None,
        on_submitted: SubmittedCallback | None,
        extensions: tuple[str, ...],
        input_image: Path | None,
        upload_subfolder: str,
        label: str,
        input_key: str = "image",
    ) -> Path:
        # A previous run of the orchestrator may have submitted this render already: reattach to it
        # instead of paying for the same GPU work twice.
        if resume and resume.get("server") and resume.get("prompt_id"):
            async with self.acquire(preferred=resume["server"]) as client:
                if client.base_url == resume["server"]:
                    try:
                        if await client.prompt_state(resume["prompt_id"]) != "unknown":
                            return await client.collect(resume["prompt_id"], dest, timeout, extensions)
                    except (ComfyUIError, httpx.HTTPError) as e:
                        log.warning("Could not reattach to prompt %s: %s", resume["prompt_id"], e)

        template = load_workflow(template_path)
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            attempt_params = dict(params, seed=seed if attempt == 0 else random.randint(0, 2**48))
            async with self.acquire() as client:
                try:
                    if input_image is not None:
                        # Every server has its own input folder: upload to the one that renders this attempt.
                        attempt_params[input_key] = await client.upload_image(input_image, upload_subfolder)
                    workflow = fill_workflow(template, attempt_params)
                    return await client.generate(workflow, dest, timeout, on_submitted, extensions)
                except (ComfyUIError, httpx.HTTPError) as e:
                    # Some httpx errors (timeouts, dropped connections) have an empty message: keep the type.
                    last_error = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                    log.warning("%s %s failed on %s (attempt %d): %s", label, dest.name, client.base_url,
                                attempt + 1, last_error)
        raise ComfyUIError(f"{label} {dest.name} failed after {retries + 1} attempts: {last_error}")
