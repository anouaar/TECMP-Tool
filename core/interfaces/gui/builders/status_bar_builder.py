#!/usr/bin/env python3
"""
TECMP Status Bar Builder - Production Grade with Real-Time Indicators
Utilise TECMPDesignSystem pour un style cohérent
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
    """Widget indicateur personnalisé pour la barre de statut"""
    
    clicked = pyqtSignal()
    
    def __init__(self, label: str, initial_value: str = "-", 
                 color_theme: str = "primary", parent=None):
        super().__init__(parent)
        self.label_text = label
        self.color_theme = color_theme
        self._init_ui(initial_value)
        
    def _init_ui(self, initial_value: str):
        """Initialise l'interface de l'indicateur"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        # Label
        self.label = QLabel(f"{self.label_text}:")
        self.label.setStyleSheet("color: #6c757d; font-weight: 500;")
        
        # Valeur
        self.value = QLabel(initial_value)
        self.value.setStyleSheet("color: #212529; font-weight: bold;")
        
        layout.addWidget(self.label)
        layout.addWidget(self.value)
        
    def set_value(self, value: str):
        """Met à jour la valeur affichée"""
        self.value.setText(value)
        
    def set_color(self, color: str):
        """Change la couleur de la valeur"""
        self.value.setStyleSheet(f"color: {color}; font-weight: bold;")
        
    def mousePressEvent(self, event):
        """Émet un signal quand cliqué"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class MemoryProgressBar(QProgressBar):
    """Barre de progression personnalisée pour la mémoire"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(True)
        self.setFormat("%v MB")
        self.setMaximumHeight(16)
        self.setMinimumWidth(120)
        

