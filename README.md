# KHALINOS

**KHALINOS is an evidence-gated autonomous production agent for bounded interactive prototypes: it turns a user's goal and authoritative materials into an immutable outcome contract, then plans, builds, runs, and verifies approved Browser or Godot outcomes on Google Cloud. Only results backed by real runtime evidence are marked complete.**

> If it is not proven, it is not complete.

KHALINOS is not a general-purpose coding chatbot and does not promise arbitrary repository completion. It separates authority, production, runtime verification, and judgment so the user does not become the hidden workflow engine. For a new project, a bounded Route Advisor compares the goal only with statically approved ToolPack manifests, explains exact fits, bounded alternatives, and incompatible routes, and waits for the user's confirmation. SixSense then inspects six project dimensions inside that selected capability boundary, asking only material unanswered questions. After authorization, a Gemini Project Owner issues an incremental Quest chain. Maker, deterministic Runtime Check, a separation-of-duties Verifier, and bounded Technical Repair remain separated by permissions and receipts. Browser products use multimodal visual selection. Godot work is composed from versioned Capability Packs: the verified top-down Trinity and side-scroll destination profiles share project, visual-foundation, and combat-feedback boundaries while retaining genre-specific mechanics and probes.

The public entrance separates a no-sign-in Judge Demo from private work. Google OpenID Connect uses only `openid`, `email`, and `profile`; the verified Google subject is the owner boundary for uploads, intakes, runs, and Project Library records. A passed run registers its artifact digest, immutable source ZIP snapshot, and receipt chain as the project's latest verified checkpoint. External browser projects enter through an owner-bound Cloud Storage resumable session and deterministic ZIP admission before SixSense can reference them.

This project targets the **Taskmaster** category of the All Things Agentic Hackathon.

## The friction

Long-running coding agents often fail in one of two ways: they improvise beyond the user's authority, or they repeatedly patch the latest symptom without preserving a verified state. Human supervision then becomes the real workflow engine.

KHALINOS replaces conversational handoffs with adaptive outcome discovery, an immutable approved brief, receipt-gated Quests, bounded repair, and a final evidence chain. After the user authorizes the Outcome Preview, the Cloud workflow completes or stops safely without a coding assistant designing, fixing, or approving intermediate work.

Once deployed, KHALINOS performs an approved run without Codex or another development assistant in the execution path. Extending KHALINOS itself—adding a new profile, changing a Capability Pack, fixing SixSense, or deploying a new release—remains ordinary product development and is not claimed as self-modification.

## SixSense outcome discovery

SixSense is not a fixed six-question survey. It always checks six dimensions but asks only when a missing choice could materially change feasibility, scope, visual direction, quality, authority, or cost:

1. Required enablers
2. Exclusions and preservation
3. Experience and visual direction
4. Operating context
5. Completion and quality standard
6. Authority, budget, and delivery

The user first supplies working material, then states the goal. Material may describe an existing project location, source folder structure, runnable build, or ordinary text and image references. KHALINOS classifies it statically without executing untrusted files. For a new project it next shows a Route recommendation: semantic fit is produced by Gemini, but the candidate set, compatibility filter, project kind, manifest digest, and final execution binding remain host-controlled. The user confirms one compatible route before SixSense begins. Each necessary SixSense question offers short, genuinely user-owned choices plus a free-form alternative; professional defaults remain KHALINOS decisions. When the six dimensions are sufficiently resolved, KHALINOS presents the expected final result, material mode, visual direction, boundaries, evidence standard, Quest estimate, cost, and duration. Execution begins only after explicit authorization. Choosing **Change route** discards the unresolved intake and returns to the goal; choosing **Revise outcome** keeps the confirmed route and carries the other confirmed decisions and sources into a fresh SixSense pass.

For judging, **Try Judge Demo** loads a bounded PUZZLE input-repair example without authentication or paid execution. **Choose a KHALINOS project**, persistent intake, run status, and authorization require a verified Google identity. When no OAuth Web Client ID is configured, the interface says so explicitly and leaves only the public Judge Demo available.

![SixSense adaptive intake](docs/evidence/sixsense-intake.png)

## Google technology

- **Gemini 3.5 Flash on Vertex AI** performs Project Owner, Visual Director, Visual Candidate Maker, multimodal Visual Verifier, Maker, separation-of-duties Quest Verifier, and Technical Repair decisions.
- **Nano Banana (`gemini-3.1-flash-lite-image`) on Vertex AI** generates one bounded environmental PNG per Browser or Godot visual concept. A separate multimodal gate inspects the raw image before any trusted compiler or rendered verifier can use it.
- **Google Agent Development Kit 2.6.2** runs every role as a schema-bound `LlmAgent`.
- **Cloud Run service** accepts an immutable brief and displays live status.
- **Cloud Run Job** performs the asynchronous long-running workflow.
- **Firestore** stores the current run projection.
- **Cloud Storage** stores immutable briefs, candidates, screenshots, Quest receipts, and the final manifest.
- **Cloud Storage resumable uploads** receive private project ZIP bytes without routing large archives through the API container.

