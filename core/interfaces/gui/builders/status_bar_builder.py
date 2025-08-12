#!/usr/bin/env python3
"""
TECMP Status Bar Builder - Production Grade with Real-Time Indicators
Uses TECMPDesignSystem for consistent styling
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from PyQt5.QtWidgets import (
    QStatusBar, QWidget, QHBoxLayout, QLabel, QProgressBar,
    QFrame, QPushButton, QVBoxLayout
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QPalette, QColor


class StatusIndicator(QWidget):
    """Custom indicator widget for status bar"""
    
    clicked = pyqtSignal()
    
    def __init__(self, label: str, initial_value: str = "-", 
                 color_theme: str = "primary", parent=None):
        super().__init__(parent)
        self.label_text = label
        self.color_theme = color_theme
        self._init_ui(initial_value)
        
    def _init_ui(self, initial_value: str):
        """Initialize the indicator interface"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        # Label
        self.label = QLabel(f"{self.label_text}:")
        self.label.setStyleSheet("color: #6c757d; font-weight: 500;")
        
        # Value
        self.value = QLabel(initial_value)
        self.value.setStyleSheet("color: #212529; font-weight: bold;")
        
        layout.addWidget(self.label)
        layout.addWidget(self.value)
        
    def set_value(self, value: str):
        """Update the displayed value"""
        self.value.setText(value)
        
    def set_color(self, color: str):
        """Change the value color"""
        self.value.setStyleSheet(f"color: {color}; font-weight: bold;")
        
    def mousePressEvent(self, event):
        """Emit signal when clicked"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class MemoryProgressBar(QProgressBar):
    """Custom progress bar for memory usage"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(True)
        self.setFormat("%v MB")
        self.setMaximumHeight(16)
        self.setMinimumWidth(120)
        

