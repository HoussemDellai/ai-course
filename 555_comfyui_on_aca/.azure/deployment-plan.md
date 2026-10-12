# CUDA 13 ComfyUI verification deployment

Status: Deployed and Verified

## Scope

Add an isolated `comfyui-cu130-a100` app to the existing Terraform-managed
`rg-aca-gpu-nvidia-comfyui` resource group in Sweden Central, subscription
`25a98a18-5e94-4b21-9d17-e8cf45bfd81f` (Microsoft-Azure-1).
Preserve the CUDA 12.6 app and all unrelated infrastructure changes.

## Architecture

- Existing `aca-env-gpu-nvidia`, `GPU-NC24-A100` workload profile.
- Verified `yanwk/comfyui-boot:cu130-slim` image, isolated application code.
- Read-only NFS model-source mount, independent outputs and runtime files.
- HTTPS ingress on port 8188; zero minimum and one maximum replica.
- Existing Terraform workflow; no azd conversion.

## Validation and deployment gates

Verify image manifest, profile capacity, resource health and model availability.
Validate Terraform and the explicit-endpoint Python API verifier before deployment.
Review a fresh saved Terraform plan: no unrelated changes, deletions or replacements.
Use azure-validate before azure-deploy. Stop for user input if safe planning is blocked.

## Functional acceptance

Capture driver, PyTorch CUDA 13.x and A100 evidence from the deployed replica.
Require synchronized CUDA and BF16 operations and two non-cached Z-Image-Turbo
generations yielding decodable 1024x1024 PNGs. Record exact versions and artifacts.
Confirm preservation of CUDA 12.6 and leave scale-to-zero configured.

## Execution tracking

1. Prerequisites: manifest verified; environment healthy; A100 usage 1 of 2.
   Supported A100 profile: 24 cores, 220 GiB, one GPU. Resource Health API
   does not support this resource type; use revision/environment health.
   Existing app model API initially timed out during cold start.
2. Isolated app and verifier: configured; ten focused Python tests pass,
   Python compilation passes, notebook JSON parses, Terraform validation passes.
3. Validation and safe plan: passed; fresh saved plan adds only the CUDA 13 app
   and the read-only storage binding (2 additions, 0 changes, 0 deletions).
4. Deployment and live inference: passed. Revision `comfyui-cu130-a100--0000003`
   startup proves driver 580.159.04, PyTorch 2.14.1+cu130, CUDA runtime 13.0,
   Python 3.13.15, A100 and BF16 matrix/attention PASS. Exact revision URL
   produced two different-seed, decoded 1024x1024 images.
5. Observed compatibility documentation: recorded in Readme.md.

The approved detailed plan is stored in the Copilot session workspace.

## 7. Validation Proof

- `python -m unittest -v test_verify_comfyui_cuda13`: 10 tests passed.
- `python -m py_compile verify_comfyui_cuda13.py verify_cuda13_runtime.py`: passed.
- Notebook JSON parsing: passed.
- `terraform fmt -check aca_comfyui_cu130_a100.tf`: passed.
- `terraform validate -no-color`: passed, including existing provider/state setup.
- `terraform state list`: existing backend/state accessible.
- `terraform plan -no-color -out=<session-files>\cuda13.tfplan`: passed.
  Action-only JSON review confirms exactly the two intended creations and no
  modifications or deletions. Existing role assignments are unchanged; the new
  NFS binding requires no new RBAC assignment or secret.
- `az containerapp env list-usages`: A100 quota limit 2, current usage 1.
- Existing app `/object_info`: model inventory available after cold start.
- Equivalent targeted preflight commands were used instead of the generic
  preflight script, which would overwrite the user's existing `tfplan` and
  recursively check unrelated formatting. Dependencies were already initialized.
- Azure MCP discovery returned no tools; Azure CLI was used for live checks.

## Deployment and runtime proof

Initial apply created only two resources. Subsequent reviewed plans changed only
the CUDA 13 app to fix CRLF shell arguments and add startup runtime diagnostics.
The startup command uses explicit LF joins and image-bundled application files.
The runtime proof passes before ComfyUI starts. One initial GPU availability
check failed during activation; the final revision's startup and GPU checks
subsequently passed. No CPU fallback was used.

Azure CLI exec encountered management timeouts and a websocket 404. Runtime
checks were wired into startup instead; console logs record the actual versions,
BF16 PASS and ComfyUI commit `daeb5e53681e2b10a3f0727d9ec5bc90784bee10`.
Read-only HTTP transport failures are retried at most three times within a
deadline and explicitly logged; POST inference submissions are never retried.

Exact-revision verification:
- Endpoint: https://comfyui-cu130-a100--0000003.kindbeach-59c96b47.swedencentral.azurecontainerapps.io
- Prompts: `6078f00e-3b3d-41cc-ba28-b74e591af327`,
  `a36dcbca-f570-4c04-bb30-b4d238296044`.
- Image/report artifact directory in the session: `files\cuda13-images\4f1281fa1d32412b9393e6a25974b4b7`.
- Startup proof in the session: `files\cuda13-proof-success.txt`.
- Final focused tests: 11 passed; Python compilation, Terraform formatting
  check on the app and Terraform validation passed.
- CUDA 12.6 baseline comparison: identical revision/template/ingress.
- New model storage binding verified `ReadOnly`; zero minimum / one maximum replica.
