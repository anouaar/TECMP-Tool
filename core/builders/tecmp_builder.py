#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Specialized builder for the proprietary TECMP protocol.
Professional-grade implementation with complete feature integration.
CORRECTED VERSION - All identified issues fixed and aligned with constants.py
"""
from __future__ import annotations
from typing import Any, Dict, Optional, List, Union, Iterator, Tuple, cast
import time
import logging
import copy
import re
import threading
import weakref
from dataclasses import dataclass, field

from core.packets.tecmp.tecmp_packet import TECMPPacket
from core.packets.tecmp.tecmp_data import TECMPDataBuilder
from core.packets.tecmp.validator import TECMPValidator
from core.packets.tecmp.constants import (
    DataType, MessageType, DeviceFlags,
    CANDataFlags, CANFDDataFlags, LINDataFlags, FlexRayDataFlags,
    UARTDataFlags, AnalogDataFlags, EthernetDataFlags
)

try:
    from core.packets.tecmp.coherence_engine import TECMPCoherenceEngine, create_coherence_engine
    from core.packets.tecmp.tecmp_engine import TECMPEngine, create_professional_engine
    from core.packets.tecmp.packet_injector import (
        inject_all_features, inject_coherence, inject_professional,
        has_coherence_features, has_professional_features,
        create_professional_packet, validate_and_fix, ensure_compliance
    )
    ADVANCED_FEATURES_AVAILABLE = True
except ImportError:
    ADVANCED_FEATURES_AVAILABLE = False

class TECMPBuilderError(Exception):
    pass

class TECMPValidationError(TECMPBuilderError):
    pass

@dataclass
class TECMPConfig:
    device_id: int = 0x0080
    counter: int = 0
    version: int = 3
    message_type: int = MessageType.LOGGING_STREAM
    data_type: int = DataType.ETHERNET_II
    reserved: int = 0x0000
    device_flags: int = 0x0007
    interface_id: int = 0x00002d4a
    timestamp: Optional[int] = None
    timestamp_sync_status: int = 0
    data_flags: int = 0x0000
    length: Optional[int] = None  # FIXED: Changed from 74 to None - will be auto-calculated
    src_mac: str = "38:2a:19:80:41:cb"
    dst_mac: str = "01:00:5e:00:00:00"
    payload: Optional[bytes] = None
    
    # Professional features config
    enable_coherence: bool = False
    enable_professional: bool = False
    enable_time_sync: bool = False
    enable_hw_monitor: bool = False
    auto_inject_features: bool = False
    automotive_mode: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

class TECMPPacketBuilder:
    # Use DataType constants instead of hardcoded values
    PROTOCOL_TO_DATATYPE = {
        "Ethernet": DataType.ETHERNET_II,
        "CAN": DataType.CAN,
        "CAN-FD": DataType.CAN_FD,
        "LIN": DataType.LIN,
        "FlexRay": DataType.FLEXRAY,
        "UART": DataType.UART_RS232,
        "UART/RS232": DataType.UART_RS232,
        "Analog": DataType.ANALOG,
        "Digital": DataType.DIGITAL
    }
    
    # Use MessageType constants
    MSG_TYPE_CONTROL = MessageType.CONTROL
    MSG_TYPE_LOGGING_STREAM = MessageType.LOGGING_STREAM
    MSG_TYPE_REPLAY_DATA = MessageType.REPLAY_DATA
    
    # Use DeviceFlags constants
    FLAG_EOS = DeviceFlags.EOS
    FLAG_SOS = DeviceFlags.SOS
    FLAG_SPY = DeviceFlags.SPY
    FLAG_MULTI_FRAME = DeviceFlags.MULTI_FRAME
    
    # Common data flags
    FLAG_OVERFLOW = 0x8000  # Common across protocols
    FLAG_TX = 0x2000        # Common for CAN/CAN-FD/LIN
    FLAG_CRC_ERROR = 0x1000 # Common for CAN/CAN-FD
    
    DEVICE_ID_CM1000_HIGH1 = 0x0091
    
    TS_SYNC_NONE = 0
    TS_SYNC_MASTER = 1
    
    def __init__(self, *args, **kwargs) -> None:
        """Initialize TECMPPacketBuilder with flexible arguments"""
        self.logger = logging.getLogger("TECMP-Tool.TECMPPacketBuilder")
        
        # Handle flexible initialization
        self.parent = None
        initial_config = {}
        
        if len(args) > 0:
            self.parent = args[0]
        if len(args) > 1 and isinstance(args[1], dict):
            initial_config = args[1]
        
        # Get config from kwargs if provided
        if 'config' in kwargs and isinstance(kwargs['config'], dict):
            initial_config.update(kwargs['config'])
        if 'parent' in kwargs and self.parent is None:
            self.parent = kwargs['parent']
        
        self._config = TECMPConfig()
        
        # Apply initial config if provided
        for key, value in initial_config.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        
        self._segments: List[TECMPPacket] = []
        self._qos_settings = {
            "priority": 0,
            "segmentation": False,
            "max_segment_size": 1400,
            "validate": True,
            "validate_segments": True  # ADDED: Separate segment validation control
        }
        
        self._outer_ethernet_config = None
        self._packet_builder = None
        self._final_packet = None
        
        self._last_build_time = None
        self._last_error = None
        
        # Professional features
        self._coherence_engine: Optional[TECMPCoherenceEngine] = None
        self._professional_engine: Optional[TECMPEngine] = None
        self._data_builder = TECMPDataBuilder()
        self._lock = threading.RLock()
        self._tracked_packets: weakref.WeakSet = weakref.WeakSet()
        
        # Performance cache
        self._template_cache: Dict[str, Dict] = {}
        self._protocol_cache: Dict[str, int] = {}
        
        self._initialize_professional_features()

    def _initialize_professional_features(self):
        if not ADVANCED_FEATURES_AVAILABLE:
            return
        
        try:
            self._coherence_engine = create_coherence_engine(auto_fix=True, strict=False)
        except Exception as e:
            self.logger.debug(f"Coherence engine initialization failed: {e}")
        
        try:
            if self._config.enable_professional:
                self._professional_engine = create_professional_engine(
                    device_id=self._config.device_id,
                    config={
                        'enable_time_sync': self._config.enable_time_sync,
                        'enable_hw_monitor': self._config.enable_hw_monitor,
                        'time_sync_master': False
                    }
                )
        except Exception as e:
            self.logger.debug(f"Professional engine initialization failed: {e}")

    def _convert_hex_value(self, value: Any) -> Any:
        if isinstance(value, str):
            if value.startswith("0x") or value.startswith("0X"):
                try:
                    return int(value, 16)
                except ValueError:
                    pass
            if re.match(r'^[0-9A-Fa-f]{1,}$', value):
                try:
                    return int(value, 16)
                except ValueError:
                    pass
        return value
    
    def _convert_dict_hex_values(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for key, value in config_dict.items():
            result[key] = self._convert_hex_value(value)
        return result
    
    def _current_nanoseconds(self) -> int:
        if self._professional_engine and hasattr(self._professional_engine, 'time_sync'):
            if self._professional_engine.time_sync.running:
                return self._professional_engine.time_sync.get_synchronized_time()
        return int(time.time() * 1e9)
    
    def _get_device_name(self, device_id: int) -> str:
        if device_id == self.DEVICE_ID_CM1000_HIGH1:
            return "CM 1000 High 1"
        elif device_id == 0x0080:
            return "Standard TECMP Device"
        else:
            return f"Unknown (0x{device_id:04X})"

    def with_device_id(self, device_id: int) -> "TECMPPacketBuilder":
        self._config.device_id = self._convert_hex_value(device_id)
        return self
    
    def with_counter(self, counter: int) -> "TECMPPacketBuilder":
        self._config.counter = counter
        return self
    
    def with_version(self, version: int) -> "TECMPPacketBuilder":
        self._config.version = version
        return self
    
    def with_message_type(self, msg_type: int) -> "TECMPPacketBuilder":
        self._config.message_type = self._convert_hex_value(msg_type)
        return self
    
    def with_data_type(self, data_type: int) -> "TECMPPacketBuilder":
        self._config.data_type = self._convert_hex_value(data_type)
        return self
    
    def with_reserved(self, reserved: int) -> "TECMPPacketBuilder":
        self._config.reserved = self._convert_hex_value(reserved)
        return self
    
    def with_device_flags(self, device_flags: int) -> "TECMPPacketBuilder":
        self._config.device_flags = self._convert_hex_value(device_flags)
        return self
    
    def with_interface_id(self, interface_id: int) -> "TECMPPacketBuilder":
        self._config.interface_id = self._convert_hex_value(interface_id)
        return self
    
    def with_timestamp(self, timestamp: int) -> "TECMPPacketBuilder":
        self._config.timestamp = timestamp
        return self
    
    def with_timestamp_sync_status(self, status: int) -> "TECMPPacketBuilder":
        self._config.timestamp_sync_status = status
        return self
    
    def with_data_flags(self, data_flags: int) -> "TECMPPacketBuilder":
        self._config.data_flags = self._convert_hex_value(data_flags)
        return self
    
    def with_length(self, length: int) -> "TECMPPacketBuilder":
        self._config.length = length
        return self

    def with_source_mac(self, src: str) -> "TECMPPacketBuilder":
        self._config.src_mac = src
        return self

    def with_destination_mac(self, dst: str) -> "TECMPPacketBuilder":
        self._config.dst_mac = dst
        return self

    def with_payload(self, payload: bytes) -> "TECMPPacketBuilder":
        self._config.payload = payload
        # FIXED: Auto-calculate length if not explicitly set
        if self._config.length is None:
            self._config.length = len(payload)
        return self

    def with_priority(self, prio: int) -> "TECMPPacketBuilder":
        self._qos_settings["priority"] = prio
        return self
    
    def with_encapsulated_protocols(self, protocols: List) -> "TECMPPacketBuilder":
        """
        Process encapsulated protocols for data type detection
        Note: encapsulated_protocols field removed from TECMPPacket
        """
        # Only use for data type detection
        if protocols:
            data_type = self.detect_data_type_from_protocols(protocols)
            if data_type != DataType.ETHERNET_II or self._config.data_type == DataType.ETHERNET_II:
                self._config.data_type = data_type
        
        return self
    
    def enable_segmentation(self, max_size: Optional[int] = None) -> "TECMPPacketBuilder":
        self._qos_settings["segmentation"] = True
        if max_size is not None:
            self._qos_settings["max_segment_size"] = max_size
        return self

    def disable_validation(self) -> "TECMPPacketBuilder":
        self._qos_settings["validate"] = False
        return self
    
    def disable_segment_validation(self) -> "TECMPPacketBuilder":
        """ADDED: Disable validation specifically for segments"""
        self._qos_settings["validate_segments"] = False
        return self

    # Professional feature methods
    def with_professional_features(self, enable: bool = True) -> "TECMPPacketBuilder":
        self._config.enable_professional = enable
        self._config.auto_inject_features = enable
        if enable and not self._professional_engine:
            self._initialize_professional_engine()
        return self
    
    def with_coherence_validation(self, enable: bool = True) -> "TECMPPacketBuilder":
        self._config.enable_coherence = enable
        self._config.auto_inject_features = enable
        return self
    
    def with_automotive_mode(self, enable: bool = True) -> "TECMPPacketBuilder":
        self._config.automotive_mode = enable
        self._config.enable_coherence = enable
        self._config.auto_inject_features = enable
        if enable:
            self._config.device_id = 0x0040  # CAN Combo default
        return self
    
    def with_time_sync(self, enable: bool = True, master: bool = False) -> "TECMPPacketBuilder":
        self._config.enable_time_sync = enable
        if enable and not self._professional_engine:
            self._initialize_professional_engine()
        if self._professional_engine:
            self._professional_engine.time_sync.is_grandmaster = master
        return self
    
    def with_hw_monitoring(self, enable: bool = True) -> "TECMPPacketBuilder":
        self._config.enable_hw_monitor = enable
        if enable and not self._professional_engine:
            self._initialize_professional_engine()
        return self

    def _initialize_professional_engine(self):
        if not ADVANCED_FEATURES_AVAILABLE or self._professional_engine:
            return
        
        try:
            self._professional_engine = create_professional_engine(
                device_id=self._config.device_id,
                config={
                    'enable_time_sync': self._config.enable_time_sync,
                    'enable_hw_monitor': self._config.enable_hw_monitor,
                    'time_sync_master': False
                }
            )
        except Exception as e:
            self.logger.debug(f"Professional engine initialization failed: {e}")

    def with_outer_ethernet_frame(self, **ethernet_config) -> "TECMPPacketBuilder":
        default_config = {
            "src_mac": "38:2a:19:80:41:cb",
            "dst_mac": "01:00:5e:00:00:00",
            "ether_type": 0x99FE
        }
        
        config = default_config.copy()
        config.update(ethernet_config)
        config = self._convert_dict_hex_values(config)
        
        self._outer_ethernet_config = config
        
        if "src_mac" in config:
            self._config.src_mac = config["src_mac"]
        if "dst_mac" in config:
            self._config.dst_mac = config["dst_mac"]
        
        return self
    
    def with_tecmp_config(self, tecmp_config: Dict[str, Any]) -> "TECMPPacketBuilder":
        tecmp_config = self._convert_dict_hex_values(tecmp_config)
        
        if "msg_type" in tecmp_config and "message_type" not in tecmp_config:
            tecmp_config["message_type"] = tecmp_config.pop("msg_type")
        
        if "timestamp_sync_status" in tecmp_config:
            self._config.timestamp_sync_status = tecmp_config.pop("timestamp_sync_status")
        
        if "encapsulated" in tecmp_config or "encapsulated_protocols" in tecmp_config:
            protocols = tecmp_config.get("encapsulated", tecmp_config.get("encapsulated_protocols", []))
            # Use protocols only for data type detection
            if "data_type" not in tecmp_config or tecmp_config["data_type"] is None:
                data_type = self.detect_data_type_from_protocols(protocols)
                tecmp_config["data_type"] = data_type
        
        # Handle professional features in config
        if "enable_professional" in tecmp_config:
            self._config.enable_professional = tecmp_config.pop("enable_professional")
        if "enable_coherence" in tecmp_config:
            self._config.enable_coherence = tecmp_config.pop("enable_coherence")
        if "auto_inject_features" in tecmp_config:
            self._config.auto_inject_features = tecmp_config.pop("auto_inject_features")
        
        for key, value in tecmp_config.items():
            if key not in ["encapsulated", "encapsulated_protocols"]:
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
        
        return self
    
    def detect_data_type_from_protocols(self, protocols: List) -> int:
        data_type = DataType.ETHERNET_II  # Default to ETHERNET_II instead of hardcoded 0x80
        
        if not protocols:
            return data_type
        
        # Cache check
        cache_key = str([type(p).__name__ for p in protocols if p])
        if cache_key in self._protocol_cache:
            return self._protocol_cache[cache_key]
        
        for protocol in protocols:
            protocol_name = None
            
            if hasattr(protocol, "name"):
                protocol_name = protocol.name
            elif isinstance(protocol, dict) and "name" in protocol:
                protocol_name = protocol["name"]
            elif hasattr(protocol, "__class__") and hasattr(protocol.__class__, "__name__"):
                protocol_name = protocol.__class__.__name__
                
            if protocol_name:
                base_name = str(protocol_name).split(" ")[0].split("(")[0]
                
                for proto_key, proto_data_type in self.PROTOCOL_TO_DATATYPE.items():
                    if proto_key.lower() in base_name.lower():
                        self.logger.debug(f"TECMP data type detected: 0x{proto_data_type:02x} ({base_name})")
                        data_type = proto_data_type
                        break
                
                if data_type != DataType.ETHERNET_II:
                    break
        
        # Cache result
        self._protocol_cache[cache_key] = data_type
        return data_type

    # Automotive specific methods - FIXED
    def with_automotive_can(self, can_id: int, data: bytes, **kwargs) -> "TECMPPacketBuilder":
        """
        Build CAN packet with proper RTR validation
        
        Args:
            can_id: CAN identifier
            data: CAN data payload
            **kwargs: Additional flags (ide, rtr, tx, etc.)
        """
        self.with_automotive_mode(True)
        self.with_data_type(DataType.CAN)
        self.with_device_id(0x0040)  # CAN Combo
        self.with_interface_id(0x00001000)
        
        # FIXED: RTR validation - RTR frames should have empty data
        rtr = kwargs.get('rtr', False)
        if rtr and len(data) > 0:
            self.logger.warning("RTR frame cannot have data - clearing data field")
            data = b''  # Clear data for RTR frames
        
        # Build CAN payload - keep essential flags
        payload, data_flags = self._data_builder.build_payload(
            data_type=DataType.CAN,
            can_id=can_id,
            data=data,
            dlc=kwargs.get('dlc', len(data)),  # DLC is required
            ide=kwargs.get('ide', False),      # Extended ID
            rtr=rtr,                           # Remote Request
            tx=kwargs.get('tx', False)         # Transmitted frame
        )
        self.with_payload(payload)
        self.with_data_flags(data_flags)
        return self
    
    def with_automotive_flexray(self, cycle: int, frame_id: int, data: bytes, **kwargs) -> "TECMPPacketBuilder":
        self.with_automotive_mode(True)
        self.with_data_type(DataType.FLEXRAY)
        self.with_device_id(0x0070)  # FlexRay High
        self.with_interface_id(0x00003000)
        
        # FlexRay basic parameters only - flags via kwargs if handler supports them
        try:
            payload, data_flags = self._data_builder.build_payload(
                data_type=DataType.FLEXRAY,
                cycle=cycle,
                frame_id=frame_id,
                data=data,
                **kwargs  # Pass any additional parameters the handler might accept
            )
        except TypeError:
            # Fallback: only basic parameters
            payload, data_flags = self._data_builder.build_payload(
                data_type=DataType.FLEXRAY,
                cycle=cycle,
                frame_id=frame_id,
                data=data
            )
        self.with_payload(payload)
        self.with_data_flags(data_flags)
        return self
    
    def with_automotive_lin(self, lin_id: int, data: bytes, **kwargs) -> "TECMPPacketBuilder":
        self.with_automotive_mode(True)
        self.with_data_type(DataType.LIN)
        self.with_device_id(0x0030)  # LIN Combo
        self.with_interface_id(0x00002000)
        
        # LIN with common flags
        try:
            payload, data_flags = self._data_builder.build_payload(
                data_type=DataType.LIN,
                lin_id=lin_id,
                data=data,
                tx=kwargs.get('tx', False),  # Transmitted frame
                **kwargs  # Other flags if supported
            )
        except TypeError:
            # Fallback: only basic parameters
            payload, data_flags = self._data_builder.build_payload(
                data_type=DataType.LIN,
                lin_id=lin_id,
                data=data
            )
        self.with_payload(payload)
        self.with_data_flags(data_flags)
        return self
    
    def with_scenario_template(self, scenario_name: str, **params) -> "TECMPPacketBuilder":
        if not self._professional_engine or not hasattr(self._professional_engine, 'template_manager'):
            self.logger.warning("Scenario templates require professional engine")
            return self
        
        # Cache check
        cache_key = f"{scenario_name}_{hash(str(sorted(params.items())))}"
        if cache_key in self._template_cache:
            template_config = self._template_cache[cache_key]
        else:
            try:
                template = self._professional_engine.template_manager.get_template(scenario_name)
                if template:
                    template_config = template.parameters.copy()
                    template_config.update(params)
                    self._template_cache[cache_key] = template_config
                else:
                    self.logger.warning(f"Template '{scenario_name}' not found")
                    return self
            except Exception as e:
                self.logger.error(f"Template loading failed: {e}")
                return self
        
        self.with_tecmp_config(template_config)
        return self

    def set_eos_flag(self, enable: bool = True) -> "TECMPPacketBuilder":
        if enable:
            self._config.device_flags |= self.FLAG_EOS
        else:
            self._config.device_flags &= ~self.FLAG_EOS
        return self
    
    def set_sos_flag(self, enable: bool = True) -> "TECMPPacketBuilder":
        if enable:
            self._config.device_flags |= self.FLAG_SOS
        else:
            self._config.device_flags &= ~self.FLAG_SOS
        return self
    
    def set_spy_flag(self, enable: bool = True) -> "TECMPPacketBuilder":
        if enable:
            self._config.device_flags |= self.FLAG_SPY
        else:
            self._config.device_flags &= ~self.FLAG_SPY
        return self
    
    def set_multi_frame_flag(self, enable: bool = True) -> "TECMPPacketBuilder":
        if enable:
            self._config.device_flags |= self.FLAG_MULTI_FRAME
        else:
            self._config.device_flags &= ~self.FLAG_MULTI_FRAME
        return self

    def set_overflow_flag(self, enable: bool = True) -> "TECMPPacketBuilder":
        if enable:
            self._config.data_flags |= self.FLAG_OVERFLOW
        else:
            self._config.data_flags &= ~self.FLAG_OVERFLOW
        return self
    
    def set_tx_flag(self, enable: bool = True) -> "TECMPPacketBuilder":
        if enable:
            self._config.data_flags |= self.FLAG_TX
        else:
            self._config.data_flags &= ~self.FLAG_TX
        return self
    
    def set_crc_error_flag(self, enable: bool = True) -> "TECMPPacketBuilder":
        if enable:
            self._config.data_flags |= self.FLAG_CRC_ERROR
        else:
            self._config.data_flags &= ~self.FLAG_CRC_ERROR
        return self

    def build_outer_ethernet(self, **ethernet_config) -> "TECMPPacketBuilder":
        self.with_outer_ethernet_frame(**ethernet_config)
        return self
    
    def build_tecmp(self, tecmp_config: Dict[str, Any]) -> "TECMPPacketBuilder":
        self.with_tecmp_config(tecmp_config)
        return self

    def as_logging_stream(self) -> "TECMPPacketBuilder":
        self._config.message_type = self.MSG_TYPE_LOGGING_STREAM
        self._config.device_id = self.DEVICE_ID_CM1000_HIGH1
        self._config.device_flags = 0x0007
        return self
    
    def as_cm1000_high1(self) -> "TECMPPacketBuilder":
        self._config.device_id = self.DEVICE_ID_CM1000_HIGH1
        return self

    def build(self) -> Union[TECMPPacket, Any]:
        start_time = time.time()
        
        try:
            # Enhanced timestamp handling
            if self._config.timestamp is None:
                self._config.timestamp = self._current_nanoseconds()
            
            # FIXED: Auto-calculate length from payload if not set
            if self._config.length is None and self._config.payload is not None:
                self._config.length = len(self._config.payload)
            elif self._config.length is None:
                self._config.length = 0
            
            # Create packet with professional features
            tecmp_packet = self._create_enhanced_packet()
            
            # Apply professional enhancements
            if self._config.enable_professional or self._config.auto_inject_features:
                self._apply_professional_enhancements(tecmp_packet)
            
            # Apply feature injection
            if self._config.auto_inject_features:
                self._apply_feature_injection(tecmp_packet)
            
            # Apply coherence validation
            if self._config.enable_coherence or self._qos_settings["validate"]:
                self._apply_validation_and_coherence(tecmp_packet)
            
            # Handle segmentation
            if (self._qos_settings["segmentation"] and 
                self._config.payload is not None and 
                len(self._config.payload) > self._qos_settings["max_segment_size"]):
                segments = self._build_segmented()
                self._segments = segments
                return segments[0]
            
            # Build complete packet if outer ethernet configured
            if self._outer_ethernet_config:
                return self.build_complete_packet(tecmp_packet)
            
            # Track packet
            self._tracked_packets.add(tecmp_packet)
            
            self._last_build_time = time.time() - start_time
            return tecmp_packet
            
        except Exception as e:
            self._last_error = str(e)
            if isinstance(e, TECMPValidationError):
                raise
            else:
                raise TECMPBuilderError(f"Error building TECMP packet: {str(e)}") from e
    
    def _create_enhanced_packet(self) -> TECMPPacket:
        """Create TECMP packet without encapsulated_protocols"""
        return TECMPPacket(
            device_id=self._config.device_id,
            counter=self._config.counter,
            version=self._config.version,
            message_type=self._config.message_type,
            data_type=self._config.data_type,
            reserved=self._config.reserved,
            device_flags=self._config.device_flags,
            interface_id=self._config.interface_id,
            timestamp=self._config.timestamp,
            timestamp_sync_status=self._config.timestamp_sync_status,
            data_flags=self._config.data_flags,
            length=self._config.length,
            payload=self._config.payload
        )
    
    def _apply_professional_enhancements(self, packet: TECMPPacket):
        if not self._professional_engine:
            return
        
        try:
            # Apply synchronized timestamp
            if hasattr(self._professional_engine, 'time_sync') and self._professional_engine.time_sync.running:
                sync_timestamp = self._professional_engine.time_sync.get_synchronized_time()
                sync_flags = self._professional_engine.time_sync.get_synchronization_flags()
                if hasattr(packet, 'set_timestamp_with_flags'):
                    packet.set_timestamp_with_flags(sync_timestamp | sync_flags)
                else:
                    packet.timestamp = sync_timestamp | sync_flags
            
            # Apply hardware monitoring
            if (packet.message_type == MessageType.STATUS_DEVICE and
                hasattr(self._professional_engine, 'hardware_monitor')):
                status_payload = self._professional_engine.hardware_monitor.generate_status_device_payload()
                if hasattr(packet, 'set_payload'):
                    packet.set_payload(status_payload)
                else:
                    packet.payload = status_payload
                    packet.length = len(status_payload)
            
        except Exception as e:
            self.logger.debug(f"Professional enhancement failed: {e}")
    
    def _apply_feature_injection(self, packet: TECMPPacket):
        if not ADVANCED_FEATURES_AVAILABLE:
            return
        
        try:
            if self._config.enable_professional:
                inject_all_features(packet)
                if hasattr(packet, 'enable_professional_mode'):
                    packet.enable_professional_mode({
                        'enable_time_sync': self._config.enable_time_sync,
                        'enable_hw_monitor': self._config.enable_hw_monitor
                    })
            elif self._config.enable_coherence:
                inject_coherence(packet)
            
        except Exception as e:
            self.logger.debug(f"Feature injection failed: {e}")
    
    def _apply_validation_and_coherence(self, packet: TECMPPacket):
        try:
            if hasattr(packet, 'validate'):
                packet.validate()
            
            if (self._coherence_engine and hasattr(packet, 'validate_coherence')):
                report = packet.validate_coherence()
                if not report.is_coherent and self._config.automotive_mode:
                    if hasattr(packet, 'auto_fix_violations'):
                        packet.auto_fix_violations(apply=True)
            
        except Exception as e:
            self.logger.debug(f"Validation failed: {e}")

    def build_complete_packet(self, tecmp_packet: TECMPPacket):
        try:
            from core.builders.packet_builder import PacketBuilder
            packet_builder = PacketBuilder()
            
            packet_builder.add_layer("ethernet", **self._outer_ethernet_config)
            
            tecmp_bytes = tecmp_packet.serialize()
            
            tecmp_config = {
                "device_id": self._config.device_id,
                "counter": self._config.counter,
                "version": self._config.version,
                "message_type": self._config.message_type,
                "data_type": self._config.data_type,
                "reserved": self._config.reserved,
                "device_flags": self._config.device_flags,
                "interface_id": self._config.interface_id,
                "timestamp": self._config.timestamp,
                "timestamp_sync_status": self._config.timestamp_sync_status,
                "data_flags": self._config.data_flags,
                "length": self._config.length,
                "payload": tecmp_bytes
            }
            
            packet_builder.encapsulate_tecmp(tecmp_config)
            final_packet = packet_builder.build()
            self._final_packet = final_packet
            
            return final_packet
            
        except Exception as e:
            raise TECMPBuilderError(f"Error building complete packet: {str(e)}") from e
    
    def _build_segmented(self) -> List[TECMPPacket]:
        """FIXED: Build segmented packets with proper validation handling"""
        try:
            payload = self._config.payload or b""
            segment_size = self._qos_settings["max_segment_size"]
            total_segments = (len(payload) + segment_size - 1) // segment_size
            
            mem_view = memoryview(payload)
            segments = []
            
            for i in range(total_segments):
                start = i * segment_size
                end = min((i + 1) * segment_size, len(payload))
                segment_data = mem_view[start:end].tobytes()
                
                # Clear existing EOS/SOS flags
                device_flags = self._config.device_flags & ~(DeviceFlags.EOS | DeviceFlags.SOS)
                
                # Set appropriate flags for segments
                if i == 0:
                    device_flags |= self.FLAG_SOS
                if i == total_segments - 1:
                    device_flags |= self.FLAG_EOS
                
                # ADDED: For multi-segment packets, set multi-frame flag
                if total_segments > 1:
                    device_flags |= self.FLAG_MULTI_FRAME
                
                segment_pkt = TECMPPacket(
                    device_id=self._config.device_id,
                    counter=self._config.counter + i,
                    version=self._config.version,
                    message_type=self._config.message_type,
                    data_type=self._config.data_type,
                    reserved=self._config.reserved,
                    device_flags=device_flags,
                    interface_id=self._config.interface_id,
                    timestamp=self._config.timestamp or self._current_nanoseconds(),
                    timestamp_sync_status=self._config.timestamp_sync_status,
                    data_flags=self._config.data_flags,
                    payload=segment_data,
                    length=len(segment_data)
                )
                
                # Apply features to segments
                if self._config.auto_inject_features:
                    self._apply_feature_injection(segment_pkt)
                
                # FIXED: Only validate if segment validation is enabled
                if self._qos_settings["validate"] and self._qos_settings["validate_segments"]:
                    try:
                        segment_pkt.validate()
                    except TECMPValidationError as e:
                        # Skip single-packet rules for segments
                        if "Single packet must have both EOS and SOS flags" not in str(e):
                            raise
                
                segments.append(segment_pkt)
            
            return segments
            
        except Exception as e:
            raise TECMPBuilderError(f"Error building segmented TECMP packets: {str(e)}") from e
    
    def segmented(self) -> Iterator[TECMPPacket]:
        """FIXED: Generate segmented packets with proper validation handling"""
        try:
            payload = self._config.payload or b""
            segment_size = self._qos_settings["max_segment_size"]
            total_segments = (len(payload) + segment_size - 1) // segment_size
            
            mem_view = memoryview(payload)
            
            for i in range(total_segments):
                start = i * segment_size
                end = min((i + 1) * segment_size, len(payload))
                segment_data = mem_view[start:end].tobytes()
                
                # Clear existing EOS/SOS flags
                device_flags = self._config.device_flags & ~(DeviceFlags.EOS | DeviceFlags.SOS)
                
                # Set appropriate flags for segments
                if i == 0:
                    device_flags |= self.FLAG_SOS
                if i == total_segments - 1:
                    device_flags |= self.FLAG_EOS
                
                # ADDED: For multi-segment packets, set multi-frame flag
                if total_segments > 1:
                    device_flags |= self.FLAG_MULTI_FRAME
                
                segment_pkt = TECMPPacket(
                    device_id=self._config.device_id,
                    counter=self._config.counter + i,
                    version=self._config.version,
                    message_type=self._config.message_type,
                    data_type=self._config.data_type,
                    reserved=self._config.reserved,
                    device_flags=device_flags,
                    interface_id=self._config.interface_id,
                    timestamp=self._config.timestamp or self._current_nanoseconds(),
                    timestamp_sync_status=self._config.timestamp_sync_status,
                    data_flags=self._config.data_flags,
                    payload=segment_data,
                    length=len(segment_data)
                )
                
                if self._config.auto_inject_features:
                    self._apply_feature_injection(segment_pkt)
                
                # FIXED: Only validate if segment validation is enabled
                if self._qos_settings["validate"] and self._qos_settings["validate_segments"]:
                    try:
                        segment_pkt.validate()
                    except TECMPValidationError as e:
                        # Skip single-packet rules for segments
                        if "Single packet must have both EOS and SOS flags" not in str(e):
                            raise
                
                yield segment_pkt
                
        except Exception as e:
            raise TECMPBuilderError(f"Error generating TECMP segments: {str(e)}") from e

    def get_segments(self) -> List[TECMPPacket]:
        return self._segments
    
    def get_final_packet(self):
        return self._final_packet
        
    def get_build_stats(self) -> Dict[str, Any]:
        return {
            "build_time": self._last_build_time,
            "last_error": self._last_error,
            "config": self._config.to_dict(),
            "professional_features": self._config.enable_professional,
            "coherence_enabled": self._config.enable_coherence,
            "automotive_mode": self._config.automotive_mode,
            "auto_fixes_applied": len([p for p in self._tracked_packets 
                                      if hasattr(p, '_auto_fixes_applied') and p._auto_fixes_applied])
        }
    
    def get_professional_status(self) -> Dict[str, Any]:
        status = {
            'builder': {
                'professional_enabled': self._config.enable_professional,
                'coherence_enabled': self._config.enable_coherence,
                'automotive_mode': self._config.automotive_mode,
                'auto_injection': self._config.auto_inject_features
            },
            'engines': {
                'coherence_available': self._coherence_engine is not None,
                'professional_available': self._professional_engine is not None
            },
            'cache': {
                'protocol_entries': len(self._protocol_cache),
                'template_entries': len(self._template_cache)
            }
        }
        
        if self._professional_engine:
            status['professional_engine'] = self._professional_engine.get_engine_status()
        
        return status

    @staticmethod
    def from_wireshark_sample() -> "TECMPPacketBuilder":
        builder = TECMPPacketBuilder()
        return (builder
                .with_device_id(0x0091)
                .with_counter(26836)
                .with_version(3)
                .with_message_type(MessageType.LOGGING_STREAM)
                .with_data_type(DataType.ETHERNET_II)
                .with_reserved(0x0000)
                .with_device_flags(0x0007)
                .with_interface_id(0x00002d4a)
                .with_timestamp_sync_status(1)
                .with_length(74)
                .with_data_flags(0x0000)
                .with_source_mac("38:2a:19:80:41:cb")
                .with_destination_mac("01:00:5e:00:00:00"))
    
    @staticmethod
    def professional_builder(device_id: int = 0x0040) -> "TECMPPacketBuilder":
        return (TECMPPacketBuilder()
                .with_device_id(device_id)
                .with_professional_features(True)
                .with_coherence_validation(True)
                .with_time_sync(True)
                .with_hw_monitoring(True))
    
    @staticmethod
    def automotive_builder(device_id: int = 0x0040) -> "TECMPPacketBuilder":
        return (TECMPPacketBuilder()
                .with_device_id(device_id)
                .with_automotive_mode(True)
                .with_professional_features(True))
    
    @staticmethod
    def build_encapsulated_packet(outer_ethernet_config, tecmp_config, encapsulated_protocols=None):
        builder = TECMPPacketBuilder()
        
        builder.with_outer_ethernet_frame(**outer_ethernet_config)
        builder.with_tecmp_config(tecmp_config)
        
        if encapsulated_protocols:
            builder.with_encapsulated_protocols(encapsulated_protocols)
        
        return builder.build()
    
    @staticmethod
    def from_config(config: Dict[str, Any]) -> "TECMPPacketBuilder":
        builder = TECMPPacketBuilder()
        builder.with_tecmp_config(config)
        return builder

# =============================================================================
# ONE-LINE API
# =============================================================================

__all__ = [
    # Main classes
    'TECMPPacketBuilder',
    'TECMPBuilderError',
    'TECMPValidationError',
    'TECMPConfig',
    
    # ONE-LINE API
    # 'Builder' - moved to builder_api.py                       
]
# Alias for backward compatibility
Builder = TECMPPacketBuilder