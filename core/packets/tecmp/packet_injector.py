#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
packet_injector.py - TECMP Feature Injection System
===================================================

Dynamic injection of advanced TECMP functionalities into packet instances.
Provides seamless integration of coherence validation and professional features
without modifying the base packet classes.

Features:
- Single-instance injection with duplicate prevention
- Method binding with proper context
- Weak reference tracking for memory efficiency
- Clean removal of injected features
- Control Message ID validation

This module acts as a bridge between the core TECMP implementation
and the advanced features, maintaining separation of concerns.
"""

import logging
import weakref
import struct
from typing import Dict, List, Any, Optional, Callable, Set

# Direct imports - no dynamic loading
from .coherence_engine import TECMPCoherenceEngine
from .tecmp_engine import TECMPEngine, create_professional_engine
from .constants import (
    MessageType, 
    ControlMessageID, 
    validate_control_message_id,
    SPECIAL_INTERFACE_IDS
)

# ============================================================================
# METHOD DEFINITIONS
# ============================================================================

class CoherenceMethods:
    """Coherence validation methods for injection"""
    
    @staticmethod
    def validate_coherence(self, level: str = "critical") -> Any:
        """
        Validate TECMP packet coherence
        
        Args:
            level: Validation level ('critical', 'important', 'recommendation')
            
        Returns:
            CoherenceReport with validation results
        """
        # Get or create coherence engine
        if not hasattr(self, '_coherence_engine'):
            self._coherence_engine = TECMPCoherenceEngine()
            
        return self._coherence_engine.validate_complete_coherence(self)
    
    @staticmethod
    def auto_fix_violations(self, apply: bool = True) -> Any:
        """
        Automatically fix coherence violations
        
        Args:
            apply: Whether to apply fixes immediately
            
        Returns:
            CoherenceReport with fixes applied
        """
        report = self.validate_coherence()
        
        if apply and report.violations:
            engine = self._coherence_engine
            fixable_violations = [v for v in report.violations if v.auto_fixable]
            
            if fixable_violations:
                engine.auto_fix_critical_violations(self, fixable_violations)
                # Re-validate after fixes
                report = self.validate_coherence()
                
        return report
    
    @staticmethod
    def get_coherence_report(self, detailed: bool = True) -> Dict[str, Any]:
        """
        Get human-readable coherence report
        
        Args:
            detailed: Include detailed violation information
            
        Returns:
            Dictionary with coherence status
        """
        report = self.validate_coherence()
        
        result = {
            'is_coherent': report.is_coherent,
            'violations_count': len(report.violations),
            'validation_time_ms': report.validation_time_ms
        }
        
        if detailed:
            result.update({
                'critical_violations': [
                    {
                        'field': v.field,
                        'message': v.message,
                        'auto_fixable': v.auto_fixable
                    }
                    for v in report.violations if v.severity == 'CRITICAL'
                ],
                'important_violations': [
                    {
                        'field': v.field,
                        'message': v.message,
                        'auto_fixable': v.auto_fixable
                    }
                    for v in report.violations if v.severity == 'IMPORTANT'
                ],
                'recommendations': [
                    {
                        'field': v.field,
                        'message': v.message
                    }
                    for v in report.violations if v.severity == 'RECOMMENDATION'
                ],
                'auto_fixes_available': len([v for v in report.violations if v.auto_fixable])
            })
            
        return result
    
    @staticmethod
    def is_tecmp_compliant(self) -> bool:
        """
        Check if packet is fully TECMP v1.7 compliant
        
        Returns:
            True if no critical violations exist
        """
        report = self.validate_coherence()
        critical_count = len([v for v in report.violations if v.severity == 'CRITICAL'])
        return report.is_coherent and critical_count == 0
    
    @staticmethod
    def ensure_coherence(self) -> 'TECMPPacket':
        """
        Ensure packet coherence by fixing all violations
        
        Returns:
            Self for method chaining
        """
        self.auto_fix_violations(apply=True)
        return self
    
    @staticmethod
    def validate_control_message_id(self) -> Optional[Dict[str, Any]]:
        """
        Validate Control Message ID if this is a control message
        
        Returns:
            Validation result dictionary or None if not a control message
        """
        # Only validate control messages
        if self.message_type != MessageType.CONTROL:
            return None
        
        # Control message must have at least 4 bytes payload
        if len(self.payload) < 4:
            return {
                'valid': False,
                'error': 'Control message payload too short (< 4 bytes)',
                'control_id': None
            }
        
        try:
            # Extract Control Message ID from payload
            device_id, control_msg_id = struct.unpack("!HH", self.payload[:4])
            
            # Validate using centralized function
            is_valid = validate_control_message_id(control_msg_id)
            
            # Determine category using official names from TECMP v1.7 Table 26
            if control_msg_id == ControlMessageID.LOGGER_READY:
                category = 'system'
                name = 'Logger Ready'
            elif control_msg_id == ControlMessageID.CAN_REPLAY_FILL_LEVEL:
                category = 'system'
                name = 'CAN Replay fill level'
            elif control_msg_id == ControlMessageID.FLEXRAY_POC_STATE:
                category = 'system'
                name = 'FlexRay POC State'
            elif 0x00 <= control_msg_id <= 0xDF:
                category = 'user_configurable'
                # Check for common user-configurable messages
                if control_msg_id in range(0x00, 0xE0):
                    name = f'User configurable (0x{control_msg_id:02X})'
                else:
                    name = f'User Defined (0x{control_msg_id:02X})'
            elif 0xE2 <= control_msg_id <= 0xFF:
                category = 'reserved'
                name = f'Reserved for future use (0x{control_msg_id:02X})'
            else:
                category = 'unknown'
                name = f'Unknown (0x{control_msg_id:02X})'
            
            return {
                'valid': is_valid,
                'control_id': control_msg_id,
                'device_id': device_id,
                'category': category,
                'name': name,
                'warning': 'Control ID in reserved range' if category == 'reserved' else None
            }
            
        except struct.error as e:
            return {
                'valid': False,
                'error': f'Failed to parse control message: {e}',
                'control_id': None
            }

class ProfessionalMethods:
    """Professional TECMP methods for injection"""
    
    @staticmethod
    def enable_professional_mode(self, config: Optional[Dict] = None) -> bool:
        """
        Enable professional TECMP features
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if successfully enabled
        """
        # Get or create TECMP engine
        if not hasattr(self, '_tecmp_engine'):
            device_id = getattr(self, 'device_id', 0x40)
            self._tecmp_engine = create_professional_engine(device_id)
            
        # Apply configuration
        cfg = {
            'enable_time_sync': True,
            'enable_hw_monitor': True,
            'time_sync_master': False
        }
        if config:
            cfg.update(config)
            
        # Update timestamp with synchronized time
        self.timestamp = self._tecmp_engine.get_synchronized_timestamp()
        
        return True
    
    @staticmethod
    def get_synchronized_timestamp(self) -> int:
        """
        Get IEEE 802.1AS synchronized timestamp
        
        Returns:
            Synchronized timestamp in nanoseconds
        """
        if hasattr(self, '_tecmp_engine'):
            return self._tecmp_engine.get_synchronized_timestamp()
        return self.timestamp
    
    @staticmethod
    def apply_sync_flags(self) -> None:
        """Apply synchronization flags to timestamp"""
        if hasattr(self, '_tecmp_engine'):
            sync_flags = self._tecmp_engine.get_sync_flags()
            self.set_timestamp_with_flags(self.timestamp | sync_flags)
    
    @staticmethod
    def configure_hardware_simulation(self, config: Dict[str, Any]) -> bool:
        """
        Configure hardware simulation parameters
        
        Args:
            config: Hardware configuration
            
        Returns:
            True if successfully configured
        """
        if not hasattr(self, '_tecmp_engine'):
            return False
            
        engine = self._tecmp_engine
        
        if 'ambient_temperature' in config:
            engine.hardware_monitor.set_environmental_conditions(
                config['ambient_temperature'],
                engine.hardware_monitor.supply_voltage_nominal
            )
            
        if 'supply_voltage' in config:
            engine.hardware_monitor.set_environmental_conditions(
                engine.hardware_monitor.ambient_temperature_c,
                config['supply_voltage']
            )
            
        return True
    
    @staticmethod
    def generate_realistic_status(self) -> bytes:
        """
        Generate realistic Status Device payload
        
        Returns:
            Status Device payload bytes
        """
        if hasattr(self, '_tecmp_engine'):
            payload = self._tecmp_engine.hardware_monitor.generate_status_device_payload()
            
            # Update packet if Status Device message
            if hasattr(self, 'message_type') and self.message_type == MessageType.STATUS_DEVICE:
                self.payload = payload
                self.length = len(payload)
                
            return payload
            
        return b'\x0C\x01\x04\x00\x20\x00' + b'\x00' * 38  # Default
    
    @staticmethod
    def configure_protocol_interface(self, interface_id: int, 
                                   protocol: str, 
                                   config: Dict[str, Any]) -> bool:
        """
        Configure protocol interface (CAN/FlexRay/LIN)
        
        Args:
            interface_id: Interface identifier
            protocol: Protocol type ('CAN', 'FLEXRAY', 'LIN')
            config: Protocol-specific configuration
            
        Returns:
            True if successfully configured
        """
        if not hasattr(self, '_tecmp_engine'):
            return False
            
        try:
            self._tecmp_engine.configure_interface(interface_id, protocol, config)
            
            # Update packet interface if appropriate
            if hasattr(self, 'interface_id'):
                self.interface_id = interface_id
                
            return True
        except Exception as e:
            logging.error(f"Protocol configuration error: {e}")
            return False
    
    @staticmethod
    def schedule_replay(self, events: List[Any], mode: str = "precise") -> int:
        """
        Schedule replay events
        
        Args:
            events: List of replay events
            mode: Timing mode ('precise', 'burst')
            
        Returns:
            Number of scheduled events
        """
        if hasattr(self, '_tecmp_engine'):
            return self._tecmp_engine.schedule_replay_sequence(events, mode)
        return 0
    
    @staticmethod
    def apply_automotive_scenario(self, scenario: str, params: Optional[Dict] = None) -> bool:
        """
        Apply pre-defined automotive scenario
        
        Args:
            scenario: Scenario name
            params: Optional parameters
            
        Returns:
            True if successfully applied
        """
        if hasattr(self, '_tecmp_engine'):
            return self._tecmp_engine.schedule_scenario(scenario, 100, params)
        return False
    
    @staticmethod
    def get_engine_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive engine statistics
        
        Returns:
            Dictionary with engine statistics
        """
        if hasattr(self, '_tecmp_engine'):
            return self._tecmp_engine.get_engine_status()
        return {}
    
    @staticmethod
    def inject_control_message(self, control_id: int, 
                             sender_device_id: Optional[int] = None,
                             payload_data: bytes = b"") -> bool:
        """
        Inject a control message with validation
        
        Args:
            control_id: Control Message ID
            sender_device_id: Sender device ID (uses packet's if None)
            payload_data: Optional additional payload
            
        Returns:
            True if injection successful
        """
        # Validate control ID
        if not validate_control_message_id(control_id):
            logging.error(f"Invalid Control Message ID: 0x{control_id:04X}")
            return False
        
        # Update to control message
        self.message_type = MessageType.CONTROL
        
        # Build control message payload
        if sender_device_id is None:
            sender_device_id = self.device_id
            
        control_payload = struct.pack("!HH", sender_device_id, control_id)
        control_payload += payload_data
        
        # Update packet
        self.payload = control_payload
        self.length = len(control_payload)
        
        # Set appropriate interface ID for control messages (Table 28)
        self.interface_id = SPECIAL_INTERFACE_IDS['CONTROL']
        
        logging.info(f"Injected Control Message ID 0x{control_id:04X}")
        return True

