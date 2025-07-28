#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# PyQt5
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# 1. Config/Settings
from core.config.config_loader import ConfigLoader
from core.config.settings_manager import SettingsManager

# 2. Core Services
from core.interfaces.controllers.core.error_handler import TECMPErrorHandler as ErrorHandler
from core.interfaces.controllers.core.memory_controller import MemoryController
from core.interfaces.controllers.core.undo_redo_controller import UndoRedoController
from core.interfaces.controllers.core.file_system_controller import FileSystemController

# 3. Factories
from core.factories.packet_factory import get_packet_registry
from core.factories.tecmp_factory import TECMPPacketFactory

# 4. Management
from core.management.packet_manager import PacketManager
from core.management.pcap_generator import PcapGenerator
from core.management.resource_manager import ResourceManager

# 5. Builders
from core.builders.packet_builder import RealPacketBuilder as PacketBuilder
from core.builders.tecmp_builder import TECMPPacketBuilder

# 6. Facade
from core.interfaces.facade.tecmp_facade import TECMPFacade

# 7. Business Controllers
from core.interfaces.controllers.protocol.protocol_validator import ProtocolValidator
from core.interfaces.controllers.protocol.protocol_stack_controller import ProtocolStackController
from core.interfaces.controllers.tecmp.tecmp_controller import TECMPController
from core.interfaces.controllers.tecmp.tecmp_encapsulation_manager import TECMPEncapsulationManager
from core.interfaces.controllers.trace.trace_controller import TraceController
from core.interfaces.controllers.trace.packet_analysis_controller import PacketAnalysisController

# 8. GUI Controllers
from core.interfaces.controllers.ui.preview_controller import PreviewController
from core.interfaces.controllers.ui.drag_drop_controller import DragDropController
from core.interfaces.controllers.ui.signal_connector import SignalConnectorController

# 9. GUI Builders
from core.interfaces.gui.builders.central_widget_builder import create_tecmp_integrated_central_widget
from core.interfaces.gui.builders.menu_builder import create_tecmp_integrated_menu
from core.interfaces.gui.builders.status_bar_builder import create_tecmp_integrated_status_bar
from core.interfaces.gui.builders.toolbar_builder import create_production_tecmp_toolbar
from core.interfaces.gui.builders.tecmp_visual_config import TECMPDesignSystem, TECMPColorScheme, apply_theme_to_application

# ================================================================================
# PATCH DRAG & DROP POUR MODE OFFSCREEN - FIXED
# ================================================================================

def apply_drag_drop_patch():
    """Patch automatique pour corriger le drag & drop en mode offscreen"""
    import os
    
    # Verifier si on est en mode offscreen
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        try:
            from core.interfaces.gui.builders.central_widget_builder import TECMPEnhancedCentralWidget
            
            def patched_show_protocol_config_dialog(self, protocol_name: str):
                """Version non-bloquante pour mode offscreen"""
                try:
                    from PyQt5.QtWidgets import QApplication
                    
                    app = QApplication.instance()
                    is_offscreen = app and app.platformName() == 'offscreen'
                    
                    from core.interfaces.gui.dialogs.protocol_config_dialog import ProtocolConfigDialog
                    dialog = ProtocolConfigDialog(protocol_name, None, self)
                    
                    if is_offscreen:
                        print(f"[PATCH] Mode offscreen: dialogue {protocol_name} simule")
                        config = dialog.get_configuration()
                        return config
                    else:
                        result = dialog.exec_()
                        if result == dialog.Accepted:
                            return dialog.get_configuration()
                        else:
                            return None
                except Exception as e:
                    print(f"[ERROR] Erreur dialogue {protocol_name}: {e}")
                    return None
            
            def patched_show_drop_error(self, message: str):
                """Show drop error message - FIXED"""
                print(f"[DROP ERROR] {message}")
                if hasattr(self, '_show_feedback'):
                    self._show_feedback(message, "error")
            
            def patched_show_feedback(self, message: str, feedback_type: str = "info"):
                """Show feedback message"""
                print(f"[{feedback_type.upper()}] {message}")
            
            # Appliquer les patches
            TECMPEnhancedCentralWidget._show_protocol_config_dialog = patched_show_protocol_config_dialog
            TECMPEnhancedCentralWidget._show_drop_error = patched_show_drop_error
            TECMPEnhancedCentralWidget._show_feedback = patched_show_feedback
            
            print("[OK] Patch drag & drop applique pour mode offscreen")
            return True
            
        except Exception as e:
            print(f"[WARNING] Erreur application patch: {e}")
            return False
    
    return False

