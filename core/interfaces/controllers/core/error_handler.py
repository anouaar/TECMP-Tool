#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
error_handler.py - TECMP-Tool Professional Error Handler
=======================================================

Comprehensive error handling system designed specifically for TECMP-Tool.
Integrates seamlessly with the factory pattern and provides:
- Context-aware error handling
- Automatic recovery strategies
- Performance impact monitoring
- Thread-safe operation
- Qt signal integration with fallbacks
"""

import logging
import traceback
import time
import threading
import weakref
from typing import Any, Dict, List, Optional, Callable, Union, Type
from enum import Enum, auto
from dataclasses import dataclass, field
from contextlib import contextmanager
from collections import deque
import sys
import os

# Qt imports with fallbacks (matching factory pattern)
try:
    from PyQt5.QtCore import QObject, pyqtSignal
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    
    class QObject:
        def __init__(self, parent=None):
            pass
    
    def pyqtSignal(*args):
        class Signal:
            def emit(self, *args, **kwargs):
                pass
            def connect(self, func):
                pass
        return Signal()

# ============================================================================
# ERROR CATEGORIES AND TYPES
# ============================================================================

class ErrorSeverity(Enum):
    """Error severity levels"""
    INFO = 0
    WARNING = 1
    ERROR = 2
    CRITICAL = 3
    FATAL = 4

class ErrorCategory(Enum):
    """Error categories for TECMP operations"""
    PACKET_CREATION = auto()
    PACKET_VALIDATION = auto()
    PROTOCOL_DETECTION = auto()
    FEATURE_INJECTION = auto()
    COHERENCE_CHECK = auto()
    ENGINE_OPERATION = auto()
    FACTORY_OPERATION = auto()
    NETWORK_OPERATION = auto()
    FILE_OPERATION = auto()
    CONFIGURATION = auto()
    PERFORMANCE = auto()
    MEMORY = auto()
    THREADING = auto()
    UNKNOWN = auto()

@dataclass
class ErrorContext:
    """Context information for errors"""
    category: ErrorCategory
    severity: ErrorSeverity
    operation: str
    component: str
    thread_id: int = field(default_factory=lambda: threading.get_ident())
    timestamp: float = field(default_factory=time.time)
    additional_info: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False

@dataclass
class ErrorStatistics:
    """Error statistics tracking"""
    total_errors: int = 0
    errors_by_category: Dict[ErrorCategory, int] = field(default_factory=dict)
    errors_by_severity: Dict[ErrorSeverity, int] = field(default_factory=dict)
    recovery_attempts: int = 0
    successful_recoveries: int = 0
    performance_impact_ms: float = 0.0
    last_error_time: Optional[float] = None

# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class TECMPError(Exception):
    """Base exception for TECMP operations"""
    def __init__(self, message: str, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.context = context or ErrorContext(
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.ERROR,
            operation="unknown",
            component="unknown"
        )

class PacketCreationError(TECMPError):
    """Error during packet creation"""
    def __init__(self, message: str, **kwargs):
        context = ErrorContext(
            category=ErrorCategory.PACKET_CREATION,
            severity=ErrorSeverity.ERROR,
            operation=kwargs.get('operation', 'create_packet'),
            component=kwargs.get('component', 'TECMPFactory'),
            additional_info=kwargs
        )
        super().__init__(message, context)

class ValidationError(TECMPError):
    """Error during validation"""
    def __init__(self, message: str, violations: List[str] = None, **kwargs):
        context = ErrorContext(
            category=ErrorCategory.PACKET_VALIDATION,
            severity=ErrorSeverity.WARNING,
            operation=kwargs.get('operation', 'validate'),
            component=kwargs.get('component', 'Validator'),
            additional_info={'violations': violations or [], **kwargs}
        )
        super().__init__(message, context)

class EngineError(TECMPError):
    """Error in professional engine operations"""
    def __init__(self, message: str, engine_type: str = "unknown", **kwargs):
        context = ErrorContext(
            category=ErrorCategory.ENGINE_OPERATION,
            severity=ErrorSeverity.ERROR,
            operation=kwargs.get('operation', 'engine_operation'),
            component=f"{engine_type}_engine",
            additional_info=kwargs
        )
        super().__init__(message, context)

class CoherenceError(TECMPError):
    """Error in coherence checking"""
    def __init__(self, message: str, violations: List[str] = None, **kwargs):
        context = ErrorContext(
            category=ErrorCategory.COHERENCE_CHECK,
            severity=ErrorSeverity.WARNING,
            operation=kwargs.get('operation', 'coherence_check'),
            component='CoherenceEngine',
            additional_info={'violations': violations or [], **kwargs}
        )
        super().__init__(message, context)

# ============================================================================
# ERROR RECOVERY STRATEGIES
# ============================================================================

class RecoveryStrategy:
    """Base class for error recovery strategies"""
    
    def can_recover(self, error: Exception, context: ErrorContext) -> bool:
        """Check if this strategy can recover from the error"""
        return False
    
    def recover(self, error: Exception, context: ErrorContext) -> Any:
        """Attempt to recover from the error"""
        raise NotImplementedError

class RetryStrategy(RecoveryStrategy):
    """Retry operation with exponential backoff"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 0.1):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    def can_recover(self, error: Exception, context: ErrorContext) -> bool:
        return (context.category in [ErrorCategory.NETWORK_OPERATION, 
                                   ErrorCategory.ENGINE_OPERATION] and
                context.additional_info.get('retry_count', 0) < self.max_retries)
    
    def recover(self, error: Exception, context: ErrorContext) -> Any:
        retry_count = context.additional_info.get('retry_count', 0)
        delay = self.base_delay * (2 ** retry_count)
        time.sleep(delay)
        context.additional_info['retry_count'] = retry_count + 1
        return None  # Signal to retry operation

