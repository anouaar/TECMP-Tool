#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sender Strategy - Base Class for TECMP Tool
Author: TECMP-Tool Development Team
Description: Base strategy class and core interfaces for packet transmission strategies

FEATURES:
- Abstract base class for all transmission strategies
- Common interfaces and data structures
- Integration with TECMP Facade and components
- Comprehensive error handling and monitoring
- Flexible sender management and configuration
- Full compatibility with TECMP-Tool architecture
- Support for Qt signals and threading
- Metrics collection and performance monitoring
"""

from __future__ import annotations
import time
import copy
import uuid  # FIXED: Added missing import
import socket
import struct
import logging
import threading
from typing import Dict, Any, List, Optional, Union, Callable, Tuple, Protocol, runtime_checkable
from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

# Qt imports for signals (compatible with TECMP-Tool GUI)
QT_AVAILABLE = False
try:
    from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread, QMutex, QWaitCondition
    from PyQt5.QtWidgets import QApplication
    QT_AVAILABLE = True
except ImportError:
    class QObject:
        def __init__(self, parent=None): 
            self.parent = parent
    
    def pyqtSignal(*args, **kwargs): 
        class MockSignal:
            def emit(self, *args, **kwargs): pass
            def connect(self, slot): pass
            def disconnect(self, slot=None): pass
        return MockSignal()

# TECMP-Tool specific imports (compatible with existing structure)
TECMP_IMPORTS = {}
IMPORT_PATHS = {
    'PacketManager': 'core.management.packet_manager',
    'PcapGenerator': 'core.management.pcap_generator', 
    'ResourceManager': 'core.management.resource_manager',
    'PacketBuilder': 'core.builders.packet_builder',
    'TECMPPacketBuilder': 'core.builders.tecmp_builder',
    'PacketModifier': 'core.builders.packet_modifier',
    'ScapyAdapter': 'core.adapters.scapy_adapter',
    'ErrorHandler': 'core.interfaces.controllers.core.error_handler',
    'MemoryController': 'core.interfaces.controllers.core.memory_controller'
}

# Import TECMP components with fallbacks
import importlib
for component_name, module_path in IMPORT_PATHS.items():
    try:
        module = importlib.import_module(module_path)
        TECMP_IMPORTS[component_name] = getattr(module, component_name)
    except (ImportError, AttributeError):
        TECMP_IMPORTS[component_name] = None


# === CORE ENUMS AND STATUS ===

class StrategyStatus(Enum):
    """Status enum for strategy execution"""
    CREATED = auto()
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    COMPLETED = auto()
    FAILED = auto()
    ERROR = auto()


class SenderType(Enum):
    """Types of packet senders"""
    UDP_SOCKET = "udp_socket"
    TCP_SOCKET = "tcp_socket"
    RAW_SOCKET = "raw_socket"
    SCAPY_SENDER = "scapy_sender"
    TECMP_SENDER = "tecmp_sender"
    FILE_SENDER = "file_sender"
    PCAP_SENDER = "pcap_sender"
    MOCK_SENDER = "mock_sender"


class TransmissionProtocol(Enum):
    """Transmission protocols supported"""
    UDP = "udp"
    TCP = "tcp"
    ICMP = "icmp"
    RAW = "raw"
    ETHERNET = "ethernet"
    TECMP = "tecmp"


class Priority(Enum):
    """Priority levels for strategies and senders"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    REAL_TIME = 5


# === CORE DATA STRUCTURES ===

@dataclass
class NetworkInterface:
    """Network interface information"""
    name: str
    ip_address: str = ""
    mac_address: str = ""
    is_active: bool = True
    mtu: int = 1500
    interface_type: str = "ethernet"
    
    def __post_init__(self):
        if not self.ip_address:
            self.ip_address = "0.0.0.0"
        if not self.mac_address:
            self.mac_address = "00:00:00:00:00:00"


@dataclass
class TransmissionTarget:
    """Target for packet transmission"""
    host: str
    port: int = 0
    protocol: TransmissionProtocol = TransmissionProtocol.UDP
    interface: Optional[NetworkInterface] = None
    timeout: float = 5.0
    
    def __post_init__(self):
        if self.port == 0:
            if self.protocol == TransmissionProtocol.UDP:
                self.port = 12345
            elif self.protocol == TransmissionProtocol.TCP:
                self.port = 80
            else:
                self.port = 0


