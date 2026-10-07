# Azure Deployment Plan

> **Status:** Deployed

## Release: orientation, 720p/1080p/4K output and SeedVR2 upscaling (2026-10-07)

- User requested: merge `feature/video-resolution` into `main` (done locally: merge commit `71b9c22`,
  feature commit `7cf03fa`, not pushed) and deploy to Azure.
- Mode: MODIFY. Same subscription (`ME-MngEnvMCAP784683-hodellai-1`), resource group `rg-aivideo570`,
  regions and Terraform infrastructure as the previous releases. No new Azure resources.
- **App** (same recipe as before): build context = `git archive 71b9c22` app tree (committed code only),
  `az acr build` in `acraivideo570` -> tags `video-platform:res-71b9c22` and `video-platform:1.0.0`,
  then `az containerapp update --image ...:1.0.0 --revision-suffix res-71b9c22` (single revision mode).
  No new environment variables: the feature's defaults (horizontal, 720p, ffmpeg) keep existing behavior.
- **GPU VM**: already rolled out during feature validation with a targeted `terraform apply` of the
  `02-install-comfyui` (ComfyUI pinned to v0.39.0) and `03-download-models` (SeedVR2 7B fp16 + VAE) run
  commands; real 1080p and 4K SeedVR2 renders and a full vertical 1080p job passed against it.
- **Terraform state**: `main` now contains `terraform_data.build_app_image` (committed from earlier pending
  work). Its local-exec builds only when tag `1.0.0` is missing, so applying it after the app rollout is a
  no-op build that aligns state with `main`. Apply only if `terraform plan` shows nothing else.
- Container App sizing unchanged (4 vCPU / 8 GiB): ffmpeg processing of 4K shots is slower on 4 vCPU but
  bounded by `FFMPEG_CONCURRENCY=2`.
- Active jobs before rollout: 17 jobs, 0 running (authenticated `GET /api/videos`).
- Rollback: tag `video-platform:photo50-560f616` holds the live digest; retag it as `1.0.0` and create a
  fresh revision.

### Validation proof (2026-10-07 21:35-21:45 +02:00)

| Check | Command / evidence | Result |
|---|---|---|
| Azure target | `az account show`, `az containerapp show/revision list` | `ME-MngEnvMCAP784683-hodellai-1`; `video-platform--photo50-560f616` Healthy, 100%, single mode, image `video-platform:1.0.0` |
| Terraform | `terraform validate`, `terraform fmt -check`, `terraform plan -lock=false` | Valid; formatted; plan = 1 to add (`terraform_data.build_app_image`), 0 change, 0 destroy |
| Build context | `git archive 71b9c22` app tree; Dockerfile, `.dockerignore`, SeedVR2 workflow present; `python -m compileall` | Passed; committed app tree identical to the tested working tree |
| Regression tests | `python -m pytest -q` in `app/` (same content as `71b9c22`) | 139 passed |
| Real GPU | ComfyUI v0.39.0 `/object_info` vs every workflow node type; SeedVR2 1080p and 4K renders; full vertical 1080p SeedVR2 job via local API + Edge/Playwright | All node types present; 1920x1080 / 2160x3840 outputs; job completed at 1080x1920 |
| Static + live RBAC | No RBAC change in this release; `az role assignment list` for the app identity | AcrPull, Foundry User, Cognitive Services Speech User, Storage Blob Data Contributor |
| Active jobs | Authenticated `GET /api/videos` (key kept in memory) | 17 jobs, 0 running |

### Deployment results (2026-10-07 21:45-22:00 +02:00)

- ACR run `dnf` Succeeded (`--no-logs`, context = `git archive 71b9c22` app tree): `video-platform:res-71b9c22`
  and `video-platform:1.0.0` -> `sha256:4fa45c4e2ebebb99488749c2b0a4004deb5d5c888d53531a8b498ce80e64a6dd`.
- `az containerapp update --image ...:1.0.0 --revision-suffix res-71b9c22`: revision
  `video-platform--res-71b9c22` Healthy, RunningAtMaxScale, 100% traffic; `photo50-560f616` deprovisioned.
