# Trinity Survivors evidence index

This directory keeps the immutable KHALINOS Cloud proof separate from later ToolPack refinements.

## Canonical Cloud run

`cloud-run-5f0964c8/` is a curated, byte-for-byte copy of evidence stored under:

`gs://khalinos-agent-20260818-runs/runs/5f0964c8e3a0443197ab5b7e05b1a468/`

The run used `godot.gameplay` 1.4.0 and completed with an unbroken four-receipt chain:

- `visual-selection-receipt.json` — independent multimodal selection receipt
- `quests/Q1-receipt.json` through `Q3-receipt.json` — receipt-gated Quest completion
- `deterministic-evidence.json` — 31 passed runtime checks, zero issues
- `godot-gameplay-probe.json` — raw mechanics receipt from Godot
- `sprite-gate.json` — independent sprite-atlas gate
- `artifact-manifest.json` — final artifact, bundle, asset, ToolPack, and receipt digests
- `godot-gameplay-render.png` — real 1280×720 display-backed Godot render
- `brief.json` and `quest_plan.json` — immutable authority and execution plan

The final manifest binds artifact SHA-256 `5eb440e336e7356123980266fd8ff3355904bddab93c8d9bf7d41bb437064da2` and bundle SHA-256 `85413af749609a370e6b643b9b72fd4f62b3a4599b6d6b546364f3da326929fe`.

## Post-run Godot v5 validation

`post-run-godot-v5/` records deterministic validation after two general ToolPack improvements. It proves the first level-one enemy is beatable, all three heroes expose role-distinct basic attacks, skills obey cooldowns and have separate feedback, healing is visible, and nearby enemy attacks use a bounded cadence and hostile impact effect.

This is intentionally not presented as part of the earlier immutable Cloud run. It demonstrates that the subsequent shared generator revisions compile and execute in the approved Godot 4.7.1 runtime.
