#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from core.packets.base.exceptions import PacketParsingError
from core.packets.base.exceptions import PacketSerializationError, PacketValidationError
"""
UDP Packet implementation for TECMP-Tool.
Provides complete UDP packet handling with all standard fields.
"""

from core.packets.base.exceptions import PacketParsingError, PacketSerializationError, PacketValidationError
from core.packets.base.packet import Packet
)


class UDPPacket(Packet):
    """
    Complete UDP packet implementation.
    
    UDP Header Format (8 bytes):
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |          Source Port          |       Destination Port        |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |            Length             |           Checksum            |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                             Data                              |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """
    
    # UDP header format: network byte order (big-endian)
    HEADER_FORMAT = '!HHHH'  # src_port, dst_port, length, checksum
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 8 bytes
    MIN_LENGTH = HEADER_SIZE  # Minimum UDP datagram length
    MAX_LENGTH = 65535  # Maximum UDP datagram length (including IP header)
    MAX_UDP_LENGTH = 65507  # Maximum UDP length (65535 - 20 (IP) - 8 (UDP))
    
    def __init__(
        self,
        # === MANDATORY FIELDS ===
        src_port: int,
        dst_port: int,
        
        # === OPTIONAL FIELDS ===
        length: Optional[int] = None,      # Auto-calculated if None
        checksum: int = 0,                 # 0 = no checksum (optional for IPv4)
        payload: Union[bytes, str] = b'',  # UDP payload data
        
        # === AUTO-CALCULATION FLAGS ===
        auto_length: bool = True,          # Auto-calculate length field
        auto_checksum: bool = False,       # Auto-calculate checksum (requires IP layer)
        
        # === METADATA ===
        interface: Optional[str] = None,   # Source interface
        vlan_id: Optional[int] = None,     # VLAN tag if applicable
        
        # === VALIDATION ===
        strict_validation: bool = True     # Enforce strict RFC compliance
    ):
        """
        Initialize UDP packet.
        
        Args:
            src_port: Source port number (0-65535)
            dst_port: Destination port number (0-65535)
            length: Total length of UDP datagram (header + data)
            checksum: UDP checksum (0 = disabled)
            payload: Data payload as bytes or string
            auto_length: Automatically calculate length field
            auto_checksum: Automatically calculate checksum
            interface: Source interface name
            vlan_id: VLAN ID if applicable
            strict_validation: Enable strict validation
        """
        super().__init__()
        
        # Port numbers
        self.src_port = src_port
        self.dst_port = dst_port
        
        # Length and checksum
        self.length = length
        self.checksum = checksum
        
        # Payload handling
        if isinstance(payload, str):
            self.payload = payload.encode('utf-8')
        elif isinstance(payload, bytes):
            self.payload = payload
        else:
            self.payload = b''
        
        # Auto-calculation flags
        self.auto_length = auto_length
        self.auto_checksum = auto_checksum
        
        # Metadata
        self.interface = interface
        self.vlan_id = vlan_id
        
        # Validation
        self.strict_validation = strict_validation
        
        # Calculate length if needed
        if self.auto_length or self.length is None:
            self._calculate_length()
        
        # Store original values for comparison
        self._original_src_port = src_port
        self._original_dst_port = dst_port
    
    def _calculate_length(self):
        """Calculate UDP length field (header + payload)"""
        self.length = self.HEADER_SIZE + len(self.payload)
    
    def serialize(self) -> bytes:
        """
        Serialize UDP packet to bytes.
        
        Returns:
            bytes: Serialized packet data
            
        Raises:
            PacketSerializationError: If serialization fails
        """
        try:
            # Auto-calculate length if needed
            if self.auto_length:
                self._calculate_length()
            
            # Validate before serialization
            if self.strict_validation:
                self.validate()
            
            # Pack UDP header
            header = struct.pack(
                self.HEADER_FORMAT,
                self.src_port,
                self.dst_port,
                self.length,
                self.checksum
            )
            
            # Combine header and payload
            packet_data = header + self.payload
            
            # Store raw data
            self._raw_data = bytearray(packet_data)
            self._update_size()
            
            return bytes(self._raw_data)
            
        except struct.error as e:
            raise PacketSerializationError(f"UDP serialization error: {e}")
        except Exception as e:
            raise PacketSerializationError(f"Unexpected error during UDP serialization: {e}")
    
    def deserialize(self, data: bytes):
        """
        Deserialize bytes to UDP packet.
        
        Args:
            data: Raw bytes to deserialize
            
        Raises:
            PacketParsingError: If parsing fails
        """
        if len(data) < self.HEADER_SIZE:
            raise PacketParsingError(
                f"UDP packet too short: {len(data)} bytes (minimum {self.HEADER_SIZE})"
            )
        
        try:
            # Unpack UDP header
            header_data = data[:self.HEADER_SIZE]
            (
                self.src_port,
                self.dst_port,
                self.length,
                self.checksum
            ) = struct.unpack(self.HEADER_FORMAT, header_data)
            
            # Extract payload
            self.payload = data[self.HEADER_SIZE:]
            
            # Verify length field
            actual_length = self.HEADER_SIZE + len(self.payload)
            if self.length != actual_length and self.strict_validation:
                self._logger.warning(
                    f"UDP length mismatch: header says {self.length}, "
                    f"actual is {actual_length}"
                )
            
            # Store raw data
            self._raw_data = bytearray(data)
            self._update_size()
            
            # Mark as validated since we successfully parsed it
            self.mark_validated(True)
            
        except struct.error as e:
            raise PacketParsingError(f"UDP deserialization error: {e}")
        except Exception as e:
            raise PacketParsingError(f"Unexpected error during UDP parsing: {e}")
    
    def validate(self) -> bool:
        """
        Validate UDP packet fields.
        
        Returns:
            bool: True if valid
            
        Raises:
            PacketValidationError: If validation fails
        """
        # Validate port numbers
        if not (0 <= self.src_port <= 65535):
            raise PacketValidationError(f"Invalid source port: {self.src_port}")
        
        if not (0 <= self.dst_port <= 65535):
            raise PacketValidationError(f"Invalid destination port: {self.dst_port}")
        
        # Validate length
        if self.length is not None:
            if not (self.MIN_LENGTH <= self.length <= self.MAX_LENGTH):
                raise PacketValidationError(
                    f"Invalid UDP length: {self.length} "
                    f"(must be {self.MIN_LENGTH}-{self.MAX_LENGTH})"
                )
            
            # Check length consistency
            expected_length = self.HEADER_SIZE + len(self.payload)
            if self.length != expected_length:
                raise PacketValidationError(
                    f"Length mismatch: field says {self.length}, "
                    f"but header+payload is {expected_length}"
                )
        
        # Validate checksum
        if not (0 <= self.checksum <= 65535):
            raise PacketValidationError(f"Invalid checksum: {self.checksum}")
        
        # Check payload size
        if len(self.payload) > (self.MAX_UDP_LENGTH - self.HEADER_SIZE):
            raise PacketValidationError(
                f"Payload too large: {len(self.payload)} bytes "
                f"(max {self.MAX_UDP_LENGTH - self.HEADER_SIZE})"
            )
        
        self.mark_validated(True)
        return True
    
    def summary(self) -> str:
        """
        Return human-readable summary of UDP packet.
        
        Returns:
            str: Packet summary
        """
        checksum_str = f"0x{self.checksum:04x}" if self.checksum else "disabled"
        payload_info = f" [{len(self.payload)} bytes]" if self.payload else " [empty]"
        
        return (
            f"UDP {self.src_port}->{self.dst_port} "
            f"len={self.length} chksum={checksum_str}{payload_info}"
        )
    
    def calculate_checksum(self, src_ip: str, dst_ip: str) -> int:
        """
        Calculate UDP checksum including pseudo-header.
        
        Args:
            src_ip: Source IP address
            dst_ip: Destination IP address
            
        Returns:
            int: Calculated checksum
            
        Note:
            This requires IP layer information for the pseudo-header
        """
        # Build pseudo-header (for IPv4)
        import socket
        
        pseudo_header = b''
        pseudo_header += socket.inet_aton(src_ip)  # Source IP
        pseudo_header += socket.inet_aton(dst_ip)  # Destination IP
        pseudo_header += struct.pack('!BBH', 0, 17, self.length)  # Zero, Protocol (17=UDP), Length
        
        # Build UDP packet with zero checksum
        udp_header = struct.pack(
            self.HEADER_FORMAT,
            self.src_port,
            self.dst_port,
            self.length,
            0  # Zero checksum for calculation
        )
        
        # Combine pseudo-header + UDP header + payload
        data = pseudo_header + udp_header + self.payload
        
        return self.calculate_checksum(data)
    
    def set_checksum(self, checksum: int):
        """
        Set UDP checksum value.
        
        Args:
            checksum: Checksum value (0 to disable)
        """
        if not (0 <= checksum <= 65535):
            raise ValueError(f"Invalid checksum value: {checksum}")
        self.checksum = checksum
    
    def get_payload_as_string(self, encoding: str = 'utf-8') -> str:
        """
        Get payload as string.
        
        Args:
            encoding: Character encoding
            
        Returns:
            str: Decoded payload
        """
        try:
            return self.payload.decode(encoding)
        except UnicodeDecodeError:
            # Return hex representation if not decodable
            return self.payload.hex()
    
    def set_payload_from_string(self, data: str, encoding: str = 'utf-8'):
        """
        Set payload from string.
        
        Args:
            data: String data
            encoding: Character encoding
        """
        self.payload = data.encode(encoding)
        if self.auto_length:
            self._calculate_length()
    
    def is_broadcast(self) -> bool:
        """
        Check if this is likely a broadcast packet.
        
        Returns:
            bool: True if broadcast characteristics detected
        """
        # Common broadcast ports
        broadcast_ports = {67, 68, 137, 138, 1900, 5353}
        return (self.dst_port in broadcast_ports or 
                self.src_port in broadcast_ports)
    
    def is_multicast(self) -> bool:
        """
        Check if this is likely a multicast packet.
        
        Returns:
            bool: True if multicast characteristics detected
        """
        # Common multicast ports
        multicast_ports = {5353, 1900, 3702}  # mDNS, SSDP, WS-Discovery
        return (self.dst_port in multicast_ports or 
                self.src_port in multicast_ports)
    
    def get_service_name(self) -> Optional[str]:
        """
        Get common service name for the destination port.
        
        Returns:
            Optional[str]: Service name or None
        """
        services = {
            53: "DNS",
            67: "DHCP Server",
            68: "DHCP Client",
            69: "TFTP",
            123: "NTP",
            137: "NetBIOS Name",
            138: "NetBIOS Datagram",
            161: "SNMP",
            162: "SNMP Trap",
            514: "Syslog",
            1900: "SSDP",
            5353: "mDNS",
            5060: "SIP",
            6343: "sFlow",
            9092: "Kafka"
        }
        return services.get(self.dst_port) or services.get(self.src_port)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert packet to dictionary representation.
        
        Returns:
            dict: Packet fields as dictionary
        """
        base_dict = super().to_dict()
        base_dict.update({
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "length": self.length,
            "checksum": self.checksum,
            "payload_size": len(self.payload),
            "service": self.get_service_name()
        })
        return base_dict
    
    def __eq__(self, other) -> bool:
        """Compare UDP packets for equality"""
        if not isinstance(other, UDPPacket):
            return False
        return (
            self.src_port == other.src_port and
            self.dst_port == other.dst_port and
            self.length == other.length and
            self.checksum == other.checksum and
            self.payload == other.payload
        )
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"UDPPacket(src_port={self.src_port}, dst_port={self.dst_port}, "
            f"length={self.length}, checksum={self.checksum}, "
            f"payload_size={len(self.payload)})"
        )


# Module exports
__all__ = ['UDPPacket']