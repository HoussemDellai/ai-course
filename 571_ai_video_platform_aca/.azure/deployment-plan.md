# Azure deployment plan: AI Video Platform 571

Status: Deployed and verified (cinematic-cutaway update, 2026-10-20).

## Current update: optional cinematic document cutaways

- User requested deployment to the same previously confirmed subscription and
  existing video-platform app in rg-aivideo571, Italy North.
- Recipe: Terraform with the existing default workspace/backend and education.tfvars.
- Scope: content-addressed ACR image build and CPU application revision only.
  Preserve GPU workers, settings, sidecar, identities, roles, networking and storage.
- Option remains off by default. Do not start paid generation or mutate existing jobs.
- Feature verification: 75 tests passed, including exact 5-second windows, audio
  preservation, horizontal/vertical output, GPU failure handling and retry reuse.
- All validation checks pass: fresh init/format/schema/tests, saved plan,
  image-only structural comparison, role verification and build checks.

### Section 7: Cinematic-cutaway validation proof

- 2026-10-20: Azure login and existing app confirmed; current revision 0000005.
- No active jobs: five completed, one failed, one awaiting review. Preserve all seven.
- `terraform init -input=false -lockfile=readonly`, recursive fmt check,
  `terraform validate` and `terraform test` passed (8 tests).
- Fresh full plan with education.tfvars and state-managed HF secret preserved:
  only image-build marker replacement and in-place app image update.
- Structural comparison verifies all fields other than the application image
  are identical, including GPU workers, sidecar, resources, probes and env.
- Target image: `video-platform:education-80f3198bcb7f`.
- Python compilation and pip dependency check passed; 75 feature/shared tests
  passed in the implementation turn. No source changes since those tests.
- Static and live roles confirmed: resource-scoped AcrPull, Foundry User,
  Speech User and Blob Data Contributor. No new role assignment needed.
- Recipe remains plain Terraform, not AZD; no new policies, services or capacity.

### Cinematic-cutaway deployment results

- Saved-plan apply succeeded; ACR build `dn9` completed successfully.
- Image: `video-platform:education-80f3198bcb7f`;
  digest `sha256:1c894c7618bf79cb58ea155fd0ffded340be05a715c4a9ddc637f72afc70e333`.
- Revision `video-platform--0000006` is Healthy and Provisioned, serving 100% traffic.
- Live HTML contains the cinematic-cutaway checkbox. OpenAPI exposes the boolean
  document option with default false and the five-second/every-30-second behavior.
- Authenticated config confirms PDF, PowerPoint and narration availability.
- Synthetic rendering check inside the deployed container passed: 65-second output,
  cutaways at 30 and 60 seconds, original narration AAC stream byte-for-byte unchanged.
  Temporary files were cleaned automatically. No paid AI/Speech/GPU job was started.
- All seven existing job IDs/statuses and both GPU revisions are unchanged.
- Live identity roles remain correct; fresh full Terraform plan reports no changes.
- Application: https://video-platform.orangeground-c268819f.italynorth.azurecontainerapps.io

## Current update: PowerPoint/PDF narrated-video scenario

- User requested deployment of the implemented scenario to the existing deployment.
- Retain the previously approved subscription, regions, resource group, environment,
  GPU workers, identities, permissions, storage and application configuration.
- Recipe: existing Terraform backend and education.tfvars. Build the content-addressed
  education container through ACR and update only the CPU application revision.
- Inspect a fresh saved plan before apply; reject GPU, storage, networking, RBAC,
  destructive or unrelated changes. Do not start paid video generation jobs.
- Prior local verification: 129 regression tests passed, dependency check and Python
  compilation passed; browser PDF upload produced a playable narrated MP4 with
  stubbed AI/Speech and real FFmpeg.
- Pending: live context, job activity, Terraform validation/plan, identity verification,
  ACR build/deployment, healthy revision and authenticated document capability checks.
- Target confirmed against the existing deployment and current Azure login.
  Confirmation form was unavailable in autopilot; proceed under the user's explicit
  "deploy it" request using the unchanged, previously approved target and scope.

### Section 7: Document-video validation proof

All validation checks pass (2026-10-20, document-video update):
- Terraform installed and existing default workspace/backend accessible.
- Azure CLI authenticated to the existing subscription; no target/region change.
- `terraform init -input=false -lockfile=readonly`, recursive format check and
  schema validation passed on 2026-10-20.
- `terraform plan -input=false -no-color -var-file=education.tfvars -out=<private
  session plan> -detailed-exitcode` passed with preserved state-managed HF secret.
  Exact inspected changes: local image-build marker replacement and CPU app update.
  Structural comparison confirms only the video-platform container image changes;
  sidecar, env, CPU/RAM, probes and all GPU resources remain identical.
- Target image: `acr4aivideo571.azurecr.io/video-platform:education-3767a142920f`.
- `terraform test -no-color`: 8 passed. Python compilation and `pip check` passed.
- Existing application has no active generation jobs (three completed, one review).
- Live identity retains AcrPull, Foundry User, Speech User and Blob Data Contributor.
- Static identity.tf review confirms the same least-privilege resource-scoped roles.
- Prior app verification: 129 tests, Python compilation and dependency check passed.
- No AZD template variables or new resource types/policies apply to this image-only update.

### Document-video deployment results

- Inspected saved-plan apply succeeded; ACR build `dn8` succeeded.
- Image: `video-platform:education-3767a142920f`;
  digest `sha256:f91e9d0a9baf5eadb10aa262e45026500ad369079025d1d67499bbf9d2733c3d`.
- Revision `video-platform--0000005` is Healthy, Provisioned, ready and serving
  100% of ingress traffic. Prior revision drains with zero traffic.
- HTTPS health check succeeded; authenticated config confirms PDF, PowerPoint and
  narration configured, 50 MB upload limit and 60-page limit. New UI and OpenAPI
  document-upload endpoint verified.
- Real LibreOffice conversion and PDF text extraction succeeded inside the deployed
  container using a synthetic PowerPoint and temporary files, cleaned automatically.
  An initial text-match assertion was whitespace-sensitive; the normalized,
  short-title conversion check passed. No AI/Speech generation job was started.
- All four existing jobs remain unchanged (three completed, one awaiting review).
- Both GPU revisions are unchanged. Live identity retains all four expected roles.
- Fresh full post-deployment Terraform plan returned exit code 0: no changes/drift.
- Application: https://video-platform.orangeground-c268819f.italynorth.azurecontainerapps.io

## Current update: two-worker ComfyUI rollout

- User approved Terraform deployment to the existing subscription
  `2524a5e1-00d7-43c2-a7cf-a87b79df2415` (ME-MngEnvMCAP752444-hodellai-1),
  resource group `rg-aivideo571`, environment `aca-env-aivideo571` in Italy North.
  Supporting resources remain Germany West Central.
- Recipe: Terraform, existing default workspace/local backend, education.tfvars.
  Preserve the primary GPU app, current 2-vCPU/32-GiB sizing per worker, model
  weights, identities, permissions, networking, storage and existing HF secret.
- Add one always-on A100 worker with its own URL; user approved its ongoing cost.
  Wire both workers into the updated educational orchestrator and GPU monitoring.
  Isolate secondary writable media/user directories and local runtime temp.
- Source/scripts changed: expect local build/provisioning markers to rerun,
  the model job configuration and primary runtime revision to update, and a
  content-addressed educational application image build. Model inventory is
  unchanged; provisioning reuses existing completed downloads.
- Deploy only after inspecting a fresh full saved plan. Reject unrelated changes,
  primary replacement, Azure resource deletion and new permissions.
- All validation checks pass:
  - Confirm subscription/regions/cost, backend and CLI authentication.
  - Verify no active platform job and empty existing worker queues.
  - Verify environment-specific A100 quota, workload profile and subnet capacity.
  - Initialize locked providers; run format/schema and mocked Terraform tests.
  - Retain locally verified Python parallel-rendering regressions.
  - Generate a new private plan preserving the state-managed HF secret in memory.
  - Inspect the exact resource/field scope and existing live identity roles.
  - Apply only that inspected saved plan, then verify healthy revisions, both
    ComfyUI endpoints, CUDA/A100 telemetry, models and application URL wiring.
  - Verify the new application code and two-server GPU API without starting work.
  - Generate a fresh post-deployment plan and require no remaining changes.
- No generation, approval, retry or paid benchmark jobs may be started.
  Existing completed/awaiting-review jobs remain untouched.

### Section 7: Two-worker validation proof

- Target/cost explicitly confirmed by user on 2026-10-20.
- Azure CLI authentication and existing group/environment confirmed; environment
  provisioning state Succeeded.
