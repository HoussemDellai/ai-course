"""Generate a video from the command line, without the API.

    python generate.py "A documentary about bees" --minutes 0.5 --model wan22
"""

import argparse
import asyncio
import logging

from video_platform.api import create_services
from video_platform.config import Settings
from video_platform.jobs import JobManager
from video_platform.schemas import VideoRequest


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("prompt")
    p.add_argument("--minutes", type=float, default=5.0)
    p.add_argument("--model", default=None, help="wan22, ltx2 or hunyuan15")
    p.add_argument("--no-narration", action="store_true")
    args = p.parse_args()

    settings = Settings.from_env()
    store, workflow_factory, close = create_services(settings)
    manager = JobManager(settings, store, workflow_factory)
    try:
        state = await manager.create(VideoRequest(
            prompt=args.prompt, duration_minutes=args.minutes, video_model=args.model,
            narration=not args.no_narration,
        ))
        print(f"Job {state.id} started")
        await manager.wait(state.id)
        print((await manager.get(state.id)).model_dump_json(indent=2))
    finally:
        await close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
