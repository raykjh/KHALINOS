"""Auditable bindings between KHALINOS's fixed agent slots and Capability Packs."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from khalinos.toolpacks import (
    CapabilityComposition,
    CapabilityPackBinding,
    CapabilityPackManifest,
)


KHALINOS_AGENT_SLOT_IDS = (
    "khalinos_accountable_maker",
    "khalinos_godot_gameplay_owner",
    "khalinos_godot_independent_verifier",
    "khalinos_godot_quest_owner",
    "khalinos_godot_topology_owner",
    "khalinos_independent_verifier",
    "khalinos_project_owner",
    "khalinos_sprite_atlas_verifier",
    "khalinos_technical_repair",
    "khalinos_visual_asset_verifier",
    "khalinos_visual_candidate_maker",
    "khalinos_visual_director",
    "khalinos_visual_verifier",
)
KHALINOS_MAX_AGENT_SLOTS = len(KHALINOS_AGENT_SLOT_IDS)


class AgentCapabilityBindingReceipt(BaseModel):
    """One fixed agent slot's exact authority for a single profile run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-agent-capability-binding-v1"] = (
        "khalinos-agent-capability-binding-v1"
    )
    agent_id: str = Field(pattern=r"^khalinos_[a-z0-9_]{3,63}$")
    role: Literal[
        "quest_owner",
        "profile_owner",
        "artifact_maker",
        "visual_director",
        "visual_maker",
        "visual_gate",
        "visual_selector",
        "sprite_gate",
        "runtime_verifier",
    ]
    operations: tuple[str, ...] = Field(min_length=1, max_length=8)
    capability_pack_bindings: tuple[CapabilityPackBinding, ...] = Field(
        min_length=1, max_length=16
    )
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    binding_state: Literal["bound", "consumed"]
    execution_actor: Literal[
        "model_agent", "trusted_host", "deterministic_verifier", "not_invoked"
    ]
    model_invoked: bool = False
    model_calls: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def fixed_slot_and_canonical_authority(self) -> "AgentCapabilityBindingReceipt":
        if self.agent_id not in KHALINOS_AGENT_SLOT_IDS:
            raise ValueError("agent capability binding uses an unconfigured KHALINOS slot")
        if tuple(sorted(set(self.operations))) != self.operations:
            raise ValueError("agent capability operations must be unique and sorted")
        pack_ids = tuple(binding.pack_id for binding in self.capability_pack_bindings)
        if len(set(pack_ids)) != len(pack_ids):
            raise ValueError("agent capability bindings must not repeat a pack")
        if self.model_invoked != (self.model_calls > 0):
            raise ValueError("model invocation state must match the recorded model-call count")
        if self.model_invoked != (self.execution_actor == "model_agent"):
            raise ValueError("model invocation state must match the execution actor")
        if self.binding_state == "consumed" and self.execution_actor == "not_invoked":
            raise ValueError("a consumed binding requires an execution actor")
        return self

    def sha256(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class AgentCapabilityBindingTrace(BaseModel):
    """A profile-level sidecar proving slot reuse without claiming extra agents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["khalinos-agent-capability-trace-v1"] = (
        "khalinos-agent-capability-trace-v1"
    )
    profile_id: Literal["godot.trinity-top-down", "godot.side-scroll-destination"]
    max_agent_slots: int = KHALINOS_MAX_AGENT_SLOTS
    active_agent_ids: tuple[str, ...] = Field(min_length=1, max_length=KHALINOS_MAX_AGENT_SLOTS)
    inactive_agent_ids: tuple[str, ...] = Field(default=(), max_length=KHALINOS_MAX_AGENT_SLOTS)
    composition_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    execution_scope: Literal[
        "local_deterministic_profile_execution", "cloud_workflow_execution"
    ] = (
        "local_deterministic_profile_execution"
    )
    receipts: tuple[AgentCapabilityBindingReceipt, ...] = Field(
        min_length=1, max_length=KHALINOS_MAX_AGENT_SLOTS
    )

    @model_validator(mode="after")
    def fixed_inventory_and_receipts_match(self) -> "AgentCapabilityBindingTrace":
        if self.max_agent_slots != KHALINOS_MAX_AGENT_SLOTS:
            raise ValueError("agent capability trace changed the fixed slot ceiling")
        if tuple(sorted(set(self.active_agent_ids))) != self.active_agent_ids:
            raise ValueError("active agent slots must be unique and sorted")
        if tuple(sorted(set(self.inactive_agent_ids))) != self.inactive_agent_ids:
            raise ValueError("inactive agent slots must be unique and sorted")
        if set(self.active_agent_ids) | set(self.inactive_agent_ids) != set(KHALINOS_AGENT_SLOT_IDS):
            raise ValueError("agent capability trace must account for the complete fixed inventory")
        if set(self.active_agent_ids) & set(self.inactive_agent_ids):
            raise ValueError("active and inactive agent slots must not overlap")
        receipt_ids = tuple(receipt.agent_id for receipt in self.receipts)
        if tuple(sorted(receipt_ids)) != self.active_agent_ids or len(set(receipt_ids)) != len(receipt_ids):
            raise ValueError("one binding receipt is required for every active agent slot")
        return self

    def sha256(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _binding(manifest: CapabilityPackManifest) -> CapabilityPackBinding:
    return CapabilityPackBinding(
        pack_id=manifest.pack_id,
        version=manifest.version,
        manifest_sha256=manifest.sha256(),
    )


def _authority_output_sha256(
    manifests: tuple[CapabilityPackManifest, ...],
    composition: CapabilityComposition,
    binary_sha256_by_path: dict[str, str],
) -> str:
    text_paths = sorted(path for manifest in manifests for path in manifest.text_paths)
    binary_paths = sorted(path for manifest in manifests for path in manifest.binary_paths)
    value = {
        "bindings": [_binding(manifest).model_dump(mode="json") for manifest in manifests],
        "text_sha256": {
            path: hashlib.sha256(composition.text_files[path].encode("utf-8")).hexdigest()
            for path in text_paths
        },
        "binary_sha256": {path: binary_sha256_by_path[path] for path in binary_paths},
    }
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_agent_capability_trace(
    *,
    profile_id: Literal["godot.trinity-top-down", "godot.side-scroll-destination"],
    plan_sha256: str,
    artifact_bundle_sha256: str,
    evidence_sha256: str,
    composition: CapabilityComposition,
    profile: tuple[CapabilityPackManifest, ...],
    binary_sha256_by_path: dict[str, str],
    model_calls_by_agent: dict[str, int] | None = None,
) -> AgentCapabilityBindingTrace:
    """Bind one approved profile to existing slots; no new agent is created here."""

    by_id = {manifest.pack_id: manifest for manifest in profile}
    if tuple(by_id) != tuple(binding.pack_id for binding in composition.bindings):
        raise PermissionError("profile manifests do not match the executed Capability composition")

    if profile_id == "godot.trinity-top-down":
        maker_ids = (
            "godot.project-core",
            "godot.top-down-auto-combat",
            "godot.combat-feedback",
            "godot.presentation-skin",
            "godot.audio-feedback",
        )
        visual_ids = ("godot.visual-foundation",)
        verifier_id = "godot.gameplay-probe"
        include_sprite_gate = "godot.sprite-atlas" in by_id
    else:
        maker_ids = (
            "godot.project-core",
            "godot.side-scroll-lane-combat",
            "godot.combat-feedback",
            "godot.presentation-skin",
            "godot.audio-feedback",
            "godot.destination-progression",
        )
        visual_ids = ("godot.visual-foundation",)
        verifier_id = "godot.side-scroll-probe"
        include_sprite_gate = False

    licensed_visual_ids = tuple(
        pack_id
        for pack_id in (
            "godot.asset-selector",
            "godot.style-composer",
            "godot.licensed-atlas",
            "godot.license-receipt",
        )
        if pack_id in by_id
    )
    visual_ids = (*visual_ids, *licensed_visual_ids)
    if "godot.sprite-atlas" in by_id:
        visual_ids = (*visual_ids, "godot.sprite-atlas")

    all_bindings = tuple(_binding(manifest) for manifest in profile)
    maker_manifests = tuple(by_id[pack_id] for pack_id in maker_ids)
    visual_manifests = tuple(by_id[pack_id] for pack_id in visual_ids)
    verifier_manifest = by_id[verifier_id]
    composition_sha = composition.sha256()
    calls = model_calls_by_agent or {}

    def execution(agent_id: str, *, fallback: str = "not_invoked") -> dict[str, object]:
        count = calls.get(agent_id, 0)
        return {
            "binding_state": "consumed" if count else ("consumed" if fallback != "not_invoked" else "bound"),
            "execution_actor": "model_agent" if count else fallback,
            "model_invoked": bool(count),
            "model_calls": count,
        }

    visual_output_sha = _authority_output_sha256(
        visual_manifests, composition, binary_sha256_by_path
    )
    visual_gate_ids = tuple(
        pack_id
        for pack_id in (
            "godot.visual-foundation",
            "godot.asset-selector",
            "godot.style-composer",
            "godot.licensed-atlas",
            "godot.license-receipt",
        )
        if pack_id in by_id
    )
    receipts = [
        AgentCapabilityBindingReceipt(
            agent_id="khalinos_godot_quest_owner",
            role="quest_owner",
            operations=("authorize", "plan"),
            capability_pack_bindings=all_bindings,
            input_sha256=plan_sha256,
            output_sha256=composition_sha,
            **execution("khalinos_godot_quest_owner"),
        ),
        AgentCapabilityBindingReceipt(
            agent_id="khalinos_godot_gameplay_owner",
            role="profile_owner",
            operations=("authorize", "select"),
            capability_pack_bindings=all_bindings,
            input_sha256=plan_sha256,
            output_sha256=composition_sha,
            **execution("khalinos_godot_gameplay_owner"),
        ),
        AgentCapabilityBindingReceipt(
            agent_id="khalinos_accountable_maker",
            role="artifact_maker",
            operations=("materialize",),
            capability_pack_bindings=tuple(_binding(item) for item in maker_manifests),
            input_sha256=composition_sha,
            output_sha256=_authority_output_sha256(
                maker_manifests, composition, binary_sha256_by_path
            ),
            **execution("khalinos_accountable_maker", fallback="trusted_host"),
        ),
        AgentCapabilityBindingReceipt(
            agent_id="khalinos_visual_director",
            role="visual_director",
            operations=("plan",),
            capability_pack_bindings=tuple(_binding(item) for item in visual_manifests),
            input_sha256=composition_sha,
            output_sha256=visual_output_sha,
            **execution("khalinos_visual_director"),
        ),
        AgentCapabilityBindingReceipt(
            agent_id="khalinos_visual_candidate_maker",
            role="visual_maker",
            operations=("generate", "materialize"),
            capability_pack_bindings=tuple(_binding(item) for item in visual_manifests),
            input_sha256=composition_sha,
            output_sha256=visual_output_sha,
            **execution("khalinos_visual_candidate_maker", fallback="trusted_host"),
        ),
        AgentCapabilityBindingReceipt(
            agent_id="khalinos_visual_asset_verifier",
            role="visual_gate",
            operations=("observe", "verify"),
            capability_pack_bindings=tuple(_binding(by_id[item]) for item in visual_gate_ids),
            input_sha256=visual_output_sha,
            output_sha256=visual_output_sha,
            **execution("khalinos_visual_asset_verifier"),
        ),
        AgentCapabilityBindingReceipt(
            agent_id="khalinos_visual_verifier",
            role="visual_selector",
            operations=("observe", "select"),
            capability_pack_bindings=tuple(_binding(by_id[item]) for item in visual_gate_ids),
            input_sha256=visual_output_sha,
            output_sha256=visual_output_sha,
            **execution("khalinos_visual_verifier"),
        ),
        AgentCapabilityBindingReceipt(
            agent_id="khalinos_godot_independent_verifier",
            role="runtime_verifier",
            operations=("execute", "observe", "verify"),
            capability_pack_bindings=(_binding(verifier_manifest),),
            input_sha256=artifact_bundle_sha256,
            output_sha256=evidence_sha256,
            **execution(
                "khalinos_godot_independent_verifier",
                fallback="deterministic_verifier",
            ),
        ),
    ]
    if include_sprite_gate:
        sprite_manifest = by_id["godot.sprite-atlas"]
        sprite_sha = binary_sha256_by_path[next(iter(sprite_manifest.binary_paths))]
        receipts.append(AgentCapabilityBindingReceipt(
            agent_id="khalinos_sprite_atlas_verifier",
            role="sprite_gate",
            operations=("observe", "verify"),
            capability_pack_bindings=(_binding(sprite_manifest),),
            input_sha256=sprite_sha,
            output_sha256=sprite_sha,
            **execution("khalinos_sprite_atlas_verifier"),
        ))
    receipts.sort(key=lambda item: item.agent_id)
    active = tuple(receipt.agent_id for receipt in receipts)
    inactive = tuple(agent_id for agent_id in KHALINOS_AGENT_SLOT_IDS if agent_id not in active)
    return AgentCapabilityBindingTrace(
        profile_id=profile_id,
        active_agent_ids=active,
        inactive_agent_ids=inactive,
        composition_sha256=composition_sha,
        artifact_bundle_sha256=artifact_bundle_sha256,
        evidence_sha256=evidence_sha256,
        execution_scope=(
            "cloud_workflow_execution"
            if model_calls_by_agent is not None and sum(calls.values()) > 0
            else "local_deterministic_profile_execution"
        ),
        receipts=tuple(receipts),
    )


def compare_agent_capability_traces(
    first: AgentCapabilityBindingTrace,
    second: AgentCapabilityBindingTrace,
) -> dict[str, object]:
    """Return a deterministic, human-readable comparison of two fixed-slot traces."""

    if first.max_agent_slots != second.max_agent_slots:
        raise PermissionError("agent capability traces use different slot ceilings")
    first_receipts = {receipt.agent_id: receipt for receipt in first.receipts}
    second_receipts = {receipt.agent_id: receipt for receipt in second.receipts}
    shared = sorted(set(first_receipts) & set(second_receipts))
    pack_changes = {}
    for agent_id in shared:
        first_packs = [item.pack_id for item in first_receipts[agent_id].capability_pack_bindings]
        second_packs = [item.pack_id for item in second_receipts[agent_id].capability_pack_bindings]
        pack_changes[agent_id] = {
            first.profile_id: first_packs,
            second.profile_id: second_packs,
            "changed": first_packs != second_packs,
        }
    return {
        "schema_version": "khalinos-agent-capability-comparison-v1",
        "fixed_max_agent_slots": first.max_agent_slots,
        "profiles": {
            first.profile_id: {
                "active_agent_count": len(first.active_agent_ids),
                "inactive_agent_count": len(first.inactive_agent_ids),
                "execution_scope": first.execution_scope,
                "trace_sha256": first.sha256(),
            },
            second.profile_id: {
                "active_agent_count": len(second.active_agent_ids),
                "inactive_agent_count": len(second.inactive_agent_ids),
                "execution_scope": second.execution_scope,
                "trace_sha256": second.sha256(),
            },
        },
        "shared_agent_slots": shared,
        "only_in_first": sorted(set(first_receipts) - set(second_receipts)),
        "only_in_second": sorted(set(second_receipts) - set(first_receipts)),
        "pack_changes_by_agent": pack_changes,
        "new_agent_slots_created": False,
        "model_agent_slots_invoked": sorted({
            receipt.agent_id
            for receipt in (*first.receipts, *second.receipts)
            if receipt.model_invoked
        }),
        "model_calls_recorded": sum(
            receipt.model_calls for receipt in (*first.receipts, *second.receipts)
        ),
        "scope_note": (
            "These Cloud workflow receipts prove fixed-slot authorization and record actual "
            "model-agent invocations alongside trusted-host and deterministic execution."
            if first.execution_scope == second.execution_scope == "cloud_workflow_execution"
            else "These receipts prove fixed-slot authorization; execution scopes are reported "
            "per profile and must not be interpreted as broader autonomy."
        ),
    }
