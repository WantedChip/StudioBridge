"""StudioBridge error taxonomy and structured exception hierarchy.

Provides typed exceptions carrying machine-readable codes, remedies,
retryable flags, and contextual details per spec 12_crosscutting.md §7.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    """Metadata specification for a standardized error code."""

    code: str
    default_message: str
    retryable: bool
    remedy: str
    docs_anchor: str


# Canonical error registry per 12_crosscutting.md §7
ERROR_REGISTRY: dict[str, ErrorInfo] = {
    # E_PROTO*: Wire protocol errors
    "E_PROTO": ErrorInfo(
        code="E_PROTO",
        default_message="Wire protocol framing violation or corrupted packet.",
        retryable=False,
        remedy="Inspect packet structure and verify framing against wire specification.",
        docs_anchor="error-e-proto",
    ),
    "E_AUTH": ErrorInfo(
        code="E_AUTH",
        default_message="HMAC signature mismatch or invalid authentication secret.",
        retryable=False,
        remedy=(
            "Verify secret matches between device script and host client, "
            "or run 'sbridge setup --repair'."
        ),
        docs_anchor="error-e-auth",
    ),
    "E_VERSION": ErrorInfo(
        code="E_VERSION",
        default_message="Protocol version negotiation failure.",
        retryable=False,
        remedy="Upgrade studiobridge host package or update FL Studio device script.",
        docs_anchor="error-e-version",
    ),
    "E_STALE": ErrorInfo(
        code="E_STALE",
        default_message="Sequence number or session ID is stale / superseded.",
        retryable=False,
        remedy="Refresh session state and re-acquire current session ID.",
        docs_anchor="error-e-stale",
    ),
    "E_TOOBIG": ErrorInfo(
        code="E_TOOBIG",
        default_message="Payload exceeds maximum chunk size or buffer limit.",
        retryable=False,
        remedy="Reduce chunk size or payload size before transmission.",
        docs_anchor="error-e-toobig",
    ),
    # E_DEV*: FL Studio and device controller errors
    "E_BUSY": ErrorInfo(
        code="E_BUSY",
        default_message="Device script is busy executing previous command.",
        retryable=True,
        remedy="Wait for idle tick or increase command timeout.",
        docs_anchor="error-e-busy",
    ),
    "E_TIMEOUT": ErrorInfo(
        code="E_TIMEOUT",
        default_message="Command timed out waiting for response from FL Studio.",
        retryable=True,
        remedy=(
            "Verify FL Studio is running, not frozen, and script output window has no modal errors."
        ),
        docs_anchor="error-e-timeout",
    ),
    "E_UNCERTAIN": ErrorInfo(
        code="E_UNCERTAIN",
        default_message="Execution state of command is uncertain.",
        retryable=False,
        remedy="Query current state with getter function to determine if operation took effect.",
        docs_anchor="error-e-uncertain",
    ),
    "E_FL": ErrorInfo(
        code="E_FL",
        default_message="Unhandled internal exception occurred within FL Studio API.",
        retryable=False,
        remedy="Check FL Studio Script Output dialog for Python traceback and inspect parameters.",
        docs_anchor="error-e-fl",
    ),
    "E_SANDBOX": ErrorInfo(
        code="E_SANDBOX",
        default_message="Restricted operation blocked by FL Studio Python sandbox.",
        retryable=False,
        remedy="Ensure operation does not invoke forbidden ctypes, sockets, or subprocess calls.",
        docs_anchor="error-e-sandbox",
    ),
    "E_CANCELLED": ErrorInfo(
        code="E_CANCELLED",
        default_message="Operation was cancelled before completion.",
        retryable=False,
        remedy="Check panic status and re-issue operation if needed.",
        docs_anchor="error-e-cancelled",
    ),
    # E_CAP*: Capability and feature availability
    "E_UNAVAILABLE": ErrorInfo(
        code="E_UNAVAILABLE",
        default_message="Requested capability is unavailable in current environment.",
        retryable=False,
        remedy="Check required prerequisites or use one of the documented alternative paths.",
        docs_anchor="error-e-unavailable",
    ),
    "E_DEGRADED": ErrorInfo(
        code="E_DEGRADED",
        default_message="Capability is running in degraded mode with reduced functionality.",
        retryable=False,
        remedy="Install recommended dependencies or enable required hardware ports.",
        docs_anchor="error-e-degraded",
    ),
    "E_EXPERIMENTAL": ErrorInfo(
        code="E_EXPERIMENTAL",
        default_message="Feature is experimental and not enabled in safe mode.",
        retryable=False,
        remedy="Enable experimental flags in configuration if intended.",
        docs_anchor="error-e-experimental",
    ),
    # E_ARG*: Argument and reference errors
    "E_ARGS": ErrorInfo(
        code="E_ARGS",
        default_message="Invalid argument types or count supplied to function.",
        retryable=False,
        remedy="Check function signature against API manifest and provide valid argument types.",
        docs_anchor="error-e-args",
    ),
    "E_BADREF": ErrorInfo(
        code="E_BADREF",
        default_message="Reference identifier not found or invalid index.",
        retryable=False,
        remedy="Query collection list to verify target ID exists.",
        docs_anchor="error-e-badref",
    ),
    "E_AMBIGUOUS": ErrorInfo(
        code="E_AMBIGUOUS",
        default_message="Name or selector matched multiple targets.",
        retryable=False,
        remedy="Disambiguate query using exact target index or unique identifier.",
        docs_anchor="error-e-ambiguous",
    ),
    "E_RANGE": ErrorInfo(
        code="E_RANGE",
        default_message="Parameter value is outside allowed numerical or enum range.",
        retryable=False,
        remedy="Constrain parameter value to valid numerical or enum bounds.",
        docs_anchor="error-e-range",
    ),
    "E_PRECONDITION": ErrorInfo(
        code="E_PRECONDITION",
        default_message="Required state prerequisite not satisfied.",
        retryable=False,
        remedy="Ensure required window is focused, transport is stopped, or channel exists.",
        docs_anchor="error-e-precondition",
    ),
    # E_VER*: Verification errors
    "E_UNVERIFIED": ErrorInfo(
        code="E_UNVERIFIED",
        default_message="Post-write read-back verification failed to match target value.",
        retryable=True,
        remedy="Verify target parameter is not automated, modulated by LFO, or locked by plugin.",
        docs_anchor="error-e-unverified",
    ),
    # E_SAFE*: Safety and permission errors
    "E_READONLY": ErrorInfo(
        code="E_READONLY",
        default_message="Session is in read-only mode and blocked a mutating write.",
        retryable=False,
        remedy="Request write lease and elevate session mode to 'write' or 'destructive'.",
        docs_anchor="error-e-readonly",
    ),
    "E_PROTECTED": ErrorInfo(
        code="E_PROTECTED",
        default_message="Target is marked protected in safety configuration.",
        retryable=False,
        remedy="Unprotect target in .sbridge.toml or pass explicit override confirmation.",
        docs_anchor="error-e-protected",
    ),
    "E_POLICY": ErrorInfo(
        code="E_POLICY",
        default_message="Action violates active safety policy.",
        retryable=False,
        remedy="Review safety policy configuration or execute in non-interactive permissive mode.",
        docs_anchor="error-e-policy",
    ),
    "E_CONFIRM": ErrorInfo(
        code="E_CONFIRM",
        default_message="User confirmation required for high-risk action.",
        retryable=False,
        remedy="Present confirmation prompt to user and retry with confirmation flag.",
        docs_anchor="error-e-confirm",
    ),
    # E_CONN*: Connection and broker errors
    "E_NOBROKER": ErrorInfo(
        code="E_NOBROKER",
        default_message="StudioBridge broker daemon is not running or unreachable.",
        retryable=True,
        remedy="Start broker with 'sbridge broker start' or verify broker port.",
        docs_anchor="error-e-nobroker",
    ),
    "E_NODEVICE": ErrorInfo(
        code="E_NODEVICE",
        default_message="Device script is not connected or FL Studio is closed.",
        retryable=True,
        remedy=(
            "Launch FL Studio and ensure StudioBridge controller script is assigned in "
            "MIDI settings."
        ),
        docs_anchor="error-e-nodevice",
    ),
    "E_DISCONNECTED": ErrorInfo(
        code="E_DISCONNECTED",
        default_message="MIDI port or connection was closed unexpectedly.",
        retryable=True,
        remedy="Reconnect MIDI port or restart StudioBridge broker.",
        docs_anchor="error-e-disconnected",
    ),
    "E_LEASE": ErrorInfo(
        code="E_LEASE",
        default_message="Failed to acquire writer lease; another client holds it.",
        retryable=True,
        remedy="Wait for current lease holder to finish or check active leases.",
        docs_anchor="error-e-lease",
    ),
    # E_FLP*: Offline FLP engine errors
    "E_FLP_PARSE": ErrorInfo(
        code="E_FLP_PARSE",
        default_message="Failed to parse binary FLP file format.",
        retryable=False,
        remedy="Verify file is a valid .flp project created by FL Studio and not corrupted.",
        docs_anchor="error-e-flp-parse",
    ),
    "E_FLP_VERSION": ErrorInfo(
        code="E_FLP_VERSION",
        default_message="Unsupported FLP project version.",
        retryable=False,
        remedy="Use compatible FL Studio version or update StudioBridge FLP profile.",
        docs_anchor="error-e-flp-version",
    ),
    "E_FLP_INVARIANT": ErrorInfo(
        code="E_FLP_INVARIANT",
        default_message="Structural invariant violated during FLP manipulation.",
        retryable=False,
        remedy="Validate project structure and ensure event stream maintains required tag order.",
        docs_anchor="error-e-flp-invariant",
    ),
    "E_FLP_WRITE_RISK": ErrorInfo(
        code="E_FLP_WRITE_RISK",
        default_message="Offline write carries high risk of file corruption.",
        retryable=False,
        remedy="Write to a new backup file instead of in-place overwrite.",
        docs_anchor="error-e-flp-write-risk",
    ),
    # E_RND*: Render orchestration errors
    "E_RND_FLRUNNING": ErrorInfo(
        code="E_RND_FLRUNNING",
        default_message=(
            "Cannot perform render because an interactive FL Studio instance is running."
        ),
        retryable=False,
        remedy="Save project and close interactive FL Studio instance before batch render.",
        docs_anchor="error-e-rnd-flrunning",
    ),
    "E_RND_DIALOG": ErrorInfo(
        code="E_RND_DIALOG",
        default_message="Render process blocked by unexpected modal dialog.",
        retryable=False,
        remedy="Dismiss dialog in FL Studio or configure silent render mode.",
        docs_anchor="error-e-rnd-dialog",
    ),
    "E_RND_TIMEOUT": ErrorInfo(
        code="E_RND_TIMEOUT",
        default_message="Render job exceeded timeout limit.",
        retryable=False,
        remedy="Increase render timeout limit or render fewer bars.",
        docs_anchor="error-e-rnd-timeout",
    ),
    "E_RND_INVALID": ErrorInfo(
        code="E_RND_INVALID",
        default_message="Render output is invalid, empty, or silent.",
        retryable=False,
        remedy="Check audio routing, master track volume, and render export settings.",
        docs_anchor="error-e-rnd-invalid",
    ),
    # E_ENV*: Environment errors
    "E_ENV_PORT": ErrorInfo(
        code="E_ENV_PORT",
        default_message="Required MIDI port not found or already opened exclusively.",
        retryable=False,
        remedy=(
            "Create virtual MIDI loopback port with 'sbridge setup' or close "
            "conflicting application."
        ),
        docs_anchor="error-e-env-port",
    ),
    "E_ENV_FL": ErrorInfo(
        code="E_ENV_FL",
        default_message="FL Studio installation or user data directory not found.",
        retryable=False,
        remedy="Run 'sbridge setup' to configure FL Studio path or set SBRIDGE_FL_USER_DIR.",
        docs_anchor="error-e-env-fl",
    ),
    "E_ENV_PY": ErrorInfo(
        code="E_ENV_PY",
        default_message="Python runtime version or environment incompatible.",
        retryable=False,
        remedy="Install Python >= 3.10 via 'uv python install 3.11'.",
        docs_anchor="error-e-env-py",
    ),
    "E_ENV_OS": ErrorInfo(
        code="E_ENV_OS",
        default_message="Operating system or platform feature missing.",
        retryable=False,
        remedy="Update to Windows 11 24H2+ for Windows MIDI Services or configure loopMIDI.",
        docs_anchor="error-e-env-os",
    ),
}


class StudioBridgeError(Exception):
    """Root exception class for all StudioBridge errors.

    Carries structured metadata: code, message, details, retryable flag,
    and an actionable remedy string for humans and AI agents.
    """

    default_code: str = "E_FL"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
        remedy: str | None = None,
        docs_anchor: str | None = None,
    ) -> None:
        self.code: str = code or getattr(self, "default_code", "E_FL")
        meta = ERROR_REGISTRY.get(self.code)

        self.message: str = message or (
            meta.default_message if meta else "An unexpected StudioBridge error occurred."
        )
        self.retryable: bool = (
            retryable if retryable is not None else (meta.retryable if meta else False)
        )
        self.remedy: str = (
            remedy
            or (meta.remedy if meta else None)
            or "Consult the StudioBridge documentation or run 'sbridge doctor'."
        )
        self.docs_anchor: str | None = docs_anchor or (meta.docs_anchor if meta else None)
        self.details: dict[str, Any] = details if details is not None else {}

        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize error attributes into a dictionary for status reporting or IPC."""
        data: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
            "remedy": self.remedy,
        }
        if self.docs_anchor:
            data["docs_anchor"] = self.docs_anchor
        return data

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} (Remedy: {self.remedy})"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r}, "
            f"retryable={self.retryable!r}, remedy={self.remedy!r})"
        )


