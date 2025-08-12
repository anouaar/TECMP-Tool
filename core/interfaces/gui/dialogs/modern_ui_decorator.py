#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modern UI Decorator - Composant de style moderne pour PyQt5
Extrait et reconstruit a partir des patterns identifies
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Dict, Optional, Union, Any, Tuple
from enum import Enum


class ThemeMode(Enum):
    """Modes de theme disponibles"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class ComponentType(Enum):
    """Types de composants supportes"""
    DIALOG = "dialog"
    BUTTON = "button"
    INPUT = "input"
    GROUP_BOX = "group_box"
    LIST = "list"
    CHECKBOX = "checkbox"
    LABEL = "label"
    CONTAINER = "container"


class AnimationType(Enum):
    """Types d'animations disponibles"""
    NONE = "none"
    FADE = "fade"
    SLIDE = "slide"
    BOUNCE = "bounce"
    HOVER = "hover"


class EffectIntensity(Enum):
    """Intensite des effets visuels"""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class ModernColors:
    """Palette de couleurs modernes pour l'interface"""
    # Couleurs principales
    PRIMARY = "#3498DB"
    PRIMARY_DARK = "#2980B9"
    PRIMARY_LIGHT = "#5DADE2"
    
    # Couleurs secondaires
    SECONDARY = "#2C3E50"
    SECONDARY_LIGHT = "#34495E"
    
    # Couleurs d'etat
    SUCCESS = "#28A745"
    SUCCESS_DARK = "#218838"
    SUCCESS_LIGHT = "#4CAF50"
    SUCCESS_BG = "#E8F5E9"
    
    WARNING = "#F39C12"
    WARNING_DARK = "#E67E22"
    WARNING_BG = "#FFF3CD"
    
    ERROR = "#DC3545"
    ERROR_DARK = "#C82333"
    ERROR_BG = "#FFEBEE"
    
    INFO = "#17A2B8"
    INFO_BG = "#E3F2FD"
    
    # Couleurs neutres
    WHITE = "#FFFFFF"
    LIGHT_GRAY = "#F8F9FA"
    GRAY_100 = "#F5F5F5"
    GRAY_200 = "#E9ECEF"
    GRAY_300 = "#DEE2E6"
    GRAY_400 = "#CED4DA"
    GRAY_500 = "#ADB5BD"
    GRAY_600 = "#6C757D"
    GRAY_700 = "#495057"
    GRAY_800 = "#343A40"
    DARK = "#212529"
    
    # Couleurs de protocole (Wireshark-like)
    PROTOCOL_COLORS = {
        "Ethernet": "#FFE4B5",   # Light peach
        "CAN": "#D3D3D3",        # Light gray
        "VLAN": "#9370DB",       # Medium purple
        "Link": "#87CEEB",       # Sky blue
        "IPv4": "#98FB98",       # Pale green
        "IPv6": "#FFB6C1",       # Light pink
        "ARP": "#FFDEAD",        # Navajo white
        "ICMP": "#E0FFFF",       # Light cyan
        "TCP": "#ADD8E6",        # Light blue
        "UDP": "#F0E68C",        # Khaki
        "SCTP": "#DDA0DD",       # Plum
        "HTTP": "#90EE90",       # Light green
        "DNS": "#FFE4E1",        # Misty rose
        "FTP": "#F5DEB3",        # Wheat
        "SMTP": "#FAFAD2"        # Light goldenrod
    }


