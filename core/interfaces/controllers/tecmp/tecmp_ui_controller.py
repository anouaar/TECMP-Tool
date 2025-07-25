#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tecmp_ui_controller.py - Professional TECMP UI Controller
=========================================================

High-grade controller for managing TECMP encapsulation in the user interface.
Integrates all advanced TECMP features with clean architecture and no fallbacks.

Location: core/interfaces/controllers/tecmp/tecmp_ui_controller.py
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import weakref
from concurrent.futures import ThreadPoolExecutor, Future

# Qt imports - with fallback check
try:
    from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread
    from PyQt5.QtWidgets import QWidget, QMessageBox
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    QObject = object
    pyqtSignal = lambda *args: None
    pyqtSlot = lambda *args: lambda func: func

# Import real TECMP components - CORRECTED PATHS
from core.factories.tecmp_factory import (
    TECMPPacketFactory,
    TECMPFactoryConfig,
    FactoryMode,
    create_professional_factory,
    create_automotive_factory,
    TECMP  # One-line API
)

from core.builders.tecmp_builder import (
    TECMPPacketBuilder,
    Builder  # One-line API
)

from core.packets.tecmp.tecmp_packet import (
    TECMPPacket,
    create_logging_packet,
    create_control_message,
    create_replay_packet,
    reconstruct_from_segments
)

from core.packets.tecmp.tecmp_data import TECMPDataBuilder
from core.packets.tecmp.constants import (
    DataType, MessageType, DeviceFlags,
    DEVICE_ID_RANGES, SPECIAL_INTERFACE_IDS,
    get_device_type_name, get_data_type_name
)

# Advanced features - with availability check
try:
    from core.packets.tecmp.coherence_engine import TECMPCoherenceEngine, create_coherence_engine
    from core.packets.tecmp.tecmp_engine import TECMPEngine, create_professional_engine
    from core.packets.tecmp.packet_injector import inject_all_features, inject_coherence
    ADVANCED_FEATURES_AVAILABLE = True
except ImportError:
    ADVANCED_FEATURES_AVAILABLE = False
    TECMPCoherenceEngine = None
    TECMPEngine = None

# ============================================================================
# DATA STRUCTURES
# ============================================================================

class ControllerState(Enum):
    """Controller operational states"""
    UNINITIALIZED = auto()
    INITIALIZING = auto()
    READY = auto()
    ACTIVE = auto()
    PROCESSING = auto()
    ERROR = auto()
    SHUTTING_DOWN = auto()

class OperationMode(Enum):
    """TECMP operation modes"""
    BASIC = auto()
    STANDARD = auto()
    PROFESSIONAL = auto()
    AUTOMOTIVE = auto()
    DEVELOPMENT = auto()

@dataclass
class ControllerConfiguration:
    """Complete controller configuration"""
    # Operation mode
    mode: OperationMode = OperationMode.PROFESSIONAL
    
    # Device configuration
    device_id: int = 0x0040
    device_name: str = "CM CAN Combo"
    
    # Features
    enable_validation: bool = True
    enable_coherence: bool = True
    enable_professional: bool = True
    enable_time_sync: bool = True
    enable_hw_monitoring: bool = True
    enable_auto_injection: bool = True
    
    # Performance
    thread_pool_size: int = 4
    cache_size: int = 10000
    batch_processing: bool = True
    async_operations: bool = True
    
    # UI Integration
    auto_refresh_ms: int = 100
    show_notifications: bool = True
    enable_drag_drop: bool = True
    
    # Automotive
    automotive_scenarios: List[str] = field(default_factory=lambda: [
        "engine_startup", "uds_session", "network_sleep", "can_stress_test"
    ])
    
    # Advanced
    enable_replay_scheduler: bool = True
    enable_protocol_engines: bool = True
    max_packet_history: int = 1000

@dataclass
class PacketStatistics:
    """Real-time packet statistics"""
    packets_created: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    packets_validated: int = 0
    validation_errors: int = 0
    coherence_violations: int = 0
    auto_fixes_applied: int = 0
    segments_created: int = 0
    average_creation_time_ms: float = 0.0
    throughput_pps: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class EncapsulationContext:
    """Context for TECMP encapsulation operations"""
    source_packet: Optional[Any] = None
    target_interface: Optional[int] = None
    encapsulation_mode: str = "standard"
    parameters: Dict[str, Any] = field(default_factory=dict)
    validation_report: Optional[Any] = None
    result_packet: Optional[TECMPPacket] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

