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


async def video_duration(path: Path) -> float:
    out = await run("ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                    "stream=duration", "-of", "json", str(path))
    streams = json.loads(out).get("streams", [])
    if not streams or float(streams[0].get("duration", 0)) <= 0:
        raise MediaError(f"Missing video duration: {path.name}")
    return float(streams[0]["duration"])


async def video_size(path: Path) -> tuple[int, int]:
    """(width, height) of the first video stream."""
    out = await run("ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                    "stream=width,height", "-of", "json", str(path))
    streams = json.loads(out).get("streams", [])
    if not streams or not streams[0].get("width") or not streams[0].get("height"):
        raise MediaError(f"Missing video size: {path.name}")
    return int(streams[0]["width"]), int(streams[0]["height"])


def fit_scale(width: int, height: int, box_width: int, box_height: int) -> float:
    """Largest factor that fits a width x height frame into the box without changing its aspect ratio."""
    return min(box_width / width, box_height / height)


async def normalize_clip(
    src: Path, dest: Path, width: int, height: int, fps: int, keep_audio: bool, audio_volume: float,
    naturalistic: bool = False, target_duration: float | None = None,
) -> Path:
    """Scales (lanczos, aspect ratio kept) and pads a clip to the output size, and gives it a stereo AAC track
    (ambient audio or silence)."""
    duration, has_audio = await probe(src)
    if naturalistic:
        if target_duration is None or target_duration <= 0:
            raise MediaError("Naturalistic normalization requires a positive frame-aligned duration")
        if await video_duration(src) + 0.000001 < target_duration:
            raise MediaError(f"Clip {src.name} is shorter than its planned duration; regenerate it")
        duration = target_duration
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},setsar=1"
    )
    args = ["ffmpeg", "-y", "-i", str(src)]
    finishing = ""
    if naturalistic:
        fade = min(0.04, duration / 2)
        finishing = (f",afade=t=in:d={fade:.6f},afade=t=out:st={duration - fade:.6f}:d={fade:.6f},"
                     "alimiter=limit=0.85:level=false:latency=true")
    if keep_audio and has_audio:
        # Pad/trim the ambient audio to the exact clip length so scenes stay in sync after concatenation.
        args += ["-filter_complex",
                 f"[0:v]{vf}[v];[0:a]asetpts=PTS-STARTPTS,volume={audio_volume},aresample=48000,"
                 f"apad=whole_dur={duration:.9f},atrim=0:{duration:.9f}{finishing}[a]"]
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        args += ["-filter_complex", f"[0:v]{vf}[v];[1:a]anull[a]"]
    args += ["-map", "[v]", "-map", "[a]", "-t", f"{duration:.9f}", *VIDEO_ENCODE, *AUDIO_ENCODE,
             "-movflags", "+faststart", str(dest)]
    dest.parent.mkdir(parents=True, exist_ok=True)
    await run(*args)
    return dest


async def concat(parts: list[Path], dest: Path, exact: bool = False) -> Path:
    """Concatenates files that share the same codecs/format (stream copy, no re-encode)."""
    if not parts:
        raise MediaError("Nothing to concatenate")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if exact:
        args, filters, inputs = ["ffmpeg", "-y"], [], []
        for i, path in enumerate(parts):
            duration = await video_duration(path)
            args += ["-i", str(path)]
            filters += [f"[{i}:v]setpts=PTS-STARTPTS[v{i}]",
                        f"[{i}:a]atrim=0:{duration:.9f},asetpts=PTS-STARTPTS[a{i}]"]
            inputs.append(f"[v{i}][a{i}]")
        filters.append("".join(inputs) + f"concat=n={len(parts)}:v=1:a=1[v][a]")
        await run(*args, "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]",
                  *VIDEO_ENCODE, *AUDIO_ENCODE, "-movflags", "+faststart", str(dest))
        return dest
    list_file = dest.with_suffix(".txt")
    list_file.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    await run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy",
              "-movflags", "+faststart", str(dest))
    list_file.unlink(missing_ok=True)
    return dest


async def mix_narration(
    video: Path, narration: Path | None, dest: Path, lead_in: float = 0.4, tail: float = 0.6,
    naturalistic: bool = False,
) -> Path:
    """Lays the voice-over on top of the scene audio. Freezes the last frame if the narration is longer."""
    video_len, _ = await probe(video)
    if narration is None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        await run("ffmpeg", "-y", "-i", str(video), "-c", "copy", "-movflags", "+faststart", str(dest))
        return dest
    narration_len, _ = await probe(narration)
    if naturalistic:
        video_len = await video_duration(video)
        if lead_in + narration_len + tail > video_len + 0.000001:
            raise MediaError("Narration exceeds the measured scene budget; naturalistic mode never freezes frames")
        delay_ms = int(lead_in * 1000)
        fc = (
            f"[0:a]apad=whole_dur={video_len:.9f},atrim=0:{video_len:.9f}[bg];"
            "[1:a]aresample=48000,aformat=channel_layouts=stereo,"
            "loudnorm=I=-18:TP=-3:LRA=7,aresample=48000,"
            f"adelay={delay_ms}|{delay_ms},apad=whole_dur={video_len:.9f},"
            f"atrim=0:{video_len:.9f},asplit=2[voice][control];"
            "[bg][control]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=300[ducked];"
            "[ducked][voice]amix=inputs=2:duration=first:normalize=0,"
            f"alimiter=limit=0.85:level=false:latency=true,atrim=0:{video_len:.9f}[a]"
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        await run("ffmpeg", "-y", "-i", str(video), "-i", str(narration), "-filter_complex", fc,
                  "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", *AUDIO_ENCODE,
                  "-t", f"{video_len:.9f}", "-movflags", "+faststart", str(dest))
        return dest
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
              "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}", *VIDEO_ENCODE, *AUDIO_ENCODE,
              "-movflags", "+faststart", str(dest))
    return dest


async def mix_music(video: Path, music: Path, dest: Path, volume: float, fade: float) -> Path:
    """Lays background music under a finished scene: faded in/out at the cuts, ducked under the scene's audio
    (narration, ambience), trimmed or padded to the exact scene length. The video stream is copied."""
    length = await video_duration(video)
    fade = max(0.0, min(fade, length / 3))
    fc = (
        f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={volume},atrim=0:{length:.9f},"
        f"asetpts=PTS-STARTPTS,afade=t=in:d={fade:.6f},afade=t=out:st={length - fade:.6f}:d={fade:.6f},"
        f"apad=whole_dur={length:.9f}[music];"
        f"[0:a]apad=whole_dur={length:.9f},atrim=0:{length:.9f},asplit=2[scene][control];"
        "[music][control]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=400[ducked];"
        "[scene][ducked]amix=inputs=2:duration=first:normalize=0,"
        f"alimiter=limit=0.85:level=false:latency=true,atrim=0:{length:.9f}[a]"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    await run("ffmpeg", "-y", "-i", str(video), "-i", str(music), "-filter_complex", fc,
              "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", *AUDIO_ENCODE, "-t", f"{length:.9f}",
              "-movflags", "+faststart", str(dest))
    return dest
