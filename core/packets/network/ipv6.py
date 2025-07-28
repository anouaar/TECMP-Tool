#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPv6 (Internet Protocol version 6) Packet implementation for TECMP-Tool.
Provides complete IPv6 packet handling with all header fields and extension headers.
"""

import struct
import socket
import random
from typing import Optional, Dict, Any, Union, List, Tuple
from core.packets.base.packet import (
    Packet,
    PacketParsingError,
    PacketSerializationError,
    PacketValidationError,
)


class IPv6Packet(Packet):
    """
    IPv6 Packet implementation (RFC 8200).
    
    IPv6 Header Format (40 bytes):
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |Version| Traffic Class |           Flow Label                  |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |         Payload Length        |  Next Header  |   Hop Limit   |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                                                               |
    +                                                               +
    |                                                               |
    +                         Source Address                        +
    |                                                               |
    +                                                               +
    |                                                               |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                                                               |
    +                                                               +
    |                                                               |
    +                      Destination Address                      +
    |                                                               |
    +                                                               +
    |                                                               |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """
    
    # IPv6 constants
    VERSION = 6
    HEADER_SIZE = 40
    MAX_PAYLOAD_SIZE = 65535
    DEFAULT_HOP_LIMIT = 64
    
    # Next Header values (Protocol numbers)
    NH_HOPOPT = 0        # Hop-by-hop options
    NH_ICMP = 1          # ICMPv4
    NH_IGMP = 2          # IGMP
    NH_TCP = 6           # TCP
    NH_UDP = 17          # UDP
    NH_IPV6 = 41         # IPv6 encapsulation
    NH_ROUTING = 43      # Routing header
    NH_FRAGMENT = 44     # Fragment header
    NH_ESP = 50          # Encapsulating Security Payload
    NH_AH = 51           # Authentication Header
    NH_ICMPV6 = 58       # ICMPv6
    NH_NONE = 59         # No next header
    NH_DSTOPTS = 60      # Destination options
    NH_MOBILITY = 135    # Mobility header
    NH_SCTP = 132        # SCTP
    
    # Traffic Class (DSCP + ECN)
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
    
    def __init__(
        self,
        # === BASIC FIELDS ===
        src_ip: str,
        dst_ip: str,
        
        # === OPTIONAL FIELDS ===
        version: int = VERSION,
        traffic_class: int = 0,             # Traffic class (DSCP + ECN)
        dscp: Optional[int] = None,         # DSCP (overrides traffic_class)
        ecn: int = 0,                       # ECN bits
        flow_label: int = 0,                # Flow label (20 bits)
        payload_length: Optional[int] = None, # Payload length (auto-calculated)
        next_header: int = NH_TCP,          # Next header (protocol)
        hop_limit: int = DEFAULT_HOP_LIMIT, # Hop limit (like TTL)
        
        # === COMPATIBILITY NAMES ===
        protocol: Optional[int] = None,     # Alias for next_header
        
        # === EXTENSION HEADERS ===
        extension_headers: List[Tuple[int, bytes]] = None,
        
        # === PAYLOAD ===
        payload: bytes = b'',               # IPv6 payload
        
        # === AUTO-CALCULATION ===
        auto_length: bool = True,           # Auto-calculate payload length
        auto_flow_label: bool = False,      # Auto-generate flow label
        
        # === METADATA ===
        interface: Optional[str] = None,
        vlan_id: Optional[int] = None,
        
        # === VALIDATION ===
        strict_validation: bool = True
    ):
        """
        Initialize IPv6 packet.
        
        Args:
            src_ip: Source IPv6 address
            dst_ip: Destination IPv6 address
            version: IP version (must be 6)
            traffic_class: Traffic class byte (DSCP + ECN)
            dscp: DSCP value (if set, overrides traffic_class)
            ecn: ECN bits
            flow_label: Flow label (20 bits)
            payload_length: Payload length
            next_header: Next header type
            hop_limit: Hop limit
            protocol: Alias for next_header (compatibility)
            extension_headers: List of (type, data) extension headers
            payload: Packet payload
            auto_length: Auto-calculate payload length
            auto_flow_label: Auto-generate flow label
            interface: Output interface
            vlan_id: VLAN ID
            strict_validation: Enable strict validation
        """
        super().__init__()
        
        # Basic fields
        self.version = version
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.hop_limit = hop_limit
        
        # Handle protocol alias
        if protocol is not None:
            self.next_header = protocol
        else:
            self.next_header = next_header
        
        # Traffic class handling
        if dscp is not None:
            self.traffic_class = (dscp << 2) | ecn
            self.dscp = dscp
            self.ecn = ecn
        else:
            self.traffic_class = traffic_class
            self.dscp = traffic_class >> 2
            self.ecn = traffic_class & 0x03
        
        # Flow label
        self.flow_label = flow_label
        if auto_flow_label and flow_label == 0:
            self.flow_label = random.randint(1, 0xFFFFF)  # 20 bits
        
        # Extension headers
        self.extension_headers = extension_headers or []
        
        # Payload
        self.payload = payload
        self.payload_length = payload_length
        self.auto_length = auto_length
        
        # Metadata
        self.interface = interface
        self.vlan_id = vlan_id
        
        # Validation
        self.strict_validation = strict_validation
    
    def _pack_ipv6_address(self, address: str) -> bytes:
        """Pack IPv6 address to 16 bytes"""
        try:
            return socket.inet_pton(socket.AF_INET6, address)
        except socket.error as e:
            raise PacketSerializationError(f"Invalid IPv6 address '{address}': {e}")
    
    def _unpack_ipv6_address(self, data: bytes) -> str:
        """Unpack IPv6 address from 16 bytes"""
        try:
            return socket.inet_ntop(socket.AF_INET6, data)
        except socket.error as e:
            raise PacketParsingError(f"Invalid IPv6 address data: {e}")
    
    def serialize(self) -> bytes:
        """
        Serialize IPv6 packet to bytes.
        
        Returns:
            bytes: Serialized packet data
            
        Raises:
            PacketSerializationError: If serialization fails
        """
        try:
            # Validate before serialization
            if self.strict_validation:
                self.validate()
            
            # Calculate payload length (includes extension headers)
            ext_headers_len = sum(len(data) for _, data in self.extension_headers)
            
            if self.auto_length or self.payload_length is None:
                self.payload_length = ext_headers_len + len(self.payload)
            
            # Build first word (version, traffic class, flow label)
            first_word = (self.version << 28) | (self.traffic_class << 20) | self.flow_label
            
            # Determine next header
            if self.extension_headers:
                next_header = self.extension_headers[0][0]
            else:
                next_header = self.next_header
            
            # Pack fixed header
            header = struct.pack('!IHBB',
                first_word,               # Version, TC, Flow Label
                self.payload_length,      # Payload Length
                next_header,              # Next Header
                self.hop_limit           # Hop Limit
            )
            
            # Add source and destination addresses
            header += self._pack_ipv6_address(self.src_ip)
            header += self._pack_ipv6_address(self.dst_ip)
            
            # Add extension headers
            ext_data = b''
            for i, (ext_type, ext_payload) in enumerate(self.extension_headers):
                # Determine next header
                if i < len(self.extension_headers) - 1:
                    next_hdr = self.extension_headers[i + 1][0]
                else:
                    next_hdr = self.next_header
                
                # Add extension header with next header field
                # Note: This is simplified - real extension headers have specific formats
                ext_data += struct.pack('!B', next_hdr) + ext_payload
            
            # Combine everything
            packet = header + ext_data + self.payload
            
            # Store raw data
            self._raw_data = bytearray(packet)
            self._update_size()
            
            return bytes(self._raw_data)
            
        except struct.error as e:
            raise PacketSerializationError(f"IPv6 serialization error: {e}")
        except Exception as e:
            raise PacketSerializationError(f"Unexpected error during IPv6 serialization: {e}")
    
    def deserialize(self, data: bytes):
        """
        Deserialize bytes to IPv6 packet.
        
        Args:
            data: Raw bytes to deserialize
            
        Raises:
            PacketParsingError: If parsing fails
        """
        if len(data) < self.HEADER_SIZE:
            raise PacketParsingError(
                f"IPv6 packet too short: {len(data)} bytes (minimum {self.HEADER_SIZE})"
            )
        
        try:
            # Unpack fixed header
            first_word, self.payload_length, self.next_header, self.hop_limit = \
                struct.unpack('!IHBB', data[:8])
            
            # Extract version, traffic class, flow label
            self.version = (first_word >> 28) & 0xF
            self.traffic_class = (first_word >> 20) & 0xFF
            self.flow_label = first_word & 0xFFFFF
            
            # Extract DSCP and ECN
            self.dscp = self.traffic_class >> 2
            self.ecn = self.traffic_class & 0x03
            
            # Extract addresses
            self.src_ip = self._unpack_ipv6_address(data[8:24])
            self.dst_ip = self._unpack_ipv6_address(data[24:40])
            
            # Extension headers parsing (simplified)
            self.extension_headers = []
            offset = 40
            current_header = self.next_header
            
            # List of extension header types
            extension_types = {0, 43, 44, 50, 51, 60, 135}
            
            while current_header in extension_types and offset < len(data):
                # Read extension header (simplified - real parsing is complex)
                if offset + 2 > len(data):
                    break
                
                next_hdr = data[offset]
                hdr_len = (data[offset + 1] + 1) * 8  # Length in 8-byte units
                
                if offset + hdr_len > len(data):
                    break
                
                ext_data = data[offset:offset + hdr_len]
                self.extension_headers.append((current_header, ext_data))
                
                current_header = next_hdr
                offset += hdr_len
            
            # Update next_header to the final protocol
            if self.extension_headers:
                self.next_header = current_header
            
            # Extract payload
            self.payload = data[offset:40 + self.payload_length]
            
            # Store raw data
            self._raw_data = bytearray(data[:40 + self.payload_length])
            self._update_size()
            
            # Mark as validated
            self.mark_validated(True)
            
        except struct.error as e:
            raise PacketParsingError(f"IPv6 deserialization error: {e}")
        except Exception as e:
            raise PacketParsingError(f"Unexpected error during IPv6 parsing: {e}")
    
    def validate(self) -> bool:
        """
        Validate IPv6 packet fields.
        
        Returns:
            bool: True if valid
            
        Raises:
            PacketValidationError: If validation fails
        """
        # Validate version
        if self.version != 6:
            raise PacketValidationError(f"Invalid IP version: {self.version} (must be 6)")
        
        # Validate traffic class
        if not (0 <= self.traffic_class <= 255):
            raise PacketValidationError(f"Invalid traffic class: {self.traffic_class}")
        
        # Validate flow label
        if not (0 <= self.flow_label <= 0xFFFFF):
            raise PacketValidationError(f"Invalid flow label: {self.flow_label}")
        
        # Validate hop limit
        if not (0 <= self.hop_limit <= 255):
            raise PacketValidationError(f"Invalid hop limit: {self.hop_limit}")
        
        # Validate next header
        if not (0 <= self.next_header <= 255):
            raise PacketValidationError(f"Invalid next header: {self.next_header}")
        
        # Validate IPv6 addresses
        try:
            socket.inet_pton(socket.AF_INET6, self.src_ip)
            socket.inet_pton(socket.AF_INET6, self.dst_ip)
        except socket.error:
            raise PacketValidationError("Invalid IPv6 address format")
        
        # Validate payload length
        if self.payload_length is not None:
            if self.payload_length > self.MAX_PAYLOAD_SIZE:
                raise PacketValidationError(
                    f"Payload length {self.payload_length} exceeds maximum {self.MAX_PAYLOAD_SIZE}"
                )
        
        self.mark_validated(True)
        return True
    
    def summary(self) -> str:
        """
        Return human-readable summary of IPv6 packet.
        
        Returns:
            str: Packet summary
        """
        proto_names = {
            6: "TCP", 17: "UDP", 58: "ICMPv6", 50: "ESP",
            51: "AH", 132: "SCTP", 41: "IPv6-in-IPv6"
        }
        
        proto = proto_names.get(self.next_header, f"Proto_{self.next_header}")
        
        # Compress IPv6 addresses for display
        src_short = self._compress_ipv6(self.src_ip)
        dst_short = self._compress_ipv6(self.dst_ip)
        
        summary = f"IPv6 {src_short} -> {dst_short} {proto}"
        summary += f" Hop={self.hop_limit}"
        
        if self.flow_label > 0:
            summary += f" Flow=0x{self.flow_label:05X}"
        
        if self.dscp > 0:
            summary += f" DSCP={self.dscp}"
        
        if self.extension_headers:
            summary += f" Ext={len(self.extension_headers)}"
        
        if self.payload:
            summary += f" [{len(self.payload)} bytes]"
        
        return summary
    
    def _compress_ipv6(self, address: str) -> str:
        """Compress IPv6 address for display"""
        try:
            # Use inet_pton/ntop to get compressed form
            packed = socket.inet_pton(socket.AF_INET6, address)
            compressed = socket.inet_ntop(socket.AF_INET6, packed)
            # Further shorten for display if very long
            if len(compressed) > 20:
                parts = compressed.split(':')
                if len(parts) > 4:
                    return f"{parts[0]}:{parts[1]}:...:{parts[-1]}"
            return compressed
        except:
            return address
    
    def get_next_header_name(self) -> str:
        """Get human-readable next header name"""
        headers = {
            0: "Hop-by-Hop", 1: "ICMPv4", 2: "IGMP", 4: "IP-in-IP", 6: "TCP",
            17: "UDP", 41: "IPv6", 43: "Routing", 44: "Fragment", 46: "RSVP",
            47: "GRE", 50: "ESP", 51: "AH", 58: "ICMPv6", 59: "None",
            60: "Destination Options", 89: "OSPF", 103: "PIM", 132: "SCTP",
            135: "Mobility"
        }
        return headers.get(self.next_header, f"Unknown ({self.next_header})")
    
    def has_extension_headers(self) -> bool:
        """Check if packet has extension headers"""
        return len(self.extension_headers) > 0
    
    def get_dscp_name(self) -> str:
        """Get DSCP class name"""
        dscp_names = {
            0: "Default", 8: "CS1", 10: "AF11", 12: "AF12", 14: "AF13",
            16: "CS2", 18: "AF21", 20: "AF22", 22: "AF23", 24: "CS3",
            26: "AF31", 28: "AF32", 30: "AF33", 32: "CS4", 34: "AF41",
            36: "AF42", 38: "AF43", 40: "CS5", 46: "EF", 48: "CS6", 56: "CS7"
        }
        return dscp_names.get(self.dscp, f"DSCP{self.dscp}")
    
    def is_link_local(self) -> bool:
        """Check if source or destination is link-local"""
        return (self.src_ip.startswith('fe80:') or 
                self.dst_ip.startswith('fe80:'))
    
    def is_multicast(self) -> bool:
        """Check if destination is multicast"""
        return self.dst_ip.startswith('ff')
    
    def is_loopback(self) -> bool:
        """Check if this is loopback traffic"""
        return self.src_ip == '::1' or self.dst_ip == '::1'
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert packet to dictionary representation.
        
        Returns:
            dict: Packet fields as dictionary
        """
        base_dict = super().to_dict()
        base_dict.update({
            "version": self.version,
            "traffic_class": self.traffic_class,
            "dscp": self.dscp,
            "dscp_name": self.get_dscp_name(),
            "ecn": self.ecn,
            "flow_label": f"0x{self.flow_label:05X}",
            "payload_length": self.payload_length,
            "next_header": self.next_header,
            "next_header_name": self.get_next_header_name(),
            "hop_limit": self.hop_limit,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "extension_headers_count": len(self.extension_headers),
            "payload_size": len(self.payload),
            "is_link_local": self.is_link_local(),
            "is_multicast": self.is_multicast(),
            "is_loopback": self.is_loopback()
        })
        return base_dict
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"IPv6Packet(src={self.src_ip}, dst={self.dst_ip}, "
            f"next_header={self.next_header}, hop_limit={self.hop_limit})"
        )


# Module exports
__all__ = ['IPv6Packet']