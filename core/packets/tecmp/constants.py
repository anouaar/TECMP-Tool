#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
constants.py - TECMP v1.7 Protocol Constants
============================================

Central repository for all TECMP v1.7 protocol constants.
Single source of truth to ensure consistency across the implementation.

This module contains all constants defined in the official TECMP User Manual v1.7
(July 2022) by Technica Engineering GmbH.

Organization:
- General TECMP constants (EtherType, version, sizes)
- Message and data type enumerations
- Device flags and data flags by protocol
- Device ID ranges and special IDs
- Physical constraints and limits
- Helper functions for validation and naming

All constants are directly referenced from the official specification tables.
"""

from enum import IntEnum, IntFlag
from typing import Dict, List, Tuple, Union, Optional

# ============================================================================
# GENERAL TECMP CONSTANTS
# ============================================================================

# Official TECMP EtherType (IANA registered) - Page 9
TECMP_ETHERTYPE = 0x99FE

# Current TECMP protocol version - Page 11
TECMP_VERSION = 3

# Structural sizes in bytes - Page 10-13
TECMP_HEADER_SIZE = 10          # Global TECMP header (without device flags)
TECMP_DEVICE_FLAGS_SIZE = 2     # Device flags field
TECMP_PAYLOAD_HEADER_SIZE = 16  # Data header per frame
TECMP_MIN_FRAME_SIZE = 64       # Minimum Ethernet frame
TECMP_MAX_FRAME_SIZE = 1518     # Maximum standard Ethernet frame

# Total TECMP header size
TECMP_TOTAL_HEADER_SIZE = TECMP_HEADER_SIZE + TECMP_DEVICE_FLAGS_SIZE + TECMP_PAYLOAD_HEADER_SIZE

# Segmentation limits - Page 26
MAX_UNSEGMENTED_SIZE = 800      # Segmentation threshold (bytes)
MAX_ETHERNET_PAYLOAD = 1500     # Maximum Ethernet payload
MAX_MULTI_FRAME_SIZE = 1500     # Maximum multi-frame packet size
MIN_SEGMENT_SIZE = 64           # Minimum segment size

# Timing constants
SYNC_TIMEOUT_NS = 375_000_000       # 375ms synchronization timeout - Page 13
STATUS_DEVICE_INTERVAL_S = 1        # Status Device message interval - Page 32
STATUS_BUS_INTERVAL_S = 1           # Status Bus message interval - Page 29
STATUS_CONFIG_INTERVAL_S = 60       # Status Configuration interval - Page 27
ANNOUNCE_TIMEOUT_MS = 250           # PTP announce timeout
PATH_DELAY_REQ_INTERVAL_S = 1       # PTP path delay request interval

# ============================================================================
# MESSAGE TYPES - Table 23, Page 36-37
# ============================================================================

class MessageType(IntEnum):
    """TECMP Message Types according to specification Table 23"""
    CONTROL = 0x00          # Control messages
    STATUS_DEVICE = 0x01    # Device status information
    STATUS_BUS = 0x02       # Bus/IVN status information
    LOGGING_STREAM = 0x03   # Captured IVN data
    STATUS_CONFIG = 0x04    # Configuration status
    REPLAY_DATA = 0x0A      # Data for replay on IVN

# ============================================================================
# DATA TYPES - Table 24, Page 37
# ============================================================================

class DataType(IntEnum):
    """TECMP Data Types according to specification Table 24"""
    LOG_MESSAGE = 0x0001        # Log/debug messages
    CAN = 0x0002                # Controller Area Network
    CAN_FD = 0x0003             # CAN with Flexible Data-rate
    LIN = 0x0004                # Local Interconnect Network
    FLEXRAY = 0x0008            # FlexRay
    UART = 0x0010               # UART/RS-232
    ANALOG = 0x0020             # Analog values
    DIGITAL = 0x0040            # Digital I/O
    ETHERNET = 0x0080           # Ethernet II (deprecated)
    ETHERNET_EXT = 0x0080       # Ethernet II Extended format

# ============================================================================
# DEVICE FLAGS - Section 2.4.1, Page 11
# ============================================================================

class DeviceFlags(IntFlag):
    """Device Flags bit positions - Page 11"""
    EOS = 0x0001                # Bit 0: End of Segment
    SOS = 0x0002                # Bit 1: Start of Segment
    SPY = 0x0004                # Bit 2: Spy mode (passive monitoring)
    MULTI_FRAME = 0x0008        # Bit 3: Multi-frame indicator
    # Bits 4-14: Reserved (must be 0)
    OVERFLOW = 0x8000           # Bit 15: Device overflow occurred

# ============================================================================
# DATA FLAGS BY PROTOCOL
# ============================================================================

class CANDataFlags(IntFlag):
    """CAN Data Flags - Section 2.4.3.1, Page 14-15"""
    ACK = 0x0001                # Bit 0: Acknowledgment received
    RTR = 0x0002                # Bit 1: Remote Transmission Request
    IDE = 0x0004                # Bit 2: Identifier Extension (29-bit)
    ERR = 0x0008                # Bit 3: Error frame
    BIT_STUFF_ERROR = 0x0010    # Bit 4: Bit stuffing error
    CRC_DEL_ERROR = 0x0020      # Bit 5: CRC delimiter error
    ACK_DEL_ERROR = 0x0040      # Bit 6: ACK delimiter error
    EOF_ERROR = 0x0080          # Bit 7: End of frame error
    # Bits 8-11: Reserved (must be 0)
    CRC_ERROR = 0x1000          # Bit 12: CRC error detected
    TX = 0x2000                 # Bit 13: Frame was transmitted
    # Bit 14: Reserved (must be 0)
    OVERFLOW = 0x8000           # Bit 15: Interface overflow

class CANFDDataFlags(IntFlag):
    """CAN-FD Data Flags - Section 2.4.3.2, Page 15-16"""
    ACK = 0x0001                # Bit 0: Acknowledgment received
    ESI = 0x0002                # Bit 1: Error State Indicator
    IDE = 0x0004                # Bit 2: Identifier Extension (29-bit)
    ERR = 0x0008                # Bit 3: Error frame
    BRS = 0x0010                # Bit 4: Bit Rate Switch
    CRC_DEL_ERROR = 0x0020      # Bit 5: CRC delimiter error
    ACK_DEL_ERROR = 0x0040      # Bit 6: ACK delimiter error
    EOF_ERROR = 0x0080          # Bit 7: End of frame error
    # Bits 8-11: Reserved (must be 0)
    CRC_ERROR = 0x1000          # Bit 12: CRC error detected
    TX = 0x2000                 # Bit 13: Frame was transmitted
    # Bit 14: Reserved (must be 0)
    OVERFLOW = 0x8000           # Bit 15: Interface overflow

class LINDataFlags(IntFlag):
    """LIN Data Flags - Section 2.4.3.3, Page 17"""
    COLLISION_ERROR = 0x0001    # Bit 0: Collision detected
    PARITY_ERROR = 0x0002       # Bit 1: Parity error in PID
    NO_SLAVE_RESPONSE = 0x0004  # Bit 2: No slave response
    # Bits 3-7: Reserved (must be 0)
    WUP = 0x0100                # Bit 8: Wakeup signal
    SHORT_WUP = 0x0200          # Bit 9: Short wakeup signal
    SLEEP = 0x0400              # Bit 10: Sleep command
    # Bit 11: Reserved (must be 0)
    CHECKSUM_ERROR = 0x1000     # Bit 12: Checksum error
    TX = 0x2000                 # Bit 13: Frame was transmitted (CORRECTED)
    # Bit 14: Reserved (must be 0)
    OVERFLOW = 0x8000           # Bit 15: Interface overflow

class FlexRayDataFlags(IntFlag):
    """FlexRay Data Flags - Section 2.4.3.4, Page 18"""
    NULL_FRAME = 0x0001         # Bit 0: Null frame indicator
    STARTUP_FRAME = 0x0002      # Bit 1: Startup frame indicator
    SYNC_FRAME = 0x0004         # Bit 2: Sync frame indicator
    WUS = 0x0008                # Bit 3: Wakeup Symbol
    PPI = 0x0010                # Bit 4: Payload Preamble Indicator
    CAS = 0x0020                # Bit 5: Collision Avoidance Symbol
    # Bits 6-11: Reserved (must be 0)
    HEADER_CRC_ERROR = 0x1000   # Bit 12: Header CRC error
    FRAME_CRC_ERROR = 0x2000    # Bit 13: Frame CRC error (ADDED)
    TX = 0x4000                 # Bit 14: Frame was transmitted
    OVERFLOW = 0x8000           # Bit 15: Interface overflow

class UARTDataFlags(IntFlag):
    """UART Data Flags - Section 2.4.3.5, Page 19"""
    PARITY_ERROR = 0x0001       # Bit 0: Parity error
    # Bits 1-3: Data Length (DL) - see UART_DATA_LENGTH
    # Bits 4-12: Reserved (must be 0)
    # Bit 13: Reserved (must be 0) (CORRECTED)
    TX = 0x4000                 # Bit 14: Data was transmitted
    # Bit 15: Reserved (must be 0)

# UART Data Length encoding (bits 1-3)
class UARTDataLength(IntEnum):
    """UART Data Length field values (bits 1-3)"""
    DL_7BIT = 0x0004            # 010: 7-bit data
    DL_8BIT = 0x0006            # 011: 8-bit data
    # Other values: undefined

class AnalogDataFlags(IntFlag):
    """Analog Data Flags - Section 2.4.3.6, Page 19-20"""
    # Bits 0-1: Reserved (must be 0)
    # Bits 2-4: Unit - see ANALOG_UNIT_*
    UNIT_VOLT = 0x0000          # 000: Volt (V)
    UNIT_AMPERE = 0x0004        # 001: Ampere (A)
    UNIT_WATT = 0x0008          # 010: Watt (W)
    UNIT_AH = 0x000C            # 011: Ampere hour (Ah)
    UNIT_CELSIUS = 0x0010       # 100: Degree Celsius (°C)
    # Bits 5-6: Reserved (must be 0)
    # Bits 7-8: Factor - see ANALOG_FACTOR_*
    FACTOR_0_1 = 0x0000         # 00: 0.1
    FACTOR_0_01 = 0x0080        # 01: 0.01
    FACTOR_0_001 = 0x0100       # 10: 0.001
    FACTOR_0_0001 = 0x0180      # 11: 0.0001
    # Bits 9-10: Reserved (must be 0)
    # Bits 11-14: Sample Time - see ANALOG_SAMPLE_*
    SAMPLE_2500MS = 0x0800      # 0001: 2500ms
    SAMPLE_1000MS = 0x1000      # 0010: 1000ms
    SAMPLE_500MS = 0x1800       # 0011: 500ms
    SAMPLE_250MS = 0x2000       # 0100: 250ms
    SAMPLE_100MS = 0x2800       # 0101: 100ms
    SAMPLE_50MS = 0x3000        # 0110: 50ms
    SAMPLE_25MS = 0x3800        # 0111: 25ms
    SAMPLE_10MS = 0x4000        # 1000: 10ms
    SAMPLE_5MS = 0x4800         # 1001: 5ms
    SAMPLE_2_5MS = 0x5000       # 1010: 2.5ms
    SAMPLE_1MS = 0x5800         # 1011: 1ms
    # Bit 15: Reserved (must be 0)

class EthernetDataFlags(IntFlag):
    """Ethernet Data Flags - Section 2.4.3.7, Page 20"""
    # Bits 0-11: Reserved (must be 0)
    CRC_ERROR = 0x1000          # Bit 12: FCS/CRC error
    # Bit 13: Reserved (must be 0)
    TX = 0x4000                 # Bit 14: Frame was transmitted
    OVERFLOW = 0x8000           # Bit 15: Interface overflow

# ============================================================================
# DEVICE ID RANGES - Table 25, Page 37
# ============================================================================

# Device ID ranges by device type
DEVICE_ID_RANGES: Dict[str, Union[range, List[int]]] = {
    "LIN_COMBO": range(0x30, 0x40),        # 0x30-0x3F: LIN Combo devices
    "CAN_COMBO": range(0x40, 0x50),        # 0x40-0x4F: CAN Combo devices
    "HIGH_100": range(0x50, 0x60),         # 0x50-0x5F: 100 High devices
    "ETH_COMBO": range(0x60, 0x70),        # 0x60-0x6F: Ethernet Combo devices
    "HIGH_1000": range(0x70, 0x80),        # 0x70-0x7F: 1000 High devices
    "STANDARD": [0x0080, 0x0091],          # Standard device IDs
    # Note: 0x00-0x2F reserved, 0x92-0xFF reserved for future use
}

# Device IP address template
DEVICE_IP_TEMPLATE = "10.104.3.{}"  # IP = 10.104.3.{device_id}

# ============================================================================
# CONTROL MESSAGE IDS - Table 26, Page 38
# ============================================================================

class ControlMessageID(IntEnum):
    """Control Message IDs"""
    LOGGER_READY = 0x02                 # Logger ready notification
    CAN_REPLAY_FILL_LEVEL = 0xE0       # CAN replay buffer status
    FLEXRAY_POC_STATE = 0xE1            # FlexRay POC state change
    # 0xE2-0xFF: Reserved for future use
    
    # User configurable IDs (0x00-0xDF) for:
    # - Linkup detected
    # - Linkdown detected
    # - Time synchronization acquired
    # - Time synchronization lost

# Valid control message ID ranges
CONTROL_MESSAGE_ID_RANGES = {
    "USER": range(0x00, 0xE0),          # User configurable
    "SYSTEM": range(0xE0, 0x100),       # System reserved
}

# ============================================================================
# DEVICE TYPES - Table 27, Page 38
# ============================================================================

class DeviceType(IntEnum):
    """Device Types"""
    CM_LIN_COMBO = 0x02
    CM_CAN_COMBO = 0x04
    CM_100_HIGH = 0x06
    CM_ETH_COMBO = 0x08
    CM_1000_HIGH = 0x0A
    OTHER = 0xFF

# ============================================================================
# SPECIAL INTERFACE IDS - Table 28, Page 38
# ============================================================================

# Special Interface IDs for Status and Control messages
SPECIAL_INTERFACE_IDS: Dict[str, int] = {
    "STATUS_CONFIG": 0x000FFF00,        # Status Configuration messages
    "STATUS_BUS": 0x000FFF01,           # Status Bus/IVN messages
    "STATUS_DEVICE": 0x000FFF02,        # Status Device messages
    "CONTROL": 0x000FFF03,              # Control messages
}

# Reverse mapping for lookup
INTERFACE_ID_NAMES: Dict[int, str] = {v: k for k, v in SPECIAL_INTERFACE_IDS.items()}

# ============================================================================
# PAYLOAD SIZE LIMITS BY DATA TYPE
# ============================================================================

MAX_PAYLOAD_SIZES: Dict[int, int] = {
    DataType.LOG_MESSAGE: 1024,         # Log messages
    DataType.CAN: 16,                   # CAN: 8 data + overhead
    DataType.CAN_FD: 72,                # CAN-FD: 64 data + overhead
    DataType.LIN: 11,                   # LIN: 8 data + overhead
    DataType.FLEXRAY: 263,              # FlexRay: 254 data + overhead
    DataType.UART: 1000,                # UART: max 1000 symbols per frame
    DataType.ANALOG: 1400,              # Analog: max 700 samples
    DataType.DIGITAL: 1400,             # Digital I/O
    DataType.ETHERNET: 1518,            # Full Ethernet frame
    DataType.ETHERNET_EXT: 1518,        # Full Ethernet frame
}

# ============================================================================
# CAN/CAN-FD SPECIFIC CONSTANTS
# ============================================================================

# CAN identifier limits
CAN_ID_11BIT_MAX = 0x7FF                # 11-bit identifier maximum (2047)
CAN_ID_29BIT_MAX = 0x1FFFFFFF            # 29-bit identifier maximum

# CAN-FD DLC to data length mapping
CANFD_DLC_TO_LENGTH: Dict[int, int] = {
    0: 0,   1: 1,   2: 2,   3: 3,   4: 4,   5: 5,   6: 6,   7: 7,   8: 8,
    9: 12,  10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64
}

# Reverse mapping for length to DLC
CANFD_LENGTH_TO_DLC: Dict[int, int] = {v: k for k, v in CANFD_DLC_TO_LENGTH.items()}

# ============================================================================
# FLEXRAY SPECIFIC CONSTANTS
# ============================================================================

FLEXRAY_CYCLE_MAX = 63                  # Maximum cycle number (6 bits)
FLEXRAY_FRAME_ID_MAX = 2047             # Maximum frame ID (11 bits)
FLEXRAY_PAYLOAD_MAX = 254               # Maximum payload length in bytes
FLEXRAY_STATIC_SLOTS_MAX = 1023         # Maximum static slots
FLEXRAY_HEADER_CRC_BITS = 11            # Header CRC is 11 bits
FLEXRAY_FRAME_CRC_BITS = 24             # Frame CRC is 24 bits

# ============================================================================
# LIN SPECIFIC CONSTANTS
# ============================================================================

LIN_ID_MAX = 63                         # Maximum LIN ID (6 bits)
LIN_VALID_LENGTHS = [1, 2, 4, 8]        # Valid LIN data lengths
LIN_BREAK_BITS = 13                     # Break field length
LIN_SYNC_BYTE = 0x55                    # Sync byte value
LIN_CLASSIC_CHECKSUM_ID_RANGE = range(0x3C, 0x3E)  # IDs using classic checksum

# ============================================================================
# TIMESTAMP CONSTANTS
# ============================================================================

# Timestamp field bit layout (64 bits total)
TIMESTAMP_VALUE_MASK = 0x3FFFFFFFFFFFFFFF  # Bits 0-61: timestamp value (ns)
TIMESTAMP_RECALC_BIT = 62                  # Bit 62: recalculation flag
TIMESTAMP_SYNC_BIT = 63                    # Bit 63: synchronization status

# Timestamp synchronization states
TIMESTAMP_SYNC_OK = 0                      # Synchronized
TIMESTAMP_SYNC_LOST = 1                    # Lost synchronization

# ============================================================================
# PHYSICAL LIMITS AND CONSTRAINTS
# ============================================================================

PHYSICAL_LIMITS: Dict[str, Tuple[float, float]] = {
    # Temperature ranges
    'temperature_celsius': (-40.0, 125.0),      # Automotive temperature range
    'silicon_temperature': (-40.0, 150.0),      # Junction temperature range
    
    # Voltage ranges
    'voltage_12v': (9.0, 16.0),                 # 12V system operational range
    'voltage_24v': (18.0, 32.0),                # 24V system operational range
    'voltage_critical_low': (6.0, 6.0),         # Critical low voltage
    'voltage_critical_high': (36.0, 36.0),      # Critical high voltage
    
    # Buffer and memory
    'buffer_percentage': (0, 100),              # Buffer fill percentage
    'buffer_size_gb': (0, 32),                  # Buffer size in Gigabits
    
    # Bus speeds (bps)
    'can_bitrate': (10_000, 5_000_000),        # 10kbps to 5Mbps
    'canfd_data_bitrate': (10_000, 8_000_000), # 10kbps to 8Mbps
    'flexray_bitrate': (2_500_000, 10_000_000),# 2.5Mbps to 10Mbps
    'lin_bitrate': (1_200, 20_000),            # 1.2kbps to 20kbps
    'uart_bitrate': (300, 921_600),            # 300bps to 921.6kbps
}

# Timing constraints
TIMING_CONSTRAINTS: Dict[str, int] = {
    'min_can_frame_interval_ns': 50_000,       # 50µs minimum CAN frame interval
    'min_lin_frame_interval_ms': 10,           # 10ms minimum LIN frame interval
    'flexray_cycle_duration_us': 5_000,        # 5ms typical FlexRay cycle
    'flexray_macrotick_ns': 1_000,             # 1µs FlexRay macrotick
    'ethernet_ifg_ns': 960,                    # 96 bit times at 100Mbps
}

# ============================================================================
# VENDOR SPECIFIC
# ============================================================================

VENDOR_ID_TECHNICA = 0x0C               # Technica Engineering vendor ID
VENDOR_NAME = "Technica Engineering GmbH"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_device_type_name(device_id: int) -> str:
    """
    Get human-readable device type name from device ID
    
    Args:
        device_id: Device ID to lookup
        
    Returns:
        Device type name string
    """
    for name, id_range in DEVICE_ID_RANGES.items():
        if isinstance(id_range, range) and device_id in id_range:
            return name.replace("_", " ").title()
        elif isinstance(id_range, list) and device_id in id_range:
            return "Standard Device"
    return f"Unknown (0x{device_id:04X})"

def get_data_type_name(data_type: int) -> str:
    """
    Get human-readable data type name
    
    Args:
        data_type: Data type value
        
    Returns:
        Data type name string
    """
    names = {
        DataType.LOG_MESSAGE: "Log Message",
        DataType.CAN: "CAN",
        DataType.CAN_FD: "CAN-FD",
        DataType.LIN: "LIN",
        DataType.FLEXRAY: "FlexRay",
        DataType.UART: "UART/RS-232",
        DataType.ANALOG: "Analog",
        DataType.DIGITAL: "Digital I/O",
        DataType.ETHERNET: "Ethernet II",
        DataType.ETHERNET_EXT: "Ethernet II Extended",
    }
    return names.get(data_type, f"Unknown (0x{data_type:04X})")

def get_message_type_name(message_type: int) -> str:
    """
    Get human-readable message type name
    
    Args:
        message_type: Message type value
        
    Returns:
        Message type name string
    """
    names = {
        MessageType.CONTROL: "Control Message",
        MessageType.STATUS_DEVICE: "Status Device",
        MessageType.STATUS_BUS: "Status Bus/IVN",
        MessageType.LOGGING_STREAM: "Logging Stream",
        MessageType.STATUS_CONFIG: "Status Configuration",
        MessageType.REPLAY_DATA: "Replay Data",
    }
    return names.get(message_type, f"Unknown (0x{message_type:02X})")

def validate_device_id(device_id: int) -> bool:
    """
    Check if device ID is in valid TECMP range
    
    Args:
        device_id: Device ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Check standard ranges
    for id_range in DEVICE_ID_RANGES.values():
        if isinstance(id_range, range) and device_id in id_range:
            return True
        elif isinstance(id_range, list) and device_id in id_range:
            return True
    
    # Check reserved ranges (invalid)
    if 0x00 <= device_id <= 0x2F:  # Reserved low
        return False
    if 0x92 <= device_id <= 0xFF:  # Reserved high
        return False
        
    return False

