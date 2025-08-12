#!/usr/bin/env python3
"""
TECMP Design System - Simple, clean, professional
No glassmorphism, no fancy effects - just solid, reliable design
"""

import logging
import math
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum, auto

from PyQt5.QtCore import QObject, pyqtSignal, Qt, QRect, QPoint
from PyQt5.QtGui import (QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QFont, 
                         QPainterPath, QPolygon)
from PyQt5.QtWidgets import QApplication, QStyle


class VisualStyle(Enum):
    """Available visual styles."""
    STANDARD = auto()      # Clean and simple
    MATERIAL = auto()      # Material Design inspired
    FLAT = auto()          # Completely flat design
    PROFESSIONAL = auto()  # Business/Enterprise look


@dataclass
class ColorPalette:
    """Professional color palette."""
    # Primary colors - Professional blue
    primary: str = "#1976d2"
    primary_light: str = "#42a5f5"
    primary_dark: str = "#0d47a1"
    
    # Secondary - Professional green  
    secondary: str = "#388e3c"
    secondary_light: str = "#66bb6a"
    secondary_dark: str = "#1b5e20"
    
    # Accent - Professional orange
    accent: str = "#f57c00"
    
    # Semantic colors
    success: str = "#2e7d32"
    warning: str = "#f9a825"
    error: str = "#c62828"
    info: str = "#0277bd"
    
    # Surface colors - Simple and clean
    surface: str = "#ffffff"
    background: str = "#fafafa"
    
    # Text colors
    on_primary: str = "#ffffff"
    on_surface: str = "#212121"
    text_primary: str = "#212121"
    text_secondary: str = "#757575"
    
    # Neutral grays
    neutral_100: str = "#f5f5f5"
    neutral_200: str = "#eeeeee"
    neutral_300: str = "#e0e0e0"
    neutral_400: str = "#bdbdbd"
    neutral_500: str = "#9e9e9e"
    neutral_600: str = "#757575"
    neutral_700: str = "#616161"
    neutral_800: str = "#424242"
    neutral_900: str = "#212121"