- Managed-environment A100 quota: current 1, limit 2. Generic quota MCP could not
  retrieve this service's quota; the authoritative environment usage API succeeded.
- Platform jobs: two completed, one awaiting review; no active job. Existing
  primary ComfyUI queue: running 0, pending 0.
- Existing default workspace/backend initialized with locked providers; recursive
  formatting and Terraform schema validation passed. Mocked tests: 8 passed.
- Python implementation validation: 206 impacted cases passed across local runs.
  One unchanged legacy T4-profile assertion conflicts with the existing environment
  in HEAD; it is unrelated to this deployment and was not used as readiness proof.
- `terraform plan -input=false -no-color -detailed-exitcode
  -var-file=education.tfvars -var=comfyui_worker_count=2` saved a new private plan;
  exact scope: primary update with preserved ID/moved address, secondary creation,
  orchestrator/model-job updates, and two local Terraform marker replacements.
  No Azure deletion/replacement, credential change, new RBAC or unrelated change.
- Container field inspection confirms preserved CPU, RAM, image (GPU/model job),
  mounts and executable commands. Changes are the intended startup/provisioning
  arguments, worker identity/version, and application image.
- Source build verification: Python compilation passed; runtime dependencies and
  Dockerfile remain unchanged. Content-addressed image
  `video-platform:education-e951b4fee6f6` will be built by Terraform's existing
  ACR helper during apply. Registry Succeeded with admin credentials disabled.
- Live application identity roles verified at their existing resource scopes:
  AcrPull, Foundry User, Speech User and Storage Blob Data Contributor.
- Existing delegated ACA subnet is 10.11.0.0/23; the extra worker fits the address
  space. Current primary revision is Healthy with one active replica.
- Quota-safe rollout uses two fresh full Terraform plans rather than concurrent
  primary update/secondary creation: first apply count=1 to roll the primary and
  application; verify it healthy, then plan/apply count=2 to add the secondary.
  The first-phase saved plan contains exactly the five expected changes with no
  secondary deletion. This avoids a possible third-GPU revision overlap at quota 2.
- The stock validation helper was not used: it hardcodes an existing tfplan name
  and omits education.tfvars. Equivalent initialization, format/schema, state,
  authentication and fresh-plan checks were run explicitly without overwriting
  existing plans or printing state secrets. This project is plain Terraform, not
  AZD: no new AZD environment, placeholder infrastructure or redundant RBAC created.

### Two-worker rollout progress

- Primary-phase inspected Terraform apply succeeded. Model provisioning execution
  `download-models-aivideo571-d2blbrf` succeeded, reusing installed model inventory.
- ACR build `dn7` succeeded for `video-platform:education-e951b4fee6f6`.
- Primary revision `comfyui-aivideo571--0000002` became Healthy; prior revision
  deprovisioned. Environment A100 use returned to 1/2 before phase two.
- Live primary verification: one CUDA A100, expected input/output/user/temp paths,
  empty queue, all 66 required workflow node types and 33 model filenames available.
- Application revision `video-platform--0000003` is ready with the new image.
  Authenticated GPU API reports the one primary; original two completed jobs and
  one awaiting-review job are unchanged.
- Fresh secondary-phase Terraform plan inspected: exactly secondary creation and
  orchestrator update for both URL lists. No primary/model job/build/RBAC changes.

### Two-worker final verification (2026-10-20)

- Both inspected Terraform applies succeeded. Phase two created one GPU app and
  updated only the orchestrator's ComfyUI/telemetry URL lists.
- Active healthy GPU revisions, each with exactly one replica:
  - Primary: `comfyui-aivideo571--0000002`.
  - Secondary: `comfyui-aivideo571-2--hvamsp5`.
- Managed-environment A100 usage is 2/2. Primary rollout overlap was allowed to
  finish and release its old GPU before secondary creation.
- Both live `/system_stats` endpoints report one CUDA A100. Runtime argv confirms
  primary legacy input/output/user paths, separate secondary paths, and local
  worker-specific temp paths. Both queues are empty.
- Each `/object_info` exposes all 66 required node types and 33 required model
  filenames. This checks runtime inventory, not generated-output quality or speed.
- Application revision `video-platform--0000004` is ready with
  `video-platform:education-e951b4fee6f6`, built by Terraform/ACR run `dn7`.
  Manifest digest:
  `sha256:3b4996cee4f8f593353108e6f64f21774b95434dedc61f905b078f8265febdde`.
- Application UI returns HTTP 200, health is ok, and authenticated `/api/gpu`
  reports exactly two online servers with no errors. Live application environment
  variables match both Terraform URL outputs in primary/secondary order.
- Existing application identity roles rechecked live and unchanged: AcrPull,
  Foundry User, Speech User and Storage Blob Data Contributor.
- Original jobs remain two completed and one awaiting review; no job was started,
  approved, retried or benchmarked.
- Fresh full default two-worker Terraform plan returned exit 0, no changes.
  One concurrent read-only verification initially encountered that plan's local
  state lock; it was rerun successfully after the plan finished, without unlocking
  or modifying state.
- Temporary private saved plans containing sensitive values were removed after
  inspection/apply/drift verification. Existing plans, Terraform state/backups and
  unrelated local work were preserved.
- Application:
  https://video-platform.orangeground-c268819f.italynorth.azurecontainerapps.io
- Primary:
  https://comfyui-aivideo571.orangeground-c268819f.italynorth.azurecontainerapps.io
- Secondary:
  https://comfyui-aivideo571-2.orangeground-c268819f.italynorth.azurecontainerapps.io

## Previous update: hybrid educational style rollout

- User confirmed the existing subscription `2524a5e1-00d7-43c2-a7cf-a87b79df2415`,
  resource group `rg-aivideo571`, ACA Italy North and supporting resources Germany
  West Central. Recipe: Terraform using `infra/education.tfvars` and the existing
  local backend. PR #12 is merged; source commit `deffbcb` is on remote main.
- Deploy only the content-hash educational app image and its local build marker.
  Preserve current GPU allocation, model inventory/provisioning marker, inline
  state-managed HF secret, storage, networking and role assignments.
- Existing jobs `c77e66e01e48` and `d69b5f44dbd2` are completed; `bce07698216c`
  awaits review. No actively rendering job was returned by the preflight API check.
  Do not approve, retry or submit any paid generation jobs during verification.
- Keep unrelated local changes untouched. Do not reuse or overwrite existing saved
  Terraform plans. Read sensitive state only into process memory and never print it.
- All validation checks pass:
  - Verify CLI authentication, subscription, existing environment and backend.
  - Initialize without provider upgrades; check Terraform formatting/schema.
  - Run Terraform tests and retain the recent 100 passing educational regressions.
  - Generate a fresh full plan with the existing sensitive variable preserved.
  - Assert the plan changes only the app image and local image-build marker.
  - Verify existing identity/ACR pull roles and successful image build.
  - Apply the reviewed saved plan, then verify healthy revision, endpoint, UI and
    deployed hybrid request schema without starting a render.
  - Verify a fresh post-deploy plan has no remaining changes and remove new plans.

### Section 7: Hybrid rollout validation proof

- `terraform init -input=false -lockfile=readonly -no-color`: passed using the
  existing local backend and locked providers; no upgrades.
- `terraform fmt -check -recursive` and `terraform validate -no-color`: passed.
- `terraform test -no-color`: 4 passed, including inline/key-vault secret paths.
- Hybrid application validation before PR #12 merged: 100 educational tests passed;
  broader cinematic/audio/resolution regressions passed; Python compilation passed.
- Fresh full `terraform plan -input=false -no-color -detailed-exitcode
  -var-file=education.tfvars -out=<private-session-plan>`: exit 2, expected changes.
  Existing inline HF secret supplied only from state to the process environment,
  then cleared. No secret values were printed.
- JSON scope assertions passed: only `terraform_data.build_app_image` replacement
  (a local marker) and `azurerm_container_app.app` in-place image update.
  Nested app-template comparison confirmed no changes beyond the app image.
  Identity, registry, secrets, ingress, profile and environment remain unchanged.
- Planned image: `acr4aivideo571.azurecr.io/video-platform:education-53181fcfa709`.
  App remains 3.5 CPU/7 GiB plus unchanged draw.io sidecar 0.5 CPU/1 GiB.
- Live existing managed identity roles verified: AcrPull on the registry, Foundry
  User, Speech User and Blob Data Contributor on their existing scopes.
- Authenticated active-job recheck: two completed jobs and one awaiting review,
  no active generation. No new rendering/provider requests submitted.