class UIDecoratorConfig:
    """Configuration pour le decorateur UI"""
    
    # Configuration des polices
    DEFAULT_FONT_FAMILY = "'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif"
    DEFAULT_FONT_SIZE = 14
    HEADER_FONT_SIZE = 24
    TITLE_FONT_SIZE = 15
    SMALL_FONT_SIZE = 13
    
    # Configuration des dimensions
    BUTTON_MIN_WIDTH = 100
    BUTTON_PADDING = "10px 24px"
    INPUT_PADDING = "10px 14px"
    BORDER_RADIUS = 4
    GROUP_BOX_BORDER_RADIUS = 5
    
    # Configuration des animations
    HOVER_TRANSITION_DURATION = 200  # ms
    
    # Configuration des etats
    VALIDATION_STATES = ['valid', 'error', 'warning', 'neutral']
    BUTTON_SCHEMES = ['primary', 'success', 'danger', 'secondary']
    
    # Configuration des icones
    VALIDATION_ICONS = {
        'valid': u'\u2713',    # Check mark
        'error': u'\u2717',    # X mark
        'warning': u'\u26A0',  # Warning sign
        'neutral': u'\u25C9'   # Circle
    }
    
    # Configuration des styles par defaut
    DIALOG_MIN_WIDTH = 800
    DIALOG_MIN_HEIGHT = 600
    FIELD_CONTAINER_SPACING = 16
    ERROR_LABEL_HEIGHT = 20
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Retourne la configuration par defaut"""
        return {
            'font_family': cls.DEFAULT_FONT_FAMILY,
            'font_size': cls.DEFAULT_FONT_SIZE,
            'border_radius': cls.BORDER_RADIUS,
            'button_min_width': cls.BUTTON_MIN_WIDTH,
            'validation_states': cls.VALIDATION_STATES,
            'button_schemes': cls.BUTTON_SCHEMES
        }
    
    @classmethod
    def get_dialog_config(cls) -> Dict[str, Any]:
        """Retourne la configuration pour les dialogs"""
        return {
            'min_width': cls.DIALOG_MIN_WIDTH,
            'min_height': cls.DIALOG_MIN_HEIGHT,
            'modal': True,
            'style': 'dialog'
        }


class ModernStyle:
    """Classe principale pour appliquer les styles modernes"""
    
    @staticmethod
    def get_base_style() -> str:
        """Retourne le style de base pour l'application"""
        return """
        /* Global styles */
        * {
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
        }
        
        QWidget {
            background-color: transparent;
        }
        
        /* Main Window */
        QMainWindow {
            background-color: #F5F5F5;
        }
        
        /* Dialog styles */
        QDialog {
            background-color: #FFFFFF;
            border: 1px solid #E9ECEF;
        }
        """
    
    @staticmethod
    def get_button_style(color_scheme: str = "primary") -> str:
        """Retourne le style pour les boutons"""
        colors = {
            "primary": {
                "bg": ModernColors.PRIMARY,
                "hover": ModernColors.PRIMARY_DARK,
                "text": ModernColors.WHITE
            },
            "success": {
                "bg": ModernColors.SUCCESS,
                "hover": ModernColors.SUCCESS_DARK,
                "text": ModernColors.WHITE
            },
            "danger": {
                "bg": ModernColors.ERROR,
                "hover": ModernColors.ERROR_DARK,
                "text": ModernColors.WHITE
            },
            "secondary": {
                "bg": ModernColors.WHITE,
                "hover": ModernColors.LIGHT_GRAY,
                "text": ModernColors.GRAY_600,
                "border": ModernColors.GRAY_400
            }
        }
        
        scheme = colors.get(color_scheme, colors["primary"])
        
        return f"""
        QPushButton {{
            background-color: {scheme['bg']};
            color: {scheme['text']};
            border: {'1px solid ' + scheme.get('border', 'none')};
            padding: 10px 24px;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            min-width: 100px;
        }}
        
        QPushButton:hover {{
            background-color: {scheme['hover']};
        }}
        
        QPushButton:pressed {{
            background-color: {scheme['hover']};
            padding: 11px 23px 9px 25px;
        }}
        
        QPushButton:disabled {{
            background-color: {ModernColors.GRAY_200};
            color: {ModernColors.GRAY_600};
            border-color: {ModernColors.GRAY_200};
        }}
        """
    
    @staticmethod
    def get_input_style() -> str:
        """Retourne le style pour les champs de saisie"""
        return f"""
        /* Input fields */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
            padding: 10px 14px;
            border: 1px solid {ModernColors.GRAY_400};
            border-radius: 4px;
            font-size: 14px;
            background-color: {ModernColors.WHITE};
            color: {ModernColors.GRAY_700};
        }}
        
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, 
        QComboBox:focus, QTextEdit:focus {{
            border-color: {ModernColors.PRIMARY};
            outline: none;
        }}
        
        QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
        QComboBox:disabled, QTextEdit:disabled {{
            background-color: {ModernColors.GRAY_100};
            color: {ModernColors.GRAY_600};
        }}
        
        /* Error state */
        QLineEdit[hasError="true"], QSpinBox[hasError="true"],
        QDoubleSpinBox[hasError="true"] {{
            border-color: {ModernColors.ERROR};
            background-color: {ModernColors.WHITE};
        }}
        
        /* Warning state */
        QLineEdit[hasWarning="true"], QSpinBox[hasWarning="true"],
        QDoubleSpinBox[hasWarning="true"] {{
            border-color: {ModernColors.WARNING};
            background-color: {ModernColors.WHITE};
        }}
        
        /* Valid state */
        QLineEdit[isValid="true"], QSpinBox[isValid="true"],
        QDoubleSpinBox[isValid="true"] {{
            border-color: {ModernColors.SUCCESS};
            background-color: {ModernColors.WHITE};
        }}
        """
    
    @staticmethod
    def get_group_box_style() -> str:
        """Retourne le style pour les group boxes"""
        return f"""
        QGroupBox {{
            font-weight: 600;
            font-size: 15px;
            color: {ModernColors.SECONDARY};
            border: 2px solid {ModernColors.GRAY_300};
            border-radius: 5px;
            margin-top: 20px;
            padding-top: 20px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            background-color: {ModernColors.WHITE};
        }}
        """
    
    @staticmethod
    def get_dialog_style() -> str:
        """Retourne le style complet pour les dialogs"""
        return f"""
        /* Dialog container */
        #dialogContainer {{
            background-color: {ModernColors.WHITE};
            border: none;
        }}
        
        /* Header */
        #dialogHeader {{
            background-color: {ModernColors.LIGHT_GRAY};
            border-bottom: 1px solid {ModernColors.GRAY_200};
        }}
        
        #protocolTitle {{
            font-size: 24px;
            font-weight: 600;
            color: {ModernColors.SECONDARY};
            padding: 8px 16px;
            border-radius: 6px;
            border: 1px solid rgba(0,0,0,0.1);
        }}
        
        #closeButton {{
            background: transparent;
            border: none;
            font-size: 24px;
            color: {ModernColors.GRAY_600};
            border-radius: 16px;
        }}
        
        #closeButton:hover {{
            background-color: {ModernColors.GRAY_200};
            color: {ModernColors.GRAY_700};
        }}
        
        /* Content area */
        #contentArea {{
            background-color: {ModernColors.WHITE};
        }}
        
        /* Button bar */
        #buttonBar {{
            background-color: {ModernColors.LIGHT_GRAY};
            border-top: 1px solid {ModernColors.GRAY_200};
        }}
        
        #cancelBtn {{
            background-color: {ModernColors.WHITE};
            color: {ModernColors.GRAY_600};
            border: 1px solid {ModernColors.GRAY_400};
        }}
        
        #cancelBtn:hover {{
            background-color: {ModernColors.LIGHT_GRAY};
            border-color: {ModernColors.GRAY_500};
        }}
        
        #saveBtn {{
            background-color: {ModernColors.SUCCESS};
            color: {ModernColors.WHITE};
            border: 1px solid {ModernColors.SUCCESS};
        }}
        
        #saveBtn:hover {{
            background-color: {ModernColors.SUCCESS_DARK};
            border-color: {ModernColors.SUCCESS_DARK};
        }}
        
        #saveBtn:disabled {{
            background-color: {ModernColors.GRAY_200};
            color: {ModernColors.GRAY_600};
            border-color: {ModernColors.GRAY_200};
        }}
        """
    
    @staticmethod
    def get_checkbox_style() -> str:
        """Retourne le style pour les checkboxes"""
        return f"""
        QCheckBox {{
            font-size: 14px;
            color: {ModernColors.GRAY_700};
            spacing: 8px;
        }}
        
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 3px;
            border: 1px solid {ModernColors.GRAY_400};
            background-color: {ModernColors.WHITE};
        }}
        
        QCheckBox::indicator:checked {{
            background-color: {ModernColors.PRIMARY};
            border-color: {ModernColors.PRIMARY};
            image: url(:/icons/check-white.png);
        }}
        
        QCheckBox::indicator:unchecked:hover {{
            border-color: {ModernColors.PRIMARY};
        }}
        
        QCheckBox::indicator:disabled {{
            background-color: {ModernColors.GRAY_200};
            border-color: {ModernColors.GRAY_300};
        }}
        """
    
    @staticmethod
    def get_list_widget_style() -> str:
        """Retourne le style pour les list widgets"""
        return f"""
        QListWidget {{
            border: 1px solid {ModernColors.GRAY_400};
            border-radius: 4px;
            background-color: {ModernColors.WHITE};
            outline: none;
        }}
        
        QListWidget::item {{
            padding: 8px;
            border-bottom: 1px solid {ModernColors.GRAY_200};
        }}
        
        QListWidget::item:hover {{
            background-color: {ModernColors.GRAY_100};
        }}
        
        QListWidget::item:selected {{
            background-color: {ModernColors.PRIMARY};
            color: {ModernColors.WHITE};
        }}
        """
    
    @staticmethod
    def get_complete_style() -> str:
        """Retourne le style complet pour l'application"""
        return (
            ModernStyle.get_base_style() +
            ModernStyle.get_input_style() +
            ModernStyle.get_button_style() +
            ModernStyle.get_group_box_style() +
            ModernStyle.get_checkbox_style() +
            ModernStyle.get_list_widget_style()
        )


