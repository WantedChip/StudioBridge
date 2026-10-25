"""FLP project mutation operators and audit journaling.

Implements validated offline project modifications per 07_l0e_flp_engine.md §3.4,
10_l2_interfaces.md §3, [FLP-21], and [FLP-30].
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from studiobridge.core.errors import FlpInvariantViolationError
from studiobridge.flp.model.elements import (
    Marker,
    Note,
    Pattern,
    PlaylistItem,
)

if TYPE_CHECKING:
    from types import TracebackType

    from studiobridge.flp.model.project import Project


@dataclass(frozen=True, slots=True)
class MutationRecord:
    """Audit log entry for an offline FLP project mutation [FLP-30].

    Attributes:
        ts: Epoch timestamp of the mutation.
        op: Operation name (e.g. 'project.set_tempo', 'pattern.set_notes').
        target: Target identifier (e.g. 'project', 'pattern:1', 'channel:0').
        params: Parameters dictionary supplied to the mutation operator.
        before: Previous value or summary before mutation.
        after: New value or summary after mutation.
    """

    ts: float
    op: str
    target: str
    params: dict[str, Any] = field(default_factory=dict)
    before: Any = None
    after: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary representation."""
        return {
            "ts": self.ts,
            "op": self.op,
            "target": self.target,
            "params": self.params,
            "before": self.before,
            "after": self.after,
        }


