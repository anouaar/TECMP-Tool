#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_controller.py - TECMP-Tool Memory Management Controller
=============================================================

Professional memory management system for TECMP-Tool.
Handles memory optimization, resource pooling, and monitoring.

Features:
- Intelligent packet pooling and recycling
- Memory usage monitoring and limits
- Cache management across components
- Automatic cleanup and garbage collection
- Memory leak detection
- Performance profiling
- Thread-safe operations
"""

import gc
import sys
import time
import psutil
import weakref
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Callable, Type
from enum import Enum, auto
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime
import tracemalloc
import logging

# Qt imports with fallbacks
try:
    from PyQt5.QtCore import QObject, pyqtSignal, QTimer
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    QObject = object
    
    def pyqtSignal(*args):
        class Signal:
            def emit(self, *args, **kwargs):
                pass
            def connect(self, func):
                pass
        return Signal()

# Import TECMP components
try:
    from core.interfaces.controllers.core.error_handler import (
        get_error_handler, handle_errors, ErrorCategory
    )
    ERROR_HANDLER_AVAILABLE = True
except ImportError:
    ERROR_HANDLER_AVAILABLE = False
    
    def handle_errors(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# ============================================================================
# MEMORY TRACKING STRUCTURES
# ============================================================================

class MemoryZone(Enum):
    """Memory zones for different component types"""
    PACKETS = auto()
    CACHE = auto()
    BUFFERS = auto()
    TEMPORARY = auto()
    PERSISTENT = auto()
    SHARED = auto()

@dataclass
class MemoryAllocation:
    """Track individual memory allocation"""
    zone: MemoryZone
    size: int
    timestamp: float
    object_type: str
    weak_ref: Optional[weakref.ref] = None
    stack_trace: Optional[str] = None
    
    @property
    def is_alive(self) -> bool:
        """Check if allocation is still alive"""
        return self.weak_ref is not None and self.weak_ref() is not None

@dataclass
class MemoryStats:
    """Memory statistics"""
    total_allocated: int = 0
    total_freed: int = 0
    current_usage: int = 0
    peak_usage: int = 0
    allocations_count: int = 0
    frees_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    pool_hits: int = 0
    pool_misses: int = 0
    gc_collections: int = 0
    last_gc_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_allocated_mb': self.total_allocated / 1024 / 1024,
            'total_freed_mb': self.total_freed / 1024 / 1024,
            'current_usage_mb': self.current_usage / 1024 / 1024,
            'peak_usage_mb': self.peak_usage / 1024 / 1024,
            'allocations_count': self.allocations_count,
            'frees_count': self.frees_count,
            'cache_efficiency': (self.cache_hits / (self.cache_hits + self.cache_misses) * 100) 
                              if (self.cache_hits + self.cache_misses) > 0 else 0,
            'pool_efficiency': (self.pool_hits / (self.pool_hits + self.pool_misses) * 100)
                             if (self.pool_hits + self.pool_misses) > 0 else 0,
            'gc_collections': self.gc_collections
        }

@dataclass
class MemoryLimit:
    """Memory limit configuration"""
    zone: MemoryZone
    soft_limit: int  # Warning threshold
    hard_limit: int  # Maximum allowed
    action: str = "warn"  # warn, gc, reject
    
# ============================================================================
# OBJECT POOLS
# ============================================================================

class ObjectPool:
    """Generic object pool for recycling"""
    
    def __init__(self, object_type: Type, max_size: int = 1000,
                 initializer: Optional[Callable] = None):
        """
        Initialize object pool
        
        Args:
            object_type: Type of objects to pool
            max_size: Maximum pool size
            initializer: Optional initialization function
        """
        self.object_type = object_type
        self.max_size = max_size
        self.initializer = initializer
        self._pool: deque = deque()
        self._lock = threading.RLock()
        self.stats = {
            'created': 0,
            'recycled': 0,
            'returned': 0,
            'discarded': 0
        }
    
    def acquire(self, **kwargs) -> Any:
        """Acquire object from pool or create new"""
        with self._lock:
            if self._pool:
                obj = self._pool.popleft()
                self.stats['recycled'] += 1
                
                # Reinitialize if needed
                if self.initializer:
                    self.initializer(obj, **kwargs)
                
                return obj
            else:
                # Create new object
                obj = self.object_type(**kwargs)
                self.stats['created'] += 1
                return obj
    
    def release(self, obj: Any):
        """Return object to pool"""
        with self._lock:
            if len(self._pool) < self.max_size:
                # Reset object state
                if hasattr(obj, 'reset'):
                    obj.reset()
                elif hasattr(obj, 'clear'):
                    obj.clear()
                
                self._pool.append(obj)
                self.stats['returned'] += 1
            else:
                # Pool full, discard
                self.stats['discarded'] += 1
    
    def clear(self):
        """Clear pool"""
        with self._lock:
            self._pool.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics"""
        with self._lock:
            return {
                **self.stats,
                'pool_size': len(self._pool)
            }

