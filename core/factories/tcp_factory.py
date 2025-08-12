#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TCP Packet Factory for creating and managing TCP packets.
Provides convenient methods for creating various TCP packet types.
"""

import struct
import random
import time
from typing import Optional, Dict, Any, List, Tuple, Union
from datetime import datetime

# Import TCP packet from the transport module
from core.packets.transport.tcp import TCPPacket
from core.packets.base.packet import Packet


class TCPFactory:
    """
    Factory class for creating TCP packets with various configurations.
    Provides static methods for common TCP packet types and conversions.
    """
    
    # Default values for TCP packets
    DEFAULT_WINDOW_SIZE = 8192
    DEFAULT_MSS = 1460
    DEFAULT_TTL = 64
    EPHEMERAL_PORT_RANGE = (49152, 65535)
    
    # Common port numbers
    COMMON_PORTS = {
        'http': 80,
        'https': 443,
        'ssh': 22,
        'telnet': 23,
        'ftp': 21,
        'smtp': 25,
        'dns': 53,
        'pop3': 110,
        'imap': 143,
        'snmp': 161,
        'ldap': 389,
        'smb': 445,
        'rdp': 3389,
        'mysql': 3306,
        'postgresql': 5432,
        'vnc': 5900,
        'redis': 6379,
        'elasticsearch': 9200,
        'kafka': 9092
    }
    
    @staticmethod
    def create_tcp_packet(**kwargs) -> TCPPacket:
        """
        Create a generic TCP packet with provided parameters.
        
        Args:
            **kwargs: All parameters accepted by TCPPacket constructor
            
        Returns:
            TCPPacket: Configured TCP packet instance
        """
        return TCPPacket(**kwargs)
    
    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> TCPPacket:
        """
        Create TCP packet from configuration dictionary (e.g., from UI dialog).
        
        Args:
            config: Configuration dictionary with TCP parameters
            
        Returns:
            TCPPacket: Configured TCP packet instance
        """
        # Convert config values to proper types and handle special cases
        packet_params = {}
        
        # Basic fields
        packet_params['src_port'] = int(config.get('src_port', 0))
        packet_params['dst_port'] = int(config.get('dst_port', 0))
        packet_params['seq_number'] = int(config.get('seq_number', 0))
        packet_params['ack_number'] = int(config.get('ack_number', 0))
        packet_params['window_size'] = int(config.get('window_size', TCPFactory.DEFAULT_WINDOW_SIZE))
        packet_params['data_offset'] = int(config.get('data_offset', 5))
        packet_params['reserved'] = int(config.get('reserved', 0))
        packet_params['checksum'] = int(config.get('checksum', 0))
        packet_params['urgent_pointer'] = int(config.get('urgent_pointer', 0))
        
        # Handle flags - could be single value or individual flags
        if 'flags' in config:
            packet_params['flags'] = int(config['flags'])
        else:
            # Build flags from individual values
            flags = 0
            if config.get('fin', False): flags |= TCPPacket.FLAG_FIN
            if config.get('syn', False): flags |= TCPPacket.FLAG_SYN
            if config.get('rst', False): flags |= TCPPacket.FLAG_RST
            if config.get('psh', False): flags |= TCPPacket.FLAG_PSH
            if config.get('ack', False): flags |= TCPPacket.FLAG_ACK
            if config.get('urg', False): flags |= TCPPacket.FLAG_URG
            if config.get('ece', False): flags |= TCPPacket.FLAG_ECE
            if config.get('cwr', False): flags |= TCPPacket.FLAG_CWR
            if config.get('ns', False): flags |= TCPPacket.FLAG_NS
            packet_params['flags'] = flags
        
        # TCP Options
        if 'mss' in config and config['mss'] != 0:
            packet_params['mss'] = int(config['mss'])
            
        if 'window_scale' in config and config['window_scale'] != -1:
            packet_params['window_scale'] = int(config['window_scale'])
            
        packet_params['sack_permitted'] = config.get('sack_permitted', False)
        
        # Handle timestamp option
        if config.get('timestamp_enabled', False):
            # Generate timestamp values
            ts_val = int(time.time() * 1000) & 0xFFFFFFFF
            ts_ecr = 0  # Echo reply timestamp (0 for initial packet)
            packet_params['timestamp'] = (ts_val, ts_ecr)
        
        # Raw options (hex string to bytes)
        if 'raw_options' in config and config['raw_options']:
            try:
                raw_hex = config['raw_options'].replace(' ', '').replace('0x', '')
                packet_params['raw_options'] = bytes.fromhex(raw_hex)
            except ValueError:
                # Invalid hex string, ignore
                pass
        
        # Payload
        if 'payload' in config:
            payload = config['payload']
            if isinstance(payload, str):
                # Try to detect if it's hex
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
        
        # Auto-calculate options
        packet_params['auto_checksum'] = config.get('auto_checksum', True)
        packet_params['auto_data_offset'] = config.get('auto_data_offset', True)
        
        return TCPPacket(**packet_params)
    
    @staticmethod
    def create_syn_packet(
        src_port: int,
        dst_port: int,
        seq_number: Optional[int] = None,
        window_size: int = DEFAULT_WINDOW_SIZE,
        mss: int = DEFAULT_MSS,
        window_scale: Optional[int] = None,
        sack_permitted: bool = True,
        timestamp: bool = True
    ) -> TCPPacket:
        """
        Create a TCP SYN packet for connection initiation.
        
        Args:
            src_port: Source port number
            dst_port: Destination port number
            seq_number: Initial sequence number (random if None)
            window_size: TCP window size
            mss: Maximum Segment Size option
            window_scale: Window scale factor (None to disable)
            sack_permitted: Enable SACK permitted option
            timestamp: Enable timestamp option
            
        Returns:
            TCPPacket: Configured SYN packet
        """
        if seq_number is None:
            seq_number = random.randint(0, 0xFFFFFFFF)
        
        params = {
            'src_port': src_port,
            'dst_port': dst_port,
            'seq_number': seq_number,
            'ack_number': 0,
            'syn': True,
            'window_size': window_size,
            'mss': mss,
            'sack_permitted': sack_permitted
        }
        
        if window_scale is not None:
            params['window_scale'] = window_scale
            
        if timestamp:
            ts_val = int(time.time() * 1000) & 0xFFFFFFFF
            params['timestamp'] = (ts_val, 0)
        
        return TCPPacket(**params)
    
    @staticmethod
    def create_syn_ack_packet(
        src_port: int,
        dst_port: int,
        seq_number: Optional[int] = None,
        ack_number: int = 0,
        window_size: int = DEFAULT_WINDOW_SIZE,
        mss: int = DEFAULT_MSS,
        window_scale: Optional[int] = None,
        sack_permitted: bool = True,
        timestamp: Optional[Tuple[int, int]] = None
    ) -> TCPPacket:
        """
        Create a TCP SYN-ACK packet for connection acknowledgment.
        
        Args:
            src_port: Source port number
            dst_port: Destination port number
            seq_number: Sequence number (random if None)
            ack_number: Acknowledgment number (usually client_seq + 1)
            window_size: TCP window size
            mss: Maximum Segment Size option
            window_scale: Window scale factor
            sack_permitted: Enable SACK permitted option
            timestamp: Tuple of (TSval, TSecr) for timestamp option
            
        Returns:
            TCPPacket: Configured SYN-ACK packet
        """
        if seq_number is None:
            seq_number = random.randint(0, 0xFFFFFFFF)
        
        params = {
            'src_port': src_port,
            'dst_port': dst_port,
            'seq_number': seq_number,
            'ack_number': ack_number,
            'syn': True,
            'ack': True,
            'window_size': window_size,
            'mss': mss,
            'sack_permitted': sack_permitted
        }
        
        if window_scale is not None:
            params['window_scale'] = window_scale
            
        if timestamp:
            params['timestamp'] = timestamp
        
        return TCPPacket(**params)
    
    @staticmethod
    def create_ack_packet(
        src_port: int,
        dst_port: int,
        seq_number: int,
        ack_number: int,
        window_size: int = DEFAULT_WINDOW_SIZE,
        payload: bytes = b''
    ) -> TCPPacket:
        """
        Create a TCP ACK packet.
        
        Args:
            src_port: Source port number
            dst_port: Destination port number
            seq_number: Sequence number
            ack_number: Acknowledgment number
            window_size: TCP window size
            payload: Optional payload data
            
        Returns:
            TCPPacket: Configured ACK packet
        """
        return TCPPacket(
            src_port=src_port,
            dst_port=dst_port,
            seq_number=seq_number,
            ack_number=ack_number,
            ack=True,
            window_size=window_size,
            payload=payload
        )
    
    @staticmethod
    def create_fin_packet(
        src_port: int,
        dst_port: int,
        seq_number: int,
        ack_number: int,
        window_size: int = DEFAULT_WINDOW_SIZE
    ) -> TCPPacket:
        """
        Create a TCP FIN packet for connection termination.
        
        Args:
            src_port: Source port number
            dst_port: Destination port number
            seq_number: Sequence number
            ack_number: Acknowledgment number
            window_size: TCP window size
            
        Returns:
            TCPPacket: Configured FIN packet
        """
        return TCPPacket(
            src_port=src_port,
            dst_port=dst_port,
            seq_number=seq_number,
            ack_number=ack_number,
            fin=True,
            ack=True,
            window_size=window_size
        )
    
    @staticmethod
    def create_rst_packet(
        src_port: int,
        dst_port: int,
        seq_number: int,
        ack_number: int = 0,
        ack_flag: bool = False
    ) -> TCPPacket:
        """
        Create a TCP RST packet for connection reset.
        
        Args:
            src_port: Source port number
            dst_port: Destination port number
            seq_number: Sequence number
            ack_number: Acknowledgment number
            ack_flag: Include ACK flag with RST
            
        Returns:
            TCPPacket: Configured RST packet
        """
        return TCPPacket(
            src_port=src_port,
            dst_port=dst_port,
            seq_number=seq_number,
            ack_number=ack_number,
            rst=True,
            ack=ack_flag
        )
    
    @staticmethod
    def create_data_packet(
        src_port: int,
        dst_port: int,
        seq_number: int,
        ack_number: int,
        payload: Union[str, bytes],
        psh: bool = True,
        window_size: int = DEFAULT_WINDOW_SIZE
    ) -> TCPPacket:
        """
        Create a TCP data packet with payload.
        
        Args:
            src_port: Source port number
            dst_port: Destination port number
            seq_number: Sequence number
            ack_number: Acknowledgment number
            payload: Data payload (string or bytes)
            psh: Set PSH flag
            window_size: TCP window size
            
        Returns:
            TCPPacket: Configured data packet
        """
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
            
        return TCPPacket(
            src_port=src_port,
            dst_port=dst_port,
            seq_number=seq_number,
            ack_number=ack_number,
            ack=True,
            psh=psh,
            window_size=window_size,
            payload=payload
        )
    
    @staticmethod
    def create_scan_packet(
        src_port: Optional[int] = None,
        dst_port: int = 80,
        scan_type: str = 'syn'
    ) -> TCPPacket:
        """
        Create a TCP packet for port scanning.
        
        Args:
            src_port: Source port (random ephemeral if None)
            dst_port: Target port to scan
            scan_type: Type of scan ('syn', 'fin', 'xmas', 'null', 'ack')
            
        Returns:
            TCPPacket: Configured scan packet
        """
        if src_port is None:
            src_port = random.randint(*TCPFactory.EPHEMERAL_PORT_RANGE)
        
        seq_number = random.randint(0, 0xFFFFFFFF)
        
        scan_configs = {
            'syn': {'syn': True},
            'fin': {'fin': True},
            'xmas': {'fin': True, 'psh': True, 'urg': True},
            'null': {'flags': 0},
            'ack': {'ack': True, 'ack_number': random.randint(0, 0xFFFFFFFF)}
        }
        
        config = scan_configs.get(scan_type.lower(), scan_configs['syn'])
        
        return TCPPacket(
            src_port=src_port,
            dst_port=dst_port,
            seq_number=seq_number,
            **config
        )
    
    @staticmethod
    def create_http_request_packet(
        src_port: Optional[int] = None,
        dst_port: int = 80,
        seq_number: int = 0,
        ack_number: int = 0,
        method: str = 'GET',
        path: str = '/',
        host: str = 'example.com',
        additional_headers: Optional[Dict[str, str]] = None
    ) -> TCPPacket:
        """
        Create a TCP packet containing an HTTP request.
        
        Args:
            src_port: Source port (random if None)
            dst_port: Destination port (default 80)
            seq_number: TCP sequence number
            ack_number: TCP acknowledgment number
            method: HTTP method (GET, POST, etc.)
            path: Request path
            host: Host header value
            additional_headers: Extra HTTP headers
            
        Returns:
            TCPPacket: TCP packet with HTTP payload
        """
        if src_port is None:
            src_port = random.randint(*TCPFactory.EPHEMERAL_PORT_RANGE)
        
        # Build HTTP request
        headers = {
            'Host': host,
            'User-Agent': 'TCPFactory/1.0',
            'Accept': '*/*',
            'Connection': 'close'
        }
        
        if additional_headers:
            headers.update(additional_headers)
        
        request_lines = [f"{method} {path} HTTP/1.1"]
        request_lines.extend([f"{k}: {v}" for k, v in headers.items()])
        request_lines.append("")  # Empty line before body
        request_lines.append("")  # Empty body
        
        http_payload = "\r\n".join(request_lines).encode('utf-8')
        
        return TCPPacket(
            src_port=src_port,
            dst_port=dst_port,
            seq_number=seq_number,
            ack_number=ack_number,
            ack=True,
            psh=True,
            payload=http_payload
        )
    
    @staticmethod
    def get_ephemeral_port() -> int:
        """
        Get a random ephemeral port number.
        
        Returns:
            int: Random port in ephemeral range
        """
        return random.randint(*TCPFactory.EPHEMERAL_PORT_RANGE)
    
    @staticmethod
    def get_common_port(service: str) -> Optional[int]:
        """
        Get common port number for a service.
        
        Args:
            service: Service name (e.g., 'http', 'ssh')
            
        Returns:
            Optional[int]: Port number or None if unknown
        """
        return TCPFactory.COMMON_PORTS.get(service.lower())
    
    @staticmethod
    def calculate_initial_seq() -> int:
        """
        Calculate initial sequence number using timestamp-based method.
        
        Returns:
            int: Initial sequence number
        """
        # Simple ISN calculation based on timestamp
        # Real implementations use more complex algorithms
        timestamp = int(time.time() * 1000000)  # Microseconds
        return timestamp & 0xFFFFFFFF
    
    @staticmethod
    def create_tcp_options(
        mss: Optional[int] = None,
        window_scale: Optional[int] = None,
        sack_permitted: bool = False,
        timestamp: Optional[Tuple[int, int]] = None,
        fast_open: Optional[bytes] = None
    ) -> bytes:
        """
        Create TCP options bytes.
        
        Args:
            mss: Maximum Segment Size
            window_scale: Window scale factor
            sack_permitted: SACK permitted flag
            timestamp: Timestamp tuple (TSval, TSecr)
            fast_open: Fast Open cookie
            
        Returns:
            bytes: Encoded TCP options
        """
        options = b''
        
        if mss is not None:
            options += struct.pack('!BBH', TCPPacket.OPT_MSS, 4, mss)
            
        if window_scale is not None:
            options += struct.pack('!BBB', TCPPacket.OPT_WSOPT, 3, window_scale)
            
        if sack_permitted:
            options += struct.pack('!BB', TCPPacket.OPT_SACK_PERMITTED, 2)
            
        if timestamp:
            ts_val, ts_ecr = timestamp
            options += struct.pack('!BBII', TCPPacket.OPT_TIMESTAMP, 10, ts_val, ts_ecr)
            
        if fast_open:
            options += struct.pack('!BB', TCPPacket.OPT_FASTOPEN, 2 + len(fast_open)) + fast_open
        
        # Pad to 4-byte boundary
        while len(options) % 4 != 0:
            options += struct.pack('!B', TCPPacket.OPT_NOP)
            
        return options
    
    @staticmethod
    def validate_port(port: int) -> bool:
        """
        Validate TCP port number.
        
        Args:
            port: Port number to validate
            
        Returns:
            bool: True if valid
        """
        return 0 <= port <= 65535
    
    @staticmethod
    def validate_sequence_number(seq: int) -> bool:
        """
        Validate TCP sequence number.
        
        Args:
            seq: Sequence number to validate
            
        Returns:
            bool: True if valid
        """
        return 0 <= seq <= 0xFFFFFFFF
    
    @classmethod
    def create_three_way_handshake(
        cls,
        client_port: int,
        server_port: int,
        client_isn: Optional[int] = None,
        server_isn: Optional[int] = None
    ) -> List[TCPPacket]:
        """
        Create packets for a complete three-way handshake.
        
        Args:
            client_port: Client port number
            server_port: Server port number
            client_isn: Client initial sequence number
            server_isn: Server initial sequence number
            
        Returns:
            List[TCPPacket]: [SYN, SYN-ACK, ACK] packets
        """
        if client_isn is None:
            client_isn = cls.calculate_initial_seq()
        if server_isn is None:
            server_isn = cls.calculate_initial_seq()
        
        # 1. Client -> Server: SYN
        syn_packet = cls.create_syn_packet(
            src_port=client_port,
            dst_port=server_port,
            seq_number=client_isn
        )
        
        # 2. Server -> Client: SYN-ACK
        syn_ack_packet = cls.create_syn_ack_packet(
            src_port=server_port,
            dst_port=client_port,
            seq_number=server_isn,
            ack_number=client_isn + 1
        )
        
        # 3. Client -> Server: ACK
        ack_packet = cls.create_ack_packet(
            src_port=client_port,
            dst_port=server_port,
            seq_number=client_isn + 1,
            ack_number=server_isn + 1
        )
        
        return [syn_packet, syn_ack_packet, ack_packet]
    
    @classmethod
    def create_connection_teardown(
        cls,
        client_port: int,
        server_port: int,
        client_seq: int,
        server_seq: int
    ) -> List[TCPPacket]:
        """
        Create packets for connection teardown (4-way handshake).
        
        Args:
            client_port: Client port number
            server_port: Server port number
            client_seq: Current client sequence number
            server_seq: Current server sequence number
            
        Returns:
            List[TCPPacket]: [FIN, ACK, FIN, ACK] packets
        """
        # 1. Client -> Server: FIN
        client_fin = cls.create_fin_packet(
            src_port=client_port,
            dst_port=server_port,
            seq_number=client_seq,
            ack_number=server_seq
        )
        
        # 2. Server -> Client: ACK
        server_ack = cls.create_ack_packet(
            src_port=server_port,
            dst_port=client_port,
            seq_number=server_seq,
            ack_number=client_seq + 1
        )
        
        # 3. Server -> Client: FIN
        server_fin = cls.create_fin_packet(
            src_port=server_port,
            dst_port=client_port,
            seq_number=server_seq,
            ack_number=client_seq + 1
        )
        
        # 4. Client -> Server: ACK
        client_ack = cls.create_ack_packet(
            src_port=client_port,
            dst_port=server_port,
            seq_number=client_seq + 1,
            ack_number=server_seq + 1
        )
        
        return [client_fin, server_ack, server_fin, client_ack]


# Module exports
__all__ = ['TCPFactory']