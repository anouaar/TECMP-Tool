#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modern UI Configuration System
"""
__version__ = "2.0.0"

# UI Decorator System
from .modern_ui_decorator import (
    ModernUIDecorator,
    UIDecoratorConfig,
    ThemeMode,
    ComponentType,
    AnimationType,
    EffectIntensity,
    create_modern_decorator,
    decorate_dialog,
    decorate_button,
    decorate_input
)

# TECMP Configuration
from .tecmp_config_dialog import (
    ProtocolDataWidget,
    TECMPIntegrationWidget,
    TECMPFullIntegrationWindow
)

# Protocol Configuration
from .protocol_config_dialog import (
    ProtocolConfigDialog
)

__all__ = [
    # Core
    'ModernUIDecorator',
    'UIDecoratorConfig', 
    'ThemeMode',
    'ComponentType',
    'AnimationType',
    'EffectIntensity',
    
    # Functions
    'create_modern_decorator',
    'decorate_dialog',
    'decorate_button', 
    'decorate_input',
    
    # TECMP
    'ProtocolDataWidget',
    'TECMPIntegrationWidget',
    'TECMPFullIntegrationWindow',
    
    # Protocols
    'ProtocolConfigDialog'
]