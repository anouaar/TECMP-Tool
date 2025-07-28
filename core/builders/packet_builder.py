#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Real Packet Builder - Aucun Fallback AutorisÃ©
==============================================

Builder qui utilise UNIQUEMENT de vraies factories et de vrais packets.
Pas de FallbackPacket ou de mock objects.
"""

from typing import Dict, Optional, Union, List, Any
from enum import Enum, auto
from abc import ABC, abstractmethod
import threading
import importlib
import sys
import time

class ProtocolType(Enum):
    """Types de protocoles supportÃ©s"""
    ETHERNET = "ethernet"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    TCP = "tcp"
    UDP = "udp"
    VLAN = "vlan"
    ARP = "arp"
    TECMP = "tecmp"

class PacketBuilderError(Exception):
    """Exception de base du builder"""
    pass

class FactoryNotFoundError(PacketBuilderError):
    """Exception quand une factory n'est pas trouvÃ©e"""
    pass

class RealPacketFactory(ABC):
    """Factory de base pour crÃ©er de vrais packets"""
    
    @abstractmethod
    def create_packet(self, **kwargs) -> 'RealPacket':
        """CrÃ©e un vrai packet avec les paramètres donnÃ©s"""
        pass
    
    @abstractmethod
    def get_protocol_type(self) -> ProtocolType:
        """Retourne le type de protocole gÃ©rÃ© par cette factory"""
        pass

class RealPacket(ABC):
    """Packet de base - tous les packets doivent hÃ©riter de cette classe"""
    
    def __init__(self):
        self.payload: Optional['RealPacket'] = None
        self.raw_data: bytes = b''
        self.header_size: int = 0
    
    @abstractmethod
    def serialize(self) -> bytes:
        """SÃ©rialise le packet en bytes"""
        pass
    
    @abstractmethod
    def get_header_length(self) -> int:
        """Retourne la taille de l'en-tête"""
        pass
    
    def encapsulate(self, upper_layer: 'RealPacket') -> None:
        """Encapsule une couche supÃ©rieure"""
        self.payload = upper_layer
    
    def calculate_checksums(self) -> None:
        """Calcule les checksums si nÃ©cessaire"""
        pass

# ============================================================================
# IMPLÉMENTATIONS DE VRAIS PACKETS
# ============================================================================

class EthernetPacket(RealPacket):
    """Vrai packet Ethernet"""
    
    def __init__(self, src_mac: str = "00:00:00:00:00:00", 
                 dst_mac: str = "00:00:00:00:00:00", 
                 ethertype: int = 0x0800):
        super().__init__()
        self.src_mac = self._parse_mac(src_mac)
        self.dst_mac = self._parse_mac(dst_mac)
        self.ethertype = ethertype
        self.header_size = 14
    
    def _parse_mac(self, mac: str) -> bytes:
        """Parse une adresse MAC"""
        return bytes.fromhex(mac.replace(':', ''))
    
    def serialize(self) -> bytes:
        """SÃ©rialise l'en-tête Ethernet"""
        header = self.dst_mac + self.src_mac + self.ethertype.to_bytes(2, 'big')
        payload_data = self.payload.serialize() if self.payload else b''
        return header + payload_data
    
    def get_header_length(self) -> int:
        return self.header_size