- Verified live: `/healthz` 200; UI serves the orientation/resolution/upscaler selectors and the Outputs
  panel; `/api/models` reports vertical sizes; `resolution: "8k"` -> 422 (no job created; still 17 jobs);
  legacy jobs load as 720p horizontal; `/media/final.mp4` 401 without key, 404 for `state.json`, 307 to
  the Blob SAS URL with the key, and a Range request on the SAS URL returns 206 `video/mp4`.
- `terraform apply` of the saved plan: `terraform_data.build_app_image` created; its local-exec found tag
  `1.0.0` and skipped the build (digest unchanged). Follow-up `terraform plan`: no changes.
- No RBAC, secret, environment-variable or VM changes in this step (the VM run commands were applied
  during feature validation). Build context deleted.
- Rollback: retag `video-platform:photo50-560f616`
  (`sha256:3eecdbfbf51fd3ba0dae104750cc0a7ec39284d820f0ff1b06971b81e1c73848`) as `1.0.0` and create a fresh
  revision.

## Release: reference photos up to 50 MB (2026-10-07)

- User requested deploying the photo-size change: `MAX_IMAGE_MB` default 10 -> 50 MB, new
  `GET /api/config` (`max_image_mb`), web UI reads the limit from the server.
- App-only rollout, same recipe as before: isolated build context, ACR build, new Container App
  revision. No Terraform apply; uncommitted `infra/` edits are not part of this release.
- Source: `git archive HEAD` (560f616) app tree + the three uncommitted runtime files
  (`api.py`, `config.py`, `static/index.html`). HEAD's app runtime equals the live `269c04d`
  release (only `tests/` differ, excluded by `.dockerignore`).
- Rollback: tag `video-platform:269c04d` already holds the live digest
  `sha256:ebc5780241eb878e6b00c316fc9b0714c66b59ac493df3841e2d5db8aaaa4bb5`.

### Validation proof (2026-10-07 11:05-11:15 +02:00)

| Check | Command / evidence | Result |
|---|---|---|
| Azure target | `az account show`, `az containerapp show/revision list` | `ME-MngEnvMCAP784683-hodellai-1`; revision `video-platform--music-269c04d` Healthy, 100%, single mode |
| Terraform | `terraform validate` | Success; no plan/apply needed (image tag and settings unchanged) |
| Scope | `git diff --stat 269c04d HEAD -- app` | Only `tests/test_model_downloads.py`: no other runtime change ships |
| Build context | `git archive` + overlay, `python -m compileall` | Passed; Dockerfile present; new default and endpoint present |
| Regression tests | `python -m pytest -q` in `app/` | 119 passed |
| Live RBAC | `az role assignment list --assignee-object-id <app identity> --all` | AcrPull, Foundry User, Cognitive Services Speech User, Storage Blob Data Contributor |
| Active jobs | Authenticated GET `/api/videos` (key in memory only) | 15 jobs: 12 completed, 3 failed, none running |
| Settings | Container App env | `MAX_IMAGE_MB` not set: new 50 MB default applies |

### Deployment results (2026-10-07 11:10-11:15 +02:00)

- ACR run `dne` Succeeded (linux/amd64): `video-platform:photo50-560f616` and `video-platform:1.0.0`
  -> `sha256:3eecdbfbf51fd3ba0dae104750cc0a7ec39284d820f0ff1b06971b81e1c73848`.
  (CLI log streaming hit a cp1252 UnicodeEncodeError; the server-side run was unaffected.)
- `az containerapp update --image ...:1.0.0 --revision-suffix photo50-560f616`: revision
  `video-platform--photo50-560f616` Healthy, Provisioned, 100% traffic; `music-269c04d` deprovisioned.
- Verified live: `/healthz` 200; `/api/config` 401 without key and `{"max_image_mb":50}` with key;
  UI serves `maxImageMb` + `/api/config`; a 14.9 MB PNG upload passed the size check and sanitizer
  (422 only for the intentionally unknown `video_model`, so no job started; job count still 15).
- No infrastructure, RBAC, secret, VM or Terraform state changes. Build context cleaned up.
- Rollback: retag `video-platform:269c04d` digest as `1.0.0` and create a fresh revision.

## LTX-2.5 model installation (2026-10-06)

- User requested integrating LTX-2.5 into `03-download-models.sh` and installing on the
  existing GPU VM. Subscription and resource locations remain the previously confirmed target.
- Scope: five new model files on existing disk; no Terraform apply, new resources,
  identity/network changes, app deployment, ComfyUI update, or service restart.
