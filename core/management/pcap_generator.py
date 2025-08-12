#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TECMP-Tool PCAP Generator 
Native implementation without Scapy dependencies
Fixed circular reference issue with PcapWriter
"""

import os
import logging
import struct
import datetime
import time
from pathlib import Path
from typing import Union, List, Optional, BinaryIO, Any, Iterable, Tuple, Dict


# =================== CUSTOM EXCEPTIONS ===================

class PCAPGenerationError(Exception):
    """Custom exception for PCAP generation errors that can be caught by UI components."""
    pass


class PCAPFormatError(PCAPGenerationError):
    """Exception raised when there's an error in PCAP formatting."""
    pass


class PCAPIOError(PCAPGenerationError):
    """Exception raised when there's an I/O error in PCAP operations."""
    pass


class PacketNormalizationError(Exception):
    """Custom exception for packet normalization errors."""
    pass


# =================== UTILITY CLASSES ===================

class PathUtils:
    """Utility class for path operations."""

    @staticmethod
    def ensure_directory_exists(path: Union[str, Path]) -> Path:
        """
        Ensure a directory exists, creating it if necessary, and verify it's writable.
        
        Args:
            path: Directory path to ensure
            
        Returns:
            Path object of created/existing directory
            
        Raises:
            PCAPIOError: If directory cannot be created or is not writable
        """
        try:
            directory_path = Path(path)
            directory_path.mkdir(parents=True, exist_ok=True)
            
            # Verify directory exists and is writable
            if not directory_path.is_dir():
                raise PCAPIOError(f"Path {path} exists but is not a directory")
                
            # Check write permissions
            if not os.access(directory_path, os.W_OK):
                raise PCAPIOError(f"Directory {path} is not writable")
                
            return directory_path
        except Exception as e:
            if isinstance(e, PCAPIOError):
                raise
            raise PCAPIOError(f"Failed to create directory {path}") from e


class PacketUtils:
    """Utility class for packet operations."""

    @staticmethod
    def normalize(packet: Any) -> bytes:
        """
        Convert various packet representations to bytes.
        
        Args:
            packet: Object to normalize (Packet, bytes, or object with serialize/raw method)
            
        Returns:
            Packet data as bytes
            
        Raises:
            PacketNormalizationError: If packet cannot be normalized
        """
        try:
            # Case 1: Already bytes
            if isinstance(packet, bytes):
                return packet
                
            # Case 2: Bytearray
            if isinstance(packet, bytearray):
                return bytes(packet)
                
            # Case 3: String
            if isinstance(packet, str):
                return packet.encode('utf-8')
                
            # Case 4: Dict with data field (from our factory system)
            if isinstance(packet, dict):
                if 'data' in packet:
                    data = packet['data']
                    if isinstance(data, bytes):
                        return data
                    elif isinstance(data, str):
                        return data.encode('utf-8')
                
            # Case 5: Packet class from our library
            try:
                from core.packets.base.packet import Packet
                if isinstance(packet, Packet):
                    return packet.serialize()
            except ImportError:
                pass
                
            # Case 6: Object with serialize() method
            if hasattr(packet, 'serialize') and callable(packet.serialize):
                result = packet.serialize()
                if isinstance(result, bytes):
                    return result
                    
            # Case 7: Object with raw() method
            if hasattr(packet, 'raw') and callable(packet.raw):
                result = packet.raw()
                if isinstance(result, bytes):
                    return result
                    
            # Case 8: Object with _data or data attribute
            for attr in ['_data', 'data', 'payload']:
                if hasattr(packet, attr):
                    data = getattr(packet, attr)
                    if isinstance(data, bytes):
                        return data
                    elif isinstance(data, bytearray):
                        return bytes(data)
                        
            # Case 9: Try direct conversion
            try:
                return bytes(packet)
            except (TypeError, ValueError):
                pass
                
            # Unsupported type - create a fallback
            packet_str = str(packet)
            return packet_str.encode('utf-8')
                
        except Exception as e:
            if isinstance(e, PacketNormalizationError):
                raise
            raise PacketNormalizationError(f"Error normalizing packet: {str(e)}") from e


# =================== PCAP WRITER CORE ===================

TimeValue = Union[float, int, datetime.datetime]


