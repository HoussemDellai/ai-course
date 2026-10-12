"""Linux/ACA local draw.io CLI adapter, without Docker or a Docker socket.

Build from project root:
docker build -f app/drawio_runtime/Dockerfile.education -t education-video-platform app
DRAWIO_EXPORT_COMMAND: ["python","/app/drawio_runtime/export_native.py"]
Native draw.io, bundled stencil/icon assets and DejaVu fonts are installed by
that opt-in image. DRAWIO_RUNTIME_DIR must be on the container's Linux-local
filesystem, not a Windows/Azure Files bind mount: Chromium mmap fails there.
A 100-second deadline terminates the entire owned process
group, including Electron and Xvfb; the backend's outer deadline is 120 seconds.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

SUPPORTED = os.name == "posix"


def _validate(source: Path) -> None:
    if not source.is_file() or source.suffix != ".drawio" or source.stat().st_size > 1_000_000:
        raise ValueError("Export requires a bounded generated .drawio file")
    text = source.read_text(encoding="utf-8")
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("External entities and DTDs are prohibited")
    graph = ET.fromstring(text)
    if graph.tag != "mxGraphModel":
        raise ValueError("Export accepts only generated uncompressed mxGraphModel XML")
    allowed = {"mxGraphModel", "root", "mxCell", "mxGeometry"}
    for element in graph.iter():
        if element.tag not in allowed:
            raise ValueError("Unsupported element in generated diagram")
        style = element.get("style", "")
        if re.search(r"(?i)(https?:|file:|data:|javascript:|<|>)", style):
            raise ValueError("External assets or executable style content are prohibited")
        pairs = dict(part.split("=", 1) for part in style.split(";") if "=" in part)
        if pairs.get("html", "0") != "0":
            raise ValueError("Generated diagram labels must use literal text, not HTML")
        asset = pairs.get("image")
        if asset is not None and (
            ".." in asset or not re.fullmatch(r"img/lib/[A-Za-z0-9_./-]+\.(?:svg|png)", asset)
        ):
            raise ValueError("Only bundled native icon assets are permitted")


def _terminate(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true", required=True)
    parser.add_argument("--format", choices=["png"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--border", choices=["0"], required=True)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    if not SUPPORTED:
        parser.error("Native export requires Linux with draw.io Desktop and Xvfb installed")
    source, dest = args.input.resolve(), args.output.resolve()
    if source.parent != dest.parent or dest.suffix != ".png":
        parser.error("Input and PNG output must share the artifact directory")
    if not (16 <= args.width <= 7680 and 16 <= args.height <= 7680):
        parser.error("Unsupported export dimensions")
    try:
        _validate(source)
    except (ValueError, OSError, ET.ParseError) as exc:
        parser.error(str(exc))
    command = [
        # A container-local deadline also survives abrupt cancellation of this
        # Python wrapper by the orchestrator; no abandoned Electron processes.
        "timeout", "--signal=TERM", "--kill-after=5", "90",
        "xvfb-run", "-a", "drawio", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
        "--disable-update", "--timeout", "60",
        "--export", "--format", "png", "--output", str(dest),
        "--width", str(args.width), "--height", str(args.height), "--border", "0", str(source),
    ]
    runtime_root = Path(os.environ.get("DRAWIO_RUNTIME_DIR", str(source.parent))).resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_home = runtime_root / f".drawio-native-{uuid.uuid4().hex}"
    runtime_home.mkdir(mode=0o700)
    try:
        environment = dict(os.environ, HOME=str(runtime_home), TMPDIR=str(runtime_home))
        proc = subprocess.Popen(command, start_new_session=True, env=environment)
        try:
            code = proc.wait(timeout=100)
            if code:
                raise subprocess.CalledProcessError(code, command)
        except BaseException:
            _terminate(proc)
            dest.unlink(missing_ok=True)
            raise
        if not dest.is_file() or not dest.stat().st_size:
            raise RuntimeError("Native draw.io export produced no PNG")
    finally:
        shutil.rmtree(runtime_home)


if __name__ == "__main__":
    main()