- Preflight runner was not used because it overwrites existing `infra/tfplan`
  and omits the required education variable file. Equivalent checks above used
  the correct variables and a new private saved plan without overwriting user files.
- Registry is Succeeded, admin access disabled; existing ACA environment is
  Succeeded in Italy North. Image build is performed by Terraform's existing
  ACR local-exec provisioner during the reviewed apply, before the app update.

### Hybrid rollout verification (2026-10-20, 06:58 UTC)

- Reviewed Terraform apply started at 06:54 UTC and succeeded: one local build
  marker replaced and one existing app updated in place. No other resources changed.
- ACR build `dn6` succeeded; image `education-53181fcfa709` pushed with digest
  `sha256:38998e49316794f65312d0594aa0b0538d638a011b2090fa07731eb36b7c0957`.
- Revision `video-platform--0000002`: Healthy, RunningAtMaxScale, one replica,
  latest ready revision and 100% ingress traffic.
- Public `/healthz`: HTTP 200. Public HTML and a refreshed browser contain
  `Hybrid: one AI clip, then animated illustration`. The deployed OpenAPI
  EducationOptions schema accepts presentation, ai_motion and hybrid.
- Fresh full Terraform plan with the state-managed HF secret preserved returned
  exit 0: no changes. Live existing identity permissions verified again.
- Existing completed jobs remain completed; the review-pending job remains
  awaiting_review. GPU telemetry reports the existing ComfyUI server online.
  No job was created, approved or retried; no paid render was submitted.
- New secret-bearing saved plan removed from the private session directory.
  Existing saved plans and unrelated workspace edits were left untouched.
- Platform: https://video-platform.orangeground-c268819f.italynorth.azurecontainerapps.io

## Current update: UML Component native shape fix

- Failed educational job `c77e66e01e48` reports no safe native shape for UML Component.
- Live private MCP search returns title Module with `shape=module`. The existing
  explicit built-in allowlist rejects that legitimate bundled draw.io primitive.
- Add only `module` to the allowlist. Preserve asset-path restrictions, style-value
  validation and rejection of unsupported primitives. Reveal restoration uses the
  same validation path and must retain the native module shape.
- Regression tests using exact live metadata reproduce the original failures:
  2 failed, 8 passed before the fix. Validate normalization, diagram export/reveal
  restoration and the existing visual safety suite after the fix.
- Deploy a new content-hash educational image through Terraform. Preserve the
  existing inline HF secret by supplying its state-managed value in process memory.
  Do not rebuild models or update ComfyUI, permissions, networking or resource sizes.
- Verify the exact stored failed diagram through real private MCP and native export,
  without retrying the full paid video job. User approved this app-only rollout and
  explicitly declined retrying the paid video job.

### Section 7: UML Component validation proof (2026-10-19)

- Exact private metadata: UML Component is title Module, `shape=module`; remaining
  scene queries Azure Container Apps and UML Artifact also return bundled metadata.
- Native normalizer and diagram/reveal regression tests reproduce the original
  exception before the fix. After adding only module, visual and educational
  tests: 57 passed.
- Live validation helper now uses the shared native-style validator instead of
  rejecting every built-in primitive lacking mxgraph/image syntax; py_compile passed.
- Terraform formatting and schema validation passed.
- Fresh saved plan: only app image update and local build marker replacement.
  Explicit scope assertion rejects all other changes. Existing HF secret preserved.
- Build `dn4` succeeded: `education-6a649d06f166`, manifest digest
  `sha256:baa3c2beb40f3bccc0b830765de8e321b78e31e21c7762834656f6f903a6b8dd`.
- Existing AcrPull role is unchanged and already verified live. No new permissions.

### UML Component rollout verification (2026-10-19)

- Terraform apply succeeded: 1 local build marker replaced, 1 app updated in place.
  ACR build `dn5` succeeded; no GPU, model job, HF secret or RBAC changes.
- New app revision `video-platform--0000001`: Healthy, RunningAtMaxScale.
- Fresh Terraform plan with the existing HF credential preserved: exit 0, no changes.
- Exact stored scene from failed job `c77e66e01e48` successfully rendered in the new
  deployed runtime using the private MCP and native draw.io exporter.
- Assertions passed: agent uses `shape=module`, final PNG is 1920x1080,
  all three reveal PNGs are 1920x1080, and a deleted reveal rebuilds from persisted
  diagram XML with the same native module shape.
- The standalone live-validation helper is not copied into the production image.
  Verification called the deployed renderer directly. Long ACA exec commands hit a
  handshake 404; a shorter compressed diagnostic command completed with an explicit
  `UML_NATIVE_VALIDATION_PASSED` assertion.
- Temporary validation files were isolated in a temporary directory and cleaned.
  The assistant did not invoke the retry endpoint or submit image/video/Speech work.
  A final read-only check found the job had independently changed to generating
  (run 3, updated 21:08:20 UTC). Its status is not claimed to remain failed; the
  source of that retry was not determined, and the running workload was not modified.
- Platform: https://video-platform.orangeground-c268819f.italynorth.azurecontainerapps.io

## Current update: gated LTX-2.5 weights

- User explicitly approved storing the supplied Hugging Face credential in Terraform
  state after declining a new Key Vault and new RBAC resources.
- Keep the same confirmed subscription, resource group and regions. No new Azure
  resources or permissions; update the existing job's Container Apps secret,
  rerun gated provisioning, and roll the existing ComfyUI app to its matching marker.
- Credential supplied only through a process environment variable; never record
  its value in this plan, committed source, literal container env or script arguments.
  State, backups and saved plans contain it and must remain private.
- Hugging Face LTX-2.5 auth-check returned HTTP 200; ComfyUI queue verified empty.
- Preserve Key Vault-reference support and reject simultaneous credential sources.
- Validate mocked credential paths and downloader regressions, inspect saved plan,
  apply with Terraform, verify all five weights and healthy endpoints. No paid render.

### Section 7: gated-weight validation proof (2026-10-19, 20:16 UTC)

- `terraform validate`: passed.
- `terraform test`: 4 passed, including inline secret references, existing Key Vault
  support, and rejection of conflicting credentials.
- Existing venv `pytest test_model_downloads.py test_aca_runtime.py -q`: 35 passed.
- Hugging Face gated-repository access check: HTTP 200. Token not printed.
- Saved `gated-models.tfplan`: 1 local-marker replacement, 2 in-place Azure updates.
  JSON scope assertions allow only the download job, provisioning marker and ComfyUI.
  No new Azure resources, Azure deletion, app-image change or RBAC change.
- Existing app image already built and healthy; no image build is required.
- User approved the inline secret and its persistence in state and saved plans.
  Subsequent plans must supply `TF_VAR_hf_token` to retain the configured job secret.

### Gated-weight deployment verification (2026-10-19)

- Terraform apply succeeded: 1 local provisioning marker replaced, 2 existing Azure
  resources updated in place. No new Azure resources, deletion or permission changes.
- Download execution `download-models-aivideo571-ms7igi2` reports Succeeded.
- All five LTX-2.5 filenames verified in the live ComfyUI model inventory:
  transformer, text encoder, video VAE, audio VAE and latent spatial upscaler.
- New ComfyUI revision `comfyui-aivideo571--0000001` is the latest ready revision:
  Healthy, ready replica, zero restarts. A100 and 32 GiB RAM preserved.
- Platform `/healthz` and ComfyUI `/system_stats`: HTTP 200. Queue empty.
  No paid render submitted; render correctness is not claimed.
- Terraform state contains the inline job secret as explicitly approved. Its value
  was not printed or written to committed source. The generated secret-bearing
  `gated-models.tfplan` was removed after apply.
- Fresh plan with the configured sensitive variable returned exit 0: no changes.
- Earlier recovery notes about missing gated weights are superseded by this update.
- Platform: https://video-platform.orangeground-c268819f.italynorth.azurecontainerapps.io
- ComfyUI: https://comfyui-aivideo571.orangeground-c268819f.italynorth.azurecontainerapps.io

## Current update: Terraform deployment recovery

- Continue the user's partially completed deployment using Terraform only for infrastructure changes.
- Inspect the current local backend, saved plan, Azure resources and failed operations before changing configuration.
- Preserve existing user edits and unrelated work. Confirm the new subscription and regions before deployment.
- Refresh and validate a saved Terraform plan; obtain approval for replacements, RBAC changes and material cost increases.
- Apply the reviewed plan and verify resource provisioning, application readiness and endpoint health.
- Recipe: Terraform. Current validation proof will be recorded after fresh checks; historical results below do not validate this recovery.
- User confirmed subscription `2524a5e1-00d7-43c2-a7cf-a87b79df2415`,
  existing `rg-aivideo571`, Germany West Central / Italy North, and `education.tfvars`.