class FallbackStrategy(RecoveryStrategy):
    """Use fallback values or methods"""
    
    def __init__(self, fallback_values: Dict[str, Any] = None):
        self.fallback_values = fallback_values or {}
    
    def can_recover(self, error: Exception, context: ErrorContext) -> bool:
        return context.category in [ErrorCategory.PACKET_CREATION,
                                  ErrorCategory.PROTOCOL_DETECTION]
    
    def recover(self, error: Exception, context: ErrorContext) -> Any:
        operation = context.operation
        if operation in self.fallback_values:
            return self.fallback_values[operation]
        
        # Default fallbacks
        if context.category == ErrorCategory.PROTOCOL_DETECTION:
            return 0x0080  # Default to Ethernet
        elif context.category == ErrorCategory.PACKET_CREATION:
            return None  # Signal to create minimal packet
        
        return None

class AutoFixStrategy(RecoveryStrategy):
    """Automatically fix validation/coherence errors"""
    
    def can_recover(self, error: Exception, context: ErrorContext) -> bool:
        return (context.category in [ErrorCategory.PACKET_VALIDATION,
                                   ErrorCategory.COHERENCE_CHECK] and
                isinstance(error, (ValidationError, CoherenceError)))
    
    def recover(self, error: Exception, context: ErrorContext) -> Any:
        if hasattr(error, 'context') and 'packet' in context.additional_info:
            packet = context.additional_info['packet']
            if hasattr(packet, 'auto_fix_violations'):
                packet.auto_fix_violations(apply=True)
                return packet
        return None

# ============================================================================
# MAIN ERROR HANDLER CLASS
# ============================================================================

