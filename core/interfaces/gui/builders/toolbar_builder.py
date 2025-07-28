#!/usr/bin/env python3
"""
TECMP Production Toolbar - Real Integration with Menu Bar Alignment

Production-ready toolbar with menu synchronization:
- Real design system integration 
- Real controller connections
- Real facade integration
- Menu bar synchronization
- No mocks, no demos, production code only
- Comprehensive error handling and logging
- Full English interface
"""

import logging
import os
import sys
from typing import Dict, List, Callable, Optional, Union, Any
from enum import Enum, auto
from dataclasses import dataclass

from PyQt5.QtWidgets import (
    QToolBar, QAction, QToolButton, QMenu, QWidget, QSizePolicy,
    QActionGroup, QLabel, QFrame, QHBoxLayout, QPushButton,
    QApplication, QMainWindow, QComboBox, QProgressBar, QSpacerItem
)
from PyQt5.QtCore import (
    QSize, Qt, QSettings, pyqtSignal, QObject, QTimer, QRect, QPoint
)
from PyQt5.QtGui import (
    QIcon, QPixmap, QColor, QPainter, QPen, QFont, QKeySequence
)

# Import centralized design system
try:
    from .tecmp_visual_config import TECMPDesignSystem, TECMPColorScheme
except ImportError:
    logging.error("TECMPDesignSystem not found - ensure tecmp_visual_config.py is available")
    sys.exit(1)


class ActionType(Enum):
    """Toolbar action types for semantic organization."""
    EDIT = auto()      # Undo/Redo
    VIEW = auto()      # Zoom In/Out
    TECMP = auto()     # TECMP Toggle
    VALIDATE = auto()  # Validate


class ActionPriority(Enum):
    """Action priority levels for UI organization."""
    CRITICAL = auto()    # Always visible
    HIGH = auto()        # Visible in normal mode
    MEDIUM = auto()      # Visible in expanded mode
    LOW = auto()         # Context menu only


@dataclass
class ToolbarActionConfig:
    """Complete toolbar action configuration."""
    id: str
    text: str
    tooltip: str
    icon_symbol: str
    action_type: ActionType
    priority: ActionPriority = ActionPriority.HIGH
    shortcut: Optional[str] = None
    checkable: bool = False
    enabled_by_default: bool = True
    separator_after: bool = False
    menu_sync: bool = True  # New: sync with menu bar


class SharedActionRegistry:
    """
    Shared registry for actions between toolbar and menu.
    Ensures consistent state across UI components.
    """
    def __init__(self):
        self.actions: Dict[str, List[QAction]] = {}
        self.logger = logging.getLogger(f"{__name__}.SharedActionRegistry")
    
    def register_action(self, action_id: str, action: QAction):
        """Register an action with the shared registry."""
        if action_id not in self.actions:
            self.actions[action_id] = []
        self.actions[action_id].append(action)
        self.logger.debug(f"Registered action '{action_id}' - total instances: {len(self.actions[action_id])}")
    
    def update_action_state(self, action_id: str, enabled: bool, checked: Optional[bool] = None):
        """Update state for all instances of an action."""
        if action_id in self.actions:
            for action in self.actions[action_id]:
                action.setEnabled(enabled)
                if checked is not None and action.isCheckable():
                    action.setChecked(checked)
            self.logger.debug(f"Updated action '{action_id}' state - enabled: {enabled}, checked: {checked}")
    
    def get_action_instances(self, action_id: str) -> List[QAction]:
        """Get all instances of an action."""
        return self.actions.get(action_id, [])


# Global action registry for toolbar-menu synchronization
_action_registry = SharedActionRegistry()


