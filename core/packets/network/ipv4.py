#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPv4 (Internet Protocol version 4) Packet implementation for TECMP-Tool.
Provides complete IPv4 packet handling with all header fields and options.
"""

import struct
import socket
import random
from core.packets.base.packet import Packet
from core.exceptions.exceptions import (
    PacketParsingError,
    PacketSerializationError,
    PacketValidationError,
)
from typing import Optional, Dict, Any, Union, List


class IPv4Packet(Packet):
    """
    IPv4 Packet implementation (RFC 791).
    
    IPv4 Header Format (20-60 bytes):
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |Version|  IHL  |Type of Service|          Total Length         |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |         Identification        |Flags|      Fragment Offset    |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |  Time to Live |    Protocol   |         Header Checksum       |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                       Source Address                          |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                    Destination Address                        |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                    Options                    |    Padding    |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """
    
    # IPv4 constants
    VERSION = 4
    MIN_HEADER_LENGTH = 20
    MAX_HEADER_LENGTH = 60
    MAX_PACKET_SIZE = 65535
    DEFAULT_TTL = 64
    
    # Protocol numbers
    PROTO_ICMP = 1
    PROTO_IGMP = 2
    PROTO_TCP = 6
    PROTO_UDP = 17
    PROTO_ENCAP = 41
    PROTO_OSPF = 89
    PROTO_SCTP = 132
    
    # Type of Service / DSCP values
    DSCP_DEFAULT = 0
    DSCP_CS1 = 8
    DSCP_AF11 = 10
    DSCP_AF12 = 12
    DSCP_AF13 = 14
    DSCP_CS2 = 16
    DSCP_AF21 = 18
    DSCP_AF22 = 20
    DSCP_AF23 = 22
    DSCP_CS3 = 24
    DSCP_AF31 = 26
    DSCP_AF32 = 28
    DSCP_AF33 = 30
    DSCP_CS4 = 32
    DSCP_AF41 = 34
    DSCP_AF42 = 36
    DSCP_AF43 = 38
    DSCP_CS5 = 40
    DSCP_EF = 46
    DSCP_CS6 = 48
    DSCP_CS7 = 56
    
    # Flags
    FLAG_RESERVED = 0x4
    FLAG_DF = 0x2  # Don't Fragment
    FLAG_MF = 0x1  # More Fragments
    
    def __init__(
        self,
        # === BASIC FIELDS ===
        src_ip: str,
        dst_ip: str,
        
        # === OPTIONAL FIELDS ===
        version: int = VERSION,
        ihl: Optional[int] = None,          # Internet Header Length (auto-calculated)
        tos: int = 0,                       # Type of Service
        dscp: Optional[int] = None,         # DSCP (overrides tos)
        ecn: int = 0,                       # ECN bits
        total_length: Optional[int] = None, # Total packet length (auto-calculated)
        identification: Optional[int] = None, # Fragment ID (random if None)
        flags: int = FLAG_DF,               # Fragment flags (default: Don't Fragment)
        fragment_offset: int = 0,           # Fragment offset
        ttl: int = DEFAULT_TTL,             # Time to Live
        protocol: int = PROTO_TCP,          # Protocol number
        checksum: Optional[int] = None,     # Header checksum (auto-calculated)
        
        # === IP OPTIONS ===
        options: bytes = b'',               # IP options
        
        # === PAYLOAD ===
        payload: bytes = b'',               # IP payload
        
        # === FLAGS AS BOOLEANS ===
        dont_fragment: Optional[bool] = None,
        more_fragments: Optional[bool] = None,
        
        # === AUTO-CALCULATION ===
        auto_checksum: bool = True,
        auto_length: bool = True,
        auto_id: bool = True,
        
        # === METADATA ===
        interface: Optional[str] = None,
        vlan_id: Optional[int] = None,
        
        # === VALIDATION ===
        strict_validation: bool = True
    ):
        """
        Initialize IPv4 packet.
        
        Args:
            src_ip: Source IP address
            dst_ip: Destination IP address
            version: IP version (must be 4)
            ihl: Internet Header Length in 32-bit words
            tos: Type of Service byte
            dscp: DSCP value (if set, overrides tos)
            ecn: ECN bits
            total_length: Total packet length
            identification: Fragment identification
            flags: Fragment flags
            fragment_offset: Fragment offset
            ttl: Time to Live
            protocol: Protocol number
            checksum: Header checksum
            options: IP options
            payload: Packet payload
            dont_fragment: Don't Fragment flag
            more_fragments: More Fragments flag
            auto_checksum: Auto-calculate checksum
            auto_length: Auto-calculate total length
            auto_id: Auto-generate identification
            interface: Output interface
            vlan_id: VLAN ID
            strict_validation: Enable strict validation
        """
        super().__init__()
        
        # Basic fields
        self.version = version
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.ttl = ttl
        self.protocol = protocol
        
        # TOS/DSCP/ECN handling
        if dscp is not None:
            self.tos = (dscp << 2) | ecn
            self.dscp = dscp
            self.ecn = ecn
        else:
            self.tos = tos
            self.dscp = tos >> 2
            self.ecn = tos & 0x03
        
        # Options and header length
        self.options = options
        if ihl is None:
            self.ihl = 5 + (len(options) + 3) // 4  # Auto-calculate
        else:
            self.ihl = ihl
        
        # Length
        self.total_length = total_length
        self.auto_length = auto_length
        
        # Fragmentation
        self.identification = identification
        if self.identification is None and auto_id:
            self.identification = random.randint(0, 65535)
        
        # Handle flags
        if dont_fragment is not None or more_fragments is not None:
            self.flags = 0
            if dont_fragment:
                self.flags |= self.FLAG_DF
            if more_fragments:
                self.flags |= self.FLAG_MF
        else:
            self.flags = flags
            
        self.fragment_offset = fragment_offset
        
        # Checksum
        self.checksum = checksum
        self.auto_checksum = auto_checksum
        
        # Payload
        self.payload = payload
        
        # Metadata
        self.interface = interface
        self.vlan_id = vlan_id
        
        # Validation
        self.strict_validation = strict_validation
    
    def _calculate_checksum(self, header: bytes) -> int:
        """
        Calculate IPv4 header checksum.
        
        Args:
            header: IP header with checksum field set to 0
            
        Returns:
            int: Calculated checksum
        """
        # Ensure even length
        if len(header) % 2 == 1:
            header += b'\x00'
        
        # Sum all 16-bit words
        checksum = 0
        for i in range(0, len(header), 2):
            word = (header[i] << 8) + header[i + 1]
            checksum += word
            # Add carry
            checksum = (checksum & 0xFFFF) + (checksum >> 16)
        
        # One's complement
        return ~checksum & 0xFFFF
    
    def serialize(self) -> bytes:
        """
        Serialize IPv4 packet to bytes.
        
        Returns:
            bytes: Serialized packet data
            
        Raises:
            PacketSerializationError: If serialization fails
        """
        try:
            # Validate before serialization
            if self.strict_validation:
                self.validate()
            
            # Auto-calculate total length
            if self.auto_length or self.total_length is None:
                self.total_length = (self.ihl * 4) + len(self.payload)
            
            # Build header
            version_ihl = (self.version << 4) | self.ihl
            flags_fragoff = (self.flags << 13) | self.fragment_offset
            
            # Pack header without checksum
            header = struct.pack('!BBHHHBBH4s4s',
                version_ihl,
                self.tos,
                self.total_length,
                self.identification or 0,
                flags_fragoff,
                self.ttl,
                self.protocol,
                0,  # Checksum placeholder
                socket.inet_aton(self.src_ip),
                socket.inet_aton(self.dst_ip)
            )
            
            # Add options if any
            if self.options:
                # Pad options to 4-byte boundary
                opt_len = len(self.options)
                padding_needed = (4 - (opt_len % 4)) % 4
                header += self.options + (b'\x00' * padding_needed)
            
            # Calculate checksum if needed
            if self.auto_checksum or self.checksum is None:
                self.checksum = self._calculate_checksum(header)
                # Repack with checksum
                header = header[:10] + struct.pack('!H', self.checksum) + header[12:]
            
            # Combine header and payload
            packet = header + self.payload
            
            # Store raw data
            self._raw_data = bytearray(packet)
            self._update_size()
            
            return bytes(self._raw_data)
            
        except struct.error as e:
            raise PacketSerializationError(f"IPv4 serialization error: {e}")
        except socket.error as e:
            raise PacketSerializationError(f"Invalid IP address: {e}")
        except Exception as e:
            raise PacketSerializationError(f"Unexpected error during IPv4 serialization: {e}")
    
    def deserialize(self, data: bytes):
        """
        Deserialize bytes to IPv4 packet.
        
        Args:
            data: Raw bytes to deserialize
            
        Raises:
            PacketParsingError: If parsing fails
        """
        if len(data) < self.MIN_HEADER_LENGTH:
            raise PacketParsingError(
                f"IPv4 packet too short: {len(data)} bytes (minimum {self.MIN_HEADER_LENGTH})"
            )
        
        try:
            # Unpack fixed header fields
            (version_ihl, self.tos, self.total_length, self.identification,
             flags_fragoff, self.ttl, self.protocol, self.checksum,
             src_bytes, dst_bytes) = struct.unpack('!BBHHHBBH4s4s', data[:20])
            
            # Extract version and IHL
            self.version = version_ihl >> 4
            self.ihl = version_ihl & 0x0F
            
            # Extract DSCP and ECN
            self.dscp = self.tos >> 2
            self.ecn = self.tos & 0x03
            
            # Extract flags and fragment offset
            self.flags = (flags_fragoff >> 13) & 0x07
            self.fragment_offset = flags_fragoff & 0x1FFF
            
            # Convert IP addresses
            self.src_ip = socket.inet_ntoa(src_bytes)
            self.dst_ip = socket.inet_ntoa(dst_bytes)
            
            # Calculate header length
            header_length = self.ihl * 4
            if header_length < 20 or header_length > len(data):
                raise PacketParsingError(f"Invalid IHL: {self.ihl}")
            
            # Extract options if present
            if header_length > 20:
                self.options = data[20:header_length]
            else:
                self.options = b''
            
            # Extract payload
            self.payload = data[header_length:self.total_length]
            
            # Store raw data
            self._raw_data = bytearray(data[:self.total_length])
            self._update_size()
            
            # Mark as validated
            self.mark_validated(True)
            
        except struct.error as e:
            raise PacketParsingError(f"IPv4 deserialization error: {e}")
        except socket.error as e:
            raise PacketParsingError(f"Invalid IP address format: {e}")
        except Exception as e:
            raise PacketParsingError(f"Unexpected error during IPv4 parsing: {e}")
    
    def validate(self) -> bool:
        """
        Validate IPv4 packet fields.
        
        Returns:
            bool: True if valid
            
        Raises:
            PacketValidationError: If validation fails
        """
        # Validate version
        if self.version != 4:
            raise PacketValidationError(f"Invalid IP version: {self.version} (must be 4)")
        
        # Validate IHL
        if not (5 <= self.ihl <= 15):
            raise PacketValidationError(f"Invalid IHL: {self.ihl} (must be 5-15)")
        
        # Validate header length vs options
        expected_options_len = (self.ihl - 5) * 4
        actual_options_len = len(self.options)
        if actual_options_len > expected_options_len:
            raise PacketValidationError(
                f"Options too long: {actual_options_len} bytes for IHL {self.ihl}"
            )
        
        # Validate TTL
        if not (0 <= self.ttl <= 255):
            raise PacketValidationError(f"Invalid TTL: {self.ttl}")
        
        # Validate protocol
        if not (0 <= self.protocol <= 255):
            raise PacketValidationError(f"Invalid protocol: {self.protocol}")
        
        # Validate IP addresses
        try:
            socket.inet_aton(self.src_ip)
            socket.inet_aton(self.dst_ip)
        except socket.error:
            raise PacketValidationError("Invalid IP address format")
        
        # Validate total length
        if self.total_length is not None:
            min_length = self.ihl * 4
            if self.total_length < min_length:
                raise PacketValidationError(
                    f"Total length {self.total_length} less than header length {min_length}"
                )
            if self.total_length > self.MAX_PACKET_SIZE:
                raise PacketValidationError(
                    f"Total length {self.total_length} exceeds maximum {self.MAX_PACKET_SIZE}"
                )
        
        # Validate fragment offset
        if self.fragment_offset > 8191:  # 13 bits max
            raise PacketValidationError(f"Invalid fragment offset: {self.fragment_offset}")
        
        self.mark_validated(True)
        return True
    
    def summary(self) -> str:
        """
        Return human-readable summary of IPv4 packet.
        
        Returns:
            str: Packet summary
        """
        proto_names = {
            1: "ICMP", 2: "IGMP", 6: "TCP", 17: "UDP",
            41: "IPv6", 89: "OSPF", 132: "SCTP"
        }
        
        proto = proto_names.get(self.protocol, f"Proto_{self.protocol}")
        
        flags_str = ""
        if self.flags & self.FLAG_DF:
            flags_str += "DF"
        if self.flags & self.FLAG_MF:
            flags_str += ",MF" if flags_str else "MF"
        if not flags_str:
            flags_str = "None"
        
        summary = f"IPv4 {self.src_ip} -> {self.dst_ip} {proto}"
        summary += f" TTL={self.ttl} Flags={flags_str}"
        
        if self.dscp > 0:
            summary += f" DSCP={self.dscp}"
        
        if self.fragment_offset > 0:
            summary += f" FragOff={self.fragment_offset}"
        
        if self.payload:
            summary += f" [{len(self.payload)} bytes]"
        
        return summary
    
    def get_protocol_name(self) -> str:
        """Get human-readable protocol name"""
        protocols = {
            0: "HOPOPT", 1: "ICMP", 2: "IGMP", 3: "GGP", 4: "IP-in-IP",
            6: "TCP", 8: "EGP", 17: "UDP", 41: "IPv6", 46: "RSVP",
            47: "GRE", 50: "ESP", 51: "AH", 89: "OSPF", 103: "PIM",
            132: "SCTP"
        }
        return protocols.get(self.protocol, f"Unknown ({self.protocol})")
    
    def is_fragment(self) -> bool:
        """Check if this is a fragmented packet"""
        return (self.flags & self.FLAG_MF) != 0 or self.fragment_offset > 0
    
    def is_first_fragment(self) -> bool:
        """Check if this is the first fragment"""
        return (self.flags & self.FLAG_MF) != 0 and self.fragment_offset == 0
    
    def is_last_fragment(self) -> bool:
        """Check if this is the last fragment"""
        return (self.flags & self.FLAG_MF) == 0 and self.fragment_offset > 0
    
    def get_dscp_name(self) -> str:
        """Get DSCP class name"""
        dscp_names = {
            0: "Default", 8: "CS1", 10: "AF11", 12: "AF12", 14: "AF13",
            16: "CS2", 18: "AF21", 20: "AF22", 22: "AF23", 24: "CS3",
            26: "AF31", 28: "AF32", 30: "AF33", 32: "CS4", 34: "AF41",
            36: "AF42", 38: "AF43", 40: "CS5", 46: "EF", 48: "CS6", 56: "CS7"
        }
        return dscp_names.get(self.dscp, f"DSCP{self.dscp}")
    
    def set_dont_fragment(self, df: bool = True):
        """Set or clear Don't Fragment flag"""
        if df:
            self.flags |= self.FLAG_DF
        else:
            self.flags &= ~self.FLAG_DF
    
    def set_more_fragments(self, mf: bool = True):
        """Set or clear More Fragments flag"""
        if mf:
            self.flags |= self.FLAG_MF
        else:
            self.flags &= ~self.FLAG_MF
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert packet to dictionary representation.
        
        Returns:
            dict: Packet fields as dictionary
        """
        base_dict = super().to_dict()
        base_dict.update({
            "version": self.version,
            "ihl": self.ihl,
            "tos": self.tos,
            "dscp": self.dscp,
            "dscp_name": self.get_dscp_name(),
            "ecn": self.ecn,
            "total_length": self.total_length,
            "identification": self.identification,
            "flags": self.flags,
            "dont_fragment": bool(self.flags & self.FLAG_DF),
            "more_fragments": bool(self.flags & self.FLAG_MF),
            "fragment_offset": self.fragment_offset,
            "ttl": self.ttl,
            "protocol": self.protocol,
            "protocol_name": self.get_protocol_name(),
            "checksum": f"0x{self.checksum:04X}" if self.checksum else "None",
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "options_length": len(self.options),
            "payload_length": len(self.payload),
            "is_fragment": self.is_fragment()
        })
        return base_dict
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"IPv4Packet(src={self.src_ip}, dst={self.dst_ip}, "
            f"proto={self.protocol}, ttl={self.ttl})"
        )


# Module exports
__all__ = ['IPv4Packet']