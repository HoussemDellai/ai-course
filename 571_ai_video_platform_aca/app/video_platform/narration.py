from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from . import media
from .agents import CreativeTeam
from .schemas import CreativeBrief, NarrationDelivery
from .speech import Narrator, SpeechError
from .storage import ArtifactStore, read_json, write_json

log = logging.getLogger(__name__)
MAX_SYNTHESES = 3
LEAD_IN = 0.4
TAIL = 0.6


def fingerprint(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class Take(BaseModel):
    text: str
    duration: float | None = None
    sha256: str | None = None


class FitRecord(BaseModel):
    takes: list[Take] = Field(default_factory=list, max_length=MAX_SYNTHESES)
    accepted: int | None = None


async def fit_narration(
    *, team: CreativeTeam, narrator: Narrator, store: ArtifactStore, job_id: str, work_dir: Path,
    scene_index: int, text: str, brief: CreativeBrief, voice: str, delivery: NarrationDelivery,
    budget: float,
) -> tuple[Path, str, float, bool]:
    """Content-addressed audio and a write-ahead attempt journal; retries share the three-take budget."""
    target = budget - LEAD_IN - TAIL
    if target <= 0:
        raise SpeechError(f"Scene {scene_index + 1} is too short for narration and breathing room")
    dependency = fingerprint({
        "version": 1, "text": text, "language": brief.narration_language, "style": brief.narration_style,
        "voice": voice, "delivery": delivery.model_dump(), "target": target,
    })
    prefix = f"narration/natural-v1/scene_{scene_index:03d}/{dependency}"
    record_name = f"{prefix}/takes.json"
    saved = await read_json(store, job_id, record_name)
    record = FitRecord.model_validate(saved) if saved is not None else FitRecord()

    async def audio(i: int) -> Path | None:
        name = f"{prefix}/take_{i}.wav"
        local = work_dir / name
        # Only published audio is reusable; a local file can be an interrupted SDK write.
        if not await store.download(job_id, name, local):
            return None
        digest = hashlib.sha256(local.read_bytes()).hexdigest()
        take = record.takes[i]
        if take.sha256 is not None and digest != take.sha256:
            raise SpeechError(f"Scene {scene_index + 1} narration checksum mismatch; create a new job")
        duration, has_audio = await media.probe(local)
        if not has_audio or duration <= 0:
            raise SpeechError(f"Scene {scene_index + 1} narration contains no usable audio")
        take.duration, take.sha256 = duration, digest
        return local

    if record.accepted is not None:
        if not 0 <= record.accepted < len(record.takes):
            raise SpeechError("Invalid accepted narration take in saved journal")
        local = await audio(record.accepted)
        take = record.takes[record.accepted]
        if local is None or take.duration is None or take.duration > target:
            raise SpeechError(f"Scene {scene_index + 1} accepted narration is missing or no longer fits")
        return local, take.text, take.duration, True

    # Recover a synthesis uploaded immediately before a restart.
    if record.takes:
        last = len(record.takes) - 1
        local = await audio(last)
        take = record.takes[last]
        if local is not None and take.duration is not None and take.duration <= target:
            record.accepted = last
            await write_json(store, job_id, record_name, record.model_dump())
            return local, take.text, take.duration, True

    while len(record.takes) < MAX_SYNTHESES:
        candidate = record.takes[-1].text if record.takes else text
        if record.takes:
            previous = record.takes[-1]
            if previous.duration is not None and previous.duration > target:
                log.warning("Scene %d narration is %.3fs; correcting to fit %.3fs (take %d/%d)",
                            scene_index + 1, previous.duration, target, len(record.takes) + 1, MAX_SYNTHESES)
                candidate = await team.shorten_narration(brief, previous.text, previous.duration, target)
            else:
                log.warning("Scene %d synthesis was interrupted; consuming the next reserved attempt",
                            scene_index + 1)
        if not candidate.strip():
            raise SpeechError(f"Scene {scene_index + 1} narration correction returned no spoken words")
        i = len(record.takes)
        record.takes.append(Take(text=candidate))
        await write_json(store, job_id, record_name, record.model_dump())
        name = f"{prefix}/take_{i}.wav"
        local = work_dir / name
        await narrator.synthesize(candidate, local, voice=voice, language=brief.narration_language,
                                  delivery=delivery)
        duration, has_audio = await media.probe(local)
        if not has_audio or duration <= 0:
            raise SpeechError(f"Scene {scene_index + 1} synthesis produced no usable audio")
        take = record.takes[i]
        take.duration = duration
        take.sha256 = hashlib.sha256(local.read_bytes()).hexdigest()
        await write_json(store, job_id, record_name, record.model_dump())
        await store.upload(job_id, name, local)
        if duration <= target:
            record.accepted = i
        await write_json(store, job_id, record_name, record.model_dump())
        if record.accepted is not None:
            return local, candidate, duration, False

    raise SpeechError(
        f"Scene {scene_index + 1} narration did not fit {target:.3f}s within {MAX_SYNTHESES} syntheses "
        "(two corrections). No GPU rendering started. Create a new job with shorter narration or longer scenes."
    )