# ============================================================================
# FEATURE INJECTOR
# ============================================================================

class TECMPFeatureInjector:
    """
    Feature injection manager for TECMP packets
    
    Manages injection of advanced features into packet instances
    with duplicate prevention and proper cleanup.
    """
    
    # Method registries
    COHERENCE_METHODS = {
        'validate_coherence': CoherenceMethods.validate_coherence,
        'auto_fix_violations': CoherenceMethods.auto_fix_violations,
        'get_coherence_report': CoherenceMethods.get_coherence_report,
        'is_tecmp_compliant': CoherenceMethods.is_tecmp_compliant,
        'ensure_coherence': CoherenceMethods.ensure_coherence,
        'validate_control_message_id': CoherenceMethods.validate_control_message_id
    }
    
    PROFESSIONAL_METHODS = {
        'enable_professional_mode': ProfessionalMethods.enable_professional_mode,
        'get_synchronized_timestamp': ProfessionalMethods.get_synchronized_timestamp,
        'apply_sync_flags': ProfessionalMethods.apply_sync_flags,
        'configure_hardware_simulation': ProfessionalMethods.configure_hardware_simulation,
        'generate_realistic_status': ProfessionalMethods.generate_realistic_status,
        'configure_protocol_interface': ProfessionalMethods.configure_protocol_interface,
        'schedule_replay': ProfessionalMethods.schedule_replay,
        'apply_automotive_scenario': ProfessionalMethods.apply_automotive_scenario,
        'get_engine_statistics': ProfessionalMethods.get_engine_statistics,
        'inject_control_message': ProfessionalMethods.inject_control_message
    }
    
    def __init__(self):
        # Track injected instances with weak references
        self._injected_instances: weakref.WeakSet = weakref.WeakSet()
        self._instance_features: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def inject_coherence(self, instance: Any) -> bool:
        """
        Inject coherence validation features
        
        Args:
            instance: Packet instance to inject into
            
        Returns:
            True if injection successful
        """
        return self._inject_feature_set(instance, 'coherence', self.COHERENCE_METHODS)
    
    def inject_professional(self, instance: Any) -> bool:
        """
        Inject professional TECMP features
        
        Args:
            instance: Packet instance to inject into
            
        Returns:
            True if injection successful
        """
        return self._inject_feature_set(instance, 'professional', self.PROFESSIONAL_METHODS)
    
    def inject_all(self, instance: Any) -> bool:
        """
        Inject all available features
        
        Args:
            instance: Packet instance to inject into
            
        Returns:
            True if all injections successful
        """
        coherence_ok = self.inject_coherence(instance)
        professional_ok = self.inject_professional(instance)
        return coherence_ok and professional_ok
    
    def _inject_feature_set(self, instance: Any, 
                          feature_name: str, 
                          methods: Dict[str, Callable]) -> bool:
        """
        Inject a set of methods into an instance
        
        Args:
            instance: Target instance
            feature_name: Feature set name
            methods: Dictionary of methods to inject
            
        Returns:
            True if injection successful
        """
        # Check for duplicate injection
        if hasattr(instance, '_already_injected'):
            existing_features = getattr(instance, '_injected_features', set())
            if feature_name in existing_features:
                self.logger.debug(f"Feature '{feature_name}' already injected")
                return True
        
        try:
            # Initialize tracking if needed
            if not hasattr(instance, '_already_injected'):
                instance._already_injected = True
                instance._injected_features = set()
                
            # Track instance
            if instance not in self._instance_features:
                self._instance_features[instance] = set()
                
            # Inject methods
            for method_name, method_func in methods.items():
                # Bind method to instance
                bound_method = method_func.__get__(instance, instance.__class__)
                setattr(instance, method_name, bound_method)
                
            # Record injection
            instance._injected_features.add(feature_name)
            self._instance_features[instance].add(feature_name)
            self._injected_instances.add(instance)
            
            self.logger.debug(f"Injected '{feature_name}' into {instance.__class__.__name__}")
            return True
            
        except Exception as e:
            self.logger.error(f"Injection failed for '{feature_name}': {e}")
            return False
    
    def remove_features(self, instance: Any) -> bool:
        """
        Remove all injected features from instance
        
        Args:
            instance: Instance to clean
            
        Returns:
            True if removal successful
        """
        try:
            # Remove all injected methods
            all_methods = list(self.COHERENCE_METHODS.keys()) + list(self.PROFESSIONAL_METHODS.keys())
            for method_name in all_methods:
                if hasattr(instance, method_name):
                    delattr(instance, method_name)
                    
            # Clean up engines
            if hasattr(instance, '_coherence_engine'):
                delattr(instance, '_coherence_engine')
                
            if hasattr(instance, '_tecmp_engine'):
                engine = getattr(instance, '_tecmp_engine', None)
                if engine:
                    engine.stop()
                delattr(instance, '_tecmp_engine')
                
            # Remove tracking
            if hasattr(instance, '_already_injected'):
                delattr(instance, '_already_injected')
            if hasattr(instance, '_injected_features'):
                delattr(instance, '_injected_features')
                
            # Clean up weak references
            self._injected_instances.discard(instance)
            self._instance_features.pop(instance, None)
            
            self.logger.debug(f"Removed features from {instance.__class__.__name__}")
            return True
            
        except Exception as e:
            self.logger.error(f"Feature removal failed: {e}")
            return False
    
    def has_feature(self, instance: Any, feature: str) -> bool:
        """
        Check if instance has a specific feature
        
        Args:
            instance: Instance to check
            feature: Feature name
            
        Returns:
            True if feature is present
        """
        return feature in self._instance_features.get(instance, set())
    
    def get_injected_features(self, instance: Any) -> Set[str]:
        """
        Get all injected features for an instance
        
        Args:
            instance: Instance to check
            
        Returns:
            Set of feature names
        """
        return self._instance_features.get(instance, set()).copy()

