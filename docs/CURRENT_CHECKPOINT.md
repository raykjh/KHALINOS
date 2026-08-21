# KHALINOS current checkpoint

This is the Git-side handoff for the active KHALINOS project. Google Drive remains the long-term human-readable memory canon; Git is the authority for code and file history.

## Active baseline

- Repository: `C:\memory R\KHALINOS`
- Branch: `agent/toolpack-restoration`
- Git baseline: `1038326` (`Record seeded profession qualification`).
- Active deployed implementation: `6bdbe2772b5d8f9837585d6f6f8566458172dd4a`.
- User-owned `smoke-input/` is intentionally untracked and must not be staged.
- User-authored `docs/test-projects/` inputs are intentionally untracked and must not be staged with ToolPack code.
- Contract-focused regression baseline: 44 passed. The full local run reached 125 passed; 22 legacy browser/Godot tests were blocked by the Windows sandbox denying child-process temporary directories, not by changed contract assertions.

## Product boundary

KHALINOS is a specialized autonomous builder for bounded browser micro-products and bounded Godot prototypes. The Godot routes are separate: screen topology, visual prototype, and a data-driven 2D top-down gameplay vertical slice. The user supplies material and a goal, answers only material SixSense questions, reviews one Outcome Preview, and authorizes an immutable brief. Project Owner, visual selection when required, trusted compiler, deterministic Runtime Check, Independent Verifier, and bounded Technical Repair then run in Google Cloud without step-by-step coding-assistant intervention.

It does not promise universal project completion. The previous general-purpose prototype is historical context, not the active project identity or scope.

## Verification baseline

- One active acceptance criterion maps to one browser journey.
- Every journey must include runtime assertion evidence for its criterion.
- Supported evidence includes bounded waits, input actions, text/count/attribute/class/state assertions, and deterministic random seeds.
- Criterion-bound text assertions require a CSS selector; unscoped page-wide text matches are rejected.
- Source inspection alone cannot pass a criterion that requires execution evidence.
- Project Owner criteria must exactly match the approved brief and cannot expand scope with verification artifacts or implementation conveniences.
- Ordered Verifier findings are host-bound to the immutable criteria.

## Browser visual production path

- Browser new-product builds create three distinct visual concepts.
- Nano Banana `gemini-3.1-flash-lite-image` produces one bounded 16:9 PNG for each concept.
- A raw multimodal Visual Asset Gate rejects readable text, interface elements, logos, and watermarks before the Maker receives even the asset metadata.
- The trusted host owns the bytes and attaches exactly one validated `assets/visual-foundation.png`; model structured output remains text-only.
- Network-isolated Chromium requires the asset to load visibly and produces screenshots. Only deterministically eligible candidates reach the independent Visual Verifier.
- At least two eligible candidates are required. The selected receipt binds candidate, artifact, screenshot, and asset digests.
- Transient image API 429/5xx errors receive at most two backoff retries; other failures stop.

Qualification run `708ec62505e544ca85bbfa898343704b` passed with 16 model calls. V1 and V2 were eligible, V2 was selected, and the final Q2 receipt preserved both Q1 and Q2 selector-bound runtime evidence. Browser ToolPack manifest: `162bd5734bdc4dab9810ce1e127b9110ec0400d30b36c7d83ea5d381009f2f8a`.

## Godot gameplay production path

- `godot.gameplay` accepts only bounded offline 2D top-down action or survival vertical slices.
- Gemini authors a strict data plan for heroes, enemy archetypes, automatic abilities, shared party stats, session length, and deterministic level-choice cadence; it never writes GDScript.
- The trusted compiler owns `project.godot`, the scene, gameplay script, probe, manifest, README, and one gated Nano Banana environmental PNG.
- PASS requires actual movement, enemy spawning, automatic ability execution, shared health initialization, deterministic level choice, approved runtime digest, asset import, and real rendered frames.
- 3D, multiplayer, networking, arbitrary plugins/scripts, existing-project repair, platform distribution, and unrestricted full-game claims remain excluded.

Cloud qualification execution `khalinos-godot-toolpack-staging-zv6zb` passed the gameplay smoke and every emitted `godot.gameplay` 1.4.0 check, including seeded profession alternatives, the three-choice profession contract, ordered role turns, deterministic seed behavior, display-backed rendering, and sprite evidence. The approved ToolPack manifest SHA-256 is `3f6a0489a01fd0e8d650cbbb488a8c27e812733a28be00bc2e9629b26e1a623d`.

## Deployment target