class TECMPStatusBar(QStatusBar):
    """
    Complete TECMP status bar with real-time indicators
    """
    
    # Custom signals
    memory_clicked = pyqtSignal()
    tecmp_clicked = pyqtSignal()
    protocols_clicked = pyqtSignal()
    
    def __init__(self, facade, design_system, parent=None):
        super().__init__(parent)
        self.facade = facade
        self.design_system = design_system
        self.logger = logging.getLogger(f"{__name__}.TECMPStatusBar")
        
        # Update timers
        self.time_timer = QTimer()
        self.memory_timer = QTimer()
        self.stats_timer = QTimer()
        
        # Widgets
        self.indicators = {}
        
        # Initialization
        self._init_ui()
        self._connect_signals()
        self._start_timers()
        self._apply_styling()
        
        self.logger.info("TECMPStatusBar initialized with real-time indicators")
        
    def _init_ui(self):
        """Initialize all status bar widgets"""
        
        # Temporary message (left part)
        self.showMessage("TECMP Tool Ready", 3000)
        
        # Main container for permanent widgets
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(12)
        
        # === INDICATORS ===
        
        # 1. Time
        self.indicators['time'] = StatusIndicator("Time", "00:00:00")
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['time'])
        
        # 2. Memory with progress bar
        memory_widget = QWidget()
        memory_layout = QHBoxLayout(memory_widget)
        memory_layout.setContentsMargins(8, 4, 8, 4)
        memory_layout.setSpacing(8)
        
        memory_label = QLabel("Memory:")
        memory_label.setStyleSheet("color: #6c757d; font-weight: 500;")
        
        self.memory_bar = MemoryProgressBar()
        self.memory_bar.setRange(0, 1000)  # Max 1000 MB
        
        self.memory_text = QLabel("0 MB")
        self.memory_text.setStyleSheet("color: #212529; font-weight: bold;")
        
        memory_layout.addWidget(memory_label)
        memory_layout.addWidget(self.memory_bar)
        memory_layout.addWidget(self.memory_text)
        
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(memory_widget)
        
        # 3. TECMP encapsulation
        self.indicators['tecmp'] = StatusIndicator("TECMP", "OFF")
        self.indicators['tecmp'].clicked.connect(self.tecmp_clicked.emit)
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['tecmp'])
        
        # 4. Protocol count
        self.indicators['protocols'] = StatusIndicator("Protocols", "0")
        self.indicators['protocols'].clicked.connect(self.protocols_clicked.emit)
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['protocols'])
        
        # 5. Generated packets
        self.indicators['packets'] = StatusIndicator("Packets", "0")
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['packets'])
        
        # 6. Capture state
        self.indicators['capture'] = StatusIndicator("Capture", "IDLE")
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['capture'])
        
        # 7. Operations
        self.indicators['operations'] = StatusIndicator("Ops", "0")
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['operations'])
        
        # 8. Mode/Theme
        self.indicators['theme'] = StatusIndicator("Theme", "Light")
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['theme'])
        
        # Add stretch to push to right
        container_layout.addStretch()
        
        # 9. Connection state with LED
        self.connection_led = QLabel("?")
        self.connection_led.setStyleSheet("color: #28a745; font-size: 16px;")
        self.connection_text = QLabel("Connected")
        self.connection_text.setStyleSheet("color: #28a745; font-weight: bold;")
        
        connection_layout = QHBoxLayout()
        connection_layout.setSpacing(4)
        connection_layout.addWidget(self.connection_led)
        connection_layout.addWidget(self.connection_text)
        
        connection_widget = QWidget()
        connection_widget.setLayout(connection_layout)
        
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(connection_widget)
        
        # Add container to status bar
        self.addPermanentWidget(container)
        
    def _create_separator(self) -> QFrame:
        """Create a vertical separator"""
        separator = QFrame()
        separator.setFrameStyle(QFrame.VLine | QFrame.Sunken)
        separator.setStyleSheet("""
            QFrame {
                color: #dee2e6;
                max-width: 1px;
                margin: 4px 0px;
            }
        """)
        return separator
        
    def _connect_signals(self):
        """Connect facade signals"""
        try:
            # Protocols
            if hasattr(self.facade, 'protocol_stack_changed'):
                self.facade.protocol_stack_changed.connect(self._update_protocol_count)
                
            # TECMP
            if hasattr(self.facade, 'tecmp_encapsulation_changed'):
                self.facade.tecmp_encapsulation_changed.connect(self._update_tecmp_status)
                
            # Packets
            if hasattr(self.facade, 'packet_built'):
                self.facade.packet_built.connect(self._on_packet_built)
                
            # Memory
            if hasattr(self.facade, 'memory_warning'):
                self.facade.memory_warning.connect(self._on_memory_warning)
                
            # Capture
            if hasattr(self.facade, 'capture_status_changed'):
                self.facade.capture_status_changed.connect(self._update_capture_status)
                
            # Operations
            if hasattr(self.facade, 'operation_completed'):
                self.facade.operation_completed.connect(self._on_operation_completed)
                
            # Theme
            if hasattr(self.design_system, 'theme_changed'):
                self.design_system.theme_changed.connect(self._update_theme_indicator)
                
            self.logger.info("Status bar signals connected")
            
        except Exception as e:
            self.logger.error(f"Error connecting signals: {e}")
            
    def _start_timers(self):
        """Start update timers"""
        # Timer for time (every second)
        self.time_timer.timeout.connect(self._update_time)
        self.time_timer.start(1000)
        
        # Timer for memory (every 2 seconds)
        self.memory_timer.timeout.connect(self._update_memory)
        self.memory_timer.start(2000)
        
        # Timer for stats (every 5 seconds)
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(5000)
        
        # Initial update
        self._update_time()
        self._update_memory()
        self._update_stats()
        
    def _apply_styling(self):
        """Apply design system styling"""
        try:
            palette = self.design_system.get_current_palette()
            
            style = f"""
                QStatusBar {{
                    background: {palette.surface};
                    border-top: 1px solid {palette.neutral_200};
                    min-height: 32px;
                }}
                
                QStatusBar::item {{
                    border: none;
                }}
                
                QProgressBar {{
                    background: {palette.neutral_100};
                    border: 1px solid {palette.neutral_300};
                    border-radius: 8px;
                    text-align: center;
                }}
                
                QProgressBar::chunk {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {palette.success},
                        stop:0.5 {palette.success_light},
                        stop:1 {palette.success});
                    border-radius: 7px;
                }}
            """
            
            self.setStyleSheet(style)
            
            # Style indicators
            for indicator in self.indicators.values():
                self._style_indicator(indicator)
                
        except Exception as e:
            self.logger.error(f"Error applying styling: {e}")
            
    def _style_indicator(self, indicator: StatusIndicator):
        """Style an individual indicator"""
        palette = self.design_system.get_current_palette()
        
        indicator.setStyleSheet(f"""
            StatusIndicator {{
                background: {palette.neutral_100};
                border: 1px solid {palette.neutral_200};
                border-radius: 12px;
                padding: 2px 8px;
            }}
            
            StatusIndicator:hover {{
                background: {palette.neutral_200};
                border-color: {palette.primary};
            }}
        """)
        
    # === REAL-TIME UPDATES ===
    
    def _update_time(self):
        """Update the time"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.indicators['time'].set_value(current_time)
        
    def _update_memory(self):
        """Update memory usage"""
        try:
            if hasattr(self.facade, 'memory_controller') and self.facade.memory_controller:
                memory_mb = self.facade.memory_controller.get_memory_usage()
                self.memory_bar.setValue(int(memory_mb))
                self.memory_text.setText(f"{memory_mb:.1f} MB")
                
                # Change color based on threshold
                palette = self.design_system.get_current_palette()
                if memory_mb > 800:
                    color = palette.error
                elif memory_mb > 500:
                    color = palette.warning
                else:
                    color = palette.success
                    
                self.memory_bar.setStyleSheet(f"""
                    QProgressBar::chunk {{
                        background: {color};
                        border-radius: 7px;
                    }}
                """)
        except Exception as e:
            self.logger.debug(f"Memory update error: {e}")
            
    def _update_stats(self):
        """Update statistics"""
        try:
            if hasattr(self.facade, 'get_statistics'):
                stats = self.facade.get_statistics()
                
                # Operations
                total_ops = stats.get('total_operations', 0)
                self.indicators['operations'].set_value(str(total_ops))
                
                # Packets
                packets = stats.get('packets_created', 0)
                self.indicators['packets'].set_value(str(packets))
                
        except Exception as e:
            self.logger.debug(f"Stats update error: {e}")
            
    def _update_protocol_count(self, protocols):
        """Update protocol count"""
        count = len(protocols) if protocols else 0
        self.indicators['protocols'].set_value(str(count))
        
    def _update_tecmp_status(self, is_active, protocols=None):
        """Update TECMP status"""
        palette = self.design_system.get_current_palette()
        
        if is_active:
            self.indicators['tecmp'].set_value("ON")
            self.indicators['tecmp'].set_color(palette.success)
        else:
            self.indicators['tecmp'].set_value("OFF")
            self.indicators['tecmp'].set_color(palette.neutral_600)
            
    def _update_capture_status(self, is_active, status=None):
        """Update capture status"""
        palette = self.design_system.get_current_palette()
        
        if is_active:
            self.indicators['capture'].set_value("ACTIVE")
            self.indicators['capture'].set_color(palette.error)
        else:
            self.indicators['capture'].set_value("IDLE")
            self.indicators['capture'].set_color(palette.neutral_600)
            
    def _update_theme_indicator(self, theme_name):
        """Update theme indicator"""
        display_name = "Dark" if "dark" in theme_name.lower() else "Light"
        self.indicators['theme'].set_value(display_name)
        
    def _on_packet_built(self, packet):
        """Increment packet counter"""
        try:
            current = int(self.indicators['packets'].value.text())
            self.indicators['packets'].set_value(str(current + 1))
        except:
            pass
            
    def _on_memory_warning(self, usage_mb, message):
        """Handle memory warnings"""
        palette = self.design_system.get_current_palette()
        
        # Flash memory bar
        self.memory_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background: {palette.error};
                border-radius: 7px;
            }}
        """)
        
        # Temporary message
        self.showMessage(f"?? Memory Warning: {message}", 5000)
        
    def _on_operation_completed(self, success, message, result):
        """Update operation counter"""
        try:
            current = int(self.indicators['operations'].value.text())
            self.indicators['operations'].set_value(str(current + 1))
            
            # Temporary message
            icon = "?" if success else "?"
            self.showMessage(f"{icon} {message}", 3000)
        except:
            pass
            
    def set_connection_status(self, connected: bool, text: str = None):
        """Update connection status"""
        palette = self.design_system.get_current_palette()
        
        if connected:
            color = palette.success
            self.connection_led.setText("?")
            self.connection_text.setText(text or "Connected")
        else:
            color = palette.error
            self.connection_led.setText("?")
            self.connection_text.setText(text or "Disconnected")
            
        self.connection_led.setStyleSheet(f"color: {color}; font-size: 16px;")
        self.connection_text.setStyleSheet(f"color: {color}; font-weight: bold;")
        
    # === PUBLIC API ===
    
    def add_custom_indicator(self, name: str, label: str, initial_value: str = "-") -> StatusIndicator:
        """Add a custom indicator"""
        indicator = StatusIndicator(label, initial_value)
        self._style_indicator(indicator)
        
        # Insert before stretch
        layout = self.findChild(QWidget).layout()
        layout.insertWidget(layout.count() - 2, self._create_separator())
        layout.insertWidget(layout.count() - 2, indicator)
        
        self.indicators[name] = indicator
        return indicator
        
    def get_indicator(self, name: str) -> Optional[StatusIndicator]:
        """Get an indicator by name"""
        return self.indicators.get(name)
        
    def cleanup(self):
        """Cleanup timers"""
        self.time_timer.stop()
        self.memory_timer.stop()
        self.stats_timer.stop()


