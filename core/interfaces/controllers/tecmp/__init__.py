
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TECMP Controllers Module
========================

Professional TECMP UI Controller module providing:
- Unified TECMP packet encapsulation
- Real-time monitoring and statistics
- Qt and non-Qt operation modes
- Automotive protocol support
"""

import logging
import time
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass
from enum import Enum

# Configure module logger
logger = logging.getLogger("TECMP.Controllers")

# Import the new UI controller
try:
    from .tecmp_ui_controller import (
        TECMPUIController,
        TECMPControllerBase,
        ControllerState,
        OperationMode,
        ControllerConfiguration,
        PacketStatistics,
        EncapsulationContext,
        PerformanceMonitor,
        create_tecmp_ui_controller
    )
    CONTROLLER_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import TECMP UI Controller: {e}")
    CONTROLLER_AVAILABLE = False
    
    # Minimal fallback
    class TECMPUIController:
        def __init__(self, *args, **kwargs):
            self.logger = logging.getLogger("TECMP.Fallback")
            self.logger.warning("Using fallback controller - limited functionality")
        
        def encapsulate_packet(self, packet_data):
            return None
        
        def get_state(self):
            return "FALLBACK"
        
        def shutdown(self):
            pass
    
    TECMPControllerBase = TECMPUIController
    ControllerState = OperationMode = ControllerConfiguration = type('Enum', (), {})
    
    def create_tecmp_ui_controller(*args, **kwargs):
        return TECMPUIController(*args, **kwargs)


# Global controller instance (singleton pattern)
_global_controller: Optional[TECMPUIController] = None


def get_or_create_controller(parent=None, 
                           mode: str = "professional",
                           device_id: int = 0x0040,
                           force_new: bool = False) -> TECMPUIController:
    """
    Get or create global TECMP controller instance.
    
    Args:
        parent: Parent widget for Qt integration
        mode: Operation mode (basic, standard, professional, automotive)
        device_id: TECMP device identifier
        force_new: Force creation of new instance
        
    Returns:
        TECMPUIController instance
    """
    global _global_controller
    
    if force_new or _global_controller is None:
        logger.info(f"Creating new TECMP controller - Mode: {mode}, Device: 0x{device_id:04X}")
        
        _global_controller = create_tecmp_ui_controller(
            parent=parent,
            mode=mode,
            device_id=device_id
        )
        
        # Register cleanup on exit
        import atexit
        atexit.register(cleanup_global_controller)
    
    return _global_controller


def init_tecmp_system(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize complete TECMP system with configuration.
    
    Args:
        config: System configuration dictionary
        
    Returns:
        Initialization result with status and controller reference
    """
    start_time = time.time()
    result = {
        'success': False,
        'controller': None,
        'errors': [],
        'warnings': [],
        'init_time': 0.0
    }
    
    try:
        # Default configuration
        default_config = {
            'mode': 'professional',
            'device_id': 0x0040,
            'parent': None,
            'enable_validation': True,
            'enable_coherence': True,
            'enable_professional': True,
            'enable_time_sync': True,
            'enable_hw_monitoring': True,
            'enable_monitoring': True,
            'auto_refresh_ms': 100,
            'thread_pool_size': 4,
            'cache_size': 10000,
            'max_packet_history': 1000
        }
        
        # Merge user configuration
        if config:
            default_config.update(config)
        
        # Extract core parameters
        mode = default_config.pop('mode')
        device_id = default_config.pop('device_id')
        parent = default_config.pop('parent', None)
        
        # Create controller configuration
        controller_config = ControllerConfiguration(
            mode=OperationMode[mode.upper()] if CONTROLLER_AVAILABLE else None,
            device_id=device_id
        )
        
        # Apply configuration settings
        for key, value in default_config.items():
            if hasattr(controller_config, key):
                setattr(controller_config, key, value)
        
        # Create controller
        controller = TECMPUIController(parent=parent, config=controller_config)
        
        # Store globally
        global _global_controller
        _global_controller = controller
        
        # Verify initialization
        if hasattr(controller, 'get_state'):
            state = controller.get_state()
            if state == 'READY':
                result['success'] = True
                result['controller'] = controller
                logger.info(f"TECMP system initialized successfully - State: {state}")
            else:
                result['errors'].append(f"Controller in unexpected state: {state}")
        
        # Check for warnings
        if not CONTROLLER_AVAILABLE:
            result['warnings'].append("Running with fallback controller - limited functionality")
        
        # Get initialization statistics
        if hasattr(controller, 'get_statistics'):
            stats = controller.get_statistics()
            logger.debug(f"Initial statistics: {stats}")
        
    except Exception as e:
        logger.error(f"TECMP system initialization failed: {e}", exc_info=True)
        result['errors'].append(str(e))
    
    finally:
        result['init_time'] = time.time() - start_time
        logger.info(f"TECMP initialization completed in {result['init_time']:.3f}s")
    
    return result


