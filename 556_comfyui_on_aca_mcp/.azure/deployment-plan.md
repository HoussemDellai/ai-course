# ComfyUI and official MCP on ACA

Status: Deployed and Verified

Approved scope: new isolated Terraform deployment in subscription
`2524a5e1-00d7-43c2-a7cf-a87b79df2415`, Sweden Central, prefix `556`.
New resource group `rg-aca-gpu-nvidia-comfyui-mcp-556`; no existing resources
are imported or modified. Base commit: `4ea0055bb13a2b85018b5b90202f5339e71fd2cf`.

## Architecture

- New VNet, private Azure Files NFS storage, Log Analytics and ACA environment.
- Public HTTPS ComfyUI CUDA 13/A100 app, zero to one replica; no model downloads.
- Separate CPU Consumption MCP app, one replica, authenticated HTTPS `/mcp`.
- Official comfy-mcp 0.10.0, comfy-cli 1.22.0 and MCP SDK 2.3.0.
  Native Streamable HTTP is available: no separate stdio bridge is needed.
  A loopback-only HTTP/WebSocket forwarder satisfies CLI discovery restrictions.
- Private ACR image pull through managed identity.
- VS Code Copilot configuration example; no agent or OAuth app registration.

## Gates

Validate focused tests, Terraform and subscription/region GPU quota before apply.
Invoke azure-validate then azure-deploy. Review saved plans for isolation.
Never copy state or secrets from another scenario. Never print the MCP token.
Public ComfyUI is intentionally not protected by the MCP token.

## Verification

Reject missing/incorrect tokens, initialize MCP, list tools, and query real
backend node information. No model downloads or generation submissions.
Read-only API checks may activate the GPU and incur charges.

## Progress

Worktree created on branch `demo/comfyui-aca-mcp` from origin/main.
Source-only baseline copied; native HTTP and official node discovery passed
against a test backend. Authentication and HTTP/WebSocket forwarding tests pass.
Terraform validation passes with AzureRM 5.10.0 and AzAPI 2.13.0.
Region supports Consumption-GPU-NC24-A100; environment count quota has 50 free.
Serverless GPU quotas are environment-scoped: create only the environment and
its prerequisites first, check its A100 usage/limit, then deploy remaining
resources. No GPU app is created before that check.

## 7. Validation Proof

- Python 3.12 isolated environment installed pinned requirements successfully.
- `python -m unittest -v test_gateway`: 12 tests passed, including real CLI
  subprocess node discovery against a test HTTP backend, authentication,
  protocol initialization, tool filtering, actionable errors, WebSocket relay.
- Python compilation, PowerShell parser checks and Copilot JSON parsing passed.
- Terraform init, formatting and validate passed.
- Full saved base plan: 17 creations, no updates/deletions; resource group
  references all target the new isolated group.
- Separate saved environment bootstrap plan contains only environment and
  prerequisites. Serverless A100 quota is checked before remaining provisioning.
- Equivalent targeted preflight commands used to preserve reviewed, named
  stage plans and avoid the generic script's unrelated recursive scans and
  nonexistent-state failure on a brand-new stack.
- State, plans and the DPAPI-protected token artifact are ignored by Git.
- Static RBAC: only the MCP identity receives AcrPull, scoped to this ACR.
  NFS mounts use private networking, not an ineffective storage RBAC assignment.
- Subscription policy assignments inspected; no blocking policy identified.
- Local Docker daemon is unavailable; native tool integration is tested locally.
  Linux image build is gated on ACR provisioning and must pass before MCP apply.
- Azure environment count: 0/50 in Sweden Central; A100 profile is supported.
  Regional dedicated-GPU quota is not applicable to the serverless profile.

## Deployment and live verification

- October 20, 2026: bootstrap environment created; serverless A100 quota 0/2.
- Base stack: 17 total Terraform resources; remaining base apply added 12,
  without modifying/deleting existing resources.
- AzureRM 5 requires explicit `logs_destination = "log-analytics"`; corrected
  and validated before resuming the environment creation.
- Private NFS uses no shared keys; configuration explicitly disables shared-key
  authentication, avoiding storage-policy drift.
- ACR build `dt1` succeeded for Linux amd64; image digest
  `sha256:6fe0842437ab5dd0e0d1a1a8baa116a28fbd8ae35ad3b6efb4e3adcbf9b20deb`.
- Live AcrPull role verified on the scenario ACR for the MCP identity.
- MCP-stage plan added only `azurerm_container_app.mcp[0]`; apply succeeded.
- MCP revision `comfy-mcp--qq41b9v` is healthy on CPU Consumption, replicas 1/1.
- ComfyUI revision `comfyui-cu130-a100--y6y0vqc` is healthy on A100, scale 0/1.
  Backend system stats: ComfyUI 0.38.2, PyTorch 2.14.1+cu130, A100 80GB.
- Read-only verifier: missing/wrong token rejected with 401; valid token
  initialized MCP, listed ten tools and retrieved actual KSampler node schema.
- Four model folders checked through MCP: checkpoints/diffusion_models/
  text_encoders/vae each returned total=0 and files=[].
- No model download or generation submission performed.
- Evidence is in ignored `verification/mcp.json` and
  `verification/model-inventory.json`; token is not included.
- Final saved-state plan returned detailed exit code 0 (no changes).
- Four Terraform tests passed with explicit bootstrap/deployed test variables.
- Existing `comfyui-aivideo571--0000002` and `video-platform--0000004` revisions
  remained unchanged.
- The stock PowerShell preflight wrapper was also attempted after deployment;
  its argument-binding defect invoked bare Terraform instead of its subcommands.
  This was a helper failure, not an infrastructure validation failure.
  Equivalent direct init/fmt/validate/plan/state checks are used for final proof.
- Final direct preflight passed: init, recursive fmt check, validate, plan
  (detailed exit code 0) and state list (18 isolated resources).
- Dependency lock is included in the scenario's versionable files; state,
  local variables and credentials remain ignored. Completed saved plans were
  removed because they contain sensitive values.
- Copilot example contains the deployed URL and a password input, not the token.
  Interactive VS Code connection remains a user action.
