#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tecmp_data.py - TECMP Data Payload Management
=============================================

Handles protocol-specific data structures for TECMP packets.
Provides clean abstraction for different data types (CAN, Ethernet, etc.)
while maintaining perfect integration with tecmp_packet.py.

This module focuses on:
- Protocol-specific payload construction
- Data flags management per protocol
- Payload validation according to TECMP v1.7
- Clean interface with TECMPPacket

Reference: TECMP User Manual v1.7 - July 2022

CORRECTED: LIN validation now conforms to TECMP v1.7 Sections 2.4.3.3 and 2.4.4.3
- Allows length=0 for WUP/SLEEP/Config removal (special cases)
- Maintains strict validation [1,2,4,8] for normal frames
"""

import struct
import logging
from typing import Optional, Dict, Any, Union, Tuple, List, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Import all constants from centralized location
from .constants import (
    DataType,
    CANDataFlags, CANFDDataFlags, LINDataFlags,
    FlexRayDataFlags, UARTDataFlags, AnalogDataFlags, EthernetDataFlags,
    CAN_ID_11BIT_MAX, CAN_ID_29BIT_MAX,
    CANFD_DLC_TO_LENGTH,
    FLEXRAY_CYCLE_MAX, FLEXRAY_FRAME_ID_MAX,
    LIN_ID_MAX, LIN_VALID_LENGTHS,
    MAX_PAYLOAD_SIZES,
    get_data_type_name
)

# ============================================================================
# EXCEPTIONS
# ============================================================================

class TECMPDataError(Exception):
    """Base exception for TECMP data errors"""
    pass

class TECMPDataValidationError(TECMPDataError):
    """Data validation error"""
    pass

# ============================================================================
# BASE PROTOCOL HANDLER
# ============================================================================

class ProtocolHandler(ABC):
    """
    Abstract base class for protocol-specific handlers.
    Ensures consistent interface across all protocols.
    """
    
    def __init__(self, data_type: DataType):
        self.data_type = data_type
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    @abstractmethod
    def build_payload(self, **kwargs) -> bytes:
        """Build protocol-specific payload"""
        pass
    
    @abstractmethod
    def parse_payload(self, payload: bytes) -> Dict[str, Any]:
        """Parse protocol-specific payload"""
        pass
    
    @abstractmethod
    def build_data_flags(self, **kwargs) -> int:
        """Build protocol-specific data flags"""
        pass
    
    @abstractmethod
    def validate(self, payload: bytes, data_flags: int) -> bool:
        """Validate payload and flags"""
        pass
    
    def get_max_payload_size(self) -> int:
        """Get maximum payload size for this protocol"""
        return MAX_PAYLOAD_SIZES.get(self.data_type, 1500)

# ============================================================================
# CAN/CAN-FD HANDLER
# ============================================================================

class CANHandler(ProtocolHandler):
    """Handler for CAN and CAN-FD protocols"""
    
    def __init__(self, is_fd: bool = False):
        super().__init__(DataType.CAN_FD if is_fd else DataType.CAN)
        self.is_fd = is_fd
        self.flags_class = CANFDDataFlags if is_fd else CANDataFlags
    
    def build_payload(self, can_id: int, data: bytes, dlc: Optional[int] = None,
                     ide: Optional[bool] = None, rtr: bool = False,
                     crc: Optional[int] = None) -> bytes:
        """
        Build CAN/CAN-FD payload structure
        
        Structure:
        - CAN ID (4 bytes) with IDE bit
        - DLC (1 byte)
        - Data (0-8 bytes for CAN, 0-64 for CAN-FD)
        - CRC (2 bytes for CAN, 3 bytes for CAN-FD) - optional
        """
        # Auto-calculate DLC if not provided
        if dlc is None:
            dlc = len(data)
        
        # Auto-detect IDE if not specified
        if ide is None:
            ide = can_id > CAN_ID_11BIT_MAX
        
        # Validate CAN ID
        max_id = CAN_ID_29BIT_MAX if ide else CAN_ID_11BIT_MAX
        if can_id > max_id:
            raise TECMPDataValidationError(
                f"CAN ID 0x{can_id:X} exceeds maximum 0x{max_id:X}")
        
        # Build CAN ID field with flags
        can_id_field = can_id & 0x1FFFFFFF
        if ide:
            can_id_field |= 0x80000000  # IDE bit (31)
        if rtr:
            can_id_field |= 0x40000000  # RTR bit (30)
        
        # Validate and adjust DLC
        if self.is_fd:
            # Map data length to DLC for CAN-FD
            if len(data) > 8:
                for dlc_value, length in CANFD_DLC_TO_LENGTH.items():
                    if len(data) <= length:
                        dlc = dlc_value
                        break
        else:
            # Standard CAN: max 8 bytes
            if len(data) > 8:
                raise TECMPDataValidationError(
                    f"CAN data length {len(data)} exceeds 8 bytes")
            dlc = len(data)
        
        # Build payload
        payload = struct.pack(">I", can_id_field)  # CAN ID (4 bytes)
        payload += struct.pack("B", dlc)           # DLC (1 byte)
        payload += data                            # Data bytes
        
        # Add CRC if provided
        if crc is not None:
            if self.is_fd:
                # CAN-FD: 17-bit or 21-bit CRC in 3 bytes
                payload += struct.pack(">I", crc)[1:]  # Last 3 bytes
            else:
                # CAN: 15-bit CRC in 2 bytes
                payload += struct.pack(">H", crc & 0x7FFF)
        
        return payload
    
    def parse_payload(self, payload: bytes) -> Dict[str, Any]:
        """Parse CAN/CAN-FD payload"""
        if len(payload) < 5:
            raise TECMPDataValidationError("CAN payload too short")
        
        # Parse CAN ID field
        can_id_field = struct.unpack(">I", payload[0:4])[0]
        ide = bool(can_id_field & 0x80000000)
        rtr = bool(can_id_field & 0x40000000)
        can_id = can_id_field & 0x1FFFFFFF
        
        # Parse DLC
        dlc = payload[4]
        
        # Determine actual data length
        if self.is_fd and dlc > 8:
            data_length = CANFD_DLC_TO_LENGTH.get(dlc, dlc)
        else:
            data_length = dlc
        
        # Parse data
        data_start = 5
        data_end = data_start + data_length
        if len(payload) < data_end:
            data = payload[data_start:]
        else:
            data = payload[data_start:data_end]
        
        # Parse CRC if present
        crc = None
        if self.is_fd and len(payload) >= data_end + 3:
            crc_bytes = b'\x00' + payload[data_end:data_end + 3]
            crc = struct.unpack(">I", crc_bytes)[0]
        elif not self.is_fd and len(payload) >= data_end + 2:
            crc = struct.unpack(">H", payload[data_end:data_end + 2])[0]
        
        return {
            'can_id': can_id,
            'ide': ide,
            'rtr': rtr,
            'dlc': dlc,
            'data': data,
            'crc': crc
        }
    
    def build_data_flags(self, ack: bool = True, rtr: bool = False,
                        ide: bool = False, err: bool = False,
                        tx: bool = False, overflow: bool = False,
                        esi: bool = False, brs: bool = False,
                        **error_flags) -> int:
        """Build CAN/CAN-FD data flags"""
        flags = 0
        
        # Common flags
        if ack:
            flags |= self.flags_class.ACK
        if rtr and not self.is_fd:  # RTR only for standard CAN
            flags |= self.flags_class.RTR
        if ide:
            flags |= self.flags_class.IDE
        if err:
            flags |= self.flags_class.ERR
        if tx:
            flags |= self.flags_class.TX
        if overflow:
            flags |= self.flags_class.OVERFLOW
        
        # CAN-FD specific flags
        if self.is_fd:
            if esi:
                flags |= CANFDDataFlags.ESI
            if brs:
                flags |= CANFDDataFlags.BRS
        
        # Error flags
        if error_flags.get('bit_stuff_error'):
            flags |= self.flags_class.BIT_STUFF_ERROR
        if error_flags.get('crc_del_error'):
            flags |= self.flags_class.CRC_DEL_ERROR
        if error_flags.get('ack_del_error'):
            flags |= self.flags_class.ACK_DEL_ERROR
        if error_flags.get('eof_error'):
            flags |= self.flags_class.EOF_ERROR
        if error_flags.get('crc_error'):
            flags |= self.flags_class.CRC_ERROR
        
        return flags
    
    def validate(self, payload: bytes, data_flags: int) -> bool:
        """Validate CAN/CAN-FD payload and flags"""
        try:
            parsed = self.parse_payload(payload)
            
            # Validate RTR frame has no data
            if data_flags & CANDataFlags.RTR and len(parsed['data']) > 0:
                raise TECMPDataValidationError("RTR frame cannot have data")
            
            # Validate TX and CRC error are exclusive
            if (data_flags & CANDataFlags.TX and 
                data_flags & CANDataFlags.CRC_ERROR):
                raise TECMPDataValidationError("TX frame cannot have CRC error")
            
            return True
            
        except Exception as e:
            self.logger.error(f"CAN validation failed: {e}")
            return False

# ============================================================================
# ETHERNET HANDLER
# ============================================================================

class EthernetHandler(ProtocolHandler):
    """Handler for Ethernet protocol"""
    
    def __init__(self):
        super().__init__(DataType.ETHERNET_II)
    
    def build_payload(self, dst_mac: bytes, src_mac: bytes,
                     ether_type: int, data: bytes,
                     vlan_tag: Optional[int] = None,  # Keep for backward compatibility
                     outer_vlan: Optional[int] = None,  # CORRECTED: Added
                     inner_vlan: Optional[int] = None,  # CORRECTED: Added
                     fcs: Optional[int] = None) -> bytes:
        """
        Build Ethernet frame payload
        
        Note: For TECMP Ethernet, the payload is the complete Ethernet frame
        including all headers and FCS
        """
        # Ethernet header
        payload = dst_mac[:6].ljust(6, b'\x00')  # Destination MAC
        payload += src_mac[:6].ljust(6, b'\x00')  # Source MAC
        
        # CORRECTED: Support both old parameter and new Q-in-Q parameters
        # Support old parameter for backward compatibility
        if vlan_tag is not None and outer_vlan is None:
            outer_vlan = vlan_tag
        
        # Outer VLAN tag (802.1Q)
        if outer_vlan is not None:
            payload += struct.pack(">HH", 0x8100, outer_vlan & 0xFFFF)
        
        # Inner VLAN tag (Q-in-Q)
        if inner_vlan is not None:
            payload += struct.pack(">HH", 0x8100, inner_vlan & 0xFFFF)
        
        # EtherType
        payload += struct.pack(">H", ether_type)
        
        # Data
        payload += data
        
        # Padding to minimum Ethernet frame size
        min_data_size = 46
        if outer_vlan is not None:
            min_data_size -= 4
        if inner_vlan is not None:
            min_data_size -= 4
        
        if len(data) < min_data_size:
            payload += b'\x00' * (min_data_size - len(data))
        
        # CORRECTED: Calculate FCS automatically if not provided
        if fcs is not None:
            payload += struct.pack(">I", fcs)
        else:
            # Calculate FCS using CRC32
            calculated_fcs = self._calculate_ethernet_fcs(payload)
            payload += struct.pack(">I", calculated_fcs)
        
        return payload
    
    def _calculate_ethernet_fcs(self, data: bytes) -> int:
        """Calculate Ethernet FCS using CRC32"""
        import zlib
        # Ethernet uses CRC32 with specific polynomial
        return zlib.crc32(data) & 0xFFFFFFFF
    
    def parse_payload(self, payload: bytes) -> Dict[str, Any]:
        """Parse Ethernet frame"""
        if len(payload) < 14:
            raise TECMPDataValidationError("Ethernet frame too short")
        
        result = {
            'dst_mac': payload[0:6],
            'src_mac': payload[6:12],
            'ether_type': struct.unpack(">H", payload[12:14])[0],
            'outer_vlan': None,
            'inner_vlan': None,
            'vlan_tag': None,  # Keep for compatibility
            'data': None,
            'fcs': None
        }
        
        offset = 14
        
        # Check for VLAN tags
        if result['ether_type'] == 0x8100 and len(payload) >= 18:
            result['outer_vlan'] = struct.unpack(">H", payload[14:16])[0]
            result['vlan_tag'] = result['outer_vlan']  # Compatibility
            next_ether_type = struct.unpack(">H", payload[16:18])[0]
            offset = 18
            
            # Check for inner VLAN (Q-in-Q)
            if next_ether_type == 0x8100 and len(payload) >= 22:
                result['inner_vlan'] = struct.unpack(">H", payload[18:20])[0]
                result['ether_type'] = struct.unpack(">H", payload[20:22])[0]
                offset = 22
            else:
                result['ether_type'] = next_ether_type
        
        # Extract data (everything except potential FCS)
        if len(payload) >= offset + 4:
            result['data'] = payload[offset:-4]
            result['fcs'] = struct.unpack(">I", payload[-4:])[0]
        else:
            result['data'] = payload[offset:]
        
        return result
    
    def build_data_flags(self, tx: bool = False, crc_error: bool = False,
                        overflow: bool = False) -> int:
        """Build Ethernet data flags"""
        flags = 0
        
        if tx:
            flags |= EthernetDataFlags.TX
        if crc_error:
            flags |= EthernetDataFlags.CRC_ERROR
        if overflow:
            flags |= EthernetDataFlags.OVERFLOW
        
        return flags
    
    def validate(self, payload: bytes, data_flags: int) -> bool:
        """Validate Ethernet payload and flags"""
        try:
            # CORRECTED: Validate reserved bits (12-0 must be 0)
            reserved_mask = 0x1FFF  # Bits 12-0
            if data_flags & reserved_mask:
                self.logger.error(f"Ethernet flags bits 12-0 must be 0, got: 0x{data_flags & reserved_mask:04X}")
                return False
            
            parsed = self.parse_payload(payload)
            
            # Check minimum frame size
            if len(payload) < 64:
                self.logger.warning(f"Ethernet frame smaller than minimum: {len(payload)} bytes")
            
            # For TECMP, various sizes are valid depending on content
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ethernet validation failed: {e}")
            return False

# ============================================================================
# LIN HANDLER - CORRECTED FOR TECMP v1.7 COMPLIANCE
# ============================================================================

class LINHandler(ProtocolHandler):
    """
    Handler for LIN protocol - CORRECTED for TECMP v1.7 compliance
    
    Now properly supports:
    - length=0 for WUP (Wake-up) signals
    - length=0 for SLEEP (Go-to-sleep) commands  
    - length=0 for config removal (Tx mode)
    - Strict validation [1,2,4,8] for normal data frames
    
    Reference: TECMP v1.7 Sections 2.4.3.3 and 2.4.4.3
    """
    
    def __init__(self):
        super().__init__(DataType.LIN)
    
    def build_payload(self, lin_id: int, data: bytes,
                     checksum: Optional[int] = None,
                     wup: bool = False, sleep: bool = False,
                     remove_config: bool = False) -> bytes:
        """
        Build LIN payload - CORRECTED for TECMP v1.7 compliance
        
        Args:
            lin_id: LIN frame identifier (0-63)
            data: Payload data bytes
            checksum: Optional checksum (auto-calculated if None)
            wup: True for Wake-up signal (allows length=0)
            sleep: True for Go-to-sleep command (allows length=0)
            remove_config: True for config removal (allows length=0)
        
        Returns:
            LIN payload bytes
            
        Raises:
            TECMPDataValidationError: If validation fails
        """
        # Validate LIN ID
        if lin_id > LIN_ID_MAX:
            raise TECMPDataValidationError(f"LIN ID {lin_id} exceeds maximum {LIN_ID_MAX}")
        
        # CORRECTED: Validate data length according to TECMP v1.7
        data_length = len(data)
        is_special_case = wup or sleep or remove_config
        
        if is_special_case:
            # Special cases: WUP, SLEEP, config removal allow length=0
            if data_length != 0:
                raise TECMPDataValidationError(
                    f"Special LIN frame (WUP/SLEEP/config) must have length 0, got {data_length}")
        else:
            # Normal frames: only [1,2,4,8] allowed
            if data_length not in LIN_VALID_LENGTHS:
                raise TECMPDataValidationError(
                    f"Invalid LIN data length {data_length}, must be one of {LIN_VALID_LENGTHS}")
        
        # Build payload
        payload = struct.pack("B", lin_id & 0x3F)  # LIN ID (6 bits)
        payload += struct.pack("B", data_length)   # Length
        
        if data_length > 0:
            payload += data.ljust(8, b'\x00')      # Data (padded to 8)
        else:
            payload += b'\x00' * 8                 # No data for special cases
        
        # Calculate or add checksum
        if checksum is None:
            checksum = self._calculate_lin_checksum(lin_id, data)
        payload += struct.pack("B", checksum)
        
        return payload
    
    def parse_payload(self, payload: bytes) -> Dict[str, Any]:
        """Parse LIN payload"""
        if len(payload) < 11:  # ID + Length + 8 data + checksum
            raise TECMPDataValidationError("LIN payload too short")
        
        lin_id = payload[0] & 0x3F
        length = payload[1]
        data = payload[2:2+length] if length > 0 else b''
        checksum = payload[10]
        
        return {
            'lin_id': lin_id,
            'length': length,
            'data': data,
            'checksum': checksum
        }
    
    def build_data_flags(self, collision_error: bool = False,
                        parity_error: bool = False,
                        no_slave_response: bool = False,
                        wup: bool = False, short_wup: bool = False,
                        sleep: bool = False, checksum_error: bool = False,
                        tx: bool = False, overflow: bool = False) -> int:
        """Build LIN data flags"""
        flags = 0
        
        if collision_error:
            flags |= LINDataFlags.COLLISION_ERROR
        if parity_error:
            flags |= LINDataFlags.PARITY_ERROR
        if no_slave_response:
            flags |= LINDataFlags.NO_SLAVE_RESPONSE
        if wup:
            flags |= LINDataFlags.WUP
        if short_wup:
            flags |= LINDataFlags.SHORT_WUP
        if sleep:
            flags |= LINDataFlags.SLEEP
        if checksum_error:
            flags |= LINDataFlags.CHECKSUM_ERROR
        if tx:
            flags |= LINDataFlags.TX
        if overflow:
            flags |= LINDataFlags.OVERFLOW
        
        return flags
    
    def validate(self, payload: bytes, data_flags: int) -> bool:
        """Validate LIN payload - CORRECTED for TECMP v1.7"""
        try:
            # Special case: wakeup or sleep commands may have no regular payload
            if (data_flags & LINDataFlags.WUP or 
                data_flags & LINDataFlags.SLEEP):
                return True
            
            parsed = self.parse_payload(payload)
            
            # Verify checksum if not error
            if not (data_flags & LINDataFlags.CHECKSUM_ERROR):
                expected = self._calculate_lin_checksum(
                    parsed['lin_id'], parsed['data'])
                if expected != parsed['checksum']:
                    self.logger.warning("LIN checksum mismatch")
            
            return True
            
        except Exception as e:
            self.logger.error(f"LIN validation failed: {e}")
            return False
    
    def _calculate_lin_checksum(self, lin_id: int, data: bytes) -> int:
        """Calculate LIN checksum"""
        checksum = lin_id
        for byte in data:
            checksum += byte
            if checksum > 255:
                checksum = (checksum & 0xFF) + 1
        return (~checksum) & 0xFF

# ============================================================================
# FLEXRAY HANDLER
# ============================================================================

class FlexRayHandler(ProtocolHandler):
    """Handler for FlexRay protocol"""
    
    def __init__(self):
        super().__init__(DataType.FLEXRAY)
    
    def build_payload(self, cycle: int, frame_id: int, data: bytes,
                     header_crc: Optional[int] = None,
                     frame_crc: Optional[int] = None) -> bytes:
        """Build FlexRay payload"""
        # Validate parameters
        if cycle > FLEXRAY_CYCLE_MAX:
            raise TECMPDataValidationError(
                f"FlexRay cycle {cycle} exceeds maximum {FLEXRAY_CYCLE_MAX}")
        
        if frame_id > FLEXRAY_FRAME_ID_MAX:
            raise TECMPDataValidationError(
                f"FlexRay frame ID {frame_id} exceeds maximum {FLEXRAY_FRAME_ID_MAX}")
        
        if len(data) > 254:
            raise TECMPDataValidationError("FlexRay data exceeds 254 bytes")
        
        # Build payload
        payload = struct.pack("B", cycle)            # Cycle
        payload += struct.pack(">H", frame_id)       # Frame ID
        payload += struct.pack("B", len(data))       # Length
        payload += data                              # Data
        
        # Add CRCs if provided
        if header_crc is not None:
            payload += struct.pack(">H", header_crc & 0x07FF)  # 11-bit CRC
        if frame_crc is not None:
            payload += struct.pack(">I", frame_crc)[1:]  # 24-bit CRC (3 bytes)
        
        return payload
    
    def parse_payload(self, payload: bytes) -> Dict[str, Any]:
        """Parse FlexRay payload"""
        if len(payload) < 4:
            raise TECMPDataValidationError("FlexRay payload too short")
        
        cycle = payload[0]
        frame_id = struct.unpack(">H", payload[1:3])[0]
        length = payload[3]
        
        data_start = 4
        data_end = data_start + length
        data = payload[data_start:data_end] if len(payload) >= data_end else payload[data_start:]
        
        result = {
            'cycle': cycle,
            'frame_id': frame_id,
            'length': length,
            'data': data,
            'header_crc': None,
            'frame_crc': None
        }
        
        # Parse CRCs if present
        offset = data_end
        if len(payload) >= offset + 2:
            result['header_crc'] = struct.unpack(">H", payload[offset:offset + 2])[0]
            offset += 2
        if len(payload) >= offset + 3:
            result['frame_crc'] = struct.unpack(">I", b'\x00' + payload[offset:offset + 3])[0]
        
        return result
    
    def build_data_flags(self, null_frame: bool = False,
                        startup_frame: bool = False,
                        sync_frame: bool = False,
                        wus: bool = False, ppi: bool = False,
                        cas: bool = False, header_crc_error: bool = False,
                        frame_crc_error: bool = False,
                        tx: bool = False, overflow: bool = False) -> int:
        """Build FlexRay data flags"""
        flags = 0
        
        if null_frame:
            flags |= FlexRayDataFlags.NULL_FRAME
        if startup_frame:
            flags |= FlexRayDataFlags.STARTUP_FRAME
        if sync_frame:
            flags |= FlexRayDataFlags.SYNC_FRAME
        if wus:
            flags |= FlexRayDataFlags.WUS
        if ppi:
            flags |= FlexRayDataFlags.PPI
        if cas:
            flags |= FlexRayDataFlags.CAS
        if header_crc_error:
            flags |= FlexRayDataFlags.HEADER_CRC_ERROR
        if frame_crc_error:
            flags |= FlexRayDataFlags.FRAME_CRC_ERROR
        if tx:
            flags |= FlexRayDataFlags.TX
        if overflow:
            flags |= FlexRayDataFlags.OVERFLOW
        
        return flags
    
    def validate(self, payload: bytes, data_flags: int) -> bool:
        """Validate FlexRay payload"""
        try:
            # Special cases
            if data_flags & (FlexRayDataFlags.WUS | FlexRayDataFlags.CAS):
                return True  # May have special format
            
            parsed = self.parse_payload(payload)
            
            # Validate sync frames
            if data_flags & FlexRayDataFlags.SYNC_FRAME:
                if parsed['frame_id'] > 2:  # Sync frames typically ID 1-2
                    self.logger.warning(f"Unusual sync frame ID: {parsed['frame_id']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"FlexRay validation failed: {e}")
            return False

# ============================================================================
# UART HANDLER
# ============================================================================

class UARTHandler(ProtocolHandler):
    """Handler for UART/RS232 protocol"""
    
    def __init__(self):
        super().__init__(DataType.UART_RS232)
    
    def build_payload(self, data: bytes) -> bytes:
        """
        Build UART payload
        
        For UART, the payload is simply the data bytes (1 byte per symbol)
        Maximum 1000 symbols per TECMP frame
        """
        if len(data) > 1000:
            raise TECMPDataValidationError(
                f"UART data length {len(data)} exceeds 1000 symbols")
        
        return data
    
    def parse_payload(self, payload: bytes) -> Dict[str, Any]:
        """Parse UART payload"""
        return {
            'data': payload,
            'symbol_count': len(payload)
        }
    
    def build_data_flags(self, parity_error: bool = False,
                        data_length: int = 8,
                        tx: bool = False) -> int:
        """
        Build UART data flags according to TECMP v1.7 page 19
        
        Bit layout:
        - Bit 15: RESERVED (must be 0)
        - Bit 14: TX
        - Bits 13-4: RESERVED (must be 0)
        - Bits 3-1: DL (Data Length)
        - Bit 0: Parity error
        """
        flags = 0
        
        # Bit 0: Parity error
        if parity_error:
            flags |= UARTDataFlags.PARITY_ERROR
        
        # Bits 3-1: Data Length (DL)
        if data_length == 7:
            flags |= 0x0004  # 010 in bits 3-1
        elif data_length == 8:
            flags |= 0x0006  # 011 in bits 3-1
        else:
            raise TECMPDataValidationError(
                f"Invalid UART data length {data_length}, must be 7 or 8")
        
        # Bit 14: TX
        if tx:
            flags |= UARTDataFlags.TX
        
        # Bits 4-13 and 15 are RESERVED and must remain 0
        # Mask to ensure reserved bits are 0
        valid_flags_mask = 0x400E  # Bits 14, 3, 2, 1, 0 are valid
        flags &= valid_flags_mask
        
        return flags
    
    def parse_data_flags(self, flags: int) -> Dict[str, Any]:
        """Parse UART data flags"""
        result = {
            'parity_error': bool(flags & UARTDataFlags.PARITY_ERROR),
            'tx': bool(flags & UARTDataFlags.TX),
            'data_length': None
        }
        
        # Extract data length from bits 3-1
        dl_bits = (flags >> 1) & 0x07
        if dl_bits == 0b010:  # 7-bit
            result['data_length'] = 7
        elif dl_bits == 0b011:  # 8-bit
            result['data_length'] = 8
        
        return result
    
    def validate(self, payload: bytes, data_flags: int) -> bool:
        """Validate UART payload and flags"""
        try:
            # Check that reserved bits are 0
            # Valid bits are: 14 (TX), 3-1 (DL), 0 (Parity)
            valid_flags_mask = 0x400E
            if data_flags & ~valid_flags_mask:
                self.logger.warning(f"UART flags have non-zero reserved bits: 0x{data_flags:04X}")
                return False
            
            # Parse flags
            flags_info = self.parse_data_flags(data_flags)
            
            # Validate data length encoding
            if flags_info['data_length'] is None:
                self.logger.error("Invalid UART data length encoding")
                return False
            
            # Check payload size
            if len(payload) > 1000:
                self.logger.error(f"UART payload exceeds 1000 symbols: {len(payload)}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"UART validation failed: {e}")
            return False

# ============================================================================
# ANALOG HANDLER
# ============================================================================

class AnalogHandler(ProtocolHandler):
    """Handler for Analog protocol"""
    
    def __init__(self):
        super().__init__(DataType.ANALOG)
    
    def build_payload(self, samples: List[int]) -> bytes:
        """
        Build Analog payload
        
        Each sample is INT16 (signed 16-bit)
        Maximum 700 samples per TECMP frame
        """
        if len(samples) > 700:
            raise TECMPDataValidationError(
                f"Analog sample count {len(samples)} exceeds 700")
        
        payload = b''
        for sample in samples:
            # Pack as signed 16-bit integer
            payload += struct.pack(">h", sample)
        
        return payload
    
    def parse_payload(self, payload: bytes) -> Dict[str, Any]:
        """Parse Analog payload"""
        if len(payload) % 2 != 0:
            raise TECMPDataValidationError("Analog payload must have even length")
        
        samples = []
        for i in range(0, len(payload), 2):
            sample = struct.unpack(">h", payload[i:i+2])[0]
            samples.append(sample)
        
        return {
            'samples': samples,
            'sample_count': len(samples)
        }
    
    def build_data_flags(self, unit: str = "V", factor: float = 0.1,
                        sample_time_ms: float = 1.0) -> int:
        """Build Analog data flags"""
        flags = 0
        
        # Unit (bits 4-2)
        unit_map = {
            "V": AnalogDataFlags.UNIT_VOLT,
            "A": AnalogDataFlags.UNIT_AMPERE,
            "W": AnalogDataFlags.UNIT_WATT,
            "Ah": AnalogDataFlags.UNIT_AH,
            "C": AnalogDataFlags.UNIT_CELSIUS
        }
        flags |= unit_map.get(unit, AnalogDataFlags.UNIT_VOLT)
        
        # Factor (bits 8-7)
        factor_map = {
            0.1: AnalogDataFlags.FACTOR_0_1,
            0.01: AnalogDataFlags.FACTOR_0_01,
            0.001: AnalogDataFlags.FACTOR_0_001,
            0.0001: AnalogDataFlags.FACTOR_0_0001
        }
        flags |= factor_map.get(factor, AnalogDataFlags.FACTOR_0_1)
        
        # Sample Time (bits 14-11)
        sample_time_map = {
            2500.0: AnalogDataFlags.SAMPLE_2500MS,
            1000.0: AnalogDataFlags.SAMPLE_1000MS,
            500.0: AnalogDataFlags.SAMPLE_500MS,
            250.0: AnalogDataFlags.SAMPLE_250MS,
            100.0: AnalogDataFlags.SAMPLE_100MS,
            50.0: AnalogDataFlags.SAMPLE_50MS,
            25.0: AnalogDataFlags.SAMPLE_25MS,
            10.0: AnalogDataFlags.SAMPLE_10MS,
            5.0: AnalogDataFlags.SAMPLE_5MS,
            2.5: AnalogDataFlags.SAMPLE_2_5MS,
            1.0: AnalogDataFlags.SAMPLE_1MS
        }
        flags |= sample_time_map.get(sample_time_ms, AnalogDataFlags.SAMPLE_1MS)
        
        return flags
    
    def validate(self, payload: bytes, data_flags: int) -> bool:
        """Validate Analog payload"""
        try:
            parsed = self.parse_payload(payload)
            
            if parsed['sample_count'] > 700:
                self.logger.error(f"Too many analog samples: {parsed['sample_count']}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Analog validation failed: {e}")
            return False

# ============================================================================
# FACTORY AND MAIN INTERFACE
# ============================================================================

class TECMPDataBuilder:
    """
    Main interface for building TECMP data payloads.
    Provides clean integration with TECMPPacket.
    """
    
    def __init__(self):
        self.handlers = {
            DataType.CAN: CANHandler(is_fd=False),
            DataType.CAN_FD: CANHandler(is_fd=True),
            DataType.LIN: LINHandler(),
            DataType.FLEXRAY: FlexRayHandler(),
            DataType.UART_RS232: UARTHandler(),
            DataType.ANALOG: AnalogHandler(),
            DataType.ETHERNET_II: EthernetHandler(),
            DataType.ETHERNET_II: EthernetHandler(),
        }
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def build_payload(self, data_type: DataType, **kwargs) -> Tuple[bytes, int]:
        """
        Build payload and data flags for given data type
        
        Args:
            data_type: TECMP data type
            **kwargs: Protocol-specific parameters
            
        Returns:
            Tuple of (payload, data_flags)
        """
        # CORRECTED: Check if this is for replay and block Ethernet
        if 'for_replay' in kwargs and kwargs['for_replay']:
            if data_type in [DataType.ETHERNET_II, DataType.ETHERNET_II]:
                raise TECMPDataError(
                    "Ethernet replay not supported by TECMP v1.7 specification (Section 2.4.4)")
        
        handler = self.handlers.get(data_type)
        if not handler:
            raise TECMPDataError(f"Unsupported data type: {get_data_type_name(data_type)}")
        
        # Extract flag parameters - CORRECTED: Added LIN special case parameters
        flag_params = {k: v for k, v in kwargs.items() if k.endswith('_error') or 
                      k in ['tx', 'overflow', 'ack', 'rtr', 'ide', 'err', 'esi', 'brs',
                            'wup', 'sleep', 'ppi', 'cas', 'null_frame', 'sync_frame',
                            'parity_error', 'data_length', 'unit', 'factor', 'sample_time_ms',
                            'remove_config']}  # Added remove_config for LIN
        
        # Build payload with remaining parameters
        payload_params = {k: v for k, v in kwargs.items() 
                         if k not in flag_params and k != 'for_replay'}
        payload = handler.build_payload(**payload_params)
        
        # Build data flags
        data_flags = handler.build_data_flags(**flag_params)
        
        return payload, data_flags
    
    def parse_payload(self, data_type: DataType, payload: bytes) -> Dict[str, Any]:
        """Parse payload for given data type"""
        handler = self.handlers.get(data_type)
        if not handler:
            raise TECMPDataError(f"Unsupported data type: {get_data_type_name(data_type)}")
        
        return handler.parse_payload(payload)
    
    def validate(self, data_type: DataType, payload: bytes, data_flags: int) -> bool:
        """Validate payload and flags for given data type"""
        handler = self.handlers.get(data_type)
        if not handler:
            raise TECMPDataError(f"Unsupported data type: {get_data_type_name(data_type)}")
        
        return handler.validate(payload, data_flags)
    
    def get_handler(self, data_type: DataType) -> Optional[ProtocolHandler]:
        """Get protocol handler for advanced usage"""
        return self.handlers.get(data_type)

# ============================================================================
# CONVENIENCE FUNCTIONS WITH LAZY INITIALIZATION
# ============================================================================

# Global builder instance (lazy initialization)
_builder = None

def _get_global_builder() -> TECMPDataBuilder:
    """Get or create global builder instance"""
    global _builder
    if _builder is None:
        _builder = TECMPDataBuilder()
    return _builder

def build_can_payload(can_id: int, data: bytes, **kwargs) -> Tuple[bytes, int]:
    """Build CAN payload and flags"""
    return _get_global_builder().build_payload(DataType.CAN, can_id=can_id, 
                                 data=data, **kwargs)

def build_canfd_payload(can_id: int, data: bytes, **kwargs) -> Tuple[bytes, int]:
    """Build CAN-FD payload and flags"""
    return _get_global_builder().build_payload(DataType.CAN_FD, can_id=can_id,
                                 data=data, **kwargs)

def build_ethernet_payload(dst_mac: bytes, src_mac: bytes, 
                         ether_type: int, data: bytes, **kwargs) -> Tuple[bytes, int]:
    """Build Ethernet payload and flags"""
    return _get_global_builder().build_payload(DataType.ETHERNET_II,
                                 dst_mac=dst_mac, src_mac=src_mac,
                                 ether_type=ether_type, data=data, **kwargs)

def build_lin_payload(lin_id: int, data: bytes, **kwargs) -> Tuple[bytes, int]:
    """
    Build LIN payload and flags - CORRECTED for TECMP v1.7
    
    Supports special cases:
    - wup=True: Wake-up signal (length=0)
    - sleep=True: Go-to-sleep command (length=0)
    - remove_config=True: Config removal (length=0)
    """
    return _get_global_builder().build_payload(DataType.LIN, lin_id=lin_id, data=data, **kwargs)

def build_flexray_payload(cycle: int, frame_id: int, data: bytes, **kwargs) -> Tuple[bytes, int]:
    """Build FlexRay payload and flags"""
    return _get_global_builder().build_payload(DataType.FLEXRAY, cycle=cycle,
                                 frame_id=frame_id, data=data, **kwargs)

def build_uart_payload(data: bytes, data_length: int = 8, **kwargs) -> Tuple[bytes, int]:
    """Build UART payload and flags"""
    return _get_global_builder().build_payload(DataType.UART_RS232, data=data, 
                                 data_length=data_length, **kwargs)

def build_analog_payload(samples: List[int], **kwargs) -> Tuple[bytes, int]:
    """Build Analog payload and flags"""
    return _get_global_builder().build_payload(DataType.ANALOG, samples=samples, **kwargs)

# Alias for compatibility
TECMPData = TECMPDataBuilder

# Export public API
__all__ = [
    'TECMPDataBuilder',
    'TECMPData',
    'ProtocolHandler',
    'CANHandler',
    'EthernetHandler',
    'LINHandler',
    'FlexRayHandler',
    'UARTHandler',
    'AnalogHandler',
    'TECMPDataError',
    'TECMPDataValidationError',
    'build_can_payload',
    'build_canfd_payload',
    'build_ethernet_payload',
    'build_lin_payload',
    'build_flexray_payload',
    'build_uart_payload',
    'build_analog_payload',
]