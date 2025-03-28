from typing import Any, Optional, Dict, List
import json
from datetime import datetime, date
from upstash_redis import Redis
from app.core.config import settings
from pydantic import BaseModel


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


class RedisClient:
    def __init__(self):
        self.redis = Redis(
            url=settings.REDIS_URL,
            token=settings.REDIS_TOKEN
        )

    async def get(self, key: str) -> Optional[Any]:
        value = self.redis.get(key)
        if value is None:
            return None

        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> None:
        """Set value in Redis with optional expiration, serializing to JSON if needed."""
        if isinstance(value, BaseModel):
            if hasattr(value, "model_dump"):
                value = value.model_dump()
            else:
                value = value.dict()
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value, cls=DateTimeEncoder)

        if expire:
            self.redis.setex(key, expire, value)
        else:
            self.redis.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete a key from Redis."""
        self.redis.delete(key)

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching a pattern.
        Note: Upstash doesn't support pattern deletion directly,
        so we handle it by getting keys first."""
        keys = self.redis.keys(pattern)
        if keys:
            for key in keys:
                self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        return bool(self.redis.exists(key))

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a value in Redis."""
        return self.redis.incrby(key, amount)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set a timeout on a key."""
        return bool(self.redis.expire(key, seconds))

    async def ttl(self, key: str) -> int:
        """Get the time to live for a key in seconds."""
        return self.redis.ttl(key)

    async def hset(self, name: str, key: str, value: Any) -> int:
        """Set a hash field to a value."""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        return self.redis.hset(name, key, value)

    async def hget(self, name: str, key: str) -> Any:
        """Get the value of a hash field."""
        value = self.redis.hget(name, key)
        if value is None:
            return None

        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value

    async def hmget(self, name: str, keys: List[str]) -> List[Any]:
        """Get the values of multiple hash fields."""
        values = self.redis.hmget(name, keys)
        result = []

        for value in values:
            if value is None:
                result.append(None)
                continue

            try:
                result.append(json.loads(value))
            except (TypeError, json.JSONDecodeError):
                result.append(value)

        return result

    async def hgetall(self, name: str) -> Dict[str, Any]:
        """Get all fields and values in a hash."""
        values = self.redis.hgetall(name)
        if not values:
            return {}

        result = {}
        for key, value in values.items():
            try:
                result[key] = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                result[key] = value

        return result


def get_redis() -> RedisClient:
    return RedisClient()