class ProtocolError(StudioBridgeError):
    """Raised on wire protocol framing, HMAC authentication, or version negotiation failures."""

    default_code: str = "E_PROTO"


class PayloadTooLargeError(StudioBridgeError):
    """Raised when note payload or frame size exceeds allowed limit."""

    default_code: str = "E_TOOBIG"


PayloadTooLarge = PayloadTooLargeError


class PortError(StudioBridgeError):
    """Raised on MIDI port open, discovery, or OS-level port configuration failures."""

    default_code: str = "E_ENV_PORT"


class ConnectionError(StudioBridgeError, builtins.ConnectionError):
    """Base exception for StudioBridge connection and communication failures."""

    default_code: str = "E_NOBROKER"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
        remedy: str | None = None,
        docs_anchor: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details=details,
            retryable=retryable,
            remedy=remedy,
            docs_anchor=docs_anchor,
        )
        builtins.ConnectionError.__init__(self, self.message)


class NoBrokerError(ConnectionError):
    """Raised when the StudioBridge broker daemon is not running or unreachable."""

    default_code: str = "E_NOBROKER"


class NoDeviceError(ConnectionError):
    """Raised when FL Studio device script is not connected or FL Studio is closed."""

    default_code: str = "E_NODEVICE"


class VersionMismatchError(ConnectionError):
    """Raised when protocol or broker minor version mismatch occurs."""

    default_code: str = "E_VERSION"


