#!/usr/bin/env python
# coding: utf-8
"""
GUI Adapter for TECMP-Tool.

This adapter provides a graphical user interface that connects to the central
TECMPFacade, providing a complete GUI experience for the TECMP tool.
"""
import logging
import sys
import os
from typing import Dict, Any, List, Optional, Tuple

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QMenuBar, QStatusBar, QToolBar, QAction, QFileDialog,
    QMessageBox, QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
    QComboBox, QSpinBox, QCheckBox, QGroupBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QObject, QSettings, QSize, QPoint
)
from PyQt5.QtGui import (
    QIcon, QPixmap, QPalette, QFont, QKeySequence, QTextCursor, QColor
)

# Import the central facade and related components
from core.interfaces.facade.tecmp_facade import TECMPFacade
from core.interfaces.controllers.core.error_handler import ErrorSeverity, ErrorCategory


class GUIAdapter(QMainWindow):
    """
    Main GUI window that adapts the TECMPFacade for graphical interaction.
    
    This adapter provides a complete graphical interface including:
    - Menu and toolbar for common operations
    - Protocol stack management
    - Packet preview and editing
    - Trace capture and analysis
    - Configuration dialogs
    - Status monitoring
    """
    
    def __init__(self, facade: TECMPFacade):
        """
        Initialize the GUI adapter.
        
        Args:
            facade: Central TECMP facade instance
        """
        super().__init__()
        self.facade = facade
        self.logger = logging.getLogger("TECMP-Tool.GUIAdapter")
        
        # UI Components
        self.central_widget = None
        self.protocol_tree = None
        self.preview_widget = None
        self.structure_widget = None
        self.trace_table = None
        self.status_label = None
        self.progress_bar = None
        
        # State
        self.current_protocols = []
        self.current_packets = []
        self.is_capturing = False
        
        # Settings
        self.settings = QSettings("TECMP-Tool", "GUIAdapter")
        
        # Initialize UI
        self._setup_ui()
        self._setup_connections()
        self._setup_styling()
        self._restore_state()
        
        # Register with facade
        self.facade.register_observer(self)
        
        self.logger.info("GUI Adapter initialized successfully")
    
    def _setup_ui(self):
        """Setup the user interface components."""
        self.setWindowTitle("TECMP Network Packet Builder")
        self.setMinimumSize(1200, 800)
        
        # Central widget with splitter layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(self.central_widget)
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Left panel - Protocol management
        left_panel = self._create_protocol_panel()
        main_splitter.addWidget(left_panel)
        
        # Right panel - Preview and analysis
        right_panel = self._create_preview_panel()
        main_splitter.addWidget(right_panel)
        
        # Set splitter proportions
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        
        # Create menu bar
        self._create_menu_bar()
        
        # Create toolbar
        self._create_toolbar()
        
        # Create status bar
        self._create_status_bar()
    
    def _create_protocol_panel(self) -> QWidget:
        """Create the protocol management panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Protocol stack section
        protocol_group = QGroupBox("Protocol Stack")
        protocol_layout = QVBoxLayout(protocol_group)
        
        # Protocol tree
        self.protocol_tree = QTreeWidget()
        self.protocol_tree.setHeaderLabels(["Protocol", "Configuration"])
        self.protocol_tree.setRootIsDecorated(False)
        self.protocol_tree.setAlternatingRowColors(True)
        protocol_layout.addWidget(self.protocol_tree)
        
        # Protocol management buttons
        button_layout = QHBoxLayout()
        
        self.add_protocol_btn = QPushButton("Add Protocol")
        self.add_protocol_btn.clicked.connect(self._on_add_protocol_clicked)
        button_layout.addWidget(self.add_protocol_btn)
        
        self.remove_protocol_btn = QPushButton("Remove")
        self.remove_protocol_btn.clicked.connect(self._on_remove_protocol_clicked)
        self.remove_protocol_btn.setEnabled(False)
        button_layout.addWidget(self.remove_protocol_btn)
        
        self.move_up_btn = QPushButton("?")
        self.move_up_btn.clicked.connect(self._on_move_up_clicked)
        self.move_up_btn.setEnabled(False)
        button_layout.addWidget(self.move_up_btn)
        
        self.move_down_btn = QPushButton("?")
        self.move_down_btn.clicked.connect(self._on_move_down_clicked)
        self.move_down_btn.setEnabled(False)
        button_layout.addWidget(self.move_down_btn)
        
        protocol_layout.addLayout(button_layout)
        layout.addWidget(protocol_group)
        
        # TECMP encapsulation section
        tecmp_group = QGroupBox("TECMP Encapsulation")
        tecmp_layout = QVBoxLayout(tecmp_group)
        
        self.tecmp_status_label = QLabel("Status: Inactive")
        tecmp_layout.addWidget(self.tecmp_status_label)
        
        tecmp_button_layout = QHBoxLayout()
        
        self.add_tecmp_btn = QPushButton("Add TECMP")
        self.add_tecmp_btn.clicked.connect(self._on_add_tecmp_clicked)
        tecmp_button_layout.addWidget(self.add_tecmp_btn)
        
        self.remove_tecmp_btn = QPushButton("Remove TECMP")
        self.remove_tecmp_btn.clicked.connect(self._on_remove_tecmp_clicked)
        self.remove_tecmp_btn.setEnabled(False)
        tecmp_button_layout.addWidget(self.remove_tecmp_btn)
        
        self.config_tecmp_btn = QPushButton("Configure")
        self.config_tecmp_btn.clicked.connect(self._on_config_tecmp_clicked)
        tecmp_button_layout.addWidget(self.config_tecmp_btn)
        
        tecmp_layout.addLayout(tecmp_button_layout)
        layout.addWidget(tecmp_group)
        
        # Available protocols section
        available_group = QGroupBox("Available Protocols")
        available_layout = QVBoxLayout(available_group)
        
        self.available_protocols = QListWidget()
        self._populate_available_protocols()
        available_layout.addWidget(self.available_protocols)
        
        layout.addWidget(available_group)
        
        return panel
    
    def _create_preview_panel(self) -> QWidget:
        """Create the preview and analysis panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Tab widget for different views
        tab_widget = QTabWidget()
        
        # Packet preview tab
        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        
        # Preview controls
        preview_controls = QHBoxLayout()
        
        self.hex_view_cb = QCheckBox("Hex View")
        self.hex_view_cb.toggled.connect(self._on_hex_view_toggled)
        preview_controls.addWidget(self.hex_view_cb)
        
        self.dark_mode_cb = QCheckBox("Dark Mode")
        self.dark_mode_cb.toggled.connect(self._on_dark_mode_toggled)
        preview_controls.addWidget(self.dark_mode_cb)
        
        preview_controls.addStretch()
        
        self.update_preview_btn = QPushButton("Update Preview")
        self.update_preview_btn.clicked.connect(self._on_update_preview_clicked)
        preview_controls.addWidget(self.update_preview_btn)
        
        preview_layout.addLayout(preview_controls)
        
        # Preview splitter
        preview_splitter = QSplitter(Qt.Vertical)
        
        # Packet content preview
        self.preview_widget = QTextEdit()
        self.preview_widget.setReadOnly(True)
        self.preview_widget.setFont(QFont("Consolas", 10))
        preview_splitter.addWidget(self.preview_widget)
        
        # Packet structure preview
        self.structure_widget = QTextEdit()
        self.structure_widget.setReadOnly(True)
        preview_splitter.addWidget(self.structure_widget)
        
        preview_splitter.setStretchFactor(0, 1)
        preview_splitter.setStretchFactor(1, 1)
        preview_layout.addWidget(preview_splitter)
        
        tab_widget.addTab(preview_tab, "Packet Preview")
        
        # Trace analysis tab
        trace_tab = QWidget()
        trace_layout = QVBoxLayout(trace_tab)
        
        # Trace controls
        trace_controls = QHBoxLayout()
        
        self.open_trace_btn = QPushButton("Open Trace")
        self.open_trace_btn.clicked.connect(self._on_open_trace_clicked)
        trace_controls.addWidget(self.open_trace_btn)
        
        self.start_capture_btn = QPushButton("Start Capture")
        self.start_capture_btn.clicked.connect(self._on_start_capture_clicked)
        trace_controls.addWidget(self.start_capture_btn)
        
        self.stop_capture_btn = QPushButton("Stop Capture")
        self.stop_capture_btn.clicked.connect(self._on_stop_capture_clicked)
        self.stop_capture_btn.setEnabled(False)
        trace_controls.addWidget(self.stop_capture_btn)
        
        trace_controls.addStretch()
        
        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.clicked.connect(self._on_analyze_clicked)
        trace_controls.addWidget(self.analyze_btn)
        
        trace_layout.addLayout(trace_controls)
        
        # Trace table
        self.trace_table = QTableWidget()
        self.trace_table.setColumnCount(4)
        self.trace_table.setHorizontalHeaderLabels(["#", "Time", "Source", "Protocol"])
        self.trace_table.horizontalHeader().setStretchLastSection(True)
        self.trace_table.setAlternatingRowColors(True)
        self.trace_table.setSelectionBehavior(QTableWidget.SelectRows)
        trace_layout.addWidget(self.trace_table)
        
        tab_widget.addTab(trace_tab, "Trace Analysis")
        
        # Analysis results tab
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        
        self.analysis_widget = QTextEdit()
        self.analysis_widget.setReadOnly(True)
        analysis_layout.addWidget(self.analysis_widget)
        
        tab_widget.addTab(analysis_tab, "Analysis Results")
        
        layout.addWidget(tab_widget)
        
        return panel
    
    def _create_menu_bar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        # New project
        new_action = QAction("New Project", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._on_new_project)
        file_menu.addAction(new_action)
        
        # Open project
        open_action = QAction("Open Project", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)
        
        # Save project
        save_action = QAction("Save Project", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._on_save_project)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        # Import/Export
        import_action = QAction("Import Trace", self)
        import_action.triggered.connect(self._on_import_trace)
        file_menu.addAction(import_action)
        
        export_action = QAction("Export Packet", self)
        export_action.triggered.connect(self._on_export_packet)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # Exit
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        # Undo/Redo (if available)
        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self._on_undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self._on_redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        # Clear all
        clear_action = QAction("Clear All Protocols", self)
        clear_action.triggered.connect(self._on_clear_protocols)
        edit_menu.addAction(clear_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        # Packet generator
        generate_action = QAction("Generate Packet", self)
        generate_action.triggered.connect(self._on_generate_packet)
        tools_menu.addAction(generate_action)
        
        # Settings
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._on_settings)
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        # About
        about_action = QAction("About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self):
        """Create the application toolbar."""
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setMovable(False)
        
        # Quick actions
        toolbar.addAction("New", self._on_new_project)
        toolbar.addAction("Open", self._on_open_project)
        toolbar.addAction("Save", self._on_save_project)
        toolbar.addSeparator()
        
        toolbar.addAction("Add Protocol", self._on_add_protocol_clicked)
        toolbar.addAction("Add TECMP", self._on_add_tecmp_clicked)
        toolbar.addSeparator()
        
        toolbar.addAction("Generate", self._on_generate_packet)
        toolbar.addAction("Analyze", self._on_analyze_clicked)
    
    def _create_status_bar(self):
        """Create the application status bar."""
        status_bar = self.statusBar()
        
        # Status label
        self.status_label = QLabel("Ready")
        status_bar.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_bar.addPermanentWidget(self.progress_bar)
        
        # Additional info
        self.info_label = QLabel("")
        status_bar.addPermanentWidget(self.info_label)
    
    def _setup_connections(self):
        """Setup signal connections with the facade."""
        # Connect facade signals
        self.facade.state_changed.connect(self._on_facade_state_changed)
        self.facade.operation_completed.connect(self._on_operation_completed)
        self.facade.error_occurred.connect(self._on_error_occurred)
        self.facade.protocol_updated.connect(self._on_protocol_updated)
        self.facade.preview_updated.connect(self._on_preview_updated)
        self.facade.trace_loaded.connect(self._on_trace_loaded)
        self.facade.capture_status_changed.connect(self._on_capture_status_changed)
        
        # Connect UI signals
        self.protocol_tree.itemSelectionChanged.connect(self._on_protocol_selection_changed)
        self.trace_table.itemSelectionChanged.connect(self._on_trace_selection_changed)
    
    def _setup_styling(self):
        """Setup UI styling and themes."""
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #e0e0e0;
                border: 1px solid #bbb;
                border-radius: 3px;
                padding: 5px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #999;
            }
            QTreeWidget, QListWidget, QTableWidget {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
    
    def _restore_state(self):
        """Restore window state from settings."""
        # Restore geometry
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # Restore window state
        window_state = self.settings.value("windowState")
        if window_state:
            self.restoreState(window_state)
        
        # Restore splitter state
        splitter_state = self.settings.value("splitterState")
        if splitter_state and hasattr(self, 'main_splitter'):
            self.main_splitter.restoreState(splitter_state)
    
    def _save_state(self):
        """Save window state to settings."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        if hasattr(self, 'main_splitter'):
            self.settings.setValue("splitterState", self.main_splitter.saveState())
    
    def _populate_available_protocols(self):
        """Populate the available protocols list."""
        protocols = [
            "Ethernet", "IPv4", "IPv6", "TCP", "UDP", "ICMP", "ICMPv6",
            "ARP", "VLAN", "HTTP", "HTTPS", "DNS", "DHCP", "SOME/IP",
            "CAN", "CAN-FD", "LIN", "FlexRay"
        ]
        
        for protocol in protocols:
            item = QListWidgetItem(protocol)
            item.setData(Qt.UserRole, protocol)
            self.available_protocols.addItem(item)
    
    def _update_protocol_tree(self):
        """Update the protocol tree display."""
        self.protocol_tree.clear()
        
        protocols = self.facade.get_protocol_stack()
        for i, protocol in enumerate(protocols):
            item = QTreeWidgetItem()
            
            # Extract protocol name and config
            if isinstance(protocol, dict):
                name = protocol.get('name', f'Protocol {i+1}')
                config = protocol.get('config', {})
            else:
                name = str(protocol)
                config = {}
            
            item.setText(0, name)
            
            # Show basic config info
            if config:
                config_summary = ", ".join([f"{k}={v}" for k, v in list(config.items())[:3]])
                if len(config) > 3:
                    config_summary += "..."
                item.setText(1, config_summary)
            
            item.setData(0, Qt.UserRole, i)  # Store index
            self.protocol_tree.addTopLevelItem(item)
        
        # Update TECMP status
        if self.facade.is_tecmp_encapsulated():
            self.tecmp_status_label.setText("Status: Active")
            self.add_tecmp_btn.setEnabled(False)
            self.remove_tecmp_btn.setEnabled(True)
        else:
            self.tecmp_status_label.setText("Status: Inactive")
            self.add_tecmp_btn.setEnabled(len(protocols) > 0)
            self.remove_tecmp_btn.setEnabled(False)
        
        # Update button states
        self._update_button_states()
    
    def _update_button_states(self):
        """Update the state of various buttons."""
        has_selection = bool(self.protocol_tree.selectedItems())
        protocol_count = self.protocol_tree.topLevelItemCount()
        
        self.remove_protocol_btn.setEnabled(has_selection)
        self.move_up_btn.setEnabled(has_selection)
        self.move_down_btn.setEnabled(has_selection)
        
        # Update preview button
        self.update_preview_btn.setEnabled(protocol_count > 0)
    
    def _update_trace_table(self, packets):
        """Update the trace table with packet data."""
        self.trace_table.setRowCount(len(packets))
        
        for i, packet in enumerate(packets):
            # Packet number
            self.trace_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            
            # Time (if available)
            time_str = "N/A"
            if hasattr(packet, 'time'):
                time_str = f"{packet.time:.6f}"
            self.trace_table.setItem(i, 1, QTableWidgetItem(time_str))
            
            # Source (if available)
            source_str = "N/A"
            if hasattr(packet, 'src'):
                source_str = str(packet.src)
            self.trace_table.setItem(i, 2, QTableWidgetItem(source_str))
            
            # Protocol
            protocol_str = packet.__class__.__name__ if hasattr(packet, '__class__') else "Unknown"
            self.trace_table.setItem(i, 3, QTableWidgetItem(protocol_str))
    
    # Event handlers for facade signals
    
    def _on_facade_state_changed(self, state_name, data):
        """Handle facade state changes."""
        self.logger.debug(f"Facade state changed: {state_name}")
        
        if state_name == "protocol_added":
            self._update_protocol_tree()
        elif state_name == "protocol_removed":
            self._update_protocol_tree()
        elif state_name == "tecmp_encapsulation_added":
            self._update_protocol_tree()
        elif state_name == "tecmp_encapsulation_removed":
            self._update_protocol_tree()
        elif state_name == "current_packet_changed":
            self._on_update_preview_clicked()
    
    def _on_operation_completed(self, success, message):
        """Handle operation completion."""
        if success:
            self.status_label.setText(f"? {message}")
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setText(f"? {message}")
            self.status_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "Operation Failed", message)
        
        # Clear status after 5 seconds
        QTimer.singleShot(5000, lambda: self.status_label.setText("Ready"))
        QTimer.singleShot(5000, lambda: self.status_label.setStyleSheet(""))
    
    def _on_error_occurred(self, error_info):
        """Handle error occurrences."""
        error_message = str(error_info) if error_info else "Unknown error occurred"
        self.logger.error(f"Error occurred: {error_message}")
        
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")
    
    def _on_protocol_updated(self):
        """Handle protocol stack updates."""
        self._update_protocol_tree()
    
    def _on_preview_updated(self):
        """Handle preview updates."""
        # Preview is handled by the preview controller
        pass
    
    def _on_trace_loaded(self, packets):
        """Handle trace loading."""
        self.current_packets = packets
        self._update_trace_table(packets)
        self.status_label.setText(f"Loaded {len(packets)} packets")
    
    def _on_capture_status_changed(self, is_active, status):
        """Handle capture status changes."""
        self.is_capturing = is_active
        
        self.start_capture_btn.setEnabled(not is_active)
        self.stop_capture_btn.setEnabled(is_active)
        
        if is_active:
            self.status_label.setText(f"Capturing... {status}")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
        else:
            self.status_label.setText(status)
            self.progress_bar.setVisible(False)
    
    # Event handlers for UI interactions
    
    def _on_add_protocol_clicked(self):
        """Handle add protocol button click."""
        selected_items = self.available_protocols.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a protocol to add.")
            return
        
        protocol_name = selected_items[0].data(Qt.UserRole)
        
        # Add protocol through facade
        success = self.facade.add_protocol(protocol_name)
        if success:
            self._update_protocol_tree()
    
    def _on_remove_protocol_clicked(self):
        """Handle remove protocol button click."""
        selected_items = self.protocol_tree.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        index = item.data(0, Qt.UserRole)
        
        # Remove protocol through facade
        success = self.facade.remove_protocol(index)
        if success:
            self._update_protocol_tree()
    
    def _on_move_up_clicked(self):
        """Handle move protocol up."""
        selected_items = self.protocol_tree.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        index = item.data(0, Qt.UserRole)
        
        if index > 0:
            success = self.facade.move_protocol(index, index - 1)
            if success:
                self._update_protocol_tree()
    
    def _on_move_down_clicked(self):
        """Handle move protocol down."""
        selected_items = self.protocol_tree.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        index = item.data(0, Qt.UserRole)
        
        protocol_count = self.protocol_tree.topLevelItemCount()
        if index < protocol_count - 1:
            success = self.facade.move_protocol(index, index + 1)
            if success:
                self._update_protocol_tree()
    
    def _on_add_tecmp_clicked(self):
        """Handle add TECMP encapsulation."""
        success = self.facade.add_tecmp_encapsulation()
        if success:
            self._update_protocol_tree()
    
    def _on_remove_tecmp_clicked(self):
        """Handle remove TECMP encapsulation."""
        reply = QMessageBox.question(
            self, "Remove TECMP", 
            "Are you sure you want to remove TECMP encapsulation?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success = self.facade.remove_tecmp_encapsulation()
            if success:
                self._update_protocol_tree()
    
    def _on_config_tecmp_clicked(self):
        """Handle TECMP configuration."""
        # Open TECMP configuration dialog
        QMessageBox.information(self, "TECMP Configuration", "TECMP configuration dialog would open here.")
    
    def _on_protocol_selection_changed(self):
        """Handle protocol tree selection changes."""
        self._update_button_states()
    
    def _on_trace_selection_changed(self):
        """Handle trace table selection changes."""
        selected_rows = set()
        for item in self.trace_table.selectedItems():
            selected_rows.add(item.row())
        
        if selected_rows and self.current_packets:
            # Show first selected packet in preview
            row = min(selected_rows)
            if row < len(self.current_packets):
                packet = self.current_packets[row]
                self.facade.set_current_packet(packet)
    
    def _on_hex_view_toggled(self, checked):
        """Handle hex view toggle."""
        self.facade.set_hex_view(checked)
    
    def _on_dark_mode_toggled(self, checked):
        """Handle dark mode toggle."""
        self.facade.set_dark_mode(checked)
    
    def _on_update_preview_clicked(self):
        """Handle update preview button click."""
        self.facade.update_preview()
    
    def _on_open_trace_clicked(self):
        """Handle open trace file."""
        success = self.facade.open_trace_file()
        if not success:
            QMessageBox.warning(self, "Open Trace", "Failed to open trace file.")
    
    def _on_start_capture_clicked(self):
        """Handle start packet capture."""
        success = self.facade.start_capture()
        if not success:
            QMessageBox.warning(self, "Start Capture", "Failed to start packet capture.")
    
    def _on_stop_capture_clicked(self):
        """Handle stop packet capture."""
        success = self.facade.stop_capture()
        if not success:
            QMessageBox.warning(self, "Stop Capture", "Failed to stop packet capture.")
    
    def _on_analyze_clicked(self):
        """Handle analyze packets button click."""
        if not self.current_packets:
            QMessageBox.information(self, "No Data", "No packets to analyze. Load a trace first.")
            return
        
        # Analyze packets through facade
        results = self.facade.analyze_packets(self.current_packets)
        
        # Display results
        if results:
            analysis_text = self._format_analysis_results(results)
            self.analysis_widget.setPlainText(analysis_text)
        else:
            self.analysis_widget.setPlainText("Analysis failed or no results available.")
    
    def _format_analysis_results(self, results):
        """Format analysis results for display."""
        text = "Packet Analysis Results\n"
        text += "=" * 50 + "\n\n"
        
        # Basic statistics
        text += f"Total Packets: {results.get('total_packets', 0)}\n"
        
        # Protocol distribution
        protocols = results.get('protocols', {})
        if protocols:
            text += "\nProtocol Distribution:\n"
            text += "-" * 20 + "\n"
            for protocol, count in protocols.items():
                text += f"  {protocol}: {count}\n"
        
        # Packet sizes
        sizes = results.get('packet_sizes', {})
        if sizes:
            text += "\nPacket Sizes:\n"
            text += "-" * 20 + "\n"
            text += f"  Min: {sizes.get('min', 0)} bytes\n"
            text += f"  Max: {sizes.get('max', 0)} bytes\n"
            text += f"  Avg: {sizes.get('avg', 0):.2f} bytes\n"
        
        # Time analysis
        time_info = results.get('time_analysis', {})
        if time_info and time_info.get('duration'):
            text += "\nTime Analysis:\n"
            text += "-" * 20 + "\n"
            text += f"  Duration: {time_info.get('duration', 0):.3f} seconds\n"
        
        # TECMP statistics
        tecmp_stats = results.get('tecmp_stats', {})
        if tecmp_stats and tecmp_stats.get('count', 0) > 0:
            text += "\nTECMP Statistics:\n"
            text += "-" * 20 + "\n"
            text += f"  TECMP Packets: {tecmp_stats.get('count', 0)}\n"
            
            data_types = tecmp_stats.get('data_types', {})
            if data_types:
                text += "  Data Types:\n"
                for data_type, count in data_types.items():
                    text += f"    0x{data_type:02X}: {count}\n"
        
        return text
    
    # Menu event handlers
    
    def _on_new_project(self):
        """Handle new project."""
        reply = QMessageBox.question(
            self, "New Project",
            "Create a new project? All unsaved changes will be lost.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Clear current state
            self.protocol_tree.clear()
            self.preview_widget.clear()
            self.structure_widget.clear()
            self.trace_table.setRowCount(0)
            self.analysis_widget.clear()
            self.current_packets = []
            
            self.status_label.setText("New project created")
    
    def _on_open_project(self):
        """Handle open project."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", 
            "TECMP Project Files (*.tecmp);;JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            success = self.facade.load_file(file_path, "project")
            if success:
                self.status_label.setText(f"Opened project: {file_path}")
            else:
                QMessageBox.warning(self, "Open Project", f"Failed to open project: {file_path}")
    
    def _on_save_project(self):
        """Handle save project."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", 
            "TECMP Project Files (*.tecmp);;JSON Files (*.json)"
        )
        
        if file_path:
            # Create project data
            project_data = {
                "version": "1.0",
                "protocols": self.facade.get_protocol_stack(),
                "tecmp_encapsulated": self.facade.is_tecmp_encapsulated(),
                "settings": {
                    "hex_view": self.hex_view_cb.isChecked(),
                    "dark_mode": self.dark_mode_cb.isChecked()
                }
            }
            
            success = self.facade.save_file(file_path, project_data, "project")
            if success:
                self.status_label.setText(f"Saved project: {file_path}")
            else:
                QMessageBox.warning(self, "Save Project", f"Failed to save project: {file_path}")
    
    def _on_import_trace(self):
        """Handle import trace."""
        success = self.facade.open_trace_file()
        if not success:
            QMessageBox.warning(self, "Import Trace", "Failed to import trace file.")
    
    def _on_export_packet(self):
        """Handle export packet."""
        current_packet = self.facade.get_current_packet()
        if not current_packet:
            QMessageBox.information(self, "No Packet", "No packet to export. Generate or load a packet first.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Packet", "", 
            "PCAP Files (*.pcap);;Binary Files (*.bin);;All Files (*)"
        )
        
        if file_path:
            packet_bytes = self.facade.get_packet_bytes(current_packet)
            if packet_bytes:
                success = self.facade.save_file(file_path, packet_bytes, "pcap")
                if success:
                    self.status_label.setText(f"Exported packet: {file_path}")
                else:
                    QMessageBox.warning(self, "Export Packet", f"Failed to export packet: {file_path}")
            else:
                QMessageBox.warning(self, "Export Packet", "Failed to serialize packet.")
    
    def _on_undo(self):
        """Handle undo operation."""
        QMessageBox.information(self, "Undo", "Undo functionality not yet implemented.")
    
    def _on_redo(self):
        """Handle redo operation."""
        QMessageBox.information(self, "Redo", "Redo functionality not yet implemented.")
    
    def _on_clear_protocols(self):
        """Handle clear all protocols."""
        reply = QMessageBox.question(
            self, "Clear Protocols",
            "Are you sure you want to clear all protocols?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Remove all protocols
            protocol_count = self.protocol_tree.topLevelItemCount()
            for i in range(protocol_count - 1, -1, -1):
                self.facade.remove_protocol(i)
            
            self._update_protocol_tree()
    
    def _on_generate_packet(self):
        """Handle generate packet."""
        protocols = self.facade.get_protocol_stack()
        if not protocols:
            QMessageBox.information(self, "No Protocols", "Add some protocols first.")
            return
        
        try:
            # Create a TECMP packet if encapsulated, or build from stack
            if self.facade.is_tecmp_encapsulated():
                packet = self.facade.create_tecmp_packet()
            else:
                # Build packet from protocol stack
                packet = self._build_packet_from_stack(protocols)
            
            if packet:
                self.facade.set_current_packet(packet)
                self.status_label.setText("Packet generated successfully")
            else:
                QMessageBox.warning(self, "Generate Packet", "Failed to generate packet.")
                
        except Exception as e:
            QMessageBox.critical(self, "Generate Packet", f"Error generating packet: {str(e)}")
    
    def _build_packet_from_stack(self, protocols):
        """Build a packet from the protocol stack."""
        # This is a simplified implementation
        # In a real implementation, you would use the packet building logic
        QMessageBox.information(self, "Generate Packet", 
                               "Direct packet building from protocol stack not yet implemented.\n"
                               "Try using TECMP encapsulation instead.")
        return None
    
    def _on_settings(self):
        """Handle settings dialog."""
        QMessageBox.information(self, "Settings", "Settings dialog not yet implemented.")
    
    def _on_about(self):
        """Handle about dialog."""
        QMessageBox.about(self, "About TECMP Tool",
                         "TECMP Network Packet Builder\n\n"
                         "A tool for building and analyzing TECMP-encapsulated network packets.\n\n"
                         "Version: 1.0\n"
                         "Built with PyQt5 and Python 3")
    
    # Window event handlers
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Save state
        self._save_state()
        
        # Check for unsaved changes
        if self.facade.has_unsaved_changes() if hasattr(self.facade, 'has_unsaved_changes') else False:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "There are unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self._on_save_project()
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        
        # Stop any running operations
        if self.is_capturing:
            self.facade.stop_capture()
        
        # Shutdown facade
        if hasattr(self.facade, 'shutdown'):
            self.facade.shutdown()
        
        event.accept()


def run_gui(facade: TECMPFacade = None):
    """
    Run the GUI application.
    
    Args:
        facade: Optional pre-configured facade instance
    """
    app = QApplication(sys.argv)
    app.setApplicationName("TECMP Tool")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("TECMP-Tool")
    
    # Create facade if not provided
    if facade is None:
        facade = TECMPFacade()
        facade.initialize()
    
    # Create and show main window
    window = GUIAdapter(facade)
    window.show()
    
    # Setup preview controller widgets if available
    if facade.preview:
        facade.preview.set_preview_widget(window.preview_widget)
        facade.preview.set_structure_widget(window.structure_widget)
    
    # Run application
    return app.exec_()


if __name__ == "__main__":
    sys.exit(run_gui())