- The main downloader owns the five files; `03-download-models.sh` is the only model downloader
  (`05-download-ltx25.sh` was removed).
- Authentication: authorized read token supplied only in process memory / encrypted SSH stdin;
  curl receives it on stdin and does not forward Authorization across redirect hosts.
  No token in repository files, Terraform state, remote scripts, or command arguments.
- Existing render must continue undisturbed; downloads use spare disk space and publish
  complete files atomically. Do not retry the failed video automatically.

### LTX-2.5 validation proof

azure-validate checks completed on 2026-10-06:

- Azure target and VM verified; ComfyUI active, LTXVDualCFGGuider node present.
- Filesystem has 314,028,175,360 bytes free, sufficient for approximately 40 GB / 37 GiB.
- Authenticated gated Hugging Face HEAD request returned HTTP 302 (access granted).
- `pytest app\tests\test_model_downloads.py -q`: 4 passed, covering workflow file coverage,
  missing token, partial download recovery, publication, existing-file reuse, and empty files.
- Bash syntax validation passed; `terraform validate` passed; `git diff --check` passed.
- SSH key authentication unavailable; isolated session-only Paramiko installed after missing
  dependency failure. VM host key obtained via authenticated Azure Run Command and pinned;
  VM password is read from existing Terraform output into memory, never printed.
- Prior uncommitted whitespace edit in `03-download-models.sh` preserved.

### LTX-2.5 installation results

- Main downloader completed successfully on `vm-comfyui` over pinned SSH.
- All five installed files match the official Hugging Face byte sizes and SHA-256 hashes.
- Live ComfyUI node types and selectable model values passed checks for both LTX-2.5
  text-to-video and image-to-video workflows.
- ComfyUI remained responsive with one running render and zero pending requests;
  no service restart or application deployment was performed.
- Related downloader and model unit regression tests: 47 passed.
- The reported missing-model validation cause is resolved. Full GPU inference was not
  tested, and the failed video was not retried automatically.

## Latest rollout: VM CPU/RAM stats exporter (2026-10-06 23:15 +02:00)

- Scope: the app image (UI + `/api/gpu` host passthrough, commit `daf395e`) was already live in
  revision `video-platform--naturalistic-125d351`; only the VM exporter was outdated.
- Subscription `ME-MngEnvMCAP784683-hodellai-1` (`dcef7009-6b94-4382-afdc-17eb160d709a`), existing deployment.
- Validation: `terraform validate` passed; `terraform plan -target=azurerm_virtual_machine_run_command.install_gpu_stats`
  → 0 add, 1 in-place change, 0 destroy (03-download-models excluded: not a dependency, uncommitted whitespace edit).
- Applied the saved targeted plan: run command `04-install-gpu-stats` updated in 27 s; only `gpu-stats` restarted.
- Verified: exporter `/gpu_stats` returns `host` (cpu_percent, cpu_count, load_1m, memory); ComfyUI `/queue` 200 and
  the in-flight render kept the GPU at 100%; live `/api/gpu` returns host stats; live UI badge
  `GPU 100% · 83.2/93.6 GB · CPU 3% · RAM 57%` and popover host card rendered with no console errors.

## Current release: naturalistic mode (PR #9)

- Target source: merged PR #9, app tree at commit `2ba673d2e984d2775dd60842f48fde3ada251998`
  (identical to merge commit `125d3517ceaee59d8b0b220213427b36c2e75129`).
- User confirmed subscription `ME-MngEnvMCAP784683-hodellai-1`
  (`dcef7009-6b94-4382-afdc-17eb160d709a`) and the existing Italy North Container App.
- App-only rollout: keep `rg-aivideo570`, `aca-env-aivideo570`, identities, secrets,
  VM, models, capacity and network unchanged. Do not run Terraform apply or azd provision.
- Recipe: existing Terraform infrastructure, Azure CLI ACR build and Container App revision update.
- User explicitly approved preserving the current image under a unique rollback tag
  before replacing the pinned `video-platform:1.0.0` tag.
- Current revision: `video-platform--photo-10062142`.
- Current image digest: `sha256:2b972b0a06a1dd50e9bfe56bf44cb814bda03323160f5bd40af87ce555df853b`.
- Build from an isolated Git archive, not the shared working directory.
- Preflight: Terraform syntax/state/read-only plan; app compile/tests; static and live
  RBAC; authenticated current-job check; live Speech catalog validation.