class DisconnectedError(ConnectionError):
    """Raised when MIDI port or broker connection closes unexpectedly."""

    default_code: str = "E_DISCONNECTED"


class LeaseError(ConnectionError):
    """Raised when a writer lease cannot be acquired or was revoked."""

    default_code: str = "E_LEASE"


class BrokerError(ConnectionError):
    """Raised on broker daemon connection, lease acquisition, or IPC failures."""

    default_code: str = "E_NOBROKER"


# Aliases per spec 09_l1_sdk.md §10
NoBroker = NoBrokerError
NoDevice = NoDeviceError
VersionMismatch = VersionMismatchError
Disconnected = DisconnectedError
Lease = LeaseError


class DeviceError(StudioBridgeError):
    """Raised on FL Studio device controller timeouts, busy states, or script runtime errors."""

    default_code: str = "E_FL"


class FLCallFailedError(DeviceError):
    """Raised when an internal exception occurred inside FL Studio."""

    default_code: str = "E_FL"


class SandboxBlockedError(DeviceError):
    """Raised when an operation is blocked by the FL Studio Python sandbox."""

    default_code: str = "E_SANDBOX"


class BusyError(DeviceError):
    """Raised when the device controller is busy executing a previous operation."""

    default_code: str = "E_BUSY"


class TimeoutError(DeviceError):
    """Raised when command timed out waiting for response from FL Studio."""

    default_code: str = "E_TIMEOUT"


