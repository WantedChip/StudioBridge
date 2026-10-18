"""Unit tests for StudioBridge error hierarchy and taxonomy.

# req: ERR-01
"""

from __future__ import annotations

from studiobridge.core.errors import (
    ERROR_REGISTRY,
    BrokerError,
    DeviceError,
    PortError,
    PreconditionError,
    ProtocolError,
    SafetyError,
    StudioBridgeError,
    UnavailableError,
    VerificationError,
)

EXPECTED_TAXONOMY_CODES = [
    # E_PROTO*
    "E_PROTO",
    "E_AUTH",
    "E_VERSION",
    "E_STALE",
    "E_TOOBIG",
    # E_DEV*
    "E_BUSY",
    "E_TIMEOUT",
    "E_UNCERTAIN",
    "E_FL",
    "E_SANDBOX",
    "E_CANCELLED",
    # E_CAP*
    "E_UNAVAILABLE",
    "E_DEGRADED",
    "E_EXPERIMENTAL",
    # E_ARG*
    "E_ARGS",
    "E_BADREF",
    "E_AMBIGUOUS",
    "E_RANGE",
    "E_PRECONDITION",
    # E_VER*
    "E_UNVERIFIED",
    # E_SAFE*
    "E_READONLY",
    "E_PROTECTED",
    "E_POLICY",
    "E_CONFIRM",
    # E_CONN*
    "E_NOBROKER",
    "E_NODEVICE",
    "E_DISCONNECTED",
    "E_LEASE",
    # E_FLP*
    "E_FLP_PARSE",
    "E_FLP_VERSION",
    "E_FLP_INVARIANT",
    "E_FLP_WRITE_RISK",
    # E_RND*
    "E_RND_FLRUNNING",
    "E_RND_DIALOG",
    "E_RND_TIMEOUT",
    "E_RND_INVALID",
    # E_ENV*
    "E_ENV_PORT",
    "E_ENV_FL",
    "E_ENV_PY",
    "E_ENV_OS",
]


def test_taxonomy_registry_completeness():
    """Verify all taxonomy error codes exist and provide remedies and metadata.

    # req: ERR-01
    """
    for code in EXPECTED_TAXONOMY_CODES:
        assert code in ERROR_REGISTRY, f"Code {code} missing from ERROR_REGISTRY"
        info = ERROR_REGISTRY[code]
        assert info.code == code
        assert isinstance(info.default_message, str) and len(info.default_message.strip()) > 0
        assert isinstance(info.retryable, bool)
        assert isinstance(info.remedy, str) and len(info.remedy.strip()) > 0, (
            f"Code {code} must have a non-empty remedy string"
        )
        assert isinstance(info.docs_anchor, str) and len(info.docs_anchor.strip()) > 0


def test_root_studiobridge_error_defaults():
    """Verify default attributes and serialization of StudioBridgeError.

    # req: ERR-01
    """
    err = StudioBridgeError()
    assert err.code == "E_FL"
    assert "FL Studio" in err.message
    assert err.retryable is False
    assert len(err.remedy) > 0
    assert err.details == {}

    data = err.to_dict()
    assert data["code"] == "E_FL"
    assert data["message"] == err.message
    assert data["retryable"] is False
    assert data["remedy"] == err.remedy
    assert data["details"] == {}

    str_repr = str(err)
    assert "[E_FL]" in str_repr
    assert "Remedy:" in str_repr


def test_error_custom_override():
    """Verify custom attributes override default metadata.

    # req: ERR-01
    """
    err = StudioBridgeError(
        message="Custom fatal failure",
        code="E_AUTH",
        details={"attempt": 3, "ip": "127.0.0.1"},
        retryable=True,
        remedy="Re-generate secret in config and restart FL.",
    )
    assert err.code == "E_AUTH"
    assert err.message == "Custom fatal failure"
    assert err.retryable is True
    assert err.remedy == "Re-generate secret in config and restart FL."
    assert err.details == {"attempt": 3, "ip": "127.0.0.1"}

    data = err.to_dict()
    assert data["code"] == "E_AUTH"
    assert data["details"]["attempt"] == 3


def test_all_subclasses_have_non_empty_remedies():
    """Ensure every error subclass carries a non-empty remedy by default.

    # req: ERR-01
    """
    subclasses = [
        ProtocolError,
        PortError,
        BrokerError,
        DeviceError,
        PreconditionError,
        VerificationError,
        UnavailableError,
        SafetyError,
    ]

    for cls in subclasses:
        instance = cls()
        assert isinstance(instance, StudioBridgeError)
        assert isinstance(instance.remedy, str), f"{cls.__name__}.remedy must be str"
        assert len(instance.remedy.strip()) > 0, f"{cls.__name__} must carry a non-empty remedy"
        assert isinstance(instance.code, str) and len(instance.code) > 0


def test_verification_error_attributes():
    """Test VerificationError captures target and actual values.

    # req: ERR-01
    """
    err = VerificationError(
        message="Volume did not settle",
        target_value=0.8,
        actual_value=0.5,
    )
    assert err.code == "E_UNVERIFIED"
    assert err.retryable is True
    assert err.details["target_value"] == 0.8
    assert err.details["actual_value"] == 0.5
    assert len(err.remedy) > 0


def test_unavailable_error_alternatives():
    """Test UnavailableError encapsulates alternatives list.

    # req: ERR-01
    """
    err = UnavailableError(
        message="Piano roll actuation is not available",
        alternatives=["offline.flp.write", "render.cli"],
    )
    assert err.code == "E_UNAVAILABLE"
    assert err.alternatives == ["offline.flp.write", "render.cli"]
    assert err.details["alternatives"] == ["offline.flp.write", "render.cli"]
    dict_data = err.to_dict()
    assert dict_data["alternatives"] == ["offline.flp.write", "render.cli"]
    assert len(err.remedy) > 0


def test_error_unknown_code_fallback():
    """Verify graceful fallback when an unrecognized code is passed.

    # req: ERR-01
    """
    err = StudioBridgeError("Custom error message", code="E_CUSTOM_NEW")
    assert err.code == "E_CUSTOM_NEW"
    assert err.message == "Custom error message"
    assert err.retryable is False
    assert len(err.remedy) > 0
    assert repr(err).startswith("StudioBridgeError(")
