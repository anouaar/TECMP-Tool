#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tecmp_packet.py - TECMP v1.7 Packet Implementation
==================================================

Complete implementation of TECMP (Technically Enhanced Capture Module Protocol) v1.7
according to official Technica Engineering specification.

Features:
- Full TECMP header and payload structure
- Automatic segmentation for payloads > 800 bytes
- Multi-frame support with proper header handling
- Device flags management (EOS/SOS/SPY/etc.)
- Timestamp handling with synchronization flags
- Complete validation according to official ranges
- Serialization/deserialization with exact byte structure

Reference: TECMP User Manual v1.7 - July 2022
"""

import struct
import time
import logging
import copy
from typing import Optional, Dict, List, Any, Tuple, Union
from dataclasses import dataclass

# Import all constants from centralized location
from .constants import (
    TECMP_ETHERTYPE, TECMP_VERSION, TECMP_HEADER_SIZE,
    TECMP_DEVICE_FLAGS_SIZE, TECMP_PAYLOAD_HEADER_SIZE,
    MAX_UNSEGMENTED_SIZE, MAX_ETHERNET_PAYLOAD,
    MessageType, DataType, DeviceFlags,
    DEVICE_ID_RANGES, SPECIAL_INTERFACE_IDS,
    TIMESTAMP_VALUE_MASK, TIMESTAMP_RECALC_BIT, TIMESTAMP_SYNC_BIT,
    get_device_type_name, get_data_type_name, validate_device_id,
    ControlMessageID, validate_control_message_id
)

# ============================================================================
# EXCEPTIONS
# ============================================================================

class TECMPError(Exception):
    """Base exception for TECMP errors"""
    pass

class TECMPParsingError(TECMPError):
    """Error during packet parsing/deserialization"""
    pass

class TECMPSerializationError(TECMPError):
    """Error during packet serialization"""
    pass

class TECMPValidationError(TECMPError):
    """Error during packet validation"""
    pass

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class SegmentInfo:
    """Information for packet segmentation tracking"""
    segment_id: int
    total_segments: int
    sequence_number: int
    is_first: bool
    is_last: bool
    original_length: int

@dataclass
class MultiFrameInfo:
    """Information for multi-frame packets"""
    frame_count: int
    total_size: int
    frame_sizes: List[int]

# ============================================================================
# MAIN TECMP PACKET CLASS
# ============================================================================

class TECMPPacket:
    """
    TECMP Packet implementation according to v1.7 specification
    
    This class represents a complete TECMP packet with all header fields,
    device flags, payload header, and data payload. It handles serialization,
    deserialization, validation, segmentation, and multi-frame support.
    
    Attributes:
        # Global header (12 bytes)
        device_id: Device identifier (0x30-0x7F + standard)
        counter: Message counter (wraps at 0xFFFF)
        version: Protocol version (always 3)
        message_type: Type of TECMP message
        data_type: Type of encapsulated data
        reserved: Reserved field (always 0)
        
        # Device flags (2 bytes)
        device_flags: Combination of DeviceFlags bits
        
        # Payload header (16 bytes)
        interface_id: Unique bus/interface identifier
        timestamp: 62-bit nanoseconds + 2-bit flags
        length: Payload length in bytes
        data_flags: Protocol-specific flags
        
        # Data
        payload: Raw data bytes
    """
    
    def __init__(self,
                 device_id: int = 0x0040,
                 counter: int = 0,
                 version: int = TECMP_VERSION,
                 message_type: int = MessageType.LOGGING_STREAM,
                 data_type: int = DataType.ETHERNET_II,  # ALIGNED: Use official name
                 reserved: int = 0x0000,
                 device_flags: Optional[int] = None,
                 interface_id: int = 0x00000000,
                 timestamp: Optional[int] = None,
                 timestamp_sync_status: int = 0,
                 timestamp_recalc_flag: bool = False,
                 length: Optional[int] = None,
                 data_flags: int = 0x0000,
                 payload: bytes = b""):
        """
        Initialize TECMP packet with all fields
        
        Args:
            device_id: Device ID according to Table 25
            counter: Message counter (auto-increments)
            version: Protocol version (default 3)
            message_type: Message type from MessageType enum
            data_type: Data type from DataType enum
            reserved: Reserved field (must be 0)
            device_flags: Combination of DeviceFlags (auto-calculated if None)
            interface_id: Unique interface identifier
            timestamp: Timestamp in nanoseconds (auto-generated if None)
            timestamp_sync_status: Synchronization status (0=synced, 1=lost)
            timestamp_recalc_flag: Whether timestamp was recalculated
            length: Payload length (auto-calculated if None)
            data_flags: Protocol-specific data flags
            payload: Raw payload bytes
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Global header fields
        self.device_id = device_id & 0xFFFF
        self.counter = counter & 0xFFFF
        self.version = version & 0xFF
        self.message_type = message_type & 0xFF
        self.data_type = data_type & 0xFFFF
        self.reserved = reserved & 0xFFFF
        
        # Payload header fields
        self.interface_id = interface_id & 0xFFFFFFFF
        self.timestamp_sync_status = timestamp_sync_status & 0x01
        self.timestamp_recalc_flag = bool(timestamp_recalc_flag)
        self.data_flags = data_flags & 0xFFFF
        
        # PAYLOAD - Ensure attribute is always defined
        self.payload = bytes(payload) if payload is not None else b""
        
        # Length (auto-calculate if not provided)
        if length is None:
            self.length = len(self.payload)
        else:
            self.length = length & 0xFFFF
        
        # Timestamp (generate if not provided)
        if timestamp is None:
            self.timestamp = int(time.time() * 1e9) & TIMESTAMP_VALUE_MASK
        else:
            self.timestamp = timestamp & TIMESTAMP_VALUE_MASK
        
        # Internal state - DEFINE FIRST BEFORE device_flags
        self._segment_info: Optional[SegmentInfo] = None
        self._multi_frame_info: Optional[MultiFrameInfo] = None
        self._device_overflow_detected = False  # Track device overflow state
        
        # Cache for performance
        self._cached_serialized: Optional[bytes] = None
        self._is_dirty = True
        
        # Device flags (auto-calculate if not provided) - AFTER internal state
        if device_flags is None:
            self.device_flags = self._calculate_default_device_flags()
        else:
            self.device_flags = device_flags & 0xFFFF
        
        # Validation - Ensure payload is accessible
        if not hasattr(self, 'payload'):
            raise RuntimeError("CRITICAL: payload attribute not set!")
        
        self.logger.debug(f"Created TECMP packet: device_id=0x{self.device_id:04X}, "
                         f"type={get_data_type_name(self.data_type)}, "
                         f"payload={len(self.payload)} bytes")
    
    # ========================================================================
    # PROPERTIES
    # ========================================================================
    
    @property
    def size(self) -> int:
        """Total packet size including all headers"""
        return (TECMP_HEADER_SIZE + TECMP_DEVICE_FLAGS_SIZE + 
                TECMP_PAYLOAD_HEADER_SIZE + len(self.payload))
    
    @property
    def is_segmented(self) -> bool:
        """Check if packet is part of a segmented sequence"""
        return self._segment_info is not None
    
    @property
    def is_multi_frame(self) -> bool:
        """Check if packet contains multiple frames"""
        return bool(self.device_flags & DeviceFlags.MULTI_FRAME)
    
    @property
    def device_type_name(self) -> str:
        """Get human-readable device type name"""
        return get_device_type_name(self.device_id)
    
    @property
    def data_type_name(self) -> str:
        """Get human-readable data type name"""
        return get_data_type_name(self.data_type)
    
    @property
    def message_type_name(self) -> str:
        """Get human-readable message type name"""
        names = {
            MessageType.CONTROL: "Control Message",
            MessageType.STATUS_DEVICE: "Status Device",
            MessageType.STATUS_BUS: "Status Bus/IVN",
            MessageType.LOGGING_STREAM: "Logging Stream",
            MessageType.STATUS_CONFIG: "Status Configuration",
            MessageType.REPLAY_DATA: "Replay Data"
        }
        return names.get(self.message_type, f"Unknown (0x{self.message_type:02X})")
    
    # ========================================================================
    # DEVICE FLAGS MANAGEMENT
    # ========================================================================
    
    def _calculate_default_device_flags(self) -> int:
        """Calculate default device flags based on context"""
        flags = 0
        
        # SPY mode is standard for logging
        if self.message_type == MessageType.LOGGING_STREAM:
            flags |= DeviceFlags.SPY
        
        # Set EOS/SOS based on payload size
        if len(self.payload) <= MAX_UNSEGMENTED_SIZE:
            flags |= DeviceFlags.EOS | DeviceFlags.SOS  # Complete packet
        else:
            flags |= DeviceFlags.SOS  # Will be segmented, this is first
        
        # Set device overflow if detected
        if self._device_overflow_detected:
            flags |= DeviceFlags.OVERFLOW
        
        return flags
    
    def set_device_flag(self, flag: DeviceFlags, value: bool = True) -> None:
        """Set or clear a specific device flag"""
        if value:
            self.device_flags |= flag
        else:
            self.device_flags &= ~flag
        self._mark_dirty()
    
    def set_device_overflow(self, overflow: bool = True) -> None:
        """
        Set device overflow flag (bit 15)
        
        According to TECMP v1.7: "The CM has lost data during transmission to the Sink"
        
        Args:
            overflow: Whether device overflow occurred
        """
        self._device_overflow_detected = overflow
        self.set_device_flag(DeviceFlags.OVERFLOW, overflow)
        
        if overflow:
            self.logger.warning(f"Device overflow detected for device 0x{self.device_id:04X}")
    
    def get_device_flags_dict(self) -> Dict[str, bool]:
        """Get all device flags as dictionary"""
        return {
            "end_of_segment": bool(self.device_flags & DeviceFlags.EOS),
            "start_of_segment": bool(self.device_flags & DeviceFlags.SOS),
            "spy_mode": bool(self.device_flags & DeviceFlags.SPY),
            "multi_frame": bool(self.device_flags & DeviceFlags.MULTI_FRAME),
            "device_overflow": bool(self.device_flags & DeviceFlags.OVERFLOW)
        }
    
    # ========================================================================
    # TIMESTAMP MANAGEMENT
    # ========================================================================
    
    def get_timestamp_with_flags(self) -> int:
        """Get complete 64-bit timestamp with flags"""
        timestamp_value = self.timestamp & TIMESTAMP_VALUE_MASK
        
        if self.timestamp_recalc_flag:
            timestamp_value |= (1 << TIMESTAMP_RECALC_BIT)
        
        if self.timestamp_sync_status:
            timestamp_value |= (1 << TIMESTAMP_SYNC_BIT)
        
        return timestamp_value
    
    def set_timestamp_with_flags(self, value: int) -> None:
        """Set timestamp from 64-bit value including flags"""
        self.timestamp = value & TIMESTAMP_VALUE_MASK
        self.timestamp_recalc_flag = bool((value >> TIMESTAMP_RECALC_BIT) & 0x01)
        self.timestamp_sync_status = (value >> TIMESTAMP_SYNC_BIT) & 0x01
        self._mark_dirty()
    
    def set_current_timestamp(self) -> None:
        """Set timestamp to current time"""
        self.timestamp = int(time.time() * 1e9) & TIMESTAMP_VALUE_MASK
        self._mark_dirty()
    
    # ========================================================================
    # PAYLOAD MANAGEMENT - CRITICAL METHODS
    # ========================================================================
    
    def set_payload(self, payload: bytes) -> None:
        """Set payload and update length"""
        self.payload = bytes(payload) if payload is not None else b""
        self.length = len(self.payload)
        self._mark_dirty()
    
    def get_payload(self) -> bytes:
        """Get payload safely"""
        if not hasattr(self, 'payload'):
            self.payload = b""
        return self.payload
    
    def append_payload(self, data: bytes) -> None:
        """Append data to existing payload"""
        if not hasattr(self, 'payload'):
            self.payload = b""
        self.payload += bytes(data)
        self.length = len(self.payload)
        self._mark_dirty()
    
    # ========================================================================
    # SERIALIZATION
    # ========================================================================
    
    def serialize(self) -> bytes:
        """
        Serialize packet to bytes according to TECMP v1.7 format
        
        Returns:
            Complete TECMP packet as bytes
            
        Raises:
            TECMPSerializationError: If serialization fails
        """
        # Use cached version if available and not dirty
        if not self._is_dirty and self._cached_serialized is not None:
            return self._cached_serialized
        
        try:
            # Ensure coherence before serialization
            self._ensure_coherence()
            
            # 1. Global header (10 bytes)
            global_header = struct.pack("!HHBBHH",
                self.device_id,      # 2 bytes
                self.counter,        # 2 bytes
                self.version,        # 1 byte
                self.message_type,   # 1 byte
                self.data_type,      # 2 bytes
                self.reserved        # 2 bytes
            )
            
            # 2. Device flags (2 bytes)
            device_flags_bytes = struct.pack("!H", self.device_flags)
            
            # 3. Payload header (16 bytes)
            timestamp_with_flags = self.get_timestamp_with_flags()
            payload_header = struct.pack("!IQHH",
                self.interface_id,      # 4 bytes
                timestamp_with_flags,   # 8 bytes
                self.length,            # 2 bytes
                self.data_flags         # 2 bytes
            )
            
            # 4. Combine all parts
            packet_data = global_header + device_flags_bytes + payload_header + self.payload
            
            # Cache the result
            self._cached_serialized = packet_data
            self._is_dirty = False
            
            # Verify size
            expected_size = self.size
            if len(packet_data) != expected_size:
                raise TECMPSerializationError(
                    f"Size mismatch: got {len(packet_data)}, expected {expected_size}")
            
            return packet_data
            
        except struct.error as e:
            raise TECMPSerializationError(f"Struct packing error: {e}")
        except Exception as e:
            raise TECMPSerializationError(f"Serialization failed: {e}")
    
    def deserialize(self, data: bytes) -> None:
        """
        Deserialize packet from bytes
        
        Args:
            data: Raw TECMP packet bytes
            
        Raises:
            TECMPParsingError: If parsing fails
        """
        min_size = TECMP_HEADER_SIZE + TECMP_DEVICE_FLAGS_SIZE + TECMP_PAYLOAD_HEADER_SIZE
        if len(data) < min_size:
            raise TECMPParsingError(f"Packet too short: {len(data)} < {min_size}")
        
        try:
            offset = 0
            
            # 1. Parse global header (10 bytes)
            (self.device_id, self.counter, self.version, self.message_type,
             self.data_type, self.reserved) = struct.unpack("!HHBBHH", 
                                                           data[offset:offset+10])
            offset += TECMP_HEADER_SIZE
            
            # 2. Parse device flags (2 bytes)
            self.device_flags = struct.unpack("!H", data[offset:offset+2])[0]
            offset += TECMP_DEVICE_FLAGS_SIZE
            
            # 3. Parse payload header (16 bytes)
            (self.interface_id, timestamp_with_flags,
             self.length, self.data_flags) = struct.unpack("!IQHH",
                                                          data[offset:offset+16])
            offset += TECMP_PAYLOAD_HEADER_SIZE
            
            # 4. Extract timestamp and flags
            self.set_timestamp_with_flags(timestamp_with_flags)
            
            # 5. Extract payload - CRITICAL
            remaining_data = data[offset:]
            if self.length > 0:
                if len(remaining_data) < self.length:
                    self.logger.warning(
                        f"Payload shorter than declared: {len(remaining_data)} < {self.length}")
                    self.payload = remaining_data
                else:
                    self.payload = remaining_data[:self.length]
            else:
                self.payload = b""
            
            # Ensure payload is bytes
            self.payload = bytes(self.payload)
            
            # 6. Update internal state from flags
            self._device_overflow_detected = bool(self.device_flags & DeviceFlags.OVERFLOW)
            
            # Mark as clean
            self._is_dirty = False
            self._cached_serialized = data
            
            self.logger.debug(f"Deserialized TECMP packet: device=0x{self.device_id:04X}, "
                            f"type={self.data_type_name}, payload={len(self.payload)} bytes")
            
        except struct.error as e:
            raise TECMPParsingError(f"Struct unpacking error: {e}")
        except Exception as e:
            raise TECMPParsingError(f"Deserialization failed: {e}")
    
    # ========================================================================
    # VALIDATION
    # ========================================================================
    
    def validate(self) -> bool:
        """
        Validate packet according to TECMP v1.7 specification
        
        Returns:
            True if valid
            
        Raises:
            TECMPValidationError: If validation fails with details
        """
        errors = []
        
        # Ensure payload exists
        if not hasattr(self, 'payload'):
            self.payload = b""
        
        # Version check
        if self.version != TECMP_VERSION:
            errors.append(f"Invalid version: {self.version} (expected {TECMP_VERSION})")
        
        # Device ID validation
        if not validate_device_id(self.device_id):
            errors.append(f"Invalid device ID: 0x{self.device_id:04X}")
        
        # Message type validation
        valid_message_types = [
            MessageType.CONTROL, MessageType.STATUS_DEVICE,
            MessageType.STATUS_BUS, MessageType.LOGGING_STREAM,
            MessageType.STATUS_CONFIG, MessageType.REPLAY_DATA
        ]
        if self.message_type not in valid_message_types:
            errors.append(f"Invalid message type: 0x{self.message_type:02X}")
        
        # Control Message ID validation (Table 26)
        if self.message_type == MessageType.CONTROL:
            if not self._validate_control_message_id():
                errors.append(f"Invalid Control Message ID in payload")
        
        # Reserved field check
        if self.reserved != 0:
            errors.append(f"Reserved field not zero: 0x{self.reserved:04X}")
        
        # Length validation
        if self.length != len(self.payload):
            errors.append(f"Length mismatch: declared={self.length}, actual={len(self.payload)}")
        
        # Timestamp validation for logging stream
        if self.message_type == MessageType.LOGGING_STREAM and self.timestamp == 0:
            errors.append("Logging stream cannot have zero timestamp")
        
        # Payload size check
        if len(self.payload) > MAX_ETHERNET_PAYLOAD:
            errors.append(f"Payload too large: {len(self.payload)} > {MAX_ETHERNET_PAYLOAD}")
        
        # Segmentation validation
        if len(self.payload) <= MAX_UNSEGMENTED_SIZE:
            flags = self.get_device_flags_dict()
            if not (flags["end_of_segment"] and flags["start_of_segment"]):
                errors.append("Single packet must have both EOS and SOS flags")
        
        # Device overflow flag coherence
        if self._device_overflow_detected and not (self.device_flags & DeviceFlags.OVERFLOW):
            errors.append("Device overflow detected but flag not set")
        
        if errors:
            raise TECMPValidationError("Validation failed:\n" + "\n".join(f"- {e}" for e in errors))
        
        return True
    
    def _validate_control_message_id(self) -> bool:
        """
        Validate Control Message ID according to Table 26
        
        Control messages have specific payload format:
        - Device ID (2 bytes)
        - Control Message ID (2 bytes)
        - Optional payload data
        """
        if self.message_type != MessageType.CONTROL:
            return True
        
        # Control message must have at least 4 bytes (Device ID + Control Message ID)
        if len(self.payload) < 4:
            return False
        
        try:
            # Extract Control Message ID from payload
            _, control_msg_id = struct.unpack("!HH", self.payload[:4])
            
            # Valid ranges from Table 26:
            # - 0x02: Logger Ready
            # - 0xE0: CAN Replay fill level
            # - 0xE1: FlexRay POC State
            # - 0x00-0xDF: User configurable
            # - 0xE2-0xFF: Reserved
            
            if control_msg_id == ControlMessageID.LOGGER_READY:
                return True
            elif control_msg_id == ControlMessageID.CAN_REPLAY_FILL_LEVEL:
                return True
            elif control_msg_id == ControlMessageID.FLEXRAY_POC_STATE:
                return True
            elif 0x00 <= control_msg_id <= 0xDF:
                # User configurable range
                return True
            else:
                # Reserved range (0xE2-0xFF except defined values)
                self.logger.warning(f"Control Message ID 0x{control_msg_id:04X} is in reserved range")
                return False
                
        except struct.error:
            return False
    
    def _ensure_coherence(self) -> None:
        """Ensure internal coherence before operations"""
        # Ensure payload exists
        if not hasattr(self, 'payload'):
            self.payload = b""
        
        # Length must match payload
        if self.length != len(self.payload):
            self.length = len(self.payload)
            self._mark_dirty()
        
        # Timestamp cannot be zero for logging
        if self.message_type == MessageType.LOGGING_STREAM and self.timestamp == 0:
            self.set_current_timestamp()
        
        # Fix segmentation flags for single packet
        if len(self.payload) <= MAX_UNSEGMENTED_SIZE:
            if not (self.device_flags & DeviceFlags.EOS and 
                    self.device_flags & DeviceFlags.SOS):
                self.device_flags |= (DeviceFlags.EOS | DeviceFlags.SOS)
                self._mark_dirty()
        
        # Ensure device overflow flag is set if overflow detected
        if self._device_overflow_detected:
            if not (self.device_flags & DeviceFlags.OVERFLOW):
                self.device_flags |= DeviceFlags.OVERFLOW
                self._mark_dirty()
    
    # ========================================================================
    # SEGMENTATION
    # ========================================================================
    
    def needs_segmentation(self) -> bool:
        """Check if packet needs segmentation"""
        return len(self.payload) > MAX_UNSEGMENTED_SIZE
    
    def segment(self) -> List['TECMPPacket']:
        """
        Segment packet if payload > 800 bytes
        
        Returns:
            List of segmented packets
        """
        if not self.needs_segmentation():
            return [self]
        
        segments = []
        segment_size = MAX_UNSEGMENTED_SIZE
        total_segments = (len(self.payload) + segment_size - 1) // segment_size
        segment_id = int(time.time() * 1000) & 0xFFFF
        
        for i in range(total_segments):
            start = i * segment_size
            end = min((i + 1) * segment_size, len(self.payload))
            segment_payload = self.payload[start:end]
            
            # Create segment
            segment = TECMPPacket(
                device_id=self.device_id,
                counter=(self.counter + i) & 0xFFFF,
                version=self.version,
                message_type=self.message_type,
                data_type=self.data_type,
                interface_id=self.interface_id,
                timestamp=self.timestamp + i * 1000,  # Add 1µs per segment
                timestamp_sync_status=self.timestamp_sync_status,
                timestamp_recalc_flag=self.timestamp_recalc_flag,
                data_flags=self.data_flags,
                payload=segment_payload
            )
            
            # CORRECTED: Set appropriate device flags according to TECMP v1.7
            if i == 0:  # First segment
                segment.device_flags = (self.device_flags | DeviceFlags.SOS) & ~DeviceFlags.EOS
            elif i == total_segments - 1:  # Last segment
                segment.device_flags = (self.device_flags | DeviceFlags.EOS) & ~DeviceFlags.SOS
            else:  # Middle segments
                segment.device_flags = self.device_flags & ~(DeviceFlags.EOS | DeviceFlags.SOS)
            
            # Preserve device overflow flag if set
            if self._device_overflow_detected:
                segment.device_flags |= DeviceFlags.OVERFLOW
                segment._device_overflow_detected = True
            
            # Store segment info
            segment._segment_info = SegmentInfo(
                segment_id=segment_id,
                total_segments=total_segments,
                sequence_number=i,
                is_first=(i == 0),
                is_last=(i == total_segments - 1),
                original_length=len(self.payload)
            )
            
            segments.append(segment)
        
        self.logger.info(f"Segmented {len(self.payload)} bytes into {total_segments} segments")
        return segments
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _mark_dirty(self) -> None:
        """Mark packet as modified"""
        self._is_dirty = True
        self._cached_serialized = None
    
    def increment_counter(self) -> None:
        """Increment counter with wrap-around"""
        self.counter = (self.counter + 1) & 0xFFFF
        self._mark_dirty()
    
    def clone(self) -> 'TECMPPacket':
        """Create deep copy of packet"""
        return copy.deepcopy(self)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert packet to dictionary for debugging/export"""
        return {
            # Header
            "device_id": f"0x{self.device_id:04X}",
            "device_type": self.device_type_name,
            "counter": self.counter,
            "version": self.version,
            "message_type": f"0x{self.message_type:02X}",
            "message_type_name": self.message_type_name,
            "data_type": f"0x{self.data_type:04X}",
            "data_type_name": self.data_type_name,
            "reserved": f"0x{self.reserved:04X}",
            
            # Device flags
            "device_flags": f"0x{self.device_flags:04X}",
            "device_flags_dict": self.get_device_flags_dict(),
            "device_overflow_detected": self._device_overflow_detected,
            
            # Payload header
            "interface_id": f"0x{self.interface_id:08X}",
            "timestamp": self.timestamp,
            "timestamp_sync_status": self.timestamp_sync_status,
            "timestamp_recalc_flag": self.timestamp_recalc_flag,
            "length": self.length,
            "data_flags": f"0x{self.data_flags:04X}",
            
            # Payload
            "payload_size": len(self.payload),
            "payload_hex": self.payload.hex() if len(self.payload) <= 64 else 
                          f"{self.payload[:32].hex()}...",
            
            # Metadata
            "is_segmented": self.is_segmented,
            "is_multi_frame": self.is_multi_frame,
            "total_size": self.size
        }
    
    def summary(self) -> str:
        """Generate human-readable summary"""
        flags = self.get_device_flags_dict()
        flags_str = ", ".join(f"{k}={v}" for k, v in flags.items() if v)
        
        lines = [
            f"TECMP Packet - {self.message_type_name}",
            f"Device: {self.device_type_name} (0x{self.device_id:04X})",
            f"Data Type: {self.data_type_name} (0x{self.data_type:04X})",
            f"Counter: {self.counter}, Version: {self.version}",
            f"Interface: 0x{self.interface_id:08X}",
            f"Timestamp: {self.timestamp} ns (sync={self.timestamp_sync_status}, "
            f"recalc={self.timestamp_recalc_flag})",
            f"Device Flags: {flags_str}",
            f"Data Flags: 0x{self.data_flags:04X}",
            f"Payload: {len(self.payload)} bytes",
            f"Total Size: {self.size} bytes"
        ]
        
        if self._device_overflow_detected:
            lines.append("??  Device Overflow Detected")
        
        if self.is_segmented and self._segment_info:
            lines.append(f"Segmentation: {self._segment_info.sequence_number + 1}/"
                        f"{self._segment_info.total_segments}")
        
        return "\n".join(lines)
    
    def __str__(self) -> str:
        """String representation"""
        overflow_marker = " [OVERFLOW]" if self._device_overflow_detected else ""
        return (f"TECMPPacket(device=0x{self.device_id:04X}, type={self.data_type_name}, "
               f"msg={self.message_type_name}, payload={len(self.payload)}b{overflow_marker})")
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (f"TECMPPacket(device_id=0x{self.device_id:04X}, counter={self.counter}, "
               f"version={self.version}, message_type=0x{self.message_type:02X}, "
               f"data_type=0x{self.data_type:04X}, device_flags=0x{self.device_flags:04X}, "
               f"interface_id=0x{self.interface_id:08X}, timestamp={self.timestamp}, "
               f"length={self.length}, payload_size={len(self.payload)}, "
               f"overflow={self._device_overflow_detected})")

# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_logging_packet(device_id: int = 0x0040, 
                         data_type: int = DataType.ETHERNET_II,  # ALIGNED: Use official name
                         interface_id: int = 0x00000000,
                         payload: bytes = b"",
                         device_overflow: bool = False,
                         **kwargs) -> TECMPPacket:
    """
    Create a logging stream packet with proper defaults
    
    Args:
        device_id: Device identifier
        data_type: Type of data being logged
        interface_id: Interface identifier
        payload: Data payload
        device_overflow: Whether device overflow occurred
        **kwargs: Additional packet parameters
        
    Returns:
        Configured TECMPPacket for logging
    """
    defaults = {
        'message_type': MessageType.LOGGING_STREAM,
        'device_flags': DeviceFlags.SPY | DeviceFlags.EOS | DeviceFlags.SOS,
        'timestamp_sync_status': 0,  # Synchronized
    }
    defaults.update(kwargs)
    
    packet = TECMPPacket(
        device_id=device_id,
        data_type=data_type,
        interface_id=interface_id,
        payload=payload,
        **defaults
    )
    
    # Set device overflow if needed
    if device_overflow:
        packet.set_device_overflow(True)
    
    return packet

def create_replay_packet(data_type: int,
                        interface_id: int,
                        payload: bytes,
                        timestamp: int = 0,
                        **kwargs) -> TECMPPacket:
    """
    Create a replay data packet with proper defaults
    
    Args:
        data_type: Type of data to replay
        interface_id: Target interface
        payload: Data to send
        timestamp: When to send (0 = immediately)
        **kwargs: Additional packet parameters
        
    Returns:
        Configured TECMPPacket for replay
    """
    # CORRECTED: Validate that Ethernet replay is not supported by TECMP v1.7
    if data_type == DataType.ETHERNET_II:  # ALIGNED: Use official name
        raise TECMPValidationError(
            "Ethernet replay not supported by TECMP v1.7 specification (Section 2.4.4)")
    
    defaults = {
        'device_id': 0x0000,  # Unused for replay
        'counter': 0x0000,    # Unused for replay
        'message_type': MessageType.REPLAY_DATA,
        'device_flags': 0x0000,
    }
    defaults.update(kwargs)
    
    return TECMPPacket(
        data_type=data_type,
        interface_id=interface_id,
        payload=payload,
        timestamp=timestamp,
        **defaults
    )

def create_control_message(control_message_id: int,
                          device_id: int = 0x0040,
                          payload_data: bytes = b"",
                          **kwargs) -> TECMPPacket:
    """
    Create a control message packet
    
    Args:
        control_message_id: Control message ID from Table 26
        device_id: Sender device ID
        payload_data: Optional additional payload
        **kwargs: Additional packet parameters
        
    Returns:
        Configured TECMPPacket for control message
    """
    # Build control message payload
    control_payload = struct.pack("!HH", device_id, control_message_id)
    control_payload += payload_data
    
    defaults = {
        'message_type': MessageType.CONTROL,
        'data_type': DataType.LOG_MESSAGE,  # Control messages use LOG_MESSAGE type
        'interface_id': SPECIAL_INTERFACE_IDS['CONTROL'],
        'device_flags': DeviceFlags.EOS | DeviceFlags.SOS,
    }
    defaults.update(kwargs)
    
    return TECMPPacket(
        device_id=device_id,
        payload=control_payload,
        **defaults
    )

def reconstruct_from_segments(segments: List[TECMPPacket]) -> Optional[TECMPPacket]:
    """
    Reconstruct original packet from segments
    
    Args:
        segments: List of segment packets
        
    Returns:
        Reconstructed packet or None if invalid
    """
    if not segments:
        return None
    
    # Sort by sequence number
    segments.sort(key=lambda p: p._segment_info.sequence_number 
                  if p._segment_info else 0)
    
    # Verify sequence integrity
    for i, segment in enumerate(segments):
        if not segment._segment_info or segment._segment_info.sequence_number != i:
            return None
    
    # Reconstruct payload
    reconstructed_payload = b''.join(s.payload for s in segments)
    
    # Create reconstructed packet from first segment
    reconstructed = segments[0].clone()
    reconstructed.set_payload(reconstructed_payload)
    reconstructed.device_flags = DeviceFlags.SPY | DeviceFlags.EOS | DeviceFlags.SOS
    reconstructed._segment_info = None
    
    # Preserve device overflow state if any segment had it
    if any(s._device_overflow_detected for s in segments):
        reconstructed.set_device_overflow(True)
    
    return reconstructed

# Export public API
__all__ = [
    'TECMPPacket',
    'TECMPError',
    'TECMPParsingError', 
    'TECMPSerializationError',
    'TECMPValidationError',
    'SegmentInfo',
    'MultiFrameInfo',
    'create_logging_packet',
    'create_replay_packet',
    'create_control_message',
    'reconstruct_from_segments',
]