class IPv4Packet(RealPacket):
    """Vrai packet IPv4"""
    
    def __init__(self, src_ip: str = "0.0.0.0", dst_ip: str = "0.0.0.0", 
                 protocol: int = 6, ttl: int = 64):
        super().__init__()
        self.version = 4
        self.ihl = 5  # Header length in 32-bit words
        self.tos = 0
        self.total_length = 20  # Will be calculated
        self.identification = 0
        self.flags = 2  # Don't fragment
        self.fragment_offset = 0
        self.ttl = ttl
        self.protocol = protocol
        self.checksum = 0
        self.src_ip = self._parse_ip(src_ip)
        self.dst_ip = self._parse_ip(dst_ip)
        self.header_size = 20
    
    def _parse_ip(self, ip: str) -> bytes:
        """Parse une adresse IP"""
        return bytes([int(x) for x in ip.split('.')])
    
    def serialize(self) -> bytes:
        """SÃ©rialise l'en-tête IPv4"""
        payload_data = self.payload.serialize() if self.payload else b''
        self.total_length = self.header_size + len(payload_data)
        
        # Construire l'en-tête
        header = bytearray(20)
        header[0] = (self.version << 4) | self.ihl
        header[1] = self.tos
        header[2:4] = self.total_length.to_bytes(2, 'big')
        header[4:6] = self.identification.to_bytes(2, 'big')
        header[6:8] = ((self.flags << 13) | self.fragment_offset).to_bytes(2, 'big')
        header[8] = self.ttl
        header[9] = self.protocol
        header[10:12] = (0).to_bytes(2, 'big')  # Checksum placeholder
        header[12:16] = self.src_ip
        header[16:20] = self.dst_ip
        
        # Calculer checksum
        self.checksum = self._calculate_checksum(header)
        header[10:12] = self.checksum.to_bytes(2, 'big')
        
        return bytes(header) + payload_data
    
    def _calculate_checksum(self, header: bytearray) -> int:
        """Calcule le checksum IPv4"""
        checksum = 0
        for i in range(0, len(header), 2):
            if i + 1 < len(header):
                checksum += (header[i] << 8) + header[i + 1]
            else:
                checksum += header[i] << 8
        
        while checksum >> 16:
            checksum = (checksum & 0xFFFF) + (checksum >> 16)
        
        return ~checksum & 0xFFFF
    
    def get_header_length(self) -> int:
        return self.header_size

class TCPPacket(RealPacket):
    """Vrai packet TCP"""
    
    def __init__(self, src_port: int = 0, dst_port: int = 0, 
                 seq: int = 0, ack: int = 0, flags: int = 0):
        super().__init__()
        self.src_port = src_port
        self.dst_port = dst_port
        self.seq = seq
        self.ack = ack
        self.data_offset = 5  # Header length in 32-bit words
        self.reserved = 0
        self.flags = flags
        self.window = 65535
        self.checksum = 0
        self.urgent_ptr = 0
        self.header_size = 20
    
    def serialize(self) -> bytes:
        """SÃ©rialise l'en-tête TCP"""
        payload_data = self.payload.serialize() if self.payload else b''
        
        # Construire l'en-tête TCP
        header = bytearray(20)
        header[0:2] = self.src_port.to_bytes(2, 'big')
        header[2:4] = self.dst_port.to_bytes(2, 'big')
        header[4:8] = self.seq.to_bytes(4, 'big')
        header[8:12] = self.ack.to_bytes(4, 'big')
        header[12] = (self.data_offset << 4) | self.reserved
        header[13] = self.flags
        header[14:16] = self.window.to_bytes(2, 'big')
        header[16:18] = (0).to_bytes(2, 'big')  # Checksum placeholder
        header[18:20] = self.urgent_ptr.to_bytes(2, 'big')
        
        return bytes(header) + payload_data
    
    def get_header_length(self) -> int:
        return self.header_size

class UDPPacket(RealPacket):
    """Vrai packet UDP"""
    
    def __init__(self, src_port: int = 0, dst_port: int = 0):
        super().__init__()
        self.src_port = src_port
        self.dst_port = dst_port
        self.length = 8  # Will be calculated
        self.checksum = 0
        self.header_size = 8
    
    def serialize(self) -> bytes:
        """SÃ©rialise l'en-tête UDP"""
        payload_data = self.payload.serialize() if self.payload else b''
        self.length = self.header_size + len(payload_data)
        
        header = bytearray(8)
        header[0:2] = self.src_port.to_bytes(2, 'big')
        header[2:4] = self.dst_port.to_bytes(2, 'big')
        header[4:6] = self.length.to_bytes(2, 'big')
        header[6:8] = self.checksum.to_bytes(2, 'big')
        
        return bytes(header) + payload_data
    
    def get_header_length(self) -> int:
        return self.header_size

# ============================================================================
# VRAIES FACTORIES
# ============================================================================

class EthernetPacketFactory(RealPacketFactory):
    """Factory pour crÃ©er de vrais packets Ethernet"""
    
    def create_packet(self, **kwargs) -> EthernetPacket:
        return EthernetPacket(**kwargs)
    
    def get_protocol_type(self) -> ProtocolType:
        return ProtocolType.ETHERNET

