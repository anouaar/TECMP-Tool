#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced Packet Modifier - Command Pattern Implementation
========================================================

Professional-grade packet modification system using Command pattern
with full undo/redo support, validation, and batch operations.

Key Features:
- Command pattern for all modifications
- Full undo/redo capability
- Batch operation support
- Validation and rollback
- Thread-safe operations
- Modification history tracking
"""
from __future__ import annotations
from typing import (
    Any, Dict, List, Optional, Union, Callable, TypeVar, 
    Protocol, runtime_checkable, Tuple, Iterator
)
from dataclasses import dataclass, field
from enum import Enum, auto
import logging
import threading
import time
import copy
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager

# ============================================================================
# PROTOCOLS AND INTERFACES
# ============================================================================

@runtime_checkable
class Packet(Protocol):
    """Protocol defining packet interface"""
    def serialize(self) -> bytes: ...

@runtime_checkable
class Validator(Protocol):
    """Protocol for packet validators"""
    def validate(self, packet: Packet) -> Tuple[bool, str]: ...

T = TypeVar('T')

# ============================================================================
# ENUMS AND DATA STRUCTURES
# ============================================================================

class ModificationResult(Enum):
    """Result of modification operation"""
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()
    VALIDATION_FAILED = auto()

class ModificationType(Enum):
    """Types of modifications"""
    SET_FIELD = auto()
    SWAP_FIELDS = auto()
    TRANSFORM_FIELD = auto()
    CONDITIONAL_MODIFY = auto()
    BATCH_MODIFY = auto()
    CUSTOM_MODIFY = auto()

@dataclass
class ModificationContext:
    """Context for modification operations"""
    packet: Packet
    operation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False
    validate_before: bool = True
    validate_after: bool = True

@dataclass
class ModificationResult:
    """Result of a modification operation"""
    success: bool
    operation_id: str
    modification_type: ModificationType
    changes_made: Dict[str, Any] = field(default_factory=dict)
    old_values: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    timestamp: float = field(default_factory=time.time)

# ============================================================================
# EXCEPTIONS
# ============================================================================

class ModificationError(Exception):
    """Base exception for modification errors"""
    def __init__(self, message: str, operation_id: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.operation_id = operation_id
        self.context = context or {}

class ValidationError(ModificationError):
    """Exception for validation failures"""
    pass

class UndoError(ModificationError):
    """Exception for undo operation failures"""
    pass

class FieldNotFoundError(ModificationError):
    """Exception when field doesn't exist"""
    pass

# ============================================================================
# COMMAND INTERFACE
# ============================================================================

class Command(ABC):
    """Abstract base class for all modification commands"""
    
    def __init__(self, operation_id: Optional[str] = None):
        self.operation_id = operation_id or str(uuid.uuid4())
        self.timestamp = time.time()
        self.executed = False
        self.undone = False
    
    @abstractmethod
    def execute(self, packet: Packet) -> ModificationResult:
        """Execute the command"""
        pass
    
    @abstractmethod
    def undo(self, packet: Packet) -> ModificationResult:
        """Undo the command"""
        pass
    
    @abstractmethod
    def can_execute(self, packet: Packet) -> bool:
        """Check if command can be executed on packet"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get human-readable description of the command"""
        pass
    
    def get_modification_type(self) -> ModificationType:
        """Get the type of modification"""
        return ModificationType.CUSTOM_MODIFY

# ============================================================================
# CONCRETE COMMAND IMPLEMENTATIONS
# ============================================================================