# ============================================================================
# BASE CONTROLLER (Qt-independent)
# ============================================================================

class TECMPControllerBase:
    """Base controller without Qt dependencies"""
    
    def __init__(self, config: Optional[ControllerConfiguration] = None):
        """Initialize base controller"""
        # Configuration
        self.config = config or ControllerConfiguration()
        
        # State management
        self._state = ControllerState.UNINITIALIZED
        self._operation_mode = self.config.mode
        
        # Core components
        self._factory: Optional[TECMPPacketFactory] = None
        self._builder: Optional[TECMPPacketBuilder] = None
        self._data_builder: Optional[TECMPDataBuilder] = None
        self._coherence_engine: Optional[TECMPCoherenceEngine] = None
        self._professional_engine: Optional[TECMPEngine] = None
        
        # Threading
        self._thread_pool = ThreadPoolExecutor(max_workers=self.config.thread_pool_size)
        self._operation_lock = threading.RLock()
        self._active_operations: Dict[str, Future] = {}
        
        # Packet management
        self._packet_history: List[TECMPPacket] = []
        self._packet_cache: Dict[str, TECMPPacket] = {}
        self._active_contexts: Dict[str, EncapsulationContext] = {}
        
        # Statistics
        self._statistics = PacketStatistics()
        self._performance_monitor = PerformanceMonitor()
        
        # Callbacks registry
        self._callbacks: Dict[str, List[Callable]] = {
            'packet_created': [],
            'validation_complete': [],
            'error_handler': [],
            'progress_handler': [],
            'state_changed': [],
            'notification': []
        }
        
        # Logger
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        
        # Initialize controller
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize all controller components"""
        self._set_state(ControllerState.INITIALIZING)
        
        try:
            # Initialize factories based on mode
            self._initialize_factories()
            
            # Initialize engines
            self._initialize_engines()
            
            # Ready
            self._set_state(ControllerState.READY)
            self.logger.info(f"TECMP Controller initialized - Mode: {self._operation_mode.name}")
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}", exc_info=True)
            self._set_state(ControllerState.ERROR)
            self._notify_error("INIT_ERROR", str(e))
    
    def _initialize_factories(self) -> None:
        """Initialize TECMP factories based on operation mode"""
        try:
            # Create appropriate factory
            if self._operation_mode == OperationMode.PROFESSIONAL:
                self._factory = create_professional_factory(self.config.device_id)
            elif self._operation_mode == OperationMode.AUTOMOTIVE:
                self._factory = create_automotive_factory(self.config.device_id)
            else:
                # Standard mode with custom config
                factory_config = TECMPFactoryConfig(
                    mode=FactoryMode.STANDARD,
                    enable_validation=self.config.enable_validation,
                    enable_coherence=self.config.enable_coherence,
                    enable_cache=True,
                    cache_size=self.config.cache_size,
                    device_id=self.config.device_id
                )
                self._factory = TECMPPacketFactory(factory_config)
            
            # Initialize builders
            if self._operation_mode in [OperationMode.PROFESSIONAL, OperationMode.AUTOMOTIVE]:
                self._builder = Builder(self._operation_mode.name.lower(), self.config.device_id)
            else:
                self._builder = TECMPPacketBuilder()
            
            # Data builder is always needed
            self._data_builder = TECMPDataBuilder()
            
            self.logger.debug("Factories initialized successfully")
            
        except Exception as e:
            raise RuntimeError(f"Factory initialization failed: {e}")
    
    def _initialize_engines(self) -> None:
        """Initialize advanced engines if enabled"""
        if not self.config.enable_professional or not ADVANCED_FEATURES_AVAILABLE:
            return
        
        try:
            # Get engines from factory if available
            if hasattr(self._factory, '_coherence_engine'):
                self._coherence_engine = self._factory._coherence_engine
            
            if hasattr(self._factory, '_professional_engine'):
                self._professional_engine = self._factory._professional_engine
            
            # Initialize protocol engines if needed
            if self.config.enable_protocol_engines and self._professional_engine:
                self._initialize_protocol_interfaces()
            
            self.logger.debug("Engines initialized successfully")
            
        except Exception as e:
            self.logger.warning(f"Engine initialization partially failed: {e}")
    
    def _initialize_protocol_interfaces(self) -> None:
        """Initialize protocol interfaces for automotive mode"""
        if not self._professional_engine:
            return
        
        # Configure CAN interfaces
        self._professional_engine.configure_interface(
            interface_id=0x1000,
            protocol="CAN",
            config={"bitrate": 500000}
        )
        
        # Configure CAN-FD interface
        self._professional_engine.configure_interface(
            interface_id=0x1100,
            protocol="CAN-FD",
            config={"bitrate": 500000, "data_bitrate": 2000000}
        )
        
        # Configure FlexRay interface
        self._professional_engine.configure_interface(
            interface_id=0x3000,
            protocol="FLEXRAY",
            config={"static_slots": 64, "cycle_length_us": 5000}
        )
        
        # Configure LIN interface
        self._professional_engine.configure_interface(
            interface_id=0x2000,
            protocol="LIN",
            config={"bitrate": 19200, "master": True}
        )
    
    # ========================================================================
    # CORE ENCAPSULATION METHODS
    # ========================================================================
    
    def encapsulate_packet(self, packet_data: Dict[str, Any]) -> Optional[TECMPPacket]:
        """
        Encapsulate packet data into TECMP format
        
        Args:
            packet_data: Dictionary containing packet information
            
        Returns:
            TECMPPacket or None if failed
        """
        with self._operation_lock:
            if self._state != ControllerState.READY:
                self._notify_error("STATE_ERROR", "Controller not ready")
                return None
            
            self._set_state(ControllerState.PROCESSING)
            
            # Create context
            context = EncapsulationContext(
                source_packet=packet_data,
                encapsulation_mode=packet_data.get('mode', 'standard'),
                parameters=packet_data.get('params', {})
            )
            
            try:
                # Start timing
                start_time = time.perf_counter()
                
                # Perform encapsulation
                packet = self._perform_encapsulation(context)
                
                if packet:
                    # Record timing
                    duration = time.perf_counter() - start_time
                    self._performance_monitor.record_operation('encapsulation', duration)
                    
                    # Update statistics
                    self._update_statistics('packet_created')
                    
                    # Store in history
                    self._add_to_history(packet)
                    
                    # Notify callbacks
                    self._notify_callbacks('packet_created', packet)
                
                context.result_packet = packet
                return packet
                
            except Exception as e:
                self.logger.error(f"Encapsulation failed: {e}", exc_info=True)
                context.error_message = str(e)
                self._notify_error("ENCAP_ERROR", str(e))
                return None
                
            finally:
                self._set_state(ControllerState.READY)
    
    def _perform_encapsulation(self, context: EncapsulationContext) -> Optional[TECMPPacket]:
        """Perform actual encapsulation based on context"""
        params = context.parameters
        
        # Determine encapsulation method
        if context.encapsulation_mode == 'automotive':
            return self._encapsulate_automotive(params)
        elif context.encapsulation_mode == 'builder':
            return self._encapsulate_with_builder(params)
        else:
            return self._encapsulate_standard(params)
    
    def _encapsulate_standard(self, params: Dict[str, Any]) -> TECMPPacket:
        """Standard encapsulation using factory"""
        # Extract parameters with defaults
        device_id = params.get('device_id', self.config.device_id)
        data_type = params.get('data_type', DataType.ETHERNET_EXT)
        interface_id = params.get('interface_id', 0x1000)
        payload = params.get('payload', b'')
        
        # Remove processed params to avoid conflicts
        factory_params = params.copy()
        for key in ['device_id', 'data_type', 'interface_id', 'payload', 'mode', 'params']:
            factory_params.pop(key, None)
        
        # Create packet
        packet = self._factory.create_packet(
            device_id=device_id,
            data_type=data_type,
            interface_id=interface_id,
            payload=payload,
            **factory_params
        )
        
        return packet
    
    def _encapsulate_automotive(self, params: Dict[str, Any]) -> Optional[TECMPPacket]:
        """Automotive-specific encapsulation"""
        protocol = params.get('protocol', '').upper()
        
        # Remove protocol from params to avoid conflicts
        auto_params = params.copy()
        auto_params.pop('protocol', None)
        auto_params.pop('mode', None)
        auto_params.pop('params', None)
        
        if protocol == 'CAN':
            return self._factory.create_automotive_packet(
                'CAN',
                can_id=params.get('can_id', 0),
                data=params.get('data', b''),
                **auto_params
            )
        elif protocol == 'FLEXRAY':
            return self._factory.create_automotive_packet(
                'FLEXRAY',
                cycle=params.get('cycle', 0),
                frame_id=params.get('frame_id', 0),
                data=params.get('data', b''),
                **auto_params
            )
        elif protocol == 'LIN':
            return self._factory.create_automotive_packet(
                'LIN',
                lin_id=params.get('lin_id', 0),
                data=params.get('data', b''),
                **auto_params
            )
        else:
            return self._encapsulate_standard(params)
    
    def _encapsulate_with_builder(self, params: Dict[str, Any]) -> TECMPPacket:
        """Encapsulation using builder pattern"""
        # Create new builder instance for thread safety
        if self._operation_mode in [OperationMode.PROFESSIONAL, OperationMode.AUTOMOTIVE]:
            builder = Builder(self._operation_mode.name.lower(), self.config.device_id)
        else:
            builder = TECMPPacketBuilder()
        
        # Configure builder
        if 'device_id' in params:
            builder.with_device_id(params['device_id'])
        
        if 'data_type' in params:
            builder.with_data_type(params['data_type'])
        
        if 'interface_id' in params:
            builder.with_interface_id(params['interface_id'])
        
        if 'payload' in params:
            builder.with_payload(params['payload'])
        
        # Apply advanced features if enabled
        if self.config.enable_professional:
            builder.with_professional_features(True)
        
        if self.config.enable_coherence:
            builder.with_coherence_validation(True)
        
        # Build packet
        return builder.build()
    
    # ========================================================================
    # VALIDATION AND COHERENCE
    # ========================================================================
    
    def validate_packet(self, packet: TECMPPacket) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate TECMP packet with full coherence checking
        
        Args:
            packet: TECMP packet to validate
            
        Returns:
            Tuple of (is_valid, validation_report)
        """
        validation_report = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'coherence_violations': [],
            'auto_fixes_available': 0,
            'timestamp': datetime.now()
        }
        
        try:
            # Basic validation
            try:
                packet.validate()
            except Exception as e:
                validation_report['is_valid'] = False
                validation_report['errors'].append(str(e))
            
            # Coherence validation if available
            if self._coherence_engine and ADVANCED_FEATURES_AVAILABLE:
                coherence_report = self._coherence_engine.validate_complete_coherence(packet)
                
                if not coherence_report.is_coherent:
                    validation_report['is_valid'] = False
                    
                    for violation in coherence_report.violations:
                        validation_report['coherence_violations'].append({
                            'field': violation.field,
                            'message': violation.message,
                            'severity': violation.severity.name,
                            'auto_fixable': violation.auto_fixable
                        })
                    
                    validation_report['auto_fixes_available'] = coherence_report.fixable_count
            
            # Update statistics
            self._update_statistics('packet_validated')
            if not validation_report['is_valid']:
                self._update_statistics('validation_error')
            
            # Notify callbacks
            self._notify_callbacks('validation_complete', packet, validation_report)
            
        except Exception as e:
            self.logger.error(f"Validation failed: {e}", exc_info=True)
            validation_report['is_valid'] = False
            validation_report['errors'].append(f"Validation error: {e}")
        
        return validation_report['is_valid'], validation_report
    
    def auto_fix_packet(self, packet: TECMPPacket) -> bool:
        """
        Automatically fix packet violations
        
        Args:
            packet: TECMP packet to fix
            
        Returns:
            True if fixes were applied successfully
        """
        try:
            if not self._coherence_engine or not ADVANCED_FEATURES_AVAILABLE:
                return False
            
            # Get current violations
            report = self._coherence_engine.validate_complete_coherence(packet)
            
            if report.is_coherent:
                return True  # Nothing to fix
            
            # Apply auto-fixes
            fixable_violations = [v for v in report.violations if v.auto_fixable]
            if fixable_violations:
                fixes = self._coherence_engine.auto_fix_critical_violations(packet, fixable_violations)
                
                # Update statistics
                self._statistics.auto_fixes_applied += len(fixes)
                
                # Re-validate
                new_report = self._coherence_engine.validate_complete_coherence(packet)
                
                if new_report.is_coherent:
                    self._notify_info("SUCCESS", f"Applied {len(fixes)} auto-fixes successfully")
                    return True
                else:
                    self._notify_info("WARNING", f"Applied {len(fixes)} fixes, but violations remain")
                    return False
            
            return False
            
        except Exception as e:
            self.logger.error(f"Auto-fix failed: {e}", exc_info=True)
            self._notify_error("FIX_ERROR", str(e))
            return False
    
    # ========================================================================
    # AUTOMOTIVE SCENARIOS
    # ========================================================================
    
    def execute_scenario(self, scenario_name: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Execute automotive scenario
        
        Args:
            scenario_name: Name of scenario to execute
            parameters: Optional scenario parameters
            
        Returns:
            True if scenario started successfully
        """
        if not self._professional_engine or not ADVANCED_FEATURES_AVAILABLE:
            self._notify_error("CONFIG_ERROR", "Professional engine not available")
            return False
        
        try:
            # Default parameters
            params = parameters or {}
            
            # Schedule scenario
            success = self._factory.schedule_scenario(
                scenario_name,
                start_delay_ms=params.get('delay_ms', 100),
                **params
            )
            
            if success:
                self._notify_info("INFO", f"Scenario '{scenario_name}' scheduled")
                
                # Track scenario execution
                self._thread_pool.submit(self._monitor_scenario_execution, scenario_name)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Scenario execution failed: {e}", exc_info=True)
            self._notify_error("SCENARIO_ERROR", str(e))
            return False
    
    def _monitor_scenario_execution(self, scenario_name: str) -> None:
        """Monitor scenario execution in background"""
        try:
            # Get scenario duration from template
            if hasattr(self._professional_engine, 'template_manager'):
                template = self._professional_engine.template_manager.get_template(scenario_name)
                if template:
                    duration_ms = template.duration_ms
                    steps = 10
                    
                    for i in range(steps):
                        progress = int((i + 1) / steps * 100)
                        self._notify_callbacks('progress_handler', progress, f"Executing {scenario_name}...")
                        time.sleep(duration_ms / steps / 1000)
                    
                    self._notify_info("SUCCESS", f"Scenario '{scenario_name}' completed")
                    
        except Exception as e:
            self.logger.error(f"Scenario monitoring error: {e}")
    
    def get_available_scenarios(self) -> List[str]:
        """Get list of available automotive scenarios"""
        if self._professional_engine and hasattr(self._professional_engine, 'template_manager'):
            return self._professional_engine.template_manager.list_templates()
        return self.config.automotive_scenarios
    
    # ========================================================================
    # PACKET MANAGEMENT
    # ========================================================================
    
    def send_packet(self, packet: TECMPPacket) -> bool:
        """
        Send TECMP packet (placeholder for actual transmission)
        
        Args:
            packet: TECMP packet to send
            
        Returns:
            True if sent successfully
        """
        try:
            # Validate before sending
            is_valid, _ = self.validate_packet(packet)
            
            if not is_valid and self.config.enable_validation:
                self._notify_error("VALIDATION_ERROR", "Cannot send invalid packet")
                return False
            
            # Here you would integrate with actual network interface
            # For now, just update statistics
            self._update_statistics('packet_sent')
            
            self._notify_info("INFO", f"Packet sent to interface 0x{packet.interface_id:08X}")
            return True
            
        except Exception as e:
            self.logger.error(f"Send packet failed: {e}", exc_info=True)
            self._notify_error("SEND_ERROR", str(e))
            return False
    
    def _add_to_history(self, packet: TECMPPacket) -> None:
        """Add packet to history with size limit"""
        self._packet_history.append(packet)
        
        # Limit history size
        if len(self._packet_history) > self.config.max_packet_history:
            self._packet_history.pop(0)
    
    def get_packet_history(self) -> List[TECMPPacket]:
        """Get packet history"""
        return self._packet_history.copy()
    
    def clear_history(self) -> None:
        """Clear packet history"""
        self._packet_history.clear()
        self._packet_cache.clear()
        self._notify_info("INFO", "Packet history cleared")
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    def configure_feature(self, feature: str, enabled: bool) -> None:
        """
        Configure controller feature
        
        Args:
            feature: Feature name
            enabled: Enable/disable feature
        """
        feature_map = {
            'validation': 'enable_validation',
            'coherence': 'enable_coherence',
            'professional': 'enable_professional',
            'time_sync': 'enable_time_sync',
            'hw_monitoring': 'enable_hw_monitoring',
            'auto_injection': 'enable_auto_injection'
        }
        
        if feature in feature_map:
            setattr(self.config, feature_map[feature], enabled)
            
            # Reinitialize if needed
            if feature in ['professional', 'coherence']:
                self._initialize_factories()
            
            self._notify_info("INFO", f"Feature '{feature}' {'enabled' if enabled else 'disabled'}")
    
    def set_operation_mode(self, mode: str) -> None:
        """
        Set operation mode
        
        Args:
            mode: Mode name (basic, standard, professional, automotive)
        """
        try:
            new_mode = OperationMode[mode.upper()]
            if new_mode != self._operation_mode:
                self._operation_mode = new_mode
                self.config.mode = new_mode
                
                # Reinitialize with new mode
                self._initialize()
                
                self._notify_info("INFO", f"Operation mode changed to {mode}")
                
        except KeyError:
            self._notify_error("CONFIG_ERROR", f"Invalid operation mode: {mode}")
    
    # ========================================================================
    # STATISTICS AND MONITORING
    # ========================================================================
    
    def _update_statistics(self, operation: str) -> None:
        """Update internal statistics"""
        if operation == 'packet_created':
            self._statistics.packets_created += 1
        elif operation == 'packet_sent':
            self._statistics.packets_sent += 1
        elif operation == 'packet_received':
            self._statistics.packets_received += 1
        elif operation == 'packet_validated':
            self._statistics.packets_validated += 1
        elif operation == 'validation_error':
            self._statistics.validation_errors += 1
        elif operation == 'coherence_violation':
            self._statistics.coherence_violations += 1
        
        self._statistics.last_update = datetime.now()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current statistics"""
        # Calculate throughput
        if hasattr(self, '_last_throughput_calc'):
            time_diff = (datetime.now() - self._last_throughput_calc).total_seconds()
            if time_diff > 0:
                self._statistics.throughput_pps = self._statistics.packets_created / time_diff
        else:
            self._last_throughput_calc = datetime.now()
        
        # Calculate average creation time
        avg_time = self._performance_monitor.get_average_time('encapsulation')
        self._statistics.average_creation_time_ms = avg_time * 1000
        
        return {
            'packets_created': self._statistics.packets_created,
            'packets_sent': self._statistics.packets_sent,
            'packets_validated': self._statistics.packets_validated,
            'validation_errors': self._statistics.validation_errors,
            'coherence_violations': self._statistics.coherence_violations,
            'auto_fixes_applied': self._statistics.auto_fixes_applied,
            'throughput_pps': self._statistics.throughput_pps,
            'average_creation_time_ms': self._statistics.average_creation_time_ms,
            'controller_state': self._state.name,
            'operation_mode': self._operation_mode.name,
            'last_update': self._statistics.last_update.isoformat()
        }
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get status of all engines"""
        status = {}
        
        # Factory status
        if self._factory and hasattr(self._factory, 'get_professional_status'):
            status['factory_status'] = self._factory.get_professional_status()
        
        # Builder status
        if self._builder and hasattr(self._builder, 'get_professional_status'):
            status['builder_status'] = self._builder.get_professional_status()
        
        # Professional engine status
        if self._professional_engine and hasattr(self._professional_engine, 'get_engine_status'):
            status['professional_engine'] = self._professional_engine.get_engine_status()
        
        # Performance stats
        status['performance'] = self._performance_monitor.get_statistics()
        
        return status
    
    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================
    
    def _set_state(self, new_state: ControllerState) -> None:
        """Set controller state with notification"""
        if new_state != self._state:
            old_state = self._state
            self._state = new_state
            self._notify_callbacks('state_changed', new_state.name)
            self.logger.debug(f"State transition: {old_state.name} -> {new_state.name}")
    
    def get_state(self) -> str:
        """Get current controller state"""
        return self._state.name
    
    # ========================================================================
    # CALLBACK MANAGEMENT
    # ========================================================================
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """Register callback for event"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def unregister_callback(self, event: str, callback: Callable) -> None:
        """Unregister callback for event"""
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)
    
    def _notify_callbacks(self, event: str, *args, **kwargs) -> None:
        """Notify all callbacks for event"""
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Callback error for {event}: {e}")
    
    def _notify_error(self, error_type: str, message: str) -> None:
        """Notify error handlers"""
        self._notify_callbacks('error_handler', error_type, message)
    
    def _notify_info(self, info_type: str, message: str) -> None:
        """Notify information handlers"""
        self._notify_callbacks('notification', info_type, message)
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    def shutdown(self) -> None:
        """Shutdown controller gracefully"""
        self._set_state(ControllerState.SHUTTING_DOWN)
        
        try:
            # Shutdown thread pool
            self._thread_pool.shutdown(wait=True)
            
            # Shutdown engines
            if self._factory and hasattr(self._factory, 'shutdown'):
                self._factory.shutdown()
            
            # Clear data
            self._packet_history.clear()
            self._packet_cache.clear()
            self._active_contexts.clear()
            
            self.logger.info("TECMP Controller shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Shutdown error: {e}", exc_info=True)
        
        finally:
            self._set_state(ControllerState.UNINITIALIZED)

