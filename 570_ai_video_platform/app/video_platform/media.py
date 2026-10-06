from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

VIDEO_ENCODE = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
AUDIO_ENCODE = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


class MediaError(RuntimeError):
    pass


async def run(*args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise MediaError(f"{args[0]} failed ({proc.returncode}): {err.decode(errors='replace')[-2000:]}")
    return out.decode(errors="replace")


async def probe(path: Path) -> tuple[float, bool]:
    """Returns (duration in seconds, has an audio stream)."""
    out = await run(
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)
    )
    info = json.loads(out)
    duration = float(info.get("format", {}).get("duration", 0.0))
    has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    return duration, has_audio


async def normalize_clip(
    src: Path, dest: Path, width: int, height: int, fps: int, keep_audio: bool, audio_volume: float
) -> Path:
    """Scales/pads a clip to the output format and gives it a stereo AAC track (ambient audio or silence)."""
    duration, has_audio = await probe(src)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},setsar=1"
    )
    args = ["ffmpeg", "-y", "-i", str(src)]
    if keep_audio and has_audio:
        # Pad/trim the ambient audio to the exact clip length so scenes stay in sync after concatenation.
        args += ["-filter_complex",
                 f"[0:v]{vf}[v];[0:a]asetpts=PTS-STARTPTS,volume={audio_volume},aresample=48000,"
                 f"apad=whole_dur={duration:.3f},atrim=0:{duration:.3f}[a]"]
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        args += ["-filter_complex", f"[0:v]{vf}[v];[1:a]anull[a]"]
    args += ["-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}", *VIDEO_ENCODE, *AUDIO_ENCODE, str(dest)]
    dest.parent.mkdir(parents=True, exist_ok=True)
    await run(*args)
    return dest


async def concat(parts: list[Path], dest: Path) -> Path:
    """Concatenates files that share the same codecs/format (stream copy, no re-encode)."""
    if not parts:
        raise MediaError("Nothing to concatenate")
    dest.parent.mkdir(parents=True, exist_ok=True)
    list_file = dest.with_suffix(".txt")
    list_file.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    await run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy",
              "-movflags", "+faststart", str(dest))
    list_file.unlink(missing_ok=True)
    return dest


async def mix_narration(video: Path, narration: Path | None, dest: Path, lead_in: float = 0.4, tail: float = 0.6) -> Path:
    """Lays the voice-over on top of the scene audio. Freezes the last frame if the narration is longer."""
    video_len, _ = await probe(video)
    if narration is None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        await run("ffmpeg", "-y", "-i", str(video), "-c", "copy", str(dest))
        return dest
    narration_len, _ = await probe(narration)
    total = max(video_len, lead_in + narration_len + tail)
    pad = max(0.0, total - video_len)
    delay_ms = int(lead_in * 1000)
    fc = (
        f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.3f}[v];"
        f"[0:a]apad=whole_dur={total:.3f}[bg];"
        f"[1:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay_ms}|{delay_ms},"
        f"apad=whole_dur={total:.3f}[nar];"
        f"[bg][nar]amix=inputs=2:duration=longest:normalize=0,atrim=0:{total:.3f}[a]"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    await run("ffmpeg", "-y", "-i", str(video), "-i", str(narration), "-filter_complex", fc,
              "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}", *VIDEO_ENCODE, *AUDIO_ENCODE, str(dest))
    return dest