class IPv4PacketFactory(RealPacketFactory):
    """Factory pour crÃ©er de vrais packets IPv4"""
    
    def create_packet(self, **kwargs) -> IPv4Packet:
        return IPv4Packet(**kwargs)
    
    def get_protocol_type(self) -> ProtocolType:
        return ProtocolType.IPV4

class TCPPacketFactory(RealPacketFactory):
    """Factory pour crÃ©er de vrais packets TCP"""
    
    def create_packet(self, **kwargs) -> TCPPacket:
        return TCPPacket(**kwargs)
    
    def get_protocol_type(self) -> ProtocolType:
        return ProtocolType.TCP

class UDPPacketFactory(RealPacketFactory):
    """Factory pour crÃ©er de vrais packets UDP"""
    
    def create_packet(self, **kwargs) -> UDPPacket:
        return UDPPacket(**kwargs)
    
    def get_protocol_type(self) -> ProtocolType:
        return ProtocolType.UDP

# ============================================================================
# REGISTRY STRICT - AUCUN FALLBACK
# ============================================================================

class StrictFactoryRegistry:
    """
    Registry stricte - AUCUN fallback autorisÃ©
    Si une factory n'existe pas, on lève une exception
    """
    
    def __init__(self):
        self._factories: Dict[ProtocolType, RealPacketFactory] = {}
        self._lock = threading.RLock()
        
        # Enregistrer les factories rÃ©elles
        self._register_real_factories()
    
    def _register_real_factories(self) -> None:
        """Enregistre UNIQUEMENT les vraies factories disponibles"""
        real_factories = [
            EthernetPacketFactory(),
            IPv4PacketFactory(),
            TCPPacketFactory(),
            UDPPacketFactory(),
        ]
        
        for factory in real_factories:
            protocol_type = factory.get_protocol_type()
            self._factories[protocol_type] = factory
            print(f"? Registered REAL factory for {protocol_type.value}")
    
    def register_factory(self, factory: RealPacketFactory) -> None:
        """Enregistre une vraie factory"""
        if not isinstance(factory, RealPacketFactory):
            raise TypeError("Only RealPacketFactory instances are allowed")
        
        with self._lock:
            protocol_type = factory.get_protocol_type()
            self._factories[protocol_type] = factory
            print(f"? Registered custom factory for {protocol_type.value}")
    
    def get_factory(self, protocol_type: ProtocolType) -> RealPacketFactory:
        """
        RÃ©cupère une factory - ÉCHEC SI PAS TROUVÉE
        AUCUN FALLBACK !
        """
        with self._lock:
            if protocol_type not in self._factories:
                available = list(self._factories.keys())
                raise FactoryNotFoundError(
                    f"? No REAL factory found for {protocol_type.value}. "
                    f"Available protocols: {[p.value for p in available]}"
                )
            
            return self._factories[protocol_type]
    
    def list_available_protocols(self) -> List[ProtocolType]:
        """Liste les protocoles avec de vraies factories"""
        with self._lock:
            return list(self._factories.keys())
    
    def is_available(self, protocol_type: ProtocolType) -> bool:
        """VÃ©rifie si une vraie factory existe"""
        with self._lock:
            return protocol_type in self._factories

# ============================================================================
# BUILDER STRICT
# ============================================================================

