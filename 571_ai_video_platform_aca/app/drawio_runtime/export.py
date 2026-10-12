"""Host-side draw.io CLI-compatible Docker export wrapper.

Build: docker build -f Dockerfile.export -t education-drawio-export:32.4.1 .
Configure DRAWIO_EXPORT_COMMAND as a JSON argv array naming Python and this file.
Only this wrapper's fixed pinned image is run; input/output share one artifact
directory. Fonts (DejaVu) and native stencils are bundled; runtime has no network.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import uuid
from pathlib import Path


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
    source, dest = args.input.resolve(), args.output.resolve()
    if source.suffix != ".drawio" or not source.is_file() or source.parent != dest.parent:
        parser.error("Export requires a local .drawio and output in the same artifact directory")
    if not (16 <= args.width <= 7680 and 16 <= args.height <= 7680):
        parser.error("Unsupported export dimensions")
    container_name = f"education-drawio-{uuid.uuid4().hex}"
    uid, gid = (os.getuid(), os.getgid()) if hasattr(os, "getuid") else (10001, 10001)
    command = [
        "docker", "run", "--rm", "--name", container_name, "--network=none", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--pids-limit=256", "--memory=2g", "--shm-size=512m",
        "--mount", f"type=bind,source={source.parent},target=/work",
        "--env", "HOME=/home/drawio",
        "--tmpfs", f"/home/drawio:rw,uid={uid},gid={gid},mode=700",
    ]
    if hasattr(os, "getuid"):
        command += ["--user", f"{os.getuid()}:{os.getgid()}"]
    command += [
        "education-drawio-export:32.4.1",
        "--disable-update", "--timeout", "60",
        "--export", "--format", "png", "--output", f"/work/{dest.name}",
        "--width", str(args.width), "--height", str(args.height), "--border", "0",
        f"/work/{source.name}",
    ]
    try:
        subprocess.run(command, check=True, timeout=100)
    finally:
        subprocess.run(["docker", "rm", "--force", container_name], timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
