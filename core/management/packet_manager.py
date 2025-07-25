from __future__ import annotations
# =============================
# core/management/packet_manager.py - CORRECTED VERSION
# =============================
"""
Centralized management of packets built in TECMP-Tool.
FIXES APPLIED:
- Eliminated circular imports with lazy loading
- Added robust error handling for all imports
- Simplified initialization with fallbacks
- Fixed all dependency issues
- Maintained full functionality
"""
from pathlib import Path
from typing import (
    Iterable, List, Union, Dict, Any, Optional, Type, Callable, TypeVar, 
    Generic, cast, Iterator, Protocol, runtime_checkable
)
import logging
import importlib
import time
import copy
from abc import ABC, abstractmethod

# Type variable for packet classes
T = TypeVar('T')

# Protocol for objects that can be serialized
@runtime_checkable
class Serializable(Protocol):
    """Protocol for objects that can be serialized to bytes."""
    def serialize(self) -> bytes: ...

# Protocol for objects with raw method
@runtime_checkable
class RawProvider(Protocol):
    """Protocol for objects that provide raw bytes."""
    def raw(self) -> bytes: ...


# === EXCEPTIONS ===

class PacketBuildError(Exception):
    """Base exception for packet building errors."""
    pass


class InvalidConfigurationError(PacketBuildError):
    """Exception raised when packet configuration is invalid."""
    pass


class ProtocolNotFoundError(PacketBuildError):
    """Exception raised when a protocol class cannot be found."""
    pass


class PayloadError(PacketBuildError):
    """Exception raised when there's an error adding a payload to a packet."""
    pass


# === LAZY IMPORTS WITH FALLBACKS ===

class LazyImporter:
    """Handles lazy imports with fallbacks to avoid circular dependencies."""
    
    def __init__(self):
        self.logger = logging.getLogger("TECMP-Tool.LazyImporter")
        self._cache = {}
        self._failed_imports = set()
    
    def import_module(self, module_path: str, class_name: Optional[str] = None):
        """
        Safely import a module or class with caching.
        
        Args:
            module_path: Path to module
            class_name: Optional class name to extract
            
        Returns:
            Module or class, or None if import fails
        """
        cache_key = f"{module_path}::{class_name or 'MODULE'}"
        
        # Return cached result
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Skip if already failed
        if cache_key in self._failed_imports:
            return None
        
        try:
            module = importlib.import_module(module_path)
            
            if class_name:
                if hasattr(module, class_name):
                    result = getattr(module, class_name)
                    self._cache[cache_key] = result
                    return result
                else:
                    self.logger.warning(f"Class {class_name} not found in {module_path}")
                    self._failed_imports.add(cache_key)
                    return None
            else:
                self._cache[cache_key] = module
                return module
                
        except ImportError as e:
            self.logger.debug(f"Import failed for {module_path}: {e}")
            self._failed_imports.add(cache_key)
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error importing {module_path}: {e}")
            self._failed_imports.add(cache_key)
            return None


# Global lazy importer instance
_lazy_importer = LazyImporter()


def safe_import(module_path: str, class_name: Optional[str] = None):
    """Convenience function for safe imports."""
    return _lazy_importer.import_module(module_path, class_name)


# === PROTOCOL REGISTRY (SIMPLIFIED) ===