class ProjectMutator:
    """Validated project modifier recording mutation journal and tracking touched elements.

    Preserves original serialized bytes for untouched elements per [FLP-21].
    """

    def __init__(self, project: Project) -> None:
        self.project: Project = project
        self.records: list[MutationRecord] = []
        self.touched_metadata: set[str] = set()
        self.touched_channels: set[int] = set()
        self.touched_patterns: set[int] = set()
        self.touched_mixer_tracks: set[int] = set()
        self.touched_playlist: bool = False

    def __enter__(self) -> ProjectMutator:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass

    def _log(
        self,
        op: str,
        target: str,
        params: dict[str, Any],
        before: Any,
        after: Any,
    ) -> None:
        """Append an audit record to the mutation journal [FLP-30]."""
        self.records.append(
            MutationRecord(
                ts=time.time(),
                op=op,
                target=target,
                params=params,
                before=before,
                after=after,
            )
        )

    # =========================================================================
    # 1. Project-Level Mutation Operators
    # =========================================================================

    def set_tempo(self, bpm: float) -> ProjectMutator:
        """Set project tempo (and fine tempo) in BPM [FLP-30].

        Args:
            bpm: Tempo in beats per minute (10.0 to 522.0).

        Raises:
            FlpInvariantViolationError: If BPM is out of valid range.
        """
        bpm_val = float(bpm)
        if not (10.0 <= bpm_val <= 522.0):
            raise FlpInvariantViolationError(
                f"Tempo {bpm_val:.2f} BPM out of valid FL Studio range [10.0, 522.0]"
            )
        before = self.project.tempo
        self.project.tempo = bpm_val
        self.project.fine_tempo = bpm_val
        self.touched_metadata.add("tempo")
        self._log("project.set_tempo", "project", {"bpm": bpm_val}, before, bpm_val)
        return self

    def set_title(self, title: str) -> ProjectMutator:
        """Set project title string [FLP-30]."""
        before = self.project.title
        self.project.title = str(title)
        self.touched_metadata.add("title")
        self._log("project.set_title", "project", {"title": title}, before, title)
        return self

    def set_author(self, author: str) -> ProjectMutator:
        """Set project author / artist string [FLP-30]."""
        before = self.project.author
        self.project.author = str(author)
        self.touched_metadata.add("author")
        self._log("project.set_author", "project", {"author": author}, before, author)
        return self

    def set_comments(self, comments: str) -> ProjectMutator:
        """Set project description / comments string [FLP-30]."""
        before = self.project.comments
        self.project.comments = str(comments)
        self.touched_metadata.add("comments")
        self._log("project.set_comments", "project", {"comments": comments}, before, comments)
        return self

    # =========================================================================
    # 2. Pattern-Level Mutation Operators
    # =========================================================================

    def add_pattern(
        self,
        name: str | None = None,
        color: int | str | None = None,
    ) -> Pattern:
        """Add a new pattern with the next available pattern number [FLP-30].

        Returns:
            Newly created Pattern instance.
        """
        existing = {p.number for p in self.project.patterns}
        new_num = 1
        while new_num in existing:
            new_num += 1

        pat_name = name or f"Pattern {new_num}"
        pattern = Pattern(
            number=new_num,
            name=pat_name,
            color=color,
        )
        self.project.patterns.append(pattern)
        self.project.patterns.sort(key=lambda p: p.number)
        self.touched_patterns.add(new_num)
        self._log(
            "pattern.add_pattern",
            f"pattern:{new_num}",
            {"name": pat_name, "color": color},
            None,
            pattern.to_dict(),
        )
        return pattern

    def rename_pattern(self, pattern_number: int, name: str) -> ProjectMutator:
        """Rename pattern by pattern number [FLP-30]."""
        pat = self.project.pattern(pattern_number)
        before = pat.name
        pat.name = str(name)
        self.touched_patterns.add(pattern_number)
        self._log(
            "pattern.rename_pattern",
            f"pattern:{pattern_number}",
            {"name": name},
            before,
            name,
        )
        return self

    def recolor_pattern(
        self,
        pattern_number: int,
        color: int | str | None,
    ) -> ProjectMutator:
        """Set pattern color [FLP-30]."""
        pat = self.project.pattern(pattern_number)
        before = pat.color
        pat.color = color
        self.touched_patterns.add(pattern_number)
        self._log(
            "pattern.recolor_pattern",
            f"pattern:{pattern_number}",
            {"color": color},
            before,
            color,
        )
        return self

    def set_notes(
        self,
        pattern_number: int,
        channel_index: int,
        notes: Sequence[Note],
        mode: str = "replace",
    ) -> ProjectMutator:
        """Set notes for a specific channel in a pattern (append or replace) [FLP-30].

        Args:
            pattern_number: 1-based pattern number.
            channel_index: Target channel rack index.
            notes: Sequence of Note instances.
            mode: 'replace' or 'append'.
        """
        pat = self.project.pattern(pattern_number)
        if not (0 <= channel_index < len(self.project.channels)):
            raise IndexError(
                f"Channel index {channel_index} out of range (0..{len(self.project.channels) - 1})"
            )
        before_notes = list(pat.get_notes(channel_index))
        if mode == "append":
            updated_notes = before_notes + list(notes)
        elif mode in ("replace", "replace_all"):
            updated_notes = list(notes)
        else:
            raise ValueError(f"Unknown set_notes mode '{mode}'; expected 'replace' or 'append'")

        # Sort notes chronologically by tick position
        updated_notes.sort(key=lambda n: n.pos)
        pat.set_notes(channel_index, updated_notes)
        self.touched_patterns.add(pattern_number)
        self._log(
            "pattern.set_notes",
            f"pattern:{pattern_number}",
            {
                "channel_index": channel_index,
                "note_count": len(notes),
                "mode": mode,
            },
            len(before_notes),
            len(updated_notes),
        )
        return self

    def clear_pattern(
        self,
        pattern_number: int,
        channel_index: int | None = None,
    ) -> ProjectMutator:
        """Clear notes in a pattern across all channels or a single channel [FLP-30]."""
        pat = self.project.pattern(pattern_number)
        if channel_index is None:
            before_count = pat.total_notes
            pat.notes.clear()
            self._log(
                "pattern.clear_pattern",
                f"pattern:{pattern_number}",
                {"channel_index": None},
                before_count,
                0,
            )
        else:
            before_count = len(pat.get_notes(channel_index))
            pat.notes.pop(channel_index, None)
            self._log(
                "pattern.clear_pattern",
                f"pattern:{pattern_number}",
                {"channel_index": channel_index},
                before_count,
                0,
            )
        self.touched_patterns.add(pattern_number)
        return self

    # =========================================================================
    # 3. Channel-Level Mutation Operators
    # =========================================================================

    def rename_channel(self, channel_index: int, name: str) -> ProjectMutator:
        """Rename channel rack generator [FLP-30]."""
        ch = self.project.channel(channel_index)
        before = ch.name
        ch.name = str(name)
        self.touched_channels.add(channel_index)
        self._log(
            "channel.rename_channel",
            f"channel:{channel_index}",
            {"name": name},
            before,
            name,
        )
        return self

    def recolor_channel(
        self,
        channel_index: int,
        color: int | str | None,
    ) -> ProjectMutator:
        """Set channel display color [FLP-30]."""
        ch = self.project.channel(channel_index)
        before = ch.color
        ch.color = color
        self.touched_channels.add(channel_index)
        self._log(
            "channel.recolor_channel",
            f"channel:{channel_index}",
            {"color": color},
            before,
            color,
        )
        return self

    def set_mixer_target(self, channel_index: int, mixer_track: int) -> ProjectMutator:
        """Route channel output to mixer track index [FLP-30]."""
        ch = self.project.channel(channel_index)
        mixer_len = len(self.project.mixer) if self.project.mixer else 126
        if not (0 <= mixer_track < mixer_len):
            raise IndexError(f"Mixer track {mixer_track} out of range (0..{mixer_len - 1})")
        before = ch.target_mixer_track
        ch.target_mixer_track = mixer_track
        self.touched_channels.add(channel_index)
        self._log(
            "channel.set_mixer_target",
            f"channel:{channel_index}",
            {"mixer_track": mixer_track},
            before,
            mixer_track,
        )
        return self

    def set_channel_volume(self, channel_index: int, volume: float) -> ProjectMutator:
        """Set channel volume level (0.0 to 1.0 or normalized) [FLP-30]."""
        ch = self.project.channel(channel_index)
        vol_val = max(0.0, min(2.0, float(volume)))
        before = ch.volume
        ch.volume = vol_val
        self.touched_channels.add(channel_index)
        self._log(
            "channel.set_channel_volume",
            f"channel:{channel_index}",
            {"volume": vol_val},
            before,
            vol_val,
        )
        return self

    def set_channel_pan(self, channel_index: int, pan: float) -> ProjectMutator:
        """Set channel stereo panning (-1.0 to 1.0) [FLP-30]."""
        ch = self.project.channel(channel_index)
        pan_val = max(-1.0, min(1.0, float(pan)))
        before = ch.pan
        ch.pan = pan_val
        self.touched_channels.add(channel_index)
        self._log(
            "channel.set_channel_pan",
            f"channel:{channel_index}",
            {"pan": pan_val},
            before,
            pan_val,
        )
        return self

    # =========================================================================
    # 4. Mixer-Level Mutation Operators
    # =========================================================================

    def rename_track(self, track_index: int, name: str) -> ProjectMutator:
        """Rename mixer insert track [FLP-30]."""
        mt = self.project.mixer_track(track_index)
        before = mt.name
        mt.name = str(name)
        self.touched_mixer_tracks.add(track_index)
        self._log(
            "mixer.rename_track",
            f"mixer:{track_index}",
            {"name": name},
            before,
            name,
        )
        return self

    def recolor_track(
        self,
        track_index: int,
        color: int | str | None,
    ) -> ProjectMutator:
        """Set mixer track display color [FLP-30]."""
        mt = self.project.mixer_track(track_index)
        before = mt.color
        mt.color = color
        self.touched_mixer_tracks.add(track_index)
        self._log(
            "mixer.recolor_track",
            f"mixer:{track_index}",
            {"color": color},
            before,
            color,
        )
        return self

    def set_track_volume(self, track_index: int, volume: float) -> ProjectMutator:
        """Set mixer track fader volume level [FLP-30]."""
        mt = self.project.mixer_track(track_index)
        vol_val = max(0.0, min(2.0, float(volume)))
        before = mt.volume
        mt.volume = vol_val
        self.touched_mixer_tracks.add(track_index)
        self._log(
            "mixer.set_track_volume",
            f"mixer:{track_index}",
            {"volume": vol_val},
            before,
            vol_val,
        )
        return self

    def set_track_pan(self, track_index: int, pan: float) -> ProjectMutator:
        """Set mixer track stereo panning (-1.0 to 1.0) [FLP-30]."""
        mt = self.project.mixer_track(track_index)
        pan_val = max(-1.0, min(1.0, float(pan)))
        before = mt.pan
        mt.pan = pan_val
        self.touched_mixer_tracks.add(track_index)
        self._log(
            "mixer.set_track_pan",
            f"mixer:{track_index}",
            {"pan": pan_val},
            before,
            pan_val,
        )
        return self

    def set_track_mute(self, track_index: int, mute: bool) -> ProjectMutator:
        """Mute or un-mute mixer track [FLP-30]."""
        mt = self.project.mixer_track(track_index)
        before = mt.mute
        mt.mute = bool(mute)
        self.touched_mixer_tracks.add(track_index)
        self._log(
            "mixer.set_track_mute",
            f"mixer:{track_index}",
            {"mute": bool(mute)},
            before,
            bool(mute),
        )
        return self

    def set_track_solo(self, track_index: int, solo: bool) -> ProjectMutator:
        """Solo or un-solo mixer track [FLP-30]."""
        mt = self.project.mixer_track(track_index)
        before = mt.solo
        mt.solo = bool(solo)
        self.touched_mixer_tracks.add(track_index)
        self._log(
            "mixer.set_track_solo",
            f"mixer:{track_index}",
            {"solo": bool(solo)},
            before,
            bool(solo),
        )
        return self

    def set_track_routing(
        self,
        track_index: int,
        dest_tracks: Sequence[int],
    ) -> ProjectMutator:
        """Configure mixer send routing destinations [FLP-30]."""
        mt = self.project.mixer_track(track_index)
        mixer_len = len(self.project.mixer) if self.project.mixer else 126
        for d in dest_tracks:
            if not (0 <= d < mixer_len):
                raise IndexError(f"Routing destination track {d} out of range (0..{mixer_len - 1})")
        before = list(mt.routing)
        mt.routing = list(dest_tracks)
        self.touched_mixer_tracks.add(track_index)
        self._log(
            "mixer.set_track_routing",
            f"mixer:{track_index}",
            {"dest_tracks": list(dest_tracks)},
            before,
            list(dest_tracks),
        )
        return self

    def set_slot_state(
        self,
        track_index: int,
        slot_index: int,
        enabled: bool,
    ) -> ProjectMutator:
        """Enable or bypass mixer insert effect slot [FLP-30]."""
        mt = self.project.mixer_track(track_index)
        if not (0 <= slot_index < len(mt.slots)):
            raise IndexError(f"Slot index {slot_index} out of range (0..{len(mt.slots) - 1})")
        slot = mt.slots[slot_index]
        before = slot.enabled
        slot.enabled = bool(enabled)
        self.touched_mixer_tracks.add(track_index)
        self._log(
            "mixer.set_slot_state",
            f"mixer:{track_index}.slot:{slot_index}",
            {"enabled": bool(enabled)},
            before,
            bool(enabled),
        )
        return self

    # =========================================================================
    # 5. Playlist-Level Mutation Operators
    # =========================================================================

    def add_playlist_item(
        self,
        track: int,
        start: int,
        length: int,
        pattern_index: int | None = None,
        clip_ref: int | None = None,
        flags: int = 0,
        mute: bool = False,
    ) -> PlaylistItem:
        """Place a pattern or clip item on the playlist timeline [FLP-30].

        Args:
            track: 1-based playlist lane track index.
            start: Start position in PPQ ticks.
            length: Duration in PPQ ticks.
            pattern_index: Pattern number placed on timeline.
            clip_ref: Channel rack index if audio/automation clip.
            flags: Raw placement flags.
            mute: Muted state.

        Returns:
            Newly created PlaylistItem instance.
        """
        if track < 1:
            raise FlpInvariantViolationError(f"Playlist lane track must be >= 1, got {track}")
        if start < 0:
            raise FlpInvariantViolationError(f"Playlist start tick {start} cannot be negative")
        if length < 0:
            raise FlpInvariantViolationError(f"Playlist length {length} cannot be negative")
        if pattern_index is not None and not any(
            p.number == pattern_index for p in self.project.patterns
        ):
            raise FlpInvariantViolationError(
                f"Playlist item references non-existent pattern number {pattern_index}"
            )
        if clip_ref is not None and not (0 <= clip_ref < len(self.project.channels)):
            raise FlpInvariantViolationError(
                f"Playlist item references non-existent clip channel {clip_ref}"
            )

        item = PlaylistItem(
            track=track,
            start=start,
            length=length,
            pattern_index=pattern_index,
            clip_ref=clip_ref,
            flags=flags,
            mute=mute,
        )
        self.project.arrangement.items.append(item)
        self.touched_playlist = True
        self._log(
            "playlist.add_playlist_item",
            "playlist",
            {
                "track": track,
                "start": start,
                "length": length,
                "pattern_index": pattern_index,
                "clip_ref": clip_ref,
            },
            None,
            item.to_dict(),
        )
        return item

    def move_playlist_item(
        self,
        item_index: int,
        track: int | None = None,
        start: int | None = None,
    ) -> ProjectMutator:
        """Move playlist item to a new track lane or timeline position [FLP-30]."""
        items = self.project.arrangement.items
        if not (0 <= item_index < len(items)):
            raise IndexError(f"Playlist item index {item_index} out of range (0..{len(items) - 1})")
        item = items[item_index]
        before = (item.track, item.start)
        if track is not None:
            if track < 1:
                raise FlpInvariantViolationError(f"Playlist track must be >= 1, got {track}")
            item.track = track
        if start is not None:
            if start < 0:
                raise FlpInvariantViolationError(f"Playlist start tick {start} cannot be negative")
            item.start = start

        self.touched_playlist = True
        self._log(
            "playlist.move_playlist_item",
            f"playlist.item:{item_index}",
            {"track": track, "start": start},
            before,
            (item.track, item.start),
        )
        return self

    def delete_playlist_item(self, item_index: int) -> ProjectMutator:
        """Remove a playlist item by index [FLP-30]."""
        items = self.project.arrangement.items
        if not (0 <= item_index < len(items)):
            raise IndexError(f"Playlist item index {item_index} out of range (0..{len(items) - 1})")
        removed = items.pop(item_index)
        self.touched_playlist = True
        self._log(
            "playlist.delete_playlist_item",
            f"playlist.item:{item_index}",
            {"item_index": item_index},
            removed.to_dict(),
            None,
        )
        return self

    def set_track_name(self, track_index: int, name: str) -> ProjectMutator:
        """Set playlist lane track display name [FLP-30]."""
        while len(self.project.arrangement.tracks) <= track_index:
            self.project.arrangement.tracks.append({})
        before = self.project.arrangement.tracks[track_index].get("name")
        self.project.arrangement.tracks[track_index]["name"] = str(name)
        self.touched_playlist = True
        self._log(
            "playlist.set_track_name",
            f"playlist.track:{track_index}",
            {"name": name},
            before,
            name,
        )
        return self

    def set_track_color(
        self,
        track_index: int,
        color: int | str | None,
    ) -> ProjectMutator:
        """Set playlist lane track display color [FLP-30]."""
        while len(self.project.arrangement.tracks) <= track_index:
            self.project.arrangement.tracks.append({})
        before = self.project.arrangement.tracks[track_index].get("color")
        self.project.arrangement.tracks[track_index]["color"] = color
        self.touched_playlist = True
        self._log(
            "playlist.set_track_color",
            f"playlist.track:{track_index}",
            {"color": color},
            before,
            color,
        )
        return self

    def add_marker(
        self,
        name: str,
        position_ticks: int,
        time_signature: tuple[int, int] | None = None,
    ) -> Marker:
        """Add a timeline marker or time signature change marker [FLP-30]."""
        if position_ticks < 0:
            raise FlpInvariantViolationError(f"Marker position {position_ticks} cannot be negative")
        marker = Marker(
            name=str(name),
            position_ticks=position_ticks,
            time_signature=time_signature,
        )
        self.project.arrangement.markers.append(marker)
        self.project.arrangement.markers.sort(key=lambda m: m.position_ticks)
        self.touched_playlist = True
        self._log(
            "playlist.add_marker",
            "playlist.markers",
            {"name": name, "position_ticks": position_ticks, "time_signature": time_signature},
            None,
            marker.to_dict(),
        )
        return marker
