# AI Video Platform on Azure: prompt (and photo) in, 5-10 minute narrated video out

You type a prompt and, optionally, attach a photo of a person or a scene. The platform writes a story, turns it into dozens of shots, renders every shot with an open-weight video model on your own GPU VM, adds a voice-over and assembles the final video. With a photo, every shot starts from a keyframe redrawn from your photo, so the person or the place stays recognizable for the whole film.

![Architecture](images/architecture.png)

> The diagram source is [images/architecture.drawio](images/architecture.drawio). Open it with [draw.io](https://app.diagrams.net) or the *Draw.io Integration* VS Code extension.

## How it works

Open-weight video models generate **~5 second clips**. A 5-10 minute video is therefore **60-120 clips** that must tell one coherent story. The orchestrator is a [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/overview/agent-framework-overview) **workflow** (`WorkflowBuilder`) in Python:

| Step | Executor | What it does |
|---|---|---|
| 1 | `EnhancePromptExecutor` | The **prompt-enhancer agent** (gpt-6-astra) turns the idea into a creative brief: title, visual style, setting, tone, and characters with a *fixed* visual description. With a reference photo, the agent **looks at the photo**: the people in it become the main characters (described faithfully, never named or identified) or the place becomes the setting, and `reference_notes` records what the photo shows. |
| 2 | `PlanStoryboardExecutor` | The **story-outliner agent** splits the story into scenes with narration and an exact shot budget (`duration / clip length`). The **shot-writer agents** then write the prompts for each scene in parallel. Each prompt is self-contained (it repeats the character and style descriptions so clips stay consistent) and follows that video model's prompting guide. With a photo, each shot gets two prompts: a **keyframe prompt** (an edit instruction: "keep the woman from image 1 identical, now ... medium shot, golden hour ...") and an **image-to-video prompt** that describes the motion and the camera. |
| 3 | `GenerateKeyframesExecutor` | Only with a photo (otherwise *skipped*). **Qwen-Image-Edit-2511** (4-step Lightning LoRA) redraws the photo into the first frame of every shot, at the video model's resolution. All keyframes are rendered before any clip, so ComfyUI loads each model once instead of swapping models for every shot. |
| 4 | `GenerateClipsExecutor` | Sends each shot to ComfyUI through its HTTP API (`/upload/image`, `/prompt`, `/history`, `/view`) and spreads the work over every server in `COMFYUI_URLS`: **text-to-video**, or **image-to-video** from the shot's keyframe. Failed clips are retried with a new seed. |
| 5 | `NarrateExecutor` | Azure AI Speech synthesizes each scene's voice-over, in the brief's language, using a multilingual neural voice. The narration is plain spoken text: screenplay-style speaker labels the LLM might add ("Narrator:", "Maya (V.O.):") are stripped so they are never read aloud. |
| 6 | `GenerateMusicExecutor` | Only with `music` (otherwise *skipped*). The **music-director agent** writes one instrumental cue per scene around a shared theme, and **MiniMax Music 3** renders each cue on ComfyUI, sized to the scene's length. See [Background music](#background-music). |
| 7 | `AssembleExecutor` | ffmpeg normalizes the clips to 1280x720 at 24 fps, concatenates each scene, and mixes in the narration (the LTX-2 / LTX-2.5 audio stays underneath as ambience at 25% volume) and the scene's music. If the narration is longer than the scene, the last frame is held. The scenes are then joined into `final.mp4`. |

This is the default pipeline. The opt-in **naturalistic mode** prepares and measures narration
immediately after the storyboard, before keyframes or clips, and never extends scenes with frozen frames.

The creative steps use LLM agents. The heavy steps are deterministic executors: an LLM tool-calling loop that runs for hours and 120 times would be slow, expensive and fragile. **Each step saves its output** (`input/reference.png`, `brief.json`, `storyboard.json`, `keyframes/shot_NNN.png`, `clips/shot_NNN.mp4`, `narration/scene_NNN.wav`, `music.json`, `music/scene_NNN.flac`) to Blob Storage. A job interrupted by a restart, deployment or failure resumes where it stopped, without re-rendering finished keyframes, clips or music. The `prompt_id` of every keyframe, clip and music cue sent to ComfyUI is saved too, so after a restart the orchestrator reattaches to a render that is still running instead of starting it again. Each running job holds a renewable **Blob lease**, so even when Container Apps briefly runs two replicas during a rollout, a job never runs twice.

### Videos from a photo

Open-weight video models only keep a person's likeness *within* one clip. To keep it across 60-120 independent clips, the platform never animates the photo directly: for each shot it first **redraws** the photo into that shot's framing, setting and lighting with Qwen-Image-Edit, then animates that keyframe with the video model's **image-to-video** workflow. Animating the photo itself would make every clip start from the same frame.

- The upload is checked and cleaned before it is stored: PNG, JPEG or WebP only, at most `MAX_IMAGE_MB` (10 MB by default), EXIF orientation applied, **all metadata (EXIF, GPS...) removed**, longest side capped at 2048 px, re-encoded as PNG.
- Each keyframe costs one extra 4-step Qwen-Image-Edit render (roughly 10-20 s on an H100) on top of the clip.
- The prompt is still required: it tells the agents what story to tell around the photo.

> [!IMPORTANT]
> Only upload photos you have the rights to, and of people who agreed to appear in an AI-generated video. The platform doesn't check consent: that responsibility is yours. The agents never try to name or identify the people in a photo.

### Naturalistic mode

Enable **Naturalistic** in the composer, use `--naturalistic` in the CLI, or send
`"naturalistic": true` in the JSON request (also supported inside a multipart request).
It is off by default; existing jobs keep their original behavior.

- **Continuity and direction:** each scene records wardrobe/props, lighting/location, screen
  direction, and starting/ending action state. Shot writers receive neighboring scene context
  while still running in parallel. Prompts favor restrained expressions, plausible contact and
  weight, motivated gestures, static cameras where appropriate, and establishing/action/reaction/detail
  shot variety. Explicitly stylized stories keep their intended genre.
- **Spoken delivery:** short conversational narration, deliberate pauses, optional voice style,
  and literal pronunciation aliases. These are structured controls, not arbitrary SSML.
  Open **Voice and delivery** in the UI to customize them.
- **Measured timing:** synthesize narration before GPU work, reserving 0.4 seconds of lead-in and
  0.6 seconds of tail per scene. If it does not fit, the narrator editor can shorten it twice:
  **at most three syntheses per scene**, including interrupted attempts across job retries.
  Speech is not automatically accelerated, truncated, or placed over a frozen ending.
  Exhaustion fails the job visibly; create a new job with a shorter script or longer scenes.
- **Audio:** consistent narration loudness (ffmpeg loudnorm target -18 LUFS), speech-driven
  ambience ducking, peak limiting with headroom, and short ambience fades at clip boundaries.
  Silent models still receive silence under narration (unless [background music](#background-music) is enabled).
  Visual cuts remain hard cuts. Extra encoding is needed to avoid accumulated AAC timestamp gaps.
- **Duration:** each clip is trimmed down to a whole number of output frames before timing
  narration. A clip shorter than its planned duration fails rather than being padded.
  The requested duration remains an approximate shot budget, not an exact final runtime.

Delivery controls require both naturalistic mode and narration:

| `delivery` field | Default | Allowed values |
|---|---|---|
| `rate_percent` | `0` | Integer from -10 to 10; an explicit artistic choice, never adjusted to fit speech |
| `sentence_pause_ms` | `180` | Integer from 0 to 1000; added between detected sentences/newlines |
| `style` | `null` | A style advertised by the selected voice, or neutral delivery |
| `pronunciations` | `[]` | Up to 20 unique `{"text": "SQL", "alias": "sequel"}` entries; case-sensitive literal substitutions |

The configured Speech endpoint's voice catalog is checked before synthesis for the selected
voice, language (including advertised secondary locales), and style. Standard neural voices
are supported; HD voices are not supported in this mode. Unsupported selections and catalog
lookup failures are explicit job errors, not silent neutral-voice fallbacks. A Speech endpoint
is required when naturalistic narration is enabled; disabling narration still enables visual
direction and ambience finishing.

```json
{
  "prompt": "A quiet documentary about a lighthouse keeper",
  "duration_minutes": 0.5,
  "naturalistic": true,
  "delivery": {
    "rate_percent": -5,
    "sentence_pause_ms": 250,
    "style": null,
    "pronunciations": [{"text": "SQL", "alias": "sequel"}]
  }
}
```

```sh
python generate.py "A quiet documentary about a lighthouse keeper" --minutes 0.5 --naturalistic \
  --voice en-US-AndrewMultilingualNeural --speech-rate -5 --sentence-pause-ms 250 --pronounce SQL=sequel
```

**Recovery:** accepted narration text, measured duration, and audio checksum are journaled
together under content-addressed `narration/natural-v1/` paths. A changed narration source uses
new audio, not a stale WAV. The original plan remains in `storyboard.json`; the accepted version
is saved as `storyboard.narrated.json` and returned by the storyboard endpoint when available.
Naturalistic jobs also record request/render dependency fingerprints. Editing an existing job's
request, visual plan, model settings, or output settings is not supported: incompatible resumes
fail explicitly and require a new job. Legacy jobs cannot be converted in place.

**Limits:** prompting improves direction, not model guarantees. There is no lip sync, new
video model, automatic visual scoring, selective retake UI, or keyframe approval gate in this
release. These remain later features. Automated fixture tests check timing and mixing, not
photorealism or whether narration edits preserve every nuance.

### Background music

Tick **Music (MiniMax-Music3)** in the composer, use `--music` in the CLI, or send `"music": true`. It is off by default, and it works with every video model, with or without a photo, in both the default and the naturalistic mode.

- **Scoring**: once the narration is ready (so every scene's final length is known), the **music-director agent** defines one musical theme for the film (instrument palette, key family, tempo range) and writes one cue per scene in the MiniMax Music 3 caption format: *Global Metadata* (genre, BPM, key, mood arc), *Vocal Details* (always "Instrumental only. No vocals, no singing, no humming, no choir, no spoken words.") and *Arrangement*. The lyrics sent to the model are only section tags (`[Intro]`, `[Instrumental]`, `[Outro]`), so it has no words to sing.
- **Rendering**: [MiniMax Music 3](https://huggingface.co/MiniMaxAI/MiniMax-Music3) renders each cue on ComfyUI ([comfy_workflows/minimax_music3_t2m.json](app/video_platform/comfy_workflows/minimax_music3_t2m.json), translated from the official `audio_minimax_music_3` template) as 32 kHz stereo FLAC, one second longer than the scene. All cues are rendered after all clips, so ComfyUI loads the model once.
- **Mixing**: the cue is trimmed to the exact scene length, faded in and out at the cuts (`MUSIC_FADE_SECONDS`, 1 s by default), played at `MUSIC_VOLUME` (0.3 by default) and **ducked** under the narration and the model's ambience. The video stream is copied, so naturalistic exact durations are kept.

> [!IMPORTANT]
> MiniMax Music 3 uses the [MiniMax-Music3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-Music3/blob/main/LICENSE). Commercial use is free under 20 million USD of yearly revenue (above that, ask MiniMax for a license), and a commercial product or service using it must **prominently display "MiniMax-Music3"** in its user interface: the composer option, the job chips and the timeline step show it. A hosted service must keep safeguards against misuse, and AI-generated content published in a public environment must be disclosed as machine-generated. Unlike MiniMax H3, the license has no territorial restriction.

Music 3 is a song model: the instrumental-only caption and the tag-only lyrics keep it instrumental, but listen to the result before publishing.

## Video models

| Key | Model | Clip | Audio | License |
|---|---|---|---|---|
| `wan22` (default) | Wan 2.2 14B fp8 + LightX2V 4-step LoRA (T2V and I2V) | 1280x720, 81 frames at 16 fps (5 s) | No | **Apache 2.0**: commercial use allowed |
| `ltx2` | LTX-2 19B distilled, two-stage with x2 latent upscaler (same checkpoint for T2V and I2V) | 1280x704, 121 frames at 24 fps (5 s) | **Yes** (synchronized ambient) | Free under **$10M revenue**, paid license above |
| `ltx25` | LTX-2.5 22B distilled (int8) + Gemma 4 12B text encoder, two-stage with x2 latent upscaler (same transformer for T2V and I2V). Sharper faces and textures, better prompt adherence than LTX-2. **Weights downloaded manually**, see [Enable LTX-2.5](#enable-ltx-25). | 1280x704, 121 frames at 24 fps (5 s) | **Yes** (synchronized ambient) | LTX-2.x Community License: free under **$10M revenue**, paid license above |
| `hunyuan15` | HunyuanVideo 1.5 720p T2V / I2V (+ SigLIP vision encoder), 20 steps | 1280x720, 121 frames at 24 fps (5 s) | No | Tencent Hunyuan Community License: territory **reportedly excludes the EU, UK and South Korea**. Check before using it in France. |

Keyframes for videos made from a photo use **Qwen-Image-Edit-2511** (fp8) with the **4-step Lightning LoRA** (Apache 2.0), whatever the video model.

The workflows in [app/video_platform/comfy_workflows](app/video_platform/comfy_workflows) are API-format translations of the official ComfyUI templates (`video_wan2_2_14B_t2v`, `video_wan2_2_14B_i2v`, `video_ltx2_t2v_distilled`, `video_ltx2_i2v_distilled`, `video_ltx2_5_t2v`, `video_ltx2_5_i2v`, `video_hunyuan_video_1.5_720p_t2v`, `video_hunyuan_video_1.5_720p_i2v`, `image_qwen_image_edit_2511`, `audio_minimax_music_3`). Values like `"{{prompt}}"`, `"{{seed}}"`, `"{{width}}"` and `"{{image}}"` are filled at run time with the right JSON type. Input images are uploaded with `/upload/image` to a per-job subfolder (`aivideo/<job id>`) of the ComfyUI server that renders them. To change a workflow, build it in the ComfyUI UI, use **Export (API)**, and put the placeholders back.

> [!NOTE]
> **Rendering time is dominated by the GPU.** Rough single-H100 estimates: Wan 2.2 (4 steps) takes about 1.5-3 min per clip, so 3-6 h for a 10-minute video. LTX-2 and LTX-2.5 distilled are faster. HunyuanVideo 1.5 (20 steps) is the slowest. Measure on your own VM. To render clips in parallel, add more ComfyUI VMs to `COMFYUI_URLS` (comma-separated).

### Enable LTX-2.5

`terraform apply` doesn't download the LTX-2.5 weights: the [Lightricks/LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5) repository on Hugging Face is gated, so the download needs your token. Until the weights are on the VM, ComfyUI rejects `ltx25` clips (*value not in list* for the model files) and the job fails.

1. Sign in to Hugging Face, open [Lightricks/LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5) and accept the license (access is granted right away).
2. Create a **read** token in [Settings > Access Tokens](https://huggingface.co/settings/tokens).
3. Run [infra/scripts/05-download-ltx25.sh](infra/scripts/05-download-ltx25.sh) on the VM. It downloads about 37 GB (transformer, text encoder, video and audio VAEs, upscaler) into the ComfyUI `models/` folders, and updates ComfyUI only if it doesn't have the LTX-2.5 nodes yet:

```sh
terraform -chdir=infra output -raw vm_admin_password   # SSH password for azureuser
read -rs HF_TOKEN                                      # paste the token (not echoed, not saved in the history)
ssh azureuser@$(terraform -chdir=infra output -raw vm_public_ip) \
  "tr -d '\r' | sudo HF_TOKEN=$HF_TOKEN bash -s" < infra/scripts/05-download-ltx25.sh
```

`tr -d '\r'` strips the Windows line endings that git adds on a Windows checkout. The script is idempotent: if the SSH session drops, run it again and the downloads resume. Run it between jobs: if ComfyUI needs an update, the restart drops the clip being rendered.

## Deploy

Prerequisites: Azure CLI (`az login`), Terraform >= 1.14, quota for `Standard_NC40ads_H100_v5` and for `gpt-6-astra` GlobalStandard in the chosen region (default `germanywestcentral`).

```sh
cd infra
terraform init
terraform apply   # about 1 h 30: GPU driver, ComfyUI, ~205 GB of model downloads, image build in ACR
```

Terraform creates:

- **VNets**: one for the GPU VM and one for Container Apps (in `italynorth`). They aren't peered, so the app reaches ComfyUI (port 8188) and the GPU stats exporter (port 8189) through the VM's static **public IP**, and the NSG allows both ports from anywhere.

> [!WARNING]
> ComfyUI has no authentication. Anyone who knows the VM's public IP can use it and queue jobs on your GPU. The GPU stats exporter has no authentication either, but it's read-only and exposes only GPU utilisation, VRAM, temperature and power, plus the VM's CPU and RAM usage. Deallocate the VM when you aren't using it.

- **GPU VM** (H100, Ubuntu 24.04, managed 512 GB Premium SSD). Run Commands install the NVIDIA driver (then reboot), install ComfyUI as a `systemd` service, download the models, and install a small GPU stats exporter (`nvidia-smi` plus the VM's CPU and RAM from `/proc` over HTTP, `gpu-stats` service on port 8189) ([infra/scripts](infra/scripts)). The scripts are idempotent. The exporter is independent of ComfyUI, so updating it never restarts a render.
- **Microsoft Foundry** resource (`AIServices`, keys disabled), a project, and the **gpt-6-astra** deployment. The same resource provides **Azure AI Speech**; its custom domain is what enables Entra ID auth for TTS.
- **Storage account** (shared keys disabled). Downloads use short-lived *user delegation* SAS URLs.
- **ACR**. The image is built with `az acr build` (no local Docker needed) and rebuilt whenever the app code changes.
- **Container Apps** environment in the VNet, plus the app (1 always-on replica, 4 vCPU / 8 GiB) with a user-assigned managed identity holding `AcrPull`, `Azure AI User`, `Cognitive Services Speech User` and `Storage Blob Data Contributor`.

```sh
terraform output app_url
terraform output -raw api_key
```

Open `app_url` in a browser, paste the API key, describe your video, optionally attach a photo (photo button, drag and drop, or paste), pick the duration and the model, then send it.

The web UI follows the GitHub Copilot app (dark theme). Your videos are listed in a sidebar. Each video opens as a session: your prompt (and photo), then a live timeline of what the agent is doing. The seven pipeline steps expand into their operations:

- each agent call
- each keyframe (with its image once rendered) and each clip, with its ComfyUI server, prompt id, seed, prompt and retries
- each narration
- each ffmpeg and upload step

Each operation has a status and a duration, and shows the warnings logged while it ran. Retries keep the earlier runs, and steps resumed from saved artifacts show as *reused*.

The top bar shows the **live GPU, CPU and RAM utilisation** of the VM (average GPU util %, VRAM used/total, CPU % and RAM %, refreshed every 2 s), or *GPU offline* when the VM is deallocated. Click it to see, for each VM: CPU and RAM usage (with vCPU count, 1-minute load and a chart of the last 2 minutes), and for each GPU: utilisation, VRAM, temperature, power draw, and a chart of the last 2 minutes. The app reads it from the exporters listed in `GPU_STATS_URLS`; leave the variable empty to hide the badge.

> [!IMPORTANT]
> The GPU VM costs money even when idle. Deallocate it between batches with `az vm deallocate -g rg-aivideo570 -n vm-comfyui` and start it again with `az vm start` (ComfyUI starts automatically). Set `vm_spot = true` for a cheaper Spot VM; clips already rendered survive an eviction thanks to resume.

## REST API

All endpoints require the `X-API-Key` header (or `?key=` for browser links).

```sh
URL=$(terraform -chdir=infra output -raw app_url); KEY=$(terraform -chdir=infra output -raw api_key)

# start a job (202 Accepted)
curl -s -X POST "$URL/api/videos" -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"prompt": "A documentary about a lighthouse keeper'\''s last winter on a remote Breton island", "duration_minutes": 5, "video_model": "wan22"}'

# start a job from a photo of a person or a scene: multipart, same JSON in the 'request' field
curl -s -X POST "$URL/api/videos" -H "X-API-Key: $KEY" \
  -F 'request={"prompt": "Her first trip to Kyoto, told as a travel diary", "duration_minutes": 2}' \
  -F "image=@photo.jpg"

curl -s "$URL/api/videos/<id>" -H "X-API-Key: $KEY"              # status, clips_done/clips_total
curl -s "$URL/api/videos/<id>/storyboard" -H "X-API-Key: $KEY"   # brief, scenes, narration, shot (and keyframe) prompts
curl -s "$URL/api/videos/<id>/operations" -H "X-API-Key: $KEY"   # timeline: steps, agent calls, keyframes, clips, ffmpeg...
curl -sN "$URL/api/videos/<id>/events?key=$KEY"                  # live Server-Sent Events: state, op, end
curl -sL "$URL/api/videos/<id>/download" -H "X-API-Key: $KEY" -o video.mp4
curl -sL "$URL/api/videos/<id>/image" -H "X-API-Key: $KEY" -o photo.png        # the cleaned reference photo
curl -sL "$URL/api/videos/<id>/keyframes/0" -H "X-API-Key: $KEY" -o shot0.png  # keyframe of shot 1 (0-based)
curl -s -X POST "$URL/api/videos/<id>/retry" -H "X-API-Key: $KEY" # resume a failed job
curl -s "$URL/api/gpu" -H "X-API-Key: $KEY"                      # live GPU, CPU and RAM stats of every VM in GPU_STATS_URLS
```

`/events` first sends the job state and all its operations, then each change as it happens, and `end` once the job is finished. If another replica runs the job, the stream follows it through the artifact store instead (about 2 s behind).

`POST /api/videos` accepts either a JSON body or `multipart/form-data` with a `request` field (the same JSON) and an optional `image` file (PNG, JPEG or WebP, up to `MAX_IMAGE_MB`, 10 MB by default). It answers 413 for a photo that is too large, 415 for a file that isn't a supported image, and 422 for an invalid request. `request.reference_image` in the job state is set by the server when a photo was uploaded; clients can't set it.

| Field | Default | Notes |
|---|---|---|
| `prompt` | (required) | Any language. The narration uses the prompt's language. Also required with a photo. |
| `duration_minutes` | `5` | 0.25 to 10. Use 0.25-0.5 for quick tests. |
| `video_model` | `wan22` | `wan22`, `ltx2`, `ltx25` or `hunyuan15` |
| `narration` | `true` | `false` gives a silent video (or LTX-2 / LTX-2.5 audio only) |
| `voice` | `en-US-AndrewMultilingualNeural` | Any Azure neural voice, e.g. `fr-FR-VivienneMultilingualNeural` |
| `seed` | random | Makes clip generation reproducible |
| `naturalistic` | `false` | Opt-in continuity, measured narration before rendering, and improved audio mixing |
| `music` | `false` | Opt-in instrumental background music per scene (MiniMax-Music3), see [Background music](#background-music) |
| `delivery` | `null` | Optional structured controls above; requires naturalistic mode and narration |

## Run the orchestrator locally

```sh
cd app
python -m venv .venv && .venv/Scripts/activate        # source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt -r requirements-dev.txt
cp .env.sample .env                                    # fill in values from `terraform output` (COMFYUI_URLS = comfyui_url, GPU_STATS_URLS = gpu_stats_url)
python main.py                                         # http://localhost:8000
# or, without the API:
python generate.py "A short film about a robot learning to paint" --minutes 0.5 --model ltx2
python generate.py "Her first trip to Kyoto" --image photo.jpg --minutes 0.5      # from a photo
```

Locally it uses your `az login` identity (Terraform grants you the same roles as the app). With `STORAGE_ACCOUNT_URL` empty, jobs are written to `./output`. ffmpeg must be on your `PATH`.

## Tests

```sh
cd app
pytest
```

The tests check every ComfyUI workflow graph (text-to-video, image-to-video, keyframe and music: placeholders, links, node types) and the ComfyUI client (image upload, submit, poll, download, retry with a new seed). They also run the **real Agent Framework workflow with real ffmpeg** against a fake ComfyUI, fake LLM agents and fake TTS. That covers the whole pipeline (from a prompt, and from a photo for all four models: the agents get the photo, keyframes come before clips, clips start from their keyframe), the photo checks (formats, size, EXIF orientation and metadata removal), narration longer than a scene, resume without re-rendering keyframes, clips or music, background music (one cue per scene after the clips, instrumental captions and tag-only lyrics, exact scene lengths, fades and ducking), reattaching to an in-flight ComfyUI prompt, concurrent retries, jobs locked by another replica, audio/video sync, the operation timeline (live, persisted, across retries and replicas), the REST API (JSON and multipart uploads) with its event stream, and the live GPU stats (exporter parsing of `nvidia-smi` and `/proc` CPU/RAM, offline VMs, `/api/gpu`).

Naturalistic regression tests cover controls and SSML escaping, language/style validation,
strict continuity output schemas, JSON/multipart/CLI options, early narration, bounded corrections,
checkpoint recovery, checksums, incompatible artifact rejection, output frame counts, decoded
audio peaks, and measured ambience attenuation/recovery. They require both ffmpeg and ffprobe
on `PATH`; skipped media tests are not evidence that the rendering path passed.

For a perceptual A/B evaluation, generate separate legacy and naturalistic jobs with the same
prompt, reference photo (if any), model, voice and seed. Include a person handling a prop, a
walking scene with changes of angle, a quiet interior, and narration in a second supported
language. Have viewers compare continuity, physical motion, voice delivery and editing rhythm,
and record GPU operation durations, synthesis/correction counts and job failures from the
timeline. Repeat across multiple seeds. No live-model quality improvement is claimed solely
from synthetic fixture tests.

## Project layout

```
570_ai_video_platform/
├── app/
│   ├── main.py                     # FastAPI entry point (container CMD)
│   ├── generate.py                 # CLI: one video, no API (--image for a photo)
│   ├── Dockerfile
│   ├── video_platform/
│   │   ├── workflow.py             # Agent Framework workflow (6 executors, each recorded as a timeline step)
│   │   ├── agents.py               # prompt-enhancer (sees the photo), story-outliner, shot-writer agents
│   │   ├── comfyui.py              # ComfyUI API client (image upload, T2V/I2V clips, keyframes) + multi-server pool
│   │   ├── gpu.py                  # live GPU, CPU and RAM stats from the VM exporters (/api/gpu)
│   │   ├── comfy_workflows/        # API-format workflows: T2V and I2V for the 4 models, Qwen-Image-Edit keyframes, MiniMax Music 3
│   │   ├── video_models.py         # model registry: resolution, fps, frames, T2V/I2V prompt guides, license
│   │   ├── images.py               # reference photo checks and cleanup (format, size, EXIF/GPS removal)
│   │   ├── speech.py               # Azure AI Speech TTS (Entra ID)
│   │   ├── media.py                # ffmpeg: normalize, concat, narration mix
│   │   ├── storage.py              # Blob / local artifact store
│   │   ├── jobs.py                 # background jobs, resume, retry, live notifications
│   │   ├── operations.py           # operation timeline (steps, agent calls, keyframes, clips...) + log capture
│   │   ├── api.py                  # REST API (JSON or multipart with a photo) + Server-Sent Events
│   │   └── static/index.html       # web UI (Copilot-style sessions, photo upload, live timeline)
│   └── tests/
├── images/architecture.drawio      # architecture diagram (draw.io, Azure icons) + .png export
└── infra/                          # Terraform + VM scripts
```

## Going further

- **Character consistency without a photo**: the keyframe + image-to-video path already exists for uploaded photos. Text-only videos could use it too: generate a reference image per character (e.g. Qwen-Image or Z-Image-Turbo, already used in [550_comfyui_on_vm](../550_comfyui_on_vm)) and feed it to `GenerateKeyframesExecutor`.
- **Several photos**: `TextEncodeQwenImageEditPlus` accepts up to three images, e.g. two people and a place.
- **LTX-2.5 multishot**: LTX-2.5 can render several connected shots in one pass, keeping the character, lighting and voice across the cuts. A scene could become one multishot clip instead of independent 5 s shots.
- **Scale out**: run several GPU VMs (or a VM Scale Set) and list them all in `COMFYUI_URLS` (and their exporters in `GPU_STATS_URLS`).
- **Hosted agent**: the same workflow can be exposed as a Foundry hosted agent with `agent-framework-foundry-hosting`.
