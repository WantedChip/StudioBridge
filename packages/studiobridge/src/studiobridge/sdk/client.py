"""High-level client interfaces: Studio (synchronous) and AsyncStudio (asynchronous).

Implements top-level SDK entry points per spec 09_l1_sdk.md §1–§4:
- AsyncStudio: asynchronous context manager over anyio.
- Studio: synchronous context manager wrapping async core via
  anyio.from_thread.BlockingPortal [SDK-01].
- fl.status(), fl.raw.call(), fl.batch(), fl.trace(), fl.stats(), and fl.caps.
- connect() top-level module convenience function.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import anyio
import anyio.from_thread
from anyio.from_thread import BlockingPortal

from studiobridge.core.capabilities import CapabilityRegistry
from studiobridge.core.errors import DisconnectedError, UnavailableError
from studiobridge.device.assets._sb_api import ALLOW
from studiobridge.ports.base import MidiPort
from studiobridge.sdk.batch import AsyncBatchContext, SyncBatchContext
from studiobridge.sdk.capabilities import check_operation_capability
from studiobridge.sdk.session import Session, Status
from studiobridge.sdk.trace import AsyncTraceContext, SyncTraceContext

BUILTIN_ALLOWED_OPS = {
    "hello",
    "ping",
    "probe",
    "broker.ping",
    "broker.status",
    "session.info",
    "device.subscribe",
    "device.unsubscribe",
    "lease.acquire",
    "lease.renew",
    "lease.release",
}


class AsyncRawApi:
    """Asynchronous allowlisted raw API passthrough."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def call(self, op: str, *args: Any, **kwargs: Any) -> Any:
        """Call a raw FL Studio API operation with allowlist verification."""
        # 1. Allowlist preflight validation
        is_allowed = False
        arg_specs: list[dict[str, Any]] = []

        if op in BUILTIN_ALLOWED_OPS:
            is_allowed = True
        elif "." in op:
            mod_name, fn_name = op.split(".", 1)
            if mod_name in ALLOW and fn_name in ALLOW[mod_name]:
                is_allowed = True
                arg_specs = ALLOW[mod_name][fn_name].get("args", [])

        if not is_allowed:
            raise UnavailableError(
                f"Operation '{op}' is unsupported or not in API allowlist.",
                code="E_UNAVAILABLE",
                details={"operation": op, "capability": "unsupported"},
                capability="unsupported",
                alternatives=["Use a supported allowlisted function from the API manifest."],
                remedy="Consult 'sbridge manifest cards' or API manifest for supported operations.",
            )

        # 2. Capability preflight gating
        check_operation_capability(self._session.caps, op)

        # 3. Format arguments dictionary
        call_args: dict[str, Any] = {}
        if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
            call_args = dict(args[0])
        elif args:
            for idx, arg_val in enumerate(args):
                if idx < len(arg_specs):
                    call_args[arg_specs[idx]["name"]] = arg_val
                else:
                    call_args[f"arg_{idx}"] = arg_val
            call_args.update(kwargs)
        elif kwargs:
            call_args = dict(kwargs)

        return await self._session.call(op, call_args)


