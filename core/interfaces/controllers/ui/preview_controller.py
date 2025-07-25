#!/usr/bin/env python
# coding: utf-8
"""
Controller for updating the packet preview and protocol structure view.
Provides high-quality visualization of packet contents and structure.
"""
import logging
import binascii
from typing import Optional, Dict, Any, List, Union, Tuple

from PyQt5.QtWidgets import QApplication, QTextBrowser, QWidget
from PyQt5.QtCore import Qt, QObject, pyqtSignal


class PreviewController(QObject):
    """
    Controller for packet preview and protocol structure visualization.
    
    Responsibilities:
    - Format packet data for preview
    - Generate hex and text representations
    - Create structured visualizations of protocol layers
    - Manage visualization preferences like hex view
    - Notify UI of changes via signals
    
    This controller follows the MVC pattern, focusing on data formatting
    without direct UI manipulation.
    """
    
    # Signals for communicating with UI
    preview_updated = pyqtSignal(str, str)  # hex/text content, structure html
    hex_view_toggled = pyqtSignal(bool)     # is_enabled
    update_required = pyqtSignal()          # request data update
    
    # Protocol color mapping - defined as class attribute to avoid recreation
    PROTOCOL_COLORS = {
        "Frame": "#f0f0f0",
        "Ethernet": "#cfe2ff",
        "VLAN": "#d1ffd1",
        "IPv4": "#f8d7da",
        "IPv6": "#ffecec",
        "TCP": "#fff3cd",
        "UDP": "#fff9e6",
        "TECMP": "#e7d9e3",
        "CAN": "#e0ebf5",
        "FlexRay": "#e8e8ff",
        "LIN": "#ffebe6",
        "ARP": "#e6ffe6",
        "HTTP": "#ede7f6",
        "HTTPS": "#d1c4e9",
        "DNS": "#b3e5fc",
        "DHCP": "#bbdefb",
        "ICMP": "#ffccbc",
        "ICMPv6": "#ffe0b2"
    }
    
    # Standard fields to show in TECMP header for consistency with tree view
    TECMP_FIELDS = [
        'device_id', 'counter', 'version', 'message_type', 
        'data_type', 'device_flags', 'interface_id', 
        'timestamp', 'data_flags'
    ]
    
    def __init__(self, facade=None):
        """
        Initialize the preview controller.
        
        Args:
            facade: Optional reference to the central facade
        """
        super().__init__()  # Initialize QObject base class
        self.logger = logging.getLogger("TECMP-Tool.PreviewController")
        
        # Configuration
        self._hex_view_enabled = False
        self._dark_mode_enabled = False
        
        # Data state
        self.last_packet = None  # Cache for the most recent packet
        
        # Optional facade reference for integrated operations
        self.facade = facade
        
        # UI widgets references (set later by injection)
        self._preview_widget = None
        self._structure_widget = None
        
        self.logger.debug("Preview controller initialized")
    
    # Config and setup methods
    
    def set_facade(self, facade):
        """
        Set the central facade reference.
        
        Args:
            facade: The central facade instance
        """
        self.facade = facade
        self.logger.debug("Facade reference set for preview controller")
    
    def set_preview_widget(self, widget: QTextBrowser):
        """
        Set the packet preview widget reference.
        
        Args:
            widget: QTextBrowser widget for displaying packet content
        """
        self._preview_widget = widget
        self.logger.debug("Preview widget reference set")
    
    def set_structure_widget(self, widget: QTextBrowser):
        """
        Set the structure preview widget reference.
        
        Args:
            widget: QTextBrowser widget for displaying structure content
        """
        self._structure_widget = widget
        self.logger.debug("Structure widget reference set")
    
    def set_dark_mode(self, enabled: bool):
        """
        Set dark mode status for formatting.
        
        Args:
            enabled: True for dark mode, False for light mode
        """
        self._dark_mode_enabled = enabled
        self.logger.debug(f"Dark mode set to: {enabled}")
        
        # Update display with new theme if packet exists
        if self.last_packet:
            self.update_preview(self.last_packet)
    
    def set_hex_view(self, enabled: bool):
        """
        Set hex view mode for packet preview.
        
        Args:
            enabled: True for hex view, False for text view
        """
        self._hex_view_enabled = enabled
        self.logger.debug(f"Hex view set to: {enabled}")
        
        # Emit signal to notify UI
        self.hex_view_toggled.emit(enabled)
        
        # Update preview with new view mode
        if self.last_packet:
            self.update_preview(self.last_packet)
    
    # Core update methods
    
    def update_preview(self, packet=None, tecmp_encapsulated=None):
        """
        Update packet preview and structure visualization.
        
        Args:
            packet: Optional specific packet to preview, otherwise uses last_packet
            tecmp_encapsulated: Flag to indicate TECMP encapsulation (affects display)
        """
        try:
            # Use provided packet or try to get one from various sources
            if packet is None:
                packet = self.last_packet
                
                # Try facade if available
                if packet is None and self.facade:
                    if hasattr(self.facade, 'get_current_packet'):
                        packet = self.facade.get_current_packet()
                
            if not packet:
                self.logger.debug("No packet available for preview")
                self._emit_empty_preview()
                return
                
            # Cache the packet for future use
            self.last_packet = packet
            
            # Determine if TECMP is encapsulated
            if tecmp_encapsulated is None and self.facade:
                if hasattr(self.facade, 'is_tecmp_encapsulated'):
                    tecmp_encapsulated = self.facade.is_tecmp_encapsulated()
                
            # Get packet content
            raw_bytes = self._get_packet_bytes(packet)
            if not raw_bytes:
                self.logger.warning("Could not serialize packet")
                self._emit_error_preview("Error: Could not serialize packet")
                return
            
            # Format preview content based on view mode
            if self._hex_view_enabled:
                # Format as hex dump
                preview_content = self._format_hex_dump(raw_bytes)
                
                # Apply styling
                bg_color = "#2d2d2d" if self._dark_mode_enabled else "white"
                text_color = "#e0e0e0" if self._dark_mode_enabled else "black"
                
                # Generate HTML
                preview_html = (
                    f"<pre style='font-family: monospace; font-size: 10pt; "
                    f"background-color: {bg_color}; color: {text_color};'>"
                    f"{preview_content}</pre>"
                )
            else:
                # Format as text representation
                preview_content = str(packet)
                preview_html = None  # Use plain text
            
            # Format structure preview
            structure_html = self._format_structure_html(packet, tecmp_encapsulated)
            
            # Update display
            self._update_display(preview_html, preview_content, structure_html)
            
            # Emit signal for any other listeners
            self.preview_updated.emit(
                preview_html if preview_html else preview_content, 
                structure_html
            )
            
        except Exception as e:
            self.logger.error(f"Error updating preview: {str(e)}", exc_info=True)
            self._emit_error_preview(f"Error updating preview: {str(e)}")
    
    def _update_display(self, preview_html, preview_text, structure_html):
        """
        Update the display widgets directly if available.
        
        Args:
            preview_html: HTML for preview (None for plain text)
            preview_text: Plain text for preview
            structure_html: HTML for structure
        """
        # Update preview widget if available
        if self._preview_widget:
            if preview_html:
                self._preview_widget.setHtml(preview_html)
            else:
                self._preview_widget.setPlainText(preview_text)
                
        # Update structure widget if available
        if self._structure_widget:
            self._structure_widget.setHtml(structure_html)
            
        # Process events to ensure immediate UI update
        QApplication.processEvents()
    
    def _emit_empty_preview(self):
        """Emit signals for empty preview."""
        empty_msg = "No packet available for preview"
        empty_html = "<div style='padding: 10px; font-style: italic;'>No packet available</div>"
        
        # Update widgets if available
        if self._preview_widget:
            self._preview_widget.setPlainText(empty_msg)
        
        if self._structure_widget:
            self._structure_widget.setHtml(empty_html)
            
        # Emit signal
        self.preview_updated.emit(empty_msg, empty_html)
    
    def _emit_error_preview(self, error_msg):
        """
        Emit signals for error preview.
        
        Args:
            error_msg: Error message to display
        """
        error_html = f"<div style='padding: 10px; color: red;'>{error_msg}</div>"
        
        # Update widgets if available
        if self._preview_widget:
            self._preview_widget.setPlainText(error_msg)
        
        if self._structure_widget:
            self._structure_widget.setHtml(error_html)
            
        # Emit signal
        self.preview_updated.emit(error_msg, error_html)
    
    # Formatting methods
    
    def _format_structure_html(self, packet, tecmp_encapsulated):
        """
        Format the packet structure as HTML.
        
        Args:
            packet: The packet object
            tecmp_encapsulated: Flag for TECMP encapsulation
            
        Returns:
            HTML representation of the structure
        """
        bg_color = "#2d2d2d" if self._dark_mode_enabled else "white"
        text_color = "#e0e0e0" if self._dark_mode_enabled else "black" 
        
        html_parts = [
            f"<div style='font-family: sans-serif; font-size: 11pt; "
            f"color: {text_color}; background-color: {bg_color}; padding: 10px;'>"
        ]
        
        # Handle TECMP encapsulation specially
        if tecmp_encapsulated:
            html_parts.append(self._format_tecmp_structure(packet))
        else:
            # Try different methods to get protocol structure
            if hasattr(packet, 'get_structure'):
                # Preferred method if available
                html_parts.append(self._format_protocol_structure(packet.get_structure()))
            elif hasattr(packet, 'layers'):
                # Try to process layers
                html_parts.append(self._format_layers(packet.layers))
            elif hasattr(packet, 'summary'):
                # Simple summary
                html_parts.append(f"<div><b>Summary:</b> {packet.summary()}</div>")
            else:
                # Generic object inspection
                html_parts.append(self._format_generic_object(packet))
        
        html_parts.append("</div>")
        
        return "".join(html_parts)
    
    def _get_packet_bytes(self, packet):
        """
        Get raw bytes from packet safely.
        
        Args:
            packet: The packet object
            
        Returns:
            bytes: Raw packet data or None on error
        """
        try:
            # First try facade if available
            if self.facade:
                if hasattr(self.facade, 'get_packet_bytes'):
                    return self.facade.get_packet_bytes(packet)
            
            # Try different possible methods
            if hasattr(packet, 'serialize'):
                return packet.serialize()
            elif hasattr(packet, 'raw'):
                return packet.raw()
            elif hasattr(packet, '__bytes__'):
                return bytes(packet)
            else:
                self.logger.warning("Packet has no serialization method")
                return None
        except Exception as e:
            self.logger.error(f"Error serializing packet: {str(e)}", exc_info=True)
            return None
    
    def _format_hex_dump(self, data, bytes_per_line=16):
        """
        Format binary data as a hex dump with ASCII representation.
        
        Args:
            data: Binary data to format
            bytes_per_line: Number of bytes per line in the output
            
        Returns:
            Formatted hex dump string
        """
        if not data:
            return "Empty packet"
            
        # For extremely large packets, limit the display
        max_bytes = 8192  # 8KB limit to prevent UI slowdown
        truncated = False
        if len(data) > max_bytes:
            truncated = True
            data = data[:max_bytes]
            
        lines = []
        for offset in range(0, len(data), bytes_per_line):
            # Get chunk of data for this line
            chunk = data[offset:offset + bytes_per_line]
            
            # Format as hex - with consistent spacing
            hex_values = " ".join(f"{b:02X}" for b in chunk)
            
            # Pad hex values to maintain alignment
            padding = bytes_per_line * 3 - len(hex_values)  # 3 chars per byte (2 hex + 1 space)
            if padding > 0:
                hex_values += " " * padding
                
            # Format as ASCII (printable chars only)
            ascii_values = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            
            # Build the line
            lines.append(f"{offset:04X}  {hex_values}  |{ascii_values}|")
            
        if truncated:
            lines.append(f"\n[Truncated - {len(data)} of {len(data)} bytes shown]")
            
        return "\n".join(lines)
    
    def _format_tecmp_structure(self, packet):
        """
        Format TECMP-encapsulated packet structure.
        
        Args:
            packet: TECMP packet
            
        Returns:
            HTML representation of the TECMP structure
        """
        html = ["<div style='margin-bottom: 10px;'>"]
        
        # TECMP header
        html.append("<div style='background-color: #e7d9e3; padding: 8px; border-radius: 4px; margin-bottom: 8px;'>")
        html.append("<b style='font-size: 12pt;'>TECMP Header</b>")
        
        # Extract TECMP-specific fields
        tecmp_fields = {}
        for attr in self.TECMP_FIELDS:
            if hasattr(packet, attr):
                value = getattr(packet, attr)
                # Format numeric values in hex
                if isinstance(value, int):
                    # Special case for timestamp
                    if attr == 'timestamp':
                        tecmp_fields[attr] = f"{value} ns"
                    # Format standard IDs in hex
                    elif attr in ['device_id', 'interface_id', 'device_flags', 'data_flags', 'data_type', 'message_type']:
                        tecmp_fields[attr] = f"0x{value:X}"
                    else:
                        tecmp_fields[attr] = str(value)
                else:
                    tecmp_fields[attr] = str(value)
        
        # Display TECMP fields in a table
        html.append("<table style='margin-left: 10px; font-size: 10pt; border-spacing: 5px;'>")
        for key, value in tecmp_fields.items():
            html.append(f"<tr><td style='font-weight: bold; padding-right: 10px;'>{key}</td><td>{value}</td></tr>")
        html.append("</table>")
        html.append("</div>")
        
        # Encapsulated payload
        if hasattr(packet, 'payload') and packet.payload:
            html.append("<div style='margin-top: 8px;'>")
            html.append("<b style='font-size: 12pt;'>Encapsulated Payload:</b>")
            
            # For payload that has its own structure
            if hasattr(packet.payload, 'get_structure'):
                html.append(self._format_protocol_structure(packet.payload.get_structure()))
            elif hasattr(packet.payload, 'layers'):
                html.append(self._format_layers(packet.payload.layers))
            elif hasattr(packet.payload, 'summary'):
                html.append(f"<div style='margin-left: 10px;'>{packet.payload.summary()}</div>")
            else:
                html.append(f"<div style='margin-left: 10px; font-style: italic;'>{len(packet.payload)} bytes</div>")
            
            html.append("</div>")
        
        html.append("</div>")
        return "".join(html)
    
    def _format_protocol_structure(self, structure):
        """
        Format a protocol structure dictionary.
        
        Args:
            structure: Protocol structure dictionary
            
        Returns:
            HTML representation of the structure
        """
        if not structure:
            return "<div>No structure information available</div>"
            
        html = []
        
        for proto_name, fields in structure.items():
            # Get protocol color
            proto_color = self._get_protocol_color(proto_name)
            
            html.append(f"<div style='background-color: {proto_color}; padding: 8px; margin-top: 8px; border-radius: 4px;'>")
            html.append(f"<b style='font-size: 11pt;'>{proto_name}</b>")
            
            # Format fields in a table
            if fields:
                html.append("<table style='margin-left: 10px; font-size: 10pt; border-spacing: 3px;'>")
                for key, value in sorted(fields.items()):  # Sort for consistency
                    formatted_value = self._format_field_value(key, value)
                    html.append(f"<tr><td style='font-weight: bold; padding-right: 10px;'>{key}</td><td>{formatted_value}</td></tr>")
                html.append("</table>")
            
            html.append("</div>")
            
        return "".join(html)
    
    def _format_layers(self, layers):
        """
        Format packet layers.
        
        Args:
            layers: List of packet layer objects
            
        Returns:
            HTML representation of the layers
        """
        if not layers:
            return "<div>No layer information available</div>"
            
        html = []
        
        for layer in layers:
            layer_name = getattr(layer, 'layer_name', layer.__class__.__name__)
            # Remove 'Packet' suffix if present
            if layer_name.endswith('Packet'):
                layer_name = layer_name[:-6]
                
            proto_color = self._get_protocol_color(layer_name)
            
            html.append(f"<div style='background-color: {proto_color}; padding: 8px; margin-top: 8px; border-radius: 4px;'>")
            html.append(f"<b style='font-size: 11pt;'>{layer_name}</b>")
            
            # Get field values
            fields = []
            # Try field_names attribute first
            if hasattr(layer, 'field_names'):
                for field in layer.field_names:
                    try:
                        value = getattr(layer, field)
                        formatted_value = self._format_field_value(field, value)
                        fields.append((field, formatted_value))
                    except (AttributeError, Exception):
                        pass
            else:
                # Generic object inspection as fallback
                for attr in dir(layer):
                    if not attr.startswith('_') and not callable(getattr(layer, attr)):
                        try:
                            value = getattr(layer, attr)
                            # Skip methods, complex objects, and None values
                            if not callable(value) and value is not None:
                                formatted_value = self._format_field_value(attr, value)
                                fields.append((attr, formatted_value))
                        except (AttributeError, Exception):
                            pass
            
            # Format fields in a table
            if fields:
                html.append("<table style='margin-left: 10px; font-size: 10pt; border-spacing: 3px;'>")
                for key, value in sorted(fields):  # Sort for consistency
                    html.append(f"<tr><td style='font-weight: bold; padding-right: 10px;'>{key}</td><td>{value}</td></tr>")
                html.append("</table>")
            
            html.append("</div>")
            
        return "".join(html)
    
    def _format_generic_object(self, obj):
        """
        Format a generic object by inspecting its attributes.
        
        Args:
            obj: Object to format
            
        Returns:
            HTML representation of the object
        """
        html = ["<div>"]
        
        # Get class name
        class_name = obj.__class__.__name__
        html.append(f"<div style='font-weight: bold; font-size: 11pt;'>{class_name}</div>")
        
        # Inspect attributes
        attrs = []
        for attr in dir(obj):
            if not attr.startswith('_') and not callable(getattr(obj, attr)):
                try:
                    value = getattr(obj, attr)
                    if not callable(value) and value is not None:
                        formatted_value = self._format_field_value(attr, value)
                        attrs.append((attr, formatted_value))
                except (AttributeError, Exception):
                    pass
        
        # Format in a table
        if attrs:
            html.append("<table style='margin-left: 10px; font-size: 10pt; border-spacing: 3px;'>")
            for key, value in sorted(attrs):  # Sort for consistency
                html.append(f"<tr><td style='font-weight: bold; padding-right: 10px;'>{key}</td><td>{value}</td></tr>")
            html.append("</table>")
        else:
            html.append("<div style='font-style: italic;'>No attributes available</div>")
        
        html.append("</div>")
        return "".join(html)
    
    def _format_field_value(self, field_name, value):
        """
        Format a field value for display.
        
        Args:
            field_name: Name of the field (for context)
            value: Value to format
            
        Returns:
            Formatted value string
        """
        # Handle None values
        if value is None:
            return "<i>None</i>"
            
        # Format binary data
        if isinstance(value, bytes):
            if len(value) > 16:
                # Show truncated hex for large binary data
                hex_str = binascii.hexlify(value[:16]).decode('ascii').upper()
                return f"<span title='{len(value)} bytes'>{hex_str}...</span>"
            else:
                hex_str = binascii.hexlify(value).decode('ascii').upper()
                return hex_str
                
        # Format MAC addresses
        elif field_name in ['src_mac', 'dst_mac', 'hwsrc', 'hwdst', 'source_mac', 'destination_mac'] and isinstance(value, bytes) and len(value) == 6:
            mac = ":".join(f"{b:02x}" for b in value)
            return mac
            
        # Format IP addresses
        elif field_name in ['src_ip', 'dst_ip', 'src', 'dst', 'source_ip', 'destination_ip'] and isinstance(value, (bytes, int)):
            if isinstance(value, bytes) and len(value) == 4:
                return ".".join(str(b) for b in value)
            if isinstance(value, bytes) and len(value) == 16:  # IPv6
                hex_parts = []
                for i in range(0, 16, 2):
                    hex_parts.append(f"{value[i]:02x}{value[i+1]:02x}")
                return ":".join(hex_parts)
            return str(value)
            
        # Format integers that look like they should be displayed in hex
        elif isinstance(value, int) and (field_name.endswith('_type') or 
                                       field_name.endswith('_id') or
                                       field_name in ['data_flags', 'device_flags', 'flags', 'options']):
            return f"0x{value:X}"
            
        # Format timestamp specially
        elif field_name == 'timestamp' and isinstance(value, int):
            return f"{value} ns"
            
        # Format enum values nicely if possible
        elif hasattr(value, 'name') and hasattr(value, 'value'):
            # Likely an enum
            return f"{value.name} ({value.value})"
            
        # Format lists and tuples
        elif isinstance(value, (list, tuple)) and len(value) > 0:
            # For small collections, show all items
            if len(value) <= 5:
                items = []
                for item in value:
                    if isinstance(item, bytes):
                        items.append(binascii.hexlify(item).decode('ascii').upper())
                    else:
                        items.append(str(item))
                return f"[{', '.join(items)}]"
            else:
                # For larger collections, show count
                return f"[{len(value)} items]"
                
        # Default formatting for other types
        else:
            return str(value)
    
    def _get_protocol_color(self, proto_name):
        """
        Get background color for a protocol based on its name.
        
        Args:
            proto_name: Protocol name or class name
            
        Returns:
            CSS color string
        """
        if not proto_name:
            return "#f5f5f5"  # Default light gray
            
        # Extract base protocol name
        base_name = proto_name.split()[0]  # Handle names like "Ethernet (External)"
        if '(' in base_name:
            base_name = base_name.split('(')[0].strip()
            
        # Remove common suffixes
        if base_name.endswith("Layer") or base_name.endswith("Packet"):
            base_name = base_name[:-5] if base_name.endswith("Layer") else base_name[:-6]
        
        # Find the matching color or default to light gray
        for proto, color in self.PROTOCOL_COLORS.items():
            if proto.lower() in base_name.lower():
                return color
                
        return "#f5f5f5"  # Default light gray
    
    # Public API methods
    
    def clear_preview(self):
        """Clear both preview panels."""
        empty_text = "No packet generated"
        empty_html = "<div>No packet available</div>"
        
        # Update widgets if available
        if self._preview_widget:
            self._preview_widget.setPlainText(empty_text)
            
        if self._structure_widget:
            self._structure_widget.setHtml(empty_html)
            
        # Reset state
        self.last_packet = None
        
        # Emit signal
        self.preview_updated.emit(empty_text, empty_html)
        
    def get_formatted_text(self, packet=None):
        """
        Get the formatted text representation of a packet.
        
        Args:
            packet: The packet object, or None to use the last packet
        
        Returns:
            Text representation of the packet
        """
        packet = packet or self.last_packet
        if not packet:
            return "No packet available"
            
        return str(packet)
        
    def get_formatted_hex(self, packet=None):
        """
        Get the formatted hex representation of a packet.
        
        Args:
            packet: The packet object, or None to use the last packet
        
        Returns:
            Hex representation of the packet
        """
        packet = packet or self.last_packet
        if not packet:
            return "No packet available"
            
        raw_bytes = self._get_packet_bytes(packet)
        if not raw_bytes:
            return "Error: Could not serialize packet"
            
        return self._format_hex_dump(raw_bytes)
    
    def is_hex_view_enabled(self):
        """
        Check if hex view is currently enabled.
        
        Returns:
            bool: True if hex view is enabled, False for text view
        """
        return self._hex_view_enabled
    
    def add_protocol_color(self, protocol_name, color):
        """
        Add or update a protocol color in the mapping.
        
        Args:
            protocol_name: Name of the protocol
            color: CSS color string
        """
        self.PROTOCOL_COLORS[protocol_name] = color