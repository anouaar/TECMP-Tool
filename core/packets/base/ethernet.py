#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ethernet Frame (IEEE 802.3) implementation for TECMP-Tool.
Provides complete Ethernet frame handling with all fields.
"""

import struct
import binascii
from typing import Optional, Dict, Any, Union, List
from core.packets.base.packet import Packet
from core.exceptions.exceptions import (
    PacketParsingError,
    PacketSerializationError,
    PacketValidationError,
)


class MacAddress:
    """MAC Address representation and manipulation"""
    
    def __init__(self, address: Union[str, bytes, int]):
        """
        Initialize MAC address from various formats.
        
        Args:
            address: MAC address as string, bytes, or integer
        """
        if isinstance(address, str):
            self._bytes = self._parse_string(address)
        elif isinstance(address, bytes):
            if len(address) != 6:
                raise ValueError(f"MAC address must be 6 bytes, got {len(address)}")
            self._bytes = address
        elif isinstance(address, int):
            if not (0 <= address <= 0xFFFFFFFFFFFF):
                raise ValueError(f"MAC address out of range: {address}")
            self._bytes = address.to_bytes(6, 'big')
        else:
            raise TypeError(f"Unsupported type for MAC address: {type(address)}")
    
    def _parse_string(self, mac_str: str) -> bytes:
        """Parse MAC address from string"""
        # Remove common separators
        mac_str = mac_str.upper().replace(':', '').replace('-', '').replace('.', '')
        
        # Check length
        if len(mac_str) != 12:
            raise ValueError(f"Invalid MAC address length: {mac_str}")
        
        # Check valid hex
        if not all(c in '0123456789ABCDEF' for c in mac_str):
            raise ValueError(f"Invalid characters in MAC address: {mac_str}")
        
        # Convert to bytes
        return bytes.fromhex(mac_str)
    
    def __str__(self) -> str:
        """String representation with colons"""
        return ':'.join(f'{b:02X}' for b in self._bytes)
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return f"MacAddress('{self}')"
    
    def __eq__(self, other) -> bool:
        """Compare MAC addresses"""
        if isinstance(other, MacAddress):
            return self._bytes == other._bytes
        elif isinstance(other, str):
            try:
                return self._bytes == MacAddress(other)._bytes
            except:
                return False
        return False
    
    def __hash__(self) -> int:
        """Hash for use in sets/dicts"""
        return hash(self._bytes)
    
    @property
    def bytes(self) -> bytes:
        """Get MAC as bytes"""
        return self._bytes
    
    @property
    def integer(self) -> int:
        """Get MAC as integer"""
        return int.from_bytes(self._bytes, 'big')
    
    def is_multicast(self) -> bool:
        """Check if this is a multicast address"""
        return bool(self._bytes[0] & 0x01)
    
    def is_broadcast(self) -> bool:
        """Check if this is the broadcast address"""
        return self._bytes == b'\xFF\xFF\xFF\xFF\xFF\xFF'
    
    def is_local(self) -> bool:
        """Check if this is a locally administered address"""
        return bool(self._bytes[0] & 0x02)


class EthernetPacket(Packet):
    """
    Ethernet II Frame implementation.
    
    Ethernet II Frame Format:
    +------------------------+------------------------+
    |  Preamble (7 bytes)    |   SFD (1 byte)        |
    +------------------------+------------------------+
    |  Destination MAC (6)   |   Source MAC (6)      |
    +------------------------+------------------------+
    |    EtherType (2)       |                       |
    +------------------------+                       +
    |                   Payload                      |
    |                 (46-1500 bytes)                |
    +------------------------------------------------+
    |                  FCS (4 bytes)                 |
    +------------------------------------------------+
    """
    
    # Ethernet constants
    MIN_FRAME_SIZE = 64      # Minimum frame size including FCS
    MAX_FRAME_SIZE = 1518    # Maximum frame size including FCS
    MIN_PAYLOAD_SIZE = 46    # Minimum payload size
    MAX_PAYLOAD_SIZE = 1500  # Maximum payload size (MTU)
    HEADER_SIZE = 14         # MAC addresses + EtherType
    FCS_SIZE = 4            # Frame Check Sequence size
    PREAMBLE_SIZE = 7       # Preamble bytes
    SFD_SIZE = 1            # Start Frame Delimiter
    
    # Common EtherTypes
    ETHERTYPE_IPV4 = 0x0800
    ETHERTYPE_ARP = 0x0806
    ETHERTYPE_VLAN = 0x8100
    ETHERTYPE_IPV6 = 0x86DD
    ETHERTYPE_QINQ = 0x88A8
    ETHERTYPE_MPLS = 0x8847
    ETHERTYPE_MPLS_MULTICAST = 0x8848
    ETHERTYPE_PPPOE_DISCOVERY = 0x8863
    ETHERTYPE_PPPOE_SESSION = 0x8864
    ETHERTYPE_LLDP = 0x88CC
    ETHERTYPE_8021X = 0x888E
    ETHERTYPE_PTP = 0x88F7
    
    # Special MAC addresses
    BROADCAST_MAC = "FF:FF:FF:FF:FF:FF"
    
    def __init__(
        self,
        # === BASIC FIELDS ===
        src_mac: Union[str, MacAddress],
        dst_mac: Union[str, MacAddress],
        ether_type: int = ETHERTYPE_IPV4,
        
        # === PAYLOAD ===
        payload: bytes = b'',
        
        # === OPTIONAL FIELDS ===
        preamble: Union[str, bytes] = None,
        sfd: Union[int, bytes] = 0xAB,
        fcs: Union[int, bytes, None] = None,
        
        # === AUTO-CALCULATION ===
        auto_fcs: bool = True,
        auto_pad: bool = True,
        
        # === METADATA ===
        interface: Optional[str] = None,
        vlan_id: Optional[int] = None,
        timestamp: Optional[float] = None,
        
        # === VALIDATION ===
        strict_validation: bool = True
    ):
        """
        Initialize Ethernet packet.
        
        Args:
            src_mac: Source MAC address
            dst_mac: Destination MAC address
            ether_type: EtherType/Length field
            payload: Frame payload
            preamble: Frame preamble (7 bytes of 0xAA)
            sfd: Start Frame Delimiter (default 0xAB)
            fcs: Frame Check Sequence (CRC32)
            auto_fcs: Automatically calculate FCS
            auto_pad: Automatically pad short frames
            interface: Network interface
            vlan_id: VLAN ID if applicable
            timestamp: Packet timestamp
            strict_validation: Enable strict validation
        """
        super().__init__()
        
        # Convert MAC addresses
        self.src_mac = MacAddress(src_mac) if not isinstance(src_mac, MacAddress) else src_mac
        self.dst_mac = MacAddress(dst_mac) if not isinstance(dst_mac, MacAddress) else dst_mac
        
        # Basic fields
        self.ether_type = ether_type
        self.payload = payload
        
        # Preamble and SFD
        if preamble is None:
            self.preamble = b'\xAA' * 7
        elif isinstance(preamble, str):
            self.preamble = bytes.fromhex(preamble.replace(' ', ''))
        else:
            self.preamble = preamble
            
        if isinstance(sfd, int):
            self.sfd = bytes([sfd])
        else:
            self.sfd = sfd
        
        # FCS
        self.fcs = fcs
        self.auto_fcs = auto_fcs
        self.auto_pad = auto_pad
        
        # Metadata
        self.interface = interface
        self.vlan_id = vlan_id
        if timestamp:
            self.set_timestamp(timestamp)
        
        # Validation
        self.strict_validation = strict_validation
        
        # Apply auto-padding if needed
        if self.auto_pad:
            self._apply_padding()
    
    def _apply_padding(self):
        """Apply padding to meet minimum frame size"""
        min_payload = self.MIN_PAYLOAD_SIZE
        if len(self.payload) < min_payload:
            padding_needed = min_payload - len(self.payload)
            self.payload += b'\x00' * padding_needed
    
    def _calculate_fcs(self, data: bytes) -> int:
        """
        Calculate FCS (CRC32) for Ethernet frame.
        
        Args:
            data: Frame data (without FCS)
            
        Returns:
            int: CRC32 value
        """
        # CRC32 for Ethernet (polynomial 0x04C11DB7)
        crc = binascii.crc32(data) & 0xFFFFFFFF
        # Ethernet uses bit-reversed CRC32
        return crc
    
    def serialize(self) -> bytes:
        """
        Serialize Ethernet packet to bytes.
        
        Returns:
            bytes: Serialized packet data
            
        Raises:
            PacketSerializationError: If serialization fails
        """
        try:
            # Validate before serialization
            if self.strict_validation:
                self.validate()
            
            # Build frame without preamble/SFD (those are physical layer)
            frame = b''
            
            # Destination MAC
            frame += self.dst_mac.bytes
            
            # Source MAC
            frame += self.src_mac.bytes
            
            # EtherType/Length
            frame += struct.pack('!H', self.ether_type)
            
            # Payload (with padding if needed)
            if self.auto_pad:
                self._apply_padding()
            frame += self.payload
            
            # Calculate FCS if needed
            if self.auto_fcs or self.fcs is None:
                self.fcs = self._calculate_fcs(frame)
            
            # Add FCS
            if isinstance(self.fcs, int):
                frame += struct.pack('<I', self.fcs)  # Little-endian for FCS
            elif isinstance(self.fcs, bytes):
                frame += self.fcs
            
            # Store raw data
            self._raw_data = bytearray(frame)
            self._update_size()
            
            return bytes(self._raw_data)
            
        except struct.error as e:
            raise PacketSerializationError(f"Ethernet serialization error: {e}")
        except Exception as e:
            raise PacketSerializationError(f"Unexpected error during Ethernet serialization: {e}")
    
    def serialize_with_preamble(self) -> bytes:
        """
        Serialize Ethernet packet including preamble and SFD.
        
        Returns:
            bytes: Complete frame with physical layer headers
        """
        frame = self.preamble + self.sfd + self.serialize()
        return frame
    
    def deserialize(self, data: bytes):
        """
        Deserialize bytes to Ethernet packet.
        
        Args:
            data: Raw bytes to deserialize
            
        Raises:
            PacketParsingError: If parsing fails
        """
        # Check for preamble and SFD
        offset = 0
        if len(data) >= 8 and data[:7] == b'\xAA' * 7:
            # Has preamble
            self.preamble = data[:7]
            self.sfd = data[7:8]
            offset = 8
        
        # Minimum size check (without preamble/SFD)
        min_size = self.HEADER_SIZE + self.FCS_SIZE
        if len(data) - offset < min_size:
            raise PacketParsingError(
                f"Ethernet frame too short: {len(data) - offset} bytes (minimum {min_size})"
            )
        
        try:
            # Parse MAC addresses
            self.dst_mac = MacAddress(data[offset:offset + 6])
            offset += 6
            
            self.src_mac = MacAddress(data[offset:offset + 6])
            offset += 6
            
            # Parse EtherType/Length
            self.ether_type = struct.unpack('!H', data[offset:offset + 2])[0]
            offset += 2
            
            # Extract payload and FCS
            # Assume last 4 bytes are FCS
            if len(data) - offset >= self.FCS_SIZE:
                self.payload = data[offset:-self.FCS_SIZE]
                self.fcs = struct.unpack('<I', data[-self.FCS_SIZE:])[0]
            else:
                # No FCS
                self.payload = data[offset:]
                self.fcs = None
            
            # Store raw data (without preamble/SFD)
            self._raw_data = bytearray(data[8:] if self.preamble else data)
            self._update_size()
            
            # Mark as validated
            self.mark_validated(True)
            
        except struct.error as e:
            raise PacketParsingError(f"Ethernet deserialization error: {e}")
        except Exception as e:
            raise PacketParsingError(f"Unexpected error during Ethernet parsing: {e}")
    
    def validate(self) -> bool:
        """
        Validate Ethernet packet fields.
        
        Returns:
            bool: True if valid
            
        Raises:
            PacketValidationError: If validation fails
        """
        # Validate MAC addresses
        if self.src_mac.is_broadcast() and self.strict_validation:
            raise PacketValidationError("Source MAC cannot be broadcast address")
        
        # Validate EtherType/Length
        if self.ether_type <= 1500:
            # It's a length field
            if self.ether_type != len(self.payload):
                self._logger.warning(
                    f"Length field mismatch: field={self.ether_type}, actual={len(self.payload)}"
                )
        elif self.ether_type < 0x0600:
            # Invalid range (1501-1535)
            raise PacketValidationError(f"Invalid EtherType/Length: {self.ether_type}")
        
        # Validate frame size
        frame_size = self.HEADER_SIZE + len(self.payload) + self.FCS_SIZE
        if frame_size < self.MIN_FRAME_SIZE:
            if not self.auto_pad:
                raise PacketValidationError(f"Frame too small: {frame_size} bytes")
        elif frame_size > self.MAX_FRAME_SIZE:
            raise PacketValidationError(f"Frame too large: {frame_size} bytes")
        
        # Validate FCS if present and not auto-calculated
        if self.fcs is not None and not self.auto_fcs and self._raw_data:
            expected_fcs = self._calculate_fcs(bytes(self._raw_data[:-4]))
            if self.fcs != expected_fcs:
                self._logger.warning(f"FCS mismatch: got {self.fcs:08X}, expected {expected_fcs:08X}")
        
        self.mark_validated(True)
        return True
    
    def summary(self) -> str:
        """
        Return human-readable summary of Ethernet packet.
        
        Returns:
            str: Packet summary
        """
        # Get protocol name
        proto_names = {
            0x0800: "IPv4",
            0x0806: "ARP",
            0x8100: "VLAN",
            0x86DD: "IPv6",
            0x88A8: "Q-in-Q",
            0x88CC: "LLDP",
            0x888E: "802.1X"
        }
        
        if self.ether_type <= 1500:
            proto = f"Length={self.ether_type}"
        else:
            proto = proto_names.get(self.ether_type, f"0x{self.ether_type:04X}")
        
        summary = f"Ethernet {self.src_mac} -> {self.dst_mac} Type={proto}"
        
        if self.dst_mac.is_broadcast():
            summary += " [Broadcast]"
        elif self.dst_mac.is_multicast():
            summary += " [Multicast]"
        
        if self.payload:
            summary += f" [{len(self.payload)} bytes]"
        
        return summary
    
    def get_ethertype_name(self) -> str:
        """Get human-readable EtherType name"""
        ethertypes = {
            0x0800: "IPv4",
            0x0806: "ARP",
            0x8100: "802.1Q VLAN",
            0x86DD: "IPv6",
            0x8847: "MPLS Unicast",
            0x8848: "MPLS Multicast",
            0x8863: "PPPoE Discovery",
            0x8864: "PPPoE Session",
            0x888E: "802.1X",
            0x88A8: "802.1ad (Q-in-Q)",
            0x88CC: "LLDP",
            0x88F7: "PTP",
            0x9000: "Configuration Test Protocol"
        }
        
        if self.ether_type <= 1500:
            return f"802.3 Length ({self.ether_type})"
        
        return ethertypes.get(self.ether_type, f"Unknown (0x{self.ether_type:04X})")
    
    def is_broadcast(self) -> bool:
        """Check if this is a broadcast frame"""
        return self.dst_mac.is_broadcast()
    
    def is_multicast(self) -> bool:
        """Check if this is a multicast frame"""
        return self.dst_mac.is_multicast()
    
    def is_unicast(self) -> bool:
        """Check if this is a unicast frame"""
        return not (self.is_broadcast() or self.is_multicast())
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert packet to dictionary representation.
        
        Returns:
            dict: Packet fields as dictionary
        """
        base_dict = super().to_dict()
        base_dict.update({
            "src_mac": str(self.src_mac),
            "dst_mac": str(self.dst_mac),
            "ether_type": f"0x{self.ether_type:04X}",
            "ethertype_name": self.get_ethertype_name(),
            "payload_size": len(self.payload),
            "is_broadcast": self.is_broadcast(),
            "is_multicast": self.is_multicast(),
            "is_unicast": self.is_unicast(),
            "fcs": f"0x{self.fcs:08X}" if isinstance(self.fcs, int) else str(self.fcs)
        })
        return base_dict
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"EthernetPacket(src={self.src_mac}, dst={self.dst_mac}, "
            f"type=0x{self.ether_type:04X}, payload_size={len(self.payload)})"
        )


# Module exports
__all__ = ['EthernetPacket', 'MacAddress']