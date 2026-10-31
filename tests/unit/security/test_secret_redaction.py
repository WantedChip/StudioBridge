"""Secret redaction, token masking, and diagnostic sanitization unit tests.

Verifies automated masking of 256-bit hexadecimal secrets, bearer authentication
tokens, passwords, private user home directory paths, exception tracebacks, and
diagnostic bundle archive contents.

# req: SEC-03
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from pathlib import Path

from studiobridge.core.errors import SecurityError
from studiobridge.core.logging import (
    RedactingFilter,
    get_logger,
    redact_sensitive_data,
    redact_string,
    setup_logging,
)
from studiobridge.setup.diag import create_diagnostic_bundle

# -----------------------------------------------------------------------------
# Token & Credential Masking Tests
# -----------------------------------------------------------------------------


class TestTokenAndCredentialRedaction:
    """Verifies string and structured payload sanitization.

    # req: SEC-03
    """

    def test_redact_hex_secrets(self) -> None:
        """Mask 32-to-64 hex character tokens with [REDACTED].

        # req: SEC-03
        """
        raw_secret_32 = "a" * 32
        raw_secret_64 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

        text = f"Token is {raw_secret_32} and master key is {raw_secret_64}."
        sanitized = redact_string(text)

        assert raw_secret_32 not in sanitized
        assert raw_secret_64 not in sanitized
        assert "[REDACTED]" in sanitized

    def test_redact_bearer_tokens(self) -> None:
        """Mask Bearer authorization headers with Bearer [REDACTED].

        # req: SEC-03
        """
        raw_token = (
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "e30.t-IDcSemACt8x4iTMCda8Yhe3iZaWbvV5XKSTbuAn0M"
        )
        text = f"Authorization: {raw_token} for request"
        sanitized = redact_string(text)

        assert raw_token not in sanitized
        assert "Bearer [REDACTED]" in sanitized

    def test_redact_key_value_credentials(self) -> None:
        """Mask key=value credential patterns.

        # req: SEC-03
        """
        samples = [
            "password=my_super_secret_pass",
            'secret: "unquoted_pass_123"',
            "broker_token='token_abc_xyz'",
            "api_key=AIzaSyA_abcdef12345",
            "auth=secret_auth_digest",
            "key=top_secret_key_value",
        ]
        for s in samples:
            sanitized = redact_string(s)
            assert "[REDACTED]" in sanitized
            assert "my_super_secret_pass" not in sanitized
            assert "unquoted_pass_123" not in sanitized
            assert "token_abc_xyz" not in sanitized

    def test_redact_sensitive_data_structures(self) -> None:
        """Recursively redact sensitive keys in dictionaries, lists, and tuples.

        # req: SEC-03
        """
        payload = {
            "status": "ok",
            "secret": "plain_secret_value",
            "broker_token": "secret_broker_token_value",
            "password": "plain_password",
            "private_key": "-----BEGIN PRIVATE KEY-----",
            "nested": {
                "auth": "inner_auth",
                "items": ["token=list_secret", "normal_item"],
                "tuple_data": ("secret_val", {"key": "kv_secret"}),
            },
        }
        cleaned = redact_sensitive_data(payload)

        assert cleaned["secret"] == "[REDACTED]"
        assert cleaned["broker_token"] == "[REDACTED]"
        assert cleaned["password"] == "[REDACTED]"
        assert cleaned["private_key"] == "[REDACTED]"
        assert cleaned["nested"]["auth"] == "[REDACTED]"
        assert "plain_secret_value" not in str(cleaned)
        assert "secret_broker_token_value" not in str(cleaned)


# -----------------------------------------------------------------------------
# Private Path Redaction Tests
# -----------------------------------------------------------------------------


class TestPrivatePathRedaction:
    """Verifies masking of user home directory paths.

    # req: SEC-03
    """

    def test_redact_windows_user_path(self) -> None:
        """Mask Windows user directories in file paths.

        # req: SEC-03
        """
        raw_path = r"C:\Users\JohnDoe\Documents\FL Studio\Projects\track.flp"
        sanitized = redact_string(raw_path)

        assert "JohnDoe" not in sanitized
        assert r"C:\Users\[REDACTED]\Documents\FL Studio\Projects\track.flp" in sanitized

    def test_redact_posix_user_path(self) -> None:
        """Mask Linux /home/username directory in paths.

        # req: SEC-03
        """
        raw_path = "/home/developer/workspace/studiobridge/project.flp"
        sanitized = redact_string(raw_path)

        assert "developer" not in sanitized
        assert "/home/[REDACTED]/workspace/studiobridge/project.flp" in sanitized

    def test_redact_macos_user_path(self) -> None:
        """Mask macOS /Users/username directory in paths.

        # req: SEC-03
        """
        raw_path = "/Users/producer/Music/FL Studio/demo.flp"
        sanitized = redact_string(raw_path)

        assert "producer" not in sanitized
        assert "/Users/[REDACTED]/Music/FL Studio/demo.flp" in sanitized

    def test_redact_does_not_mask_already_redacted_path(self) -> None:
        """Idempotent redaction on already masked paths.

        # req: SEC-03
        """
        masked = r"C:\Users\[REDACTED]\secret.txt"
        assert redact_string(masked) == masked


# -----------------------------------------------------------------------------
# Structured Logging Sanitization Tests
# -----------------------------------------------------------------------------


class TestLoggingSecretSanitization:
    """Verifies that emitted log records and tracebacks never contain unredacted secrets.

    # req: SEC-03, LOG-01
    """

    def test_jsonl_log_emission_redacts_secrets(self) -> None:
        """Emitted JSONL lines mask tokens, passwords, and private paths.

        # req: SEC-03, LOG-01
        """
        stream = io.StringIO()
        setup_logging(log_level="DEBUG", stream=stream)

        test_secret = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        test_path = r"C:\Users\SecretUser\Projects\project.flp"
        logger = get_logger("security_test")

        logger.info(
            evt="audit_event",
            message=f"Processing file {test_path} with token={test_secret}",
            details={"password": "super_secret_password", "path": test_path},
        )

        output = stream.getvalue().strip()
        assert len(output) > 0
        assert test_secret not in output
        assert "SecretUser" not in output
        assert "super_secret_password" not in output
        assert "[REDACTED]" in output

        parsed = json.loads(output)
        assert parsed["details"]["password"] == "[REDACTED]"
        assert "SecretUser" not in parsed["details"]["path"]

    def test_exception_traceback_redacts_secrets(self) -> None:
        """Captured exceptions with secrets in messages or frames are sanitized.

        # req: SEC-03, LOG-01
        """
        stream = io.StringIO()
        setup_logging(log_level="DEBUG", stream=stream)
        logger = get_logger("security_test_exc")

        secret_val = "secret_in_exception_val_9876543210"
        try:
            err_msg = f"Failed loading token={secret_val} from C:\\Users\\PrivateUser\\config"
            raise ValueError(err_msg)
        except ValueError:
            logger.exception(
                evt="load_failure",
                message="Exception caught during loading",
            )

        output = stream.getvalue().strip()
        assert secret_val not in output
        assert "PrivateUser" not in output
        assert "[REDACTED]" in output

    def test_redacting_filter_sanitizes_record_args(self) -> None:
        """RedactingFilter intercepts record.args dicts and tuples.

        # req: SEC-03, LOG-01
        """
        filt = RedactingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="User login token=%s",
            args=("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",),
            exc_info=None,
        )
        filt.filter(record)
        assert "0123456789abcdef" not in str(record.args)
        assert "[REDACTED]" in str(record.args)


# -----------------------------------------------------------------------------
# Exception Serialization Redaction Tests
# -----------------------------------------------------------------------------


class TestExceptionFormattingRedaction:
    """Verifies error dictionaries and serialization mask secrets.

    # req: SEC-03
    """

    def test_error_to_dict_sanitizes_sensitive_fields(self) -> None:
        """StudioBridgeError.to_dict() masks secrets in message, remedy, and details.

        # req: SEC-03
        """
        token_64 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        err = SecurityError(
            f"Access denied with token={token_64}",
            code="E_SECURITY",
            remedy="Check password=plaintext_secret in C:\\Users\\Alice\\settings.toml",
            details={
                "secret_key": "raw_sensitive_key",
                "normal_field": "public_data",
            },
        )
        d = err.to_dict()

        assert "0123456789abcdef" not in d["message"]
        assert "[REDACTED]" in d["message"]
        assert "plaintext_secret" not in d["remedy"]
        assert "Alice" not in d["remedy"]
        assert d["details"]["secret_key"] == "[REDACTED]"
        assert d["details"]["normal_field"] == "public_data"


# -----------------------------------------------------------------------------
# Diagnostic Bundle Zero Secrets Grep Tests
# -----------------------------------------------------------------------------


class TestDiagnosticBundleZeroSecrets:
    """Verifies diagnostic bundle generation sanitizes all archives.

    # req: SEC-03, DOC-02
    """

    def test_diagnostic_bundle_contains_zero_secrets(self, tmp_path: Path) -> None:
        """Diagnostic bundle excludes token files and redacts all secrets across all archive bytes.

        # req: SEC-03, DOC-02
        """
        app_data = tmp_path / "app_data"
        logs_dir = app_data / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        raw_secret = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        raw_token = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
        raw_password = "very_sensitive_diagnostic_password"

        # 1. Write secret files that MUST be excluded from zip
        (app_data / "secret").write_text(raw_secret, encoding="utf-8")
        (app_data / "broker.token").write_text(raw_token, encoding="utf-8")

        # 2. Write configuration file containing secrets
        cfg_content = (
            f'[broker]\nport = 50051\nbroker_token = "{raw_token}"\n'
            f'[wire]\nsecret = "{raw_secret}"\n'
            f'[auth]\npassword = "{raw_password}"\n'
        )
        (app_data / "config.toml").write_text(cfg_content, encoding="utf-8")

        # 3. Write logs containing secrets and user paths
        log_file = logs_dir / "service.log"
        log_file.write_text(
            f"INFO Connection token={raw_token} path=C:\\Users\\Bob\\project.flp\n"
            f"DEBUG Session secret: {raw_secret} password={raw_password}\n",
            encoding="utf-8",
        )

        out_zip = tmp_path / "sanitized_diag.zip"
        bundle_path = create_diagnostic_bundle(
            out_path=out_zip,
            app_data_dir=app_data,
            skip_live=True,
        )

        assert bundle_path.exists()
        assert bundle_path == out_zip

        with zipfile.ZipFile(bundle_path, "r") as zf:
            names = zf.namelist()
            # Explicit exclusion check
            assert "secret" not in names
            assert "broker.token" not in names

            # Comprehensive byte-level grep over 100% of archive members
            for name in names:
                data = zf.read(name).decode("utf-8", errors="replace")
                assert raw_secret not in data, f"Secret leaked in {name}"
                assert raw_token not in data, f"Token leaked in {name}"
                assert raw_password not in data, f"Password leaked in {name}"
                assert "C:\\Users\\Bob" not in data, f"User path leaked in {name}"