class TECMPDesignSystem(QObject):
    """
    Simple and professional design system.
    Clean, functional, no unnecessary effects.
    """
    
    # Signals
    theme_changed = pyqtSignal(str)
    colors_changed = pyqtSignal(dict)
    effects_changed = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        
        self.logger = logging.getLogger(f"{__name__}.TECMPDesignSystem")
        
        # Color palettes
        self.light_palette = ColorPalette()
        self.dark_palette = ColorPalette(
            primary="#64b5f6",
            primary_light="#90caf9",
            primary_dark="#42a5f5",
            secondary="#81c784",
            secondary_light="#a5d6a7",
            secondary_dark="#66bb6a",
            accent="#ffb74d",
            surface="#303030",
            background="#212121",
            on_primary="#000000",
            on_surface="#ffffff",
            text_primary="#ffffff",
            text_secondary="#b0b0b0",
            neutral_100="#424242",
            neutral_200="#616161",
            neutral_300="#757575",
            neutral_400="#9e9e9e",
            neutral_500="#bdbdbd",
            neutral_600="#e0e0e0",
            neutral_700="#eeeeee",
            neutral_800="#f5f5f5",
            neutral_900="#fafafa"
        )
        
        self._dark_mode = False
        self._current_style = VisualStyle.STANDARD
        
        # Simple spacing system
        self._spacing = {
            'xs': 4,
            'sm': 8,
            'md': 16,
            'lg': 24,
            'xl': 32
        }
        
        # Simple radius values
        self._radius = {
            'sm': 4,
            'md': 6,
            'lg': 8,
            'xl': 12
        }
        
        # Clean typography
        self._typography = {
            'font_family_primary': 'Segoe UI',
            'font_family_secondary': 'Arial',
            'font_family_mono': 'Consolas',
            'font_size_xs': 11,
            'font_size_sm': 12,
            'font_size_base': 14,
            'font_size_lg': 16,
            'font_size_xl': 20
        }
        
        # Minimal effects
        self._effects = {
            'shadow_opacity': 0.1,
            'shadow_blur': 4,
            'shadow_offset_x': 0,
            'shadow_offset_y': 2,
            'hover_brightness': 1.1,
            'pressed_brightness': 0.9,
            'disabled_opacity': 0.5,
            'border_width': 1,
            'glassmorphism_background_opacity': 0.1,
            'glassmorphism_border_opacity': 0.2
        }
        
        self._icon_cache = {}
        
        self.logger.info("TECMP Design System initialized (Simple & Professional)")
    
    # === CORE INTERFACE METHODS ===
    
    def get_current_palette(self) -> ColorPalette:
        """Get the current color palette."""
        return self.dark_palette if self._dark_mode else self.light_palette
    
    def get_spacing(self, size: str) -> int:
        """Get spacing value."""
        return self._spacing.get(size, self._spacing['md'])
    
    def get_radius(self, size: str) -> int:
        """Get border radius value."""
        return self._radius.get(size, self._radius['md'])
    
    def get_typography(self, property_name: str) -> Any:
        """Get typography property."""
        return self._typography.get(property_name)
    
    def get_effect(self, effect_name: str) -> float:
        """Get effect value."""
        return self._effects.get(effect_name, 0.0)
    
    def get_colors_for_theme(self) -> Dict[str, str]:
        """Get colors dictionary."""
        palette = self.get_current_palette()
        return {
            'primary': palette.primary,
            'primary_dark': palette.primary_dark,
            'secondary': palette.secondary,
            'accent': palette.accent,
            'success': palette.success,
            'warning': palette.warning,
            'error': palette.error,
            'info': palette.info,
            'surface': palette.surface,
            'background': palette.background,
            'on_primary': palette.on_primary,
            'on_surface': palette.on_surface,
            'neutral_200': palette.neutral_200,
            'neutral_300': palette.neutral_300,
            'neutral_500': palette.neutral_500,
            'neutral_600': palette.neutral_600
        }
    
    def set_dark_mode(self, enabled: bool):
        """Enable or disable dark mode."""
        if self._dark_mode != enabled:
            self._dark_mode = enabled
            self.theme_changed.emit("dark" if enabled else "light")
            self.colors_changed.emit(self.get_colors_for_theme())
            self._icon_cache.clear()
    
    # === ICON CREATION WITH IMPROVED DRAWINGS ===
    
    def get_icon(self, name: str) -> QIcon:
        """Get or create icon."""
        cache_key = f"{name}_{self._dark_mode}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        icon = self._create_simple_icon(name)
        self._icon_cache[cache_key] = icon
        return icon
    
    def _create_simple_icon(self, name: str) -> QIcon:
        """Create simple, clean icon with improved drawings."""
        size = 24
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter()
        
        # CRITICAL: Properly manage painter lifecycle
        if not painter.begin(pixmap):
            # If painter fails to begin, return empty icon
            return QIcon()
        
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            
            palette = self.get_current_palette()
            color = QColor(palette.primary)
            
            # Draw specific icons with better details
            if name in ['new', 'add', 'add_protocol', 'add_tecmp']:
                # Plus sign with circle background
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(2, 2, 20, 20)
                painter.setPen(QPen(QColor(palette.on_primary), 2))
                painter.drawLine(12, 7, 12, 17)
                painter.drawLine(7, 12, 17, 12)
                
            elif name in ['open', 'folder']:
                # Folder icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                # Folder back
                painter.drawRect(4, 8, 16, 11)
                # Folder tab
                path = QPainterPath()
                path.moveTo(4, 8)
                path.lineTo(8, 4)
                path.lineTo(12, 4)
                path.lineTo(14, 8)
                painter.drawPath(path)
                
            elif name == 'save':
                # Floppy disk icon
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                # Disk body
                painter.drawRoundedRect(4, 4, 16, 16, 2, 2)
                # Metal slider - FIXED: Use QColor for QBrush
                painter.setBrush(QBrush(QColor(palette.surface)))
                painter.drawRect(6, 4, 10, 6)
                painter.drawRect(14, 6, 3, 2)
                # Label area - FIXED: Use QColor for QBrush
                painter.setBrush(QBrush(QColor(palette.surface)))
                painter.drawRect(7, 12, 10, 6)
                
            elif name == 'trace':
                # Wave/trace icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                path = QPainterPath()
                path.moveTo(2, 12)
                path.cubicTo(6, 4, 10, 20, 14, 12)
                path.cubicTo(18, 4, 22, 12, 22, 12)
                painter.drawPath(path)
                
            elif name == 'export':
                # Export arrow icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                # Arrow up
                painter.drawLine(12, 16, 12, 4)
                painter.drawLine(12, 4, 8, 8)
                painter.drawLine(12, 4, 16, 8)
                # Box
                painter.drawLine(4, 16, 4, 20)
                painter.drawLine(20, 16, 20, 20)
                painter.drawLine(4, 20, 20, 20)
                
            elif name == 'exit':
                # Exit door icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                # Door frame
                painter.drawRect(8, 3, 12, 18)
                # Door
                painter.drawLine(10, 3, 10, 21)
                # Arrow pointing out
                painter.drawLine(2, 12, 12, 12)
                painter.drawLine(12, 12, 9, 9)
                painter.drawLine(12, 12, 9, 15)
                
            elif name == 'preferences':
                # Gear icon
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                # Center circle
                painter.drawEllipse(8, 8, 8, 8)
                # Teeth
                for angle in range(0, 360, 45):
                    painter.save()
                    painter.translate(12, 12)
                    painter.rotate(angle)
                    painter.drawRect(-2, -11, 4, 4)
                    painter.restore()
                # Center hole - FIXED: Use QColor for QBrush
                painter.setBrush(QBrush(QColor(palette.surface)))
                painter.drawEllipse(10, 10, 4, 4)
                
            elif name == 'zoom':
                # Magnifying glass icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                # Glass circle
                painter.drawEllipse(3, 3, 14, 14)
                # Handle
                painter.setPen(QPen(color, 3))
                painter.drawLine(15, 15, 20, 20)
                # Plus inside
                painter.setPen(QPen(color, 1.5))
                painter.drawLine(10, 7, 10, 13)
                painter.drawLine(7, 10, 13, 10)
                
            elif name == 'dark_mode':
                # Moon icon
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                path = QPainterPath()
                path.addEllipse(6, 3, 15, 15)
                path2 = QPainterPath()
                path2.addEllipse(11, 1, 13, 13)
                painter.drawPath(path.subtracted(path2))
                
            elif name == 'hex_view':
                # Hex/grid icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                # Draw hexagon
                hexPoints = []
                cx, cy = 12, 12
                for i in range(6):
                    angle = i * 60 * 3.14159 / 180
                    x = cx + 8 * math.cos(angle)
                    y = cy + 8 * math.sin(angle)
                    hexPoints.append(QPoint(int(x), int(y)))
                painter.drawPolygon(QPolygon(hexPoints))
                # Center dot
                painter.setBrush(QBrush(color))
                painter.drawEllipse(10, 10, 4, 4)
                
            elif name == 'recent':
                # Clock icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                painter.drawEllipse(3, 3, 18, 18)
                # Clock hands
                painter.setPen(QPen(color, 2))
                painter.drawLine(12, 12, 12, 7)
                painter.drawLine(12, 12, 16, 14)
                # Hour marks
                painter.setPen(QPen(color, 1))
                for hour in [0, 3, 6, 9]:
                    angle = hour * 30 * 3.14159 / 180
                    x1 = 12 + 7 * math.cos(angle - 3.14159/2)
                    y1 = 12 + 7 * math.sin(angle - 3.14159/2)
                    x2 = 12 + 9 * math.cos(angle - 3.14159/2)
                    y2 = 12 + 9 * math.sin(angle - 3.14159/2)
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
                
            elif name in ['template', 'templates']:
                # Document template icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                # Document outline with folded corner
                path = QPainterPath()
                path.moveTo(5, 3)
                path.lineTo(14, 3)
                path.lineTo(19, 8)
                path.lineTo(19, 21)
                path.lineTo(5, 21)
                path.closeSubpath()
                painter.drawPath(path)
                # Folded corner
                painter.drawLine(14, 3, 14, 8)
                painter.drawLine(14, 8, 19, 8)
                # Text lines
                painter.setPen(QPen(color, 1))
                painter.drawLine(7, 11, 17, 11)
                painter.drawLine(7, 14, 17, 14)
                painter.drawLine(7, 17, 14, 17)
                
            elif name == 'performance':
                # Chart/graph icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                # Axes
                painter.drawLine(3, 19, 21, 19)
                painter.drawLine(3, 19, 3, 3)
                # Bars
                painter.setBrush(QBrush(color))
                painter.drawRect(6, 15, 3, 4)
                painter.drawRect(11, 11, 3, 8)
                painter.drawRect(16, 7, 3, 12)
                
            elif name == 'statistics':
                # Pie chart icon
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color, 1))
                # Full circle
                painter.drawEllipse(3, 3, 18, 18)
                # Pie slices - FIXED: Use QColor for QPen
                painter.setPen(QPen(QColor(palette.surface), 2))
                painter.drawLine(12, 12, 21, 12)
                painter.drawLine(12, 12, 12, 3)
                painter.drawLine(12, 12, 5, 18)
                
            elif name == 'status':
                # Dashboard icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                # Semi-circle gauge
                painter.drawArc(3, 6, 18, 18, 0, 180*16)
                # Ticks
                for angle in [-45, 0, 45]:
                    rad = angle * 3.14159 / 180
                    x1 = 12 + 7 * math.cos(rad - 3.14159/2)
                    y1 = 15 + 7 * math.sin(rad - 3.14159/2)
                    x2 = 12 + 9 * math.cos(rad - 3.14159/2)
                    y2 = 15 + 9 * math.sin(rad - 3.14159/2)
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
                # Needle - FIXED: Use QColor for QPen
                painter.setPen(QPen(QColor(palette.error), 2))
                painter.drawLine(12, 15, 7, 10)
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(10, 13, 4, 4)
                
            elif name in ['remove', 'delete', 'clear_protocols', 'remove_tecmp']:
                # Minus/remove icon with circle
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(2, 2, 20, 20)
                painter.setPen(QPen(QColor(palette.on_primary), 2))
                painter.drawLine(7, 12, 17, 12)
                
            elif name == 'undo':
                # Undo arrow icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                path = QPainterPath()
                path.moveTo(8, 12)
                path.arcTo(8, 4, 12, 12, 90, 180)
                painter.drawPath(path)
                # Arrow head
                painter.drawLine(8, 12, 11, 9)
                painter.drawLine(8, 12, 11, 15)
                
            elif name == 'redo':
                # Redo arrow icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                path = QPainterPath()
                path.moveTo(16, 12)
                path.arcTo(4, 4, 12, 12, 90, -180)
                painter.drawPath(path)
                # Arrow head
                painter.drawLine(16, 12, 13, 9)
                painter.drawLine(16, 12, 13, 15)
                
            elif name in ['generate', 'build']:
                # Play/generate icon
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                points = [QPoint(8, 5), QPoint(18, 12), QPoint(8, 19)]
                painter.drawPolygon(QPolygon(points))
                
            elif name in ['validate', 'check']:
                # Checkmark icon
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 3))
                painter.drawLine(6, 13, 10, 17)
                painter.drawLine(10, 17, 18, 7)
                
            elif name in ['help', 'info']:
                # Info/help icon
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(2, 2, 20, 20)
                painter.setPen(QPen(QColor(palette.on_primary), 2))
                painter.setBrush(QBrush(QColor(palette.on_primary)))
                # Question mark
                painter.drawEllipse(11, 6, 2, 2)
                painter.setPen(QPen(QColor(palette.on_primary), 2))
                painter.drawLine(12, 10, 12, 16)
                
            else:
                # Default icon - filled circle
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(4, 4, 16, 16)
                # Add first letter
                if name:
                    painter.setPen(QColor(palette.on_primary))
                    painter.setFont(QFont(self.get_typography('font_family_primary'), 10, QFont.Bold))
                    painter.drawText(QRect(4, 4, 16, 16), Qt.AlignCenter, name[0].upper())
            
        finally:
            # CRITICAL: Always end the painter
            painter.end()
        
        # Create icon from pixmap only after painter is ended
        icon = QIcon(pixmap)
        return icon
    
    # === SIMPLE STYLE GENERATION ===
    
    def generate_button_style(self, button_type: str = "primary") -> str:
        """Generate clean button style."""
        palette = self.get_current_palette()
        radius = self.get_radius('sm')
        
        if button_type == "primary":
            return f"""
                QPushButton {{
                    background-color: {palette.primary};
                    color: {palette.on_primary};
                    border: none;
                    border-radius: {radius}px;
                    padding: 8px 16px;
                    font-weight: 500;
                    font-size: {self.get_typography('font_size_base')}px;
                }}
                QPushButton:hover {{
                    background-color: {palette.primary_light};
                }}
                QPushButton:pressed {{
                    background-color: {palette.primary_dark};
                }}
                QPushButton:disabled {{
                    background-color: {palette.neutral_300};
                    color: {palette.neutral_500};
                }}
            """
        elif button_type == "secondary":
            return f"""
                QPushButton {{
                    background-color: {palette.surface};
                    color: {palette.primary};
                    border: 1px solid {palette.primary};
                    border-radius: {radius}px;
                    padding: 8px 16px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {palette.primary};
                    color: {palette.on_primary};
                }}
            """
        elif button_type == "flat":
            return f"""
                QPushButton {{
                    background-color: transparent;
                    color: {palette.primary};
                    border: none;
                    padding: 8px 16px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {palette.neutral_100};
                }}
            """
    
    def generate_clean_app_style(self) -> str:
        """Generate clean application style."""
        palette = self.get_current_palette()
        
        return f"""
            /* Clean Professional Style */
            QMainWindow {{
                background-color: {palette.background};
            }}
            
            QWidget {{
                font-family: '{self.get_typography('font_family_primary')}';
                font-size: {self.get_typography('font_size_base')}px;
                color: {palette.text_primary};
            }}
            
            /* Simple toolbar */
            QToolBar {{
                background-color: {palette.surface};
                border-bottom: 1px solid {palette.neutral_300};
                padding: 4px;
                spacing: 4px;
            }}
            
            QToolBar QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: {self.get_radius('sm')}px;
                padding: 6px;
                margin: 2px;
            }}
            
            QToolBar QToolButton:hover {{
                background-color: {palette.neutral_100};
                border-color: {palette.neutral_300};
            }}
            
            QToolBar QToolButton:pressed {{
                background-color: {palette.neutral_200};
            }}
            
            /* Clean lists */
            QListWidget {{
                background-color: {palette.surface};
                border: 1px solid {palette.neutral_300};
                border-radius: {self.get_radius('sm')}px;
                outline: none;
            }}
            
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {palette.neutral_200};
            }}
            
            QListWidget::item:hover {{
                background-color: {palette.neutral_100};
            }}
            
            QListWidget::item:selected {{
                background-color: {palette.primary};
                color: {palette.on_primary};
            }}
            
            /* Simple menus */
            QMenu {{
                background-color: {palette.surface};
                border: 1px solid {palette.neutral_300};
                padding: 4px;
            }}
            
            QMenu::item {{
                padding: 6px 20px;
                border-radius: {self.get_radius('sm')}px;
            }}
            
            QMenu::item:selected {{
                background-color: {palette.primary};
                color: {palette.on_primary};
            }}
            
            /* Clean scrollbars */
            QScrollBar:vertical {{
                background: {palette.neutral_100};
                width: 12px;
                border: none;
            }}
            
            QScrollBar::handle:vertical {{
                background: {palette.neutral_400};
                min-height: 30px;
                border-radius: 6px;
                margin: 2px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background: {palette.neutral_500};
            }}
        """


