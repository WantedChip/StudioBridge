"""MIDI port discovery and name resolution logic [PORT-16, PORT-17]."""

from __future__ import annotations

from typing import Literal

from studiobridge.core.errors import PortError
from studiobridge.ports.base import MidiPort, MidiPortInfo


class PortResolver:
    """Resolves MIDI device names to enumerated MidiPortInfo instances.

    Resolves devices by name at open time rather than unstable device indices [PORT-17].
    Matching order follows exact -> case-insensitive -> prefix [PORT-16].
    Ambiguous matches raise a PortError with a candidate listing.
    """

    def __init__(self, port_backend: MidiPort) -> None:
        self._backend = port_backend

    def find_candidates(
        self,
        query: str,
        direction: Literal["in", "out"] | None = None,
        *,
        available_ports: list[MidiPortInfo] | None = None,
    ) -> list[MidiPortInfo]:
        """Find candidate ports matching query using exact -> case-insensitive -> prefix order."""
        ports = available_ports if available_ports is not None else self._backend.list_ports()
        if direction is not None:
            ports = [p for p in ports if p.direction == direction]

        # 1. Exact match (case-sensitive)
        exact = [p for p in ports if p.name == query]
        if exact:
            return exact

        # 2. Case-insensitive exact match
        q_lower = query.strip().lower()
        case_match = [p for p in ports if p.name.strip().lower() == q_lower]
        if case_match:
            return case_match

        # 3. Prefix match (case-insensitive)
        prefix_match = [p for p in ports if p.name.strip().lower().startswith(q_lower)]
        return prefix_match

    def resolve(
        self,
        query: str,
        direction: Literal["in", "out"] | None = None,
        *,
        available_ports: list[MidiPortInfo] | None = None,
    ) -> MidiPortInfo:
        """Resolve a single port matching query.

        Raises:
            PortError: If no port matches or if multiple candidates match (ambiguity).
        """
        candidates = self.find_candidates(
            query, direction=direction, available_ports=available_ports
        )

        if not candidates:
            all_ports = (
                available_ports if available_ports is not None else self._backend.list_ports()
            )
            if direction is not None:
                all_ports = [p for p in all_ports if p.direction == direction]
            available_names = sorted({p.name for p in all_ports})

            dir_str = f" {direction}" if direction else ""
            raise PortError(
                f"MIDI{dir_str} port matching {query!r} was not found.",
                code="E_ENV_PORT",
                details={
                    "query": query,
                    "direction": direction,
                    "available_ports": available_names,
                },
                remedy=(
                    f"Available{dir_str} ports: {available_names}. "
                    "Run 'sbridge ports list' or verify loopback port setup."
                ),
            )

        if len(candidates) > 1:
            candidate_names = [f"{c.name} (index {c.index}, {c.direction})" for c in candidates]
            dir_str = f" {direction}" if direction else ""
            raise PortError(
                f"Ambiguous MIDI{dir_str} port match for {query!r}. "
                f"Found multiple candidates: {candidate_names}.",
                code="E_ENV_PORT",
                details={
                    "query": query,
                    "direction": direction,
                    "candidates": [c.name for c in candidates],
                },
                remedy=(
                    f"Specify the exact full name of the desired MIDI port among: "
                    f"{[c.name for c in candidates]}."
                ),
            )

        return candidates[0]

    def resolve_in(
        self,
        query: str,
        *,
        available_ports: list[MidiPortInfo] | None = None,
    ) -> MidiPortInfo:
        """Resolve an input MIDI port by name."""
        return self.resolve(query, direction="in", available_ports=available_ports)

    def resolve_out(
        self,
        query: str,
        *,
        available_ports: list[MidiPortInfo] | None = None,
    ) -> MidiPortInfo:
        """Resolve an output MIDI port by name."""
        return self.resolve(query, direction="out", available_ports=available_ports)

    def resolve_pair(
        self,
        root_name: str = "StudioBridge",
        *,
        available_ports: list[MidiPortInfo] | None = None,
    ) -> tuple[MidiPortInfo, MidiPortInfo]:
        """Resolve a paired virtual endpoint for bidirectional communication.

        Looks for paired naming conventions:
        - WMS Loopback Pair: Side A and Side B (e.g. "{root} (A)" / "{root} (B)")
        - loopMIDI Pair: Req and Res (e.g. "{root} Req" / "{root} Res")
        - In-box default: "Default App Loopback (A)" / "Default App Loopback (B)"
        - Single duplex endpoint: "{root}" (identical input and output name)

        Returns:
            Tuple of (in_port, out_port).

        Raises:
            PortError: If no suitable pair can be resolved.
        """
        ports = available_ports if available_ports is not None else self._backend.list_ports()
        in_ports = [p for p in ports if p.direction == "in"]
        out_ports = [p for p in ports if p.direction == "out"]

        candidate_pairs: list[tuple[str, str]] = [
            (f"{root_name} (A)", f"{root_name} (B)"),
            (f"{root_name} A", f"{root_name} B"),
            (f"{root_name} Req", f"{root_name} Res"),
            (f"{root_name} (B)", f"{root_name} (A)"),
            (f"{root_name} B", f"{root_name} A"),
            (f"{root_name} Res", f"{root_name} Req"),
        ]

        if root_name.lower() in ("auto", "default", "loopback"):
            candidate_pairs.append(("Default App Loopback (A)", "Default App Loopback (B)"))
            candidate_pairs.append(("StudioBridge Loopback (A)", "StudioBridge Loopback (B)"))

        # Try designated pair patterns
        for in_query, out_query in candidate_pairs:
            try:
                p_in = self.resolve(in_query, direction="in", available_ports=in_ports)
                p_out = self.resolve(out_query, direction="out", available_ports=out_ports)
                return p_in, p_out
            except PortError:
                continue

        # Try single shared loopback endpoint (e.g. basic loopback)
        try:
            p_in = self.resolve(root_name, direction="in", available_ports=in_ports)
            p_out = self.resolve(root_name, direction="out", available_ports=out_ports)
            return p_in, p_out
        except PortError:
            pass

        # If still not found, search for any pair sharing root prefix
        prefix_in = [p for p in in_ports if root_name.lower() in p.name.lower()]
        prefix_out = [p for p in out_ports if root_name.lower() in p.name.lower()]
        if len(prefix_in) == 1 and len(prefix_out) == 1:
            return prefix_in[0], prefix_out[0]

        all_names = sorted({p.name for p in ports})
        raise PortError(
            f"Could not resolve a matching MIDI loopback port pair for {root_name!r}.",
            code="E_ENV_PORT",
            details={"root_name": root_name, "available_ports": all_names},
            remedy=(
                f"Create a virtual MIDI loopback pair named '{root_name} (A)' and "
                f"'{root_name} (B)' using Windows MIDI Services or loopMIDI. "
                f"Current ports: {all_names}."
            ),
        )