- Google Cloud project: `khalinos-agent-20260818`
- Region: `asia-northeast3`
- Cloud Run Job: `khalinos-worker`
- Service: `khalinos`
- Cloud Run Job: `khalinos-worker`
- Code commit deployed: `6bdbe2772b5d8f9837585d6f6f8566458172dd4a`.
- Image digest: `sha256:f17c20a52ec73f7c8f647407aa177623fef98bf30444d51cb553859eda8dbd31`.
- Cloud Build: `22fea684-8b6c-40bc-9205-56ddbb7f3f85`.
- Service revision: `khalinos-00032-hbc`, serving 100 percent of traffic.
- Worker uses the same image digest.
- Safety: zero retries, 1800-second task timeout.

The qualified code is deployed to the service and Worker with the same image digest. The public `/health` endpoint returned `ok: true` after deployment.

## Next decision

Review the new Trinity Survivors Outcome Preview `41d7b6e9dfe745acbe7c86406299c2bd`. It is bound to `godot.gameplay` 1.4.0 and is ready but not authorized. Only after user review should KHALINOS authorize the first paid end-to-end gameplay run. Do not reuse the stale 1.3.0 preview or reinterpret the gameplay vertical slice as a full production game.

For a new project, follow this order: materials, goal, approved ToolPack Route recommendation and user confirmation, only necessary SixSense questions, Outcome Preview, explicit authorization, then autonomous Cloud execution. Route semantics may be model-assisted, but candidate IDs, compatibility, manifest digests, and authorization remain host-controlled. Existing-project repair continues from its verified source type. Do not implement the new product or spend on a new run before the outcome is approved.

## Sprite Asset qualification after the Drive checkpoint

The Godot Gameplay ToolPack now carries an exact `isnet-anime.onnx` external dependency and a digest-bound segmentation contract. Each character is generated as one isolated source, segmented locally by the approved model, normalized into a fixed slot, composed deterministically, and inspected by an independent multimodal Sprite Atlas Gate for full-body completeness, role-defining equipment, residue, clipping, overlap, text, UI, and style consistency.

Local regression is 132 passed. Cloud execution `khalinos-godot-toolpack-staging-5lqm8` then qualified the complete live path with zero retries: two real Nano Banana character generations, one independent Sprite Gate call, approved IS-Net Anime inference, deterministic atlas composition, and 23 passing Godot runtime/render checks. The qualified image digest is `sha256:e56694534228eae0b5b3615a5bba1682e695c061c3929de2cebafa9cf4e9ee92`; the ToolPack binding is `godot.gameplay` `1.2.0` with manifest `3d8972e2f0b651e59ce80d1d58bbc7ff1c7bcb211f41076c2b6b90c141dbd06a`. Production service and Worker were not changed.

The exact evidence is stored in `docs/evidence/toolpack-restoration/sprite-isnet-cloud-qualification.json`. The staging preflight failure is preserved there; it occurred before any model call and was caused by an invalid qualification fixture plus malformed environment-variable quoting. The contract and visual thresholds were not weakened.

## Seeded profession contract and new Trinity Survivors preview

The previous ready intake `9d1501ac63ff4caa91a38cf2f90624ce` remains preserved as an auditable 1.3.0 contract. Its authorization attempt failed before Worker dispatch because its preview required two seeded random profession alternatives while the old validator vocabulary did not admit that criterion. No paid execution or additional Worker retry occurred.

The structural fix moved this requirement into the trusted gameplay contract. `godot.gameplay` 1.4.0 now guarantees one current-profession rank-up plus two distinct, current-profession-excluding seeded alternatives; the same seed is repeatable and a different seed varies when the candidate pool permits it. Authorization validation also returns bounded 4xx responses instead of an opaque 500 for contract or binding conflicts.

Using the original five source files, original goal, and confirmed SixSense choice `Vibrant Stylized`, KHALINOS created a new Outcome Preview:

- Intake: `41d7b6e9dfe745acbe7c86406299c2bd`
- Status: `ready`; not authorized and no run dispatched
- ToolPack: `godot.gameplay` 1.4.0
- Manifest: `3f6a0489a01fd0e8d650cbbb488a8c27e812733a28be00bc2e9629b26e1a623d`
- Delivery: nine digest-bound files, three Quests, zero repairs, USD 5 maximum, 30 minutes maximum
- Key completion contract: 600-second session, ten Trinity levels at 60-second intervals, Tank -> Damage -> Healer turns, one guaranteed rank-up plus two seeded alternatives, summed party statistics, capped stored resurrection, live gameplay mechanics, and display-backed render evidence

The exact contract snapshot is stored in `docs/evidence/toolpack-restoration/trinity-survivors-contract-20260820.json`. The next external action is explicit user review and authorization; contract creation itself does not authorize paid execution.