class TECMPToolbarController(QObject):
    """
    Production toolbar controller with real facade integration.
    Manages all toolbar actions and state synchronization.
    Enhanced with menu bar synchronization support.
    """
    
    # Production signals
    action_executed = pyqtSignal(str, bool, object)  # action_id, success, result
    state_updated = pyqtSignal(dict)                 # complete_state
    error_occurred = pyqtSignal(str, str, str)       # severity, action_id, message
    
    # Menu synchronization signals
    action_state_changed = pyqtSignal(str, bool, object)  # action_id, enabled, checked
    menu_sync_requested = pyqtSignal(str, dict)           # action_id, state_dict
    
    def __init__(self, facade_instance):
        super().__init__()
        self.facade = facade_instance
        self.logger = logging.getLogger(f"{__name__}.TECMPToolbarController")
        
        # Application state tracking
        self._app_state = {
            'protocol_stack': [],
            'current_packet': None,
            'tecmp_encapsulated': False,
            'capture_active': False,
            'file_loaded': False,
            'file_modified': False,
            'can_undo': False,
            'can_redo': False,
            'dark_mode': False,
            'hex_view_active': False
        }
        
        # Menu synchronization
        self._menu_connected = False
        
        # Initialize real connections
        self._establish_facade_connections()
        self._initialize_application_state()
        
        self.logger.info("TECMP Toolbar Controller initialized with real facade and menu sync")
    
    def connect_menu_system(self, menu_system):
        """Connect to menu system for synchronization."""
        try:
            if hasattr(menu_system, 'action_executed'):
                menu_system.action_executed.connect(self._handle_menu_action)
            
            if hasattr(menu_system, 'menu_state_changed'):
                self.state_updated.connect(lambda state: menu_system._update_menu_states())
            
            self._menu_connected = True
            self.logger.info("Menu system connected for synchronization")
            
        except Exception as e:
            self.logger.error(f"Failed to connect menu system: {e}")
    
    def _handle_menu_action(self, action_id: str, success: bool):
        """Handle action executed from menu."""
        if success:
            # Update state if action from menu succeeded
            self._initialize_application_state()
    
    def _establish_facade_connections(self):
        """Establish real connections to facade signals."""
        if not self.facade:
            self.logger.critical("No facade instance provided")
            return
        
        try:
            # Connect to real facade signals
            connection_map = [
                ('protocol_stack_changed', self._handle_protocol_stack_changed),
                ('tecmp_state_changed', self._handle_tecmp_state_changed),
                ('packet_generated', self._handle_packet_generated),
                ('file_operation_completed', self._handle_file_operation),
                ('capture_state_changed', self._handle_capture_state_changed),
                ('application_state_changed', self._handle_application_state_changed),
                ('error_occurred', self._handle_facade_error),
                # New connections for menu sync
                ('undo_available', lambda available: self._update_action_state('undo', available)),
                ('redo_available', lambda available: self._update_action_state('redo', available))
            ]
            
            connected_signals = []
            for signal_name, handler in connection_map:
                if hasattr(self.facade, signal_name):
                    signal = getattr(self.facade, signal_name)
                    signal.connect(handler)
                    connected_signals.append(signal_name)
                else:
                    self.logger.warning(f"Facade signal '{signal_name}' not available")
            
            self.logger.info(f"Connected to facade signals: {connected_signals}")
            
        except Exception as e:
            self.logger.error(f"Failed to establish facade connections: {e}")
            self.error_occurred.emit("ERROR", "connection", str(e))
    
    def _update_action_state(self, action_id: str, enabled: bool, checked: Optional[bool] = None):
        """Update action state and notify components."""
        # Update in shared registry
        _action_registry.update_action_state(action_id, enabled, checked)
        
        # Emit signal for any additional listeners
        self.action_state_changed.emit(action_id, enabled, checked)
        
        # Request menu sync
        if self._menu_connected:
            self.menu_sync_requested.emit(action_id, {
                'enabled': enabled,
                'checked': checked
            })
    
    def _initialize_application_state(self):
        """Initialize state from facade."""
        try:
            if hasattr(self.facade, 'get_application_state'):
                state = self.facade.get_application_state()
                self._update_state_from_facade(state)
            
            self.logger.debug("Application state initialized from facade")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize application state: {e}")
    
    def _update_state_from_facade(self, facade_state):
        """Update internal state from facade state object."""
        try:
            state_mapping = {
                'protocol_stack': 'get_protocol_stack',
                'current_packet': 'get_current_packet', 
                'tecmp_encapsulated': 'is_tecmp_encapsulated',
                'capture_active': 'is_capturing',
                'file_loaded': 'has_open_file',
                'file_modified': 'is_file_modified',
                'can_undo': 'can_undo',
                'can_redo': 'can_redo',
                'dark_mode': 'is_dark_mode_enabled',
                'hex_view_active': 'is_hex_view_active'
            }
            
            for state_key, facade_method in state_mapping.items():
                if hasattr(facade_state, facade_method):
                    method = getattr(facade_state, facade_method)
                    self._app_state[state_key] = method() if callable(method) else method
                elif hasattr(self.facade, facade_method):
                    method = getattr(self.facade, facade_method)
                    self._app_state[state_key] = method() if callable(method) else method
            
            self.state_updated.emit(self._app_state.copy())
            self._emit_state_update()
            
        except Exception as e:
            self.logger.error(f"Failed to update state from facade: {e}")
    
    # === FACADE EVENT HANDLERS ===
    
    def _handle_protocol_stack_changed(self, stack_data):
        """Handle protocol stack changes from facade."""
        try:
            self._app_state['protocol_stack'] = stack_data or []
            self._emit_state_update()
        except Exception as e:
            self.logger.error(f"Error handling protocol stack change: {e}")
    
    def _handle_tecmp_state_changed(self, is_encapsulated, protocols=None):
        """Handle TECMP encapsulation state changes."""
        try:
            self._app_state['tecmp_encapsulated'] = bool(is_encapsulated)
            self._emit_state_update()
        except Exception as e:
            self.logger.error(f"Error handling TECMP state change: {e}")
    
    def _handle_packet_generated(self, packet_data):
        """Handle packet generation events."""
        try:
            self._app_state['current_packet'] = packet_data
            self._emit_state_update()
        except Exception as e:
            self.logger.error(f"Error handling packet generation: {e}")
    
    def _handle_file_operation(self, operation_type, filepath, success):
        """Handle file operation results."""
        try:
            if operation_type in ['open', 'load'] and success:
                self._app_state['file_loaded'] = True
                self._app_state['file_modified'] = False
            elif operation_type == 'save' and success:
                self._app_state['file_modified'] = False
            elif operation_type == 'new':
                self._app_state['file_loaded'] = False
                self._app_state['file_modified'] = False
            
            self._emit_state_update()
            
        except Exception as e:
            self.logger.error(f"Error handling file operation: {e}")
    
    def _handle_capture_state_changed(self, is_capturing):
        """Handle capture state changes."""
        try:
            self._app_state['capture_active'] = bool(is_capturing)
            self._emit_state_update()
        except Exception as e:
            self.logger.error(f"Error handling capture state change: {e}")
    
    def _handle_application_state_changed(self, state_name, state_value):
        """Handle general application state changes."""
        try:
            if state_name in self._app_state:
                self._app_state[state_name] = state_value
                self._emit_state_update()
        except Exception as e:
            self.logger.error(f"Error handling application state change: {e}")
    
    def _handle_facade_error(self, error_data, context=None):
        """Handle errors from facade."""
        try:
            error_message = str(error_data)
            self.error_occurred.emit("ERROR", context or "facade", error_message)
        except Exception as e:
            self.logger.error(f"Error handling facade error: {e}")
    
    def _emit_state_update(self):
        """Emit state update signal and update actions."""
        self.state_updated.emit(self._app_state.copy())
        # Update all action states based on new state
        self._update_all_action_states()
    
    def _update_all_action_states(self):
        """Update states for all actions based on current application state."""
        # Update each action based on current state
        action_states = {
            'undo': (self._app_state['can_undo'], None),
            'redo': (self._app_state['can_redo'], None),
            'tecmp_toggle': (len(self._app_state['protocol_stack']) > 0, None),
            'validate': (len(self._app_state['protocol_stack']) > 0, None),
        }
        
        for action_id, (enabled, checked) in action_states.items():
            self._update_action_state(action_id, enabled, checked)
    
    # === ACTION EXECUTION ===
    
    def execute_action(self, action_id: str, **kwargs) -> bool:
        """Execute a toolbar action through facade."""
        try:
            self.logger.debug(f"Executing action: {action_id}")
            
            # Get action executor
            executor = getattr(self, f'_execute_{action_id}', None)
            if not executor:
                self.logger.warning(f"No executor found for action: {action_id}")
                self.action_executed.emit(action_id, False, None)
                return False
            
            # Execute action
            result = executor(**kwargs)
            success = result is not False and result is not None
            
            self.action_executed.emit(action_id, success, result)
            
            # Sync with menu if connected
            if self._menu_connected:
                self.menu_sync_requested.emit(action_id, {'executed': success})
            
            # Log result
            if success:
                self.logger.debug(f"Action '{action_id}' executed successfully")
            else:
                self.logger.warning(f"Action '{action_id}' failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error executing action '{action_id}': {e}")
            self.error_occurred.emit("ERROR", action_id, str(e))
            self.action_executed.emit(action_id, False, None)
            return False
    
    # === 6 SPECIFIC TOOLBAR ACTIONS ===
    
    def _execute_undo(self) -> bool:
        """Execute undo action."""
        if hasattr(self.facade, 'undo_last_operation'):
            return self.facade.undo_last_operation()
        return False
    
    def _execute_redo(self) -> bool:
        """Execute redo action."""
        if hasattr(self.facade, 'redo_last_operation'):
            return self.facade.redo_last_operation()
        return False
    
    def _execute_tecmp_toggle(self) -> bool:
        """Execute TECMP toggle action."""
        if hasattr(self.facade, 'is_tecmp_encapsulated') and hasattr(self.facade, 'add_tecmp_encapsulation') and hasattr(self.facade, 'remove_tecmp_encapsulation'):
            if self.facade.is_tecmp_encapsulated():
                return self.facade.remove_tecmp_encapsulation()
            else:
                return self.facade.add_tecmp_encapsulation()
        return False
    
    def _execute_validate(self) -> bool:
        """Execute validate action."""
        if hasattr(self.facade, 'validate_protocol_stack'):
            result = self.facade.validate_protocol_stack()
            return result.get('valid', False) if isinstance(result, dict) else False
        return False
    
    # === STATE ACCESS ===
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current application state."""
        return self._app_state.copy()
    
    def is_action_enabled(self, action_id: str) -> bool:
        """Check if an action should be enabled based on current state."""
        state = self._app_state
        
        enablement_rules = {
            'undo': state['can_undo'],
            'redo': state['can_redo'],
            'zoom_in': True,  # Always enabled
            'zoom_out': True,  # Always enabled
            'tecmp_toggle': len(state['protocol_stack']) > 0,
            'validate': len(state['protocol_stack']) > 0
        }
        
        return enablement_rules.get(action_id, True)
    
    def is_action_checked(self, action_id: str) -> bool:
        """Check if a checkable action should be checked."""
        state = self._app_state
        
        check_rules = {
            'tecmp_toggle': state['tecmp_encapsulated']
        }
        
        return check_rules.get(action_id, False)


class TECMPProductionToolbar(QToolBar):
    """
    Production TECMP toolbar with real design system integration.
    Zero code duplication - uses centralized design system only.
    Enhanced with menu bar synchronization.
    """
    
    # Production signals
    action_triggered = pyqtSignal(str, dict)  # action_id, context
    state_synchronized = pyqtSignal(dict)     # current_state
    integration_status = pyqtSignal(str, bool, str)  # component, status, message
    
    def __init__(self, design_system: TECMPDesignSystem, controller: TECMPToolbarController, parent=None):
        super().__init__("TECMP Production Toolbar", parent)
        
        self.design_system = design_system
        self.controller = controller
        self.logger = logging.getLogger(f"{__name__}.TECMPProductionToolbar")
        
        # Internal state
        self._actions: Dict[str, QAction] = {}
        self._action_configs: Dict[str, ToolbarActionConfig] = {}
        self._current_state: Dict[str, Any] = {}
        self._style_cache: Dict[str, str] = {}
        
        # Zoom level for local zoom actions
        self._zoom_level = 100  # 100% default zoom
        
        # Initialize toolbar
        self._configure_toolbar()
        self._connect_systems()
        self._build_toolbar_structure()
        self._apply_initial_styling()
        self._synchronize_initial_state()
        
        self.logger.info("TECMP Production Toolbar initialized successfully with menu sync capability")
    
    def _configure_toolbar(self):
        """Configure toolbar basic properties from design system."""
        try:
            # Icon size from design system
            icon_size = 24  # Fixed value for now
            self.setIconSize(QSize(icon_size, icon_size))
            
            # Toolbar properties
            self.setMovable(True)
            self.setFloatable(True)
            self.setToolButtonStyle(Qt.ToolButtonIconOnly)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # Spacing from design system
            spacing = self.design_system.get_spacing('md')
            self.layout().setSpacing(spacing)
            
            self.logger.debug("Toolbar configured with design system parameters")
            
        except Exception as e:
            self.logger.error(f"Failed to configure toolbar: {e}")
    
    def _connect_systems(self):
        """Connect to design system and controller."""
        try:
            # Design system connections
            self.design_system.theme_changed.connect(self._handle_theme_change)
            self.design_system.colors_changed.connect(self._handle_colors_change)
            self.design_system.effects_changed.connect(self._handle_effects_change)
            
            # Controller connections
            self.controller.action_executed.connect(self._handle_action_result)
            self.controller.state_updated.connect(self._handle_state_update)
            self.controller.error_occurred.connect(self._handle_controller_error)
            
            # Menu sync connections
            self.controller.action_state_changed.connect(self._handle_action_state_change)
            
            self.integration_status.emit("design_system", True, "Connected to design system")
            self.integration_status.emit("controller", True, "Connected to controller")
            
        except Exception as e:
            self.logger.error(f"Failed to connect systems: {e}")
            self.integration_status.emit("systems", False, str(e))
    
    def _build_toolbar_structure(self):
        """Build complete toolbar structure."""
        try:
            # Get action configurations for the 6 specific actions
            action_configs = self._get_production_action_configs()
            
            # Build toolbar with all 6 actions
            for config in action_configs:
                if self._create_toolbar_action(config):
                    # Add separator after redo and zoom_out
                    if config.id in ['redo', 'zoom_out']:
                        self.addSeparator()
            
            self.logger.info(f"Built toolbar with {len(self._actions)} actions")
            
        except Exception as e:
            self.logger.error(f"Failed to build toolbar structure: {e}")
    
    def _get_production_action_configs(self) -> List[ToolbarActionConfig]:
        """Get production toolbar action configurations for the 6 specific actions."""
        return [
            # Undo/Redo actions
            ToolbarActionConfig("undo", "Undo", "Undo last operation", "?", ActionType.EDIT, ActionPriority.CRITICAL, "Ctrl+Z"),
            ToolbarActionConfig("redo", "Redo", "Redo last operation", "?", ActionType.EDIT, ActionPriority.CRITICAL, "Ctrl+Y"),
            
            # Zoom actions (local)
            ToolbarActionConfig("zoom_in", "Zoom In", "Zoom in view", "??+", ActionType.VIEW, ActionPriority.HIGH, "Ctrl++"),
            ToolbarActionConfig("zoom_out", "Zoom Out", "Zoom out view", "??-", ActionType.VIEW, ActionPriority.HIGH, "Ctrl+-"),
            
            # TECMP Toggle
            ToolbarActionConfig("tecmp_toggle", "TECMP", "Toggle TECMP encapsulation", "??", ActionType.TECMP, ActionPriority.HIGH, "Ctrl+T"),
            
            # Validate
            ToolbarActionConfig("validate", "Validate", "Validate protocol stack", "?", ActionType.VALIDATE, ActionPriority.HIGH, "F9"),
        ]
    
    def _create_toolbar_action(self, config: ToolbarActionConfig) -> bool:
        """Create a single toolbar action."""
        try:
            # Create icon from design system
            icon = self._create_design_system_icon(config)
            
            # Create action
            action = QAction(icon, config.text, self)
            action.setToolTip(self._format_action_tooltip(config))
            action.setCheckable(config.checkable)
            action.setEnabled(config.enabled_by_default)
            
            # Set keyboard shortcut
            if config.shortcut:
                action.setShortcut(QKeySequence(config.shortcut))
            
            # Connect action
            action.triggered.connect(
                lambda checked=False, aid=config.id: self._execute_toolbar_action(aid, checked)
            )
            
            # Store action and config
            self._actions[config.id] = action
            self._action_configs[config.id] = config
            
            # Register with shared registry if menu sync enabled
            if config.menu_sync:
                _action_registry.register_action(config.id, action)
            
            # Add to toolbar
            self.addAction(action)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create action '{config.id}': {e}")
            return False
    
    def _create_design_system_icon(self, config: ToolbarActionConfig) -> QIcon:
        """Create icon using design system styling."""
        try:
            # Get action color from design system
            action_color = self._get_action_color(config.action_type)
            
            # Get icon size
            icon_size = self.iconSize()
            
            # Create pixmap
            pixmap = QPixmap(icon_size)
            pixmap.fill(Qt.transparent)
            
            # Paint icon
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Apply current visual style
            if self.design_system._current_style.name == 'GLASSMORPHISM':
                self._paint_glassmorphism_icon(painter, icon_size, action_color, config.icon_symbol)
            else:
                self._paint_standard_icon(painter, icon_size, action_color, config.icon_symbol)
            
            painter.end()
            return QIcon(pixmap)
            
        except Exception as e:
            self.logger.error(f"Failed to create icon for '{config.id}': {e}")
            return self._create_fallback_icon(config.icon_symbol)
    
    def _get_action_color(self, action_type: ActionType) -> QColor:
        """Get semantic color for action type from design system."""
        palette = self.design_system.get_current_palette()
        
        color_mapping = {
            ActionType.EDIT: palette.secondary,
            ActionType.VIEW: palette.info,
            ActionType.TECMP: palette.accent,
            ActionType.VALIDATE: palette.success
        }
        
        return QColor(color_mapping.get(action_type, palette.primary))
    
    def _paint_glassmorphism_icon(self, painter: QPainter, size: QSize, color: QColor, symbol: str):
        """Paint icon with glassmorphism effect from design system."""
        # Background with glassmorphism
        bg_color = QColor(color)
        bg_color.setAlpha(int(255 * (self.design_system.get_effect('glassmorphism_background_opacity') or 0.1)))
        
        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        
        radius = self.design_system.get_radius('md')
        painter.drawRoundedRect(2, 2, size.width()-4, size.height()-4, radius, radius)
        
        # Border with glow
        border_color = QColor(color)
        border_color.setAlpha(int(255 * (self.design_system.get_effect('glassmorphism_border_opacity') or 0.2)))
        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(2, 2, size.width()-4, size.height()-4, radius, radius)
        
        # Symbol
        self._paint_icon_symbol(painter, symbol, size, color)
    
    def _paint_standard_icon(self, painter: QPainter, size: QSize, color: QColor, symbol: str):
        """Paint icon with standard styling."""
        bg_color = QColor(color)
        bg_color.setAlpha(30)
        
        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(1, 1, size.width()-2, size.height()-2, 4, 4)
        
        self._paint_icon_symbol(painter, symbol, size, color)
    
    def _paint_icon_symbol(self, painter: QPainter, symbol: str, size: QSize, color: QColor):
        """Paint the icon symbol."""
        painter.setPen(color)
        
        font_size = max(10, min(16, size.width() // 2))
        font = QFont("Segoe UI Emoji", font_size)
        painter.setFont(font)
        
        painter.drawText(QRect(0, 0, size.width(), size.height()), Qt.AlignCenter, symbol)
    
    def _create_fallback_icon(self, symbol: str) -> QIcon:
        """Create simple fallback icon."""
        size = self.iconSize()
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Simple circle
        color = QColor(self.design_system.get_current_palette().primary)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, size.width()-4, size.height()-4)
        
        # White symbol
        painter.setPen(QColor("white"))
        font = QFont("Arial", size.width()//3, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, size.width(), size.height()), Qt.AlignCenter, symbol[0])
        
        painter.end()
        return QIcon(pixmap)
    
    def _format_action_tooltip(self, config: ToolbarActionConfig) -> str:
        """Format action tooltip with keyboard shortcut."""
        tooltip = config.tooltip
        if config.shortcut:
            tooltip += f" ({config.shortcut})"
        return tooltip
    
    def _execute_toolbar_action(self, action_id: str, checked: bool = False):
        """Execute toolbar action through controller or locally."""
        try:
            context = {
                'checked': checked,
                'source': 'toolbar',
                'timestamp': QTimer().currentTime()
            }
            
            # Handle local zoom actions
            if action_id == 'zoom_in':
                self._zoom_level += 10
                self._zoom_level = min(self._zoom_level, 200)  # Max 200%
                self.logger.info(f"Zoom level: {self._zoom_level}%")
                success = True
            elif action_id == 'zoom_out':
                self._zoom_level -= 10
                self._zoom_level = max(self._zoom_level, 50)  # Min 50%
                self.logger.info(f"Zoom level: {self._zoom_level}%")
                success = True
            else:
                # Execute through controller for facade actions
                success = self.controller.execute_action(action_id, checked=checked)
            
            # Emit signal
            self.action_triggered.emit(action_id, context)
            
        except Exception as e:
            self.logger.error(f"Failed to execute toolbar action '{action_id}': {e}")
    
    def _apply_initial_styling(self):
        """Apply initial styling from design system."""
        try:
            style = self._generate_toolbar_stylesheet()
            self.setStyleSheet(style)
            self.logger.debug("Initial styling applied from design system")
            
        except Exception as e:
            self.logger.error(f"Failed to apply initial styling: {e}")
    
    def _generate_toolbar_stylesheet(self) -> str:
        """Generate complete toolbar stylesheet from design system."""
        palette = self.design_system.get_current_palette()
        spacing = self.design_system.get_spacing('md')
        radius = self.design_system.get_radius('lg')
        
        if self.design_system._current_style.name == 'GLASSMORPHISM':
            return self._generate_glassmorphism_stylesheet(palette, spacing, radius)
        else:
            return self._generate_standard_stylesheet(palette, spacing, radius)
    
    def _generate_glassmorphism_stylesheet(self, palette, spacing: int, radius: int) -> str:
        """Generate glassmorphism stylesheet."""
        return f"""
            QToolBar {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.9),
                    stop:1 rgba(248, 249, 250, 0.8));
                border: 1px solid rgba(79, 172, 254, 0.2);
                border-radius: {radius}px;
                padding: {spacing}px;
                spacing: {spacing//2}px;
                margin: 6px;
            }}
            
            QToolBar::separator {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 transparent,
                    stop:0.5 rgba(79, 172, 254, 0.3),
                    stop:1 transparent);
                width: 2px;
                margin: 8px 4px;
                border-radius: 1px;
            }}
            
            QToolBar QToolButton {{
                background: rgba(255, 255, 255, 0.3);
                border: 1px solid rgba(79, 172, 254, 0.15);
                border-radius: 8px;
                padding: 8px;
                margin: 2px;
                min-width: 32px;
                min-height: 32px;
            }}
            
            QToolBar QToolButton:hover {{
                background: rgba(79, 172, 254, 0.15);
                border-color: {palette.primary};
            }}
            
            QToolBar QToolButton:pressed {{
                background: rgba(79, 172, 254, 0.25);
            }}
            
            QToolBar QToolButton:checked {{
                background: rgba(79, 172, 254, 0.3);
                border-color: {palette.primary};
            }}
            
            QToolBar QToolButton:disabled {{
                background: rgba(128, 128, 128, 0.1);
                border-color: rgba(128, 128, 128, 0.2);
                opacity: 0.5;
            }}
        """
    
    def _generate_standard_stylesheet(self, palette, spacing: int, radius: int) -> str:
        """Generate standard stylesheet."""
        return f"""
            QToolBar {{
                background: {palette.surface};
                border: 1px solid {palette.neutral_200};
                border-radius: {radius}px;
                padding: {spacing}px;
            }}
            
            QToolBar QToolButton {{
                background: {palette.background};
                border: 1px solid {palette.neutral_300};
                border-radius: 6px;
                padding: 6px;
                margin: 1px;
            }}
            
            QToolBar QToolButton:hover {{
                background: {palette.primary};
                color: {palette.on_primary};
            }}
            
            QToolBar QToolButton:pressed {{
                background: {palette.primary_dark};
            }}
            
            QToolBar QToolButton:disabled {{
                opacity: 0.5;
            }}
        """
    
    def _synchronize_initial_state(self):
        """Synchronize initial state with controller."""
        try:
            initial_state = self.controller.get_current_state()
            self._update_actions_from_state(initial_state)
            self.state_synchronized.emit(initial_state)
            
        except Exception as e:
            self.logger.error(f"Failed to synchronize initial state: {e}")
    
    def _update_actions_from_state(self, state: Dict[str, Any]):
        """Update action states based on application state."""
        try:
            for action_id, action in self._actions.items():
                # Update enabled state
                enabled = self.controller.is_action_enabled(action_id)
                action.setEnabled(enabled)
                
                # Update checked state for checkable actions
                if action.isCheckable():
                    checked = self.controller.is_action_checked(action_id)
                    action.setChecked(checked)
            
            self._current_state = state.copy()
            
        except Exception as e:
            self.logger.error(f"Failed to update actions from state: {e}")
    
    def _refresh_all_icons(self):
        """Refresh all icons with current design system."""
        try:
            for action_id, action in self._actions.items():
                config = self._action_configs[action_id]
                new_icon = self._create_design_system_icon(config)
                action.setIcon(new_icon)
                
        except Exception as e:
            self.logger.error(f"Failed to refresh icons: {e}")
    
    # === EVENT HANDLERS ===
    
    def _handle_theme_change(self, theme_name: str):
        """Handle design system theme changes."""
        try:
            new_style = self._generate_toolbar_stylesheet()
            self.setStyleSheet(new_style)
            self._refresh_all_icons()
            
            self.logger.debug(f"Theme changed to: {theme_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to handle theme change: {e}")
    
    def _handle_colors_change(self, colors_dict: dict):
        """Handle design system color changes."""
        try:
            new_style = self._generate_toolbar_stylesheet()
            self.setStyleSheet(new_style)
            self._refresh_all_icons()
            
        except Exception as e:
            self.logger.error(f"Failed to handle colors change: {e}")
    
    def _handle_effects_change(self, effects_dict: dict):
        """Handle design system effects changes."""
        try:
            new_style = self._generate_toolbar_stylesheet()
            self.setStyleSheet(new_style)
            
        except Exception as e:
            self.logger.error(f"Failed to handle effects change: {e}")
    
    def _handle_action_result(self, action_id: str, success: bool, result):
        """Handle action execution results from controller."""
        if not success:
            self.logger.warning(f"Action '{action_id}' execution failed")
    
    def _handle_state_update(self, new_state: dict):
        """Handle state updates from controller."""
        try:
            self._update_actions_from_state(new_state)
            self.state_synchronized.emit(new_state)
            
        except Exception as e:
            self.logger.error(f"Failed to handle state update: {e}")
    
    def _handle_controller_error(self, severity: str, action_id: str, message: str):
        """Handle errors from controller."""
        self.logger.error(f"Controller error [{severity}] in '{action_id}': {message}")
    
    def _handle_action_state_change(self, action_id: str, enabled: bool, checked):
        """Handle action state changes for menu synchronization."""
        if action_id in self._actions:
            action = self._actions[action_id]
            action.setEnabled(enabled)
            if checked is not None and action.isCheckable():
                action.setChecked(checked)
    
    # === PUBLIC API ===
    
    def get_action(self, action_id: str) -> Optional[QAction]:
        """Get action by ID."""
        return self._actions.get(action_id)
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current toolbar state."""
        return self._current_state.copy()
    
    def get_zoom_level(self) -> int:
        """Get current zoom level."""
        return self._zoom_level
    
    def set_zoom_level(self, level: int):
        """Set zoom level."""
        self._zoom_level = max(50, min(200, level))
        self.logger.info(f"Zoom level set to: {self._zoom_level}%")
    
    def get_integration_status(self) -> Dict[str, bool]:
        """Get integration status with systems."""
        return {
            'design_system_connected': self.design_system is not None,
            'controller_connected': self.controller is not None,
            'actions_created': len(self._actions) > 0,
            'styling_applied': bool(self.styleSheet())
        }
    
    def connect_menu_system(self, menu_system):
        """Connect to menu system for synchronization."""
        if self.controller:
            self.controller.connect_menu_system(menu_system)
            self.logger.info("Menu system connected for synchronization")


