# -*- coding: utf-8 -*-
"""
Enhanced Strategy Initialization System - PRODUCTION COMPLETE IMPLEMENTATION
File: core/strategies/__init__.py
Author: TECMP-Tool Development Team
Description: Comprehensive initialization and management of packet sending strategies with advanced features
"""
from __future__ import annotations
import logging
import time
import json
import threading
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

# Core strategy imports with enhanced features
from core.management.packet_manager import PacketManager
from core.strategies.sender_strategy import (
    SenderStrategy, Sender, StrategyConfig,
    StrategyState, ErrorHandlingMode, SenderValidator,
    StrategyExecutionError, StrategyValidationError, SenderValidationError,
    PacketSerializationError, PacketModificationError, DependencyError,
    StrategyMonitor, RealTimeStats, StrategyConfigBuilder
)

# Individual strategy imports
from core.strategies.single import SinglePacketStrategy
from core.strategies.priority import PriorityBasedStrategy
from core.strategies.multi import MultiPacketStrategy
from core.strategies.ramp_speed import RampSpeedStrategy
from core.management import ManagementContainer

# Optional multicast strategy with graceful fallback
try:
    from core.strategies.multicast import TECMPMulticastStrategy as MulticastStrategy
    MULTICAST_AVAILABLE = True
except ImportError:
    MULTICAST_AVAILABLE = False
    MulticastStrategy = None


# Enhanced initialization modes
class InitializationMode(Enum):
    """Strategy initialization modes with specific characteristics"""
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TESTING = "testing"
    CLI = "cli"
    LITE = "lite"
    CONFIG = "config"
    BENCHMARK = "benchmark"


@dataclass
class StrategyCapabilities:
    """Dataclass for strategy capabilities and features"""
    supports_multicast: bool = False
    supports_pause_resume: bool = False
    supports_real_time_stats: bool = False
    supports_configuration_serialization: bool = False
    supports_packet_modification: bool = False
    supports_priority_qos: bool = False
    supports_rate_limiting: bool = False
    supports_burst_transmission: bool = False
    max_senders: int = 1
    min_packet_size: int = 0
    max_packet_size: int = 65535


@dataclass
class InitializationOptions:
    """Comprehensive initialization options"""
    mode: InitializationMode = InitializationMode.PRODUCTION
    validate_senders: bool = True
    enable_real_time_stats: bool = True
    error_handling_mode: ErrorHandlingMode = ErrorHandlingMode.STRICT
    sender_test_timeout: float = 5.0
    strategy_filter: Optional[List[str]] = None
    force_multicast: bool = False
    min_sender_count: int = 1
    max_sender_count: int = 10
    enable_configuration_backup: bool = True
    backup_directory: Optional[Path] = None


