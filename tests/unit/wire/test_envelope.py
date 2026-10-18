"""Unit tests for JSON envelopes, 7-bit ASCII serialization, and deserialization.

Validates RequestEnvelope, ResponseEnvelope, EventEnvelope, and ControlEnvelope models,
strict 7-bit ASCII cleanliness, Vector 1 alignment, and deserialization error handling
per spec 03_l0a_wire_protocol.md §5.
"""

from __future__ import annotations

import json

import pytest

from studiobridge.core.errors import ProtocolError
from studiobridge.wire.envelope import (
    MAX_IDEM_LENGTH,
    ControlEnvelope,
    EventEnvelope,
    RequestEnvelope,
    RequestOpts,
    ResponseEnvelope,
    deserialize_envelope,
    serialize_envelope,
)
from studiobridge.wire.frame import FrameKind


class TestRequestEnvelope:
    """Test RequestEnvelope fields, serialization, and constraints."""

    def test_minimal_request_vector_1(self) -> None:
        """Vector 1 payload {"op":"ping"} serializes identically to golden byte string."""
        req = RequestEnvelope(op="ping")
        encoded = req.to_json()
        assert encoded == b'{"op":"ping"}'
        assert len(encoded) == 13

        decoded = RequestEnvelope.from_json(encoded)
        assert decoded.op == "ping"
        assert decoded.idem is None
        assert decoded.auth is None
        assert decoded.args == {}
        assert decoded.opts.to_dict() == {}

    def test_full_request_serialization(self) -> None:
        """Full mutating request matches wire specification §5.1."""
        req = RequestEnvelope(
            op="call",
            idem="c-7f3a",
            auth="9be1000000000000",
            args={"fn": "mixer.setTrackVolume", "a": [3, 0.8]},
            opts=RequestOpts(
                verify="settled",
                budget_ms=8,
                budget_calls=150,
                expect={"fn": "mixer.getTrackVolume", "a": [3], "eq": 0.8, "tol": 0.005},
                fp="fp-12345678",
            ),
        )
        encoded = req.to_json()
        data = json.loads(encoded)
        assert data["op"] == "call"
        assert data["idem"] == "c-7f3a"
        assert data["auth"] == "9be1000000000000"
        assert data["args"]["fn"] == "mixer.setTrackVolume"
        assert data["opts"]["verify"] == "settled"
        assert data["opts"]["budget_ms"] == 8
        assert data["opts"]["expect"]["eq"] == 0.8
        assert data["opts"]["fp"] == "fp-12345678"

        # Roundtrip verification
        decoded = RequestEnvelope.from_json(encoded)
        assert decoded.op == req.op
        assert decoded.idem == req.idem
        assert decoded.auth == req.auth
        assert decoded.args == req.args
        assert decoded.opts.verify == "settled"
        assert decoded.opts.fp == "fp-12345678"

    def test_missing_op_raises_error(self) -> None:
        """Request without op raises ProtocolError."""
        with pytest.raises(ProtocolError) as exc_info:
            RequestEnvelope(op="")
        assert exc_info.value.code == "E_PROTO"

        with pytest.raises(ProtocolError) as exc_info2:
            RequestEnvelope.from_dict({})
        assert exc_info2.value.code == "E_PROTO"

    def test_idem_length_limit(self) -> None:
        """idem string longer than MAX_IDEM_LENGTH (24 chars) raises E_ARGS."""
        valid_idem = "x" * MAX_IDEM_LENGTH
        req = RequestEnvelope(op="call", idem=valid_idem)
        assert req.idem == valid_idem

        invalid_idem = "x" * (MAX_IDEM_LENGTH + 1)
        with pytest.raises(ProtocolError) as exc_info:
            RequestEnvelope(op="call", idem=invalid_idem)
        assert exc_info.value.code == "E_ARGS"


class TestResponseEnvelope:
    """Test ResponseEnvelope success, failure, and metrics formatting."""

    def test_success_response_vector_2_style(self) -> None:
        """Successful response matching spec §5.2."""
        res = ResponseEnvelope.success(
            r=0.8,
            rb=0.8,
            m={"settled": True, "ms": 3, "q": 0},
        )
        encoded = res.to_json()
        assert encoded == b'{"ok":true,"r":0.8,"rb":0.8,"m":{"settled":true,"ms":3,"q":0}}'

        decoded = ResponseEnvelope.from_json(encoded)
        assert decoded.ok is True
        assert decoded.r == 0.8
        assert decoded.rb == 0.8
        assert decoded.m == {"settled": True, "ms": 3, "q": 0}
        assert decoded.code is None
        assert decoded.err is None

    def test_failure_response(self) -> None:
        """Failure response matching wire specification §5.2."""
        res = ResponseEnvelope.failure(
            code="E_ARGS",
            message="track out of range",
            details={"max": 126},
            retry=False,
        )
        encoded = res.to_json()
        data = json.loads(encoded)
        assert data["ok"] is False
        assert data["e"]["c"] == "E_ARGS"
        assert data["e"]["m"] == "track out of range"
        assert data["e"]["d"] == {"max": 126}
        assert "retry" not in data["e"]  # false is omitted or included

        decoded = ResponseEnvelope.from_json(encoded)
        assert decoded.ok is False
        assert decoded.code == "E_ARGS"
        assert decoded.err == "track out of range"
        assert decoded.details == {"max": 126}
        assert decoded.retryable is False

    def test_alternative_flat_error_deserialization(self) -> None:
        """Allow deserializing responses with top-level error attributes."""
        flat_error = b'{"ok":false,"code":"E_STALE","err":"Stale session ID"}'
        res = ResponseEnvelope.from_json(flat_error)
        assert res.ok is False
        assert res.code == "E_STALE"
        assert res.err == "Stale session ID"


