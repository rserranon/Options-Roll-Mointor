"""
Greeks caching system to reduce IB API calls.
Caches option Greeks for a configurable TTL (time-to-live).
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import threading


class GreeksCache:
    """Thread-safe cache for option Greeks data."""
    
    def __init__(self, ttl_seconds=60):
        """
        Initialize Greeks cache.
        
        Args:
            ttl_seconds: Time-to-live for cached data in seconds (default: 60)
        """
        self.ttl_seconds = ttl_seconds
        self.cache = {}  # key -> (data, timestamp)
        self.lock = threading.Lock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'expired': 0,
            'total_requests': 0
        }
    
    def _make_key(self, symbol, expiry, strike, right):
        """Create cache key from option parameters."""
        return f"{symbol}_{expiry}_{strike}_{right}"
    
    def get(self, symbol, expiry, strike, right) -> Optional[Dict[str, Any]]:
        """
        Get cached Greeks data if available and not expired.
        
        Args:
            symbol: Underlying symbol
            expiry: Option expiry (YYYYMMDD)
            strike: Strike price
            right: 'C' or 'P'
        
        Returns:
            Cached data dict or None if not found/expired
        """
        self.stats['total_requests'] += 1
        
        key = self._make_key(symbol, expiry, strike, right)
        
        with self.lock:
            if key not in self.cache:
                self.stats['misses'] += 1
                return None
            
            data, timestamp = self.cache[key]
            age = datetime.now() - timestamp
            
            if age.total_seconds() > self.ttl_seconds:
                # Expired - remove from cache
                del self.cache[key]
                self.stats['expired'] += 1
                return None
            
            # Cache hit!
            self.stats['hits'] += 1
            return data.copy()  # Return copy to prevent modifications
    
    def put(self, symbol, expiry, strike, right, data: Dict[str, Any]):
        """
        Store Greeks data in cache.
        
        Args:
            symbol: Underlying symbol
            expiry: Option expiry (YYYYMMDD)
            strike: Strike price
            right: 'C' or 'P'
            data: Greeks data dictionary
        """
        key = self._make_key(symbol, expiry, strike, right)
        
        with self.lock:
            self.cache[key] = (data.copy(), datetime.now())
    
    def clear(self):
        """Clear all cached data."""
        with self.lock:
            self.cache.clear()
    
    def clear_expired(self):
        """Remove all expired entries from cache."""
        now = datetime.now()
        expired_keys = []
        
        with self.lock:
            for key, (data, timestamp) in self.cache.items():
                age = now - timestamp
                if age.total_seconds() > self.ttl_seconds:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            stats = self.stats.copy()
            stats['cache_size'] = len(self.cache)
            
            if stats['total_requests'] > 0:
                stats['hit_rate'] = (stats['hits'] / stats['total_requests']) * 100
            else:
                stats['hit_rate'] = 0.0
            
            return stats
    
    def reset_stats(self):
        """Reset cache statistics."""
        with self.lock:
            self.stats = {
                'hits': 0,
                'misses': 0,
                'expired': 0,
                'total_requests': 0
            }


# Global cache instance
_global_cache = None


def get_cache(ttl_seconds=60) -> GreeksCache:
    """
    Get or create the global cache instance.
    
    Args:
        ttl_seconds: TTL for cached data (only used on first call)
    
    Returns:
        GreeksCache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = GreeksCache(ttl_seconds=ttl_seconds)
    return _global_cache


def clear_global_cache():
    """Clear the global cache."""
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()
