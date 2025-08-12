#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARP (Address Resolution Protocol) Packet implementation for TECMP-Tool.
Provides complete ARP packet handling for IPv4 address resolution.
"""
from core.packets.base.packet import Packet
from core.exceptions.exceptions import (
    PacketParsingError,
    PacketSerializationError,
    PacketValidationError,
)

import struct
import socket
from typing import Optional, Dict, Any, Union


class ARPPacket(Packet):
    """
    ARP Packet implementation (RFC 826).
    
    ARP Header Format (28 bytes for Ethernet/IPv4):
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |         Hardware Type         |         Protocol Type         |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    | HW Addr Len   | Proto Addr Len|           Operation           |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                    Sender Hardware Address                    |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |      Sender Hardware Address  |    Sender Protocol Address    |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |    Sender Protocol Address    |    Target Hardware Address    |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                    Target Hardware Address                    |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                    Target Protocol Address                    |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """
    
    # ARP header format
    HEADER_FORMAT = '!HHBBH'  # hw_type, proto_type, hw_len, proto_len, operation
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 8 bytes
    
    # Hardware types
    HW_TYPE_ETHERNET = 1
    HW_TYPE_IEEE802 = 6
    HW_TYPE_ARCNET = 7
    HW_TYPE_FRAME_RELAY = 15
    HW_TYPE_ATM = 16
    HW_TYPE_HDLC = 17
    HW_TYPE_FIBRE_CHANNEL = 18
    HW_TYPE_ATM2 = 19
    HW_TYPE_SERIAL = 20
    
    # Protocol types
    PROTO_TYPE_IP = 0x0800  # IPv4
    
    # Operations
    OP_REQUEST = 1
    OP_REPLY = 2
    OP_RARP_REQUEST = 3
    OP_RARP_REPLY = 4
    OP_DRARP_REQUEST = 5
    OP_DRARP_REPLY = 6
    OP_DRARP_ERROR = 7
    OP_INARP_REQUEST = 8
    OP_INARP_REPLY = 9
    
    # Standard lengths
    ETHERNET_HW_LEN = 6  # MAC address length
    IPV4_PROTO_LEN = 4   # IPv4 address length
    
    def __init__(
        self,
        # === COMPATIBILITY NAMES (from packet_factory) ===
        src_mac: Optional[str] = None,
        src_ip: Optional[str] = None,
        dst_mac: Optional[str] = None,
        dst_ip: Optional[str] = None,
        op: Optional[int] = None,
        
        # === STANDARD ARP FIELDS ===
        hw_type: int = HW_TYPE_ETHERNET,
        proto_type: int = PROTO_TYPE_IP,
        hw_len: int = ETHERNET_HW_LEN,
        proto_len: int = IPV4_PROTO_LEN,
        operation: Optional[int] = None,
        
        # === EXPLICIT FIELD NAMES ===
        sender_mac: Optional[str] = None,
        sender_ip: Optional[str] = None,
        target_mac: Optional[str] = None,
        target_ip: Optional[str] = None,
        
        # === ALTERNATE NAMES ===
        sender_hw_addr: Optional[str] = None,
        sender_proto_addr: Optional[str] = None,
        target_hw_addr: Optional[str] = None,
        target_proto_addr: Optional[str] = None,
        
        # === METADATA ===
        interface: Optional[str] = None,
        vlan_id: Optional[int] = None,
        is_gratuitous: bool = False,
        
        # === VALIDATION ===
        strict_validation: bool = True
    ):
        """
        Initialize ARP packet with multiple naming conventions for compatibility.
        
        Args:
            src_mac/sender_mac/sender_hw_addr: Sender MAC address
            src_ip/sender_ip/sender_proto_addr: Sender IP address
            dst_mac/target_mac/target_hw_addr: Target MAC address
            dst_ip/target_ip/target_proto_addr: Target IP address
            op/operation: ARP operation (1=request, 2=reply)
            hw_type: Hardware type
            proto_type: Protocol type
            hw_len: Hardware address length
            proto_len: Protocol address length
            interface: Network interface
            vlan_id: VLAN ID if applicable
            is_gratuitous: Whether this is a gratuitous ARP
            strict_validation: Enable strict validation
        """
        super().__init__()
        
        # Resolve naming conflicts - prioritize explicit names
        self.sender_mac = sender_mac or sender_hw_addr or src_mac or "00:00:00:00:00:00"
        self.sender_ip = sender_ip or sender_proto_addr or src_ip or "0.0.0.0"
        self.target_mac = target_mac or target_hw_addr or dst_mac or "00:00:00:00:00:00"
        self.target_ip = target_ip or target_proto_addr or dst_ip or "0.0.0.0"
        
        # Operation
        self.operation = operation or op or self.OP_REQUEST
        
        # Hardware and protocol info
        self.hw_type = hw_type
        self.proto_type = proto_type
        self.hw_len = hw_len
        self.proto_len = proto_len
        
        # Metadata
        self.interface = interface
        self.vlan_id = vlan_id
        self.is_gratuitous = is_gratuitous
        
        # Validation
        self.strict_validation = strict_validation
        
        # Normalize MAC addresses
        self._normalize_mac_addresses()
        
        # Check for gratuitous ARP
        if not is_gratuitous:
            self._check_gratuitous()
    
    def _normalize_mac_addresses(self):
        """Normalize MAC address format to XX:XX:XX:XX:XX:XX"""
        self.sender_mac = self._normalize_mac(self.sender_mac)
        self.target_mac = self._normalize_mac(self.target_mac)
    
    def _normalize_mac(self, mac: str) -> str:
        """Normalize a single MAC address"""
        if not mac:
            return "00:00:00:00:00:00"
        
        # Remove common separators and convert to uppercase
        mac = mac.upper().replace(':', '').replace('-', '').replace('.', '')
        
        # Ensure 12 hex digits
        if len(mac) != 12 or not all(c in '0123456789ABCDEF' for c in mac):
            return "00:00:00:00:00:00"
        
        # Format as XX:XX:XX:XX:XX:XX
        return ':'.join(mac[i:i+2] for i in range(0, 12, 2))
    
    def _check_gratuitous(self):
        """Check if this is a gratuitous ARP"""
        # Gratuitous ARP: sender IP == target IP
        if self.sender_ip == self.target_ip and self.sender_ip != "0.0.0.0":
            self.is_gratuitous = True
    
    def _mac_to_bytes(self, mac: str) -> bytes:
        """Convert MAC address string to bytes"""
        return bytes.fromhex(mac.replace(':', ''))
    
    def _bytes_to_mac(self, data: bytes) -> str:
        """Convert bytes to MAC address string"""
        return ':'.join(f'{b:02X}' for b in data)
    
    def _ip_to_bytes(self, ip: str) -> bytes:
        """Convert IP address string to bytes"""
        try:
            return socket.inet_aton(ip)
        except socket.error:
            return b'\x00\x00\x00\x00'
    
    def _bytes_to_ip(self, data: bytes) -> str:
        """Convert bytes to IP address string"""
        try:
            return socket.inet_ntoa(data)
        except socket.error:
            return "0.0.0.0"
    
    def serialize(self) -> bytes:
        """
        Serialize ARP packet to bytes.
        
        Returns:
            bytes: Serialized packet data
            
        Raises:
            PacketSerializationError: If serialization fails
        """
        try:
            # Validate before serialization
            if self.strict_validation:
                self.validate()
            
            # Pack ARP header
            header = struct.pack(
                self.HEADER_FORMAT,
                self.hw_type,
                self.proto_type,
                self.hw_len,
                self.proto_len,
                self.operation
            )
            
            # Pack addresses
            addresses = b''
            addresses += self._mac_to_bytes(self.sender_mac)
            addresses += self._ip_to_bytes(self.sender_ip)
            addresses += self._mac_to_bytes(self.target_mac)
            addresses += self._ip_to_bytes(self.target_ip)
            
            # Combine header and addresses
            arp_data = header + addresses
            
            # Store raw data
            self._raw_data = bytearray(arp_data)
            self._update_size()
            
            return bytes(self._raw_data)
            
        except struct.error as e:
            raise PacketSerializationError(f"ARP serialization error: {e}")
        except Exception as e:
            raise PacketSerializationError(f"Unexpected error during ARP serialization: {e}")
    
    def deserialize(self, data: bytes):
        """
        Deserialize bytes to ARP packet.
        
        Args:
            data: Raw bytes to deserialize
            
        Raises:
            PacketParsingError: If parsing fails
        """
        min_size = self.HEADER_SIZE + (self.ETHERNET_HW_LEN * 2) + (self.IPV4_PROTO_LEN * 2)
        if len(data) < min_size:
            raise PacketParsingError(
                f"ARP packet too short: {len(data)} bytes (minimum {min_size})"
            )
        
        try:
            # Unpack ARP header
            header_data = data[:self.HEADER_SIZE]
            (
                self.hw_type,
                self.proto_type,
                self.hw_len,
                self.proto_len,
                self.operation
            ) = struct.unpack(self.HEADER_FORMAT, header_data)
            
            # Calculate expected size
            expected_size = self.HEADER_SIZE + (self.hw_len * 2) + (self.proto_len * 2)
            if len(data) < expected_size:
                raise PacketParsingError(f"ARP packet too short for declared lengths")
            
            # Extract addresses
            offset = self.HEADER_SIZE
            
            # Sender hardware address
            sender_hw = data[offset:offset + self.hw_len]
            self.sender_mac = self._bytes_to_mac(sender_hw) if self.hw_len == 6 else sender_hw.hex()
            offset += self.hw_len
            
            # Sender protocol address
            sender_proto = data[offset:offset + self.proto_len]
            self.sender_ip = self._bytes_to_ip(sender_proto) if self.proto_len == 4 else sender_proto.hex()
            offset += self.proto_len
            
            # Target hardware address
            target_hw = data[offset:offset + self.hw_len]
            self.target_mac = self._bytes_to_mac(target_hw) if self.hw_len == 6 else target_hw.hex()
            offset += self.hw_len
            
            # Target protocol address
            target_proto = data[offset:offset + self.proto_len]
            self.target_ip = self._bytes_to_ip(target_proto) if self.proto_len == 4 else target_proto.hex()
            
            # Check for gratuitous ARP
            self._check_gratuitous()
            
            # Store raw data
            self._raw_data = bytearray(data[:expected_size])
            self._update_size()
            
            # Mark as validated
            self.mark_validated(True)
            
        except struct.error as e:
            raise PacketParsingError(f"ARP deserialization error: {e}")
        except Exception as e:
            raise PacketParsingError(f"Unexpected error during ARP parsing: {e}")
    
    def validate(self) -> bool:
        """
        Validate ARP packet fields.
        
        Returns:
            bool: True if valid
            
        Raises:
            PacketValidationError: If validation fails
        """
        # Validate hardware type
        valid_hw_types = [
            self.HW_TYPE_ETHERNET, self.HW_TYPE_IEEE802, self.HW_TYPE_ARCNET,
            self.HW_TYPE_FRAME_RELAY, self.HW_TYPE_ATM, self.HW_TYPE_HDLC
        ]
        if self.strict_validation and self.hw_type not in valid_hw_types:
            raise PacketValidationError(f"Invalid hardware type: {self.hw_type}")
        
        # Validate protocol type
        if self.proto_type not in [self.PROTO_TYPE_IP]:
            self._logger.warning(f"Unusual protocol type: 0x{self.proto_type:04X}")
        
        # Validate operation
        valid_operations = [
            self.OP_REQUEST, self.OP_REPLY, self.OP_RARP_REQUEST, self.OP_RARP_REPLY,
            self.OP_DRARP_REQUEST, self.OP_DRARP_REPLY, self.OP_DRARP_ERROR,
            self.OP_INARP_REQUEST, self.OP_INARP_REPLY
        ]
        if self.operation not in valid_operations:
            raise PacketValidationError(f"Invalid operation: {self.operation}")
        
        # Validate address lengths
        if self.hw_type == self.HW_TYPE_ETHERNET and self.hw_len != 6:
            raise PacketValidationError(f"Invalid hardware length for Ethernet: {self.hw_len}")
        
        if self.proto_type == self.PROTO_TYPE_IP and self.proto_len != 4:
            raise PacketValidationError(f"Invalid protocol length for IPv4: {self.proto_len}")
        
        # Validate MAC addresses format
        mac_pattern = r'^[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}$'
        import re
        if not re.match(mac_pattern, self.sender_mac):
            raise PacketValidationError(f"Invalid sender MAC: {self.sender_mac}")
        if not re.match(mac_pattern, self.target_mac):
            raise PacketValidationError(f"Invalid target MAC: {self.target_mac}")
        
        # Validate IP addresses
        try:
            socket.inet_aton(self.sender_ip)
            socket.inet_aton(self.target_ip)
        except socket.error:
            raise PacketValidationError("Invalid IP address format")
        
        self.mark_validated(True)
        return True
    
    def summary(self) -> str:
        """
        Return human-readable summary of ARP packet.
        
        Returns:
            str: Packet summary
        """
        op_names = {
            self.OP_REQUEST: "REQUEST",
            self.OP_REPLY: "REPLY",
            self.OP_RARP_REQUEST: "RARP_REQ",
            self.OP_RARP_REPLY: "RARP_REPLY"
        }
        
        op_str = op_names.get(self.operation, f"OP_{self.operation}")
        
        if self.is_gratuitous:
            return f"ARP {op_str} (Gratuitous) {self.sender_mac} -> {self.sender_ip}"
        elif self.operation == self.OP_REQUEST:
            return f"ARP {op_str} Who has {self.target_ip}? Tell {self.sender_ip}"
        elif self.operation == self.OP_REPLY:
            return f"ARP {op_str} {self.sender_ip} is at {self.sender_mac}"
        else:
            return f"ARP {op_str} {self.sender_mac}/{self.sender_ip} -> {self.target_mac}/{self.target_ip}"
    
    def is_request(self) -> bool:
        """Check if this is an ARP request"""
        return self.operation == self.OP_REQUEST
    
    def is_reply(self) -> bool:
        """Check if this is an ARP reply"""
        return self.operation == self.OP_REPLY
    
    def get_operation_name(self) -> str:
        """Get human-readable operation name"""
        op_names = {
            self.OP_REQUEST: "Request",
            self.OP_REPLY: "Reply",
            self.OP_RARP_REQUEST: "RARP Request",
            self.OP_RARP_REPLY: "RARP Reply",
            self.OP_DRARP_REQUEST: "DRARP Request",
            self.OP_DRARP_REPLY: "DRARP Reply",
            self.OP_DRARP_ERROR: "DRARP Error",
            self.OP_INARP_REQUEST: "InARP Request",
            self.OP_INARP_REPLY: "InARP Reply"
        }
        return op_names.get(self.operation, f"Unknown ({self.operation})")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert packet to dictionary representation.
        
        Returns:
            dict: Packet fields as dictionary
        """
        base_dict = super().to_dict()
        base_dict.update({
            "hw_type": self.hw_type,
            "proto_type": f"0x{self.proto_type:04X}",
            "hw_len": self.hw_len,
            "proto_len": self.proto_len,
            "operation": self.operation,
            "operation_name": self.get_operation_name(),
            "sender_mac": self.sender_mac,
            "sender_ip": self.sender_ip,
            "target_mac": self.target_mac,
            "target_ip": self.target_ip,
            "is_gratuitous": self.is_gratuitous
        })
        return base_dict
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"ARPPacket(operation={self.operation}, "
            f"sender={self.sender_mac}/{self.sender_ip}, "
            f"target={self.target_mac}/{self.target_ip})"
        )


# Module exports
__all__ = ['ARPPacket']