# Appliquer le patch immediatement
apply_drag_drop_patch()

print("\n" + "="*80)
print("TECMP TOOL - PRODUCTION VERSION")
print("="*80)

class ComponentRegistry:
    def __init__(self):
        self.components = {}
        self.initialization_order = []
        
    def register(self, name: str, instance: Any):
        self.components[name] = instance
        self.initialization_order.append(name)
        logger.info(f"[OK] {name}")
        
    def get(self, name: str) -> Any:
        return self.components.get(name)

REGISTRY = ComponentRegistry()

# ================================================================================
# STEP 1: CONFIG / SETTINGS
# ================================================================================

def initialize_config_and_settings():
    logger.info("=" * 60)
    logger.info("STEP 1: CONFIG / SETTINGS")
    logger.info("=" * 60)
    
    # ConfigLoader
    try:
        config_loader = ConfigLoader(['config', 'configs', '.tecmp'])
        REGISTRY.register('config_loader', config_loader)
    except Exception as e:
        logger.error(f"ConfigLoader init failed: {e}")
        config_loader = None
        
    # SettingsManager
    try:
        settings_manager = SettingsManager()
        default_settings = {
            'core': {'log_errors': True, 'show_dialogs': True, 'max_errors': 1000},
            'advanced': {'memory_warning_threshold': 500, 'memory_critical_threshold': 1000},
            'file_system': {'base_dir': str(Path.home() / '.tecmp'), 'max_recent_files': 10, 'autosave_enabled': True},
            'ui': {'theme': 'azure_comfort', 'hex_view_enabled': False, 'preview_panel_visible': True, 'dark_mode_enabled': False},
            'protocol': {'strict_validation': False, 'auto_validate': True, 'auto_build_packets': True, 'max_stack_size': 20}
        }
        
        for section, values in default_settings.items():
            for key, value in values.items():
                settings_manager.set(section, key, value)
                
        REGISTRY.register('settings_manager', settings_manager)
    except Exception as e:
        logger.error(f"SettingsManager init failed: {e}")
        settings_manager = None
        
    return config_loader, settings_manager

# ================================================================================
# STEP 2: CORE SERVICES
# ================================================================================

def initialize_core_services(settings_manager):
    logger.info("=" * 60)
    logger.info("STEP 2: CORE SERVICES")
    logger.info("=" * 60)
    
    # ErrorHandler
    try:
        error_handler = ErrorHandler(
            log_errors=settings_manager.get('core', 'log_errors', True) if settings_manager else True,
            show_user_dialogs=settings_manager.get('core', 'show_dialogs', True) if settings_manager else True,
            max_error_history=settings_manager.get('core', 'max_errors', 1000) if settings_manager else 1000
        )
        REGISTRY.register('error_handler', error_handler)
    except Exception as e:
        logger.error(f"ErrorHandler init failed: {e}")
        error_handler = None
        
    # MemoryController - NOTE: start_monitoring() will be called AFTER QApplication
    try:
        memory_controller = MemoryController(
            warning_threshold_mb=settings_manager.get('advanced', 'memory_warning_threshold', 500) if settings_manager else 500,
            critical_threshold_mb=settings_manager.get('advanced', 'memory_critical_threshold', 1000) if settings_manager else 1000
        )
        REGISTRY.register('memory_controller', memory_controller)
        # DO NOT start monitoring here - wait for QApplication
        
    except Exception as e:
        logger.error(f"MemoryController init failed: {e}")
        memory_controller = None
        
    # UndoRedoController
    try:
        undo_redo_controller = UndoRedoController(max_history=100)
        REGISTRY.register('undo_redo_controller', undo_redo_controller)
    except Exception as e:
        logger.error(f"UndoRedoController init failed: {e}")
        undo_redo_controller = None
        
    # FileSystemController
    try:
        base_dir = settings_manager.get('file_system', 'base_dir') if settings_manager else str(Path.home() / '.tecmp')
        file_system_controller = FileSystemController(
            base_dir=base_dir,
            max_recent_files=settings_manager.get('file_system', 'max_recent_files', 10) if settings_manager else 10,
            autosave_enabled=settings_manager.get('file_system', 'autosave_enabled', True) if settings_manager else True
        )
        REGISTRY.register('file_system_controller', file_system_controller)
    except Exception as e:
        logger.error(f"FileSystemController init failed: {e}")
        file_system_controller = None
        
    return error_handler, memory_controller, undo_redo_controller, file_system_controller

