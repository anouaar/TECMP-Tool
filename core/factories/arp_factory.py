#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARP Packet Factory for creating and managing ARP packets.
Provides convenient methods for creating various ARP packet types.
"""

import random
from typing import Optional, Dict, Any, List, Tuple

# Import ARP packet from the network module
from core.packets.network.arp import ARPPacket
from core.packets.base.packet import Packet, PacketError


class ARPFactory:
    """
    Factory class for creating ARP packets with various configurations.
    Provides static methods for common ARP scenarios and conversions.
    """
    
    # Common MAC addresses
    BROADCAST_MAC = "FF:FF:FF:FF:FF:FF"
    ZERO_MAC = "00:00:00:00:00:00"
    
    # Common IP addresses
    ZERO_IP = "0.0.0.0"
    
    @staticmethod
    def create_arp_packet(**kwargs) -> ARPPacket:
        """
        Create a generic ARP packet with provided parameters.
        
        Args:
            **kwargs: All parameters accepted by ARPPacket constructor
            
        Returns:
            ARPPacket: Configured ARP packet instance
        """
        return ARPPacket(**kwargs)
    
    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> ARPPacket:
        """
        Create ARP packet from configuration dictionary (e.g., from UI dialog).
        Supports multiple naming conventions for compatibility.
        
        Args:
            config: Configuration dictionary with ARP parameters
            
        Returns:
            ARPPacket: Configured ARP packet instance
        """
        # Map all possible field names to standard names
        packet_params = {}
        
        # Hardware and protocol types
        packet_params['hw_type'] = int(config.get('hw_type', ARPPacket.HW_TYPE_ETHERNET))
        packet_params['proto_type'] = int(config.get('proto_type', ARPPacket.PROTO_TYPE_IP))
        packet_params['hw_len'] = int(config.get('hw_len', ARPPacket.ETHERNET_HW_LEN))
        packet_params['proto_len'] = int(config.get('proto_len', ARPPacket.IPV4_PROTO_LEN))
        
        # Operation - support both 'operation' and 'op'
        if 'operation' in config:
            packet_params['operation'] = int(config['operation'])
        elif 'op' in config:
            packet_params['operation'] = int(config['op'])
        else:
            packet_params['operation'] = ARPPacket.OP_REQUEST
        
        # Sender addresses - support multiple naming conventions
        if 'sender_mac' in config:
            packet_params['sender_mac'] = config['sender_mac']
        elif 'sender_hw_addr' in config:
            packet_params['sender_mac'] = config['sender_hw_addr']
        elif 'src_mac' in config:
            packet_params['sender_mac'] = config['src_mac']
        
        if 'sender_ip' in config:
            packet_params['sender_ip'] = config['sender_ip']
        elif 'sender_proto_addr' in config:
            packet_params['sender_ip'] = config['sender_proto_addr']
        elif 'src_ip' in config:
            packet_params['sender_ip'] = config['src_ip']
        
        # Target addresses - support multiple naming conventions
        if 'target_mac' in config:
            packet_params['target_mac'] = config['target_mac']
        elif 'target_hw_addr' in config:
            packet_params['target_mac'] = config['target_hw_addr']
        elif 'dst_mac' in config:
            packet_params['target_mac'] = config['dst_mac']
        
        if 'target_ip' in config:
            packet_params['target_ip'] = config['target_ip']
        elif 'target_proto_addr' in config:
            packet_params['target_ip'] = config['target_proto_addr']
        elif 'dst_ip' in config:
            packet_params['target_ip'] = config['dst_ip']
        
        # Metadata
        if 'interface' in config:
            packet_params['interface'] = config['interface']
        if 'vlan_id' in config:
            packet_params['vlan_id'] = config['vlan_id']
        if 'is_gratuitous' in config:
            packet_params['is_gratuitous'] = bool(config['is_gratuitous'])
        
        # Validation
        packet_params['strict_validation'] = config.get('strict_validation', True)
        
        return ARPPacket(**packet_params)
    
    @staticmethod
    def create_request(
        sender_mac: str,
        sender_ip: str,
        target_ip: str,
        target_mac: str = ZERO_MAC
    ) -> ARPPacket:
        """
        Create an ARP request packet.
        
        Args:
            sender_mac: Sender's MAC address
            sender_ip: Sender's IP address
            target_ip: IP address to resolve
            target_mac: Target MAC (usually 00:00:00:00:00:00 for requests)
            
        Returns:
            ARPPacket: ARP request packet
        """
        return ARPPacket(
            operation=ARPPacket.OP_REQUEST,
            sender_mac=sender_mac,
            sender_ip=sender_ip,
            target_mac=target_mac,
            target_ip=target_ip
        )
    
    @staticmethod
    def create_reply(
        sender_mac: str,
        sender_ip: str,
        target_mac: str,
        target_ip: str
    ) -> ARPPacket:
        """
        Create an ARP reply packet.
        
        Args:
            sender_mac: Sender's MAC address (the resolved address)
            sender_ip: Sender's IP address
            target_mac: Original requester's MAC address
            target_ip: Original requester's IP address
            
        Returns:
            ARPPacket: ARP reply packet
        """
        return ARPPacket(
            operation=ARPPacket.OP_REPLY,
            sender_mac=sender_mac,
            sender_ip=sender_ip,
            target_mac=target_mac,
            target_ip=target_ip
        )
    
    @staticmethod
    def create_gratuitous_arp(
        mac_address: str,
        ip_address: str,
        operation: int = ARPPacket.OP_REQUEST
    ) -> ARPPacket:
        """
        Create a gratuitous ARP packet.
        
        Args:
            mac_address: MAC address to announce
            ip_address: IP address to announce
            operation: ARP operation (request or reply)
            
        Returns:
            ARPPacket: Gratuitous ARP packet
        """
        if operation == ARPPacket.OP_REQUEST:
            # Gratuitous ARP request
            return ARPPacket(
                operation=ARPPacket.OP_REQUEST,
                sender_mac=mac_address,
                sender_ip=ip_address,
                target_mac=ARPFactory.ZERO_MAC,
                target_ip=ip_address,
                is_gratuitous=True
            )
        else:
            # Gratuitous ARP reply
            return ARPPacket(
                operation=ARPPacket.OP_REPLY,
                sender_mac=mac_address,
                sender_ip=ip_address,
                target_mac=ARPFactory.BROADCAST_MAC,
                target_ip=ip_address,
                is_gratuitous=True
            )
    
    @staticmethod
    def create_probe(
        sender_mac: str,
        target_ip: str
    ) -> ARPPacket:
        """
        Create an ARP probe packet (for duplicate address detection).
        
        Args:
            sender_mac: Sender's MAC address
            target_ip: IP address to probe
            
        Returns:
            ARPPacket: ARP probe packet
        """
        # ARP probe has sender IP = 0.0.0.0
        return ARPPacket(
            operation=ARPPacket.OP_REQUEST,
            sender_mac=sender_mac,
            sender_ip=ARPFactory.ZERO_IP,
            target_mac=ARPFactory.ZERO_MAC,
            target_ip=target_ip
        )
    
    @staticmethod
    def create_announcement(
        mac_address: str,
        ip_address: str
    ) -> ARPPacket:
        """
        Create an ARP announcement packet.
        
        Args:
            mac_address: MAC address to announce
            ip_address: IP address to announce
            
        Returns:
            ARPPacket: ARP announcement packet
        """
        # ARP announcement is a special gratuitous ARP reply
        return ARPFactory.create_gratuitous_arp(
            mac_address=mac_address,
            ip_address=ip_address,
            operation=ARPPacket.OP_REPLY
        )
    
    @staticmethod
    def create_rarp_request(
        sender_mac: str,
        sender_ip: str = ZERO_IP,
        target_mac: str = ZERO_MAC,
        target_ip: str = ZERO_IP
    ) -> ARPPacket:
        """
        Create a Reverse ARP (RARP) request packet.
        
        Args:
            sender_mac: Sender's MAC address
            sender_ip: Sender's IP (usually 0.0.0.0)
            target_mac: Target MAC (usually 0)
            target_ip: Target IP (usually 0.0.0.0)
            
        Returns:
            ARPPacket: RARP request packet
        """
        return ARPPacket(
            operation=ARPPacket.OP_RARP_REQUEST,
            sender_mac=sender_mac,
            sender_ip=sender_ip,
            target_mac=target_mac,
            target_ip=target_ip
        )
    
    @staticmethod
    def create_proxy_arp_reply(
        proxy_mac: str,
        target_ip: str,
        requester_mac: str,
        requester_ip: str
    ) -> ARPPacket:
        """
        Create a proxy ARP reply packet.
        
        Args:
            proxy_mac: MAC address of the proxy
            target_ip: IP address being proxied
            requester_mac: Original requester's MAC
            requester_ip: Original requester's IP
            
        Returns:
            ARPPacket: Proxy ARP reply
        """
        return ARPPacket(
            operation=ARPPacket.OP_REPLY,
            sender_mac=proxy_mac,
            sender_ip=target_ip,  # IP being proxied
            target_mac=requester_mac,
            target_ip=requester_ip
        )
    
    @staticmethod
    def create_conflict_detection(
        mac_address: str,
        ip_address: str
    ) -> List[ARPPacket]:
        """
        Create a sequence of ARP packets for IP conflict detection.
        
        Args:
            mac_address: MAC address of the device
            ip_address: IP address to check
            
        Returns:
            List[ARPPacket]: List of ARP probe packets
        """
        # RFC 5227 recommends 3 probes
        probes = []
        for _ in range(3):
            probes.append(ARPFactory.create_probe(mac_address, ip_address))
        return probes
    
    @staticmethod
    def generate_random_mac() -> str:
        """
        Generate a random MAC address (locally administered).
        
        Returns:
            str: Random MAC address
        """
        # Set locally administered bit (bit 1 of first octet)
        # Clear multicast bit (bit 0 of first octet)
        first_octet = (random.randint(0, 255) & 0xFC) | 0x02
        mac_bytes = [first_octet] + [random.randint(0, 255) for _ in range(5)]
        return ':'.join(f'{b:02X}' for b in mac_bytes)
    
    @staticmethod
    def is_valid_mac(mac: str) -> bool:
        """
        Validate MAC address format.
        
        Args:
            mac: MAC address to validate
            
        Returns:
            bool: True if valid
        """
        import re
        patterns = [
            r'^[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}$',
            r'^[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}$',
            r'^[0-9A-Fa-f]{12}$'
        ]
        return any(re.match(pattern, mac) for pattern in patterns)
    
    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """
        Validate IPv4 address format.
        
        Args:
            ip: IP address to validate
            
        Returns:
            bool: True if valid
        """
        import socket
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False
    
    @classmethod
    def create_scan_range(
        cls,
        sender_mac: str,
        sender_ip: str,
        target_network: str,
        target_mask: int = 24
    ) -> List[ARPPacket]:
        """
        Create ARP requests for scanning a network range.
        
        Args:
            sender_mac: Scanner's MAC address
            sender_ip: Scanner's IP address
            target_network: Target network (e.g., "192.168.1.0")
            target_mask: Network mask bits (default /24)
            
        Returns:
            List[ARPPacket]: List of ARP requests
        """
        import ipaddress
        
        requests = []
        try:
            network = ipaddress.ip_network(f"{target_network}/{target_mask}")
            for ip in network.hosts():  # Skip network and broadcast
                requests.append(cls.create_request(
                    sender_mac=sender_mac,
                    sender_ip=sender_ip,
                    target_ip=str(ip)
                ))
        except ValueError:
            pass
        
        return requests
    
    @classmethod
    def create_from_packet_factory_params(
        cls,
        operation: int = 1,
        sender_hw_addr: str = "00:00:00:00:00:00",
        sender_proto_addr: str = "0.0.0.0",
        target_hw_addr: str = "00:00:00:00:00:00",
        target_proto_addr: str = "0.0.0.0",
        **kwargs
    ) -> ARPPacket:
        """
        Create ARP packet using packet_factory naming convention.
        For compatibility with existing packet_factory code.
        
        Args:
            operation: ARP operation
            sender_hw_addr: Sender hardware address
            sender_proto_addr: Sender protocol address
            target_hw_addr: Target hardware address
            target_proto_addr: Target protocol address
            **kwargs: Additional parameters
            
        Returns:
            ARPPacket: Configured ARP packet
        """
        return ARPPacket(
            operation=operation,
            sender_hw_addr=sender_hw_addr,
            sender_proto_addr=sender_proto_addr,
            target_hw_addr=target_hw_addr,
            target_proto_addr=target_proto_addr,
            **kwargs
        )


# Module exports
__all__ = ['ARPFactory']