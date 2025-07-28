#!/usr/bin/env python3
"""
TECMP Integrated Menu System - Design-System First + Facade Plug & Play
Architecture simplifiée et directe pour intégration parfaite sans duplication.

? Design-System First : Utilise TECMPDesignSystem comme source unique
? Facade Plug & Play : Connexion directe sans mocks
? Zero Duplication : Réutilise les composants existants
[STAR] Clean Architecture : Séparation claire des responsabilités
"""

import logging
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass
from enum import Enum, auto

from PyQt5.QtWidgets import (
    QMenuBar, QMenu, QAction, QActionGroup, QApplication, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QKeySequence
from PyQt5.QtGui import QIcon, QFont


class MenuSection(Enum):
    """Sections principales du menu."""
    FILE = "File"
    EDIT = "Edit" 
    VIEW = "View"
    TECMP = "TECMP"
    ANALYSIS = "Analysis"


@dataclass
class MenuActionSpec:
    """Spécification d'une action de menu."""
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
    Menu TECMP intégré - Design-System First + Facade Plug & Play
    
    Architecture pure qui utilise directement :
    - TECMPDesignSystem pour le style et icônes
    - TECMPFacade pour les actions réelles
    - Pas de duplication de code
    """
    
    # Signaux pour communication
    action_executed = pyqtSignal(str, bool)
    menu_state_changed = pyqtSignal(str, dict)
    
    def __init__(self, facade, design_system, parent=None):
        """
        Initialise le menu intégré.
        
        Args:
            facade: Instance de TECMPFacade (vraie connexion)
            design_system: Instance de TECMPDesignSystem (style unifié)
            parent: Widget parent
        """
        super().__init__(parent)
        
        # Références directes - pas de mocks
        self.facade = facade
        self.design_system = design_system
        self.parent = parent
        
        # Logger
        self.logger = logging.getLogger(f"{__name__}.TECMPIntegratedMenu")
        
        # Stockage
        self.menu_bar = None
        self.menus: Dict[str, QMenu] = {}
        self.actions: Dict[str, QAction] = {}
        self.action_groups: Dict[str, QActionGroup] = {}
        
        # Zoom level tracking
        self._current_zoom = 100
        
        # Configuration des actions (source unique de vérité)
        self.action_specs = self._define_action_specifications()
        
        # Connexions à la façade (vraies connexions)
        self._connect_facade_signals()
        
        # Connexions au design system
        self._connect_design_system_signals()
        
        self.logger.info("Menu TECMP intégré initialisé - Design-System First")
    
    def _define_action_specifications(self) -> Dict[MenuSection, List[MenuActionSpec]]:
        """Définit toutes les spécifications d'actions (source unique)."""
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
        """Construit la barre de menu complète."""
        try:
            self.menu_bar = QMenuBar(self.parent)
            
            # Appliquer le style du design system
            self._apply_design_system_style()
            
            # Construire chaque section
            for section in MenuSection:
                menu = self._build_menu_section(section)
                self.menus[section.value] = menu
                self.menu_bar.addMenu(menu)
            
            # Mise à jour initiale des états
            self._update_menu_states()
            
            # Populate dynamic menus
            self._populate_templates_menu()
            
            self.logger.info("Menu bar construit avec succès")
            return self.menu_bar
            
        except Exception as e:
            self.logger.error(f"Erreur construction menu bar: {e}")
            raise
    
    def _build_menu_section(self, section: MenuSection) -> QMenu:
        """Construit une section de menu."""
        try:
            menu = QMenu(section.value, self.parent)
            
            # Obtenir les spécifications pour cette section
            specs = self.action_specs.get(section, [])
            
            for spec in specs:
                if spec.is_submenu:
                    # Créer un sous-menu
                    submenu = QMenu(spec.text, self.parent)
                    if spec.submenu_items:
                        for sub_spec in spec.submenu_items:
                            sub_action = self._create_action(sub_spec)
                            submenu.addAction(sub_action)
                            # Stocker l'action
                            action_key = f"{section.value.lower()}_{sub_spec.icon_name}_{sub_spec.text.replace('&', '').replace(' ', '_').lower()}"
                            self.actions[action_key] = sub_action
                    menu.addMenu(submenu)
                    # Store submenu reference
                    menu_key = f"{section.value.lower()}_{spec.icon_name}_menu"
                    self.menus[menu_key] = submenu
                else:
                    # Créer l'action normale
                    action = self._create_action(spec)
                    menu.addAction(action)
                    
                    # Stocker l'action
                    action_key = f"{section.value.lower()}_{spec.icon_name}"
                    self.actions[action_key] = action
                
                # Ajouter séparateur si nécessaire
                if spec.separator_after:
                    menu.addSeparator()
            
            return menu
            
        except Exception as e:
            self.logger.error(f"Erreur construction section {section.value}: {e}")
            raise
    
    def _create_action(self, spec: MenuActionSpec) -> QAction:
        """Crée une action à partir de sa spécification."""
        try:
            # Obtenir l'icône du design system
            icon = self.design_system.get_icon(spec.icon_name) if hasattr(self.design_system, 'get_icon') else QIcon()
            
            # Créer l'action
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
            
            # Connexion du signal
            action.triggered.connect(lambda checked=False: self._execute_action(spec.method_name, spec.checkable, checked))
            
            return action
            
        except Exception as e:
            self.logger.error(f"Erreur création action {spec.text}: {e}")
            raise
    
    def _execute_action(self, method_name: str, is_checkable: bool = False, checked: bool = False):
        """Exécute une action de menu."""
        try:
            # Actions spéciales (méthodes internes)
            if method_name.startswith('_'):
                method = getattr(self, method_name, None)
                if method:
                    if is_checkable:
                        result = method(checked)
                    else:
                        result = method()
                    success = result is not False
                else:
                    self.logger.warning(f"Méthode interne non trouvée: {method_name}")
                    success = False
            else:
                # Actions de la façade (connexion directe)
                method = getattr(self.facade, method_name, None)
                if method:
                    if is_checkable:
                        result = method(checked) if 'checked' in method.__code__.co_varnames else method()
                    else:
                        result = method()
                    success = result is not False
                else:
                    self.logger.warning(f"Méthode façade non trouvée: {method_name}")
                    success = False
            
            # Émettre signal de résultat
            self.action_executed.emit(method_name, success)
            
            # Mettre à jour les états si nécessaire
            if success:
                self._update_menu_states()
            
        except Exception as e:
            self.logger.error(f"Erreur exécution action {method_name}: {e}")
            self.action_executed.emit(method_name, False)
    
    def _apply_design_system_style(self):
        """Applique le style du design system au menu."""
        try:
            if not hasattr(self.design_system, 'get_current_palette'):
                return
            
            palette = self.design_system.get_current_palette()
            
            # Style CSS basé sur le design system
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
            self.logger.error(f"Erreur application style: {e}")
    
    def _connect_facade_signals(self):
        """Connecte les signaux de la façade pour mise à jour automatique."""
        try:
            # Connexions directes aux signaux réels de la façade
            if hasattr(self.facade, 'file_saved'):
                self.facade.file_saved.connect(self._on_file_saved)
            
            if hasattr(self.facade, 'file_loaded'):
                self.facade.file_loaded.connect(self._on_file_loaded)
            
            if hasattr(self.facade, 'operation_completed'):
                self.facade.operation_completed.connect(self._on_operation_completed)
            
            self.logger.info("Signaux façade connectés")
            
        except Exception as e:
            self.logger.error(f"Erreur connexion signaux façade: {e}")
    
    def _connect_design_system_signals(self):
        """Connecte les signaux du design system."""
        try:
            if hasattr(self.design_system, 'theme_changed'):
                self.design_system.theme_changed.connect(self._on_theme_changed)
            
            if hasattr(self.design_system, 'colors_changed'):
                self.design_system.colors_changed.connect(self._on_colors_changed)
            
            self.logger.info("Signaux design system connectés")
            
        except Exception as e:
            self.logger.error(f"Erreur connexion signaux design system: {e}")
    
    def _update_menu_states(self):
        """Met à jour l'état des actions selon l'état de la façade."""
        try:
            # État dark mode et hex view
            if 'view_dark_mode' in self.actions:
                is_dark = self.facade.get_setting('ui', 'dark_mode_enabled', False)
                self.actions['view_dark_mode'].setChecked(is_dark)
            
            if 'view_hex_view' in self.actions:
                is_hex = self.facade.get_setting('ui', 'hex_view_enabled', False)
                self.actions['view_hex_view'].setChecked(is_hex)
            
        except Exception as e:
            self.logger.error(f"Erreur mise à jour états menu: {e}")
    
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
            self.logger.error(f"Erreur population menu templates: {e}")
    
    # === HANDLERS DE SIGNAUX ===
    
    def _on_file_saved(self, path: str, size: int):
        """Handler pour fichier sauvegardé."""
        self.menu_state_changed.emit("file", {"saved": True, "path": path})
    
    def _on_file_loaded(self, path: str, file_type: str):
        """Handler pour fichier chargé."""
        self.menu_state_changed.emit("file", {"loaded": True, "path": path})
    
    def _on_operation_completed(self, success: bool, message: str, result):
        """Handler pour opération terminée."""
        self._update_menu_states()
    
    def _on_theme_changed(self, theme_name: str):
        """Handler pour changement de thème."""
        self._apply_design_system_style()
    
    def _on_colors_changed(self, colors_dict: dict):
        """Handler pour changement de couleurs."""
        self._apply_design_system_style()
    
    # === MÉTHODES INTERNES (ACTIONS SPÉCIALES) ===
    
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
            self.logger.error(f"Erreur ouverture fichier: {e}")
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
            self.logger.error(f"Erreur sauvegarde fichier: {e}")
            return False
    
    def _load_trace(self):
        """Load trace file."""
        try:
            return self.facade.load_trace_file() if hasattr(self.facade, 'load_trace_file') else False
        except Exception as e:
            self.logger.error(f"Erreur chargement trace: {e}")
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
            self.logger.error(f"Erreur export PCAP: {e}")
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
            self.logger.error(f"Erreur export JSON: {e}")
            return False
    
    def _exit_application(self):
        """Ferme l'application."""
        try:
            if self.parent:
                self.parent.close()
            return True
        except Exception as e:
            self.logger.error(f"Erreur fermeture application: {e}")
            return False
    
    # Edit menu actions
    def _show_preferences(self):
        """Show preferences dialog."""
        try:
            # Placeholder pour dialog préférences
            self.logger.info("Affichage préférences")
            # Could show a dialog with facade.get_setting()/set_setting()
            return True
        except Exception as e:
            self.logger.error(f"Erreur affichage préférences: {e}")
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
            self.logger.error(f"Erreur changement zoom: {e}")
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
            self.logger.error(f"Erreur basculement mode sombre: {e}")
            return False
    
    def _toggle_hex_view(self, checked: bool):
        """Toggle hex view."""
        try:
            return self.facade.set_setting('ui', 'hex_view_enabled', checked)
        except Exception as e:
            self.logger.error(f"Erreur basculement vue hex: {e}")
            return False
    
    def _show_recent_operations(self):
        """Show recent operations."""
        try:
            operations = self.facade.get_recent_operations() if hasattr(self.facade, 'get_recent_operations') else []
            # Could show in a dialog
            self.logger.info(f"Recent operations: {len(operations)} items")
            return True
        except Exception as e:
            self.logger.error(f"Erreur affichage opérations récentes: {e}")
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
            self.logger.error(f"Erreur chargement template: {e}")
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
            self.logger.error(f"Erreur chargement template {template_name}: {e}")
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
            self.logger.error(f"Erreur affichage métriques: {e}")
            return False
    
    def _show_statistics(self):
        """Show statistics."""
        try:
            stats = self.facade.get_statistics() if hasattr(self.facade, 'get_statistics') else {}
            # Could show in a dialog
            self.logger.info(f"Statistics retrieved: {len(stats)} items")
            return True
        except Exception as e:
            self.logger.error(f"Erreur affichage statistiques: {e}")
            return False
    
    def _show_system_status(self):
        """Show comprehensive system status."""
        try:
            status = self.facade.get_comprehensive_status() if hasattr(self.facade, 'get_comprehensive_status') else {}
            # Could show in a dialog
            self.logger.info(f"System status retrieved")
            return True
        except Exception as e:
            self.logger.error(f"Erreur affichage statut système: {e}")
            return False


# === FONCTION DE CRÉATION ===

def create_tecmp_integrated_menu(facade, design_system, parent=None) -> QMenuBar:
    """
    Crée un menu TECMP intégré.
    
    Args:
        facade: Instance de TECMPFacade
        design_system: Instance de TECMPDesignSystem  
        parent: Widget parent
        
    Returns:
        QMenuBar: Barre de menu configurée
    """
    try:
        menu_system = TECMPIntegratedMenu(facade, design_system, parent)
        return menu_system.build_menu_bar()
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Erreur création menu intégré: {e}")
        raise


# === EXEMPLE D'UTILISATION ===

if __name__ == "__main__":
    """Exemple d'intégration avec facade et design system réels."""
    
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QInputDialog
    
    # Simuler les composants réels (dans vraie app, imports depuis leurs modules)
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
            return QIcon()  # Icône vide pour la démo
            
        def set_dark_mode(self, enabled):
            print(f"? Dark mode: {enabled}")
    
    class TestMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("TECMP-Tool - Integrated Menu System")
            self.setGeometry(100, 100, 1000, 700)
            
            # Composants réels (simulation)
            self.facade = MockTECMPFacade()
            self.design_system = MockTECMPDesignSystem()
            
            # Menu intégré
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
            <p><i>Toutes les actions sont connectées directement à la façade !</i></p>
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
    
    # Fenêtre principale
    window = TestMainWindow()
    window.show()
    
    print("=== TECMP Integrated Menu System ===")
    print("? 5 Menus - 16 Actions")
    print("? Design-System First Architecture")
    print("? Facade Plug & Play Integration")
    print("? Zero Code Duplication")
    
    # Démarrage
    sys.exit(app.exec_())
    
# Alias pour compatibilité
MenuBuilder = TECMPIntegratedMenu