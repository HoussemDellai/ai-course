"""Generate a video from the command line, without the API.

    python generate.py "A documentary about bees" --minutes 0.5 --model wan22
    python generate.py "Her first trip to Japan" --image photo.jpg --minutes 0.5
"""

import argparse
import asyncio
import logging
from pathlib import Path

from video_platform.api import create_services
from video_platform.config import Settings
from video_platform.images import sanitize_image
from video_platform.jobs import JobManager
from video_platform.schemas import NarrationDelivery, Pronunciation, VideoRequest


def parse_request(argv: list[str] | None = None) -> tuple[VideoRequest, Path | None]:
    p = argparse.ArgumentParser()
    p.add_argument("prompt")
    p.add_argument("--minutes", type=float, default=5.0)
    p.add_argument("--model", default=None, help="wan22, ltx2 or hunyuan15")
    p.add_argument("--no-narration", action="store_true")
    p.add_argument("--naturalistic", action="store_true", help="opt in to continuity, measured narration and audio mixing")
    p.add_argument("--voice", help="Speech voice short name (default: configured TTS_VOICE)")
    p.add_argument("--speech-rate", type=int, default=None, help="delivery rate adjustment, -10 to 10 percent")
    p.add_argument("--sentence-pause-ms", type=int, default=None, help="sentence pause, 0 to 1000 ms (default: 180)")
    p.add_argument("--speech-style", help="style advertised by the selected voice; unsupported styles fail explicitly")
    p.add_argument("--pronounce", action="append", default=[], metavar="TEXT=ALIAS",
                   help="literal pronunciation substitution; may be repeated (maximum 20)")
    p.add_argument("--image", type=Path, default=None,
                   help="reference photo (PNG, JPEG or WebP) of a person or a scene to build the video from")
    args = p.parse_args(argv)
    pronunciations = []
    for value in args.pronounce:
        text, separator, alias = value.partition("=")
        if not separator:
            p.error("--pronounce requires TEXT=ALIAS")
        pronunciations.append(Pronunciation(text=text.strip(), alias=alias.strip()))
    explicit_delivery = any(v is not None for v in (args.speech_rate, args.sentence_pause_ms, args.speech_style))
    delivery = None
    if explicit_delivery or pronunciations:
        delivery = NarrationDelivery(
            rate_percent=args.speech_rate if args.speech_rate is not None else 0,
            sentence_pause_ms=args.sentence_pause_ms if args.sentence_pause_ms is not None else 180,
            style=args.speech_style, pronunciations=pronunciations,
        )
    return VideoRequest(
        prompt=args.prompt, duration_minutes=args.minutes, video_model=args.model,
        narration=not args.no_narration, voice=args.voice, naturalistic=args.naturalistic, delivery=delivery,
    ), args.image


async def main() -> None:
    request, image_path = parse_request()
    settings = Settings.from_env()
    image = sanitize_image(image_path.read_bytes(), settings.max_image_bytes) if image_path else None
    store, workflow_factory, close = create_services(settings)
    manager = JobManager(settings, store, workflow_factory)
    try:
        state = await manager.create(request, image=image)
        print(f"Job {state.id} started")
        await manager.wait(state.id)
        print((await manager.get(state.id)).model_dump_json(indent=2))
    finally:
        await close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