# ============================================================================
# CACHE MANAGER
# ============================================================================

class CacheManager:
    """Centralized cache management"""
    
    def __init__(self, default_ttl: int = 300, max_memory: int = 100 * 1024 * 1024):
        """
        Initialize cache manager
        
        Args:
            default_ttl: Default time-to-live in seconds
            max_memory: Maximum memory for caches in bytes
        """
        self.default_ttl = default_ttl
        self.max_memory = max_memory
        self._caches: Dict[str, Dict[str, Any]] = {}
        self._cache_metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._total_size = 0
        
    def create_cache(self, name: str, ttl: Optional[int] = None,
                    max_size: Optional[int] = None) -> bool:
        """Create named cache"""
        with self._lock:
            if name in self._caches:
                return False
            
            self._caches[name] = {}
            self._cache_metadata[name] = {
                'ttl': ttl or self.default_ttl,
                'max_size': max_size,
                'created': time.time(),
                'hits': 0,
                'misses': 0,
                'evictions': 0
            }
            return True
    
    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if cache_name not in self._caches:
                return None
            
            cache = self._caches[cache_name]
            metadata = self._cache_metadata[cache_name]
            
            if key in cache:
                entry = cache[key]
                
                # Check TTL
                if time.time() - entry['timestamp'] > metadata['ttl']:
                    del cache[key]
                    metadata['misses'] += 1
                    return None
                
                metadata['hits'] += 1
                return entry['value']
            
            metadata['misses'] += 1
            return None
    
    def put(self, cache_name: str, key: str, value: Any,
            size: Optional[int] = None) -> bool:
        """Put value in cache"""
        with self._lock:
            if cache_name not in self._caches:
                return False
            
            cache = self._caches[cache_name]
            metadata = self._cache_metadata[cache_name]
            
            # Calculate size if not provided
            if size is None:
                size = sys.getsizeof(value)
            
            # Check memory limit
            if self._total_size + size > self.max_memory:
                self._evict_lru(size)
            
            # Check cache size limit
            if metadata['max_size'] and len(cache) >= metadata['max_size']:
                self._evict_oldest(cache_name)
                metadata['evictions'] += 1
            
            cache[key] = {
                'value': value,
                'timestamp': time.time(),
                'size': size
            }
            
            self._total_size += size
            return True
    
    def invalidate(self, cache_name: str, key: Optional[str] = None):
        """Invalidate cache entries"""
        with self._lock:
            if cache_name not in self._caches:
                return
            
            if key:
                # Invalidate specific key
                cache = self._caches[cache_name]
                if key in cache:
                    self._total_size -= cache[key]['size']
                    del cache[key]
            else:
                # Invalidate entire cache
                cache = self._caches[cache_name]
                for entry in cache.values():
                    self._total_size -= entry['size']
                cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            stats = {
                'total_size_mb': self._total_size / 1024 / 1024,
                'cache_count': len(self._caches),
                'caches': {}
            }
            
            for name, metadata in self._cache_metadata.items():
                cache = self._caches[name]
                total_hits = metadata['hits']
                total_misses = metadata['misses']
                
                stats['caches'][name] = {
                    'size': len(cache),
                    'hits': total_hits,
                    'misses': total_misses,
                    'hit_rate': (total_hits / (total_hits + total_misses) * 100)
                               if (total_hits + total_misses) > 0 else 0,
                    'evictions': metadata['evictions']
                }
            
            return stats
    
    def _evict_lru(self, required_size: int):
        """Evict least recently used entries"""
        # Simple implementation - can be optimized
        candidates = []
        
        for cache_name, cache in self._caches.items():
            for key, entry in cache.items():
                candidates.append((
                    entry['timestamp'],
                    cache_name,
                    key,
                    entry['size']
                ))
        
        # Sort by timestamp (oldest first)
        candidates.sort(key=lambda x: x[0])
        
        freed = 0
        for timestamp, cache_name, key, size in candidates:
            if freed >= required_size:
                break
            
            cache = self._caches[cache_name]
            if key in cache:
                del cache[key]
                freed += size
                self._cache_metadata[cache_name]['evictions'] += 1
        
        self._total_size -= freed
    
    def _evict_oldest(self, cache_name: str):
        """Evict oldest entry from cache"""
        cache = self._caches[cache_name]
        if not cache:
            return
        
        oldest_key = None
        oldest_time = float('inf')
        
        for key, entry in cache.items():
            if entry['timestamp'] < oldest_time:
                oldest_time = entry['timestamp']
                oldest_key = key
        
        if oldest_key:
            self._total_size -= cache[oldest_key]['size']
            del cache[oldest_key]