# ================================================================================
# STEP 3: FACTORIES
# ================================================================================

def initialize_factories():
    logger.info("=" * 60)
    logger.info("STEP 3: FACTORIES")
    logger.info("=" * 60)
    
    # Packet Factory Registry
    try:
        packet_registry = get_packet_registry() if get_packet_registry else None
        if packet_registry:
            REGISTRY.register('packet_registry', packet_registry)
    except Exception as e:
        logger.error(f"PacketRegistry init failed: {e}")
        packet_registry = None
        
    # TECMP Factory
    try:
        tecmp_factory = TECMPPacketFactory()
        REGISTRY.register('tecmp_factory', tecmp_factory)
    except Exception as e:
        logger.error(f"TECMPFactory init failed: {e}")
        tecmp_factory = None
        
    return packet_registry, tecmp_factory

# ================================================================================
# STEP 4: MANAGEMENT
# ================================================================================

def initialize_management():
    logger.info("=" * 60)
    logger.info("STEP 4: MANAGEMENT")
    logger.info("=" * 60)
    
    # PacketManager
    try:
        packet_manager = PacketManager()
        REGISTRY.register('packet_manager', packet_manager)
    except Exception as e:
        logger.error(f"PacketManager init failed: {e}")
        packet_manager = None
        
    # PcapGenerator
    try:
        settings = REGISTRY.get('settings_manager')
        output_dir = settings.get('file_system', 'base_dir', '.') if settings else '.'
        pcap_generator = PcapGenerator(output_directory=output_dir)
        REGISTRY.register('pcap_generator', pcap_generator)
    except Exception as e:
        logger.error(f"PcapGenerator init failed: {e}")
        pcap_generator = None
        
    # ResourceManager
    try:
        resource_manager = ResourceManager()
        if hasattr(resource_manager, 'initialize'):
            resource_manager.initialize()
        REGISTRY.register('resource_manager', resource_manager)
    except Exception as e:
        logger.error(f"ResourceManager init failed: {e}")
        resource_manager = None
        
    return packet_manager, pcap_generator, resource_manager

# ================================================================================
# STEP 5: BUILDERS
# ================================================================================

def initialize_builders():
    logger.info("=" * 60)
    logger.info("STEP 5: BUILDERS")
    logger.info("=" * 60)
    
    # PacketBuilder
    try:
        packet_builder = PacketBuilder()
        REGISTRY.register('packet_builder', packet_builder)
    except Exception as e:
        logger.error(f"PacketBuilder init failed: {e}")
        packet_builder = None
        
    # TECMPPacketBuilder
    try:
        tecmp_builder = TECMPPacketBuilder()
        REGISTRY.register('tecmp_builder', tecmp_builder)
    except Exception as e:
        logger.error(f"TECMPBuilder init failed: {e}")
        tecmp_builder = None
        
    return packet_builder, tecmp_builder

# ================================================================================
# STEP 6: FACADE - SINGLE INSTANCE
# ================================================================================

