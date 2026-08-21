from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from khalinos.godot_gameplay import GODOT_GAMEPLAY_BASE_PROFILE
from khalinos.godot_side_scroll import (
    GODOT_SIDE_SCROLL_PROFILE,
    CompiledGodotSideScroll,
    GodotSideScrollPlan,
    GodotSideScrollProjectPlan,
    compile_godot_side_scroll,
    compose_godot_side_scroll_capabilities,
)
from khalinos.godot_side_scroll_toolpack import (
    GODOT_SIDE_SCROLL_MANIFEST,
    GODOT_SIDE_SCROLL_TOOLPACK,
)
from khalinos.godot_side_scroll_workflow import execute_godot_side_scroll_run
from khalinos.models import (
    AgentVerification,
    CriterionFinding,
    DeterministicEvidence,
    QuestPlan,
    QuestSpec,
    RunRecord,
    RunStatus,
    UserBrief,
    VisualAssessment,
    VisualAssetGate,
    VisualConcept,
    VisualConceptPlan,
    VisualSelection,
    canonical_sha256,
)
from khalinos.storage import LocalRunStore
from khalinos.toolpacks import RegisteredToolPack, ToolPackRegistry
from khalinos.visual_assets import trusted_png_asset


def background_png() -> bytes:
    image = Image.new("RGB", (960, 540), "#bde6ef")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 310, 960, 540), fill="#d6c58b")
    for x in range(0, 960, 120):
        draw.ellipse((x - 40, 220, x + 90, 360), fill="#79aa68")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def side_scroll_artifact() -> CompiledGodotSideScroll:
    plan = GodotSideScrollPlan(project_name="Trinity Roadbound")
    concept = VisualConcept(
        candidate_id="V1",
        name="Sunlit Roadbound",
        design_thesis="A bright horizontal road makes forward travel and approaching green enemies immediately readable.",
        composition="The party anchors the left third while enemies and the destination occupy the travel lane to the right.",
        typography="Compact dark HUD labels remain legible against the bright landscape.",
        palette=["sky", "sand", "leaf"],
        interaction_emphasis="Travel progress, automatic attacks, enemies, and the destination flag dominate the frame.",
        anti_goals=["top-down arena", "static dashboard"],
    )
    return compile_godot_side_scroll(plan, concept, trusted_png_asset(background_png()))


def test_side_scroll_reuses_common_packs_but_replaces_the_genre_chain() -> None:
    assert GODOT_SIDE_SCROLL_PROFILE[:2] == GODOT_GAMEPLAY_BASE_PROFILE[:2]
    assert tuple(pack.pack_id for pack in GODOT_SIDE_SCROLL_PROFILE) == (
        "godot.project-core",
        "godot.visual-foundation",
        "godot.side-scroll-lane-combat",
        "godot.destination-progression",
        "godot.side-scroll-probe",
    )
    assert set(pack.pack_id for pack in GODOT_SIDE_SCROLL_PROFILE[2:]).isdisjoint(
        pack.pack_id for pack in GODOT_GAMEPLAY_BASE_PROFILE[2:]
    )


def test_side_scroll_compiler_is_deterministic_and_owns_exact_outputs(tmp_path: Path) -> None:
    first = side_scroll_artifact()
    second = side_scroll_artifact()
    assert first.bundle_sha256 == second.bundle_sha256
    composition = compose_godot_side_scroll_capabilities(first.plan)
    assert tuple(binding.pack_id for binding in composition.bindings) == tuple(
        pack.pack_id for pack in GODOT_SIDE_SCROLL_PROFILE
    )
    assert set(composition.text_files) == set(first.files)
    assert composition.binary_paths == (first.asset.path,)
    destination = tmp_path / "product"
    GODOT_SIDE_SCROLL_TOOLPACK.execution_adapter.materialize(first, destination)
    assert {path.as_posix() for path in destination.rglob("*") if path.is_file()} == {
        (destination / path).as_posix() for path in [*first.files, first.asset.path]
    }


