"""UI focus, window visibility, and hint display namespace for StudioBridge Python SDK.

Provides high-level typed UI controllers (AsyncUi and SyncUi)
mounted on AsyncStudio.ui and Studio.ui.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, UnverifiedWriteError
from studiobridge.sdk.types import Verified

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


class AsyncUi:
    """Asynchronous FL Studio user interface interaction interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def is_focused(self, window: int) -> bool:
        """Query whether target window index currently has focus."""
        res = await self._session.call("ui.getFocused", {"window": int(window)})
        return bool(res) if res is not None else False

    async def focus(
        self,
        window: int,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Focus target FL Studio window (0=Mixer, 1=Channel Rack, 2=Playlist, 3=Piano Roll)."""
        win_idx = int(window)
        await self._session.call("ui.setFocused", {"window": win_idx})
        focused = await self.is_focused(win_idx)

        if strict and not focused:
            raise UnverifiedWriteError(
                f"Failed to focus window {win_idx}",
                target_value=True,
                actual_value=focused,
                details={"window": win_idx},
                remedy="Ensure window index is valid and FL Studio is not blocked by a modal.",
            )

        return Verified(
            value=focused,
            requested=True,
            verified=focused,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"window": win_idx, "focused": focused},
        )

    async def is_visible(self, window: int) -> bool:
        """Query whether target window is currently visible."""
        res = await self._session.call("ui.getVisible", {"window": int(window)})
        return bool(res) if res is not None else False

    async def show(
        self,
        window: int,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Show / open target FL Studio window with visibility verification."""
        win_idx = int(window)
        await self._session.call("ui.showWindow", {"window": win_idx})
        visible = await self.is_visible(win_idx)

        if strict and not visible:
            raise UnverifiedWriteError(
                f"Failed to show window {win_idx}",
                target_value=True,
                actual_value=visible,
                details={"window": win_idx},
                remedy="Ensure window index is valid.",
            )

        return Verified(
            value=visible,
            requested=True,
            verified=visible,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"window": win_idx, "visible": visible},
        )

    async def hide(
        self,
        window: int,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Hide / close target FL Studio window with visibility verification."""
        win_idx = int(window)
        await self._session.call("ui.hideWindow", {"window": win_idx})
        visible = await self.is_visible(win_idx)
        hidden = not visible

        if strict and not hidden:
            raise UnverifiedWriteError(
                f"Failed to hide window {win_idx}",
                target_value=True,
                actual_value=hidden,
                details={"window": win_idx},
                remedy="Ensure window index is valid.",
            )

        return Verified(
            value=hidden,
            requested=True,
            verified=hidden,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"window": win_idx, "hidden": hidden},
        )

    async def hint(self, text: str) -> None:
        """Display a hint message in the FL Studio hint panel (top left)."""
        await self._session.call("ui.setHintMsg", {"msg": str(text)})


class SyncUi:
    """Synchronous FL Studio user interface wrapper around AsyncUi."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_ui: AsyncUi,
        *,
        session: Session | None = None,
    ) -> None:
        self._portal = portal
        self._async = async_ui
        self._session = session

    def _check_connection(self) -> None:
        if self._session is not None and not self._session.is_connected:
            raise DisconnectedError(
                "Cannot issue UI operation: Session is disconnected.",
                code="E_DISCONNECTED",
                remedy="Establish session connection before invoking UI methods.",
            )

    def is_focused(self, window: int) -> bool:
        """Query whether target window index currently has focus."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_focused, window))

    def focus(
        self,
        window: int,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Focus target FL Studio window."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.focus, window, strict=strict))

    def is_visible(self, window: int) -> bool:
        """Query whether target window is currently visible."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_visible, window))

    def show(
        self,
        window: int,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Show / open target FL Studio window."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.show, window, strict=strict))

    def hide(
        self,
        window: int,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Hide / close target FL Studio window."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.hide, window, strict=strict))

    def hint(self, text: str) -> None:
        """Display a hint message in the FL Studio hint panel."""
        self._check_connection()
        self._portal.call(functools.partial(self._async.hint, text))


__all__ = [
    "AsyncUi",
    "SyncUi",
]
