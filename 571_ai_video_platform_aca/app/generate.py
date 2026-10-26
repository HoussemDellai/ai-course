"""Generate a video from the command line, without the API.

    python generate.py "A documentary about bees" --minutes 0.5 --model wan22
    python generate.py "Her first trip to Japan" --image photo.jpg --minutes 0.5
    python generate.py "A day at the beach" --orientation vertical --resolution 1080p --upscaler seedvr2
    python generate.py "A documentary about bees" --voice-sample my_voice.wav --clone-model chatterbox --voice-consent
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from video_platform.api import create_services
from video_platform.config import Settings
from video_platform.images import sanitize_image
from video_platform.jobs import JobManager
from video_platform.schemas import NarrationDelivery, Pronunciation, VideoBatchRequest, VideoRequest, VoiceCloneOptions
from video_platform.education_schemas import DraftUpdate, EducationOptions
from video_platform.document_schemas import DocumentOptions
from video_platform.documents import validate_document
from video_platform.voice_clone import validate_voice_sample


def voice_sample_path(argv: list[str]) -> Path | None:
    """The --voice-sample file of a creation command (parse_request returns only the photo/document path)."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--voice-sample", type=Path, default=None)
    return p.parse_known_args(argv)[0].voice_sample


def parse_request(argv: list[str] | None = None) -> tuple[VideoRequest, Path | None]:
    p = argparse.ArgumentParser()
    p.add_argument("prompt")
    p.add_argument("--use-case", "--usecase", choices=["cinematic", "educational", "document"], default="cinematic")
    p.add_argument("--document", type=Path, help="PowerPoint (.pptx) or PDF (.pdf) for --use-case document")
    p.add_argument("--language", default=None, help="Document narration locale, e.g. en-US or fr-FR")
    p.add_argument("--cinematic-cutaways", action="store_true",
                   help="Document videos: replace page visuals with 5-second cinematic clips every 30 seconds")
    p.add_argument("--animations", action="store_true",
                   help="Document videos: animate pages with a gentle zoom and fade in/out (ffmpeg, no GPU)")
    p.add_argument("--style", choices=["presentation", "ai_motion", "hybrid"], default=None)
    p.add_argument("--public-topic", help="Required public-only search topic; never include private information")
    p.add_argument("--image-provider", choices=["comfyui", "foundry"], default=None)
    p.add_argument("--motion-provider", choices=["comfyui", "foundry"], default=None)
    p.add_argument("--text-model", help="Configured educational text deployment name")
    p.add_argument("--audience", default=None)
    p.add_argument("--music-mode", choices=["off", "intro_outro", "background"], default=None,
                   help="Educational music placement (MiniMax-Music3); default: intro_outro")
    p.add_argument("--minutes", type=float, default=5.0)
    p.add_argument("--model", default=None, help="wan22, ltx2, ltx25 or hunyuan15")
    p.add_argument("--variants", type=Path, help="JSON file containing 2-12 explicit video/voice variant objects")
    p.add_argument("--batch-execution", choices=["sequential", "auto"], default="sequential",
                   help="With --variants: sequential by default; auto uses independent video GPUs when safe")
    p.add_argument("--no-narration", action="store_true")
    p.add_argument("--naturalistic", action="store_true", help="opt in to continuity, measured narration and audio mixing")
    p.add_argument("--music", action="store_true", help="instrumental background music per scene (MiniMax-Music3)")
    p.add_argument("--voice", help="Speech voice short name (default: configured TTS_VOICE)")
    p.add_argument("--speech-rate", type=int, default=None, help="delivery rate adjustment, -10 to 10 percent")
    p.add_argument("--sentence-pause-ms", type=int, default=None, help="sentence pause, 0 to 1000 ms (default: 180)")
    p.add_argument("--speech-style", help="style advertised by the selected voice; unsupported styles fail explicitly")
    p.add_argument("--pronounce", action="append", default=[], metavar="TEXT=ALIAS",
                   help="literal pronunciation substitution; may be repeated (maximum 20)")
    p.add_argument("--image", type=Path, default=None,
                   help="reference photo (PNG, JPEG or WebP) of a person or a scene to build the video from")
    p.add_argument("--orientation", choices=["horizontal", "vertical"], default="horizontal",
                   help="horizontal (16:9) or vertical (9:16, mobile)")
    p.add_argument("--resolution", choices=["720p", "1080p", "4k"], default=None,
                   help="output resolution; clips render natively at about 720p and are upscaled above it")
    p.add_argument("--upscaler", choices=["ffmpeg", "seedvr2"], default="ffmpeg",
                   help="upscaler for 1080p and 4K: ffmpeg (fast) or seedvr2 (SeedVR2 7B on the GPU); ignored at 720p")
    p.add_argument("--voice-sample", type=Path, default=None,
                   help="voice cloning: .wav or .mp4 sample of the voice to clone (at least 3 seconds)")
    p.add_argument("--clone-model", choices=["qwen3-tts", "chatterbox", "openvoice-v2", "fish-s2-pro"], default=None,
                   help="voice cloning model (default with --voice-sample: qwen3-tts)")
    p.add_argument("--sample-transcript", default=None,
                   help="voice cloning: exact transcript of the sample (default: transcribed automatically)")
    p.add_argument("--voice-consent", action="store_true",
                   help="confirm you have the right to clone the voice in the sample (required with --voice-sample)")
    args = p.parse_args(argv)
    voice_clone = None
    if args.voice_sample is not None:
        if args.voice or args.no_narration:
            p.error("--voice-sample cannot be combined with --voice or --no-narration")
        if not args.voice_consent:
            p.error("--voice-consent is required: confirm you have the right to clone the sampled voice")
        voice_clone = VoiceCloneOptions(model=args.clone_model or "qwen3-tts", consent=True,
                                        sample_transcript=args.sample_transcript)
    elif args.clone_model or args.sample_transcript or args.voice_consent:
        p.error("--clone-model, --sample-transcript and --voice-consent require --voice-sample")
    education = None
    if args.use_case == "document":
        if not args.document:
            p.error("--document is required for document videos")
        if args.image or args.naturalistic or args.no_narration or args.music or args.upscaler != "ffmpeg":
            p.error("Document videos require narration and do not accept photos, naturalistic mode, music or GPU upscaling")
    elif args.document is not None or args.language is not None or args.cinematic_cutaways or args.animations:
        p.error("--document, --language, --cinematic-cutaways and --animations require --use-case document")
    if args.use_case == "educational":
        if not args.public_topic or len(args.public_topic.strip()) < 3:
            p.error("--public-topic is required for educational videos")
        if args.image or args.naturalistic or args.no_narration or args.music:
            p.error("Educational videos require narration, do not accept photos/naturalistic, and use --music-mode instead of --music")
        education = EducationOptions(
            public_topic=args.public_topic.strip(), style=args.style or "presentation",
            image_provider=args.image_provider or "comfyui", motion_provider=args.motion_provider or "comfyui",
            text_model=args.text_model, audience=args.audience or "General audience",
            music_mode=args.music_mode or "intro_outro",
        )
    elif any(value is not None for value in (
        args.style, args.public_topic, args.image_provider, args.motion_provider,
        args.text_model, args.audience, args.music_mode,
    )):
        p.error("Educational selectors require --use-case educational")
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
        use_case=args.use_case, education=education,
        document=DocumentOptions(language=args.language or "en-US", cinematic_cutaways=args.cinematic_cutaways,
                                 animations=args.animations)
        if args.use_case == "document" else None,
        prompt=args.prompt, duration_minutes=args.minutes, video_model=args.model,
        narration=not args.no_narration, voice=args.voice, naturalistic=args.naturalistic, delivery=delivery,
        voice_clone=voice_clone,
        music=args.music, orientation=args.orientation,
        resolution=args.resolution or ("1080p" if args.use_case != "cinematic" else "720p"), upscaler=args.upscaler,
    ), args.document if args.use_case == "document" else args.image


