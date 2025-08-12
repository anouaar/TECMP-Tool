#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VLAN Packet Factory for creating and managing VLAN (802.1Q) packets.
Provides convenient methods for creating various VLAN configurations.
"""

import random
from typing import Optional, Dict, Any, List, Union, Tuple

# Import VLAN packet from the network module
from core.packets.network.vlan import VLANPacket
from core.packets.base.packet import Packet
from core.exceptions.exceptions import PacketError


class VLANFactory:
    """
    Factory class for creating VLAN packets with various configurations.
    Provides static methods for common VLAN scenarios and conversions.
    """
    
    # Common VLAN ranges
    DEFAULT_VLAN = 1
    VOICE_VLAN_RANGE = (100, 199)
    DATA_VLAN_RANGE = (200, 299)
    MANAGEMENT_VLAN_RANGE = (10, 19)
    GUEST_VLAN_RANGE = (300, 399)
    
    # Priority mappings
    PRIORITY_MAPPINGS = {
        'voice': 5,
        'video': 4,
        'critical': 3,
        'excellent': 2,
        'background': 1,
        'best_effort': 0,
        'network_control': 7,
        'internetwork_control': 6
    }
    
    @staticmethod
    def create_vlan_packet(**kwargs) -> VLANPacket:
        """
        Create a generic VLAN packet with provided parameters.
        
        Args:
            **kwargs: All parameters accepted by VLANPacket constructor
            
        Returns:
            VLANPacket: Configured VLAN packet instance
        """
        return VLANPacket(**kwargs)
    
    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> VLANPacket:
        """
        Create VLAN packet from configuration dictionary (e.g., from UI dialog).
        
        Args:
            config: Configuration dictionary with VLAN parameters
            
        Returns:
            VLANPacket: Configured VLAN packet instance
        """
        # Extract and convert parameters
        packet_params = {}
        
        # VLAN ID (mandatory)
        packet_params['vlan_id'] = int(config.get('vlan_id', 1))
        
        # Priority and CFI
        packet_params['priority'] = int(config.get('priority', 0))
        packet_params['cfi'] = int(config.get('cfi', 0))
        
        # Ether type
        ether_type = config.get('ether_type', 0x0800)
        if isinstance(ether_type, str):
            # Handle hex string format
            if ether_type.startswith('0x'):
                packet_params['ether_type'] = int(ether_type, 16)
            else:
                packet_params['ether_type'] = int(ether_type)
        else:
            packet_params['ether_type'] = int(ether_type)
        
        # TPID
        if 'tpid' in config:
            tpid = config['tpid']
            if isinstance(tpid, str) and tpid.startswith('0x'):
                packet_params['tpid'] = int(tpid, 16)
            else:
                packet_params['tpid'] = int(tpid) if tpid else VLANPacket.TPID_8021Q
        
        # Payload
        if 'payload' in config:
            payload = config['payload']
            if isinstance(payload, str):
                packet_params['payload'] = payload.encode('utf-8')
            else:
                packet_params['payload'] = payload or b''
        
        # Metadata
        if 'interface' in config:
            packet_params['interface'] = config['interface']
        if 'trunk_port' in config:
            packet_params['trunk_port'] = bool(config['trunk_port'])
        if 'native_vlan' in config:
            packet_params['native_vlan'] = bool(config['native_vlan'])
        
        # Q-in-Q support
        if 'outer_vlan_id' in config and config['outer_vlan_id']:
            packet_params['outer_vlan_id'] = int(config['outer_vlan_id'])
            packet_params['outer_priority'] = int(config.get('outer_priority', 0))
            packet_params['outer_cfi'] = int(config.get('outer_cfi', 0))
        
        # Validation
        packet_params['strict_validation'] = config.get('strict_validation', True)
        
        return VLANPacket(**packet_params)
    
    @staticmethod
    def create_data_vlan(
        vlan_id: Optional[int] = None,
        priority: int = 0,
        ether_type: int = 0x0800,
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create a VLAN packet for data traffic.
        
        Args:
            vlan_id: VLAN ID (random from data range if None)
            priority: Priority (default 0 - Best Effort)
            ether_type: Encapsulated protocol type
            payload: Packet payload
            
        Returns:
            VLANPacket: Data VLAN packet
        """
        if vlan_id is None:
            vlan_id = random.randint(*VLANFactory.DATA_VLAN_RANGE)
        
        return VLANPacket(
            vlan_id=vlan_id,
            priority=priority,
            ether_type=ether_type,
            payload=payload
        )
    
    @staticmethod
    def create_voice_vlan(
        vlan_id: Optional[int] = None,
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create a VLAN packet for voice traffic with appropriate priority.
        
        Args:
            vlan_id: VLAN ID (random from voice range if None)
            payload: Voice packet payload
            
        Returns:
            VLANPacket: Voice VLAN packet
        """
        if vlan_id is None:
            vlan_id = random.randint(*VLANFactory.VOICE_VLAN_RANGE)
        
        return VLANPacket(
            vlan_id=vlan_id,
            priority=VLANFactory.PRIORITY_MAPPINGS['voice'],
            ether_type=0x0800,  # Usually IPv4 for VoIP
            payload=payload
        )
    
    @staticmethod
    def create_video_vlan(
        vlan_id: int,
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create a VLAN packet for video traffic with appropriate priority.
        
        Args:
            vlan_id: VLAN ID
            payload: Video packet payload
            
        Returns:
            VLANPacket: Video VLAN packet
        """
        return VLANPacket(
            vlan_id=vlan_id,
            priority=VLANFactory.PRIORITY_MAPPINGS['video'],
            ether_type=0x0800,
            payload=payload
        )
    
    @staticmethod
    def create_management_vlan(
        vlan_id: Optional[int] = None,
        priority: int = 6,  # Internetwork Control
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create a VLAN packet for management traffic.
        
        Args:
            vlan_id: VLAN ID (random from management range if None)
            priority: Priority (default 6 - Internetwork Control)
            payload: Management packet payload
            
        Returns:
            VLANPacket: Management VLAN packet
        """
        if vlan_id is None:
            vlan_id = random.randint(*VLANFactory.MANAGEMENT_VLAN_RANGE)
        
        return VLANPacket(
            vlan_id=vlan_id,
            priority=priority,
            ether_type=0x0800,
            payload=payload
        )
    
    @staticmethod
    def create_guest_vlan(
        vlan_id: Optional[int] = None,
        priority: int = 0,
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create a VLAN packet for guest network traffic.
        
        Args:
            vlan_id: VLAN ID (random from guest range if None)
            priority: Priority (default 0 - Best Effort)
            payload: Packet payload
            
        Returns:
            VLANPacket: Guest VLAN packet
        """
        if vlan_id is None:
            vlan_id = random.randint(*VLANFactory.GUEST_VLAN_RANGE)
        
        return VLANPacket(
            vlan_id=vlan_id,
            priority=priority,
            ether_type=0x0800,
            payload=payload
        )
    
    @staticmethod
    def create_qinq_packet(
        outer_vlan_id: int,
        inner_vlan_id: int,
        outer_priority: int = 0,
        inner_priority: int = 0,
        ether_type: int = 0x0800,
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create a Q-in-Q (double-tagged) VLAN packet.
        
        Args:
            outer_vlan_id: Outer VLAN ID (Service Provider)
            inner_vlan_id: Inner VLAN ID (Customer)
            outer_priority: Outer tag priority
            inner_priority: Inner tag priority
            ether_type: Encapsulated protocol type
            payload: Packet payload
            
        Returns:
            VLANPacket: Q-in-Q packet
        """
        return VLANPacket(
            vlan_id=inner_vlan_id,
            priority=inner_priority,
            outer_vlan_id=outer_vlan_id,
            outer_priority=outer_priority,
            ether_type=ether_type,
            payload=payload
        )
    
    @staticmethod
    def create_trunk_packet(
        vlan_id: int,
        priority: int = 0,
        ether_type: int = 0x0800,
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create a VLAN packet for trunk port transmission.
        
        Args:
            vlan_id: VLAN ID
            priority: Priority
            ether_type: Encapsulated protocol type
            payload: Packet payload
            
        Returns:
            VLANPacket: Trunk VLAN packet
        """
        packet = VLANPacket(
            vlan_id=vlan_id,
            priority=priority,
            ether_type=ether_type,
            payload=payload,
            trunk_port=True
        )
        return packet
    
    @staticmethod
    def create_native_vlan(
        vlan_id: int = 1,
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create a native VLAN packet (typically untagged on trunk).
        
        Args:
            vlan_id: Native VLAN ID (default 1)
            payload: Packet payload
            
        Returns:
            VLANPacket: Native VLAN packet
        """
        return VLANPacket(
            vlan_id=vlan_id,
            priority=0,
            ether_type=0x0800,
            payload=payload,
            native_vlan=True
        )
    
    @staticmethod
    def create_priority_tagged(
        priority: int,
        ether_type: int = 0x0800,
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create a priority-tagged packet (VLAN ID 0).
        
        Args:
            priority: Priority value (0-7)
            ether_type: Encapsulated protocol type
            payload: Packet payload
            
        Returns:
            VLANPacket: Priority-tagged packet
        """
        # VLAN ID 0 is used for priority tagging only
        return VLANPacket(
            vlan_id=0,
            priority=priority,
            ether_type=ether_type,
            payload=payload,
            strict_validation=False  # Allow VLAN ID 0
        )
    
    @staticmethod
    def create_by_service(
        service_type: str,
        vlan_id: Optional[int] = None,
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create VLAN packet based on service type.
        
        Args:
            service_type: Type of service ('voice', 'video', 'data', etc.)
            vlan_id: VLAN ID (auto-selected if None)
            payload: Packet payload
            
        Returns:
            VLANPacket: Service-specific VLAN packet
        """
        service_type = service_type.lower()
        
        if service_type == 'voice':
            return VLANFactory.create_voice_vlan(vlan_id, payload)
        elif service_type == 'video':
            if vlan_id is None:
                vlan_id = random.randint(200, 299)  # Default video range
            return VLANFactory.create_video_vlan(vlan_id, payload)
        elif service_type == 'management':
            return VLANFactory.create_management_vlan(vlan_id, payload=payload)
        elif service_type == 'guest':
            return VLANFactory.create_guest_vlan(vlan_id, payload=payload)
        else:  # Default to data
            return VLANFactory.create_data_vlan(vlan_id, payload=payload)
    
    @staticmethod
    def get_priority_by_name(priority_name: str) -> int:
        """
        Get priority value by name.
        
        Args:
            priority_name: Priority name (e.g., 'voice', 'video')
            
        Returns:
            int: Priority value (0-7)
        """
        return VLANFactory.PRIORITY_MAPPINGS.get(priority_name.lower(), 0)
    
    @staticmethod
    def validate_vlan_id(vlan_id: int) -> bool:
        """
        Validate VLAN ID.
        
        Args:
            vlan_id: VLAN ID to validate
            
        Returns:
            bool: True if valid
        """
        return VLANPacket.MIN_VLAN_ID <= vlan_id <= VLANPacket.MAX_VLAN_ID
    
    @staticmethod
    def validate_priority(priority: int) -> bool:
        """
        Validate priority value.
        
        Args:
            priority: Priority to validate
            
        Returns:
            bool: True if valid
        """
        return 0 <= priority <= 7
    
    @classmethod
    def create_vlan_stack(
        cls,
        vlan_ids: List[int],
        priorities: Optional[List[int]] = None,
        ether_type: int = 0x0800,
        payload: bytes = b''
    ) -> VLANPacket:
        """
        Create a VLAN stack (multiple tags).
        
        Note: Current implementation supports up to 2 tags (Q-in-Q).
        
        Args:
            vlan_ids: List of VLAN IDs (outer to inner)
            priorities: List of priorities (matching vlan_ids)
            ether_type: Final encapsulated protocol
            payload: Packet payload
            
        Returns:
            VLANPacket: Multi-tagged packet
        """
        if not vlan_ids:
            raise ValueError("At least one VLAN ID required")
        
        if len(vlan_ids) > 2:
            raise ValueError("Maximum 2 VLAN tags supported (Q-in-Q)")
        
        if priorities is None:
            priorities = [0] * len(vlan_ids)
        elif len(priorities) != len(vlan_ids):
            raise ValueError("Number of priorities must match number of VLAN IDs")
        
        if len(vlan_ids) == 1:
            # Single tag
            return VLANPacket(
                vlan_id=vlan_ids[0],
                priority=priorities[0],
                ether_type=ether_type,
                payload=payload
            )
        else:
            # Double tag (Q-in-Q)
            return VLANPacket(
                vlan_id=vlan_ids[1],  # Inner
                priority=priorities[1],
                outer_vlan_id=vlan_ids[0],  # Outer
                outer_priority=priorities[0],
                ether_type=ether_type,
                payload=payload
            )
    
    @classmethod
    def suggest_vlan_id(cls, service_type: str) -> int:
        """
        Suggest a VLAN ID based on service type.
        
        Args:
            service_type: Type of service
            
        Returns:
            int: Suggested VLAN ID
        """
        ranges = {
            'voice': cls.VOICE_VLAN_RANGE,
            'data': cls.DATA_VLAN_RANGE,
            'management': cls.MANAGEMENT_VLAN_RANGE,
            'guest': cls.GUEST_VLAN_RANGE
        }
        
        range_tuple = ranges.get(service_type.lower(), cls.DATA_VLAN_RANGE)
        return random.randint(*range_tuple)


# Module exports
__all__ = ['VLANFactory']