class ModernUIDecorator:
    """Decorateur principal pour appliquer le style moderne aux widgets"""
    
    @staticmethod
    def apply_modern_style(widget: QWidget, style_type: str = "complete"):
        """
        Applique un style moderne au widget
        
        Args:
            widget: Le widget PyQt5 a styliser
            style_type: Type de style ('complete', 'dialog', 'button', 'input', etc.)
        """
        style_map = {
            'complete': ModernStyle.get_complete_style(),
            'dialog': ModernStyle.get_dialog_style(),
            'button': ModernStyle.get_button_style(),
            'input': ModernStyle.get_input_style(),
            'group_box': ModernStyle.get_group_box_style(),
            'checkbox': ModernStyle.get_checkbox_style(),
            'list': ModernStyle.get_list_widget_style()
        }
        
        style = style_map.get(style_type, ModernStyle.get_complete_style())
        widget.setStyleSheet(style)
    
    @staticmethod
    def create_styled_button(text: str, color_scheme: str = "primary", 
                           parent: Optional[QWidget] = None) -> QPushButton:
        """Cree un bouton avec le style moderne applique"""
        button = QPushButton(text, parent)
        button.setStyleSheet(ModernStyle.get_button_style(color_scheme))
        button.setCursor(Qt.PointingHandCursor)
        return button
    
    @staticmethod
    def create_validation_label(parent: Optional[QWidget] = None) -> QLabel:
        """Cree un label pour afficher l'etat de validation"""
        label = QLabel(parent)
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumHeight(40)
        ModernUIDecorator.set_validation_state(label, "neutral", "En attente...")
        return label
    
    @staticmethod
    def set_validation_state(label: QLabel, state: str, text: str):
        """
        Met a jour l'etat visuel d'un label de validation
        
        Args:
            label: Le QLabel a mettre a jour
            state: L'etat ('valid', 'error', 'warning', 'neutral')
            text: Le texte a afficher
        """
        styles = {
            'valid': f"""
                padding: 10px;
                border: 2px solid {ModernColors.SUCCESS};
                border-radius: 5px;
                background-color: {ModernColors.SUCCESS_BG};
                color: {ModernColors.SUCCESS_DARK};
                font-weight: bold;
            """,
            'error': f"""
                padding: 10px;
                border: 2px solid {ModernColors.ERROR};
                border-radius: 5px;
                background-color: {ModernColors.ERROR_BG};
                color: {ModernColors.ERROR_DARK};
                font-weight: bold;
            """,
            'warning': f"""
                padding: 10px;
                border: 2px solid {ModernColors.WARNING};
                border-radius: 5px;
                background-color: {ModernColors.WARNING_BG};
                color: {ModernColors.WARNING_DARK};
                font-weight: bold;
            """,
            'neutral': f"""
                padding: 10px;
                border: 2px solid {ModernColors.GRAY_400};
                border-radius: 5px;
                background-color: {ModernColors.GRAY_100};
                color: {ModernColors.GRAY_700};
            """
        }
        
        icon_map = {
            'valid': u'\u2713',    # Check mark
            'error': u'\u2717',    # X mark
            'warning': u'\u26A0',  # Warning sign
            'neutral': u'\u25C9'   # Circle
        }
        
        label.setText(f"{icon_map.get(state, '')} {text}")
        label.setStyleSheet(styles.get(state, styles['neutral']))
    
    @staticmethod
    def set_field_validation_state(widget: Union[QLineEdit, QSpinBox, QDoubleSpinBox], 
                                 state: str):
        """
        Met a jour l'etat de validation d'un champ de saisie
        
        Args:
            widget: Le widget de saisie
            state: L'etat ('valid', 'error', 'warning', 'neutral')
        """
        # Reinitialiser les proprietes
        widget.setProperty("hasError", False)
        widget.setProperty("hasWarning", False)
        widget.setProperty("isValid", False)
        
        # Appliquer la nouvelle propriete
        if state == 'error':
            widget.setProperty("hasError", True)
        elif state == 'warning':
            widget.setProperty("hasWarning", True)
        elif state == 'valid':
            widget.setProperty("isValid", True)
        
        # Rafraichir le style
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
    
    @staticmethod
    def create_error_label(field_name: str, parent: Optional[QWidget] = None) -> QLabel:
        """Cree un label d'erreur pour un champ"""
        error_label = QLabel(parent)
        error_label.setObjectName(f"error_{field_name}")
        error_label.setStyleSheet(f"""
            color: {ModernColors.ERROR};
            font-size: 13px;
            padding-top: 4px;
        """)
        error_label.hide()
        return error_label
    
    @staticmethod
    def apply_protocol_color(widget: QWidget, protocol: str):
        """Applique la couleur du protocole au widget"""
        color = ModernColors.PROTOCOL_COLORS.get(protocol, ModernColors.GRAY_200)
        widget.setStyleSheet(f"""
            background-color: {color};
            padding: 8px 16px;
            border-radius: 6px;
            border: 1px solid rgba(0,0,0,0.1);
            font-weight: 600;
        """)
    
    @staticmethod
    def create_modern_group_box(title: str, parent: Optional[QWidget] = None) -> QGroupBox:
        """Cree un group box avec le style moderne"""
        group = QGroupBox(title, parent)
        group.setStyleSheet(ModernStyle.get_group_box_style())
        return group
    
    @staticmethod
    def apply_hover_effect(widget: QWidget, normal_style: str, hover_style: str):
        """Applique un effet de survol a un widget"""
        widget.installEventFilter(HoverEventFilter(widget, normal_style, hover_style))
    
    @staticmethod
    def create_custom_style(base_color: str, text_color: str = None) -> str:
        """Cree un style personnalise base sur une couleur"""
        if not text_color:
            # Determiner automatiquement la couleur du texte
            # Si la couleur est claire, utiliser du texte fonce
            text_color = ModernColors.DARK
            
        return f"""
        QPushButton {{
            background-color: {base_color};
            color: {text_color};
            border: 1px solid {base_color};
            padding: 10px 24px;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            min-width: 100px;
        }}
        
        QPushButton:hover {{
            background-color: {base_color};
            opacity: 0.8;
        }}
        """