class PcapWriter:
    """
    Pure utility class for PCAP format operations without I/O concerns.
    Native implementation instead of Scapy.
    """
    
    # PCAP global header format - little-endian
    PCAP_GLOBAL_HEADER_FORMAT = '<IHHIIII'
    
    # PCAP packet header format - little-endian
    PCAP_PACKET_HEADER_FORMAT = '<IIII'
    
    # PCAP constants
    PCAP_MAGIC = 0xa1b2c3d4  # magic number (little-endian)
    PCAP_VERSION_MAJOR = 2    # major version
    PCAP_VERSION_MINOR = 4    # minor version
    PCAP_THISZONE = 0         # GMT to local correction
    PCAP_SIGFIGS = 0          # accuracy of timestamps
    
    # Linktype constants
    LINKTYPE_ETHERNET = 1
    LINKTYPE_RAW = 12
    LINKTYPE_USER0 = 147    # For TECMP
    LINKTYPE_USER1 = 148
    LINKTYPE_USER2 = 149
    LINKTYPE_USER3 = 150
    LINKTYPE_USER4 = 151
    
    @classmethod
    def format_global_header(cls, snaplen: int = 65535, network: int = 1) -> bytes:
        """
        Format PCAP global header as bytes.
        
        Args:
            snaplen: Maximum length of captured packets
            network: Data link type (1 = Ethernet, 147 = USER0, etc.)
            
        Returns:
            Formatted global header as bytes
        """
        try:
            return struct.pack(
                cls.PCAP_GLOBAL_HEADER_FORMAT,
                cls.PCAP_MAGIC,
                cls.PCAP_VERSION_MAJOR,
                cls.PCAP_VERSION_MINOR,
                cls.PCAP_THISZONE,
                cls.PCAP_SIGFIGS,
                snaplen,
                network
            )
        except struct.error as e:
            raise PCAPFormatError(f"Failed to format PCAP global header: {str(e)}") from e
    
    @classmethod
    def normalize_timestamp(cls, timestamp: Optional[TimeValue] = None) -> Tuple[int, int]:
        """
        Normalize various timestamp formats to seconds and microseconds.
        
        Args:
            timestamp: Timestamp value (float, int, datetime, or None for current time)
            
        Returns:
            Tuple of (seconds, microseconds)
        """
        if timestamp is None:
            # Use current time
            timestamp = time.time()
            
        # Convert datetime to float
        if isinstance(timestamp, datetime.datetime):
            timestamp = timestamp.timestamp()
            
        # Convert to seconds and microseconds
        seconds = int(timestamp)
        microseconds = int((timestamp - seconds) * 1000000)
        
        return seconds, microseconds
    
    @classmethod
    def format_packet_header(cls, packet_data: bytes, 
                            timestamp: Optional[TimeValue] = None) -> bytes:
        """
        Format PCAP packet header as bytes.
        
        Args:
            packet_data: Packet data as bytes
            timestamp: Packet timestamp (optional)
            
        Returns:
            Formatted packet header as bytes
        """
        try:
            seconds, microseconds = cls.normalize_timestamp(timestamp)
            
            return struct.pack(
                cls.PCAP_PACKET_HEADER_FORMAT,
                seconds,
                microseconds,
                len(packet_data),
                len(packet_data)
            )
        except struct.error as e:
            raise PCAPFormatError(f"Failed to format PCAP packet header: {str(e)}") from e


# =================== MAIN PCAP GENERATOR ===================