def parse_batch_request(argv: list[str], request: VideoRequest) -> VideoBatchRequest | None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--variants", type=Path)
    p.add_argument("--batch-execution", choices=["sequential", "auto"], default="sequential")
    args = p.parse_known_args(argv)[0]
    if args.variants is None:
        if args.batch_execution != "sequential":
            p.error("--batch-execution requires --variants")
        return None
    batch = VideoBatchRequest(request=request, execution=args.batch_execution,
                              variants=json.loads(args.variants.read_text(encoding="utf-8")))
    batch.requests()  # validate overrides before opening service clients
    return batch


def parse_review_command(argv: list[str]) -> argparse.Namespace:
    """Review persisted jobs through the running API, including Blob-backed jobs."""
    p = argparse.ArgumentParser(description="Review an educational job; no automatic approval.")
    p.add_argument("command", choices=["draft", "update", "approve", "regenerate"])
    p.add_argument("job_id")
    p.add_argument("--api-url", default=os.environ.get("VIDEO_API_URL", "http://localhost:8000"))
    p.add_argument("--api-key", default=os.environ.get("API_KEY", ""))
    p.add_argument("--revision", type=int, help="Exact current draft revision (required for mutations)")
    p.add_argument("--file", type=Path, help="Local JSON containing brief and scenes for update")
    p.add_argument("--output", type=Path, help="Save the retrieved draft as JSON")
    args = p.parse_args(argv)
    if args.command != "draft" and (args.revision is None or args.revision < 1):
        p.error("Mutations require --revision with a positive current revision")
    if args.command == "update" and args.file is None:
        p.error("update requires --file")
    if args.command != "update" and args.file is not None:
        p.error("--file is only supported by update")
    if args.command != "draft" and args.output is not None:
        p.error("--output is only supported by draft")
    if not args.job_id.isalnum():
        p.error("job_id must be alphanumeric")
    return args