## Architecture

[![KHALINOS architecture: authority to verified result](docs/architecture/khalinos-architecture.svg)](docs/architecture/khalinos-architecture.svg)

The standalone diagram shows the full authority boundary, Gemini/ADK orchestration, fixed Agent–Capability bindings, the shared Godot Capability Pack graph, deterministic and separation-of-duties evidence gates, bounded repair loop, and Google Cloud state/evidence plane. A 1600×900 [PNG export](docs/architecture/khalinos-architecture.png) is included for the Devpost page and demo video.

## Safety and autonomy contract

- The user authorizes the selected ToolPack's exact bounded output surface and hard Quest/repair limits.
- External ZIP admission currently accepts only that exact bounded browser profile. Godot, Unity, executables, symlinks, encrypted entries, traversal paths, extra files, oversized text, and high-ratio archives are rejected before execution.
- The 30-minute setting is a per-execution runaway safety slice, not a general project deadline. The current browser micro-app profile is intentionally non-resumable, so an authorized run must fit one slice.
- Browser new-product visual selection requires at least two deterministically renderable candidates and records raw-asset gate receipts, asset digests, the concept plan, screenshots, rubric scores, selected artifact digest, and selection receipt.
- Godot visual-prototype selection has the same two-candidate minimum, but the host compiles every accepted PNG into bounded Godot scenes, imports the texture, proves scene loading and translucent composition, and captures three real 1280×720 frames through an isolated Xvfb display before multimodal selection.
- Godot gameplay composition validates pack dependencies before materialization. The Trinity profile owns top-down survival mechanics, profession progression, and its gameplay probe; its default visual path now binds the qualified AetherAI licensed atlas by semantic hero roles and bounded enemy order instead of requiring a redundant generated Sprite Atlas. The side-scroll profile owns lane combat, destination progression, and its genre probe. Both consume `godot.combat-feedback`, which owns only attack-line, attack-range, basic-attack, skill/heal, and enemy-attack drawing primitives.
- Every Godot Cloud result includes an Agent–Capability trace. The fixed ceiling remains 13 slots; the final Trinity and side-scroll qualifications each activate 8 slots, but bind different least-authority Capability Pack graphs and produce different composition digests. The same accountable Maker slot consumes the profile-specific pack set; no new agent is invented to match a new genre.
- Licensed visual inputs use a four-Pack chain: `Asset Selector → Style Composer → Godot Atlas → License Receipt`. Clean and Cloud environments load one qualified, profile-specific composed atlas plus its selection, style, atlas, and license receipts from the application package. `KHALINOS_LICENSED_ASSET_ROOT` remains an optional full-catalog override for authorized reselection; if set, catalog count, image decodability, selected source hashes, atlas digest, profile role binding, and the license receipt all fail closed. The original source catalog is not shipped or redistributed as a standalone KHALINOS asset pack.

### Licensed-art development qualification (local, not Cloud production evidence)

The user-approved AetherAI library was regraded without deleting originals: 354 decoded PNGs produced 13 grade-A profile bindings, 336 grade-B reserves, and 5 preserved grade-C exclusions. Trinity selects 8 bounded roles; the side-scroll profile selects 13. The Trinity atlas SHA-256 is `310350dfa301a8349092e6723f123b7b7f8807e4a26d74ed7ac3539769564b56`; the side-scroll atlas SHA-256 is `3d7f794dd1e3385e36e93ee8d725ec73a9d2e549cf20e17c550dfaf3b1ebc94e`. Those two bounded composed atlases are application inputs and game components, not a standalone source-asset library. The earlier local result is [`licensed-art-local-qualification-20260822.json`](docs/evidence/capability-pack-composition/licensed-art-local-qualification-20260822.json).

Fresh Cloud qualification then proved the bundled licensed-art path instead of the previous generic fallback. Side-scroll run `53ef9772db26450ca96e77a0e661c248` passed 30/30 checks with atlas `3d7f794d…ebc94e`. Trinity run `bf5cf8ff39df42b484eb1d2c16be6e68` passed 59/59 checks with atlas `310350df…64b56`, all five semantic profile roles bound, a beatable opening enemy, no generated Sprite Atlas, 13 Gemini calls, four receipts, and zero issues. The exact image digests, executions, artifact/bundle/ZIP hashes, failure corrections, and claim boundary are in [`licensed-art-cloud-qualification-20260822.json`](docs/evidence/capability-pack-composition/licensed-art-cloud-qualification-20260822.json).