class HoverEventFilter(QObject):
    """Filtre d'evenements pour gerer les effets de survol"""
    
    def __init__(self, widget: QWidget, normal_style: str, hover_style: str):
        super().__init__(widget)
        self.widget = widget
        self.normal_style = normal_style
        self.hover_style = hover_style
        
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj == self.widget:
            if event.type() == QEvent.Enter:
                self.widget.setStyleSheet(self.hover_style)
            elif event.type() == QEvent.Leave:
                self.widget.setStyleSheet(self.normal_style)
        return super().eventFilter(obj, event)


# Fonctions utilitaires pour une utilisation simplifiee
def apply_modern_theme(app: QApplication):
    """Applique le theme moderne a toute l'application"""
    app.setStyle('Fusion')
    app.setStyleSheet(ModernStyle.get_complete_style())


def style_dialog(dialog: QDialog):
    """Applique le style moderne a un dialog"""
    ModernUIDecorator.apply_modern_style(dialog, 'dialog')


def style_widget(widget: QWidget, style_type: str = "complete"):
    """Applique le style moderne a un widget"""
    ModernUIDecorator.apply_modern_style(widget, style_type)


def create_modern_button(text: str, color: str = "primary", parent=None) -> QPushButton:
    """Cree un bouton moderne"""
    return ModernUIDecorator.create_styled_button(text, color, parent)