- Azure activity logs confirmed global resource-name collisions and model quota
  500 requested versus 250 available. User's renamed resources and 200 capacity
  are already deployed; preserve them. Foundry deployment reports Succeeded.
- A100 environment quota: 2 available, 0 used. Required managed-identity roles
  are present on the new ACR, Foundry and Blob account.
- Existing public-model download execution `download-models-aivideo571-l5hwcyu`
  is still running. Preserve it; the recovery helper waits before starting the
  educational revision, reuses completed files, and resumes partial downloads.
- Keep NFS shared keys disabled to match live configuration and avoid weakening
  access policy. No Azure resource replacement or RBAC change is planned.
- Fresh saved recovery plan: 4 add, 1 update, 2 destroy. Both destroyed objects
  are local `terraform_data` provisioning/build markers, not Azure resources.
  Azure changes: create educational orchestrator and A100 app; update download
  job for educational image weights and current provisioning revision.
- User approved applying the reviewed plan and activating always-on paid compute.
  Disclosed active-rate estimate: about USD 3.79/hour, USD 2,765 at 730 hours/month,
  excluding storage, ACR, model/Speech usage, networking and tax.
  Public unauthenticated ComfyUI exposure and missing gated weights were disclosed.
- Windows image-build helper now selects one Azure CLI application when multiple
  launchers resolve, and Terraform invokes that helper for UTF-8 logs.

### Section 7: recovery validation proof (2026-10-19)

- All validation checks pass:
  - `terraform -chdir=infra init -input=false -lockfile=readonly`: passed.
  - `terraform -chdir=infra fmt -check` and `validate`: passed.
  - `terraform -chdir=infra test -no-color`: 1 mocked plan test passed.
  - Existing venv `pytest test_aca_runtime.py test_model_downloads.py -q`: 35 passed.
  - After multiple-launcher fix, focused `pytest -k "acr_build or model_job"`:
    14 passed, including concurrency and CLI failure handling.
  - Fresh `plan -var-file=education.tfvars -out=recovery.tfplan`: 4 add,
    1 update, 2 local-marker replacements; no Azure destruction.
  - Plan JSON checked for subscription, educational runtime and 32 GiB RAM.
  - Static identity roles reviewed; matching live scoped assignments verified.
  - Template-variable scan passed; no JSON tfvars file applies.
- Bundled validation wrapper has an argument-binding bug: all Terraform calls
  printed bare CLI usage. Direct commands above passed; wrapper success is not claimed.
- Original public-model execution succeeded. Educational Linux image build `dn2`
  succeeded in ACR, tag `education-a656a43ef960`, manifest digest
  `sha256:4110d5645deed9431a285316b9a4778a9744bca6691643a0d3bab863bb344277`.
- Validation completed at 2026-10-19 approximately 19:47 UTC. User approved
  deployment; Terraform may now apply the reviewed recovery plan.

### Terraform recovery deployment verification (2026-10-19, 19:59 UTC)

- `terraform apply -input=false -no-color recovery.tfplan` succeeded:
  4 added, 1 updated, 2 destroyed. Destroyed resources were only the two local
  Terraform provisioning/build markers; no Azure resources were deleted.
- Terraform ACR build `dn3` succeeded. Educational model provisioning execution
  `download-models-aivideo571-2hv4e2y` succeeded after reusing public weights.
- Fresh `terraform plan -var-file=education.tfvars -detailed-exitcode` returned
  0: no changes, configuration and Azure state match.
- Platform UI `/` and `/healthz`: HTTP 200.
- `/api/models`: HTTP 401 without a key; HTTP 200 using the Terraform-managed key.
  The key was used in memory and not printed.
- GPU `/system_stats` and `/gpu_stats`: healthy NVIDIA A100 80 GB,
  2 CPU, 32 GiB container memory. Educational Qwen image weights are listed
  by the live model inventory.
- ComfyUI revision `comfyui-aivideo571--thlgsfc`: Healthy, replica ready,
  zero restarts. Initial endpoint timeout was startup delay; subsequent checks passed.
- Platform revision `video-platform--vx1fg1k` is running; private draw.io sidecar
  reports 10,446 indexed shapes and MCP listening on localhost port 3001.
- Live identity roles confirmed: AcrPull on ACR, Foundry User and Speech User on
  Foundry, Storage Blob Data Contributor on Blob storage. NFS shared keys remain
  disabled and public network access remains disabled.
- Queue empty; no paid render or model/Speech generation smoke test submitted.
  Render correctness is not claimed. Five gated LTX-2.5 weights still need an
  authorized Key Vault token reference; all public/educational weights provisioned.
- Platform: https://video-platform.orangeground-c268819f.italynorth.azurecontainerapps.io
- ComfyUI: https://comfyui-aivideo571.orangeground-c268819f.italynorth.azurecontainerapps.io

## Current update: Wan render memory sizing

- Failed job `cab8e81026a1`, Wan 2.2 720p: GPU container terminated with exit 137
  at 07:50:46 UTC immediately after requesting WanVAE. No preceding probe failures.
  Container restarted once; healthy again, but queued prompt/history were lost.
- System RAM allocation is 4 GiB, independently of the A100 80 GB VRAM.
  Azure's sampled working set reached 4,232,564,736 bytes near the incident.
  OOM is the leading hypothesis, not explicitly recorded as the termination reason.
  New-container cgroup counters are reset and cannot prove the prior OOM kill.
- User approved the memory-only deployment in the existing subscription and Italy
  North location through `ask_user`; paid job retry still requires approval.
- Propose 32 GiB system RAM as a validation starting point. Preserve 2 CPU, A100,
  one replica, image, models, startup, probes, networking and application app.
- Scope: expose the existing RAM allocation as a Terraform variable with backward
  compatible 4 GiB default; educational variable file proposes 32 GiB.
- Review a saved targeted plan before approval. No Terraform apply yet.
- Cost: 28 additional GiB allocated while the always-on replica runs; memory is
  billed separately from the unchanged GPU and CPU. Azure Retail Prices API for
  Italy North returns USD 0.000004/GiB-second for active/idle memory. Increment:
  USD 0.4032/hour, about USD 294.34 at 730 hours/month, before discounts/grants/taxes.
  User approved this disclosed retail estimate; account-specific rates may differ.
- Render validation: after explicit rollout/retry approval, rerun the existing Wan
  job while sampling RAM/GPU metrics and checking restart count and final output.
  Healthy probes alone are not proof that video rendering succeeds.

### Validation proof

#### Section 7: refreshed deployment validation (2026-10-12, 08:25 UTC)

- `terraform validate` and `terraform fmt -check`: passed.
- Focused ACA/RAM checks: 6 passed, 1 unrelated legacy T4 assertion deselected.
- Fresh saved plan: 0 add, 1 in-place update, 0 destroy. JSON scope assertion
  confirms `4Gi` to `32Gi` only, preserving all other template properties.
- Existing subscription/location rechecked; empty ComfyUI queue confirmed.
- Pre-rollout live configuration saved for exact post-rollout comparison.
- No image build needed; pinned image, models, startup and RBAC unchanged.
- Static/live ComfyUI identity: none; no private ACR or new role dependency.
- Targeted recovery deployment deliberately excludes the known unrelated T4
  architecture-test inconsistency. Full-suite success is not claimed.

- Terraform schema validation passed. Saved targeted plan shows exactly one
  in-place change: ComfyUI memory `4Gi` to `32Gi`; 0 add, 0 destroy.
  This is a proposed experiment, not proof of regional acceptance or render success.
- RAM configurability and remaining ACA checks: 6 passed, 1 deselected.
  Full ACA file has a pre-existing failure: architecture test forbids T4 even
  though existing environment configuration includes a T4 profile. Not changed
  as part of the RAM fix; full-suite success is not claimed.
- No Terraform apply, Azure configuration change, or render retry performed.

### Memory rollout verification (2026-10-12)

- Applied refreshed saved plan: 0 added, 1 updated, 0 destroyed.
- Revision `comfyui-aivideo571--0000003`: Healthy, latest ready revision,
  ready running replica, zero restarts.
- Exact before/after comparison confirmed memory `4Gi` to `32Gi` only;
  CPU, image, models, probes, ingress, scale, storage and identity unchanged.
- `/system_stats` returns HTTP 200 with `ram_total = 34359738368` and A100 CUDA.
  `/gpu_stats` confirms 32768 MiB memory limit and 2 CPU.