class TECMPErrorHandler(QObject if QT_AVAILABLE else object):
    """
    Comprehensive error handler for TECMP-Tool
    
    Features:
    - Centralized error handling with context
    - Automatic recovery strategies
    - Performance impact tracking
    - Thread-safe operation
    - Qt signal integration
    - Detailed error logging and statistics
    """
    
    # Qt signals (if available)
    if QT_AVAILABLE:
        error_occurred = pyqtSignal(str, str, dict)  # component, message, context
        warning_occurred = pyqtSignal(str, str, dict)
        recovery_attempted = pyqtSignal(str, bool)  # error_message, success
        critical_error = pyqtSignal(str, str)
    
    def __init__(self, logger: Optional[logging.Logger] = None,
                 enable_recovery: bool = True,
                 enable_statistics: bool = True):
        """
        Initialize error handler
        
        Args:
            logger: Logger instance (creates one if not provided)
            enable_recovery: Enable automatic recovery strategies
            enable_statistics: Enable error statistics tracking
        """
        if QT_AVAILABLE:
            super().__init__()
        
        self.logger = logger or logging.getLogger("TECMP-Tool.ErrorHandler")
        self.enable_recovery = enable_recovery
        self.enable_statistics = enable_statistics
        
        # Error tracking
        self._error_history = deque(maxlen=1000)
        self._statistics = ErrorStatistics()
        self._lock = threading.RLock()
        
        # Recovery strategies
        self._recovery_strategies = [
            RetryStrategy(),
            FallbackStrategy(),
            AutoFixStrategy()
        ]
        
        # Component error handlers
        self._component_handlers: Dict[str, Callable] = {}
        
        # Performance tracking
        self._performance_threshold_ms = 100.0
        
        # Fallback Qt signals if not available
        if not QT_AVAILABLE:
            self.error_occurred = self._create_mock_signal()
            self.warning_occurred = self._create_mock_signal()
            self.recovery_attempted = self._create_mock_signal()
            self.critical_error = self._create_mock_signal()
    
    def _create_mock_signal(self):
        """Create mock signal for non-Qt environments"""
        class MockSignal:
            def emit(self, *args, **kwargs):
                pass
            def connect(self, func):
                pass
        return MockSignal()
    
    # ========================================================================
    # ERROR HANDLING METHODS
    # ========================================================================
    
    def handle_error(self, error: Exception, component: str = "Unknown",
                    operation: str = "Unknown", **context_info) -> Any:
        """
        Main error handling method
        
        Args:
            error: The exception that occurred
            component: Component where error occurred
            operation: Operation being performed
            **context_info: Additional context information
            
        Returns:
            Recovery result or None
        """
        start_time = time.perf_counter()
        
        with self._lock:
            try:
                # Create error context
                context = self._create_error_context(error, component, operation, context_info)
                
                # Log the error
                self._log_error(error, context)
                
                # Update statistics
                if self.enable_statistics:
                    self._update_statistics(context)
                
                # Store in history
                self._error_history.append({
                    'error': error,
                    'context': context,
                    'timestamp': time.time()
                })
                
                # Emit signals
                self._emit_error_signals(error, context)
                
                # Attempt recovery
                recovery_result = None
                if self.enable_recovery:
                    recovery_result = self._attempt_recovery(error, context)
                
                # Track performance impact
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                if elapsed_ms > self._performance_threshold_ms:
                    self.logger.warning(f"Error handling took {elapsed_ms:.2f}ms")
                
                return recovery_result
                
            except Exception as handler_error:
                # Error in error handler - log and continue
                self.logger.critical(f"Error in error handler: {handler_error}")
                return None
    
    def _create_error_context(self, error: Exception, component: str,
                            operation: str, context_info: Dict) -> ErrorContext:
        """Create error context from exception and info"""
        # Determine category and severity
        category = ErrorCategory.UNKNOWN
        severity = ErrorSeverity.ERROR
        
        if isinstance(error, TECMPError):
            return error.context
        
        # Categorize based on error type
        if isinstance(error, (ValueError, TypeError)):
            category = ErrorCategory.PACKET_VALIDATION
            severity = ErrorSeverity.WARNING
        elif isinstance(error, OSError):
            category = ErrorCategory.FILE_OPERATION
        elif isinstance(error, MemoryError):
            category = ErrorCategory.MEMORY
            severity = ErrorSeverity.CRITICAL
        elif isinstance(error, RuntimeError):
            if "thread" in str(error).lower():
                category = ErrorCategory.THREADING
        
        # Create context
        return ErrorContext(
            category=category,
            severity=severity,
            operation=operation,
            component=component,
            stack_trace=traceback.format_exc(),
            additional_info=context_info
        )
    
    def _log_error(self, error: Exception, context: ErrorContext):
        """Log error with appropriate level"""
        message = f"[{context.component}] {context.operation}: {str(error)}"
        
        if context.severity == ErrorSeverity.INFO:
            self.logger.info(message)
        elif context.severity == ErrorSeverity.WARNING:
            self.logger.warning(message)
        elif context.severity == ErrorSeverity.ERROR:
            self.logger.error(message, exc_info=True)
        elif context.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
            self.logger.critical(message, exc_info=True)
    
    def _emit_error_signals(self, error: Exception, context: ErrorContext):
        """Emit Qt signals for error events"""
        try:
            context_dict = {
                'category': context.category.name,
                'severity': context.severity.name,
                'operation': context.operation,
                'thread_id': context.thread_id,
                'additional_info': context.additional_info
            }
            
            if context.severity == ErrorSeverity.WARNING:
                self.warning_occurred.emit(context.component, str(error), context_dict)
            elif context.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
                self.critical_error.emit(context.component, str(error))
            else:
                self.error_occurred.emit(context.component, str(error), context_dict)
                
        except Exception:
            # Ignore signal emission errors
            pass
    
    def _attempt_recovery(self, error: Exception, context: ErrorContext) -> Any:
        """Attempt to recover from error using strategies"""
        for strategy in self._recovery_strategies:
            if strategy.can_recover(error, context):
                try:
                    self.logger.debug(f"Attempting recovery with {strategy.__class__.__name__}")
                    context.recovery_attempted = True
                    
                    result = strategy.recover(error, context)
                    
                    context.recovery_successful = True
                    self._statistics.successful_recoveries += 1
                    
                    self.recovery_attempted.emit(str(error), True)
                    self.logger.info(f"Successfully recovered from {error.__class__.__name__}")
                    
                    return result
                    
                except Exception as recovery_error:
                    self.logger.warning(f"Recovery strategy failed: {recovery_error}")
                    
                finally:
                    self._statistics.recovery_attempts += 1
        
        self.recovery_attempted.emit(str(error), False)
        return None
    
    def _update_statistics(self, context: ErrorContext):
        """Update error statistics"""
        self._statistics.total_errors += 1
        self._statistics.last_error_time = context.timestamp
        
        # Count by category
        if context.category not in self._statistics.errors_by_category:
            self._statistics.errors_by_category[context.category] = 0
        self._statistics.errors_by_category[context.category] += 1
        
        # Count by severity
        if context.severity not in self._statistics.errors_by_severity:
            self._statistics.errors_by_severity[context.severity] = 0
        self._statistics.errors_by_severity[context.severity] += 1
    
    # ========================================================================
    # CONTEXT MANAGERS
    # ========================================================================
    
    @contextmanager
    def error_context(self, component: str, operation: str, **context_info):
        """
        Context manager for error handling
        
        Usage:
            with error_handler.error_context("Factory", "create_packet"):
                # Code that might raise exceptions
                packet = factory.create_packet()
        """
        try:
            yield
        except Exception as e:
            self.handle_error(e, component, operation, **context_info)
            raise
    
    @contextmanager
    def suppress_errors(self, component: str, operation: str,
                       default_value: Any = None, **context_info):
        """
        Context manager that suppresses errors and returns default
        
        Usage:
            with error_handler.suppress_errors("Factory", "detect_protocol", 
                                             default_value=DataType.ETHERNET_II):
                detected_type = factory.detect_data_type(protocols)
        """
        try:
            yield
        except Exception as e:
            result = self.handle_error(e, component, operation, **context_info)
            return result if result is not None else default_value
    
    # ========================================================================
    # DECORATORS
    # ========================================================================
    
    def handle_errors(self, component: str = None, operation: str = None,
                     reraise: bool = True, default_value: Any = None):
        """
        Decorator for automatic error handling
        
        Usage:
            @error_handler.handle_errors("Factory", "create_packet")
            def create_packet(self, **kwargs):
                # Method implementation
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                comp = component or func.__module__
                op = operation or func.__name__
                
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    result = self.handle_error(e, comp, op, 
                                             function=func.__name__,
                                             args=str(args)[:100],
                                             kwargs=str(kwargs)[:100])
                    
                    if reraise and result is None:
                        raise
                    
                    return result if result is not None else default_value
            
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        
        return decorator
    
    # ========================================================================
    # COMPONENT REGISTRATION
    # ========================================================================
    
    def register_component_handler(self, component: str, 
                                 handler: Callable[[Exception, ErrorContext], Any]):
        """Register custom error handler for specific component"""
        self._component_handlers[component] = handler
        self.logger.debug(f"Registered error handler for component: {component}")
    
    def unregister_component_handler(self, component: str):
        """Unregister component error handler"""
        if component in self._component_handlers:
            del self._component_handlers[component]
            self.logger.debug(f"Unregistered error handler for component: {component}")
    
    # ========================================================================
    # STATISTICS AND REPORTING
    # ========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get error statistics"""
        with self._lock:
            return {
                'total_errors': self._statistics.total_errors,
                'errors_by_category': {
                    cat.name: count 
                    for cat, count in self._statistics.errors_by_category.items()
                },
                'errors_by_severity': {
                    sev.name: count 
                    for sev, count in self._statistics.errors_by_severity.items()
                },
                'recovery_attempts': self._statistics.recovery_attempts,
                'successful_recoveries': self._statistics.successful_recoveries,
                'recovery_rate': (self._statistics.successful_recoveries / 
                                self._statistics.recovery_attempts * 100
                                if self._statistics.recovery_attempts > 0 else 0),
                'last_error_time': self._statistics.last_error_time,
                'performance_impact_ms': self._statistics.performance_impact_ms
            }
    
    def get_error_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent error history"""
        with self._lock:
            history = []
            for entry in list(self._error_history)[-limit:]:
                context = entry['context']
                history.append({
                    'timestamp': entry['timestamp'],
                    'error_type': entry['error'].__class__.__name__,
                    'message': str(entry['error']),
                    'component': context.component,
                    'operation': context.operation,
                    'category': context.category.name,
                    'severity': context.severity.name,
                    'recovery_attempted': context.recovery_attempted,
                    'recovery_successful': context.recovery_successful
                })
            return history
    
    def clear_statistics(self):
        """Clear error statistics"""
        with self._lock:
            self._statistics = ErrorStatistics()
            self._error_history.clear()
            self.logger.info("Error statistics cleared")
    
    # ========================================================================
    # FACTORY INTEGRATION HELPERS
    # ========================================================================
    
    def wrap_factory_method(self, factory_instance, method_name: str):
        """Wrap factory method with error handling"""
        original_method = getattr(factory_instance, method_name)
        
        @self.handle_errors(factory_instance.__class__.__name__, method_name)
        def wrapped_method(*args, **kwargs):
            return original_method(*args, **kwargs)
        
        setattr(factory_instance, method_name, wrapped_method)
        self.logger.debug(f"Wrapped factory method: {method_name}")
    
    def integrate_with_factory(self, factory_instance):
        """Full integration with TECMP factory"""
        # Wrap critical methods
        critical_methods = [
            'create_packet',
            'create_with_auto_detection',
            'create_automotive_packet',
            'detect_data_type',
            '_apply_professional_enhancements',
            '_apply_feature_injection',
            '_apply_validation_and_coherence'
        ]
        
        for method in critical_methods:
            if hasattr(factory_instance, method):
                self.wrap_factory_method(factory_instance, method)
        
        # Register as factory error handler
        if hasattr(factory_instance, 'error_handler'):
            factory_instance.error_handler = self
        
        self.logger.info("Error handler integrated with TECMP factory")

# ============================================================================
# SINGLETON INSTANCE AND HELPERS
# ============================================================================

_global_error_handler = None

def get_error_handler() -> TECMPErrorHandler:
    """Get or create global error handler instance"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = TECMPErrorHandler()
    return _global_error_handler