class PcapGenerator:
    """
    PCAP file generator with improved error handling and consistent API.
    Native implementation without Scapy dependencies.
    
    This class is responsible for:
    1. Writing packets to PCAP files
    2. Managing file I/O operations
    3. Handling output directory management
    4. Providing TECMP-specific functionality
    """

    def __init__(self, output_directory: Optional[Union[str, Path]] = None,
                 snaplen: int = 65535, network: int = 1):
        """
        Initialize PcapGenerator with an optional output directory.
        
        Args:
            output_directory: Directory to save PCAP files (optional)
            snaplen: Maximum length of captured packets (default: 65535)
            network: Data link type (1 = Ethernet, 147 = USER0 for TECMP)
        """
        self.logger = logging.getLogger("TECMP-Tool.PcapGenerator")
        self.output_directory: Optional[Path] = None
        self.snaplen = snaplen
        self.network = network
        
        if output_directory:
            self.set_output_directory(output_directory)
            
        self.logger.info("PcapGenerator initialized with native implementation")

    def set_output_directory(self, directory: Union[str, Path]) -> None:
        """
        Set and create the output directory for PCAP files.
        
        Args:
            directory: Path to directory
            
        Raises:
            PCAPIOError: If directory cannot be created or is not writable
        """
        try:
            self.output_directory = PathUtils.ensure_directory_exists(directory)
            self.logger.debug(f"PCAP output directory set to: {self.output_directory}")
        except Exception as e:
            if isinstance(e, PCAPIOError):
                raise
            raise PCAPIOError(f"Failed to set output directory: {str(e)}") from e

    @classmethod
    def write_pcap_header(cls, file_handle: BinaryIO, 
                         snaplen: int = 65535, network: int = 1) -> None:
        """
        Write PCAP global header to file using native implementation.
        
        Args:
            file_handle: Open file handle for writing
            snaplen: Maximum length of captured packets
            network: Data link type (1 = Ethernet, 147 = USER0, etc.)
            
        Raises:
            PCAPIOError: If writing header fails
        """
        try:
            header = PcapWriter.format_global_header(snaplen, network)
            file_handle.write(header)
        except Exception as e:
            if isinstance(e, PCAPFormatError):
                raise PCAPIOError(f"Failed to write PCAP header: {str(e)}") from e
            raise PCAPIOError(f"Failed to write PCAP header: {str(e)}") from e

    @classmethod
    def write_packet_header(cls, file_handle: BinaryIO, packet_data: bytes, 
                           timestamp: Optional[TimeValue] = None) -> None:
        """
        Write PCAP packet header followed by packet data using native implementation.
        
        Args:
            file_handle: Open file handle for writing
            packet_data: Packet data as bytes
            timestamp: Optional packet timestamp (current time if None)
            
        Raises:
            PCAPIOError: If writing packet header fails
        """
        try:
            header = PcapWriter.format_packet_header(packet_data, timestamp)
            file_handle.write(header)
            file_handle.write(packet_data)
        except Exception as e:
            if isinstance(e, PCAPFormatError):
                raise PCAPIOError(f"Failed to write packet header: {str(e)}") from e
            raise PCAPIOError(f"Failed to write packet header: {str(e)}") from e

    @classmethod
    def write_pcap(cls, output_path: Union[str, Path], 
                  packets: Iterable[Any], 
                  timestamps: Optional[List[TimeValue]] = None,
                  snaplen: int = 65535, network: int = 1) -> Path:
        """
        Write multiple packets to a PCAP file using native implementation.
        
        Args:
            output_path: Path to output PCAP file
            packets: Iterable of packets to write
            timestamps: Optional list of timestamps (one per packet)
            snaplen: Maximum length of captured packets
            network: Data link type (1 = Ethernet, 147 = USER0, etc.)
            
        Returns:
            Path to the generated PCAP file
            
        Raises:
            PCAPIOError: If writing PCAP fails
        """
        logger = logging.getLogger("TECMP-Tool.PcapGenerator")
        
        try:
            # Ensure parent directory exists
            output_path = Path(output_path)
            if output_path.parent != Path('.'):
                PathUtils.ensure_directory_exists(output_path.parent)
                
            # Count packets for logging
            packet_count = 0
            
            # Open file for writing
            with open(output_path, 'wb') as f:
                # Write PCAP global header
                cls.write_pcap_header(f, snaplen, network)
                
                # Write each packet
                for i, packet in enumerate(packets):
                    # Get timestamp for this packet
                    timestamp = None if timestamps is None else (
                        timestamps[i] if i < len(timestamps) else None
                    )
                    
                    # Normalize packet to bytes
                    try:
                        normalized_packet = PacketUtils.normalize(packet)
                    except PacketNormalizationError as e:
                        # Log warning but continue with other packets
                        logger.warning(f"Failed to normalize packet {i}: {e}")
                        continue
                    
                    # Write packet with header
                    cls.write_packet_header(f, normalized_packet, timestamp)
                    packet_count += 1
            
            logger.info(f"PCAP file generated: {output_path} ({packet_count} packets)")
            return output_path
            
        except Exception as e:
            if isinstance(e, PCAPGenerationError):
                raise
            raise PCAPIOError(f"Failed to write PCAP file: {str(e)}") from e

    def generate_pcap(self, filename: str, packets: Iterable[Any], 
                     timestamps: Optional[List[TimeValue]] = None) -> Path:
        """
        Generate a PCAP file in the configured output directory.
        
        Args:
            filename: Name of the PCAP file to generate
            packets: Iterable of packets to write
            timestamps: Optional list of timestamps (one per packet)
            
        Returns:
            Path to the generated PCAP file
            
        Raises:
            PCAPIOError: If output directory not set or writing fails
        """
        if not self.output_directory:
            raise PCAPIOError("Output directory not set. Call set_output_directory() first.")
            
        # Ensure filename has .pcap extension
        if not filename.lower().endswith('.pcap'):
            filename += '.pcap'
            
        output_path = self.output_directory / filename
        
        return self.write_pcap(output_path, packets, timestamps, 
                             self.snaplen, self.network)

    def write_packet_to_pcap(self, packet: Any, output_path: Union[str, Path], 
                            timestamp: Optional[TimeValue] = None) -> Path:
        """
        Write a single packet to a PCAP file.
        
        Args:
            packet: Packet to write
            output_path: Path to output PCAP file
            timestamp: Optional packet timestamp
            
        Returns:
            Path to the generated PCAP file
            
        Raises:
            PCAPIOError: If writing fails
        """
        return self.write_pcap(output_path, [packet], 
                             [timestamp] if timestamp else None,
                             self.snaplen, self.network)

    def generate_pcap_for_tecmp(self, filename: str, packets: Iterable[Any],
                               timestamps: Optional[List[TimeValue]] = None,
                               use_ethernet_encapsulation: bool = True) -> Path:
        """
        Generate a PCAP file specifically optimized for TECMP packets.
        
        Args:
            filename: Name of the PCAP file to generate
            packets: Iterable of TECMP packets to write
            timestamps: Optional list of timestamps (one per packet)
            use_ethernet_encapsulation: If True, use Ethernet linktype for better Wireshark compatibility
            
        Returns:
            Path to the generated PCAP file
        """
        # Choose linktype based on preference
        if use_ethernet_encapsulation:
            linktype = PcapWriter.LINKTYPE_ETHERNET  # Better Wireshark compatibility
            self.logger.info("Using Ethernet linktype for TECMP PCAP (better Wireshark compatibility)")
        else:
            linktype = PcapWriter.LINKTYPE_USER0     # Pure TECMP format
            self.logger.info("Using USER0 linktype for TECMP PCAP (pure TECMP format)")
        
        # Temporarily change network type
        original_network = self.network
        self.network = linktype
        
        try:
            result = self.generate_pcap(filename, packets, timestamps)
            self.logger.info(f"TECMP PCAP generated: {result}")
            return result
        finally:
            # Restore original network type
            self.network = original_network