def validate_control_message_id(msg_id: int) -> bool:
    """
    Validate control message ID
    
    Args:
        msg_id: Control message ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Check known system IDs
    if msg_id in [ControlMessageID.LOGGER_READY, 
                  ControlMessageID.CAN_REPLAY_FILL_LEVEL,
                  ControlMessageID.FLEXRAY_POC_STATE]:
        return True
        
    # Check valid ranges
    for range_type, id_range in CONTROL_MESSAGE_ID_RANGES.items():
        if msg_id in id_range:
            return True
            
    return False

def get_interface_id_name(interface_id: int) -> str:
    """
    Get name for special interface ID
    
    Args:
        interface_id: Interface ID to lookup
        
    Returns:
        Interface name or hex string if not special
    """
    return INTERFACE_ID_NAMES.get(interface_id, f"0x{interface_id:08X}")

def is_special_interface_id(interface_id: int) -> bool:
    """
    Check if interface ID is a special TECMP ID
    
    Args:
        interface_id: Interface ID to check
        
    Returns:
        True if special ID, False otherwise
    """
    return interface_id in INTERFACE_ID_NAMES

def get_analog_unit(flags: int) -> str:
    """
    Extract analog unit from data flags
    
    Args:
        flags: Analog data flags
        
    Returns:
        Unit string (V, A, W, Ah, C)
    """
    unit_bits = (flags >> 2) & 0x07
    units = ['V', 'A', 'W', 'Ah', 'C', '?', '?', '?']
    return units[unit_bits]

def get_analog_factor(flags: int) -> float:
    """
    Extract analog scaling factor from data flags
    
    Args:
        flags: Analog data flags
        
    Returns:
        Scaling factor (0.1, 0.01, 0.001, 0.0001)
    """
    factor_bits = (flags >> 7) & 0x03
    factors = [0.1, 0.01, 0.001, 0.0001]
    return factors[factor_bits]

def get_analog_sample_time_ms(flags: int) -> Optional[float]:
    """
    Extract analog sample time from data flags
    
    Args:
        flags: Analog data flags
        
    Returns:
        Sample time in milliseconds or None if reserved
    """
    sample_bits = (flags >> 11) & 0x0F
    times = {
        0: None,      # Reserved
        1: 2500.0,    2: 1000.0,   3: 500.0,    4: 250.0,
        5: 100.0,     6: 50.0,     7: 25.0,     8: 10.0,
        9: 5.0,       10: 2.5,     11: 1.0,
        # 12-15: Undefined
    }
    return times.get(sample_bits)

def get_uart_data_length(flags: int) -> Optional[int]:
    """
    Extract UART data length from data flags
    
    Args:
        flags: UART data flags
        
    Returns:
        Data length (7 or 8) or None if invalid
    """
    dl_bits = (flags >> 1) & 0x07
    if dl_bits == 0b010:  # 7-bit
        return 7
    elif dl_bits == 0b011:  # 8-bit
        return 8
    return None

def calculate_lin_checksum(lin_id: int, data: bytes, enhanced: bool = True) -> int:
    """
    Calculate LIN checksum according to specification
    
    Args:
        lin_id: LIN identifier (0-63)
        data: LIN data bytes
        enhanced: Use enhanced checksum (LIN 2.x) if True
        
    Returns:
        Calculated checksum value (0-255)
    """
    # Classic checksum for diagnostic frames
    if not enhanced or lin_id in LIN_CLASSIC_CHECKSUM_ID_RANGE:
        checksum = 0
    else:
        # Enhanced checksum includes protected ID
        checksum = lin_id | ((~(lin_id ^ (lin_id >> 1) ^ (lin_id >> 2) ^ (lin_id >> 4)) & 0x03) << 6)
    
    # Sum all data bytes
    for byte in data:
        checksum += byte
        if checksum > 255:
            checksum = (checksum & 0xFF) + 1
            
    # Invert for final checksum
    return (~checksum) & 0xFF

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_can_id(can_id: int, extended: bool) -> bool:
    """Validate CAN identifier"""
    if extended:
        return 0 <= can_id <= CAN_ID_29BIT_MAX
    else:
        return 0 <= can_id <= CAN_ID_11BIT_MAX

def validate_canfd_dlc(dlc: int) -> bool:
    """Validate CAN-FD DLC value"""
    return dlc in CANFD_DLC_TO_LENGTH

def validate_flexray_cycle(cycle: int) -> bool:
    """Validate FlexRay cycle number"""
    return 0 <= cycle <= FLEXRAY_CYCLE_MAX

def validate_flexray_frame_id(frame_id: int) -> bool:
    """Validate FlexRay frame ID"""
    return 0 <= frame_id <= FLEXRAY_FRAME_ID_MAX

def validate_lin_id(lin_id: int) -> bool:
    """Validate LIN identifier"""
    return 0 <= lin_id <= LIN_ID_MAX

def validate_lin_data_length(length: int) -> bool:
    """Validate LIN data length"""
    return length in LIN_VALID_LENGTHS

# ============================================================================
# EXPORT PUBLIC API
# ============================================================================

__all__ = [
    # General constants
    'TECMP_ETHERTYPE', 'TECMP_VERSION', 
    'TECMP_HEADER_SIZE', 'TECMP_DEVICE_FLAGS_SIZE', 'TECMP_PAYLOAD_HEADER_SIZE',
    'TECMP_TOTAL_HEADER_SIZE', 'TECMP_MIN_FRAME_SIZE', 'TECMP_MAX_FRAME_SIZE',
    'MAX_UNSEGMENTED_SIZE', 'MAX_ETHERNET_PAYLOAD',
    'SYNC_TIMEOUT_NS', 'STATUS_DEVICE_INTERVAL_S', 'STATUS_BUS_INTERVAL_S', 'STATUS_CONFIG_INTERVAL_S',
    
    # Enumerations
    'MessageType', 'DataType', 'DeviceFlags',
    'CANDataFlags', 'CANFDDataFlags', 'LINDataFlags',
    'FlexRayDataFlags', 'UARTDataFlags', 'AnalogDataFlags', 'EthernetDataFlags',
    'ControlMessageID', 'DeviceType',
    'UARTDataLength',
    
    # Mappings and ranges
    'DEVICE_ID_RANGES', 'SPECIAL_INTERFACE_IDS', 'INTERFACE_ID_NAMES',
    'MAX_PAYLOAD_SIZES', 'CANFD_DLC_TO_LENGTH', 'CANFD_LENGTH_TO_DLC',
    'CONTROL_MESSAGE_ID_RANGES', 'PHYSICAL_LIMITS', 'TIMING_CONSTRAINTS',
    
    # Protocol-specific constants
    'CAN_ID_11BIT_MAX', 'CAN_ID_29BIT_MAX',
    'FLEXRAY_CYCLE_MAX', 'FLEXRAY_FRAME_ID_MAX', 'FLEXRAY_PAYLOAD_MAX',
    'LIN_ID_MAX', 'LIN_VALID_LENGTHS', 'LIN_CLASSIC_CHECKSUM_ID_RANGE',
    'TIMESTAMP_VALUE_MASK', 'TIMESTAMP_RECALC_BIT', 'TIMESTAMP_SYNC_BIT',
    
    # Helper functions
    'get_device_type_name', 'get_data_type_name', 'get_message_type_name',
    'validate_device_id', 'validate_control_message_id',
    'get_interface_id_name', 'is_special_interface_id',
    'get_analog_unit', 'get_analog_factor', 'get_analog_sample_time_ms',
    'get_uart_data_length', 'calculate_lin_checksum',
    
    # Validation functions
    'validate_can_id', 'validate_canfd_dlc',
    'validate_flexray_cycle', 'validate_flexray_frame_id',
    'validate_lin_id', 'validate_lin_data_length',
    
   
]