class SetFieldCommand(Command):
    """Command to set a field value"""
    
    def __init__(self, field_name: str, new_value: Any, 
                 condition: Optional[Callable[[Packet], bool]] = None,
                 operation_id: Optional[str] = None):
        super().__init__(operation_id)
        self.field_name = field_name
        self.new_value = new_value
        self.condition = condition or (lambda p: True)
        self.old_value = None
        self.value_changed = False
    
    def can_execute(self, packet: Packet) -> bool:
        """Check if field exists and condition is met"""
        return hasattr(packet, self.field_name) and self.condition(packet)
    
    def execute(self, packet: Packet) -> ModificationResult:
        """Execute field assignment"""
        start_time = time.perf_counter()
        
        try:
            if not self.can_execute(packet):
                return ModificationResult(
                    success=False,
                    operation_id=self.operation_id,
                    modification_type=ModificationType.SET_FIELD,
                    error_message=f"Cannot execute: field '{self.field_name}' not found or condition not met",
                    execution_time=time.perf_counter() - start_time
                )
            
            # Store old value for undo
            self.old_value = getattr(packet, self.field_name)
            
            # Check if value actually changes
            if self.old_value == self.new_value:
                self.value_changed = False
                return ModificationResult(
                    success=True,
                    operation_id=self.operation_id,
                    modification_type=ModificationType.SET_FIELD,
                    execution_time=time.perf_counter() - start_time
                )
            
            # Set new value
            setattr(packet, self.field_name, self.new_value)
            self.value_changed = True
            self.executed = True
            
            return ModificationResult(
                success=True,
                operation_id=self.operation_id,
                modification_type=ModificationType.SET_FIELD,
                changes_made={self.field_name: self.new_value},
                old_values={self.field_name: self.old_value},
                execution_time=time.perf_counter() - start_time
            )
            
        except Exception as e:
            return ModificationResult(
                success=False,
                operation_id=self.operation_id,
                modification_type=ModificationType.SET_FIELD,
                error_message=f"Execution failed: {e}",
                execution_time=time.perf_counter() - start_time
            )
    
    def undo(self, packet: Packet) -> ModificationResult:
        """Undo field assignment"""
        start_time = time.perf_counter()
        
        try:
            if not self.executed or not self.value_changed:
                return ModificationResult(
                    success=True,
                    operation_id=self.operation_id,
                    modification_type=ModificationType.SET_FIELD,
                    error_message="Nothing to undo",
                    execution_time=time.perf_counter() - start_time
                )
            
            if not hasattr(packet, self.field_name):
                return ModificationResult(
                    success=False,
                    operation_id=self.operation_id,
                    modification_type=ModificationType.SET_FIELD,
                    error_message=f"Cannot undo: field '{self.field_name}' not found",
                    execution_time=time.perf_counter() - start_time
                )
            
            # Restore old value
            setattr(packet, self.field_name, self.old_value)
            self.undone = True
            
            return ModificationResult(
                success=True,
                operation_id=self.operation_id,
                modification_type=ModificationType.SET_FIELD,
                changes_made={self.field_name: self.old_value},
                execution_time=time.perf_counter() - start_time
            )
            
        except Exception as e:
            return ModificationResult(
                success=False,
                operation_id=self.operation_id,
                modification_type=ModificationType.SET_FIELD,
                error_message=f"Undo failed: {e}",
                execution_time=time.perf_counter() - start_time
            )
    
    def get_description(self) -> str:
        """Get command description"""
        return f"Set {self.field_name} = {self.new_value}"
    
    def get_modification_type(self) -> ModificationType:
        return ModificationType.SET_FIELD

class SwapFieldsCommand(Command):
    """Command to swap two field values"""
    
    def __init__(self, field1: str, field2: str, operation_id: Optional[str] = None):
        super().__init__(operation_id)
        self.field1 = field1
        self.field2 = field2
        self.value1 = None
        self.value2 = None
        self.swapped = False
    
    def can_execute(self, packet: Packet) -> bool:
        """Check if both fields exist"""
        return hasattr(packet, self.field1) and hasattr(packet, self.field2)
    
    def execute(self, packet: Packet) -> ModificationResult:
        """Execute field swap"""
        start_time = time.perf_counter()
        
        try:
            if not self.can_execute(packet):
                return ModificationResult(
                    success=False,
                    operation_id=self.operation_id,
                    modification_type=ModificationType.SWAP_FIELDS,
                    error_message=f"Cannot swap: fields '{self.field1}' or '{self.field2}' not found",
                    execution_time=time.perf_counter() - start_time
                )
            
            # Get current values
            self.value1 = getattr(packet, self.field1)
            self.value2 = getattr(packet, self.field2)
            
            # Check if values are actually different
            if self.value1 == self.value2:
                return ModificationResult(
                    success=True,
                    operation_id=self.operation_id,
                    modification_type=ModificationType.SWAP_FIELDS,
                    execution_time=time.perf_counter() - start_time
                )
            
            # Perform swap
            setattr(packet, self.field1, self.value2)
            setattr(packet, self.field2, self.value1)
            self.swapped = True
            self.executed = True
            
            return ModificationResult(
                success=True,
                operation_id=self.operation_id,
                modification_type=ModificationType.SWAP_FIELDS,
                changes_made={self.field1: self.value2, self.field2: self.value1},
                old_values={self.field1: self.value1, self.field2: self.value2},
                execution_time=time.perf_counter() - start_time
            )
            
        except Exception as e:
            return ModificationResult(
                success=False,
                operation_id=self.operation_id,
                modification_type=ModificationType.SWAP_FIELDS,
                error_message=f"Swap failed: {e}",
                execution_time=time.perf_counter() - start_time
            )
    
    def undo(self, packet: Packet) -> ModificationResult:
        """Undo field swap (swap them back)"""
        if not self.executed or not self.swapped:
            return ModificationResult(
                success=True,
                operation_id=self.operation_id,
                modification_type=ModificationType.SWAP_FIELDS,
                error_message="Nothing to undo"
            )
        
        # Swapping back is the same operation
        result = self.execute(packet)
        result.operation_id = self.operation_id  # Keep original operation ID
        self.undone = True
        return result
    
    def get_description(self) -> str:
        """Get command description"""
        return f"Swap {self.field1} â {self.field2}"
    
    def get_modification_type(self) -> ModificationType:
        return ModificationType.SWAP_FIELDS

