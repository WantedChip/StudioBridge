"""Semantic diffing engine for FL Studio project files (.flp).

Implements structural comparison,
detecting added/removed channels, modified tempos, altered notes, mixer routing,
and metadata differences in structured and human-readable formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from studiobridge.flp.model.project import Project


@dataclass
class ProjectDiff:
    """Semantic comparison report between two Project instances.

    Attributes:
        proj_a_version: Version string of project A.
        proj_b_version: Version string of project B.
        metadata: Changed project metadata fields {field_name: {'before': val_a, 'after': val_b}}.
        channels_added: List of channel descriptions added in project B.
        channels_removed: List of channel descriptions removed in project B.
        channels_modified: Channel modifications {index, name, changes: {...}}.
        patterns_added: Patterns present in B but not in A.
        patterns_removed: Patterns present in A but not in B.
        patterns_modified: Pattern modifications (name, length, note differences).
        mixer_modified: Mixer track changes (volume, pan, routing, solo, mute).
        playlist_diff: Summary of playlist item count and placement changes.
    """

    proj_a_version: str = ""
    proj_b_version: str = ""
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    channels_added: list[dict[str, Any]] = field(default_factory=list)
    channels_removed: list[dict[str, Any]] = field(default_factory=list)
    channels_modified: list[dict[str, Any]] = field(default_factory=list)
    patterns_added: list[dict[str, Any]] = field(default_factory=list)
    patterns_removed: list[dict[str, Any]] = field(default_factory=list)
    patterns_modified: list[dict[str, Any]] = field(default_factory=list)
    mixer_modified: list[dict[str, Any]] = field(default_factory=list)
    playlist_diff: dict[str, Any] = field(default_factory=dict)

    @property
    def has_differences(self) -> bool:
        """True if any structural or metadata difference was detected."""
        return bool(
            self.metadata
            or self.channels_added
            or self.channels_removed
            or self.channels_modified
            or self.patterns_added
            or self.patterns_removed
            or self.patterns_modified
            or self.mixer_modified
            or self.playlist_diff.get("has_changes", False)
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert diff report to serializable dictionary."""
        return {
            "has_differences": self.has_differences,
            "version_a": self.proj_a_version,
            "version_b": self.proj_b_version,
            "metadata": self.metadata,
            "channels": {
                "added": self.channels_added,
                "removed": self.channels_removed,
                "modified": self.channels_modified,
            },
            "patterns": {
                "added": self.patterns_added,
                "removed": self.patterns_removed,
                "modified": self.patterns_modified,
            },
            "mixer": {
                "modified": self.mixer_modified,
            },
            "playlist": self.playlist_diff,
        }

    def format_text(self) -> str:
        """Format human-readable text comparison summary."""
        if not self.has_differences:
            return "Project Diff: Projects are structurally identical."

        lines: list[str] = [
            f"Project Diff (v{self.proj_a_version} -> v{self.proj_b_version}):",
        ]

        if self.metadata:
            lines.append("  Metadata Changes:")
            for field_name, vals in self.metadata.items():
                lines.append(f"    - {field_name}: {vals['before']!r} -> {vals['after']!r}")

        if self.channels_added or self.channels_removed or self.channels_modified:
            lines.append("  Channels:")
            for c in self.channels_added:
                lines.append(f"    + Added Channel {c['index']}: {c['name']!r} ({c['type']})")
            for c in self.channels_removed:
                lines.append(f"    - Removed Channel {c['index']}: {c['name']!r} ({c['type']})")
            for c in self.channels_modified:
                changes_str = ", ".join(
                    f"{k}: {v['before']!r} -> {v['after']!r}" for k, v in c["changes"].items()
                )
                lines.append(
                    f"    ~ Modified Channel {c['index']} ({c['name']!r}): [{changes_str}]"
                )

        if self.patterns_added or self.patterns_removed or self.patterns_modified:
            lines.append("  Patterns:")
            for p in self.patterns_added:
                notes_cnt = p.get("total_notes", 0)
                lines.append(
                    f"    + Added Pattern {p['number']}: {p['name']!r} ({notes_cnt} notes)"
                )
            for p in self.patterns_removed:
                lines.append(f"    - Removed Pattern {p['number']}: {p['name']!r}")
            for p in self.patterns_modified:
                changes = p.get("changes", {})
                changes_str = ", ".join(
                    f"{k}: {v['before']!r} -> {v['after']!r}" for k, v in changes.items()
                )
                lines.append(
                    f"    ~ Modified Pattern {p['number']} ({p['name']!r}): [{changes_str}]"
                )

        if self.mixer_modified:
            lines.append("  Mixer:")
            for m in self.mixer_modified:
                changes_str = ", ".join(
                    f"{k}: {v['before']!r} -> {v['after']!r}" for k, v in m["changes"].items()
                )
                lines.append(f"    ~ Track {m['index']} ({m['name']!r}): [{changes_str}]")

        if self.playlist_diff.get("has_changes", False):
            cnt_a = self.playlist_diff.get("count_a", 0)
            cnt_b = self.playlist_diff.get("count_b", 0)
            diff_cnt = self.playlist_diff.get("count_diff", 0)
            lines.append("  Playlist:")
            lines.append(f"    Items: {cnt_a} -> {cnt_b} (diff: {diff_cnt:+d})")

        return "\n".join(lines)