def create_field_container(label_text: str, widget: QWidget, description: str, 
                          field_name: str, parent=None) -> QWidget:
    """Cree un conteneur de champ avec label, widget, description et erreur"""
    container = QWidget(parent)
    container.setObjectName("fieldContainer")
    layout = QVBoxLayout(container)
    layout.setSpacing(4)
    layout.setContentsMargins(0, 0, 0, 16)
    
    # Label
    label = QLabel(label_text)
    label.setStyleSheet(f"""
        font-weight: 500; 
        font-size: 14px; 
        color: {ModernColors.GRAY_700}; 
        padding-bottom: 2px;
    """)
    layout.addWidget(label)
    
    # Widget
    widget.setMinimumHeight(38)
    layout.addWidget(widget)
    
    # Description
    if description:
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            color: {ModernColors.GRAY_600}; 
            font-size: 12px; 
            padding-top: 2px;
        """)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
    
    # Error label
    error_label = ModernUIDecorator.create_error_label(field_name, container)
    layout.addWidget(error_label)
    
    return container


def apply_validation_style(widget: QWidget, is_valid: bool):
    """Applique le style de validation a un widget"""
    state = 'valid' if is_valid else 'error'
    if isinstance(widget, (QLineEdit, QSpinBox, QDoubleSpinBox)):
        ModernUIDecorator.set_field_validation_state(widget, state)


def get_protocol_color(protocol: str) -> str:
    """Retourne la couleur associee a un protocole"""
    return ModernColors.PROTOCOL_COLORS.get(protocol, ModernColors.GRAY_200)


def create_styled_dialog(title: str, parent=None) -> QDialog:
    """Cree un dialog avec le style moderne applique"""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
    style_dialog(dialog)
    return dialog


def create_styled_group_box(title: str, parent=None) -> QGroupBox:
    """Cree un group box style"""
    return ModernUIDecorator.create_modern_group_box(title, parent)


# Fonctions requises par __init__.py
def create_modern_decorator(config: Optional[Dict[str, Any]] = None) -> ModernUIDecorator:
    """Cree une instance du decorateur moderne avec configuration optionnelle"""
    return ModernUIDecorator()


def decorate_dialog(dialog: QDialog, theme: ThemeMode = ThemeMode.LIGHT) -> None:
    """Decore un dialog avec le style moderne"""
    style_dialog(dialog)


def decorate_button(button: QPushButton, color_scheme: str = "primary") -> None:
    """Decore un bouton avec le style moderne"""
    button.setStyleSheet(ModernStyle.get_button_style(color_scheme))
    button.setCursor(Qt.PointingHandCursor)


def decorate_input(input_widget: QWidget) -> None:
    """Decore un widget d'entree avec le style moderne"""
    input_widget.setStyleSheet(ModernStyle.get_input_style())