The AetherAI candidate library was subsequently expanded by 30 user-approved `32px-pastel` downloads: seven characters, eight monsters, seven props, and eight buildings. The originals remain outside the repository and are treated as grade-B reserves, not silently mixed into the active dark-expedition atlas. The hash-bound catalog now contains 384 candidates across three styles; the active Trinity and side-scroll bindings remain the visually compatible grade-A selections. This expansion is local qualification and does not claim standalone asset-pack redistribution permission.

Generated combat feedback uses a second four-Pack chain: `Effect Selector → Effect Atlas → Godot VFX Player → Effect Receipt`. The candidate pool now contains 12 transparent ImageGen sheets—three each for warrior, archer, healer, and enemy feedback—with nine forward-playback frames per effect. The selector binds nine semantic combat roles per profile, and Trinity and side-scroll deliberately choose different basic attack, healing, and enemy-melee candidates. All candidates are hash-locked into a bounded 2016×672 atlas; the existing Visual Maker/Verifier slots record the expanded bindings without increasing the 13-agent ceiling. Local approved-Godot qualification passed Trinity 58/58 and side-scroll 30/30 after one placement-and-scale adjustment, with atlas-load, receipt, and frame-change checks; see [`expanded-asset-vfx-local-qualification-20260822.json`](docs/evidence/capability-pack-composition/expanded-asset-vfx-local-qualification-20260822.json).

The same repository-contained VFX path then passed two Cloud workflows on immutable image digest `sha256:760f091fc0a571d4e2b2bcdd4c9daa3d1e77db769ff4f1474b7462681dd8cfae`. That historical qualification is preserved in [`expanded-vfx-cloud-qualification-20260822.json`](docs/evidence/capability-pack-composition/expanded-vfx-cloud-qualification-20260822.json); it is no longer described as the latest release.

### Final two-profile release qualification

The API and Worker were rebuilt from source commit `f7e7d8c` with the Godot-specific Cloud Build path and rebound to one immutable digest, `sha256:56a8f4429365c5170cf4c0c6149a497236b43a51144308154c633d1ed3fec24b`. Service revision `khalinos-00065-xmv` receives 100% of production traffic. Trinity run `15100d664c8840c2b85a24d2068e270f` / execution `khalinos-worker-dzcj6` passed 59/59 checks, three receipts, 12 Gemini calls, and zero issues. Side-scroll run `c9fa277674c940a685c48de576713239` / execution `khalinos-worker-m95cm` passed 30/30 checks, three receipts, 12 calls, and zero issues. Both selected V3, loaded the qualified licensed-art and generated-effect atlases, and produced different Agent–Capability composition hashes while using the same 8 active slots. The exact release, deployment, SHA, receipt, and corrected-failure record is [`submission-release-cloud-qualification-20260823.json`](docs/evidence/capability-pack-composition/submission-release-cloud-qualification-20260823.json).
- The model never emits binary asset fields. The trusted host validates and attaches exactly one `assets/visual-foundation.png` sidecar, while Makers receive only its path, digest, and dimensions.
- Image generation retries only transient 429/5xx responses, at most twice with backoff. Content rejection, invalid output, and non-transient client errors stop immediately.
- Generated Browser products cannot use external URLs, network calls, dynamic code loading, or files outside the five text files plus the one approved PNG. Prohibited external CSS imports are removed at the trusted promotion boundary before verification.
- Browser verification blocks every request except the local isolated product server.
- The Maker cannot approve its own work.
- The Verifier cannot modify the artifact.
- The Verifier is independent from the Maker by role, context, and write authority inside the KHALINOS trust boundary; it is not represented as an external audit organization.
- A transactional execution claim admits only one Worker for a queued run; duplicate or terminal dispatches are idempotent no-ops.
- A failed Quest receives at most two Technical Repair rounds and then stops as `blocked`.
- No previous PASS receipt is rewritten or silently weakened.

## Runtime evidence contract

Every active acceptance criterion must be exercised by its own browser journey and backed by at least one runtime assertion. The trusted verifier supports bounded waits, click/right-click/key input, deterministic random seeds, and assertions over text, element count, attributes, classes, and browser state. Criterion-bound text evidence must name a CSS selector, so unrelated page copy cannot create a false PASS. A criterion that requires execution evidence cannot pass from source inspection alone.

