"""MissionManager – CRUD for missions stored in MongoDB."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from .db import get_db
from .models import Mission, MissionCreate, Waypoint


class MissionManager:
    def __init__(self) -> None:
        self._missions: dict[str, Mission] = {}

    async def create(self, data: MissionCreate) -> Mission:
        m = Mission(**data.model_dump())
        self._missions[m.id] = m
        try:
            await get_db().missions.insert_one(m.model_dump())
        except Exception:
            pass
        return m

    async def list(self) -> List[Mission]:
        try:
            docs = await get_db().missions.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
            if docs:
                return [Mission(**d) for d in docs]
        except Exception:
            pass
        return list(self._missions.values())

    async def get(self, mission_id: str) -> Optional[Mission]:
        try:
            doc = await get_db().missions.find_one({"id": mission_id}, {"_id": 0})
            if doc:
                return Mission(**doc)
        except Exception:
            pass
        return self._missions.get(mission_id)

    async def update(self, mission_id: str, data: MissionCreate) -> Optional[Mission]:
        existing = await self.get(mission_id)
        if not existing:
            return None
        updated = Mission(
            id=existing.id,
            name=data.name,
            description=data.description,
            default_altitude=data.default_altitude,
            default_speed=data.default_speed,
            waypoints=data.waypoints,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._missions[mission_id] = updated
        try:
            await get_db().missions.update_one({"id": mission_id}, {"$set": updated.model_dump()})
        except Exception:
            pass
        return updated

    async def delete(self, mission_id: str) -> bool:
        existed = mission_id in self._missions
        self._missions.pop(mission_id, None)
        try:
            res = await get_db().missions.delete_one({"id": mission_id})
            return res.deleted_count > 0
        except Exception:
            return existed

    async def duplicate(self, mission_id: str) -> Optional[Mission]:
        original = await self.get(mission_id)
        if not original:
            return None
        clone = Mission(
            name=f"{original.name} (copy)",
            description=original.description,
            default_altitude=original.default_altitude,
            default_speed=original.default_speed,
            waypoints=original.waypoints,
        )
        self._missions[clone.id] = clone
        try:
            await get_db().missions.insert_one(clone.model_dump())
        except Exception:
            pass
        return clone