def create_packet(packet_data: Dict[str, Any]) -> Optional[Any]:
    """
    Create TECMP packet using global controller.
    
    Args:
        packet_data: Packet configuration
        
    Returns:
        TECMP packet or None
    """
    controller = get_or_create_controller()
    
    if controller and hasattr(controller, 'encapsulate_packet'):
        return controller.encapsulate_packet(packet_data)
    
    return None


def validate_packet(packet: Any) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate TECMP packet.
    
    Args:
        packet: TECMP packet to validate
        
    Returns:
        Tuple of (is_valid, validation_report)
    """
    controller = get_or_create_controller()
    
    if controller and hasattr(controller, 'validate_packet'):
        return controller.validate_packet(packet)
    
    return False, {'error': 'Validation not available'}


def get_controller_status() -> Dict[str, Any]:
    """
    Get current controller status.
    
    Returns:
        Status dictionary
    """
    if _global_controller:
        try:
            return {
                'available': True,
                'state': _global_controller.get_state() if hasattr(_global_controller, 'get_state') else 'UNKNOWN',
                'statistics': _global_controller.get_statistics() if hasattr(_global_controller, 'get_statistics') else {},
                'engine_status': _global_controller.get_engine_status() if hasattr(_global_controller, 'get_engine_status') else {}
            }
        except Exception as e:
            return {'available': True, 'error': str(e)}
    
    return {'available': False, 'error': 'Controller not initialized'}


def cleanup_global_controller():
    """Cleanup global controller instance."""
    global _global_controller
    
    if _global_controller:
        try:
            logger.info("Cleaning up global TECMP controller...")
            _global_controller.shutdown()
            _global_controller = None
            logger.info("Global TECMP controller cleaned up")
        except Exception as e:
            logger.error(f"Error during controller cleanup: {e}")


# Compatibility layer for old code
class TECMPController:
    """Compatibility wrapper for old TECMPController usage."""
    
    def __init__(self, *args, **kwargs):
        self._controller = get_or_create_controller()
        logger.warning("Using compatibility wrapper for TECMPController - consider updating to TECMPUIController")
    
    def add_tecmp_encapsulation(self, protocols, tecmp_config=None, ethernet_config=None):
        """Legacy method - redirects to new API."""
        packet_data = {
            'mode': 'standard',
            'params': tecmp_config or {}
        }
        
        packet = self._controller.encapsulate_packet(packet_data)
        return packet is not None
    
    def remove_tecmp_encapsulation(self):
        """Legacy method - redirects to new API."""
        if hasattr(self._controller, 'clear_history'):
            self._controller.clear_history()
        return True
    
    def get_encapsulation_state(self):
        """Legacy method - redirects to new API."""
        state = self._controller.get_state()
        # Map new states to old EncapsulationState enum values
        state_map = {
            'READY': 'INACTIVE',
            'ACTIVE': 'ACTIVE',
            'PROCESSING': 'PENDING',
            'ERROR': 'ERROR'
        }
        return state_map.get(state, 'INACTIVE')
    
    def is_encapsulation_active(self):
        """Legacy method - redirects to new API."""
        return self._controller.get_state() == 'ACTIVE'


# Compatibility aliases
TECMPEncapsulationManager = TECMPController
create_tecmp_encapsulation_manager = lambda: TECMPController()
create_tecmp_controller = lambda *args, **kwargs: TECMPController(*args, **kwargs)


# Module exports
__all__ = [
    # New controller system
    'TECMPUIController',
    'TECMPControllerBase',
    'ControllerState',
    'OperationMode',
    'ControllerConfiguration',
    'PacketStatistics',
    'EncapsulationContext',
    'PerformanceMonitor',
    
    # Factory functions
    'create_tecmp_ui_controller',
    'get_or_create_controller',
    'init_tecmp_system',
    
    # High-level APIs
    'create_packet',
    'validate_packet',
    'get_controller_status',
    'cleanup_global_controller',
    
    # Compatibility layer
    'TECMPController',
    'TECMPEncapsulationManager',
    'create_tecmp_controller',
    'create_tecmp_encapsulation_manager',
    
    # Status flag
    'CONTROLLER_AVAILABLE'
]


# Auto-initialization for convenience
if __name__ != "__main__":
    # Log module loading
    if CONTROLLER_AVAILABLE:
        logger.info("TECMP Controllers module loaded successfully")
    else:
        logger.warning("TECMP Controllers module loaded with limited functionality")
