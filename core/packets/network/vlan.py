#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VLAN (802.1Q) Packet implementation for TECMP-Tool.
Provides complete VLAN tagging support.
"""

import struct
from typing import Optional, Dict, Any, Union

from core.packets.base.packet import Packet
from core.exceptions.exceptions import (
    PacketParsingError,
    PacketSerializationError,
    PacketValidationError,
)

class VLANPacket(Packet):
    """
    IEEE 802.1Q VLAN Tag implementation.
    
    VLAN Tag Format (4 bytes):
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |        TPID (0x8100)          |PCP|C|        VLAN ID          |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    
    Where:
    - TPID: Tag Protocol Identifier (0x8100 for 802.1Q)
    - PCP: Priority Code Point (3 bits)
    - CFI: Canonical Format Indicator (1 bit)
    - VLAN ID: VLAN Identifier (12 bits)
    """
    
    # Constants
    VLAN_TAG_SIZE = 4  # Size of VLAN tag in bytes
    TPID_8021Q = 0x8100  # Standard 802.1Q TPID
    TPID_8021AD = 0x88A8  # 802.1ad (Q-in-Q) TPID
    
    # Valid VLAN ID range
    MIN_VLAN_ID = 1
    MAX_VLAN_ID = 4094  # 4095 is reserved
    
    # Priority levels
    PRIORITY_BACKGROUND = 1
    PRIORITY_BEST_EFFORT = 0
    PRIORITY_EXCELLENT_EFFORT = 2
    PRIORITY_CRITICAL_APPLICATIONS = 3
    PRIORITY_VIDEO = 4
    PRIORITY_VOICE = 5
    PRIORITY_INTERNETWORK_CONTROL = 6
    PRIORITY_NETWORK_CONTROL = 7
    
    def __init__(
        self,
        # === MANDATORY FIELDS ===
        vlan_id: int,
        
        # === OPTIONAL FIELDS ===
        priority: int = 0,              # Priority Code Point (0-7)
        cfi: int = 0,                  # Canonical Format Indicator (0 or 1)
        ether_type: int = 0x0800,      # Encapsulated protocol (IPv4 default)
        tpid: int = TPID_8021Q,        # Tag Protocol ID
        
        # === PAYLOAD ===
        payload: bytes = b'',          # Encapsulated data
        
        # === METADATA ===
        interface: Optional[str] = None,
        trunk_port: bool = False,      # Is this from a trunk port
        native_vlan: bool = False,     # Is this the native VLAN
        
        # === Q-IN-Q SUPPORT ===
        outer_vlan_id: Optional[int] = None,    # For double tagging
        outer_priority: Optional[int] = None,
        outer_cfi: Optional[int] = None,
        
        # === VALIDATION ===
        strict_validation: bool = True
    ):
        """
        Initialize VLAN packet.
        
        Args:
            vlan_id: VLAN identifier (1-4094)
            priority: Priority Code Point (0-7)
            cfi: Canonical Format Indicator (0 or 1)
            ether_type: Type of encapsulated protocol
            tpid: Tag Protocol Identifier
            payload: Encapsulated packet data
            interface: Network interface
            trunk_port: Whether this is from a trunk port
            native_vlan: Whether this is the native VLAN
            outer_vlan_id: Outer VLAN ID for Q-in-Q
            outer_priority: Outer tag priority
            outer_cfi: Outer tag CFI
            strict_validation: Enable strict validation
        """
        super().__init__()
        
        # VLAN fields
        self.vlan_id = vlan_id
        self.priority = priority
        self.cfi = cfi
        self.ether_type = ether_type
        self.tpid = tpid
        self.payload = payload
        
        # Metadata
        self.interface = interface
        self.trunk_port = trunk_port
        self.native_vlan = native_vlan
        
        # Q-in-Q support
        self.outer_vlan_id = outer_vlan_id
        self.outer_priority = outer_priority if outer_priority is not None else 0
        self.outer_cfi = outer_cfi if outer_cfi is not None else 0
        
        # Validation
        self.strict_validation = strict_validation
        
        # Calculate TCI (Tag Control Information)
        self._update_tci()
    
    def _update_tci(self):
        """Update Tag Control Information field"""
        # TCI = Priority (3 bits) | CFI (1 bit) | VLAN ID (12 bits)
        self.tci = (self.priority << 13) | (self.cfi << 12) | self.vlan_id
    
    def serialize(self) -> bytes:
        """
        Serialize VLAN packet to bytes.
        
        Returns:
            bytes: Serialized packet data
            
        Raises:
            PacketSerializationError: If serialization fails
        """
        try:
            # Validate before serialization
            if self.strict_validation:
                self.validate()
            
            # Update TCI
            self._update_tci()
            
            # Build VLAN tag
            vlan_data = b''
            
            # Add outer tag if Q-in-Q
            if self.outer_vlan_id is not None:
                outer_tci = (self.outer_priority << 13) | (self.outer_cfi << 12) | self.outer_vlan_id
                vlan_data += struct.pack('!HH', self.TPID_8021AD, outer_tci)
            
            # Add VLAN tag
            vlan_data += struct.pack('!HH', self.tpid, self.tci)
            
            # Add the encapsulated protocol type/length if not part of payload
            if self.ether_type is not None:
                vlan_data += struct.pack('!H', self.ether_type)
            
            # Add payload
            vlan_data += self.payload
            
            # Store raw data
            self._raw_data = bytearray(vlan_data)
            self._update_size()
            
            return bytes(self._raw_data)
            
        except struct.error as e:
            raise PacketSerializationError(f"VLAN serialization error: {e}")
        except Exception as e:
            raise PacketSerializationError(f"Unexpected error during VLAN serialization: {e}")
    
    def deserialize(self, data: bytes):
        """
        Deserialize bytes to VLAN packet.
        
        Args:
            data: Raw bytes to deserialize
            
        Raises:
            PacketParsingError: If parsing fails
        """
        if len(data) < self.VLAN_TAG_SIZE:
            raise PacketParsingError(
                f"VLAN packet too short: {len(data)} bytes (minimum {self.VLAN_TAG_SIZE})"
            )
        
        try:
            offset = 0
            
            # Check for outer tag (Q-in-Q)
            tpid_check = struct.unpack('!H', data[offset:offset+2])[0]
            if tpid_check == self.TPID_8021AD:
                # Parse outer tag
                self.outer_vlan_id = struct.unpack('!H', data[offset+2:offset+4])[0]
                self.outer_priority = (self.outer_vlan_id >> 13) & 0x7
                self.outer_cfi = (self.outer_vlan_id >> 12) & 0x1
                self.outer_vlan_id &= 0xFFF
                offset += 4
            
            # Parse VLAN tag
            self.tpid, self.tci = struct.unpack('!HH', data[offset:offset+4])
            offset += 4
            
            # Extract fields from TCI
            self.priority = (self.tci >> 13) & 0x7
            self.cfi = (self.tci >> 12) & 0x1
            self.vlan_id = self.tci & 0xFFF
            
            # Parse ether_type if present
            if len(data) > offset + 2:
                self.ether_type = struct.unpack('!H', data[offset:offset+2])[0]
                offset += 2
            
            # Rest is payload
            self.payload = data[offset:]
            
            # Store raw data
            self._raw_data = bytearray(data)
            self._update_size()
            
            # Mark as validated
            self.mark_validated(True)
            
        except struct.error as e:
            raise PacketParsingError(f"VLAN deserialization error: {e}")
        except Exception as e:
            raise PacketParsingError(f"Unexpected error during VLAN parsing: {e}")
    
    def validate(self) -> bool:
        """
        Validate VLAN packet fields.
        
        Returns:
            bool: True if valid
            
        Raises:
            PacketValidationError: If validation fails
        """
        # Validate VLAN ID
        if not (self.MIN_VLAN_ID <= self.vlan_id <= self.MAX_VLAN_ID):
            raise PacketValidationError(
                f"Invalid VLAN ID: {self.vlan_id} "
                f"(must be {self.MIN_VLAN_ID}-{self.MAX_VLAN_ID})"
            )
        
        # Validate priority
        if not (0 <= self.priority <= 7):
            raise PacketValidationError(f"Invalid priority: {self.priority} (must be 0-7)")
        
        # Validate CFI
        if self.cfi not in (0, 1):
            raise PacketValidationError(f"Invalid CFI: {self.cfi} (must be 0 or 1)")
        
        # Validate TPID
        valid_tpids = [self.TPID_8021Q, self.TPID_8021AD, 0x9100, 0x9200]  # Include some vendor TPIDs
        if self.tpid not in valid_tpids:
            self._logger.warning(f"Non-standard TPID: 0x{self.tpid:04X}")
        
        # Validate ether_type
        if self.ether_type is not None:
            if not (0 <= self.ether_type <= 0xFFFF):
                raise PacketValidationError(f"Invalid ether_type: {self.ether_type}")
        
        # Validate Q-in-Q if present
        if self.outer_vlan_id is not None:
            if not (self.MIN_VLAN_ID <= self.outer_vlan_id <= self.MAX_VLAN_ID):
                raise PacketValidationError(f"Invalid outer VLAN ID: {self.outer_vlan_id}")
            if not (0 <= self.outer_priority <= 7):
                raise PacketValidationError(f"Invalid outer priority: {self.outer_priority}")
            if self.outer_cfi not in (0, 1):
                raise PacketValidationError(f"Invalid outer CFI: {self.outer_cfi}")
        
        self.mark_validated(True)
        return True
    
    def summary(self) -> str:
        """
        Return human-readable summary of VLAN packet.
        
        Returns:
            str: Packet summary
        """
        priority_names = {
            0: "BE", 1: "BK", 2: "EE", 3: "CA",
            4: "VI", 5: "VO", 6: "IC", 7: "NC"
        }
        
        proto_names = {
            0x0800: "IPv4", 0x86DD: "IPv6", 0x0806: "ARP",
            0x8100: "VLAN", 0x88A8: "Q-in-Q", 0x8847: "MPLS"
        }
        
        priority_str = priority_names.get(self.priority, str(self.priority))
        proto_str = proto_names.get(self.ether_type, f"0x{self.ether_type:04X}")
        
        summary = f"VLAN {self.vlan_id} pri={priority_str}"
        
        if self.outer_vlan_id is not None:
            outer_pri_str = priority_names.get(self.outer_priority, str(self.outer_priority))
            summary = f"Q-in-Q outer={self.outer_vlan_id}/{outer_pri_str} inner={self.vlan_id}/{priority_str}"
        
        summary += f" proto={proto_str}"
        
        if self.payload:
            summary += f" [{len(self.payload)} bytes]"
        
        return summary
    
    def get_priority_name(self) -> str:
        """
        Get human-readable priority name.
        
        Returns:
            str: Priority name
        """
        priority_names = {
            0: "Best Effort",
            1: "Background",
            2: "Excellent Effort",
            3: "Critical Applications",
            4: "Video",
            5: "Voice",
            6: "Internetwork Control",
            7: "Network Control"
        }
        return priority_names.get(self.priority, f"Unknown ({self.priority})")
    
    def is_double_tagged(self) -> bool:
        """
        Check if this is a double-tagged (Q-in-Q) packet.
        
        Returns:
            bool: True if double-tagged
        """
        return self.outer_vlan_id is not None
    
    def get_protocol_name(self) -> str:
        """
        Get the name of the encapsulated protocol.
        
        Returns:
            str: Protocol name
        """
        protocols = {
            0x0800: "IPv4",
            0x0806: "ARP",
            0x86DD: "IPv6",
            0x8847: "MPLS Unicast",
            0x8848: "MPLS Multicast",
            0x8863: "PPPoE Discovery",
            0x8864: "PPPoE Session",
            0x888E: "802.1X",
            0x88CC: "LLDP",
            0x88F7: "PTP"
        }
        return protocols.get(self.ether_type, f"Unknown (0x{self.ether_type:04X})")
    
    def strip_vlan_tag(self) -> bytes:
        """
        Get the payload without VLAN tags.
        
        Returns:
            bytes: Payload data
        """
        return self.payload
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert packet to dictionary representation.
        
        Returns:
            dict: Packet fields as dictionary
        """
        base_dict = super().to_dict()
        base_dict.update({
            "vlan_id": self.vlan_id,
            "priority": self.priority,
            "priority_name": self.get_priority_name(),
            "cfi": self.cfi,
            "ether_type": f"0x{self.ether_type:04X}",
            "protocol": self.get_protocol_name(),
            "tpid": f"0x{self.tpid:04X}",
            "double_tagged": self.is_double_tagged()
        })
        
        if self.is_double_tagged():
            base_dict.update({
                "outer_vlan_id": self.outer_vlan_id,
                "outer_priority": self.outer_priority,
                "outer_cfi": self.outer_cfi
            })
        
        return base_dict
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"VLANPacket(vlan_id={self.vlan_id}, priority={self.priority}, "
            f"cfi={self.cfi}, ether_type=0x{self.ether_type:04X})"
        )


# Module exports
__all__ = ['VLANPacket']