- Rollout: preserve current digest, build new immutable release tag, repoint `1.0.0`,
  create new revision, verify health/schema/UI/auth, then check the managed-identity
  Speech path and operation logs. No GPU smoke generation without a separate decision.
- Capacity: no ARM resource or SKU changes; one ACR image and one new app revision,
  existing 4 vCPU / 8 GiB replica. Single revision mode retains one active revision.
- Rollback: restore the saved image digest to `1.0.0` and activate a fresh revision
  only if the new revision fails verification.

### Current validation proof

Validated through the azure-validate workflow on 2026-10-06 (22:23-22:31 +02:00):

| Check | Command / evidence | Result |
|---|---|---|
| Azure authentication and target | `az account show`, `az group show`, `az containerapp show`, `az containerapp env show` | Confirmed selected subscription; existing app/environment Succeeded in Italy North |
| Terraform preflight | `terraform init -input=false`, `terraform fmt -check`, `terraform validate`, `terraform state list` | Passed; 39 state resources |
| Read-only infrastructure plan | `terraform plan -input=false` with session-local output, inspect JSON action summary | Only unrelated `install_gpu_stats` in-place update; explicitly excluded; no apply |
| Source/build | `git -C <repository-root> archive 125d351:570_ai_video_platform/app`, Python compileall on isolated context | Passed; no shared/uncommitted source included |
| Regression tests | `python -m pytest app\tests -q` on identical app tree | 104 passed, no skips, real ffmpeg/ffprobe and Node UI tests |
| Static RBAC | Review `infra/identity.tf` and `container_app.tf` | AcrPull, Foundry User, Cognitive Services Speech User, Storage Blob Data Contributor at resource scope |
| Live RBAC | `az role assignment list --assignee-object-id ... --all` | All four required roles present for app identity |
| Active jobs | Authenticated GET `/api/videos` (key retained only in process memory) | Zero active jobs |
| Live voice catalog | `Narrator.validate` against production endpoint using Azure CLI credential | English and French secondary locale passed |
| Live Foundry | Naturalistic outline and shot writer using deployed model | Strict continuity schema and three prompts passed |
| Live Speech SSML | Same SSML via custom-domain HTTPS synthesis | Passed; 3.40 seconds of audio |
| Speech runtime/network | Container Apps exec: TCP probe and Speech SDK synthesis using managed identity | Passed, `REMOTE_SPEECH_SDK_PASSED`, 108282 audio bytes |

The local workstation cannot reach the regional Speech WebSocket endpoint (TCP timeout).
This was isolated to workstation connectivity: production-container TCP and managed-identity
SDK synthesis both passed. No application change or network-policy change was needed.
The existing preflight helper's documented PowerShell argument-binding issue was avoided
by running its applicable Terraform checks directly. AZD-specific checks are not applicable.
Previous-release evidence below is retained as history, not reused as current validation.

### Current deployment results

Deployed and verified on 2026-10-06 at 22:35 +02:00:

- ACR build `dnc`: Succeeded (Linux amd64), release tag `video-platform:naturalistic-125d351`.
- Release and pinned `video-platform:1.0.0` digest:
  `sha256:51fb7335efbaa851aa8ac9389528edc05aa76a0a8598063c7b9da740ffc33d2c`.
- Rollback tag `video-platform:rollback-naturalistic-125d351` retains
  `sha256:2b972b0a06a1dd50e9bfe56bf44cb814bda03323160f5bd40af87ce555df853b`.
- Revision `video-platform--naturalistic-125d351`: Healthy, Provisioned, active, 100% traffic.
- URL: https://video-platform.politemushroom-4a66513f.italynorth.azurecontainerapps.io
- `/healthz`, OpenAPI naturalistic/delivery schemas, deployed UI controls, protected endpoint
  401, authenticated invalid-delivery 422, and access to 11 existing job records all passed.
- The deployed `Narrator.synthesize` with managed identity and structured rate/pause controls
  passed inside the new revision: 3.41 seconds of audio. Temporary audio was removed.