- Queue empty, platform `/healthz` HTTP 200.
- User chose to retry failed Wan job `cab8e81026a1` later. No paid render or retry
  submitted; video-render stability and required RAM peak remain unverified.
- Endpoint: https://comfyui-aivideo571.gentlemoss-8f7bc2ae.italynorth.azurecontainerapps.io

## Current update: flowchart shape handling and nested job errors

- User requested fixing the remaining failed educational job and deploying to Azure.
- Live job `f0e60871bc48` fails in diagram rendering: `VisualError: No safe bundled
  native shape for 'Flowchart Process'; revise icon_query`. MCP and Agent Framework
  TaskGroups wrap this in nested ExceptionGroups, obscuring the cause in job state.
- Target: existing `video-platform` app, `rg-aivideo571`, Italy North, subscription
  `Microsoft-Azure-1` (`25a98a18-5e94-4b21-9d17-e8cf45bfd81f`).
  Existing subscription/location confirmations remain applicable.
- Investigate live private draw.io shape metadata before changing validation.
  Preserve external-asset/style restrictions and semantic icon matching.
- Fix job/operation error formatting so nested causes remain actionable without
  discarding full traceback logging or hiding additional grouped failures.
- Recipe: existing ACR educational image build with Terraform's content-hash tag;
  update only the `video-platform` image through Azure CLI. Preserve ComfyUI,
  sidecar, networking, identities, resource allocations, secrets and scaling.
- Validation: focused shape/error regressions, real private MCP searches and native
  export of the failed scene, dependency check, IaC schema and successful image build.
- Acceptance: healthy new app revision, authenticated API, matching deployed code,
  successful real draw.io export and actionable grouped error details. Any retry
  of the user's render requires explicit approval before triggering paid providers.

### Section 7: validation proof

| Check | Command / evidence | Result |
|---|---|---|
| Shape/pipeline/error regressions | Existing venv: `python -m pytest app\tests\test_education_visuals.py app\tests\test_operations.py app\tests\test_education.py -q` | 67 passed, including failed-render retry and exact root-cause persistence |
| Dependency consistency | Existing venv: `python -m pip check` | No broken requirements |
| Existing IaC schema | `terraform -chdir=infra validate` | Passed; no plan/apply |
| Image tag | `terraform console -var-file=education.tfvars`, `local.app_image_tag` | `video-platform:education-a656a43ef960` |
| Live private MCP searches | ACA exec `search_shapes` for every failed-scene flowchart query | Verified actual styles; implicit Process rectangle and Manual Operation trapezoid caused rejection |
| Identity permissions | `az role assignment list` for existing app principal | AcrPull, Foundry User, Speech User and Blob Data Contributor present |
| Rollback / target | Live app/ACR checks and configuration snapshot | Existing healthy app revision `video-platform--0000004`; rollback image `education-1cfc056fe149` |
| Linux image build | Azure CLI bundled Python, `az acr build --registry acraivideo571 --image video-platform:education-a656a43ef960 --file drawio_runtime\Dockerfile.education --no-logs .` | ACR run `dn7` Succeeded, Linux/amd64 |
| Build digest | ACR run `dn7` output | `sha256:c41579697fea11c2567f2c22b33a502fcc5d732f7a13e7d31e546992c67fd231` |

Real native export of the exact failed scene is required after deployment.
Pre-deployment ACA exec rejected long diagnostic commands with a 404 handshake;
short commands work. Post-deployment verification will import deployed functions
and read the stored draft rather than transmit code/scene data in the exec URL.
The build helper found multiple Windows Azure CLI launchers; the existing bundled
Python launcher built successfully without modifying unrelated helper behavior.

- Scoped application build/deploy approved through `ask_user`.
- Live private MCP metadata verified all failed-scene queries: Process has an
  implicit rectangle style; Manual Operation has built-in `shape=trapezoid`.
  Document, Decision and Stored Data use existing bundled mxgraph stencils.
- Added an explicit built-in primitive allowlist and preserved flowchart geometry
  properties. Exact title matching ignores the Flowchart category prefix.
- Shared error formatting exposes all grouped leaf failures in job and operation
  state while preserving full traceback logging and cancellation behavior.

### Deployment and end-to-end verification

- Deployed `acraivideo571.azurecr.io/video-platform:education-a656a43ef960`
  to `video-platform--0000005`: Healthy, ready, 100% traffic; app and draw.io sidecar
  both ready with zero restarts.
- Exact live configuration comparison confirms app image was the only change.
  ComfyUI remains Healthy on `comfyui-aivideo571--0000002`; identity roles unchanged.
- Deployed SHA-256 hashes of `education_visuals.py`, `operations.py`, and `jobs.py`
  match tested local files; deployed nested ExceptionGroup formatting verified.
- Real private MCP/native draw.io export of the exact stored failed scene passed:
  six nodes, all six progressive-reveal PNGs, exact 1920x1080 canvas.
  Temporary verification directories/files removed automatically.
- Initial remote export verifier used a nonexistent `/app/work` directory; isolated
  `/tmp` verification succeeded. Concurrent ACA exec token conflict was resolved by
  serializing remote validation, without restarting or changing the application.
- User explicitly approved retrying existing failed job `f0e60871bc48` with normal
  provider costs. Retry completed successfully; final state has `error = null`.
- Downloaded stored final video and verified with ffprobe: 1920x1080, 24 fps,
  60 seconds, audio present. Temporary local media file removed.
- Latest operation run 5 has no failed steps and reused 7 saved artifacts.
- `/healthz` and authenticated jobs API return HTTP 200; unauthenticated jobs API
  remains HTTP 401. No new draft/job was created and approved content was unchanged.
- Endpoint: https://video-platform.gentlemoss-8f7bc2ae.italynorth.azurecontainerapps.io

## Follow-up update: educational model provisioning and runtime directory ownership

- User approved downloading the missing educational Qwen-Image model and a further
  ComfyUI rollout in the existing subscription/location.
- User separately approved assigning only the NFS `input`, `output`, and `temp`
  directory owners to `10000:10000`. Live pinned-image user is `appuser` (UID/GID 10000);
  input/output are root-owned mode 0755 and cannot accept runtime writes.
- Enable `download_education_images` in the existing educational variable file.
  Reuse the existing resumable, checksum-verified downloader and Consumption job.
- Saved targeted Terraform plan must update only the provisioning job, replace its
  local execution trigger, and update ComfyUI's provisioning version. No Azure resource
  deletion/replacement, app-image changes, RBAC changes, or resource-allocation changes.
- Verify an empty queue before applying; provisioning must finish successfully before
  ComfyUI rolls out. Existing source/model owners and existing media files stay unchanged.
- Validation: provisioning ownership/failure regressions, downloader checks, Bash syntax,
  Terraform schema/format, and exact saved-plan inspection.
- Acceptance: healthy ComfyUI, runtime-writable media directories, and all educational
  Qwen workflow nodes/model names exposed by `/object_info`. No paid render submitted.

### Follow-up Section 7: validation proof (2026-10-11, 19:11 UTC)

| Check | Command / evidence | Result |
|---|---|---|
| Regression | Existing venv: `python -m pytest app\tests\test_aca_runtime.py app\tests\test_model_downloads.py -q` | 31 passed; scoped chown precedes downloader/ready marker and failure prevents publication |
| Bash syntax | Git Bash `bash -n -s` with provisioning script on stdin | Passed |
| Terraform schema / format | `terraform -chdir=infra validate`; `terraform -chdir=infra fmt education.tfvars`; `terraform -chdir=infra fmt -check` | Passed |
| Saved targeted plan | `terraform plan -var-file=education.tfvars -target=azurerm_container_app.comfyui -out=<session artifact>` | Job and ComfyUI updated in place; only local `terraform_data.provision_models` replaced |
| Exact plan scope | `terraform show -json` recursive difference checks | Model-download flag, scoped three-directory ownership command, and provisioning-version changes only; no Azure deletions/replacements |
| Idle window | HTTPS `/queue`; `az containerapp job execution list` | No running/pending renders; previous model execution Succeeded |
| Ownership evidence | Read-only `az containerapp exec`: `id`, directory/file listings | Runtime UID/GID 10000; input/output root-owned 0755; model files readable 0644 |
| Approval | `ask_user` scope, ownership, and final saved-plan confirmations | All approved for existing subscription/location |

No application image build or RBAC propagation gate is required: pinned images,
identities, credentials, networking and resource allocations are unchanged.

### Follow-up deployment verification (2026-10-11, 20:12 UTC)

- Provisioning execution `download-models-aivideo571-koeleai` succeeded.
  The existing downloader published the educational Qwen model only after its
  pinned SHA-256 check passed. Existing public models were reused; gated LTX-2.5
  remains skipped as before because no authorized token is configured.