class UncertainError(DeviceError):
    """Raised when execution state of a command cannot be verified."""

    default_code: str = "E_UNCERTAIN"


class PreconditionError(StudioBridgeError):
    """Raised when an argument, target reference, or state precondition is violated."""

    default_code: str = "E_PRECONDITION"


class ArgumentError(StudioBridgeError):
    """Raised on argument type, value, or reference mismatch."""

    default_code: str = "E_ARGS"


class BadRefError(ArgumentError):
    """Raised when a target reference identifier or index was not found."""

    default_code: str = "E_BADREF"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str = "E_BADREF",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        remedy: str | None = None,
        docs_anchor: str | None = None,
        target: Any = None,
    ) -> None:
        det = dict(details) if details else {}
        self.target: Any = target or det.get("target")
        if self.target is not None and "target" not in det:
            det["target"] = self.target
        super().__init__(
            message=message,
            code=code,
            details=det,
            retryable=retryable,
            remedy=remedy,
            docs_anchor=docs_anchor,
        )

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.target is not None:
            data["target"] = self.target
        return data


class AmbiguousRefError(ArgumentError):
    """Raised when a name or query matches multiple target candidates."""

    default_code: str = "E_AMBIGUOUS"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str = "E_AMBIGUOUS",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        remedy: str | None = None,
        docs_anchor: str | None = None,
        candidates: list[Any] | None = None,
        query: str | None = None,
    ) -> None:
        det = dict(details) if details else {}
        self.candidates: list[Any] = (
            list(candidates) if candidates is not None else list(det.get("candidates", []))
        )
        self.query: str | None = query or det.get("query")
        if self.candidates and "candidates" not in det:
            det["candidates"] = self.candidates
        if self.query is not None and "query" not in det:
            det["query"] = self.query
        super().__init__(
            message=message,
            code=code,
            details=det,
            retryable=retryable,
            remedy=remedy,
            docs_anchor=docs_anchor,
        )

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["candidates"] = self.candidates
        if self.query is not None:
            data["query"] = self.query
        return data