# =================== SCAPY COMPATIBILITY LAYER ===================

class NativePCAPWriter:
    """
    Native PCAP writer context manager.
    Compatible replacement for Scapy's PcapWriter.
    """
    
    def __init__(self, filename: Union[str, Path], 
                 linktype: int = PcapWriter.LINKTYPE_ETHERNET,
                 sync: bool = True, **kwargs):
        """
        Initialize native PCAP writer.
        
        Args:
            filename: Output filename
            linktype: Link layer type  
            sync: Ignored (for Scapy compatibility)
            **kwargs: Additional arguments (ignored for compatibility)
        """
        self.filename = Path(filename)
        self.linktype = linktype
        self.file_handle = None
        self.packet_count = 0
        self.is_open = False
        self.logger = logging.getLogger("TECMP-Tool.NativePCAPWriter")
        
        # Open file and write header
        self._open()
    
    def _open(self):
        """Open file and write global header"""
        try:
            self.file_handle = open(self.filename, 'wb')
            self.is_open = True
            
            # Write global header using PcapWriter class (not self)
            header = PcapWriter.format_global_header(65535, self.linktype)
            self.file_handle.write(header)
            
            self.logger.debug(f"Opened PCAP file: {self.filename}")
            
        except Exception as e:
            raise PCAPIOError(f"Failed to open {self.filename}: {e}")
    
    def write(self, packet: Any):
        """
        Write a packet (compatible with Scapy Raw packets)
        
        Args:
            packet: Packet to write (Raw packet, bytes, or packet object)
        """
        if not self.is_open:
            raise PCAPIOError("PCAP writer is closed")
        
        try:
            # Normalize packet to bytes
            packet_data = PacketUtils.normalize(packet)
            
            # Write packet with header
            PcapGenerator.write_packet_header(self.file_handle, packet_data)
            self.packet_count += 1
            
        except Exception as e:
            raise PCAPIOError(f"Failed to write packet: {e}")
    
    def close(self):
        """Close the PCAP file"""
        if self.file_handle and self.is_open:
            self.file_handle.close()
            self.is_open = False
            self.logger.debug(f"Closed PCAP file: {self.filename} ({self.packet_count} packets)")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def __del__(self):
        if self.is_open:
            self.close()


class RawPacket:
    """
    Replacement for Scapy's Raw packet.
    Compatible interface for easy migration.
    """
    
    def __init__(self, data: Union[bytes, str, bytearray] = b""):
        """
        Create a raw packet.
        
        Args:
            data: Packet data
        """
        if isinstance(data, str):
            self._data = data.encode('utf-8')
        elif isinstance(data, bytearray):
            self._data = bytes(data)
        elif isinstance(data, bytes):
            self._data = data
        else:
            self._data = bytes(data)
    
    def raw(self) -> bytes:
        """Return raw packet data (Scapy compatibility)"""
        return self._data
    
    def serialize(self) -> bytes:
        """Serialize packet (our library compatibility)"""
        return self._data
    
    def __bytes__(self) -> bytes:
        return self._data
    
    def __len__(self) -> int:
        return len(self._data)
    
    def __str__(self) -> str:
        return f"RawPacket({len(self._data)} bytes)"


