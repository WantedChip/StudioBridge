"""Pattern management namespace for StudioBridge Python SDK.

Provides high-level typed pattern controllers (AsyncPatterns and SyncPatterns)
mounted on AsyncStudio.patterns and Studio.patterns per spec 09_l1_sdk.md §4.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, UnverifiedWriteError
from studiobridge.sdk.types import Pattern, Verified

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

    async def get_name(self, index: int | Pattern) -> str:
        """Retrieve pattern label."""
        num = _resolve_pattern_number(index)
        res = await self._session.call("patterns.getPatternName", {"index": num})
        return str(res) if res is not None else ""

    async def set_name(
        self,
        index: int | Pattern,
        name: str,
        *,
        strict: bool = False,
    ) -> Verified[str]:
        """Set pattern name with read-back verification."""
        num = _resolve_pattern_number(index)
        str_val = str(name)
        before = await self.get_name(num)
        await self._session.call("patterns.setPatternName", {"index": num, "name": str_val})
        after = await self.get_name(num)
        verified = after == str_val

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify pattern {num} name: requested {str_val!r}, got {after!r}",
                target_value=str_val,
                actual_value=after,
                details={"pattern": num, "before": before, "after": after},
                remedy="Ensure pattern index exists and name is non-empty.",
            )

        return Verified(
            value=after,
            requested=str_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"pattern": num, "before": before, "after": after},
        )

    async def get_color(self, index: int | Pattern) -> int:
        """Retrieve pattern RGB color integer."""
        num = _resolve_pattern_number(index)
        res = await self._session.call("patterns.getPatternColor", {"index": num})
        return int(res) if res is not None else 0

    async def set_color(
        self,
        index: int | Pattern,
        color: int,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Set pattern RGB color with read-back verification."""
        num = _resolve_pattern_number(index)
        col_val = int(color)
        before = await self.get_color(num)
        await self._session.call("patterns.setPatternColor", {"index": num, "color": col_val})
        after = await self.get_color(num)
        verified = after == col_val

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify pattern {num} color: "
                f"requested 0x{col_val:06X}, got 0x{after:06X}",
                target_value=col_val,
                actual_value=after,
                details={"pattern": num, "before": before, "after": after},
                remedy="Ensure color is valid 24-bit RGB integer.",
            )

        return Verified(
            value=after,
            requested=col_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"pattern": num, "before": before, "after": after},
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
        strict: bool = False,
    ) -> Verified[int]:
        """Select active pattern (1-based) with read-back verification."""
        num = _resolve_pattern_number(index)
        before = await self.get_active_number()
        await self._session.call("patterns.jumpToPattern", {"index": num})
        after = await self.get_active_number()
        verified = after == num

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify active pattern selection: "
                f"requested pattern {num}, active is {after}",
                target_value=num,
                actual_value=after,
                details={"requested": num, "before": before, "after": after},
                remedy="Check whether pattern index exceeds patternCount.",
            )

        return Verified(
            value=after,
            requested=num,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"before": before, "after": after},
        )

    async def jump(
        self,
        index: int | Pattern,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Jump to target pattern (alias for set_active)."""
        return await self.set_active(index, strict=strict)

    async def clear(
        self,
        index: int | Pattern,
        *,
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

    def get_active_number(self) -> int:
        """Retrieve 1-based index of currently active pattern."""
        self._check_connection()
        return self._portal.call(self._async.get_active_number)

    def set_active(
        self,
        index: int | Pattern,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Select active pattern (1-based) with read-back verification."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.set_active, index, strict=strict))

    def jump(
        self,
        index: int | Pattern,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Jump to target pattern (alias for set_active)."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.jump, index, strict=strict))

    def get_name(self, index: int | Pattern) -> str:
        """Retrieve pattern label."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_name, index))

    def set_name(
        self,
        index: int | Pattern,
        name: str,
        *,
        strict: bool = False,
    ) -> Verified[str]:
        """Set pattern name with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_name, index, name, strict=strict)
        )

    def get_color(self, index: int | Pattern) -> int:
        """Retrieve pattern RGB color integer."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_color, index))

    def set_color(
        self,
        index: int | Pattern,
        color: int,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Set pattern RGB color with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_color, index, color, strict=strict)
        )

    def clear(
        self,
        index: int | Pattern,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Clear notes and automation data in pattern."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.clear, index, strict=strict))

    def get_length(self, index: int | Pattern) -> int:
        """Retrieve pattern length in steps or ticks."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_length, index))


__all__ = [
    "AsyncPatterns",
    "SyncPatterns",
]