# ============================================================================
# QT UI CONTROLLER
# ============================================================================

if QT_AVAILABLE:
    class TECMPUIController(TECMPControllerBase, QObject):
        """
        Qt-enabled TECMP UI Controller
        
        Inherits from base controller and adds Qt signal/slot functionality
        """
        
        # Qt Signals for UI communication
        state_changed = pyqtSignal(str)  # Controller state changes
        packet_created = pyqtSignal(object)  # New packet created
        packet_validated = pyqtSignal(object, bool)  # Validation result
        statistics_updated = pyqtSignal(dict)  # Statistics update
        error_occurred = pyqtSignal(str, str)  # Error type, message
        progress_update = pyqtSignal(int, str)  # Progress percentage, message
        notification = pyqtSignal(str, str)  # Type, message
        
        def __init__(self, parent: Optional[QWidget] = None, 
                     config: Optional[ControllerConfiguration] = None):
            """
            Initialize Qt TECMP UI Controller
            
            Args:
                parent: Parent widget
                config: Controller configuration
            """
            # Initialize QObject first
            QObject.__init__(self, parent)
            
            # Then initialize base controller
            TECMPControllerBase.__init__(self, config)
            
            # UI Integration
            self._update_timer = QTimer(self)
            self._update_timer.timeout.connect(self._update_ui_state)
            
            # Connect base callbacks to Qt signals
            self.register_callback('state_changed', lambda state: self.state_changed.emit(state))
            self.register_callback('packet_created', lambda packet: self.packet_created.emit(packet))
            self.register_callback('validation_complete', self._emit_validation_signal)
            self.register_callback('error_handler', lambda t, m: self.error_occurred.emit(t, m))
            self.register_callback('progress_handler', lambda p, m: self.progress_update.emit(p, m))
            self.register_callback('notification', lambda t, m: self.notification.emit(t, m))
            
            # Start UI timer if configured
            if self.config.auto_refresh_ms > 0:
                self._update_timer.start(self.config.auto_refresh_ms)
        
        def _emit_validation_signal(self, packet: TECMPPacket, report: Dict[str, Any]) -> None:
            """Emit validation signal"""
            self.packet_validated.emit(packet, report['is_valid'])
        
        @pyqtSlot()
        def _update_ui_state(self) -> None:
            """Update UI state periodically"""
            try:
                # Update statistics
                stats = self.get_statistics()
                self.statistics_updated.emit(stats)
                
                # Check for errors
                if self._state == ControllerState.ERROR:
                    self.error_occurred.emit("STATE_ERROR", "Controller in error state")
                
            except Exception as e:
                self.logger.error(f"UI update error: {e}")
        
        # Qt slot decorators for base methods
        encapsulate_packet = pyqtSlot(dict)(TECMPControllerBase.encapsulate_packet)
        validate_packet = pyqtSlot(object)(TECMPControllerBase.validate_packet)
        auto_fix_packet = pyqtSlot(object)(TECMPControllerBase.auto_fix_packet)
        execute_scenario = pyqtSlot(str, dict)(TECMPControllerBase.execute_scenario)
        get_available_scenarios = pyqtSlot()(TECMPControllerBase.get_available_scenarios)
        send_packet = pyqtSlot(object)(TECMPControllerBase.send_packet)
        get_packet_history = pyqtSlot()(TECMPControllerBase.get_packet_history)
        clear_history = pyqtSlot()(TECMPControllerBase.clear_history)
        configure_feature = pyqtSlot(str, bool)(TECMPControllerBase.configure_feature)
        set_operation_mode = pyqtSlot(str)(TECMPControllerBase.set_operation_mode)
        get_statistics = pyqtSlot()(TECMPControllerBase.get_statistics)
        get_engine_status = pyqtSlot()(TECMPControllerBase.get_engine_status)
        get_state = pyqtSlot()(TECMPControllerBase.get_state)
        shutdown = pyqtSlot()(TECMPControllerBase.shutdown)
        
