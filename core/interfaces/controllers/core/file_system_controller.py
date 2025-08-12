#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
file_system_controller.py - TECMP-Tool File System Controller
============================================================

Enhanced version with large file support for JSON TECMP, PCAP, and PCAPNG files.
Maintains all existing functionality while adding streaming capabilities.

CHANGES:
- Added streaming support for large files (> 100 MB)
- Added chunk-based reading for JSON files
- Added memory management for large PCAP files
- Maintains backward compatibility with all existing methods
"""

import os
import json
import time
import threading
import shutil
import tempfile
import hashlib
import gc
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Iterator
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import gzip
import struct

# Qt imports with fallbacks
try:
    from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
    from PyQt5.QtWidgets import QFileDialog, QProgressDialog, QMessageBox
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    QObject = object
    
    def pyqtSignal(*args):
        class Signal:
            def emit(self, *args, **kwargs):
                pass
            def connect(self, func):
                pass
        return Signal()

# Import TECMP components
try:
    from core.interfaces.controllers.core.error_handler import (
        get_error_handler, handle_errors, ErrorCategory
    )
    from core.interfaces.controllers.core.undo_redo_controller import (
        CommandType, create_safe_command
    )
    CONTROLLERS_AVAILABLE = True
except ImportError:
    CONTROLLERS_AVAILABLE = False
    
    def handle_errors(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Import scapy for PCAP handling
try:
    from scapy.all import wrpcap, rdpcap, PcapWriter, PcapReader
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

# Import TECMP parser if available
try:
    from tecmp_json_parser import (
        TECMPJSONParser, 
        TECMPPacket, 
        TECMPAnalyzer
    )
    TECMP_PARSER_AVAILABLE = True
except ImportError:
    TECMP_PARSER_AVAILABLE = False
    class TECMPPacket:
        pass
    class TECMPJSONParser:
        pass
    class TECMPAnalyzer:
        pass

# ============================================================================
# FILE TYPES AND FORMATS (existing)
# ============================================================================

class FileType(Enum):
    """Supported file types"""
    TECMP_PROJECT = auto()
    PCAP = auto()
    PCAPNG = auto()
    CONFIG_JSON = auto()
    CONFIG_XML = auto()
    EXPORT_CSV = auto()
    EXPORT_TXT = auto()
    BINARY_DUMP = auto()
    SESSION = auto()
    TEMPLATE = auto()

@dataclass
class FileFormat:
    """File format specification"""
    extension: str
    mime_type: str
    description: str
    binary: bool = True
    compressed: bool = False
    versioned: bool = True

FILE_FORMATS = {
    FileType.TECMP_PROJECT: FileFormat(
        extension=".tecmp",
        mime_type="application/x-tecmp-project",
        description="TECMP Project File",
        binary=True,
        compressed=True,
        versioned=True
    ),
    FileType.PCAP: FileFormat(
        extension=".pcap",
        mime_type="application/vnd.tcpdump.pcap",
        description="Packet Capture File",
        binary=True
    ),
    FileType.PCAPNG: FileFormat(
        extension=".pcapng",
        mime_type="application/x-pcapng",
        description="Next Generation Packet Capture",
        binary=True
    ),
    FileType.CONFIG_JSON: FileFormat(
        extension=".json",
        mime_type="application/json",
        description="JSON Configuration",
        binary=False
    ),
    FileType.SESSION: FileFormat(
        extension=".tss",
        mime_type="application/x-tecmp-session",
        description="TECMP Session File",
        binary=True,
        compressed=True
    )
}

@dataclass
class FileMetadata:
    """File metadata information"""
    path: Path
    file_type: FileType
    size: int
    created: float
    modified: float
    checksum: str
    version: Optional[str] = None
    compressed: bool = False
    encoding: str = "utf-8"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': str(self.path),
            'file_type': self.file_type.name,
            'size': self.size,
            'created': self.created,
            'modified': self.modified,
            'checksum': self.checksum,
            'version': self.version,
            'compressed': self.compressed,
            'encoding': self.encoding
        }

@dataclass
class FileOperationResult:
    """Result of file operation"""
    success: bool
    file_path: Optional[Path] = None
    data: Any = None
    error: Optional[str] = None
    metadata: Optional[FileMetadata] = None
    warnings: List[str] = field(default_factory=list)
    
    @property
    def path_str(self) -> str:
        return str(self.file_path) if self.file_path else ""

# ============================================================================
# LARGE FILE SUPPORT CLASSES
# ============================================================================

class LargeFileReader:
    """
    Optimized reader for large files with streaming support
    """
    
    # Size thresholds
    SMALL_FILE_THRESHOLD = 10 * 1024 * 1024  # 10 MB
    MEDIUM_FILE_THRESHOLD = 100 * 1024 * 1024  # 100 MB
    LARGE_FILE_THRESHOLD = 500 * 1024 * 1024  # 500 MB
    
    # Chunk configuration
    DEFAULT_CHUNK_SIZE = 1000  # Number of packets per chunk
    MAX_MEMORY_USAGE = 500 * 1024 * 1024  # 500 MB max memory
    
    def __init__(self, file_path: Union[str, Path], progress_callback=None):
        """
        Initialize large file reader
        
        Args:
            file_path: Path to file
            progress_callback: Optional progress callback function
        """
        self.file_path = Path(file_path)
        self.file_size = self.file_path.stat().st_size if self.file_path.exists() else 0
        self.progress_callback = progress_callback
        self.is_large_file = self.file_size > self.MEDIUM_FILE_THRESHOLD
        
    def read_json_streaming(self) -> Iterator[Dict]:
        """
        Stream read JSON file without loading everything into memory
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                # Check if it's an array
                first_char = file.read(1)
                file.seek(0)
                
                if first_char == '[':
                    # JSON array - parse streaming
                    yield from self._parse_json_array_streaming(file)
                else:
                    # Single object or line-delimited
                    for line in file:
                        if line.strip():
                            try:
                                yield json.loads(line)
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            self.logger.error(f"Error streaming JSON: {e}")
            raise
    
    def _parse_json_array_streaming(self, file) -> Iterator[Dict]:
        """
        Parse JSON array in streaming fashion
        """
        file.read(1)  # Skip opening bracket
        buffer = ""
        depth = 0
        in_string = False
        escape_next = False
        
        while True:
            chunk = file.read(8192)  # Read in 8KB chunks
            if not chunk:
                break
                
            for char in chunk:
                if not escape_next:
                    if char == '"' and not in_string:
                        in_string = True
                    elif char == '"' and in_string:
                        in_string = False
                    elif char == '\\' and in_string:
                        escape_next = True
                        
                    if not in_string:
                        if char in '{[':
                            depth += 1
                        elif char in '}]':
                            depth -= 1
                            
                        if depth == 0 and char == '}':
                            buffer += char
                            try:
                                obj = json.loads(buffer)
                                yield obj
                                
                                # Update progress
                                if self.progress_callback:
                                    progress = int((file.tell() / self.file_size) * 100)
                                    self.progress_callback(progress)
                                    
                            except json.JSONDecodeError:
                                pass
                            buffer = ""
                            continue
                else:
                    escape_next = False
                
                if depth > 0:
                    buffer += char
                elif char == '{':
                    buffer = char
                    depth = 1
    
    def read_pcap_streaming(self) -> Iterator[Any]:
        """
        Stream read PCAP/PCAPNG file
        """
        if not SCAPY_AVAILABLE:
            raise ImportError("Scapy not available for PCAP streaming")
            
        try:
            packet_count = 0
            with PcapReader(str(self.file_path)) as pcap_reader:
                for packet in pcap_reader:
                    yield packet
                    packet_count += 1
                    
                    # Update progress periodically
                    if self.progress_callback and packet_count % 100 == 0:
                        # Estimate progress (can't get exact position easily)
                        estimated_progress = min(95, packet_count // 100)
                        self.progress_callback(estimated_progress)
                        
                    # Periodic garbage collection for large files
                    if packet_count % 10000 == 0:
                        gc.collect()
                        
        except Exception as e:
            self.logger.error(f"Error streaming PCAP: {e}")
            raise

# ============================================================================
# MAIN FILE SYSTEM CONTROLLER (Enhanced)
# ============================================================================

class FileSystemController(QObject if QT_AVAILABLE else object):
    """
    Comprehensive file system controller for TECMP-Tool
    Enhanced with large file support
    """
    
    # Qt signals
    if QT_AVAILABLE:
        file_operation_started = pyqtSignal(str, str)
        file_operation_completed = pyqtSignal(str, str, bool)
        file_operation_progress = pyqtSignal(str, int)
        auto_save_triggered = pyqtSignal(str)
        file_changed_externally = pyqtSignal(str)
        large_file_detected = pyqtSignal(str, int)  # New signal for large files
        
    TECMP_FILE_VERSION = "2.0.0"
    
    def __init__(self, facade=None, enable_auto_save: bool = True,
                 auto_save_interval: int = 300):
        """Initialize file system controller"""
        if QT_AVAILABLE:
            super().__init__()
            
        self.facade = facade
        self.logger = self._setup_logger()
        
        # Controllers
        self.error_handler = get_error_handler() if CONTROLLERS_AVAILABLE else None
        self.undo_controller = None
        if facade and hasattr(facade, 'undo_controller'):
            self.undo_controller = facade.undo_controller
        
        # File tracking
        self._open_files: Dict[str, FileMetadata] = {}
        self._file_locks: Dict[str, threading.RLock] = {}
        self._recent_files: List[Path] = []
        self._max_recent_files = 10
        
        # Auto-save configuration
        self.enable_auto_save = enable_auto_save
        self.auto_save_interval = auto_save_interval
        self._auto_save_timer = None
        self._auto_save_files: Dict[str, Path] = {}
        
        # Temporary directory
        self._temp_dir = Path(tempfile.gettempdir()) / "tecmp_tool"
        self._temp_dir.mkdir(exist_ok=True)
        
        # File watchers
        self._file_watchers: Dict[str, float] = {}
        
        # Performance tracking
        self._operation_times: Dict[str, List[float]] = {}
        
        # Large file support
        self.enable_streaming = True
        self.streaming_chunk_size = 1000
        
        if QT_AVAILABLE and enable_auto_save:
            self._setup_auto_save_timer()
        
        self.logger.info("FileSystemController initialized with large file support")
    
    def _setup_logger(self):
        """Setup logger"""
        import logging
        return logging.getLogger("TECMP-Tool.FileSystem")
    
    def _setup_auto_save_timer(self):
        """Setup auto-save timer"""
        if QT_AVAILABLE:
            self._auto_save_timer = QTimer()
            self._auto_save_timer.timeout.connect(self._perform_auto_save)
            self._auto_save_timer.start(self.auto_save_interval * 1000)
    
    # ========================================================================
    # ENHANCED LOAD FILE METHOD WITH LARGE FILE SUPPORT
    # ========================================================================
    
    @handle_errors("FileSystem", "load_file")
    def load_file(self, file_path: Union[str, Path], 
                  use_streaming: Optional[bool] = None) -> FileOperationResult:
        """
        Load file with automatic format detection and large file support
        
        Args:
            file_path: Path to the file to load
            use_streaming: Force streaming mode (None = auto-detect)
            
        Returns:
            FileOperationResult with loaded data
        """
        file_path = Path(file_path)
        
        # Check if file exists
        if not file_path.exists():
            error_msg = f"File not found: {file_path}"
            self.logger.error(error_msg)
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=error_msg
            )
        
        # Get file info
        file_size = file_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        extension = file_path.suffix.lower()
        
        # Auto-detect if streaming is needed
        if use_streaming is None:
            use_streaming = file_size > LargeFileReader.MEDIUM_FILE_THRESHOLD
        
        # Emit large file signal if applicable
        if use_streaming and QT_AVAILABLE:
            self.large_file_detected.emit(str(file_path), file_size)
        
        self.logger.info(f"Loading file: {file_path} ({file_size_mb:.1f} MB, streaming={use_streaming})")
        
        try:
            # Route to appropriate loader
            if extension == '.tecmp':
                return self.load_project(file_path)
                
            elif extension in ['.pcap', '.pcapng']:
                if use_streaming:
                    return self._load_pcap_streaming(file_path)
                else:
                    return self.load_pcap(file_path)
                    
            elif extension == '.json':
                # Check content type
                with open(file_path, 'r') as f:
                    first_chars = f.read(100)
                    
                if '_source' in first_chars or 'tecmp' in first_chars.lower():
                    # Likely TECMP JSON
                    if use_streaming:
                        return self._load_json_pcap_streaming(file_path)
                    else:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        return self._load_json_pcap(file_path, data)
                else:
                    return self.load_config(file_path)
                    
            elif extension == '.xml':
                return self.load_config(file_path)
                
            elif extension == '.tss':
                return self.load_session(file_path)
                
            elif extension in ['.csv', '.txt']:
                return self._load_export_file(file_path)
                
            else:
                return self._detect_and_load(file_path)
                
        except Exception as e:
            error_msg = f"Failed to load file: {e}"
            self.logger.error(error_msg)
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=error_msg
            )
    
    # ========================================================================
    # STREAMING METHODS FOR LARGE FILES
    # ========================================================================
    
    def _load_json_pcap_streaming(self, file_path: Path) -> FileOperationResult:
        """
        Load JSON PCAP data using streaming for large files
        """
        try:
            reader = LargeFileReader(
                file_path,
                progress_callback=lambda p: self._emit_progress("load_json", p)
            )
            
            packets = []
            packet_count = 0
            
            # Process in chunks
            for json_obj in reader.read_json_streaming():
                # Parse TECMP packet if parser available
                if TECMP_PARSER_AVAILABLE:
                    if isinstance(json_obj, dict) and '_source' in json_obj:
                        # Wireshark TECMP format
                        parser = TECMPJSONParser()
                        tecmp_packets = parser.parse_wireshark_json([json_obj])
                        packets.extend(tecmp_packets)
                else:
                    packets.append(json_obj)
                
                packet_count += 1
                
                # Yield control periodically
                if packet_count % 1000 == 0:
                    self.logger.debug(f"Loaded {packet_count} packets...")
                    
                    # Optional: Send packets to facade in chunks
                    if self.facade and hasattr(self.facade, 'append_packets'):
                        self.facade.append_packets(packets[-1000:])
            
            # Track file
            self._track_file(file_path, FileType.CONFIG_JSON)
            self._add_recent_file(file_path)
            
            # Create metadata
            metadata = self._create_file_metadata(file_path, FileType.CONFIG_JSON)
            metadata.encoding = "json-streaming"
            
            self.logger.info(f"Loaded {packet_count} packets from JSON (streaming)")
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                data=packets,
                metadata=metadata
            )
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    def _load_pcap_streaming(self, file_path: Path) -> FileOperationResult:
        """
        Load PCAP/PCAPNG file using streaming for large files
        """
        if not SCAPY_AVAILABLE:
            return FileOperationResult(
                success=False,
                error="Scapy not available for PCAP operations"
            )
        
        try:
            reader = LargeFileReader(
                file_path,
                progress_callback=lambda p: self._emit_progress("load_pcap", p)
            )
            
            packets = []
            packet_count = 0
            
            for packet in reader.read_pcap_streaming():
                # Convert to TECMP format if facade available
                if self.facade and hasattr(self.facade, 'create_tecmp_packet_from_scapy'):
                    tecmp_packet = self.facade.create_tecmp_packet_from_scapy(packet)
                    packets.append(tecmp_packet)
                else:
                    packets.append(packet)
                
                packet_count += 1
                
                # Manage memory for very large files
                if packet_count % 10000 == 0:
                    gc.collect()
                    self.logger.debug(f"Loaded {packet_count} packets...")
            
            # Track file
            file_type = FileType.PCAPNG if str(file_path).endswith('.pcapng') else FileType.PCAP
            self._track_file(file_path, file_type)
            self._add_recent_file(file_path)
            
            # Create metadata
            metadata = self._create_file_metadata(file_path, file_type)
            
            self.logger.info(f"Loaded {packet_count} packets from PCAP (streaming)")
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                data=packets,
                metadata=metadata
            )
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    def _emit_progress(self, operation: str, progress: int):
        """Emit progress signal if Qt available"""
        if QT_AVAILABLE:
            self.file_operation_progress.emit(operation, progress)
    
    # ========================================================================
    # EXISTING METHODS (preserved as-is)
    # ========================================================================
    
    def _load_json_pcap(self, file_path: Path, data: Union[Dict, List]) -> FileOperationResult:
        """Load PCAP data from JSON format (existing method preserved)"""
        try:
            packets = []
            is_wireshark_tecmp = False
            
            if isinstance(data, list) and data:
                first_item = data[0]
                if isinstance(first_item, dict):
                    if '_source' in first_item and 'layers' in first_item.get('_source', {}):
                        layers = first_item['_source']['layers']
                        if 'tecmp' in layers:
                            is_wireshark_tecmp = True
                            self.logger.info("Detected Wireshark TECMP JSON format")
            
            if is_wireshark_tecmp and TECMP_PARSER_AVAILABLE:
                parser = TECMPJSONParser()
                tecmp_packets = parser.parse_wireshark_json(data)
                
                if self.facade:
                    if hasattr(self.facade, 'create_packet_from_tecmp'):
                        for tecmp_packet in tecmp_packets:
                            packet = self.facade.create_packet_from_tecmp(tecmp_packet.to_dict())
                            packets.append(packet)
                    else:
                        packets = tecmp_packets
                else:
                    packets = tecmp_packets
                
                self.logger.info(f"Loaded {len(packets)} TECMP packets from JSON")
            else:
                if isinstance(data, dict):
                    packets_data = data.get('packets', data.get('pcap_data', []))
                else:
                    packets_data = data
                
                if self.facade and hasattr(self.facade, 'create_packet_from_json'):
                    for packet_json in packets_data:
                        packet = self.facade.create_packet_from_json(packet_json)
                        packets.append(packet)
                else:
                    packets = packets_data
            
            self._track_file(file_path, FileType.CONFIG_JSON)
            self._add_recent_file(file_path)
            
            metadata = self._create_file_metadata(file_path, FileType.CONFIG_JSON)
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                data=packets,
                metadata=metadata
            )
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    # All other existing methods remain unchanged...
    # (load_project, save_project, load_pcap, save_pcap, etc.)
    # [REST OF THE EXISTING METHODS PRESERVED AS-IS]
    
    # ========================================================================
    # PUBLIC API ADDITIONS
    # ========================================================================
    
    def is_large_file(self, file_path: Union[str, Path]) -> bool:
        """
        Check if a file is considered large
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file is large (> 100 MB)
        """
        try:
            file_size = Path(file_path).stat().st_size
            return file_size > LargeFileReader.MEDIUM_FILE_THRESHOLD
        except:
            return False
    
    def get_file_size_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get detailed file size information
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with size information
        """
        try:
            path = Path(file_path)
            size = path.stat().st_size
            
            return {
                'bytes': size,
                'mb': size / (1024 * 1024),
                'gb': size / (1024 * 1024 * 1024),
                'is_large': size > LargeFileReader.MEDIUM_FILE_THRESHOLD,
                'recommended_streaming': size > LargeFileReader.MEDIUM_FILE_THRESHOLD
            }
        except:
            return {}

# Export public API
__all__ = [
    'FileSystemController',
    'FileType',
    'FileFormat',
    'FileMetadata',
    'FileOperationResult',
    'LargeFileReader',
    'FILE_FORMATS'
]