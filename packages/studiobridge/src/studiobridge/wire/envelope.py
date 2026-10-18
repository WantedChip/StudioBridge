"""Structured JSON envelope definitions, serialization, and deserialization.

Provides strongly-typed request, response, event, and control envelope models
with compact, deterministic 7-bit clean ASCII JSON serialization per
spec 03_l0a_wire_protocol.md §5.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from studiobridge.core.errors import ProtocolError
from studiobridge.wire.frame import FrameKind

# Maximum allowed length for idempotency key per [WIRE-20]
MAX_IDEM_LENGTH: int = 24

# Allowed control commands per [WIRE §5.4]
VALID_CONTROL_COMMANDS: frozenset[str] = frozenset({"ping", "pong", "ack", "nack", "busy", "panic"})


def _ensure_ascii_json(data: dict[str, Any]) -> bytes:
    """Serialize dictionary to deterministic, compact 7-bit clean ASCII bytes."""
    encoded_str = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    encoded_bytes = encoded_str.encode("ascii")
    if not all(b < 128 for b in encoded_bytes):
        raise ProtocolError(
            "Envelope serialization produced non-7-bit ASCII bytes",
            code="E_PROTO",
        )
    return encoded_bytes


@dataclass(slots=True)
class RequestOpts:
    """Execution options and guards for a request envelope."""

    verify: str | None = None  # "none" | "readback" | "settled"
    budget_ms: int | None = None
    budget_calls: int | None = None
    expect: dict[str, Any] | None = None  # Precondition guard per V1-A2
    fp: str | None = None  # Session fingerprint per V1-A1

    def to_dict(self) -> dict[str, Any]:
        """Convert options to a minimal dictionary omitting None values."""
        d: dict[str, Any] = {}
        if self.verify is not None:
            d["verify"] = self.verify
        if self.budget_ms is not None:
            d["budget_ms"] = self.budget_ms
        if self.budget_calls is not None:
            d["budget_calls"] = self.budget_calls
        if self.expect is not None:
            d["expect"] = self.expect
        if self.fp is not None:
            d["fp"] = self.fp
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RequestOpts:
        """Create RequestOpts from a dictionary."""
        if not data:
            return cls()
        return cls(
            verify=data.get("verify"),
            budget_ms=data.get("budget_ms"),
            budget_calls=data.get("budget_calls"),
            expect=data.get("expect"),
            fp=data.get("fp"),
        )


@dataclass(slots=True)
class RequestEnvelope:
    """Strongly-typed request envelope (KIND=REQ)."""

    op: str
    idem: str | None = None
    auth: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    opts: RequestOpts = field(default_factory=RequestOpts)

    def __post_init__(self) -> None:
        if not self.op:
            raise ProtocolError("Request envelope missing required 'op' field", code="E_PROTO")
        if self.idem is not None and len(self.idem) > MAX_IDEM_LENGTH:
            raise ProtocolError(
                f"Idempotency key '{self.idem}' exceeds maximum length of {MAX_IDEM_LENGTH} chars",
                code="E_ARGS",
                details={"idem": self.idem, "max_length": MAX_IDEM_LENGTH},
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert request to dictionary matching wire format §5.1."""
        d: dict[str, Any] = {"op": self.op}
        if self.idem is not None:
            d["idem"] = self.idem
        if self.auth is not None:
            d["auth"] = self.auth
        if self.args:
            d["args"] = self.args
        opts_dict = self.opts.to_dict()
        if opts_dict:
            d["opts"] = opts_dict
        return d

    def to_json(self) -> bytes:
        """Serialize request envelope to compact, 7-bit clean ASCII JSON bytes."""
        return _ensure_ascii_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RequestEnvelope:
        """Construct RequestEnvelope from raw dictionary."""
        if "op" not in data:
            raise ProtocolError("Missing 'op' key in request payload", code="E_PROTO")
        raw_opts = data.get("opts")
        opts = RequestOpts.from_dict(raw_opts if isinstance(raw_opts, dict) else None)
        return cls(
            op=str(data["op"]),
            idem=data.get("idem"),
            auth=data.get("auth"),
            args=dict(data.get("args") or {}),
            opts=opts,
        )

    @classmethod
    def from_json(cls, raw: bytes | str) -> RequestEnvelope:
        """Deserialize RequestEnvelope from JSON bytes or string."""
        try:
            data = json.loads(raw)
        except Exception as exc:
            raise ProtocolError(f"Malformed JSON request: {exc}", code="E_PROTO") from exc
        if not isinstance(data, dict):
            raise ProtocolError("Request payload must be a JSON object", code="E_PROTO")
        return cls.from_dict(data)