@dataclass
class SenderConfiguration:
    """Configuration for a packet sender"""
    sender_id: str = field(default_factory=lambda: f"sender_{uuid.uuid4().hex[:8]}")
    sender_type: SenderType = SenderType.UDP_SOCKET
    target: Optional[TransmissionTarget] = None
    
    # Network configuration
    bind_address: str = "0.0.0.0"
    bind_port: int = 0
    source_interface: Optional[NetworkInterface] = None
    
    # Performance settings
    buffer_size: int = 65536
    send_timeout: float = 1.0
    max_retries: int = 3
    retry_delay: float = 0.1
    
    # Advanced settings
    priority: Priority = Priority.NORMAL
    enable_keepalive: bool = False
    enable_nagle: bool = True
    enable_broadcast: bool = False
    
    # TECMP specific
    tecmp_device_id: int = 0x01
    tecmp_counter_start: int = 0
    
    # Monitoring
    enable_metrics: bool = True
    enable_logging: bool = True
    log_level: str = "INFO"
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Validate sender configuration"""
        errors = []
        
        if not self.sender_id:
            errors.append("Sender ID cannot be empty")
        
        if self.buffer_size <= 0:
            errors.append("Buffer size must be positive")
        
        if self.send_timeout <= 0:
            errors.append("Send timeout must be positive")
        
        if self.max_retries < 0:
            errors.append("Max retries cannot be negative")
        
        if self.retry_delay < 0:
            errors.append("Retry delay cannot be negative")
        
        if self.target and not self.target.host:
            errors.append("Target host cannot be empty")
        
        return len(errors) == 0, errors


@dataclass
class StrategyConfiguration:
    """Base configuration for strategies"""
    strategy_id: str = field(default_factory=lambda: f"strategy_{uuid.uuid4().hex[:8]}")
    strategy_name: str = ""
    strategy_type: str = "base"
    
    # Execution parameters
    max_execution_time: float = 300.0  # 5 minutes max
    execution_timeout: float = 60.0
    enable_threading: bool = True
    thread_priority: Priority = Priority.NORMAL
    
    # Error handling
    stop_on_error: bool = False
    max_errors: int = 100
    error_threshold_rate: float = 0.1  # 10%
    
    # Monitoring and logging
    enable_metrics: bool = True
    enable_detailed_logging: bool = False
    metrics_interval: float = 1.0
    log_file_path: Optional[str] = None
    
    # Integration settings
    integrate_with_facade: bool = True
    update_facade_metrics: bool = True
    emit_qt_signals: bool = True
    
    def __post_init__(self):
        if not self.strategy_name:
            self.strategy_name = f"{self.strategy_type}_{self.strategy_id}"


@dataclass 
class StrategyMetrics:
    """Base metrics for strategy execution"""
    strategy_id: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    # Execution metrics
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    
    # Performance metrics
    operations_per_second: float = 0.0
    average_operation_time: float = 0.0
    min_operation_time: float = float('inf')
    max_operation_time: float = 0.0
    
    # Resource metrics
    peak_memory_usage: float = 0.0
    average_cpu_usage: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_received: int = 0
    
    # Error metrics
    error_count: int = 0
    error_rate: float = 0.0
    last_error_time: Optional[float] = None
    last_error_message: str = ""
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_operations == 0:
            return 0.0
        return (self.successful_operations / self.total_operations) * 100.0
    
    @property
    def duration(self) -> float:
        """Calculate total duration"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def update_performance_metrics(self):
        """Update calculated performance metrics"""
        duration = self.duration
        if duration > 0:
            self.operations_per_second = self.total_operations / duration
        
        if self.total_operations > 0:
            self.error_rate = (self.error_count / self.total_operations) * 100.0


# === SENDER INTERFACE AND IMPLEMENTATIONS ===

@runtime_checkable
class Sender(Protocol):
    """Protocol for packet senders"""
    
    def send_packet(self, packet: Any) -> bool:
        """Send a packet"""
        ...
    
    def close(self) -> None:
        """Close the sender"""
        ...
    
    def is_connected(self) -> bool:
        """Check if sender is connected"""
        ...