class SyncRawApi:
    """Synchronous allowlisted raw API passthrough wrapping AsyncRawApi via portal."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_raw: AsyncRawApi,
        session: Session | None = None,
    ) -> None:
        self._portal = portal
        self._async_raw = async_raw
        self._session = session

    def call(self, op: str, *args: Any, **kwargs: Any) -> Any:
        """Synchronously execute allowlisted raw API operation."""
        if self._session is not None and not self._session.is_connected:
            raise DisconnectedError(
                "Cannot issue operation: Session is not connected.",
                code="E_DISCONNECTED",
                remedy="Establish session connection before calling operations.",
            )
        call_fn = functools.partial(self._async_raw.call, op, *args, **kwargs)
        try:
            return self._portal.call(call_fn)
        except RuntimeError as exc:
            if "portal not running" in str(exc).lower() or (
                self._session is not None and not self._session.is_connected
            ):
                raise DisconnectedError(
                    "Cannot issue operation: Session is closed or disconnected.",
                    code="E_DISCONNECTED",
                    remedy="Establish session connection before calling operations.",
                ) from exc
            raise


class _AsyncStudioConnectBuilder:
    """Builder providing both coroutine await and asynchronous context manager protocols."""

    def __init__(
        self,
        session_coro_fn: Callable[[], Coroutine[Any, Any, Session]],
    ) -> None:
        self._session_coro_fn = session_coro_fn
        self._studio: AsyncStudio | None = None

    async def _resolve(self) -> AsyncStudio:
        if self._studio is None:
            session = await self._session_coro_fn()
            self._studio = AsyncStudio(session)
        return self._studio

    def __await__(self):
        return self._resolve().__await__()

    async def __aenter__(self) -> AsyncStudio:
        return await self._resolve()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._studio is not None:
            await self._studio.close()


class AsyncStudio:
    """Asynchronous FL Studio client context manager."""

    def __init__(self, session: Session) -> None:
        self._session: Session = session
        self.raw: AsyncRawApi = AsyncRawApi(session)
        self.caps: CapabilityRegistry = session.caps

    @property
    def session(self) -> Session:
        """Access underlying Session instance."""
        return self._session

    @property
    def is_connected(self) -> bool:
        """Whether client is currently connected."""
        return self._session.is_connected

    @property
    def sid(self) -> int:
        """Active session ID."""
        return self._session.sid

    @property
    def fp(self) -> str | None:
        """Active session fingerprint."""
        return self._session.fp

    @property
    def mode(self) -> str:
        """Current session safety mode ('read_only', 'write', 'unsafe')."""
        return self._session.mode

    @classmethod
    def connect(
        cls,
        *,
        embedded: bool = False,
        port: MidiPort | str | None = None,
        broker: Any = None,
        secret: str | None = None,
        direct_handler: Callable[[str, dict[str, Any]], Any] | None = None,
        host: str = "127.0.0.1",
        port_number: int | None = None,
        token: str | None = None,
        timeout: float = 10.0,
        mode: str = "read_only",
        caps: CapabilityRegistry | None = None,
    ) -> _AsyncStudioConnectBuilder:
        """Connect asynchronously to StudioBridge."""
        coro_fn = functools.partial(
            Session.create_and_connect,
            embedded=embedded,
            port=port,
            broker=broker,
            secret=secret,
            direct_handler=direct_handler,
            host=host,
            port_number=port_number,
            token=token,
            timeout=timeout,
            mode=mode,
            caps=caps,
        )
        return _AsyncStudioConnectBuilder(coro_fn)

    def status(self) -> Status:
        """Return structured session status snapshot per 09_l1_sdk.md §2."""
        return self._session.status()

    async def ping(self) -> float:
        """Send heartbeat ping and return round-trip latency in seconds."""
        return await self._session.ping()

    def stats(self) -> dict[str, Any]:
        """Return runtime in-process telemetry statistics."""
        return self._session.stats_accumulator.snapshot()

    def batch(self) -> AsyncBatchContext:
        """Create asynchronous batch execution context."""
        return AsyncBatchContext(self._session)

    def trace(self, output_path: Path | str | None = None) -> AsyncTraceContext:
        """Create asynchronous trace recording context."""
        return AsyncTraceContext(self._session, output_path=output_path)

    async def close(self) -> None:
        """Close active session and release resources."""
        await self._session.close()

    async def __aenter__(self) -> AsyncStudio:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        await self.close()


class Studio:
    """Synchronous FL Studio client wrapping AsyncStudio via BlockingPortal per [SDK-01]."""

    def __init__(
        self,
        portal_cm: Any,
        portal: BlockingPortal,
        async_studio: AsyncStudio,
    ) -> None:
        self._portal_cm = portal_cm
        self._portal = portal
        self._async = async_studio
        self.raw: SyncRawApi = SyncRawApi(portal, async_studio.raw, session=async_studio.session)
        self.caps: CapabilityRegistry = async_studio.caps

    @property
    def session(self) -> Session:
        """Access underlying Session instance."""
        return self._async.session

    @property
    def is_connected(self) -> bool:
        """Whether client is currently connected."""
        return self._async.is_connected

    @property
    def sid(self) -> int:
        """Active session ID."""
        return self._async.sid

    @property
    def fp(self) -> str | None:
        """Active session fingerprint."""
        return self._async.fp

    @property
    def mode(self) -> str:
        """Current session safety mode ('read_only', 'write', 'unsafe')."""
        return self._async.mode

    @classmethod
    def connect(
        cls,
        *,
        embedded: bool = False,
        port: MidiPort | str | None = None,
        broker: Any = None,
        secret: str | None = None,
        direct_handler: Callable[[str, dict[str, Any]], Any] | None = None,
        host: str = "127.0.0.1",
        port_number: int | None = None,
        token: str | None = None,
        timeout: float = 10.0,
        mode: str = "read_only",
        caps: CapabilityRegistry | None = None,
    ) -> Studio:
        """Synchronously connect to StudioBridge, initializing an isolated BlockingPortal."""
        portal_cm = anyio.from_thread.start_blocking_portal()
        portal = portal_cm.__enter__()
        try:
            connect_fn = functools.partial(
                Session.create_and_connect,
                embedded=embedded,
                port=port,
                broker=broker,
                secret=secret,
                direct_handler=direct_handler,
                host=host,
                port_number=port_number,
                token=token,
                timeout=timeout,
                mode=mode,
                caps=caps,
            )
            session = portal.call(connect_fn)
            async_studio = AsyncStudio(session)
            return cls(portal_cm, portal, async_studio)
        except Exception:
            portal_cm.__exit__(None, None, None)
            raise

    def status(self) -> Status:
        """Return structured session status snapshot per 09_l1_sdk.md §2."""
        return self._portal.call(self._async.status)

    def ping(self) -> float:
        """Send heartbeat ping and return round-trip latency in seconds."""
        return self._portal.call(self._async.ping)

    def stats(self) -> dict[str, Any]:
        """Return runtime in-process telemetry statistics."""
        return self._async.stats()

    def batch(self) -> SyncBatchContext:
        """Create synchronous batch execution context."""
        return SyncBatchContext(self._portal, self._async.session)

    def trace(self, output_path: Path | str | None = None) -> SyncTraceContext:
        """Create synchronous trace recording context."""
        return SyncTraceContext(self._portal, self._async.session, output_path=output_path)

    def close(self) -> None:
        """Close session and terminate BlockingPortal."""
        try:
            self._portal.call(self._async.close)
        finally:
            self._portal_cm.__exit__(None, None, None)

    def __enter__(self) -> Studio:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.close()


def connect(*args: Any, **kwargs: Any) -> Studio:
    """Convenience module-level entry point connecting to StudioBridge synchronously."""
    return Studio.connect(*args, **kwargs)


__all__ = [
    "AsyncRawApi",
    "AsyncStudio",
    "Studio",
    "SyncRawApi",
    "connect",
]
