"""Command history logger – append-only log stored in MongoDB."""
from __future__ import annotations

from typing import List

from .db import get_db
from .models import CommandLog


class CommandLogStore:
    COLLECTION = "command_history"
    MAX_LOG = 500

    async def add(self, entry: CommandLog) -> None:
        await get_db()[self.COLLECTION].insert_one(entry.model_dump())

    async def list(self, limit: int = 200) -> List[CommandLog]:
        docs = (
            await get_db()[self.COLLECTION]
            .find({}, {"_id": 0})
            .sort("ts", -1)
            .to_list(limit)
        )
        return [CommandLog(**d) for d in docs]

    async def clear(self) -> None:
        await get_db()[self.COLLECTION].delete_many({})