class TECMPStatusBar(QStatusBar):
    """
    Barre de statut TECMP complète avec indicateurs temps réel
    """
    
    # Signaux personnalisés
    memory_clicked = pyqtSignal()
    tecmp_clicked = pyqtSignal()
    protocols_clicked = pyqtSignal()
    
    def __init__(self, facade, design_system, parent=None):
        super().__init__(parent)
        self.facade = facade
        self.design_system = design_system
        self.logger = logging.getLogger(f"{__name__}.TECMPStatusBar")
        
        # Timers pour mises à jour
        self.time_timer = QTimer()
        self.memory_timer = QTimer()
        self.stats_timer = QTimer()
        
        # Widgets
        self.indicators = {}
        
        # Initialisation
        self._init_ui()
        self._connect_signals()
        self._start_timers()
        self._apply_styling()
        
        self.logger.info("TECMPStatusBar initialized with real-time indicators")
        
    def _init_ui(self):
        """Initialise tous les widgets de la barre de statut"""
        
        # Message temporaire (partie gauche)
        self.showMessage("TECMP Tool Ready", 3000)
        
        # Container principal pour les widgets permanents
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(12)
        
        # === INDICATEURS ===
        
        # 1. Temps
        self.indicators['time'] = StatusIndicator("Time", "00:00:00")
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['time'])
        
        # 2. Mémoire avec barre de progression
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
        
        # 3. Encapsulation TECMP
        self.indicators['tecmp'] = StatusIndicator("TECMP", "OFF")
        self.indicators['tecmp'].clicked.connect(self.tecmp_clicked.emit)
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['tecmp'])
        
        # 4. Nombre de protocoles
        self.indicators['protocols'] = StatusIndicator("Protocols", "0")
        self.indicators['protocols'].clicked.connect(self.protocols_clicked.emit)
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['protocols'])
        
        # 5. Paquets générés
        self.indicators['packets'] = StatusIndicator("Packets", "0")
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['packets'])
        
        # 6. État de capture
        self.indicators['capture'] = StatusIndicator("Capture", "IDLE")
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['capture'])
        
        # 7. Opérations
        self.indicators['operations'] = StatusIndicator("Ops", "0")
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['operations'])
        
        # 8. Mode/Thème
        self.indicators['theme'] = StatusIndicator("Theme", "Light")
        container_layout.addWidget(self._create_separator())
        container_layout.addWidget(self.indicators['theme'])
        
        # Ajouter stretch pour pousser à droite
        container_layout.addStretch()
        
        # 9. État de connexion avec LED
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
        
        # Ajouter le container à la barre de statut
        self.addPermanentWidget(container)
        
    def _create_separator(self) -> QFrame:
        """Crée un séparateur vertical"""
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
        """Connecte les signaux du facade"""
        try:
            # Protocoles
            if hasattr(self.facade, 'protocol_stack_changed'):
                self.facade.protocol_stack_changed.connect(self._update_protocol_count)
                
            # TECMP
            if hasattr(self.facade, 'tecmp_encapsulation_changed'):
                self.facade.tecmp_encapsulation_changed.connect(self._update_tecmp_status)
                
            # Paquets
            if hasattr(self.facade, 'packet_built'):
                self.facade.packet_built.connect(self._on_packet_built)
                
            # Mémoire
            if hasattr(self.facade, 'memory_warning'):
                self.facade.memory_warning.connect(self._on_memory_warning)
                
            # Capture
            if hasattr(self.facade, 'capture_status_changed'):
                self.facade.capture_status_changed.connect(self._update_capture_status)
                
            # Opérations
            if hasattr(self.facade, 'operation_completed'):
                self.facade.operation_completed.connect(self._on_operation_completed)
                
            # Thème
            if hasattr(self.design_system, 'theme_changed'):
                self.design_system.theme_changed.connect(self._update_theme_indicator)
                
            self.logger.info("Status bar signals connected")
            
        except Exception as e:
            self.logger.error(f"Error connecting signals: {e}")
            
    def _start_timers(self):
        """Démarre les timers de mise à jour"""
        # Timer pour l'heure (chaque seconde)
        self.time_timer.timeout.connect(self._update_time)
        self.time_timer.start(1000)
        
        # Timer pour la mémoire (toutes les 2 secondes)
        self.memory_timer.timeout.connect(self._update_memory)
        self.memory_timer.start(2000)
        
        # Timer pour les stats (toutes les 5 secondes)
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(5000)
        
        # Mise à jour initiale
        self._update_time()
        self._update_memory()
        self._update_stats()
        
    def _apply_styling(self):
        """Applique le style du design system"""
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
            
            # Style des indicateurs
            for indicator in self.indicators.values():
                self._style_indicator(indicator)
                
        except Exception as e:
            self.logger.error(f"Error applying styling: {e}")
            
    def _style_indicator(self, indicator: StatusIndicator):
        """Style un indicateur individuel"""
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
        
    # === MISES À JOUR EN TEMPS RÉEL ===
    
    def _update_time(self):
        """Met à jour l'heure"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.indicators['time'].set_value(current_time)
        
    def _update_memory(self):
        """Met à jour l'utilisation mémoire"""
        try:
            if hasattr(self.facade, 'memory_controller') and self.facade.memory_controller:
                memory_mb = self.facade.memory_controller.get_memory_usage()
                self.memory_bar.setValue(int(memory_mb))
                self.memory_text.setText(f"{memory_mb:.1f} MB")
                
                # Changer couleur selon seuil
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
        """Met à jour les statistiques"""
        try:
            if hasattr(self.facade, 'get_statistics'):
                stats = self.facade.get_statistics()
                
                # Opérations
                total_ops = stats.get('total_operations', 0)
                self.indicators['operations'].set_value(str(total_ops))
                
                # Paquets
                packets = stats.get('packets_created', 0)
                self.indicators['packets'].set_value(str(packets))
                
        except Exception as e:
            self.logger.debug(f"Stats update error: {e}")
            
    def _update_protocol_count(self, protocols):
        """Met à jour le nombre de protocoles"""
        count = len(protocols) if protocols else 0
        self.indicators['protocols'].set_value(str(count))
        
    def _update_tecmp_status(self, is_active, protocols=None):
        """Met à jour le statut TECMP"""
        palette = self.design_system.get_current_palette()
        
        if is_active:
            self.indicators['tecmp'].set_value("ON")
            self.indicators['tecmp'].set_color(palette.success)
        else:
            self.indicators['tecmp'].set_value("OFF")
            self.indicators['tecmp'].set_color(palette.neutral_600)
            
    def _update_capture_status(self, is_active, status=None):
        """Met à jour le statut de capture"""
        palette = self.design_system.get_current_palette()
        
        if is_active:
            self.indicators['capture'].set_value("ACTIVE")
            self.indicators['capture'].set_color(palette.error)
        else:
            self.indicators['capture'].set_value("IDLE")
            self.indicators['capture'].set_color(palette.neutral_600)
            
    def _update_theme_indicator(self, theme_name):
        """Met à jour l'indicateur de thème"""
        display_name = "Dark" if "dark" in theme_name.lower() else "Light"
        self.indicators['theme'].set_value(display_name)
        
    def _on_packet_built(self, packet):
        """Incrémente le compteur de paquets"""
        try:
            current = int(self.indicators['packets'].value.text())
            self.indicators['packets'].set_value(str(current + 1))
        except:
            pass
            
    def _on_memory_warning(self, usage_mb, message):
        """Gère les avertissements mémoire"""
        palette = self.design_system.get_current_palette()
        
        # Flash la barre de mémoire
        self.memory_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background: {palette.error};
                border-radius: 7px;
            }}
        """)
        
        # Message temporaire
        self.showMessage(f"?? Memory Warning: {message}", 5000)
        
    def _on_operation_completed(self, success, message, result):
        """Met à jour le compteur d'opérations"""
        try:
            current = int(self.indicators['operations'].value.text())
            self.indicators['operations'].set_value(str(current + 1))
            
            # Message temporaire
            icon = "?" if success else "?"
            self.showMessage(f"{icon} {message}", 3000)
        except:
            pass
            
    def set_connection_status(self, connected: bool, text: str = None):
        """Met à jour le statut de connexion"""
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
        """Ajoute un indicateur personnalisé"""
        indicator = StatusIndicator(label, initial_value)
        self._style_indicator(indicator)
        
        # Insérer avant le stretch
        layout = self.findChild(QWidget).layout()
        layout.insertWidget(layout.count() - 2, self._create_separator())
        layout.insertWidget(layout.count() - 2, indicator)
        
        self.indicators[name] = indicator
        return indicator
        
    def get_indicator(self, name: str) -> Optional[StatusIndicator]:
        """Récupère un indicateur par son nom"""
        return self.indicators.get(name)
        
    def cleanup(self):
        """Nettoyage des timers"""
        self.time_timer.stop()
        self.memory_timer.stop()
        self.stats_timer.stop()


