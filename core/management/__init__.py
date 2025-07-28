#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Management Initialization for TECMP-Tool - Complete Version.

Provides init_management() for backend managers with Qt signals integration.
Role: File operations, packet management, resource handling with real-time coordination.
"""
import logging
import tempfile
import time
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path
from dataclasses import dataclass
from PyQt5.QtCore import QObject, pyqtSignal

# Component imports with proper error handling
_COMPONENT_STATUS = {
    "packet_manager": False,
    "pcap_generator": False,
    "resource_manager": False
}

try:
    from .packet_manager import PacketManager
    _COMPONENT_STATUS["packet_manager"] = True
except ImportError as e:
    PacketManager = None
    logging.debug(f"PacketManager import failed: {e}")
    
try:
    from .pcap_generator import PcapGenerator
    _COMPONENT_STATUS["pcap_generator"] = True
except ImportError as e:
    PcapGenerator = None
    logging.debug(f"PcapGenerator import failed: {e}")
    
try:
    from .resource_manager import ResourceManager
    _COMPONENT_STATUS["resource_manager"] = True
except ImportError as e:
    ResourceManager = None
    logging.debug(f"ResourceManager import failed: {e}")


# === CUSTOM EXCEPTIONS ===

class ComponentInitializationError(Exception):
    """Raised when a critical component fails to initialize."""
    pass


class InsufficientComponentsError(Exception):
    """Raised when too few components are available for operation."""
    pass


# === DATA STRUCTURES ===

@dataclass
class PcapMetadata:
    """Metadata for PCAP generation compatibility with preview systems."""
    file_size: int = 0
    packet_count: int = 0
    duration_ms: float = 0.0
    export_format: str = "pcap"
    protocol_stats: Dict[str, int] = None
    protocol_bytes: Dict[str, int] = None
    generation_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    export_path: str = ""
    
    def __post_init__(self):
        if self.protocol_stats is None:
            self.protocol_stats = {}
        if self.protocol_bytes is None:
            self.protocol_bytes = {}


@dataclass
class SessionInfo:
    """Information about a management session."""
    session_id: str
    created_at: float
    session_type: str
    config: Dict[str, Any]
    packets_managed: int = 0
    files_generated: int = 0
    resources_loaded: int = 0
    errors: int = 0


# === MANAGEMENT CONTAINER CLASS ===

class ManagementContainer(QObject):
    """
    Unified container for backend management operations with Qt signals.
    
    Role:
    - Packet collection management
    - PCAP file generation and export
    - Resource management (icons, templates)
    - Real-time metadata tracking
    - Qt signals for UI integration
    - Standardized API consistent with other containers
    """
    
    # === QT SIGNALS FOR REAL-TIME INTEGRATION ===
    packet_created = pyqtSignal(object)                    # New packet added
    packet_collection_changed = pyqtSignal(int)            # Collection size changed
    pcap_generation_started = pyqtSignal(str)              # Filename
    pcap_generation_progress = pyqtSignal(int)             # Progress percentage
    pcap_generation_completed = pyqtSignal(str, bool)      # Filepath, success
    metadata_updated = pyqtSignal(object)                  # PcapMetadata
    resource_loaded = pyqtSignal(str, str)                 # Resource type, name
    session_created = pyqtSignal(str)                      # Session ID
    session_ended = pyqtSignal(str, object)                # Session ID, stats
    error_occurred = pyqtSignal(str, str)                  # Component, error
    status_changed = pyqtSignal(str)                       # Global status
    
    def __init__(self, packet_manager=None, pcap_generator=None, resource_manager=None, 
                 config=None):
        """Initialize management container with Qt signals."""
        super().__init__()
        self.logger = logging.getLogger("TECMP-Tool.ManagementContainer")
        
        # Core managers
        self._packet_manager = packet_manager
        self._pcap_generator = pcap_generator
        self._resource_manager = resource_manager
        
        # Configuration reference
        self.config = config
        
        # Container state
        self._initialized = False
        self._temp_directory = None
        self._active_sessions: Dict[str, SessionInfo] = {}
        self._current_metadata = PcapMetadata()
        
        # Performance statistics
        self._stats = {
            "packets_managed": 0,
            "packets_exported": 0,
            "pcap_files_generated": 0,
            "resources_loaded": 0,
            "temp_files_created": 0,
            "sessions_created": 0,
            "errors": 0,
            "total_generation_time_ms": 0.0,
            "average_generation_time_ms": 0.0,
            "memory_usage_mb": 0.0,
            "last_file_size": 0,
            "last_export_path": ""
        }
        
        # Resource cache
        self._resource_cache = {}
        
        # Generation hooks for external monitoring
        self._generation_hooks = {
            "start": [],
            "progress": [],
            "complete": [],
            "error": []
        }
        
        self.logger.info("ManagementContainer with Qt signals initialized")
    
    # === PACKET MANAGEMENT METHODS ===
    
    def add_packet(self, packet: Any) -> bool:
        """
        Add packet to collection with real-time notification.
        
        Args:
            packet: Packet object to add
            
        Returns:
            bool: True if packet added successfully
        """
        try:
            if not self._packet_manager:
                self.error_occurred.emit("packet_manager", "PacketManager not available")
                return False
                
            # Add packet to manager
            self._packet_manager.add(packet)
            self._stats["packets_managed"] += 1
            
            # Emit signals
            self.packet_created.emit(packet)
            self.packet_collection_changed.emit(len(self._packet_manager))
            
            # Update metadata
            self._update_current_metadata()
            
            # Track in active sessions
            for session in self._active_sessions.values():
                if session.session_type in ["packet_management", "general"]:
                    session.packets_managed += 1
            
            self.logger.debug(f"Packet added to collection (total: {len(self._packet_manager)})")
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            self.logger.error(f"Error adding packet: {e}")
            self.error_occurred.emit("add_packet", str(e))
            return False
    
    def clear_packets(self) -> bool:
        """
        Clear all packets from collection.
        
        Returns:
            bool: True if packets cleared successfully
        """
        try:
            if not self._packet_manager:
                return False
                
            count = len(self._packet_manager)
            self._packet_manager.clear()
            
            # Emit signals
            self.packet_collection_changed.emit(0)
            self._update_current_metadata()
            
            self.logger.debug(f"Cleared {count} packets from collection")
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            self.logger.error(f"Error clearing packets: {e}")
            self.error_occurred.emit("clear_packets", str(e))
            return False
    
    def get_packets(self) -> List[Any]:
        """
        Get all packets from collection.
        
        Returns:
            List[Any]: List of packets
        """
        try:
            if not self._packet_manager:
                return []
                
            return self._packet_manager.get_packets()
            
        except Exception as e:
            self.logger.error(f"Error getting packets: {e}")
            return []
    
    def get_packet_count(self) -> int:
        """
        Get number of packets in collection.
        
        Returns:
            int: Number of packets
        """
        try:
            if not self._packet_manager:
                return 0
                
            return len(self._packet_manager)
            
        except Exception as e:
            self.logger.error(f"Error getting packet count: {e}")
            return 0
    
    # === PCAP GENERATION METHODS ===
    
    def generate_pcap(self, filename: str, packets: Optional[List[Any]] = None,
                     timestamps: Optional[List] = None, 
                     use_current_packets: bool = True) -> Optional[Path]:
        """
        Generate PCAP file with real-time progress signals.
        
        Args:
            filename: Output filename
            packets: Packets to export (None to use current collection)
            timestamps: Custom timestamps
            use_current_packets: Whether to use current packet collection
            
        Returns:
            Optional[Path]: Path to generated file or None if failed
        """
        try:
            if not self._pcap_generator:
                self.error_occurred.emit("pcap_generator", "PcapGenerator not available")
                return None
            
            # Determine packets to export
            if packets is None and use_current_packets:
                packets = self.get_packets()
            
            if not packets:
                self.logger.warning("No packets to export")
                return None
            
            # Start generation process
            self.pcap_generation_started.emit(filename)
            self._run_hooks("start", filename=filename, packet_count=len(packets))
            
            # Measure generation time
            start_time = time.time()
            
            # Progress simulation (if PcapGenerator doesn't provide real progress)
            self._simulate_progress()
            
            # Generate PCAP file
            pcap_path = self._pcap_generator.generate_pcap(filename, packets, timestamps)
            
            generation_time_ms = (time.time() - start_time) * 1000
            
            if pcap_path and pcap_path.exists():
                # Update statistics
                self._stats["pcap_files_generated"] += 1
                self._stats["packets_exported"] += len(packets)
                self._stats["total_generation_time_ms"] += generation_time_ms
                self._update_average_generation_time()
                self._stats["last_file_size"] = pcap_path.stat().st_size
                self._stats["last_export_path"] = str(pcap_path)
                
                # Update metadata
                self._update_current_metadata(
                    file_size=self._stats["last_file_size"],
                    packet_count=len(packets),
                    export_path=str(pcap_path),
                    generation_time_ms=generation_time_ms,
                    export_format="pcap"
                )
                
                # Track in sessions
                for session in self._active_sessions.values():
                    if session.session_type in ["pcap_generation", "general"]:
                        session.files_generated += 1
                
                # Emit completion signals
                self.pcap_generation_progress.emit(100)
                self.pcap_generation_completed.emit(str(pcap_path), True)
                self._run_hooks("complete", filepath=str(pcap_path), success=True)
                
                self.logger.info(f"PCAP generated: {pcap_path} ({len(packets)} packets, {generation_time_ms:.1f}ms)")
            else:
                self.pcap_generation_completed.emit("", False)
                self._run_hooks("error", error="Generation failed")
                
            return pcap_path
            
        except Exception as e:
            self._stats["errors"] += 1
            self.logger.error(f"Error generating PCAP: {e}")
            self.error_occurred.emit("generate_pcap", str(e))
            self.pcap_generation_completed.emit("", False)
            self._run_hooks("error", error=str(e))
            return None
    
    # === RESOURCE MANAGEMENT METHODS ===
    
    def get_icon(self, icon_name: str) -> Any:
        """
        Get icon resource with caching.
        
        Args:
            icon_name: Name of the icon
            
        Returns:
            Icon object or None if not found
        """
        try:
            if not self._resource_manager:
                return None
                
            # Check cache first
            cache_key = f"icon_{icon_name}"
            if cache_key in self._resource_cache:
                return self._resource_cache[cache_key]
                
            # Load icon
            icon = self._resource_manager.get_icon(icon_name)
            
            if icon:
                # Cache the icon
                self._resource_cache[cache_key] = icon
                self._stats["resources_loaded"] += 1
                
                # Track in sessions
                for session in self._active_sessions.values():
                    if session.session_type in ["resource_management", "general"]:
                        session.resources_loaded += 1
                
                # Emit signal
                self.resource_loaded.emit("icon", icon_name)
                
                self.logger.debug(f"Icon loaded: {icon_name}")
                
            return icon
            
        except Exception as e:
            self._stats["errors"] += 1
            self.logger.error(f"Error getting icon {icon_name}: {e}")
            self.error_occurred.emit("get_icon", str(e))
            return None
    
    # === SESSION MANAGEMENT ===
    
    def create_session(self, session_id: str, session_type: str = "general", 
                      **session_config) -> bool:
        """
        Create management session for tracking operations.
        
        Args:
            session_id: Unique session identifier
            session_type: Type of session (general, pcap_generation, etc.)
            **session_config: Session configuration
            
        Returns:
            bool: True if session created successfully
        """
        try:
            if session_id in self._active_sessions:
                self.logger.warning(f"Session {session_id} already exists")
                return False

            session = SessionInfo(
                session_id=session_id,
                created_at=time.time(),
                session_type=session_type,
                config=session_config
            )
            
            self._active_sessions[session_id] = session
            self._stats["sessions_created"] += 1
            
            # Emit signal
            self.session_created.emit(session_id)
            
            self.logger.debug(f"Management session created: {session_id} (type: {session_type})")
            return True

        except Exception as e:
            self.logger.error(f"Error creating session: {e}")
            return False

    def end_session(self, session_id: str) -> Dict[str, Any]:
        """
        End session and return statistics.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict: Session statistics
        """
        try:
            if session_id not in self._active_sessions:
                return {"error": "Session not found"}

            session = self._active_sessions.pop(session_id)
            duration = time.time() - session.created_at
            
            session_stats = {
                "session_id": session_id,
                "session_type": session.session_type,
                "duration_seconds": duration,
                "packets_managed": session.packets_managed,
                "files_generated": session.files_generated,
                "resources_loaded": session.resources_loaded,
                "errors": session.errors,
                "config": session.config
            }
            
            # Emit signal
            self.session_ended.emit(session_id, session_stats)
            
            self.logger.debug(f"Session ended: {session_id}")
            return session_stats

        except Exception as e:
            self.logger.error(f"Error ending session: {e}")
            return {"error": str(e)}

    # === METADATA AND MONITORING ===
    
    def get_current_metadata(self) -> PcapMetadata:
        """
        Get current metadata compatible with preview systems.
        
        Returns:
            PcapMetadata: Current metadata
        """
        return self._current_metadata
    
    def _update_current_metadata(self, **kwargs) -> None:
        """Update current metadata and emit signal."""
        try:
            # Update provided fields
            for key, value in kwargs.items():
                if hasattr(self._current_metadata, key):
                    setattr(self._current_metadata, key, value)
            
            # Update with current state
            self._current_metadata.packet_count = self.get_packet_count()
            
            # Emit signal
            self.metadata_updated.emit(self._current_metadata)
            
        except Exception as e:
            self.logger.error(f"Error updating metadata: {e}")
    
    # === UTILITY METHODS ===
    
    def setup_temporary_directory(self, temp_dir: Optional[str] = None) -> bool:
        """
        Setup temporary directory for operations.
        
        Args:
            temp_dir: Custom temporary directory path
            
        Returns:
            bool: True if setup successful
        """
        try:
            if temp_dir:
                self._temp_directory = Path(temp_dir)
                self._temp_directory.mkdir(parents=True, exist_ok=True)
            else:
                self._temp_directory = Path(tempfile.mkdtemp(prefix="tecmp_tool_"))
            
            self.logger.debug(f"Temporary directory setup: {self._temp_directory}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up temporary directory: {e}")
            return False
    
    def set_pcap_output_directory(self, output_dir: Union[str, Path]) -> bool:
        """
        Set PCAP output directory.
        
        Args:
            output_dir: Output directory path
            
        Returns:
            bool: True if set successfully
        """
        try:
            if not self._pcap_generator:
                return False
                
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            if hasattr(self._pcap_generator, 'set_output_directory'):
                self._pcap_generator.set_output_directory(output_path)
            
            self.logger.debug(f"PCAP output directory set: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting PCAP output directory: {e}")
            return False
    
    def _simulate_progress(self) -> None:
        """Simulate progress for operations without real progress tracking."""
        try:
            from PyQt5.QtCore import QTimer
            
            progress_timer = QTimer()
            progress_value = [0]
            
            def emit_progress():
                progress_value[0] += 20
                if progress_value[0] <= 80:  # Don't reach 100% in simulation
                    self.pcap_generation_progress.emit(progress_value[0])
                else:
                    progress_timer.stop()
            
            progress_timer.timeout.connect(emit_progress)
            progress_timer.start(100)  # Progress every 100ms
            
        except Exception as e:
            self.logger.debug(f"Progress simulation error: {e}")
    
    def _update_average_generation_time(self) -> None:
        """Update average generation time statistic."""
        if self._stats["pcap_files_generated"] > 0:
            self._stats["average_generation_time_ms"] = (
                self._stats["total_generation_time_ms"] / self._stats["pcap_files_generated"]
            )
    
    def _run_hooks(self, event_type: str, **kwargs) -> None:
        """Execute hooks for event type."""
        for callback in self._generation_hooks.get(event_type, []):
            try:
                callback(**kwargs)
            except Exception as e:
                self.logger.error(f"Error in {event_type} hook: {e}")
    
    # === STANDARDIZED API ===
    
    def validate(self) -> Dict[str, bool]:
        """
        Standardized API: Validate management system.
        
        Returns:
            Dict[str, bool]: Validation results
        """
        validation = {
            "management_container": True,
            "packet_manager": self._packet_manager is not None,
            "pcap_generator": self._pcap_generator is not None,
            "resource_manager": self._resource_manager is not None,
            "qt_signals": True,
            "temp_directory": True,
            "metadata_system": True
        }
        
        try:
            # Test managers
            if self._packet_manager:
                try:
                    validation["packet_manager"] = hasattr(self._packet_manager, 'add')
                except Exception:
                    validation["packet_manager"] = False
            
            if self._pcap_generator:
                try:
                    validation["pcap_generator"] = hasattr(self._pcap_generator, 'generate_pcap')
                except Exception:
                    validation["pcap_generator"] = False
            
            if self._resource_manager:
                try:
                    validation["resource_manager"] = hasattr(self._resource_manager, 'get_icon')
                except Exception:
                    validation["resource_manager"] = False
            
            # Test Qt signals
            try:
                self.status_changed.emit("validation_test")
                validation["qt_signals"] = True
            except Exception:
                validation["qt_signals"] = False
            
            # Test temporary directory
            if self._temp_directory:
                validation["temp_directory"] = self._temp_directory.exists()
            else:
                validation["temp_directory"] = False
            
            # Test metadata system
            try:
                metadata = self.get_current_metadata()
                validation["metadata_system"] = isinstance(metadata, PcapMetadata)
            except Exception:
                validation["metadata_system"] = False
            
        except Exception as e:
            self.logger.error(f"Error during validation: {e}")
            validation["error"] = str(e)
        
        return validation

    def get_metrics(self) -> Dict[str, Any]:
        """
        Standardized API: Get management performance metrics.
        
        Returns:
            Dict[str, Any]: Performance metrics
        """
        try:
            return {
                "statistics": self._stats.copy(),
                "performance": {
                    "average_generation_time_ms": self._stats["average_generation_time_ms"],
                    "memory_usage_mb": self._calculate_memory_usage(),
                    "resource_cache_size": len(self._resource_cache),
                    "packets_per_export": (
                        self._stats["packets_exported"] / max(1, self._stats["pcap_files_generated"])
                    )
                },
                "sessions": {
                    "active_sessions": len(self._active_sessions),
                    "session_types": [s.session_type for s in self._active_sessions.values()],
                    "total_sessions_created": self._stats["sessions_created"]
                },
                "metadata": {
                    "current_packet_count": self._current_metadata.packet_count,
                    "last_export_format": self._current_metadata.export_format,
                    "last_file_size": self._current_metadata.file_size,
                    "protocols_tracked": len(self._current_metadata.protocol_stats)
                },
                "components": {
                    "packet_manager_available": self._packet_manager is not None,
                    "pcap_generator_available": self._pcap_generator is not None,
                    "resource_manager_available": self._resource_manager is not None,
                    "temp_directory_available": self._temp_directory is not None
                }
            }
        except Exception as e:
            return {"error": str(e)}

    def cleanup(self) -> bool:
        """
        Standardized API: Clean up management container.
        
        Returns:
            bool: True if cleanup successful
        """
        try:
            # Log final metrics
            final_metrics = self.get_metrics()
            self.logger.info(f"ManagementContainer final metrics: {final_metrics['statistics']}")
            
            # End all active sessions
            cleanup_results = []
            for session_id in list(self._active_sessions.keys()):
                try:
                    session_stats = self.end_session(session_id)
                    cleanup_results.append(f"session_{session_id}: OK")
                except Exception as e:
                    cleanup_results.append(f"session_{session_id}: ERROR - {e}")
            
            # Clear resource cache
            self._resource_cache.clear()
            cleanup_results.append("resource_cache: OK")
            
            # Clear generation hooks
            for hook_type in self._generation_hooks:
                self._generation_hooks[hook_type].clear()
            cleanup_results.append("generation_hooks: OK")
            
            # Clean up temporary directory
            if self._temp_directory and self._temp_directory.exists():
                try:
                    import shutil
                    shutil.rmtree(self._temp_directory)
                    cleanup_results.append("temp_directory: OK")
                except Exception as e:
                    cleanup_results.append(f"temp_directory: ERROR - {e}")
            
            self.logger.info(f"Cleanup results: {cleanup_results}")
            return all("ERROR" not in result for result in cleanup_results)
            
        except Exception as e:
            self.logger.error(f"Error during management cleanup: {e}")
            return False
    
    def _calculate_memory_usage(self) -> float:
        """Calculate current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    # === PROPERTIES FOR EXTERNAL ACCESS ===
    
    @property
    def packet_manager(self):
        """Get packet manager instance."""
        return self._packet_manager

    @property
    def pcap_generator(self):
        """Get PCAP generator instance."""
        return self._pcap_generator

    @property
    def resource_manager(self):
        """Get resource manager instance."""
        return self._resource_manager

    @property
    def is_ready(self) -> bool:
        """Check if management container is ready for operations."""
        return any([
            self._packet_manager is not None,
            self._pcap_generator is not None,
            self._resource_manager is not None
        ])