def initialize_facade():
    logger.info("=" * 60)
    logger.info("STEP 6: TECMP FACADE (SINGLE INSTANCE)")
    logger.info("=" * 60)
    
    # Configuration for facade
    facade_config = {
        'settings_manager': REGISTRY.get('settings_manager'),
        'config_loader': REGISTRY.get('config_loader'),
        'error_handler': REGISTRY.get('error_handler'),
        'memory_controller': REGISTRY.get('memory_controller'),
        'undo_redo_controller': REGISTRY.get('undo_redo_controller'),
        'file_system_controller': REGISTRY.get('file_system_controller'),
        'packet_registry': REGISTRY.get('packet_registry'),
        'tecmp_factory': REGISTRY.get('tecmp_factory'),
        'packet_manager': REGISTRY.get('packet_manager'),
        'pcap_generator': REGISTRY.get('pcap_generator'),
        'resource_manager': REGISTRY.get('resource_manager'),
        'packet_builder': REGISTRY.get('packet_builder'),
        'tecmp_builder': REGISTRY.get('tecmp_builder')
    }
    
    # Create THE facade
    facade = TECMPFacade(config=facade_config)
    
    # Initialize the facade
    if not facade.initialize():
        logger.error("CRITICAL: Facade initialization failed!")
        raise RuntimeError("Cannot initialize TECMP Facade")
        
    REGISTRY.register('facade', facade)
    logger.info("[OK] TECMP Facade initialized successfully")
    
    return facade

# ================================================================================
# STEP 7: BUSINESS CONTROLLERS
# ================================================================================

def initialize_business_controllers(facade, settings_manager):
    logger.info("=" * 60)
    logger.info("STEP 7: BUSINESS CONTROLLERS")
    logger.info("=" * 60)
    
    # ProtocolValidator
    try:
        if hasattr(facade, 'protocol_validator') and facade.protocol_validator:
            protocol_validator = facade.protocol_validator
            logger.info("[OK] Reusing ProtocolValidator from facade")
        else:
            protocol_validator = ProtocolValidator()
        REGISTRY.register('protocol_validator', protocol_validator)
        logger.info("[OK] ProtocolValidator initialized successfully")
    except Exception as e:
        logger.error(f"ProtocolValidator init failed: {e}")
        protocol_validator = None
        
    # ProtocolStackController
    try:
        stack_controller = ProtocolStackController(
            facade=facade,
            validator=protocol_validator
        )
        REGISTRY.register('protocol_stack_controller', stack_controller)
        
        # Connection des builders
        packet_builder = REGISTRY.get('packet_builder')
        tecmp_builder = REGISTRY.get('tecmp_builder')
        
        if packet_builder and tecmp_builder:
            from types import SimpleNamespace
            builders = SimpleNamespace(
                packet_builder=packet_builder,
                tecmp_builder=tecmp_builder
            )
            stack_controller.set_builders(builders)
            logger.info("[OK] Builders connected to ProtocolStackController")
        else:
            logger.warning("Builders not available for ProtocolStackController")
        
        # Connection au PacketManager
        packet_manager = REGISTRY.get('packet_manager')
        if packet_manager:
            stack_controller.set_packet_manager(packet_manager)
            logger.info("[OK] PacketManager connected to ProtocolStackController")
        else:
            logger.warning("PacketManager not available for ProtocolStackController")
        
        # Apply configuration from settings with CORRECTION
        if settings_manager:
            protocol_settings = settings_manager.get('protocol', {})
            # IMPORTANT: Force strict_validation to False for better UX
            protocol_settings['strict_validation'] = False
            stack_controller.configure(protocol_settings)
            logger.info("[OK] ProtocolStackController configured from settings (strict_validation=False)")
        else:
            # If no settings_manager, still force strict_validation to False
            stack_controller.set_strict_validation(False)
            logger.info("[OK] ProtocolStackController strict_validation set to False")
            
    except Exception as e:
        logger.error(f"ProtocolStackController init failed: {e}")
        stack_controller = None
        
    # TECMPEncapsulationManager
    try:
        tecmp_manager = TECMPEncapsulationManager()
        REGISTRY.register('tecmp_manager', tecmp_manager)
        logger.info("[OK] TECMPEncapsulationManager initialized successfully")
    except Exception as e:
        logger.error(f"TECMPEncapsulationManager init failed: {e}")
        tecmp_manager = None
        
    # TECMPController
    try:
        tecmp_controller = TECMPController(
            main_window=None,
            tecmp_manager=tecmp_manager
        )
        REGISTRY.register('tecmp_controller', tecmp_controller)
        logger.info("[OK] TECMPController initialized successfully")
    except Exception as e:
        logger.error(f"TECMPController init failed: {e}")
        tecmp_controller = None
        
    # TraceController
    try:
        trace_controller = TraceController(main_window=None)
        REGISTRY.register('trace_controller', trace_controller)
        logger.info("[OK] TraceController initialized successfully")
    except Exception as e:
        logger.error(f"TraceController init failed: {e}")
        trace_controller = None
        
    # PacketAnalysisController
    try:
        analysis_controller = PacketAnalysisController()
        REGISTRY.register('packet_analysis_controller', analysis_controller)
        
        if hasattr(analysis_controller, 'set_facade'):
            analysis_controller.set_facade(facade)
            logger.info("[OK] PacketAnalysisController connected to facade")
            
        if hasattr(analysis_controller, 'set_trace_controller') and trace_controller:
            analysis_controller.set_trace_controller(trace_controller)
            logger.info("[OK] PacketAnalysisController connected to trace controller")
            
        if hasattr(analysis_controller, 'set_validator') and protocol_validator:
            analysis_controller.set_validator(protocol_validator)
            logger.info("[OK] PacketAnalysisController connected to validator")
        
        logger.info("[OK] PacketAnalysisController connected to facade, trace controller, and validator")
            
    except Exception as e:
        logger.error(f"PacketAnalysisController init failed: {e}")
        analysis_controller = None
    
    # Return components for later use
    return {
        'protocol_validator': protocol_validator,
        'stack_controller': stack_controller,
        'tecmp_manager': tecmp_manager,
        'tecmp_controller': tecmp_controller,
        'trace_controller': trace_controller,
        'packet_analysis_controller': analysis_controller
    }

