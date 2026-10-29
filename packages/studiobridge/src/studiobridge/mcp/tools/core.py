"""Core discovery and status MCP tools for StudioBridge.

Implements always-on core tools:
- studio_status: Connection, FL/API versions, active mode, transport state, broker health.
- studio_capabilities: Capability matrix, limits, and alternatives.
- studio_doctor: Run diagnostics and return checks with remedies.
- api_search: Progressive disclosure search across FL scripting API by keyword or module.
- api_describe: Signature, since-version, quirks, and examples for a function.
- project_snapshot: Compact overview of tempo, channels, patterns, and mixer tracks.
"""

from __future__ import annotations

import json
from typing import Any

from studiobridge.broker.client import is_process_alive
from studiobridge.core.capabilities import CapabilityRegistry, create_default_registry
from studiobridge.core.errors import DisconnectedError
from studiobridge.core.paths import get_broker_json_path
from studiobridge.manifest.cards import _format_signature
from studiobridge.manifest.drift import load_baseline_manifest
from studiobridge.manifest.overlay import load_default_overlay
from studiobridge.manifest.schema import Manifest
from studiobridge.mcp.schemas import get_schema
from studiobridge.mcp.server import ToolDefinition, ToolResult
from studiobridge.setup.doctor import Doctor
from studiobridge.setup.installer import Installer

# Cached manifest and overlay instances for fast zero-cost search
_CACHED_MANIFEST: Manifest | None = None


def _get_manifest() -> Manifest:
    global _CACHED_MANIFEST
    if _CACHED_MANIFEST is None:
        _CACHED_MANIFEST = load_baseline_manifest()
    return _CACHED_MANIFEST


def _resolve_client(client: Any = None, server: Any = None) -> Any:
    """Resolve an active Studio client from server reference or argument."""
    if client is not None:
        return client
    if server is not None and getattr(server, "client", None) is not None:
        return server.client
    return None


