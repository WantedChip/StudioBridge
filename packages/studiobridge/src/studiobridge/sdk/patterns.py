"""Pattern management namespace for StudioBridge Python SDK.

Provides high-level typed pattern controllers (AsyncPatterns and SyncPatterns)
mounted on AsyncStudio.patterns and Studio.patterns.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, PreconditionError
from studiobridge.sdk.refs import Pattern, resolve_reference
from studiobridge.sdk.types import UntrustedString, Verified
from studiobridge.sdk.units import Color
from studiobridge.sdk.verification import build_expect_guard, verify_mutation

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


def _resolve_pattern_number(pattern: int | Pattern) -> int:
    num = pattern.number if isinstance(pattern, Pattern) else int(pattern)
    if num < 1:
        raise ValueError(f"Pattern number must be >= 1 (1-based), got {num}")
    return num


class AsyncPatterns:
    """Asynchronous FL Studio pattern management interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def count(self) -> int:
        """Retrieve total count of patterns in project."""
        res = await self._session.call("patterns.patternCount", {})
        return int(res) if res is not None else 0

    async def get_active_number(self) -> int:
        """Retrieve 1-based index of currently active pattern."""
        res = await self._session.call("patterns.patternNumber", {})
        return int(res) if res is not None else 1

    async def get_name(self, index: int | Pattern) -> UntrustedString:
        """Retrieve pattern label tagged with untrusted metadata."""
        num = _resolve_pattern_number(index)
        res = await self._session.call("patterns.getPatternName", {"index": num})
        return UntrustedString(res) if res is not None else UntrustedString("")

    async def set_name(
        self,
        index: int | Pattern,
        name: str,
        *,
        expect: str | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[str]:
        """Set pattern name with read-back verification."""
        num = _resolve_pattern_number(index)
        str_val = str(name)
        before = await self.get_name(num)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = str(expect)
                guard = build_expect_guard(
                    "patterns.setPatternName", "patterns.getPatternName", [num], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for patterns.setPatternName: "
                        f"expected {exp_val!r}, current value is {before!r}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "patterns.setPatternName",
            {"index": num, "name": str_val},
            opts=call_opts,
        )
        after = await self.get_name(num)
        return verify_mutation(
            "patterns.setPatternName",
            str_val,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"pattern": num},
            journal=self._session.safety.journal,
            remedy="Ensure pattern index exists and name is non-empty.",
        )

    async def get_color(self, index: int | Pattern) -> int:
        """Retrieve pattern RGB color integer."""
        num = _resolve_pattern_number(index)
        res = await self._session.call("patterns.getPatternColor", {"index": num})
        return int(res) if res is not None else 0

    async def set_color(
        self,
        index: int | Pattern,
        color: int | Color | str | tuple[int, int, int],
        *,
        expect: int | Color | str | tuple[int, int, int] | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set pattern RGB color with read-back verification."""
        num = _resolve_pattern_number(index)
        col_val = int(Color(color)) if not isinstance(color, int) else int(color)
        before = await self.get_color(num)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = int(Color(expect)) if not isinstance(expect, int) else int(expect)
                guard = build_expect_guard(
                    "patterns.setPatternColor", "patterns.getPatternColor", [num], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for patterns.setPatternColor: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "patterns.setPatternColor",
            {"index": num, "color": col_val},
            opts=call_opts,
        )
        after = await self.get_color(num)
        return verify_mutation(
            "patterns.setPatternColor",
            col_val,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"pattern": num},
            journal=self._session.safety.journal,
            remedy="Ensure color is valid 24-bit RGB integer.",
        )

    async def get_length(self, index: int | Pattern) -> int:
        """Retrieve pattern length in steps or ticks."""
        num = _resolve_pattern_number(index)
        res = await self._session.call("patterns.getPatternLength", {"index": num})
        return int(res) if res is not None else 64

    async def set_active(
        self,
        index: int | Pattern,
        *,
        expect: int | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Select active pattern (1-based) with read-back verification."""
        num = _resolve_pattern_number(index)
        before = await self.get_active_number()

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = int(expect)
                guard = build_expect_guard(
                    "patterns.jumpToPattern", "patterns.patternNumber", [], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for patterns.jumpToPattern: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "patterns.jumpToPattern",
            {"index": num},
            opts=call_opts,
        )
        after = await self.get_active_number()
        return verify_mutation(
            "patterns.jumpToPattern",
            num,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"requested": num},
            journal=self._session.safety.journal,
            remedy="Check whether pattern index exceeds patternCount.",
        )

    async def jump(
        self,
        index: int | Pattern,
        *,
        expect: int | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Jump to target pattern (alias for set_active)."""
        return await self.set_active(index, expect=expect, strict=strict)

    async def clear(
        self,
        index: int | Pattern,
        *,
        expect: Any = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Clear notes and automation data in pattern."""
        num = _resolve_pattern_number(index)
        await self._session.call("patterns.clearPattern", {"index": num})
        return Verified(
            value=True,
            requested=True,
            verified=True,
            plane="live",
            settled=True,
            proof="none",
            fp=self._session.fp,
            evidence={"pattern": num},
        )

    async def get_active(self) -> Pattern:
        """Retrieve active pattern snapshot as a Pattern object."""
        num = await self.get_active_number()
        name = await self.get_name(num)
        color = await self.get_color(num)
        length = await self.get_length(num)
        return Pattern(number=num, name=name, color=color, length=length)

    async def list(self) -> list[Pattern]:
        """Retrieve list of Pattern objects for all patterns in project."""
        total = await self.count()
        patterns: list[Pattern] = []
        for i in range(1, total + 1):
            name = await self.get_name(i)
            color = await self.get_color(i)
            length = await self.get_length(i)
            patterns.append(Pattern(number=i, name=name, color=color, length=length))
        return patterns

    async def find(self, name: str) -> Pattern:
        """Find pattern by name.

        Args:
            name: Pattern name to look up.

        Returns:
            Resolved Pattern handle.

        Raises:
            AmbiguousRefError: When multiple patterns match name.
            BadRefError: When no pattern matches name.
        """
        patterns = await self.list()
        return resolve_reference(
            patterns,
            name,
            name_accessor=lambda p: p.name,
            entity_type="pattern",
        )


class SyncPatterns:
    """Synchronous FL Studio pattern interface wrapping AsyncPatterns via BlockingPortal."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_patterns: AsyncPatterns,
        session: Session | None = None,
    ) -> None:
        self._portal = portal
        self._async = async_patterns
        self._session = session

    def _check_connection(self) -> None:
        if self._session is not None and not self._session.is_connected:
            raise DisconnectedError(
                "Cannot issue pattern operation: Session is disconnected.",
                code="E_DISCONNECTED",
                remedy="Establish session connection before calling pattern operations.",
            )

    def count(self) -> int:
        """Retrieve total count of patterns in project."""
        self._check_connection()
        return self._portal.call(self._async.count)

    def get_active(self) -> Pattern:
        """Retrieve active pattern snapshot as a Pattern object."""
        self._check_connection()
        return self._portal.call(self._async.get_active)

    def list(self) -> list[Pattern]:
        """Retrieve list of Pattern objects for all patterns in project."""
        self._check_connection()
        return self._portal.call(self._async.list)

    def find(self, name: str) -> Pattern:
        """Find pattern by name."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.find, name))

    def get_active_number(self) -> int:
        """Retrieve 1-based index of currently active pattern."""
        self._check_connection()
        return self._portal.call(self._async.get_active_number)

    def set_active(
        self,
        index: int | Pattern,
        *,
        expect: int | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Select active pattern (1-based) with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_active, index, expect=expect, strict=strict)
        )

    def jump(
        self,
        index: int | Pattern,
        *,
        expect: int | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Jump to target pattern (alias for set_active)."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.jump, index, expect=expect, strict=strict)
        )

    def get_name(self, index: int | Pattern) -> UntrustedString | str:
        """Retrieve pattern label tagged with untrusted metadata."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_name, index))

    def set_name(
        self,
        index: int | Pattern,
        name: str,
        *,
        expect: str | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[str]:
        """Set pattern name with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_name, index, name, expect=expect, strict=strict)
        )

    def get_color(self, index: int | Pattern) -> int:
        """Retrieve pattern RGB color integer."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_color, index))

    def set_color(
        self,
        index: int | Pattern,
        color: int | Color | str | tuple[int, int, int],
        *,
        expect: int | Color | str | tuple[int, int, int] | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set pattern RGB color with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_color, index, color, expect=expect, strict=strict)
        )

    def clear(
        self,
        index: int | Pattern,
        *,
        expect: Any = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Clear notes and automation data in pattern."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.clear, index, expect=expect, strict=strict)
        )

    def get_length(self, index: int | Pattern) -> int:
        """Retrieve pattern length in steps or ticks."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_length, index))


__all__ = [
    "AsyncPatterns",
    "SyncPatterns",
]