class TestEventEnvelope:
    """Test EventEnvelope creation and serialization."""

    def test_event_serialization(self) -> None:
        """Event envelope matching spec §5.3."""
        evt = EventEnvelope(
            ev="transport",
            seq=812,
            d={"playing": True, "pos_ticks": 1920},
        )
        encoded = evt.to_json()
        assert encoded == b'{"ev":"transport","seq":812,"d":{"playing":true,"pos_ticks":1920}}'

        decoded = EventEnvelope.from_json(encoded)
        assert decoded.ev == "transport"
        assert decoded.seq == 812
        assert decoded.d == {"playing": True, "pos_ticks": 1920}

    def test_missing_ev_raises_error(self) -> None:
        """Event without ev or seq raises ProtocolError."""
        with pytest.raises(ProtocolError):
            EventEnvelope.from_dict({"seq": 1})
        with pytest.raises(ProtocolError):
            EventEnvelope.from_dict({"ev": "test"})


class TestControlEnvelope:
    """Test ControlEnvelope factory methods and validation."""

    def test_control_variants(self) -> None:
        """Verify all control message variants serialize per §5.4."""
        nack = ControlEnvelope.nack(mid=12, missing=[3, 4])
        assert nack.to_json() == b'{"c":"nack","mid":12,"missing":[3,4]}'

        ack = ControlEnvelope.ack(mid=12)
        assert ack.to_json() == b'{"c":"ack","mid":12}'

        busy = ControlEnvelope.busy(retry_ms=50)
        assert busy.to_json() == b'{"c":"busy","retry_ms":50}'

        ping = ControlEnvelope.ping()
        assert ping.to_json() == b'{"c":"ping"}'

        pong = ControlEnvelope.pong(mid=5)
        assert pong.to_json() == b'{"c":"pong","mid":5}'

        panic = ControlEnvelope.panic()
        assert panic.to_json() == b'{"c":"panic"}'

    def test_invalid_control_command_raises_error(self) -> None:
        """Unknown control command raises ProtocolError."""
        with pytest.raises(ProtocolError) as exc_info:
            ControlEnvelope(c="invalid_cmd")
        assert exc_info.value.code == "E_PROTO"


class TestSevenBitAsciiCleanliness:
    """Definition of Done: strictly 7-bit clean ASCII JSON (all(b < 128))."""

    def test_ascii_cleanliness_with_unicode_strings(self) -> None:
        """All Unicode characters are escaped so all bytes are strictly < 128."""
        req = RequestEnvelope(
            op="call",
            args={
                "title": "Song in C# Minor ♩♪♫♬",
                "japanese": "スタジオブリッジ",
                "emoji": "🎹🎶🚀",
                "accents": "Café & Résumé",
            },
        )
        encoded = serialize_envelope(req)

        # Check all bytes are strictly 7-bit ASCII
        assert all(b < 128 for b in encoded)

        # Confirm roundtrip decodes unicode correctly
        decoded = deserialize_envelope(encoded)
        assert isinstance(decoded, RequestEnvelope)
        assert decoded.args["title"] == "Song in C# Minor ♩♪♫♬"
        assert decoded.args["japanese"] == "スタジオブリッジ"
        assert decoded.args["emoji"] == "🎹🎶🚀"
        assert decoded.args["accents"] == "Café & Résumé"


class TestGenericSerialization:
    """Test serialize_envelope and deserialize_envelope dispatch."""

    def test_explicit_kind_deserialization(self) -> None:
        """Deserialization using explicit FrameKind."""
        req_bytes = b'{"op":"ping"}'
        env1 = deserialize_envelope(req_bytes, kind=FrameKind.REQ)
        assert isinstance(env1, RequestEnvelope)

        res_bytes = b'{"ok":true,"r":1}'
        env2 = deserialize_envelope(res_bytes, kind=FrameKind.RES)
        assert isinstance(env2, ResponseEnvelope)

        evt_bytes = b'{"ev":"test","seq":1,"d":{}}'
        env3 = deserialize_envelope(evt_bytes, kind=FrameKind.EVT)
        assert isinstance(env3, EventEnvelope)

        ctl_bytes = b'{"c":"busy","retry_ms":20}'
        env4 = deserialize_envelope(ctl_bytes, kind=FrameKind.CTL)
        assert isinstance(env4, ControlEnvelope)

    def test_inferred_kind_deserialization(self) -> None:
        """Deserialization with inferred types from JSON keys."""
        assert isinstance(deserialize_envelope(b'{"op":"ping"}'), RequestEnvelope)
        assert isinstance(deserialize_envelope(b'{"ok":true}'), ResponseEnvelope)
        assert isinstance(deserialize_envelope(b'{"ev":"tick","seq":10}'), EventEnvelope)
        assert isinstance(deserialize_envelope(b'{"c":"panic"}'), ControlEnvelope)

    def test_malformed_json_raises_proto_error(self) -> None:
        """Malformed JSON raises ProtocolError with E_PROTO."""
        with pytest.raises(ProtocolError) as exc_info:
            deserialize_envelope(b"not-json")
        assert exc_info.value.code == "E_PROTO"

        with pytest.raises(ProtocolError) as exc_info2:
            deserialize_envelope(b"[1, 2, 3]")
        assert exc_info2.value.code == "E_PROTO"