# ================================================================================
# STEP 8: GUI CONTROLLERS (HEADLESS)
# ================================================================================

def initialize_gui_controllers(facade):
    logger.info("=" * 60)
    logger.info("STEP 8: GUI CONTROLLERS (HEADLESS)")
    logger.info("=" * 60)
    
    # PreviewController
    try:
        preview_controller = PreviewController(facade=facade)
        REGISTRY.register('preview_controller', preview_controller)
    except Exception as e:
        logger.error(f"PreviewController init failed: {e}")
        
    # SignalConnectorController
    try:
        signal_connector = SignalConnectorController(facade=facade)
        REGISTRY.register('signal_connector', signal_connector)
    except Exception as e:
        logger.error(f"SignalConnector init failed: {e}")
        
    # DragDropController
    try:
        drag_drop_controller = DragDropController(
            main_window=None,
            protocol_controller=REGISTRY.get('protocol_stack_controller'),
            tecmp_manager=REGISTRY.get('tecmp_manager')
        )
        REGISTRY.register('drag_drop_controller', drag_drop_controller)
    except Exception as e:
        logger.error(f"DragDropController init failed: {e}")

# ================================================================================
# MAIN WINDOW
# ================================================================================

class TECMPMainWindow(QMainWindow):
    def __init__(self, facade, registry):
        super().__init__()
        self.facade = facade
        self.registry = registry
        
        # Register window in facade
        self.facade.register_main_window(self)
        
        # Update controllers with window reference
        self._update_controllers_with_window()
        
        # Window configuration
        self.setWindowTitle("TECMP Tool - Production")
        self.setGeometry(100, 100, 1600, 1000)
        
        # Design system
        self.design_system = TECMPDesignSystem()
        self.design_system.set_color_scheme(TECMPColorScheme.AZURE_COMFORT)
        
        # Build interface
        self._build_interface()
        
        # Connect signals
        self._connect_facade_signals()
        
        logger.info("[OK] Main window initialized")
        
    def _update_controllers_with_window(self):
        """Update controllers with window reference"""
        # TECMPController
        tecmp_controller = self.registry.get('tecmp_controller')
        if tecmp_controller and hasattr(tecmp_controller, 'main_window'):
            tecmp_controller.main_window = self
            
        # TraceController
        trace_controller = self.registry.get('trace_controller')
        if trace_controller and hasattr(trace_controller, 'main_window'):
            trace_controller.main_window = self
            
        # DragDropController
        drag_drop = self.registry.get('drag_drop_controller')
        if drag_drop and hasattr(drag_drop, 'main_window'):
            drag_drop.main_window = self
            
    def _build_interface(self):
        """Build interface with real components"""
        
        self.central_widget = create_tecmp_integrated_central_widget(
            facade=self.facade,
            design_system=self.design_system,
            parent=self
        )
        
        # If the central widget needs controllers, set them
        if hasattr(self.central_widget, 'stack_controller'):
            self.central_widget.stack_controller = self.registry.get('protocol_stack_controller')
        if hasattr(self.central_widget, 'tecmp_manager'):
            self.central_widget.tecmp_manager = self.registry.get('tecmp_manager')
        if hasattr(self.central_widget, 'trace_controller'):
            self.central_widget.trace_controller = self.registry.get('trace_controller')
            
        self.setCentralWidget(self.central_widget)
        
        # Connect ProtocolStackController to views if available
        stack_controller = self.registry.get('protocol_stack_controller')
        if stack_controller and hasattr(stack_controller, 'connect_to_views'):
            if hasattr(self.central_widget, 'views'):
                stack_controller.connect_to_views(self.central_widget.views)
                logger.info("[OK] ProtocolStackController connected to views")
            elif hasattr(self.central_widget, 'protocol_view'):
                stack_controller.connect_to_views(self.central_widget)
                logger.info("[OK] ProtocolStackController connected to central widget")
        
        # Menu Bar
        self.menu_bar = create_tecmp_integrated_menu(
            facade=self.facade,
            design_system=self.design_system,
            parent=self
        )
        self.setMenuBar(self.menu_bar)
        
        # Status Bar
        self.status_bar = create_tecmp_integrated_status_bar(
            facade=self.facade,
            design_system=self.design_system,
            parent=self
        )
        
        # Add status widgets
        self.protocol_lbl = QLabel("Protocols: 0")
        self.memory_lbl = QLabel("Memory: 0 MB")
        self.theme_lbl = QLabel("Azure Comfort")
        self.conn_lbl = QLabel("Ready")
        
        for widget in (self.protocol_lbl, self.memory_lbl, self.theme_lbl, self.conn_lbl):
            widget.setStyleSheet("""
                QLabel {
                    padding: 5px 10px;
                    background: white;
                    border: 1px solid #dee2e6;
                    border-radius: 12px;
                    color: #495057;
                }
            """)
            self.status_bar.addPermanentWidget(widget)
            
        self.setStatusBar(self.status_bar)
        
        # Toolbar - CORRECTED
        self.toolbar = create_production_tecmp_toolbar(
            self.design_system,
            self.facade,
            self
        )
        self.addToolBar(self.toolbar)
        
    def _connect_facade_signals(self):
        """Connect facade signals"""
        logger.info("=" * 60)
        logger.info("STEP 10: CONNECTING SIGNALS")
        logger.info("=" * 60)
        
        # Protocol
        self.facade.protocol_added.connect(self._on_protocol_added)
        self.facade.protocol_removed.connect(self._on_protocol_removed)
        self.facade.protocol_stack_changed.connect(self._on_stack_changed)
        
        # Packet
        self.facade.packet_built.connect(self._on_packet_built)
        
        # TECMP
        self.facade.tecmp_encapsulation_changed.connect(self._on_tecmp_changed)
        
        # Errors
        self.facade.error_occurred.connect(self._on_error)
        
        # Memory
        self.facade.memory_warning.connect(self._on_memory_warning)
        
        logger.info("[OK] All signals connected")
        
    def _on_protocol_added(self, name, index):
        logger.info(f"Protocol added: {name}")
        self.statusBar().showMessage(f"Protocol '{name}' added", 3000)
        self._update_protocol_count()
        
    def _on_protocol_removed(self, index):
        logger.info("Protocol removed")
        self.statusBar().showMessage("Protocol removed", 3000)
        self._update_protocol_count()
        
    def _on_stack_changed(self, stack):
        self._update_protocol_count()
        
    def _update_protocol_count(self):
        count = len(self.facade.get_protocol_stack())
        self.protocol_lbl.setText(f"Protocols: {count}")
        
    def _on_packet_built(self, packet):
        logger.info("Packet built successfully")
        self.statusBar().showMessage("Packet generated!", 3000)
        
    def _on_tecmp_changed(self, is_active, protocols):
        status = "enabled" if is_active else "disabled"
        logger.info(f"TECMP {status}")
        self.statusBar().showMessage(f"TECMP {status}", 3000)
        
    def _on_memory_warning(self, usage_mb, message):
        logger.warning(f"Memory warning: {usage_mb:.1f} MB - {message}")
        self.statusBar().showMessage(f"Memory warning: {usage_mb:.1f} MB", 5000)
        
    def _on_error(self, error, context):
        logger.error(f"Error in {context}: {error}")
        QMessageBox.critical(self, "Error", f"Error: {str(error)}")
        
    def closeEvent(self, event):
        """Clean shutdown"""
        # Stop ALL monitoring
        for name in ["memory_controller", "tecmp_controller", 
                     "undo_redo_controller", "protocol_stack_controller"]:
            controller = self.registry.get(name)
            if controller and hasattr(controller, 'stop_monitoring'):
                try:
                    controller.stop_monitoring()
                    logger.info(f"[OK] {name} monitoring stopped")
                except Exception as e:
                    logger.warning(f"Error stopping {name}: {e}")
        
        # Shutdown facade
        self.facade.shutdown()
        event.accept()

