"""
Production caching module for performance optimization
"""
import time
import json
from typing import Any, Optional, Dict
from functools import wraps
from pathlib import Path

class ProductionCache:
    """Production-ready caching system"""
    
    def __init__(self, cache_dir: str = "/tmp/serverbond-cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.memory_cache = {}
        self.cache_ttl = {
            "container_status": 30,  # 30 seconds
            "system_status": 60,    # 1 minute
            "site_list": 120,       # 2 minutes
            "config": 300,          # 5 minutes
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            # Check memory cache first
            if key in self.memory_cache:
                data, timestamp = self.memory_cache[key]
                if time.time() - timestamp < self.cache_ttl.get(key, 60):
                    return data
                else:
                    del self.memory_cache[key]
            
            # Check file cache
            cache_file = self.cache_dir / f"{key}.json"
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                if time.time() - cache_data['timestamp'] < self.cache_ttl.get(key, 60):
                    # Update memory cache
                    self.memory_cache[key] = (cache_data['data'], cache_data['timestamp'])
                    return cache_data['data']
                else:
                    cache_file.unlink()  # Remove expired cache
            
            return None
        except Exception:
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            timestamp = time.time()
            ttl = ttl or self.cache_ttl.get(key, 60)
            
            # Update memory cache
            self.memory_cache[key] = (value, timestamp)
            
            # Update file cache
            cache_file = self.cache_dir / f"{key}.json"
            cache_data = {
                'data': value,
                'timestamp': timestamp,
                'ttl': ttl
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
            
            return True
        except Exception:
            return False
    
    def invalidate(self, key: str) -> bool:
        """Invalidate cache entry"""
        try:
            # Remove from memory
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            # Remove from file
            cache_file = self.cache_dir / f"{key}.json"
            if cache_file.exists():
                cache_file.unlink()
            
            return True
        except Exception:
            return False
    
    def clear(self) -> bool:
        """Clear all cache"""
        try:
            self.memory_cache.clear()
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            return True
        except Exception:
            return False

# Global cache instance
cache = ProductionCache()

def cached(key: str, ttl: Optional[int] = None):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key}_{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator

def invalidate_cache(pattern: str):
    """Invalidate cache entries matching pattern"""
    try:
        for cache_file in cache.cache_dir.glob(f"{pattern}*.json"):
            cache_file.unlink()
        
        # Remove from memory cache
        keys_to_remove = [k for k in cache.memory_cache.keys() if k.startswith(pattern)]
        for key in keys_to_remove:
            del cache.memory_cache[key]
        
        return True
    except Exception:
        return False
