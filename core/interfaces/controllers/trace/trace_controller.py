#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TraceController - Enhanced version with continuous flow for TECMP-Tool
=====================================================================

COMPLETE FIXED VERSION - Resolves all stream type enum issues
Comprehensive protection against 'int' object has no attribute 'value' errors
"""

import os
import sys
import time
import logging
import threading
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque, Counter
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty, Full
import struct
import importlib

try:
    from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    QObject = object
    def pyqtSignal(*args, **kwargs):
        return None

# === ENUMS AND DATA STRUCTURES ===

class FlowState(Enum):
    """Data flow states"""
    IDLE = auto()
    INITIALIZING = auto()
    RUNNING = auto()
    PAUSED = auto()
    THROTTLED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()

class StreamType(Enum):
    """Data stream types"""
    ETHERNET = "ethernet"
    CAN = "can"
    CAN_FD = "can_fd"
    FLEXRAY = "flexray"
    LIN = "lin"
    TECMP = "tecmp"
    UART = "uart"
    ANALOG = "analog"
    UNKNOWN = "unknown"

# === UTILITY FUNCTIONS FOR TYPE SAFETY ===

def ensure_stream_type(value) -> StreamType:
    """Ensure any value is converted to StreamType enum safely"""
    if isinstance(value, StreamType):
        return value
    
    if isinstance(value, str):
        try:
            return StreamType(value)
        except ValueError:
            return StreamType.UNKNOWN
    
    if isinstance(value, int):
        # Convert int to StreamType based on common mappings
        int_to_stream = {
            0: StreamType.UNKNOWN,
            1: StreamType.ETHERNET, 
            2: StreamType.CAN,
            3: StreamType.TECMP,
            4: StreamType.FLEXRAY,
            5: StreamType.LIN,
            6: StreamType.UART,
            7: StreamType.ANALOG
        }
        return int_to_stream.get(value, StreamType.UNKNOWN)
    
    return StreamType.UNKNOWN

def get_stream_value(stream_type) -> str:
    """Safely get the value from a StreamType, handling all types"""
    if isinstance(stream_type, StreamType):
        return stream_type.value
    elif isinstance(stream_type, str):
        return stream_type
    elif isinstance(stream_type, int):
        int_to_name = {
            0: "unknown", 1: "ethernet", 2: "can", 3: "tecmp", 
            4: "flexray", 5: "lin", 6: "uart", 7: "analog"
        }
        return int_to_name.get(stream_type, "unknown")
    else:
        return "unknown"

@dataclass
class StreamMetrics:
    """Metrics per stream"""
    stream_type: StreamType
    packets_count: int = 0
    bytes_count: int = 0
    errors_count: int = 0
    last_packet_time: float = 0.0
    packets_per_second: float = 0.0
    bytes_per_second: float = 0.0
    buffer_usage: float = 0.0

@dataclass
class PacketInfo:
    """Packet information"""
    timestamp: float
    stream_type: StreamType
    size: int
    data: bytes
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure stream_type is always StreamType enum"""
        self.stream_type = ensure_stream_type(self.stream_type)

# === CONTINUOUS FLOW COMPONENTS ===

class PacketRingBuffer:
    """Thread-safe circular buffer for high performance"""
    
    def __init__(self, size: int = 100000):
        self.size = size
        self.buffer = [None] * size
        self.write_pos = 0
        self.read_pos = 0
        self.count = 0
        self.lock = threading.RLock()
        self.not_empty = threading.Condition(self.lock)
        self.not_full = threading.Condition(self.lock)
        
    def write(self, packet: PacketInfo, timeout: Optional[float] = None) -> bool:
        """Write a packet to the buffer"""
        # Ensure packet has valid stream_type
        packet.stream_type = ensure_stream_type(packet.stream_type)
        
        with self.not_full:
            while self.count >= self.size:
                if timeout is None:
                    self.not_full.wait()
                elif not self.not_full.wait(timeout):
                    return False
            
            self.buffer[self.write_pos] = packet
            self.write_pos = (self.write_pos + 1) % self.size
            self.count += 1
            self.not_empty.notify()
            return True
    
    def read(self, timeout: Optional[float] = None) -> Optional[PacketInfo]:
        """Read a packet from the buffer"""
        with self.not_empty:
            while self.count == 0:
                if timeout is None:
                    self.not_empty.wait()
                elif not self.not_empty.wait(timeout):
                    return None
            
            packet = self.buffer[self.read_pos]
            # Ensure stream_type is valid when reading
            if packet:
                packet.stream_type = ensure_stream_type(packet.stream_type)
            self.read_pos = (self.read_pos + 1) % self.size
            self.count -= 1
            self.not_full.notify()
            return packet
    
    def read_batch(self, max_count: int = 100) -> List[PacketInfo]:
        """Read multiple packets at once"""
        packets = []
        with self.lock:
            actual_count = min(max_count, self.count)
            for _ in range(actual_count):
                packet = self.buffer[self.read_pos]
                if packet:
                    # Ensure stream_type is valid
                    packet.stream_type = ensure_stream_type(packet.stream_type)
                    packets.append(packet)
                self.read_pos = (self.read_pos + 1) % self.size
                self.count -= 1
            
            if actual_count > 0:
                self.not_full.notify_all()
        
        return packets
    
    def get_usage(self) -> float:
        """Return buffer usage rate (0.0 to 1.0)"""
        with self.lock:
            return self.count / self.size

