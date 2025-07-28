#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
file_system_controller.py - TECMP-Tool File System Controller
============================================================

Professional file system controller with facade integration.
Handles all file operations for TECMP-Tool including:
- Packet capture files (PCAP/PCAPNG)
- TECMP project files (.tecmp)
- Configuration files (JSON/XML)
- Export/Import operations
- Session management
- Auto-save functionality

Integrates with error handler and undo/redo system.
"""

import os
import json
import time
import threading
import shutil
import tempfile
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import gzip
import struct

# Qt imports with fallbacks
try:
    from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
    from PyQt5.QtWidgets import QFileDialog
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
    
    # Fallback decorators
    def handle_errors(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Import scapy for PCAP handling
try:
    from scapy.all import wrpcap, rdpcap, PcapWriter
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

# ============================================================================
# FILE TYPES AND FORMATS
# ============================================================================

class FileType(Enum):
    """Supported file types"""
    TECMP_PROJECT = auto()      # .tecmp project files
    PCAP = auto()               # .pcap capture files
    PCAPNG = auto()             # .pcapng capture files
    CONFIG_JSON = auto()        # .json configuration
    CONFIG_XML = auto()         # .xml configuration
    EXPORT_CSV = auto()         # .csv export
    EXPORT_TXT = auto()         # .txt export
    BINARY_DUMP = auto()        # .bin binary dump
    SESSION = auto()            # .tss session file
    TEMPLATE = auto()           # .tpt template file

@dataclass
class FileFormat:
    """File format specification"""
    extension: str
    mime_type: str
    description: str
    binary: bool = True
    compressed: bool = False
    versioned: bool = True

# File format registry
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
        """Convert to dictionary"""
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

# ============================================================================
# FILE OPERATIONS RESULT
# ============================================================================

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
        """Get path as string"""
        return str(self.file_path) if self.file_path else ""

# ============================================================================
# MAIN FILE SYSTEM CONTROLLER
# ============================================================================

class FileSystemController(QObject if QT_AVAILABLE else object):
    """
    Comprehensive file system controller for TECMP-Tool
    
    Features:
    - Multiple file format support
    - Automatic format detection
    - Compression and versioning
    - Atomic operations with rollback
    - Integration with undo/redo system
    - Auto-save functionality
    - File watching and change detection
    - Thread-safe operations
    - Progress reporting for large files
    """
    
    # Qt signals
    if QT_AVAILABLE:
        file_operation_started = pyqtSignal(str, str)  # operation, file_path
        file_operation_completed = pyqtSignal(str, str, bool)  # operation, file_path, success
        file_operation_progress = pyqtSignal(str, int)  # operation, percentage
        auto_save_triggered = pyqtSignal(str)  # file_path
        file_changed_externally = pyqtSignal(str)  # file_path
        
    # File version for TECMP formats
    TECMP_FILE_VERSION = "2.0.0"
    
    def __init__(self, facade=None, enable_auto_save: bool = True,
                 auto_save_interval: int = 300):
        """
        Initialize file system controller
        
        Args:
            facade: TECMP facade instance
            enable_auto_save: Enable automatic saving
            auto_save_interval: Auto-save interval in seconds
        """
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
        self._auto_save_files: Dict[str, Path] = {}  # original -> auto-save
        
        # Temporary directory for atomic operations
        self._temp_dir = Path(tempfile.gettempdir()) / "tecmp_tool"
        self._temp_dir.mkdir(exist_ok=True)
        
        # File watchers
        self._file_watchers: Dict[str, float] = {}  # path -> last_modified
        
        # Performance tracking
        self._operation_times: Dict[str, List[float]] = {}
        
        # Initialize auto-save timer if Qt available
        if QT_AVAILABLE and enable_auto_save:
            self._setup_auto_save_timer()
        
        self.logger.info("FileSystemController initialized")
    
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
    # PROJECT FILE OPERATIONS
    # ========================================================================
    
    @handle_errors("FileSystem", "save_project")
    def save_project(self, file_path: Union[str, Path], 
                    project_data: Dict[str, Any],
                    compress: bool = True) -> FileOperationResult:
        """
        Save TECMP project file
        
        Args:
            file_path: Target file path
            project_data: Project data to save
            compress: Whether to compress the file
            
        Returns:
            FileOperationResult
        """
        file_path = Path(file_path)
        
        # Emit start signal
        if QT_AVAILABLE:
            self.file_operation_started.emit("save_project", str(file_path))
        
        try:
            # Prepare project structure
            project = {
                'version': self.TECMP_FILE_VERSION,
                'created': datetime.now().isoformat(),
                'application': 'TECMP-Tool',
                'data': project_data
            }
            
            # Validate project data
            if self.facade:
                self._validate_project_data(project_data)
            
            # Save with atomic operation
            result = self._atomic_write(
                file_path,
                lambda f: self._write_project_file(f, project, compress),
                binary=True
            )
            
            if result.success:
                # Update tracking
                self._track_file(file_path, FileType.TECMP_PROJECT)
                self._add_recent_file(file_path)
                
                # Create undo command
                if self.undo_controller:
                    self._create_save_undo_command(file_path, project_data)
                
                self.logger.info(f"Project saved: {file_path}")
            
            # Emit completion signal
            if QT_AVAILABLE:
                self.file_operation_completed.emit("save_project", 
                                                 str(file_path), 
                                                 result.success)
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to save project: {e}"
            self.logger.error(error_msg)
            
            if QT_AVAILABLE:
                self.file_operation_completed.emit("save_project", 
                                                 str(file_path), 
                                                 False)
            
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=error_msg
            )
    
    @handle_errors("FileSystem", "load_project")
    def load_project(self, file_path: Union[str, Path]) -> FileOperationResult:
        """
        Load TECMP project file
        
        Args:
            file_path: Project file path
            
        Returns:
            FileOperationResult with project data
        """
        file_path = Path(file_path)
        
        if QT_AVAILABLE:
            self.file_operation_started.emit("load_project", str(file_path))
        
        try:
            # Check file exists
            if not file_path.exists():
                raise FileNotFoundError(f"Project file not found: {file_path}")
            
            # Detect if compressed
            compressed = self._is_compressed(file_path)
            
            # Read project file
            with open(file_path, 'rb') as f:
                if compressed:
                    with gzip.open(f, 'rb') as gz:
                        project = pickle.load(gz)
                else:
                    project = pickle.load(f)
            
            # Validate version
            if project.get('version') != self.TECMP_FILE_VERSION:
                self._handle_version_mismatch(project)
            
            # Extract data
            project_data = project.get('data', {})
            
            # Update tracking
            self._track_file(file_path, FileType.TECMP_PROJECT)
            self._add_recent_file(file_path)
            
            # Create metadata
            metadata = self._create_file_metadata(file_path, FileType.TECMP_PROJECT)
            
            self.logger.info(f"Project loaded: {file_path}")
            
            if QT_AVAILABLE:
                self.file_operation_completed.emit("load_project", 
                                                 str(file_path), 
                                                 True)
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                data=project_data,
                metadata=metadata
            )
            
        except Exception as e:
            error_msg = f"Failed to load project: {e}"
            self.logger.error(error_msg)
            
            if QT_AVAILABLE:
                self.file_operation_completed.emit("load_project", 
                                                 str(file_path), 
                                                 False)
            
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=error_msg
            )
    
    # ========================================================================
    # PCAP FILE OPERATIONS
    # ========================================================================
    
    @handle_errors("FileSystem", "save_pcap")
    def save_pcap(self, file_path: Union[str, Path], 
                  packets: List[Any],
                  pcapng: bool = False) -> FileOperationResult:
        """
        Save packets to PCAP/PCAPNG file
        
        Args:
            file_path: Target file path
            packets: List of packets to save
            pcapng: Use PCAPNG format
            
        Returns:
            FileOperationResult
        """
        if not SCAPY_AVAILABLE:
            return FileOperationResult(
                success=False,
                error="Scapy not available for PCAP operations"
            )
        
        file_path = Path(file_path)
        
        if QT_AVAILABLE:
            self.file_operation_started.emit("save_pcap", str(file_path))
        
        try:
            # Ensure correct extension
            if pcapng and not str(file_path).endswith('.pcapng'):
                file_path = file_path.with_suffix('.pcapng')
            elif not pcapng and not str(file_path).endswith('.pcap'):
                file_path = file_path.with_suffix('.pcap')
            
            # Convert TECMP packets to scapy format if needed
            scapy_packets = self._convert_to_scapy_packets(packets)
            
            # Save packets
            wrpcap(str(file_path), scapy_packets)
            
            # Update tracking
            file_type = FileType.PCAPNG if pcapng else FileType.PCAP
            self._track_file(file_path, file_type)
            
            # Create metadata
            metadata = self._create_file_metadata(file_path, file_type)
            
            self.logger.info(f"Saved {len(packets)} packets to {file_path}")
            
            if QT_AVAILABLE:
                self.file_operation_completed.emit("save_pcap", 
                                                 str(file_path), 
                                                 True)
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                metadata=metadata
            )
            
        except Exception as e:
            error_msg = f"Failed to save PCAP: {e}"
            self.logger.error(error_msg)
            
            if QT_AVAILABLE:
                self.file_operation_completed.emit("save_pcap", 
                                                 str(file_path), 
                                                 False)
            
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=error_msg
            )
    
    @handle_errors("FileSystem", "load_pcap")
    def load_pcap(self, file_path: Union[str, Path]) -> FileOperationResult:
        """
        Load packets from PCAP/PCAPNG file
        
        Args:
            file_path: PCAP file path
            
        Returns:
            FileOperationResult with packets
        """
        if not SCAPY_AVAILABLE:
            return FileOperationResult(
                success=False,
                error="Scapy not available for PCAP operations"
            )
        
        file_path = Path(file_path)
        
        if QT_AVAILABLE:
            self.file_operation_started.emit("load_pcap", str(file_path))
        
        try:
            # Load packets
            packets = rdpcap(str(file_path))
            
            # Convert to TECMP format if facade available
            if self.facade:
                tecmp_packets = self._convert_from_scapy_packets(packets)
            else:
                tecmp_packets = packets
            
            # Update tracking
            file_type = FileType.PCAPNG if str(file_path).endswith('.pcapng') else FileType.PCAP
            self._track_file(file_path, file_type)
            self._add_recent_file(file_path)
            
            # Create metadata
            metadata = self._create_file_metadata(file_path, file_type)
            
            self.logger.info(f"Loaded {len(packets)} packets from {file_path}")
            
            if QT_AVAILABLE:
                self.file_operation_completed.emit("load_pcap", 
                                                 str(file_path), 
                                                 True)
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                data=tecmp_packets,
                metadata=metadata
            )
            
        except Exception as e:
            error_msg = f"Failed to load PCAP: {e}"
            self.logger.error(error_msg)
            
            if QT_AVAILABLE:
                self.file_operation_completed.emit("load_pcap", 
                                                 str(file_path), 
                                                 False)
            
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=error_msg
            )
    
    # ========================================================================
    # CONFIGURATION FILE OPERATIONS
    # ========================================================================
    
    @handle_errors("FileSystem", "save_config")
    def save_config(self, file_path: Union[str, Path], 
                   config_data: Dict[str, Any],
                   format: str = "json") -> FileOperationResult:
        """
        Save configuration file
        
        Args:
            file_path: Target file path
            config_data: Configuration data
            format: File format (json/xml)
            
        Returns:
            FileOperationResult
        """
        file_path = Path(file_path)
        
        try:
            if format == "json":
                # Save as JSON
                result = self._atomic_write(
                    file_path,
                    lambda f: json.dump(config_data, f, indent=2),
                    binary=False
                )
                file_type = FileType.CONFIG_JSON
                
            elif format == "xml":
                # Save as XML (implement if needed)
                raise NotImplementedError("XML format not yet implemented")
                
            else:
                raise ValueError(f"Unsupported config format: {format}")
            
            if result.success:
                self._track_file(file_path, file_type)
                self._add_recent_file(file_path)
                
            return result
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    @handle_errors("FileSystem", "load_config")
    def load_config(self, file_path: Union[str, Path]) -> FileOperationResult:
        """
        Load configuration file
        
        Args:
            file_path: Configuration file path
            
        Returns:
            FileOperationResult with config data
        """
        file_path = Path(file_path)
        
        try:
            if file_path.suffix == '.json':
                with open(file_path, 'r') as f:
                    config_data = json.load(f)
                file_type = FileType.CONFIG_JSON
                
            elif file_path.suffix == '.xml':
                raise NotImplementedError("XML format not yet implemented")
                
            else:
                # Try to detect format
                with open(file_path, 'r') as f:
                    content = f.read()
                    try:
                        config_data = json.loads(content)
                        file_type = FileType.CONFIG_JSON
                    except:
                        raise ValueError("Unknown configuration format")
            
            self._track_file(file_path, file_type)
            self._add_recent_file(file_path)
            
            metadata = self._create_file_metadata(file_path, file_type)
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                data=config_data,
                metadata=metadata
            )
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    # ========================================================================
    # EXPORT OPERATIONS
    # ========================================================================
    
    @handle_errors("FileSystem", "export_packets")
    def export_packets(self, file_path: Union[str, Path],
                      packets: List[Any],
                      format: str = "csv",
                      options: Dict[str, Any] = None) -> FileOperationResult:
        """
        Export packets to various formats
        
        Args:
            file_path: Export file path
            packets: Packets to export
            format: Export format (csv/txt/bin)
            options: Export options
            
        Returns:
            FileOperationResult
        """
        file_path = Path(file_path)
        options = options or {}
        
        try:
            if format == "csv":
                result = self._export_to_csv(file_path, packets, options)
            elif format == "txt":
                result = self._export_to_txt(file_path, packets, options)
            elif format == "bin":
                result = self._export_to_binary(file_path, packets, options)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            if result.success:
                self._add_recent_file(file_path)
                self.logger.info(f"Exported {len(packets)} packets to {file_path}")
            
            return result
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    def _export_to_csv(self, file_path: Path, packets: List[Any],
                      options: Dict[str, Any]) -> FileOperationResult:
        """Export packets to CSV format"""
        import csv
        
        # Default CSV fields
        fields = options.get('fields', [
            'timestamp', 'device_id', 'interface_id',
            'data_type', 'length', 'payload_hex'
        ])
        
        try:
            with open(file_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                
                for packet in packets:
                    row = {}
                    for field in fields:
                        if hasattr(packet, field):
                            value = getattr(packet, field)
                            if field == 'payload' or field == 'payload_hex':
                                value = value.hex() if isinstance(value, bytes) else str(value)
                            row[field] = value
                        else:
                            row[field] = ''
                    writer.writerow(row)
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                metadata=self._create_file_metadata(file_path, FileType.EXPORT_CSV)
            )
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    def _export_to_txt(self, file_path: Path, packets: List[Any],
                      options: Dict[str, Any]) -> FileOperationResult:
        """Export packets to text format"""
        try:
            with open(file_path, 'w') as f:
                for i, packet in enumerate(packets):
                    f.write(f"=== Packet {i+1} ===\n")
                    f.write(str(packet))
                    f.write("\n\n")
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                metadata=self._create_file_metadata(file_path, FileType.EXPORT_TXT)
            )
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    def _export_to_binary(self, file_path: Path, packets: List[Any],
                         options: Dict[str, Any]) -> FileOperationResult:
        """Export packets to binary format"""
        try:
            with open(file_path, 'wb') as f:
                for packet in packets:
                    if hasattr(packet, 'to_bytes'):
                        f.write(packet.to_bytes())
                    elif hasattr(packet, 'payload'):
                        f.write(packet.payload)
                    else:
                        f.write(bytes(packet))
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                metadata=self._create_file_metadata(file_path, FileType.BINARY_DUMP)
            )
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================
    
    @handle_errors("FileSystem", "save_session")
    def save_session(self, file_path: Union[str, Path] = None) -> FileOperationResult:
        """
        Save current session
        
        Args:
            file_path: Session file path (auto-generated if None)
            
        Returns:
            FileOperationResult
        """
        if not self.facade:
            return FileOperationResult(
                success=False,
                error="No facade available for session save"
            )
        
        # Auto-generate session filename if not provided
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = self._get_session_directory() / f"session_{timestamp}.tss"
        else:
            file_path = Path(file_path)
        
        try:
            # Collect session data
            session_data = {
                'version': self.TECMP_FILE_VERSION,
                'timestamp': time.time(),
                'facade_state': self.facade.get_state() if hasattr(self.facade, 'get_state') else {},
                'open_files': list(self._open_files.keys()),
                'recent_files': [str(p) for p in self._recent_files],
                'undo_history': self._get_undo_history() if self.undo_controller else []
            }
            
            # Save session
            result = self._atomic_write(
                file_path,
                lambda f: pickle.dump(gzip.compress(pickle.dumps(session_data)), f),
                binary=True
            )
            
            if result.success:
                self.logger.info(f"Session saved: {file_path}")
            
            return result
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    @handle_errors("FileSystem", "load_session")
    def load_session(self, file_path: Union[str, Path]) -> FileOperationResult:
        """
        Load session
        
        Args:
            file_path: Session file path
            
        Returns:
            FileOperationResult with session data
        """
        file_path = Path(file_path)
        
        try:
            # Load session file
            with open(file_path, 'rb') as f:
                compressed_data = pickle.load(f)
                session_data = pickle.loads(gzip.decompress(compressed_data))
            
            # Validate version
            if session_data.get('version') != self.TECMP_FILE_VERSION:
                self.logger.warning("Session version mismatch")
            
            # Restore recent files
            self._recent_files = [Path(p) for p in session_data.get('recent_files', [])]
            
            return FileOperationResult(
                success=True,
                file_path=file_path,
                data=session_data
            )
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    # ========================================================================
    # AUTO-SAVE FUNCTIONALITY
    # ========================================================================
    
    def enable_auto_save_for_file(self, original_path: Union[str, Path]):
        """Enable auto-save for specific file"""
        original_path = Path(original_path)
        
        # Create auto-save path
        auto_save_path = self._get_auto_save_path(original_path)
        
        self._auto_save_files[str(original_path)] = auto_save_path
        self.logger.debug(f"Auto-save enabled for {original_path}")
    
    def disable_auto_save_for_file(self, original_path: Union[str, Path]):
        """Disable auto-save for specific file"""
        original_path = str(Path(original_path))
        
        if original_path in self._auto_save_files:
            # Remove auto-save file if exists
            auto_save_path = self._auto_save_files[original_path]
            if auto_save_path.exists():
                auto_save_path.unlink()
            
            del self._auto_save_files[original_path]
            self.logger.debug(f"Auto-save disabled for {original_path}")
    
    def _perform_auto_save(self):
        """Perform auto-save for all tracked files"""
        if not self.facade:
            return
        
        for original_path, auto_save_path in self._auto_save_files.items():
            try:
                # Get current data from facade
                if hasattr(self.facade, 'get_project_data'):
                    project_data = self.facade.get_project_data()
                    
                    # Save to auto-save file
                    self.save_project(auto_save_path, project_data, compress=True)
                    
                    if QT_AVAILABLE:
                        self.auto_save_triggered.emit(str(auto_save_path))
                    
                    self.logger.debug(f"Auto-saved to {auto_save_path}")
                    
            except Exception as e:
                self.logger.error(f"Auto-save failed for {original_path}: {e}")
    
    def recover_auto_save(self, original_path: Union[str, Path]) -> FileOperationResult:
        """Recover from auto-save file"""
        original_path = Path(original_path)
        auto_save_path = self._get_auto_save_path(original_path)
        
        if not auto_save_path.exists():
            return FileOperationResult(
                success=False,
                error="No auto-save file found"
            )
        
        try:
            # Load auto-save file
            result = self.load_project(auto_save_path)
            
            if result.success:
                # Copy auto-save to original
                shutil.copy2(auto_save_path, original_path)
                self.logger.info(f"Recovered from auto-save: {original_path}")
            
            return result
            
        except Exception as e:
            return FileOperationResult(
                success=False,
                error=str(e)
            )
    
    def _get_auto_save_path(self, original_path: Path) -> Path:
        """Get auto-save file path"""
        return self._temp_dir / f".{original_path.name}.autosave"
    
    # ========================================================================
    # FILE WATCHING
    # ========================================================================
    
    def watch_file(self, file_path: Union[str, Path]):
        """Start watching file for external changes"""
        file_path = Path(file_path)
        
        if file_path.exists():
            self._file_watchers[str(file_path)] = file_path.stat().st_mtime
            self.logger.debug(f"Watching file: {file_path}")
    
    def unwatch_file(self, file_path: Union[str, Path]):
        """Stop watching file"""
        file_path = str(Path(file_path))
        
        if file_path in self._file_watchers:
            del self._file_watchers[file_path]
            self.logger.debug(f"Stopped watching: {file_path}")
    
    def check_file_changes(self):
        """Check for external file changes"""
        for file_path, last_mtime in list(self._file_watchers.items()):
            try:
                path = Path(file_path)
                if path.exists():
                    current_mtime = path.stat().st_mtime
                    if current_mtime != last_mtime:
                        self._file_watchers[file_path] = current_mtime
                        
                        if QT_AVAILABLE:
                            self.file_changed_externally.emit(file_path)
                        
                        self.logger.info(f"External change detected: {file_path}")
            except Exception as e:
                self.logger.error(f"Error checking file changes: {e}")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _atomic_write(self, file_path: Path, write_func: Callable,
                     binary: bool = True) -> FileOperationResult:
        """Perform atomic file write operation"""
        temp_path = self._temp_dir / f"{file_path.name}.tmp"
        
        try:
            # Write to temporary file
            mode = 'wb' if binary else 'w'
            with open(temp_path, mode) as f:
                write_func(f)
            
            # Move to final location (atomic on most systems)
            shutil.move(str(temp_path), str(file_path))
            
            return FileOperationResult(
                success=True,
                file_path=file_path
            )
            
        except Exception as e:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
            
            return FileOperationResult(
                success=False,
                file_path=file_path,
                error=str(e)
            )
    
    def _track_file(self, file_path: Path, file_type: FileType):
        """Track opened file"""
        metadata = self._create_file_metadata(file_path, file_type)
        self._open_files[str(file_path)] = metadata
        
        # Create lock for file
        if str(file_path) not in self._file_locks:
            self._file_locks[str(file_path)] = threading.RLock()
    
    def _add_recent_file(self, file_path: Path):
        """Add file to recent files list"""
        # Remove if already in list
        if file_path in self._recent_files:
            self._recent_files.remove(file_path)
        
        # Add to front
        self._recent_files.insert(0, file_path)
        
        # Trim to max size
        self._recent_files = self._recent_files[:self._max_recent_files]
    
    def _create_file_metadata(self, file_path: Path, 
                            file_type: FileType) -> FileMetadata:
        """Create file metadata"""
        stat = file_path.stat()
        
        # Calculate checksum
        checksum = self._calculate_checksum(file_path)
        
        return FileMetadata(
            path=file_path,
            file_type=file_type,
            size=stat.st_size,
            created=stat.st_ctime,
            modified=stat.st_mtime,
            checksum=checksum,
            version=self.TECMP_FILE_VERSION if file_type == FileType.TECMP_PROJECT else None
        )
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate file checksum"""
        hash_md5 = hashlib.md5()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return ""
    
    def _is_compressed(self, file_path: Path) -> bool:
        """Check if file is compressed"""
        try:
            with open(file_path, 'rb') as f:
                # Check for gzip magic number
                return f.read(2) == b'\x1f\x8b'
        except:
            return False
    
    def _validate_project_data(self, project_data: Dict[str, Any]):
        """Validate project data structure"""
        required_keys = ['packets', 'configuration', 'metadata']
        
        for key in required_keys:
            if key not in project_data:
                self.logger.warning(f"Missing required key in project data: {key}")
    
    def _handle_version_mismatch(self, project: Dict[str, Any]):
        """Handle version mismatch in loaded project"""
        old_version = project.get('version', 'Unknown')
        self.logger.warning(f"Project version mismatch: {old_version} vs {self.TECMP_FILE_VERSION}")
        
        # Add migration logic here if needed
    
    def _write_project_file(self, file_obj, project: Dict[str, Any], 
                          compress: bool):
        """Write project data to file"""
        if compress:
            with gzip.open(file_obj, 'wb') as gz:
                pickle.dump(project, gz)
        else:
            pickle.dump(project, file_obj)
    
    def _convert_to_scapy_packets(self, packets: List[Any]) -> List[Any]:
        """Convert TECMP packets to scapy format"""
        if not packets:
            return []
        
        # If already scapy packets
        if hasattr(packets[0], 'show'):
            return packets
        
        # Convert TECMP to scapy
        scapy_packets = []
        for packet in packets:
            if hasattr(packet, 'to_scapy'):
                scapy_packets.append(packet.to_scapy())
            elif hasattr(packet, 'payload'):
                # Create raw packet
                from scapy.all import Raw
                scapy_packets.append(Raw(packet.payload))
            else:
                self.logger.warning(f"Cannot convert packet type: {type(packet)}")
        
        return scapy_packets
    
    def _convert_from_scapy_packets(self, packets: List[Any]) -> List[Any]:
        """Convert scapy packets to TECMP format"""
        if not self.facade:
            return packets
        
        tecmp_packets = []
        for packet in packets:
            try:
                # Use facade to create TECMP packet
                tecmp_packet = self.facade.create_tecmp_packet_from_scapy(packet)
                tecmp_packets.append(tecmp_packet)
            except:
                self.logger.warning(f"Failed to convert packet: {packet.summary()}")
        
        return tecmp_packets
    
    def _create_save_undo_command(self, file_path: Path, 
                                project_data: Dict[str, Any]):
        """Create undo command for save operation"""
        if not self.undo_controller:
            return
        
        # Store previous data if file existed
        previous_data = None
        if file_path.exists():
            result = self.load_project(file_path)
            if result.success:
                previous_data = result.data
        
        def undo():
            if previous_data:
                self.save_project(file_path, previous_data)
            elif file_path.exists():
                file_path.unlink()
        
        def redo():
            self.save_project(file_path, project_data)
        
        self.undo_controller.execute_command(
            command_type=CommandType.FILE_SAVE,
            description=f"Save project: {file_path.name}",
            do_func=lambda: None,  # Already done
            undo_func=undo
        )
    
    def _get_session_directory(self) -> Path:
        """Get session directory"""
        session_dir = self._temp_dir / "sessions"
        session_dir.mkdir(exist_ok=True)
        return session_dir
    
    def _get_undo_history(self) -> List[Dict[str, Any]]:
        """Get undo history for session"""
        if not self.undo_controller:
            return []
        
        return self.undo_controller.get_command_history(max_commands=50)
    
    # ========================================================================
    # PUBLIC API
    # ========================================================================
    
    def get_recent_files(self) -> List[str]:
        """Get list of recent files"""
        return [str(p) for p in self._recent_files if p.exists()]
    
    def get_open_files(self) -> Dict[str, FileMetadata]:
        """Get currently open files"""
        return self._open_files.copy()
    
    def close_file(self, file_path: Union[str, Path]):
        """Close file and clean up resources"""
        file_path = str(Path(file_path))
        
        # Remove from tracking
        if file_path in self._open_files:
            del self._open_files[file_path]
        
        # Remove lock
        if file_path in self._file_locks:
            del self._file_locks[file_path]
        
        # Stop watching
        self.unwatch_file(file_path)
        
        # Disable auto-save
        self.disable_auto_save_for_file(file_path)
        
        self.logger.debug(f"Closed file: {file_path}")
    
    def get_file_metadata(self, file_path: Union[str, Path]) -> Optional[FileMetadata]:
        """Get metadata for file"""
        file_path = str(Path(file_path))
        return self._open_files.get(file_path)
    
    def cleanup(self):
        """Clean up resources"""
        # Stop auto-save timer
        if self._auto_save_timer and QT_AVAILABLE:
            self._auto_save_timer.stop()
        
        # Remove auto-save files
        for auto_save_path in self._auto_save_files.values():
            if auto_save_path.exists():
                auto_save_path.unlink()
        
        # Clear temporary directory
        try:
            shutil.rmtree(self._temp_dir)
        except:
            pass
        
        self.logger.info("FileSystemController cleanup completed")

# ============================================================================
# FACADE INTEGRATION
# ============================================================================

def integrate_file_system_with_facade(facade):
    """
    Integrate file system controller with TECMP facade
    
    Args:
        facade: TECMP facade instance
        
    Returns:
        FileSystemController instance
    """
    # Create controller
    controller = FileSystemController(facade=facade)
    
    # Set as facade file system
    if hasattr(facade, 'file_system'):
        facade.file_system = controller
    
    # Connect signals if Qt available
    if QT_AVAILABLE and hasattr(facade, 'project_saved'):
        controller.file_operation_completed.connect(
            lambda op, path, success: 
            facade.project_saved.emit(path) if op == "save_project" and success else None
        )
    
    # Register with error handler
    if CONTROLLERS_AVAILABLE:
        error_handler = get_error_handler()
        error_handler.register_component_handler(
            "FileSystem",
            lambda e, ctx: FileOperationResult(success=False, error=str(e))
        )
    
    return controller

# Export public API
__all__ = [
    'FileSystemController',
    'FileType',
    'FileFormat',
    'FileMetadata',
    'FileOperationResult',
    'integrate_file_system_with_facade',
    'FILE_FORMATS'
]