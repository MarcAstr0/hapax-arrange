"""Content-hash pattern deduplication and slot assignment per source track."""

from __future__ import annotations

import hashlib

import mido

from hapax_arrange.model import PatternContent, PatternSlot


def assign_slots(
    contents: list[PatternContent],
    *,
    ppq: int,
    enabled: bool = True,
    hapax_track_of: dict[int, int] | None = None,
) -> tuple[dict[int, list[PatternSlot]], dict[str, dict[int, int]]]:
    """Group per-track contents into PatternSlots; build (track, section) -> slot map.

    Returns:
        slots_per_track: dict keyed by hapax_track -> ordered list of PatternSlots
        section_slot_map: dict keyed by section_name -> {hapax_track: slot_index}
    """
    if hapax_track_of is None:
        hapax_track_of = {c.track_id: c.track_id + 1 for c in contents}

    # Group contents by source track while preserving their section order.
    by_track: dict[int, list[PatternContent]] = {}
    for c in contents:
        by_track.setdefault(c.track_id, []).append(c)

    slots_per_track: dict[int, list[PatternSlot]] = {}
    section_slot_map: dict[str, dict[int, int]] = {}

    quantum = max(1, ppq // 96)

    for track_id, items in by_track.items():
        hapax_track = hapax_track_of.get(track_id, track_id + 1)
        hash_to_slot: dict[str, PatternSlot] = {}
        hash_to_sections: dict[str, list[str]] = {}
        slot_order: list[str] = []

        for content in items:
            if _is_empty(content):
                # Empty sections don't consume a slot; mark as inactive in section_slot_map.
                section_slot_map.setdefault(content.section_name, {})
                continue
            h = _hash_content(content, quantum) if enabled else _unique_hash(content)
            if h not in hash_to_slot:
                idx = len(slot_order) + 1
                slot_order.append(h)
                hash_to_sections[h] = [content.section_name]
                hash_to_slot[h] = PatternSlot(
                    track_id=track_id,
                    hapax_track=hapax_track,
                    slot_index=idx,
                    content_hash=h,
                    length_bars=content.length_bars,
                    length_ticks=content.length_ticks,
                    sections_using=(content.section_name,),
                    source_content=content,
                )
            else:
                hash_to_sections[h].append(content.section_name)
            section_slot_map.setdefault(content.section_name, {})[hapax_track] = hash_to_slot[
                h
            ].slot_index

        # Finalize sections_using tuples (order of first appearance).
        finalized: list[PatternSlot] = []
        for h in slot_order:
            slot = hash_to_slot[h]
            finalized.append(
                PatternSlot(
                    track_id=slot.track_id,
                    hapax_track=slot.hapax_track,
                    slot_index=slot.slot_index,
                    content_hash=slot.content_hash,
                    length_bars=slot.length_bars,
                    length_ticks=slot.length_ticks,
                    sections_using=tuple(hash_to_sections[h]),
                    source_content=slot.source_content,
                )
            )
        slots_per_track[hapax_track] = finalized

    return slots_per_track, section_slot_map


def _is_empty(content: PatternContent) -> bool:
    return all(msg.is_meta for _, msg in content.events)


def _hash_content(content: PatternContent, quantum: int) -> str:
    """Hash a pattern's event stream with quantized timing to absorb microtiming."""
    digest = hashlib.sha256()
    digest.update(f"len={content.length_ticks};".encode())
    for abs_tick, msg in content.events:
        if msg.is_meta:
            continue
        q_tick = round(abs_tick / quantum) * quantum
        token = _msg_token(msg)
        digest.update(f"{q_tick}|{token};".encode())
    return digest.hexdigest()


def _unique_hash(content: PatternContent) -> str:
    return hashlib.sha256(
        f"{content.track_id}|{content.section_name}|{id(content)}".encode()
    ).hexdigest()


def _msg_token(msg: mido.Message) -> str:
    t = msg.type
    ch = getattr(msg, "channel", -1)
    if t in ("note_on", "note_off"):
        note = msg.note
        vel = msg.velocity
        # Normalize zero-velocity note_on into note_off for hashing.
        if t == "note_on" and vel == 0:
            t = "note_off"
        return f"{t}:{ch}:{note}:{vel}"
    if t == "control_change":
        return f"cc:{ch}:{msg.control}:{msg.value}"
    if t == "pitchwheel":
        return f"pw:{ch}:{msg.pitch}"
    if t == "program_change":
        return f"pc:{ch}:{msg.program}"
    if t == "aftertouch":
        return f"at:{ch}:{msg.value}"
    if t == "polytouch":
        return f"pt:{ch}:{msg.note}:{msg.value}"
    return f"{t}:{ch}"
