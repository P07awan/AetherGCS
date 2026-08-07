"""Command history logger – append-only log stored in MongoDB."""
from __future__ import annotations

from typing import List

from .db import get_db
from .models import CommandLog


class CommandLogStore:
    COLLECTION = "command_history"
    MAX_LOG = 500

    def __init__(self) -> None:
        self._history: List[CommandLog] = []

    async def add(self, entry: CommandLog) -> None:
        self._history.insert(0, entry)
        if len(self._history) > self.MAX_LOG:
            self._history = self._history[:self.MAX_LOG]
        try:
            await get_db()[self.COLLECTION].insert_one(entry.model_dump())
        except Exception:
            pass

    async def list(self, limit: int = 200) -> List[CommandLog]:
        try:
            docs = (
                await get_db()[self.COLLECTION]
                .find({}, {"_id": 0})
                .sort("ts", -1)
                .to_list(limit)
            )
            if docs:
                return [CommandLog(**d) for d in docs]
        except Exception:
            pass
        return self._history[:limit]

    async def clear(self) -> None:
        self._history.clear()
        try:
            await get_db()[self.COLLECTION].delete_many({})
        except Exception:
            pass

