"""Model Context Protocol (MCP) read-only resource providers and URI handlers.

Implements URI resource resolution for live bridge status, machine capabilities,
project overview, API manifest cards, and recent journal records per
10_l2_interfaces.md §2.5 and 12_crosscutting.md §1 [SEC-05].
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from studiobridge.core.capabilities import create_default_registry
from studiobridge.core.paths import get_broker_json_path, get_journal_dir
from studiobridge.manifest.cards import _format_signature, generate_card
from studiobridge.manifest.drift import load_baseline_manifest
from studiobridge.manifest.schema import Manifest
from studiobridge.mcp.instructions import mark_untrusted
from studiobridge.sdk.journal import MutationJournal

# RFC 6570 URI template patterns
API_FN_PATTERN = re.compile(r"^studio://api/([a-zA-Z0-9_]+)/([a-zA-Z0-9_]+)$")
API_MOD_PATTERN = re.compile(r"^studio://api/([a-zA-Z0-9_]+)$")
RENDER_JOB_PATTERN = re.compile(r"^studio://render/([a-zA-Z0-9_\-]+)$")


@dataclass(frozen=True)
class ResourceDefinition:
    """Framework-agnostic MCP resource definition."""

    uri: str
    name: str
    description: str | None = None
    mime_type: str = "application/json"

    def to_mcp_dict(self) -> dict[str, Any]:
        """Serialize resource definition into standard MCP resources/list shape."""
        res: dict[str, Any] = {
            "uri": self.uri,
            "name": self.name,
            "mimeType": self.mime_type,
        }
        if self.description:
            res["description"] = self.description
        return res


@dataclass(frozen=True)
class ResourceTemplate:
    """Framework-agnostic MCP resource template definition."""

    uri_template: str
    name: str
    description: str | None = None
    mime_type: str = "application/json"

    def to_mcp_dict(self) -> dict[str, Any]:
        """Serialize resource template into standard MCP resources/templates/list shape."""
        res: dict[str, Any] = {
            "uriTemplate": self.uri_template,
            "name": self.name,
            "mimeType": self.mime_type,
        }
        if self.description:
            res["description"] = self.description
        return res


@dataclass(frozen=True)
class ResourceContent:
    """Content payload for a resolved resource read."""

    uri: str
    mime_type: str = "application/json"
    text: str | None = None
    blob: str | None = None

    def to_mcp_dict(self) -> dict[str, Any]:
        """Serialize resource content into standard MCP resources/read item shape."""
        res: dict[str, Any] = {
            "uri": self.uri,
            "mimeType": self.mime_type,
        }
        if self.text is not None:
            res["text"] = self.text
        if self.blob is not None:
            res["blob"] = self.blob
        return res


def _resolve_client(client: Any = None, server: Any = None) -> Any:
    """Resolve active Studio client from explicit arg, server reference, or daemon."""
    if client is not None:
        return client
    if server is not None and getattr(server, "client", None) is not None:
        return server.client
    from studiobridge.sdk.client import Studio

    try:
        return Studio.connect(timeout=0.5)
    except Exception:
        return None


class ResourceProvider:
    """Provider for StudioBridge read-only MCP resources and URI templates."""

    def __init__(self, client: Any = None, server: Any = None) -> None:
        self.client = client
        self.server = server
        self._manifest: Manifest | None = None

    def _get_manifest(self) -> Manifest:
        if self._manifest is None:
            self._manifest = load_baseline_manifest()
        return self._manifest

    def get_resources(self) -> list[ResourceDefinition]:
        """Return catalog of static resources."""
        return [
            ResourceDefinition(
                uri="studio://status",
                name="Live Bridge Status",
                description="Live connection, broker, and FL Studio engine status.",
                mime_type="application/json",
            ),
            ResourceDefinition(
                uri="studio://capabilities",
                name="Machine Capability Matrix",
                description="Dynamic machine and FL Studio capability matrix.",
                mime_type="application/json",
            ),
            ResourceDefinition(
                uri="studio://project/summary",
                name="Project Summary",
                description="Compact overview of currently loaded project in FL Studio.",
                mime_type="application/json",
            ),
            ResourceDefinition(
                uri="studio://journal/latest",
                name="Recent Journal Entries",
                description="Recent operation journal entries from the mutation journal.",
                mime_type="application/json",
            ),
        ]

    def get_resource_templates(self) -> list[ResourceTemplate]:
        """Return catalog of parameterized resource templates."""
        return [
            ResourceTemplate(
                uri_template="studio://api/{module}",
                name="Module API Functions",
                description=(
                    "List of functions available in an FL Studio Python module "
                    "with short signatures."
                ),
                mime_type="application/json",
            ),
            ResourceTemplate(
                uri_template="studio://api/{module}/{function}",
                name="Function Documentation Card",
                description=(
                    "Full markdown documentation card for an FL Studio Python API function."
                ),
                mime_type="text/markdown",
            ),
            ResourceTemplate(
                uri_template="studio://render/{job_id}",
                name="Render Job Progress and Metrics",
                description=(
                    "Streaming progress, completion state, and audio sidecar metrics "
                    "for a render job."
                ),
                mime_type="application/json",
            ),
        ]

    def read_resource(self, uri: str) -> ResourceContent:
        """Resolve and read a resource by URI.

        Raises ValueError if URI is unrecognized or refers to missing module/function.
        """
        clean_uri = uri.strip()

        # 1. Static resources
        if clean_uri == "studio://status":
            return self._read_status()
        if clean_uri == "studio://capabilities":
            return self._read_capabilities()
        if clean_uri == "studio://project/summary":
            return self._read_project_summary()
        if clean_uri == "studio://journal/latest":
            return self._read_journal_latest()

        # 2. Function card template: studio://api/{module}/{function}
        fn_match = API_FN_PATTERN.match(clean_uri)
        if fn_match:
            mod_name = fn_match.group(1)
            fn_name = fn_match.group(2)
            return self._read_api_function(clean_uri, mod_name, fn_name)

        # 3. Module functions template: studio://api/{module}
        mod_match = API_MOD_PATTERN.match(clean_uri)
        if mod_match:
            mod_name = mod_match.group(1)
            return self._read_api_module(clean_uri, mod_name)

        # 4. Render job template: studio://render/{job_id}
        render_match = RENDER_JOB_PATTERN.match(clean_uri)
        if render_match:
            job_id = render_match.group(1)
            return self._read_render_job(clean_uri, job_id)

        raise ValueError(f"Resource URI not recognized: '{clean_uri}'")

    def _read_status(self) -> ResourceContent:
        """Generate studio://status JSON content."""
        client = _resolve_client(self.client, self.server)

        # Inspect local broker process & metadata
        meta_path = get_broker_json_path()
        broker_info: dict[str, Any] = {
            "status": "stopped",
            "running": False,
            "pid": None,
            "port": None,
            "uptime_s": None,
            "message": "Broker daemon is not running.",
        }
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                broker_info.update(
                    {
                        "status": "running" if meta.get("alive") else "stale",
                        "running": bool(meta.get("alive")),
                        "pid": meta.get("pid"),
                        "port": meta.get("port"),
                        "uptime_s": meta.get("uptime_s"),
                        "message": "Broker is running.",
                    }
                )
            except Exception as exc:
                broker_info["message"] = f"Failed to read broker metadata: {exc}"

        if client is not None and getattr(client, "is_connected", True):
            try:
                st = client.status()
                is_playing = False
                tempo = 130.0
                song_pos = 0.0
                time_sig = [4, 4]
                try:
                    is_playing = bool(client.transport.is_playing())
                    tempo = float(client.transport.get_tempo())
                    song_pos = float(client.transport.get_time())
                    sig = client.transport.get_time_signature()
                    time_sig = [int(sig[0]), int(sig[1])]
                except Exception:
                    pass

                payload: dict[str, Any] = {
                    "connected": True,
                    "fl_version": getattr(st, "fl_version", None),
                    "api": getattr(st, "api", None),
                    "mode": getattr(client, "mode", "read_only"),
                    "project": mark_untrusted(getattr(st, "project", None) or "Untitled"),
                    "transport": {
                        "is_playing": is_playing,
                        "tempo": tempo,
                        "song_pos": song_pos,
                        "time_signature": time_sig,
                    },
                    "broker": broker_info,
                }
                return ResourceContent(
                    uri="studio://status",
                    mime_type="application/json",
                    text=json.dumps(payload, indent=2),
                )
            except Exception:
                pass

        payload = {
            "connected": False,
            "fl_version": None,
            "api": None,
            "mode": "read_only",
            "project": None,
            "transport": None,
            "broker": broker_info,
        }
        return ResourceContent(
            uri="studio://status",
            mime_type="application/json",
            text=json.dumps(payload, indent=2),
        )

    def _read_capabilities(self) -> ResourceContent:
        """Generate studio://capabilities JSON content."""
        client = _resolve_client(self.client, self.server)
        reg = (
            client.caps
            if client is not None and hasattr(client, "caps")
            else create_default_registry()
        )
        agg = reg.aggregate_status()
        return ResourceContent(
            uri="studio://capabilities",
            mime_type="application/json",
            text=json.dumps(agg, indent=2),
        )

    def _read_project_summary(self) -> ResourceContent:
        """Generate studio://project/summary JSON content with untrusted metadata."""
        client = _resolve_client(self.client, self.server)
        if client is None:
            payload = {
                "connected": False,
                "project": None,
                "message": "Not connected to FL Studio.",
            }
            return ResourceContent(
                uri="studio://project/summary",
                mime_type="application/json",
                text=json.dumps(payload, indent=2),
            )

        tempo = float(client.transport.get_tempo())
        is_playing = bool(client.transport.is_playing())
        time_sig = list(client.transport.get_time_signature())

        # Project title, author, and comments carry untrusted: true metadata [SEC-05]
        project_title = "Untitled"
        project_author = ""
        project_comment = ""
        try:
            p_info = client.project.get_info()
            project_title = str(p_info.title)
            project_author = str(p_info.author)
            project_comment = str(p_info.comment)
        except Exception:
            try:
                p_title = client.project.get_title()
                if p_title:
                    project_title = str(p_title)
            except Exception:
                pass

        project_meta = {
            "title": project_title,
            "author": project_author,
            "comment": project_comment,
            "untrusted": True,
        }

        # Channel summaries with untrusted name marker
        channels_summary: list[dict[str, Any]] = []
        for ch in client.channels.list()[:20]:
            channels_summary.append(
                {
                    "index": ch.index,
                    "name": str(ch.name),
                    "muted": bool(ch.muted),
                    "volume": round(float(ch.volume), 2),
                    "untrusted": True,
                }
            )

        # Pattern summaries with untrusted name marker
        patterns_summary: list[dict[str, Any]] = []
        for pat in client.patterns.list()[:20]:
            patterns_summary.append(
                {
                    "number": pat.number,
                    "name": str(pat.name),
                    "untrusted": True,
                }
            )

        # Mixer track summaries with untrusted name marker
        all_tracks = client.mixer.get_tracks()
        mixer_tracks: list[dict[str, Any]] = []
        for trk in all_tracks:
            is_master = trk.index == 0
            is_named = trk.name not in (f"Insert {trk.index}", "Master")
            is_tweaked = (
                abs(trk.volume - 0.8) > 0.01
                or abs(trk.pan) > 0.01
                or trk.muted
                or trk.solo
                or trk.peak > 0.0
            )
            if is_master or is_named or is_tweaked:
                mixer_tracks.append(
                    {
                        "index": trk.index,
                        "name": str(trk.name),
                        "volume": round(float(trk.volume), 2),
                        "pan": round(float(trk.pan), 2),
                        "muted": bool(trk.muted),
                        "solo": bool(trk.solo),
                        "untrusted": True,
                    }
                )

        payload = {
            "connected": True,
            "project": project_meta,
            "tempo": tempo,
            "time_signature": time_sig,
            "is_playing": is_playing,
            "channel_count": client.channels.count(),
            "channels": channels_summary,
            "pattern_count": client.patterns.count(),
            "active_pattern": int(
                getattr(client.patterns.get_active(), "number", client.patterns.get_active())
            ),
            "patterns": patterns_summary,
            "mixer_track_count": len(all_tracks),
            "mixer_tracks": mixer_tracks,
        }

        return ResourceContent(
            uri="studio://project/summary",
            mime_type="application/json",
            text=json.dumps(payload, indent=2),
        )

    def _read_journal_latest(self) -> ResourceContent:
        """Generate studio://journal/latest JSON content."""
        client = _resolve_client(self.client, self.server)
        entries: list[Any] = []
        session_id = "default"

        if client is not None and hasattr(client, "safety") and hasattr(client.safety, "journal"):
            entries = client.safety.journal.list(limit=50)
            session_id = getattr(client.safety.journal, "session_id", "default")
        else:
            # Fallback: check latest journal file in journal directory
            journal_dir = get_journal_dir()
            if journal_dir.exists():
                files = sorted(
                    journal_dir.glob("*.jsonl"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if files:
                    session_id = files[0].stem
                    j = MutationJournal(session_id=session_id)
                    entries = j.list(limit=50)

        entry_dicts = [e.to_dict() if hasattr(e, "to_dict") else e for e in entries]
        payload = {
            "session_id": session_id,
            "count": len(entry_dicts),
            "entries": entry_dicts,
        }
        return ResourceContent(
            uri="studio://journal/latest",
            mime_type="application/json",
            text=json.dumps(payload, indent=2),
        )

    def _read_api_module(self, uri: str, module_name: str) -> ResourceContent:
        """Generate studio://api/{module} JSON function catalog."""
        manifest = self._get_manifest()
        if module_name not in manifest.modules:
            valid_mods = ", ".join(sorted(manifest.modules.keys()))
            raise ValueError(
                f"Module '{module_name}' not found in API manifest. Available modules: {valid_mods}"
            )

        mod_doc = manifest.modules[module_name]
        fns: list[dict[str, Any]] = []
        for fn_name, fn_doc in mod_doc.functions.items():
            sig = _format_signature(module_name, fn_name, fn_doc).strip()
            fns.append(
                {
                    "name": fn_name,
                    "signature": sig,
                    "summary": fn_doc.summary.strip() if fn_doc.summary else "",
                    "since": fn_doc.since,
                    "mutating": bool(fn_doc.mutating),
                    "plane": fn_doc.plane,
                    "args_count": len(fn_doc.args),
                    "ret": fn_doc.ret,
                    "uri": f"studio://api/{module_name}/{fn_name}",
                }
            )

        payload = {
            "module": module_name,
            "summary": mod_doc.summary.strip()
            if mod_doc.summary
            else f"FL Studio {module_name} API module",
            "function_count": len(fns),
            "functions": fns,
        }
        return ResourceContent(
            uri=uri,
            mime_type="application/json",
            text=json.dumps(payload, indent=2),
        )

    def _read_api_function(self, uri: str, module_name: str, fn_name: str) -> ResourceContent:
        """Generate studio://api/{module}/{function} Markdown reference card."""
        manifest = self._get_manifest()
        if module_name not in manifest.modules:
            valid_mods = ", ".join(sorted(manifest.modules.keys()))
            raise ValueError(
                f"Module '{module_name}' not found in API manifest. Available modules: {valid_mods}"
            )

        mod_doc = manifest.modules[module_name]
        if fn_name not in mod_doc.functions:
            raise ValueError(f"Function '{fn_name}' not found in module '{module_name}'.")

        fn_doc = mod_doc.functions[fn_name]
        card_md = generate_card(module_name, fn_name, fn_doc, mod_doc)

        return ResourceContent(
            uri=uri,
            mime_type="text/markdown",
            text=card_md,
        )

    def _read_render_job(self, uri: str, job_id: str) -> ResourceContent:
        """Generate studio://render/{job_id} JSON content."""
        from studiobridge.mcp.tools.render import _lookup_job

        data = _lookup_job(job_id)
        if data is None:
            raise ValueError(f"Render job '{job_id}' not found.")

        payload = {
            "uri": uri,
            "job_id": data.get("job_id", job_id),
            "state": data.get("state", "unknown"),
            "source": data.get("source", ""),
            "formats": data.get("formats", ["wav"]),
            "output_files": data.get("output_files", []),
            "sidecar_path": data.get("sidecar_path"),
            "metrics": data.get("metrics", {}),
            "error": data.get("error"),
            "created_at": data.get("created_at"),
            "completed_at": data.get("completed_at"),
        }
        return ResourceContent(
            uri=uri,
            mime_type="application/json",
            text=json.dumps(payload, indent=2),
        )


def get_default_resources(client: Any = None, server: Any = None) -> list[ResourceDefinition]:
    """Return default catalog of static resources."""
    return ResourceProvider(client=client, server=server).get_resources()


def get_default_resource_templates() -> list[ResourceTemplate]:
    """Return default catalog of parameterized resource templates."""
    return ResourceProvider().get_resource_templates()


def read_resource(uri: str, client: Any = None, server: Any = None) -> ResourceContent:
    """Read resource content by URI using ResourceProvider."""
    return ResourceProvider(client=client, server=server).read_resource(uri)


__all__ = [
    "ResourceContent",
    "ResourceDefinition",
    "ResourceProvider",
    "ResourceTemplate",
    "get_default_resource_templates",
    "get_default_resources",
    "read_resource",
]
