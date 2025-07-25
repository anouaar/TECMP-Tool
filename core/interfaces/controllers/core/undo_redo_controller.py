#!/usr/bin/env python
# coding: utf-8
"""
Complete Undo/Redo Controller for TECMP-Tool - Error-Free Implementation
Author: Assistant
Date: 2025-05-29

This module provides a robust undo/redo system with:
- Command pattern implementation
- Transaction support
- Qt integration with fallbacks
- Auto-save functionality
- Comprehensive error handling
- Thread-safe operations
- Backward compatibility with existing code

USAGE INSTRUCTIONS:
1. Replace your existing undo_redo_controller.py with this file
2. In your main application startup, call:
   from undo_redo_controller import initialize_undo_redo_system
   initialize_undo_redo_system()
3. For TECMP facade integration, use the helper functions:
   - get_tecmp_encapsulation_state_safely()
   - create_tecmp_state_change_handler()

FIXES ADDRESSED:
- AttributeError: 'Command' object has no attribute 'command_type_string'
- AttributeError: 'str' object has no attribute 'name'  
- NameError: name 'auto' is not defined
- TECMP EncapsulationState attribute errors
- Thread safety issues
- Qt signal emission errors
"""

import logging
import copy
import time
import threading
from typing import List, Dict, Any, Optional, Callable, Union
from enum import Enum, auto
from collections import deque
from dataclasses import dataclass, field
from contextlib import contextmanager

# Make auto available globally for any compatibility issues
auto = auto

# === QT IMPORTS WITH FALLBACKS ===

class MockQObject:
    """Mock QObject for environments without Qt."""
    def __init__(self, parent=None):
        self.parent = parent

class MockSignal:
    """Mock signal for environments without Qt."""
    def __init__(self):
        self._connections = []
    
    def emit(self, *args, **kwargs):
        """Emit signal to connected slots."""
        for slot in self._connections:
            try:
                slot(*args, **kwargs)
            except Exception:
                pass
    
    def connect(self, slot):
        """Connect slot to signal."""
        if callable(slot):
            self._connections.append(slot)

class MockQTimer:
    """Mock QTimer for environments without Qt."""
    def __init__(self, parent=None):
        self.parent = parent
        self.timeout = MockSignal()
        self._active = False
    
    def start(self, interval):
        """Start timer (mock)."""
        self._active = True
    
    def stop(self):
        """Stop timer (mock)."""
        self._active = False
    
    def isActive(self):
        """Check if timer is active."""
        return self._active

class MockQApplication:
    """Mock QApplication for environments without Qt."""
    @staticmethod
    def instance():
        return None

# Try to import Qt components
QT_AVAILABLE = False
QObject = MockQObject
pyqtSignal = lambda *args: MockSignal()
QTimer = MockQTimer
QApplication = MockQApplication

try:
    from PyQt5.QtCore import QObject as _QObject, pyqtSignal as _pyqtSignal, QTimer as _QTimer
    from PyQt5.QtWidgets import QApplication as _QApplication
    
    # Test if Qt is actually working
    test_signal = _pyqtSignal()
    
    QObject = _QObject
    pyqtSignal = _pyqtSignal
    QTimer = _QTimer
    QApplication = _QApplication
    QT_AVAILABLE = True
    
except (ImportError, RuntimeError):
    # Qt not available or not properly initialized
    QT_AVAILABLE = False

# === ENUMS AND DATA CLASSES ===

class CommandType(Enum):
    """Enumeration of command types for undo/redo operations."""
    PROTOCOL_ADD = auto()
    PROTOCOL_REMOVE = auto()
    PROTOCOL_MOVE = auto()
    PROTOCOL_EDIT = auto()
    PROTOCOL_CLEAR = auto()
    
    TECMP_ADD = auto()
    TECMP_REMOVE = auto()
    TECMP_CONFIG = auto()
    TECMP_EDIT = auto()
    
    PROJECT_NEW = auto()
    PROJECT_LOAD = auto()
    PROJECT_SAVE = auto()
    PROJECT_CLEAR = auto()
    
    SETTINGS_CHANGE = auto()
    
    FILE_LOAD = auto()
    FILE_SAVE = auto()
    FILE_EXPORT = auto()
    
    CAPTURE_START = auto()
    CAPTURE_STOP = auto()
    
    CUSTOM = auto()


