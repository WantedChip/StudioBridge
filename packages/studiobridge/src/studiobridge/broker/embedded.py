"""In-process broker facade for direct SDK execution and headless testing.

Implements EmbeddedBroker per [BRK-20] and spec 04_l0b_ports_broker.md §8.7.
Allows in-process scheduling, port arbitration, event multiplexing, and lease management
without requiring a detached background daemon process.
"""

from __future__ import annotations

import collections
import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anyio

from studiobridge._version import __version__
from studiobridge.broker.lease import DEFAULT_LEASE_TTL, LeaseManager
from studiobridge.broker.scheduler import (
    Priority,
    RateLimiter,
    ScheduledRequest,
    Scheduler,
    classify_priority,
)
from studiobridge.core.errors import BrokerError, StudioBridgeError
from studiobridge.core.logging import get_logger
from studiobridge.device.assets._sb_api import ALLOW
from studiobridge.ports.base import MidiPort
from studiobridge.wire.auth import sign_request
from studiobridge.wire.chunk import Reassembler, chunk_payload
from studiobridge.wire.envelope import EventEnvelope, RequestEnvelope, RequestOpts, ResponseEnvelope
from studiobridge.wire.frame import Frame, FrameKind, decode_frame, encode_frame
from studiobridge.wire.session import Session, is_mutating_operation

logger = get_logger("broker.embedded")


@dataclass(slots=True)
class EventSubscription:
    """Subscription record for an event consumer."""

    client_id: str
    callback: Callable[[str, Any], None] | None = None
    queue: collections.deque[tuple[str, Any, int]] = field(
        default_factory=lambda: collections.deque(maxlen=256)
    )


