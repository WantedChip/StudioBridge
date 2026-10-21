"""Project metadata and save management namespace for StudioBridge Python SDK.

Provides high-level typed project controllers (AsyncProject and SyncProject)
mounted on AsyncStudio.project and Studio.project per spec 09_l1_sdk.md §4, §5.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import (
    DisconnectedError,
    ProtectedTargetError,
    ReadOnlyError,
)
from studiobridge.sdk.types import ProjectInfo, Verified

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


class AsyncProject:
    """Asynchronous FL Studio project metadata and save management interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_title(self) -> str:
        """Retrieve project title / song name."""
        res = await self._session.call("project.getTitle", {})
        return str(res) if res is not None else ""

    async def get_author(self) -> str:
        """Retrieve project author metadata."""
        res = await self._session.call("project.getAuthor", {})
        return str(res) if res is not None else ""

    async def get_comment(self) -> str:
        """Retrieve project comments / notes metadata."""
        res = await self._session.call("project.getComment", {})
        return str(res) if res is not None else ""

    async def is_dirty(self) -> bool:
        """Query whether active project has unsaved modifications."""
        res = await self._session.call("project.isDirty", {})
        return bool(res) if res is not None else False

    async def info(self) -> ProjectInfo:
        """Return a structured ProjectInfo snapshot containing project metadata."""
        title = await self.get_title()
        author = await self.get_author()
        comment = await self.get_comment()
        dirty = await self.is_dirty()
        return ProjectInfo(
            title=title,
            author=author,
            comment=comment,
            is_dirty=dirty,
        )

    async def save(
        self,
        *,
        confirm: bool = False,
        allow_overwrite: bool = False,
    ) -> Verified[bool]:
        """Save project to current file.

        Requires explicit confirmation (confirm=True or allow_overwrite=True) and
        write safety mode to prevent unprompted file overwrites per [SAF-01] and [SAF-03].
        """
        # 1. Enforce read-only safety guard [SAF-01]
        if self._session.mode == "read_only":
            raise ReadOnlyError(
                "Cannot execute project.save(): active session safety mode is 'read_only'. "
                "Mutating operations require write safety mode.",
                code="E_READONLY",
                details={"mode": self._session.mode},
                remedy="Acquire writer lease and set mode to 'write' via fl.safety.set_mode().",
            )

        # 2. Enforce explicit overwrite confirmation [SAF-03]
        if not (confirm or allow_overwrite):
            raise ProtectedTargetError(
                "Project save requires explicit confirmation ([SAF-01], [SAF-03]). "
                "Pass confirm=True or allow_overwrite=True.",
                code="E_PROTECTED",
                details={
                    "target": "project.save",
                    "confirm": confirm,
                    "allow_overwrite": allow_overwrite,
                },
                remedy=(
                    "Call fl.project.save(confirm=True) to confirm overwrite, "
                    "or prefer fl.project.save_new_version()."
                ),
            )

        await self._session.call("project.save", {})
        return Verified(
            value=True,
            requested=True,
            verified=True,
            plane="live",
            settled=True,
            proof="display_only",
            fp=self._session.fp,
            evidence={"confirmed": True},
        )

    async def save_new_version(self) -> Verified[bool]:
        """Save project as a new non-destructive version per [SAF-03] (preferred over save)."""
        if self._session.mode == "read_only":
            raise ReadOnlyError(
                "Cannot execute project.save_new_version(): safety mode is 'read_only'.",
                code="E_READONLY",
                details={"mode": self._session.mode},
                remedy="Acquire writer lease and set mode to 'write' via fl.safety.set_mode().",
            )

        await self._session.call("project.saveNewVersion", {})
        return Verified(
            value=True,
            requested=True,
            verified=True,
            plane="live",
            settled=True,
            proof="display_only",
            fp=self._session.fp,
            evidence={"new_version": True},
        )


class SyncProject:
    """Synchronous FL Studio project interface wrapping AsyncProject."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_project: AsyncProject,
        *,
        session: Session | None = None,
    ) -> None:
        self._portal = portal
        self._async = async_project
        self._session = session

    def _check_connection(self) -> None:
        if self._session is not None and not self._session.is_connected:
            raise DisconnectedError(
                "Cannot issue project operation: Session is disconnected.",
                code="E_DISCONNECTED",
                remedy="Establish session connection before invoking project methods.",
            )

    def get_title(self) -> str:
        """Retrieve project title / song name."""
        self._check_connection()
        return self._portal.call(self._async.get_title)

    def get_author(self) -> str:
        """Retrieve project author metadata."""
        self._check_connection()
        return self._portal.call(self._async.get_author)

    def get_comment(self) -> str:
        """Retrieve project comments / notes metadata."""
        self._check_connection()
        return self._portal.call(self._async.get_comment)

    def is_dirty(self) -> bool:
        """Query whether active project has unsaved modifications."""
        self._check_connection()
        return self._portal.call(self._async.is_dirty)

    def info(self) -> ProjectInfo:
        """Return a structured ProjectInfo snapshot containing project metadata."""
        self._check_connection()
        return self._portal.call(self._async.info)

    def save(
        self,
        *,
        confirm: bool = False,
        allow_overwrite: bool = False,
    ) -> Verified[bool]:
        """Save project to current file with confirmation guard."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.save,
                confirm=confirm,
                allow_overwrite=allow_overwrite,
            )
        )

    def save_new_version(self) -> Verified[bool]:
        """Save project as a new non-destructive version."""
        self._check_connection()
        return self._portal.call(self._async.save_new_version)


__all__ = [
    "AsyncProject",
    "SyncProject",
]