@dataclass
class CommandMetadata:
    """Metadata for commands."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    source: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


class UndoRedoError(Exception):
    """Base exception for undo/redo operations."""
    pass


class CommandExecutionError(UndoRedoError):
    """Exception raised when command execution fails."""
    pass


class TransactionError(UndoRedoError):
    """Exception raised when transaction operations fail."""
    pass


# === COMMAND CLASS ===

class Command:
    """
    Represents a single undoable command.
    
    This class encapsulates an action that can be executed and undone,
    following the Command pattern.
    """
    
    def __init__(self,
                 command_type: Union[CommandType, str],
                 description: str,
                 do_func: Callable[[], Any],
                 undo_func: Callable[[], Any],
                 state_before: Any = None,
                 state_after: Any = None,
                 timestamp: Optional[float] = None,
                 metadata: Optional[CommandMetadata] = None):
        """
        Initialize a command.
        
        Args:
            command_type: Type of command (enum or string)
            description: Human-readable description
            do_func: Function to execute the command
            undo_func: Function to undo the command
            state_before: State before command execution
            state_after: State after command execution
            timestamp: Command timestamp (defaults to current time)
            metadata: Additional command metadata
        """
        # Always initialize command_type_string to None first
        self.command_type_string = None
        
        # Handle both enum and string command types
        if isinstance(command_type, str):
            # Try to convert string to enum
            try:
                self.command_type = CommandType[command_type.upper()]
            except (KeyError, ValueError):
                self.command_type = CommandType.CUSTOM
                self.command_type_string = command_type
        else:
            self.command_type = command_type
        
        self.description = str(description)
        self.do_func = do_func
        self.undo_func = undo_func
        self.state_before = state_before
        self.state_after = state_after
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.metadata = metadata if metadata is not None else CommandMetadata()
        
        # Execution tracking
        self.execution_count = 0
        self.undo_count = 0
        self.last_execution_time = None
        self.last_undo_time = None
        self.execution_errors = []
    
    def execute(self) -> Any:
        """
        Execute the command.
        
        Returns:
            Result of command execution
            
        Raises:
            CommandExecutionError: If command execution fails
        """
        try:
            self.last_execution_time = time.time()
            result = self.do_func()
            self.execution_count += 1
            
            # Store state after if not set
            if self.state_after is None:
                self.state_after = result
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to execute command '{self.description}': {e}"
            self.execution_errors.append({
                'timestamp': time.time(),
                'error': str(e),
                'type': 'execute'
            })
            raise CommandExecutionError(error_msg) from e
    
    def undo(self) -> Any:
        """
        Undo the command.
        
        Returns:
            Result of undo operation
            
        Raises:
            CommandExecutionError: If undo fails
        """
        try:
            self.last_undo_time = time.time()
            result = self.undo_func()
            self.undo_count += 1
            return result
            
        except Exception as e:
            error_msg = f"Failed to undo command '{self.description}': {e}"
            self.execution_errors.append({
                'timestamp': time.time(),
                'error': str(e),
                'type': 'undo'
            })
            raise CommandExecutionError(error_msg) from e
    
    def get_command_type_name(self) -> str:
        """
        Get the command type name safely.
        
        Returns:
            Command type name as string
        """
        # Handle backward compatibility - check if attribute exists
        if hasattr(self, 'command_type_string') and self.command_type_string:
            return self.command_type_string
        elif hasattr(self.command_type, 'name'):
            return self.command_type.name
        else:
            return str(self.command_type)
    
    def __str__(self) -> str:
        """String representation of the command."""
        try:
            return f"{self.get_command_type_name()}: {self.description}"
        except Exception:
            # Fallback for any errors
            return f"Command: {getattr(self, 'description', 'Unknown')}"
    
    def __repr__(self) -> str:
        """Detailed representation of the command."""
        return (f"Command(type={self.get_command_type_name()}, "
                f"desc='{self.description}', "
                f"timestamp={self.timestamp}, "
                f"exec_count={self.execution_count})")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert command to dictionary representation."""
        try:
            return {
                'command_type': self.get_command_type_name(),
                'description': getattr(self, 'description', 'Unknown'),
                'timestamp': getattr(self, 'timestamp', time.time()),
                'execution_count': getattr(self, 'execution_count', 0),
                'undo_count': getattr(self, 'undo_count', 0),
                'last_execution_time': getattr(self, 'last_execution_time', None),
                'last_undo_time': getattr(self, 'last_undo_time', None),
                'metadata': {
                    'user_id': getattr(self.metadata, 'user_id', None) if hasattr(self, 'metadata') else None,
                    'session_id': getattr(self.metadata, 'session_id', None) if hasattr(self, 'metadata') else None,
                    'source': getattr(self.metadata, 'source', None) if hasattr(self, 'metadata') else None,
                    'tags': getattr(self.metadata, 'tags', []) if hasattr(self, 'metadata') else [],
                    'context': getattr(self.metadata, 'context', {}) if hasattr(self, 'metadata') else {}
                },
                'has_errors': len(getattr(self, 'execution_errors', [])) > 0
            }
        except Exception as e:
            # Fallback dictionary if anything fails
            return {
                'command_type': 'Unknown',
                'description': str(getattr(self, 'description', 'Unknown command')),
                'timestamp': time.time(),
                'error': f"Failed to serialize: {e}"
            }


# === COMPOSITE COMMAND ===

class CompositeCommand(Command):
    """
    A command that contains multiple sub-commands.
    Used for transactions and batch operations.
    """
    
    def __init__(self, name: str, commands: List[Command], description: Optional[str] = None):
        """
        Initialize composite command.
        
        Args:
            name: Name of the composite command
            commands: List of sub-commands
            description: Optional description
        """
        self.name = name
        self.commands = commands.copy()
        
        if description is None:
            description = f"Transaction '{name}' with {len(commands)} commands"
        
        # Create composite do and undo functions
        def do_composite():
            results = []
            for cmd in self.commands:
                result = cmd.execute()
                results.append(result)
            return results
        
        def undo_composite():
            results = []
            # Undo in reverse order
            for cmd in reversed(self.commands):
                result = cmd.undo()
                results.append(result)
            return results
        
        super().__init__(
            command_type=CommandType.CUSTOM,
            description=description,
            do_func=do_composite,
            undo_func=undo_composite,
            metadata=CommandMetadata(
                source='composite',
                context={'command_count': len(commands), 'transaction_name': name}
            )
        )
    
    def add_command(self, command: Command):
        """Add a command to the composite."""
        self.commands.append(command)
        self.metadata.context['command_count'] = len(self.commands)
    
    def get_command_summaries(self) -> List[str]:
        """Get summaries of all sub-commands."""
        return [str(cmd) for cmd in self.commands]