# ============================================================================
# GLOBAL INJECTOR INSTANCE
# ============================================================================

_global_injector = TECMPFeatureInjector()

# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================

def inject_coherence(packet: Any) -> bool:
    """Inject coherence validation features into packet"""
    return _global_injector.inject_coherence(packet)

def inject_professional(packet: Any) -> bool:
    """Inject professional TECMP features into packet"""
    return _global_injector.inject_professional(packet)

def inject_all_features(packet: Any) -> bool:
    """Inject all available features into packet"""
    return _global_injector.inject_all(packet)

def remove_injected_features(packet: Any) -> bool:
    """Remove all injected features from packet"""
    return _global_injector.remove_features(packet)

def has_coherence_features(packet: Any) -> bool:
    """Check if packet has coherence features"""
    return _global_injector.has_feature(packet, 'coherence')

def has_professional_features(packet: Any) -> bool:
    """Check if packet has professional features"""
    return _global_injector.has_feature(packet, 'professional')

def get_injected_features(packet: Any) -> Set[str]:
    """Get all injected features for packet"""
    return _global_injector.get_injected_features(packet)

# ============================================================================
# CONVENIENCE WRAPPERS
# ============================================================================

def validate_and_fix(packet: Any) -> Any:
    """
    Validate packet and automatically fix violations
    
    Args:
        packet: TECMP packet to validate and fix
        
    Returns:
        Fixed packet
    """
    if not has_coherence_features(packet):
        inject_coherence(packet)
        
    packet.auto_fix_violations(apply=True)
    return packet