# ============================================================================
# MAIN MEMORY CONTROLLER
# ============================================================================

class MemoryController(QObject if QT_AVAILABLE else object):
    """
    Comprehensive memory management controller for TECMP-Tool
    
    Features:
    - Memory tracking and monitoring
    - Object pooling for common types
    - Centralized cache management
    - Memory limit enforcement
    - Leak detection
    - Performance profiling
    - Automatic cleanup
    """
    
    # Qt signals
    if QT_AVAILABLE:
        memory_warning = pyqtSignal(str, float)  # zone, usage_percent
        memory_critical = pyqtSignal(str, float)
        memory_stats_updated = pyqtSignal(dict)
        gc_triggered = pyqtSignal(int)  # objects_collected
        leak_detected = pyqtSignal(str, int)  # description, size
    
    def __init__(self, facade=None, enable_profiling: bool = False,
                 gc_threshold: float = 0.8):
        """
        Initialize memory controller
        
        Args:
            facade: TECMP facade instance
            enable_profiling: Enable memory profiling
            gc_threshold: Memory usage threshold for GC
        """
        if QT_AVAILABLE:
            super().__init__()
        
        self.facade = facade
        self.logger = logging.getLogger("TECMP-Tool.Memory")
        self.enable_profiling = enable_profiling
        self.gc_threshold = gc_threshold
        
        # Error handler integration
        self.error_handler = get_error_handler() if ERROR_HANDLER_AVAILABLE else None
        
        # Memory tracking
        self._allocations: Dict[int, MemoryAllocation] = {}
        self._stats = MemoryStats()
        self._zone_stats: Dict[MemoryZone, MemoryStats] = defaultdict(MemoryStats)
        self._lock = threading.RLock()
        
        # Memory limits
        self._limits: Dict[MemoryZone, MemoryLimit] = {}
        self._setup_default_limits()
        
        # Object pools
        self._pools: Dict[str, ObjectPool] = {}
        self._setup_default_pools()
        
        # Cache manager
        self.cache_manager = CacheManager()
        self._setup_default_caches()
        
        # Weak references for leak detection
        self._tracked_objects: weakref.WeakSet = weakref.WeakSet()
        self._object_counts: Dict[str, int] = defaultdict(int)
        
        # Monitoring
        self._monitor_timer = None
        self._monitor_interval = 10  # seconds
        self._last_gc_time = time.time()
        
        # Process info
        self._process = psutil.Process()
        self._initial_memory = self._process.memory_info().rss
        
        # Start profiling if enabled
        if enable_profiling:
            tracemalloc.start()
        
        # Start monitoring if Qt available
        if QT_AVAILABLE:
            self._start_monitoring()
        
        self.logger.info("MemoryController initialized")
    
    def _setup_default_limits(self):
        """Setup default memory limits"""
        # Get system memory
        total_memory = psutil.virtual_memory().total
        
        # Conservative limits (adjust based on needs)
        self._limits[MemoryZone.PACKETS] = MemoryLimit(
            zone=MemoryZone.PACKETS,
            soft_limit=int(total_memory * 0.3),  # 30% for packets
            hard_limit=int(total_memory * 0.5),  # 50% max
            action="gc"
        )
        
        self._limits[MemoryZone.CACHE] = MemoryLimit(
            zone=MemoryZone.CACHE,
            soft_limit=100 * 1024 * 1024,  # 100 MB
            hard_limit=500 * 1024 * 1024,  # 500 MB
            action="evict"
        )
        
        self._limits[MemoryZone.TEMPORARY] = MemoryLimit(
            zone=MemoryZone.TEMPORARY,
            soft_limit=50 * 1024 * 1024,   # 50 MB
            hard_limit=200 * 1024 * 1024,  # 200 MB
            action="clear"
        )
    
    def _setup_default_pools(self):
        """Setup default object pools"""
        # Pool for common packet types
        if self.facade:
            try:
                # TECMP packet pool
                from core.packets.tecmp.tecmp_packet import TECMPPacket
                self._pools['tecmp_packet'] = ObjectPool(
                    TECMPPacket,
                    max_size=1000
                )
            except ImportError:
                pass
        
        # Pool for byte arrays
        self._pools['bytearray'] = ObjectPool(
            bytearray,
            max_size=500,
            initializer=lambda ba, size=1024: ba.__init__(size)
        )
        
        # Pool for dictionaries
        self._pools['dict'] = ObjectPool(
            dict,
            max_size=1000
        )
    
    def _setup_default_caches(self):
        """Setup default caches"""
        # Protocol detection cache
        self.cache_manager.create_cache(
            'protocol_detection',
            ttl=3600,  # 1 hour
            max_size=1000
        )
        
        # Packet validation cache
        self.cache_manager.create_cache(
            'validation_results',
            ttl=300,  # 5 minutes
            max_size=500
        )
        
        # Template cache
        self.cache_manager.create_cache(
            'templates',
            ttl=7200,  # 2 hours
            max_size=100
        )
    
    def _start_monitoring(self):
        """Start memory monitoring"""
        if QT_AVAILABLE:
            self._monitor_timer = QTimer()
            self._monitor_timer.timeout.connect(self._monitor_memory)
            self._monitor_timer.start(self._monitor_interval * 1000)
    
    # ========================================================================
    # MEMORY ALLOCATION TRACKING
    # ========================================================================
    
    @handle_errors("Memory", "allocate")
    def allocate(self, size: int, zone: MemoryZone = MemoryZone.TEMPORARY,
                object_ref: Any = None, object_type: str = None) -> int:
        """
        Track memory allocation
        
        Args:
            size: Size in bytes
            zone: Memory zone
            object_ref: Object reference for tracking
            object_type: Type description
            
        Returns:
            Allocation ID
        """
        with self._lock:
            # Check limits
            if not self._check_memory_limit(zone, size):
                raise MemoryError(f"Memory limit exceeded for zone {zone.name}")
            
            # Create allocation record
            alloc_id = id(object_ref) if object_ref else hash(time.time())
            
            allocation = MemoryAllocation(
                zone=zone,
                size=size,
                timestamp=time.time(),
                object_type=object_type or type(object_ref).__name__,
                weak_ref=weakref.ref(object_ref) if object_ref else None,
                stack_trace=traceback.format_stack()[-3] if self.enable_profiling else None
            )
            
            self._allocations[alloc_id] = allocation
            
            # Update statistics
            self._stats.total_allocated += size
            self._stats.current_usage += size
            self._stats.allocations_count += 1
            
            if self._stats.current_usage > self._stats.peak_usage:
                self._stats.peak_usage = self._stats.current_usage
            
            # Update zone statistics
            zone_stats = self._zone_stats[zone]
            zone_stats.total_allocated += size
            zone_stats.current_usage += size
            zone_stats.allocations_count += 1
            
            # Track object
            if object_ref:
                self._tracked_objects.add(object_ref)
                self._object_counts[object_type] += 1
            
            return alloc_id
    
    @handle_errors("Memory", "free")
    def free(self, alloc_id: int):
        """
        Free memory allocation
        
        Args:
            alloc_id: Allocation ID
        """
        with self._lock:
            if alloc_id not in self._allocations:
                return
            
            allocation = self._allocations[alloc_id]
            
            # Update statistics
            self._stats.total_freed += allocation.size
            self._stats.current_usage -= allocation.size
            self._stats.frees_count += 1
            
            # Update zone statistics
            zone_stats = self._zone_stats[allocation.zone]
            zone_stats.total_freed += allocation.size
            zone_stats.current_usage -= allocation.size
            zone_stats.frees_count += 1
            
            # Update object count
            if allocation.object_type in self._object_counts:
                self._object_counts[allocation.object_type] -= 1
            
            # Remove allocation
            del self._allocations[alloc_id]
    
    def track_object(self, obj: Any, zone: MemoryZone = MemoryZone.TEMPORARY):
        """
        Track object for memory management
        
        Args:
            obj: Object to track
            zone: Memory zone
        """
        size = sys.getsizeof(obj)
        alloc_id = self.allocate(size, zone, obj, type(obj).__name__)
        
        # Setup cleanup on deletion
        weakref.finalize(obj, self.free, alloc_id)
    
    # ========================================================================
    # OBJECT POOLING
    # ========================================================================
    
    def acquire_from_pool(self, pool_name: str, **kwargs) -> Any:
        """
        Acquire object from pool
        
        Args:
            pool_name: Pool name
            **kwargs: Arguments for object creation
            
        Returns:
            Object from pool or newly created
        """
        if pool_name not in self._pools:
            self._stats.pool_misses += 1
            return None
        
        pool = self._pools[pool_name]
        obj = pool.acquire(**kwargs)
        
        if pool.stats['recycled'] > pool.stats['created']:
            self._stats.pool_hits += 1
        else:
            self._stats.pool_misses += 1
        
        # Track allocation
        self.track_object(obj, MemoryZone.PACKETS if 'packet' in pool_name else MemoryZone.TEMPORARY)
        
        return obj
    
    def release_to_pool(self, pool_name: str, obj: Any):
        """
        Release object back to pool
        
        Args:
            pool_name: Pool name
            obj: Object to release
        """
        if pool_name not in self._pools:
            return
        
        self._pools[pool_name].release(obj)
    
    def create_pool(self, name: str, object_type: Type,
                   max_size: int = 1000,
                   initializer: Optional[Callable] = None):
        """
        Create new object pool
        
        Args:
            name: Pool name
            object_type: Type of objects
            max_size: Maximum pool size
            initializer: Initialization function
        """
        self._pools[name] = ObjectPool(object_type, max_size, initializer)
        self.logger.info(f"Created object pool: {name}")
    
    # ========================================================================
    # CACHE OPERATIONS
    # ========================================================================
    
    def cache_get(self, cache_name: str, key: str) -> Optional[Any]:
        """Get value from cache"""
        value = self.cache_manager.get(cache_name, key)
        
        if value is not None:
            self._stats.cache_hits += 1
        else:
            self._stats.cache_misses += 1
        
        return value
    
    def cache_put(self, cache_name: str, key: str, value: Any) -> bool:
        """Put value in cache"""
        return self.cache_manager.put(cache_name, key, value)
    
    def cache_invalidate(self, cache_name: str, key: Optional[str] = None):
        """Invalidate cache entries"""
        self.cache_manager.invalidate(cache_name, key)
    
    # ========================================================================
    # MEMORY MANAGEMENT
    # ========================================================================
    
    def _check_memory_limit(self, zone: MemoryZone, additional: int = 0) -> bool:
        """Check if allocation would exceed limits"""
        if zone not in self._limits:
            return True
        
        limit = self._limits[zone]
        zone_stats = self._zone_stats[zone]
        projected_usage = zone_stats.current_usage + additional
        
        if projected_usage > limit.hard_limit:
            # Try to free memory
            if limit.action == "gc":
                self.trigger_gc()
            elif limit.action == "evict":
                self._evict_zone_memory(zone)
            
            # Recheck
            if zone_stats.current_usage + additional > limit.hard_limit:
                return False
        
        elif projected_usage > limit.soft_limit:
            # Emit warning
            if QT_AVAILABLE:
                usage_percent = (projected_usage / limit.hard_limit) * 100
                self.memory_warning.emit(zone.name, usage_percent)
        
        return True
    
    def _evict_zone_memory(self, zone: MemoryZone):
        """Evict memory from specific zone"""
        if zone == MemoryZone.CACHE:
            # Clear oldest cache entries
            required_size = self._zone_stats[zone].current_usage // 4
            self.cache_manager._evict_lru(required_size)
        
        elif zone == MemoryZone.TEMPORARY:
            # Clear temporary allocations
            self.clear_zone(zone)
    
    def clear_zone(self, zone: MemoryZone):
        """Clear all allocations in zone"""
        with self._lock:
            to_remove = []
            
            for alloc_id, allocation in self._allocations.items():
                if allocation.zone == zone:
                    to_remove.append(alloc_id)
            
            for alloc_id in to_remove:
                self.free(alloc_id)
            
            self.logger.info(f"Cleared {len(to_remove)} allocations from zone {zone.name}")
    
    @handle_errors("Memory", "trigger_gc")
    def trigger_gc(self, full: bool = True) -> int:
        """
        Trigger garbage collection
        
        Args:
            full: Perform full collection
            
        Returns:
            Number of objects collected
        """
        self.logger.debug("Triggering garbage collection")
        
        # Clear dead weak references
        self._cleanup_dead_references()
        
        # Run Python GC
        if full:
            collected = gc.collect(2)  # Full collection
        else:
            collected = gc.collect(0)  # Quick collection
        
        # Update stats
        self._stats.gc_collections += 1
        self._stats.last_gc_time = time.time()
        self._last_gc_time = time.time()
        
        # Emit signal
        if QT_AVAILABLE:
            self.gc_triggered.emit(collected)
        
        self.logger.info(f"GC collected {collected} objects")
        return collected
    
    def _cleanup_dead_references(self):
        """Clean up dead weak references"""
        with self._lock:
            dead_allocs = []
            
            for alloc_id, allocation in self._allocations.items():
                if allocation.weak_ref and not allocation.is_alive:
                    dead_allocs.append(alloc_id)
            
            for alloc_id in dead_allocs:
                self.free(alloc_id)
            
            if dead_allocs:
                self.logger.debug(f"Cleaned up {len(dead_allocs)} dead references")
    
    # ========================================================================
    # MONITORING
    # ========================================================================
    
    def _monitor_memory(self):
        """Monitor memory usage"""
        try:
            # Get current memory info
            memory_info = self._process.memory_info()
            current_rss = memory_info.rss
            
            # Check system memory
            system_memory = psutil.virtual_memory()
            
            # Check if we should trigger GC
            if system_memory.percent > self.gc_threshold * 100:
                self.trigger_gc()
            
            # Check for memory leaks
            self._check_for_leaks()
            
            # Update and emit statistics
            stats = self.get_stats()
            
            if QT_AVAILABLE:
                self.memory_stats_updated.emit(stats)
            
            # Log if memory usage is high
            usage_mb = (current_rss - self._initial_memory) / 1024 / 1024
            if usage_mb > 100:  # More than 100MB increase
                self.logger.warning(f"High memory usage: +{usage_mb:.1f} MB")
        
        except Exception as e:
            self.logger.error(f"Error in memory monitoring: {e}")
    
    def _check_for_leaks(self):
        """Check for potential memory leaks"""
        # Simple leak detection based on allocation patterns
        with self._lock:
            # Check for old allocations
            current_time = time.time()
            old_threshold = 3600  # 1 hour
            
            old_allocations = []
            for alloc_id, allocation in self._allocations.items():
                age = current_time - allocation.timestamp
                if age > old_threshold and allocation.zone == MemoryZone.TEMPORARY:
                    old_allocations.append((alloc_id, allocation))
            
            if len(old_allocations) > 100:
                # Potential leak detected
                total_size = sum(alloc.size for _, alloc in old_allocations)
                
                if QT_AVAILABLE:
                    self.leak_detected.emit(
                        f"Found {len(old_allocations)} old temporary allocations",
                        total_size
                    )
                
                self.logger.warning(
                    f"Potential memory leak: {len(old_allocations)} "
                    f"old allocations ({total_size / 1024 / 1024:.1f} MB)"
                )
    
    # ========================================================================
    # STATISTICS AND REPORTING
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        with self._lock:
            # Get process memory
            memory_info = self._process.memory_info()
            
            # Get system memory
            system_memory = psutil.virtual_memory()
            
            stats = {
                'process': {
                    'rss_mb': memory_info.rss / 1024 / 1024,
                    'vms_mb': memory_info.vms / 1024 / 1024,
                    'increase_mb': (memory_info.rss - self._initial_memory) / 1024 / 1024
                },
                'system': {
                    'total_mb': system_memory.total / 1024 / 1024,
                    'available_mb': system_memory.available / 1024 / 1024,
                    'percent': system_memory.percent
                },
                'controller': self._stats.to_dict(),
                'zones': {
                    zone.name: stats.to_dict() 
                    for zone, stats in self._zone_stats.items()
                },
                'pools': {
                    name: pool.get_stats() 
                    for name, pool in self._pools.items()
                },
                'caches': self.cache_manager.get_stats(),
                'objects': dict(self._object_counts)
            }
            
            # Add profiling info if enabled
            if self.enable_profiling and tracemalloc.is_tracing():
                snapshot = tracemalloc.take_snapshot()
                top_stats = snapshot.statistics('lineno')[:10]
                
                stats['profiling'] = {
                    'top_allocations': [
                        {
                            'file': stat.traceback.format()[0],
                            'size_mb': stat.size / 1024 / 1024,
                            'count': stat.count
                        }
                        for stat in top_stats
                    ]
                }
            
            return stats
    
    def get_memory_report(self) -> str:
        """Generate detailed memory report"""
        stats = self.get_stats()
        
        report = [
            "=== TECMP Memory Report ===",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "Process Memory:",
            f"  RSS: {stats['process']['rss_mb']:.1f} MB",
            f"  VMS: {stats['process']['vms_mb']:.1f} MB",
            f"  Increase: {stats['process']['increase_mb']:.1f} MB",
            "",
            "System Memory:",
            f"  Total: {stats['system']['total_mb']:.1f} MB",
            f"  Available: {stats['system']['available_mb']:.1f} MB",
            f"  Usage: {stats['system']['percent']:.1f}%",
            "",
            "Controller Statistics:",
            f"  Current Usage: {stats['controller']['current_usage_mb']:.1f} MB",
            f"  Peak Usage: {stats['controller']['peak_usage_mb']:.1f} MB",
            f"  Allocations: {stats['controller']['allocations_count']}",
            f"  Cache Efficiency: {stats['controller']['cache_efficiency']:.1f}%",
            f"  Pool Efficiency: {stats['controller']['pool_efficiency']:.1f}%",
            "",
            "Zone Usage:"
        ]
        
        for zone_name, zone_stats in stats['zones'].items():
            report.append(f"  {zone_name}:")
            report.append(f"    Current: {zone_stats['current_usage_mb']:.1f} MB")
            report.append(f"    Total: {zone_stats['total_allocated_mb']:.1f} MB")
        
        report.append("")
        report.append("Object Pools:")
        
        for pool_name, pool_stats in stats['pools'].items():
            report.append(f"  {pool_name}:")
            report.append(f"    Created: {pool_stats['created']}")
            report.append(f"    Recycled: {pool_stats['recycled']}")
            report.append(f"    Pool Size: {pool_stats['pool_size']}")
        
        return "\n".join(report)
    
    # ========================================================================
    # OPTIMIZATION
    # ========================================================================
    
    def optimize(self) -> Dict[str, Any]:
        """
        Perform memory optimization
        
        Returns:
            Optimization results
        """
        self.logger.info("Starting memory optimization")
        
        results = {
            'freed_mb': 0,
            'pools_cleared': 0,
            'caches_cleared': 0,
            'gc_collected': 0
        }
        
        # Clear temporary zone
        temp_before = self._zone_stats[MemoryZone.TEMPORARY].current_usage
        self.clear_zone(MemoryZone.TEMPORARY)
        temp_freed = temp_before - self._zone_stats[MemoryZone.TEMPORARY].current_usage
        results['freed_mb'] += temp_freed / 1024 / 1024
        
        # Clear unused pools
        for name, pool in self._pools.items():
            stats = pool.get_stats()
            if stats['pool_size'] > stats['recycled'] * 2:
                pool.clear()
                results['pools_cleared'] += 1
        
        # Clear old cache entries
        for cache_name in ['validation_results', 'protocol_detection']:
            self.cache_manager.invalidate(cache_name)
            results['caches_cleared'] += 1
        
        # Trigger GC
        results['gc_collected'] = self.trigger_gc(full=True)
        
        self.logger.info(f"Optimization complete: {results}")
        return results
    
    # ========================================================================
    # FACADE INTEGRATION
    # ========================================================================
    
    def set_facade(self, facade):
        """Set facade reference"""
        self.facade = facade
        
        # Setup facade-specific pools
        if hasattr(facade, 'factory'):
            # Create pool for facade packets
            self.create_pool(
                'facade_packets',
                type(facade.factory.create_packet()),
                max_size=2000
            )
    
    def cleanup(self):
        """Clean up resources"""
        # Stop monitoring
        if self._monitor_timer and QT_AVAILABLE:
            self._monitor_timer.stop()
        
        # Clear all pools
        for pool in self._pools.values():
            pool.clear()
        
        # Clear all caches
        for cache_name in list(self.cache_manager._caches.keys()):
            self.cache_manager.invalidate(cache_name)
        
        # Stop profiling
        if self.enable_profiling and tracemalloc.is_tracing():
            tracemalloc.stop()
        
        self.logger.info("MemoryController cleanup completed")

