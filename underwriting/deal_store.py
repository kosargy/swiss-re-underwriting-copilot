from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class SavedDeal:
    deal_id: str
    name: str
    location: str
    updated_at: str
    payload: dict


class DealStore:
    """Small SQLite repository for local deal snapshots."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS deals (
                        deal_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        location TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )

    def save(
        self,
        *,
        name: str,
        location: str,
        payload: dict,
        deal_id: str | None = None,
    ) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Deal name cannot be empty")
        identifier = deal_id or str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        serialized = json.dumps(payload, ensure_ascii=False)
        with closing(self._connect()) as connection:
            with connection:
                existing = connection.execute(
                    "SELECT created_at FROM deals WHERE deal_id = ?",
                    (identifier,),
                ).fetchone()
                created_at = existing["created_at"] if existing else timestamp
                connection.execute(
                    """
                    INSERT INTO deals (
                        deal_id, name, location, payload_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(deal_id) DO UPDATE SET
                        name = excluded.name,
                        location = excluded.location,
                        payload_json = excluded.payload_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        identifier,
                        clean_name,
                        location.strip(),
                        serialized,
                        created_at,
                        timestamp,
                    ),
                )
        return identifier

    def list(self) -> tuple[SavedDeal, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT deal_id, name, location, payload_json, updated_at
                FROM deals
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return tuple(
            SavedDeal(
                deal_id=row["deal_id"],
                name=row["name"],
                location=row["location"],
                updated_at=row["updated_at"],
                payload=json.loads(row["payload_json"]),
            )
            for row in rows
        )

    def get(self, deal_id: str) -> SavedDeal | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT deal_id, name, location, payload_json, updated_at
                FROM deals
                WHERE deal_id = ?
                """,
                (deal_id,),
            ).fetchone()
        if row is None:
            return None
        return SavedDeal(
            deal_id=row["deal_id"],
            name=row["name"],
            location=row["location"],
            updated_at=row["updated_at"],
            payload=json.loads(row["payload_json"]),
        )