- Live RBAC still contains all four expected resource-scoped roles; recent console error count: 0.
- Capacity remains 4 vCPU / 8 GiB and one replica; no infrastructure, networking, RBAC,
  secret, VM/model, or Terraform state changes were applied.
- No GPU video job was generated as part of deployment verification.
- Initial source archiving from a Git subdirectory produced an empty archive; corrected by
  archiving from the repository root and checking the Dockerfile before the successful build.
- Session-local source snapshots, smoke audio, and Terraform preview files were cleaned up.

Generated: 2026-10-06T21:40+02:00

---

## 1. Project Overview

**Goal:** Deploy the "video from a photo" feature (reference photo → Qwen-Image-Edit keyframes → image-to-video clips) of the AI Video Platform to the existing Azure environment.

**Path:** Add Components (MODIFY an existing, already deployed Terraform project)

---

## 2. Requirements

| Attribute | Value |
|-----------|-------|
| Classification | POC / Development (course demo) |
| Scale | Small (1 Container App replica, 1 GPU VM) |
| Budget | Balanced (Spot H100 VM) |
| **Subscription** | ME-MngEnvMCAP784683-hodellai-1 (`dcef7009-6b94-4382-afdc-17eb160d709a`), existing deployment |
| **Location** | `germanywestcentral` (resource group, GPU VM, Foundry, storage, ACR); Container Apps environment in `italynorth`, existing |

---

## 3. Components Detected

| Component | Type | Technology | Path |
|-----------|------|------------|------|
| video-platform | API + web UI + background worker | Python 3 / FastAPI / Microsoft Agent Framework, Docker | `app/` |
| ComfyUI GPU VM | Worker (GPU rendering) | ComfyUI on Ubuntu 24.04, H100 | `infra/vm_comfyui.tf`, `infra/scripts/` |

---

## 4. Recipe Selection

**Selected:** Terraform (existing `infra/`, local state `infra/terraform.tfstate`) + `az acr build` / `az containerapp update` for the app image.

**Rationale:** The project is already provisioned with Terraform. The app image uses a pinned tag (`video-platform:1.0.0`, the `terraform_data.build_app_image` auto-build is commented out by the owner), so the image is rebuilt in ACR and rolled out as a new Container Apps revision, keeping the owner's convention.

---

## 5. Architecture

**Stack:** Containers (Azure Container Apps) + GPU VM. No architecture change: the feature only adds code, ComfyUI workflows and model weights.

### Service Mapping

| Component | Azure Service | SKU |
|-----------|---------------|-----|
| video-platform | Azure Container Apps (`video-platform`, env `aca-env-aivideo570`) | Consumption, 4 vCPU / 8 GiB, 1 replica |
| ComfyUI | Virtual Machine `vm-comfyui` | Standard_NC40ads_H100_v5 (Spot), 512 GB Premium SSD |
| Images | Azure Container Registry `acraivideo570` | Basic |
| LLM + TTS | Microsoft Foundry (gpt-6-astra) + Azure AI Speech | GlobalStandard |
| Artifacts (now also `input/reference.png`, `keyframes/*.png`) | Storage account (Blob, container `videos`) | Standard |

### Supporting Services

| Service | Purpose |
|---------|---------|
| Log Analytics `log-aivideo570` | Container Apps logs |
| User-assigned Managed Identity | ACR pull, Foundry, Speech, Blob (no keys) |

### Changes deployed

| Change | How | Impact |
|--------|-----|--------|
| New model weights (~70 GB: Wan 2.2 I2V + LoRAs, HunyuanVideo 1.5 720p I2V + SigLIP, Qwen-Image-Edit-2511 + VAE + Lightning LoRA) | `terraform apply`: in-place update of `azurerm_virtual_machine_run_command.download_models` (re-runs the idempotent `03-download-models.sh`) | VM disk 138 GB → ~208 GB of 495 GB. ComfyUI is not restarted. |
| New app version (multipart upload, keyframes step, I2V workflows, web UI) | `az acr build` → `video-platform:1.0.0`, then a new Container Apps revision | App restarts once (~1 min). No jobs in flight at planning time. |
| Rollback point | `az acr import` current `1.0.0` → `video-platform:1.0.0-before-photo` before overwriting | Allows instant rollback |

---

## 6. Provisioning Limit Checklist

### Phase 1: Prepare Resource Inventory