def review_command(args: argparse.Namespace) -> None:
    endpoint = "draft" if args.command in {"draft", "update"} else args.command
    method = {"draft": "GET", "update": "PUT", "approve": "POST", "regenerate": "POST"}[args.command]
    payload = None
    if args.command == "update":
        data = json.loads(args.file.read_text(encoding="utf-8"))
        payload = DraftUpdate(
            revision=args.revision, brief=data["brief"], scenes=data["scenes"],
        ).model_dump(mode="json")
    elif args.command != "draft":
        payload = {"revision": args.revision}
    request = Request(
        f"{args.api_url.rstrip('/')}/api/videos/{args.job_id}/{endpoint}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json", "X-API-Key": args.api_key}, method=method,
    )
    try:
        with urlopen(request, timeout=60) as response:
            result = json.loads(response.read())
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Review failed ({error.code}): {detail}. Reload the draft after a revision conflict.") from error
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.command == "update":
        print("Draft saved. Retrieve its new revision before approving or regenerating.")


async def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in {"draft", "update", "approve", "regenerate"}:
        await asyncio.to_thread(review_command, parse_review_command(argv))
        return
    request, input_path = parse_request(argv)
    batch = parse_batch_request(argv, request)
    settings = Settings.from_env()
    document = None
    image = None
    if input_path:
        if request.use_case == "document":
            if input_path.stat().st_size > settings.max_document_bytes:
                raise ValueError(f"The document is larger than {settings.max_document_mb} MB")
            document = await asyncio.to_thread(validate_document, input_path.read_bytes(),
                                               input_path.name, settings.max_document_bytes)
        else:
            image = sanitize_image(input_path.read_bytes(), settings.max_image_bytes)
    store, workflow_factory, close = create_services(settings)
    manager = JobManager(settings, store, workflow_factory)
    try:
        voice_sample = None
        if (sample_path := voice_sample_path(argv)) is not None:
            if sample_path.stat().st_size > settings.max_voice_sample_bytes:
                raise ValueError(f"The voice sample is larger than {settings.max_voice_sample_mb} MB")
            voice_sample = await validate_voice_sample(sample_path.read_bytes(), sample_path.name,
                                                       settings.max_voice_sample_bytes)
        extra = {"voice_sample": voice_sample} if voice_sample is not None else {}
        if batch is not None:
            result = await manager.create_batch(batch, image=image, document=document, **extra)
            print(f"Batch {result.id}: {result.scheduling_note}")
            try:
                for state in result.jobs:
                    print(f"Variant {state.batch.index + 1}: job {state.id}")
                    await manager.wait(state.id)
                    finished = await manager.get(state.id)
                    if finished.status == "awaiting_review":
                        print(f"awaiting_review: job {state.id}, revision {finished.draft_revision}. "
                              "Start the API with the same storage to review each variant and resume the batch.")
                        break
                print((await manager.get_batch(result.id)).model_dump_json(indent=2))
            finally:
                await manager.shutdown()
            return
        state = await manager.create(request, image=image, document=document, **extra)
        print(f"Job {state.id} started")
        await manager.wait(state.id)
        finished = await manager.get(state.id)
        print(finished.model_dump_json(indent=2))
        if finished.status == "awaiting_review":
            print(f"awaiting_review: revision {finished.draft_revision}; nothing renders until explicit approval.")
            print(f"Start the API with the same storage configuration, then:\n"
                  f"  python generate.py draft {state.id} --output draft.json\n"
                  f"  python generate.py update {state.id} --revision {finished.draft_revision} --file draft.json\n"
                  f"  python generate.py draft {state.id} --output draft.json\n"
                  f"  python generate.py approve {state.id} --revision <current-revision>\n"
                  f"  python generate.py regenerate {state.id} --revision <current-revision>")
    finally:
        await close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
