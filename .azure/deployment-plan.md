# Five-second ComfyUI portrait video

Status: Deployed and Verified

## Goal and approved scope

Generate a real five-second image-to-video MP4 of the latest generated adult
woman inside a sunlit house. Use the portrait as a reference; likeness may vary.
The user approved installing video models, adjusting the existing container,
and creating this deployment plan.

## Azure context

- Subscription: ME-MngEnvMCAP752444-hodellai-1,
  `2524a5e1-00d7-43c2-a7cf-a87b79df2415`.
- Region: Sweden Central.
- Resource group: `rg-aca-gpu-nvidia-comfyui-mcp-556a`.
- Existing GPU app: `comfyui-cu130-a100`, A100 Consumption.
- Recipe: AZCLI, scoped update of the existing app only.
- Existing Terraform source: `556_comfyui_on_aca_mcp/aca_comfyui_cu130_a100.tf`.

## Planned changes

1. Change GPU container from 2 vCPU / 4 GiB to 8 vCPU / 32 GiB.
2. Change maximum replicas from ten to one, preserving scale-to-zero.
3. Preserve image, environment, storage, ingress, identity and all other settings.
4. Store Wan 2.2 5B, UMT5 FP8 and Wan 2.2 VAE weights on the existing NFS mount.
5. Upload the generated portrait only to the existing backend, create an indoor
   reference, and submit an image-conditioned Wan video through MCP.
6. Download the result locally and verify an exact five-second MP4 duration.

## Resource inventory and cost

No new Azure resources, networking, storage capacity, identities, or quota
increases. One existing A100 replica maximum; existing storage and GPU/runtime
charges apply. Higher CPU/RAM allocation remains configured after completion.
No paid partner APIs and no transmission to an external image-generation service.

## Validation and deployment gates

Inspect live configuration and supported resource limits, validate Terraform,
confirm the app-scoped update arguments, and invoke azure-validate before applying.
Keep existing unrelated working-tree changes intact.

Preparation completed: live configuration confirms 2 vCPU / 4 GiB and ten
maximum replicas. Azure's supported A100 profile has 24 cores and 220 GiB memory,
so the proposed 8 vCPU / 32 GiB is within the profile. The existing Terraform
source and directly related README now reflect the approved settings. Only an
app-scoped CLI update will be deployed; unrelated Terraform changes will not
be applied. Existing image-pull configuration and RBAC remain untouched.

## 7. Validation Proof

2026-10-20: Azure CLI authentication and existing resource reads succeeded.
`terraform fmt -check aca_comfyui_cu130_a100.tf` passed. Full module validate
is excluded from this app-only deployment because of the unrelated existing
CUDA 12.6 dependency error documented below.
The isolated Bicep compiled and `az deployment group validate` returned
`Succeeded`. Initial what-if showed one existing app modification, no resource
creates/deletes, CPU 2 -> 8, RAM 4 -> 32 GiB, max replicas 10 -> 1, and explicit
minimum zero. Two omitted zero-valued defaults were then preserved in the
validation template. Final preflight returned `Succeeded`; final what-if
confirmed exactly one existing app modification with only the approved
CPU/RAM, maximum replicas, and explicit scale-to-zero minimum changes.
No image build or new role assignments are necessary.

### All validation checks pass

- Core AZCLI validation: CLI/auth, compile the isolated app-update Bicep,
  resource-group deployment validate and what-if against current live properties.
- Docker build: not applicable; the deployed image is unchanged.
- Azure policy: server-side resource validation for the existing app update.
- Static RBAC: not applicable to the GPU app, which has no managed identity;
  the separate MCP registry identity and permissions are unchanged.
- Terraform formatting: passed for the modified GPU file.
- Full module Terraform validation failed on a pre-existing undeclared dependency
  in the unrelated CUDA 12.6 file. That module will not be deployed. The scoped
  AZCLI app update is validated independently and does not deploy that file.

## Verification

The app-scoped `az containerapp update` succeeded. Live verification confirms
8 vCPU / 32 GiB, max replicas one, minimum zero, and a healthy ready revision
`comfyui-cu130-a100--0000001`. Image, NFS mount and identity (`None`) are
unchanged. No role assignments were added or changed.

All three video models were downloaded to NFS, checked against publisher file
sizes and SHA256 hashes, and atomically installed. MCP template validation now
reports `runnable: true`.

An indoor reference was created by masked background replacement, preserving
the latest portrait's face. Wan generation job
`70f1ba7d-2c79-4b54-8f62-4640c79ec0ba` was submitted through MCP: 81 generated
frames, trim to 80, encode at 16 FPS for exactly five seconds.

The Wan job completed successfully. The MP4 was downloaded before scale-down.
A five-frame contact sheet confirms the same woman indoors with natural eye and
head movement and a stable room background. All frames decoded successfully.
The initial backend MP4 reported 4.999 seconds due to timestamp quantization;
local constant-frame-rate encoding corrected this rather than rounding the
reported duration.

Final `Woman_at_home_5s.mp4`: H.264, 768 x 640, 80 frames at 16 FPS, stream and
container duration both exactly 5.000000 seconds, 1,664,279 bytes, no audio.
FFprobe assertions and a complete FFmpeg decode passed. The final deliverable
is saved in the session files directory. Temporary validation templates,
parameters, intermediate mask and unnormalized video were removed.
