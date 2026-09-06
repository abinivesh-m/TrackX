"""Distributed Redis caching layer."""

import redis
import json
import logging
from typing import Optional, Any
from functools import wraps
import time

logger = logging.getLogger(__name__)

class CacheManager:
    """Redis cache with fallback to in-memory."""
    
    def __init__(self, redis_url: Optional[str] = None, ttl: int = 300):
        self.redis_client = None
        self.ttl = ttl
        self.memory_cache = {}
        
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("Redis connected")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using in-memory cache")
                self.redis_client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            if self.redis_client:
                val = self.redis_client.get(key)
                if val:
                    return json.loads(val)
            else:
                return self.memory_cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL."""
        try:
            ttl = ttl or self.ttl
            val = json.dumps(value)
            if self.redis_client:
                self.redis_client.setex(key, ttl, val)
            else:
                self.memory_cache[key] = value
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            elif key in self.memory_cache:
                del self.memory_cache[key]
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        count = 0
        try:
            if self.redis_client:
                for key in self.redis_client.scan_iter(match=pattern):
                    self.redis_client.delete(key)
                    count += 1
            else:
                keys_to_del = [k for k in self.memory_cache.keys() if pattern.replace("*", "") in k]
                for k in keys_to_del:
                    del self.memory_cache[k]
                    count += 1
            return count
        except Exception as e:
            logger.error(f"Cache pattern clear error: {e}")
            return 0


# Global cache instance
_cache_manager: Optional[CacheManager] = None

def init_cache(redis_url: Optional[str] = None) -> CacheManager:
    """Initialize cache."""
    global _cache_manager
    _cache_manager = CacheManager(redis_url=redis_url)
    return _cache_manager

def get_cache() -> CacheManager:
    """Get cache instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager

def cached(key_prefix: str, ttl: int = 300):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cache = get_cache()
            cached_val = cache.get(cache_key)
            if cached_val is not None:
                return cached_val
            
            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result
        
        return wrapper
    return decorator