# === MAIN INITIALIZATION FUNCTION ===

def init_management(config: Any, facade: Optional[Any] = None, 
                   require_all_components: bool = False,
                   minimum_components: int = 1) -> ManagementContainer:
    """
    Initialize the management system with improved error handling and validation.
    
    This function creates and configures the management container that handles:
    - Packet collection management
    - PCAP file generation and export  
    - Resource management (icons, templates)
    - Real-time Qt signals for UI integration
    
    Args:
        config: Configuration object from init_config()
        facade: Optional facade object for system integration
        require_all_components: If True, all components must initialize successfully
        minimum_components: Minimum number of components required (default: 1)
        
    Returns:
        ManagementContainer: Fully initialized container with available components
        
    Raises:
        ValueError: If configuration is invalid
        InsufficientComponentsError: If minimum component requirement not met
        ComponentInitializationError: If critical initialization fails
        
    Example:
        >>> config = init_config()
        >>> management = init_management(config)
        >>> 
        >>> # Check component availability
        >>> if management.packet_manager:
        >>>     management.add_packet(packet)
        >>> 
        >>> # Generate PCAP with error handling
        >>> if management.pcap_generator:
        >>>     pcap_path = management.generate_pcap("output.pcap")
    """
    logger = logging.getLogger("TECMP-Tool.init_management")
    
    # Validate prerequisites
    if not config:
        raise ValueError("Configuration object is required for initialization")
    
    try:
        logger.info("Initializing management system with Qt signal integration")
        
        # Extract configuration parameters
        mode = getattr(config, 'mode', 'production')
        management_config = getattr(config, 'management_config', {})
        
        logger.debug(f"Initialization mode: {mode}")
        logger.debug(f"Component availability: {_COMPONENT_STATUS}")
        
        # Build comprehensive configuration
        default_config = _build_default_configuration(mode, management_config)
        
        # Initialize components with proper error handling
        components = _initialize_components(management_config, default_config, logger)
        
        # Validate component initialization
        _validate_component_initialization(
            components, 
            require_all_components, 
            minimum_components,
            logger
        )
        
        # Create the management container
        container = _create_management_container(components, config, logger)
        
        # Configure the container based on mode
        _configure_container(container, mode, default_config, logger)
        
        # Integrate with facade if provided
        if facade:
            _integrate_with_facade(container, facade, logger)
        
        # Perform final validation and health check
        _perform_health_check(container, logger)
        
        logger.info("Management system initialization completed successfully")
        return container
        
    except Exception as e:
        logger.error(f"Failed to initialize management system: {e}")
        raise