class BaseSender(QObject if QT_AVAILABLE else object):
    """Base implementation for packet senders"""
    
    if QT_AVAILABLE:
        packet_sent = pyqtSignal(dict)  # packet_info
        send_error = pyqtSignal(str)    # error_message
        connection_changed = pyqtSignal(bool)  # is_connected
    
    def __init__(self, config: SenderConfiguration, parent=None):
        if QT_AVAILABLE:
            super().__init__(parent)
        else:
            self.parent = parent
        
        self.config = config
        self.logger = logging.getLogger(f"TECMP.Sender.{config.sender_id}")
        self._is_connected = False
        self._packets_sent = 0
        self._bytes_sent = 0
        self._errors_count = 0
        self._last_send_time = 0.0
        
        # Thread safety
        self._send_lock = threading.RLock()
        
        # Setup mock signals if Qt not available
        if not QT_AVAILABLE:
            self.packet_sent = self._mock_signal()
            self.send_error = self._mock_signal()
            self.connection_changed = self._mock_signal()
    
    def _mock_signal(self):
        """Create mock signal"""
        class MockSignal:
            def emit(self, *args): pass
            def connect(self, slot): pass
        return MockSignal()
    
    @abstractmethod
    def _initialize_connection(self) -> bool:
        """Initialize the connection (abstract)"""
        pass
    
    @abstractmethod
    def _send_packet_impl(self, packet: Any) -> bool:
        """Send packet implementation (abstract)"""
        pass
    
    @abstractmethod
    def _close_connection(self) -> None:
        """Close connection implementation (abstract)"""
        pass
    
    def send_packet(self, packet: Any) -> bool:
        """Send a packet with error handling and metrics"""
        with self._send_lock:
            try:
                # Initialize connection if needed
                if not self._is_connected:
                    if not self._initialize_connection():
                        self.send_error.emit("Failed to initialize connection")
                        return False
                
                # Send packet
                send_start = time.time()
                success = self._send_packet_impl(packet)
                send_duration = time.time() - send_start
                
                # Update metrics
                if success:
                    self._packets_sent += 1
                    if hasattr(packet, '__len__'):
                        self._bytes_sent += len(packet)
                    elif isinstance(packet, (dict, str)):
                        self._bytes_sent += len(str(packet))
                    else:
                        self._bytes_sent += 64  # Estimate
                    
                    self._last_send_time = time.time()
                    
                    # Emit success signal
                    self.packet_sent.emit({
                        'sender_id': self.config.sender_id,
                        'packet_size': len(str(packet)),
                        'send_duration': send_duration,
                        'timestamp': self._last_send_time
                    })
                else:
                    self._errors_count += 1
                    self.send_error.emit(f"Packet send failed for sender {self.config.sender_id}")
                
                return success
                
            except Exception as e:
                self._errors_count += 1
                error_msg = f"Exception in send_packet: {e}"
                self.logger.error(error_msg)
                self.send_error.emit(error_msg)
                return False
    
    def close(self) -> None:
        """Close the sender connection"""
        try:
            self._close_connection()
            self._is_connected = False
            self.connection_changed.emit(False)
            self.logger.debug(f"Sender {self.config.sender_id} closed")
        except Exception as e:
            self.logger.error(f"Error closing sender: {e}")
    
    def is_connected(self) -> bool:
        """Check if sender is connected"""
        return self._is_connected
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get sender statistics"""
        return {
            'sender_id': self.config.sender_id,
            'sender_type': self.config.sender_type.value,
            'is_connected': self._is_connected,
            'packets_sent': self._packets_sent,
            'bytes_sent': self._bytes_sent,
            'errors_count': self._errors_count,
            'last_send_time': self._last_send_time,
            'success_rate': (self._packets_sent / max(1, self._packets_sent + self._errors_count)) * 100.0
        }


class UDPSender(BaseSender):
    """UDP socket sender implementation"""
    
    def __init__(self, config: SenderConfiguration, parent=None):
        super().__init__(config, parent)
        self._socket = None
        self._target_addr = None
    
    def _initialize_connection(self) -> bool:
        """Initialize UDP socket"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.settimeout(self.config.send_timeout)
            
            # Configure socket options
            if self.config.enable_broadcast:
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Bind if specified
            if self.config.bind_port > 0:
                self._socket.bind((self.config.bind_address, self.config.bind_port))
            
            # Set target address
            if self.config.target:
                self._target_addr = (self.config.target.host, self.config.target.port)
            else:
                self._target_addr = ("127.0.0.1", 12345)  # Default
            
            self._is_connected = True
            self.connection_changed.emit(True)
            self.logger.debug(f"UDP sender initialized: {self._target_addr}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize UDP sender: {e}")
            return False
    
    def _send_packet_impl(self, packet: Any) -> bool:
        """Send packet via UDP"""
        try:
            if not self._socket or not self._target_addr:
                return False
            
            # Convert packet to bytes
            if isinstance(packet, bytes):
                data = packet
            elif isinstance(packet, str):
                data = packet.encode('utf-8')
            elif isinstance(packet, dict):
                import json
                data = json.dumps(packet).encode('utf-8')
            else:
                data = str(packet).encode('utf-8')
            
            # Send packet
            bytes_sent = self._socket.sendto(data, self._target_addr)
            return bytes_sent > 0
            
        except Exception as e:
            self.logger.warning(f"UDP send failed: {e}")
            return False
    
    def _close_connection(self) -> None:
        """Close UDP socket"""
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            self._socket = None