def create_tecmp_integrated_status_bar(facade, design_system, parent=None) -> TECMPStatusBar:
    """
    Crée une barre de statut TECMP intégrée
    
    Args:
        facade: Instance du TECMPFacade
        design_system: Instance du TECMPDesignSystem
        parent: Widget parent
        
    Returns:
        TECMPStatusBar: Barre de statut configurée et prête
    """
    try:
        status_bar = TECMPStatusBar(facade, design_system, parent)
        
        # Connexions additionnelles si nécessaire
        if parent and hasattr(parent, 'centralWidget'):
            # Connecter les clics aux actions
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
        # Fallback simple
        simple_bar = QStatusBar(parent)
        simple_bar.showMessage("Status Bar Error - Using fallback", 5000)
        return simple_bar


# === EXEMPLE D'UTILISATION ===

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    # Créer une app de test
    app = QApplication(sys.argv)
    
    # Simuler facade et design system
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
    
    # Créer fenêtre
    window = QMainWindow()
    window.setWindowTitle("TECMP Status Bar Test")
    window.resize(1200, 600)
    
    # Créer la barre de statut
    status_bar = create_tecmp_integrated_status_bar(
        MockFacade(),
        MockDesignSystem(),
        window
    )
    
    window.setStatusBar(status_bar)
    
    # Widget central simple
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
    
    # Ajouter un indicateur custom
    custom = status_bar.add_custom_indicator("custom", "Custom", "Hello")
    
    # Simuler des changements
    QTimer.singleShot(2000, lambda: status_bar.set_connection_status(False, "Offline"))
    QTimer.singleShot(4000, lambda: status_bar.set_connection_status(True, "Online"))
    QTimer.singleShot(6000, lambda: custom.set_value("World"))
    
    window.show()
    sys.exit(app.exec_())