def handle_tecmp_error(error: Exception, component: str = "TECMP",
                      operation: str = "Unknown", **context) -> Any:
    """Quick error handling function"""
    return get_error_handler().handle_error(error, component, operation, **context)

# Decorator shorthand
handle_errors = get_error_handler().handle_errors

# ============================================================================
# FACADE INTEGRATION
# ============================================================================

def integrate_error_handler_with_facade(facade_instance):
    """
    Integrate error handler with TECMP facade
    
    Args:
        facade_instance: TECMPFacade instance
    """
    handler = get_error_handler()
    
    # Register facade-specific handlers
    def facade_error_handler(error: Exception, context: ErrorContext):
        # Custom facade error handling logic
        if context.category == ErrorCategory.PACKET_CREATION:
            # Try to create minimal packet
            try:
                from core.packets.tecmp.tecmp_packet import TECMPPacket
                return TECMPPacket()
            except:
                return None
        return None
    
    handler.register_component_handler("TECMPFacade", facade_error_handler)
    
    # Connect Qt signals if available
    if hasattr(facade_instance, 'error_occurred'):
        handler.error_occurred.connect(
            lambda comp, msg, ctx: facade_instance.error_occurred.emit(msg)
        )
    
    # Set as facade error handler
    if hasattr(facade_instance, '_error_handler'):
        facade_instance._error_handler = handler
    
    return handler

# Export public API
__all__ = [
    # Main classes
    'TECMPErrorHandler',
    'TECMPError',
    'PacketCreationError',
    'ValidationError',
    'EngineError',
    'CoherenceError',
    
    # Enums
    'ErrorSeverity',
    'ErrorCategory',
    'ErrorContext',
    
    # Functions
    'get_error_handler',
    'handle_tecmp_error',
    'handle_errors',
    'integrate_error_handler_with_facade',
    
    # Recovery strategies
    'RecoveryStrategy',
    'RetryStrategy',
    'FallbackStrategy',
    'AutoFixStrategy'
]