- Applied only the approved job/ComfyUI updates and local Terraform trigger
  replacement. No Azure resources deleted/replaced or resource allocations increased.
- Final revision `comfyui-aivideo571--0000002`: Healthy, latest ready revision,
  one running ready replica, zero restarts, 100% traffic.
- `/system_stats`, `/queue`, `/history`, `/gpu_stats` return HTTP 200; A100 80GB
  CUDA device confirmed. `/object_info` exposes every educational Qwen workflow
  node and the diffusion model, text encoder and VAE filenames.
- Real runtime write/remove checks succeeded in `input`, `output`, and `temp`
  with UID/GID 10000. All three verification files were removed. The previous
  permission-denied 3D-node import warning no longer appears in startup logs.
- Final configuration comparison preserved image, CPU/RAM, scaling, probes,
  mounts, ingress and identity. Only Git trust and provisioning version changed.
  Installing the required CLI job-log extension changed API representations:
  omitted/null optional fields, empty `targetLabel`, and default `ContainerImage`.
  These were explicitly checked and normalized, not treated as deployment drift.
- Follow-up targeted Terraform plan reports no changes.
- `video-platform--0000004` remained unchanged and `/healthz` returns HTTP 200.
- No paid image/video render was submitted; render success is not claimed.
- Endpoints:
  https://comfyui-aivideo571.gentlemoss-8f7bc2ae.italynorth.azurecontainerapps.io
  and https://video-platform.gentlemoss-8f7bc2ae.italynorth.azurecontainerapps.io

## Current update: ComfyUI startup ownership fix (2026-10-11)

- Target: existing `comfyui-aivideo571` in `rg-aivideo571`, Italy North,
  subscription `Microsoft-Azure-1` (`25a98a18-5e94-4b21-9d17-e8cf45bfd81f`).
  Subscription and existing Italy North rollout approved with `ask_user`.
- Scope: trust only the provisioned `$COMFY_DIR` Git repository before startup
  bootstrap, add regression coverage, and document the ownership failure.
- Recipe: Terraform targeted saved plan for `azurerm_container_app.comfyui`,
  using the existing local `state-571` backend and `education.tfvars`.
  Reject replacement, deletion, model provisioning, and unrelated changes.
- Preserve the current image, models, storage, CPU/RAM, replicas, probes, ingress,
  platform app and RBAC. No new resources or increased allocations.
- Validation: startup regression tests, Bash syntax, Terraform validation and
  saved-plan inspection. Refresh live revision/replica health before rollout.
- Acceptance: new healthy revision, ready replica, HTTP 200 from `/system_stats`,
  available queue/history APIs and CUDA/A100 identity. Do not submit a paid render.
- Rollback: capture the current ComfyUI configuration before deployment; only
  replace the startup arguments. Existing failed startup is not a healthy rollback.

### Section 7: ComfyUI startup validation proof (2026-10-11, 18:04 UTC)

All validation checks pass:

| Check | Command / evidence | Result |
|---|---|---|
| Startup regression | Existing venv: `python -m pytest app\tests\test_aca_runtime.py -k "bootstrap or startup" -q` | 5 passed, 16 deselected; trust precedes bootstrap and configuration failure stops startup |
| Bash syntax | Git Bash `bash -n -s` with the startup script on stdin | Passed |
| IaC schema / format | `terraform -chdir=infra validate`; `terraform -chdir=infra fmt -check` | Passed |
| Existing backend | `terraform -chdir=infra workspace show`; `terraform -chdir=infra state list` | Default workspace, existing local `state-571` backend accessible |
| Saved targeted plan | `terraform -chdir=infra plan -input=false -var-file=education.tfvars -target=azurerm_container_app.comfyui -out=<session artifact>` | 0 add, 1 in-place update, 0 destroy |
| Exact deployment scope | Inspect `terraform show -json` and recursively compare all known properties | Only `template[0].container[0].args[0]`; removing the scoped Git trust line exactly restores the previous startup command |
| Static / live identity review | Existing ComfyUI Terraform and live identity/registries | No managed identity or private ACR dependency; NFS access unchanged; no RBAC changes |
| Confirmed target | `az account show`; `az containerapp show`; `az group show`; `az containerapp env list` | Approved subscription; existing healthy Italy North environment; existing resource group metadata in Germany West Central |
| Startup failure | Live replica and recent console logs | CrashLoopBackOff, 35 restarts, repeated dubious ownership failure |
| Configuration snapshot | Read-only `az containerapp show` saved to session artifacts | Rollback/comparison context captured |
| Unaffected application | `az containerapp show` and HTTPS `/healthz` | `video-platform--0000004`, HTTP 200 |

The initial unquoted PowerShell plan arguments were rejected before planning;
quoting native arguments resolved it. The generic validation runner was not used:
it overwrites the existing `infra/tfplan`; equivalent applicable checks above preserve
that artifact and use a new scoped saved plan. No image build is needed because this
deployment changes only an inline startup argument on the existing pinned image.

### ComfyUI startup deployment verification (2026-10-11, 18:08 UTC)

- Applied the reviewed targeted plan: 0 added, 1 updated, 0 destroyed.
- Revision `comfyui-aivideo571--0000001`: Healthy, ready running replica, zero restarts,
  100% traffic. Old failed revision no longer active.
- `/system_stats`, `/queue`, `/history`, `/gpu_stats` return HTTP 200.
  CUDA identifies NVIDIA A100 80GB PCIe; ComfyUI is 0.39.0.
- Exact live configuration comparison confirmed only the scoped Git trust line changed.
  Follow-up targeted Terraform plan reports no changes.
- Platform revision `video-platform--0000004` unchanged; `/healthz` remains HTTP 200.
- Windows CLI log streaming initially failed on Unicode output; UTF-8 environment
  resolved it and confirmed ComfyUI started. A 3D-node import warning exposed the
  separate NFS runtime-write issue recorded in the approved follow-up.
- `/object_info` confirmed the educational diffusion model is missing; provisioning
  currently has `DOWNLOAD_EDUCATION_IMAGES=0`. User approved the follow-up above.

## Previous update: URL-only research sources (2026-10-11)

- Recipe: AZCLI application-only deployment using the existing subscription/locations
  and normal ACR build/storage costs already confirmed in this session. User requested deployment.
- Target: `Microsoft-Azure-1` (`25a98a18-5e94-4b21-9d17-e8cf45bfd81f`),
  `rg-aivideo571` / `video-platform` in Italy North; registry `acraivideo571`
  in Germany West Central.
- Scope: build the existing educational Dockerfile with its Terraform content-hash tag,
  update only the `video-platform` container image, and verify URL-only links under
  **Research public sources**, including the existing historical job.
- No Terraform apply, GPU/model changes, new infrastructure, sidecar changes, RBAC changes,
  secret rotation, environment changes, resource allocation changes or scaling.
- Live rollback image: `acraivideo571.azurecr.io/video-platform:education-fa59267a8953`,
  healthy ready revision `video-platform--0000003`.
- Preflight: health 200, authenticated jobs available, no active jobs; live configuration
  saved to session artifacts for comparison and rollback context.
- Validation: focused UI/persisted research/composer tests, dependency consistency,
  existing Terraform schema, identity permissions and successful Linux/amd64 build.
- Acceptance: healthy new revision, 100% traffic, deployed HTML exactly matches local file,
  real draft-source URLs visible inside the research timeline only, no titles/IDs/summary
  or duplicate Public sources panel, desktop/mobile display and safe external links.
- Do not submit a real video or mutate existing jobs during verification.

### URL-only research sources validation proof (2026-10-11, 17:13 UTC)

| Check | Command / evidence | Result |
|---|---|---|
| Focused regression | Existing venv: `python -m pytest app\tests\test_education_ui.py app\tests\test_education.py app\tests\test_naturalistic.py -k "public_source_urls or pause_edit_approve or regenerate_retains or browser_composer" -q` | 5 passed, 30 deselected |
| Dependency consistency | Existing venv: `python -m pip check` | No broken requirements |
| Existing IaC schema | `terraform -chdir=infra validate` | Passed; no plan/apply |
| Image tag | `terraform -chdir=infra console -var-file=education.tfvars`, `local.app_image_tag` | `video-platform:education-1cfc056fe149` |
| Identity permissions | `az role assignment list` for existing app principal | AcrPull, Foundry User, Speech User and Blob Data Contributor verified |
| Target/health/idle window | `az account show`; `az containerapp show`; HTTPS `/healthz` and authenticated jobs | Confirmed target, health 200, no active jobs |
| Image build | Azure CLI bundled Python: `az acr build --registry acraivideo571 --image video-platform:education-1cfc056fe149 --file drawio_runtime\Dockerfile.education --no-logs .` | Run `dn6` succeeded, Linux/amd64 |
| Image digest | ACR run `dn6` output | `sha256:f71c1b8013010fea9adbd2fc086b971846ce33a1783aa78c9bff54d8da1e9456` |
| Safeguards | Existing app-only Dockerfile/context and live configuration snapshot | Credentials/venv excluded; snapshot retained for comparison |