class TransformFieldCommand(Command):
    """Command to apply a transformation function to a field"""
    
    def __init__(self, field_name: str, transform_func: Callable[[Any], Any],
                 condition: Optional[Callable[[Packet], bool]] = None,
                 operation_id: Optional[str] = None):
        super().__init__(operation_id)
        self.field_name = field_name
        self.transform_func = transform_func
        self.condition = condition or (lambda p: True)
        self.old_value = None
        self.new_value = None
        self.transformed = False
    
    def can_execute(self, packet: Packet) -> bool:
        """Check if field exists and condition is met"""
        return hasattr(packet, self.field_name) and self.condition(packet)
    
    def execute(self, packet: Packet) -> ModificationResult:
        """Execute transformation"""
        start_time = time.perf_counter()
        
        try:
            if not self.can_execute(packet):
                return ModificationResult(
                    success=False,
                    operation_id=self.operation_id,
                    modification_type=ModificationType.TRANSFORM_FIELD,
                    error_message=f"Cannot transform: field '{self.field_name}' not found or condition not met",
                    execution_time=time.perf_counter() - start_time
                )
            
            # Get current value and apply transformation
            self.old_value = getattr(packet, self.field_name)
            self.new_value = self.transform_func(self.old_value)
            
            # Check if value actually changed
            if self.old_value == self.new_value:
                return ModificationResult(
                    success=True,
                    operation_id=self.operation_id,
                    modification_type=ModificationType.TRANSFORM_FIELD,
                    execution_time=time.perf_counter() - start_time
                )
            
            # Apply transformation
            setattr(packet, self.field_name, self.new_value)
            self.transformed = True
            self.executed = True
            
            return ModificationResult(
                success=True,
                operation_id=self.operation_id,
                modification_type=ModificationType.TRANSFORM_FIELD,
                changes_made={self.field_name: self.new_value},
                old_values={self.field_name: self.old_value},
                execution_time=time.perf_counter() - start_time
            )
            
        except Exception as e:
            return ModificationResult(
                success=False,
                operation_id=self.operation_id,
                modification_type=ModificationType.TRANSFORM_FIELD,
                error_message=f"Transformation failed: {e}",
                execution_time=time.perf_counter() - start_time
            )
    
    def undo(self, packet: Packet) -> ModificationResult:
        """Undo transformation"""
        start_time = time.perf_counter()
        
        try:
            if not self.executed or not self.transformed:
                return ModificationResult(
                    success=True,
                    operation_id=self.operation_id,
                    modification_type=ModificationType.TRANSFORM_FIELD,
                    error_message="Nothing to undo",
                    execution_time=time.perf_counter() - start_time
                )
            
            if not hasattr(packet, self.field_name):
                return ModificationResult(
                    success=False,
                    operation_id=self.operation_id,
                    modification_type=ModificationType.TRANSFORM_FIELD,
                    error_message=f"Cannot undo: field '{self.field_name}' not found",
                    execution_time=time.perf_counter() - start_time
                )
            
            # Restore old value
            setattr(packet, self.field_name, self.old_value)
            self.undone = True
            
            return ModificationResult(
                success=True,
                operation_id=self.operation_id,
                modification_type=ModificationType.TRANSFORM_FIELD,
                changes_made={self.field_name: self.old_value},
                execution_time=time.perf_counter() - start_time
            )
            
        except Exception as e:
            return ModificationResult(
                success=False,
                operation_id=self.operation_id,
                modification_type=ModificationType.TRANSFORM_FIELD,
                error_message=f"Undo failed: {e}",
                execution_time=time.perf_counter() - start_time
            )
    
    def get_description(self) -> str:
        """Get command description"""
        return f"Transform {self.field_name} using {self.transform_func.__name__}"
    
    def get_modification_type(self) -> ModificationType:
        return ModificationType.TRANSFORM_FIELD

