#!/usr/bin/env python
# coding: utf-8
"""
Signal Connector Controller for the TECMP Tool.

This controller centralizes and manages signal connections between components,
providing a cleaner separation of concerns and reducing tight coupling.
It serves as a mediator for inter-component communication.
"""
import logging
from typing import Dict, Any, Callable, Set, Optional, List, Tuple, Union

from PyQt5.QtCore import QObject, pyqtSignal, QMetaObject, Qt


class SignalConnectorController(QObject):
    """
    Controller for managing signal connections between application components.
    
    The SignalConnectorController serves as a central mediator for signals in the application:
    - Establishes and manages connections between components
    - Provides a registry of available signals
    - Enables dynamic connection/disconnection of signals
    - Allows signal interception and transformation
    - Eliminates direct dependencies between UI components
    
    This supports a more decoupled, maintainable architecture where components
    communicate without direct references to each other.
    """
    
    # Mediator signals that can be connected to multiple slots
    state_changed = pyqtSignal(str, object)  # state_name, data
    operation_completed = pyqtSignal(bool, str)  # success, message
    protocol_state_changed = pyqtSignal(str, int)  # action, index
    ui_action_triggered = pyqtSignal(str, object)  # action_name, data
    theme_changed = pyqtSignal(bool)  # is_dark_mode
    
    def __init__(self, facade=None):
        """
        Initialize the signal connector controller.
        
        Args:
            facade: Optional reference to the central facade
        """
        super().__init__()
        self.logger = logging.getLogger("TECMP-Tool.SignalConnectorController")
        
        # Facade reference
        self.facade = facade
        
        # Component registry
        self._components = {}
        
        # Signal connection registry - tracks which signals are connected
        self._connections = {}
        
        # Signal transformers - modify signals before forwarding
        self._transformers = {}
        
        self.logger.info("SignalConnectorController initialized")
    
    def register_component(self, name: str, component: QObject) -> None:
        """
        Register a component for signal connections.
        
        Args:
            name: Unique identifier for the component
            component: The component object with signals/slots
        """
        if name in self._components:
            self.logger.warning(f"Component '{name}' already registered, replacing")
            
        self._components[name] = component
        self.logger.debug(f"Component registered: {name}")
    
    def unregister_component(self, name: str) -> bool:
        """
        Unregister a component and disconnect its signals.
        
        Args:
            name: Component identifier
            
        Returns:
            bool: True if component was unregistered, False if not found
        """
        if name not in self._components:
            self.logger.warning(f"Cannot unregister: Component '{name}' not found")
            return False
            
        # Disconnect all signals for this component
        self._disconnect_component_signals(name)
        
        # Remove from registry
        del self._components[name]
        self.logger.debug(f"Component unregistered: {name}")
        return True
    
    def connect_signal(self, 
                     source_component: str, 
                     signal_name: str, 
                     target_component: str, 
                     slot_name: str,
                     transform_func: Optional[Callable] = None) -> bool:
        """
        Connect a signal from one component to a slot on another.
        
        Args:
            source_component: Name of the component emitting the signal
            signal_name: Name of the signal to connect
            target_component: Name of the component with the slot
            slot_name: Name of the slot to connect to
            transform_func: Optional function to transform signal arguments
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
        # Validate components exist
        if source_component not in self._components:
            self.logger.error(f"Source component '{source_component}' not found")
            return False
            
        if target_component not in self._components:
            self.logger.error(f"Target component '{target_component}' not found")
            return False
            
        # Get component objects
        source = self._components[source_component]
        target = self._components[target_component]
        
        # Validate signal exists
        if not hasattr(source, signal_name):
            self.logger.error(f"Signal '{signal_name}' not found in '{source_component}'")
            return False
            
        # Validate slot exists
        if not hasattr(target, slot_name):
            self.logger.error(f"Slot '{slot_name}' not found in '{target_component}'")
            return False
            
        # Get signal and slot
        signal = getattr(source, signal_name)
        slot = getattr(target, slot_name)
        
        # Store transformer if provided
        connection_key = f"{source_component}.{signal_name}->{target_component}.{slot_name}"
        if transform_func:
            self._transformers[connection_key] = transform_func
            
            # Create wrapper slot that applies transformation
            def transform_slot(*args, **kwargs):
                transformed_args = transform_func(*args, **kwargs)
                if isinstance(transformed_args, tuple):
                    slot(*transformed_args)
                else:
                    slot(transformed_args)
                    
            # Connect with transformation
            try:
                signal.connect(transform_slot)
                self._connections[connection_key] = (signal, transform_slot)
                self.logger.debug(f"Connected with transformation: {connection_key}")
                return True
            except Exception as e:
                self.logger.error(f"Error connecting signals with transformation: {e}")
                return False
        else:
            # Direct connection
            try:
                signal.connect(slot)
                self._connections[connection_key] = (signal, slot)
                self.logger.debug(f"Connected: {connection_key}")
                return True
            except Exception as e:
                self.logger.error(f"Error connecting signals: {e}")
                return False
    
    def disconnect_signal(self, 
                        source_component: str, 
                        signal_name: str, 
                        target_component: str, 
                        slot_name: str) -> bool:
        """
        Disconnect a signal connection.
        
        Args:
            source_component: Name of the component emitting the signal
            signal_name: Name of the signal to disconnect
            target_component: Name of the component with the slot
            slot_name: Name of the slot to disconnect
            
        Returns:
            bool: True if disconnection was successful, False otherwise
        """
        connection_key = f"{source_component}.{signal_name}->{target_component}.{slot_name}"
        
        if connection_key not in self._connections:
            self.logger.warning(f"Connection not found: {connection_key}")
            return False
            
        # Get the signal and slot
        signal, slot = self._connections[connection_key]
        
        try:
            # Disconnect the signal
            signal.disconnect(slot)
            
            # Remove from registries
            del self._connections[connection_key]
            if connection_key in self._transformers:
                del self._transformers[connection_key]
                
            self.logger.debug(f"Disconnected: {connection_key}")
            return True
        except Exception as e:
            self.logger.error(f"Error disconnecting signals: {e}")
            return False
    
    def _disconnect_component_signals(self, component_name: str) -> None:
        """
        Disconnect all signals for a specific component.
        
        Args:
            component_name: Name of the component
        """
        # Find all connections involving this component
        connections_to_remove = []
        
        for connection_key in self._connections:
            if connection_key.startswith(f"{component_name}.") or f"->{component_name}." in connection_key:
                connections_to_remove.append(connection_key)
        
        # Disconnect each connection
        for connection_key in connections_to_remove:
            signal, slot = self._connections[connection_key]
            try:
                signal.disconnect(slot)
                self.logger.debug(f"Disconnected: {connection_key}")
            except Exception as e:
                self.logger.warning(f"Error disconnecting {connection_key}: {e}")
                
            # Remove from registries
            del self._connections[connection_key]
            if connection_key in self._transformers:
                del self._transformers[connection_key]
    
    def connect_to_facade(self, 
                         component_name: str, 
                         signal_name: str, 
                         facade_method_name: str,
                         transform_func: Optional[Callable] = None) -> bool:
        """
        Connect a component signal to a method on the facade.
        
        Args:
            component_name: Name of the component emitting the signal
            signal_name: Name of the signal to connect
            facade_method_name: Name of the method on the facade
            transform_func: Optional function to transform signal arguments
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
        if not self.facade:
            self.logger.error("Cannot connect to facade: No facade reference")
            return False
            
        if component_name not in self._components:
            self.logger.error(f"Component '{component_name}' not found")
            return False
            
        # Get component and signal
        component = self._components[component_name]
        
        if not hasattr(component, signal_name):
            self.logger.error(f"Signal '{signal_name}' not found in '{component_name}'")
            return False
            
        if not hasattr(self.facade, facade_method_name):
            self.logger.error(f"Method '{facade_method_name}' not found in facade")
            return False
            
        # Get signal and method
        signal = getattr(component, signal_name)
        facade_method = getattr(self.facade, facade_method_name)
        
        # Create connection key
        connection_key = f"{component_name}.{signal_name}->facade.{facade_method_name}"
        
        # Connect with transformation if provided
        if transform_func:
            self._transformers[connection_key] = transform_func
            
            # Create wrapper that applies transformation
            def transform_facade_method(*args, **kwargs):
                transformed_args = transform_func(*args, **kwargs)
                if isinstance(transformed_args, tuple):
                    facade_method(*transformed_args)
                else:
                    facade_method(transformed_args)
                    
            # Connect with transformation
            try:
                signal.connect(transform_facade_method)
                self._connections[connection_key] = (signal, transform_facade_method)
                self.logger.debug(f"Connected to facade with transformation: {connection_key}")
                return True
            except Exception as e:
                self.logger.error(f"Error connecting to facade with transformation: {e}")
                return False
        else:
            # Direct connection
            try:
                signal.connect(facade_method)
                self._connections[connection_key] = (signal, facade_method)
                self.logger.debug(f"Connected to facade: {connection_key}")
                return True
            except Exception as e:
                self.logger.error(f"Error connecting to facade: {e}")
                return False
    
    def connect_facade_signal(self, 
                            facade_attribute: str, 
                            target_component: str, 
                            slot_name: str,
                            transform_func: Optional[Callable] = None) -> bool:
        """
        Connect a facade attribute (likely a signal) to a component slot.
        
        Args:
            facade_attribute: Name of the attribute on the facade
            target_component: Name of the component with the slot
            slot_name: Name of the slot to connect to
            transform_func: Optional function to transform signal arguments
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
        if not self.facade:
            self.logger.error("Cannot connect from facade: No facade reference")
            return False
            
        if target_component not in self._components:
            self.logger.error(f"Target component '{target_component}' not found")
            return False
            
        # Verify facade attribute exists
        if not hasattr(self.facade, facade_attribute):
            self.logger.error(f"Attribute '{facade_attribute}' not found on facade")
            return False
            
        # Get facade attribute and target slot
        facade_attr = getattr(self.facade, facade_attribute)
        target = self._components[target_component]
        
        if not hasattr(target, slot_name):
            self.logger.error(f"Slot '{slot_name}' not found in '{target_component}'")
            return False
            
        target_slot = getattr(target, slot_name)
        
        # Ensure facade attribute is a signal
        if not hasattr(facade_attr, 'connect'):
            self.logger.error(f"Facade attribute '{facade_attribute}' is not a signal")
            return False
            
        # Create connection key
        connection_key = f"facade.{facade_attribute}->{target_component}.{slot_name}"
        
        # Connect with transformation if provided
        if transform_func:
            self._transformers[connection_key] = transform_func
            
            # Create wrapper that applies transformation
            def transform_slot(*args, **kwargs):
                transformed_args = transform_func(*args, **kwargs)
                if isinstance(transformed_args, tuple):
                    target_slot(*transformed_args)
                else:
                    target_slot(transformed_args)
                    
            # Connect with transformation
            try:
                facade_attr.connect(transform_slot)
                self._connections[connection_key] = (facade_attr, transform_slot)
                self.logger.debug(f"Connected from facade with transformation: {connection_key}")
                return True
            except Exception as e:
                self.logger.error(f"Error connecting from facade with transformation: {e}")
                return False
        else:
            # Direct connection
            try:
                facade_attr.connect(target_slot)
                self._connections[connection_key] = (facade_attr, target_slot)
                self.logger.debug(f"Connected from facade: {connection_key}")
                return True
            except Exception as e:
                self.logger.error(f"Error connecting from facade: {e}")
                return False
    
    def establish_standard_connections(self) -> None:
        """
        Establish standard connections between components.
        
        This sets up common connections that most applications will need,
        based on the components that have been registered.
        """
        self.logger.info("Establishing standard connections")
        
        # Connect protocol controllers if available
        if 'protocol_controller' in self._components and 'main_window' in self._components:
            protocol_controller = self._components['protocol_controller']
            main_window = self._components['main_window']
            
            # Protocol add/remove signals
            if hasattr(protocol_controller, 'protocol_added') and hasattr(main_window, 'on_protocol_added'):
                self.connect_signal('protocol_controller', 'protocol_added', 'main_window', 'on_protocol_added')
                
            if hasattr(protocol_controller, 'protocol_removed') and hasattr(main_window, 'on_protocol_removed'):
                self.connect_signal('protocol_controller', 'protocol_removed', 'main_window', 'on_protocol_removed')
        
        # Connect TECMP controllers if available
        if 'tecmp_controller' in self._components and 'main_window' in self._components:
            tecmp_controller = self._components['tecmp_controller']
            main_window = self._components['main_window']
            
            # TECMP state change signals
            if hasattr(tecmp_controller, 'encapsulation_changed') and hasattr(main_window, 'on_tecmp_state_changed'):
                self.connect_signal('tecmp_controller', 'encapsulation_changed', 'main_window', 'on_tecmp_state_changed')
        
        # Connect preview controller if available
        if 'preview_controller' in self._components and 'main_window' in self._components:
            preview_controller = self._components['preview_controller']
            main_window = self._components['main_window']
            
            # Preview update signals
            if hasattr(preview_controller, 'preview_updated') and hasattr(main_window, 'on_preview_updated'):
                self.connect_signal('preview_controller', 'preview_updated', 'main_window', 'on_preview_updated')
        
        # Connect trace controller if available
        if 'trace_controller' in self._components and 'main_window' in self._components:
            trace_controller = self._components['trace_controller']
            main_window = self._components['main_window']
            
            # Trace loaded signals
            if hasattr(trace_controller, 'trace_loaded') and hasattr(main_window, 'on_trace_loaded'):
                self.connect_signal('trace_controller', 'trace_loaded', 'main_window', 'on_trace_loaded')
        
        # Connect drag drop controller if available
        if 'drag_drop_controller' in self._components and 'main_window' in self._components:
            drag_drop_controller = self._components['drag_drop_controller']
            main_window = self._components['main_window']
            
            # Protocol drag/drop signals
            if hasattr(drag_drop_controller, 'protocol_dropped') and hasattr(main_window, 'handle_protocol_drop'):
                self.connect_signal('drag_drop_controller', 'protocol_dropped', 'main_window', 'handle_protocol_drop')
    
    def broadcast_state_change(self, state_name: str, data: Any = None) -> None:
        """
        Broadcast a state change to all interested components.
        
        Args:
            state_name: Name of the state that changed
            data: Optional data associated with the state change
        """
        self.state_changed.emit(state_name, data)
        self.logger.debug(f"Broadcast state change: {state_name}")
    
    def notify_operation_result(self, success: bool, message: str) -> None:
        """
        Notify listeners of an operation result.
        
        Args:
            success: Whether the operation succeeded
            message: Result message
        """
        self.operation_completed.emit(success, message)
        self.logger.debug(f"Operation {'completed' if success else 'failed'}: {message}")
    
    def notify_protocol_change(self, action: str, index: int) -> None:
        """
        Notify listeners of a protocol state change.
        
        Args:
            action: Action performed (add, remove, move, update)
            index: Index of the affected protocol
        """
        self.protocol_state_changed.emit(action, index)
        self.logger.debug(f"Protocol state change: {action} at index {index}")
    
    def trigger_ui_action(self, action_name: str, data: Any = None) -> None:
        """
        Trigger a UI action through the mediator.
        
        Args:
            action_name: Name of the action to trigger
            data: Optional data for the action
        """
        self.ui_action_triggered.emit(action_name, data)
        self.logger.debug(f"UI action triggered: {action_name}")
    
    def notify_theme_change(self, is_dark_mode: bool) -> None:
        """
        Notify components of a theme change.
        
        Args:
            is_dark_mode: Whether dark mode is enabled
        """
        self.theme_changed.emit(is_dark_mode)
        self.logger.debug(f"Theme changed: {'dark' if is_dark_mode else 'light'} mode")
    
    def get_component(self, name: str) -> Optional[QObject]:
        """
        Get a registered component by name.
        
        Args:
            name: Component name
            
        Returns:
            The component object or None if not found
        """
        return self._components.get(name)
    
    def list_connections(self) -> List[str]:
        """
        Get a list of all active connections.
        
        Returns:
            List of connection strings
        """
        return list(self._connections.keys())
    
    def set_facade(self, facade: Any) -> None:
        """
        Set the facade reference.
        
        Args:
            facade: The central facade instance
        """
        self.facade = facade
        self.logger.debug("Facade reference set")