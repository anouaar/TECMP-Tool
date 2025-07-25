# -*- coding: utf-8 -*-
"""
Ethernet factory - instancie systematiquement EthernetPacket
"""
from __future__ import annotations
from typing import Any
from core.packets.base.ethernet import EthernetPacket  # Import direct
# PacketFactory import removed


class EthernetPacketFactory:
    """Factory officielle pour la creation de paquets Ethernet."""
    
    PROTOCOL_NAME = "ethernet"
    
    # EtherType constants for convenience
    ETHERTYPES = {
        "IPV4": 0x0800,
        "ARP": 0x0806,
        "IPV6": 0x86DD,
        "VLAN": 0x8100,
        "TECMP": 0x88B5,  # TECMP protocol
        "LLDP": 0x88CC,
        "WAKE_ON_LAN": 0x0842,
    }
    
    @staticmethod
    def create_packet(**kw: Any) -> EthernetPacket:
        """
        Create an Ethernet packet with the provided parameters.
        
        Parameters
        ----------
        src_mac : str, optional (default="00:11:22:33:44:55")
            Source MAC address in format "XX:XX:XX:XX:XX:XX"
        dst_mac : str, optional (default="aa:bb:cc:dd:ee:ff")
            Destination MAC address in format "XX:XX:XX:XX:XX:XX"
        ether_type : int, optional (default=0x0800 IPV4)
            EtherType field value
        payload : bytes, optional
            Ethernet payload data
        ether_type_name : str, optional
            EtherType by name (IPV4, ARP, IPV6, VLAN, etc.)
            
        Returns
        -------
        EthernetPacket
        """
        # Handle EtherType by name
        ether_type = kw.get("ether_type", 0x0800)  # Default to IPv4
        if "ether_type_name" in kw:
            ether_type_name = kw["ether_type_name"].upper()
            if ether_type_name in EthernetPacketFactory.ETHERTYPES:
                ether_type = EthernetPacketFactory.ETHERTYPES[ether_type_name]
        
        # Create the Ethernet packet
        pkt = EthernetPacket(
            src_mac=kw.get("src_mac", "00:11:22:33:44:55"),
            dst_mac=kw.get("dst_mac", "aa:bb:cc:dd:ee:ff"),
            ether_type=ether_type,
            payload=kw.get("payload", b""),
        )
        
        # Removed pkt.serialize() - will be called when needed
        return pkt
    
    @staticmethod
    def create_ipv4_frame(src_mac: str, dst_mac: str, **kw: Any) -> EthernetPacket:
        """
        Create an Ethernet frame for IPv4 traffic.
        
        Parameters
        ----------
        src_mac : str
            Source MAC address
        dst_mac : str  
            Destination MAC address
        **kw : Any
            Additional parameters for create_packet()
            
        Returns
        -------
        EthernetPacket
        """
        return EthernetPacketFactory.create_packet(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=0x0800,  # IPv4
            **kw
        )
    
    @staticmethod
    def create_arp_frame(src_mac: str, dst_mac: str = "ff:ff:ff:ff:ff:ff", **kw: Any) -> EthernetPacket:
        """
        Create an Ethernet frame for ARP traffic.
        
        Parameters
        ----------
        src_mac : str
            Source MAC address
        dst_mac : str, optional (default=broadcast)
            Destination MAC address (broadcast for ARP requests)
        **kw : Any
            Additional parameters for create_packet()
            
        Returns
        -------
        EthernetPacket
        """
        return EthernetPacketFactory.create_packet(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=0x0806,  # ARP
            **kw
        )
    
    @staticmethod
    def create_vlan_frame(src_mac: str, dst_mac: str, **kw: Any) -> EthernetPacket:
        """
        Create an Ethernet frame for VLAN tagged traffic.
        
        Parameters
        ----------
        src_mac : str
            Source MAC address
        dst_mac : str
            Destination MAC address
        **kw : Any
            Additional parameters for create_packet()
            
        Returns
        -------
        EthernetPacket
        """
        return EthernetPacketFactory.create_packet(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=0x8100,  # VLAN
            **kw
        )
    
    @staticmethod
    def create_tecmp_frame(src_mac: str, dst_mac: str, **kw: Any) -> EthernetPacket:
        """
        Create an Ethernet frame for TECMP traffic.
        
        Parameters
        ----------
        src_mac : str
            Source MAC address
        dst_mac : str
            Destination MAC address
        **kw : Any
            Additional parameters for create_packet()
            
        Returns
        -------
        EthernetPacket
        """
        return EthernetPacketFactory.create_packet(
            src_mac=src_mac,
            dst_mac=dst_mac,
            ether_type=0x88B5,  # TECMP
            **kw
        )