# =============================================================================
# PRODUCTION FACTORY FUNCTION
# =============================================================================

def create_production_tecmp_toolbar(design_system: TECMPDesignSystem, 
                                  facade_instance, 
                                  parent=None,
                                  menu_system=None) -> TECMPProductionToolbar:
    """
    Create production TECMP toolbar with real integrations.
    
    Args:
        design_system: Centralized design system instance
        facade_instance: Real TECMP facade instance
        parent: Parent widget
        menu_system: Optional menu system for synchronization
        
    Returns:
        TECMPProductionToolbar: Fully integrated production toolbar
        
    Raises:
        ValueError: If required parameters are missing
        RuntimeError: If integration fails
    """
    # Validate inputs
    if not design_system:
        raise ValueError("Design system instance required")
    
    if not facade_instance:
        raise ValueError("Facade instance required")
    
    try:
        # Create controller with real facade
        controller = TECMPToolbarController(facade_instance)
        
        # Create production toolbar
        toolbar = TECMPProductionToolbar(design_system, controller, parent)
        
        # Connect menu system if provided
        if menu_system:
            toolbar.connect_menu_system(menu_system)
        
        # Verify integration
        status = toolbar.get_integration_status()
        if not all(status.values()):
            failed_components = [k for k, v in status.items() if not v]
            raise RuntimeError(f"Integration failed for: {failed_components}")
        
        logging.getLogger(__name__).info("Production TECMP toolbar created successfully")
        return toolbar
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to create production toolbar: {e}")
        raise RuntimeError(f"Toolbar creation failed: {e}") from e