class OutOfRangeError(ArgumentError):
    """Raised when a parameter value is outside allowed numerical or enum range."""

    default_code: str = "E_RANGE"


# Aliases per spec 09_l1_sdk.md §10
BadRef = BadRefError
AmbiguousRef = AmbiguousRefError
OutOfRange = OutOfRangeError


class CapabilityError(StudioBridgeError):
    """Base exception for capability and feature availability errors."""

    default_code: str = "E_UNAVAILABLE"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str = "E_UNAVAILABLE",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        remedy: str | None = None,
        docs_anchor: str | None = None,
        capability: str | None = None,
        alternatives: list[str] | None = None,
    ) -> None:
        det = dict(details) if details else {}
        self.capability: str | None = capability or det.get("capability")
        self.alternatives: list[str] = (
            list(alternatives) if alternatives else list(det.get("alternatives", []))
        )
        if self.capability and "capability" not in det:
            det["capability"] = self.capability
        if self.alternatives and "alternatives" not in det:
            det["alternatives"] = self.alternatives

        super().__init__(
            message=message,
            code=code,
            details=det,
            retryable=retryable,
            remedy=remedy,
            docs_anchor=docs_anchor,
        )

    @property
    def capability_id(self) -> str | None:
        """Alias for capability."""
        return self.capability

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["capability"] = self.capability
        data["alternatives"] = self.alternatives
        return data


class UnavailableError(CapabilityError):
    """Raised when a requested capability is unavailable in the current environment."""

    default_code: str = "E_UNAVAILABLE"


class DegradedError(CapabilityError):
    """Raised when a capability is running in degraded mode with reduced functionality."""

    default_code: str = "E_DEGRADED"


class ExperimentalDisabledError(UnavailableError):
    """Raised when an experimental feature is invoked while disabled."""

    default_code: str = "E_EXPERIMENTAL"


# Aliases per spec 09_l1_sdk.md §10
Unavailable = UnavailableError
Degraded = DegradedError
ExperimentalDisabled = ExperimentalDisabledError


