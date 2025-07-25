#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Protocol Configuration Dialog with factory integration.
Clean version with all TCP and Ethernet fields.
"""

import logging
import re
from typing import Dict, Any, Optional, Type
from datetime import datetime

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# Import des factories existantes
from core.factories.tcp_factory import TCPFactory
from core.factories.udp_factory import UDPFactory
from core.factories.ethernet_factory import EthernetPacketFactory
from core.factories.ip_packet_factory import IPPacketFactory
from core.factories.arp_factory import ARPFactory
from core.factories.vlan_factory import VLANFactory

# Protocol colors from Wireshark
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

# Validation rules
VALIDATION_RULES = {
    "Ethernet": {
        "src_mac": {"pattern": r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', "message": "Invalid MAC address format"},
        "dst_mac": {"pattern": r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', "message": "Invalid MAC address format"},
        "ether_type": {"min": 0, "max": 0xFFFF, "message": "Must be between 0x0000 and 0xFFFF"},
        "preamble": {"pattern": r'^[0-9A-Fa-f]+$', "message": "Must be hexadecimal string"},
        "sfd": {"pattern": r'^[0-9A-Fa-f]{2}$', "message": "Must be 2 hex characters"},
        "fcs": {"pattern": r'^(0x)?[0-9A-Fa-f]{0,8}$|^0$', "message": "Must be hex value (max 8 hex digits) or 0"}
    },
    "IPv4": {
        "version": {"value": 4, "message": "Must be 4 for IPv4"},
        "protocol": {"min": 0, "max": 255, "message": "Must be between 0 and 255"},
        "src_ip": {"pattern": r'^(\d{1,3}\.){3}\d{1,3}$', "message": "Invalid IP address format"},
        "dst_ip": {"pattern": r'^(\d{1,3}\.){3}\d{1,3}$', "message": "Invalid IP address format"}
    },
    "IPv6": {
        "version": {"value": 6, "message": "Must be 6 for IPv6"},
        "protocol": {"min": 0, "max": 255, "message": "Must be between 0 and 255"},
        "src_ip": {"ipv6": True, "message": "Invalid IPv6 address format"},
        "dst_ip": {"ipv6": True, "message": "Invalid IPv6 address format"}
    },
    "TCP": {
        "src_port": {"min": 1, "max": 65535, "message": "Must be between 1 and 65535"},
        "dst_port": {"min": 1, "max": 65535, "message": "Must be between 1 and 65535"},
        "seq_number": {"min": 0, "max": 4294967295, "message": "Must be between 0 and 2^32-1"},
        "ack_number": {"min": 0, "max": 4294967295, "message": "Must be between 0 and 2^32-1"},
        "data_offset": {"min": 5, "max": 15, "message": "Must be between 5 and 15"},
        "reserved": {"min": 0, "max": 7, "message": "Must be between 0 and 7"},
        "window_size": {"min": 0, "max": 65535, "message": "Must be between 0 and 65535"},
        "checksum": {"min": 0, "max": 65535, "message": "Must be between 0 and 65535"},
        "urgent_pointer": {"min": 0, "max": 65535, "message": "Must be between 0 and 65535"},
        "mss": {"min": 0, "max": 65535, "message": "Must be between 0 and 65535"},
        "window_scale": {"min": -1, "max": 14, "message": "Must be between -1 (disabled) and 14"},
        "raw_options": {"pattern": r'^[0-9A-Fa-f]*$', "message": "Must be hexadecimal string"}
    },
    "UDP": {
        "src_port": {"min": 1, "max": 65535, "message": "Must be between 1 and 65535"},
        "dst_port": {"min": 1, "max": 65535, "message": "Must be between 1 and 65535"},
        "length": {"min": 8, "max": 65535, "message": "Must be between 8 and 65535"},
        "checksum": {"min": 0, "max": 65535, "message": "Must be between 0 and 65535"}
    },
    "VLAN": {
        "vlan_id": {"min": 1, "max": 4094, "message": "Must be between 1 and 4094"},
        "priority": {"min": 0, "max": 7, "message": "Must be between 0 and 7"},
        "cfi": {"min": 0, "max": 1, "message": "Must be 0 or 1"},
        "ether_type": {"min": 0, "max": 0xFFFF, "message": "Must be between 0x0000 and 0xFFFF"}
    },
    "ARP": {
        "hw_type": {"min": 0, "max": 65535, "message": "Must be between 0 and 65535"},
        "proto_type": {"min": 0, "max": 65535, "message": "Must be between 0 and 65535"},
        "hw_len": {"min": 0, "max": 255, "message": "Must be between 0 and 255"},
        "proto_len": {"min": 0, "max": 255, "message": "Must be between 0 and 255"},
        "operation": {"min": 1, "max": 2, "message": "Must be 1 (request) or 2 (reply)"},
        "sender_mac": {"pattern": r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', "message": "Invalid MAC address format"},
        "sender_ip": {"pattern": r'^(\d{1,3}\.){3}\d{1,3}$', "message": "Invalid IP address format"},
        "target_mac": {"pattern": r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', "message": "Invalid MAC address format"},
        "target_ip": {"pattern": r'^(\d{1,3}\.){3}\d{1,3}$', "message": "Invalid IP address format"}
    }
}


class ProtocolConfigDialog(QDialog):
    """Protocol Configuration Dialog with factory integration"""
    config_validated = pyqtSignal(dict)
    
    def __init__(self, protocol_name, stack_controller=None, parent=None):
        super().__init__(parent)
        self.protocol_name = protocol_name
        self.stack_controller = stack_controller
        self.config = {}
        self.field_widgets = {}
        self.error_labels = {}
        self.validation_errors = {}
        self.logger = logging.getLogger("ProtocolConfigDialog")
        
        # Get default config from stack controller if available
        if self.stack_controller and hasattr(self.stack_controller, 'get_default_config'):
            self.default_config = self.stack_controller.get_default_config(protocol_name)
        else:
            # Fallback to local defaults
            self.default_config = self._get_local_default_config()
        
        self.setWindowTitle(f"Configure {protocol_name}")
        self.setModal(True)
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self._setup_ui()
        
    def _get_local_default_config(self):
        """Local default configs matching ProtocolStackController"""
        DEFAULT_CONFIGS = {
            "Ethernet": {
                "preamble": "AAAAAAAAAAAAAAAA",
                "sfd": "AB",
                "src_mac": "02:00:00:00:00:01",
                "dst_mac": "02:00:00:00:00:02",
                "ether_type": 0x0800,
                "fcs": "0",
                "payload": ""
            },
            "IPv4": {
                "version": 4,
                "src_ip": "10.0.0.1",
                "dst_ip": "10.0.0.2",
                "protocol": 6
            },
            "IPv6": {
                "version": 6,
                "src_ip": "2001:db8::1",
                "dst_ip": "2001:db8::2",
                "protocol": 6
            },
            "TCP": {
                "src_port": 49152,
                "dst_port": 80,
                "seq_number": 0,
                "ack_number": 0,
                "data_offset": 5,
                "reserved": 0,
                "flags": 0x02,
                "window_size": 8192,
                "checksum": 0,
                "urgent_pointer": 0,
                "mss": 1460,
                "window_scale": -1,
                "sack_permitted": False,
                "timestamp_enabled": False,
                "raw_options": "",
                "payload": ""
            },
            "UDP": {
                "src_port": 49152,
                "dst_port": 53,
                "length": 8,
                "checksum": 0
            },
            "VLAN": {
                "vlan_id": 100,
                "priority": 0,
                "cfi": 0,
                "ether_type": 0x0800
            },
            "ARP": {
                "hw_type": 1,
                "proto_type": 0x0800,
                "hw_len": 6,
                "proto_len": 4,
                "operation": 1,
                "sender_mac": "02:00:00:00:00:01",
                "sender_ip": "10.0.0.1",
                "target_mac": "00:00:00:00:00:00",
                "target_ip": "10.0.0.2"
            }
        }
        return DEFAULT_CONFIGS.get(self.protocol_name, {})
        
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Main container
        container = QWidget()
        container.setObjectName("dialogContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(0)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = self._create_header()
        container_layout.addWidget(header)
        
        # Content area
        content_widget = QWidget()
        content_widget.setObjectName("contentArea")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 20, 30, 20)
        
        # Form scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        form_widget = QWidget()
        form_widget.setObjectName("formWidget")
        self.form_layout = QVBoxLayout(form_widget)
        self.form_layout.setSpacing(0)
        self.form_layout.setContentsMargins(0, 0, 20, 0)
        
        scroll.setWidget(form_widget)
        content_layout.addWidget(scroll, 1)
        
        container_layout.addWidget(content_widget, 1)
        
        # Bottom buttons
        buttons = self._create_buttons()
        container_layout.addWidget(buttons)
        
        main_layout.addWidget(container)
        
        # Apply style
        self._apply_modern_style()
        
        # Load fields
        self._load_fields()
        
        # Update button state
        self._update_save_button_state()
        
    def _create_header(self):
        header = QWidget()
        header.setObjectName("dialogHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(30, 20, 30, 20)
        
        # Protocol name with Wireshark color
        protocol_color = PROTOCOL_COLORS.get(self.protocol_name, "#E9ECEF")
        
        title = QLabel(self.protocol_name)
        title.setObjectName("protocolTitle")
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                font-weight: 600;
                color: #2C3E50;
                background-color: {protocol_color};
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid rgba(0,0,0,0.1);
            }}""")
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeButton")
        close_btn.clicked.connect(self.reject)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(32, 32)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        
        return header
        
    def _create_buttons(self):
        buttons = QWidget()
        buttons.setObjectName("buttonBar")
        layout = QHBoxLayout(buttons)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)
        
        layout.addStretch()
        
        # Only Cancel and Save buttons
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.clicked.connect(self._accept)
        self.save_btn.setDefault(True)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        
        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.save_btn)
        
        return buttons
        
    def _apply_modern_style(self):
        self.setStyleSheet("""
            /* Global styles */
            * {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            
            /* Dialog container */
            #dialogContainer {
                background-color: #FFFFFF;
                border: none;
            }
            
            /* Header */
            #dialogHeader {
                background-color: #F8F9FA;
                border-bottom: 1px solid #E9ECEF;
            }
            
            #closeButton {
                background: transparent;
                border: none;
                font-size: 24px;
                color: #6C757D;
                border-radius: 16px;
            }
            
            #closeButton:hover {
                background-color: #E9ECEF;
                color: #495057;
            }
            
            /* Content area */
            #contentArea {
                background-color: #FFFFFF;
            }
            
            /* Form fields */
            QLineEdit, QSpinBox, QComboBox {
                padding: 10px 14px;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                font-size: 14px;
                background-color: white;
                color: #495057;
            }
            
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #3498DB;
                outline: none;
            }
            
            QLineEdit[hasError="true"], QSpinBox[hasError="true"] {
                border-color: #DC3545;
                background-color: #FFFFFF;
            }
            
            QCheckBox {
                font-size: 14px;
                color: #495057;
                spacing: 8px;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 1px solid #CED4DA;
                background-color: white;
            }
            
            QCheckBox::indicator:checked {
                background-color: #3498DB;
                border-color: #3498DB;
            }
            
            /* Buttons */
            #buttonBar {
                background-color: #F8F9FA;
                border-top: 1px solid #E9ECEF;
            }
            
            QPushButton {
                padding: 10px 24px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: 500;
                border: 1px solid transparent;
                min-width: 100px;
            }
            
            #cancelBtn {
                background-color: #FFFFFF;
                color: #6C757D;
                border-color: #CED4DA;
            }
            
            #cancelBtn:hover {
                background-color: #F8F9FA;
                border-color: #ADB5BD;
            }
            
            #saveBtn {
                background-color: #28A745;
                color: white;
                border-color: #28A745;
            }
            
            #saveBtn:hover {
                background-color: #218838;
                border-color: #1E7E34;
            }
            
            #saveBtn:disabled {
                background-color: #E9ECEF;
                color: #6C757D;
                border-color: #E9ECEF;
            }
            
            /* Group boxes */
            QGroupBox {
                font-weight: 600;
                font-size: 15px;
                color: #2C3E50;
                border: none;
                margin-top: 20px;
                padding-top: 20px;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 0px;
                padding: 0 0 10px 0;
            }
            
            /* Text areas */
            QTextEdit {
                padding: 10px;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                font-size: 14px;
                background-color: white;
                color: #495057;
            }
            
            QTextEdit:focus {
                border-color: #3498DB;
                outline: none;
            }
        """)
        
    def _load_fields(self):
        """Load fields based on protocol with default values"""
        self.config = self.default_config.copy()
        
        # Create widgets for each field based on protocol
        if self.protocol_name == "TCP":
            self._create_tcp_fields()
        elif self.protocol_name == "UDP":
            self._create_udp_fields()
        elif self.protocol_name == "Ethernet":
            self._create_ethernet_fields()
        elif self.protocol_name == "VLAN":
            self._create_vlan_fields()
        elif self.protocol_name == "IPv4":
            self._create_ipv4_fields()
        elif self.protocol_name == "IPv6":
            self._create_ipv6_fields()
        elif self.protocol_name == "ARP":
            self._create_arp_fields()
        else:
            self._create_generic_fields()
            
    def _create_field_container(self, label_text, widget, description, field_name):
        """Create a field container with label, widget, description and error"""
        container = QWidget()
        container.setObjectName("fieldContainer")
        layout = QVBoxLayout(container)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 16)
        
        # Label
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: 500; font-size: 14px; color: #495057; padding-bottom: 2px;")
        layout.addWidget(label)
        
        # Widget
        widget.setMinimumHeight(38)
        layout.addWidget(widget)
        
        # Description
        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: #6C757D; font-size: 12px; padding-top: 2px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # Error label (hidden by default)
        error_label = QLabel()
        error_label.setObjectName(f"error_{field_name}")
        error_label.setStyleSheet("color: #DC3545; font-size: 13px; padding-top: 4px;")
        error_label.hide()
        layout.addWidget(error_label)
        
        # Store references
        self.field_widgets[field_name] = widget
        self.error_labels[field_name] = error_label
        
        # Connect validation
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda: self._validate_field(field_name))
            if widget.text():
                self._validate_field(field_name)
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.valueChanged.connect(lambda: self._validate_field(field_name))
        elif isinstance(widget, QCheckBox):
            widget.stateChanged.connect(lambda: self._validate_field(field_name))
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(lambda: self._validate_field(field_name))
        
        return container
        
    def _create_tcp_fields(self):
        """Create TCP fields matching TCPPacket implementation"""
        # Ports Section
        ports_group = QGroupBox("Port Configuration")
        ports_layout = QGridLayout()
        ports_layout.setSpacing(20)
        
        # Source Port
        src_port_widget = QSpinBox()
        src_port_widget.setRange(1, 65535)
        src_port_widget.setValue(self.config.get("src_port", 49152))
        src_port_container = self._create_field_container(
            "Source Port",
            src_port_widget,
            "TCP source port (1-65535)",
            "src_port"
        )
        ports_layout.addWidget(src_port_container, 0, 0)
        
        # Destination Port
        dst_port_widget = QSpinBox()
        dst_port_widget.setRange(1, 65535)
        dst_port_widget.setValue(self.config.get("dst_port", 80))
        dst_port_container = self._create_field_container(
            "Destination Port",
            dst_port_widget,
            "TCP destination port (1-65535)",
            "dst_port"
        )
        ports_layout.addWidget(dst_port_container, 0, 1)
        
        ports_group.setLayout(ports_layout)
        self.form_layout.addWidget(ports_group)
        
        # Sequence Numbers Section
        seq_group = QGroupBox("Sequence Numbers")
        seq_layout = QGridLayout()
        seq_layout.setSpacing(20)
        
        # Sequence Number
        seq_widget = QSpinBox()
        seq_widget.setRange(0, 2147483647)
        seq_widget.setValue(self.config.get("seq_number", 0))
        seq_widget.setDisplayIntegerBase(10)
        seq_container = self._create_field_container(
            "Sequence Number",
            seq_widget,
            "Initial sequence number",
            "seq_number"
        )
        seq_layout.addWidget(seq_container, 0, 0)
        
        # Acknowledgment Number
        ack_widget = QSpinBox()
        ack_widget.setRange(0, 2147483647)
        ack_widget.setValue(self.config.get("ack_number", 0))
        ack_widget.setDisplayIntegerBase(10)
        ack_container = self._create_field_container(
            "Acknowledgment Number",
            ack_widget,
            "Acknowledgment number",
            "ack_number"
        )
        seq_layout.addWidget(ack_container, 0, 1)
        
        seq_group.setLayout(seq_layout)
        self.form_layout.addWidget(seq_group)
        
        # Header Fields Section
        header_group = QGroupBox("Header Fields")
        header_layout = QGridLayout()
        header_layout.setSpacing(20)
        
        # Data Offset
        offset_widget = QSpinBox()
        offset_widget.setRange(5, 15)
        offset_widget.setValue(self.config.get("data_offset", 5))
        offset_container = self._create_field_container(
            "Data Offset",
            offset_widget,
            "Header size in 32-bit words (5-15)",
            "data_offset"
        )
        header_layout.addWidget(offset_container, 0, 0)
        
        # Reserved
        reserved_widget = QSpinBox()
        reserved_widget.setRange(0, 7)
        reserved_widget.setValue(self.config.get("reserved", 0))
        reserved_container = self._create_field_container(
            "Reserved",
            reserved_widget,
            "Reserved bits (must be 0)",
            "reserved"
        )
        header_layout.addWidget(reserved_container, 0, 1)
        
        # Window Size
        window_widget = QSpinBox()
        window_widget.setRange(0, 65535)
        window_widget.setValue(self.config.get("window_size", 8192))
        window_container = self._create_field_container(
            "Window Size",
            window_widget,
            "Receive window size",
            "window_size"
        )
        header_layout.addWidget(window_container, 1, 0)
        
        # Checksum
        checksum_widget = QSpinBox()
        checksum_widget.setRange(0, 65535)
        checksum_widget.setValue(self.config.get("checksum", 0))
        checksum_widget.setDisplayIntegerBase(16)
        checksum_widget.setPrefix("0x")
        checksum_container = self._create_field_container(
            "Checksum",
            checksum_widget,
            "TCP checksum (0 = auto-calculate)",
            "checksum"
        )
        header_layout.addWidget(checksum_container, 1, 1)
        
        # Urgent Pointer
        urgent_widget = QSpinBox()
        urgent_widget.setRange(0, 65535)
        urgent_widget.setValue(self.config.get("urgent_pointer", 0))
        urgent_container = self._create_field_container(
            "Urgent Pointer",
            urgent_widget,
            "Pointer to urgent data",
            "urgent_pointer"
        )
        header_layout.addWidget(urgent_container, 2, 0)
        
        header_group.setLayout(header_layout)
        self.form_layout.addWidget(header_group)
        
        # TCP Flags Section (All 9 flags)
        flags_group = QGroupBox("TCP Flags")
        flags_layout = QGridLayout()
        flags_layout.setSpacing(15)
        
        # Get current flags value
        flags_value = self.config.get("flags", 0x02)
        
        tcp_flags = [
            ("fin", "FIN - Finish", bool(flags_value & 0x001), 0, 0),
            ("syn", "SYN - Synchronize", bool(flags_value & 0x002), 0, 1),
            ("rst", "RST - Reset", bool(flags_value & 0x004), 0, 2),
            ("psh", "PSH - Push", bool(flags_value & 0x008), 1, 0),
            ("ack", "ACK - Acknowledgment", bool(flags_value & 0x010), 1, 1),
            ("urg", "URG - Urgent", bool(flags_value & 0x020), 1, 2),
            ("ece", "ECE - ECN Echo", bool(flags_value & 0x040), 2, 0),
            ("cwr", "CWR - Congestion Window Reduced", bool(flags_value & 0x080), 2, 1),
            ("ns", "NS - Nonce Sum", bool(flags_value & 0x100), 2, 2)
        ]
        
        for flag_name, flag_label, is_set, row, col in tcp_flags:
            checkbox = QCheckBox(flag_label)
            checkbox.setChecked(is_set)
            self.field_widgets[flag_name] = checkbox
            # Les flags n'ont pas besoin d'error labels
            flags_layout.addWidget(checkbox, row, col)
            
        flags_group.setLayout(flags_layout)
        self.form_layout.addWidget(flags_group)
        
        # TCP Options Section
        options_group = QGroupBox("TCP Options")
        options_layout = QGridLayout()
        options_layout.setSpacing(20)
        
        # MSS (Maximum Segment Size)
        mss_widget = QSpinBox()
        mss_widget.setRange(0, 65535)
        mss_widget.setValue(self.config.get("mss", 1460))
        mss_widget.setSpecialValueText("Disabled")
        mss_container = self._create_field_container(
            "MSS",
            mss_widget,
            "Maximum Segment Size (0 = disabled)",
            "mss"
        )
        options_layout.addWidget(mss_container, 0, 0)
        
        # Window Scale
        ws_widget = QSpinBox()
        ws_widget.setRange(-1, 14)
        ws_widget.setValue(self.config.get("window_scale", -1))
        ws_widget.setSpecialValueText("Disabled")
        ws_container = self._create_field_container(
            "Window Scale",
            ws_widget,
            "Window scale factor (-1 = disabled, 0-14)",
            "window_scale"
        )
        options_layout.addWidget(ws_container, 0, 1)
        
        # SACK Permitted
        sack_widget = QCheckBox("SACK Permitted")
        sack_widget.setChecked(self.config.get("sack_permitted", False))
        self.field_widgets["sack_permitted"] = sack_widget
        options_layout.addWidget(sack_widget, 1, 0)
        
        # Timestamp
        ts_widget = QCheckBox("Enable Timestamp")
        ts_widget.setChecked(self.config.get("timestamp_enabled", False))
        self.field_widgets["timestamp_enabled"] = ts_widget
        options_layout.addWidget(ts_widget, 1, 1)
        
        # Raw Options (hex)
        raw_opt_widget = QLineEdit()
        raw_opt_widget.setText(self.config.get("raw_options", ""))
        raw_opt_widget.setPlaceholderText("Hex string (e.g., 020405b4)")
        raw_opt_container = self._create_field_container(
            "Raw Options",
            raw_opt_widget,
            "Additional TCP options as hex string",
            "raw_options"
        )
        options_layout.addWidget(raw_opt_container, 2, 0, 1, 2)
        
        options_group.setLayout(options_layout)
        self.form_layout.addWidget(options_group)
        
        # Payload Section
        payload_group = QGroupBox("Payload")
        payload_layout = QVBoxLayout()
        
        payload_widget = QTextEdit()
        payload_widget.setPlainText(self.config.get("payload", ""))
        payload_widget.setMaximumHeight(100)
        payload_widget.setPlaceholderText("TCP payload data (text or hex)")
        self.field_widgets["payload"] = payload_widget
        
        payload_layout.addWidget(QLabel("Payload Data:"))
        payload_layout.addWidget(payload_widget)
        
        payload_group.setLayout(payload_layout)
        self.form_layout.addWidget(payload_group)
        
    def _create_udp_fields(self):
        """Create UDP fields matching UDPFactory parameters"""
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(20)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        
        # Source Port
        src_port_widget = QSpinBox()
        src_port_widget.setRange(1, 65535)
        src_port_widget.setValue(self.config.get("src_port", 49152))
        src_port_container = self._create_field_container(
            "Source Port",
            src_port_widget,
            "UDP source port (1-65535)",
            "src_port"
        )
        grid_layout.addWidget(src_port_container, 0, 0)
        
        # Destination Port
        dst_port_widget = QSpinBox()
        dst_port_widget.setRange(1, 65535)
        dst_port_widget.setValue(self.config.get("dst_port", 53))
        dst_port_container = self._create_field_container(
            "Destination Port",
            dst_port_widget,
            "UDP destination port (1-65535)",
            "dst_port"
        )
        grid_layout.addWidget(dst_port_container, 0, 1)
        
        # Length
        length_widget = QSpinBox()
        length_widget.setRange(8, 65535)
        length_widget.setValue(self.config.get("length", 8))
        length_container = self._create_field_container(
            "Length",
            length_widget,
            "Total UDP datagram length (8-65535)",
            "length"
        )
        grid_layout.addWidget(length_container, 1, 0)
        
        # Checksum
        checksum_widget = QSpinBox()
        checksum_widget.setRange(0, 65535)
        checksum_widget.setValue(self.config.get("checksum", 0))
        checksum_widget.setDisplayIntegerBase(16)
        checksum_widget.setPrefix("0x")
        checksum_container = self._create_field_container(
            "Checksum",
            checksum_widget,
            "UDP checksum (0 = disabled)",
            "checksum"
        )
        grid_layout.addWidget(checksum_container, 1, 1)
        
        self.form_layout.addWidget(grid_widget)
        
    def _create_ethernet_fields(self):
        """Create Ethernet fields - complete Ethernet frame"""
        # Frame Structure Section
        frame_group = QGroupBox("Frame Structure")
        frame_layout = QGridLayout()
        frame_layout.setSpacing(20)
        
        # Preamble
        preamble_widget = QLineEdit()
        preamble_widget.setText(self.config.get("preamble", "AAAAAAAAAAAAAAAA"))
        preamble_widget.setPlaceholderText("Hex string (default: AAAAAAAAAAAAAAAA)")
        preamble_container = self._create_field_container(
            "Preamble",
            preamble_widget,
            "7 bytes of 0xAA (56 bits of alternating 1s and 0s)",
            "preamble"
        )
        frame_layout.addWidget(preamble_container, 0, 0)
        
        # SFD (Start Frame Delimiter)
        sfd_widget = QLineEdit()
        sfd_widget.setText(self.config.get("sfd", "AB"))
        sfd_widget.setMaxLength(2)
        sfd_widget.setPlaceholderText("AB")
        sfd_container = self._create_field_container(
            "SFD",
            sfd_widget,
            "Start Frame Delimiter (default: 0xAB)",
            "sfd"
        )
        frame_layout.addWidget(sfd_container, 0, 1)
        
        frame_group.setLayout(frame_layout)
        self.form_layout.addWidget(frame_group)
        
        # MAC Addresses Section
        mac_group = QGroupBox("MAC Addresses")
        mac_layout = QGridLayout()
        mac_layout.setSpacing(20)
        
        # Destination MAC
        dst_mac_widget = QLineEdit()
        dst_mac_widget.setText(self.config.get("dst_mac", "02:00:00:00:00:02"))
        dst_mac_widget.setPlaceholderText("XX:XX:XX:XX:XX:XX")
        dst_mac_container = self._create_field_container(
            "Destination MAC",
            dst_mac_widget,
            "Format: XX:XX:XX:XX:XX:XX",
            "dst_mac"
        )
        mac_layout.addWidget(dst_mac_container, 0, 0)
        
        # Source MAC
        src_mac_widget = QLineEdit()
        src_mac_widget.setText(self.config.get("src_mac", "02:00:00:00:00:01"))
        src_mac_widget.setPlaceholderText("XX:XX:XX:XX:XX:XX")
        src_mac_container = self._create_field_container(
            "Source MAC",
            src_mac_widget,
            "Format: XX:XX:XX:XX:XX:XX",
            "src_mac"
        )
        mac_layout.addWidget(src_mac_container, 0, 1)
        
        mac_group.setLayout(mac_layout)
        self.form_layout.addWidget(mac_group)
        
        # Type/Length and FCS Section
        control_group = QGroupBox("Control Fields")
        control_layout = QGridLayout()
        control_layout.setSpacing(20)
        
        # EtherType/Length
        ether_widget = QSpinBox()
        ether_widget.setRange(0, 0xFFFF)
        ether_widget.setValue(self.config.get("ether_type", 0x0800))
        ether_widget.setDisplayIntegerBase(16)
        ether_widget.setPrefix("0x")
        ether_container = self._create_field_container(
            "EtherType/Length",
            ether_widget,
            "0x0800=IPv4, 0x86DD=IPv6, 0x0806=ARP, <1536=Length",
            "ether_type"
        )
        control_layout.addWidget(ether_container, 0, 0)
        
        # FCS (Frame Check Sequence)
        fcs_widget = QLineEdit()
        fcs_widget.setText(self.config.get("fcs", "0"))
        fcs_widget.setPlaceholderText("Hex value or 0 for auto-calculate")
        fcs_container = self._create_field_container(
            "FCS",
            fcs_widget,
            "Frame Check Sequence (0 = auto-calculate CRC32)",
            "fcs"
        )
        control_layout.addWidget(fcs_container, 0, 1)
        
        control_group.setLayout(control_layout)
        self.form_layout.addWidget(control_group)
        
        # Optional: Payload Section for Ethernet
        payload_group = QGroupBox("Payload (Optional)")
        payload_layout = QVBoxLayout()
        
        payload_widget = QTextEdit()
        payload_widget.setPlainText(self.config.get("payload", ""))
        payload_widget.setMaximumHeight(80)
        payload_widget.setPlaceholderText("Ethernet payload (46-1500 bytes)")
        self.field_widgets["payload"] = payload_widget
        
        payload_layout.addWidget(payload_widget)
        
        payload_group.setLayout(payload_layout)
        self.form_layout.addWidget(payload_group)
        
    def _create_vlan_fields(self):
        """Create VLAN fields matching VLANFactory parameters"""
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(20)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        
        # VLAN ID
        vlan_widget = QSpinBox()
        vlan_widget.setRange(1, 4094)
        vlan_widget.setValue(self.config.get("vlan_id", 100))
        vlan_container = self._create_field_container(
            "VLAN ID",
            vlan_widget,
            "Unique VLAN identifier (1-4094)",
            "vlan_id"
        )
        grid_layout.addWidget(vlan_container, 0, 0)
        
        # Priority (PCP)
        priority_widget = QSpinBox()
        priority_widget.setRange(0, 7)
        priority_widget.setValue(self.config.get("priority", 0))
        priority_container = self._create_field_container(
            "Priority (PCP)",
            priority_widget,
            "Priority Code Point for QoS (0-7)",
            "priority"
        )
        grid_layout.addWidget(priority_container, 0, 1)
        
        # CFI
        cfi_widget = QSpinBox()
        cfi_widget.setRange(0, 1)
        cfi_widget.setValue(self.config.get("cfi", 0))
        cfi_container = self._create_field_container(
            "CFI",
            cfi_widget,
            "Canonical Format Indicator (0 or 1)",
            "cfi"
        )
        grid_layout.addWidget(cfi_container, 1, 0)
        
        # Ethernet Type
        ether_widget = QSpinBox()
        ether_widget.setRange(0, 0xFFFF)
        ether_widget.setValue(self.config.get("ether_type", 0x0800))
        ether_widget.setDisplayIntegerBase(16)
        ether_widget.setPrefix("0x")
        ether_container = self._create_field_container(
            "Ethernet Type",
            ether_widget,
            "0x0800 for IPv4, 0x86DD for IPv6",
            "ether_type"
        )
        grid_layout.addWidget(ether_container, 1, 1)
        
        self.form_layout.addWidget(grid_widget)
        
    def _create_ipv4_fields(self):
        """Create IPv4 fields matching IPPacketFactory parameters"""
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(20)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        
        # Source IP
        src_ip_widget = QLineEdit()
        src_ip_widget.setText(self.config.get("src_ip", "10.0.0.1"))
        src_ip_widget.setPlaceholderText("xxx.xxx.xxx.xxx")
        src_ip_container = self._create_field_container(
            "Source IP",
            src_ip_widget,
            "Source IP address",
            "src_ip"
        )
        grid_layout.addWidget(src_ip_container, 0, 0)
        
        # Destination IP
        dst_ip_widget = QLineEdit()
        dst_ip_widget.setText(self.config.get("dst_ip", "10.0.0.2"))
        dst_ip_widget.setPlaceholderText("xxx.xxx.xxx.xxx")
        dst_ip_container = self._create_field_container(
            "Destination IP",
            dst_ip_widget,
            "Destination IP address",
            "dst_ip"
        )
        grid_layout.addWidget(dst_ip_container, 0, 1)
        
        # Protocol
        protocol_widget = QSpinBox()
        protocol_widget.setRange(0, 255)
        protocol_widget.setValue(self.config.get("protocol", 6))
        protocol_container = self._create_field_container(
            "Protocol",
            protocol_widget,
            "6=TCP, 17=UDP, 1=ICMP",
            "protocol"
        )
        grid_layout.addWidget(protocol_container, 1, 0)
        
        self.form_layout.addWidget(grid_widget)
        
    def _create_ipv6_fields(self):
        """Create IPv6 fields matching IPPacketFactory parameters"""
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(20)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        
        # Source IPv6
        src_ipv6_widget = QLineEdit()
        src_ipv6_widget.setText(self.config.get("src_ip", "2001:db8::1"))
        src_ipv6_widget.setPlaceholderText("xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx")
        src_ipv6_container = self._create_field_container(
            "Source IPv6",
            src_ipv6_widget,
            "Source IPv6 address",
            "src_ip"
        )
        grid_layout.addWidget(src_ipv6_container, 0, 0)
        
        # Destination IPv6
        dst_ipv6_widget = QLineEdit()
        dst_ipv6_widget.setText(self.config.get("dst_ip", "2001:db8::2"))
        dst_ipv6_widget.setPlaceholderText("xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx")
        dst_ipv6_container = self._create_field_container(
            "Destination IPv6",
            dst_ipv6_widget,
            "Destination IPv6 address",
            "dst_ip"
        )
        grid_layout.addWidget(dst_ipv6_container, 0, 1)
        
        # Protocol
        protocol_widget = QSpinBox()
        protocol_widget.setRange(0, 255)
        protocol_widget.setValue(self.config.get("protocol", 6))
        protocol_container = self._create_field_container(
            "Next Header",
            protocol_widget,
            "6=TCP, 17=UDP, 58=ICMPv6",
            "protocol"
        )
        grid_layout.addWidget(protocol_container, 1, 0)
        
        self.form_layout.addWidget(grid_widget)
        
    def _create_arp_fields(self):
        """Create ARP fields matching ARPFactory parameters"""
        # Hardware/Protocol Section
        hw_group = QGroupBox("Hardware/Protocol Configuration")
        hw_layout = QGridLayout()
        hw_layout.setSpacing(20)
        
        # Hardware Type
        hw_type_widget = QSpinBox()
        hw_type_widget.setRange(0, 65535)
        hw_type_widget.setValue(self.config.get("hw_type", 1))
        hw_type_container = self._create_field_container(
            "Hardware Type",
            hw_type_widget,
            "1 = Ethernet",
            "hw_type"
        )
        hw_layout.addWidget(hw_type_container, 0, 0)
        
        # Protocol Type
        proto_type_widget = QSpinBox()
        proto_type_widget.setRange(0, 0xFFFF)
        proto_type_widget.setValue(self.config.get("proto_type", 0x0800))
        proto_type_widget.setDisplayIntegerBase(16)
        proto_type_widget.setPrefix("0x")
        proto_type_container = self._create_field_container(
            "Protocol Type",
            proto_type_widget,
            "0x0800 = IPv4",
            "proto_type"
        )
        hw_layout.addWidget(proto_type_container, 0, 1)
        
        # Hardware Length
        hw_len_widget = QSpinBox()
        hw_len_widget.setRange(0, 255)
        hw_len_widget.setValue(self.config.get("hw_len", 6))
        hw_len_container = self._create_field_container(
            "Hardware Length",
            hw_len_widget,
            "6 for Ethernet",
            "hw_len"
        )
        hw_layout.addWidget(hw_len_container, 1, 0)
        
        # Protocol Length
        proto_len_widget = QSpinBox()
        proto_len_widget.setRange(0, 255)
        proto_len_widget.setValue(self.config.get("proto_len", 4))
        proto_len_container = self._create_field_container(
            "Protocol Length",
            proto_len_widget,
            "4 for IPv4",
            "proto_len"
        )
        hw_layout.addWidget(proto_len_container, 1, 1)
        
        # Operation
        op_widget = QComboBox()
        op_widget.addItems(["1 - Request", "2 - Reply"])
        op_widget.setCurrentIndex(self.config.get("operation", 1) - 1)
        op_container = self._create_field_container(
            "Operation",
            op_widget,
            "ARP operation type",
            "operation"
        )
        hw_layout.addWidget(op_container, 2, 0, 1, 2)
        
        hw_group.setLayout(hw_layout)
        self.form_layout.addWidget(hw_group)
        
        # Addresses Section
        addr_group = QGroupBox("Addresses")
        addr_layout = QGridLayout()
        addr_layout.setSpacing(20)
        
        # Sender MAC
        sender_mac_widget = QLineEdit()
        sender_mac_widget.setText(self.config.get("sender_mac", "02:00:00:00:00:01"))
        sender_mac_widget.setPlaceholderText("XX:XX:XX:XX:XX:XX")
        sender_mac_container = self._create_field_container(
            "Sender MAC",
            sender_mac_widget,
            "Sender MAC address",
            "sender_mac"
        )
        addr_layout.addWidget(sender_mac_container, 0, 0)
        
        # Sender IP
        sender_ip_widget = QLineEdit()
        sender_ip_widget.setText(self.config.get("sender_ip", "10.0.0.1"))
        sender_ip_widget.setPlaceholderText("xxx.xxx.xxx.xxx")
        sender_ip_container = self._create_field_container(
            "Sender IP",
            sender_ip_widget,
            "Sender IP address",
            "sender_ip"
        )
        addr_layout.addWidget(sender_ip_container, 0, 1)
        
        # Target MAC
        target_mac_widget = QLineEdit()
        target_mac_widget.setText(self.config.get("target_mac", "00:00:00:00:00:00"))
        target_mac_widget.setPlaceholderText("XX:XX:XX:XX:XX:XX")
        target_mac_container = self._create_field_container(
            "Target MAC",
            target_mac_widget,
            "Target MAC (00:00:00:00:00:00 for request)",
            "target_mac"
        )
        addr_layout.addWidget(target_mac_container, 1, 0)
        
        # Target IP
        target_ip_widget = QLineEdit()
        target_ip_widget.setText(self.config.get("target_ip", "10.0.0.2"))
        target_ip_widget.setPlaceholderText("xxx.xxx.xxx.xxx")
        target_ip_container = self._create_field_container(
            "Target IP",
            target_ip_widget,
            "Target IP address",
            "target_ip"
        )
        addr_layout.addWidget(target_ip_container, 1, 1)
        
        addr_group.setLayout(addr_layout)
        self.form_layout.addWidget(addr_group)
        
    def _create_generic_fields(self):
        """Create generic fields for unknown protocols"""
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(20)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        
        row = 0
        col = 0
        
        for field_name, default_value in self.config.items():
            label = field_name.replace('_', ' ').title()
            
            if isinstance(default_value, bool):
                widget = QCheckBox(label)
                widget.setChecked(default_value)
            elif isinstance(default_value, int):
                widget = QSpinBox()
                widget.setRange(0, 2147483647)
                widget.setValue(default_value)
            else:
                widget = QLineEdit(str(default_value))
                
            container = self._create_field_container(label, widget, "", field_name)
            grid_layout.addWidget(container, row, col)
            
            col += 1
            if col > 1:
                col = 0
                row += 1
                
        self.form_layout.addWidget(grid_widget)
        
    def _validate_field(self, field_name):
        """Validate a single field with real-time feedback"""
        if field_name not in self.field_widgets:
            return
            
        # Skip validation for TCP flags (they don't have error labels)
        if self.protocol_name == "TCP" and field_name in ["fin", "syn", "rst", "psh", "ack", "urg", "ece", "cwr", "ns"]:
            return
            
        widget = self.field_widgets[field_name]
        value = self._get_widget_value(widget)
        
        # Skip validation for empty optional fields
        if isinstance(widget, QLineEdit) and not value and field_name not in ["src_mac", "dst_mac", "src_ip", "dst_ip"]:
            if field_name in self.error_labels:
                self.error_labels[field_name].hide()
                widget.setProperty("hasError", False)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            return
            
        # Get validation rules
        rules = VALIDATION_RULES.get(self.protocol_name, {}).get(field_name, {})
        
        error_message = None
        
        # Check validation rules
        if "pattern" in rules and isinstance(value, str):
            if not re.match(rules["pattern"], value):
                error_message = rules["message"]
        elif "min" in rules and "max" in rules and isinstance(value, (int, float)):
            if not rules["min"] <= value <= rules["max"]:
                error_message = rules["message"]
        elif "value" in rules:
            if value != rules["value"]:
                error_message = rules["message"]
        elif "ipv6" in rules and isinstance(value, str):
            # Basic IPv6 validation
            try:
                import socket
                socket.inet_pton(socket.AF_INET6, value)
            except:
                error_message = rules["message"]
            
        # Update UI
        if field_name in self.error_labels:
            if error_message:
                self.validation_errors[field_name] = error_message
                self.error_labels[field_name].setText(error_message)
                self.error_labels[field_name].show()
                widget.setProperty("hasError", True)
            else:
                self.validation_errors.pop(field_name, None)
                self.error_labels[field_name].hide()
                widget.setProperty("hasError", False)
                
            # Refresh style
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        
        # Update button state
        self._update_save_button_state()
        
    def _get_widget_value(self, widget):
        """Get value from widget"""
        if isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget.value()
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QComboBox):
            # For operation field in ARP
            return widget.currentIndex() + 1
        elif isinstance(widget, QTextEdit):
            return widget.toPlainText()
        return None
        
    def _update_save_button_state(self):
        """Update Save button based on validation state"""
        has_errors = bool(self.validation_errors)
        self.save_btn.setEnabled(not has_errors)
        
    def _get_current_config(self):
        """Get current configuration from all widgets"""
        config = {}
        
        for field_name, widget in self.field_widgets.items():
            value = self._get_widget_value(widget)
            config[field_name] = value
            
        # Special handling for TCP flags
        if self.protocol_name == "TCP":
            # Build flags value from checkboxes
            flags = 0
            if config.get("fin", False): flags |= 0x001
            if config.get("syn", False): flags |= 0x002
            if config.get("rst", False): flags |= 0x004
            if config.get("psh", False): flags |= 0x008
            if config.get("ack", False): flags |= 0x010
            if config.get("urg", False): flags |= 0x020
            if config.get("ece", False): flags |= 0x040
            if config.get("cwr", False): flags |= 0x080
            if config.get("ns", False): flags |= 0x100
            config["flags"] = flags
            # Remove individual flag fields
            for flag in ["fin", "syn", "rst", "psh", "ack", "urg", "ece", "cwr", "ns"]:
                config.pop(flag, None)
            
            # Handle special values for options
            if config.get("mss") == 0:
                config.pop("mss", None)
            if config.get("window_scale") == -1:
                config.pop("window_scale", None)
                
        return config
        
    def _accept(self):
        """Accept dialog if validation passes"""
        # Final validation
        all_valid = True
        for field_name in self.field_widgets:
            # Skip TCP flags validation
            if self.protocol_name == "TCP" and field_name in ["fin", "syn", "rst", "psh", "ack", "urg", "ece", "cwr", "ns"]:
                continue
            self._validate_field(field_name)
            
        if self.validation_errors:
            all_valid = False
            
        if all_valid:
            self.config = self._get_current_config()
            
            # Send config to stack controller if available
            if self.stack_controller:
                # Try to validate with controller
                if hasattr(self.stack_controller, 'validate_protocol_config'):
                    is_valid, msg = self.stack_controller.validate_protocol_config(
                        self.protocol_name, self.config
                    )
                    if not is_valid:
                        QMessageBox.warning(self, "Validation Error", msg)
                        return
                        
            self.config_validated.emit(self.config)
            self.accept()
            
    def get_configuration(self):
        """Get the final configuration"""
        return self._get_current_config()


# Test if executed directly
if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Test dialog for each protocol
    protocols = ["TCP", "UDP", "Ethernet", "IPv4", "IPv6", "VLAN", "ARP"]
    
    for protocol in protocols:
        dialog = ProtocolConfigDialog(protocol)
        print(f"\n=== Testing {protocol} ===")
        print(f"Available fields: {list(dialog.field_widgets.keys())}")
        print(f"Default config: {dialog.config}")
        
    # Show a test dialog
    dialog = ProtocolConfigDialog("TCP")
    result = dialog.exec_()
    
    if result == QDialog.Accepted:
        print("Configuration accepted:", dialog.get_configuration())
    else:
        print("Configuration cancelled")
    
    sys.exit()