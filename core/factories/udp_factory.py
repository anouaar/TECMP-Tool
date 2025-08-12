#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDP Packet Factory for creating and managing UDP packets.
Provides convenient methods for creating various UDP packet types.
"""

import struct
import random
from typing import Optional, Dict, Any, List, Union, Tuple
from datetime import datetime

# Import UDP packet from the transport module
from core.packets.transport.udp import UDPPacket
from core.packets.base.packet import Packet


class UDPFactory:
    """
    Factory class for creating UDP packets with various configurations.
    Provides static methods for common UDP packet types and conversions.
    """
    
    # Default values
    DEFAULT_PAYLOAD = b''
    EPHEMERAL_PORT_RANGE = (49152, 65535)
    
    # Common UDP port numbers
    COMMON_PORTS = {
        'dns': 53,
        'dhcp-server': 67,
        'dhcp-client': 68,
        'tftp': 69,
        'ntp': 123,
        'netbios-ns': 137,
        'netbios-dgm': 138,
        'snmp': 161,
        'snmp-trap': 162,
        'syslog': 514,
        'rip': 520,
        'radius': 1812,
        'radius-acct': 1813,
        'ssdp': 1900,
        'openvpn': 1194,
        'l2tp': 1701,
        'mqtt': 1883,
        'coap': 5683,
        'mdns': 5353,
        'sip': 5060,
        'rtp': 5004,
        'rtcp': 5005,
        'sflow': 6343,
        'kafka': 9092
    }
    
    @staticmethod
    def create_udp_packet(**kwargs) -> UDPPacket:
        """
        Create a generic UDP packet with provided parameters.
        
        Args:
            **kwargs: All parameters accepted by UDPPacket constructor
            
        Returns:
            UDPPacket: Configured UDP packet instance
        """
        return UDPPacket(**kwargs)
    
    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> UDPPacket:
        """
        Create UDP packet from configuration dictionary (e.g., from UI dialog).
        
        Args:
            config: Configuration dictionary with UDP parameters
            
        Returns:
            UDPPacket: Configured UDP packet instance
        """
        # Extract and convert parameters
        packet_params = {}
        
        # Port numbers
        packet_params['src_port'] = int(config.get('src_port', 0))
        packet_params['dst_port'] = int(config.get('dst_port', 0))
        
        # Length and checksum
        if 'length' in config:
            packet_params['length'] = int(config['length'])
        else:
            packet_params['length'] = None  # Will be auto-calculated
            
        packet_params['checksum'] = int(config.get('checksum', 0))
        
        # Payload handling
        if 'payload' in config:
            payload = config['payload']
            if isinstance(payload, str):
                # Check if it's hex format
                if payload.startswith('0x') or all(c in '0123456789abcdefABCDEF ' for c in payload):
                    try:
                        payload = payload.replace(' ', '').replace('0x', '')
                        packet_params['payload'] = bytes.fromhex(payload)
                    except ValueError:
                        # Not valid hex, treat as string
                        packet_params['payload'] = payload.encode('utf-8')
                else:
                    packet_params['payload'] = payload.encode('utf-8')
            elif isinstance(payload, bytes):
                packet_params['payload'] = payload
            else:
                packet_params['payload'] = b''
        
        # Auto-calculation flags
        packet_params['auto_length'] = config.get('auto_length', True)
        packet_params['auto_checksum'] = config.get('auto_checksum', False)
        
        # Metadata
        if 'interface' in config:
            packet_params['interface'] = config['interface']
        if 'vlan_id' in config:
            packet_params['vlan_id'] = config['vlan_id']
            
        # Validation
        packet_params['strict_validation'] = config.get('strict_validation', True)
        
        return UDPPacket(**packet_params)
    
    @staticmethod
    def create_dns_query(
        query_name: str,
        query_type: str = 'A',
        src_port: Optional[int] = None,
        dst_port: int = 53,
        transaction_id: Optional[int] = None
    ) -> UDPPacket:
        """
        Create a UDP packet containing a DNS query.
        
        Args:
            query_name: Domain name to query
            query_type: DNS query type (A, AAAA, MX, etc.)
            src_port: Source port (random if None)
            dst_port: Destination port (default 53)
            transaction_id: DNS transaction ID (random if None)
            
        Returns:
            UDPPacket: UDP packet with DNS query payload
        """
        if src_port is None:
            src_port = random.randint(*UDPFactory.EPHEMERAL_PORT_RANGE)
            
        if transaction_id is None:
            transaction_id = random.randint(0, 65535)
        
        # DNS query types
        query_types = {
            'A': 1, 'NS': 2, 'CNAME': 5, 'SOA': 6,
            'PTR': 12, 'MX': 15, 'TXT': 16, 'AAAA': 28
        }
        qtype = query_types.get(query_type.upper(), 1)
        
        # Build DNS query
        dns_payload = struct.pack('!HHHHHH',
            transaction_id,  # Transaction ID
            0x0100,         # Flags: Standard query
            1,              # Questions
            0,              # Answers
            0,              # Authority
            0               # Additional
        )
        
        # Encode domain name
        for part in query_name.split('.'):
            dns_payload += struct.pack('!B', len(part)) + part.encode()
        dns_payload += b'\x00'  # End of name
        
        # Query type and class
        dns_payload += struct.pack('!HH', qtype, 1)  # Type and Class (IN)
        
        return UDPPacket(
            src_port=src_port,
            dst_port=dst_port,
            payload=dns_payload
        )
    
    @staticmethod
    def create_dhcp_discover(
        src_port: int = 68,
        dst_port: int = 67,
        mac_address: str = "00:11:22:33:44:55",
        transaction_id: Optional[int] = None
    ) -> UDPPacket:
        """
        Create a UDP packet containing a DHCP DISCOVER message.
        
        Args:
            src_port: Source port (default 68)
            dst_port: Destination port (default 67)
            mac_address: Client MAC address
            transaction_id: DHCP transaction ID
            
        Returns:
            UDPPacket: UDP packet with DHCP DISCOVER payload
        """
        if transaction_id is None:
            transaction_id = random.randint(0, 0xFFFFFFFF)
        
        # Convert MAC address
        mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
        
        # DHCP DISCOVER packet
        dhcp_payload = struct.pack('!BBBBIHH',
            1,              # Message type: BOOTREQUEST
            1,              # Hardware type: Ethernet
            6,              # Hardware address length
            0,              # Hops
            transaction_id, # Transaction ID
            0,              # Seconds elapsed
            0x8000          # Flags: Broadcast
        )
        
        # Add IP addresses (ciaddr, yiaddr, siaddr, giaddr)
        dhcp_payload += struct.pack('!IIII', 0, 0, 0, 0)
        
        # Client MAC address + padding
        dhcp_payload += mac_bytes + b'\x00' * 10
        
        # Server hostname and boot filename (zeros)
        dhcp_payload += b'\x00' * 192
        
        # Magic cookie
        dhcp_payload += b'\x63\x82\x53\x63'
        
        # DHCP options
        dhcp_payload += b'\x35\x01\x01'  # Option 53: DHCP Discover
        dhcp_payload += b'\xff'           # End option
        
        return UDPPacket(
            src_port=src_port,
            dst_port=dst_port,
            payload=dhcp_payload
        )
    
    @staticmethod
    def create_ntp_request(
        src_port: Optional[int] = None,
        dst_port: int = 123
    ) -> UDPPacket:
        """
        Create a UDP packet containing an NTP request.
        
        Args:
            src_port: Source port (random if None)
            dst_port: Destination port (default 123)
            
        Returns:
            UDPPacket: UDP packet with NTP request payload
        """
        if src_port is None:
            src_port = random.randint(*UDPFactory.EPHEMERAL_PORT_RANGE)
        
        # NTP packet (48 bytes)
        # LI=0, VN=3, Mode=3 (client)
        ntp_payload = struct.pack('!BBBb', 0x1b, 0, 0, 0)
        ntp_payload += b'\x00' * 44  # Rest of NTP packet
        
        return UDPPacket(
            src_port=src_port,
            dst_port=dst_port,
            payload=ntp_payload
        )
    
    @staticmethod
    def create_syslog_message(
        message: str,
        facility: int = 16,  # Local0
        severity: int = 6,   # Info
        src_port: Optional[int] = None,
        dst_port: int = 514
    ) -> UDPPacket:
        """
        Create a UDP packet containing a syslog message.
        
        Args:
            message: Syslog message text
            facility: Syslog facility (0-23)
            severity: Syslog severity (0-7)
            src_port: Source port (random if None)
            dst_port: Destination port (default 514)
            
        Returns:
            UDPPacket: UDP packet with syslog payload
        """
        if src_port is None:
            src_port = random.randint(*UDPFactory.EPHEMERAL_PORT_RANGE)
        
        # Calculate priority
        priority = facility * 8 + severity
        
        # Format syslog message
        timestamp = datetime.now().strftime('%b %d %H:%M:%S')
        hostname = 'udpfactory'
        syslog_msg = f"<{priority}>{timestamp} {hostname} {message}"
        
        return UDPPacket(
            src_port=src_port,
            dst_port=dst_port,
            payload=syslog_msg.encode('utf-8')
        )
    
    @staticmethod
    def create_snmp_get_request(
        oid: str = "1.3.6.1.2.1.1.1.0",  # sysDescr
        community: str = "public",
        src_port: Optional[int] = None,
        dst_port: int = 161
    ) -> UDPPacket:
        """
        Create a UDP packet containing an SNMP GET request.
        
        Args:
            oid: Object Identifier to query
            community: SNMP community string
            src_port: Source port (random if None)
            dst_port: Destination port (default 161)
            
        Returns:
            UDPPacket: UDP packet with SNMP GET request
        """
        if src_port is None:
            src_port = random.randint(*UDPFactory.EPHEMERAL_PORT_RANGE)
        
        # Simple SNMP v1 GET request (simplified)
        # This is a basic implementation
        request_id = random.randint(1, 0x7FFFFFFF)
        
        # Build a simplified SNMP packet
        # Note: Real SNMP encoding is complex (ASN.1 BER)
        snmp_payload = b'\x30'  # SEQUENCE
        snmp_payload += b'\x00'  # Length (placeholder)
        snmp_payload += b'\x02\x01\x00'  # Version: SNMPv1
        snmp_payload += b'\x04' + bytes([len(community)]) + community.encode()
        snmp_payload += b'\xa0'  # GetRequest PDU
        # ... (simplified for demonstration)
        
        return UDPPacket(
            src_port=src_port,
            dst_port=dst_port,
            payload=snmp_payload
        )
    
    @staticmethod
    def create_tftp_read_request(
        filename: str,
        mode: str = "octet",
        src_port: Optional[int] = None,
        dst_port: int = 69
    ) -> UDPPacket:
        """
        Create a UDP packet containing a TFTP read request.
        
        Args:
            filename: File to request
            mode: Transfer mode ("netascii", "octet", "mail")
            src_port: Source port (random if None)
            dst_port: Destination port (default 69)
            
        Returns:
            UDPPacket: UDP packet with TFTP RRQ
        """
        if src_port is None:
            src_port = random.randint(*UDPFactory.EPHEMERAL_PORT_RANGE)
        
        # TFTP Read Request
        tftp_payload = struct.pack('!H', 1)  # Opcode: RRQ
        tftp_payload += filename.encode() + b'\x00'
        tftp_payload += mode.encode() + b'\x00'
        
        return UDPPacket(
            src_port=src_port,
            dst_port=dst_port,
            payload=tftp_payload
        )
    
    @staticmethod
    def create_rtp_packet(
        payload_type: int = 0,  # PCMU
        sequence_number: int = 0,
        timestamp: int = 0,
        ssrc: Optional[int] = None,
        payload: bytes = b'',
        src_port: Optional[int] = None,
        dst_port: int = 5004
    ) -> UDPPacket:
        """
        Create a UDP packet containing an RTP packet.
        
        Args:
            payload_type: RTP payload type
            sequence_number: RTP sequence number
            timestamp: RTP timestamp
            ssrc: Synchronization source identifier
            payload: RTP payload (audio/video data)
            src_port: Source port (random if None)
            dst_port: Destination port (default 5004)
            
        Returns:
            UDPPacket: UDP packet with RTP payload
        """
        if src_port is None:
            src_port = random.randint(*UDPFactory.EPHEMERAL_PORT_RANGE)
            
        if ssrc is None:
            ssrc = random.randint(0, 0xFFFFFFFF)
        
        # RTP header
        # V=2, P=0, X=0, CC=0, M=0, PT=payload_type
        rtp_header = struct.pack('!BBHII',
            0x80,  # V=2, P=0, X=0, CC=0
            payload_type & 0x7F,  # M=0, PT
            sequence_number,
            timestamp,
            ssrc
        )
        
        return UDPPacket(
            src_port=src_port,
            dst_port=dst_port,
            payload=rtp_header + payload
        )
    
    @staticmethod
    def get_ephemeral_port() -> int:
        """
        Get a random ephemeral port number.
        
        Returns:
            int: Random port in ephemeral range
        """
        return random.randint(*UDPFactory.EPHEMERAL_PORT_RANGE)
    
    @staticmethod
    def get_common_port(service: str) -> Optional[int]:
        """
        Get common port number for a service.
        
        Args:
            service: Service name (e.g., 'dns', 'dhcp-server')
            
        Returns:
            Optional[int]: Port number or None if unknown
        """
        return UDPFactory.COMMON_PORTS.get(service.lower())
    
    @staticmethod
    def validate_port(port: int) -> bool:
        """
        Validate UDP port number.
        
        Args:
            port: Port number to validate
            
        Returns:
            bool: True if valid
        """
        return 0 <= port <= 65535
    
    @staticmethod
    def calculate_length(payload: Union[bytes, str]) -> int:
        """
        Calculate UDP length for given payload.
        
        Args:
            payload: Payload data
            
        Returns:
            int: Total UDP length (header + payload)
        """
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        return UDPPacket.HEADER_SIZE + len(payload)
    
    @classmethod
    def create_echo_service(
        cls,
        data: Union[str, bytes] = "Echo test",
        src_port: Optional[int] = None,
        dst_port: int = 7
    ) -> UDPPacket:
        """
        Create UDP echo service packet.
        
        Args:
            data: Data to echo
            src_port: Source port
            dst_port: Echo port (default 7)
            
        Returns:
            UDPPacket: Echo packet
        """
        if src_port is None:
            src_port = cls.get_ephemeral_port()
            
        if isinstance(data, str):
            data = data.encode('utf-8')
            
        return UDPPacket(
            src_port=src_port,
            dst_port=dst_port,
            payload=data
        )
    
    @classmethod
    def create_broadcast_packet(
        cls,
        payload: Union[str, bytes],
        src_port: int,
        dst_port: int
    ) -> UDPPacket:
        """
        Create a UDP broadcast packet.
        
        Args:
            payload: Broadcast data
            src_port: Source port
            dst_port: Destination port
            
        Returns:
            UDPPacket: Broadcast packet
        """
        packet = UDPPacket(
            src_port=src_port,
            dst_port=dst_port,
            payload=payload
        )
        
        # Set metadata for broadcast
        packet.set_metadata('broadcast', True)
        return packet
    
    @classmethod
    def create_multicast_packet(
        cls,
        payload: Union[str, bytes],
        src_port: Optional[int] = None,
        dst_port: int = 5353,  # mDNS
        multicast_group: str = "224.0.0.251"
    ) -> UDPPacket:
        """
        Create a UDP multicast packet.
        
        Args:
            payload: Multicast data
            src_port: Source port
            dst_port: Destination port
            multicast_group: Multicast IP address
            
        Returns:
            UDPPacket: Multicast packet
        """
        if src_port is None:
            src_port = cls.get_ephemeral_port()
            
        packet = UDPPacket(
            src_port=src_port,
            dst_port=dst_port,
            payload=payload
        )
        
        # Set metadata
        packet.set_metadata('multicast', True)
        packet.set_metadata('multicast_group', multicast_group)
        return packet


# Module exports
__all__ = ['UDPFactory']