### URL-only research sources deployment verification (2026-10-11)

- Image: `acraivideo571.azurecr.io/video-platform:education-1cfc056fe149`.
- Revision `video-platform--0000004`: Healthy, Provisioned, one running replica,
  100% traffic. Previous revision drained under existing Single revision mode.
- Endpoint: https://video-platform.gentlemoss-8f7bc2ae.italynorth.azurecontainerapps.io
- Live HTML matches the local updated file exactly (SHA-256
  `e0747fd6f166025da6f29d3aa05588eeee7f1ef99ffe5a4d4d13226a0e359c13`).
- Health and authenticated API return 200; unauthenticated jobs API remains 401.
- Live Edge verification used the existing educational job and its real draft:
  two clickable URL-only entries inside **Research public sources**, no source titles,
  citation IDs, summary or separate Public sources panel.
- Historical research run opens automatically. Manual collapse survives rerender, and
  reopening the same job in the same page restores its sources correctly.
- URLs wrap within the viewport at 320/390/768px. Desktop/mobile screenshots retained.
  No JavaScript errors or server writes; no paid video generation triggered.
- Element screenshot initially raced a timeline refresh; page screenshots succeeded
  and the complete live browser checks passed on rerun.
- App image is the only semantic configuration change; sidecar, secrets, environment,
  resources, scaling, ingress, managed identity and registry preserved.
  Existing application RBAC roles reverified after rollout.
- No active video jobs interrupted; no Terraform apply, GPU/model or infrastructure changes.
- Isolated temporary browser tooling removed; app dependency manifests unchanged.

## Previous update: Generate video button (2026-10-11)

- Recipe: AZCLI application-only update, using the deployment target and normal ACR
  build/storage costs already confirmed in this session. User requested deployment.
- Target: `Microsoft-Azure-1` (`25a98a18-5e94-4b21-9d17-e8cf45bfd81f`),
  `rg-aivideo571` / `video-platform` in Italy North, and existing `acraivideo571`
  registry in Germany West Central.
- Build the existing educational Dockerfile with the Terraform content-hash image tag.
  Replace only the `video-platform` container image. Do not apply Terraform or alter
  GPU/model services, sidecar, secrets, environment variables, resource allocations,
  replicas, ingress, or managed identity.
- Live rollback image confirmed:
  `acraivideo571.azurecr.io/video-platform:education-56bb09c986e8`,
  ready revision `video-platform--0000002`.
- Preflight: live health 200, no active jobs, current configuration snapshotted.
- Validation: rerun focused composer/public-source tests and dependency checks,
  verify image build and existing identity permissions.
- Acceptance: new healthy revision with 100% traffic, exact deployed HTML match,
  authenticated API behavior preserved, and live desktop/mobile browser checks of
  the larger gradient button. Do not submit a real video during verification.
- Prior local visual checks: 48px height, at least 180px desktop width, full-width at
  320/390/768px viewports, hover/focus/disabled states, readable white text (4.63:1
  minimum gradient endpoint contrast), and no JavaScript errors.

### Button update validation proof (2026-10-11, 16:39 UTC)

| Check | Command / evidence | Result |
|---|---|---|
| Focused composer/source regression | Existing venv: `python -m pytest app\tests\test_naturalistic.py app\tests\test_education_ui.py -k "browser_composer or public_sources" -q` | 2 passed, 23 deselected |
| Dependency consistency | Existing venv: `python -m pip check` | No broken requirements |
| Existing IaC schema | `terraform -chdir=infra validate` | Passed; no plan/apply |
| Image tag | `terraform -chdir=infra console -var-file=education.tfvars`, `local.app_image_tag` | `video-platform:education-fa59267a8953` |
| Identity permissions | `az role assignment list` for app principal | Existing AcrPull, Foundry User, Speech User and Blob Data Contributor roles present |
| Live target | `az account show`; `az containerapp show`; HTTPS health/authenticated jobs | Existing confirmed target, health 200, no active jobs |
| Container build | Azure CLI bundled Python: `az acr build --registry acraivideo571 --image video-platform:education-fa59267a8953 --file drawio_runtime\Dockerfile.education --no-logs .` | ACR run `dn5` succeeded, Linux/amd64 |
| Image digest | ACR build output | `sha256:961bd111c4914fa9153c87686fb39fab2df5e2d5012e6e0cf628b096e5b00cbb` |
| Configuration snapshot | Read-only current template/identity/registry/ingress | Saved to session artifacts for before/after comparison |

### Button update deployment verification (2026-10-11)

- Image: `acraivideo571.azurecr.io/video-platform:education-fa59267a8953`.
- Revision `video-platform--0000003`: Healthy, Provisioned, one running replica,
  100% traffic. Previous revision drained under existing Single revision mode.
- Endpoint: https://video-platform.gentlemoss-8f7bc2ae.italynorth.azurecontainerapps.io
- Live HTML matches the local file exactly (SHA-256
  `f2ab008b7a91205575bb033e82010656cdeba7989e0d5da4399ab0a3cb2d3cb3`).
- Health and authenticated jobs API return 200; unauthenticated jobs API remains 401.
- Edge live-page verification: visible Generate video label, 180.3x48px desktop
  gradient button, distinct hover, keyboard focus ring, muted disabled state,
  and full-width layout without viewport overflow at 320/390/768px.
- No JavaScript errors, real job submissions or server-side writes during browser checks.
  Live desktop/mobile screenshots retained in session artifacts.
- Before/after comparison confirms only the app image changed. Sidecar, secrets,
  environment variables, resources, scaling, ingress, identity and registry preserved.
  Existing RBAC roles reverified after rollout.
- No active video jobs interrupted, no Terraform apply or GPU/model changes.
- Temporary browser tooling removed; application dependency manifests unchanged.

## Previous update: public sources web page (2026-10-11)

- Recipe: AZCLI application deployment to the existing Terraform-managed Container App.
- Subscription confirmed: `Microsoft-Azure-1`
  (`25a98a18-5e94-4b21-9d17-e8cf45bfd81f`).
- Scope: build the existing educational application Dockerfile in the existing ACR,
  update only the `video-platform` container image, and verify health plus deployed HTML.
- Do not apply Terraform, create resources, change GPU/model services, change RBAC,
  rotate secrets, or alter replicas, environment variables, storage, or the draw.io sidecar.
- Confirmed target: `rg-aivideo571` / `video-platform` in Italy North; registry
  `acraivideo571` in Germany West Central.
- Current image / rollback target:
  `acraivideo571.azurecr.io/video-platform:education-85c0ef93a585`.
- Preserve the existing `drawio-mcp` sidecar image, managed identity, resource allocations,
  Single revision mode, and one always-on replica. The new image tag follows the
  existing Terraform educational content-hash convention.
- Deployment approval: user approved the existing subscription/locations, normal ACR
  build/storage charges, and app-image-only rollout on 2026-10-11.
- Preserve the previous image for rollback. Check for active video jobs before rollout.
- Validation: focused public-source UI and education API tests, dependency consistency,
  existing Dockerfile/build context, identity permissions, and successful container build.
- Deployment validation proof and live verification will be recorded below.

### Current update validation proof (2026-10-11, 16:09 UTC)