class BatchCommand(Command):
    """Command to execute multiple commands as a batch"""
    
    def __init__(self, commands: List[Command], 
                 fail_on_first_error: bool = True,
                 operation_id: Optional[str] = None):
        super().__init__(operation_id)
        self.commands = commands
        self.fail_on_first_error = fail_on_first_error
        self.executed_commands: List[Command] = []
        self.results: List[ModificationResult] = []
    
    def can_execute(self, packet: Packet) -> bool:
        """Check if at least one command can be executed"""
        return any(cmd.can_execute(packet) for cmd in self.commands)
    
    def execute(self, packet: Packet) -> ModificationResult:
        """Execute all commands in batch"""
        start_time = time.perf_counter()
        self.results.clear()
        self.executed_commands.clear()
        
        successful_count = 0
        failed_count = 0
        all_changes = {}
        all_old_values = {}
        error_messages = []
        
        try:
            for cmd in self.commands:
                if cmd.can_execute(packet):
                    result = cmd.execute(packet)
                    self.results.append(result)
                    
                    if result.success:
                        successful_count += 1
                        self.executed_commands.append(cmd)
                        all_changes.update(result.changes_made)
                        all_old_values.update(result.old_values)
                    else:
                        failed_count += 1
                        if result.error_message:
                            error_messages.append(result.error_message)
                        
                        if self.fail_on_first_error:
                            break
                else:
                    failed_count += 1
                    error_messages.append(f"Command {cmd.get_description()} cannot be executed")
                    
                    if self.fail_on_first_error:
                        break
            
            self.executed = True
            overall_success = successful_count > 0 and (not self.fail_on_first_error or failed_count == 0)
            
            return ModificationResult(
                success=overall_success,
                operation_id=self.operation_id,
                modification_type=ModificationType.BATCH_MODIFY,
                changes_made=all_changes,
                old_values=all_old_values,
                error_message="; ".join(error_messages) if error_messages else None,
                execution_time=time.perf_counter() - start_time
            )
            
        except Exception as e:
            return ModificationResult(
                success=False,
                operation_id=self.operation_id,
                modification_type=ModificationType.BATCH_MODIFY,
                error_message=f"Batch execution failed: {e}",
                execution_time=time.perf_counter() - start_time
            )
    
    def undo(self, packet: Packet) -> ModificationResult:
        """Undo all executed commands in reverse order"""
        start_time = time.perf_counter()
        
        if not self.executed or not self.executed_commands:
            return ModificationResult(
                success=True,
                operation_id=self.operation_id,
                modification_type=ModificationType.BATCH_MODIFY,
                error_message="Nothing to undo",
                execution_time=time.perf_counter() - start_time
            )
        
        successful_undos = 0
        failed_undos = 0
        error_messages = []
        
        # Undo in reverse order
        for cmd in reversed(self.executed_commands):
            try:
                result = cmd.undo(packet)
                if result.success:
                    successful_undos += 1
                else:
                    failed_undos += 1
                    if result.error_message:
                        error_messages.append(result.error_message)
            except Exception as e:
                failed_undos += 1
                error_messages.append(f"Undo failed for {cmd.get_description()}: {e}")
        
        self.undone = True
        
        return ModificationResult(
            success=failed_undos == 0,
            operation_id=self.operation_id,
            modification_type=ModificationType.BATCH_MODIFY,
            error_message="; ".join(error_messages) if error_messages else None,
            execution_time=time.perf_counter() - start_time
        )
    
    def get_description(self) -> str:
        """Get batch description"""
        cmd_descriptions = [cmd.get_description() for cmd in self.commands[:3]]
        if len(self.commands) > 3:
            cmd_descriptions.append(f"... and {len(self.commands) - 3} more")
        return f"Batch: [{'; '.join(cmd_descriptions)}]"
    
    def get_modification_type(self) -> ModificationType:
        return ModificationType.BATCH_MODIFY

# ============================================================================
# PACKET MODIFIER MAIN CLASS
# ============================================================================