@dataclass(slots=True)
class ResponseError:
    """Structured error descriptor within a ResponseEnvelope."""

    c: str  # Error code, e.g. "E_ARGS"
    m: str  # Short human-readable message
    d: dict[str, Any] = field(default_factory=dict)  # Contextual details
    retry: bool = False  # Retryable flag

    def to_dict(self) -> dict[str, Any]:
        """Convert error structure to dictionary."""
        d: dict[str, Any] = {"c": self.c, "m": self.m}
        if self.d:
            d["d"] = self.d
        if self.retry:
            d["retry"] = self.retry
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResponseError:
        """Construct ResponseError from dictionary."""
        return cls(
            c=str(data.get("c", data.get("code", "E_FL"))),
            m=str(data.get("m", data.get("err", data.get("message", "Error")))),
            d=dict(data.get("d", data.get("details", {}))),
            retry=bool(data.get("retry", False)),
        )


@dataclass(slots=True)
class ResponseEnvelope:
    """Strongly-typed response envelope (KIND=RES)."""

    ok: bool
    r: Any = None
    e: ResponseError | None = None
    rb: Any = None
    m: dict[str, Any] | None = None

    @property
    def code(self) -> str | None:
        """Convenience accessor for error code."""
        return self.e.c if self.e else None

    @property
    def err(self) -> str | None:
        """Convenience accessor for error message."""
        return self.e.m if self.e else None

    @property
    def details(self) -> dict[str, Any]:
        """Convenience accessor for error details dictionary."""
        return self.e.d if self.e else {}

    @property
    def retryable(self) -> bool:
        """Convenience accessor for retryable flag."""
        return self.e.retry if self.e else False

    @classmethod
    def success(
        cls,
        r: Any = None,
        rb: Any = None,
        m: dict[str, Any] | None = None,
    ) -> ResponseEnvelope:
        """Create a successful ResponseEnvelope."""
        return cls(ok=True, r=r, rb=rb, m=m)

    @classmethod
    def failure(
        cls,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        retry: bool = False,
        m: dict[str, Any] | None = None,
    ) -> ResponseEnvelope:
        """Create a failed ResponseEnvelope."""
        return cls(
            ok=False,
            e=ResponseError(c=code, m=message, d=details or {}, retry=retry),
            m=m,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert response to dictionary matching wire format §5.2."""
        d: dict[str, Any] = {"ok": self.ok}
        if self.ok:
            if self.r is not None:
                d["r"] = self.r
            if self.rb is not None:
                d["rb"] = self.rb
        else:
            if self.e is not None:
                d["e"] = self.e.to_dict()
        if self.m is not None:
            d["m"] = self.m
        return d

    def to_json(self) -> bytes:
        """Serialize response envelope to compact, 7-bit clean ASCII JSON bytes."""
        return _ensure_ascii_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResponseEnvelope:
        """Construct ResponseEnvelope from raw dictionary."""
        if "ok" not in data:
            raise ProtocolError("Missing 'ok' field in response envelope", code="E_PROTO")
        ok = bool(data["ok"])
        r = data.get("r")
        rb = data.get("rb")
        m = data.get("m") if isinstance(data.get("m"), dict) else None

        err_obj: ResponseError | None = None
        if "e" in data and isinstance(data["e"], dict):
            err_obj = ResponseError.from_dict(data["e"])
        elif not ok and ("code" in data or "err" in data):
            err_obj = ResponseError.from_dict(data)

        return cls(ok=ok, r=r, e=err_obj, rb=rb, m=m)

    @classmethod
    def from_json(cls, raw: bytes | str) -> ResponseEnvelope:
        """Deserialize ResponseEnvelope from JSON bytes or string."""
        try:
            data = json.loads(raw)
        except Exception as exc:
            raise ProtocolError(f"Malformed JSON response: {exc}", code="E_PROTO") from exc
        if not isinstance(data, dict):
            raise ProtocolError("Response payload must be a JSON object", code="E_PROTO")
        return cls.from_dict(data)


@dataclass(slots=True)
class EventEnvelope:
    """Strongly-typed best-effort event envelope (KIND=EVT)."""

    ev: str
    seq: int
    d: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary matching wire format §5.3."""
        return {"ev": self.ev, "seq": self.seq, "d": self.d}

    def to_json(self) -> bytes:
        """Serialize event envelope to compact, 7-bit clean ASCII JSON bytes."""
        return _ensure_ascii_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventEnvelope:
        """Construct EventEnvelope from raw dictionary."""
        if "ev" not in data or "seq" not in data:
            raise ProtocolError("Event envelope requires 'ev' and 'seq' fields", code="E_PROTO")
        return cls(
            ev=str(data["ev"]),
            seq=int(data["seq"]),
            d=dict(data.get("d") or {}),
        )

    @classmethod
    def from_json(cls, raw: bytes | str) -> EventEnvelope:
        """Deserialize EventEnvelope from JSON bytes or string."""
        try:
            data = json.loads(raw)
        except Exception as exc:
            raise ProtocolError(f"Malformed JSON event: {exc}", code="E_PROTO") from exc
        if not isinstance(data, dict):
            raise ProtocolError("Event payload must be a JSON object", code="E_PROTO")
        return cls.from_dict(data)


@dataclass(slots=True)
class ControlEnvelope:
    """Strongly-typed control message envelope (KIND=CTL)."""

    c: str  # "ping", "pong", "ack", "nack", "busy", "panic"
    mid: int | None = None
    missing: list[int] | None = None
    retry_ms: int | None = None

    def __post_init__(self) -> None:
        if self.c not in VALID_CONTROL_COMMANDS:
            cmds = sorted(VALID_CONTROL_COMMANDS)
            raise ProtocolError(
                f"Invalid control command '{self.c}', expected one of {cmds}",
                code="E_PROTO",
            )

    @classmethod
    def ping(cls, mid: int | None = None) -> ControlEnvelope:
        """Create a CTL ping envelope."""
        return cls(c="ping", mid=mid)

    @classmethod
    def pong(cls, mid: int | None = None) -> ControlEnvelope:
        """Create a CTL pong envelope."""
        return cls(c="pong", mid=mid)

    @classmethod
    def ack(cls, mid: int) -> ControlEnvelope:
        """Create a CTL ack envelope."""
        return cls(c="ack", mid=mid)

    @classmethod
    def nack(cls, mid: int, missing: list[int]) -> ControlEnvelope:
        """Create a CTL nack envelope requesting retransmission of missing chunks."""
        return cls(c="nack", mid=mid, missing=missing)

    @classmethod
    def busy(cls, retry_ms: int = 50) -> ControlEnvelope:
        """Create a CTL busy backpressure envelope."""
        return cls(c="busy", retry_ms=retry_ms)

    @classmethod
    def panic(cls) -> ControlEnvelope:
        """Create a CTL panic envelope."""
        return cls(c="panic")

    def to_dict(self) -> dict[str, Any]:
        """Convert control envelope to dictionary matching wire format §5.4."""
        d: dict[str, Any] = {"c": self.c}
        if self.mid is not None:
            d["mid"] = self.mid
        if self.missing is not None:
            d["missing"] = self.missing
        if self.retry_ms is not None:
            d["retry_ms"] = self.retry_ms
        return d

    def to_json(self) -> bytes:
        """Serialize control envelope to compact, 7-bit clean ASCII JSON bytes."""
        return _ensure_ascii_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControlEnvelope:
        """Construct ControlEnvelope from raw dictionary."""
        if "c" not in data:
            raise ProtocolError("Missing 'c' field in control envelope", code="E_PROTO")
        return cls(
            c=str(data["c"]),
            mid=data.get("mid"),
            missing=data.get("missing"),
            retry_ms=data.get("retry_ms"),
        )

    @classmethod
    def from_json(cls, raw: bytes | str) -> ControlEnvelope:
        """Deserialize ControlEnvelope from JSON bytes or string."""
        try:
            data = json.loads(raw)
        except Exception as exc:
            raise ProtocolError(f"Malformed JSON control message: {exc}", code="E_PROTO") from exc
        if not isinstance(data, dict):
            raise ProtocolError("Control payload must be a JSON object", code="E_PROTO")
        return cls.from_dict(data)


Envelope = RequestEnvelope | ResponseEnvelope | EventEnvelope | ControlEnvelope


def serialize_envelope(envelope: Envelope) -> bytes:
    """Serialize any strongly-typed envelope to 7-bit clean ASCII JSON bytes."""
    return envelope.to_json()


def deserialize_envelope(
    raw: bytes | str,
    kind: int | FrameKind | None = None,
) -> Envelope:
    """Deserialize raw JSON bytes into an appropriate Envelope instance.

    If kind is explicitly provided, parses according to that FrameKind.
    Otherwise, inspects fields ('op', 'ok', 'ev', 'c') to determine type.
    """
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise ProtocolError(f"Malformed envelope JSON: {exc}", code="E_PROTO") from exc

    if not isinstance(data, dict):
        raise ProtocolError("Envelope JSON must be an object", code="E_PROTO")

    if kind is not None:
        k = int(kind)
        if k == FrameKind.REQ or k == 1:
            return RequestEnvelope.from_dict(data)
        if k == FrameKind.RES or k == 2:
            return ResponseEnvelope.from_dict(data)
        if k == FrameKind.EVT or k == 3:
            return EventEnvelope.from_dict(data)
        if k == FrameKind.CTL or k == 4:
            return ControlEnvelope.from_dict(data)
        raise ProtocolError(f"Unknown FrameKind value: {kind}", code="E_PROTO")

    # Dynamic detection based on signature keys
    if "op" in data:
        return RequestEnvelope.from_dict(data)
    if "ok" in data:
        return ResponseEnvelope.from_dict(data)
    if "ev" in data:
        return EventEnvelope.from_dict(data)
    if "c" in data:
        return ControlEnvelope.from_dict(data)

    raise ProtocolError(
        f"Unrecognized envelope payload structure: keys={sorted(data.keys())}",
        code="E_PROTO",
    )