class StreamManager:
    """Manager for parallel streams"""
    
    def __init__(self, buffer_size: int = 10000):
        self.streams: Dict[StreamType, PacketRingBuffer] = {}
        self.metrics: Dict[StreamType, StreamMetrics] = {}
        self.processors: Dict[StreamType, Callable] = {}
        self.lock = threading.RLock()
        self.logger = logging.getLogger("TECMP-Tool.StreamManager")
        
        # Initialize main streams
        for stream_type in StreamType:
            if stream_type != StreamType.UNKNOWN:
                self.streams[stream_type] = PacketRingBuffer(buffer_size)
                self.metrics[stream_type] = StreamMetrics(stream_type)
    
    def route_packet(self, packet: PacketInfo) -> bool:
        """Route a packet to the correct stream"""
        try:
            # Ensure stream_type is always a StreamType enum
            packet.stream_type = ensure_stream_type(packet.stream_type)
            stream_type = packet.stream_type
            
            if stream_type in self.streams:
                success = self.streams[stream_type].write(packet, timeout=0.1)
                
                if success:
                    with self.lock:
                        metrics = self.metrics[stream_type]
                        metrics.packets_count += 1
                        metrics.bytes_count += packet.size
                        metrics.last_packet_time = packet.timestamp
                
                return success
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error routing packet: {e}")
            return False
    
    def get_stream(self, stream_type: StreamType) -> Optional[PacketRingBuffer]:
        """Get a specific stream"""
        stream_type = ensure_stream_type(stream_type)
        return self.streams.get(stream_type)
    
    def get_all_metrics(self) -> Dict[StreamType, StreamMetrics]:
        """Return all metrics"""
        with self.lock:
            return dict(self.metrics)

class BackpressureManager:
    """Backpressure manager to prevent saturation"""
    
    def __init__(self):
        self.thresholds = {
            'low': 0.3,
            'medium': 0.6,
            'high': 0.8,
            'critical': 0.95
        }
        self.current_level = 'low'
        self.actions = {
            'low': self._action_boost,
            'medium': self._action_maintain,
            'high': self._action_throttle,
            'critical': self._action_pause
        }
        
    def check_pressure(self, buffer_usage: float) -> str:
        """Check pressure level and return action"""
        if buffer_usage >= self.thresholds['critical']:
            self.current_level = 'critical'
        elif buffer_usage >= self.thresholds['high']:
            self.current_level = 'high'
        elif buffer_usage >= self.thresholds['medium']:
            self.current_level = 'medium'
        else:
            self.current_level = 'low'
        
        return self.current_level
    
    def get_action(self) -> Callable:
        """Return action to perform based on level"""
        return self.actions.get(self.current_level, self._action_maintain)
    
    def _action_boost(self):
        return {'action': 'boost', 'delay': 0}
    
    def _action_maintain(self):
        return {'action': 'maintain', 'delay': 0.001}
    
    def _action_throttle(self):
        return {'action': 'throttle', 'delay': 0.01}
    
    def _action_pause(self):
        return {'action': 'pause', 'delay': 0.1}

class ParallelTraceOrganizer:
    """Organizer for parallel traces"""
    
    def __init__(self):
        self.timeline: List[Tuple[float, PacketInfo]] = []
        self.groups: Dict[str, List[PacketInfo]] = defaultdict(list)
        self.correlations: Dict[str, List[str]] = defaultdict(list)
        self.lock = threading.RLock()
        self.logger = logging.getLogger("TECMP-Tool.TraceOrganizer")
        
    def add_packet(self, packet: PacketInfo):
        """Add a packet to the organization"""
        try:
            # Ensure stream_type is valid
            packet.stream_type = ensure_stream_type(packet.stream_type)
            
            with self.lock:
                # Chronological timeline
                self.timeline.append((packet.timestamp, packet))
                
                # Group by criteria
                self._group_packet(packet)
                
                # Detect correlations
                self._detect_correlations(packet)
                
        except Exception as e:
            self.logger.error(f"Error adding packet to organizer: {e}")
    
    def _group_packet(self, packet: PacketInfo):
        """Group packets by different criteria"""
        try:
            # Safe stream value extraction
            stream_value = get_stream_value(packet.stream_type)
            self.groups[f"stream_{stream_value}"].append(packet)
            
            # By time window (1 second window)
            time_window = int(packet.timestamp)
            self.groups[f"time_{time_window}"].append(packet)
            
            # By size
            size_category = "small" if packet.size < 64 else "medium" if packet.size < 1500 else "large"
            self.groups[f"size_{size_category}"].append(packet)
            
        except Exception as e:
            self.logger.error(f"Error grouping packet: {e}")
    
    def _detect_correlations(self, packet: PacketInfo):
        """Detect correlations between packets"""
        try:
            # Simple example: packets close in time
            recent_packets = [p for t, p in self.timeline[-10:] 
                             if abs(t - packet.timestamp) < 0.001]
            
            for recent in recent_packets:
                if recent.stream_type != packet.stream_type:
                    correlation_id = f"{packet.timestamp:.6f}"
                    self.correlations[correlation_id].append(str(packet))
                    self.correlations[correlation_id].append(str(recent))
                    
        except Exception as e:
            self.logger.error(f"Error detecting correlations: {e}")