The Project Owner cannot promote verification files, logs, or implementation conveniences into new product requirements. Quest boundaries and objectives may be model-proposed, but the trusted host binds the immutable ordered acceptance criteria verbatim before execution. Verifier findings are bound back to the same criteria, so model wording drift cannot lose or broaden the user's contract.

The Browser visual-asset path passed an isolated production qualification on run `708ec62505e544ca85bbfa898343704b`. Two raw-gated candidates rendered successfully under network isolation; the independent Visual Verifier selected V2, and both Quest receipts preserved cumulative selector-bound runtime evidence. The qualified Browser ToolPack manifest SHA-256 is `162bd5734bdc4dab9810ce1e127b9110ec0400d30b36c7d83ea5d381009f2f8a`.

The current authenticated Browser qualification generated **Launch Triage Board** on run `32b5306b2c984683b406012b4ffb79f6` / execution `khalinos-worker-rfszp`. Three Quests produced four chained receipts with 19 Gemini calls and zero Quest repairs. The final revision passed all 12 deterministic checks: exact bounded files, offline/network isolation, accessibility, 320px responsiveness, trusted PNG loading, selector-bound journeys, complete criterion coverage, and a clean console. The journeys proved adding and completing `Final QA`, High-priority filtering, and the empty-filter state. Artifact SHA-256 is `01a23976...a3cc`; source ZIP SHA-256 is `d47e8783...1fde`. The exact Cloud image, manifest, receipt IDs, failure corrections, and claim boundary are recorded in [`launch-triage-cloud-qualification-20260823.json`](docs/evidence/browser-product/launch-triage-cloud-qualification-20260823.json).

![Launch Triage Board after completing Final QA](docs/evidence/browser-product/launch-triage-final-qa-completed.png)

The separate Godot visual-prototype path passed isolated Cloud qualification on run `5ac8abad53dd4919bca5708557421c3c`. All three Nano Banana assets passed the strict no-text/no-glyph/no-interface gate, all three produced real 1280×720 Godot renders, the independent multimodal Visual Verifier selected V2, and two Quest receipts plus the final source ZIP were stored in Cloud Storage. The qualification used 12 model calls and completed in 2 minutes 7 seconds. The qualified `godot.visual-prototype` manifest SHA-256 is `de20c1d17ea546e69d6b40098f0c5c2acb9363a95a74aca9bb5fe8e08224286d`.

The composed Godot path passed two fresh Cloud qualifications on one Worker image, `sha256:615da3f80441c55e3eb0fca598db0abe8d44d1dd6ea6fd1b7815ce780797a24c`. Trinity run `78d1d06f2a034714b1d917ce6ce6f969` passed 45/45 deterministic mechanics, asset, sprite-atlas, pack-load, and display checks; the side-scroll run `fe2f3493c6af432e9ebd0b0c61852dcf` passed 18/18 horizontal movement, automatic combat, destination, pack-load, and display checks. Both had zero runtime issues and `cloud_workflow_execution` Agent–Capability traces. The comparison receipt is preserved in [`docs/evidence/capability-pack-composition/combat-feedback-cloud-qualification-20260821.json`](docs/evidence/capability-pack-composition/combat-feedback-cloud-qualification-20260821.json).

Live execution telemetry then passed a fresh side-scroll Cloud qualification on run `36dd87aa06bf43d49f3c819287b6a20b` / execution `khalinos-worker-vrv5n`. Persisted state moved the presented horse through Owner, Visual, Runtime, Maker, Verifier, and Result roles while milestone cargo advanced from M01 through M06. The run passed 18/18 deterministic checks with zero issues, 12 Gemini calls, and three receipts. The machine-readable qualification, including three causally corrected safe stops, is preserved in [`docs/evidence/capability-pack-composition/live-execution-telemetry-cloud-qualification-20260822.json`](docs/evidence/capability-pack-composition/live-execution-telemetry-cloud-qualification-20260822.json).

The authenticated delivery path was requalified after exposing the selected visual foundation in the side-scroll render. Run `43fbc45542f247f9a9081a956da89da7` / execution `khalinos-worker-prmm6` visibly advanced through the presented agents, candidates, and M01–M06 milestones, passed 18/18 runtime checks, and exposed the owner-bound source download action. Its exact Cloud and digest record is [`visual-foundation-cloud-qualification-20260822.json`](docs/evidence/capability-pack-composition/visual-foundation-cloud-qualification-20260822.json).

