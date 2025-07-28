#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP Packet Factory for creating and managing IPv4 and IPv6 packets.
Provides convenient methods for creating various IP packet types.
"""

import random
import ipaddress
from typing import Optional, Dict, Any, List, Union, Tuple

# Import IP packets from the network module
from core.packets.network.ipv4 import IPv4Packet
from core.packets.network.ipv6 import IPv6Packet
from core.packets.base.packet import Packet, PacketError


class IPPacketFactory:
    """
    Factory class for creating IP packets (both IPv4 and IPv6).
    Note: Class name is IPPacketFactory for compatibility with existing imports.
    """
    
    # Common private IP ranges
    PRIVATE_IPV4_RANGES = [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16"
    ]
    
    # Common IPv6 prefixes
    IPV6_LINK_LOCAL = "fe80::/10"
    IPV6_UNIQUE_LOCAL = "fc00::/7"
    IPV6_MULTICAST = "ff00::/8"
    IPV6_LOOPBACK = "::1/128"
    
    # Common protocols
    PROTOCOLS = {
        'icmp': 1,
        'igmp': 2,
        'tcp': 6,
        'udp': 17,
        'icmpv6': 58,
        'ospf': 89,
        'sctp': 132
    }
    
    @staticmethod
    def create_packet(**kwargs) -> Union[IPv4Packet, IPv6Packet]:
        """
        Create an IP packet (IPv4 or IPv6) based on parameters.
        Method name matches packet_factory expectations.
        
        Args:
            **kwargs: Parameters for IP packet
            
        Returns:
            IPv4Packet or IPv6Packet based on detected version
        """
        # Detect version from IP addresses
        src_ip = kwargs.get('src_ip', '')
        dst_ip = kwargs.get('dst_ip', '')
        version = kwargs.get('version')
        
        if version == 6 or ':' in src_ip or ':' in dst_ip:
            return IPPacketFactory.create_ipv6_packet(**kwargs)
        else:
            return IPPacketFactory.create_ipv4_packet(**kwargs)
    
    @staticmethod
    def create_ipv4_packet(**kwargs) -> IPv4Packet:
        """
        Create an IPv4 packet with provided parameters.
        
        Args:
            **kwargs: All parameters accepted by IPv4Packet constructor
            
        Returns:
            IPv4Packet: Configured IPv4 packet instance
        """
        return IPv4Packet(**kwargs)
    
    @staticmethod
    def create_ipv6_packet(**kwargs) -> IPv6Packet:
        """
        Create an IPv6 packet with provided parameters.
        
        Args:
            **kwargs: All parameters accepted by IPv6Packet constructor
            
        Returns:
            IPv6Packet: Configured IPv6 packet instance
        """
        return IPv6Packet(**kwargs)
    
    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> Union[IPv4Packet, IPv6Packet]:
        """
        Create IP packet from configuration dictionary (e.g., from UI dialog).
        
        Args:
            config: Configuration dictionary with IP parameters
            
        Returns:
            IPv4Packet or IPv6Packet based on configuration
        """
        # Detect version
        version = config.get('version')
        src_ip = config.get('src_ip', '')
        dst_ip = config.get('dst_ip', '')
        
        # Auto-detect version if not specified
        if version is None:
            if ':' in src_ip or ':' in dst_ip:
                version = 6
            else:
                version = 4
        
        # Extract common parameters
        packet_params = {
            'src_ip': src_ip,
            'dst_ip': dst_ip,
            'payload': config.get('payload', b'')
        }
        
        # Handle payload encoding
        if isinstance(packet_params['payload'], str):
            packet_params['payload'] = packet_params['payload'].encode('utf-8')
        
        if version == 4:
            # IPv4 specific parameters
            packet_params['version'] = 4
            packet_params['ttl'] = config.get('ttl', IPv4Packet.DEFAULT_TTL)
            packet_params['protocol'] = config.get('protocol', IPv4Packet.PROTO_TCP)
            
            # Optional IPv4 fields
            if 'tos' in config:
                packet_params['tos'] = config['tos']
            if 'dscp' in config:
                packet_params['dscp'] = config['dscp']
            if 'ecn' in config:
                packet_params['ecn'] = config['ecn']
            if 'identification' in config:
                packet_params['identification'] = config['identification']
            if 'flags' in config:
                packet_params['flags'] = config['flags']
            if 'fragment_offset' in config:
                packet_params['fragment_offset'] = config['fragment_offset']
            if 'options' in config:
                packet_params['options'] = config['options']
            
            # Boolean flags
            if 'dont_fragment' in config:
                packet_params['dont_fragment'] = config['dont_fragment']
            if 'more_fragments' in config:
                packet_params['more_fragments'] = config['more_fragments']
            
            return IPv4Packet(**packet_params)
            
        else:  # IPv6
            # IPv6 specific parameters
            packet_params['version'] = 6
            packet_params['hop_limit'] = config.get('hop_limit', IPv6Packet.DEFAULT_HOP_LIMIT)
            
            # Handle both 'protocol' and 'next_header' names
            if 'protocol' in config:
                packet_params['next_header'] = config['protocol']
            elif 'next_header' in config:
                packet_params['next_header'] = config['next_header']
            else:
                packet_params['next_header'] = IPv6Packet.NH_TCP
            
            # Optional IPv6 fields
            if 'traffic_class' in config:
                packet_params['traffic_class'] = config['traffic_class']
            if 'dscp' in config:
                packet_params['dscp'] = config['dscp']
            if 'ecn' in config:
                packet_params['ecn'] = config['ecn']
            if 'flow_label' in config:
                packet_params['flow_label'] = config['flow_label']
            
            return IPv6Packet(**packet_params)
    
    @staticmethod
    def create_tcp_packet(
        src_ip: str,
        dst_ip: str,
        ttl_or_hop_limit: Optional[int] = None,
        **kwargs
    ) -> Union[IPv4Packet, IPv6Packet]:
        """
        Create an IP packet configured for TCP.
        
        Args:
            src_ip: Source IP address
            dst_ip: Destination IP address
            ttl_or_hop_limit: TTL (IPv4) or Hop Limit (IPv6)
            **kwargs: Additional parameters
            
        Returns:
            IP packet configured for TCP
        """
        params = kwargs.copy()
        params['src_ip'] = src_ip
        params['dst_ip'] = dst_ip
        
        if ':' in src_ip or ':' in dst_ip:
            # IPv6
            params['next_header'] = IPv6Packet.NH_TCP
            if ttl_or_hop_limit:
                params['hop_limit'] = ttl_or_hop_limit
        else:
            # IPv4
            params['protocol'] = IPv4Packet.PROTO_TCP
            if ttl_or_hop_limit:
                params['ttl'] = ttl_or_hop_limit
        
        return IPPacketFactory.create_packet(**params)
    
    @staticmethod
    def create_udp_packet(
        src_ip: str,
        dst_ip: str,
        ttl_or_hop_limit: Optional[int] = None,
        **kwargs
    ) -> Union[IPv4Packet, IPv6Packet]:
        """
        Create an IP packet configured for UDP.
        
        Args:
            src_ip: Source IP address
            dst_ip: Destination IP address
            ttl_or_hop_limit: TTL (IPv4) or Hop Limit (IPv6)
            **kwargs: Additional parameters
            
        Returns:
            IP packet configured for UDP
        """
        params = kwargs.copy()
        params['src_ip'] = src_ip
        params['dst_ip'] = dst_ip
        
        if ':' in src_ip or ':' in dst_ip:
            # IPv6
            params['next_header'] = IPv6Packet.NH_UDP
            if ttl_or_hop_limit:
                params['hop_limit'] = ttl_or_hop_limit
        else:
            # IPv4
            params['protocol'] = IPv4Packet.PROTO_UDP
            if ttl_or_hop_limit:
                params['ttl'] = ttl_or_hop_limit
        
        return IPPacketFactory.create_packet(**params)
    
    @staticmethod
    def create_icmp_packet(
        src_ip: str,
        dst_ip: str,
        **kwargs
    ) -> Union[IPv4Packet, IPv6Packet]:
        """
        Create an IP packet configured for ICMP/ICMPv6.
        
        Args:
            src_ip: Source IP address
            dst_ip: Destination IP address
            **kwargs: Additional parameters
            
        Returns:
            IP packet configured for ICMP
        """
        params = kwargs.copy()
        params['src_ip'] = src_ip
        params['dst_ip'] = dst_ip
        
        if ':' in src_ip or ':' in dst_ip:
            # IPv6
            params['next_header'] = IPv6Packet.NH_ICMPV6
        else:
            # IPv4
            params['protocol'] = IPv4Packet.PROTO_ICMP
        
        return IPPacketFactory.create_packet(**params)
    
    @staticmethod
    def create_fragment(
        src_ip: str,
        dst_ip: str,
        identification: int,
        fragment_offset: int,
        more_fragments: bool = True,
        **kwargs
    ) -> IPv4Packet:
        """
        Create a fragmented IPv4 packet.
        
        Args:
            src_ip: Source IP address
            dst_ip: Destination IP address
            identification: Fragment identification
            fragment_offset: Fragment offset (in 8-byte units)
            more_fragments: More fragments flag
            **kwargs: Additional parameters
            
        Returns:
            IPv4Packet: Fragmented packet
        """
        return IPv4Packet(
            src_ip=src_ip,
            dst_ip=dst_ip,
            identification=identification,
            fragment_offset=fragment_offset,
            more_fragments=more_fragments,
            dont_fragment=False,  # Can't be fragmented if DF is set
            **kwargs
        )
    
    @staticmethod
    def create_with_random_ips(
        version: int = 4,
        private: bool = True,
        **kwargs
    ) -> Union[IPv4Packet, IPv6Packet]:
        """
        Create an IP packet with random IP addresses.
        
        Args:
            version: IP version (4 or 6)
            private: Use private address ranges
            **kwargs: Additional parameters
            
        Returns:
            IP packet with random addresses
        """
        if version == 4:
            if private:
                # Random private IPv4
                network = random.choice([
                    ipaddress.ip_network("10.0.0.0/8"),
                    ipaddress.ip_network("172.16.0.0/12"),
                    ipaddress.ip_network("192.168.0.0/16")
                ])
            else:
                # Random public IPv4 (example range)
                network = ipaddress.ip_network("8.8.0.0/16")
            
            src_ip = str(ipaddress.ip_address(
                random.randint(int(network.network_address) + 1, 
                             int(network.broadcast_address) - 1)
            ))
            dst_ip = str(ipaddress.ip_address(
                random.randint(int(network.network_address) + 1,
                             int(network.broadcast_address) - 1)
            ))
            
            return IPv4Packet(src_ip=src_ip, dst_ip=dst_ip, **kwargs)
            
        else:  # IPv6
            if private:
                # Random unique local IPv6
                prefix = "fd00::"
                src_ip = f"{prefix}{random.randint(1, 65535):x}:{random.randint(0, 65535):x}"
                dst_ip = f"{prefix}{random.randint(1, 65535):x}:{random.randint(0, 65535):x}"
            else:
                # Random global IPv6 (example)
                prefix = "2001:db8::"
                src_ip = f"{prefix}{random.randint(1, 65535):x}"
                dst_ip = f"{prefix}{random.randint(1, 65535):x}"
            
            return IPv6Packet(src_ip=src_ip, dst_ip=dst_ip, **kwargs)
    
    @staticmethod
    def create_multicast_packet(
        src_ip: str,
        multicast_group: str,
        ttl_or_hop_limit: int = 1,
        **kwargs
    ) -> Union[IPv4Packet, IPv6Packet]:
        """
        Create a multicast IP packet.
        
        Args:
            src_ip: Source IP address
            multicast_group: Multicast group address
            ttl_or_hop_limit: TTL/Hop limit (default 1 for local)
            **kwargs: Additional parameters
            
        Returns:
            Multicast IP packet
        """
        if ':' in multicast_group:
            # IPv6 multicast
            return IPv6Packet(
                src_ip=src_ip,
                dst_ip=multicast_group,
                hop_limit=ttl_or_hop_limit,
                **kwargs
            )
        else:
            # IPv4 multicast
            return IPv4Packet(
                src_ip=src_ip,
                dst_ip=multicast_group,
                ttl=ttl_or_hop_limit,
                **kwargs
            )
    
    @staticmethod
    def create_broadcast_packet(
        src_ip: str,
        network: str = "192.168.1.0/24",
        **kwargs
    ) -> IPv4Packet:
        """
        Create an IPv4 broadcast packet.
        
        Args:
            src_ip: Source IP address
            network: Network for broadcast (CIDR notation)
            **kwargs: Additional parameters
            
        Returns:
            IPv4Packet: Broadcast packet
        """
        net = ipaddress.ip_network(network)
        broadcast_ip = str(net.broadcast_address)
        
        return IPv4Packet(
            src_ip=src_ip,
            dst_ip=broadcast_ip,
            **kwargs
        )
    
    @staticmethod
    def generate_random_ipv4(
        private: bool = True,
        exclude_reserved: bool = True
    ) -> str:
        """
        Generate a random IPv4 address.
        
        Args:
            private: Generate private address
            exclude_reserved: Exclude reserved addresses
            
        Returns:
            str: Random IPv4 address
        """
        if private:
            network = random.choice([
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16")
            ])
            
            return str(ipaddress.ip_address(
                random.randint(int(network.network_address) + 1,
                             int(network.broadcast_address) - 1)
            ))
        else:
            # Generate public IP (avoiding reserved ranges)
            while True:
                ip = ipaddress.ip_address(random.randint(1, 0xFFFFFFFF))
                if exclude_reserved and (
                    ip.is_private or ip.is_multicast or 
                    ip.is_reserved or ip.is_loopback
                ):
                    continue
                return str(ip)
    
    @staticmethod
    def generate_random_ipv6(
        prefix: str = "2001:db8::",
        subnet_bits: int = 64
    ) -> str:
        """
        Generate a random IPv6 address.
        
        Args:
            prefix: IPv6 prefix
            subnet_bits: Subnet prefix length
            
        Returns:
            str: Random IPv6 address
        """
        # Generate random interface ID
        interface_id = ':'.join(f'{random.randint(0, 65535):x}' for _ in range(4))
        return f"{prefix}{interface_id}"
    
    @staticmethod
    def is_valid_ip(ip_address: str) -> bool:
        """
        Validate IP address (v4 or v6).
        
        Args:
            ip_address: IP address to validate
            
        Returns:
            bool: True if valid
        """
        try:
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def get_ip_version(ip_address: str) -> Optional[int]:
        """
        Get IP version from address.
        
        Args:
            ip_address: IP address
            
        Returns:
            int: 4 or 6, or None if invalid
        """
        try:
            return ipaddress.ip_address(ip_address).version
        except ValueError:
            return None
    
    @classmethod
    def create_traceroute_packets(
        cls,
        src_ip: str,
        dst_ip: str,
        max_hops: int = 30,
        protocol: str = 'udp',
        **kwargs
    ) -> List[Union[IPv4Packet, IPv6Packet]]:
        """
        Create packets for traceroute with increasing TTL/hop limit.
        
        Args:
            src_ip: Source IP
            dst_ip: Destination IP
            max_hops: Maximum hops
            protocol: Protocol to use
            **kwargs: Additional parameters
            
        Returns:
            List of IP packets with increasing TTL/hop limit
        """
        packets = []
        proto_num = cls.PROTOCOLS.get(protocol.lower(), 17)  # Default UDP
        
        for ttl in range(1, max_hops + 1):
            if ':' in src_ip or ':' in dst_ip:
                packet = IPv6Packet(
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    hop_limit=ttl,
                    next_header=proto_num,
                    **kwargs
                )
            else:
                packet = IPv4Packet(
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    ttl=ttl,
                    protocol=proto_num,
                    **kwargs
                )
            packets.append(packet)
        
        return packets


# Module exports
__all__ = ['IPPacketFactory']