class VerificationError(StudioBridgeError):
    """Raised when post-write read-back verification does not match target value."""

    default_code: str = "E_UNVERIFIED"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str = "E_UNVERIFIED",
        details: dict[str, Any] | None = None,
        retryable: bool = True,
        remedy: str | None = None,
        docs_anchor: str | None = None,
        target_value: Any = None,
        actual_value: Any = None,
    ) -> None:
        det = dict(details) if details else {}
        self.target_value: Any = (
            target_value if target_value is not None else det.get("target_value")
        )
        self.actual_value: Any = (
            actual_value if actual_value is not None else det.get("actual_value")
        )
        if self.target_value is not None and "target_value" not in det:
            det["target_value"] = self.target_value
        if self.actual_value is not None and "actual_value" not in det:
            det["actual_value"] = self.actual_value
        super().__init__(
            message=message,
            code=code,
            details=det,
            retryable=retryable,
            remedy=remedy,
            docs_anchor=docs_anchor,
        )

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.target_value is not None:
            data["target_value"] = self.target_value
        if self.actual_value is not None:
            data["actual_value"] = self.actual_value
        return data


class UnverifiedWriteError(VerificationError):
    """Raised when a write cannot be verified and strict write verification is enabled."""

    default_code: str = "E_UNVERIFIED"


UnverifiedWrite = UnverifiedWriteError


class SafetyError(StudioBridgeError):
    """Raised when an operation violates active safety policy or read-only mode."""

    default_code: str = "E_READONLY"


class ReadOnlyError(SafetyError):
    """Raised when a mutating operation is attempted in read-only mode."""

    default_code: str = "E_READONLY"


class ProtectedTargetError(SafetyError):
    """Raised when an operation targets a protected parameter without override."""

    default_code: str = "E_PROTECTED"


class PolicyDeniedError(SafetyError):
    """Raised when an action violates safety policy rules."""

    default_code: str = "E_POLICY"


class ConfirmationRequiredError(SafetyError):
    """Raised when user or explicit confirmation is required for a mutating action."""

    default_code: str = "E_CONFIRM"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str = "E_CONFIRM",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        remedy: str | None = None,
        docs_anchor: str | None = None,
        token: str | None = None,
        operation: str | None = None,
    ) -> None:
        det = dict(details) if details else {}
        self.token: str | None = token or det.get("token")
        self.operation: str | None = operation or det.get("operation")
        if self.token is not None and "token" not in det:
            det["token"] = self.token
        if self.operation is not None and "operation" not in det:
            det["operation"] = self.operation
        super().__init__(
            message=message,
            code=code,
            details=det,
            retryable=retryable,
            remedy=remedy,
            docs_anchor=docs_anchor,
        )

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.token is not None:
            data["token"] = self.token
        if self.operation is not None:
            data["operation"] = self.operation
        return data


# Aliases per spec 09_l1_sdk.md §10
ReadOnlyMode = ReadOnlyError
ProtectedTarget = ProtectedTargetError
PolicyDenied = PolicyDeniedError
ConfirmationRequired = ConfirmationRequiredError


class OfflineError(StudioBridgeError):
    """Base exception for offline FLP engine operations."""

    default_code: str = "E_FLP_PARSE"


class FlpParseError(OfflineError):
    """Raised when binary FLP parser fails."""

    default_code: str = "E_FLP_PARSE"


class FlpVersionUnsupportedError(OfflineError):
    """Raised when an unsupported FLP file version is encountered."""

    default_code: str = "E_FLP_VERSION"


class FlpInvariantViolationError(OfflineError):
    """Raised when an offline FLP structural invariant is violated."""

    default_code: str = "E_FLP_INVARIANT"


class RenderError(StudioBridgeError):
    """Base exception for render orchestration failures."""

    default_code: str = "E_RND_FLRUNNING"


class FlRunningError(RenderError):
    """Raised when an interactive FL Studio instance blocks offline rendering."""

    default_code: str = "E_RND_FLRUNNING"


class BlockingDialogError(RenderError):
    """Raised when an unexpected modal dialog blocks rendering."""

    default_code: str = "E_RND_DIALOG"


class RenderTimeoutError(RenderError):
    """Raised when a render job exceeds its timeout limit."""

    default_code: str = "E_RND_TIMEOUT"


class InvalidOutputError(RenderError):
    """Raised when render output is empty, silent, or invalid."""

    default_code: str = "E_RND_INVALID"