# Alias pour compatibilite
StyleHelper = ModernUIDecorator
ColorPalette = ModernColors
StyleConfig = UIDecoratorConfig


# Classes de style predefinies pour utilisation directe
class DialogStyles:
    """Styles predifinis pour les dialogs"""
    MODERN_DIALOG = ModernStyle.get_dialog_style()
    BASE_STYLE = ModernStyle.get_base_style()
    COMPLETE_STYLE = ModernStyle.get_complete_style()


class ValidationHelper:
    """Helper pour la gestion de la validation visuelle"""
    
    @staticmethod
    def show_field_error(widget: QWidget, error_label: QLabel, message: str):
        """Affiche une erreur pour un champ"""
        ModernUIDecorator.set_field_validation_state(widget, 'error')
        error_label.setText(message)
        error_label.show()
    
    @staticmethod
    def clear_field_error(widget: QWidget, error_label: QLabel):
        """Efface l'erreur d'un champ"""
        ModernUIDecorator.set_field_validation_state(widget, 'neutral')
        error_label.hide()
    
    @staticmethod
    def set_field_valid(widget: QWidget, error_label: QLabel):
        """Marque un champ comme valide"""
        ModernUIDecorator.set_field_validation_state(widget, 'valid')
        error_label.hide()


# Export des classes et fonctions principales
__all__ = [
    # Classes principales
    'ModernColors',
    'ModernStyle',
    'ModernUIDecorator',
    'UIDecoratorConfig',
    'HoverEventFilter',
    'DialogStyles',
    'ValidationHelper',
    # Enums
    'ThemeMode',
    'ComponentType',
    'AnimationType',
    'EffectIntensity',
    # Alias pour compatibilite
    'StyleHelper',
    'ColorPalette',
    'StyleConfig',
    # Fonctions principales
    'apply_modern_theme',
    'style_dialog',
    'style_widget',
    'create_modern_button',
    'create_field_container',
    'apply_validation_style',
    'get_protocol_color',
    'create_styled_dialog',
    'create_styled_group_box',
    # Fonctions requises par __init__.py
    'create_modern_decorator',
    'decorate_dialog',
    'decorate_button',
    'decorate_input'
]