# === ENHANCED TRACE CONTROLLER ===

class TraceController(QObject if QT_AVAILABLE else object):
    """
    Enhanced trace controller with continuous flow
    Compatible with existing TECMP facade
    """
    
    # Qt signals (compatible with original)
    if QT_AVAILABLE:
        trace_loaded = pyqtSignal(str, int)      # filepath, packet_count
        capture_status_changed = pyqtSignal(bool) # is_capturing
        error_occurred = pyqtSignal(str)
        
        # New signals for continuous flow
        flow_state_changed = pyqtSignal(str)     # new_state
        metrics_updated = pyqtSignal(dict)       # metrics
        buffer_warning = pyqtSignal(float)       # usage_percent
        stream_packet_received = pyqtSignal(str, dict)  # stream_type, packet_info
    
    def __init__(self, parent=None):
        """Enhanced constructor with flow components"""
        if QT_AVAILABLE:
            super().__init__(parent)
        
        self.logger = logging.getLogger("TECMP-Tool.TraceController")
        
        # === Original attributes (compatibility) ===
        self.main_window = None
        self._is_capturing = False
        self._capture_thread = None
        self._capture_interface = None
        
        # Dependencies (injected after creation)
        self.packet_manager = None
        self.file_system_controller = None
        self.memory_controller = None
        
        # Configuration
        self.supported_formats = ['.pcap', '.pcapng', '.cap', '.trc']
        self.current_trace_file = None
        
        # === New components for continuous flow ===
        self.flow_state = FlowState.IDLE
        self.stream_manager = StreamManager(buffer_size=50000)
        self.trace_organizer = ParallelTraceOrganizer()
        self.backpressure_manager = BackpressureManager()
        
        # Main ring buffer
        self.main_buffer = PacketRingBuffer(size=100000)
        
        # Thread pool for parallel processing
        self.worker_pool = ThreadPoolExecutor(max_workers=6)
        self.processing_tasks = []
        
        # Real-time metrics
        self.real_time_metrics = {
            'total_packets': 0,
            'total_bytes': 0,
            'packets_per_second': 0.0,
            'bytes_per_second': 0.0,
            'buffer_usage': 0.0,
            'active_streams': 0,
            'errors': 0,
            'start_time': time.time()
        }
        
        # Timer for periodic updates (fixed for Qt issues)
        self._metrics_timer = None
        if QT_AVAILABLE:
            try:
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app and hasattr(self, 'thread') and app.thread() == self.thread():
                    self._metrics_timer = QTimer()
                    self._metrics_timer.timeout.connect(self._update_metrics)
                    self._metrics_timer.start(1000)
            except:
                self._metrics_timer = None
        
        # Flow state
        self._flow_lock = threading.RLock()
        self._stop_flow = threading.Event()
        self._pause_flow = threading.Event()
        self._pause_flow.set()  # Start unpaused
        
        # Time window statistics
        self._time_windows = defaultdict(lambda: {'packets': 0, 'bytes': 0})
        self._current_window = int(time.time())
        
        self.logger.info("TraceController initialized with continuous flow support")
    
    # === ORIGINAL METHODS (COMPATIBILITY) ===
    
    @property
    def is_capturing(self) -> bool:
        """Property to check if capture is active"""
        return self._is_capturing
    
    def start_packet_capture(self, interface: str, **kwargs) -> bool:
        """
        Start packet capture (compatible with original)
        Enhanced version with continuous flow
        """
        try:
            if self._is_capturing:
                self.logger.warning("Capture already in progress")
                return False
            
            self._capture_interface = interface
            self._is_capturing = True
            
            # Options
            capture_filter = kwargs.get('filter', None)
            packet_limit = kwargs.get('limit', None)
            continuous_mode = kwargs.get('continuous', True)
            
            # Initialize continuous flow
            if continuous_mode:
                self._init_continuous_flow()
            
            # Start capture in thread
            self._capture_thread = threading.Thread(
                target=self._enhanced_capture_worker,
                args=(interface, capture_filter, packet_limit),
                daemon=True
            )
            self._capture_thread.start()
            
            # Start processing workers
            self._start_processing_workers()
            
            # Emit signal
            if QT_AVAILABLE and self.capture_status_changed:
                self.capture_status_changed.emit(True)
            
            self.logger.info(f"Started enhanced capture on interface: {interface}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start capture: {e}")
            self._is_capturing = False
            if QT_AVAILABLE and self.error_occurred:
                self.error_occurred.emit(str(e))
            return False
    
    def stop_packet_capture(self) -> bool:
        """
        Stop packet capture (compatible with original)
        """
        try:
            if not self._is_capturing:
                self.logger.warning("No capture in progress")
                return False
            
            # Stop flow
            self._stop_flow.set()
            self._is_capturing = False
            
            # Stop workers
            self._stop_processing_workers()
            
            # Wait for capture thread
            if self._capture_thread:
                self._capture_thread.join(timeout=5.0)
                self._capture_thread = None
            
            # Finalize metrics
            self._finalize_metrics()
            
            # Emit signal
            if QT_AVAILABLE and self.capture_status_changed:
                self.capture_status_changed.emit(False)
            
            self.logger.info("Stopped packet capture")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping capture: {e}")
            return False
    
    def load_trace_file(self, file_path: str) -> bool:
        """
        Load a trace file (compatible with original)
        Enhanced version with stream processing
        """
        try:
            path = Path(file_path)
            
            # Verifications
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if path.suffix.lower() not in self.supported_formats:
                raise ValueError(f"Unsupported format: {path.suffix}")
            
            # Initialize flow for loading
            self._init_continuous_flow()
            
            # Start workers
            self._start_processing_workers()
            
            # Load file in separate thread
            load_future = self.worker_pool.submit(
                self._load_trace_with_streaming, path
            )
            
            # Wait briefly to verify it starts
            time.sleep(0.1)
            
            if load_future.running():
                self.current_trace_file = file_path
                self.logger.info(f"Loading trace file: {file_path}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to load trace file: {e}")
            if QT_AVAILABLE and self.error_occurred:
                self.error_occurred.emit(str(e))
            return False
    
    def open_trace_file(self) -> bool:
        """
        Open trace file via dialog (compatible)
        """
        try:
            if self.main_window and QT_AVAILABLE:
                try:
                    from PyQt5.QtWidgets import QFileDialog
                    
                    filters = "Trace Files ({});;All Files (*.*)".format(
                        ' '.join(f'*{ext}' for ext in self.supported_formats)
                    )
                    
                    file_path, _ = QFileDialog.getOpenFileName(
                        self.main_window() if callable(self.main_window) else self.main_window,
                        "Open Trace File",
                        "",
                        filters
                    )
                    
                    if file_path:
                        return self.load_trace_file(file_path)
                    
                except ImportError:
                    self.logger.warning("Qt not available for file dialog")
            
            self.logger.info("No UI available for file selection")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening trace file: {e}")
            return False
    
    # === NEW METHODS FOR CONTINUOUS FLOW ===
    
    def _init_continuous_flow(self):
        """Initialize continuous flow components"""
        with self._flow_lock:
            self.flow_state = FlowState.INITIALIZING
            self._stop_flow.clear()
            self._pause_flow.set()
            
            # Reset buffers
            self.main_buffer = PacketRingBuffer(size=100000)
            self.stream_manager = StreamManager(buffer_size=50000)
            
            # Reset metrics
            self.real_time_metrics = {
                'total_packets': 0,
                'total_bytes': 0,
                'packets_per_second': 0.0,
                'bytes_per_second': 0.0,
                'buffer_usage': 0.0,
                'active_streams': 0,
                'errors': 0,
                'start_time': time.time()
            }
            
            self.flow_state = FlowState.RUNNING
            
            if QT_AVAILABLE and hasattr(self, 'flow_state_changed'):
                self.flow_state_changed.emit(self.flow_state.name)
    
    def _start_processing_workers(self):
        """Start parallel processing workers"""
        # Main distribution worker
        self.processing_tasks.append(
            self.worker_pool.submit(self._main_distribution_worker)
        )
        
        # Workers per stream type
        for stream_type in [StreamType.ETHERNET, StreamType.CAN, StreamType.TECMP]:
            self.processing_tasks.append(
                self.worker_pool.submit(self._stream_processing_worker, stream_type)
            )
        
        # Metrics worker
        self.processing_tasks.append(
            self.worker_pool.submit(self._metrics_worker)
        )
        
        # Backpressure management worker
        self.processing_tasks.append(
            self.worker_pool.submit(self._backpressure_worker)
        )
    
    def _stop_processing_workers(self):
        """Stop all processing workers"""
        self._stop_flow.set()
        
        # Wait for tasks to finish
        for task in self.processing_tasks:
            try:
                task.result(timeout=2.0)
            except:
                pass
        
        self.processing_tasks.clear()
    
    def _enhanced_capture_worker(self, interface: str, capture_filter: Optional[str], 
                                packet_limit: Optional[int]):
        """Enhanced capture worker with continuous flow"""
        packets_captured = 0
        
        try:
            self.logger.info(f"Enhanced capture worker started on {interface}")
            
            # Try to use Scapy if available
            try:
                from scapy.all import sniff, conf
                conf.use_pcap = True
                
                def packet_handler(pkt):
                    if self._stop_flow.is_set():
                        return True  # Stop sniff
                    
                    # Create PacketInfo - Ensure StreamType enum
                    stream_type = self._detect_stream_type_from_scapy(pkt)
                    
                    packet_info = PacketInfo(
                        timestamp=time.time(),
                        stream_type=stream_type,
                        size=len(bytes(pkt)),
                        data=bytes(pkt),
                        metadata={'interface': interface}
                    )
                    
                    # Add to main buffer
                    self.main_buffer.write(packet_info, timeout=0.1)
                    return False
                
                # Capture with Scapy
                sniff(
                    iface=interface,
                    prn=packet_handler,
                    filter=capture_filter,
                    count=packet_limit,
                    stop_filter=lambda x: self._stop_flow.is_set()
                )
                
            except ImportError:
                # Fallback: simulation for tests
                self.logger.warning("Scapy not available, using simulation mode")
                self._simulate_capture(interface, packet_limit)
            
        except Exception as e:
            self.logger.error(f"Capture worker error: {e}")
            self.real_time_metrics['errors'] += 1
        
        finally:
            self._is_capturing = False
            self.logger.info(f"Capture worker stopped. Captured {packets_captured} packets")
    
    def _simulate_capture(self, interface: str, packet_limit: Optional[int]):
        """Simulate capture for testing"""
        packet_count = 0
        
        while not self._stop_flow.is_set():
            if packet_limit and packet_count >= packet_limit:
                break
            
            # Wait if paused
            self._pause_flow.wait()
            
            # Generate varied simulated packets
            stream_type = self._get_random_stream_type()
            packet_info = self._generate_simulated_packet(stream_type, interface)
            
            # Add to buffer
            if self.main_buffer.write(packet_info, timeout=0.1):
                packet_count += 1
            
            # Variable delay by type
            time.sleep(0.001 if stream_type == StreamType.CAN else 0.01)
    
    def _main_distribution_worker(self):
        """Main worker that distributes packets to streams"""
        self.logger.info("Main distribution worker started")
        
        while not self._stop_flow.is_set():
            try:
                # Read batch of packets with error handling
                try:
                    packets = self.main_buffer.read_batch(100)
                except Exception as e:
                    self.logger.error(f"Error reading from buffer: {e}")
                    time.sleep(0.1)
                    continue
                
                if not packets:
                    time.sleep(0.01)
                    continue
                
                # Process each packet individually with error isolation
                for i, packet in enumerate(packets):
                    try:
                        # Ensure packet and stream_type are valid
                        if not packet:
                            continue
                            
                        packet.stream_type = ensure_stream_type(packet.stream_type)
                        
                        # Route to correct stream
                        try:
                            self.stream_manager.route_packet(packet)
                        except Exception as e:
                            self.logger.error(f"Error routing packet {i}: {e}")
                        
                        # Organize for parallel analysis
                        try:
                            self.trace_organizer.add_packet(packet)
                        except Exception as e:
                            self.logger.error(f"Error organizing packet {i}: {e}")
                        
                        # Update global metrics
                        with self._flow_lock:
                            self.real_time_metrics['total_packets'] += 1
                            self.real_time_metrics['total_bytes'] += packet.size
                    
                    except Exception as e:
                        self.logger.error(f"Error processing individual packet {i}: {e}")
                        continue
                
            except Exception as e:
                self.logger.error(f"Distribution worker error: {e}")
                import traceback
                self.logger.error(f"Full traceback: {traceback.format_exc()}")
                self.real_time_metrics['errors'] += 1
                time.sleep(0.1)
        
        self.logger.info("Main distribution worker stopped")
    
    def _stream_processing_worker(self, stream_type: StreamType):
        """Processing worker for specific stream type"""
        stream_type = ensure_stream_type(stream_type)
        stream_value = get_stream_value(stream_type)
        
        self.logger.info(f"Stream processing worker started for {stream_value}")
        
        stream_buffer = self.stream_manager.get_stream(stream_type)
        if not stream_buffer:
            self.logger.error(f"No buffer for stream {stream_value}")
            return
        
        while not self._stop_flow.is_set():
            try:
                # Read packets from stream
                packets = stream_buffer.read_batch(50)
                
                if not packets:
                    time.sleep(0.01)
                    continue
                
                # Process packets
                for packet in packets:
                    try:
                        self._process_packet(packet)
                        
                        # Emit signal if Qt available
                        if QT_AVAILABLE and hasattr(self, 'stream_packet_received'):
                            packet_dict = {
                                'timestamp': packet.timestamp,
                                'size': packet.size,
                                'metadata': packet.metadata
                            }
                            self.stream_packet_received.emit(stream_value, packet_dict)
                    except Exception as e:
                        self.logger.error(f"Error processing stream packet: {e}")
                
            except Exception as e:
                self.logger.error(f"Stream worker error ({stream_value}): {e}")
                time.sleep(0.1)
        
        self.logger.info(f"Stream processing worker stopped for {stream_value}")
    
    def _process_packet(self, packet: PacketInfo):
        """Process individual packet"""
        try:
            # Ensure valid stream type
            packet.stream_type = ensure_stream_type(packet.stream_type)
            
            # Store in packet_manager if available
            if self.packet_manager:
                # Convert PacketInfo to expected format
                packet_data = {
                    'timestamp': packet.timestamp,
                    'stream_type': get_stream_value(packet.stream_type),
                    'size': packet.size,
                    'data': packet.data,
                    'metadata': packet.metadata
                }
                self.packet_manager.add(packet_data)
            
            # Update time window statistics
            window = int(packet.timestamp)
            with self._flow_lock:
                self._time_windows[window]['packets'] += 1
                self._time_windows[window]['bytes'] += packet.size
            
        except Exception as e:
            self.logger.error(f"Error processing packet: {e}")
    
    def _metrics_worker(self):
        """Real-time metrics calculation worker"""
        self.logger.info("Metrics worker started")
        
        last_update = time.time()
        last_packets = 0
        last_bytes = 0
        
        while not self._stop_flow.is_set():
            try:
                current_time = time.time()
                elapsed = current_time - last_update
                
                if elapsed >= 1.0:  # Update every second
                    with self._flow_lock:
                        # Calculate rates
                        current_packets = self.real_time_metrics['total_packets']
                        current_bytes = self.real_time_metrics['total_bytes']
                        
                        self.real_time_metrics['packets_per_second'] = (
                            (current_packets - last_packets) / elapsed
                        )
                        self.real_time_metrics['bytes_per_second'] = (
                            (current_bytes - last_bytes) / elapsed
                        )
                        
                        # Buffer usage
                        self.real_time_metrics['buffer_usage'] = self.main_buffer.get_usage()
                        
                        # Active streams
                        active_streams = sum(
                            1 for metrics in self.stream_manager.get_all_metrics().values()
                            if metrics.packets_count > 0
                        )
                        self.real_time_metrics['active_streams'] = active_streams
                        
                        last_update = current_time
                        last_packets = current_packets
                        last_bytes = current_bytes
                
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Metrics worker error: {e}")
                time.sleep(1.0)
        
        self.logger.info("Metrics worker stopped")
    
    def _backpressure_worker(self):
        """Backpressure management worker"""
        self.logger.info("Backpressure worker started")
        
        while not self._stop_flow.is_set():
            try:
                # Check main buffer usage
                usage = self.main_buffer.get_usage()
                
                # Determine action
                pressure_level = self.backpressure_manager.check_pressure(usage)
                action_func = self.backpressure_manager.get_action()
                action = action_func()  # Call the function to get action dict
                
                # Apply action
                if action['action'] == 'pause':
                    self._pause_flow.clear()
                    self.flow_state = FlowState.PAUSED
                elif action['action'] == 'throttle':
                    self.flow_state = FlowState.THROTTLED
                else:
                    self._pause_flow.set()
                    if self.flow_state in [FlowState.PAUSED, FlowState.THROTTLED]:
                        self.flow_state = FlowState.RUNNING
                
                # Emit warning if usage high
                if usage > 0.8 and QT_AVAILABLE and hasattr(self, 'buffer_warning'):
                    self.buffer_warning.emit(usage * 100)
                
                # Delay based on action
                time.sleep(action['delay'] if action['delay'] > 0 else 0.1)
                
            except Exception as e:
                self.logger.error(f"Backpressure worker error: {e}")
                time.sleep(1.0)
        
        self.logger.info("Backpressure worker stopped")
    
    def _load_trace_with_streaming(self, file_path: Path):
        """Load trace file in streaming mode"""
        packet_count = 0
        
        try:
            # Use dpkt or pyshark based on availability
            try:
                import dpkt
                
                with open(file_path, 'rb') as f:
                    if file_path.suffix.lower() in ['.pcap', '.cap']:
                        pcap = dpkt.pcap.Reader(f)
                    else:  # pcapng
                        pcap = dpkt.pcapng.Reader(f)
                    
                    for timestamp, buf in pcap:
                        if self._stop_flow.is_set():
                            break
                        
                        # Detect stream type and ensure it's valid
                        stream_type = self._detect_stream_type_from_data(buf)
                        
                        # Create PacketInfo
                        packet_info = PacketInfo(
                            timestamp=float(timestamp),
                            stream_type=stream_type,
                            size=len(buf),
                            data=buf,
                            metadata={'source': str(file_path)}
                        )
                        
                        # Add to buffer
                        self.main_buffer.write(packet_info)
                        packet_count += 1
                        
                        # Pause if necessary
                        self._pause_flow.wait()
                        
            except ImportError:
                # Fallback: basic loading
                self._load_trace_basic(file_path)
            
            # Emit end signal
            if QT_AVAILABLE and self.trace_loaded:
                self.trace_loaded.emit(str(file_path), packet_count)
            
            self.logger.info(f"Loaded {packet_count} packets from {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error loading trace file: {e}")
            if QT_AVAILABLE and self.error_occurred:
                self.error_occurred.emit(str(e))
    
    def _load_trace_basic(self, file_path: Path):
        """Basic file loading (fallback)"""
        # Simplified implementation for tests
        with open(file_path, 'rb') as f:
            data = f.read()
            
        # Create single packet with all data
        packet_info = PacketInfo(
            timestamp=time.time(),
            stream_type=StreamType.UNKNOWN,
            size=len(data),
            data=data,
            metadata={'source': str(file_path), 'fallback': True}
        )
        
        self.main_buffer.write(packet_info)
    
    # === UTILITY METHODS ===
    
    def _detect_stream_type_from_scapy(self, packet) -> StreamType:
        """Detect stream type from Scapy packet"""
        try:
            if hasattr(packet, 'type'):
                # Ethernet type field
                if packet.type == 0x88EC:  # TECMP
                    return StreamType.TECMP
            
            # Further analysis if needed
            packet_str = str(packet)
            if 'CAN' in packet_str:
                return StreamType.CAN
            elif 'FlexRay' in packet_str:
                return StreamType.FLEXRAY
            
            return StreamType.ETHERNET
            
        except:
            return StreamType.UNKNOWN
    
    def _detect_stream_type_from_data(self, data: bytes) -> StreamType:
        """Detect stream type from raw data"""
        if len(data) < 14:
            return StreamType.UNKNOWN
        
        try:
            # Check EtherType
            ethertype = struct.unpack('!H', data[12:14])[0]
            
            if ethertype == 0x88EC:  # TECMP
                return StreamType.TECMP
            elif ethertype == 0x0800:  # IPv4
                return StreamType.ETHERNET
            elif ethertype == 0x86DD:  # IPv6
                return StreamType.ETHERNET
            
            # Check specific patterns
            if len(data) >= 16:
                if data[14:16] == b'\x00\x00':  # Possible CAN
                    return StreamType.CAN
            
            return StreamType.ETHERNET
            
        except:
            return StreamType.UNKNOWN
    
    def _get_random_stream_type(self) -> StreamType:
        """Return random stream type for simulation"""
        import random
        types = [StreamType.ETHERNET, StreamType.CAN, StreamType.TECMP, 
                StreamType.FLEXRAY, StreamType.LIN]
        weights = [0.4, 0.3, 0.2, 0.05, 0.05]
        return random.choices(types, weights=weights)[0]
    
    def _generate_simulated_packet(self, stream_type: StreamType, 
                                  interface: str) -> PacketInfo:
        """Generate simulated packet for tests"""
        import random
        
        # Ensure stream_type is valid
        stream_type = ensure_stream_type(stream_type)
        
        # Size by type
        if stream_type == StreamType.CAN:
            size = random.choice([8, 16, 24, 32, 64])
        elif stream_type == StreamType.ETHERNET:
            size = random.randint(64, 1500)
        else:
            size = random.randint(20, 500)
        
        # Simulated data
        data = bytes([random.randint(0, 255) for _ in range(size)])
        
        return PacketInfo(
            timestamp=time.time(),
            stream_type=stream_type,
            size=size,
            data=data,
            metadata={
                'interface': interface,
                'simulated': True,
                'seq': self.real_time_metrics['total_packets']
            }
        )
    
    def _update_metrics(self):
        """Periodic metrics update (called by QTimer)"""
        try:
            # Collect all metrics
            metrics = {
                'global': dict(self.real_time_metrics),
                'streams': {},
                'buffer_usage': {
                    'main': self.main_buffer.get_usage() * 100,
                },
                'flow_state': self.flow_state.name
            }
            
            # Metrics per stream - PROTECTED .value access
            for stream_type, stream_metrics in self.stream_manager.get_all_metrics().items():
                try:
                    # Safe stream value extraction
                    stream_key = get_stream_value(stream_type)
                    
                    metrics['streams'][stream_key] = {
                        'packets': stream_metrics.packets_count,
                        'bytes': stream_metrics.bytes_count,
                        'errors': stream_metrics.errors_count,
                        'pps': stream_metrics.packets_per_second
                    }
                    
                    # Stream buffer usage
                    stream_buffer = self.stream_manager.get_stream(stream_type)
                    if stream_buffer:
                        metrics['buffer_usage'][stream_key] = (
                            stream_buffer.get_usage() * 100
                        )
                except Exception as e:
                    self.logger.error(f"Error processing stream metrics for {stream_type}: {e}")
            
            # Emit signal
            if QT_AVAILABLE and hasattr(self, 'metrics_updated'):
                self.metrics_updated.emit(metrics)
            
        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")
            import traceback
            self.logger.error(f"Metrics update traceback: {traceback.format_exc()}")
    
    def _finalize_metrics(self):
        """Finalize metrics at end of capture"""
        with self._flow_lock:
            # Calculate final statistics
            total_duration = time.time() - self.real_time_metrics.get('start_time', time.time())
            
            if total_duration > 0:
                avg_pps = self.real_time_metrics['total_packets'] / total_duration
                avg_bps = self.real_time_metrics['total_bytes'] / total_duration
                
                self.logger.info(
                    f"Capture statistics: "
                    f"{self.real_time_metrics['total_packets']} packets, "
                    f"{self.real_time_metrics['total_bytes']} bytes, "
                    f"{avg_pps:.1f} pps, {avg_bps:.1f} Bps"
                )
    
    # === ADDITIONAL PUBLIC METHODS ===
    
    def pause_flow(self):
        """Pause data flow"""
        self._pause_flow.clear()
        self.flow_state = FlowState.PAUSED
        self.logger.info("Flow paused")
    
    def resume_flow(self):
        """Resume data flow"""
        self._pause_flow.set()
        if self.flow_state == FlowState.PAUSED:
            self.flow_state = FlowState.RUNNING
        self.logger.info("Flow resumed")
    
    def get_flow_statistics(self) -> Dict[str, Any]:
        """Return complete flow statistics"""
        # PROTECTED .value access in streams dictionary comprehension
        try:
            streams_dict = {}
            for st, metrics in self.stream_manager.get_all_metrics().items():
                try:
                    key = get_stream_value(st)
                    streams_dict[key] = metrics
                except Exception as e:
                    self.logger.error(f"Error processing stream {st} in flow statistics: {e}")
                    streams_dict[str(st)] = metrics
        except Exception as e:
            self.logger.error(f"Error building streams dict: {e}")
            streams_dict = {}
        
        return {
            'state': self.flow_state.name,
            'metrics': dict(self.real_time_metrics),
            'streams': streams_dict,
            'buffer_usage': self.main_buffer.get_usage(),
            'backpressure_level': self.backpressure_manager.current_level,
            'timeline_size': len(self.trace_organizer.timeline),
            'groups': {k: len(v) for k, v in self.trace_organizer.groups.items()}
        }
    
    def get_stream_packets(self, stream_type: StreamType, 
                          max_count: int = 100) -> List[PacketInfo]:
        """Get last packets from specific stream"""
        stream_type = ensure_stream_type(stream_type)
        stream_buffer = self.stream_manager.get_stream(stream_type)
        if stream_buffer:
            return stream_buffer.read_batch(max_count)
        return []
    
    def export_timeline(self, start_time: Optional[float] = None,
                       end_time: Optional[float] = None) -> List[Tuple[float, PacketInfo]]:
        """Export portion of timeline"""
        with self.trace_organizer.lock:
            timeline = self.trace_organizer.timeline
            
            if start_time is None and end_time is None:
                return timeline.copy()
            
            filtered = []
            for timestamp, packet in timeline:
                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    break
                filtered.append((timestamp, packet))
            
            return filtered
    
    def set_dependencies(self, packet_manager=None, 
                        file_system_controller=None,
                        memory_controller=None):
        """
        Inject dependencies after creation (compatible)
        """
        self.packet_manager = packet_manager
        self.file_system_controller = file_system_controller
        self.memory_controller = memory_controller
        self.logger.debug("Dependencies injected")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get trace statistics (compatible)"""
        stats = {
            'is_capturing': self._is_capturing,
            'capture_interface': self._capture_interface,
            'current_trace_file': self.current_trace_file,
            'packet_count': self.real_time_metrics['total_packets'],
            # New statistics
            'flow_state': self.flow_state.name,
            'streams_active': self.real_time_metrics['active_streams'],
            'packets_per_second': self.real_time_metrics['packets_per_second'],
            'buffer_usage_percent': self.real_time_metrics['buffer_usage'] * 100
        }
        
        return stats