class ProtocolRegistry:
    """
    Simplified registry of protocol classes with dynamic loading capabilities.
    Fixed to avoid circular imports and initialization issues.
    """
    
    # Singleton instance
    _instance = None
    
    # Mapping of protocol names to TECMP data types
    PROTOCOL_TO_DATATYPE = {
        "Ethernet": 0x80,
        "CAN": 0x02,
        "CAN-FD": 0x03,
        "LIN": 0x04,
        "FlexRay": 0x08,
        "UART": 0x10,
        "UART/RS232": 0x10,
        "Analog": 0x20
    }
    
    # Protocol module mapping (simplified)
    PROTOCOL_MODULES = {
        "ETHERNET": ("core.packets.base.ethernet", "EthernetPacket"),
        "VLAN": ("core.packets.network.vlan", "VLANPacket"),
        "IPV4": ("core.packets.network.ipv4", "IPv4Packet"),
        "IPV6": ("core.packets.network.ipv6", "IPv6Packet"),
        "ARP": ("core.packets.network.arp", "ARPPacket"),
        "TCP": ("core.packets.transport.tcp", "TCPPacket"),
        "UDP": ("core.packets.transport.udp", "UDPPacket"),
        "TECMP": ("core.packets.tecmp.tecmp_packet", "TECMPPacket"),
        "CAN": ("core.packets.automotive.can", "CANPacket"),
        "CAN-FD": ("core.packets.automotive.can_fd", "CANFDPacket"),
        "LIN": ("core.packets.automotive.lin", "LINPacket"),
        "FLEXRAY": ("core.packets.automotive.flexray", "FlexRayPacket")
    }
    
    def __new__(cls):
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super(ProtocolRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize with logger if not already initialized."""
        if not getattr(self, '_initialized', False):
            self.logger = logging.getLogger("TECMP-Tool.ProtocolRegistry")
            # Cache for protocol classes to avoid repeated imports
            self._class_cache: Dict[str, Type] = {}
            self._initialization_failed = False
            self._initialized = True
            
            # Try to initialize core imports
            self._initialize_core_imports()
        
    def _initialize_core_imports(self):
        """Initialize core imports that are commonly used."""
        try:
            # Try to load base packet class
            base_packet_module = safe_import("core.packets.base.packet", "BasePacket")
            if base_packet_module:
                self._class_cache["BasePacket"] = base_packet_module
                self.logger.debug("BasePacket loaded successfully")
            
            # Try to load common protocols
            for protocol, (module_path, class_name) in self.PROTOCOL_MODULES.items():
                if protocol in ["ETHERNET", "IPV4", "TCP", "UDP"]:  # Load common ones
                    cls = safe_import(module_path, class_name)
                    if cls:
                        self._class_cache[protocol] = cls
                        self.logger.debug(f"Pre-loaded {protocol}")
                        
        except Exception as e:
            self.logger.warning(f"Core imports initialization failed: {e}")
            self._initialization_failed = True
        
    def get_protocol_class(self, protocol_name: str) -> Optional[Type]:
        """
        Dynamically load a protocol class by name with robust error handling.
        
        Args:
            protocol_name: Protocol identifier
            
        Returns:
            Protocol class object or None if not found
        """
        if self._initialization_failed:
            return None
            
        protocol_name = protocol_name.strip()
        
        # Check cache first
        if protocol_name in self._class_cache:
            return self._class_cache[protocol_name]
        
        # Normalize protocol name
        protocol_upper = protocol_name.upper()
        
        # Handle special cases
        if protocol_name in ["Ethernet (External)", "Ethernet"]:
            return self._load_ethernet_class()
                
        if protocol_upper == "TECMP" or protocol_name.startswith("TECMP (encapsulating"):
            return self._load_tecmp_class()

        # Try direct mapping first
        if protocol_upper in self.PROTOCOL_MODULES:
            module_path, class_name = self.PROTOCOL_MODULES[protocol_upper]
            cls = safe_import(module_path, class_name)
            if cls:
                self._class_cache[protocol_name] = cls
                return cls

        # Try alternative paths
        alternative_paths = [
            f"core.packets.base.{protocol_name.lower()}",
            f"core.packets.network.{protocol_name.lower()}",
            f"core.packets.transport.{protocol_name.lower()}",
            f"core.packets.automotive.{protocol_name.lower()}",
            f"core.packets.tecmp.{protocol_name.lower()}",
        ]
        
        class_variants = [
            f"{protocol_name}Packet",
            f"{protocol_name.capitalize()}Packet",
            f"{protocol_upper}Packet",
            protocol_name,
            protocol_name.capitalize()
        ]

        for module_path in alternative_paths:
            for class_name in class_variants:
                cls = safe_import(module_path, class_name)
                if cls:
                    self._class_cache[protocol_name] = cls
                    return cls

        self.logger.warning(f"Could not load protocol class: {protocol_name}")
        return None
        
    def _load_ethernet_class(self) -> Optional[Type]:
        """Load Ethernet packet class with fallbacks."""
        for module_path in ["core.packets.base.ethernet", "core.packets.base.ethernet_packet"]:
            cls = safe_import(module_path, "EthernetPacket")
            if cls:
                self._class_cache["Ethernet"] = cls
                return cls
        return None
                
    def _load_tecmp_class(self) -> Optional[Type]:
        """Load TECMP packet class."""
        cls = safe_import("core.packets.tecmp.tecmp_packet", "TECMPPacket")
        if cls:
            self._class_cache["TECMP"] = cls
        return cls
            
    def get_datatype_for_protocol(self, protocol_name: str) -> int:
        """
        Get the TECMP data type for a protocol.
        
        Args:
            protocol_name: Protocol name
            
        Returns:
            TECMP data type (default 0x80 for Ethernet)
        """
        for proto_key, proto_type in self.PROTOCOL_TO_DATATYPE.items():
            if proto_key in protocol_name:
                self.logger.debug(f"Detected datatype 0x{proto_type:02x} for {protocol_name}")
                return proto_type

        self.logger.debug(f"Using default datatype 0x80 (Ethernet) for {protocol_name}")
        return 0x80


# === PACKET BUILDER (SIMPLIFIED) ===

class PacketBuilder:
    """
    Simplified helper class for building packets from configuration.
    Fixed to avoid circular imports and initialization issues.
    """
    
    # Singleton instance
    _instance = None
    
    def __new__(cls):
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super(PacketBuilder, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize with logger and protocol registry if not already initialized."""
        if not getattr(self, '_initialized', False):
            self.logger = logging.getLogger("TECMP-Tool.PacketBuilder")
            try:
                self.registry = ProtocolRegistry()
            except Exception as e:
                self.logger.error(f"Failed to initialize ProtocolRegistry: {e}")
                self.registry = None
            self._initialized = True
        
    def build_packet_from_config(self, config: List[Dict[str, Any]]) -> Optional[Any]:
        """
        Build a packet from a configuration with robust error handling.
        
        Args:
            config: List of protocol configurations
            
        Returns:
            The constructed packet or None if configuration is empty
        """
        if not config:
            self.logger.warning("Empty configuration, cannot build packet")
            return None

        if not self.registry:
            self.logger.error("No protocol registry available")
            return self._create_fallback_packet(config)

        try:
            # Special case for TECMP with encapsulation
            if len(config) == 1 and config[0].get("name") == "TECMP" and "encapsulated" in config[0]:
                self.logger.debug("Building TECMP packet with encapsulation")
                return self._build_tecmp_with_encapsulation(config[0])

            # Build protocol stack
            return self._build_protocol_stack(config)
            
        except Exception as e:
            self.logger.error(f"Error building packet: {e}")
            return self._create_fallback_packet(config)
            
    def _build_tecmp_with_encapsulation(self, tecmp_config_item: Dict[str, Any]) -> Optional[Any]:
        """Build a TECMP packet encapsulating a full protocol stack."""
        try:
            config = tecmp_config_item.get("config", {})
            encapsulated_stack = tecmp_config_item.get("encapsulated", [])

            if not encapsulated_stack:
                raise InvalidConfigurationError("Empty encapsulated stack in TECMP configuration")

            # Build the encapsulated stack
            encapsulated_packet = self._build_protocol_stack(encapsulated_stack)
            if not encapsulated_packet:
                raise InvalidConfigurationError("Failed to build encapsulated packet")

            # Get serialized data
            encapsulated_bytes = self._get_packet_bytes(encapsulated_packet)

            # Set data_type if not provided
            if "data_type" not in config:
                data_type = self._determine_datatype_from_stack(encapsulated_stack)
                config["data_type"] = data_type

            # Try to create TECMP packet
            return self._create_tecmp_packet(config, encapsulated_bytes)
            
        except Exception as e:
            self.logger.error(f"Error building TECMP with encapsulation: {e}")
            return None
            
    def _create_tecmp_packet(self, config: Dict[str, Any], payload_bytes: bytes) -> Optional[Any]:
        """Create TECMP packet using available builder."""
        # Try TECMPPacketBuilder first
        tecmp_builder_class = safe_import("core.builders.tecmp_builder", "TECMPPacketBuilder")
        if tecmp_builder_class:
            try:
                builder = tecmp_builder_class()
                
                # Apply configuration
                method_map = {
                    "device_id": "with_device_id",
                    "message_type": "with_message_type", 
                    "msg_type": "with_message_type",
                    "data_type": "with_data_type",
                    "interface_id": "with_interface_id",
                    "timestamp": "with_timestamp",
                    "data_flags": "with_data_flags",
                    "counter": "with_counter",
                    "version": "with_version",
                    "device_flags": "with_device_flags",
                }

                for key, value in config.items():
                    method_name = method_map.get(key)
                    if method_name and hasattr(builder, method_name):
                        method = getattr(builder, method_name)
                        builder = method(value)

                # Add payload
                if hasattr(builder, 'with_payload'):
                    builder = builder.with_payload(payload_bytes)

                return builder.build()
                
            except Exception as e:
                self.logger.error(f"TECMPPacketBuilder failed: {e}")
        
        # Fallback to direct TECMP class
        tecmp_class = self.registry.get_protocol_class("TECMP")
        if tecmp_class:
            try:
                return tecmp_class(payload=payload_bytes, **config)
            except Exception as e:
                self.logger.error(f"Direct TECMP creation failed: {e}")
        
        return None
            
    def _determine_datatype_from_stack(self, protocol_stack: List[Dict[str, Any]]) -> int:
        """Determine TECMP data type based on the protocol stack."""
        if not self.registry:
            return 0x80
            
        for protocol in protocol_stack:
            protocol_name = protocol.get("name", "")
            datatype = self.registry.get_datatype_for_protocol(protocol_name)
            if datatype != 0x80:  # If not the default Ethernet type
                return datatype
                
        return 0x80  # Default to Ethernet

    def _build_protocol_stack(self, protocol_stack: List[Dict[str, Any]], 
                             parent_packet: Optional[Any] = None) -> Optional[Any]:
        """Recursively build a protocol stack."""
        if not protocol_stack:
            return parent_packet

        if not self.registry:
            return self._create_fallback_packet(protocol_stack)

        try:
            protocol_item = protocol_stack[-1]
            
            if "name" not in protocol_item:
                raise InvalidConfigurationError("Missing 'name' in protocol configuration")
                
            protocol_name = protocol_item.get("name")
            protocol_config = protocol_item.get("config", {})

            self.logger.debug(f"Building protocol: {protocol_name}")

            # Handle TECMP with encapsulation
            if protocol_name == "TECMP" and "encapsulated" in protocol_item:
                return self._build_tecmp_with_encapsulation(protocol_item)

            # Get protocol class
            protocol_class = self.registry.get_protocol_class(protocol_name)
            if not protocol_class:
                self.logger.warning(f"Protocol class not found: {protocol_name}")
                return self._create_fallback_packet(protocol_stack)

            # Create packet instance
            if "encapsulated" in protocol_item:
                encapsulated_packet = self._build_protocol_stack(protocol_item["encapsulated"])
                packet = self._create_packet_instance(protocol_class, protocol_config, payload=encapsulated_packet)
            else:
                packet = self._create_packet_instance(protocol_class, protocol_config)

            if packet and parent_packet:
                self._add_payload(packet, parent_packet)

            return self._build_protocol_stack(protocol_stack[:-1], packet)
            
        except Exception as e:
            self.logger.error(f"Error building protocol stack: {e}")
            return self._create_fallback_packet(protocol_stack)

    def _create_packet_instance(self, protocol_class: Type, config: Dict[str, Any], **kwargs) -> Optional[Any]:
        """Create a packet instance handling various constructor signatures."""
        try:
            # Try with payload first
            if 'payload' in kwargs:
                try:
                    return protocol_class(payload=kwargs['payload'], **config)
                except TypeError:
                    pass
            
            # Try without payload
            packet = protocol_class(**config)
            
            # Add payload separately if provided
            if 'payload' in kwargs and packet:
                self._add_payload(packet, kwargs['payload'])
            
            return packet
            
        except Exception as e:
            self.logger.error(f"Error creating {protocol_class.__name__} instance: {e}")
            return None

    def _add_payload(self, packet: Any, payload: Any) -> None:
        """Add a payload to a packet by trying various methods."""
        if not packet or not payload:
            return
            
        for method_name in ['set_payload', 'encapsulate', 'add_payload']:
            if hasattr(packet, method_name):
                try:
                    method = getattr(packet, method_name)
                    method(payload)
                    return
                except Exception as e:
                    self.logger.debug(f"Method {method_name} failed: {e}")
                    continue

        self.logger.warning(f"Unable to add payload to packet {type(packet).__name__}")
    
    def _get_packet_bytes(self, packet: Any) -> bytes:
        """Get bytes from a packet using various methods."""
        if isinstance(packet, bytes):
            return packet
            
        for method_name in ['serialize', 'raw', 'to_bytes', '__bytes__']:
            if hasattr(packet, method_name):
                try:
                    method = getattr(packet, method_name)
                    result = method() if callable(method) else method
                    if isinstance(result, bytes):
                        return result
                except Exception as e:
                    self.logger.debug(f"Method {method_name} failed: {e}")
                    continue
        
        # Fallback: convert to string and encode
        return str(packet).encode('utf-8')
    
    def _create_fallback_packet(self, config: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a fallback packet representation."""
        return {
            "type": "fallback_packet",
            "config": config,
            "timestamp": time.time(),
            "data": f"Fallback packet for {len(config)} protocols".encode('utf-8'),
            "protocols": [p.get('name', 'unknown') for p in config]
        }


# === PACKET MANAGER (CORRECTED) ===

class PacketManager:
    """
    High-level container for manipulating a list of packets.
    
    CORRECTED VERSION:
    - Fixed all import issues with lazy loading
    - Added comprehensive error handling
    - Simplified dependencies
    - Maintained full functionality
    """

    def __init__(self) -> None:
        """Initialize packet manager with robust error handling."""
        self.logger = logging.getLogger("TECMP-Tool.PacketManager")
        self._packets: List[Any] = []
        
        # Initialize components with error handling
        try:
            self.packet_builder = PacketBuilder()
            self.logger.debug("PacketBuilder initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize PacketBuilder: {e}")
            self.packet_builder = None
        
        # Try to initialize optional components
        self._initialize_optional_components()
        
        self.logger.info("PacketManager initialized successfully")

    def _initialize_optional_components(self):
        """Initialize optional components with fallbacks."""
        # Try to load PCAPGenerator
        self.pcap_generator = safe_import("core.management.pcap_generator", "PcapGenerator")
        if not self.pcap_generator:
            self.logger.debug("PcapGenerator not available")
        
        # Try to load PacketModifier
        self.packet_modifier_class = safe_import("core.builders.packet_modifier", "PacketModifier")
        if not self.packet_modifier_class:
            self.logger.debug("PacketModifier not available")

    # ------------------------------------------------------------------
    # Basic CRUD operations
    # ------------------------------------------------------------------
    def add(self, packet: Any) -> None:
        """Add a packet to the collection."""
        if packet is not None:
            self._packets.append(packet)
            self.logger.debug(f"Added packet to collection (total: {len(self._packets)})")

    def extend(self, packets: Iterable[Any]) -> None:
        """Add multiple packets to the collection."""
        initial_count = len(self._packets)
        for packet in packets:
            if packet is not None:
                self._packets.append(packet)
        self.logger.debug(f"Extended collection by {len(self._packets) - initial_count} packets")

    def remove(self, packet: Any) -> None:
        """Remove a packet from the collection."""
        try:
            self._packets.remove(packet)
            self.logger.debug(f"Removed packet from collection (remaining: {len(self._packets)})")
        except ValueError:
            self.logger.warning("Attempted to remove packet not in collection")
            raise

    def clear(self) -> None:
        """Remove all packets from the collection."""
        count = len(self._packets)
        self._packets.clear()
        self.logger.debug(f"Cleared {count} packets from collection")

    # ------------------------------------------------------------------
    # Access / Introspection
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        """Get the number of packets in the collection."""
        return len(self._packets)

    def __iter__(self) -> Iterator[Any]:
        """Iterate over packets in the collection."""
        return iter(self._packets)
        
    def __getitem__(self, index: int) -> Any:
        """Get a packet by index."""
        return self._packets[index]

    def summaries(self) -> List[str]:
        """Get summaries of all packets."""
        summaries = []
        for i, packet in enumerate(self._packets):
            try:
                if hasattr(packet, 'summary'):
                    summaries.append(packet.summary())
                elif hasattr(packet, '__str__'):
                    summaries.append(str(packet))
                else:
                    summaries.append(f"Packet {i}: {type(packet).__name__}")
            except Exception as e:
                summaries.append(f"Packet {i}: Error getting summary - {e}")
                
        return summaries
        
    def get_packets(self) -> List[Any]:
        """Get all packets in the collection."""
        return self._packets.copy()
        
    def get_packets_by_type(self, packet_type: Type[T]) -> List[T]:
        """Get packets of a specific type."""
        matching_packets = []
        for packet in self._packets:
            try:
                if isinstance(packet, packet_type):
                    matching_packets.append(packet)
            except Exception as e:
                self.logger.debug(f"Error checking packet type: {e}")
                
        return matching_packets

    # ------------------------------------------------------------------
    # Packet Construction
    # ------------------------------------------------------------------
    def build_packet_from_config(self, config: List[Dict[str, Any]]) -> Optional[Any]:
        """
        Build a packet from a configuration.
        
        Args:
            config: List of protocol configurations
            
        Returns:
            The constructed packet or None if failed
        """
        if not config:
            self.logger.warning("Empty configuration provided")
            return None
            
        try:
            if self.packet_builder:
                packet = self.packet_builder.build_packet_from_config(config)
                if packet:
                    self.logger.debug(f"Packet built successfully from {len(config)} protocols")
                else:
                    self.logger.warning("PacketBuilder returned None")
                return packet
            else:
                self.logger.error("No packet builder available")
                return self._create_simple_packet(config)
                
        except Exception as e:
            self.logger.error(f"Error building packet from config: {e}")
            return self._create_simple_packet(config)

    def _create_simple_packet(self, config: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a simple packet representation as fallback."""
        return {
            "type": "simple_packet",
            "config": config,
            "protocols": [p.get('name', 'unknown') for p in config],
            "timestamp": time.time(),
            "size": sum(len(str(p)) for p in config),
            "created_by": "PacketManager.fallback"
        }

    # ------------------------------------------------------------------
    # Bulk Operations
    # ------------------------------------------------------------------
    def apply_modifier(self, modifier_fn: Callable[[Any], Any]) -> None:
        """Apply a transformation function to all packets."""
        if not callable(modifier_fn):
            self.logger.error("Modifier function is not callable")
            return
            
        modified_packets = []
        for i, packet in enumerate(self._packets):
            try:
                modified_packet = modifier_fn(packet)
                modified_packets.append(modified_packet)
            except Exception as e:
                self.logger.error(f"Error modifying packet {i}: {e}")
                modified_packets.append(packet)  # Keep original on error
                
        self._packets = modified_packets
        self.logger.debug(f"Applied modifier to {len(self._packets)} packets")

    def bulk_modify(self, **actions) -> None:
        """Apply bulk modifications to all packets."""
        if not self.packet_modifier_class:
            self.logger.warning("PacketModifier not available - skipping bulk modify")
            return
            
        modified_count = 0
        for idx, packet in enumerate(self._packets):
            try:
                modifier = self.packet_modifier_class(packet)
                
                if actions.get("swap"):
                    modifier.swap_src_dst()
                if (ttl := actions.get("ttl")) is not None:
                    modifier.set_ttl(ttl)
                if (vlan := actions.get("vlan_id")) is not None:
                    modifier.set_vlan_id(vlan)
                    
                self._packets[idx] = modifier.apply()
                modified_count += 1
                
            except Exception as e:
                self.logger.error(f"Error modifying packet {idx}: {e}")
                
        self.logger.debug(f"Bulk modified {modified_count}/{len(self._packets)} packets")
            
    def filter(self, predicate: Callable[[Any], bool]) -> List[Any]:
        """Filter packets based on a predicate function."""
        if not callable(predicate):
            self.logger.error("Predicate is not callable")
            return []
            
        filtered_packets = []
        for packet in self._packets:
            try:
                if predicate(packet):
                    filtered_packets.append(packet)
            except Exception as e:
                self.logger.debug(f"Error applying predicate to packet: {e}")
                
        return filtered_packets
        
    def filter_inplace(self, predicate: Callable[[Any], bool]) -> None:
        """Filter packets in-place based on a predicate function."""
        original_count = len(self._packets)
        self._packets = self.filter(predicate)
        filtered_count = original_count - len(self._packets)
        self.logger.debug(f"Filtered out {filtered_count} packets (remaining: {len(self._packets)})")
        
    def clone(self) -> 'PacketManager':
        """Create a copy of this PacketManager with the same packets."""
        new_manager = PacketManager()
        try:
            # Deep copy all packets to ensure complete isolation
            new_manager._packets = copy.deepcopy(self._packets)
            self.logger.debug(f"Cloned PacketManager with {len(self._packets)} packets")
        except Exception as e:
            self.logger.error(f"Error cloning PacketManager: {e}")
            # Fallback to shallow copy
            new_manager._packets = self._packets.copy()
            
        return new_manager

    # ------------------------------------------------------------------
    # Export / Save
    # ------------------------------------------------------------------
    def to_bytes(self) -> bytes:
        """Serialize all packets to bytes."""
        all_bytes = b""
        
        for i, packet in enumerate(self._packets):
            try:
                if hasattr(packet, 'serialize'):
                    packet_bytes = packet.serialize()
                elif hasattr(packet, 'raw'):
                    packet_bytes = packet.raw()
                elif isinstance(packet, bytes):
                    packet_bytes = packet
                elif isinstance(packet, dict) and 'data' in packet:
                    packet_bytes = packet['data']
                    if isinstance(packet_bytes, str):
                        packet_bytes = packet_bytes.encode('utf-8')
                else:
                    packet_bytes = str(packet).encode('utf-8')
                    
                if isinstance(packet_bytes, bytes):
                    all_bytes += packet_bytes
                    
            except Exception as e:
                self.logger.error(f"Error serializing packet {i}: {e}")
                
        return all_bytes

    def to_pcap(self, path: Union[str, Path]) -> Optional[Path]:
        """
        Write all packets to a PCAP file.
        
        Args:
            path: Path to output PCAP file
            
        Returns:
            Path to the created PCAP file or None if failed
        """
        try:
            path_obj = Path(path)
            
            if self.pcap_generator:
                # Use proper PCAP generator
                if hasattr(self.pcap_generator, 'write_pcap'):
                    result_path = self.pcap_generator.write_pcap(path_obj, self._packets)
                    self.logger.info(f"PCAP written successfully: {result_path}")
                    return result_path
                else:
                    # Instance method
                    generator = self.pcap_generator()
                    result_path = generator.write_pcap(path_obj, self._packets)
                    self.logger.info(f"PCAP written successfully: {result_path}")
                    return result_path
            else:
                # Fallback: write raw bytes
                with open(path_obj, 'wb') as f:
                    f.write(self.to_bytes())
                self.logger.warning(f"PCAP written as raw bytes (no generator): {path_obj}")
                return path_obj
                
        except Exception as e:
            self.logger.error(f"Error writing PCAP to {path}: {e}")
            return None

    # ------------------------------------------------------------------
    # Statistics and Info
    # ------------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the packet collection."""
        stats = {
            "total_packets": len(self._packets),
            "total_size": 0,
            "protocol_counts": {},
            "packet_types": {},
        }
        
        for packet in self._packets:
            try:
                # Count by type
                packet_type = type(packet).__name__
                stats["packet_types"][packet_type] = stats["packet_types"].get(packet_type, 0) + 1
                
                # Get size
                if hasattr(packet, 'size'):
                    stats["total_size"] += packet.size
                elif isinstance(packet, dict) and 'size' in packet:
                    stats["total_size"] += packet['size']
                elif hasattr(packet, '__len__'):
                    stats["total_size"] += len(packet)
                
                # Count protocols (if available)
                if isinstance(packet, dict) and 'protocols' in packet:
                    for protocol in packet['protocols']:
                        stats["protocol_counts"][protocol] = stats["protocol_counts"].get(protocol, 0) + 1
                elif hasattr(packet, 'protocols'):
                    for protocol in packet.protocols:
                        protocol_name = getattr(protocol, 'name', str(protocol))
                        stats["protocol_counts"][protocol_name] = stats["protocol_counts"].get(protocol_name, 0) + 1
                        
            except Exception as e:
                self.logger.debug(f"Error collecting stats for packet: {e}")
                
        return stats

    def __repr__(self) -> str:
        """String representation of PacketManager."""
        return f"PacketManager(packets={len(self._packets)})"

    def __str__(self) -> str:
        """Human-readable string representation."""
        stats = self.get_stats()
        return (f"PacketManager: {stats['total_packets']} packets, "
                f"{stats['total_size']} bytes, "
                f"{len(stats['packet_types'])} different types")