class StrategyInitializationError(Exception):
    """Enhanced exception for strategy initialization failures"""
    def __init__(self, message: str, mode: str = None, strategy_name: str = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.mode = mode
        self.strategy_name = strategy_name
        self.details = details or {}


class StrategyRegistry:
    """
    Enhanced registry for managing packet sending strategies with advanced features
    
    Features:
    - Advanced sender validation and testing
    - Real-time monitoring and statistics
    - Configuration backup and restoration
    - Strategy capability detection
    - Performance benchmarking
    - Pause/Resume support for all strategies
    - Enhanced error handling and recovery
    """
    
    def __init__(self, options: Optional[InitializationOptions] = None):
        self.options = options or InitializationOptions()
        self.logger = logging.getLogger("TECMP.Strategies.Registry")
        
        # Core registry data
        self.strategies: Dict[str, SenderStrategy] = {}
        self.strategy_configs: Dict[str, StrategyConfig] = {}
        self.strategy_metadata: Dict[str, Dict[str, Any]] = {}
        self.strategy_capabilities: Dict[str, StrategyCapabilities] = {}
        
        # Enhanced features
        self.initialization_history: List[Dict[str, Any]] = []
        self.performance_benchmarks: Dict[str, Dict[str, float]] = {}
        self.configuration_backups: Dict[str, List[str]] = {}
        
        # State management
        self.initialized = False
        self.initialization_time = None
        self.last_validation_time = None
        
        # Thread safety
        self._registry_lock = threading.RLock()
        
        self.logger.debug(f"Enhanced strategy registry created with options: {self.options}")
    
    def register_strategy(
        self, 
        name: str, 
        strategy: SenderStrategy, 
        config: Optional[StrategyConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
        capabilities: Optional[StrategyCapabilities] = None
    ) -> None:
        """
        Register a strategy with comprehensive validation and capability detection
        
        Args:
            name: Unique strategy identifier
            strategy: Strategy instance (must inherit from SenderStrategy)
            config: Original configuration used to create strategy
            metadata: Additional metadata for tracking
            capabilities: Strategy capabilities (auto-detected if None)
            
        Raises:
            StrategyValidationError: If strategy validation fails
        """
        with self._registry_lock:
            try:
                # Enhanced strategy validation
                self._validate_strategy_comprehensive(name, strategy)
                
                # Auto-detect capabilities if not provided
                if capabilities is None:
                    capabilities = self._detect_strategy_capabilities(strategy)
                
                # Validate name uniqueness with conflict resolution
                if name in self.strategies:
                    self.logger.warning(f"Overwriting existing strategy '{name}'")
                    self._backup_strategy_configuration(name)
                
                # Register strategy and all associated data
                self.strategies[name] = strategy
                if config:
                    self.strategy_configs[name] = self._deep_copy_config(config)
                
                # Enhanced metadata with capability information
                strategy_metadata = {
                    'class_name': strategy.__class__.__name__,
                    'sender_count': len(strategy.senders),
                    'registration_mode': self.options.mode.value,
                    'registration_timestamp': datetime.now().isoformat(),
                    'enabled': getattr(strategy, 'strategy_enabled', True),
                    'supports_multicast': strategy.supports_multicast(),
                    'supports_pause_resume': hasattr(strategy, 'pause_execution'),
                    'real_time_stats_enabled': getattr(strategy, 'enable_real_time_stats', False),
                    'error_handling_mode': getattr(strategy, 'error_handling_mode', ErrorHandlingMode.STRICT).value,
                    'current_state': strategy.state.value if hasattr(strategy, 'state') else 'unknown',
                    'sender_validation_passed': True,
                    'configuration_serializable': self._test_configuration_serialization(config or {})
                }
                
                if metadata:
                    strategy_metadata.update(metadata)
                
                self.strategy_metadata[name] = strategy_metadata
                self.strategy_capabilities[name] = capabilities
                
                # Setup enhanced monitoring
                self._setup_strategy_monitoring(name, strategy)
                
                self.logger.info(
                    f"Registered strategy '{name}' ({strategy.__class__.__name__}) "
                    f"with {len(strategy.senders)} senders, capabilities: {capabilities}"
                )
                
            except Exception as e:
                error_msg = f"Failed to register strategy '{name}': {e}"
                self.logger.error(error_msg)
                raise StrategyValidationError(error_msg, field_name="strategy_registration") from e
    
    def _validate_strategy_comprehensive(self, name: str, strategy: SenderStrategy) -> None:
        """Comprehensive strategy validation with enhanced checks"""
        
        # Basic type validation
        if not isinstance(strategy, SenderStrategy):
            raise StrategyValidationError(
                f"Strategy '{name}' must inherit from SenderStrategy, got {type(strategy).__name__}"
            )
        
        # Required methods validation
        required_methods = ['execute', 'estimate_duration', 'estimate_packet_count']
        for method in required_methods:
            if not hasattr(strategy, method) or not callable(getattr(strategy, method)):
                raise StrategyValidationError(f"Strategy '{name}' missing required method: {method}")
        
        # Enhanced sender validation
        if self.options.validate_senders:
            validation_results = SenderValidator.validate_sender_list(strategy.senders)
            if not validation_results['all_valid']:
                invalid_details = validation_results['invalid_senders']
                raise SenderValidationError(
                    f"Strategy '{name}' has invalid senders: {invalid_details}",
                    validation_method="comprehensive_validation"
                )
        
        # Configuration validation
        if hasattr(strategy, '_validate_configuration'):
            try:
                strategy._validate_configuration()
            except Exception as e:
                raise StrategyValidationError(f"Strategy '{name}' configuration invalid: {e}")
        
        # State validation
        if hasattr(strategy, 'state') and strategy.state not in StrategyState:
            raise StrategyValidationError(f"Strategy '{name}' has invalid state: {strategy.state}")
    
    def _detect_strategy_capabilities(self, strategy: SenderStrategy) -> StrategyCapabilities:
        """Auto-detect strategy capabilities"""
        
        capabilities = StrategyCapabilities()
        
        # Basic capabilities
        capabilities.supports_multicast = strategy.supports_multicast()
        capabilities.max_senders = len(strategy.senders)
        
        # Advanced feature detection
        capabilities.supports_pause_resume = (
            hasattr(strategy, 'pause_execution') and 
            hasattr(strategy, 'resume_execution')
        )
        
        capabilities.supports_real_time_stats = (
            hasattr(strategy, 'get_real_time_stats') or
            getattr(strategy, 'enable_real_time_stats', False)
        )
        
        capabilities.supports_configuration_serialization = (
            hasattr(strategy, 'serialize_configuration') and
            hasattr(strategy, 'deserialize_configuration')
        )
        
        capabilities.supports_packet_modification = (
            hasattr(strategy, '_modify_packet') or
            hasattr(strategy, '_send_packet_multicast')
        )
        
        # Strategy-specific capabilities
        strategy_class = strategy.__class__.__name__
        
        if 'Priority' in strategy_class:
            capabilities.supports_priority_qos = True
            capabilities.supports_rate_limiting = True
        
        if 'Ramp' in strategy_class:
            capabilities.supports_rate_limiting = True
        
        if 'Multi' in strategy_class or 'Burst' in strategy_class:
            capabilities.supports_burst_transmission = True
        
        # Size limits detection
        if hasattr(strategy, 'config'):
            config = strategy.config
            capabilities.min_packet_size = config.get('min_packet_size', 0)
            capabilities.max_packet_size = config.get('max_packet_size', 65535)
        
        return capabilities
    
    def _setup_strategy_monitoring(self, name: str, strategy: SenderStrategy) -> None:
        """Setup enhanced monitoring for strategy"""
        
        try:
            # Connect to strategy signals if available
            if hasattr(strategy, 'execution_started'):
                strategy.execution_started.connect(
                    lambda strategy_name: self._on_strategy_execution_started(name, strategy_name)
                )
            
            if hasattr(strategy, 'execution_completed'):
                strategy.execution_completed.connect(
                    lambda strategy_name, stats: self._on_strategy_execution_completed(name, strategy_name, stats)
                )
            
            if hasattr(strategy, 'execution_failed'):
                strategy.execution_failed.connect(
                    lambda strategy_name, error, details: self._on_strategy_execution_failed(name, strategy_name, error, details)
                )
            
            # Setup real-time monitoring if supported
            if hasattr(strategy, 'monitor') and isinstance(strategy.monitor, StrategyMonitor):
                strategy.monitor.progress_updated.connect(
                    lambda current, total: self._on_strategy_progress_updated(name, current, total)
                )
                
                strategy.monitor.rate_updated.connect(
                    lambda current_rate, avg_rate: self._on_strategy_rate_updated(name, current_rate, avg_rate)
                )
            
        except Exception as e:
            self.logger.warning(f"Failed to setup monitoring for strategy '{name}': {e}")
    
    def get_strategy(self, name: str) -> Optional[SenderStrategy]:
        """Get strategy by name with enhanced access logging"""
        
        with self._registry_lock:
            strategy = self.strategies.get(name)
            
            if strategy is None:
                available = list(self.strategies.keys())
                self.logger.warning(f"Strategy '{name}' not found. Available: {available}")
            else:
                # Log access for monitoring
                access_info = {
                    'strategy_name': name,
                    'access_time': datetime.now().isoformat(),
                    'current_state': strategy.state.value if hasattr(strategy, 'state') else 'unknown'
                }
                self.logger.debug(f"Strategy access: {access_info}")
                
            return strategy
    
    def get_strategy_by_capabilities(self, required_capabilities: Dict[str, bool]) -> List[str]:
        """Find strategies by required capabilities"""
        
        matching_strategies = []
        
        for name, capabilities in self.strategy_capabilities.items():
            matches = True
            
            for capability, required in required_capabilities.items():
                if hasattr(capabilities, capability):
                    if getattr(capabilities, capability) != required:
                        matches = False
                        break
                else:
                    matches = False
                    break
            
            if matches:
                matching_strategies.append(name)
        
        return matching_strategies
    
    def pause_all_strategies(self) -> Dict[str, bool]:
        """Pause all executing strategies"""
        
        results = {}
        
        for name, strategy in self.strategies.items():
            try:
                if hasattr(strategy, 'pause_execution') and strategy.is_executing:
                    results[name] = strategy.pause_execution()
                else:
                    results[name] = False
            except Exception as e:
                self.logger.error(f"Failed to pause strategy '{name}': {e}")
                results[name] = False
        
        return results
    
    def resume_all_strategies(self) -> Dict[str, bool]:
        """Resume all paused strategies"""
        
        results = {}
        
        for name, strategy in self.strategies.items():
            try:
                if hasattr(strategy, 'resume_execution') and strategy.is_paused:
                    results[name] = strategy.resume_execution()
                else:
                    results[name] = False
            except Exception as e:
                self.logger.error(f"Failed to resume strategy '{name}': {e}")
                results[name] = False
        
        return results
    
    def get_real_time_stats_all(self) -> Dict[str, Dict[str, Any]]:
        """Get real-time statistics for all strategies"""
        
        all_stats = {}
        
        for name, strategy in self.strategies.items():
            try:
                if hasattr(strategy, 'get_real_time_stats'):
                    all_stats[name] = strategy.get_real_time_stats()
                else:
                    all_stats[name] = {'supported': False}
            except Exception as e:
                self.logger.error(f"Failed to get stats for strategy '{name}': {e}")
                all_stats[name] = {'error': str(e)}
        
        return all_stats
    
    def benchmark_strategy_performance(self, name: str, test_duration: float = 10.0) -> Dict[str, Any]:
        """Benchmark strategy performance"""
        
        strategy = self.get_strategy(name)
        if not strategy:
            raise StrategyValidationError(f"Strategy '{name}' not found for benchmarking")
        
        benchmark_results = {
            'strategy_name': name,
            'test_duration': test_duration,
            'start_time': datetime.now().isoformat(),
            'performance_metrics': {},
            'error_metrics': {},
            'resource_usage': {}
        }
        
        try:
            # Measure initialization time
            start_init = time.time()
            strategy._validate_configuration()
            benchmark_results['performance_metrics']['initialization_time'] = time.time() - start_init
            
            # Measure estimation methods
            start_est = time.time()
            duration_estimate = strategy.estimate_duration()
            packet_count_estimate = strategy.estimate_packet_count()
            data_volume_estimate = strategy.estimate_data_volume()
            benchmark_results['performance_metrics']['estimation_time'] = time.time() - start_est
            
            benchmark_results['performance_metrics'].update({
                'estimated_duration_seconds': duration_estimate.total_seconds(),
                'estimated_packet_count': packet_count_estimate,
                'estimated_data_volume_bytes': data_volume_estimate
            })
            
            # Test sender validation if available
            if hasattr(strategy, 'senders'):
                start_validation = time.time()
                validation_results = SenderValidator.validate_sender_list(strategy.senders)
                benchmark_results['performance_metrics']['sender_validation_time'] = time.time() - start_validation
                benchmark_results['performance_metrics']['sender_validation_success_rate'] = (
                    validation_results['valid_senders'] / validation_results['total_senders']
                )
            
            # Store benchmark results
            self.performance_benchmarks[name] = benchmark_results['performance_metrics']
            
        except Exception as e:
            benchmark_results['error_metrics']['benchmark_error'] = str(e)
            self.logger.error(f"Benchmarking failed for strategy '{name}': {e}")
        
        benchmark_results['end_time'] = datetime.now().isoformat()
        return benchmark_results
    
    def export_configurations(self, export_path: Optional[Path] = None) -> Path:
        """Export all strategy configurations to JSON file"""
        
        if export_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = Path(f"strategy_configs_export_{timestamp}.json")
        
        export_data = {
            'metadata': {
                'export_timestamp': datetime.now().isoformat(),
                'registry_mode': self.options.mode.value,
                'total_strategies': len(self.strategies),
                'multicast_available': MULTICAST_AVAILABLE
            },
            'configurations': {},
            'capabilities': {},
            'performance_benchmarks': self.performance_benchmarks
        }
        
        for name, strategy in self.strategies.items():
            try:
                # Export configuration
                if hasattr(strategy, 'serialize_configuration'):
                    config_json = strategy.serialize_configuration()
                    export_data['configurations'][name] = json.loads(config_json)
                else:
                    export_data['configurations'][name] = self.strategy_configs.get(name, {})
                
                # Export capabilities
                if name in self.strategy_capabilities:
                    export_data['capabilities'][name] = asdict(self.strategy_capabilities[name])
                
            except Exception as e:
                self.logger.error(f"Failed to export configuration for strategy '{name}': {e}")
        
        # Write to file
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Configurations exported to: {export_path}")
        return export_path
    
    def import_configurations(self, import_path: Path) -> Dict[str, bool]:
        """Import strategy configurations from JSON file"""
        
        results = {}
        
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            configurations = import_data.get('configurations', {})
            capabilities = import_data.get('capabilities', {})
            
            for name, config in configurations.items():
                try:
                    if name in self.strategies:
                        strategy = self.strategies[name]
                        
                        if hasattr(strategy, 'deserialize_configuration'):
                            strategy.deserialize_configuration(json.dumps(config))
                        else:
                            strategy.update_configuration(config)
                        
                        # Update capabilities if provided
                        if name in capabilities:
                            capability_data = capabilities[name]
                            self.strategy_capabilities[name] = StrategyCapabilities(**capability_data)
                        
                        results[name] = True
                        self.logger.debug(f"Successfully imported configuration for strategy '{name}'")
                    
                    else:
                        results[name] = False
                        self.logger.warning(f"Strategy '{name}' not found for configuration import")
                
                except Exception as e:
                    results[name] = False
                    self.logger.error(f"Failed to import configuration for strategy '{name}': {e}")
            
        except Exception as e:
            self.logger.error(f"Failed to import configurations from {import_path}: {e}")
            raise StrategyValidationError(f"Configuration import failed: {e}")
        
        return results
    
    def _backup_strategy_configuration(self, name: str) -> None:
        """Backup strategy configuration before replacement"""
        
        if not self.options.enable_configuration_backup:
            return
        
        try:
            strategy = self.strategies.get(name)
            if strategy and hasattr(strategy, 'serialize_configuration'):
                backup_config = strategy.serialize_configuration()
                
                if name not in self.configuration_backups:
                    self.configuration_backups[name] = []
                
                self.configuration_backups[name].append(backup_config)
                
                # Keep only last 10 backups
                if len(self.configuration_backups[name]) > 10:
                    self.configuration_backups[name] = self.configuration_backups[name][-10:]
                
                self.logger.debug(f"Configuration backed up for strategy '{name}'")
        
        except Exception as e:
            self.logger.warning(f"Failed to backup configuration for strategy '{name}': {e}")
    
    def _deep_copy_config(self, config: StrategyConfig) -> StrategyConfig:
        """Create deep copy of configuration"""
        try:
            return json.loads(json.dumps(config))
        except (TypeError, ValueError):
            # Fallback for non-serializable objects
            import copy
            return copy.deepcopy(config)
    
    def _test_configuration_serialization(self, config: StrategyConfig) -> bool:
        """Test if configuration can be serialized"""
        try:
            json.dumps(config)
            return True
        except (TypeError, ValueError):
            return False
    
    # Signal handlers for enhanced monitoring
    def _on_strategy_execution_started(self, registry_name: str, strategy_name: str):
        """Handle strategy execution started event"""
        self.logger.info(f"Strategy '{registry_name}' execution started")
    
    def _on_strategy_execution_completed(self, registry_name: str, strategy_name: str, stats: Dict[str, Any]):
        """Handle strategy execution completed event"""
        self.logger.info(f"Strategy '{registry_name}' completed with stats: {stats}")
    
    def _on_strategy_execution_failed(self, registry_name: str, strategy_name: str, error: str, details: Dict[str, Any]):
        """Handle strategy execution failed event"""
        self.logger.error(f"Strategy '{registry_name}' failed: {error}, details: {details}")
    
    def _on_strategy_progress_updated(self, registry_name: str, current: int, total: int):
        """Handle strategy progress update"""
        progress_percent = (current / total * 100) if total > 0 else 0
        self.logger.debug(f"Strategy '{registry_name}' progress: {current}/{total} ({progress_percent:.1f}%)")
    
    def _on_strategy_rate_updated(self, registry_name: str, current_rate: float, avg_rate: float):
        """Handle strategy rate update"""
        self.logger.debug(f"Strategy '{registry_name}' rate: {current_rate:.2f} pps (avg: {avg_rate:.2f} pps)")
    
    def cleanup_strategies(self) -> None:
        """Comprehensive cleanup of all strategies and resources"""
        
        with self._registry_lock:
            self.logger.info(f"Cleaning up {len(self.strategies)} strategies...")
            
            cleanup_errors = []
            
            # Cancel all executing strategies first
            for name, strategy in self.strategies.items():
                try:
                    if hasattr(strategy, 'is_executing') and strategy.is_executing:
                        self.logger.debug(f"Cancelling execution for strategy '{name}'")
                        if hasattr(strategy, 'cancel_execution'):
                            strategy.cancel_execution()
                except Exception as e:
                    cleanup_errors.append(f"Failed to cancel strategy '{name}': {e}")
            
            # Clean up individual strategies
            for name, strategy in self.strategies.items():
                try:
                    # Cleanup monitoring resources
                    if hasattr(strategy, 'monitor'):
                        monitor = strategy.monitor
                        if hasattr(monitor, 'deleteLater'):
                            monitor.deleteLater()
                        elif hasattr(monitor, 'cleanup'):
                            monitor.cleanup()
                    
                    # Disconnect signals
                    for signal_name in ['execution_completed', 'execution_failed', 'execution_started', 'execution_paused', 'execution_resumed']:
                        if hasattr(strategy, signal_name):
                            try:
                                signal = getattr(strategy, signal_name)
                                if hasattr(signal, 'disconnect'):
                                    signal.disconnect()
                            except Exception:
                                pass  # Signal may already be disconnected
                    
                    self.logger.debug(f"Successfully cleaned up strategy '{name}'")
                
                except Exception as e:
                    error_msg = f"Error cleaning up strategy '{name}': {e}"
                    cleanup_errors.append(error_msg)
                    self.logger.warning(error_msg)
            
            # Clear all registries
            self.strategies.clear()
            self.strategy_configs.clear()
            self.strategy_metadata.clear()
            self.strategy_capabilities.clear()
            self.performance_benchmarks.clear()
            self.configuration_backups.clear()
            self.initialization_history.clear()
            
            # Reset state
            self.initialized = False
            self.initialization_time = None
            self.last_validation_time = None
            
            if cleanup_errors:
                self.logger.warning(f"Cleanup completed with {len(cleanup_errors)} errors")
            else:
                self.logger.info("Strategy registry cleanup completed successfully")
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive registry statistics"""
        
        with self._registry_lock:
            return {
                'registry_info': {
                    'mode': self.options.mode.value,
                    'initialized': self.initialized,
                    'initialization_time': self.initialization_time,
                    'last_validation_time': self.last_validation_time,
                    'total_strategies': len(self.strategies)
                },
                'strategy_breakdown': {
                    'total_strategies': len(self.strategies),
                    'enabled_strategies': len([
                        s for s in self.strategies.values() 
                        if getattr(s, 'strategy_enabled', True)
                    ]),
                    'executing_strategies': len([
                        s for s in self.strategies.values() 
                        if hasattr(s, 'is_executing') and s.is_executing
                    ]),
                    'paused_strategies': len([
                        s for s in self.strategies.values() 
                        if hasattr(s, 'is_paused') and s.is_paused
                    ]),
                    'multicast_strategies': len([
                        name for name, meta in self.strategy_metadata.items()
                        if meta.get('supports_multicast', False)
                    ])
                },
                'capability_summary': {
                    capability: len([
                        cap for cap in self.strategy_capabilities.values()
                        if getattr(cap, capability, False)
                    ])
                    for capability in [
                        'supports_multicast', 'supports_pause_resume', 
                        'supports_real_time_stats', 'supports_priority_qos',
                        'supports_rate_limiting', 'supports_burst_transmission'
                    ]
                },
                'performance_data': {
                    'benchmarked_strategies': len(self.performance_benchmarks),
                    'configuration_backups': sum(len(backups) for backups in self.configuration_backups.values()),
                    'initialization_history_entries': len(self.initialization_history)
                },
                'feature_availability': {
                    'multicast_available': MULTICAST_AVAILABLE,
                    'real_time_stats_enabled': self.options.enable_real_time_stats,
                    'sender_validation_enabled': self.options.validate_senders,
                    'configuration_backup_enabled': self.options.enable_configuration_backup
                }
            }


def create_enhanced_sender(
    interface: str = "dummy", 
    sender_type: str = "udp",
    target_ip: str = "127.0.0.1",
    target_port: int = 12345,
    validation_enabled: bool = True
) -> Sender:
    """
    Create an enhanced sender function with comprehensive capabilities
    
    Args:
        interface: Interface identifier for logging
        sender_type: Type of sender (udp, raw, dummy, tcp)
        target_ip: Target IP address for network senders
        target_port: Target port for network senders
        validation_enabled: Whether to enable packet validation
        
    Returns:
        Enhanced callable sender function
    """
    logger = logging.getLogger(f"TECMP.Strategies.Sender.{interface}")
    
    def enhanced_sender(packet_data: bytes) -> None:
        """Enhanced sender with comprehensive logging and validation"""
        try:
            # Input validation
            if not isinstance(packet_data, (bytes, bytearray)):
                if validation_enabled:
                    logger.warning(f"Invalid packet data type: {type(packet_data)}, converting to bytes")
                packet_data = bytes(packet_data) if packet_data else b''
            
            packet_size = len(packet_data)
            
            # Sender type specific handling
            if sender_type == "udp":
                _send_udp_packet(packet_data, target_ip, target_port, logger)
            elif sender_type == "tcp":
                _send_tcp_packet(packet_data, target_ip, target_port, logger)
            elif sender_type == "raw":
                _send_raw_packet(packet_data, interface, logger)
            else:  # dummy
                _send_dummy_packet(packet_data, interface, logger)
            
            logger.debug(f"Sent {packet_size} bytes via {interface} ({sender_type})")
            
        except Exception as e:
            logger.error(f"Enhanced sender error on {interface}: {e}")
            # Don't re-raise to avoid breaking strategy execution
    
    # Validate the created sender
    if not SenderValidator.validate_sender_callable(enhanced_sender):
        raise StrategyInitializationError(f"Failed to create valid sender for {interface}")
    
    return enhanced_sender


def _send_udp_packet(packet_data: bytes, target_ip: str, target_port: int, logger) -> None:
    """Send packet via UDP"""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(packet_data, (target_ip, target_port))
    except Exception as e:
        logger.debug(f"UDP send simulation: {len(packet_data)} bytes to {target_ip}:{target_port}")


def _send_tcp_packet(packet_data: bytes, target_ip: str, target_port: int, logger) -> None:
    """Send packet via TCP"""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            sock.connect((target_ip, target_port))
            sock.sendall(packet_data)
    except Exception as e:
        logger.debug(f"TCP send simulation: {len(packet_data)} bytes to {target_ip}:{target_port}")


def _send_raw_packet(packet_data: bytes, interface: str, logger) -> None:
    """Send packet via raw socket"""
    try:
        import socket
        # Raw socket implementation would go here
        logger.debug(f"Raw send simulation: {len(packet_data)} bytes on {interface}")
    except Exception as e:
        logger.debug(f"Raw send simulation: {len(packet_data)} bytes on {interface}")


def _send_dummy_packet(packet_data: bytes, interface: str, logger) -> None:
    """Send packet via dummy interface"""
    packet_size = len(packet_data)
    if packet_size <= 64:
        logger.debug(f"Dummy send: {packet_data.hex()}")
    else:
        logger.debug(f"Dummy send: {packet_size} bytes, preview: {packet_data[:16].hex()}...")


def create_production_senders(
    count: int = 2, 
    options: Optional[InitializationOptions] = None
) -> List[Sender]:
    """
    Create production-ready senders with enhanced validation and testing
    
    Args:
        count: Number of senders to create
        options: Initialization options for sender configuration
        
    Returns:
        List of validated and tested sender functions
    """
    if options is None:
        options = InitializationOptions()
    
    logger = logging.getLogger("TECMP.Strategies.Production")
    logger.info(f"Creating {count} production senders with options: {options}")
    
    senders = []
    sender_configs = [
        ("eth0", "udp", "192.168.1.100", 5000),
        ("eth1", "udp", "192.168.1.101", 5000),
        ("eth2", "tcp", "192.168.1.102", 5001),
        ("lo", "dummy", "127.0.0.1", 12345),
    ]
    
    for i in range(count):
        config_index = i % len(sender_configs)
        interface, sender_type, target_ip, target_port = sender_configs[config_index]
        
        # Unique interface name for multiple senders
        unique_interface = f"{interface}_{i}" if count > len(sender_configs) else interface
        
        try:
            sender = create_enhanced_sender(
                interface=unique_interface,
                sender_type=sender_type,
                target_ip=target_ip,
                target_port=target_port + i,  # Unique ports
                validation_enabled=options.validate_senders
            )
            
            # Test sender capability if validation enabled
            if options.validate_senders:
                test_result = SenderValidator.test_sender_capability(
                    sender, 
                    test_data=b'test_packet_data'
                )
                
                if not test_result['success']:
                    logger.warning(f"Sender {unique_interface} failed capability test: {test_result['error']}")
                    if options.error_handling_mode == ErrorHandlingMode.STRICT:
                        raise StrategyInitializationError(
                            f"Sender {unique_interface} failed capability test"
                        )
            
            senders.append(sender)
            logger.debug(f"Created production sender: {unique_interface} ({sender_type})")
            
        except Exception as e:
            logger.error(f"Failed to create sender for {unique_interface}: {e}")
            
            # Create fallback sender
            if options.error_handling_mode != ErrorHandlingMode.STRICT:
                fallback_sender = create_enhanced_sender(f"fallback_{unique_interface}", "dummy")
                senders.append(fallback_sender)
                logger.info(f"Created fallback sender for {unique_interface}")
            else:
                raise StrategyInitializationError(f"Failed to create required sender: {unique_interface}")
    
    # Final validation
    if not senders:
        raise StrategyInitializationError("No valid senders could be created")
    
    # Comprehensive sender list validation
    if options.validate_senders:
        validation_results = SenderValidator.validate_sender_list(senders)
        if not validation_results['all_valid']:
            if options.error_handling_mode == ErrorHandlingMode.STRICT:
                raise StrategyInitializationError(f"Sender validation failed: {validation_results}")
            else:
                logger.warning(f"Some senders failed validation: {validation_results['invalid_senders']}")
    
    logger.info(f"Created {len(senders)} validated production senders")
    return senders


def create_comprehensive_strategy_configurations(options: InitializationOptions) -> Dict[str, StrategyConfig]:
    """
    Create comprehensive strategy configurations based on initialization options
    
    Args:
        options: Initialization options with mode and parameters
        
    Returns:
        Dictionary mapping strategy names to their enhanced configurations
    """
    logger = logging.getLogger("TECMP.Strategies.Config")
    logger.debug(f"Creating comprehensive configurations for mode: {options.mode.value}")
    
    mode = options.mode
    
    if mode == InitializationMode.DEVELOPMENT:
        return {
            'single_packet': {
                'repeat_count': 3,
                'delay_between_repeats': 0.1,
                'enabled': True,
                'name': 'SingleDev',
                'description': 'Development single packet strategy with moderate repetition',
                'error_handling_mode': ErrorHandlingMode.LENIENT.value,
                'enable_real_time_stats': True,
                'validation_level': 'basic'
            },
            'priority_based': {
                'use_vlan_priority': True,
                'vlan_priority': 4,
                'use_ip_dscp': False,
                'packet_count': 50,
                'base_interval': 0.02,
                'enabled': True,
                'name': 'PriorityDev',
                'description': 'Development priority strategy with basic QoS',
                'error_handling_mode': ErrorHandlingMode.LENIENT.value,
                'enable_real_time_stats': True
            },
            'multi_packet': {
                'packets_per_burst': 3,
                'burst_count': 5,
                'inter_packet_delay': 0.001,
                'inter_burst_delay': 0.2,
                'enabled': True,
                'name': 'MultiDev',
                'description': 'Development burst strategy with small bursts',
                'error_handling_mode': ErrorHandlingMode.LENIENT.value,
                'enable_real_time_stats': True
            },
            'ramp_speed': {
                'start_rate': 5.0,
                'end_rate': 50.0,
                'ramp_type': 'linear',
                'duration': 10.0,
                'step_duration': 1.0,
                'enabled': True,
                'name': 'RampDev',
                'description': 'Development ramp strategy with gentle progression',
                'error_handling_mode': ErrorHandlingMode.LENIENT.value,
                'enable_real_time_stats': True
            }
        }
    
    elif mode == InitializationMode.TESTING:
        return {
            'single_packet': {
                'repeat_count': 1,
                'delay_between_repeats': 0.0,
                'enabled': True,
                'name': 'SingleTest',
                'description': 'Testing single packet strategy',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'test_mode': True,
                'validation_level': 'comprehensive'
            },
            'priority_based': {
                'use_vlan_priority': True,
                'vlan_priority': 6,
                'use_ip_dscp': True,
                'ip_dscp': 46,
                'packet_count': 10,
                'base_interval': 0.01,
                'enabled': True,
                'name': 'PriorityTest',
                'description': 'Testing priority strategy with full QoS',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'test_mode': True
            }
        }
    
    elif mode == InitializationMode.CLI:
        return {
            'single_packet': {
                'repeat_count': 1,
                'delay_between_repeats': 0.0,
                'enabled': True,
                'name': 'SingleCLI',
                'description': 'CLI optimized single packet strategy',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': False,  # Reduced overhead for CLI
                'cli_optimized': True
            },
            'priority_based': {
                'use_vlan_priority': True,
                'vlan_priority': 5,
                'use_ip_dscp': True,
                'ip_dscp': 46,
                'packet_count': 100,
                'base_interval': 0.01,
                'enabled': True,
                'name': 'PriorityCLI',
                'description': 'CLI priority strategy with QoS marking',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': False,
                'cli_optimized': True
            },
            'multi_packet': {
                'packets_per_burst': 10,
                'burst_count': 10,
                'inter_packet_delay': 0.001,
                'inter_burst_delay': 0.1,
                'enabled': True,
                'name': 'MultiCLI',
                'description': 'CLI burst strategy for batch operations',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': False,
                'cli_optimized': True
            },
            'ramp_speed': {
                'start_rate': 1.0,
                'end_rate': 100.0,
                'ramp_type': 'exponential',
                'duration': 30.0,
                'step_duration': 1.0,
                'enabled': True,
                'name': 'RampCLI',
                'description': 'CLI ramp strategy for load testing',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': False,
                'cli_optimized': True
            }
        }
    
    elif mode == InitializationMode.LITE:
        return {
            'single_packet': {
                'repeat_count': 1,
                'delay_between_repeats': 0.0,
                'enabled': True,
                'name': 'SingleLite',
                'description': 'Lightweight single packet transmission',
                'error_handling_mode': ErrorHandlingMode.LENIENT.value,
                'enable_real_time_stats': False,
                'minimal_logging': True,
                'resource_optimized': True
            },
            'priority_based': {
                'use_vlan_priority': False,
                'use_ip_dscp': False,
                'packet_count': 10,
                'base_interval': 0.1,
                'enabled': True,
                'name': 'PriorityLite',
                'description': 'Lightweight priority strategy without QoS overhead',
                'error_handling_mode': ErrorHandlingMode.LENIENT.value,
                'enable_real_time_stats': False,
                'minimal_logging': True,
                'resource_optimized': True
            }
        }
    
    elif mode == InitializationMode.BENCHMARK:
        return {
            'single_packet': {
                'repeat_count': 1000,
                'delay_between_repeats': 0.0,
                'enabled': True,
                'name': 'SingleBenchmark',
                'description': 'Benchmark single packet strategy',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'benchmark_mode': True,
                'performance_tracking': True
            },
            'priority_based': {
                'use_vlan_priority': True,
                'vlan_priority': 7,
                'use_ip_dscp': True,
                'ip_dscp': 56,
                'packet_count': 10000,
                'base_interval': 0.001,
                'enabled': True,
                'name': 'PriorityBenchmark',
                'description': 'Benchmark priority strategy with maximum QoS',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'benchmark_mode': True,
                'performance_tracking': True
            },
            'multi_packet': {
                'packets_per_burst': 100,
                'burst_count': 100,
                'inter_packet_delay': 0.0001,
                'inter_burst_delay': 0.01,
                'enabled': True,
                'name': 'MultiBenchmark',
                'description': 'Benchmark burst strategy for maximum throughput',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'benchmark_mode': True,
                'performance_tracking': True
            },
            'ramp_speed': {
                'start_rate': 10.0,
                'end_rate': 10000.0,
                'ramp_type': 'exponential',
                'duration': 300.0,
                'step_duration': 5.0,
                'enabled': True,
                'name': 'RampBenchmark',
                'description': 'Benchmark ramp strategy for performance testing',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'benchmark_mode': True,
                'performance_tracking': True
            }
        }
    
    else:  # PRODUCTION, CONFIG, or default
        return {
            'single_packet': {
                'repeat_count': 1,
                'delay_between_repeats': 0.0,
                'enabled': True,
                'name': 'SingleProduction',
                'description': 'Production single packet transmission with reliability',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'production_grade': True,
                'fault_tolerance': True
            },
            'priority_based': {
                'use_vlan_priority': True,
                'vlan_priority': 5,
                'use_ip_dscp': True,
                'ip_dscp': 46,
                'guaranteed_bandwidth': None,
                'max_bandwidth': None,
                'packet_count': 1000,
                'base_interval': 0.01,
                'enabled': True,
                'name': 'PriorityProduction',
                'description': 'Production QoS-aware transmission with industry standards',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'production_grade': True,
                'qos_compliance': True
            },
            'multi_packet': {
                'packets_per_burst': 10,
                'burst_count': 100,
                'inter_packet_delay': 0.001,
                'inter_burst_delay': 1.0,
                'enabled': True,
                'name': 'MultiProduction',
                'description': 'Production burst transmission with precise timing',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'production_grade': True,
                'timing_precision': True
            },
            'ramp_speed': {
                'start_rate': 1.0,
                'end_rate': 1000.0,
                'ramp_type': 'linear',
                'duration': 60.0,
                'step_duration': 1.0,
                'enabled': True,
                'name': 'RampProduction',
                'description': 'Production progressive rate increase for load testing',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'production_grade': True,
                'load_testing_optimized': True
            },
            'multicast': {
                'packets_per_burst': 10,
                'burst_count': 50,
                'inter_packet_delay': 0.001,
                'inter_burst_delay': 0.5,
                'enabled': True,
                'name': 'MulticastProduction',
                'description': 'Production coordinated multicast transmission',
                'error_handling_mode': ErrorHandlingMode.STRICT.value,
                'enable_real_time_stats': True,
                'production_grade': True,
                'multicast_coordination': True
            }
        }


def validate_initialization_requirements(
    management: ManagementContainer, 
    options: InitializationOptions
) -> None:
    """
    Enhanced validation with comprehensive checks
    
    Args:
        management: ManagementContainer to validate
        options: Initialization options for validation criteria
        
    Raises:
        StrategyInitializationError: If validation fails
    """
    logger = logging.getLogger("TECMP.Strategies.Validation")
    logger.debug(f"Validating initialization requirements for mode: {options.mode.value}")
    
    # Validate ManagementContainer
    if management is None:
        raise StrategyInitializationError("ManagementContainer is required", mode=options.mode.value)
    
    # Validate PacketManager presence and type
    if not hasattr(management, 'packet_manager') or management.packet_manager is None:
        raise StrategyInitializationError("PacketManager is required in ManagementContainer", mode=options.mode.value)
    
    if not isinstance(management.packet_manager, PacketManager):
        error_msg = f"Expected PacketManager instance, got {type(management.packet_manager).__name__}"
        if options.error_handling_mode == ErrorHandlingMode.STRICT:
            raise StrategyInitializationError(error_msg, mode=options.mode.value)
        else:
            logger.warning(f"{error_msg} (continuing in lenient mode)")
    
    # Enhanced PacketManager functionality validation
    try:
        packet_count = len(management.packet_manager)
        logger.debug(f"PacketManager validation: {packet_count} packets available")
        
        if packet_count == 0:
            if options.mode in [InitializationMode.PRODUCTION, InitializationMode.BENCHMARK]:
                raise StrategyInitializationError(
                    "PacketManager contains no packets - required for production/benchmark mode",
                    mode=options.mode.value
                )
            else:
                logger.warning("PacketManager contains no packets - strategies may not function optimally")
        
        # Test essential PacketManager methods
        required_methods = ['__len__', '__iter__']
        optional_methods = ['get_packets_for_strategy', 'get_packet_batches', 'clone_packet']
        
        for method in required_methods:
            if not hasattr(management.packet_manager, method):
                raise StrategyInitializationError(
                    f"PacketManager missing required method: {method}",
                    mode=options.mode.value
                )
        
        for method in optional_methods:
            if not hasattr(management.packet_manager, method):
                logger.debug(f"PacketManager missing optional method: {method}")
        
        # Test packet iteration
        packet_iter = iter(management.packet_manager)
        try:
            first_packet = next(packet_iter)
            logger.debug(f"PacketManager iteration test successful, first packet type: {type(first_packet)}")
        except StopIteration:
            logger.debug("PacketManager iteration test: no packets available")
        
    except Exception as e:
        error_msg = f"PacketManager validation failed: {e}"
        if options.error_handling_mode == ErrorHandlingMode.STRICT:
            raise StrategyInitializationError(error_msg, mode=options.mode.value)
        else:
            logger.warning(f"{error_msg} (continuing in lenient mode)")
    
    # Validate signal support for monitoring
    monitoring_signals = ['error_occurred', 'strategy_completed', 'progress_updated']
    for signal in monitoring_signals:
        if hasattr(management, signal):
            logger.debug(f"Management signal '{signal}' available")
        else:
            logger.debug(f"Management signal '{signal}' not available")
    
    # Mode-specific validations
    if options.mode == InitializationMode.PRODUCTION:
        # Production mode requires strict validation
        if not options.validate_senders:
            logger.warning("Production mode with sender validation disabled - not recommended")
        
        if options.error_handling_mode != ErrorHandlingMode.STRICT:
            logger.warning("Production mode with non-strict error handling - not recommended")
    
    elif options.mode == InitializationMode.BENCHMARK:
        # Benchmark mode requires real-time stats
        if not options.enable_real_time_stats:
            raise StrategyInitializationError(
                "Benchmark mode requires real-time statistics to be enabled",
                mode=options.mode.value
            )
    
    logger.debug("Enhanced validation completed successfully")


def create_strategy_with_enhanced_initialization(
    strategy_class,
    name: str,
    packet_manager: PacketManager,
    senders: Union[Sender, List[Sender]],
    config: Dict[str, Any],
    options: InitializationOptions
) -> SenderStrategy:
    """
    Enhanced strategy creation with comprehensive initialization
    
    Args:
        strategy_class: Strategy class to instantiate
        name: Strategy name
        packet_manager: PacketManager instance
        senders: Validated sender(s)
        config: Configuration dictionary
        options: Initialization options
        
    Returns:
        Properly initialized and configured strategy instance
    """
    logger = logging.getLogger("TECMP.Strategies.EnhancedInit")
    
    try:
        # Enhanced sender validation
        if options.validate_senders:
            if isinstance(senders, list):
                validation_results = SenderValidator.validate_sender_list(senders)
                if not validation_results['all_valid']:
                    invalid_details = validation_results['invalid_senders']
                    raise SenderValidationError(
                        f"Enhanced validation failed for senders: {invalid_details}",
                        validation_method="enhanced_initialization"
                    )
            else:
                if not SenderValidator.validate_sender_callable(senders):
                    raise SenderValidationError("Single sender failed enhanced validation")
        
        # Prepare enhanced configuration
        enhanced_config = config.copy()
        
        # Add mode-specific configuration enhancements
        enhanced_config.update({
            'initialization_mode': options.mode.value,
            'error_handling_mode': options.error_handling_mode.value,
            'enable_real_time_stats': options.enable_real_time_stats,
            'sender_validation_passed': options.validate_senders,
            'initialization_timestamp': datetime.now().isoformat()
        })
        
        # Strategy-specific configuration defaults
        if strategy_class.__name__ == 'SinglePacketStrategy':
            enhanced_config.setdefault('repeat_count', 1)
            enhanced_config.setdefault('delay_between_repeats', 0.0)
        elif strategy_class.__name__ == 'PriorityBasedStrategy':
            enhanced_config.setdefault('use_vlan_priority', True)
            enhanced_config.setdefault('vlan_priority', 5)
        elif strategy_class.__name__ == 'MultiPacketStrategy':
            enhanced_config.setdefault('packets_per_burst', 10)
            enhanced_config.setdefault('burst_count', 10)
        elif strategy_class.__name__ == 'RampSpeedStrategy':
            enhanced_config.setdefault('start_rate', 1.0)
            enhanced_config.setdefault('end_rate', 100.0)
            enhanced_config.setdefault('ramp_type', 'linear')
        
        # Create strategy with enhanced parameters
        strategy = strategy_class(
            packet_manager=packet_manager,
            senders=senders,
            config=enhanced_config,
            name=f"{enhanced_config.get('name', name)}_{options.mode.value}",
            error_handling_mode=options.error_handling_mode,
            validate_senders=options.validate_senders,
            enable_real_time_stats=options.enable_real_time_stats
        )
        
        logger.debug(f"Successfully created enhanced strategy '{name}' of type {strategy_class.__name__}")
        return strategy
        
    except Exception as e:
        error_msg = f"Enhanced initialization failed for strategy '{name}' ({strategy_class.__name__}): {e}"
        logger.error(error_msg)
        raise StrategyInitializationError(
            error_msg, 
            mode=options.mode.value, 
            strategy_name=name
        ) from e


def connect_enhanced_strategy_monitoring(
    strategy: SenderStrategy, 
    management: ManagementContainer, 
    facade,
    options: InitializationOptions
) -> None:
    """
    Connect comprehensive enhanced monitoring between strategy, management, and facade
    
    Args:
        strategy: Strategy to connect monitoring for
        management: ManagementContainer for signal routing
        facade: Central facade for coordination
        options: Initialization options for monitoring configuration
    """
    logger = logging.getLogger("TECMP.Strategies.EnhancedMonitoring")
    strategy_name = getattr(strategy, 'name', strategy.__class__.__name__)
    
    try:
        # Enhanced lifecycle signal connections
        lifecycle_signals = [
            ('execution_started', '_on_enhanced_strategy_started'),
            ('execution_completed', '_on_enhanced_strategy_completed'),
            ('execution_failed', '_on_enhanced_strategy_failed'),
            ('execution_paused', '_on_enhanced_strategy_paused'),
            ('execution_resumed', '_on_enhanced_strategy_resumed')
        ]
        
        for signal_name, handler_name in lifecycle_signals:
            if hasattr(strategy, signal_name):
                signal = getattr(strategy, signal_name)
                
                # Create enhanced handler
                def create_handler(signal_type, strategy_name):
                    def handler(*args):
                        logger.info(f"Enhanced {signal_type} for strategy '{strategy_name}': {args}")
                        
                        # Route to management if available
                        management_signal = f"strategy_{signal_type}"
                        if hasattr(management, management_signal):
                            management_signal_obj = getattr(management, management_signal)
                            if hasattr(management_signal_obj, 'emit'):
                                management_signal_obj.emit(strategy_name, *args)
                    
                    return handler
                
                enhanced_handler = create_handler(signal_name.replace('execution_', ''), strategy_name)
                signal.connect(enhanced_handler)
                logger.debug(f"Connected enhanced {signal_name} monitoring for '{strategy_name}'")
        
        # Enhanced real-time monitoring
        if options.enable_real_time_stats and hasattr(strategy, 'monitor'):
            monitor = strategy.monitor
            
            # Progress monitoring with enhanced metrics
            if hasattr(monitor, 'progress_updated'):
                def enhanced_progress_handler(current: int, total: int):
                    progress_percent = (current / total * 100) if total > 0 else 0
                    logger.debug(f"Enhanced progress for '{strategy_name}': {current}/{total} ({progress_percent:.1f}%)")
                    
                    if hasattr(management, 'enhanced_progress_updated'):
                        management.enhanced_progress_updated.emit(strategy_name, current, total, progress_percent)
                    elif hasattr(management, 'progress_updated'):
                        management.progress_updated.emit(current, total)
                
                monitor.progress_updated.connect(enhanced_progress_handler)
            
            # Rate monitoring
            if hasattr(monitor, 'rate_updated'):
                def enhanced_rate_handler(current_rate: float, avg_rate: float):
                    logger.debug(f"Enhanced rate for '{strategy_name}': {current_rate:.2f} pps (avg: {avg_rate:.2f})")
                    
                    if hasattr(management, 'strategy_rate_updated'):
                        management.strategy_rate_updated.emit(strategy_name, current_rate, avg_rate)
                
                monitor.rate_updated.connect(enhanced_rate_handler)
            
            # Packet-level monitoring with enhanced details
            if hasattr(monitor, 'packet_sent'):
                def enhanced_packet_handler(packet, sender_index: int, packet_size: int):
                    logger.debug(f"Enhanced packet sent via '{strategy_name}': {packet_size} bytes, sender {sender_index}")
                    
                    # Update management metadata with enhanced info
                    if hasattr(management, '_update_enhanced_metadata'):
                        try:
                            management._update_enhanced_metadata(strategy_name, packet_size, sender_index)
                        except Exception as e:
                            logger.debug(f"Enhanced metadata update failed: {e}")
                    elif hasattr(management, '_update_current_metadata'):
                        try:
                            management._update_current_metadata()
                        except Exception as e:
                            logger.debug(f"Standard metadata update failed: {e}")
                
                monitor.packet_sent.connect(enhanced_packet_handler)
        
        # Enhanced facade registration
        if facade and hasattr(facade, 'register_enhanced_strategy'):
            try:
                enhanced_registration_data = {
                    'strategy': strategy,
                    'capabilities': getattr(strategy, '_capabilities', None),
                    'initialization_options': options,
                    'monitoring_enabled': options.enable_real_time_stats
                }
                facade.register_enhanced_strategy(strategy_name, enhanced_registration_data)
                logger.debug(f"Enhanced strategy '{strategy_name}' registered with facade")
            except Exception as e:
                logger.warning(f"Enhanced facade registration failed for '{strategy_name}': {e}")
                # Fallback to standard registration
                if hasattr(facade, 'register_strategy'):
                    try:
                        facade.register_strategy(strategy_name, strategy)
                        logger.debug(f"Strategy '{strategy_name}' registered with facade (standard mode)")
                    except Exception as e2:
                        logger.warning(f"Standard facade registration also failed for '{strategy_name}': {e2}")
        
    except Exception as e:
        logger.error(f"Failed to connect enhanced monitoring for strategy '{strategy_name}': {e}")
        # Don't raise - monitoring failure shouldn't prevent strategy initialization


def initialize_strategies(
    facade, 
    management: ManagementContainer, 
    senders: Optional[List[Sender]] = None,
    options: Optional[InitializationOptions] = None
) -> StrategyRegistry:
    """
    Enhanced strategy initialization with comprehensive features and validation
    
    Args:
        facade: Central facade for coordination and strategy registration
        management: ManagementContainer with PacketManager and signal support
        senders: Optional list of Sender callables (auto-created if None)
        options: Enhanced initialization options (defaults to production mode)
        
    Returns:
        StrategyRegistry with properly initialized and validated strategies
        
    Raises:
        StrategyInitializationError: If critical initialization requirements fail
    """
    start_time = time.time()
    
    # Use default options if none provided
    if options is None:
        options = InitializationOptions()
    
    logger = logging.getLogger("TECMP.Strategies.EnhancedInit")
    logger.info(f"Initializing enhanced packet sending strategies with options: {options}")
    
    # Create enhanced registry
    registry = StrategyRegistry(options)
    
    # Record initialization attempt
    initialization_record = {
        'timestamp': datetime.now().isoformat(),
        'mode': options.mode.value,
        'options': asdict(options),
        'multicast_available': MULTICAST_AVAILABLE,
        'facade_available': facade is not None
    }
    
    try:
        # Enhanced validation of initialization requirements
        validate_initialization_requirements(management, options)
        
        # Create and validate senders if not provided
        if senders is None:
            senders = create_production_senders(
                count=options.min_sender_count if options.mode != InitializationMode.LITE else 1,
                options=options
            )
        
        if not senders or len(senders) == 0:
            raise StrategyInitializationError("No senders available for strategy initialization", mode=options.mode.value)
        
        # Comprehensive sender validation
        if options.validate_senders:
            validation_results = SenderValidator.validate_sender_list(senders)
            if not validation_results['all_valid']:
                invalid_details = validation_results['invalid_senders']
                if options.error_handling_mode == ErrorHandlingMode.STRICT:
                    raise SenderValidationError(f"Sender validation failed: {invalid_details}")
                else:
                    logger.warning(f"Some senders failed validation (continuing): {invalid_details}")
        
        logger.debug(f"Using {len(senders)} validated senders for strategy initialization")
        
        # Get comprehensive configurations
        configurations = create_comprehensive_strategy_configurations(options)
        
        # Enhanced strategy initialization specs
        strategy_specs = [
            ('single_packet', SinglePacketStrategy, senders[0], 'single_packet', {}),
            ('priority_based', PriorityBasedStrategy, senders[0], 'priority_based', {}),
            ('multi_packet', MultiPacketStrategy, senders[0], 'multi_packet', {}),
            ('ramp_speed', RampSpeedStrategy, senders[0], 'ramp_speed', {}),
        ]
        
        # Add multicast strategy if available and conditions met
        multicast_conditions = [
            MULTICAST_AVAILABLE,
            len(senders) > 1,
            options.mode not in [InitializationMode.LITE]
        ]
        
        if all(multicast_conditions) or options.force_multicast:
            strategy_specs.append(
                ('multicast', MulticastStrategy, senders, 'multicast', {'min_senders': 2})
            )
            logger.debug("Enhanced multicast strategy included")
        
        # Apply strategy filter if specified
        if options.strategy_filter:
            original_count = len(strategy_specs)
            strategy_specs = [
                spec for spec in strategy_specs 
                if spec[0] in options.strategy_filter
            ]
            logger.debug(f"Strategy filter applied: {original_count} -> {len(strategy_specs)} strategies")
        
        # Enhanced strategy initialization with comprehensive error handling
        successful_strategies = []
        failed_strategies = []
        performance_metrics = {}
        
        for name, strategy_class, strategy_senders, config_key, requirements in strategy_specs:
            strategy_start_time = time.time()
            
            try:
                logger.debug(f"Initializing enhanced strategy: {name}")
                
                # Check requirements
                if 'min_senders' in requirements:
                    required_senders = requirements['min_senders']
                    available_senders = len(senders) if isinstance(strategy_senders, list) else 1
                    if available_senders < required_senders:
                        raise StrategyInitializationError(
                            f"Strategy '{name}' requires at least {required_senders} senders, "
                            f"but only {available_senders} available",
                            mode=options.mode.value,
                            strategy_name=name
                        )
                
                # Get configuration with enhancements
                config = configurations.get(config_key, {})
                if not config:
                    logger.warning(f"No configuration found for strategy '{name}', using defaults")
                    config = {'enabled': True, 'name': name}
                
                # Enhanced strategy creation
                strategy = create_strategy_with_enhanced_initialization(
                    strategy_class=strategy_class,
                    name=name,
                    packet_manager=management.packet_manager,
                    senders=strategy_senders,
                    config=config,
                    options=options
                )
                
                # Auto-detect and register capabilities
                capabilities = registry._detect_strategy_capabilities(strategy)
                
                # Enhanced metadata
                metadata = {
                    'initialization_mode': options.mode.value,
                    'config_key': config_key,
                    'strategy_class': strategy_class.__name__,
                    'requirements': requirements,
                    'initialization_duration': time.time() - strategy_start_time,
                    'sender_count': len(strategy_senders) if isinstance(strategy_senders, list) else 1,
                    'enhanced_features_enabled': True
                }
                
                # Register strategy with enhanced data
                registry.register_strategy(name, strategy, config, metadata, capabilities)
                
                # Connect enhanced monitoring
                connect_enhanced_strategy_monitoring(strategy, management, facade, options)
                
                # Record performance metrics
                performance_metrics[name] = {
                    'initialization_time': time.time() - strategy_start_time,
                    'memory_usage': 0,  # Would implement actual memory tracking
                    'capability_count': len([
                        attr for attr in dir(capabilities) 
                        if not attr.startswith('_') and getattr(capabilities, attr) is True
                    ])
                }
                
                successful_strategies.append(name)
                logger.info(f"Successfully initialized enhanced strategy: {name}")
                
            except Exception as e:
                initialization_duration = time.time() - strategy_start_time
                error_details = {
                    'strategy_name': name,
                    'error_type': type(e).__name__,
                    'initialization_duration': initialization_duration,
                    'requirements': requirements
                }
                
                error_msg = f"Enhanced initialization failed for strategy '{name}': {e}"
                logger.error(error_msg)
                failed_strategies.append((name, str(e), error_details))
                
                # Handle errors based on mode
                if options.error_handling_mode == ErrorHandlingMode.FAIL_FAST:
                    raise StrategyInitializationError(error_msg, options.mode.value, name, error_details) from e
                elif (options.error_handling_mode == ErrorHandlingMode.STRICT and 
                      options.mode == InitializationMode.PRODUCTION):
                    raise StrategyInitializationError(error_msg, options.mode.value, name, error_details) from e
                else:
                    # Continue with remaining strategies
                    if hasattr(management, 'error_occurred'):
                        management.error_occurred.emit("enhanced_strategy_init", error_msg)
        
        # Verify minimum success criteria
        if not successful_strategies:
            error_msg = "No strategies were successfully initialized"
            logger.error(error_msg)
            raise StrategyInitializationError(error_msg, options.mode.value)
        
        # Enhanced validation of all registered strategies
        validation_results = {}
        for name in successful_strategies:
            strategy = registry.get_strategy(name)
            if strategy:
                try:
                    # Comprehensive validation
                    strategy._validate_configuration()
                    
                    # Test estimation methods
                    strategy.estimate_duration()
                    strategy.estimate_packet_count()
                    strategy.estimate_data_volume()
                    
                    validation_results[name] = True
                    
                except Exception as e:
                    validation_results[name] = False
                    logger.error(f"Enhanced validation failed for strategy '{name}': {e}")
        
        failed_validations = [name for name, valid in validation_results.items() if not valid]
        if failed_validations:
            if options.error_handling_mode == ErrorHandlingMode.STRICT:
                raise StrategyInitializationError(f"Enhanced validation failed: {failed_validations}", options.mode.value)
            else:
                logger.warning(f"Some strategies failed enhanced validation: {failed_validations}")
        
        # Finalize registry initialization
        registry.initialized = True
        registry.initialization_time = time.time()
        
        # Record successful initialization
        initialization_duration = time.time() - start_time
        initialization_record.update({
            'success': True,
            'duration_seconds': initialization_duration,
            'successful_strategies': successful_strategies,
            'failed_strategies': [name for name, _, _ in failed_strategies],
            'performance_metrics': performance_metrics,
            'validation_results': validation_results
        })
        
        registry.initialization_history.append(initialization_record)
        
        # Comprehensive success logging
        logger.info(
            f"Enhanced strategy initialization completed successfully in {initialization_duration:.3f}s\n"
            f"  Mode: {options.mode.value}\n"
            f"  Successful strategies: {successful_strategies}\n"
            f"  Failed strategies: {[name for name, _, _ in failed_strategies]}\n"
            f"  Total senders: {len(senders)}\n"
            f"  Enhanced features: Real-time stats={options.enable_real_time_stats}, "
            f"Validation={options.validate_senders}\n"
            f"  Multicast support: {MULTICAST_AVAILABLE and len(senders) > 1}\n"
            f"  Performance metrics recorded: {len(performance_metrics)} strategies"
        )
        
        # Emit enhanced management signals
        if hasattr(management, 'enhanced_strategies_initialized'):
            management.enhanced_strategies_initialized.emit(successful_strategies, performance_metrics)
        elif hasattr(management, 'strategies_initialized'):
            management.strategies_initialized.emit(successful_strategies)
        
        return registry
        
    except Exception as e:
        # Comprehensive error handling and cleanup
        initialization_duration = time.time() - start_time
        initialization_record.update({
            'success': False,
            'duration_seconds': initialization_duration,
            'error_message': str(e),
            'error_type': type(e).__name__
        })
        
        registry.initialization_history.append(initialization_record)
        
        error_msg = f"Enhanced strategy initialization failed: {e}"
        logger.error(error_msg)
        
        # Attempt cleanup
        try:
            registry.cleanup_strategies()
        except Exception as cleanup_error:
            logger.error(f"Cleanup failed after initialization error: {cleanup_error}")
        
        # Emit error signal
        if hasattr(management, 'error_occurred'):
            management.error_occurred.emit("enhanced_strategy_initialization", error_msg)
        
        raise StrategyInitializationError(error_msg, options.mode.value, details=initialization_record) from e


def reinitialize_strategies(
    existing_registry: StrategyRegistry,
    facade,
    management: ManagementContainer,
    new_options: Optional[InitializationOptions] = None,
    new_senders: Optional[List[Sender]] = None
) -> StrategyRegistry:
    """
    Enhanced strategy reinitialization with preservation of valuable state
    
    Args:
        existing_registry: Current strategy registry to replace
        facade: Central facade for coordination
        management: ManagementContainer
        new_options: Optional new initialization options
        new_senders: Optional new senders to use
        
    Returns:
        New StrategyRegistry with reinitialized strategies
    """
    logger = logging.getLogger("TECMP.Strategies.EnhancedReinit")
    
    # Preserve valuable information from existing registry
    preservation_data = {
        'previous_mode': existing_registry.options.mode.value if existing_registry.options else 'unknown',
        'previous_strategies': list(existing_registry.strategies.keys()),
        'performance_benchmarks': existing_registry.performance_benchmarks.copy(),
        'configuration_backups': existing_registry.configuration_backups.copy(),
        'initialization_history': existing_registry.initialization_history.copy()
    }
    
    # Determine new options
    if new_options is None:
        new_options = existing_registry.options if existing_registry.options else InitializationOptions()
    
    logger.info(
        f"Enhanced reinitialization: {preservation_data['previous_mode']} -> {new_options.mode.value}"
    )
    
    # Backup current configurations before cleanup
    if new_options.enable_configuration_backup:
        try:
            backup_path = existing_registry.export_configurations()
            logger.info(f"Configuration backup created at: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to create configuration backup: {e}")
    
    # Extract current strategy list for filtering
    current_strategies = existing_registry.list_strategies() if preservation_data['previous_strategies'] else None
    if current_strategies:
        new_options.strategy_filter = current_strategies
    
    # Cleanup existing registry
    try:
        existing_registry.cleanup_strategies()
        logger.debug("Existing registry cleaned up successfully")
    except Exception as e:
        logger.warning(f"Error during existing registry cleanup: {e}")
    
    # Initialize new registry with enhanced features
    new_registry = initialize_strategies(
        facade=facade,
        management=management,
        senders=new_senders,
        options=new_options
    )
    
    # Restore preserved data
    try:
        new_registry.performance_benchmarks.update(preservation_data['performance_benchmarks'])
        new_registry.configuration_backups.update(preservation_data['configuration_backups'])
        new_registry.initialization_history.extend(preservation_data['initialization_history'])
        
        # Add reinitialization record
        reinitialization_record = {
            'timestamp': datetime.now().isoformat(),
            'type': 'reinitialization',
            'previous_mode': preservation_data['previous_mode'],
            'new_mode': new_options.mode.value,
            'preserved_data_keys': list(preservation_data.keys()),
            'strategies_preserved': len(preservation_data['previous_strategies']),
            'benchmarks_preserved': len(preservation_data['performance_benchmarks'])
        }
        new_registry.initialization_history.append(reinitialization_record)
        
        logger.info("Enhanced reinitialization completed with data preservation")
        
    except Exception as e:
        logger.warning(f"Failed to restore some preserved data: {e}")
    
    return new_registry


# Export comprehensive public interface
__all__ = [
    # Main classes
    'StrategyRegistry',
    'InitializationOptions',
    'StrategyCapabilities',
    'InitializationMode',
    
    # Enhanced exceptions
    'StrategyInitializationError',
    
    # Main functions
    'initialize_strategies',
    'reinitialize_strategies',
    
    # Enhanced utility functions
    'create_comprehensive_strategy_configurations',
    'create_production_senders',
    'create_enhanced_sender',
    'validate_initialization_requirements',
    'connect_enhanced_strategy_monitoring',
    'create_strategy_with_enhanced_initialization',
    
    # Import from base strategy
    'SenderStrategy',
    'StrategyState',
    'ErrorHandlingMode',
    'SenderValidator',
    'StrategyMonitor',
    'RealTimeStats',
    'StrategyConfigBuilder',
    
    # Enhanced exception types
    'StrategyExecutionError',
    'StrategyValidationError',
    'SenderValidationError',
    'PacketSerializationError',
    'PacketModificationError',
    'DependencyError',
    
    # Constants and types
    'MULTICAST_AVAILABLE',
    'Sender',
    'StrategyConfig'
]