class RealPacketBuilder:
    """
    Builder qui utilise UNIQUEMENT de vraies factories
    Aucun fallback - Ã©chec rapide si factory manquante
    """
    
    def __init__(self):
        self._factory_registry = StrictFactoryRegistry()
        self._layers: List[RealPacket] = []
        self._built_packet: Optional[RealPacket] = None
        
        print("?? RealPacketBuilder initialized - NO FALLBACKS ALLOWED")
    
    def add_layer(self, protocol: Union[str, ProtocolType], **kwargs) -> 'RealPacketBuilder':
        """
        Ajoute une couche avec UNE VRAIE FACTORY
        Lève une exception si la factory n'existe pas
        """
        # Conversion vers enum
        if isinstance(protocol, str):
            try:
                protocol_type = ProtocolType(protocol.lower())
            except ValueError:
                available = [p.value for p in self._factory_registry.list_available_protocols()]
                raise PacketBuilderError(
                    f"? Unknown protocol '{protocol}'. Available: {available}"
                )
        else:
            protocol_type = protocol
        
        # RÃ©cupÃ©ration de la VRAIE factory (peut lever FactoryNotFoundError)
        factory = self._factory_registry.get_factory(protocol_type)
        
        # CrÃ©ation du VRAI packet
        packet = factory.create_packet(**kwargs)
        
        # VÃ©rification que c'est bien un RealPacket
        if not isinstance(packet, RealPacket):
            raise TypeError(
                f"Factory for {protocol_type.value} returned {type(packet)}, "
                f"expected RealPacket subclass"
            )
        
        self._layers.append(packet)
        self._built_packet = None  # Reset
        
        print(f"? Added REAL {protocol_type.value} layer: {type(packet).__name__}")
        
        return self
    
    def build(self) -> Optional[RealPacket]:
        """
        Construit la pile de protocoles avec de vrais packets
        """
        if not self._layers:
            raise PacketBuilderError("? Cannot build packet from empty stack")
        
        # Commencer par la couche de base
        bottom_packet = self._layers[0]
        current_packet = bottom_packet
        
        # Encapsuler chaque couche supÃ©rieure
        for layer in self._layers[1:]:
            current_packet.encapsulate(layer)
            current_packet = layer
        
        self._built_packet = bottom_packet
        
        # Calculer les checksums
        for layer in self._layers:
            layer.calculate_checksums()
        
        print(f"? Built REAL packet stack with {len(self._layers)} layers")
        return self._built_packet
    
    def get_available_protocols(self) -> List[str]:
        """Liste des protocoles avec de vraies factories"""
        return [p.value for p in self._factory_registry.list_available_protocols()]
    
    def register_custom_factory(self, factory: RealPacketFactory) -> 'RealPacketBuilder':
        """Enregistre une factory personnalisÃ©e"""
        self._factory_registry.register_factory(factory)
        return self
    
    def get_layer_count(self) -> int:
        """Nombre de couches ajoutÃ©es"""
        return len(self._layers)
    
    def get_total_size(self) -> int:
        """Taille totale du packet construit"""
        if self._built_packet:
            return len(self._built_packet.serialize())
        return 0
    
    def clear(self) -> 'RealPacketBuilder':
        """Vide la pile"""
        self._layers.clear()
        self._built_packet = None
        print("?? Cleared packet stack")
        return self

# ============================================================================
# FONCTION UTILITAIRE
# ============================================================================

def create_real_builder() -> RealPacketBuilder:
    """CrÃ©e un builder strict sans fallback"""
    return RealPacketBuilder()

# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    print("=== REAL PACKET BUILDER - NO FALLBACKS ===\n")
    
    # CrÃ©er le builder
    builder = create_real_builder()
    
    print(f"Available protocols: {builder.get_available_protocols()}\n")
    
    try:
        # Construire un packet rÃ©el
        packet = (builder
                 .add_layer("ethernet", 
                           src_mac="aa:bb:cc:dd:ee:ff", 
                           dst_mac="11:22:33:44:55:66")
                 .add_layer("ipv4", 
                           src_ip="192.168.1.1", 
                           dst_ip="192.168.1.100")
                 .add_layer("tcp", 
                           src_port=12345, 
                           dst_port=80, 
                           flags=0x18)  # PSH+ACK
                 .build())
        
        if packet:
            serialized = packet.serialize()
            print(f"? SUCCESS: Built real packet")
            print(f"   Type: {type(packet).__name__}")
            print(f"   Total size: {len(serialized)} bytes")
            print(f"   Layers: {builder.get_layer_count()}")
            print(f"   Raw data: {serialized[:32].hex()}...")
        
    except FactoryNotFoundError as e:
        print(f"? FACTORY ERROR: {e}")
    except Exception as e:
        print(f"? BUILD ERROR: {e}")
    
    print("\n" + "="*50)
    
    # Test avec protocole inexistant
    try:
        print("\nTesting with non-existent protocol...")
        builder.clear().add_layer("nonexistent")
    except PacketBuilderError as e:
        print(f"? CORRECTLY REJECTED: {e}")
    
    print("\n=== REAL PACKETS ONLY - NO COMPROMISES ===")