def _build_default_configuration(mode: str, management_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the default configuration based on mode and user config.
    
    Args:
        mode: Operation mode (production, dev, lite)
        management_config: User-provided configuration
        
    Returns:
        Dict containing merged configuration
    """
    return {
        "enable_caching": mode in ["production", "dev"],
        "temp_directory": management_config.get("temp_directory"),
        "pcap_output_dir": management_config.get("pcap_output_dir"),
        "resource_paths": management_config.get("resource_paths", {}),
        "max_cache_size": 100 if mode == "lite" else 500,
        "enable_statistics": True,
        "auto_cleanup": mode != "dev",
        "enable_qt_signals": True,
        "preview_integration": True,
        "snaplen": management_config.get("snaplen", 65535),
        "network_type": management_config.get("network_type", 1)  # 1 = Ethernet
    }


def _initialize_components(management_config: Dict[str, Any], 
                          default_config: Dict[str, Any],
                          logger: logging.Logger) -> Dict[str, Optional[Any]]:
    """
    Initialize all available components with proper error handling.
    
    Args:
        management_config: User configuration
        default_config: Default configuration
        logger: Logger instance
        
    Returns:
        Dict mapping component names to initialized instances (or None)
    """
    components = {
        "packet_manager": None,
        "pcap_generator": None,
        "resource_manager": None
    }
    
    # Initialize PacketManager
    if PacketManager is not None:
        try:
            components["packet_manager"] = PacketManager()
            logger.debug("? PacketManager initialized successfully")
        except Exception as e:
            logger.warning(f"? PacketManager initialization failed: {e}")
    else:
        logger.warning("? PacketManager class not available for import")
    
    # Initialize PcapGenerator with configuration
    if PcapGenerator is not None:
        try:
            output_dir = default_config.get("pcap_output_dir")
            snaplen = default_config.get("snaplen", 65535)
            network = default_config.get("network_type", 1)
            
            components["pcap_generator"] = PcapGenerator(
                output_directory=output_dir,
                snaplen=snaplen,
                network=network
            )
            logger.debug("? PcapGenerator initialized successfully")
        except Exception as e:
            logger.warning(f"? PcapGenerator initialization failed: {e}")
    else:
        logger.warning("? PcapGenerator class not available for import")
    
    # Initialize ResourceManager
    if ResourceManager is not None:
        try:
            components["resource_manager"] = ResourceManager()
            logger.debug("? ResourceManager initialized successfully")
        except Exception as e:
            logger.warning(f"? ResourceManager initialization failed: {e}")
    else:
        logger.warning("? ResourceManager class not available for import")
    
    return components


def _validate_component_initialization(components: Dict[str, Optional[Any]],
                                     require_all: bool,
                                     minimum_required: int,
                                     logger: logging.Logger) -> None:
    """
    Validate that component initialization meets requirements.
    
    Args:
        components: Dictionary of initialized components
        require_all: Whether all components are required
        minimum_required: Minimum number of components needed
        logger: Logger instance
        
    Raises:
        InsufficientComponentsError: If requirements not met
    """
    available_components = [name for name, instance in components.items() if instance is not None]
    unavailable_components = [name for name, instance in components.items() if instance is None]
    
    available_count = len(available_components)
    
    if require_all and unavailable_components:
        raise InsufficientComponentsError(
            f"All components required but these failed: {unavailable_components}"
        )
    
    if available_count < minimum_required:
        raise InsufficientComponentsError(
            f"Minimum {minimum_required} components required but only {available_count} available. "
            f"Available: {available_components}, Missing: {unavailable_components}"
        )
    
    if available_components:
        logger.info(f"? Available components: {available_components}")
    
    if unavailable_components:
        logger.warning(f"? Unavailable components: {unavailable_components}")


def _create_management_container(components: Dict[str, Optional[Any]],
                               config: Any,
                               logger: logging.Logger) -> ManagementContainer:
    """
    Create and return the management container.
    
    Args:
        components: Dictionary of initialized components
        config: Configuration object
        logger: Logger instance
        
    Returns:
        ManagementContainer instance
        
    Raises:
        ComponentInitializationError: If container creation fails
    """
    try:
        container = ManagementContainer(
            packet_manager=components["packet_manager"],
            pcap_generator=components["pcap_generator"],
            resource_manager=components["resource_manager"],
            config=config
        )
        
        logger.debug("Management container created successfully")
        return container
        
    except Exception as e:
        raise ComponentInitializationError(f"Failed to create management container: {e}")


def _configure_container(container: ManagementContainer,
                        mode: str,
                        default_config: Dict[str, Any],
                        logger: logging.Logger) -> None:
    """
    Configure the container based on mode and settings.
    
    Args:
        container: Management container to configure
        mode: Operation mode
        default_config: Configuration dictionary
        logger: Logger instance
    """
    # Set up temporary directory
    if default_config.get("temp_directory"):
        container.setup_temporary_directory(default_config["temp_directory"])
    elif default_config.get("auto_cleanup"):
        container.setup_temporary_directory()  # Auto-create temp directory
    
    # Set up PCAP output directory
    if container.pcap_generator and default_config.get("pcap_output_dir"):
        container.set_pcap_output_directory(default_config["pcap_output_dir"])
    
    # Configure mode-specific settings
    if mode == "dev":
        _configure_development_mode(container, logger)
    elif mode == "lite":
        _configure_lite_mode(container, logger)
    elif mode == "production":
        _configure_production_mode(container, logger)
    
    # Initialize metadata for preview integration
    if default_config.get("preview_integration"):
        container._update_current_metadata(
            export_format="pcap",
            packet_count=0,
            file_size=0
        )
        logger.debug("Preview integration configured")


def _configure_development_mode(container: ManagementContainer, logger: logging.Logger) -> None:
    """Configure container for development mode with verbose debugging."""
    container.create_session(
        "dev_session",
        session_type="development",
        debug=True,
        signals_verbose=True
    )
    
    # Connect verbose logging to signals
    container.status_changed.connect(
        lambda status: logger.debug(f"?? DEV STATUS: {status}")
    )
    container.error_occurred.connect(
        lambda comp, err: logger.debug(f"?? DEV ERROR: {comp} - {err}")
    )
    
    logger.debug("?? Development mode configured with verbose signals")


def _configure_lite_mode(container: ManagementContainer, logger: logging.Logger) -> None:
    """Configure container for lite mode with minimal overhead."""
    container.create_session(
        "lite_session",
        session_type="lite",
        minimal_stats=True
    )
    logger.debug("?? Lite mode configured with minimal overhead")


def _configure_production_mode(container: ManagementContainer, logger: logging.Logger) -> None:
    """Configure container for production mode with monitoring."""
    container.create_session(
        "prod_session",
        session_type="production",
        enable_monitoring=True
    )
    
    # Set up default output directory for production
    if container.pcap_generator:
        default_output = Path.home() / "Documents" / "TECMP-Tool" / "exports"
        container.set_pcap_output_directory(default_output)
    
    logger.debug("?? Production mode configured with monitoring")


def _integrate_with_facade(container: ManagementContainer, 
                          facade: Any,
                          logger: logging.Logger) -> None:
    """
    Integrate the container with the system facade.
    
    Args:
        container: Management container
        facade: Facade object
        logger: Logger instance
    """
    try:
        if hasattr(facade, '_management_ref'):
            facade._management_ref = container
            logger.debug("? Management integrated with facade")
        else:
            logger.warning("? Facade does not support management integration")
    except Exception as e:
        logger.warning(f"? Error integrating with facade: {e}")


def _perform_health_check(container: ManagementContainer, 
                         logger: logging.Logger) -> None:
    """
    Perform final health check and validation.
    
    Args:
        container: Management container
        logger: Logger instance
    """
    try:
        # Run validation
        validation_results = container.validate()
        
        # Get metrics
        metrics = container.get_metrics()
        component_count = sum([
            metrics["components"]["packet_manager_available"],
            metrics["components"]["pcap_generator_available"],
            metrics["components"]["resource_manager_available"]
        ])
        
        logger.info(f"?? Management system: {component_count}/3 core components available")
        
        # Emit ready signal if applicable
        if container.is_ready:
            container.status_changed.emit("Management system ready")
            logger.debug("? Management system health check passed")
        else:
            logger.warning("? Management system has limited functionality")
            
    except Exception as e:
        logger.warning(f"? Health check encountered error: {e}")


# === UTILITY FUNCTIONS ===

def create_test_management(mode="dev") -> ManagementContainer:
    """Create test management container."""
    class MockConfig:
        def __init__(self):
            self.mode = mode
            self.management_config = {
                "temp_directory": None,
                "pcap_output_dir": None,
                "snaplen": 65535,
                "network_type": 1
            }
    
    return init_management(MockConfig())


# === CONSTANTS ===

SESSION_TYPES = [
    "general",              # General purpose session
    "pcap_generation",      # PCAP export focused session
    "resource_management",  # Resource loading focused session
    "development",          # Development and debugging session
    "production",          # Production optimized session
    "lite"                 # Lightweight session
]

MODE_MANAGEMENT_CONFIG = {
    "production": {
        "enable_caching": True,
        "max_cache_size": 500,
        "enable_statistics": True,
        "auto_cleanup": True,
        "session_type": "production"
    },
    "dev": {
        "enable_caching": True,
        "max_cache_size": 1000,
        "enable_statistics": True,
        "auto_cleanup": False,
        "session_type": "development"
    },
    "lite": {
        "enable_caching": False,
        "max_cache_size": 50,
        "enable_statistics": False,
        "auto_cleanup": True,
        "session_type": "lite"
    }
}


# === EXPORTS ===
__all__ = [
    "ManagementContainer",
    "PcapMetadata",
    "SessionInfo",
    "init_management",
    "create_test_management",
    "SESSION_TYPES",
    "MODE_MANAGEMENT_CONFIG",
    "ComponentInitializationError",
    "InsufficientComponentsError"
]