class CoreTools:
    """Provider for core StudioBridge discovery and inspection MCP tools."""

    def __init__(self, client: Any = None, server: Any = None) -> None:
        self.client = client
        self.server = server

    def _get_active_client(self) -> Any:
        resolved = _resolve_client(self.client, self.server)
        if resolved is not None:
            return resolved
        # Attempt connecting to running background broker
        from studiobridge.sdk.client import Studio

        try:
            return Studio.connect(timeout=2.0)
        except Exception as exc:
            raise DisconnectedError(
                f"No active StudioBridge connection: {exc}",
                remedy=(
                    "Ensure FL Studio and the StudioBridge broker daemon are running "
                    "('sbridge broker start')."
                ),
            ) from exc

    def studio_status(self, **kwargs: Any) -> ToolResult:
        """Report connection status, FL Studio and API versions, mode, transport, and broker."""
        client = _resolve_client(self.client, self.server)

        # 1. Inspect local broker process & metadata
        meta_path = get_broker_json_path()
        broker_info: dict[str, Any] = {
            "status": "stopped",
            "running": False,
            "pid": None,
            "port": None,
            "uptime_s": None,
            "lease_holder": None,
            "message": "Broker daemon is not running.",
        }

        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                pid = int(meta.get("pid", 0))
                port = int(meta.get("port", 0))
                alive = is_process_alive(pid)
                broker_info["pid"] = pid
                broker_info["port"] = port
                broker_info["running"] = alive
                if alive:
                    broker_info["status"] = "running"
                    broker_info["message"] = f"Broker daemon running on port {port} (PID {pid})."
                else:
                    broker_info["status"] = "stale"
                    broker_info["message"] = f"Stale metadata: PID {pid} is dead."
            except Exception as exc:
                broker_info["status"] = "error"
                broker_info["message"] = f"Failed to read broker metadata: {exc}"

        # 2. Check client connection and transport state
        if client is not None and getattr(client, "is_connected", False):
            try:
                st = client.status()
                is_playing = False
                tempo = 130.0
                song_pos = 0
                time_sig = [4, 4]
                try:
                    is_playing = bool(client.transport.is_playing())
                    tempo = float(client.transport.get_tempo())
                    song_pos = int(client.transport.get_time())
                    sig = client.transport.get_time_signature()
                    time_sig = [int(sig[0]), int(sig[1])]
                except Exception:
                    pass

                lease_holder = getattr(st, "lease_holder", None)
                if lease_holder:
                    broker_info["lease_holder"] = lease_holder

                structured: dict[str, Any] = {
                    "connected": True,
                    "fl_version": st.fl_version,
                    "api": st.api,
                    "mode": getattr(client, "mode", "read_only"),
                    "project": st.project or "Untitled",
                    "transport": {
                        "is_playing": is_playing,
                        "tempo": tempo,
                        "song_pos": song_pos,
                        "time_signature": time_sig,
                    },
                    "broker": broker_info,
                }
                summary_text = (
                    f"Connected to FL Studio v{st.fl_version} (API {st.api}), "
                    f"mode: {structured['mode']}, transport: "
                    f"{'playing' if is_playing else 'stopped'} at {tempo:.1f} BPM."
                )
                return ToolResult(
                    content=[{"type": "text", "text": summary_text}],
                    structured_content=structured,
                    is_error=False,
                )
            except Exception as exc:
                broker_info["message"] = f"Client status query failed: {exc}"

        # Disconnected fallback
        structured = {
            "connected": False,
            "fl_version": None,
            "api": None,
            "mode": "read_only",
            "project": None,
            "transport": None,
            "broker": broker_info,
        }
        return ToolResult(
            content=[
                {
                    "type": "text",
                    "text": f"StudioBridge disconnected. Broker status: {broker_info['status']}.",
                }
            ],
            structured_content=structured,
            is_error=False,
        )

    def studio_capabilities(
        self,
        capability: str | None = None,
        state: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Inspect the capability matrix, availability states, limits, and alternatives."""
        client = _resolve_client(self.client, self.server)
        reg: CapabilityRegistry = (
            client.caps
            if client is not None and hasattr(client, "caps")
            else create_default_registry()
        )

        if capability:
            eff = reg.evaluate(capability)
            structured = {"capability": eff.to_dict()}
            summary = f"Capability '{capability}': {eff.state.value} ({eff.reason or 'OK'})"
            return ToolResult(
                content=[{"type": "text", "text": summary}],
                structured_content=structured,
                is_error=False,
            )

        agg = reg.aggregate_status()
        caps_map = agg["capabilities"]
        if state:
            caps_map = {k: v for k, v in caps_map.items() if v.get("state") == state}

        structured = {
            "summary": agg["summary"],
            "capabilities": caps_map,
        }
        summary_text = (
            f"StudioBridge Capabilities: {agg['summary']['total']} total, "
            f"{agg['summary'].get('available', 0)} available, "
            f"{agg['summary'].get('degraded', 0)} degraded, "
            f"{agg['summary'].get('unavailable', 0)} unavailable."
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def studio_doctor(
        self,
        skip_live: bool = False,
        fix: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Run diagnostic health checks and return check results with remedies."""
        doctor = Doctor(skip_live=skip_live)
        report = doctor.run()

        if fix and report.has_errors:
            needs_install = any(
                c.id in ("D-DEV-01", "D-SEC-01") and c.status == "fail" for c in report.checks
            )
            if needs_install:
                installer = Installer()
                installer.install(repair=True)
                report = doctor.run()

        counts = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
        checks_list: list[dict[str, Any]] = []
        for c in report.checks:
            status_val = str(c.status)
            counts[status_val] = counts.get(status_val, 0) + 1
            checks_list.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "status": status_val,
                    "details": c.evidence,
                    "remedy": c.remedy,
                }
            )

        structured = {
            "status": "ok" if not report.has_errors else "error",
            "has_errors": report.has_errors,
            "checks": checks_list,
            "summary": counts,
        }
        summary_text = (
            f"Doctor diagnosis: {'HEALTHY' if not report.has_errors else 'ISSUES FOUND'}. "
            f"{counts['pass']} passed, {counts['fail']} failed, {counts['warn']} warnings."
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=report.has_errors,
        )

    def api_search(
        self,
        query: str | None = None,
        module: str | None = None,
        limit: int = 20,
        include_constants: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Search FL Studio scripting API functions and constants by keyword or module filter."""
        manifest = _get_manifest()
        q = (query or "").strip().lower()
        mod_filter = (module or "").strip().lower()

        matches: list[dict[str, Any]] = []

        for mod_name, mod_doc in sorted(manifest.modules.items()):
            if mod_filter and mod_name.lower() != mod_filter:
                continue

            for fn_name, fn_doc in sorted(mod_doc.functions.items()):
                # Match logic: check name, summary, and parameter names
                match_name = q in fn_name.lower() or not q
                match_summary = bool(q and fn_doc.summary and q in fn_doc.summary.lower())
                match_args = bool(q and any(q in a.name.lower() for a in fn_doc.args))

                if match_name or match_summary or match_args:
                    sig = _format_signature(mod_name, fn_name, fn_doc).strip()
                    matches.append(
                        {
                            "module": mod_name,
                            "name": fn_name,
                            "signature": sig,
                            "summary": fn_doc.summary or "",
                            "mutating": bool(fn_doc.mutating),
                            "since": fn_doc.since,
                        }
                    )

            if include_constants and q:
                for const_name, const_val in mod_doc.constants.items():
                    if q in const_name.lower():
                        matches.append(
                            {
                                "module": mod_name,
                                "name": const_name,
                                "signature": f"{mod_name}.{const_name} = {const_val!r}",
                                "summary": f"Constant {const_val}",
                                "mutating": False,
                                "since": 1,
                            }
                        )

        sliced = matches[:limit]
        structured = {
            "matches": sliced,
            "total": len(matches),
            "query": query,
            "module": module,
            "limit": limit,
        }
        summary_text = (
            f"Found {len(matches)} API matches"
            + (f" for '{query}'" if query else "")
            + (f" in module '{module}'" if module else "")
            + f" (showing top {len(sliced)})."
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def api_describe(
        self,
        function: str,
        module: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Retrieve full documentation, signature, quirks, and usage example for a function."""
        manifest = _get_manifest()
        overlay = load_default_overlay()

        clean_fn = function.strip()
        mod_name = module.strip() if module else None

        if "." in clean_fn:
            mod_part, fn_part = clean_fn.split(".", 1)
            mod_name = mod_part
            clean_fn = fn_part

        # If module not specified, search for unique function across modules
        if not mod_name:
            candidates: list[str] = [
                m_name for m_name, m_doc in manifest.modules.items() if clean_fn in m_doc.functions
            ]
            if len(candidates) == 1:
                mod_name = candidates[0]
            elif len(candidates) > 1:
                raise ValueError(
                    f"Ambiguous function name '{clean_fn}' found in multiple modules: "
                    f"{', '.join(candidates)}. Specify 'module' explicitly."
                )
            else:
                raise ValueError(f"Function '{clean_fn}' not found in any API module.")

        if mod_name not in manifest.modules:
            raise ValueError(f"Module '{mod_name}' not found in API manifest.")

        mod_doc = manifest.modules[mod_name]
        if clean_fn not in mod_doc.functions:
            raise ValueError(f"Function '{clean_fn}' not found in module '{mod_name}'.")

        fn_doc = mod_doc.functions[clean_fn]
        sig = _format_signature(mod_name, clean_fn, fn_doc).strip()

        # Check quirks overlay for empirical evidence and tolerances
        quirks_key = f"{mod_name}.{clean_fn}"
        quirks_entry = overlay.get(quirks_key)
        quirks_dict = None
        if quirks_entry is not None:
            tol_val = None
            paired_getter = None
            if quirks_entry.verify is not None:
                if isinstance(quirks_entry.verify, dict):
                    tol_val = quirks_entry.verify.get("tol")
                    paired_getter = quirks_entry.verify.get("getter")
                elif hasattr(quirks_entry.verify, "tol"):
                    tol_val = getattr(quirks_entry.verify, "tol", None)
                    paired_getter = getattr(quirks_entry.verify, "getter", None)

            quirks_dict = {
                "tol": tol_val,
                "notes": quirks_entry.note,
                "evidence": list(quirks_entry.evidence),
                "paired_getter": paired_getter,
            }

        # Construct a clean Python usage example
        if fn_doc.mutating:
            example = (
                f"# Using high-level SDK:\n"
                f"fl.{mod_name}.set_...(...)  # Verified write\n\n"
                f"# Using raw API passthrough:\n"
                f"fl.raw.call('{mod_name}.{clean_fn}', ...)"
            )
        else:
            example = f"# Querying status via SDK:\nresult = fl.raw.call('{mod_name}.{clean_fn}')"

        structured = {
            "module": mod_name,
            "function": clean_fn,
            "signature": sig,
            "since": fn_doc.since,
            "summary": fn_doc.summary or "",
            "args": [a.to_dict() for a in fn_doc.args],
            "ret": fn_doc.ret,
            "mutating": bool(fn_doc.mutating),
            "protected": bool(fn_doc.protected),
            "undo": fn_doc.undo,
            "plane": fn_doc.plane,
            "quirks": quirks_dict,
            "example": example,
        }

        card_text = (
            f"### `{sig}`\n"
            f"**Since API:** v{fn_doc.since} | "
            f"**Plane:** {fn_doc.plane} | **Mutating:** {fn_doc.mutating}\n\n"
            f"{fn_doc.summary or 'No docstring summary available.'}\n"
        )
        return ToolResult(
            content=[{"type": "text", "text": card_text}],
            structured_content=structured,
            is_error=False,
        )

    def project_snapshot(
        self,
        include_empty: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Return a compact overview of tempo, channels, patterns, and active mixer tracks."""
        client = self._get_active_client()

        tempo = float(client.transport.get_tempo())
        is_playing = bool(client.transport.is_playing())
        time_sig = list(client.transport.get_time_signature())

        # Project title
        project_name = "Untitled"
        try:
            p_title = client.project.get_title()
            if p_title:
                project_name = p_title
        except Exception:
            pass

        # Channel summaries (top 20)
        channel_count = client.channels.count()
        channels_summary: list[dict[str, Any]] = []
        for ch in client.channels.list()[:20]:
            channels_summary.append(
                {
                    "index": ch.index,
                    "name": ch.name,
                    "muted": ch.muted,
                    "volume": round(ch.volume, 2),
                }
            )

        # Pattern summaries (top 20)
        pattern_count = client.patterns.count()
        active_pat = int(
            getattr(client.patterns.get_active(), "number", client.patterns.get_active())
        )
        patterns_summary: list[dict[str, Any]] = []
        for pat in client.patterns.list()[:20]:
            patterns_summary.append(
                {
                    "number": pat.number,
                    "name": pat.name,
                }
            )

        # Mixer tracks: Master (track 0) + modified/named tracks
        all_tracks = client.mixer.get_tracks()
        mixer_tracks: list[dict[str, Any]] = []
        for trk in all_tracks:
            # Include Master track always; include others only if non-default unless include_empty
            is_master = trk.index == 0
            is_named = trk.name != f"Insert {trk.index}" and trk.name != "Master"
            is_tweaked = (
                abs(trk.volume - 0.8) > 0.01
                or abs(trk.pan) > 0.01
                or trk.muted
                or trk.solo
                or trk.peak > 0.0
            )

            if is_master or is_named or is_tweaked or include_empty:
                mixer_tracks.append(
                    {
                        "index": trk.index,
                        "name": trk.name,
                        "volume": round(trk.volume, 2),
                        "pan": round(trk.pan, 2),
                        "muted": trk.muted,
                        "solo": trk.solo,
                        "peak": round(trk.peak, 2),
                    }
                )

        structured = {
            "project": project_name,
            "tempo": tempo,
            "time_signature": time_sig,
            "is_playing": is_playing,
            "channel_count": channel_count,
            "channels": channels_summary,
            "pattern_count": pattern_count,
            "active_pattern": active_pat,
            "patterns": patterns_summary,
            "mixer_track_count": 127,
            "mixer_tracks": mixer_tracks,
        }

        summary_text = (
            f"Project '{project_name}' snapshot: {tempo:.1f} BPM, {time_sig[0]}/{time_sig[1]}, "
            f"{channel_count} channels, {pattern_count} patterns, "
            f"{len(mixer_tracks)} active mixer tracks."
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )


def get_core_tools(client: Any = None, server: Any = None) -> list[ToolDefinition]:
    """Instantiate and return the list of core ToolDefinitions."""
    provider = CoreTools(client=client, server=server)

    schema_status = get_schema("studio_status")
    schema_caps = get_schema("studio_capabilities")
    schema_doctor = get_schema("studio_doctor")
    schema_search = get_schema("api_search")
    schema_describe = get_schema("api_describe")
    schema_snapshot = get_schema("project_snapshot")

    return [
        ToolDefinition(
            name="studio_status",
            title=schema_status.get("title", "Studio Status"),
            description=schema_status.get(
                "description",
                "Report connection status, versions, safety mode, transport, and broker health.",
            ),
            input_schema=schema_status.get("inputSchema", {}),
            toolset="core",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.studio_status,
        ),
        ToolDefinition(
            name="studio_capabilities",
            title=schema_caps.get("title", "Studio Capabilities"),
            description=schema_caps.get(
                "description",
                "Inspect capability matrix, availability states, prerequisites, and alternatives.",
            ),
            input_schema=schema_caps.get("inputSchema", {}),
            toolset="core",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.studio_capabilities,
        ),
        ToolDefinition(
            name="studio_doctor",
            title=schema_doctor.get("title", "Studio Doctor"),
            description=schema_doctor.get(
                "description",
                "Run diagnostic health checks across environment, MIDI ports, and scripts.",
            ),
            input_schema=schema_doctor.get("inputSchema", {}),
            toolset="core",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.studio_doctor,
        ),
        ToolDefinition(
            name="api_search",
            title=schema_search.get("title", "API Search"),
            description=schema_search.get(
                "description",
                "Search FL Studio Python scripting API functions, modules, and constants.",
            ),
            input_schema=schema_search.get("inputSchema", {}),
            toolset="core",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.api_search,
        ),
        ToolDefinition(
            name="api_describe",
            title=schema_describe.get("title", "API Describe"),
            description=schema_describe.get(
                "description",
                "Retrieve documentation, signature, quirks, and examples for an FL function.",
            ),
            input_schema=schema_describe.get("inputSchema", {}),
            toolset="core",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.api_describe,
        ),
        ToolDefinition(
            name="project_snapshot",
            title=schema_snapshot.get("title", "Project Snapshot"),
            description=schema_snapshot.get(
                "description",
                "Compact overview of project: tempo, signature, transport, channels, and patterns.",
            ),
            input_schema=schema_snapshot.get("inputSchema", {}),
            toolset="core",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.project_snapshot,
        ),
    ]


__all__ = [
    "CoreTools",
    "get_core_tools",
]