| Check | Command / evidence | Result |
|---|---|---|
| Focused UI/API regression | Existing venv: `python -m pytest app\tests\test_education_ui.py app\tests\test_education.py app\tests\test_naturalistic.py -k "public_sources or api or defaults or browser_composer" -q` | 6 passed, 29 deselected |
| Dependencies | Existing venv: `python -m pip check` | No broken requirements |
| Existing IaC schema | `terraform -chdir=infra validate` | Passed; no plan/apply |
| Content-hash image tag | `terraform -chdir=infra console -var-file=education.tfvars`, expression `local.app_image_tag` | `video-platform:education-56bb09c986e8` |
| Live target and authentication | `az account show`; `az containerapp show`; `az acr show` | Confirmed subscription/locations and healthy existing app |
| Static and live RBAC | Existing `infra\identity.tf`; `az role assignment list` for app principal | AcrPull on existing registry, Foundry User/Speech User on existing Foundry account, Blob Data Contributor on existing storage |
| Build context | Existing educational Dockerfile and `.dockerignore` | Existing app-only context; credentials/venv excluded |
| Container build | Azure CLI bundled Python: `az acr build --registry acraivideo571 --image video-platform:education-56bb09c986e8 --file drawio_runtime\Dockerfile.education --no-logs .` | ACR run `dn4` succeeded, Linux/amd64 |
| Image digest | ACR run `dn4` output image | `sha256:11effb3ec6c82f281e1f93d22a626c7ccf40a88d172637408b5fd65d4cf2f8ab` |
| Pre-rollout health / safe window | HTTPS `/healthz` and authenticated `/api/videos` | Health 200; waited for active job to stop; no active jobs |
| Configuration safeguard | Read-only live template/identity/registry/ingress snapshot | Saved in session artifacts; compare after image update |

The existing build helper did not resolve the Windows Azure CLI launcher correctly in
this shell. The build succeeded using the CLI's bundled Python directly; no helper or
application code changes were required.

### Current update deployment verification (2026-10-11)

- Deployed with `az containerapp update --name video-platform --container-name video-platform
  --image acraivideo571.azurecr.io/video-platform:education-56bb09c986e8`.
- Ready revision: `video-platform--0000002`; Healthy, Provisioned, one running replica,
  100% traffic. The prior revision drained automatically under existing Single revision mode.
- Endpoint: https://video-platform.gentlemoss-8f7bc2ae.italynorth.azurecontainerapps.io
- HTTPS `/healthz`: 200. Served HTML matches the local updated file byte-for-byte
  (SHA-256 `162fc80a4f7c1f6eb48e7ba5cff7f7255d58232f3cf7f33aad824b02d0d64181`).
- Authenticated job/draft/source-download endpoints: 200; two public sources from the
  existing educational draft verified. `/api/videos` without the key remains 401.
- Edge browser: both real source titles/URLs visible and clickable, safe new-tab link
  attributes, download link present, no editing controls on the read-only job,
  no JavaScript errors. Screenshot retained in session artifacts.
- Before/after configuration comparison confirms the app image is the only semantic change.
  Azure CLI serialized an unused empty `value` beside the unchanged API-key `secretRef`;
  secret reference and authentication behavior are unchanged.
- Sidecar, environment variables, resource allocations, scaling, ingress, registry,
  managed identity and revision mode preserved. Live RBAC reverified after rollout.
- No active video jobs were interrupted. The previously running educational job failed
  before rollout; its source data remains accessible. This update does not repair that render.
- No Terraform apply, infrastructure provisioning, GPU/model changes or secret rotation.
- Temporary isolated browser tooling removed; application dependency manifests unchanged.

The sections below retain the original infrastructure preparation record. Its deferred
GPU/provisioning gates are not authorization to reprovision infrastructure for this update.

## Scope and target

- Independent Terraform deployment with prefix `aivideo571` in subscription
  `Microsoft-Azure-1` (`25a98a18-5e94-4b21-9d17-e8cf45bfd81f`).
- Italy North: ACA environment, delegated VNet, A100 ComfyUI app, Premium NFS
  share/private endpoint/DNS and Log Analytics.
- Separately configurable supporting-services region: Foundry/Speech, Blob and ACR.
- CPU orchestrator remains one always-on Consumption replica with API-key protection,
  managed identity, ffmpeg and optional private educational draw.io sidecar.
- GPU app: one always-on A100 replica, Single revision, digest-pinned yanwk boot
  image and checked ComfyUI v0.39.0. ComfyUI/telemetry are public HTTPS without auth,
  as explicitly requested. This permits billable third-party submissions and file access.
- Consumption job prepares source, telemetry and the complete model inventory.
  Execution success is required before GPU startup. Optional gated weights use a
  Key Vault secret reference; no HF token value is passed to Terraform.
- Persistent NFS media/models and Blob checkpoints survive restart; in-memory
  ComfyUI queue/history do not. Updates/provisioning must occur between jobs.

## State and deployment safeguards

Use `infra\scripts\initialize-state.ps1`. It preserves inherited root state in ignored
`infra\inherited-state` and initializes `infra\state-571\terraform.tfstate`.
Do not migrate/import 570 state or apply copied saved plans.
Use `infra\scripts\check-plan.ps1` on a fresh saved plan and inspect all changes/costs.
No 555/570 resources may be changed. The 555 reference folder remains read-only.

## Deployment gates

- `comfyui_cpu` and `comfyui_memory_gib` have no unverified deployment defaults.
  Profile representative workflows on the selected runtime, record peak container
  usage, choose a smaller allocation with headroom, verify it is accepted by the
  regional profile, and rerun representative renders.
- Obtain separate approval for temporary profiling infrastructure, model downloads,
  inference costs and final Terraform apply. Code implementation approval is not
  cloud-spend authorization.
- Validate current A100 availability/quota, driver/PyTorch compatibility, Foundry
  deployment availability, Key Vault permissions and required ComfyUI nodes.
- Invoke Azure validation before deployment; only apply the approved new-only plan.

## Validation

- Terraform format/validate: passed with the existing locked providers.
- Terraform mocked plan test: passed; verifies independent resource group, one GPU
  replica, A100 profile, regional consistency, public HTTPS and CPU orchestration.
- Focused ACA runtime/telemetry/downloader tests: 36 passed; two additional educational
  checksum failure tests passed in the eight-test downloader rerun.
- Bash, PowerShell and modified inline JavaScript syntax: passed.
- Pinned yanwk image manifest: verified Linux/amd64. Image contents, CUDA execution
  and workload memory peaks have not been live-tested.
- Full application regression suite: 248 passed. The final downloader rerun passed
  all eight tests, including two subsequently added educational checksum cases.
- Existing Python environment dependency check: passed (`pip check`).
- Architecture preview regenerated locally from the updated draw.io source.
- Separate 571 backend initialized; inherited state preserved, no state migration.

Local fixtures are not live GPU compatibility evidence. Repository-only validation is
authorized; do not generate/apply a cloud plan, build paid images, download models, launch
profiling resources or deploy without the separate approval and profiled sizing inputs.

Future cloud acceptance: successful model-job execution, healthy revision, CUDA/A100
identity, workflow node/model coverage, real submit/history/download, public telemetry,
platform API authentication, cinematic and reviewed educational rendering, audio/artifacts,
and controlled between-job restart with persistent media/checkpoint resume.

## Costs and limitations

Always-on A100/CPU/RAM, Premium Files capacity, ACR builds/storage, logs, Foundry/Speech
and inference incur charges. No invented pricing or final resource allocation is implied.
Missing gated LTX-2.5 weights are explicitly reported; other models are not substituted.
Public unauthenticated ComfyUI is intentionally unsuitable for a production-secure setup.

## Validation proof

| Check | Command or evidence | Result |
|---|---|---|
| Independent backend | `scripts\initialize-state.ps1`; local backend metadata | Passed; `state-571/terraform.tfstate`, inherited state archived |
| Terraform syntax/provider schema | `terraform fmt -check -recursive`; `terraform validate` | Passed with locked AzureRM 5.9.0 |
| Declarative architecture | `terraform test` | 1 mocked plan test passed; no cloud provisioning |
| Application regression | Existing venv: `python -m pytest -q` | 248 passed |
| Final downloader checks | `python -m pytest tests\test_model_downloads.py -q` | 8 passed, including optional educational checksum failures |
| Runtime failures/routing/telemetry | Focused ACA/runtime/GPU/downloader suite | 36 passed before additional checksum cases |
| Runtime syntax | Bash `-n`, PowerShell parser, Python AST/compileall, Node `--check` | Passed |
| Dependency consistency | Existing venv: `python -m pip check` | Passed |
| Static RBAC | Identity, Foundry and Blob Terraform review | Resource-scoped AcrPull, Foundry User, Speech User and Blob Data Contributor; local-user equivalents retained |
| Optional HF token | Key Vault secret URI and job managed identity | Token value excluded from Terraform; external vault access remains a deployment prerequisite |
| Boot-image manifest | Docker Registry digest metadata | Linux/amd64 verified; runtime/GPU behavior pending |
| Architecture | Local render from updated draw.io source | Updated PNG persisted |
| Cloud readiness | Real plan, policies/quota, paid image build, GPU profiling and live renders | Deferred: no deployment approval or profiled CPU/RAM inputs |

Preparation is locally verified, not certified for cloud deployment. Keep the status at
Ready for Validation until the deferred cloud preflight and runtime checks pass.