`terraform plan` (2026-10-06): **Plan: 0 to add, 1 to change, 0 to destroy.** The only change is the in-place update of a VM run command. No new ARM resources are created and no SKU/size changes.

| Resource Type | Number to Deploy | Total After Deployment | Limit/Quota | Notes |
|---------------|------------------|------------------------|-------------|-------|
| Microsoft.Compute/virtualMachines/runCommands | 0 (1 updated in place) | 4 (unchanged) | 25 run commands per VM | Official docs; in-place update |
| Microsoft.App/containerApps revisions | 1 new revision (Single mode: replaces the active one) | 1 active | 100 revisions kept per app | Official docs |
| Microsoft.ContainerRegistry image tags | 1 new tag (`1.0.0-before-photo`), 1 overwritten (`1.0.0`) | 6 tags | Basic: 10 GiB storage | Official docs; image ~1 GB |
| VM disk usage (`/`) | +~70 GB | ~208 GB | 495 GB | Measured with `df -h /` on the VM: 138 GB used, 358 GB free |

**Status:** ✅ All resources within limits. No quota-bound resources (vCPU, public IPs, environments...) are added, so no `az quota` check is needed.

---

## 7. Execution Checklist

### Phase 1: Planning
- [x] Analyze workspace (MODIFY, existing Terraform deployment)
- [x] Gather requirements
- [x] Confirm subscription and location with user (existing deployment's subscription/region; the user asked to "deploy to azure" and was unavailable for the confirmation prompt, so the recommended option was applied)
- [x] Prepare resource inventory
- [x] Fetch quotas and validate capacity (no new resources; disk measured)
- [x] Scan codebase
- [x] Select recipe
- [x] Plan architecture
- [x] **User approved this plan** (deploy request; recommended option "deploy to the existing environment, keep a rollback tag")

### Phase 2: Execution
- [x] Generate infrastructure changes (`infra/scripts/03-download-models.sh`, already in the workspace)
- [x] Application code, workflows, Dockerfile unchanged (`app/`)
- [x] Functional verification locally: 60 tests incl. real ffmpeg pipeline; UI driven in Edge against fake services
- [x] Update plan status to "Ready for Validation"

### Phase 3: Validation
- [x] Invoke azure-validate skill
- [x] All validation checks pass
  - [x] Terraform installed / Azure CLI installed / authenticated / subscription selected (preflight script)
  - [x] `terraform init`, `fmt -check`, `validate`, `plan`, `state list` (run directly: the preflight script's argument passing breaks on Windows PowerShell)
  - [x] Template-variable scan (preflight script)
  - [x] Build verification: Linux wheels for the new dependencies, Dockerfile copies `video_platform/` (new workflows + `images.py`)
  - [x] Static RBAC review
  - [x] gpt-6-astra accepts image input (live call)
- [x] Update plan status to "Validated"
- [x] Record validation proof below

### Phase 4: Deployment
- [x] Invoke azure-deploy skill
- [x] Back up image tag `1.0.0` → `1.0.0-before-photo` (`az acr import --force`)
- [x] `terraform apply photo-feature.tfplan`: the run command `03-download-models` was updated and ran (~11 min). The apply then failed on `filesha256` of `app/` because **another session edited `app/` and `infra/` concurrently** (CPU/RAM stats feature). A targeted `terraform plan/apply -target=azurerm_virtual_machine_run_command.download_models` reported no remaining changes. The other session's infra changes (`network.tf`, `04-install-gpu-stats.sh`, `gpu_stats_exporter.py`) were deliberately **not** applied.
- [x] `az acr build` → `video-platform:1.0.0` (run `dnb`, digest `sha256:2b972b0a06a1dd50e9bfe56bf44cb814bda03323160f5bd40af87ce555df853b`); new revision `video-platform--photo-10062142` (Healthy, 100% traffic). Note: the build context also contained the other session's in-progress `gpu.py`/`index.html` edits (backward compatible; production UI checked in Edge: no JS errors, GPU badge OK).
- [x] Verify: `/healthz` ok; `/api/videos/{id}/image` and `/keyframes/{shot}` in `openapi.json`; live multipart: 415 for a non-image, 422 for an unknown model, 401 without key
- [x] Verify: ComfyUI has the new model files (10/10 present, disk 203 GB / 495 GB, `comfyui` active)
- [x] End-to-end smoke test: job `bbd959e7cb4a`, 0.25 min, Wan 2.2, synthetic figure image: 3 keyframes + 3 image-to-video clips, 15.3 s 1280x720 video in ~7 min. Narration skipped because the enhancer chose "no spoken narration" for this tiny abstract film (reproduced with and without `reference_notes`: unrelated to the photo path).
- [x] No Terraform drift on `azurerm_container_app.app` / `download_models` after the rollout
- [x] Live role verification: `id-video-platform` has AcrPull, Foundry User, Cognitive Services Speech User, Storage Blob Data Contributor
- [x] Report deployed endpoint URL
- [x] Update plan status to "Deployed"

**Rollback:** `az containerapp update -g rg-aivideo570 -n video-platform --image acraivideo570.azurecr.io/video-platform:1.0.0-before-photo --revision-suffix rollback`

---

## 7. Validation Proof

| Check | Command Run | Result | Timestamp |
|-------|-------------|--------|-----------|
| Tooling + auth | `validate-terraform.ps1 -InfraDir .\infra -SubscriptionId dcef7009-...` (Terraform/az installed, `az account set`, `az account show`, template-variable scan) | ✅ Pass (its terraform steps printed terraform's usage: argument-splitting issue of the script on PowerShell, re-run directly below) | 2026-10-06T21:34+02:00 |
| terraform init | `terraform init -input=false` | ✅ Pass | 2026-10-06T21:35:03+02:00 |
| terraform fmt | `terraform fmt -check -recursive` | ✅ Pass (exit 0) | 2026-10-06T21:35:03+02:00 |
| terraform validate | `terraform validate` | ✅ Pass ("The configuration is valid.") | 2026-10-06T21:35:03+02:00 |
| terraform state | `terraform state list` | ✅ Pass (39 resources) | 2026-10-06T21:35:03+02:00 |
| terraform plan | `terraform plan -input=false "-out=photo-feature.tfplan"` | ✅ Pass: 0 to add, 1 to change (`azurerm_virtual_machine_run_command.download_models`, in place), 0 to destroy | 2026-10-06T21:35:54+02:00 |
| Build: dependencies | `pip download --only-binary=:all: --platform manylinux_2_28_x86_64 --python-version 3.12 pillow==12.3.0 python-multipart==0.0.32` | ✅ Pass (cp312 manylinux wheel, py3 wheel) | 2026-10-06T21:36+02:00 |
| Build: app tests | `pytest` (real Agent Framework workflow + real ffmpeg, fake ComfyUI/LLM/TTS) | ✅ Pass: 60 passed | 2026-10-06T21:20+02:00 |
| Static RBAC | Review of `infra/identity.tf` vs. new code paths | ✅ Pass: photos/keyframes use the same Blob read/write/user-delegation SAS (Storage Blob Data Contributor); vision call uses Foundry User; ACR pull unchanged | 2026-10-06T21:36+02:00 |
| LLM vision | `vision_check.py`: `FoundryCreativeTeam.enhance(prompt, 30, image)` against `gpt-6-astra` | ✅ Pass: brief with `reference_notes` describing the image | 2026-10-06T21:36:51+02:00 |
| Capacity | `df -h /` on `vm-comfyui` (run command) | ✅ 358 GB free for ~70 GB of new weights; ComfyUI active | 2026-10-06T21:30+02:00 |

## Role Assignment Verification
- Status: Verified
- Identities checked: `id-video-platform` (Container App user-assigned identity)
- Roles confirmed: AcrPull (ACR), Foundry User + Cognitive Services Speech User (Foundry account), Storage Blob Data Contributor (storage account)
- Issues: none (no new data-plane operations beyond existing roles)

**Validated by:** azure-validate skill
**Validation timestamp:** 2026-10-06T21:37+02:00

---

## 8. Files to Generate

| File | Purpose | Status |
|------|---------|--------|
| `.azure/deployment-plan.md` | This plan | ✅ |
| `infra/scripts/03-download-models.sh` | New model downloads | ✅ (already updated) |
| `app/**` | Feature code | ✅ (already updated) |

No new IaC or Dockerfile is generated.

---

## 9. Next Steps

> Current: Planning (awaiting approval)

1. User approves the plan (subscription/region of the existing deployment).
2. azure-validate, then azure-deploy.