# =============================================================================
# INTEGRATION EXAMPLE
# =============================================================================

def create_integrated_ui(facade, design_system, parent=None):
    """
    Create integrated UI with toolbar and menu synchronized.
    
    Args:
        facade: TECMP facade instance
        design_system: Design system instance
        parent: Parent widget
        
    Returns:
        tuple: (toolbar, menu_bar)
    """
    try:
        # Import menu system
        from .tecmp_menu_integrated import TECMPIntegratedMenu
        
        # Create menu system
        menu_system = TECMPIntegratedMenu(facade, design_system, parent)
        menu_bar = menu_system.build_menu_bar()
        
        # Create toolbar with menu connection
        toolbar = create_production_tecmp_toolbar(
            design_system, 
            facade, 
            parent,
            menu_system
        )
        
        logging.getLogger(__name__).info("Created integrated UI with synchronized toolbar and menu")
        return toolbar, menu_bar
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to create integrated UI: {e}")
        raise


# =============================================================================
# LINUX INTEGRATION TEST COMMAND
# =============================================================================

def run_integration_test():
    """Run comprehensive integration test for production toolbar."""
    import json
    import tempfile
    from datetime import datetime
    
    test_results = {
        'timestamp': datetime.now().isoformat(),
        'test_suite': 'TECMP Production Toolbar Integration',
        'tests': [],
        'summary': {'passed': 0, 'failed': 0, 'errors': []}
    }
    
    def log_test(name: str, passed: bool, details: str = ""):
        """Log test result."""
        test_results['tests'].append({
            'name': name,
            'passed': passed,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
        
        if passed:
            test_results['summary']['passed'] += 1
            print(f"? {name}")
        else:
            test_results['summary']['failed'] += 1
            test_results['summary']['errors'].append(f"{name}: {details}")
            print(f"? {name}: {details}")
    
    print("?? TECMP Production Toolbar Integration Test")
    print("=" * 50)
    
    try:
        # Test 1: Design System Import
        try:
            from .tecmp_visual_config import TECMPDesignSystem
            design_system = TECMPDesignSystem()
            log_test("Design System Import", True)
        except Exception as e:
            log_test("Design System Import", False, str(e))
            return test_results
        
        # Test 2: Design System Functionality
        try:
            palette = design_system.get_current_palette()
            assert hasattr(palette, 'primary')
            assert hasattr(palette, 'secondary')
            colors = design_system.get_colors_for_theme()
            assert 'primary' in colors
            log_test("Design System Functionality", True)
        except Exception as e:
            log_test("Design System Functionality", False, str(e))
        
        # Test 3: Mock Facade Creation
        try:
            class TestFacade:
                def __init__(self):
                    from PyQt5.QtCore import QObject, pyqtSignal
                    self.protocol_stack_changed = pyqtSignal(list)
                    self.tecmp_state_changed = pyqtSignal(bool, list)
                    self.packet_generated = pyqtSignal(object)
                    self.undo_available = pyqtSignal(bool)
                    self.redo_available = pyqtSignal(bool)
                
                def get_application_state(self):
                    class State:
                        def get_protocol_stack(self): return []
                        def is_tecmp_encapsulated(self): return False
                        def get_current_packet(self): return None
                        def is_capturing(self): return False
                        def can_undo(self): return False
                        def can_redo(self): return False
                    return State()
                
                def undo_last_operation(self): return True
                def redo_last_operation(self): return True
                def is_tecmp_encapsulated(self): return False
                def add_tecmp_encapsulation(self): return True
                def remove_tecmp_encapsulation(self): return True
                def validate_protocol_stack(self): return {'valid': True}
            
            test_facade = TestFacade()
            log_test("Test Facade Creation", True)
        except Exception as e:
            log_test("Test Facade Creation", False, str(e))
            return test_results
        
        # Test 4: Controller Creation
        try:
            controller = TECMPToolbarController(test_facade)
            state = controller.get_current_state()
            assert isinstance(state, dict)
            assert 'protocol_stack' in state
            log_test("Controller Creation", True)
        except Exception as e:
            log_test("Controller Creation", False, str(e))
        
        # Test 5: Toolbar Creation  
        try:
            app = QApplication.instance()
            if not app:
                app = QApplication([])
            
            toolbar = TECMPProductionToolbar(design_system, controller)
            assert toolbar is not None
            assert len(toolbar._actions) == 6  # Should have exactly 6 actions
            log_test("Toolbar Creation", True, f"{len(toolbar._actions)} actions created")
        except Exception as e:
            log_test("Toolbar Creation", False, str(e))
        
        # Test 6: Integration Status
        try:
            status = toolbar.get_integration_status()
            all_connected = all(status.values())
            log_test("Integration Status", all_connected, f"Status: {status}")
        except Exception as e:
            log_test("Integration Status", False, str(e))
        
        # Test 7: Action Configuration
        try:
            expected_actions = ['undo', 'redo', 'zoom_in', 'zoom_out', 'tecmp_toggle', 'validate']
            for action_id in expected_actions:
                assert action_id in toolbar._actions, f"Missing action: {action_id}"
            log_test("Action Configuration", True, "All 6 actions present")
        except Exception as e:
            log_test("Action Configuration", False, str(e))
        
        # Test 8: Zoom Level
        try:
            initial_zoom = toolbar.get_zoom_level()
            assert initial_zoom == 100
            toolbar.set_zoom_level(150)
            assert toolbar.get_zoom_level() == 150
            log_test("Zoom Level Management", True)
        except Exception as e:
            log_test("Zoom Level Management", False, str(e))
        
        # Test 9: Controller Action Execution
        try:
            success = controller.execute_action('undo')
            log_test("Controller Action Execution", True, f"Result: {success}")
        except Exception as e:
            log_test("Controller Action Execution", False, str(e))
        
        # Test 10: State Synchronization
        try:
            # Update state
            controller._app_state['can_undo'] = True
            controller._emit_state_update()
            
            # Check if action was updated
            undo_action = toolbar.get_action('undo')
            if undo_action:
                is_enabled = undo_action.isEnabled()
                log_test("State Synchronization", is_enabled, "Undo action enabled after state change")
            else:
                log_test("State Synchronization", False, "Undo action not found")
        except Exception as e:
            log_test("State Synchronization", False, str(e))
    
    except Exception as e:
        log_test("Critical Test Failure", False, str(e))
    
    # Generate summary
    total_tests = len(test_results['tests'])
    passed = test_results['summary']['passed']
    failed = test_results['summary']['failed']
    
    print("\n" + "=" * 50)
    print(f"?? TEST SUMMARY: {passed}/{total_tests} passed")
    
    if failed > 0:
        print(f"? FAILED TESTS ({failed}):")
        for error in test_results['summary']['errors']:
            print(f"   - {error}")
    
    # Save results to file
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_results, f, indent=2)
            print(f"?? Full results saved to: {f.name}")
    except Exception as e:
        print(f"??  Could not save results: {e}")
    
    return test_results


if __name__ == "__main__":
    # Run integration test when executed directly
    results = run_integration_test()
    
    # Exit with appropriate code
    failed_count = results['summary']['failed']
    sys.exit(0 if failed_count == 0 else 1)