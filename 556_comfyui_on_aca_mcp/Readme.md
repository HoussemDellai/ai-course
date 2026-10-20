# ComfyUI + official Comfy MCP on Azure Container Apps

An isolated Terraform demo with two apps:

| App | Workload profile | Replicas | Access |
| --- | --- | --- | --- |
| ComfyUI CUDA 13 | Serverless A100 GPU | 0-1 | Public HTTPS UI/API |
| Official Comfy MCP | CPU Consumption, 0.5 vCPU / 1 GiB | 1 | Public HTTPS `/mcp`, bearer token |

Use the MCP endpoint directly from GitHub Copilot in VS Code. No agent is
deployed. This scenario does not manage the original
[ComfyUI demo](../555_comfyui_on_aca/Readme.md) or the video-platform demo.

## What is hosted

[Comfy's official MCP](https://docs.comfy.org/agent-tools/mcp) has two variants:
the hosted Comfy Cloud endpoint runs on Comfy Cloud; the open-source
[comfy-mcp](https://github.com/Comfy-Org/comfy-mcp) drives your own ComfyUI.
This demo uses the latter, not the Comfy Cloud service.

The official console command uses stdio, but its underlying MCP SDK supports
Streamable HTTP natively. [gateway.py](mcp/gateway.py) registers the official
tool functions with that native HTTP transport and a fail-closed bearer-token
middleware. No third-party ComfyUI MCP implementation or stdio bridge is needed.

`comfy-cli` restricts local node discovery to loopback HTTP. A loopback-only
HTTP/WebSocket forwarder on port 8188 routes **all** local tool traffic to the
GPU app over HTTPS, rather than inspecting the CPU gateway. Only port 8000 is
exposed through ACA.

Exposed official tools: `nodes`, `search_models`, `system_stats`,
`search_templates`, `get_template`, `run_template`, `generate_image`, and `job`.
Two constrained adapters also call the official implementation:

- `run_workflow`: accepts an API-format JSON workflow object instead of a path
  into the gateway filesystem.
- `fetch_outputs`: returns backend download URLs, without accepting an arbitrary
  output directory or writing files into the gateway.

Installation, local process lifecycle, model download, partner-cloud credential,
and other local-filesystem tools are not exposed. Gallery/template discovery
may access Comfy's public catalog, but no Comfy Cloud account is required for
local GPU execution. Built-in templates can change upstream.

**No models are downloaded.** Node discovery works without models; generation
will fail until you explicitly provision the workflow's required models in the
new NFS share. Neither deployment nor the read-only verifier submits a workflow.
Outputs are local to the GPU replica and must be downloaded before scale-down.

## Important demo limitations and costs

- The MCP token protects **only MCP**. ComfyUI's public UI/API is intentionally
  unauthenticated, matching the selected demo configuration. Anyone with its
  URL can call it directly, bypass MCP, and potentially incur GPU charges.
  Do not use this exposure for production.
- Read-only requests can wake the A100 and incur GPU startup/runtime charges.
- One ready MCP replica, Basic ACR, logs, private networking and the configured
  **1 TiB premium Azure Files share** incur charges even without inference.
- GPU capacity is regional and not guaranteed by a supported-profile listing.
  Environment-level A100 quota is checked after the environment exists.
- The bearer token is a sensitive Terraform input and ACA secret. Terraform
  state and saved plans still contain it in plaintext. Keep them private,
  encrypted at rest, and out of Git. Configure a protected remote state backend
  if collaborating; this standalone demo defaults to local state.
- The optional token helper uses Windows DPAPI: its file can only be decrypted
  by the same Windows user on the same machine. Back up credentials securely.
- Dependencies are version-pinned in [requirements.txt](mcp/requirements.txt);
  the deployed image is digest-pinned. Upstream Comfy MCP is AGPL-3.0-or-later
  or commercially licensed; review its terms before distributing/modifying it.

## Prerequisites

- Azure CLI, Terraform >= 1.14 and < 2, and PowerShell 7.
- Permissions to create resources and assign `AcrPull` to a managed identity.
- A100 Consumption support and quota in the selected region.
- Python 3.12 for local tests/verifier. Docker Desktop is optional: ACR builds
  the Linux image remotely.

Defaults: subscription `2524a5e1-00d7-43c2-a7cf-a87b79df2415`, region
`swedencentral`, prefix `556`, resource group
`rg-aca-gpu-nvidia-comfyui-mcp-556`. Review before provisioning. Both providers
receive the explicit subscription, independently of your Azure CLI default.

## Deploy with Terraform

Run from this scenario directory in its separate worktree. Do not copy another
demo's state or `.terraform` directory.

### 1. Prepare configuration and token

```powershell
Copy-Item .\terraform.tfvars.example .\terraform.tfvars
.\scripts\New-McpToken.ps1
$secure = Import-Clixml .\.mcp-token.clixml
$env:TF_VAR_mcp_token = [PSCredential]::new("mcp", $secure).GetNetworkCredential().Password
terraform init
terraform fmt -check
terraform validate
```

The token is never a Terraform output. Do not put it on the command line,
in committed configuration, or in screenshots.

### 2. Provision the base stack

Leave `enable_mcp = false` initially. There is no public placeholder MCP app.

```powershell
terraform plan "-target=azurerm_container_app_environment.aca_environment" "-out=environment.tfplan"
# Review and apply only the environment prerequisites first.
terraform apply environment.tfplan

$subscription = "2524a5e1-00d7-43c2-a7cf-a87b79df2415" # Your selected subscription
$rg = terraform output -raw resource_group_name
$environment = terraform output -raw environment_name
az containerapp env list-usages --subscription $subscription -g $rg -n $environment
# Stop if the A100 Consumption quota does not allow one GPU.

terraform plan "-out=base.tfplan"
# Review: only new resources in this scenario; no existing-resource changes.
terraform apply base.tfplan
```

AzureRM cannot declare serverless GPU profiles directly; the existing
Terraform-managed CLI workaround adds only `GPU-NC24-A100`, with an explicit
subscription. Consumption is retained; no dedicated D4 or extra T4 app is created.

### 3. Build and deploy MCP

```powershell
.\scripts\Build-McpImage.ps1
```

The final line is the digest-pinned image reference. Set `enable_mcp = true`
and `mcp_image = "<that reference>"` in your ignored `terraform.tfvars`.

```powershell
terraform validate
terraform plan "-out=mcp.tfplan"
# Review: only the authenticated MCP app is added.
terraform apply mcp.tfplan
terraform output mcp_url
terraform output comfyui_url
terraform output portal_url
```

ACR admin access is disabled. The new app pulls using a user-assigned managed
identity and its `AcrPull` role. No public app is enabled until its real
authenticated image exists. Subsequent image upgrades use another build,
update `mcp_image`, and apply a reviewed plan; Terraform remains the source of
truth for the app's image and registry.

## Connect GitHub Copilot in VS Code

1. Open the new worktree in VS Code.
2. Use **MCP: Open Workspace Folder MCP Configuration** (or your existing
   workspace MCP configuration) and merge the example from
   [copilot/mcp.json](copilot/mcp.json); do not replace unrelated servers.
3. The example contains the verified demo endpoint. For another deployment,
   replace its URL with `terraform output -raw mcp_url`.
4. Start `comfy-aca`. VS Code prompts for the token using a password input.
   Retrieve it locally from your secret manager or decrypt the DPAPI file;
   do not paste it into a committed JSON file.
5. In Copilot Chat, select the server's tools and ask:
   **"Using comfy-aca, inspect the KSampler node and list model folders.
   Do not submit a workflow or download models."**

Interactive Copilot confirmation is a user action; successful API verification
does not by itself prove that the VS Code UI has connected.

On Windows, to paste your saved token into the VS Code password prompt without
printing it in terminal history:

```powershell
$secure = Import-Clixml .\.mcp-token.clixml
[PSCredential]::new("mcp", $secure).GetNetworkCredential().Password | Set-Clipboard
# Paste into the VS Code prompt, then clear the clipboard:
Set-Clipboard -Value ""
```

Avoid clipboard history/sync for secrets; use your secret manager instead if
those features are enabled.

## Read-only verification

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\mcp\requirements.txt
Push-Location .\mcp
..\.venv\Scripts\python.exe -m unittest -v test_gateway
Pop-Location

$env:MCP_TOKEN = $env:TF_VAR_mcp_token
$endpoint = terraform output -raw mcp_url
.\.venv\Scripts\python.exe .\scripts\verify_mcp.py `
  --endpoint $endpoint --report .\verification\mcp.json
```

The verifier requires 401 for absent/incorrect tokens, then initializes MCP,
lists tools, inspects the live backend's `KSampler` and lists model inventory.
It fails explicitly on protocol/backend/tool errors. No generation is submitted.
The focused tests also verify HTTP errors, WebSocket forwarding, omitted local
tools, output URL mapping and invalid configuration.

Infrastructure regression tests run without creating Azure resources:

```powershell
terraform test
```

If the GPU is cold, open `terraform output -raw comfyui_url`, allow startup to
finish, inspect the GPU app's console/system logs, and rerun verification.
Do not confuse an ACA health probe with successful backend/tool verification.

## Rotate the token and clean up

To rotate, generate a fresh secret through your secret manager (or explicitly
remove/recreate only `.mcp-token.clixml`), update `TF_VAR_mcp_token`, review/apply
the Terraform plan, and update the VS Code password input. Keep the new token
for subsequent applies, and remove token environment variables when finished.

To remove **only this isolated demo**, run `terraform plan -destroy` in this
scenario directory, review every resource, then explicitly approve its
destruction. Never run destroy against another scenario's state.

## Verified deployment

Observed on October 20, 2026:

- [MCP endpoint](https://comfy-mcp.agreeablecliff-e935d0a6.swedencentral.azurecontainerapps.io/mcp):
  revision `comfy-mcp--qq41b9v`, healthy, CPU Consumption, one ready replica.
- [ComfyUI UI/API](https://comfyui-cu130-a100.agreeablecliff-e935d0a6.swedencentral.azurecontainerapps.io):
  revision `comfyui-cu130-a100--y6y0vqc`, healthy, A100, zero-to-one scaling.
- Live backend: ComfyUI 0.38.2, PyTorch 2.14.1+cu130, NVIDIA A100 80GB.
- Missing/wrong MCP tokens: 401. Valid token: initialize, ten tools, live
  KSampler schema and model-folder queries succeeded.
- `checkpoints`, `diffusion_models`, `text_encoders` and `vae`: zero model files.
  No model downloads or generation submissions were performed.
- 12 Python gateway tests and four mocked Terraform tests passed.
- Final Terraform plan reported no changes. Existing video-platform app
  revisions were unchanged. Interactive VS Code integration remains for you
  to try; inference is intentionally unverified without models.

The ignored `verification` directory contains read-only API evidence. The
ignored `.mcp-token.clixml` file holds the local DPAPI-protected credential.