The current production API and Worker are deployed from the same SHA-verified Godot image so the UI, route contracts, and executable runtime cannot drift. The Worker uses 8 GiB memory, 2 CPU, a 1,800-second timeout, and zero automatic retries. An exact single ToolPack fit is bound before SixSense; the compatibility page appears only for unsupported or genuinely ambiguous decisions. Explicit New project inputs remain references and cannot silently convert the intake to existing-project work. The current composed Godot bindings are `godot.gameplay` 2.5.0 / `5193ea8bef79137a2a05d5e0ea0e820a64054f6e611da4908549d4226d30a3c8` and `godot.side-scroll-experiment` 0.8.0 / `b497d3490d921660a42c8a9a31f5b3fdc3768a4a240737115b7fde8a78ecfe4d`. Exact submission revision and digest evidence is recorded under [`docs/evidence/capability-pack-composition`](docs/evidence/capability-pack-composition).

## Local setup

Requirements: Python 3.12+, a local Chromium or Chrome executable, and Google Cloud Application Default Credentials with Vertex AI access.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:GOOGLE_GENAI_USE_VERTEXAI="TRUE"
$env:GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
$env:GOOGLE_CLOUD_LOCATION="global"
$env:KHALINOS_CHROMIUM_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"
.\.venv\Scripts\python.exe -m pytest -q
```

The production API requires Firestore, a Cloud Storage bucket, and a fixed Cloud Run Job. For local workflow tests, the test suite uses an isolated filesystem store and fake role implementations; it never calls Vertex AI.

## Google Cloud deployment

Set a unique project and bucket name, then enable the required services:

```powershell
$env:KHALINOS_PROJECT="YOUR_PROJECT_ID"
$env:KHALINOS_REGION="asia-northeast3"
$env:KHALINOS_BUCKET="$env:KHALINOS_PROJECT-runs"
$env:KHALINOS_IMAGE="$env:KHALINOS_REGION-docker.pkg.dev/$env:KHALINOS_PROJECT/khalinos/worker:0.6.0-hackathon"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com firestore.googleapis.com storage.googleapis.com --project=$env:KHALINOS_PROJECT
gcloud artifacts repositories create khalinos --repository-format=docker --location=$env:KHALINOS_REGION --project=$env:KHALINOS_PROJECT
gcloud storage buckets create "gs://$env:KHALINOS_BUCKET" --project=$env:KHALINOS_PROJECT --location=$env:KHALINOS_REGION --uniform-bucket-level-access
gcloud storage buckets update "gs://$env:KHALINOS_BUCKET" --cors-file=deploy/storage-cors.json
gcloud firestore databases create --project=$env:KHALINOS_PROJECT --location=$env:KHALINOS_REGION --type=firestore-native
```

Create separate service identities:

```powershell
gcloud iam service-accounts create khalinos-api --project=$env:KHALINOS_PROJECT
gcloud iam service-accounts create khalinos-worker --project=$env:KHALINOS_PROJECT

$api="khalinos-api@$env:KHALINOS_PROJECT.iam.gserviceaccount.com"
$worker="khalinos-worker@$env:KHALINOS_PROJECT.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $env:KHALINOS_PROJECT --member="serviceAccount:$api" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding $env:KHALINOS_PROJECT --member="serviceAccount:$api" --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding $env:KHALINOS_PROJECT --member="serviceAccount:$api" --role="roles/run.developer"
gcloud projects add-iam-policy-binding $env:KHALINOS_PROJECT --member="serviceAccount:$api" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding $env:KHALINOS_PROJECT --member="serviceAccount:$worker" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding $env:KHALINOS_PROJECT --member="serviceAccount:$worker" --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding $env:KHALINOS_PROJECT --member="serviceAccount:$worker" --role="roles/aiplatform.user"
```

Build and deploy:

```powershell
gcloud builds submit --project=$env:KHALINOS_PROJECT --config=cloudbuild.godot.yaml --substitutions="_IMAGE=$env:KHALINOS_IMAGE"

gcloud run jobs deploy khalinos-worker --project=$env:KHALINOS_PROJECT --region=$env:KHALINOS_REGION --image=$env:KHALINOS_IMAGE --service-account=$worker --command=python --args="-m" --args="khalinos.worker" --set-env-vars="GOOGLE_CLOUD_PROJECT=$env:KHALINOS_PROJECT,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=TRUE,KHALINOS_BUCKET=$env:KHALINOS_BUCKET,KHALINOS_MODEL=gemini-3.5-flash" --task-timeout=1800 --max-retries=0 --memory=8Gi --cpu=2