# ============================================================================
# DECORATORS
# ============================================================================

def track_memory(zone: MemoryZone = MemoryZone.TEMPORARY):
    """
    Decorator to track memory usage of function results
    
    Usage:
        @track_memory(MemoryZone.PACKETS)
        def create_packet():
            return TECMPPacket()
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Get memory controller
            from core.interfaces.controllers.core.memory_controller import get_memory_controller
            controller = get_memory_controller()
            
            if controller and result is not None:
                controller.track_object(result, zone)
            
            return result
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator

def cached(cache_name: str, key_func: Optional[Callable] = None):
    """
    Decorator for caching function results
    
    Usage:
        @cached('validation_results', key_func=lambda pkt: pkt.id)
        def validate_packet(packet):
            return expensive_validation(packet)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get memory controller
            from core.interfaces.controllers.core.memory_controller import get_memory_controller
            controller = get_memory_controller()
            
            if not controller:
                return func(*args, **kwargs)
            
            # Generate cache key
            if key_func:
                key = str(key_func(*args, **kwargs))
            else:
                key = str((args, tuple(kwargs.items())))
            
            # Check cache
            cached_value = controller.cache_get(cache_name, key)
            if cached_value is not None:
                return cached_value
            
            # Compute and cache
            result = func(*args, **kwargs)
            controller.cache_put(cache_name, key, result)
            
            return result
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator

