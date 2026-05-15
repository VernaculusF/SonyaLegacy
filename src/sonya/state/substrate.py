from __future__ import annotations

import sqlite3
from pathlib import Path

from sonya.state.migrations import apply_initial_schema, migrate_to_current, read_current_version


class SubstrateVersionError(RuntimeError):
    """Raised when substrate schema version is incompatible with this reader."""


class Substrate:
    """Persistent substrate of Sonya. Long-lived connection, single owner."""

    WRITABLE_VERSION: int = 2
    READABLE_VERSIONS: frozenset[int] = frozenset({1, 2})

    def __init__(self, path: Path, connection: sqlite3.Connection, version: int) -> None:
        self._path = path
        self._connection = connection
        self._version = version

    @classmethod
    def open(cls, path: Path | str, *, read_only: bool = False) -> "Substrate":
        path = Path(path)
        if read_only:
            if not path.exists():
                raise FileNotFoundError(path)
            uri = f"file:{path.as_posix()}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path)

        version = read_current_version(conn)
        if version == 0 and not read_only:
            apply_initial_schema(conn)
            version = read_current_version(conn)
        elif version > 0 and version < cls.WRITABLE_VERSION and not read_only:
            version = migrate_to_current(conn, version)
        if version not in cls.READABLE_VERSIONS:
            conn.close()
            raise SubstrateVersionError(
                f"Substrate at {path} has schema version {version}, "
                f"reader supports {sorted(cls.READABLE_VERSIONS)}"
            )
        return cls(path, conn, version)

    @property
    def schema_version(self) -> int:
        return self._version

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._connection.close()