class EmbeddedBroker:
    """In-process broker managing scheduler, writer leases, MIDI port, and event fan-out.

    Adheres to [BRK-20], allowing SDK clients to execute directly against local ports
    or fake ports without launching an external daemon.
    """

    def __init__(
        self,
        *,
        port: MidiPort | None = None,
        secret: str | None = None,
        scheduler: Scheduler | None = None,
        lease_manager: LeaseManager | None = None,
        clock: Callable[[], float] = time.monotonic,
        direct_handler: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        self.clock = clock
        self.port: MidiPort | None = port
        self.secret: str | None = secret
        self.direct_handler = direct_handler

        self.lease_manager: LeaseManager = (
            lease_manager if lease_manager is not None else LeaseManager(clock=clock)
        )
        self.scheduler: Scheduler = (
            scheduler
            if scheduler is not None
            else Scheduler(rate_limiter=RateLimiter(clock=clock), clock=clock)
        )

        self.session: Session = Session.allocate(sid=1)
        if port is not None:
            self.session.fp = ""
        self._reassembler: Reassembler = Reassembler()
        self._mid_counter: int = 1
        self._started_at: float = clock()

        # In-flight request matching: mid -> ScheduledRequest
        self._in_flight: dict[int, ScheduledRequest] = {}

        # Topic -> list of EventSubscription
        self._subscriptions: dict[str, list[EventSubscription]] = collections.defaultdict(list)
        # client_id -> set of topics
        self._client_topics: dict[str, set[str]] = collections.defaultdict(set)

        self._is_running: bool = False
        self._worker_scope: anyio.CancelScope | None = None

        if self.port is not None:
            self.port.on_sysex(self._on_port_sysex)

    @property
    def is_running(self) -> bool:
        """Whether the embedded broker scheduler loop is active."""
        return self._is_running

    async def start(self) -> None:
        """Start the broker request processing loop."""
        if self._is_running:
            return
        self._is_running = True
        logger.info("broker_started", "EmbeddedBroker initialized", sid=str(self.session.sid))

    async def stop(self) -> None:
        """Stop the broker and clean up resources."""
        if not self._is_running:
            return
        self._is_running = False
        if self._worker_scope:
            self._worker_scope.cancel()
        if self.port is not None:
            with contextlib.suppress(Exception):
                self.port.close()
        logger.info("broker_stopped", "EmbeddedBroker shut down")

    async def __aenter__(self) -> EmbeddedBroker:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()

    def _next_mid(self) -> int:
        mid = self._mid_counter
        self._mid_counter = (mid % 0x1FFFFF) + 1
        return mid

    # -------------------------------------------------------------------------
    # Core JSON-RPC Dispatch Methods
    # -------------------------------------------------------------------------

    async def session_info(self) -> dict[str, Any]:
        """Return active session identifiers and status."""
        port_open = False
        port_name = None
        if self.port is not None:
            port_open = getattr(self.port, "_is_open", True)
            port_name = getattr(self.port, "_in_name", "midi")

        return {
            "sid": self.session.sid,
            "nonce": self.session.nonce,
            "fp": self.session.fp,
            "version": __version__,
            "port_open": port_open,
            "port_name": port_name,
            "uptime_seconds": round(self.clock() - self._started_at, 2),
        }

    async def ping(self) -> dict[str, Any]:
        """Broker health ping."""
        return {"pong": True, "timestamp": time.time()}

    async def broker_status(self) -> dict[str, Any]:
        """Comprehensive broker health and telemetry snapshot per §8.6."""
        now = self.clock()
        port_api = "embedded"
        stats = {}
        if self.port is not None:
            port_api = getattr(self.port, "api", "midi")
            if hasattr(self.port, "stats"):
                port_stats = self.port.stats
                stats = {
                    "bytes_sent": getattr(port_stats, "bytes_sent", 0),
                    "bytes_recv": getattr(port_stats, "bytes_recv", 0),
                    "frames_sent": getattr(port_stats, "frames_sent", 0),
                    "frames_recv": getattr(port_stats, "frames_recv", 0),
                    "dropped": getattr(port_stats, "dropped", 0),
                }

        return {
            "uptime": round(now - self._started_at, 2),
            "backend": port_api,
            "sid": self.session.sid,
            "lease": self.lease_manager.get_state(),
            "pending_requests": self.scheduler.pending_count,
            "subscriptions": len(self._subscriptions),
            "port_stats": stats,
            "version": __version__,
        }

    async def lease_acquire(
        self,
        owner: str,
        ttl: float = DEFAULT_LEASE_TTL,
        purpose: str = "",
    ) -> dict[str, Any]:
        """Acquire or renew writer lease for owner."""
        lease = self.lease_manager.acquire(owner, ttl=ttl, purpose=purpose)
        return lease.to_dict(self.clock())

    async def lease_renew(
        self,
        owner: str,
        ttl: float = DEFAULT_LEASE_TTL,
    ) -> dict[str, Any]:
        """Extend active writer lease for owner."""
        lease = self.lease_manager.renew(owner, ttl=ttl)
        return lease.to_dict(self.clock())

    async def lease_release(self, owner: str) -> dict[str, Any]:
        """Explicitly release active lease held by owner."""
        released = self.lease_manager.release(owner)
        return {"released": released}

    async def device_call(
        self,
        op: str,
        args: dict[str, Any] | None = None,
        *,
        client_id: str = "default",
        priority: str | Priority | None = None,
        timeout: float = 5.0,
    ) -> Any:
        """Schedule and execute a single device operation."""
        call_args = args or {}
        p = classify_priority(op, explicit=priority)
        leaf = op.split(".")[-1].lower()
        is_write = (
            p in {Priority.WRITE, Priority.BULK}
            and op not in {"hello", "probe", "ping", "session.info"}
            and not leaf.startswith(("get", "read", "list", "is", "probe", "info", "find", "check"))
        )

        # 1. Enforce single-writer lease on mutating operations
        if is_write:
            self.lease_manager.validate_write(client_id)
            self.lease_manager.begin_request(client_id)

        # 3. Create scheduled request
        mid = self._next_mid()
        req = ScheduledRequest(
            request_id=f"{client_id}:{mid}",
            client_id=client_id,
            priority=p,
            op=op,
            args=call_args,
            created_at=self.clock(),
        )

        try:
            # Enqueue into priority scheduler
            self.scheduler.enqueue(req)

            # Direct dispatch if handler or port available
            result = await self._execute_request(req, mid, timeout=timeout)
            return result
        finally:
            if is_write:
                self.lease_manager.end_request(client_id)

    async def device_batch(
        self,
        ops: list[dict[str, Any]],
        *,
        client_id: str = "default",
        timeout: float = 15.0,
    ) -> list[Any]:
        """Execute a batch of device operations."""
        has_mutating = any(is_mutating_operation(op.get("op", "")) for op in ops)
        if has_mutating:
            self.lease_manager.validate_write(client_id)
            self.lease_manager.begin_request(client_id)

        try:
            results: list[Any] = []
            for op_item in ops:
                op_name = op_item.get("op", "")
                op_args = op_item.get("args", {})
                res = await self.device_call(
                    op_name,
                    op_args,
                    client_id=client_id,
                    priority=Priority.BULK,
                    timeout=timeout,
                )
                results.append(res)
            return results
        finally:
            if has_mutating:
                self.lease_manager.end_request(client_id)

    async def device_subscribe(
        self,
        topics: list[str],
        client_id: str,
        callback: Callable[[str, Any], None] | None = None,
    ) -> dict[str, Any]:
        """Subscribe client to device event notification topics."""
        sub = EventSubscription(client_id=client_id, callback=callback)
        for topic in topics:
            self._subscriptions[topic].append(sub)
            self._client_topics[client_id].add(topic)
        return {"subscribed": list(topics)}

    async def device_unsubscribe(self, topics: list[str], client_id: str) -> dict[str, Any]:
        """Unsubscribe client from event notification topics."""
        for topic in topics:
            subs = self._subscriptions.get(topic, [])
            filtered = [s for s in subs if s.client_id != client_id]
            if filtered:
                self._subscriptions[topic] = filtered
            else:
                self._subscriptions.pop(topic, None)
            self._client_topics[client_id].discard(topic)
        return {"unsubscribed": list(topics)}

    def on_client_disconnect(self, client_id: str) -> None:
        """Cleanup all state, subscriptions, and leases for disconnected client."""
        # Revoke lease held by this client [BRK-10]
        self.lease_manager.revoke_owner(client_id)
        # Purge queued requests
        self.scheduler.cancel_client(client_id)
        # Remove subscriptions
        topics = list(self._client_topics.pop(client_id, set()))
        for topic in topics:
            subs = self._subscriptions.get(topic, [])
            filtered = [s for s in subs if s.client_id != client_id]
            if filtered:
                self._subscriptions[topic] = filtered
            else:
                self._subscriptions.pop(topic, None)

    # -------------------------------------------------------------------------
    # Execution & SysEx Transport
    # -------------------------------------------------------------------------

    async def _execute_request(
        self,
        req: ScheduledRequest,
        mid: int,
        timeout: float = 5.0,
    ) -> Any:
        """Internal execution path for scheduled requests."""
        # 1. Custom mock/direct handler support (for testing / headless)
        if self.direct_handler is not None:
            try:
                res = self.direct_handler(req.op, req.args)
                req.set_result(res)
                return res
            except Exception as exc:
                req.set_error(exc)
                raise

        # 2. Builtin operations without port requirement
        if req.op in {"ping", "broker.ping"}:
            res = {"pong": True, "timestamp": time.time()}
            req.set_result(res)
            return res

        if req.op == "session.info" or (req.op == "hello" and self.port is None):
            res = await self.session_info()
            req.set_result(res)
            return res

        # 3. Transport over MIDI port
        if self.port is None:
            raise BrokerError(
                f"Cannot execute '{req.op}': no MIDI port or device connected",
                code="E_NODEVICE",
                retryable=True,
            )

        self._in_flight[mid] = req

        try:
            wire_op = req.op
            wire_args = req.args
            if req.op not in {"ping", "hello", "probe", "call", "batch", "log", "panic"}:
                wire_op = "call"
                if isinstance(req.args, dict) and "fn" in req.args and "a" in req.args:
                    wire_args = req.args
                else:
                    a_list: list[Any] = []
                    if "." in req.op:
                        m_name, f_name = req.op.split(".", 1)
                        if m_name in ALLOW and f_name in ALLOW[m_name]:
                            param_specs = ALLOW[m_name][f_name].get("args", [])
                            for p_spec in param_specs:
                                p_name = p_spec["name"]
                                if p_name in req.args:
                                    a_list.append(req.args[p_name])
                                elif not p_spec.get("optional", False) and len(a_list) < len(
                                    req.args
                                ):
                                    a_list = list(req.args.values())
                                    break
                    if not a_list and isinstance(req.args, dict):
                        a_list = list(req.args.values())
                    wire_args = {"fn": req.op, "a": a_list}

            # Build RequestEnvelope
            fp_to_send = (
                self.session.fp
                if (self.session.fp and wire_op not in {"hello", "probe", "ping"})
                else None
            )
            req_env = RequestEnvelope(
                op=wire_op,
                args=wire_args,
                opts=RequestOpts(fp=fp_to_send),
            )
            if self.secret is not None:
                req_env = sign_request(self.secret, req_env)

            payload_bytes = req_env.to_json()
            chunks = chunk_payload(payload_bytes, max_payload=490)
            ccnt = len(chunks)

            # Transmit frames sequentially
            for cidx, chunk_data in enumerate(chunks):
                frame = Frame(
                    kind=FrameKind.REQ,
                    flags=0,
                    sid=self.session.sid,
                    mid=mid,
                    cidx=cidx,
                    ccnt=ccnt,
                    payload=chunk_data,
                )
                frame_bytes = encode_frame(frame)
                self.port.send_sysex(frame_bytes)

            # Wait for response with timeout
            with anyio.fail_after(timeout):
                await req.future_event.wait()

            if req.error is not None:
                raise req.error
            return req.result

        except TimeoutError as exc:
            msg = f"Operation '{req.op}' timed out after {timeout}s"
            raise BrokerError(msg, code="E_TIMEOUT", retryable=True) from exc
        finally:
            self._in_flight.pop(mid, None)

    def _on_port_sysex(self, data: bytes) -> None:
        """Callback invoked when SysEx frame arrives on the MIDI port."""
        try:
            frame = decode_frame(data)
        except Exception:
            return

        complete_payload = self._reassembler.feed(frame)
        if complete_payload is None:
            return

        if frame.kind == FrameKind.RES:
            try:
                res_env = ResponseEnvelope.from_json(complete_payload)
                req = self._in_flight.get(frame.mid)
                if req is not None:
                    if not res_env.ok:
                        req.set_error(
                            StudioBridgeError(
                                res_env.err or "FL Studio error",
                                code=res_env.code or "E_FL",
                                details=res_env.details,
                            )
                        )
                    else:
                        if req.op == "hello" and isinstance(res_env.r, dict):
                            if "sid" in res_env.r:
                                self.session.sid = int(res_env.r["sid"])
                            if "fp" in res_env.r:
                                self.session.fp = res_env.r["fp"]
                        req.set_result(res_env.r)
            except Exception as exc:
                logger.error("res_decode_failed", f"Failed decoding response: {exc}")

        elif frame.kind == FrameKind.EVT:
            try:
                evt_env = EventEnvelope.from_json(complete_payload)
                self.publish_event(evt_env.ev, evt_env.d, seq=evt_env.seq)
            except Exception as exc:
                logger.error("evt_decode_failed", f"Failed decoding event: {exc}")

    def publish_event(self, topic: str, data: Any, seq: int = 0) -> None:
        """Fan out incoming event notification to all subscribed clients."""
        subs = self._subscriptions.get(topic, [])
        for sub in list(subs):
            sub.queue.append((topic, data, seq))
            if sub.callback is not None:
                try:
                    sub.callback(topic, data)
                except Exception as exc:
                    logger.warning(
                        "sub_callback_error",
                        f"Subscriber callback error for {topic}: {exc}",
                    )