# === TEST ===

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QGridLayout
    
    app = QApplication(sys.argv)
    
    # Create design system
    ds = TECMPDesignSystem()
    
    # Create window
    window = QMainWindow()
    window.setWindowTitle("TECMP Design System - Icon Test")
    window.setStyleSheet(ds.generate_clean_app_style())
    
    # Central widget
    central = QWidget()
    layout = QVBoxLayout(central)
    
    # Icon showcase
    icon_grid = QGridLayout()
    icon_names = [
        'open', 'save', 'trace', 'export', 'exit',
        'preferences', 'zoom', 'dark_mode', 'hex_view', 'recent',
        'template', 'performance', 'statistics', 'status',
        'add', 'remove', 'undo', 'redo', 'validate', 'help'
    ]
    
    row = 0
    col = 0
    for icon_name in icon_names:
        btn = QPushButton(icon_name.title())
        btn.setIcon(ds.get_icon(icon_name))
        btn.setToolTip(f"{icon_name} icon")
        icon_grid.addWidget(btn, row, col)
        col += 1
        if col > 4:
            col = 0
            row += 1
    
    layout.addLayout(icon_grid)
    
    # Toggle dark mode button
    dark_btn = QPushButton("Toggle Dark Mode")
    dark_btn.setStyleSheet(ds.generate_button_style("primary"))
    dark_btn.clicked.connect(lambda: ds.set_dark_mode(not ds._dark_mode))
    layout.addWidget(dark_btn)
    
    layout.addStretch()
    
    window.setCentralWidget(central)
    window.resize(600, 400)
    window.show()
    
    sys.exit(app.exec_())