def create_tecmp_integrated_status_bar(facade, design_system, parent=None) -> TECMPStatusBar:
    """
    Create a TECMP integrated status bar
    
    Args:
        facade: TECMPFacade instance
        design_system: TECMPDesignSystem instance
        parent: Parent widget
        
    Returns:
        TECMPStatusBar: Configured and ready status bar
    """
    try:
        status_bar = TECMPStatusBar(facade, design_system, parent)
        
        # Additional connections if needed
        if parent and hasattr(parent, 'centralWidget'):
            # Connect clicks to actions
            status_bar.protocols_clicked.connect(
                lambda: parent.centralWidget().show_protocol_details()
                if hasattr(parent.centralWidget(), 'show_protocol_details') else None
            )
            
            status_bar.tecmp_clicked.connect(
                lambda: parent.centralWidget().toggle_tecmp_view()
                if hasattr(parent.centralWidget(), 'toggle_tecmp_view') else None
            )
        
        return status_bar
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to create status bar: {e}")
        # Simple fallback
        simple_bar = QStatusBar(parent)
        simple_bar.showMessage("Status Bar Error - Using fallback", 5000)
        return simple_bar


# === USAGE EXAMPLE ===

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    # Create test app
    app = QApplication(sys.argv)
    
    # Simulate facade and design system
    class MockFacade:
        def get_statistics(self):
            return {
                'total_operations': 42,
                'packets_created': 15
            }
    
    class MockDesignSystem:
        def get_current_palette(self):
            class Palette:
                surface = "#ffffff"
                neutral_100 = "#f5f5f5"
                neutral_200 = "#e0e0e0"
                neutral_300 = "#bdbdbd"
                neutral_600 = "#757575"
                primary = "#1976d2"
                success = "#4caf50"
                success_light = "#81c784"
                warning = "#ff9800"
                error = "#f44336"
            return Palette()
    
    # Create window
    window = QMainWindow()
    window.setWindowTitle("TECMP Status Bar Test")
    window.resize(1200, 600)
    
    # Create status bar
    status_bar = create_tecmp_integrated_status_bar(
        MockFacade(),
        MockDesignSystem(),
        window
    )
    
    window.setStatusBar(status_bar)
    
    # Simple central widget
    from PyQt5.QtWidgets import QLabel
    central = QLabel("TECMP Tool - Status Bar Demo")
    central.setAlignment(Qt.AlignCenter)
    central.setStyleSheet("""
        QLabel {
            font-size: 24px;
            padding: 50px;
            background: #f8f9fa;
        }
    """)
    window.setCentralWidget(central)
    
    # Add custom indicator
    custom = status_bar.add_custom_indicator("custom", "Custom", "Hello")
    
    # Simulate changes
    QTimer.singleShot(2000, lambda: status_bar.set_connection_status(False, "Offline"))
    QTimer.singleShot(4000, lambda: status_bar.set_connection_status(True, "Online"))
    QTimer.singleShot(6000, lambda: custom.set_value("World"))
    
    window.show()
    sys.exit(app.exec_())