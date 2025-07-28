#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TECMP Package
=============
Complete TECMP protocol implementation v1.7
"""

import logging

logger = logging.getLogger(__name__)

# Import core TECMP components
try:
    from .constants import (
        TECMP_VERSION, TECMP_ETHERTYPE, TECMP_HEADER_SIZE,
        TECMP_DEVICE_FLAGS_SIZE, TECMP_PAYLOAD_HEADER_SIZE,
        MAX_UNSEGMENTED_SIZE, MAX_ETHERNET_PAYLOAD,
        MessageType, DataType, DeviceFlags,
        CANDataFlags, CANFDDataFlags, LINDataFlags,
        FlexRayDataFlags, UARTDataFlags, AnalogDataFlags, EthernetDataFlags,
        ControlMessageID, DeviceType,
        DEVICE_ID_RANGES, SPECIAL_INTERFACE_IDS,
        TIMESTAMP_VALUE_MASK, TIMESTAMP_RECALC_BIT, TIMESTAMP_SYNC_BIT,
        get_device_type_name, get_data_type_name, validate_device_id,
        validate_control_message_id
    )
    logger.debug("Constants imported successfully")
except ImportError as e:
    logger.warning(f"Could not import constants: {e}")

try:
    from .tecmp_packet import (
        TECMPPacket,
        create_logging_packet,
        create_replay_packet,
        create_control_message,
        reconstruct_from_segments,
        TECMPError,
        TECMPParsingError,
        TECMPSerializationError,
        TECMPValidationError,
        SegmentInfo,
        MultiFrameInfo
    )
    logger.debug("TECMPPacket components imported successfully")
except ImportError as e:
    logger.warning(f"Could not import TECMPPacket: {e}")

try:
    from .tecmp_data import (
        TECMPDataBuilder,
        TECMPData,
        build_can_payload,
        build_canfd_payload,
        build_ethernet_payload,
        build_lin_payload,
        build_flexray_payload,
        build_uart_payload,
        build_analog_payload,
        # parse_can_payload,
        # parse_canfd_payload,
        # parse_ethernet_payload,
        # parse_lin_payload,
        # parse_flexray_payload,
        # parse_uart_payload,
        # parse_analog_payload,
        TECMPDataError,
        TECMPDataValidationError
    )
    logger.debug("TECMPData components imported successfully")
except ImportError as e:
    logger.warning(f"Could not import TECMPData: {e}")

# Import advanced components (optional)
try:
    from .coherence_engine import (
        TECMPCoherenceEngine,
        CoherenceReport,
        ViolationSeverity,
        ViolationType,
        CoherenceViolation,
        create_coherence_engine
    )
    logger.debug("Coherence engine imported successfully")
except ImportError as e:
    logger.debug(f"Coherence engine not available: {e}")

try:
    from .packet_injector import (
        inject_coherence,
        inject_professional,
        inject_all_features,
        remove_injected_features,
        has_coherence_features,
        has_professional_features,
        get_injected_features,
        validate_and_fix,
        ensure_compliance
    )
    logger.debug("Packet injector imported successfully")
except ImportError as e:
    logger.debug(f"Packet injector not available: {e}")

try:
    from .tecmp_engine import (
        TECMPEngine,
        create_professional_engine,
        TimeSyncManager,
        HardwareMonitor,
        ProtocolEngine,
        ReplayScheduler,
        TemplateManager,
        MessageBroker,
        PerformanceMonitor,
        DiagnosticsManager
    )
    logger.debug("TECMP engine imported successfully")
except ImportError as e:
    logger.debug(f"TECMP engine not available: {e}")

try:
    from .validator import (
        TECMPValidator,
        ValidationResult,
        ValidationSeverity,
        ValidationRule,
        validate_packet,
        validate_timestamp,
        validate_device_flags,
        validate_payload
    )
    logger.debug("Validator imported successfully")
except ImportError as e:
    logger.debug(f"Validator not available: {e}")

# Export all available components
__all__ = [
    # Version
    '__version__',
    
    # Constants
    'TECMP_VERSION', 'TECMP_ETHERTYPE', 'TECMP_HEADER_SIZE',
    'TECMP_DEVICE_FLAGS_SIZE', 'TECMP_PAYLOAD_HEADER_SIZE',
    'MAX_UNSEGMENTED_SIZE', 'MAX_ETHERNET_PAYLOAD',
    
    # Enums
    'MessageType', 'DataType', 'DeviceFlags', 'DeviceType',
    'CANDataFlags', 'CANFDDataFlags', 'LINDataFlags',
    'FlexRayDataFlags', 'UARTDataFlags', 'AnalogDataFlags', 
    'EthernetDataFlags', 'ControlMessageID',
    
    # Constants and helpers
    'DEVICE_ID_RANGES', 'SPECIAL_INTERFACE_IDS',
    'TIMESTAMP_VALUE_MASK', 'TIMESTAMP_RECALC_BIT', 'TIMESTAMP_SYNC_BIT',
    'get_device_type_name', 'get_data_type_name', 
    'validate_device_id', 'validate_control_message_id',
    
    # Core packet classes
    'TECMPPacket',
    'create_logging_packet',
    'create_replay_packet', 
    'create_control_message',
    'reconstruct_from_segments',
    'SegmentInfo',
    'MultiFrameInfo',
    
    # Exceptions
    'TECMPError',
    'TECMPParsingError',
    'TECMPSerializationError',
    'TECMPValidationError',
    
    # Data builders
    'TECMPDataBuilder',
    'TECMPData',
    'build_can_payload',
    'build_canfd_payload',
    'build_ethernet_payload',
    'build_lin_payload',
    'build_flexray_payload',
    'build_uart_payload',
    'build_analog_payload',
    'parse_can_payload',
    'parse_canfd_payload',
    'parse_ethernet_payload',
    'parse_lin_payload',
    'parse_flexray_payload',
    'parse_uart_payload',
    'parse_analog_payload',
    'TECMPDataError',
    'TECMPDataValidationError',
    
    # Advanced components
    'TECMPCoherenceEngine',
    'CoherenceReport',
    'ViolationSeverity',
    'ViolationType',
    'CoherenceViolation',
    'create_coherence_engine',
    
    # Packet injector
    'inject_coherence',
    'inject_professional',
    'inject_all_features',
    'remove_injected_features',
    'has_coherence_features',
    'has_professional_features',
    'get_injected_features',
    'validate_and_fix',
    'ensure_compliance',
    
    # Engine components
    'TECMPEngine',
    'create_professional_engine',
    'TimeSyncManager',
    'HardwareMonitor',
    'ProtocolEngine',
    'ReplayScheduler',
    'TemplateManager',
    'MessageBroker',
    'PerformanceMonitor',
    'DiagnosticsManager',
    
    # Validator
    'TECMPValidator',
    'ValidationResult',
    'ValidationSeverity',
    'ValidationRule',
    'validate_packet',
    'validate_timestamp',
    'validate_device_flags',
    'validate_payload'
]

# Remove items that failed to import
__all__ = [item for item in __all__ if item in globals()]


# Log summary
logger.info(f"TECMP package loaded. Available components: {len(__all__)}")