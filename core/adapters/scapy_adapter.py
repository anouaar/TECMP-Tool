#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scapy Adapter for TECMP-Tool.
Provides bidirectional conversion between TECMP-Tool packets and Scapy packets.
"""

import logging
from typing import Optional, Union, List, Dict, Any, Type, Tuple
from datetime import datetime

try:
    from scapy.all import *
    from scapy.layers.l2 import Ether, ARP, Dot1Q
    from scapy.layers.inet import IP, TCP, UDP, ICMP
    from scapy.layers.inet6 import IPv6, ICMPv6Unknown
    from scapy.packet import Raw
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    # Define dummy classes for type hints
    class Ether: pass
    class IP: pass
    class IPv6: pass
    class TCP: pass
    class UDP: pass
    class ARP: pass
    class Dot1Q: pass
    class Raw: pass

# Import TECMP-Tool packet classes
from core.packets.base.ethernet import EthernetPacket, MacAddress
from core.packets.network.ipv4 import IPv4Packet
from core.packets.network.ipv6 import IPv6Packet
from core.packets.transport.tcp import TCPPacket
from core.packets.transport.udp import UDPPacket
from core.packets.network.arp import ARPPacket
from core.packets.network.vlan import VLANPacket
from core.packets.base.packet import Packet
from core.exceptions.exceptions import PacketError


class ScapyAdapter:
    """
    Adapter for converting between TECMP-Tool packets and Scapy packets.
    Provides bidirectional conversion and utility methods for packet manipulation.
    """
    
    def __init__(self):
        """Initialize Scapy adapter"""
        self.logger = logging.getLogger("TECMP-Tool.ScapyAdapter")
        
        if not SCAPY_AVAILABLE:
            self.logger.warning("Scapy is not installed. Adapter functionality limited.")
        
        # Mapping of TECMP-Tool packet types to Scapy layers
        self.tecmp_to_scapy_map = {
            EthernetPacket: Ether,
            IPv4Packet: IP,
            IPv6Packet: IPv6,
            TCPPacket: TCP,
            UDPPacket: UDP,
            ARPPacket: ARP,
            VLANPacket: Dot1Q
        }
        
        # Reverse mapping
        self.scapy_to_tecmp_map = {
            Ether: EthernetPacket,
            IP: IPv4Packet,
            IPv6: IPv6Packet,
            TCP: TCPPacket,
            UDP: UDPPacket,
            ARP: ARPPacket,
            Dot1Q: VLANPacket
        }
    
    def is_available(self) -> bool:
        """
        Check if Scapy is available.
        
        Returns:
            bool: True if Scapy is installed
        """
        return SCAPY_AVAILABLE
    
    def from_tecmp_to_scapy(self, packet: Packet) -> Optional[Any]:
        """
        Convert TECMP-Tool packet to Scapy packet.
        
        Args:
            packet: TECMP-Tool packet instance
            
        Returns:
            Scapy packet or None if conversion fails
        """
        if not SCAPY_AVAILABLE:
            self.logger.error("Scapy not available")
            return None
        
        try:
            # Serialize the TECMP packet
            raw_data = packet.serialize()
            
            # Determine packet type and create appropriate Scapy packet
            if isinstance(packet, EthernetPacket):
                return self._ethernet_to_scapy(packet)
            elif isinstance(packet, IPv4Packet):
                return self._ipv4_to_scapy(packet)
            elif isinstance(packet, IPv6Packet):
                return self._ipv6_to_scapy(packet)
            elif isinstance(packet, TCPPacket):
                return self._tcp_to_scapy(packet)
            elif isinstance(packet, UDPPacket):
                return self._udp_to_scapy(packet)
            elif isinstance(packet, ARPPacket):
                return self._arp_to_scapy(packet)
            elif isinstance(packet, VLANPacket):
                return self._vlan_to_scapy(packet)
            else:
                # Try to parse as raw bytes
                return Ether(raw_data)
                
        except Exception as e:
            self.logger.error(f"Error converting to Scapy: {e}")
            return None
    
    def from_scapy_to_tecmp(self, scapy_packet: Any) -> Optional[Packet]:
        """
        Convert Scapy packet to TECMP-Tool packet.
        
        Args:
            scapy_packet: Scapy packet instance
            
        Returns:
            TECMP-Tool packet or None if conversion fails
        """
        if not SCAPY_AVAILABLE:
            self.logger.error("Scapy not available")
            return None
        
        try:
            # Get the bottom layer
            layer = scapy_packet
            while layer.underlayer is not None:
                layer = layer.underlayer
            
            # Build from bottom up
            return self._build_tecmp_stack(layer)
            
        except Exception as e:
            self.logger.error(f"Error converting from Scapy: {e}")
            return None
    
    def _ethernet_to_scapy(self, packet: EthernetPacket) -> Ether:
        """Convert EthernetPacket to Scapy Ether"""
        ether = Ether(
            src=str(packet.src_mac),
            dst=str(packet.dst_mac),
            type=packet.ether_type
        )
        
        if packet.payload:
            # Try to parse payload as next layer
            if packet.ether_type == 0x0800:  # IPv4
                try:
                    ip_packet = IPv4Packet(src_ip="0.0.0.0", dst_ip="0.0.0.0")
                    ip_packet.deserialize(packet.payload)
                    ether = ether / self._ipv4_to_scapy(ip_packet)
                except:
                    ether = ether / Raw(packet.payload)
            elif packet.ether_type == 0x86DD:  # IPv6
                try:
                    ip_packet = IPv6Packet(src_ip="::", dst_ip="::")
                    ip_packet.deserialize(packet.payload)
                    ether = ether / self._ipv6_to_scapy(ip_packet)
                except:
                    ether = ether / Raw(packet.payload)
            elif packet.ether_type == 0x0806:  # ARP
                try:
                    arp_packet = ARPPacket()
                    arp_packet.deserialize(packet.payload)
                    # Remove Ether layer for ARP as Scapy handles it differently
                    return self._arp_to_scapy(arp_packet)
                except:
                    ether = ether / Raw(packet.payload)
            else:
                ether = ether / Raw(packet.payload)
        
        return ether
    
    def _ipv4_to_scapy(self, packet: IPv4Packet) -> IP:
        """Convert IPv4Packet to Scapy IP"""
        ip = IP(
            version=packet.version,
            ihl=packet.ihl,
            tos=packet.tos,
            len=packet.total_length,
            id=packet.identification or 0,
            flags=packet.flags,
            frag=packet.fragment_offset,
            ttl=packet.ttl,
            proto=packet.protocol,
            src=packet.src_ip,
            dst=packet.dst_ip
        )
        
        # Add options if present
        if packet.options:
            ip.options = packet.options
        
        # Add payload
        if packet.payload:
            if packet.protocol == 6:  # TCP
                try:
                    tcp_packet = TCPPacket(src_port=0, dst_port=0)
                    tcp_packet.deserialize(packet.payload)
                    ip = ip / self._tcp_to_scapy(tcp_packet)
                except:
                    ip = ip / Raw(packet.payload)
            elif packet.protocol == 17:  # UDP
                try:
                    udp_packet = UDPPacket(src_port=0, dst_port=0)
                    udp_packet.deserialize(packet.payload)
                    ip = ip / self._udp_to_scapy(udp_packet)
                except:
                    ip = ip / Raw(packet.payload)
            else:
                ip = ip / Raw(packet.payload)
        
        return ip
    
    def _ipv6_to_scapy(self, packet: IPv6Packet) -> IPv6:
        """Convert IPv6Packet to Scapy IPv6"""
        ipv6 = IPv6(
            version=packet.version,
            tc=packet.traffic_class,
            fl=packet.flow_label,
            plen=packet.payload_length,
            nh=packet.next_header,
            hlim=packet.hop_limit,
            src=packet.src_ip,
            dst=packet.dst_ip
        )
        
        # Add payload
        if packet.payload:
            if packet.next_header == 6:  # TCP
                try:
                    tcp_packet = TCPPacket(src_port=0, dst_port=0)
                    tcp_packet.deserialize(packet.payload)
                    ipv6 = ipv6 / self._tcp_to_scapy(tcp_packet)
                except:
                    ipv6 = ipv6 / Raw(packet.payload)
            elif packet.next_header == 17:  # UDP
                try:
                    udp_packet = UDPPacket(src_port=0, dst_port=0)
                    udp_packet.deserialize(packet.payload)
                    ipv6 = ipv6 / self._udp_to_scapy(udp_packet)
                except:
                    ipv6 = ipv6 / Raw(packet.payload)
            else:
                ipv6 = ipv6 / Raw(packet.payload)
        
        return ipv6
    
    def _tcp_to_scapy(self, packet: TCPPacket) -> TCP:
        """Convert TCPPacket to Scapy TCP"""
        tcp = TCP(
            sport=packet.src_port,
            dport=packet.dst_port,
            seq=packet.seq_number,
            ack=packet.ack_number,
            dataofs=packet.data_offset,
            reserved=packet.reserved,
            flags=packet.flags,
            window=packet.window_size,
            chksum=packet.checksum,
            urgptr=packet.urgent_pointer
        )
        
        # Add TCP options
        options = []
        if packet.mss is not None:
            options.append(('MSS', packet.mss))
        if packet.window_scale is not None and packet.window_scale >= 0:
            options.append(('WScale', packet.window_scale))
        if packet.sack_permitted:
            options.append(('SAckOK', ''))
        if packet.timestamp:
            options.append(('Timestamp', packet.timestamp))
        
        if options:
            tcp.options = options
        
        # Add payload
        if packet.payload:
            tcp = tcp / Raw(packet.payload)
        
        return tcp
    
    def _udp_to_scapy(self, packet: UDPPacket) -> UDP:
        """Convert UDPPacket to Scapy UDP"""
        udp = UDP(
            sport=packet.src_port,
            dport=packet.dst_port,
            len=packet.length,
            chksum=packet.checksum
        )
        
        # Add payload
        if packet.payload:
            udp = udp / Raw(packet.payload)
        
        return udp
    
    def _arp_to_scapy(self, packet: ARPPacket) -> ARP:
        """Convert ARPPacket to Scapy ARP"""
        # Scapy ARP is typically encapsulated in Ether
        arp = ARP(
            hwtype=packet.hw_type,
            ptype=packet.proto_type,
            hwlen=packet.hw_len,
            plen=packet.proto_len,
            op=packet.operation,
            hwsrc=packet.sender_mac,
            psrc=packet.sender_ip,
            hwdst=packet.target_mac,
            pdst=packet.target_ip
        )
        
        # Wrap in Ether for broadcast ARP
        if packet.operation == 1:  # Request
            ether = Ether(src=packet.sender_mac, dst="ff:ff:ff:ff:ff:ff")
        else:  # Reply
            ether = Ether(src=packet.sender_mac, dst=packet.target_mac)
        
        return ether / arp
    
    def _vlan_to_scapy(self, packet: VLANPacket) -> Dot1Q:
        """Convert VLANPacket to Scapy Dot1Q"""
        dot1q = Dot1Q(
            prio=packet.priority,
            vlan=packet.vlan_id,
            type=packet.ether_type
        )
        
        # Add payload
        if packet.payload:
            # Try to parse next layer based on ether_type
            if packet.ether_type == 0x0800:  # IPv4
                try:
                    ip_packet = IPv4Packet(src_ip="0.0.0.0", dst_ip="0.0.0.0")
                    ip_packet.deserialize(packet.payload)
                    dot1q = dot1q / self._ipv4_to_scapy(ip_packet)
                except:
                    dot1q = dot1q / Raw(packet.payload)
            else:
                dot1q = dot1q / Raw(packet.payload)
        
        return dot1q
    
    def _build_tecmp_stack(self, bottom_layer: Any) -> Optional[Packet]:
        """Build TECMP packet stack from Scapy layers"""
        if isinstance(bottom_layer, Ether):
            return self._scapy_ether_to_tecmp(bottom_layer)
        elif isinstance(bottom_layer, IP):
            return self._scapy_ip_to_tecmp(bottom_layer)
        elif isinstance(bottom_layer, IPv6):
            return self._scapy_ipv6_to_tecmp(bottom_layer)
        elif isinstance(bottom_layer, TCP):
            return self._scapy_tcp_to_tecmp(bottom_layer)
        elif isinstance(bottom_layer, UDP):
            return self._scapy_udp_to_tecmp(bottom_layer)
        elif isinstance(bottom_layer, ARP):
            return self._scapy_arp_to_tecmp(bottom_layer)
        elif isinstance(bottom_layer, Dot1Q):
            return self._scapy_vlan_to_tecmp(bottom_layer)
        else:
            self.logger.warning(f"Unsupported Scapy layer type: {type(bottom_layer)}")
            return None
    
    def _scapy_ether_to_tecmp(self, ether: Ether) -> EthernetPacket:
        """Convert Scapy Ether to EthernetPacket"""
        # Get payload
        payload = b''
        if ether.payload:
            # Check if it's Raw or another layer
            if isinstance(ether.payload, Raw):
                payload = bytes(ether.payload)
            else:
                # Recursively convert upper layers
                upper_packet = self._build_tecmp_stack(ether.payload)
                if upper_packet:
                    payload = upper_packet.serialize()
                else:
                    payload = bytes(ether.payload)
        
        return EthernetPacket(
            src_mac=ether.src,
            dst_mac=ether.dst,
            ether_type=ether.type,
            payload=payload
        )
    
    def _scapy_ip_to_tecmp(self, ip: IP) -> IPv4Packet:
        """Convert Scapy IP to IPv4Packet"""
        # Get payload
        payload = b''
        if ip.payload:
            if isinstance(ip.payload, Raw):
                payload = bytes(ip.payload)
            else:
                upper_packet = self._build_tecmp_stack(ip.payload)
                if upper_packet:
                    payload = upper_packet.serialize()
                else:
                    payload = bytes(ip.payload)
        
        return IPv4Packet(
            src_ip=ip.src,
            dst_ip=ip.dst,
            version=ip.version,
            ihl=ip.ihl,
            tos=ip.tos,
            total_length=ip.len,
            identification=ip.id,
            flags=ip.flags,
            fragment_offset=ip.frag,
            ttl=ip.ttl,
            protocol=ip.proto,
            checksum=ip.chksum,
            payload=payload
        )
    
    def _scapy_ipv6_to_tecmp(self, ipv6: IPv6) -> IPv6Packet:
        """Convert Scapy IPv6 to IPv6Packet"""
        # Get payload
        payload = b''
        if ipv6.payload:
            if isinstance(ipv6.payload, Raw):
                payload = bytes(ipv6.payload)
            else:
                upper_packet = self._build_tecmp_stack(ipv6.payload)
                if upper_packet:
                    payload = upper_packet.serialize()
                else:
                    payload = bytes(ipv6.payload)
        
        return IPv6Packet(
            src_ip=ipv6.src,
            dst_ip=ipv6.dst,
            version=ipv6.version,
            traffic_class=ipv6.tc,
            flow_label=ipv6.fl,
            payload_length=ipv6.plen,
            next_header=ipv6.nh,
            hop_limit=ipv6.hlim,
            payload=payload
        )
    
    def _scapy_tcp_to_tecmp(self, tcp: TCP) -> TCPPacket:
        """Convert Scapy TCP to TCPPacket"""
        # Get payload
        payload = b''
        if tcp.payload:
            if isinstance(tcp.payload, Raw):
                payload = bytes(tcp.payload)
            else:
                payload = bytes(tcp.payload)
        
        # Extract options
        mss = None
        window_scale = None
        sack_permitted = False
        timestamp = None
        
        if hasattr(tcp, 'options') and tcp.options:
            for opt_name, opt_value in tcp.options:
                if opt_name == 'MSS':
                    mss = opt_value
                elif opt_name == 'WScale':
                    window_scale = opt_value
                elif opt_name == 'SAckOK':
                    sack_permitted = True
                elif opt_name == 'Timestamp':
                    timestamp = opt_value
        
        return TCPPacket(
            src_port=tcp.sport,
            dst_port=tcp.dport,
            seq_number=tcp.seq,
            ack_number=tcp.ack,
            data_offset=tcp.dataofs,
            reserved=tcp.reserved,
            flags=tcp.flags,
            window_size=tcp.window,
            checksum=tcp.chksum,
            urgent_pointer=tcp.urgptr,
            payload=payload,
            mss=mss,
            window_scale=window_scale,
            sack_permitted=sack_permitted,
            timestamp=timestamp
        )
    
    def _scapy_udp_to_tecmp(self, udp: UDP) -> UDPPacket:
        """Convert Scapy UDP to UDPPacket"""
        # Get payload
        payload = b''
        if udp.payload:
            if isinstance(udp.payload, Raw):
                payload = bytes(udp.payload)
            else:
                payload = bytes(udp.payload)
        
        return UDPPacket(
            src_port=udp.sport,
            dst_port=udp.dport,
            length=udp.len,
            checksum=udp.chksum,
            payload=payload
        )
    
    def _scapy_arp_to_tecmp(self, arp_layer: Any) -> ARPPacket:
        """Convert Scapy ARP to ARPPacket"""
        # Extract ARP from potential Ether encapsulation
        if isinstance(arp_layer, Ether) and isinstance(arp_layer.payload, ARP):
            arp = arp_layer.payload
        else:
            arp = arp_layer
        
        return ARPPacket(
            hw_type=arp.hwtype,
            proto_type=arp.ptype,
            hw_len=arp.hwlen,
            proto_len=arp.plen,
            operation=arp.op,
            sender_mac=arp.hwsrc,
            sender_ip=arp.psrc,
            target_mac=arp.hwdst,
            target_ip=arp.pdst
        )
    
    def _scapy_vlan_to_tecmp(self, dot1q: Dot1Q) -> VLANPacket:
        """Convert Scapy Dot1Q to VLANPacket"""
        # Get payload
        payload = b''
        if dot1q.payload:
            if isinstance(dot1q.payload, Raw):
                payload = bytes(dot1q.payload)
            else:
                upper_packet = self._build_tecmp_stack(dot1q.payload)
                if upper_packet:
                    payload = upper_packet.serialize()
                else:
                    payload = bytes(dot1q.payload)
        
        return VLANPacket(
            vlan_id=dot1q.vlan,
            priority=dot1q.prio,
            ether_type=dot1q.type,
            payload=payload
        )
    
    # Utility methods
    
    def read_pcap(self, filename: str) -> List[Packet]:
        """
        Read packets from PCAP file using Scapy.
        
        Args:
            filename: Path to PCAP file
            
        Returns:
            List of TECMP-Tool packets
        """
        if not SCAPY_AVAILABLE:
            self.logger.error("Scapy not available")
            return []
        
        try:
            scapy_packets = rdpcap(filename)
            tecmp_packets = []
            
            for scapy_pkt in scapy_packets:
                tecmp_pkt = self.from_scapy_to_tecmp(scapy_pkt)
                if tecmp_pkt:
                    tecmp_packets.append(tecmp_pkt)
                    
            self.logger.info(f"Read {len(tecmp_packets)} packets from {filename}")
            return tecmp_packets
            
        except Exception as e:
            self.logger.error(f"Error reading PCAP: {e}")
            return []
    
    def write_pcap(self, filename: str, packets: List[Packet]) -> bool:
        """
        Write packets to PCAP file using Scapy.
        
        Args:
            filename: Output PCAP filename
            packets: List of TECMP-Tool packets
            
        Returns:
            bool: True if successful
        """
        if not SCAPY_AVAILABLE:
            self.logger.error("Scapy not available")
            return False
        
        try:
            scapy_packets = []
            
            for tecmp_pkt in packets:
                scapy_pkt = self.from_tecmp_to_scapy(tecmp_pkt)
                if scapy_pkt:
                    scapy_packets.append(scapy_pkt)
            
            wrpcap(filename, scapy_packets)
            self.logger.info(f"Wrote {len(scapy_packets)} packets to {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing PCAP: {e}")
            return False
    
    def send_packet(self, packet: Packet, interface: Optional[str] = None) -> bool:
        """
        Send packet using Scapy.
        
        Args:
            packet: TECMP-Tool packet to send
            interface: Network interface (optional)
            
        Returns:
            bool: True if successful
        """
        if not SCAPY_AVAILABLE:
            self.logger.error("Scapy not available")
            return False
        
        try:
            scapy_pkt = self.from_tecmp_to_scapy(packet)
            if not scapy_pkt:
                return False
            
            if interface:
                sendp(scapy_pkt, iface=interface, verbose=False)
            else:
                send(scapy_pkt, verbose=False)
                
            self.logger.info(f"Sent packet: {packet.summary()}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending packet: {e}")
            return False
    
    def sniff_packets(
        self,
        count: int = 0,
        timeout: Optional[int] = None,
        interface: Optional[str] = None,
        filter_str: Optional[str] = None
    ) -> List[Packet]:
        """
        Sniff packets using Scapy.
        
        Args:
            count: Number of packets to capture (0 = infinite)
            timeout: Capture timeout in seconds
            interface: Network interface
            filter_str: BPF filter string
            
        Returns:
            List of captured TECMP-Tool packets
        """
        if not SCAPY_AVAILABLE:
            self.logger.error("Scapy not available")
            return []
        
        try:
            kwargs = {}
            if count > 0:
                kwargs['count'] = count
            if timeout:
                kwargs['timeout'] = timeout
            if interface:
                kwargs['iface'] = interface
            if filter_str:
                kwargs['filter'] = filter_str
            
            scapy_packets = sniff(**kwargs)
            tecmp_packets = []
            
            for scapy_pkt in scapy_packets:
                tecmp_pkt = self.from_scapy_to_tecmp(scapy_pkt)
                if tecmp_pkt:
                    tecmp_packets.append(tecmp_pkt)
            
            self.logger.info(f"Captured {len(tecmp_packets)} packets")
            return tecmp_packets
            
        except Exception as e:
            self.logger.error(f"Error sniffing packets: {e}")
            return []
    
    def analyze_packet(self, packet: Packet) -> Dict[str, Any]:
        """
        Analyze packet using Scapy's features.
        
        Args:
            packet: TECMP-Tool packet
            
        Returns:
            Dictionary with analysis results
        """
        if not SCAPY_AVAILABLE:
            return {"error": "Scapy not available"}
        
        try:
            scapy_pkt = self.from_tecmp_to_scapy(packet)
            if not scapy_pkt:
                return {"error": "Conversion failed"}
            
            analysis = {
                "layers": [],
                "summary": scapy_pkt.summary(),
                "fields": {},
                "hex_dump": hexdump(scapy_pkt, dump=True)
            }
            
            # Analyze each layer
            layer = scapy_pkt
            while layer:
                layer_info = {
                    "name": layer.__class__.__name__,
                    "fields": {}
                }
                
                # Get all fields
                for field in layer.fields_desc:
                    field_name = field.name
                    field_value = getattr(layer, field_name)
                    layer_info["fields"][field_name] = str(field_value)
                
                analysis["layers"].append(layer_info)
                layer = layer.payload if layer.payload else None
            
            return analysis
            
        except Exception as e:
            return {"error": str(e)}
    
    def craft_packet(self, packet_def: str) -> Optional[Packet]:
        """
        Craft packet using Scapy syntax and convert to TECMP.
        
        Args:
            packet_def: Scapy packet definition string
            
        Returns:
            TECMP-Tool packet or None
            
        Example:
            packet = adapter.craft_packet("Ether()/IP(dst='8.8.8.8')/TCP()")
        """
        if not SCAPY_AVAILABLE:
            self.logger.error("Scapy not available")
            return None
        
        try:
            # Evaluate Scapy packet definition
            scapy_pkt = eval(packet_def)
            
            # Convert to TECMP
            return self.from_scapy_to_tecmp(scapy_pkt)
            
        except Exception as e:
            self.logger.error(f"Error crafting packet: {e}")
            return None


# Singleton instance
_adapter_instance = None


def get_scapy_adapter() -> ScapyAdapter:
    """
    Get singleton instance of ScapyAdapter.
    
    Returns:
        ScapyAdapter: The adapter instance
    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = ScapyAdapter()
    return _adapter_instance


# Module exports
__all__ = ['ScapyAdapter', 'get_scapy_adapter']