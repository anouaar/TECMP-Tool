"""TECMP Design System - Unified visual configuration"""

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QColor

class TECMPColorScheme:
    SKYBLUE_DREAM = "skyblue_dream"
    OCEAN_DEPTH = "ocean_depth"
    DARK_ELEGANCE = "dark_elegance"

class TECMPDesignSystem(QObject):
    """Unified design system for TECMP Tool"""
    
    theme_changed = pyqtSignal(str)
    colors_changed = pyqtSignal(dict)
    effects_changed = pyqtSignal(dict)
    
    class ColorPalette:
        def __init__(self):
            self.primary = "#4facfe"
            self.secondary = "#00f2fe"
            self.surface = "#ffffff"
            self.background = "#f8f9fa"
            self.on_surface = "#333333"
            self.on_primary = "#ffffff"
            self.primary_dark = "#357ABD"
            self.neutral_200 = "#e2e8f0"
            self.neutral_300 = "#cbd5e0"
            self.neutral_500 = "#718096"
            self.neutral_600 = "#4a5568"
            self.info = "#3182ce"
            self.accent = "#ed64a6"
            self.success = "#48bb78"
            self.warning = "#f6ad55"
            self.error = "#fc8181"
    
    def __init__(self):
        super().__init__()
        self._current_palette = self.ColorPalette()
        self._current_style = type('Style', (), {'name': 'STANDARD'})()
        self._current_scheme = TECMPColorScheme.SKYBLUE_DREAM
        
    def get_current_palette(self):
        return self._current_palette
    
    def get_spacing(self, size):
        return {'xs': 4, 'sm': 8, 'md': 16, 'lg': 24, 'xl': 32}.get(size, 8)
    
    def get_radius(self, size):
        return {'sm': 4, 'md': 8, 'lg': 12, 'xl': 16}.get(size, 4)
    
    def get_typography(self, prop):
        return {
            'font_family_primary': 'Arial',
            'font_size_base': 14,
            'font_size_sm': 12,
            'font_size_lg': 16
        }.get(prop, 'Arial')
    
    def get_effect(self, name):
        effects = {
            'glassmorphism_background_opacity': 0.1,
            'glassmorphism_border_opacity': 0.2,
            'shadow_opacity': 0.1,
            'blur_radius': 10
        }
        return effects.get(name, 0.1)
    
    def set_color_scheme(self, scheme):
        self._current_scheme = scheme
        self.colors_changed.emit(self.get_colors_for_theme())
    
    def get_colors_for_theme(self):
        return {
            'primary': self._current_palette.primary,
            'secondary': self._current_palette.secondary,
            'surface': self._current_palette.surface,
            'background': self._current_palette.background
        }