def ensure_compliance(packet: Any) -> Any:
    """
    Ensure packet is TECMP v1.7 compliant
    
    Args:
        packet: TECMP packet to check
        
    Returns:
        Compliant packet
    """
    if not has_coherence_features(packet):
        inject_coherence(packet)
        
    if not packet.is_tecmp_compliant():
        packet.auto_fix_violations(apply=True)
        
    return packet

def create_professional_packet(*args, **kwargs) -> Any:
    """
    Create packet with professional features enabled
    
    Returns:
        New packet with professional features
    """
    # Import packet creation function
    from .tecmp_packet import create_logging_packet
    
    # Create packet
    packet = create_logging_packet(*args, **kwargs)
    
    # Inject features
    inject_all_features(packet)
    
    # Enable professional mode
    packet.enable_professional_mode()
    
    return packet

def validate_injected_control_message(packet: Any) -> Dict[str, Any]:
    """
    Validate control message ID for an injected packet
    
    Args:
        packet: TECMP packet to validate
        
    Returns:
        Validation result dictionary
    """
    if not has_coherence_features(packet):
        inject_coherence(packet)
    
    result = packet.validate_control_message_id()
    if result is None:
        return {
            'valid': True,
            'info': 'Not a control message',
            'message_type': packet.message_type
        }
    
    return result

