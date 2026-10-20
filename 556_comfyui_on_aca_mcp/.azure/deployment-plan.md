# ComfyUI MCP: remove authentication

Status: Deployed and Verified

## Approved change

The user explicitly approved anonymous public MCP access, deployment to the
existing app, and a follow-up PR merged into main after tests and verification.
Anyone reaching the endpoint can invoke workflow/job tools and incur GPU charges.
This is an intentionally open, disposable demo, not a production configuration.

## Azure context and scope

- Subscription: `2524a5e1-00d7-43c2-a7cf-a87b79df2415`.
- Location: Sweden Central.
- Resource group: `rg-aca-gpu-nvidia-comfyui-mcp-556`.
- Existing app: `comfy-mcp`, CPU Consumption, minimum/maximum replicas one/one.
- Endpoint: https://comfy-mcp.agreeablecliff-e935d0a6.swedencentral.azurecontainerapps.io/mcp
- Branch: `demo/comfyui-mcp-no-auth`, based on origin/main after PR #14.

Remove bearer-token middleware and startup validation, Terraform token input,
ACA secret and environment reference, token helper, and Copilot password/header
configuration. Update tests, read-only verifier and README.

Preserve HTTPS, tool allowlist, backend routing, managed-identity ACR pulls,
ComfyUI GPU app, storage, networking, and all profile/scaling settings.
No models will be downloaded and no generation will be submitted.

## Execution

1. Remove authentication across runtime, infrastructure and client configuration.
2. Validate focused Python/Terraform tests and build a new Linux image in ACR.
3. Review a saved plan changing only the MCP app; deploy via azure-deploy.
4. Verify anonymous initialization, ten tools and real backend node discovery.
5. Verify the app has no token secret/reference and Terraform reports no drift.
6. Commit, push, open a PR to main, merge without bypasses and verify ancestry.

## Gates and considerations

- Invoke azure-validate before azure-deploy.
- Inspect plan JSON without printing old secret values.
- No new Azure resources or quota increases are needed.
- Historical state/backups and legacy ignored token files may retain the retired
  token; do not publish or rewrite them.
- Existing public ComfyUI exposure is unchanged.
- Previous authenticated deployment history remains in Git; do not mistake its
  old proof for anonymous-access verification.

## 7. Validation Proof

- October 20, 2026: 12 focused Python tests passed, including anonymous MCP
  initialization, tool discovery and a real CLI backend query with MCP_TOKEN unset.
- Four mocked Terraform tests passed, including no ACA secrets or token
  environment reference, HTTPS and unchanged CPU Consumption scaling.
- Terraform formatting and validate passed. Python compilation, Copilot JSON
  (no inputs/headers) and PowerShell syntax checks passed.
- ACR Linux amd64 build dt2 succeeded; image digest
  `sha256:20161f0d95b8801de67a3448c10cd25bb0d8d729e3deea53ad819ae9c3ecade7`.
  The initial local CLI log stream failed on Windows character encoding, but
  the server-side build succeeded. The build helper now suppresses streamed
  build logs to avoid that encoding failure.
- Saved deployment plan: one in-place update, `azurerm_container_app.mcp[0]`;
  no creates/deletions or GPU/backend changes. Planned secrets and MCP_TOKEN
  environment references are absent.
- Static RBAC unchanged: managed identity retains AcrPull scoped to the ACR;
  no Azure identity/image-pull authentication is removed.

## Live verification

- Applied the reviewed plan: 0 added, 1 changed, 0 destroyed.
- New revision `comfy-mcp--0000001` is healthy. The live app has only
  COMFY_BACKEND_URL in its environment and no configured token secrets.
- Both exact-revision and stable public URLs passed anonymous initialize,
  tool-list (ten tools), actual KSampler discovery and model-folder queries.
- Reports: ignored `verification/anonymous-revision.json` and
  `verification/anonymous-mcp.json`; no token or generation submission.
- The first request during ingress rollout reached the previous revision and
  returned 401. After the new revision was ready, anonymous protocol calls
  succeeded. The first node call then timed out while the scale-to-zero GPU
  started; a read-only system-stats warmup returned the A100, after which both
  complete MCP verifications passed. No errors were hidden or bypassed.
- GPU revision remains `comfyui-cu130-a100--y6y0vqc`. Registry AcrPull is unchanged.
- Final Terraform plan returned detailed exit code 0 (no changes). The
  completed sensitive saved plan was removed before PR publication.