def diff_projects(proj_a: Project, proj_b: Project) -> ProjectDiff:
    """Compare two Project instances and compute structural semantic differences."""
    metadata_diffs: dict[str, dict[str, Any]] = {}

    # Compare core metadata fields
    for field_name in ("title", "author", "comments", "ppq", "version", "licensed"):
        val_a = getattr(proj_a, field_name)
        val_b = getattr(proj_b, field_name)
        if val_a != val_b:
            metadata_diffs[field_name] = {"before": val_a, "after": val_b}

    # Compare tempo with float tolerance
    if abs(proj_a.tempo - proj_b.tempo) > 0.001:
        metadata_diffs["tempo"] = {
            "before": round(proj_a.tempo, 4),
            "after": round(proj_b.tempo, 4),
        }
    if abs(proj_a.fine_tempo - proj_b.fine_tempo) > 0.001:
        metadata_diffs["fine_tempo"] = {
            "before": round(proj_a.fine_tempo, 4),
            "after": round(proj_b.fine_tempo, 4),
        }

    # Channel diffs
    channels_added: list[dict[str, Any]] = []
    channels_removed: list[dict[str, Any]] = []
    channels_modified: list[dict[str, Any]] = []

    a_chans = {c.index: c for c in proj_a.channels}
    b_chans = {c.index: c for c in proj_b.channels}

    all_ch_indices = sorted(set(a_chans.keys()) | set(b_chans.keys()))
    for idx in all_ch_indices:
        if idx in a_chans and idx not in b_chans:
            c = a_chans[idx]
            channels_removed.append({"index": c.index, "name": c.name, "type": c.channel_type})
        elif idx in b_chans and idx not in a_chans:
            c = b_chans[idx]
            channels_added.append({"index": c.index, "name": c.name, "type": c.channel_type})
        else:
            ca = a_chans[idx]
            cb = b_chans[idx]
            changes: dict[str, dict[str, Any]] = {}
            if ca.name != cb.name:
                changes["name"] = {"before": ca.name, "after": cb.name}
            if ca.channel_type != cb.channel_type:
                changes["type"] = {"before": ca.channel_type, "after": cb.channel_type}
            if ca.target_mixer_track != cb.target_mixer_track:
                changes["mixer_track"] = {
                    "before": ca.target_mixer_track,
                    "after": cb.target_mixer_track,
                }
            if abs(ca.volume - cb.volume) > 0.005:
                changes["volume"] = {"before": round(ca.volume, 4), "after": round(cb.volume, 4)}
            if abs(ca.pan - cb.pan) > 0.005:
                changes["pan"] = {"before": round(ca.pan, 4), "after": round(cb.pan, 4)}
            if ca.pitch != cb.pitch:
                changes["pitch"] = {"before": ca.pitch, "after": cb.pitch}

            has_plugin_a = ca.plugin is not None
            has_plugin_b = cb.plugin is not None
            if has_plugin_a != has_plugin_b:
                changes["plugin"] = {"before": has_plugin_a, "after": has_plugin_b}

            if changes:
                channels_modified.append({"index": idx, "name": cb.name, "changes": changes})

    # Pattern diffs
    patterns_added: list[dict[str, Any]] = []
    patterns_removed: list[dict[str, Any]] = []
    patterns_modified: list[dict[str, Any]] = []

    a_pats = {p.number: p for p in proj_a.patterns}
    b_pats = {p.number: p for p in proj_b.patterns}

    all_pat_nums = sorted(set(a_pats.keys()) | set(b_pats.keys()))
    for num in all_pat_nums:
        if num in a_pats and num not in b_pats:
            pa = a_pats[num]
            patterns_removed.append({"number": pa.number, "name": pa.name})
        elif num in b_pats and num not in a_pats:
            pb = b_pats[num]
            patterns_added.append(
                {
                    "number": pb.number,
                    "name": pb.name,
                    "total_notes": pb.total_notes,
                }
            )
        else:
            pa = a_pats[num]
            pb = b_pats[num]
            changes = {}
            if pa.name != pb.name:
                changes["name"] = {"before": pa.name, "after": pb.name}
            if pa.length != pb.length:
                changes["length"] = {"before": pa.length, "after": pb.length}
            if pa.total_notes != pb.total_notes:
                changes["total_notes"] = {"before": pa.total_notes, "after": pb.total_notes}
            else:
                # Compare note content if counts match
                notes_a = [(n.pos, n.len, n.key, n.velocity) for n in pa.all_notes]
                notes_b = [(n.pos, n.len, n.key, n.velocity) for n in pb.all_notes]
                if notes_a != notes_b:
                    changes["notes_content"] = {"before": "different", "after": "different"}

            if changes:
                patterns_modified.append({"number": num, "name": pb.name, "changes": changes})

    # Mixer diffs
    mixer_modified: list[dict[str, Any]] = []
    max_tracks = min(len(proj_a.mixer), len(proj_b.mixer))
    for i in range(max_tracks):
        ma = proj_a.mixer[i]
        mb = proj_b.mixer[i]
        changes = {}
        if ma.name != mb.name:
            changes["name"] = {"before": ma.name, "after": mb.name}
        if abs(ma.volume - mb.volume) > 0.005:
            changes["volume"] = {"before": round(ma.volume, 4), "after": round(mb.volume, 4)}
        if abs(ma.pan - mb.pan) > 0.005:
            changes["pan"] = {"before": round(ma.pan, 4), "after": round(mb.pan, 4)}
        if ma.mute != mb.mute:
            changes["mute"] = {"before": ma.mute, "after": mb.mute}
        if ma.solo != mb.solo:
            changes["solo"] = {"before": ma.solo, "after": mb.solo}
        if ma.routing != mb.routing:
            changes["routing"] = {"before": list(ma.routing), "after": list(mb.routing)}

        if changes:
            mixer_modified.append({"index": i, "name": mb.name or f"Track {i}", "changes": changes})

    # Playlist diffs
    count_a = len(proj_a.arrangement.items)
    count_b = len(proj_b.arrangement.items)
    playlist_diff: dict[str, Any] = {
        "count_a": count_a,
        "count_b": count_b,
        "count_diff": count_b - count_a,
        "has_changes": count_a != count_b,
    }

    return ProjectDiff(
        proj_a_version=proj_a.version,
        proj_b_version=proj_b.version,
        metadata=metadata_diffs,
        channels_added=channels_added,
        channels_removed=channels_removed,
        channels_modified=channels_modified,
        patterns_added=patterns_added,
        patterns_removed=patterns_removed,
        patterns_modified=patterns_modified,
        mixer_modified=mixer_modified,
        playlist_diff=playlist_diff,
    )