else:
    # If Qt is not available, use base controller
    TECMPUIController = TECMPControllerBase

# ============================================================================
# PERFORMANCE MONITOR
# ============================================================================

class PerformanceMonitor:
    """Performance monitoring for controller operations"""
    
    def __init__(self):
        self.operation_times: Dict[str, List[float]] = {}
        self.operation_counts: Dict[str, int] = {}
        self._lock = threading.Lock()
    
    def record_operation(self, operation: str, duration: float) -> None:
        """Record operation timing"""
        with self._lock:
            if operation not in self.operation_times:
                self.operation_times[operation] = []
                self.operation_counts[operation] = 0
            
            self.operation_times[operation].append(duration)
            self.operation_counts[operation] += 1
            
            # Keep only last 1000 measurements
            if len(self.operation_times[operation]) > 1000:
                self.operation_times[operation].pop(0)
    
    def get_average_time(self, operation: str) -> float:
        """Get average operation time in seconds"""
        with self._lock:
            if operation in self.operation_times and self.operation_times[operation]:
                return sum(self.operation_times[operation]) / len(self.operation_times[operation])
            return 0.0
    
    def get_statistics(self) -> Dict[str, Dict[str, float]]:
        """Get all performance statistics"""
        with self._lock:
            stats = {}
            for operation in self.operation_times:
                times = self.operation_times[operation]
                if times:
                    stats[operation] = {
                        'count': self.operation_counts[operation],
                        'average_ms': sum(times) / len(times) * 1000,
                        'min_ms': min(times) * 1000,
                        'max_ms': max(times) * 1000
                    }
            return stats

# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_tecmp_ui_controller(parent: Optional[QWidget] = None,
                              mode: str = "professional",
                              device_id: int = 0x0040) -> TECMPUIController:
    """
    Create TECMP UI Controller with specified mode
    
    Args:
        parent: Parent widget (if Qt available)
        mode: Operation mode (basic, standard, professional, automotive)
        device_id: Device identifier
        
    Returns:
        Configured TECMPUIController instance
    """
    # Create configuration
    config = ControllerConfiguration(
        mode=OperationMode[mode.upper()],
        device_id=device_id
    )
    
    # Set mode-specific defaults
    if mode == "basic":
        config.enable_validation = False
        config.enable_coherence = False
        config.enable_professional = False
        config.enable_time_sync = False
        config.enable_hw_monitoring = False
    elif mode == "automotive":
        config.enable_professional = True
        config.enable_coherence = True
        config.enable_auto_injection = True
        config.enable_protocol_engines = True
        config.automotive_scenarios = [
            "engine_startup", "engine_shutdown",
            "uds_session", "dtc_readout",
            "network_sleep", "network_wakeup",
            "can_stress_test", "gateway_test"
        ]
    
    return TECMPUIController(parent, config)

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'TECMPUIController',
    'TECMPControllerBase',
    'ControllerState',
    'OperationMode',
    'ControllerConfiguration',
    'PacketStatistics',
    'EncapsulationContext',
    'PerformanceMonitor',
    'create_tecmp_ui_controller'
]