# ================================================================================
# MAIN
# ================================================================================

def main():
    try:
        # STEP 1-8: Initialize all components BEFORE QApplication
        config_loader, settings_manager = initialize_config_and_settings()
        error_handler, memory_controller, undo_redo, file_system = initialize_core_services(settings_manager)
        packet_registry, tecmp_factory = initialize_factories()
        packet_manager, pcap_generator, resource_manager = initialize_management()
        packet_builder, tecmp_builder = initialize_builders()
        facade = initialize_facade()
        initialize_business_controllers(facade, settings_manager)
        initialize_gui_controllers(facade)
        
        # STEP 9: Qt Application
        logger.info("=" * 60)
        logger.info("STEP 9: QT APPLICATION")
        logger.info("=" * 60)
        
        app = QApplication(sys.argv)
        app.setApplicationName("TECMP Tool")
        app.setOrganizationName("TECMP")
        app.setStyle('Fusion')
        
        # Apply theme - CORRECTED with only 2 parameters
        apply_theme_to_application(app, TECMPColorScheme.AZURE_COMFORT)
        logger.info("[OK] Theme applied")
        
        # Start monitoring for controllers - IMPROVED
        controllers_to_monitor = {
            "memory_controller": REGISTRY.get("memory_controller"),
            "tecmp_controller": REGISTRY.get("tecmp_controller"),
            "undo_redo_controller": REGISTRY.get("undo_redo_controller"),
            "protocol_stack_controller": REGISTRY.get("protocol_stack_controller")
        }
        
        for name, controller in controllers_to_monitor.items():
            if controller is None:
                logger.warning(f"{name} not available")
                continue
                
            if hasattr(controller, "start_monitoring"):
                try:
                    controller.start_monitoring()
                    logger.info(f"[OK] {name} monitoring started")
                except Exception as e:
                    logger.warning(f"Failed to start monitoring for {name}: {e}")
            else:
                logger.debug(f"{name} does not have start_monitoring() method")
        
        # Create main window
        window = TECMPMainWindow(facade, REGISTRY)
        window.show()
        
        print("\n" + "="*80)
        print("TECMP TOOL - READY")
        print("="*80)
        print(f"[OK] {len(REGISTRY.initialization_order)} components initialized")
        print("[OK] All corrections applied")
        print("[OK] Ready for production!")
        print("="*80 + "\n")
        
        return app.exec_()
        
    except Exception as e:
        logger.critical(f"FATAL ERROR: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())