# ============================================================================
# CLASS DECORATORS
# ============================================================================

def with_coherence(cls):
    """
    Class decorator to automatically inject coherence features
    
    Usage:
        @with_coherence
        class MyPacket(TECMPPacket):
            pass
    """
    original_init = cls.__init__
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        inject_coherence(self)
        
    cls.__init__ = new_init
    cls._coherence_decorated = True
    return cls

def with_professional(cls):
    """
    Class decorator to automatically inject professional features
    
    Usage:
        @with_professional
        class MyPacket(TECMPPacket):
            pass
    """
    original_init = cls.__init__
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        inject_professional(self)
        
    cls.__init__ = new_init
    cls._professional_decorated = True
    return cls

def with_full_features(cls):
    """
    Class decorator to automatically inject all features
    
    Usage:
        @with_full_features
        class MyPacket(TECMPPacket):
            pass
    """
    original_init = cls.__init__
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        inject_all_features(self)
        
    cls.__init__ = new_init
    cls._full_features_decorated = True
    return cls

# Export public API
__all__ = [
    # Core injection functions
    'inject_coherence',
    'inject_professional',
    'inject_all_features',
    'remove_injected_features',
    
    # Feature checks
    'has_coherence_features',
    'has_professional_features',
    'get_injected_features',
    
    # Convenience wrappers
    'validate_and_fix',
    'ensure_compliance',
    'create_professional_packet',
    'validate_injected_control_message',
    
    # Decorators
    'with_coherence',
    'with_professional',
    'with_full_features',
    
    # Main class (for advanced usage)
    'TECMPFeatureInjector'
]