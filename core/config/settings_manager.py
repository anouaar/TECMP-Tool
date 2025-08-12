#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Settings Manager for TECMP-Tool - Centralized Configuration Management

This module provides a centralized settings management system for the TECMP-Tool
application, handling user preferences, application configuration, and persistence.

FIXED VERSION: Resolves "unhashable type: 'dict'" error in get() method
"""

import logging
import os
import json
import time  # Import moved to top
from typing import Any, Dict, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum, auto

from PyQt5.QtCore import QSettings, QStandardPaths, QObject, pyqtSignal


class SettingsScope(Enum):
    """Scope of settings storage."""
    USER = auto()      # User-specific settings
    SYSTEM = auto()    # System-wide settings
    SESSION = auto()   # Session-only settings
    PROJECT = auto()   # Project-specific settings


@dataclass
class SettingsGroup:
    """Settings group definition."""
    name: str
    description: str
    scope: SettingsScope = SettingsScope.USER
    defaults: Dict[str, Any] = field(default_factory=dict)
    validators: Dict[str, callable] = field(default_factory=dict)


class SettingsManager(QObject):
    """
    Centralized settings management for TECMP-Tool.
    
    Features:
    - Hierarchical settings organization
    - Type-safe configuration access
    - Automatic validation and defaults
    - Multi-scope settings support
    - Change notifications via signals
    - Persistence across sessions
    - Migration support for settings upgrades
    
    FIXED: Resolves "unhashable type: 'dict'" error in get() method
    """
    
    # Signals
    setting_changed = pyqtSignal(str, str, object)  # group, key, value
    settings_reset = pyqtSignal(str)  # group
    settings_imported = pyqtSignal(str)  # file_path
    settings_exported = pyqtSignal(str)  # file_path
    
    # Default settings groups
    DEFAULT_GROUPS = {
        'core': SettingsGroup(
            name='core',
            description='Core application settings',
            scope=SettingsScope.USER,
            defaults={
                'log_level': 'INFO',
                'log_errors': True,
                'show_dialogs': True,
                'max_errors': 1000,
                'auto_save': True,
                'auto_save_interval': 300,
                'language': 'en_US',
                'theme': 'auto',
                'animations_enabled': True,
                'performance_mode': False
            }
        ),
        'gui': SettingsGroup(
            name='gui',
            description='GUI preferences',
            scope=SettingsScope.USER,
            defaults={
                'window_geometry': None,
                'window_state': None,
                'splitter_states': {},
                'column_widths': {},
                'toolbar_visible': True,
                'statusbar_visible': True,
                'dark_mode': False,
                'font_family': 'default',
                'font_size': 11,
                'hex_view_enabled': False
            }
        ),
        'network': SettingsGroup(
            name='network',
            description='Network and capture settings',
            scope=SettingsScope.USER,
            defaults={
                'default_interface': None,
                'capture_buffer_size': 1000,
                'promiscuous_mode': True,
                'capture_timeout': 30,
                'packet_filter': '',
                'auto_scroll': True,
                'real_time_capture': True
            }
        ),
        'tecmp': SettingsGroup(
            name='tecmp',
            description='TECMP protocol settings',
            scope=SettingsScope.USER,
            defaults={
                'device_id': 0x0080,
                'counter_start': 0,
                'version': 3,
                'message_type': 0x03,
                'data_type': 0x80,
                'device_flags': 0x000F,
                'interface_id': 0x0070128a,
                'data_flags': 0x0000,
                'validate_crc': True,
                'auto_timestamp': True
            }
        ),
        'file_system': SettingsGroup(
            name='file_system',
            description='File system and paths',
            scope=SettingsScope.USER,
            defaults={
                'base_dir': None,
                'max_recent_files': 10,
                'autosave_enabled': True,
                'default_export_format': 'pcap',
                'working_directory': None,
                'temp_directory': None
            }
        ),
        # AJOUT DU GROUPE 'advanced' POUR CORRIGER L'ERREUR
        'advanced': SettingsGroup(
            name='advanced',
            description='Advanced settings for memory and performance',
            scope=SettingsScope.USER,
            defaults={
                'memory_warning_threshold': 500,
                'memory_critical_threshold': 1000,
                'enable_debug_mode': False,
                'enable_profiling': False,
                'cache_size_mb': 100,
                'thread_pool_size': 4
            }
        ),
        # AJOUT DU GROUPE 'protocol' (sans 's')
        'protocol': SettingsGroup(
            name='protocol',
            description='Protocol-specific settings (singular)',
            scope=SettingsScope.USER,
            defaults={
                'strict_validation': False,
                'auto_detect': True,
                'default_protocol': 'Ethernet',
                'protocol_timeout': 30,
                'max_retries': 3
            }
        ),
        'protocols': SettingsGroup(
            name='protocols',
            description='Protocol-specific settings',
            scope=SettingsScope.USER,
            defaults={
                'validation_enabled': True,
                'auto_configure': True,
                'show_advanced_options': False,
                'default_protocols': ['Ethernet', 'IPv4', 'TCP'],
                'protocol_colors': {},
                'custom_protocols': []
            }
        ),
        'performance': SettingsGroup(
            name='performance',
            description='Performance optimization settings',
            scope=SettingsScope.USER,
            defaults={
                'max_packets_display': 10000,
                'refresh_interval': 100,
                'memory_limit_mb': 512,
                'enable_caching': True,
                'lazy_loading': True,
                'background_processing': True
            }
        ),
        'security': SettingsGroup(
            name='security',
            description='Security and privacy settings',
            scope=SettingsScope.USER,
            defaults={
                'save_credentials': False,
                'encrypt_exports': False,
                'anonymize_data': False,
                'audit_logging': True,
                'secure_temp_files': True
            }
        ),
        # AJOUT DU GROUPE 'ui' pour la facade
        'ui': SettingsGroup(
            name='ui',
            description='UI settings for facade',
            scope=SettingsScope.USER,
            defaults={
                'hex_view_enabled': False,
                'preview_panel_visible': True,
                'details_panel_visible': True,
                'dark_mode_enabled': False
            }
        )
    }
    
    def __init__(self, organization: str = "TECMP-Tool", application: str = "TECMP-Tool"):
        """
        Initialize the settings manager.
        
        Args:
            organization: Organization name for settings storage
            application: Application name for settings storage
        """
        super().__init__()
        self.logger = logging.getLogger("TECMP-Tool.SettingsManager")
        
        # Configuration
        self.organization = organization
        self.application = application
        
        # Settings storage
        self._qt_settings = QSettings(organization, application)
        self._session_settings: Dict[str, Dict[str, Any]] = {}
        self._project_settings: Dict[str, Dict[str, Any]] = {}
        
        # Settings groups
        self._groups: Dict[str, SettingsGroup] = {}
        
        # State
        self._settings_file: Optional[str] = None
        self._is_dirty = False
        self._auto_save_enabled = True
        
        # Initialize default groups
        for group in self.DEFAULT_GROUPS.values():
            self.register_group(group)
        
        # Load existing settings
        self._load_settings()
        
        self.logger.info(f"SettingsManager initialized for {organization}/{application}")
    
    def register_group(self, group: SettingsGroup) -> None:
        """
        Register a settings group.
        
        Args:
            group: Settings group to register
        """
        self._groups[group.name] = group
        
        # Initialize defaults for the group
        for key, default_value in group.defaults.items():
            if not self.has_setting(group.name, key):
                self.set(group.name, key, default_value, save=False)
        
        self.logger.debug(f"Registered settings group: {group.name}")
    
    def get(self, group: str, key: str, default: Any = None) -> Any:
        """
        Get a setting value.
        
        Args:
            group: Settings group name
            key: Setting key
            default: Default value if setting doesn't exist
            
        Returns:
            Setting value or default
            
        Note:
            FIXED: Handles unhashable types (dict, list, set) as default values
            to prevent "unhashable type" errors when defaults are used in hash contexts.
        """
        # Check if group exists
        if group not in self._groups:
            self.logger.warning(f"Settings group '{group}' not registered")
            return default
        
        group_obj = self._groups[group]
        
        # Get from appropriate storage based on scope
        if group_obj.scope == SettingsScope.SESSION:
            session_value = self._session_settings.get(group, {}).get(key)
            if session_value is not None:
                return session_value
            # Fall back to group defaults, then provided default
            return group_obj.defaults.get(key, default)
            
        elif group_obj.scope == SettingsScope.PROJECT:
            project_value = self._project_settings.get(group, {}).get(key)
            if project_value is not None:
                return project_value
            # Fall back to group defaults, then provided default
            return group_obj.defaults.get(key, default)
            
        else:  # USER or SYSTEM scope
            qt_key = f"{group}/{key}"
            
            # CRITICAL FIX: Handle unhashable defaults safely
            # Check if setting exists first to avoid passing unhashable defaults to QSettings
            if self._qt_settings.contains(qt_key):
                # Setting exists, get it with a safe fallback (None)
                return self._qt_settings.value(qt_key, None)
            
            # Setting doesn't exist, check group defaults
            if key in group_obj.defaults:
                return group_obj.defaults[key]
            
            # No group default, return provided default
            return default
    
    def set(self, group: str, key: str, value: Any, save: bool = True) -> bool:
        """
        Set a setting value.
        
        Args:
            group: Settings group name
            key: Setting key
            value: Setting value
            save: Whether to save immediately
            
        Returns:
            True if setting was set successfully
        """
        try:
            # Check if group exists
            if group not in self._groups:
                self.logger.warning(f"Settings group '{group}' not registered")
                return False
            
            group_obj = self._groups[group]
            
            # Validate value if validator exists
            if key in group_obj.validators:
                validator = group_obj.validators[key]
                if not validator(value):
                    self.logger.error(f"Validation failed for {group}.{key} = {value}")
                    return False
            
            # Store in appropriate storage based on scope
            if group_obj.scope == SettingsScope.SESSION:
                if group not in self._session_settings:
                    self._session_settings[group] = {}
                self._session_settings[group][key] = value
            elif group_obj.scope == SettingsScope.PROJECT:
                if group not in self._project_settings:
                    self._project_settings[group] = {}
                self._project_settings[group][key] = value
            else:  # USER or SYSTEM scope
                qt_key = f"{group}/{key}"
                self._qt_settings.setValue(qt_key, value)
            
            # Mark as dirty and save if requested
            self._is_dirty = True
            if save and self._auto_save_enabled:
                self.save()
            
            # Emit change signal
            self.setting_changed.emit(group, key, value)
            
            self.logger.debug(f"Setting updated: {group}.{key} = {value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting {group}.{key}: {e}")
            return False
    
    def has_setting(self, group: str, key: str) -> bool:
        """
        Check if a setting exists.
        
        Args:
            group: Settings group name
            key: Setting key
            
        Returns:
            True if setting exists
        """
        if group not in self._groups:
            return False
        
        group_obj = self._groups[group]
        
        if group_obj.scope == SettingsScope.SESSION:
            return key in self._session_settings.get(group, {})
        elif group_obj.scope == SettingsScope.PROJECT:
            return key in self._project_settings.get(group, {})
        else:
            qt_key = f"{group}/{key}"
            return self._qt_settings.contains(qt_key)
    
    def remove_setting(self, group: str, key: str) -> bool:
        """
        Remove a setting.
        
        Args:
            group: Settings group name
            key: Setting key
            
        Returns:
            True if setting was removed
        """
        try:
            if group not in self._groups:
                return False
            
            group_obj = self._groups[group]
            
            if group_obj.scope == SettingsScope.SESSION:
                if group in self._session_settings and key in self._session_settings[group]:
                    del self._session_settings[group][key]
                    return True
            elif group_obj.scope == SettingsScope.PROJECT:
                if group in self._project_settings and key in self._project_settings[group]:
                    del self._project_settings[group][key]
                    return True
            else:
                qt_key = f"{group}/{key}"
                if self._qt_settings.contains(qt_key):
                    self._qt_settings.remove(qt_key)
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error removing setting {group}.{key}: {e}")
            return False
    
    def reset_group(self, group: str) -> bool:
        """
        Reset a settings group to defaults.
        
        Args:
            group: Settings group name
            
        Returns:
            True if group was reset
        """
        try:
            if group not in self._groups:
                return False
            
            group_obj = self._groups[group]
            
            # Clear existing settings
            if group_obj.scope == SettingsScope.SESSION:
                self._session_settings[group] = {}
            elif group_obj.scope == SettingsScope.PROJECT:
                self._project_settings[group] = {}
            else:
                # Remove all settings in this group from QSettings
                self._qt_settings.beginGroup(group)
                self._qt_settings.remove("")
                self._qt_settings.endGroup()
            
            # Restore defaults
            for key, default_value in group_obj.defaults.items():
                self.set(group, key, default_value, save=False)
            
            self.save()
            self.settings_reset.emit(group)
            
            self.logger.info(f"Settings group '{group}' reset to defaults")
            return True
            
        except Exception as e:
            self.logger.error(f"Error resetting group {group}: {e}")
            return False
    
    def get_group_settings(self, group: str) -> Dict[str, Any]:
        """
        Get all settings for a group.
        
        Args:
            group: Settings group name
            
        Returns:
            Dictionary of settings
        """
        if group not in self._groups:
            return {}
        
        group_obj = self._groups[group]
        settings = {}
        
        # Get all keys for this group
        if group_obj.scope == SettingsScope.SESSION:
            settings = self._session_settings.get(group, {}).copy()
        elif group_obj.scope == SettingsScope.PROJECT:
            settings = self._project_settings.get(group, {}).copy()
        else:
            # Get from QSettings
            self._qt_settings.beginGroup(group)
            for key in self._qt_settings.childKeys():
                settings[key] = self._qt_settings.value(key)
            self._qt_settings.endGroup()
        
        # Add defaults for missing keys
        for key, default_value in group_obj.defaults.items():
            if key not in settings:
                settings[key] = default_value
        
        return settings
    
    def set_group_settings(self, group: str, settings: Dict[str, Any]) -> bool:
        """
        Set multiple settings for a group.
        
        Args:
            group: Settings group name
            settings: Dictionary of settings to set
            
        Returns:
            True if all settings were set successfully
        """
        success = True
        for key, value in settings.items():
            if not self.set(group, key, value, save=False):
                success = False
        
        if success:
            self.save()
        
        return success
    
    def save(self) -> bool:
        """
        Save settings to persistent storage.
        
        Returns:
            True if save was successful
        """
        try:
            # QSettings auto-saves, but we force a sync
            self._qt_settings.sync()
            
            # Save project settings if we have a project file
            if self._settings_file and self._project_settings:
                self._save_project_settings()
            
            self._is_dirty = False
            self.logger.debug("Settings saved successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            return False
    
    def load_project_settings(self, file_path: str) -> bool:
        """
        Load project-specific settings from file.
        
        Args:
            file_path: Path to project settings file
            
        Returns:
            True if loaded successfully
        """
        try:
            self._settings_file = file_path
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                    self._project_settings = project_data.get('settings', {})
                
                self.logger.info(f"Project settings loaded from: {file_path}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error loading project settings: {e}")
            return False
    
    def save_project_settings(self, file_path: str = None) -> bool:
        """
        Save project-specific settings to file.
        
        Args:
            file_path: Optional path to save to (uses current project file if None)
            
        Returns:
            True if saved successfully
        """
        try:
            target_file = file_path or self._settings_file
            if not target_file:
                return False
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            
            project_data = {
                'version': '1.0',
                'application': self.application,
                'settings': self._project_settings
            }
            
            with open(target_file, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Project settings saved to: {target_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving project settings: {e}")
            return False
    
    def _save_project_settings(self) -> None:
        """Internal method to save project settings."""
        if self._settings_file:
            self.save_project_settings()
    
    def export_settings(self, file_path: str, groups: List[str] = None) -> bool:
        """
        Export settings to a file.
        
        Args:
            file_path: Path to export file
            groups: List of groups to export (all if None)
            
        Returns:
            True if exported successfully
        """
        try:
            export_data = {
                'version': '1.0',
                'application': self.application,
                'export_timestamp': str(time.time()),
                'settings': {}
            }
            
            groups_to_export = groups or list(self._groups.keys())
            
            for group in groups_to_export:
                if group in self._groups:
                    export_data['settings'][group] = self.get_group_settings(group)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.settings_exported.emit(file_path)
            self.logger.info(f"Settings exported to: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting settings: {e}")
            return False
    
    def import_settings(self, file_path: str, merge: bool = True) -> bool:
        """
        Import settings from a file.
        
        Args:
            file_path: Path to import file
            merge: Whether to merge with existing settings (True) or replace (False)
            
        Returns:
            True if imported successfully
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            settings_data = import_data.get('settings', {})
            
            for group, group_settings in settings_data.items():
                if group in self._groups:
                    if merge:
                        # Merge with existing settings
                        for key, value in group_settings.items():
                            self.set(group, key, value, save=False)
                    else:
                        # Replace entire group
                        self.reset_group(group)
                        self.set_group_settings(group, group_settings)
            
            self.save()
            self.settings_imported.emit(file_path)
            self.logger.info(f"Settings imported from: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing settings: {e}")
            return False
    
    def _load_settings(self) -> None:
        """Load existing settings from storage."""
        try:
            # QSettings are automatically loaded
            # Just ensure all groups have their defaults
            for group_name, group in self._groups.items():
                for key, default_value in group.defaults.items():
                    if not self.has_setting(group_name, key):
                        self.set(group_name, key, default_value, save=False)
            
            self.logger.debug("Settings loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")
    
    def get_settings_info(self) -> Dict[str, Any]:
        """
        Get information about the settings system.
        
        Returns:
            Dictionary with settings information
        """
        return {
            'organization': self.organization,
            'application': self.application,
            'settings_file': self._qt_settings.fileName(),
            'project_file': self._settings_file,
            'groups_count': len(self._groups),
            'groups': list(self._groups.keys()),
            'is_dirty': self._is_dirty,
            'auto_save_enabled': self._auto_save_enabled
        }
    
    def enable_auto_save(self, enabled: bool) -> None:
        """
        Enable or disable automatic saving.
        
        Args:
            enabled: Whether to enable auto-save
        """
        self._auto_save_enabled = enabled
        self.logger.debug(f"Auto-save {'enabled' if enabled else 'disabled'}")
    
    def is_dirty(self) -> bool:
        """
        Check if settings have unsaved changes.
        
        Returns:
            True if there are unsaved changes
        """
        return self._is_dirty


# Global settings instance (singleton pattern)
_settings_instance: Optional[SettingsManager] = None


def get_settings() -> SettingsManager:
    """
    Get the global settings instance (singleton).
    
    Returns:
        Global SettingsManager instance
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = SettingsManager()
    return _settings_instance


def initialize_settings(organization: str = "TECMP-Tool", application: str = "TECMP-Tool") -> SettingsManager:
    """
    Initialize the global settings instance.
    
    Args:
        organization: Organization name
        application: Application name
        
    Returns:
        Initialized SettingsManager instance
    """
    global _settings_instance
    _settings_instance = SettingsManager(organization, application)
    return _settings_instance