# =================== BACKWARDS COMPATIBILITY ===================

# Aliases for backwards compatibility and drop-in Scapy replacement
# FIXED: Removed circular reference by creating separate aliases
ScapyPcapWriter = NativePCAPWriter  # Safe alias for Scapy compatibility
Raw = RawPacket                     # Drop-in replacement for Scapy


# =================== FACTORY INTEGRATION ===================

def create_pcap_from_packets(packets: List[Any], output_path: str) -> bool:
    """
    Convenience function to create PCAP from a list of packets.
    Integrates with the packet factory system.
    
    Args:
        packets: List of packet objects
        output_path: Path to output PCAP file
        
    Returns:
        bool: True if successful
    """
    try:
        generator = PcapGenerator()
        generator.write_pcap(output_path, packets)
        return True
    except Exception as e:
        logger = logging.getLogger("TECMP-Tool.PcapGenerator")
        logger.error(f"Failed to create PCAP from packets: {e}")
        return False


# =================== TESTING ===================

def test_pcap_generation():
    """Test PCAP generation functionality"""
    import tempfile
    
    logger = logging.getLogger("TECMP-Tool.PcapGenerator.Test")
    
    try:
        # Create test packets
        test_packets = []
        for i in range(3):
            # Create simple test packet
            packet_data = f"Test packet {i}".encode('utf-8')
            test_packets.append(packet_data)
        
        # Test with temporary file
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            output_path = tmp.name
        
        # Generate PCAP
        generator = PcapGenerator()
        result_path = generator.write_pcap(output_path, test_packets)
        
        # Verify file exists and has content
        if result_path.exists() and result_path.stat().st_size > 24:  # Header is 24 bytes
            logger.info(f"? PCAP generation test passed: {result_path}")
            return True
        else:
            logger.error("? PCAP generation test failed: file not created or empty")
            return False
            
    except Exception as e:
        logger.error(f"? PCAP generation test failed: {e}")
        return False


# =================== MODULE INITIALIZATION ===================

def _initialize_module():
    """Initialize the module"""
    logger = logging.getLogger("TECMP-Tool.PcapGenerator")
    logger.info("PcapGenerator module initialized successfully (native implementation)")
    return True


# Initialize when imported
_INITIALIZED = _initialize_module()


# =================== EXPORTS ===================

__all__ = [
    # Main classes
    'PcapGenerator',
    'NativePCAPWriter',
    'RawPacket',
    
    # Utilities
    'PacketUtils',
    'PathUtils',
    'PcapWriter',
    
    # Exceptions
    'PCAPGenerationError',
    'PCAPFormatError', 
    'PCAPIOError',
    'PacketNormalizationError',
    
    # Compatibility aliases
    'ScapyPcapWriter',  # Changed from PcapWriter to avoid circular ref
    'Raw',
    
    # Functions
    'create_pcap_from_packets',
    'test_pcap_generation'
]


# =================== DEMO/TESTING ===================

if __name__ == "__main__":
    # Run tests when module is executed directly
    print("=== PCAP Generator Testing ===")
    
    if test_pcap_generation():
        print("? All tests passed")
    else:
        print("? Some tests failed")
        exit(1)
    
    print("\n=== Demo Usage ===")
    
    # Demo: Create some test packets
    test_packets = []
    for i in range(5):
        # Create TECMP-like packet
        tecmp_data = struct.pack("!HHBBHHH", 0x0080, i, 3, 0x03, 0x0080, 0x0000, 0x000f)
        tecmp_data += f"Test payload {i}".encode()
        test_packets.append(tecmp_data)
    
    # Method 1: Using PcapGenerator class (recommended)
    print("1. Testing PcapGenerator...")
    generator = PcapGenerator("test_output")
    output_file = generator.generate_pcap_for_tecmp("demo_tecmp.pcap", test_packets)
    print(f"   Generated: {output_file}")
    
    # Method 2: Using context manager (Scapy-compatible)
    print("\n2. Testing NativePCAPWriter...")
    with NativePCAPWriter("demo_native.pcap") as pcap:
        for packet_data in test_packets:
            pcap.write(RawPacket(packet_data))
    print("   Generated: demo_native.pcap")
    
    print("\n=== Demo Complete ===")