def test_side_scroll_materializer_refuses_changed_approved_output(tmp_path: Path) -> None:
    artifact = side_scroll_artifact()
    changed = artifact.model_copy(update={
        "files": {**artifact.files, "scripts/khalinos_side_scroll.gd": "extends Node\n"},
    })
    with pytest.raises(PermissionError, match="bundle digest changed"):
        GODOT_SIDE_SCROLL_TOOLPACK.execution_adapter.materialize(changed, tmp_path / "product")


def test_real_godot_side_scroll_probe_and_render(tmp_path: Path, monkeypatch) -> None:
    executable = r"E:\memory R data\archive_20260818_first_priority\C-tmp\khalinos-engine-bakeoff\godot\Godot_v4.7.1-stable_win64.exe"
    monkeypatch.setenv("KHALINOS_GODOT_EXECUTABLE", executable)
    artifact = side_scroll_artifact()
    product = tmp_path / "product"
    evidence = tmp_path / "evidence"
    GODOT_SIDE_SCROLL_TOOLPACK.execution_adapter.materialize(artifact, product)
    receipt = GODOT_SIDE_SCROLL_TOOLPACK.evidence_adapter.verify(
        artifact,
        product,
        evidence,
        ["The party advances right, defeats enemies automatically, and reaches the destination."],
    )
    assert receipt.passed is True
    assert all(receipt.checks.values())
    assert (evidence / "side-scroll-probe.json").is_file()
    assert receipt.screenshot_names


class StubSideScrollEvidenceAdapter:
    adapter_id = GODOT_SIDE_SCROLL_MANIFEST.evidence.adapter_id

    def verify(self, artifact, root, evidence_dir, acceptance_criteria):
        assert (root / "scripts" / "khalinos_side_scroll.gd").is_file()
        evidence_dir.mkdir(parents=True, exist_ok=True)
        screenshot = evidence_dir / "side-scroll-render00000089.png"
        screenshot.write_bytes(background_png())
        return DeterministicEvidence(
            passed=True,
            checks={"side_scroll_probe": True, "display_render": True},
            issues=[],
            screenshot_names=[screenshot.name],
            criterion_evidence={
                item: ["Digest-bound side-scroll mechanics and rendered evidence passed."]
                for item in acceptance_criteria
            },
        )


class StubSideScrollTeam:
    def __init__(self) -> None:
        self.call_count = 0
        self.call_count_by_agent: dict[str, int] = {}
        self.concepts = [
            VisualConcept(
                candidate_id=f"V{index}",
                name=name,
                design_thesis=f"{name} creates a readable horizontal journey with clear forward movement and enemies.",
                composition="The party anchors the left third while enemies and the destination occupy the rightward lane.",
                typography="Compact dark labels remain readable over a restrained landscape.",
                palette=palette,
                interaction_emphasis="Travel, enemies, attacks, and the destination remain the strongest signals.",
                anti_goals=["top-down arena", "static dashboard"],
            )
            for index, (name, palette) in enumerate((
                ("Sunlit Road", ["sky", "sand", "leaf"]),
                ("Moonlit Pass", ["navy", "silver", "pine"]),
                ("Amber Frontier", ["amber", "stone", "sage"]),
            ), start=1)
        ]

    def record_call(self, agent_id: str) -> None:
        self.call_count += 1
        self.call_count_by_agent[agent_id] = self.call_count_by_agent.get(agent_id, 0) + 1

    async def plan_godot_side_scroll(self, payload):
        self.record_call("khalinos_godot_quest_owner")
        self.record_call("khalinos_godot_gameplay_owner")
        criteria = payload["approved_brief"]["acceptance_criteria"]
        return GodotSideScrollProjectPlan(
            quest_plan=QuestPlan(
                product_summary="A bounded side-scroll auto-combat destination journey.",
                architecture_decision="Use the approved side-scroll Capability profile and runtime probe.",
                quests=[
                    QuestSpec(
                        quest_id="Q1",
                        objective="Build and prove horizontal automatic combat.",
                        acceptance_criteria=[criteria[0]],
                        evidence_required=["Side-scroll probe and real render."],
                    ),
                    QuestSpec(
                        quest_id="Q2",
                        objective="Build and prove destination progression.",
                        acceptance_criteria=[criteria[1]],
                        evidence_required=["Destination receipt and real render."],
                        depends_on=["Q1"],
                    ),
                ],
            ),
            gameplay=GodotSideScrollPlan(project_name=payload["approved_brief"]["project_name"]),
        )

    async def plan_visuals(self, payload):
        self.record_call("khalinos_visual_director")
        return VisualConceptPlan(
            shared_contract="Three distinct readable foundations for the same bounded horizontal journey.",
            candidates=self.concepts,
        )

    async def make_visual_asset(self, brief, concept):
        self.record_call("khalinos_visual_candidate_maker")
        return trusted_png_asset(background_png())

    async def verify_visual_asset(self, candidate_id, asset, concept):
        self.record_call("khalinos_visual_asset_verifier")
        return VisualAssetGate(
            candidate_id=candidate_id,
            approved=True,
            contains_text_or_glyphs=False,
            contains_interface_elements=False,
            contains_logo_or_watermark=False,
            rationale="The environmental foundation contains no text, interface, logo, or watermark.",
        )

    async def select_visual(self, payload, screenshots):
        self.record_call("khalinos_visual_verifier")
        return VisualSelection(
            assessments=[
                VisualAssessment(
                    candidate_id=candidate_id,
                    contract_alignment=score,
                    visual_hierarchy=score,
                    distinctiveness=score,
                    interaction_clarity=score,
                    craft_and_cohesion=score,
                    strengths=["Readable horizontal journey."],
                )
                for candidate_id, score in (("V1", 10), ("V2", 9), ("V3", 8))
            ],
            selected_candidate_id="V1",
            rationale="V1 provides the clearest horizontal travel hierarchy and destination readability.",
        )

    async def verify_godot(self, payload):
        self.record_call("khalinos_godot_independent_verifier")
        criterion = payload["quest"]["acceptance_criteria"][0]
        return AgentVerification(
            findings=[CriterionFinding(
                criterion=criterion,
                passed=True,
                evidence="The deterministic side-scroll receipt directly proves this criterion.",
            )],
            verdict="PASS",
        )


