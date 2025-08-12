#!/usr/bin/env python3
"""
TECMP Integrated Menu System - Design-System First + Facade Plug & Play
Simplified and direct architecture for perfect integration without duplication.

? Design-System First: Uses TECMPDesignSystem as single source
? Facade Plug & Play: Direct connection without mocks
? Zero Duplication: Reuses existing components
? Clean Architecture: Clear separation of responsibilities
"""

import logging
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass
from enum import Enum, auto

from PyQt5.QtWidgets import (
    QMenuBar, QMenu, QAction, QActionGroup, QApplication, QFileDialog, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QKeySequence
from PyQt5.QtGui import QIcon, QFont


class MenuSection(Enum):
    """Main menu sections."""
    FILE = "File"
    EDIT = "Edit" 
    VIEW = "View"
    TECMP = "TECMP"
    ANALYSIS = "Analysis"


@dataclass
class MenuActionSpec:
    """Menu action specification."""
    text: str
    icon_name: str
    method_name: str
    tooltip: str = ""
    shortcut: str = ""
    checkable: bool = False
    separator_after: bool = False
    is_submenu: bool = False
    submenu_items: List['MenuActionSpec'] = None


class TECMPIntegratedMenu(QObject):
    """
    TECMP Integrated Menu - Design-System First + Facade Plug & Play
    
    Pure architecture that directly uses:
    - TECMPDesignSystem for style and icons
    - TECMPFacade for real actions
    - No code duplication
    """
    
    # Signals for communication
    action_executed = pyqtSignal(str, bool)
    menu_state_changed = pyqtSignal(str, dict)
    
    def __init__(self, facade, design_system, parent=None):
        """
        Initialize the integrated menu.
        
        Args:
            facade: TECMPFacade instance (real connection)
            design_system: TECMPDesignSystem instance (unified style)
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Direct references - no mocks
        self.facade = facade
        self.design_system = design_system
        self.parent = parent
        
        # Logger
        self.logger = logging.getLogger(f"{__name__}.TECMPIntegratedMenu")
        
        # Storage
        self.menu_bar = None
        self.menus: Dict[str, QMenu] = {}
        self.actions: Dict[str, QAction] = {}
        self.action_groups: Dict[str, QActionGroup] = {}
        
        # Zoom level tracking
        self._current_zoom = 100
        
        # Action configuration (single source of truth)
        self.action_specs = self._define_action_specifications()
        
        # Facade connections (real connections)
        self._connect_facade_signals()
        
        # Design system connections
        self._connect_design_system_signals()
        
        self.logger.info("TECMP integrated menu initialized - Design-System First")
    
    def _define_action_specifications(self) -> Dict[MenuSection, List[MenuActionSpec]]:
        """Define all action specifications (single source)."""
        return {
            MenuSection.FILE: [
                MenuActionSpec("&Open File...", "open", "_open_file", 
                              "Open existing file", "Ctrl+O"),
                MenuActionSpec("&Save File", "save", "_save_file", 
                              "Save current file", "Ctrl+S"),
                MenuActionSpec("&Load Trace...", "trace", "_load_trace", 
                              "Load trace file", separator_after=True),
                MenuActionSpec("&Export", "export", "_export_submenu",
                              "Export options", is_submenu=True,
                              submenu_items=[
                                  MenuActionSpec("Export as &PCAP", "export", "_export_pcap",
                                               "Export to PCAP format"),
                                  MenuActionSpec("Export as &JSON", "export", "_export_json", 
                                               "Export to JSON format")
                              ], separator_after=True),
                MenuActionSpec("E&xit", "exit", "_exit_application", 
                              "Exit application", "Ctrl+Q")
            ],
            
            MenuSection.EDIT: [
                MenuActionSpec("&Preferences...", "preferences", "_show_preferences", 
                              "Open preferences", "Ctrl+,")
            ],
            
            MenuSection.VIEW: [
                MenuActionSpec("&Zoom", "zoom", "_zoom_submenu",
                              "Zoom options", is_submenu=True,
                              submenu_items=[
                                  MenuActionSpec("50%", "zoom", "_zoom_50", "Set zoom to 50%"),
                                  MenuActionSpec("100%", "zoom", "_zoom_100", "Set zoom to 100%"),
                                  MenuActionSpec("150%", "zoom", "_zoom_150", "Set zoom to 150%"),
                                  MenuActionSpec("200%", "zoom", "_zoom_200", "Set zoom to 200%")
                              ], separator_after=True),
                MenuActionSpec("&Dark Mode", "dark_mode", "_toggle_dark_mode", 
                              "Toggle dark mode", "Ctrl+Shift+D", checkable=True),
                MenuActionSpec("&Hex View", "hex_view", "_toggle_hex_view", 
                              "Toggle hex view", "Ctrl+H", checkable=True, separator_after=True),
                MenuActionSpec("&Recent Operations", "recent", "_show_recent_operations", 
                              "Show recent operations")
            ],
            
            MenuSection.TECMP: [
                MenuActionSpec("&Load Template...", "template", "_load_template", 
                              "Load TECMP template", separator_after=True),
                MenuActionSpec("&Templates", "templates", "_templates_submenu",
                              "Available templates", is_submenu=True)
            ],
            
            MenuSection.ANALYSIS: [
                MenuActionSpec("&Performance Metrics", "performance", "_show_performance_metrics", 
                              "Show performance metrics"),
                MenuActionSpec("&Statistics", "statistics", "_show_statistics", 
                              "Show statistics", separator_after=True),
                MenuActionSpec("&System Status", "status", "_show_system_status", 
                              "Show comprehensive system status")
            ]
        }
    
    def build_menu_bar(self) -> QMenuBar:
        """Build the complete menu bar."""
        try:
            self.menu_bar = QMenuBar(self.parent)
            
            # Apply design system style
            self._apply_design_system_style()
            
            # Build each section
            for section in MenuSection:
                menu = self._build_menu_section(section)
                self.menus[section.value] = menu
                self.menu_bar.addMenu(menu)
            
            # Initial state update
            self._update_menu_states()
            
            # Populate dynamic menus
            self._populate_templates_menu()
            
            self.logger.info("Menu bar built successfully")
            return self.menu_bar
            
        except Exception as e:
            self.logger.error(f"Error building menu bar: {e}")
            raise
    
    def _build_menu_section(self, section: MenuSection) -> QMenu:
        """Build a menu section."""
        try:
            menu = QMenu(section.value, self.parent)
            
            # Get specifications for this section
            specs = self.action_specs.get(section, [])
            
            for spec in specs:
                if spec.is_submenu:
                    # Create submenu
                    submenu = QMenu(spec.text, self.parent)
                    if spec.submenu_items:
                        for sub_spec in spec.submenu_items:
                            sub_action = self._create_action(sub_spec)
                            submenu.addAction(sub_action)
                            # Store action
                            action_key = f"{section.value.lower()}_{sub_spec.icon_name}_{sub_spec.text.replace('&', '').replace(' ', '_').lower()}"
                            self.actions[action_key] = sub_action
                    menu.addMenu(submenu)
                    # Store submenu reference
                    menu_key = f"{section.value.lower()}_{spec.icon_name}_menu"
                    self.menus[menu_key] = submenu
                else:
                    # Create normal action
                    action = self._create_action(spec)
                    menu.addAction(action)
                    
                    # Store action
                    action_key = f"{section.value.lower()}_{spec.icon_name}"
                    self.actions[action_key] = action
                
                # Add separator if needed
                if spec.separator_after:
                    menu.addSeparator()
            
            return menu
            
        except Exception as e:
            self.logger.error(f"Error building section {section.value}: {e}")
            raise
    
    def _create_action(self, spec: MenuActionSpec) -> QAction:
        """Create an action from its specification."""
        try:
            # Get icon from design system
            icon = self.design_system.get_icon(spec.icon_name) if hasattr(self.design_system, 'get_icon') else QIcon()
            
            # Create action
            action = QAction(icon, spec.text, self.parent)
            
            # Configuration
            if spec.checkable:
                action.setCheckable(True)
            
            if spec.shortcut:
                action.setShortcut(QKeySequence(spec.shortcut))
                
            if spec.tooltip:
                tooltip_text = spec.tooltip
                if spec.shortcut:
                    tooltip_text += f" ({spec.shortcut})"
                action.setToolTip(tooltip_text)
                action.setStatusTip(spec.tooltip)
            
            # Signal connection
            action.triggered.connect(lambda checked=False: self._execute_action(spec.method_name, spec.checkable, checked))
            
            return action
            
        except Exception as e:
            self.logger.error(f"Error creating action {spec.text}: {e}")
            raise
    
    def _execute_action(self, method_name: str, is_checkable: bool = False, checked: bool = False):
        """Execute a menu action."""
        try:
            # Special actions (internal methods)
            if method_name.startswith('_'):
                method = getattr(self, method_name, None)
                if method:
                    if is_checkable:
                        result = method(checked)
                    else:
                        result = method()
                    success = result is not False
                else:
                    self.logger.warning(f"Internal method not found: {method_name}")
                    success = False
            else:
                # Facade actions (direct connection)
                method = getattr(self.facade, method_name, None)
                if method:
                    if is_checkable:
                        result = method(checked) if 'checked' in method.__code__.co_varnames else method()
                    else:
                        result = method()
                    success = result is not False
                else:
                    self.logger.warning(f"Facade method not found: {method_name}")
                    success = False
            
            # Emit result signal
            self.action_executed.emit(method_name, success)
            
            # Update states if necessary
            if success:
                self._update_menu_states()
            
        except Exception as e:
            self.logger.error(f"Error executing action {method_name}: {e}")
            self.action_executed.emit(method_name, False)
    
    def _apply_design_system_style(self):
        """Apply design system style to menu."""
        try:
            if not hasattr(self.design_system, 'get_current_palette'):
                return
            
            palette = self.design_system.get_current_palette()
            
            # CSS style based on design system
            style = f"""
            QMenuBar {{
                background: {palette.surface};
                color: {palette.on_surface};
                border: none;
                padding: {self.design_system.get_spacing('sm')}px;
                font-family: '{self.design_system.get_typography('font_family_primary')}';
                font-size: {self.design_system.get_typography('font_size_base')}px;
            }}
            
            QMenuBar::item {{
                background: transparent;
                padding: {self.design_system.get_spacing('sm')}px {self.design_system.get_spacing('md')}px;
                border-radius: {self.design_system.get_radius('sm')}px;
                margin: 2px;
            }}
            
            QMenuBar::item:selected {{
                background: {palette.primary};
                color: {palette.on_primary};
            }}
            
            QMenu {{
                background: {palette.surface};
                color: {palette.on_surface};
                border: 1px solid {palette.neutral_200};
                border-radius: {self.design_system.get_radius('md')}px;
                padding: {self.design_system.get_spacing('sm')}px;
            }}
            
            QMenu::item {{
                padding: {self.design_system.get_spacing('sm')}px {self.design_system.get_spacing('md')}px;
                border-radius: {self.design_system.get_radius('sm')}px;
                margin: 1px;
            }}
            
            QMenu::item:selected {{
                background: {palette.primary};
                color: {palette.on_primary};
            }}
            
            QMenu::separator {{
                height: 1px;
                background: {palette.neutral_200};
                margin: {self.design_system.get_spacing('xs')}px {self.design_system.get_spacing('md')}px;
            }}
            """
            
            if self.menu_bar:
                self.menu_bar.setStyleSheet(style)
                
        except Exception as e:
            self.logger.error(f"Error applying style: {e}")
    
    def _connect_facade_signals(self):
        """Connect facade signals for automatic updates."""
        try:
            # Direct connections to real facade signals
            if hasattr(self.facade, 'file_saved'):
                self.facade.file_saved.connect(self._on_file_saved)
            
            if hasattr(self.facade, 'file_loaded'):
                self.facade.file_loaded.connect(self._on_file_loaded)
            
            if hasattr(self.facade, 'operation_completed'):
                self.facade.operation_completed.connect(self._on_operation_completed)
            
            self.logger.info("Facade signals connected")
            
        except Exception as e:
            self.logger.error(f"Error connecting facade signals: {e}")
    
    def _connect_design_system_signals(self):
        """Connect design system signals."""
        try:
            if hasattr(self.design_system, 'theme_changed'):
                self.design_system.theme_changed.connect(self._on_theme_changed)
            
            if hasattr(self.design_system, 'colors_changed'):
                self.design_system.colors_changed.connect(self._on_colors_changed)
            
            self.logger.info("Design system signals connected")
            
        except Exception as e:
            self.logger.error(f"Error connecting design system signals: {e}")
    
    def _update_menu_states(self):
        """Update menu action states according to facade state."""
        try:
            # Dark mode and hex view state
            if 'view_dark_mode' in self.actions:
                is_dark = self.facade.get_setting('ui', 'dark_mode_enabled', False)
                self.actions['view_dark_mode'].setChecked(is_dark)
            
            if 'view_hex_view' in self.actions:
                is_hex = self.facade.get_setting('ui', 'hex_view_enabled', False)
                self.actions['view_hex_view'].setChecked(is_hex)
            
        except Exception as e:
            self.logger.error(f"Error updating menu states: {e}")
    
    def _populate_templates_menu(self):
        """Populate the templates submenu dynamically."""
        try:
            templates_menu = self.menus.get('tecmp_templates_menu')
            if not templates_menu:
                return
            
            # Clear existing items
            templates_menu.clear()
            
            # Get available templates
            templates = self.facade.get_available_templates() if hasattr(self.facade, 'get_available_templates') else {}
            
            if templates:
                for template_name in sorted(templates.keys()):
                    action = QAction(template_name, self.parent)
                    action.triggered.connect(lambda checked, name=template_name: self._load_specific_template(name))
                    templates_menu.addAction(action)
            else:
                action = QAction("No templates available", self.parent)
                action.setEnabled(False)
                templates_menu.addAction(action)
                
        except Exception as e:
            self.logger.error(f"Error populating templates menu: {e}")
    
    # === SIGNAL HANDLERS ===
    
    def _on_file_saved(self, path: str, size: int):
        """Handler for file saved."""
        self.menu_state_changed.emit("file", {"saved": True, "path": path})
    
    def _on_file_loaded(self, path: str, file_type: str):
        """Handler for file loaded."""
        self.menu_state_changed.emit("file", {"loaded": True, "path": path})
    
    def _on_operation_completed(self, success: bool, message: str, result):
        """Handler for operation completed."""
        self._update_menu_states()
    
    def _on_theme_changed(self, theme_name: str):
        """Handler for theme changed."""
        self._apply_design_system_style()
    
    def _on_colors_changed(self, colors_dict: dict):
        """Handler for colors changed."""
        self._apply_design_system_style()
    
    # === INTERNAL METHODS (SPECIAL ACTIONS) ===
    
    # File menu actions
    def _open_file(self):
        """Open a file."""
        try:
            filename, _ = QFileDialog.getOpenFileName(
                self.parent, "Open File", "", "All Files (*)"
            )
            if filename:
                return self.facade.load_file(filename)
            return False
        except Exception as e:
            self.logger.error(f"Error opening file: {e}")
            return False
    
    def _save_file(self):
        """Save current file."""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self.parent, "Save File", "", "All Files (*)"
            )
            if filename:
                return self.facade.save_file(filename)
            return False
        except Exception as e:
            self.logger.error(f"Error saving file: {e}")
            return False
    
    def _load_trace(self):
        """Load trace file."""
        try:
            return self.facade.load_trace_file() if hasattr(self.facade, 'load_trace_file') else False
        except Exception as e:
            self.logger.error(f"Error loading trace: {e}")
            return False
    
    def _export_pcap(self):
        """Export as PCAP."""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self.parent, "Export PCAP", "", "PCAP Files (*.pcap)"
            )
            if filename:
                return self.facade.export_pcap(filename)
            return False
        except Exception as e:
            self.logger.error(f"Error exporting PCAP: {e}")
            return False
    
    def _export_json(self):
        """Export as JSON."""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self.parent, "Export JSON", "", "JSON Files (*.json)"
            )
            if filename:
                return self.facade.save_file(filename, file_type='json')
            return False
        except Exception as e:
            self.logger.error(f"Error exporting JSON: {e}")
            return False
    
    def _exit_application(self):
        """Exit the application."""
        try:
            if self.parent:
                self.parent.close()
            return True
        except Exception as e:
            self.logger.error(f"Error exiting application: {e}")
            return False
    
    # Edit menu actions
    def _show_preferences(self):
        """Show preferences dialog."""
        try:
            # Placeholder for preferences dialog
            self.logger.info("Showing preferences")
            # Could show a dialog with facade.get_setting()/set_setting()
            return True
        except Exception as e:
            self.logger.error(f"Error showing preferences: {e}")
            return False
    
    # View menu actions
    def _set_zoom(self, level: int):
        """Set zoom level internally."""
        try:
            self._current_zoom = level
            self.logger.info(f"Zoom set to {level}%")
            self.menu_state_changed.emit("view", {"zoom": level})
            return True
        except Exception as e:
            self.logger.error(f"Error changing zoom: {e}")
            return False
    
    def _zoom_50(self):
        """Set zoom to 50%."""
        return self._set_zoom(50)
    
    def _zoom_100(self):
        """Set zoom to 100%."""
        return self._set_zoom(100)
    
    def _zoom_150(self):
        """Set zoom to 150%."""
        return self._set_zoom(150)
    
    def _zoom_200(self):
        """Set zoom to 200%."""
        return self._set_zoom(200)
    
    def _toggle_dark_mode(self, checked: bool):
        """Toggle dark mode."""
        try:
            if hasattr(self.design_system, 'set_dark_mode'):
                self.design_system.set_dark_mode(checked)
            return self.facade.set_setting('ui', 'dark_mode_enabled', checked)
        except Exception as e:
            self.logger.error(f"Error toggling dark mode: {e}")
            return False
    
    def _toggle_hex_view(self, checked: bool):
        """Toggle hex view."""
        try:
            return self.facade.set_setting('ui', 'hex_view_enabled', checked)
        except Exception as e:
            self.logger.error(f"Error toggling hex view: {e}")
            return False
    
    def _show_recent_operations(self):
        """Show recent operations."""
        try:
            operations = self.facade.get_recent_operations() if hasattr(self.facade, 'get_recent_operations') else []
            # Could show in a dialog
            self.logger.info(f"Recent operations: {len(operations)} items")
            return True
        except Exception as e:
            self.logger.error(f"Error showing recent operations: {e}")
            return False
    
    # TECMP menu actions
    def _load_template(self):
        """Load a TECMP template."""
        try:
            templates = self.facade.get_available_templates() if hasattr(self.facade, 'get_available_templates') else {}
            if templates:
                template_names = list(templates.keys())
                template_name, ok = QInputDialog.getItem(
                    self.parent, "Load Template", "Select template:", template_names, 0, False
                )
                if ok and template_name:
                    config = self.facade.load_config_template(template_name)
                    if config:
                        self.logger.info(f"Template loaded: {template_name}")
                        return True
            return False
        except Exception as e:
            self.logger.error(f"Error loading template: {e}")
            return False
    
    def _load_specific_template(self, template_name: str):
        """Load a specific template."""
        try:
            config = self.facade.load_config_template(template_name)
            if config:
                self.logger.info(f"Template loaded: {template_name}")
                QMessageBox.information(self.parent, "Template Loaded", 
                                      f"Template '{template_name}' loaded successfully")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error loading template {template_name}: {e}")
            return False
    
    # Analysis menu actions
    def _show_performance_metrics(self):
        """Show performance metrics."""
        try:
            metrics = self.facade.get_performance_metrics() if hasattr(self.facade, 'get_performance_metrics') else {}
            # Could show in a dialog
            self.logger.info(f"Performance metrics retrieved: {len(metrics)} items")
            return True
        except Exception as e:
            self.logger.error(f"Error showing metrics: {e}")
            return False
    
    def _show_statistics(self):
        """Show statistics."""
        try:
            stats = self.facade.get_statistics() if hasattr(self.facade, 'get_statistics') else {}
            # Could show in a dialog
            self.logger.info(f"Statistics retrieved: {len(stats)} items")
            return True
        except Exception as e:
            self.logger.error(f"Error showing statistics: {e}")
            return False
    
    def _show_system_status(self):
        """Show comprehensive system status."""
        try:
            status = self.facade.get_comprehensive_status() if hasattr(self.facade, 'get_comprehensive_status') else {}
            # Could show in a dialog
            self.logger.info(f"System status retrieved")
            return True
        except Exception as e:
            self.logger.error(f"Error showing system status: {e}")
            return False


# === CREATION FUNCTION ===

def create_tecmp_integrated_menu(facade, design_system, parent=None) -> QMenuBar:
    """
    Create a TECMP integrated menu.
    
    Args:
        facade: TECMPFacade instance
        design_system: TECMPDesignSystem instance  
        parent: Parent widget
        
    Returns:
        QMenuBar: Configured menu bar
    """
    try:
        menu_system = TECMPIntegratedMenu(facade, design_system, parent)
        return menu_system.build_menu_bar()
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Error creating integrated menu: {e}")
        raise


# === USAGE EXAMPLE ===

if __name__ == "__main__":
    """Example integration with real facade and design system."""
    
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
    
    # Simulate real components (in real app, imports from their modules)
    class MockTECMPFacade:
        def __init__(self):
            self.settings = {
                'ui': {
                    'dark_mode_enabled': False,
                    'hex_view_enabled': False
                }
            }
            
        def load_file(self, path):
            print(f"? Loading file: {path}")
            return True
            
        def save_file(self, path, file_type=None):
            print(f"? Saving file: {path} (type: {file_type})")
            return True
            
        def load_trace_file(self):
            print("? Loading trace file")
            return True
            
        def export_pcap(self, path):
            print(f"? Exporting PCAP: {path}")
            return True
            
        def get_setting(self, section, key, default=None):
            return self.settings.get(section, {}).get(key, default)
            
        def set_setting(self, section, key, value):
            if section not in self.settings:
                self.settings[section] = {}
            self.settings[section][key] = value
            print(f"? Setting {section}.{key} = {value}")
            return True
            
        def get_recent_operations(self):
            return [
                {"operation": "load_file", "time": "10:30:15"},
                {"operation": "export_pcap", "time": "10:35:22"}
            ]
            
        def load_config_template(self, name):
            print(f"? Loading template: {name}")
            return {"name": name, "data": {}}
            
        def get_available_templates(self):
            return {
                "Basic Ethernet": {},
                "TCP/IP Stack": {},
                "TECMP Logging": {}
            }
            
        def get_performance_metrics(self):
            return {"cpu": 45, "memory": 60, "operations": 150}
            
        def get_statistics(self):
            return {"packets": 1000, "errors": 5, "success_rate": 99.5}
            
        def get_comprehensive_status(self):
            return {"status": "healthy", "uptime": 3600, "components": 15}
    
    class MockTECMPDesignSystem:
        def get_current_palette(self):
            class Palette:
                surface = "#ffffff"
                on_surface = "#333333"
                primary = "#4facfe"
                on_primary = "#ffffff"
                neutral_200 = "#e2e8f0"
            return Palette()
            
        def get_spacing(self, size):
            return {"xs": 4, "sm": 8, "md": 16}[size]
            
        def get_radius(self, size):
            return {"sm": 4, "md": 8}[size]
            
        def get_typography(self, prop):
            return {"font_family_primary": "Arial", "font_size_base": 14}[prop]
            
        def get_icon(self, name):
            from PyQt5.QtGui import QIcon
            return QIcon()  # Empty icon for demo
            
        def set_dark_mode(self, enabled):
            print(f"? Dark mode: {enabled}")
    
    class TestMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("TECMP-Tool - Integrated Menu System")
            self.setGeometry(100, 100, 1000, 700)
            
            # Real components (simulation)
            self.facade = MockTECMPFacade()
            self.design_system = MockTECMPDesignSystem()
            
            # Integrated menu
            menu_bar = create_tecmp_integrated_menu(
                self.facade, 
                self.design_system, 
                self
            )
            self.setMenuBar(menu_bar)
            
            # Interface
            central_widget = QWidget()
            layout = QVBoxLayout(central_widget)
            
            info_label = QLabel("""
            <h2>? TECMP Integrated Menu System</h2>
            <p><b>5 Menus - 16 Actions:</b></p>
            <ul>
                <li><b>File:</b> Open, Save, Load Trace, Export (PCAP/JSON), Exit</li>
                <li><b>Edit:</b> Preferences</li>
                <li><b>View:</b> Zoom (50/100/150/200%), Dark Mode, Hex View, Recent Operations</li>
                <li><b>TECMP:</b> Load Template, Templates List</li>
                <li><b>Analysis:</b> Performance Metrics, Statistics, System Status</li>
            </ul>
            <p><i>All actions are directly connected to the facade!</i></p>
            """)
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            self.setCentralWidget(central_widget)
            
            # Style
            self.setStyleSheet("""
                QMainWindow {
                    background: #f8f9fa;
                }
                QLabel {
                    background: white;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px;
                }
            """)
            
            self.statusBar().showMessage("Integrated Menu System - Ready")
    
    # Application
    app = QApplication(sys.argv)
    
    # Main window
    window = TestMainWindow()
    window.show()
    
    print("=== TECMP Integrated Menu System ===")
    print("? 5 Menus - 16 Actions")
    print("? Design-System First Architecture")
    print("? Facade Plug & Play Integration")
    print("? Zero Code Duplication")
    
    # Start
    sys.exit(app.exec_())
    
# Alias for compatibility
MenuBuilder = TECMPIntegratedMenu