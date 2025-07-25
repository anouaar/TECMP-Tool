#!/usr/bin/env python
# coding: utf-8
"""Protocol Stack Controller - Version complete corrigee"""

import logging
import copy
import time
import weakref
from typing import List, Dict, Any, Optional, Union, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from PyQt5.QtCore import QObject, pyqtSignal, QTimer

# IMPORTS DES FACTORIES
from core.factories.tcp_factory import TCPFactory
from core.factories.udp_factory import UDPFactory
from core.factories.ethernet_factory import EthernetPacketFactory
from core.factories.ip_packet_factory import IPPacketFactory
from core.factories.arp_factory import ARPFactory
from core.factories.vlan_factory import VLANFactory
from core.factories.tecmp_factory import TECMPPacketFactory

# IMPORT DU VALIDATOR
try:
    from core.interfaces.controllers.protocol.protocol_validator import ProtocolValidator
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False


class StackOperation(Enum):
    ADD_PROTOCOL = auto()
    REMOVE_PROTOCOL = auto()
    MOVE_PROTOCOL = auto()
    UPDATE_CONFIG = auto()
    CLEAR_STACK = auto()
    SET_STACK = auto()


@dataclass
class StackOperationRecord:
    operation: StackOperation
    timestamp: float
    protocol_name: Optional[str] = None
    protocol_index: Optional[int] = None
    old_config: Optional[List[Any]] = None
    new_config: Optional[List[Any]] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StackStatistics:
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    protocols_added: int = 0
    protocols_removed: int = 0
    protocols_moved: int = 0
    configurations_updated: int = 0
    validation_failures: int = 0
    packet_constructions: int = 0
    last_operation_time: Optional[float] = None
    session_start_time: float = field(default_factory=time.time)