# ============================================================================
# SINGLETON AND HELPERS
# ============================================================================

_global_memory_controller = None

def get_memory_controller() -> MemoryController:
    """Get or create global memory controller"""
    global _global_memory_controller
    if _global_memory_controller is None:
        _global_memory_controller = MemoryController()
    return _global_memory_controller

def integrate_memory_controller_with_facade(facade) -> MemoryController:
    """
    Integrate memory controller with TECMP facade
    
    Args:
        facade: TECMP facade instance
        
    Returns:
        MemoryController instance
    """
    controller = get_memory_controller()
    controller.set_facade(facade)
    
    # Set as facade memory controller
    if hasattr(facade, 'memory_controller'):
        facade.memory_controller = controller
    
    # Connect signals if Qt available
    if QT_AVAILABLE and hasattr(facade, 'memory_warning'):
        controller.memory_warning.connect(
            lambda zone, percent: facade.memory_warning.emit(
                f"Memory warning: {zone} at {percent:.1f}%"
            )
        )
    
    return controller

# Export public API
__all__ = [
    'MemoryController',
    'MemoryZone',
    'MemoryAllocation',
    'MemoryStats',
    'MemoryLimit',
    'ObjectPool',
    'CacheManager',
    'get_memory_controller',
    'integrate_memory_controller_with_facade',
    'track_memory',
    'cached'
]