class PacketModifier:
    """
    Enhanced packet modifier using Command pattern with full undo/redo support
    
    Features:
    - Command pattern for all modifications
    - Complete undo/redo capability
    - Batch operations
    - Validation and rollback
    - Thread-safe operations
    - Modification history
    """
    
    def __init__(self, packet: Packet, enable_validation: bool = True,
                 thread_safe: bool = True, max_history: int = 100):
        """
        Initialize packet modifier
        
        Args:
            packet: Packet to modify
            enable_validation: Enable validation before/after modifications
            thread_safe: Enable thread-safe operations
            max_history: Maximum number of operations to keep in history
        """
        self.packet = packet
        self.enable_validation = enable_validation
        self.max_history = max_history
        
        # Command history for undo/redo
        self._command_history: List[Command] = []
        self._history_position = -1
        
        # Validators
        self._validators: List[Validator] = []
        
        # Thread safety
        self._lock = threading.RLock() if thread_safe else None
        
        # Statistics
        self._stats = {
            'total_modifications': 0,
            'successful_modifications': 0,
            'failed_modifications': 0,
            'undos_performed': 0,
            'redos_performed': 0,
            'validation_failures': 0
        }
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    # ========================================================================
    # CONTEXT MANAGERS
    # ========================================================================
    
    @contextmanager
    def _thread_safe_operation(self):
        """Context manager for thread-safe operations"""
        if self._lock:
            with self._lock:
                yield
        else:
            yield
    
    @contextmanager
    def batch_modification(self, fail_on_first_error: bool = True) -> Iterator['BatchModificationContext']:
        """
        Context manager for batch modifications
        
        Args:
            fail_on_first_error: Stop on first error if True
            
        Yields:
            BatchModificationContext for adding commands
        """
        context = BatchModificationContext(self, fail_on_first_error)
        try:
            yield context
        finally:
            if context.commands:
                batch_cmd = BatchCommand(context.commands, fail_on_first_error)
                self._execute_command(batch_cmd)
    
    # ========================================================================
    # VALIDATOR MANAGEMENT
    # ========================================================================
    
    def add_validator(self, validator: Validator) -> 'PacketModifier':
        """Add a validator"""
        with self._thread_safe_operation():
            self._validators.append(validator)
        return self
    
    def remove_validator(self, validator: Validator) -> 'PacketModifier':
        """Remove a validator"""
        with self._thread_safe_operation():
            if validator in self._validators:
                self._validators.remove(validator)
        return self
    
    def validate_packet(self) -> Tuple[bool, List[str]]:
        """Validate current packet state"""
        errors = []
        
        for validator in self._validators:
            try:
                is_valid, error_msg = validator.validate(self.packet)
                if not is_valid:
                    errors.append(error_msg)
            except Exception as e:
                errors.append(f"Validator error: {e}")
        
        return len(errors) == 0, errors
    
    # ========================================================================
    # MODIFICATION METHODS (FLUENT INTERFACE)
    # ========================================================================
    
    def set_field(self, field_name: str, value: Any, 
                  condition: Optional[Callable[[Packet], bool]] = None) -> 'PacketModifier':
        """
        Set a field value
        
        Args:
            field_name: Name of field to set
            value: New value
            condition: Optional condition function
            
        Returns:
            Self for chaining
        """
        with self._thread_safe_operation():
            cmd = SetFieldCommand(field_name, value, condition)
            self._execute_command(cmd)
        return self
    
    def swap_fields(self, field1: str, field2: str) -> 'PacketModifier':
        """
        Swap two field values
        
        Args:
            field1: First field name
            field2: Second field name
            
        Returns:
            Self for chaining
        """
        with self._thread_safe_operation():
            cmd = SwapFieldsCommand(field1, field2)
            self._execute_command(cmd)
        return self
    
    def transform_field(self, field_name: str, transform_func: Callable[[Any], Any],
                       condition: Optional[Callable[[Packet], bool]] = None) -> 'PacketModifier':
        """
        Apply a transformation function to a field
        
        Args:
            field_name: Name of field to transform
            transform_func: Transformation function
            condition: Optional condition function
            
        Returns:
            Self for chaining
        """
        with self._thread_safe_operation():
            cmd = TransformFieldCommand(field_name, transform_func, condition)
            self._execute_command(cmd)
        return self
    
    def increment_field(self, field_name: str, amount: Union[int, float] = 1) -> 'PacketModifier':
        """
        Increment a numeric field
        
        Args:
            field_name: Name of field to increment
            amount: Amount to increment by
            
        Returns:
            Self for chaining
        """
        return self.transform_field(field_name, lambda x: x + amount)
    
    def toggle_flag(self, field_name: str, flag_bit: int) -> 'PacketModifier':
        """
        Toggle a bit flag in a field
        
        Args:
            field_name: Name of field containing flags
            flag_bit: Bit position to toggle
            
        Returns:
            Self for chaining
        """
        return self.transform_field(field_name, lambda x: x ^ (1 << flag_bit))
    
    def set_flag(self, field_name: str, flag_bit: int, value: bool) -> 'PacketModifier':
        """
        Set or clear a bit flag in a field
        
        Args:
            field_name: Name of field containing flags
            flag_bit: Bit position to modify
            value: True to set, False to clear
            
        Returns:
            Self for chaining
        """
        if value:
            return self.transform_field(field_name, lambda x: x | (1 << flag_bit))
        else:
            return self.transform_field(field_name, lambda x: x & ~(1 << flag_bit))
    
    def apply_if(self, condition: Callable[[Packet], bool]) -> 'ConditionalModifier':
        """
        Create a conditional modifier
        
        Args:
            condition: Condition function
            
        Returns:
            ConditionalModifier for conditional operations
        """
        return ConditionalModifier(self, condition)
    
    # ========================================================================
    # COMMAND EXECUTION
    # ========================================================================
    
    def _execute_command(self, command: Command) -> ModificationResult:
        """Execute a command with validation and history management"""
        # Pre-execution validation
        if self.enable_validation:
            is_valid, errors = self.validate_packet()
            if not is_valid:
                self._stats['validation_failures'] += 1
                return ModificationResult(
                    success=False,
                    operation_id=command.operation_id,
                    modification_type=command.get_modification_type(),
                    validation_errors=errors,
                    error_message=f"Pre-execution validation failed: {'; '.join(errors)}"
                )
        
        # Execute command
        result = command.execute(self.packet)
        
        # Update statistics
        self._stats['total_modifications'] += 1
        if result.success:
            self._stats['successful_modifications'] += 1
        else:
            self._stats['failed_modifications'] += 1
        
        # Post-execution validation
        if result.success and self.enable_validation:
            is_valid, errors = self.validate_packet()
            if not is_valid:
                # Rollback the command
                command.undo(self.packet)
                self._stats['validation_failures'] += 1
                return ModificationResult(
                    success=False,
                    operation_id=command.operation_id,
                    modification_type=command.get_modification_type(),
                    validation_errors=errors,
                    error_message=f"Post-execution validation failed: {'; '.join(errors)}"
                )
        
        # Add to history if successful
        if result.success:
            self._add_to_history(command)
        
        return result
    
    def _add_to_history(self, command: Command) -> None:
        """Add command to history"""
        # Remove any commands after current position (for redo)
        if self._history_position < len(self._command_history) - 1:
            self._command_history = self._command_history[:self._history_position + 1]
        
        # Add new command
        self._command_history.append(command)
        self._history_position += 1
        
        # Limit history size
        if len(self._command_history) > self.max_history:
            self._command_history.pop(0)
            self._history_position -= 1
    
    # ========================================================================
    # UNDO/REDO OPERATIONS
    # ========================================================================
    
    def can_undo(self) -> bool:
        """Check if undo is possible"""
        with self._thread_safe_operation():
            return self._history_position >= 0
    
    def can_redo(self) -> bool:
        """Check if redo is possible"""
        with self._thread_safe_operation():
            return self._history_position < len(self._command_history) - 1
    
    def undo(self) -> ModificationResult:
        """Undo the last modification"""
        with self._thread_safe_operation():
            if not self.can_undo():
                return ModificationResult(
                    success=False,
                    operation_id="undo",
                    modification_type=ModificationType.CUSTOM_MODIFY,
                    error_message="Nothing to undo"
                )
            
            command = self._command_history[self._history_position]
            result = command.undo(self.packet)
            
            if result.success:
                self._history_position -= 1
                self._stats['undos_performed'] += 1
                self.logger.debug(f"Undid command: {command.get_description()}")
            
            return result
    
    def redo(self) -> ModificationResult:
        """Redo the next modification"""
        with self._thread_safe_operation():
            if not self.can_redo():
                return ModificationResult(
                    success=False,
                    operation_id="redo",
                    modification_type=ModificationType.CUSTOM_MODIFY,
                    error_message="Nothing to redo"
                )
            
            self._history_position += 1
            command = self._command_history[self._history_position]
            result = command.execute(self.packet)
            
            if result.success:
                self._stats['redos_performed'] += 1
                self.logger.debug(f"Redid command: {command.get_description()}")
            else:
                # Rollback position if redo failed
                self._history_position -= 1
            
            return result
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of command that would be undone"""
        if self.can_undo():
            return self._command_history[self._history_position].get_description()
        return None
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of command that would be redone"""
        if self.can_redo():
            return self._command_history[self._history_position + 1].get_description()
        return None
    
    # ========================================================================
    # INFORMATION AND DEBUGGING
    # ========================================================================
    
    def get_modification_history(self) -> List[Dict[str, Any]]:
        """Get modification history"""
        with self._thread_safe_operation():
            history = []
            for i, cmd in enumerate(self._command_history):
                history.append({
                    'index': i,
                    'description': cmd.get_description(),
                    'type': cmd.get_modification_type().name,
                    'executed': cmd.executed,
                    'undone': cmd.undone,
                    'timestamp': cmd.timestamp,
                    'operation_id': cmd.operation_id,
                    'current': i == self._history_position
                })
            return history
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get modification statistics"""
        with self._thread_safe_operation():
            return self._stats.copy()
    
    def clear_history(self) -> None:
        """Clear modification history"""
        with self._thread_safe_operation():
            self._command_history.clear()
            self._history_position = -1
            self.logger.info("Modification history cleared")
    
    # ========================================================================
    # FINALIZATION
    # ========================================================================
    
    def finalize(self) -> Packet:
        """
        Finalize modifications and return the modified packet
        
        Returns:
            The modified packet
        """
        with self._thread_safe_operation():
            # Final validation
            if self.enable_validation:
                is_valid, errors = self.validate_packet()
                if not is_valid:
                    raise ValidationError(
                        f"Final validation failed: {'; '.join(errors)}",
                        context={'errors': errors}
                    )
            
            # Ensure packet is serializable
            try:
                self.packet.serialize()
            except Exception as e:
                raise ModificationError(f"Packet serialization failed: {e}")
            
            self.logger.info(f"Packet modification finalized. Total modifications: {self._stats['total_modifications']}")
            return self.packet

# ============================================================================
# HELPER CLASSES
# ============================================================================

class BatchModificationContext:
    """Context for batch modifications"""
    
    def __init__(self, modifier: PacketModifier, fail_on_first_error: bool):
        self.modifier = modifier
        self.fail_on_first_error = fail_on_first_error
        self.commands: List[Command] = []
    
    def set_field(self, field_name: str, value: Any, 
                  condition: Optional[Callable[[Packet], bool]] = None) -> 'BatchModificationContext':
        """Add set field command to batch"""
        self.commands.append(SetFieldCommand(field_name, value, condition))
        return self
    
    def swap_fields(self, field1: str, field2: str) -> 'BatchModificationContext':
        """Add swap fields command to batch"""
        self.commands.append(SwapFieldsCommand(field1, field2))
        return self
    
    def transform_field(self, field_name: str, transform_func: Callable[[Any], Any],
                       condition: Optional[Callable[[Packet], bool]] = None) -> 'BatchModificationContext':
        """Add transform field command to batch"""
        self.commands.append(TransformFieldCommand(field_name, transform_func, condition))
        return self

class ConditionalModifier:
    """Conditional modifier for applying modifications only when condition is met"""
    
    def __init__(self, modifier: PacketModifier, condition: Callable[[Packet], bool]):
        self.modifier = modifier
        self.condition = condition
    
    def set_field(self, field_name: str, value: Any) -> PacketModifier:
        """Set field if condition is met"""
        return self.modifier.set_field(field_name, value, self.condition)
    
    def swap_fields(self, field1: str, field2: str) -> PacketModifier:
        """Swap fields if condition is met"""
        if self.condition(self.modifier.packet):
            return self.modifier.swap_fields(field1, field2)
        return self.modifier
    
    def transform_field(self, field_name: str, transform_func: Callable[[Any], Any]) -> PacketModifier:
        """Transform field if condition is met"""
        return self.modifier.transform_field(field_name, transform_func, self.condition)

# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def modify_packet(packet: Packet, enable_validation: bool = True) -> PacketModifier:
    """
    Create a packet modifier for the given packet
    
    Args:
        packet: Packet to modify
        enable_validation: Enable validation
        
    Returns:
        PacketModifier instance
    """
    return PacketModifier(packet, enable_validation)

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Main classes
    'PacketModifier',
    'Command',
    
    # Command implementations
    'SetFieldCommand',
    'SwapFieldsCommand',
    'TransformFieldCommand',
    'BatchCommand',
    
    # Helper classes
    'BatchModificationContext',
    'ConditionalModifier',
    
    # Data structures
    'ModificationContext',
    'ModificationResult',
    
    # Enums
    'ModificationResult',
    'ModificationType',
    
    # Exceptions
    'ModificationError',
    'ValidationError',
    'UndoError',
    'FieldNotFoundError',
    
    # Convenience functions
    'modify_packet',
    
    # Protocols
    'Packet',
    'Validator'
]

# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Mock packet class for examples
    class MockPacket:
        def __init__(self):
            self.src_ip = "192.168.1.1"
            self.dst_ip = "192.168.1.2"
            self.ttl = 64
            self.flags = 0x02
            self.src_port = 12345
            self.dst_port = 80
        
        def serialize(self) -> bytes:
            return f"{self.src_ip}:{self.dst_ip}:{self.ttl}".encode()
        
        def __repr__(self):
            return f"MockPacket(src_ip={self.src_ip}, dst_ip={self.dst_ip}, ttl={self.ttl})"
    
    # Example 1: Basic modifications
    print("=== Example 1: Basic Modifications ===")
    
    packet = MockPacket()
    print(f"Original: {packet}")
    
    modifier = (modify_packet(packet)
                .set_field("ttl", 128)
                .swap_fields("src_ip", "dst_ip")
                .increment_field("src_port", 1000))
    
    final_packet = modifier.finalize()
    print(f"Modified: {final_packet}")
    
    # Example 2: Undo/Redo operations
    print("\n=== Example 2: Undo/Redo Operations ===")
    
    packet2 = MockPacket()
    modifier2 = modify_packet(packet2)
    
    print(f"Initial: {packet2}")
    
    # Make some modifications
    modifier2.set_field("ttl", 32)
    print(f"After TTL change: {packet2}")
    
    modifier2.set_field("src_port", 8080)
    print(f"After port change: {packet2}")
    
    # Undo operations
    print(f"Can undo: {modifier2.can_undo()}")
    if modifier2.can_undo():
        print(f"Will undo: {modifier2.get_undo_description()}")
        modifier2.undo()
        print(f"After undo: {packet2}")
    
    if modifier2.can_undo():
        print(f"Will undo: {modifier2.get_undo_description()}")
        modifier2.undo()
        print(f"After second undo: {packet2}")
    
    # Redo operations
    print(f"Can redo: {modifier2.can_redo()}")
    if modifier2.can_redo():
        print(f"Will redo: {modifier2.get_redo_description()}")
        modifier2.redo()
        print(f"After redo: {packet2}")
    
    # Example 3: Batch modifications
    print("\n=== Example 3: Batch Modifications ===")
    
    packet3 = MockPacket()
    modifier3 = modify_packet(packet3)
    
    print(f"Before batch: {packet3}")
    
    with modifier3.batch_modification() as batch:
        batch.set_field("ttl", 255)
        batch.swap_fields("src_port", "dst_port")
        batch.transform_field("flags", lambda x: x | 0x08)  # Set flag
    
    print(f"After batch: {packet3}")
    
    # Example 4: Conditional modifications
    print("\n=== Example 4: Conditional Modifications ===")
    
    packet4 = MockPacket()
    modifier4 = modify_packet(packet4)
    
    print(f"Before conditional: {packet4}")
    
    # Only modify if TTL is less than 100
    (modifier4
     .apply_if(lambda p: p.ttl < 100)
     .set_field("ttl", 200))
    
    print(f"After conditional (TTL was {packet4.ttl}): {packet4}")
    
    # Example 5: Statistics and history
    print("\n=== Example 5: Statistics and History ===")
    
    stats = modifier4.get_statistics()
    print(f"Statistics: {stats}")
    
    history = modifier4.get_modification_history()
    print("Modification History:")
    for entry in history:
        current_marker = " <-- CURRENT" if entry['current'] else ""
        print(f"  {entry['index']}: {entry['description']}{current_marker}")
    
    print("\n=== All Examples Completed ===")