class ProtocolStackController(QObject):
    """Protocol Stack Controller avec intégration des factories réelles."""
    
    # Qt signals
    stack_changed = pyqtSignal(list)
    protocol_added = pyqtSignal(str, int)
    protocol_removed = pyqtSignal(str, int)
    protocol_moved = pyqtSignal(str, int, int)
    protocol_configured = pyqtSignal(str, int, object)
    validation_result = pyqtSignal(bool, str)
    dependency_warning = pyqtSignal(str, str)
    validation_error = pyqtSignal(str, str, str)
    operation_started = pyqtSignal(str, str)
    operation_completed = pyqtSignal(str, str, bool)
    operation_failed = pyqtSignal(str, str, str)
    packet_construction_started = pyqtSignal()
    packet_construction_completed = pyqtSignal(object)
    packet_construction_failed = pyqtSignal(str)
    statistics_updated = pyqtSignal(object)
    
    # MAPPAGE DES FACTORIES
    PROTOCOL_FACTORIES = {
        "Ethernet": EthernetPacketFactory,
        "IPv4": IPPacketFactory,
        "IPv6": IPPacketFactory,
        "TCP": TCPFactory,
        "UDP": UDPFactory,
        "VLAN": VLANFactory,
        "ARP": ARPFactory,
        "TECMP": TECMPPacketFactory
    }
    
    # DEFAULT_CONFIGS COMPLÈTES
    DEFAULT_CONFIGS = {
        "Ethernet": {
            "src_mac": "02:00:00:00:00:01",
            "dst_mac": "02:00:00:00:00:02",
            "ether_type": 0x0800
        },
        "IPv4": {
            "version": 4,
            "src_ip": "10.0.0.1",
            "dst_ip": "10.0.0.2",
            "protocol": 6
        },
        "IPv6": {
            "version": 6,
            "src_ip": "2001:db8::1",
            "dst_ip": "2001:db8::2",
            "protocol": 6
        },
        "TCP": {
            "src_port": 49152,
            "dst_port": 80,
            "seq_number": 0,
            "ack_number": 0,
            "data_offset": 5,
            "reserved": 0,
            "flags": 0x02,
            "window_size": 8192,
            "checksum": 0,
            "urgent_pointer": 0
        },
        "UDP": {
            "src_port": 49152,
            "dst_port": 53,
            "length": 8,
            "checksum": 0
        },
        "VLAN": {
            "vlan_id": 100,
            "priority": 0,
            "cfi": 0,
            "ether_type": 0x0800
        },
        "ARP": {
            "hw_type": 1,
            "proto_type": 0x0800,
            "hw_len": 6,
            "proto_len": 4,
            "operation": 1,
            "sender_mac": "02:00:00:00:00:01",
            "sender_ip": "10.0.0.1",
            "target_mac": "00:00:00:00:00:00",
            "target_ip": "10.0.0.2"
        },
        "TECMP": {
            "device_id": 0x0080,
            "counter": 0,
            "version": 1,
            "message_type": 0x01,
            "data_type": 0x0080,
            "interface_id": 1,
            "device_flags": 0,
            "data_flags": 0,
            "timestamp": 0
        }
    }

    def __init__(self, facade=None, validator=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("TECMP-Tool.ProtocolStackController")
        
        if validator is None and VALIDATOR_AVAILABLE:
            self.validator = ProtocolValidator()
        else:
            self.validator = validator
        
        self.facade = facade
        self._current_stack = []
        self._stack_history = []
        self._max_history = 50
        self._protocol_factories = {}
        self._init_factories()
        
        self._packet_manager = None
        self._builders = None
        self._ui_builders = None
        self._views = None
        
        self._strict_validation = False  # Non strict par défaut
        self._auto_validate = True
        self._auto_build_packets = False
        self._max_stack_size = 20
        
        self._operation_history = []
        self._statistics = StackStatistics()
        
        self._performance_metrics = {
            'average_operation_time': 0.0,
            'slowest_operation_time': 0.0,
            'fastest_operation_time': float('inf'),
            'total_processing_time': 0.0
        }
        
        self._error_recovery_enabled = True
        self._last_known_good_stack = []
        
        if self.validator:
            self.validator.set_strict_validation(self._strict_validation)
        
        self.logger.info("ProtocolStackController initialized successfully")

    # ADD PROPERTY FOR STRICT VALIDATION - MINIMAL CHANGE NEEDED
    @property
    def strict_validation(self):
        """Get strict validation mode"""
        return self._strict_validation
    
    @strict_validation.setter
    def strict_validation(self, value):
        """Set strict validation mode"""
        self._strict_validation = bool(value)
        if self.validator:
            self.validator.set_strict_validation(self._strict_validation)

    def _init_factories(self):
        try:
            for protocol_name, factory_class in self.PROTOCOL_FACTORIES.items():
                self._protocol_factories[protocol_name] = factory_class
                self.logger.debug(f"Initialized {protocol_name} factory: {factory_class.__name__}")
        except Exception as e:
            self.logger.error(f"Error initializing factories: {e}")

    def _get_protocol_name(self, instance: Any) -> str:
        """Extraire le nom du protocole d'une instance."""
        class_name = instance.__class__.__name__
        if class_name.endswith('Packet'):
            return class_name[:-6]
        return class_name

    def _create_protocol_instance(self, protocol_name: str, config: Dict[str, Any]) -> Any:
        try:
            factory = self._protocol_factories.get(protocol_name)
            if not factory:
                raise ValueError(f"Protocol factory not found: {protocol_name}")
            
            full_config = copy.deepcopy(self.DEFAULT_CONFIGS.get(protocol_name, {}))
            full_config.update(config)
            
            if protocol_name == "IPv4":
                full_config["version"] = 4
            elif protocol_name == "IPv6":
                full_config["version"] = 6
            
            instance = factory.create_packet(**full_config)
            
            self.logger.debug(f"Created {protocol_name} instance successfully")
            return instance
            
        except Exception as e:
            self.logger.error(f"Failed to create {protocol_name} instance: {e}")
            raise
    
    def _validate_protocol_instance(self, protocol_name: str, instance: Any) -> Tuple[bool, str]:
        try:
            if hasattr(instance, 'validate') and callable(getattr(instance, 'validate')):
                try:
                    is_valid = instance.validate()
                    return is_valid, "Valid" if is_valid else "Validation failed"
                except Exception as e:
                    if not self._strict_validation:
                        return True, f"Validation skipped: {e}"
                    return False, f"Validation error: {e}"
            return True, "Valid (no validation method)"
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def _build_packet_from_stack(self) -> Optional[Any]:
        try:
            if not self._current_stack:
                return None
            
            base_packet = self._current_stack[0]
            current_packet = base_packet
            
            for i in range(1, len(self._current_stack)):
                next_protocol = self._current_stack[i]
                
                if hasattr(current_packet, 'set_payload'):
                    current_packet.set_payload(next_protocol)
                elif hasattr(current_packet, 'payload'):
                    current_packet.payload = next_protocol
                elif hasattr(current_packet, 'encapsulate'):
                    current_packet.encapsulate(next_protocol)
                else:
                    self.logger.warning(
                        f"Cannot encapsulate {self._get_protocol_name(next_protocol)} "
                        f"in {self._get_protocol_name(current_packet)}"
                    )
                
                current_packet = next_protocol
            
            return base_packet
            
        except Exception as e:
            self.logger.error(f"Failed to build packet: {e}")
            return None

    def add_protocol(self, protocol_name: str, config: Optional[Dict[str, Any]] = None, 
                    index: Optional[int] = None) -> bool:
        operation_start = time.time()
        
        try:
            self.operation_started.emit("add_protocol", protocol_name)
            self.logger.debug(f"Adding protocol '{protocol_name}'")
            
            if not protocol_name or not isinstance(protocol_name, str):
                raise ValueError("Protocol name must be a non-empty string")
            
            if protocol_name not in self.PROTOCOL_FACTORIES:
                raise ValueError(f"Unknown protocol: {protocol_name}")
            
            if len(self._current_stack) >= self._max_stack_size:
                raise ValueError(f"Stack size limit reached ({self._max_stack_size})")
            
            if config is None:
                config = {}
            
            old_stack = copy.deepcopy(self._current_stack)
            protocol_instance = self._create_protocol_instance(protocol_name, config)
            
            is_valid, error_msg = self._validate_protocol_instance(protocol_name, protocol_instance)
            if not is_valid and self._strict_validation:
                raise ValueError(f"Protocol validation failed: {error_msg}")
            elif not is_valid:
                self.dependency_warning.emit(protocol_name, error_msg)
            
            if index is not None:
                if 0 <= index <= len(self._current_stack):
                    self._current_stack.insert(index, protocol_instance)
                    actual_index = index
                else:
                    raise ValueError(f"Invalid index {index}")
            else:
                self._current_stack.append(protocol_instance)
                actual_index = len(self._current_stack) - 1
            
            if self._auto_validate:
                stack_valid, stack_error = self._validate_current_stack()
                if not stack_valid and self._strict_validation:
                    self._current_stack = old_stack
                    raise ValueError(f"Stack validation failed: {stack_error}")
                elif not stack_valid:
                    self.validation_result.emit(False, stack_error)
                else:
                    self.validation_result.emit(True, "Stack is valid")
            
            self._add_to_history(old_stack)
            self._update_statistics(StackOperation.ADD_PROTOCOL, True)
            
            if self._auto_build_packets:
                self._build_packet_async()
            
            self.protocol_added.emit(protocol_name, actual_index)
            self.stack_changed.emit(copy.deepcopy(self._current_stack))
            self.operation_completed.emit("add_protocol", protocol_name, True)
            
            operation_time = time.time() - operation_start
            self._record_operation(StackOperationRecord(
                operation=StackOperation.ADD_PROTOCOL,
                timestamp=time.time(),
                protocol_name=protocol_name,
                protocol_index=actual_index,
                old_config=old_stack,
                new_config=copy.deepcopy(self._current_stack),
                success=True,
                metadata={'operation_time': operation_time}
            ))
            
            self.logger.info(f"Protocol '{protocol_name}' added successfully")
            return True
            
        except Exception as e:
            operation_time = time.time() - operation_start
            error_msg = f"Failed to add protocol '{protocol_name}': {e}"
            self.logger.error(error_msg)
            
            self._update_statistics(StackOperation.ADD_PROTOCOL, False)
            self.operation_failed.emit("add_protocol", protocol_name, str(e))
            
            self._record_operation(StackOperationRecord(
                operation=StackOperation.ADD_PROTOCOL,
                timestamp=time.time(),
                protocol_name=protocol_name,
                success=False,
                error_message=str(e),
                metadata={'operation_time': operation_time}
            ))
            
            return False

    def remove_protocol(self, index: int) -> bool:
        operation_start = time.time()
        
        try:
            if not 0 <= index < len(self._current_stack):
                raise ValueError(f"Invalid protocol index: {index}")
            
            protocol_instance = self._current_stack[index]
            protocol_name = self._get_protocol_name(protocol_instance)
            
            self.operation_started.emit("remove_protocol", protocol_name)
            self.logger.debug(f"Removing protocol '{protocol_name}'")
            
            old_stack = copy.deepcopy(self._current_stack)
            self._current_stack.pop(index)
            
            if self._auto_validate and self._current_stack:
                stack_valid, stack_error = self._validate_current_stack()
                if not stack_valid and self._strict_validation:
                    self._current_stack = old_stack
                    raise ValueError(f"Stack validation failed: {stack_error}")
                elif not stack_valid:
                    self.dependency_warning.emit(protocol_name, stack_error)
                    self.validation_result.emit(False, stack_error)
                else:
                    self.validation_result.emit(True, "Stack is valid")
            
            self._add_to_history(old_stack)
            self._update_statistics(StackOperation.REMOVE_PROTOCOL, True)
            
            if self._auto_build_packets and self._current_stack:
                self._build_packet_async()
            
            self.protocol_removed.emit(protocol_name, index)
            self.stack_changed.emit(copy.deepcopy(self._current_stack))
            self.operation_completed.emit("remove_protocol", protocol_name, True)
            
            operation_time = time.time() - operation_start
            self._record_operation(StackOperationRecord(
                operation=StackOperation.REMOVE_PROTOCOL,
                timestamp=time.time(),
                protocol_name=protocol_name,
                protocol_index=index,
                old_config=old_stack,
                new_config=copy.deepcopy(self._current_stack),
                success=True,
                metadata={'operation_time': operation_time}
            ))
            
            self.logger.info(f"Protocol '{protocol_name}' removed successfully")
            return True
            
        except Exception as e:
            self._update_statistics(StackOperation.REMOVE_PROTOCOL, False)
            self.operation_failed.emit("remove_protocol", str(index), str(e))
            return False

    def move_protocol(self, from_index: int, to_index: int) -> bool:
        operation_start = time.time()
        
        try:
            if not (0 <= from_index < len(self._current_stack)):
                raise ValueError(f"Invalid source index: {from_index}")
            if not (0 <= to_index < len(self._current_stack)):
                raise ValueError(f"Invalid destination index: {to_index}")
            if from_index == to_index:
                return True
            
            protocol_instance = self._current_stack[from_index]
            protocol_name = self._get_protocol_name(protocol_instance)
            
            self.operation_started.emit("move_protocol", protocol_name)
            old_stack = copy.deepcopy(self._current_stack)
            
            self._current_stack.insert(to_index, self._current_stack.pop(from_index))
            
            if self._auto_validate:
                stack_valid, stack_error = self._validate_current_stack()
                if not stack_valid and self._strict_validation:
                    self._current_stack = old_stack
                    raise ValueError(f"Stack validation failed: {stack_error}")
                elif not stack_valid:
                    self.validation_result.emit(False, stack_error)
                else:
                    self.validation_result.emit(True, "Stack is valid")
            
            self._add_to_history(old_stack)
            self._update_statistics(StackOperation.MOVE_PROTOCOL, True)
            
            if self._auto_build_packets:
                self._build_packet_async()
            
            self.protocol_moved.emit(protocol_name, from_index, to_index)
            self.stack_changed.emit(copy.deepcopy(self._current_stack))
            self.operation_completed.emit("move_protocol", protocol_name, True)
            
            operation_time = time.time() - operation_start
            self._record_operation(StackOperationRecord(
                operation=StackOperation.MOVE_PROTOCOL,
                timestamp=time.time(),
                protocol_name=protocol_name,
                protocol_index=from_index,
                old_config=old_stack,
                new_config=copy.deepcopy(self._current_stack),
                success=True,
                metadata={'operation_time': operation_time, 'to_index': to_index}
            ))
            
            return True
            
        except Exception as e:
            self._update_statistics(StackOperation.MOVE_PROTOCOL, False)
            self.operation_failed.emit("move_protocol", str(from_index), str(e))
            return False

    def update_protocol_config(self, index: int, config: Dict[str, Any]) -> bool:
        operation_start = time.time()
        
        try:
            if not 0 <= index < len(self._current_stack):
                raise ValueError(f"Invalid protocol index: {index}")
            
            old_instance = self._current_stack[index]
            protocol_name = self._get_protocol_name(old_instance)
            
            self.operation_started.emit("update_config", protocol_name)
            old_stack = copy.deepcopy(self._current_stack)
            
            new_instance = self._create_protocol_instance(protocol_name, config)
            
            is_valid, error_msg = self._validate_protocol_instance(protocol_name, new_instance)
            if not is_valid and self._strict_validation:
                raise ValueError(f"Protocol validation failed: {error_msg}")
            elif not is_valid:
                self.dependency_warning.emit(protocol_name, error_msg)
            
            self._current_stack[index] = new_instance
            
            if self._auto_validate:
                stack_valid, stack_error = self._validate_current_stack()
                if not stack_valid and self._strict_validation:
                    self._current_stack = old_stack
                    raise ValueError(f"Stack validation failed: {stack_error}")
                elif not stack_valid:
                    self.validation_result.emit(False, stack_error)
                else:
                    self.validation_result.emit(True, "Stack is valid")
            
            self._add_to_history(old_stack)
            self._update_statistics(StackOperation.UPDATE_CONFIG, True)
            
            if self._auto_build_packets:
                self._build_packet_async()
            
            self.protocol_configured.emit(protocol_name, index, config)
            self.stack_changed.emit(copy.deepcopy(self._current_stack))
            self.operation_completed.emit("update_config", protocol_name, True)
            
            operation_time = time.time() - operation_start
            self._record_operation(StackOperationRecord(
                operation=StackOperation.UPDATE_CONFIG,
                timestamp=time.time(),
                protocol_name=protocol_name,
                protocol_index=index,
                old_config=old_stack,
                new_config=copy.deepcopy(self._current_stack),
                success=True,
                metadata={'operation_time': operation_time}
            ))
            
            return True
            
        except Exception as e:
            self._update_statistics(StackOperation.UPDATE_CONFIG, False)
            self.operation_failed.emit("update_config", str(index), str(e))
            return False

    def set_stack(self, stack_config: List[Dict[str, Any]]) -> bool:
        operation_start = time.time()
        
        try:
            self.operation_started.emit("set_stack", "complete")
            old_stack = copy.deepcopy(self._current_stack)
            
            new_stack = []
            for proto_config in stack_config:
                protocol_name = proto_config.get('name')
                config = proto_config.get('config', {})
                
                if not protocol_name:
                    raise ValueError("Protocol name missing in stack configuration")
                
                instance = self._create_protocol_instance(protocol_name, config)
                new_stack.append(instance)
            
            self._current_stack = new_stack
            
            if self._auto_validate and self._current_stack:
                stack_valid, stack_error = self._validate_current_stack()
                if not stack_valid and self._strict_validation:
                    self._current_stack = old_stack
                    raise ValueError(f"Stack validation failed: {stack_error}")
                elif not stack_valid:
                    self.validation_result.emit(False, stack_error)
                else:
                    self.validation_result.emit(True, "Stack is valid")
            
            self._add_to_history(old_stack)
            self._update_statistics(StackOperation.SET_STACK, True)
            
            if self._auto_build_packets and self._current_stack:
                self._build_packet_async()
            
            self.stack_changed.emit(copy.deepcopy(self._current_stack))
            self.operation_completed.emit("set_stack", "complete", True)
            
            operation_time = time.time() - operation_start
            self._record_operation(StackOperationRecord(
                operation=StackOperation.SET_STACK,
                timestamp=time.time(),
                old_config=old_stack,
                new_config=copy.deepcopy(self._current_stack),
                success=True,
                metadata={'operation_time': operation_time, 'stack_size': len(new_stack)}
            ))
            
            return True
            
        except Exception as e:
            self._update_statistics(StackOperation.SET_STACK, False)
            self.operation_failed.emit("set_stack", "complete", str(e))
            return False

    def clear_stack(self) -> bool:
        try:
            self.operation_started.emit("clear_stack", "all")
            self.logger.debug("Clearing protocol stack")
            
            old_stack = copy.deepcopy(self._current_stack)
            self._current_stack = []
            
            self.validation_result.emit(True, "Empty stack is valid")
            
            self._add_to_history(old_stack)
            self._update_statistics(StackOperation.CLEAR_STACK, True)
            
            self.stack_changed.emit(copy.deepcopy(self._current_stack))
            self.operation_completed.emit("clear_stack", "all", True)
            
            self._record_operation(StackOperationRecord(
                operation=StackOperation.CLEAR_STACK,
                timestamp=time.time(),
                old_config=old_stack,
                new_config=[],
                success=True,
                metadata={'protocols_cleared': len(old_stack)}
            ))
            
            self.logger.info("Protocol stack cleared successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing stack: {e}")
            self.operation_failed.emit("clear_stack", "all", str(e))
            return False

    def validate_protocol_config(self, protocol_name: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            temp_instance = self._create_protocol_instance(protocol_name, config)
            is_valid, error_msg = self._validate_protocol_instance(protocol_name, temp_instance)
            
            if self.validator and self._strict_validation:
                try:
                    validator_result = self.validator.validate_protocol_config(protocol_name, config)
                    if isinstance(validator_result, tuple):
                        val_valid, val_msg = validator_result
                        if not val_valid:
                            is_valid = False
                            error_msg = val_msg
                except Exception as e:
                    self.logger.debug(f"Validator error: {e}")
            
            if not is_valid:
                self.logger.warning(f"Invalid {protocol_name} configuration: {error_msg}")
                self.validation_result.emit(False, error_msg)
            else:
                self.validation_result.emit(True, f"{protocol_name} configuration is valid")
            
            return is_valid, error_msg
            
        except Exception as e:
            error_msg = f"Validation error for {protocol_name}: {e}"
            self.logger.error(error_msg)
            self.validation_error.emit("ERROR", "VALIDATION", error_msg)
            return False, error_msg

    def _validate_current_stack(self) -> Tuple[bool, str]:
        try:
            if not self._current_stack:
                return True, "Empty stack is valid"
            
            for i, protocol_instance in enumerate(self._current_stack):
                protocol_name = self._get_protocol_name(protocol_instance)
                is_valid, error_msg = self._validate_protocol_instance(protocol_name, protocol_instance)
                if not is_valid and self._strict_validation:
                    return False, f"Protocol {i} ({protocol_name}) validation failed: {error_msg}"
            
            if self.validator:
                try:
                    stack_configs = []
                    for instance in self._current_stack:
                        protocol_name = self._get_protocol_name(instance)
                        stack_configs.append({
                            'name': protocol_name,
                            'config': {}
                        })
                    
                    validator_result = self.validator.validate_protocol_stack(stack_configs)
                    if isinstance(validator_result, tuple):
                        val_valid, val_msg = validator_result
                        if not val_valid and self._strict_validation:
                            return False, val_msg
                        elif not val_valid:
                            self.logger.debug(f"Stack validation warning: {val_msg}")
                except Exception as e:
                    if self._strict_validation:
                        return False, f"Validator error: {e}"
                    self.logger.debug(f"Validator error ignored: {e}")
            
            return True, "Stack is valid"
            
        except Exception as e:
            error_msg = f"Stack validation error: {e}"
            self.logger.error(error_msg)
            self._statistics.validation_failures += 1
            if self._strict_validation:
                return False, error_msg
            return True, f"Stack validation warning: {error_msg}"

    def validate_current_stack(self) -> Tuple[bool, str]:
        return self._validate_current_stack()

    def get_validation_report(self) -> Dict[str, Any]:
        try:
            is_valid, message = self._validate_current_stack()
            
            protocol_details = []
            for i, instance in enumerate(self._current_stack):
                protocol_name = self._get_protocol_name(instance)
                inst_valid, inst_msg = self._validate_protocol_instance(protocol_name, instance)
                
                protocol_details.append({
                    'index': i,
                    'name': protocol_name,
                    'class': instance.__class__.__name__,
                    'valid': inst_valid,
                    'message': inst_msg,
                    'instance_id': id(instance)
                })
            
            return {
                'is_valid': is_valid,
                'message': message,
                'stack_size': len(self._current_stack),
                'validation_failures': self._statistics.validation_failures,
                'protocol_details': protocol_details,
                'timestamp': time.time()
            }
            
        except Exception as e:
            return {
                'is_valid': False,
                'message': f"Validation report error: {e}",
                'error': True,
                'timestamp': time.time()
            }

    def build_packet(self) -> Optional[Any]:
        try:
            if not self._current_stack:
                error_msg = "Cannot build packet - empty stack"
                self.packet_construction_failed.emit(error_msg)
                return None
            
            self.packet_construction_started.emit()
            self.logger.debug("Building packet from stack")
            
            if self._strict_validation:
                is_valid, error_msg = self._validate_current_stack()
                if not is_valid:
                    error_msg = f"Cannot build packet - validation failed: {error_msg}"
                    self.packet_construction_failed.emit(error_msg)
                    return None
            
            packet_data = self._build_packet_from_stack()
            
            if packet_data:
                self._statistics.packet_constructions += 1
                self.packet_construction_completed.emit(packet_data)
                self.logger.info("Packet constructed successfully")
                return packet_data
            else:
                error_msg = "Packet construction returned None"
                self.packet_construction_failed.emit(error_msg)
                self.logger.warning(error_msg)
                return None
            
        except Exception as e:
            error_msg = f"Packet construction failed: {e}"
            self.logger.error(error_msg)
            self.packet_construction_failed.emit(error_msg)
            return None

    def _build_packet_async(self) -> None:
        try:
            QTimer.singleShot(0, self.build_packet)
        except Exception as e:
            self.logger.debug(f"Async packet building error: {e}")

    def get_protocol_stack(self) -> List[Any]:
        return copy.deepcopy(self._current_stack)
    
    def get_protocol_at(self, index: int) -> Optional[Any]:
        if 0 <= index < len(self._current_stack):
            return copy.deepcopy(self._current_stack[index])
        return None
    
    def has_protocols(self) -> bool:
        return len(self._current_stack) > 0
    
    def get_stack_size(self) -> int:
        return len(self._current_stack)
    
    def get_protocol_names(self) -> List[str]:
        return [self._get_protocol_name(instance) for instance in self._current_stack]
    
    def get_available_protocols(self) -> List[str]:
        return list(self.PROTOCOL_FACTORIES.keys())
    
    def get_default_config(self, protocol_name: str) -> Dict[str, Any]:
        return self.DEFAULT_CONFIGS.get(protocol_name, {}).copy()
    
    def get_factory_info(self) -> Dict[str, Any]:
        factory_info = {}
        for protocol_name, factory in self._protocol_factories.items():
            factory_info[protocol_name] = {
                'class_name': factory.__name__ if hasattr(factory, '__name__') else str(factory),
                'has_create_packet': hasattr(factory, 'create_packet'),
                'module': factory.__module__ if hasattr(factory, '__module__') else 'unknown'
            }
        return factory_info

    def _add_to_history(self, stack: List[Any]) -> None:
        try:
            self._stack_history.append(copy.deepcopy(stack))
            if len(self._stack_history) > self._max_history:
                self._stack_history = self._stack_history[-self._max_history:]
        except Exception as e:
            self.logger.debug(f"Error adding to history: {e}")
    
    def can_undo(self) -> bool:
        return len(self._stack_history) > 0
    
    def undo_last_operation(self) -> bool:
        try:
            if not self.can_undo():
                self.logger.debug("No operations to undo")
                return False
            
            previous_stack = self._stack_history.pop()
            
            if self._auto_validate and self._strict_validation and previous_stack:
                temp_stack = self._current_stack
                self._current_stack = previous_stack
                
                is_valid, error_msg = self._validate_current_stack()
                if not is_valid:
                    self._current_stack = temp_stack
                    self._stack_history.append(previous_stack)
                    self.logger.warning(f"Cannot undo - previous state is invalid: {error_msg}")
                    return False
            else:
                self._current_stack = previous_stack
            
            self.stack_changed.emit(copy.deepcopy(self._current_stack))
            self.validation_result.emit(True, "Undo successful")
            
            self.logger.info("Last operation undone successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Undo operation failed: {e}")
            return False

    def _record_operation(self, operation: StackOperationRecord) -> None:
        try:
            self._operation_history.append(operation)
            if len(self._operation_history) > 100:
                self._operation_history = self._operation_history[-100:]
            
            if 'operation_time' in operation.metadata:
                self._update_performance_metrics(operation.metadata['operation_time'])
        except Exception as e:
            self.logger.debug(f"Error recording operation: {e}")
    
    def _update_performance_metrics(self, operation_time: float) -> None:
        try:
            self._performance_metrics['total_processing_time'] += operation_time
            
            total_ops = self._statistics.total_operations
            if total_ops > 0:
                self._performance_metrics['average_operation_time'] = (
                    self._performance_metrics['total_processing_time'] / total_ops
                )
            
            if operation_time > 0:
                self._performance_metrics['slowest_operation_time'] = max(
                    self._performance_metrics['slowest_operation_time'], operation_time
                )
                self._performance_metrics['fastest_operation_time'] = min(
                    self._performance_metrics['fastest_operation_time'], operation_time
                )
        except Exception as e:
            self.logger.debug(f"Error updating performance metrics: {e}")
    
    def _update_statistics(self, operation: StackOperation, success: bool) -> None:
        try:
            self._statistics.total_operations += 1
            self._statistics.last_operation_time = time.time()
            
            if success:
                self._statistics.successful_operations += 1
                
                if operation == StackOperation.ADD_PROTOCOL:
                    self._statistics.protocols_added += 1
                elif operation == StackOperation.REMOVE_PROTOCOL:
                    self._statistics.protocols_removed += 1
                elif operation == StackOperation.MOVE_PROTOCOL:
                    self._statistics.protocols_moved += 1
                elif operation == StackOperation.UPDATE_CONFIG:
                    self._statistics.configurations_updated += 1
            else:
                self._statistics.failed_operations += 1
            
            self.statistics_updated.emit(copy.deepcopy(self._statistics))
        except Exception as e:
            self.logger.debug(f"Error updating statistics: {e}")
    
    def get_statistics(self) -> StackStatistics:
        return copy.deepcopy(self._statistics)
    
    def get_performance_metrics(self) -> Dict[str, float]:
        return self._performance_metrics.copy()
    
    def reset_statistics(self) -> None:
        self._statistics = StackStatistics()
        self._performance_metrics = {
            'average_operation_time': 0.0,
            'slowest_operation_time': 0.0,
            'fastest_operation_time': float('inf'),
            'total_processing_time': 0.0
        }
        self._operation_history.clear()
        self.logger.info("Statistics and performance metrics reset")

    def get_status(self) -> Dict[str, Any]:
        try:
            uptime = time.time() - self._statistics.session_start_time
            
            instance_info = []
            for i, instance in enumerate(self._current_stack):
                instance_info.append({
                    'index': i,
                    'class': instance.__class__.__name__,
                    'name': self._get_protocol_name(instance),
                    'id': id(instance),
                    'valid': hasattr(instance, 'validate')
                })
            
            return {
                'type': 'ProtocolStackController',
                'initialized': True,
                'current_stack_size': len(self._current_stack),
                'max_stack_size': self._max_stack_size,
                'uptime_seconds': uptime,
                'available_protocols': list(self.PROTOCOL_FACTORIES.keys()),
                'factory_info': self.get_factory_info(),
                'instance_info': instance_info,
                'validator': {
                    'type': type(self.validator).__name__ if self.validator else 'None',
                    'strict_validation': self._strict_validation,
                    'available': self.validator is not None
                },
                'connections': {
                    'packet_manager': self._packet_manager is not None,
                    'builders': self._builders is not None,
                    'ui_builders': self._ui_builders is not None,
                    'views': self._views is not None
                },
                'configuration': {
                    'strict_validation': self._strict_validation,
                    'auto_validate': self._auto_validate,
                    'auto_build_packets': self._auto_build_packets,
                    'error_recovery_enabled': self._error_recovery_enabled
                },
                'statistics': self._statistics.__dict__,
                'performance': self._performance_metrics,
                'current_protocols': self.get_protocol_names(),
                'validation_report': self.get_validation_report()
            }
            
        except Exception as e:
            return {
                'type': 'ProtocolStackController',
                'initialized': False,
                'error': str(e)
            }
    
    def cleanup(self) -> None:
        try:
            self.logger.info("Cleaning up ProtocolStackController")
            
            self._current_stack.clear()
            self._packet_manager = None
            self._builders = None
            self._ui_builders = None
            self._views = None
            self._stack_history.clear()
            self._operation_history.clear()
            
            self.logger.info("ProtocolStackController cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    # === ECOSYSTEM INTEGRATION METHODS ===
    
    def set_facade(self, facade: Any) -> bool:
        try:
            if facade:
                self.facade = weakref.ref(facade) if not isinstance(facade, weakref.ref) else facade
            else:
                self.facade = None
            
            self.logger.debug("Facade reference set successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set facade reference: {e}")
            return False
    
    def set_packet_manager(self, packet_manager: Any) -> bool:
        try:
            self._packet_manager = packet_manager
            self.logger.info("Successfully connected to PacketManager")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to PacketManager: {e}")
            self._packet_manager = None
            return False
    
    def set_builders(self, builders: Any) -> bool:
        try:
            self._builders = builders
            self.logger.info("Successfully connected to BuildersContainer")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to BuildersContainer: {e}")
            self._builders = None
            return False
    
    def set_ui_builders(self, ui_builders: Any) -> bool:
        try:
            self._ui_builders = ui_builders
            self.logger.info("Successfully connected to UIBuildersContainer")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to UIBuildersContainer: {e}")
            self._ui_builders = None
            return False
    
    def connect_to_views(self, views: Any) -> bool:
        try:
            self._views = views
            
            if hasattr(views, 'update_protocol_stack'):
                try:
                    self.stack_changed.disconnect()
                except:
                    pass
                self.stack_changed.connect(views.update_protocol_stack)
                self.logger.debug("Connected stack_changed signal to views")
            
            if hasattr(views, 'on_validation_result'):
                try:
                    self.validation_result.disconnect()
                except:
                    pass
                self.validation_result.connect(views.on_validation_result)
            
            if hasattr(views, 'on_validation_error'):
                try:
                    self.validation_error.disconnect()
                except:
                    pass
                self.validation_error.connect(views.on_validation_error)
            
            if hasattr(views, 'on_dependency_warning'):
                try:
                    self.dependency_warning.disconnect()
                except:
                    pass
                self.dependency_warning.connect(views.on_dependency_warning)
            
            self.logger.info("Successfully connected to views")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to views: {e}")
            self._views = None
            return False
    
    def set_views(self, views: Any) -> bool:
        return self.connect_to_views(views)
    
    def connect_packet_manager(self, packet_manager: Any) -> bool:
        return self.set_packet_manager(packet_manager)
    
    def connect_builders(self, builders: Any) -> bool:
        return self.set_builders(builders)
    
    def connect_ui_builders(self, ui_builders: Any) -> bool:
        return self.set_ui_builders(ui_builders)
    
    # === CONFIGURATION METHODS ===
    
    def configure(self, config: Dict[str, Any]) -> bool:
        try:
            self._strict_validation = config.get('strict_validation', self._strict_validation)
            self._auto_validate = config.get('auto_validate', self._auto_validate)
            self._auto_build_packets = config.get('auto_build_packets', self._auto_build_packets)
            self._max_stack_size = config.get('max_stack_size', self._max_stack_size)
            self._max_history = config.get('max_history', self._max_history)
            
            if self.validator:
                self.validator.set_strict_validation(self._strict_validation)
            
            if 'validator_config' in config:
                validator_config = config['validator_config']
                if self.validator and hasattr(self.validator, 'configure'):
                    self.validator.configure(validator_config)
            
            self.logger.info("Controller configured successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to configure controller: {e}")
            return False
    
    def set_strict_validation(self, strict: bool) -> None:
        self._strict_validation = strict
        if self.validator:
            self.validator.set_strict_validation(strict)
        self.logger.info(f"Strict validation {'enabled' if strict else 'disabled'}")
    
    def set_auto_validate(self, auto: bool) -> None:
        self._auto_validate = auto
        self.logger.info(f"Auto-validation {'enabled' if auto else 'disabled'}")
    
    def set_auto_build_packets(self, auto: bool) -> None:
        self._auto_build_packets = auto
        self.logger.info(f"Auto packet building {'enabled' if auto else 'disabled'}")
    
    def start_monitoring(self):
        self.logger.info("Protocol stack controller mon