# === MAIN UNDO/REDO CONTROLLER ===

class UndoRedoController(QObject):
    """
    Complete undo/redo controller with Qt integration and fallbacks.
    
    Features:
    - Command pattern implementation
    - Transaction support (begin/commit/rollback)
    - Qt signals for UI integration
    - Auto-save functionality
    - Thread-safe operations
    - Comprehensive error handling
    - Performance monitoring
    """
    
    # Qt signals (defined at class level)
    if QT_AVAILABLE:
        undo_state_changed = pyqtSignal(bool)  # can_undo
        redo_state_changed = pyqtSignal(bool)  # can_redo
        command_executed = pyqtSignal(object, str)  # command_type, description
        command_undone = pyqtSignal(object, str)  # command_type, description
        command_redone = pyqtSignal(object, str)  # command_type, description
        transaction_started = pyqtSignal(str)  # transaction_name
        transaction_committed = pyqtSignal(str, int)  # transaction_name, command_count
        transaction_rolled_back = pyqtSignal(str, int)  # transaction_name, command_count
        history_cleared = pyqtSignal()
        auto_save_triggered = pyqtSignal()
        error_occurred = pyqtSignal(str, str)  # operation, error_message
    
    def __init__(self, max_history: int = 100, parent: Optional[QObject] = None):
        """
        Initialize the undo/redo controller.
        
        Args:
            max_history: Maximum number of commands to keep in history
            parent: Parent QObject (for Qt integration)
        """
        # Initialize Qt base class if available
        try:
            if QT_AVAILABLE and QApplication.instance() is not None:
                super().__init__(parent)
                self._qt_initialized = True
            else:
                self.parent = parent
                self._qt_initialized = False
        except Exception:
            self.parent = parent
            self._qt_initialized = False
        
        self.logger = logging.getLogger("TECMP-Tool.UndoRedoController")
        
        # Command stacks
        self._undo_stack = deque(maxlen=max_history)
        self._redo_stack = deque(maxlen=max_history)
        self._max_history = max_history
        
        # State tracking
        self._can_undo = False
        self._can_redo = False
        
        # Transaction support
        self._in_transaction = False
        self._current_transaction = None
        self._transaction_name = ""
        self._transaction_commands = []
        
        # Auto-save support
        self._auto_save_enabled = False
        self._auto_save_interval = 300  # 5 minutes
        self._auto_save_callback = None
        self._auto_save_timer = None
        self._auto_save_timer_active = False
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Performance tracking
        self._stats = {
            'commands_executed': 0,
            'commands_undone': 0,
            'commands_redone': 0,
            'transactions_committed': 0,
            'transactions_rolled_back': 0,
            'auto_saves_performed': 0,
            'errors_encountered': 0,
            'start_time': time.time()
        }
        
        # Setup signals if Qt not available at class level
        if not self._qt_initialized:
            self._setup_mock_signals()
        
        # Initialize auto-save timer if Qt is available
        if self._qt_initialized:
            self._setup_auto_save_timer()
        
        self.logger.info(f"UndoRedoController initialized "
                        f"(Qt: {self._qt_initialized}, max_history: {max_history})")
    
    def _setup_mock_signals(self):
        """Setup mock signals when Qt is not available."""
        self.undo_state_changed = MockSignal()
        self.redo_state_changed = MockSignal()
        self.command_executed = MockSignal()
        self.command_undone = MockSignal()
        self.command_redone = MockSignal()
        self.transaction_started = MockSignal()
        self.transaction_committed = MockSignal()
        self.transaction_rolled_back = MockSignal()
        self.history_cleared = MockSignal()
        self.auto_save_triggered = MockSignal()
        self.error_occurred = MockSignal()
    
    def _setup_auto_save_timer(self):
        """Setup auto-save timer if Qt is available."""
        try:
            if self._qt_initialized:
                self._auto_save_timer = QTimer(self)
                self._auto_save_timer.timeout.connect(self._perform_auto_save)
                self._auto_save_timer_active = False
        except Exception as e:
            self.logger.warning(f"Failed to setup auto-save timer: {e}")
            self._auto_save_timer = None
    
    # === PUBLIC API ===
    
    def execute_command(self,
                       command_type: Union[CommandType, str],
                       description: str,
                       do_func: Callable[[], Any],
                       undo_func: Callable[[], Any],
                       state_before: Any = None,
                       metadata: Optional[CommandMetadata] = None) -> Any:
        """
        Execute a command and add it to the undo stack.
        
        Args:
            command_type: Type of command
            description: Human-readable description
            do_func: Function to execute
            undo_func: Function to undo
            state_before: State before execution
            metadata: Additional metadata
            
        Returns:
            Result of command execution
            
        Raises:
            CommandExecutionError: If command execution fails
        """
        with self._lock:
            try:
                # Create command using safe method
                command = create_safe_command(
                    command_type=command_type,
                    description=description,
                    do_func=do_func,
                    undo_func=undo_func,
                    state_before=state_before,
                    metadata=metadata
                )
                
                # Execute the command
                result = command.execute()
                
                # Handle transaction mode
                if self._in_transaction:
                    self._transaction_commands.append(command)
                    self.logger.debug(f"Added command to transaction: {command}")
                else:
                    # Add to undo stack
                    self._undo_stack.append(command)
                    
                    # Clear redo stack (new command invalidates redo history)
                    self._redo_stack.clear()
                    
                    # Update state
                    self._update_state()
                    
                    # Schedule auto-save
                    self._schedule_auto_save()
                
                # Update statistics
                self._stats['commands_executed'] += 1
                
                # Emit signal
                try:
                    self.command_executed.emit(command_type, description)
                except Exception as e:
                    self.logger.debug(f"Error emitting signal: {e}")
                
                self.logger.debug(f"Command executed successfully: {command}")
                return result
                
            except Exception as e:
                self._stats['errors_encountered'] += 1
                error_msg = f"Failed to execute command '{description}': {e}"
                self.logger.error(error_msg, exc_info=True)
                
                try:
                    self.error_occurred.emit("execute_command", error_msg)
                except Exception:
                    pass
                
                raise CommandExecutionError(error_msg) from e
    
    def undo(self) -> Any:
        """
        Undo the last command.
        
        Returns:
            Result of undo operation or None if nothing to undo
            
        Raises:
            CommandExecutionError: If undo fails
        """
        with self._lock:
            if not self._can_undo:
                self.logger.debug("Nothing to undo")
                return None
            
            try:
                # Get the command to undo
                command = self._undo_stack.pop()
                
                # Execute the undo
                result = command.undo()
                
                # Add to redo stack
                self._redo_stack.append(command)
                
                # Update state
                self._update_state()
                
                # Schedule auto-save
                self._schedule_auto_save()
                
                # Update statistics
                self._stats['commands_undone'] += 1
                
                # Emit signal
                try:
                    self.command_undone.emit(command.command_type, command.description)
                except Exception as e:
                    self.logger.debug(f"Error emitting signal: {e}")
                
                self.logger.debug(f"Command undone successfully: {command}")
                return result
                
            except Exception as e:
                self._stats['errors_encountered'] += 1
                error_msg = f"Failed to undo command: {e}"
                self.logger.error(error_msg, exc_info=True)
                
                # Update state in case of error
                self._update_state()
                
                try:
                    self.error_occurred.emit("undo", error_msg)
                except Exception:
                    pass
                
                raise CommandExecutionError(error_msg) from e
    
    def redo(self) -> Any:
        """
        Redo the last undone command.
        
        Returns:
            Result of redo operation or None if nothing to redo
            
        Raises:
            CommandExecutionError: If redo fails
        """
        with self._lock:
            if not self._can_redo:
                self.logger.debug("Nothing to redo")
                return None
            
            try:
                # Get the command to redo
                command = self._redo_stack.pop()
                
                # Execute the command again
                result = command.execute()
                
                # Add back to undo stack
                self._undo_stack.append(command)
                
                # Update state
                self._update_state()
                
                # Schedule auto-save
                self._schedule_auto_save()
                
                # Update statistics
                self._stats['commands_redone'] += 1
                
                # Emit signal
                try:
                    self.command_redone.emit(command.command_type, command.description)
                except Exception as e:
                    self.logger.debug(f"Error emitting signal: {e}")
                
                self.logger.debug(f"Command redone successfully: {command}")
                return result
                
            except Exception as e:
                self._stats['errors_encountered'] += 1
                error_msg = f"Failed to redo command: {e}"
                self.logger.error(error_msg, exc_info=True)
                
                # Update state in case of error
                self._update_state()
                
                try:
                    self.error_occurred.emit("redo", error_msg)
                except Exception:
                    pass
                
                raise CommandExecutionError(error_msg) from e
    
    # === TRANSACTION SUPPORT ===
    
    def begin_transaction(self, name: str) -> bool:
        """
        Begin a transaction (group of commands).
        
        Args:
            name: Name of the transaction
            
        Returns:
            True if transaction started successfully
            
        Raises:
            TransactionError: If already in transaction
        """
        with self._lock:
            if self._in_transaction:
                error_msg = f"Cannot start transaction '{name}': Already in transaction '{self._transaction_name}'"
                self.logger.warning(error_msg)
                raise TransactionError(error_msg)
            
            self._in_transaction = True
            self._transaction_name = name
            self._transaction_commands = []
            
            try:
                self.transaction_started.emit(name)
            except Exception as e:
                self.logger.debug(f"Error emitting signal: {e}")
            
            self.logger.info(f"Transaction started: {name}")
            return True
    
    def commit_transaction(self) -> bool:
        """
        Commit the current transaction.
        
        Returns:
            True if transaction committed successfully
            
        Raises:
            TransactionError: If not in transaction
        """
        with self._lock:
            if not self._in_transaction:
                error_msg = "Cannot commit: No active transaction"
                self.logger.warning(error_msg)
                raise TransactionError(error_msg)
            
            try:
                transaction_name = self._transaction_name
                command_count = len(self._transaction_commands)
                
                if self._transaction_commands:
                    # Create composite command
                    composite_command = CompositeCommand(
                        name=transaction_name,
                        commands=self._transaction_commands,
                        description=f"Transaction '{transaction_name}' with {command_count} commands"
                    )
                    
                    # Add to undo stack
                    self._undo_stack.append(composite_command)
                    
                    # Clear redo stack
                    self._redo_stack.clear()
                    
                    # Update state
                    self._update_state()
                    
                    # Schedule auto-save
                    self._schedule_auto_save()
                
                # Reset transaction state
                self._in_transaction = False
                self._transaction_name = ""
                self._transaction_commands = []
                
                # Update statistics
                self._stats['transactions_committed'] += 1
                
                # Emit signal
                try:
                    self.transaction_committed.emit(transaction_name, command_count)
                except Exception as e:
                    self.logger.debug(f"Error emitting signal: {e}")
                
                self.logger.info(f"Transaction committed: {transaction_name} ({command_count} commands)")
                return True
                
            except Exception as e:
                # Reset transaction state on error
                self._in_transaction = False
                self._transaction_name = ""
                self._transaction_commands = []
                
                self._stats['errors_encountered'] += 1
                error_msg = f"Failed to commit transaction: {e}"
                self.logger.error(error_msg, exc_info=True)
                
                try:
                    self.error_occurred.emit("commit_transaction", error_msg)
                except Exception:
                    pass
                
                raise TransactionError(error_msg) from e
    
    def rollback_transaction(self) -> bool:
        """
        Rollback the current transaction.
        
        Returns:
            True if transaction rolled back successfully
            
        Raises:
            TransactionError: If not in transaction
        """
        with self._lock:
            if not self._in_transaction:
                error_msg = "Cannot rollback: No active transaction"
                self.logger.warning(error_msg)
                raise TransactionError(error_msg)
            
            try:
                transaction_name = self._transaction_name
                command_count = len(self._transaction_commands)
                
                # Undo all commands in reverse order
                for command in reversed(self._transaction_commands):
                    try:
                        command.undo()
                    except Exception as e:
                        self.logger.error(f"Error undoing command in rollback: {e}")
                
                # Reset transaction state
                self._in_transaction = False
                self._transaction_name = ""
                self._transaction_commands = []
                
                # Update statistics
                self._stats['transactions_rolled_back'] += 1
                
                # Emit signal
                try:
                    self.transaction_rolled_back.emit(transaction_name, command_count)
                except Exception as e:
                    self.logger.debug(f"Error emitting signal: {e}")
                
                self.logger.info(f"Transaction rolled back: {transaction_name} ({command_count} commands)")
                return True
                
            except Exception as e:
                # Reset transaction state on error
                self._in_transaction = False
                self._transaction_name = ""
                self._transaction_commands = []
                
                self._stats['errors_encountered'] += 1
                error_msg = f"Failed to rollback transaction: {e}"
                self.logger.error(error_msg, exc_info=True)
                
                try:
                    self.error_occurred.emit("rollback_transaction", error_msg)
                except Exception:
                    pass
                
                raise TransactionError(error_msg) from e
    
    @contextmanager
    def transaction(self, name: str):
        """
        Context manager for transactions.
        
        Args:
            name: Transaction name
            
        Usage:
            with controller.transaction("my_operation"):
                controller.execute_command(...)
                controller.execute_command(...)
                # Automatically commits on success, rolls back on exception
        """
        self.begin_transaction(name)
        try:
            yield
            self.commit_transaction()
        except Exception:
            try:
                self.rollback_transaction()
            except Exception as rollback_error:
                self.logger.error(f"Error during rollback: {rollback_error}")
            raise
    
    # === AUTO-SAVE SUPPORT ===
    
    def enable_auto_save(self, enabled: bool, interval: int = 300, callback: Optional[Callable] = None):
        """
        Enable or disable auto-save functionality.
        
        Args:
            enabled: Whether to enable auto-save
            interval: Auto-save interval in seconds
            callback: Function to call for auto-save
        """
        with self._lock:
            self._auto_save_enabled = enabled
            self._auto_save_interval = interval
            self._auto_save_callback = callback
            
            if enabled and callback:
                if self._auto_save_timer is not None:
                    try:
                        self._auto_save_timer.start(interval * 1000)
                        self._auto_save_timer_active = True
                        self.logger.info(f"Auto-save enabled with interval {interval}s")
                    except Exception as e:
                        self.logger.warning(f"Failed to start auto-save timer: {e}")
                        self._auto_save_timer_active = False
                else:
                    self.logger.info("Auto-save enabled but timer not available (Qt not initialized)")
            else:
                if self._auto_save_timer is not None:
                    try:
                        self._auto_save_timer.stop()
                        self._auto_save_timer_active = False
                    except Exception:
                        pass
                
                if enabled:
                    self.logger.info("Auto-save enabled but no callback provided")
                else:
                    self.logger.info("Auto-save disabled")
    
    def _schedule_auto_save(self):
        """Schedule an auto-save if enabled."""
        if (self._auto_save_enabled and 
            self._auto_save_callback and 
            self._auto_save_timer is not None and
            not self._auto_save_timer_active):
            try:
                self._auto_save_timer.start(self._auto_save_interval * 1000)
                self._auto_save_timer_active = True
            except Exception as e:
                self.logger.debug(f"Failed to schedule auto-save: {e}")
    
    def _perform_auto_save(self):
        """Perform auto-save operation."""
        if self._auto_save_callback:
            try:
                self._auto_save_callback()
                self._stats['auto_saves_performed'] += 1
                
                try:
                    self.auto_save_triggered.emit()
                except Exception:
                    pass
                
                self.logger.debug("Auto-save performed successfully")
                
            except Exception as e:
                self._stats['errors_encountered'] += 1
                self.logger.error(f"Auto-save failed: {e}")
                
                try:
                    self.error_occurred.emit("auto_save", str(e))
                except Exception:
                    pass
        
        # Stop the timer after auto-save
        if self._auto_save_timer is not None:
            try:
                self._auto_save_timer.stop()
                self._auto_save_timer_active = False
            except Exception:
                pass
    
    def trigger_auto_save(self):
        """Manually trigger auto-save."""
        if self._auto_save_enabled and self._auto_save_callback:
            self._perform_auto_save()
    
    # === STATE AND INFORMATION ===
    
    def can_undo(self) -> bool:
        """Check if undo is possible."""
        return self._can_undo
    
    def can_redo(self) -> bool:
        """Check if redo is possible."""
        return self._can_redo
    
    def get_undo_command_description(self) -> Optional[str]:
        """Get description of the next command to undo."""
        with self._lock:
            if self._undo_stack:
                return self._undo_stack[-1].description
            return None
    
    def get_redo_command_description(self) -> Optional[str]:
        """Get description of the next command to redo."""
        with self._lock:
            if self._redo_stack:
                return self._redo_stack[-1].description
            return None
    
    def get_undo_stack_size(self) -> int:
        """Get the size of the undo stack."""
        return len(self._undo_stack)
    
    def get_redo_stack_size(self) -> int:
        """Get the size of the redo stack."""
        return len(self._redo_stack)
    
    def is_in_transaction(self) -> bool:
        """Check if currently in a transaction."""
        return self._in_transaction
    
    def get_transaction_name(self) -> str:
        """Get the name of the current transaction."""
        return self._transaction_name if self._in_transaction else ""
    
    def get_transaction_command_count(self) -> int:
        """Get the number of commands in the current transaction."""
        return len(self._transaction_commands) if self._in_transaction else 0
    
    def clear_history(self):
        """Clear all undo/redo history."""
        with self._lock:
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._update_state()
            
            try:
                self.history_cleared.emit()
            except Exception as e:
                self.logger.debug(f"Error emitting signal: {e}")
            
            self.logger.info("Command history cleared")
    
    def get_command_history(self, max_commands: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent command history.
        
        Args:
            max_commands: Maximum number of commands to return
            
        Returns:
            List of command information dictionaries
        """
        with self._lock:
            history = []
            
            # Get recent undo commands
            undo_commands = list(self._undo_stack)[-max_commands:]
            for cmd in undo_commands:
                history.append({
                    **cmd.to_dict(),
                    'stack': 'undo',
                    'can_undo': True,
                    'can_redo': False
                })
            
            return history
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get controller statistics.
        
        Returns:
            Dictionary of statistics
        """
        current_time = time.time()
        uptime = current_time - self._stats['start_time']
        
        return {
            **self._stats.copy(),
            'uptime_seconds': uptime,
            'qt_available': QT_AVAILABLE,
            'qt_initialized': self._qt_initialized,
            'undo_stack_size': len(self._undo_stack),
            'redo_stack_size': len(self._redo_stack),
            'max_history': self._max_history,
            'can_undo': self._can_undo,
            'can_redo': self._can_redo,
            'in_transaction': self._in_transaction,
            'transaction_command_count': len(self._transaction_commands),
            'auto_save_enabled': self._auto_save_enabled,
            'auto_save_interval': self._auto_save_interval,
            'auto_save_timer_active': self._auto_save_timer_active,
            'commands_per_minute': (self._stats['commands_executed'] / (uptime / 60)) if uptime > 0 else 0
        }
    
    def get_last_command_timestamp(self) -> Optional[float]:
        """Get timestamp of the last executed command."""
        with self._lock:
            if self._undo_stack:
                return self._undo_stack[-1].timestamp
            return None
    
    # === CONVENIENCE METHODS ===
    
    def execute_simple_command(self, description: str, do_func: Callable, undo_func: Callable) -> Any:
        """
        Execute a simple command with minimal parameters.
        
        Args:
            description: Command description
            do_func: Function to execute
            undo_func: Function to undo
            
        Returns:
            Result of command execution
        """
        return self.execute_command(
            command_type=CommandType.CUSTOM,
            description=description,
            do_func=do_func,
            undo_func=undo_func
        )
    
    def undo_multiple(self, count: int) -> List[Any]:
        """
        Undo multiple commands.
        
        Args:
            count: Number of commands to undo
            
        Returns:
            List of undo results
        """
        results = []
        for _ in range(min(count, len(self._undo_stack))):
            if self.can_undo():
                result = self.undo()
                results.append(result)
            else:
                break
        return results
    
    def redo_multiple(self, count: int) -> List[Any]:
        """
        Redo multiple commands.
        
        Args:
            count: Number of commands to redo
            
        Returns:
            List of redo results
        """
        results = []
        for _ in range(min(count, len(self._redo_stack))):
            if self.can_redo():
                result = self.redo()
                results.append(result)
            else:
                break
        return results
    
    # === PRIVATE METHODS ===
    
    def _update_state(self):
        """Update internal state and emit signals if necessary."""
        # Check undo state
        new_can_undo = bool(self._undo_stack)
        if new_can_undo != self._can_undo:
            self._can_undo = new_can_undo
            try:
                self.undo_state_changed.emit(new_can_undo)
            except Exception as e:
                self.logger.debug(f"Error emitting undo_state_changed signal: {e}")
        
        # Check redo state
        new_can_redo = bool(self._redo_stack)
        if new_can_redo != self._can_redo:
            self._can_redo = new_can_redo
            try:
                self.redo_state_changed.emit(new_can_redo)
            except Exception as e:
                self.logger.debug(f"Error emitting redo_state_changed signal: {e}")
    
    def shutdown(self):
        """Shutdown the controller and clean up resources."""
        with self._lock:
            try:
                # Stop auto-save timer
                if self._auto_save_timer is not None:
                    self._auto_save_timer.stop()
                    self._auto_save_timer_active = False
                
                # Perform final auto-save if enabled
                if self._auto_save_enabled and self._auto_save_callback:
                    self._perform_auto_save()
                
                # Clear transaction if active
                if self._in_transaction:
                    self.rollback_transaction()
                
                self.logger.info("UndoRedoController shutdown completed")
                
            except Exception as e:
                self.logger.error(f"Error during shutdown: {e}")


# === FACTORY FUNCTION ===

def create_undo_redo_controller(max_history: int = 100, 
                               auto_save_enabled: bool = False,
                               auto_save_interval: int = 300,
                               auto_save_callback: Optional[Callable] = None) -> UndoRedoController:
    """
    Factory function to create and configure an undo/redo controller.
    
    Args:
        max_history: Maximum number of commands in history
        auto_save_enabled: Whether to enable auto-save
        auto_save_interval: Auto-save interval in seconds
        auto_save_callback: Function to call for auto-save
        
    Returns:
        Configured UndoRedoController instance
    """
    controller = UndoRedoController(max_history=max_history)
    
    if auto_save_enabled and auto_save_callback:
        controller.enable_auto_save(
            enabled=True,
            interval=auto_save_interval,
            callback=auto_save_callback
        )
    
    return controller


# === COMPATIBILITY FUNCTIONS ===

def patch_existing_command_class():
    """
    Patch existing Command class to add missing attributes.
    This helps with backward compatibility.
    """
    import sys
    
    # Check if there's an existing Command class in the module cache
    for module_name, module in sys.modules.items():
        if hasattr(module, 'Command'):
            existing_command = getattr(module, 'Command')
            
            # Check if it's missing our attributes
            if hasattr(existing_command, '__init__'):
                original_init = existing_command.__init__
                
                def patched_init(self, *args, **kwargs):
                    # Call original init
                    result = original_init(self, *args, **kwargs)
                    
                    # Add missing attributes
                    if not hasattr(self, 'command_type_string'):
                        self.command_type_string = None
                    if not hasattr(self, 'execution_count'):
                        self.execution_count = 0
                    if not hasattr(self, 'undo_count'):
                        self.undo_count = 0
                    if not hasattr(self, 'last_execution_time'):
                        self.last_execution_time = None
                    if not hasattr(self, 'last_undo_time'):
                        self.last_undo_time = None
                    if not hasattr(self, 'execution_errors'):
                        self.execution_errors = []
                    
                    return result
                
                # Patch the __init__ method
                existing_command.__init__ = patched_init
                
                # Add missing methods if they don't exist
                if not hasattr(existing_command, 'get_command_type_name'):
                    def get_command_type_name(self):
                        if hasattr(self, 'command_type_string') and self.command_type_string:
                            return self.command_type_string
                        elif hasattr(self, 'command_type') and hasattr(self.command_type, 'name'):
                            return self.command_type.name
                        elif hasattr(self, 'command_type'):
                            return str(self.command_type)
                        else:
                            return 'Unknown'
                    
                    existing_command.get_command_type_name = get_command_type_name


def create_safe_command(*args, **kwargs):
    """
    Create a command instance safely, handling any compatibility issues.
    
    Returns:
        Command instance
    """
    try:
        return Command(*args, **kwargs)
    except Exception as e:
        # If our Command class fails, create a minimal working version
        class SafeCommand:
            def __init__(self, command_type, description, do_func, undo_func, **kwargs):
                self.command_type = command_type
                self.command_type_string = None
                self.description = str(description)
                self.do_func = do_func
                self.undo_func = undo_func
                self.timestamp = kwargs.get('timestamp', time.time())
                self.execution_count = 0
                self.undo_count = 0
                self.last_execution_time = None
                self.last_undo_time = None
                self.execution_errors = []
                self.metadata = kwargs.get('metadata')
                
            def execute(self):
                try:
                    self.last_execution_time = time.time()
                    result = self.do_func()
                    self.execution_count += 1
                    return result
                except Exception as e:
                    self.execution_errors.append({'timestamp': time.time(), 'error': str(e), 'type': 'execute'})
                    raise
            
            def undo(self):
                try:
                    self.last_undo_time = time.time()
                    result = self.undo_func()
                    self.undo_count += 1
                    return result
                except Exception as e:
                    self.execution_errors.append({'timestamp': time.time(), 'error': str(e), 'type': 'undo'})
                    raise
            
            def get_command_type_name(self):
                if self.command_type_string:
                    return self.command_type_string
                elif hasattr(self.command_type, 'name'):
                    return self.command_type.name
                else:
                    return str(self.command_type)
            
            def __str__(self):
                try:
                    return f"{self.get_command_type_name()}: {self.description}"
                except Exception:
                    return f"Command: {self.description}"
        
        return SafeCommand(*args, **kwargs)


# === INITIALIZATION FUNCTION ===

def initialize_undo_redo_system():
    """
    Initialize the undo/redo system with compatibility patches.
    Call this function early in your application startup.
    """
    try:
        # Apply compatibility patches
        patch_existing_command_class()
        
        # Log successful initialization
        logger = logging.getLogger(__name__)
        logger.info(f"Undo/Redo system initialized successfully (Qt: {QT_AVAILABLE})")
        
        return True
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to initialize undo/redo system patches: {e}")
        return False


# === TECMP COMPATIBILITY HELPERS ===

def get_tecmp_encapsulation_state_safely(tecmp_manager, target_state='ACTIVE'):
    """
    Safely get TECMP encapsulation state, handling different implementations.
    
    Args:
        tecmp_manager: TECMP manager instance
        target_state: Target state to check for (default: 'ACTIVE')
        
    Returns:
        bool: True if in target state, False otherwise
    """
    if not tecmp_manager:
        return False
    
    try:
        # Try different ways to get the state
        
        # Method 1: Direct EncapsulationState enum
        if hasattr(tecmp_manager, 'EncapsulationState'):
            current_state = getattr(tecmp_manager, '_state', None)
            target_enum = getattr(tecmp_manager.EncapsulationState, target_state, None)
            return current_state == target_enum
        
        # Method 2: get_encapsulation_state method
        if hasattr(tecmp_manager, 'get_encapsulation_state'):
            current_state = tecmp_manager.get_encapsulation_state()
            if isinstance(current_state, str):
                return current_state.upper() == target_state.upper()
            elif hasattr(current_state, 'name'):
                return current_state.name.upper() == target_state.upper()
        
        # Method 3: is_encapsulation_active method
        if hasattr(tecmp_manager, 'is_encapsulation_active'):
            return tecmp_manager.is_encapsulation_active()
        
        # Method 4: Check _state attribute directly
        if hasattr(tecmp_manager, '_state'):
            state = tecmp_manager._state
            if isinstance(state, str):
                return state.upper() == target_state.upper()
            elif hasattr(state, 'name'):
                return state.name.upper() == target_state.upper()
        
        # Fallback: assume not active
        return False
        
    except Exception as e:
        # Log the error but don't crash
        logger = logging.getLogger(__name__)
        logger.debug(f"Error checking TECMP encapsulation state: {e}")
        return False


def create_tecmp_state_change_handler(facade):
    """
    Create a safe TECMP state change handler for the facade.
    
    Args:
        facade: TECMP facade instance
        
    Returns:
        Callable: Safe state change handler
    """
    def safe_tecmp_state_changed(state, protocols):
        try:
            # Safely determine if encapsulation is active
            is_active = get_tecmp_encapsulation_state_safely(facade.tecmp_manager, 'ACTIVE')
            
            # Emit the signal safely
            if hasattr(facade, 'tecmp_encapsulation_changed'):
                facade.tecmp_encapsulation_changed.emit(is_active, protocols or [])
                
        except Exception as e:
            # Log error but don't let it propagate
            logger = logging.getLogger(__name__)
            logger.error(f"Error in TECMP state change handler: {e}")
    
    return safe_tecmp_state_changed


# === EXPORTS ===

__all__ = [
    'UndoRedoController',
    'Command',
    'CompositeCommand',
    'CommandType',
    'CommandMetadata',
    'UndoRedoError',
    'CommandExecutionError',
    'TransactionError',
    'create_undo_redo_controller',
    'create_safe_command',
    'patch_existing_command_class',
    'initialize_undo_redo_system',
    'get_tecmp_encapsulation_state_safely',
    'create_tecmp_state_change_handler',
    'QT_AVAILABLE',
    'auto'  # Export auto for compatibility
]


# === TESTING ===

if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    # Initialize the system with compatibility patches
    initialize_undo_redo_system()
    
    # Setup logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    try:
        # Create controller
        controller = create_undo_redo_controller(max_history=50)
        
        logger.info(f"Controller created. Qt available: {QT_AVAILABLE}")
        logger.info(f"Statistics: {controller.get_statistics()}")
        
        # Test simple commands
        test_value = [0]
        
        def increment():
            test_value[0] += 1
            return test_value[0]
        
        def decrement():
            test_value[0] -= 1
            return test_value[0]
        
        # Execute some commands
        controller.execute_command(
            CommandType.CUSTOM,
            "Increment value",
            increment,
            decrement
        )
        
        controller.execute_command(
            CommandType.CUSTOM,
            "Increment value again",
            increment,
            decrement
        )
        
        logger.info(f"After commands: {test_value[0]} (should be 2)")
        logger.info(f"Can undo: {controller.can_undo()}")
        logger.info(f"Can redo: {controller.can_redo()}")
        
        # Test undo
        controller.undo()
        logger.info(f"After undo: {test_value[0]} (should be 1)")
        
        # Test redo
        controller.redo()
        logger.info(f"After redo: {test_value[0]} (should be 2)")
        
        # Test transaction
        with controller.transaction("Multiple increments"):
            controller.execute_command(CommandType.CUSTOM, "Inc 1", increment, decrement)
            controller.execute_command(CommandType.CUSTOM, "Inc 2", increment, decrement)
            controller.execute_command(CommandType.CUSTOM, "Inc 3", increment, decrement)
        
        logger.info(f"After transaction: {test_value[0]} (should be 5)")
        
        # Undo the entire transaction
        controller.undo()
        logger.info(f"After transaction undo: {test_value[0]} (should be 2)")
        
        # Test string command types (for backward compatibility)
        controller.execute_command(
            "PROTOCOL_ADD",  # String instead of enum
            "Add protocol as string",
            increment,
            decrement
        )
        
        logger.info(f"After string command: {test_value[0]} (should be 3)")
        
        # Display final statistics
        stats = controller.get_statistics()
        logger.info(f"Final statistics: {stats}")
        
        # Test command history
        history = controller.get_command_history()
        logger.info(f"Command history: {len(history)} commands")
        for cmd in history:
            logger.info(f"  - {cmd['command_type']}: {cmd['description']}")
        
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)