class TCPSender(BaseSender):
    """TCP socket sender implementation"""
    
    def __init__(self, config: SenderConfiguration, parent=None):
        super().__init__(config, parent)
        self._socket = None
        self._connected = False
    
    def _initialize_connection(self) -> bool:
        """Initialize TCP connection"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.config.send_timeout)
            
            # Configure socket options
            if not self.config.enable_nagle:
                self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            if self.config.enable_keepalive:
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            # Connect to target
            if self.config.target:
                target_addr = (self.config.target.host, self.config.target.port)
            else:
                target_addr = ("127.0.0.1", 80)  # Default
            
            self._socket.connect(target_addr)
            self._connected = True
            self._is_connected = True
            self.connection_changed.emit(True)
            self.logger.debug(f"TCP sender connected to: {target_addr}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect TCP sender: {e}")
            return False
    
    def _send_packet_impl(self, packet: Any) -> bool:
        """Send packet via TCP"""
        try:
            if not self._socket or not self._connected:
                return False
            
            # Convert packet to bytes
            if isinstance(packet, bytes):
                data = packet
            elif isinstance(packet, str):
                data = packet.encode('utf-8')
            else:
                data = str(packet).encode('utf-8')
            
            # Send packet
            bytes_sent = self._socket.send(data)
            return bytes_sent > 0
            
        except Exception as e:
            self.logger.warning(f"TCP send failed: {e}")
            self._connected = False
            self._is_connected = False
            return False
    
    def _close_connection(self) -> None:
        """Close TCP connection"""
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            self._socket = None
            self._connected = False


class FileSender(BaseSender):
    """File-based sender (writes packets to file)"""
    
    def __init__(self, config: SenderConfiguration, parent=None, file_path: Optional[str] = None):
        super().__init__(config, parent)
        self.file_path = file_path or f"packets_{config.sender_id}.log"
        self._file_handle = None
    
    def _initialize_connection(self) -> bool:
        """Open file for writing"""
        try:
            self._file_handle = open(self.file_path, 'w', encoding='utf-8')
            self._is_connected = True
            self.connection_changed.emit(True)
            self.logger.debug(f"File sender initialized: {self.file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to open file: {e}")
            return False
    
    def _send_packet_impl(self, packet: Any) -> bool:
        """Write packet to file"""
        try:
            if not self._file_handle:
                return False
            
            timestamp = datetime.now().isoformat()
            
            if isinstance(packet, dict):
                import json
                packet_str = json.dumps(packet)
            else:
                packet_str = str(packet)
            
            self._file_handle.write(f"[{timestamp}] {packet_str}\n")
            self._file_handle.flush()
            return True
            
        except Exception as e:
            self.logger.warning(f"File write failed: {e}")
            return False
    
    def _close_connection(self) -> None:
        """Close file"""
        if self._file_handle:
            try:
                self._file_handle.close()
            except:
                pass
            self._file_handle = None


class MockSender(BaseSender):
    """Mock sender for testing"""
    
    def __init__(self, config: SenderConfiguration, parent=None, fail_rate: float = 0.0):
        super().__init__(config, parent)
        self.fail_rate = max(0.0, min(1.0, fail_rate))
        self.sent_packets = []
    
    def _initialize_connection(self) -> bool:
        """Mock initialization"""
        self._is_connected = True
        self.connection_changed.emit(True)
        return True
    
    def _send_packet_impl(self, packet: Any) -> bool:
        """Mock packet sending"""
        import random
        
        # Simulate send delay
        time.sleep(0.001)  # 1ms
        
        # Simulate failure based on fail_rate
        if random.random() < self.fail_rate:
            return False
        
        # Store packet
        self.sent_packets.append({
            'packet': packet,
            'timestamp': time.time(),
            'sender_id': self.config.sender_id
        })
        
        return True
    
    def _close_connection(self) -> None:
        """Mock close"""
        pass
    
    def get_sent_packets(self) -> List[Dict[str, Any]]:
        """Get list of sent packets (for testing)"""
        return self.sent_packets.copy()


# === SENDER FACTORY ===

class SenderFactory:
    """Factory for creating senders"""
    
    @staticmethod
    def create_sender(config: SenderConfiguration, **kwargs) -> BaseSender:
        """Create a sender based on configuration"""
        
        if config.sender_type == SenderType.UDP_SOCKET:
            return UDPSender(config, **kwargs)
        
        elif config.sender_type == SenderType.TCP_SOCKET:
            return TCPSender(config, **kwargs)
        
        elif config.sender_type == SenderType.FILE_SENDER:
            return FileSender(config, **kwargs)
        
        elif config.sender_type == SenderType.MOCK_SENDER:
            return MockSender(config, **kwargs)
        
        else:
            raise ValueError(f"Unsupported sender type: {config.sender_type}")
    
    @staticmethod
    def create_udp_sender(host: str, port: int, sender_id: Optional[str] = None) -> UDPSender:
        """Quick UDP sender creation"""
        target = TransmissionTarget(host=host, port=port, protocol=TransmissionProtocol.UDP)
        config = SenderConfiguration(
            sender_id=sender_id or f"udp_{host}_{port}",
            sender_type=SenderType.UDP_SOCKET,
            target=target
        )
        return UDPSender(config)
    
    @staticmethod
    def create_tcp_sender(host: str, port: int, sender_id: Optional[str] = None) -> TCPSender:
        """Quick TCP sender creation"""
        target = TransmissionTarget(host=host, port=port, protocol=TransmissionProtocol.TCP)
        config = SenderConfiguration(
            sender_id=sender_id or f"tcp_{host}_{port}",
            sender_type=SenderType.TCP_SOCKET,
            target=target
        )
        return TCPSender(config)
    
    @staticmethod
    def create_mock_sender(sender_id: Optional[str] = None, fail_rate: float = 0.0) -> MockSender:
        """Quick mock sender creation"""
        config = SenderConfiguration(
            sender_id=sender_id or f"mock_{uuid.uuid4().hex[:8]}",
            sender_type=SenderType.MOCK_SENDER
        )
        return MockSender(config, fail_rate=fail_rate)


# === BASE STRATEGY CLASS ===

class SenderStrategy(ABC):
    """
    Abstract base class for all packet transmission strategies
    
    This is the foundation class that all specific strategies inherit from.
    It provides common functionality for strategy management, execution,
    monitoring, and integration with the TECMP-Tool ecosystem.
    """
    
    if QT_AVAILABLE:
        # Base strategy signals
        strategy_started = pyqtSignal(str)           # strategy_id
        strategy_completed = pyqtSignal(str, dict)   # strategy_id, results
        strategy_failed = pyqtSignal(str, str)       # strategy_id, error_message
        strategy_stopped = pyqtSignal(str)           # strategy_id
        status_changed = pyqtSignal(str, str)        # strategy_id, new_status
        progress_updated = pyqtSignal(str, float)    # strategy_id, progress_percent
        metrics_updated = pyqtSignal(str, dict)      # strategy_id, metrics
        error_occurred = pyqtSignal(str, str, str)   # strategy_id, error_type, error_message
    
    def __init__(self, config: StrategyConfiguration, senders: List[Sender], parent=None):
        """
        Initialize base strategy
        
        Args:
            config: Strategy configuration
            senders: List of packet senders
            parent: Parent QObject (for Qt integration)
        """
        # Initialize Qt parent if available
        if QT_AVAILABLE:
            super().__init__(parent)
        else:
            self.parent = parent
        
        # Core attributes
        self.config = config
        self.senders = senders or []
        self.logger = logging.getLogger(f"TECMP.Strategy.{config.strategy_id}")
        
        # State management
        self.status = StrategyStatus.CREATED
        self.metrics = StrategyMetrics(strategy_id=config.strategy_id)
        self._execution_start_time = 0.0
        self._progress = 0.0
        
        # Threading and control
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._execution_thread = None
        self._monitoring_thread = None
        self._is_running = False
        self._is_paused = False
        
        # Thread safety
        self._state_lock = threading.RLock()
        self._metrics_lock = threading.RLock()
        
        # TECMP-Tool integration
        self._facade_reference = None
        self._packet_manager = None
        self._error_handler = None
        self._memory_controller = None
        
        # Performance monitoring
        self._performance_timer = QTimer() if QT_AVAILABLE else None
        if self._performance_timer:
            self._performance_timer.timeout.connect(self._update_performance_metrics)
        
        # Setup mock signals if Qt not available
        if not QT_AVAILABLE:
            self._setup_mock_signals()
        
        # Initialize TECMP components
        self._initialize_tecmp_integration()
        
        self.logger.info(f"Strategy initialized: {config.strategy_id} ({config.strategy_type})")
    
    def _setup_mock_signals(self):
        """Setup mock signals when Qt is not available"""
        signal_names = [
            'strategy_started', 'strategy_completed', 'strategy_failed', 'strategy_stopped',
            'status_changed', 'progress_updated', 'metrics_updated', 'error_occurred'
        ]
        
        for signal_name in signal_names:
            signal = type('MockSignal', (), {
                'emit': lambda *args, **kwargs: None,
                'connect': lambda slot: None,
                'disconnect': lambda slot=None: None
            })()
            setattr(self, signal_name, signal)
    
    def _initialize_tecmp_integration(self):
        """Initialize integration with TECMP-Tool components"""
        try:
            # Initialize PacketManager if available
            if TECMP_IMPORTS['PacketManager']:
                try:
                    self._packet_manager = TECMP_IMPORTS['PacketManager']()
                    self.logger.debug("PacketManager initialized")
                except Exception as e:
                    self.logger.warning(f"Could not initialize PacketManager: {e}")
            
            # Initialize ErrorHandler if available
            if TECMP_IMPORTS['ErrorHandler']:
                try:
                    self._error_handler = TECMP_IMPORTS['ErrorHandler']()
                    self.logger.debug("ErrorHandler initialized")
                except Exception as e:
                    self.logger.warning(f"Could not initialize ErrorHandler: {e}")
            
            # Initialize MemoryController if available
            if TECMP_IMPORTS['MemoryController']:
                try:
                    self._memory_controller = TECMP_IMPORTS['MemoryController']()
                    self.logger.debug("MemoryController initialized")
                except Exception as e:
                    self.logger.warning(f"Could not initialize MemoryController: {e}")
        
        except Exception as e:
            self.logger.error(f"Error initializing TECMP integration: {e}")
    
    def set_facade_reference(self, facade_reference: Any) -> None:
        """Set reference to TECMP Facade"""
        self._facade_reference = facade_reference
        self.logger.debug("Facade reference set")
    
    # === ABSTRACT METHODS ===
    
    @abstractmethod
    def execute(self) -> bool:
        """
        Execute the strategy (abstract method)
        
        Returns:
            bool: True if execution started successfully
        """
        pass
    
    @abstractmethod
    def _execute_implementation(self) -> None:
        """
        Strategy-specific execution implementation (abstract method)
        
        This method contains the core logic for each strategy type.
        It will be called by the base execute() method in a separate thread.
        """
        pass
    
    # === CORE EXECUTION METHODS ===
    
    def start(self) -> bool:
        """Start strategy execution (public interface)"""
        return self.execute()
    
    def stop(self) -> bool:
        """
        Stop strategy execution
        
        Returns:
            bool: True if stop was successful
        """
        try:
            with self._state_lock:
                if self.status not in [StrategyStatus.RUNNING, StrategyStatus.PAUSED]:
                    self.logger.warning(f"Cannot stop strategy in status: {self.status}")
                    return False
                
                self.logger.info(f"Stopping strategy: {self.config.strategy_id}")
                
                # Signal stop
                self._stop_event.set()
                self._pause_event.set()  # Also unpause if paused
                
                # Update status
                self._update_status(StrategyStatus.STOPPING)
                
                # Wait for execution thread
                if self._execution_thread and self._execution_thread.is_alive():
                    self._execution_thread.join(timeout=5.0)
                    if self._execution_thread.is_alive():
                        self.logger.warning("Execution thread did not stop gracefully")
                
                # Stop monitoring
                self._stop_monitoring()
                
                # Close senders
                self._close_all_senders()
                
                # Update final status
                self._update_status(StrategyStatus.STOPPED)
                self._is_running = False
                
                # Emit stop signal
                self.strategy_stopped.emit(self.config.strategy_id)
                
                self.logger.info("Strategy stopped successfully")
                return True
        
        except Exception as e:
            self.logger.error(f"Error stopping strategy: {e}")
            self._handle_error("stop_error", str(e))
            return False
    
    def pause(self) -> bool:
        """
        Pause strategy execution
        
        Returns:
            bool: True if pause was successful
        """
        try:
            with self._state_lock:
                if self.status != StrategyStatus.RUNNING:
                    return False
                
                self._pause_event.clear()
                self._is_paused = True
                self._update_status(StrategyStatus.PAUSED)
                
                self.logger.info("Strategy paused")
                return True
        
        except Exception as e:
            self.logger.error(f"Error pausing strategy: {e}")
            return False
    
    def resume(self) -> bool:
        """
        Resume strategy execution from pause
        
        Returns:
            bool: True if resume was successful
        """
        try:
            with self._state_lock:
                if self.status != StrategyStatus.PAUSED:
                    return False
                
                self._pause_event.set()
                self._is_paused = False
                self._update_status(StrategyStatus.RUNNING)
                
                self.logger.info("Strategy resumed")
                return True
        
        except Exception as e:
            self.logger.error(f"Error resuming strategy: {e}")
            return False
    
    def _base_execute(self) -> None:
        """Base execution method (called by concrete strategies)"""
        try:
            with self._state_lock:
                if self.status != StrategyStatus.READY:
                    raise RuntimeError(f"Strategy not ready for execution: {self.status}")
                
                # Initialize execution
                self._execution_start_time = time.time()
                self.metrics.start_time = self._execution_start_time
                self._stop_event.clear()
                self._pause_event.set()  # Start unpaused
                self._is_running = True
                self._progress = 0.0
                
                # Update status
                self._update_status(StrategyStatus.RUNNING)
                
                # Start monitoring
                self._start_monitoring()
                
                # Emit start signal
                self.strategy_started.emit(self.config.strategy_id)
                
                self.logger.info(f"Strategy execution started: {self.config.strategy_id}")
            
            # Execute strategy-specific implementation
            self._execute_implementation()
            
            # Complete execution
            self._complete_execution()
        
        except Exception as e:
            self.logger.error(f"Error in strategy execution: {e}")
            self._handle_execution_failure(str(e))
    
    def _complete_execution(self) -> None:
        """Complete strategy execution successfully"""
        try:
            with self._state_lock:
                # Update metrics
                self.metrics.end_time = time.time()
                self.metrics.update_performance_metrics()
                
                # Update status
                self._update_status(StrategyStatus.COMPLETED)
                self._is_running = False
                self._progress = 100.0
                
                # Stop monitoring
                self._stop_monitoring()
                
                # Close senders
                self._close_all_senders()
                
                # Update facade metrics if configured
                self._update_facade_metrics()
                
                # Emit completion signal
                final_metrics = self._get_final_metrics()
                self.strategy_completed.emit(self.config.strategy_id, final_metrics)
                
                self.logger.info(f"Strategy completed successfully: {self.config.strategy_id}")
        
        except Exception as e:
            self.logger.error(f"Error completing execution: {e}")
    
    def _handle_execution_failure(self, error_message: str) -> None:
        """Handle strategy execution failure"""
        try:
            with self._state_lock:
                # Update metrics
                self.metrics.end_time = time.time()
                self.metrics.error_count += 1
                self.metrics.last_error_message = error_message
                self.metrics.last_error_time = time.time()
                
                # Update status
                self._update_status(StrategyStatus.FAILED)
                self._is_running = False
                
                # Stop monitoring
                self._stop_monitoring()
                
                # Close senders
                self._close_all_senders()
                
                # Handle with error handler if available
                if self._error_handler:
                    self._error_handler.handle_error(error_message)
                
                # Emit failure signal
                self.strategy_failed.emit(self.config.strategy_id, error_message)
                
                self.logger.error(f"Strategy failed: {self.config.strategy_id} - {error_message}")
        
        except Exception as e:
            self.logger.critical(f"Error handling execution failure: {e}")
    
    # === STATUS AND PROGRESS MANAGEMENT ===
    
    def _update_status(self, new_status: StrategyStatus) -> None:
        """Update strategy status"""
        with self._state_lock:
            old_status = self.status
            self.status = new_status
            
            if old_status != new_status:
                self.status_changed.emit(self.config.strategy_id, new_status.name)
                self.logger.debug(f"Status changed: {old_status.name} -> {new_status.name}")
    
    def _update_progress(self, progress: float) -> None:
        """Update execution progress"""
        with self._state_lock:
            self._progress = max(0.0, min(100.0, progress))
            self.progress_updated.emit(self.config.strategy_id, self._progress)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive strategy status
        
        Returns:
            Dict containing status information
        """
        with self._state_lock:
            return {
                'strategy_id': self.config.strategy_id,
                'strategy_name': self.config.strategy_name,
                'strategy_type': self.config.strategy_type,
                'status': self.status.name,
                'is_running': self._is_running,
                'is_paused': self._is_paused,
                'progress': self._progress,
                'execution_time': time.time() - self._execution_start_time if self._is_running else 0.0,
                'metrics': self._get_current_metrics(),
                'senders_count': len(self.senders),
                'active_senders': sum(1 for sender in self.senders if sender.is_connected()),
                'config': {
                    'max_execution_time': self.config.max_execution_time,
                    'enable_threading': self.config.enable_threading,
                    'integrate_with_facade': self.config.integrate_with_facade
                }
            }
    
    # === MONITORING AND METRICS ===
    
    def _start_monitoring(self) -> None:
        """Start performance monitoring"""
        try:
            if self.config.enable_metrics:
                # Start performance timer
                if self._performance_timer:
                    self._performance_timer.start(int(self.config.metrics_interval * 1000))
                
                # Start monitoring thread
                if self.config.enable_detailed_logging:
                    self._monitoring_thread = threading.Thread(
                        target=self._monitoring_loop,
                        name=f"Monitor_{self.config.strategy_id}"
                    )
                    self._monitoring_thread.start()
        
        except Exception as e:
            self.logger.warning(f"Error starting monitoring: {e}")
    
    def _stop_monitoring(self) -> None:
        """Stop performance monitoring"""
        try:
            # Stop performance timer
            if self._performance_timer and self._performance_timer.isActive():
                self._performance_timer.stop()
            
            # Stop monitoring thread
            if self._monitoring_thread and self._monitoring_thread.is_alive():
                self._monitoring_thread.join(timeout=2.0)
        
        except Exception as e:
            self.logger.warning(f"Error stopping monitoring: {e}")
    
    def _monitoring_loop(self) -> None:
        """Monitoring loop for detailed logging"""
        while not self._stop_event.is_set() and self._is_running:
            try:
                if self.config.enable_detailed_logging:
                    metrics = self._get_current_metrics()
                    self.logger.debug(f"Strategy metrics: {metrics}")
                
                time.sleep(self.config.metrics_interval)
            
            except Exception as e:
                self.logger.warning(f"Error in monitoring loop: {e}")
                time.sleep(1.0)
    
    def _update_performance_metrics(self) -> None:
        """Update performance metrics (called by timer)"""
        try:
            with self._metrics_lock:
                # Update calculated metrics
                self.metrics.update_performance_metrics()
                
                # Update memory usage if available
                if self._memory_controller and hasattr(self._memory_controller, 'get_memory_usage'):
                    try:
                        memory_usage = self._memory_controller.get_memory_usage()
                        self.metrics.peak_memory_usage = max(self.metrics.peak_memory_usage, memory_usage)
                    except:
                        pass
                
                # Emit metrics update
                if self.config.emit_qt_signals:
                    current_metrics = self._get_current_metrics()
                    self.metrics_updated.emit(self.config.strategy_id, current_metrics)
        
        except Exception as e:
            self.logger.warning(f"Error updating performance metrics: {e}")
    
    def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics as dictionary"""
        with self._metrics_lock:
            return {
                'strategy_id': self.metrics.strategy_id,
                'duration': self.metrics.duration,
                'total_operations': self.metrics.total_operations,
                'successful_operations': self.metrics.successful_operations,
                'failed_operations': self.metrics.failed_operations,
                'success_rate': self.metrics.success_rate,
                'operations_per_second': self.metrics.operations_per_second,
                'average_operation_time': self.metrics.average_operation_time,
                'peak_memory_usage': self.metrics.peak_memory_usage,
                'network_bytes_sent': self.metrics.network_bytes_sent,
                'error_count': self.metrics.error_count,
                'error_rate': self.metrics.error_rate
            }
    
    def _get_final_metrics(self) -> Dict[str, Any]:
        """Get final comprehensive metrics"""
        metrics = self._get_current_metrics()
        
        # Add sender statistics
        sender_stats = []
        for sender in self.senders:
            if hasattr(sender, 'get_statistics'):
                sender_stats.append(sender.get_statistics())
        
        metrics['senders'] = sender_stats
        metrics['configuration'] = {
            'strategy_type': self.config.strategy_type,
            'max_execution_time': self.config.max_execution_time,
            'max_errors': self.config.max_errors,
            'enable_metrics': self.config.enable_metrics
        }
        
        return metrics
    
    def _update_facade_metrics(self) -> None:
        """Update facade metrics if configured"""
        try:
            if (self.config.update_facade_metrics and 
                self._facade_reference and 
                hasattr(self._facade_reference, 'statistics')):
                
                facade_stats = self._facade_reference.statistics
                facade_stats.strategy_operations += 1
                facade_stats.successful_operations += self.metrics.successful_operations
                facade_stats.failed_operations += self.metrics.failed_operations
        
        except Exception as e:
            self.logger.warning(f"Error updating facade metrics: {e}")
    
    # === ERROR HANDLING ===
    
    def _handle_error(self, error_type: str, error_message: str) -> None:
        """Handle strategy errors"""
        try:
            with self._metrics_lock:
                self.metrics.error_count += 1
                self.metrics.last_error_message = error_message
                self.metrics.last_error_time = time.time()
            
            # Log error
            self.logger.error(f"Strategy error ({error_type}): {error_message}")
            
            # Handle with error handler if available
            if self._error_handler:
                self._error_handler.handle_error(error_message)
            
            # Emit error signal
            self.error_occurred.emit(self.config.strategy_id, error_type, error_message)
            
            # Check if we should stop on error
            if self.config.stop_on_error:
                self.stop()
            
            # Check error threshold
            elif self.metrics.error_rate > self.config.error_threshold_rate * 100:
                self.logger.critical(f"Error rate exceeded threshold: {self.metrics.error_rate:.1f}%")
                self.stop()
        
        except Exception as e:
            self.logger.critical(f"Error in error handler: {e}")
    
    # === SENDER MANAGEMENT ===
    
    def add_sender(self, sender: Sender) -> bool:
        """Add a sender to the strategy"""
        try:
            if sender not in self.senders:
                self.senders.append(sender)
                self.logger.debug(f"Sender added: {getattr(sender, 'config', {}).get('sender_id', 'unknown')}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error adding sender: {e}")
            return False
    
    def remove_sender(self, sender: Sender) -> bool:
        """Remove a sender from the strategy"""
        try:
            if sender in self.senders:
                sender.close()
                self.senders.remove(sender)
                self.logger.debug(f"Sender removed: {getattr(sender, 'config', {}).get('sender_id', 'unknown')}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error removing sender: {e}")
            return False
    
    def _close_all_senders(self) -> None:
        """Close all senders"""
        for sender in self.senders:
            try:
                sender.close()
            except Exception as e:
                self.logger.warning(f"Error closing sender: {e}")
    
    # === UTILITY METHODS ===
    
    def _wait_for_pause_or_stop(self) -> bool:
        """
        Wait for pause or stop signals
        
        Returns:
            bool: True if should continue, False if should stop
        """
        # Check for stop
        if self._stop_event.is_set():
            return False
        
        # Wait for unpause if paused
        if not self._pause_event.wait(timeout=0.1):
            # Paused, check for stop while waiting
            return not self._stop_event.is_set()
        
        return True
    
    def __str__(self) -> str:
        """String representation"""
        return f"SenderStrategy(id={self.config.strategy_id}, type={self.config.strategy_type}, status={self.status.name})"
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (f"SenderStrategy(id='{self.config.strategy_id}', "
                f"name='{self.config.strategy_name}', "
                f"type='{self.config.strategy_type}', "
                f"status={self.status.name}, "
                f"senders={len(self.senders)})")


# === UTILITY FUNCTIONS ===

def create_strategy_config(strategy_type: str, strategy_name: str = "", **kwargs) -> StrategyConfiguration:
    """Create a strategy configuration with defaults"""
    return StrategyConfiguration(
        strategy_type=strategy_type,
        strategy_name=strategy_name or f"{strategy_type}_strategy",
        **kwargs
    )

def create_sender_config(sender_type: SenderType, target_host: str = "127.0.0.1", 
                        target_port: int = 12345, **kwargs) -> SenderConfiguration:
    """Create a sender configuration with defaults"""
    target = TransmissionTarget(host=target_host, port=target_port)
    return SenderConfiguration(
        sender_type=sender_type,
        target=target,
        **kwargs
    )

def create_mock_senders(count: int, fail_rate: float = 0.0) -> List[MockSender]:
    """Create multiple mock senders for testing"""
    senders = []
    for i in range(count):
        config = SenderConfiguration(
            sender_id=f"mock_sender_{i}",
            sender_type=SenderType.MOCK_SENDER
        )
        sender = MockSender(config, fail_rate=fail_rate)
        senders.append(sender)
    return senders


# === EXPORTS ===

__all__ = [
    # Enums
    'StrategyStatus', 'SenderType', 'TransmissionProtocol', 'Priority',
    
    # Data structures
    'NetworkInterface', 'TransmissionTarget', 'SenderConfiguration', 
    'StrategyConfiguration', 'StrategyMetrics',
    
    # Interfaces
    'Sender',
    
    # Base classes
    'BaseSender', 'SenderStrategy',
    
    # Concrete implementations
    'UDPSender', 'TCPSender', 'FileSender', 'MockSender',
    
    # Factory
    'SenderFactory',
    
    # Utility functions
    'create_strategy_config', 'create_sender_config', 'create_mock_senders'
]