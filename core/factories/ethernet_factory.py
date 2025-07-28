#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ethernet Packet Factory for creating and managing Ethernet frames.
Provides convenient methods for creating various Ethernet packet types.
"""

import random
from typing import Optional, Dict, Any, List, Union, Tuple

# Import Ethernet packet from the base module
from core.packets.base.ethernet import EthernetPacket, MacAddress
from core.packets.base.packet import Packet, PacketError


class EthernetPacketFactory:
    """
    Factory class for creating Ethernet packets with various configurations.
    Note: Class name is EthernetPacketFactory for compatibility with existing imports.
    """
    
    # Common MAC addresses
    BROADCAST_MAC = "FF:FF:FF:FF:FF:FF"
    IPV4_MULTICAST_PREFIX = "01:00:5E"
    IPV6_MULTICAST_PREFIX = "33:33"
    LLDP_MULTICAST = "01:80:C2:00:00:0E"
    STP_MULTICAST = "01:80:C2:00:00:00"
    CDP_MULTICAST = "01:00:0C:CC:CC:CC"
    
    # OUI (Organizationally Unique Identifier) prefixes
    OUI_CISCO = "00:00:0C"
    OUI_VMWARE = "00:50:56"
    OUI_VIRTUALBOX = "08:00:27"
    OUI_INTEL = "00:1B:21"
    OUI_REALTEK = "00:E0:4C"
    
    @staticmethod
    def create_packet(**kwargs) -> EthernetPacket:
        """
        Create a generic Ethernet packet with provided parameters.
        Method name matches packet_factory expectations.
        
        Args:
            **kwargs: All parameters accepted by EthernetPacket constructor
            
        Returns:
            EthernetPacket: Configured Ethernet packet instance
        """
        return EthernetPacket(**kwargs)
    
    @staticmethod
    def create_ethernet_packet(**kwargs) -> EthernetPacket:
        """
        Alternative method name for creating Ethernet packets.
        
        Args:
            **kwargs: All parameters accepted by EthernetPacket constructor
            
        Returns:
            EthernetPacket: Configured Ethernet packet instance
        """
        return EthernetPacket(**kwargs)
    
    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> EthernetPacket:
        """
        Create Ethernet packet from configuration dictionary (e.g., from UI dialog).
        
        Args:
            config: Configuration dictionary with Ethernet parameters
            
        Returns:
            EthernetPacket: Configured Ethernet packet instance
        """
        # Extract parameters
        packet_params = {}
        
        # MAC addresses
        packet_params['src_mac'] = config.get('src_mac', '00:00:00:00:00:00')
        packet_params['dst_mac'] = config.get('dst_mac', 'FF:FF:FF:FF:FF:FF')
        
        # EtherType
        ether_type = config.get('ether_type', 0x0800)
        if isinstance(ether_type, str):
            # Handle hex string format
            if ether_type.startswith('0x'):
                packet_params['ether_type'] = int(ether_type, 16)
            else:
                packet_params['ether_type'] = int(ether_type)
        else:
            packet_params['ether_type'] = int(ether_type)
        
        # Payload
        if 'payload' in config:
            payload = config['payload']
            if isinstance(payload, str):
                # Check if hex format
                if payload.startswith('0x') or all(c in '0123456789abcdefABCDEF ' for c in payload):
                    try:
                        payload = payload.replace(' ', '').replace('0x', '')
                        packet_params['payload'] = bytes.fromhex(payload)
                    except ValueError:
                        # Not valid hex, treat as string
                        packet_params['payload'] = payload.encode('utf-8')
                else:
                    packet_params['payload'] = payload.encode('utf-8')
            else:
                packet_params['payload'] = payload or b''
        
        # Optional fields
        if 'preamble' in config:
            packet_params['preamble'] = config['preamble']
        if 'sfd' in config:
            packet_params['sfd'] = config['sfd']
        if 'fcs' in config:
            fcs = config['fcs']
            if isinstance(fcs, str):
                if fcs == '0' or fcs.lower() == 'auto':
                    packet_params['fcs'] = None
                    packet_params['auto_fcs'] = True
                else:
                    try:
                        packet_params['fcs'] = int(fcs, 16 if fcs.startswith('0x') else 10)
                    except:
                        packet_params['fcs'] = None
            else:
                packet_params['fcs'] = fcs
        
        # Auto flags
        packet_params['auto_fcs'] = config.get('auto_fcs', True)
        packet_params['auto_pad'] = config.get('auto_pad', True)
        
        # Metadata
        if 'interface' in config:
            packet_params['interface'] = config['interface']
        if 'vlan_id' in config:
            packet_params['vlan_id'] = config['vlan_id']
        
        # Validation
        packet_params['strict_validation'] = config.get('strict_validation', True)
        
        return EthernetPacket(**packet_params)
    
    @staticmethod
    def create_broadcast(
        src_mac: Union[str, MacAddress],
        ether_type: int = 0x0800,
        payload: bytes = b''
    ) -> EthernetPacket:
        """
        Create a broadcast Ethernet frame.
        
        Args:
            src_mac: Source MAC address
            ether_type: EtherType (default IPv4)
            payload: Frame payload
            
        Returns:
            EthernetPacket: Broadcast frame
        """
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=EthernetPacketFactory.BROADCAST_MAC,
            ether_type=ether_type,
            payload=payload
        )
    
    @staticmethod
    def create_multicast(
        src_mac: Union[str, MacAddress],
        multicast_group: str,
        ether_type: int = 0x0800,
        payload: bytes = b''
    ) -> EthernetPacket:
        """
        Create a multicast Ethernet frame.
        
        Args:
            src_mac: Source MAC address
            multicast_group: Multicast MAC address
            ether_type: EtherType
            payload: Frame payload
            
        Returns:
            EthernetPacket: Multicast frame
        """
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=multicast_group,
            ether_type=ether_type,
            payload=payload
        )
    
    @staticmethod
    def create_ipv4_frame(
        src_mac: Union[str, MacAddress],
        dst_mac: Union[str, MacAddress],
        payload: bytes = b''
    ) -> EthernetPacket:
        """
        Create an Ethernet frame for IPv4.
        
        Args:
            src_mac: Source MAC address
            dst_mac: Destination MAC address
            payload: IPv4 packet as payload
            
        Returns:
            EthernetPacket: IPv4 Ethernet frame
        """
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=EthernetPacket.ETHERTYPE_IPV4,
            payload=payload
        )
    
    @staticmethod
    def create_ipv6_frame(
        src_mac: Union[str, MacAddress],
        dst_mac: Union[str, MacAddress],
        payload: bytes = b''
    ) -> EthernetPacket:
        """
        Create an Ethernet frame for IPv6.
        
        Args:
            src_mac: Source MAC address
            dst_mac: Destination MAC address
            payload: IPv6 packet as payload
            
        Returns:
            EthernetPacket: IPv6 Ethernet frame
        """
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=EthernetPacket.ETHERTYPE_IPV6,
            payload=payload
        )
    
    @staticmethod
    def create_arp_frame(
        src_mac: Union[str, MacAddress],
        payload: bytes = b''
    ) -> EthernetPacket:
        """
        Create an Ethernet frame for ARP.
        
        Args:
            src_mac: Source MAC address
            payload: ARP packet as payload
            
        Returns:
            EthernetPacket: ARP Ethernet frame
        """
        # ARP typically uses broadcast
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=EthernetPacketFactory.BROADCAST_MAC,
            ether_type=EthernetPacket.ETHERTYPE_ARP,
            payload=payload
        )
    
    @staticmethod
    def create_vlan_frame(
        src_mac: Union[str, MacAddress],
        dst_mac: Union[str, MacAddress],
        payload: bytes = b''
    ) -> EthernetPacket:
        """
        Create an Ethernet frame for VLAN (802.1Q).
        
        Args:
            src_mac: Source MAC address
            dst_mac: Destination MAC address
            payload: VLAN tagged payload
            
        Returns:
            EthernetPacket: VLAN Ethernet frame
        """
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=EthernetPacket.ETHERTYPE_VLAN,
            payload=payload
        )
    
    @staticmethod
    def create_lldp_frame(
        src_mac: Union[str, MacAddress],
        payload: bytes = b''
    ) -> EthernetPacket:
        """
        Create an Ethernet frame for LLDP.
        
        Args:
            src_mac: Source MAC address
            payload: LLDP payload
            
        Returns:
            EthernetPacket: LLDP frame
        """
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=EthernetPacketFactory.LLDP_MULTICAST,
            ether_type=EthernetPacket.ETHERTYPE_LLDP,
            payload=payload
        )
    
    @staticmethod
    def create_with_random_macs(
        ether_type: int = 0x0800,
        payload: bytes = b'',
        src_oui: Optional[str] = None,
        unicast: bool = True
    ) -> EthernetPacket:
        """
        Create an Ethernet frame with random MAC addresses.
        
        Args:
            ether_type: EtherType
            payload: Frame payload
            src_oui: OUI prefix for source MAC (e.g., "00:50:56" for VMware)
            unicast: Generate unicast destination MAC
            
        Returns:
            EthernetPacket: Frame with random MACs
        """
        src_mac = EthernetPacketFactory.generate_random_mac(oui=src_oui, unicast=True)
        dst_mac = EthernetPacketFactory.generate_random_mac(unicast=unicast)
        
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=ether_type,
            payload=payload
        )
    
    @staticmethod
    def create_minimum_frame(
        src_mac: Union[str, MacAddress] = "00:00:00:00:00:01",
        dst_mac: Union[str, MacAddress] = "00:00:00:00:00:02",
        ether_type: int = 0x0800
    ) -> EthernetPacket:
        """
        Create a minimum-sized Ethernet frame (64 bytes with FCS).
        
        Args:
            src_mac: Source MAC address
            dst_mac: Destination MAC address
            ether_type: EtherType
            
        Returns:
            EthernetPacket: Minimum-sized frame
        """
        # Minimum payload is 46 bytes
        min_payload = b'\x00' * 46
        
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=ether_type,
            payload=min_payload,
            auto_pad=False  # Already padded
        )
    
    @staticmethod
    def create_jumbo_frame(
        src_mac: Union[str, MacAddress],
        dst_mac: Union[str, MacAddress],
        payload_size: int = 9000,
        ether_type: int = 0x0800
    ) -> EthernetPacket:
        """
        Create a jumbo Ethernet frame.
        
        Args:
            src_mac: Source MAC address
            dst_mac: Destination MAC address
            payload_size: Jumbo payload size (default 9000)
            ether_type: EtherType
            
        Returns:
            EthernetPacket: Jumbo frame
        """
        # Generate payload of specified size
        payload = bytes(range(256)) * (payload_size // 256 + 1)
        payload = payload[:payload_size]
        
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=ether_type,
            payload=payload,
            strict_validation=False  # Jumbo frames exceed standard size
        )
    
    @staticmethod
    def generate_random_mac(
        oui: Optional[str] = None,
        unicast: bool = True,
        local: bool = True
    ) -> str:
        """
        Generate a random MAC address.
        
        Args:
            oui: OUI prefix (first 3 octets)
            unicast: Generate unicast address
            local: Generate locally administered address
            
        Returns:
            str: Random MAC address
        """
        if oui:
            # Use provided OUI
            oui_bytes = MacAddress(oui + ":00:00:00").bytes[:3]
            nic_bytes = bytes([random.randint(0, 255) for _ in range(3)])
            mac_bytes = oui_bytes + nic_bytes
        else:
            # Generate random
            mac_bytes = bytearray([random.randint(0, 255) for _ in range(6)])
            
            # Set flags in first octet
            if unicast:
                mac_bytes[0] &= 0xFE  # Clear multicast bit
            else:
                mac_bytes[0] |= 0x01  # Set multicast bit
                
            if local:
                mac_bytes[0] |= 0x02  # Set locally administered bit
            else:
                mac_bytes[0] &= 0xFD  # Clear locally administered bit
        
        return str(MacAddress(bytes(mac_bytes)))
    
    @staticmethod
    def is_valid_mac(mac: str) -> bool:
        """
        Validate MAC address format.
        
        Args:
            mac: MAC address to validate
            
        Returns:
            bool: True if valid
        """
        try:
            MacAddress(mac)
            return True
        except:
            return False
    
    @staticmethod
    def is_valid_ethertype(ether_type: int) -> bool:
        """
        Validate EtherType value.
        
        Args:
            ether_type: EtherType to validate
            
        Returns:
            bool: True if valid
        """
        # Valid ranges: 0-1500 (length) or >= 1536 (type)
        if 0 <= ether_type <= 1500:
            return True
        elif ether_type >= 0x0600:  # 1536
            return True
        return False
    
    @classmethod
    def create_test_frames(cls, count: int = 5) -> List[EthernetPacket]:
        """
        Create a set of test frames with various configurations.
        
        Args:
            count: Number of frames to create
            
        Returns:
            List[EthernetPacket]: Test frames
        """
        frames = []
        
        configs = [
            # Broadcast ARP
            {'dst_mac': cls.BROADCAST_MAC, 'ether_type': 0x0806},
            # Unicast IPv4
            {'ether_type': 0x0800},
            # IPv6
            {'ether_type': 0x86DD},
            # VLAN
            {'ether_type': 0x8100},
            # Random
            {}
        ]
        
        for i in range(count):
            config = configs[i % len(configs)].copy()
            
            # Add random MACs if not specified
            if 'src_mac' not in config:
                config['src_mac'] = cls.generate_random_mac()
            if 'dst_mac' not in config:
                config['dst_mac'] = cls.generate_random_mac()
            
            # Add test payload
            config['payload'] = f"Test frame {i + 1}".encode()
            
            frames.append(EthernetPacket(**config))
        
        return frames
    
    @classmethod
    def encapsulate_packet(
        cls,
        inner_packet: Packet,
        src_mac: Union[str, MacAddress],
        dst_mac: Union[str, MacAddress],
        ether_type: Optional[int] = None
    ) -> EthernetPacket:
        """
        Encapsulate another packet in an Ethernet frame.
        
        Args:
            inner_packet: Packet to encapsulate
            src_mac: Source MAC address
            dst_mac: Destination MAC address
            ether_type: EtherType (auto-detected if None)
            
        Returns:
            EthernetPacket: Ethernet frame containing the packet
        """
        # Auto-detect EtherType based on packet type
        if ether_type is None:
            packet_type = type(inner_packet).__name__.lower()
            if 'ipv4' in packet_type:
                ether_type = EthernetPacket.ETHERTYPE_IPV4
            elif 'ipv6' in packet_type:
                ether_type = EthernetPacket.ETHERTYPE_IPV6
            elif 'arp' in packet_type:
                ether_type = EthernetPacket.ETHERTYPE_ARP
            elif 'vlan' in packet_type:
                ether_type = EthernetPacket.ETHERTYPE_VLAN
            else:
                ether_type = 0x0800  # Default to IPv4
        
        # Serialize inner packet
        payload = inner_packet.serialize()
        
        return EthernetPacket(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=ether_type,
            payload=payload
        )


# Module exports
__all__ = ['EthernetPacketFactory']