async def test_side_scroll_cloud_workflow_records_real_slot_calls(tmp_path: Path) -> None:
    toolpack = RegisteredToolPack(
        manifest=GODOT_SIDE_SCROLL_MANIFEST,
        execution_adapter=GODOT_SIDE_SCROLL_TOOLPACK.execution_adapter,
        evidence_adapter=StubSideScrollEvidenceAdapter(),
    )
    binding = toolpack.binding()
    criteria = [
        "The party advances right and defeats approaching enemies automatically.",
        "The horizontal journey reaches its declared destination and reports victory.",
    ]
    brief = UserBrief(
        project_name="Roadbound Cloud Trial",
        goal="Create a bounded side-scrolling auto-combat journey in Godot.",
        acceptance_criteria=criteria,
        max_quests=2,
        toolpack_binding=binding,
        authorized_output_files=list(toolpack.manifest.output.authorized_paths),
    )
    run_id = "9" * 32
    store = LocalRunStore(tmp_path)
    store.create(
        RunRecord(
            run_id=run_id,
            status=RunStatus.QUEUED,
            brief_sha256=canonical_sha256(brief),
            toolpack_binding=binding,
            message="Queued.",
            work_mode="new_product_build",
        ),
        brief,
    )
    team = StubSideScrollTeam()
    result = await execute_godot_side_scroll_run(
        run_id,
        store=store,
        team=team,
        registry=ToolPackRegistry([toolpack]),
    )
    assert result.status == RunStatus.PASSED
    trace = json.loads(
        (tmp_path / "runs" / run_id / "final" / "agent-capability-trace.json").read_text(
            encoding="utf-8"
        )
    )
    calls = {item["agent_id"]: item["model_calls"] for item in trace["receipts"]}
    assert trace["profile_id"] == "godot.side-scroll-destination"
    assert calls["khalinos_godot_quest_owner"] == 1
    assert calls["khalinos_godot_gameplay_owner"] == 1
    assert calls["khalinos_visual_candidate_maker"] == 3
    assert calls["khalinos_godot_independent_verifier"] == 2
    assert "khalinos_sprite_atlas_verifier" not in calls
    assert (tmp_path / "runs" / run_id / "final" / "source.zip").is_file()
