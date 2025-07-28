#!/usr/bin/env python
# coding: utf-8
"""
Resource Manager for TECMP Network Packet Builder application.

This component handles application resources like icons, templates and other assets.
Fixed version with robust error handling and fallback mechanisms.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Try to import PyQt5 with fallback
try:
    from PyQt5.QtCore import QObject, QDir
    from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
    from PyQt5.QtCore import Qt
    PYQT5_AVAILABLE = True
except ImportError:
    # Fallback when PyQt5 is not available
    PYQT5_AVAILABLE = False
    QObject = object
    QIcon = None
    QPixmap = None


class ResourceManager(QObject if PYQT5_AVAILABLE else object):
    """
    Manages application resources such as icons, templates, and other assets.
    
    Centralizes resource access and ensures consistent resource loading across
    the application. Works with or without PyQt5.
    """
    
    def __init__(self):
        """Initialize the resource manager."""
        if PYQT5_AVAILABLE:
            super().__init__()
        
        self.logger = logging.getLogger("TECMP-Tool.ResourceManager")
        
        # Determine base paths based on project structure
        self.project_root = self._find_project_root()
        
        # GUI resources path
        self.gui_resources_path = os.path.join(
            self.project_root, "core", "interfaces", "gui", "resources"
        )
        
        # Icons path
        self.icons_path = os.path.join(self.gui_resources_path, "icons")
        
        # Templates path
        self.templates_path = os.path.join(
            self.project_root, "core", "interfaces", "gui", "templates"
        )
        
        # Icon cache for performance
        self.icon_cache = {}
        
        # Create directories if they don't exist
        self._ensure_directories()
        
        self.logger.info(f"ResourceManager initialized with project root: {self.project_root}")
        if not PYQT5_AVAILABLE:
            self.logger.warning("PyQt5 not available - icon functionality limited")
    
    def _find_project_root(self):
        """
        Find the project root directory.
        
        Returns:
            str: Path to the project root
        """
        # Start with the current file's directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Go up to find the project root (where we expect to find 'core' directory)
        max_depth = 10  # Prevent infinite loops
        for _ in range(max_depth):
            # Check if we found the project root
            if os.path.basename(current_dir) == "TECMP-Tool":
                return current_dir
            
            if os.path.isdir(os.path.join(current_dir, "core")):
                return current_dir
            
            # Check for common project indicators
            project_indicators = [
                "setup.py", 
                "pyproject.toml", 
                "requirements.txt",
                ".git",
                "main.py",
                "core"
            ]
            
            if any(os.path.exists(os.path.join(current_dir, indicator)) 
                   for indicator in project_indicators):
                return current_dir
            
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:  # Reached the filesystem root
                break
            current_dir = parent_dir
        
        # If we couldn't determine the root, use a relative path from current location
        fallback_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.logger.warning(f"Could not determine project root, using fallback: {fallback_root}")
        return fallback_root
    
    def _ensure_directories(self):
        """Ensure resource directories exist."""
        directories = [
            self.gui_resources_path,
            self.icons_path,
            self.templates_path
        ]
        
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
                self.logger.debug(f"Ensured directory exists: {directory}")
            except Exception as e:
                self.logger.warning(f"Could not create directory {directory}: {e}")
    
    def get_icon(self, name: str):
        """
        Get an icon by name from the resources.
        
        Args:
            name: Name of the icon (without file extension)
            
        Returns:
            QIcon: The icon object, or an empty icon if not found (when PyQt5 available)
            str: Path to icon file (when PyQt5 not available)
        """
        if not PYQT5_AVAILABLE:
            return self._get_icon_path(name)
        
        # Check cache first
        if name in self.icon_cache:
            return self.icon_cache[name]
        
        # Check for Qt resource path
        if name.startswith(":/"):
            icon = QIcon(name)
            if not icon.isNull():
                self.icon_cache[name] = icon
                return icon
        
        # Try common extensions
        for ext in [".png", ".svg", ".jpg", ".ico", ".gif"]:
            file_path = os.path.join(self.icons_path, name + ext)
            if os.path.exists(file_path):
                icon = QIcon(file_path)
                if not icon.isNull():
                    self.icon_cache[name] = icon
                    return icon
        
        # Try Qt theme as fallback
        try:
            icon = QIcon.fromTheme(name)
            if not icon.isNull():
                self.icon_cache[name] = icon
                return icon
        except Exception as e:
            self.logger.debug(f"Theme icon lookup failed for {name}: {e}")
        
        # Last resort: create a colored icon
        colored_icon = self._create_colored_icon(name)
        if colored_icon:
            self.icon_cache[name] = colored_icon
            return colored_icon
        
        # Return empty icon as final fallback
        empty_icon = QIcon()
        self.icon_cache[name] = empty_icon
        return empty_icon
    
    def _get_icon_path(self, name: str) -> Optional[str]:
        """Get icon file path when PyQt5 is not available."""
        for ext in [".png", ".svg", ".jpg", ".ico", ".gif"]:
            file_path = os.path.join(self.icons_path, name + ext)
            if os.path.exists(file_path):
                return file_path
        
        self.logger.warning(f"Icon not found: {name}")
        return None
    
    def _create_colored_icon(self, name: str):
        """
        Create a colored icon with the first letter when an icon isn't found.
        
        Args:
            name: Name to use for the icon
            
        Returns:
            QIcon: Generated icon (if PyQt5 available), None otherwise
        """
        if not PYQT5_AVAILABLE:
            return None
        
        try:
            # Define a color based on name hash
            name_hash = sum(ord(c) for c in name)
            colors = [
                "#4A90E2", "#5CB85C", "#F0AD4E", "#D9534F", "#5BC0DE",
                "#BA68C8", "#FF7043", "#FFA726", "#FFEE58", "#66BB6A",
                "#7E57C2", "#EC407A", "#26A69A", "#AB47BC", "#42A5F5"
            ]
            color = colors[name_hash % len(colors)]
            
            # Create a pixmap
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background
            
            # Create a QPainter to draw on the pixmap
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw a colored rounded rectangle
            painter.setBrush(QColor(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(4, 4, 24, 24, 4, 4)
            
            # Draw the first letter of the name
            if name:
                letter = name[0].upper()
                painter.setPen(QColor("white"))
                painter.setFont(QFont("Arial", 16, QFont.Bold))
                painter.drawText(pixmap.rect(), Qt.AlignCenter, letter)
            
            painter.end()
            
            return QIcon(pixmap)
            
        except Exception as e:
            self.logger.error(f"Failed to create colored icon for {name}: {e}")
            return None
    
    def get_template_path(self, template_name: str) -> str:
        """
        Get the full path to a template file.
        
        Args:
            template_name: Name of the template file
            
        Returns:
            str: Path to the template file
        """
        return os.path.join(self.templates_path, template_name)
    
    def get_template_content(self, template_name: str) -> str:
        """
        Get the content of a template file.
        
        Args:
            template_name: Name of the template file
            
        Returns:
            str: Content of the template file, or empty string if not found
        """
        template_path = self.get_template_path(template_name)
        
        if not os.path.exists(template_path):
            self.logger.warning(f"Template not found: {template_name}")
            return ""
        
        try:
            with open(template_path, 'r', encoding='utf-8') as file:
                content = file.read()
                self.logger.debug(f"Loaded template: {template_name} ({len(content)} chars)")
                return content
        except Exception as e:
            self.logger.error(f"Error reading template {template_name}: {str(e)}")
            return ""
    
    def save_template_content(self, template_name: str, content: str) -> bool:
        """
        Save content to a template file.
        
        Args:
            template_name: Name of the template file
            content: Content to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        template_path = self.get_template_path(template_name)
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(template_path), exist_ok=True)
            
            with open(template_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            self.logger.info(f"Saved template: {template_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving template {template_name}: {str(e)}")
            return False
    
    def list_templates(self) -> list:
        """
        List all available template files.
        
        Returns:
            list: List of template filenames
        """
        if not os.path.exists(self.templates_path):
            return []
        
        try:
            templates = []
            for filename in os.listdir(self.templates_path):
                if os.path.isfile(os.path.join(self.templates_path, filename)):
                    templates.append(filename)
            
            self.logger.debug(f"Found {len(templates)} templates")
            return sorted(templates)
            
        except Exception as e:
            self.logger.error(f"Error listing templates: {str(e)}")
            return []
    
    def list_icons(self) -> list:
        """
        List all available icon files.
        
        Returns:
            list: List of icon filenames (without extensions)
        """
        if not os.path.exists(self.icons_path):
            return []
        
        try:
            icons = []
            icon_extensions = ['.png', '.svg', '.jpg', '.ico', '.gif']
            
            for filename in os.listdir(self.icons_path):
                if os.path.isfile(os.path.join(self.icons_path, filename)):
                    name, ext = os.path.splitext(filename)
                    if ext.lower() in icon_extensions:
                        icons.append(name)
            
            self.logger.debug(f"Found {len(icons)} icons")
            return sorted(list(set(icons)))  # Remove duplicates and sort
            
        except Exception as e:
            self.logger.error(f"Error listing icons: {str(e)}")
            return []
    
    def get_resource_info(self) -> Dict[str, Any]:
        """
        Get information about available resources.
        
        Returns:
            dict: Resource information
        """
        info = {
            "project_root": self.project_root,
            "gui_resources_path": self.gui_resources_path,
            "icons_path": self.icons_path,
            "templates_path": self.templates_path,
            "pyqt5_available": PYQT5_AVAILABLE,
            "icon_cache_size": len(self.icon_cache),
            "templates_count": len(self.list_templates()),
            "icons_count": len(self.list_icons()),
            "directories_exist": {
                "gui_resources": os.path.exists(self.gui_resources_path),
                "icons": os.path.exists(self.icons_path),
                "templates": os.path.exists(self.templates_path)
            }
        }
        
        return info
    
    def clear_cache(self) -> None:
        """Clear the icon cache."""
        self.icon_cache.clear()
        self.logger.info("Icon cache cleared")
    
    def preload_common_icons(self) -> None:
        """Preload commonly used icons into cache."""
        if not PYQT5_AVAILABLE:
            self.logger.info("PyQt5 not available - skipping icon preloading")
            return
        
        common_icons = [
            "play", "pause", "stop", "record", "save", "open", "new",
            "settings", "help", "info", "warning", "error", "network",
            "can", "lin", "flexray", "ethernet", "usb", "serial"
        ]
        
        loaded_count = 0
        for icon_name in common_icons:
            try:
                icon = self.get_icon(icon_name)
                if icon and not icon.isNull():
                    loaded_count += 1
            except Exception as e:
                self.logger.debug(f"Failed to preload icon {icon_name}: {e}")
        
        self.logger.info(f"Preloaded {loaded_count}/{len(common_icons)} common icons")
    
    def __str__(self) -> str:
        """String representation."""
        return f"ResourceManager(root={self.project_root}, pyqt5={PYQT5_AVAILABLE})"
    
    def __repr__(self) -> str:
        """Detailed representation."""
        info = self.get_resource_info()
        return (f"ResourceManager(project_root='{self.project_root}', "
                f"pyqt5_available={PYQT5_AVAILABLE}, "
                f"templates={info['templates_count']}, "
                f"icons={info['icons_count']}, "
                f"cache_size={info['icon_cache_size']})")


# === FACTORY FUNCTION ===

def create_resource_manager() -> ResourceManager:
    """
    Create and initialize a ResourceManager instance.
    
    Returns:
        ResourceManager: Configured resource manager
    """
    manager = ResourceManager()
    
    # Preload common icons if PyQt5 is available
    if PYQT5_AVAILABLE:
        try:
            manager.preload_common_icons()
        except Exception as e:
            manager.logger.warning(f"Failed to preload icons: {e}")
    
    return manager


# === EXPORT ===
__all__ = [
    'ResourceManager',
    'create_resource_manager',
    'PYQT5_AVAILABLE'
]


# === TEST FUNCTIONALITY ===
if __name__ == "__main__":
    # Test the resource manager
    import sys
    
    # Setup basic logging
    logging.basicConfig(level=logging.INFO)
    
    print("=== ResourceManager Test ===")
    
    # Create resource manager
    rm = create_resource_manager()
    print(f"Created: {rm}")
    
    # Get resource info
    info = rm.get_resource_info()
    print(f"\nResource Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Test template operations
    print(f"\nTemplates available: {rm.list_templates()}")
    
    # Test icon operations
    if PYQT5_AVAILABLE:
        print(f"Icons available: {rm.list_icons()}")
        
        # Test icon creation
        test_icon = rm.get_icon("test_icon")
        print(f"Test icon created: {test_icon is not None}")
    else:
        print("PyQt5 not available - icon functionality limited")
    
    print("\n=== Test Complete ===")