gcloud run deploy khalinos --project=$env:KHALINOS_PROJECT --region=$env:KHALINOS_REGION --image=$env:KHALINOS_IMAGE --service-account=$api --set-env-vars="GOOGLE_CLOUD_PROJECT=$env:KHALINOS_PROJECT,KHALINOS_REGION=$env:KHALINOS_REGION,KHALINOS_BUCKET=$env:KHALINOS_BUCKET,KHALINOS_WORKER_JOB=khalinos-worker,KHALINOS_MODEL=gemini-3.5-flash,KHALINOS_PUBLIC_ORIGIN=https://YOUR_CLOUD_RUN_HOST" --min=0 --max=2 --memory=512Mi --cpu=1 --allow-unauthenticated
```

Create an External Google OAuth Web client for the deployed HTTPS origin and set its client ID on the API service. Request basic identity only; do not request Drive or `cloud-platform` scopes.

```powershell
gcloud run services update khalinos --project=$env:KHALINOS_PROJECT --region=$env:KHALINOS_REGION --update-env-vars="KHALINOS_GOOGLE_CLIENT_ID=YOUR_WEB_CLIENT_ID.apps.googleusercontent.com"
```

The service remains publicly reachable so the Judge Demo and landing page load, but every private API validates the Google ID token and checks the stored `owner_id`. The Worker needs no end-user token; it receives only an immutable run ID and writes the verified checkpoint to the already owner-bound project record. A passed Browser result can be played in an isolated browser tab, and every passed Browser or Godot project exposes an owner-bound **Download verified source** action.

Grant the API identity permission to run the fixed worker Job and act as its identity using the narrowest organization policy available. Verify the deployed `/health` response, submit one brief through the UI, and observe the Cloud Run execution, Vertex AI calls, Firestore state changes, Cloud Storage evidence, and final receipt chain.

## Reproducible proof checklist

1. Show the public Cloud Run URL and `/health` response.
2. Submit one brief and do not edit the run afterward.
3. Show the asynchronous Cloud Run Job execution.
4. Show Vertex AI/Cloud logs for the four ADK roles.
5. Show Firestore advancing through planning, execution, verification, and repair if needed.
6. Show Cloud Storage screenshots and every Quest receipt.
7. Open the final generated application and its final manifest.

## Trinity Survivors: verified Godot proof

Trinity Survivors is a proof output, not KHALINOS's product boundary. The current bounded `godot.gameplay` ToolPack converted one immutable game brief into a playable Godot 4.7 vertical slice, executed its real mechanics and display runtimes, and completed only after deterministic checks and the role-separated Verifier passed. The Verifier is separated from planning and making inside KHALINOS; this is not a claim of an external audit organization.

- Run ID: `15100d664c8840c2b85a24d2068e270f`
- Result: `PASS` — `Godot gameplay vertical slice passed real mechanics, rendering, and independent verification.`
- Cloud deployment: project `khalinos-agent-20260818`, region `asia-northeast3`, Job `khalinos-worker`, execution `khalinos-worker-dzcj6`
- Worker image: `sha256:56a8f4429365c5170cf4c0c6149a497236b43a51144308154c633d1ed3fec24b`
- ToolPack: `godot.gameplay` 2.5.0, manifest SHA-256 `5193ea8bef79137a2a05d5e0ea0e820a64054f6e611da4908549d4226d30a3c8`
- Agent work: 12 Gemini calls; three immutable receipts (one Visual Selection and two Quest receipts)
- Runtime proof: 59/59 deterministic Godot mechanics, audio, licensed-art, generated-effect, pack-load, and display checks passed; zero issues
- Artifact SHA-256: `6954141ff4f4fa9a6633055c25d91dc9beacc48d64fe5828c5d04acef830c3bc`
- Bundle SHA-256: `740c548dda5d8317d450fdcb98f2182af76923be0d545a6326aa83b7b3a8c7df`
- Licensed-art atlas SHA-256: `310350dfa301a8349092e6723f123b7b7f8807e4a26d74ed7ac3539769564b56`
- Generated-effect atlas SHA-256: `25636189ae67738e2023a4310bdbb2117d38da4294eb908dded9fc167a3bfdc9`
- Agent–Capability trace SHA-256: `a0b7881b14a0539f9a787ff633769b1580199fee7373662b084b447784e6525c`

![Representative Trinity Survivors real Godot render from the retained earlier evidence set](docs/evidence/trinity-survivors/cloud-run-8be19784/godot-gameplay-render.png)

The frame above is the retained render from the earlier `8be19784...` evidence set, not a screenshot attributed to the latest run. The latest two-profile qualification is recorded by the digest-bound comparison receipt linked above.

The immutable brief, Quest plan, Visual Selection receipt, three Quest receipts, final artifact manifest, Sprite Gate result, deterministic evidence, raw Godot probe receipt, and rendered frame are preserved in [`docs/evidence/trinity-survivors`](docs/evidence/trinity-survivors).

### Measured execution utility

These are direct log and artifact measurements, not estimated labor or cost savings.

| Measure | Observed value |
| --- | ---: |
| Human interventions after immutable authorization | 0 |
| Cloud Run Job duration | 4m 14.15s |
| Gemini calls | 12 |
| Generated source files | 21 |
| Deterministic checks | 59/59 PASS |
| Role-separated receipts | 3 |
| Technical Repair rounds | 0 |
| Final runtime issues | 0 |

The evidence proves a bounded vertical slice with executable mechanics, rendering, and receipt-gated verification. It does not prove general-purpose repository autonomy, production-scale reliability, external organizational independence, or polished commercial game quality. The single retained display capture is a real runtime frame, but the temporal mechanics are proven by the typed Godot probe rather than by claiming that one screenshot shows every state. The failure-and-recovery ledger is preserved beside the run evidence.

## Side-scroll destination: verified composition proof

The experimental side-scroll profile reuses the same project, visual-foundation, and combat-feedback boundaries while replacing Trinity's genre chain with lane combat, destination progression, and a side-scroll probe. This is evidence that fixed KHALINOS agent slots can consume different compatible pack combinations; it is not a claim that arbitrary game genres are already supported.

- Run ID: `c9fa277674c940a685c48de576713239`
- Result: `PASS` — `Godot side-scroll journey passed real mechanics, rendering, and independent verification.`
- Cloud Run Job execution: `khalinos-worker-m95cm`, completed in 3m 8.38s
- Qualified image: `sha256:56a8f4429365c5170cf4c0c6149a497236b43a51144308154c633d1ed3fec24b`
- ToolPack: `godot.side-scroll-experiment` 0.8.0, manifest SHA-256 `b497d3490d921660a42c8a9a31f5b3fdc3768a4a240737115b7fde8a78ecfe4d`
- Agent work: 12 Gemini calls; three immutable receipts
- Runtime proof: 30/30 deterministic mechanics, audio, generated-effect, pack-load, and display checks passed; zero issues
- Artifact SHA-256: `180dd46c4c84cdc567fd842ec2d7577f5140c205909035010c7b1ad76bdd3f82`
- Bundle SHA-256: `7c5f14db70aadbae6ae0e3b20767f7be121ccff4f989039d5fa19b8746022097`
- Licensed-art atlas SHA-256: `3d7f794dd1e3385e36e93ee8d725ec73a9d2e549cf20e17c550dfaf3b1ebc94e`
- Generated-effect atlas SHA-256: `25636189ae67738e2023a4310bdbb2117d38da4294eb908dded9fc167a3bfdc9`
- Agent–Capability trace SHA-256: `8a8212c562d264f99205d8f040335ad5033490d01784e9512a79ee78b9f624a8`
- Authenticated presentation proof remains separately preserved on run `43fbc45542f247f9a9081a956da89da7`: Chrome showed `Cloud Run Service → Gemini Project Owner → Deterministic Runtime V1/V2/V3 → Verified Result`, completed M01–M06, and exposed the owner-bound source download action

![Selected side-scroll visual foundation from the fresh Cloud PASS](docs/evidence/capability-pack-composition/side-scroll-visual-foundation-cloud-pass-43fbc455.png)

The layer correction makes the generated foundations visible, and the Visual Verifier distinguished V1's forest, V2's mountain/celestial direction, and V3's misty woodland direction. The honest boundary remains: characters, enemies, and typography are prototype-level geometric presentation, not polished custom pixel art. The PASS proves mechanics, rendering, destination victory, receipt-gated verification, and truthful live telemetry—not commercial game polish.

| Profile | Active fixed slots | Accountable Maker packs | Genre-specific verifier |
| --- | ---: | --- | --- |
| Trinity top-down | 9 | `project-core`, `top-down-auto-combat`, `combat-feedback` | `gameplay-probe` plus Sprite Gate |
| Side-scroll destination | 8 | `project-core`, `side-scroll-lane-combat`, `combat-feedback`, `destination-progression` | `side-scroll-probe` |

The fixed ceiling is 13 agent slots and `new_agent_slots_created` is false. The role-separated Verifiers remain inside the KHALINOS trust boundary; deterministic Godot probes and digest-bound evidence compensate for, but do not turn them into, external organizational audits.

## Earlier verified Browser proof

The repository includes evidence from a fresh autonomous run made after deployment:

- Run ID: `5fc00dc96e0a41cd8df713c58eb06678`
- Immutable brief SHA-256: `86c29a41b04fcdbaec6aa3452f3ccd0b5a361e9346a83915b09ee4b6a9fc95d8`
- Worker image digest: `sha256:89f47eecede50ac291aa96d7c272d7652a85eedb960d05336d49afcf72cbf429`
- Result: 3 of 3 receipt-gated Quests passed, 0 repair rounds, 7 Gemini calls
- Cloud Run Job execution: `khalinos-worker-7nwtm`, completed successfully in 2m 4.72s

![Autonomously generated and verified Signal Board](docs/evidence/signal-board-final.png)

The machine-readable Quest plan, receipts, and final manifest are in [`docs/evidence`](docs/evidence). The live service is [KHALINOS on Cloud Run](https://khalinos-lnvkyx4gca-du.a.run.app).

### SixSense visual-contract proof

A second fresh run tested whether a detailed SixSense visual contract changes the generated result without human or coding-assistant intervention after authorization:

- Intake ID: `d1ca99ad93404e8390e53a0cad367a43`
- Run ID: `1a88eddcb56f45648bd4e51716284ee4`
- Immutable brief SHA-256: `a49bb41248383b8418f143471e4135027f918987a74bfe3997331f4880da1e6e`
- Worker image digest: `sha256:0d73aba5561cd50e5ab9773682dc70d01bf17a3c35185a4e2c6290b48d580e99`
- Result: 3 of 3 Quests passed, 0 repair rounds, 7 Gemini execution calls
- Cloud Run Job execution: `khalinos-worker-dtp9v`, completed successfully in 2m 16.49s
- Visual contract: warm parchment, charcoal ink, restrained brass, editorial hierarchy, tactile depth, and explicit rejection of generic admin-dashboard styling

| Baseline brief | SixSense visual contract |
| --- | --- |
| ![Baseline generated board](docs/evidence/signal-board-final.png) | ![SixSense-guided generated board](docs/evidence/sixsense-run/signal-board-atelier-final.png) |

The second run's machine-readable brief, Quest plan, receipts, and final manifest are in [`docs/evidence/sixsense-run`](docs/evidence/sixsense-run).

### Multimodal visual-selection proof

A third fresh run reused the same Signal Board Atelier user goal to test visual competition rather than a different prompt. KHALINOS generated three structural concepts, rendered each in isolated Chromium, admitted the two candidates that passed deterministic checks, and asked an independent multimodal Visual Verifier to score only their screenshots. V2 won with a 9.2 rubric average over V3's 9.0, and its artifact digest became the parent of Q1.

- Intake ID: `9b9cb169a5cf498390de03c55624945c`
- Run ID: `683ae8d01f2143d89b57ac53f9bbc8de`
- Immutable brief SHA-256: `c153b1f0b2da9ecf24653a74356dcb1577b7b0a48f97e423eabce0dac228df68`
- Worker image digest: `sha256:52c1714dca706190b81e5e894fc485c41cb214cde21624a246b4fedda351e22e`
- Visual receipt: `VS-36570c0819ff47a9`, selected `V2` from eligible `V2` and `V3`
- Result: visual selection plus 3 of 3 receipt-gated Quests passed, 0 repair rounds, 12 Gemini execution calls
- Cloud Run Job execution: `khalinos-worker-rnv7l`, completed successfully in 5m 56.56s

| Earlier single-generation result | Visual-selected final result |
| --- | --- |
| ![Earlier SixSense-guided result](docs/evidence/sixsense-run/signal-board-atelier-final.png) | ![Multimodal visual-selected result](docs/evidence/visual-selection-run/final.png) |

| Eligible V2 | Eligible V3 |
| --- | --- |
| ![Triptych Atelier candidate](docs/evidence/visual-selection-run/candidate-v2.png) | ![Cartographic Desk candidate](docs/evidence/visual-selection-run/candidate-v3.png) |

The concept plan, rendered screenshots, selection receipt, Quest receipts, immutable brief, and final manifest are in [`docs/evidence/visual-selection-run`](docs/evidence/visual-selection-run).

## Hackathon alignment

KHALINOS follows the [official rules](https://allthingsagentichackathon.devpost.com/rules) and [official resources](https://allthingsagentichackathon.devpost.com/resources): it uses Gemini 3.5 Flash through Vertex AI, Google ADK as its agent framework, and four Google Cloud services. It is entered as a **Taskmaster** because one user brief triggers a complete asynchronous workflow without step-by-step human guidance.

## Development disclosure

KHALINOS was created during the contest period. AI coding tools assisted implementation and debugging during product development. They are not part of the demonstrated autonomous run after the user submits the brief. The submitted proof run must be a fresh Cloud execution in which KHALINOS itself performs planning, creation, verification, repair, and completion.
