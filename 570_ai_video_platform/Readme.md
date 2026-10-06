# AI Video Platform on Azure: prompt in, 5-10 minute narrated video out

You type a prompt. The platform writes a story, turns it into dozens of shots, renders every shot with an open-weight video model on your own GPU VM, adds a voice-over and assembles the final video.

![Architecture](images/architecture.png)

> The diagram source is [images/architecture.drawio](images/architecture.drawio). Open it with [draw.io](https://app.diagrams.net) or the *Draw.io Integration* VS Code extension.

## How it works

Open-weight video models generate **~5 second clips**. A 5-10 minute video is therefore **60-120 clips** that must tell one coherent story. The orchestrator is a [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/overview/agent-framework-overview) **workflow** (`WorkflowBuilder`) in Python:

| Step | Executor | What it does |
|---|---|---|
| 1 | `EnhancePromptExecutor` | The **prompt-enhancer agent** (gpt-6-astra) turns the idea into a creative brief: title, visual style, setting, tone, and characters with a *fixed* visual description. |
| 2 | `PlanStoryboardExecutor` | The **story-outliner agent** splits the story into scenes with narration and an exact shot budget (`duration / clip length`). The **shot-writer agents** then write the prompts for each scene in parallel. Each prompt is self-contained (it repeats the character and style descriptions so clips stay consistent) and follows that video model's prompting guide. |
| 3 | `GenerateClipsExecutor` | Sends each shot to ComfyUI through its HTTP API (`/prompt`, `/history`, `/view`) and spreads the work over every server in `COMFYUI_URLS`. Failed clips are retried with a new seed. |
| 4 | `NarrateExecutor` | Azure AI Speech synthesizes each scene's voice-over, in the brief's language, using a multilingual neural voice. |
| 5 | `AssembleExecutor` | ffmpeg normalizes the clips to 1280x720 at 24 fps, concatenates each scene, and mixes in the narration (LTX-2's own audio stays underneath as ambience at 25% volume). If the narration is longer than the scene, the last frame is held. The scenes are then joined into `final.mp4`. |

The creative steps use LLM agents. The heavy steps are deterministic executors: an LLM tool-calling loop that runs for hours and 120 times would be slow, expensive and fragile. **Each step saves its output** (`brief.json`, `storyboard.json`, `clips/shot_NNN.mp4`, `narration/scene_NNN.wav`) to Blob Storage. A job interrupted by a restart, deployment or failure resumes where it stopped, without re-rendering finished clips. The `prompt_id` of every clip sent to ComfyUI is saved too, so after a restart the orchestrator reattaches to a render that is still running instead of starting it again. Each running job holds a renewable **Blob lease**, so even when Container Apps briefly runs two replicas during a rollout, a job never runs twice.

## Video models

| Key | Model | Clip | Audio | License |
|---|---|---|---|---|
| `wan22` (default) | Wan 2.2 14B fp8 + LightX2V 4-step LoRA | 1280x720, 81 frames at 16 fps (5 s) | No | **Apache 2.0**: commercial use allowed |
| `ltx2` | LTX-2 19B distilled, two-stage with x2 latent upscaler | 1280x704, 121 frames at 24 fps (5 s) | **Yes** (synchronized ambient) | Free under **$10M revenue**, paid license above |
| `hunyuan15` | HunyuanVideo 1.5 720p T2V, 20 steps | 1280x720, 121 frames at 24 fps (5 s) | No | Tencent Hunyuan Community License: territory **reportedly excludes the EU, UK and South Korea**. Check before using it in France. |

The workflows in [app/video_platform/comfy_workflows](app/video_platform/comfy_workflows) are API-format translations of the official ComfyUI templates (`video_wan2_2_14B_t2v`, `video_ltx2_t2v_distilled`, `video_hunyuan_video_1.5_720p_t2v`). Values like `"{{prompt}}"`, `"{{seed}}"` and `"{{width}}"` are filled at run time with the right JSON type. To change a workflow, build it in the ComfyUI UI, use **Export (API)**, and put the placeholders back.

> [!NOTE]
> **Rendering time is dominated by the GPU.** Rough single-H100 estimates: Wan 2.2 (4 steps) takes about 1.5-3 min per clip, so 3-6 h for a 10-minute video. LTX-2 distilled is faster. HunyuanVideo 1.5 (20 steps) is the slowest. Measure on your own VM. To render clips in parallel, add more ComfyUI VMs to `COMFYUI_URLS` (comma-separated).

## Deploy

Prerequisites: Azure CLI (`az login`), Terraform >= 1.14, quota for `Standard_NC40ads_H100_v5` and for `gpt-6-astra` GlobalStandard in the chosen region (default `germanywestcentral`).

```sh
cd infra
terraform init
terraform apply   # about 1 h: GPU driver, ComfyUI, ~121 GB of model downloads, image build in ACR
```

Terraform creates:

- **VNets**: one for the GPU VM and one for Container Apps (in `italynorth`). They aren't peered, so the app reaches ComfyUI (port 8188) through the VM's static **public IP**, and the NSG allows port 8188 from anywhere.

> [!WARNING]
> ComfyUI has no authentication. Anyone who knows the VM's public IP can use it and queue jobs on your GPU. Deallocate the VM when you aren't using it.

- **GPU VM** (H100, Ubuntu 24.04, managed 512 GB Premium SSD). Three Run Commands install the NVIDIA driver (then reboot), install ComfyUI as a `systemd` service, and download the models ([infra/scripts](infra/scripts)). The scripts are idempotent.
- **Microsoft Foundry** resource (`AIServices`, keys disabled), a project, and the **gpt-6-astra** deployment. The same resource provides **Azure AI Speech**; its custom domain is what enables Entra ID auth for TTS.
- **Storage account** (shared keys disabled). Downloads use short-lived *user delegation* SAS URLs.
- **ACR**. The image is built with `az acr build` (no local Docker needed) and rebuilt whenever the app code changes.
- **Container Apps** environment in the VNet, plus the app (1 always-on replica, 4 vCPU / 8 GiB) with a user-assigned managed identity holding `AcrPull`, `Azure AI User`, `Cognitive Services Speech User` and `Storage Blob Data Contributor`.

```sh
terraform output app_url
terraform output -raw api_key
```

Open `app_url` in a browser, paste the API key, describe your video, pick the duration and the model, then click **Generate video**.

> [!IMPORTANT]
> The GPU VM costs money even when idle. Deallocate it between batches with `az vm deallocate -g rg-aivideo570 -n vm-comfyui` and start it again with `az vm start` (ComfyUI starts automatically). Set `vm_spot = true` for a cheaper Spot VM; clips already rendered survive an eviction thanks to resume.

## REST API

All endpoints require the `X-API-Key` header (or `?key=` for browser links).

```sh
URL=$(terraform -chdir=infra output -raw app_url); KEY=$(terraform -chdir=infra output -raw api_key)

# start a job (202 Accepted)
curl -s -X POST "$URL/api/videos" -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"prompt": "A documentary about a lighthouse keeper'\''s last winter on a remote Breton island", "duration_minutes": 5, "video_model": "wan22"}'

curl -s "$URL/api/videos/<id>" -H "X-API-Key: $KEY"              # status, clips_done/clips_total
curl -s "$URL/api/videos/<id>/storyboard" -H "X-API-Key: $KEY"   # brief, scenes, narration, shot prompts
curl -sL "$URL/api/videos/<id>/download" -H "X-API-Key: $KEY" -o video.mp4
curl -s -X POST "$URL/api/videos/<id>/retry" -H "X-API-Key: $KEY" # resume a failed job
```

| Field | Default | Notes |
|---|---|---|
| `prompt` | (required) | Any language. The narration uses the prompt's language. |
| `duration_minutes` | `5` | 0.25 to 10. Use 0.25-0.5 for quick tests. |
| `video_model` | `wan22` | `wan22`, `ltx2` or `hunyuan15` |
| `narration` | `true` | `false` gives a silent video (or LTX-2 audio only) |
| `voice` | `en-US-AndrewMultilingualNeural` | Any Azure neural voice, e.g. `fr-FR-VivienneMultilingualNeural` |
| `seed` | random | Makes clip generation reproducible |

## Run the orchestrator locally

```sh
cd app
python -m venv .venv && .venv/Scripts/activate        # source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt -r requirements-dev.txt
cp .env.sample .env                                    # fill in values from `terraform output` (COMFYUI_URLS = comfyui_url)
python main.py                                         # http://localhost:8000
# or, without the API:
python generate.py "A short film about a robot learning to paint" --minutes 0.5 --model ltx2
```

Locally it uses your `az login` identity (Terraform grants you the same roles as the app). With `STORAGE_ACCOUNT_URL` empty, jobs are written to `./output`. ffmpeg must be on your `PATH`.

## Tests

```sh
cd app
pytest
```

The tests check every ComfyUI workflow graph (placeholders, links, node types) and the ComfyUI client (submit, poll, download, retry with a new seed). They also run the **real Agent Framework workflow with real ffmpeg** against a fake ComfyUI, fake LLM agents and fake TTS. That covers the whole pipeline, narration longer than a scene, resume without re-rendering, reattaching to an in-flight ComfyUI prompt, concurrent retries, jobs locked by another replica, audio/video sync, and the REST API.

## Project layout

```
570_ai_video_platform/
├── app/
│   ├── main.py                     # FastAPI entry point (container CMD)
│   ├── generate.py                 # CLI: one video, no API
│   ├── Dockerfile
│   ├── video_platform/
│   │   ├── workflow.py             # Agent Framework workflow (5 executors)
│   │   ├── agents.py               # prompt-enhancer, story-outliner, shot-writer agents
│   │   ├── comfyui.py              # ComfyUI API client + multi-server pool
│   │   ├── comfy_workflows/        # API-format workflows for the 3 models
│   │   ├── video_models.py         # model registry: resolution, fps, frames, prompt guide, license
│   │   ├── speech.py               # Azure AI Speech TTS (Entra ID)
│   │   ├── media.py                # ffmpeg: normalize, concat, narration mix
│   │   ├── storage.py              # Blob / local artifact store
│   │   ├── jobs.py                 # background jobs, resume, retry
│   │   ├── api.py                  # REST API
│   │   └── static/index.html       # minimal web UI
│   └── tests/
├── images/architecture.drawio      # architecture diagram (draw.io, Azure icons) + .png export
└── infra/                          # Terraform + VM scripts
```

## Going further

- **Character consistency**: generate a reference image per character (e.g. Qwen-Image or Z-Image-Turbo, already used in [550_comfyui_on_vm](../550_comfyui_on_vm)) and switch the shots to image-to-video workflows.
- **Scale out**: run several GPU VMs (or a VM Scale Set) and list them all in `COMFYUI_URLS`.
- **Music**: add a music-generation step and mix it under the narration in `media.mix_narration`.
- **Hosted agent**: the same workflow can be exposed as a Foundry hosted agent with `agent-framework-foundry-hosting`.
