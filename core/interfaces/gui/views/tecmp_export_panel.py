#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TECMP Export Panel - Multi-Format Export
Version corrigee avec integration complete du trace view
"""

import json
import time
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QComboBox,
    QCheckBox, QProgressBar, QLabel, QFileDialog, QMessageBox, QSpinBox,
    QButtonGroup, QRadioButton, QFrame, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont

# Import conditionnel de scapy
try:
    from scapy.all import Packet, wrpcap
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    class Packet:
        pass


class ExportFormat(Enum):
    """Supported export formats."""
    PCAP = ("pcap", "PCAP File", "Wireshark PCAP format")
    PCAPNG = ("pcapng", "PCAPNG File", "Next generation PCAP format")
    JSON = ("json", "JSON File", "Human-readable JSON format")
    CSV = ("csv", "CSV File", "Comma-separated values")
    TXT = ("txt", "Text File", "Plain text summary")
    XML = ("xml", "XML File", "Structured XML format")
    HEX = ("hex", "Hex Dump", "Raw hexadecimal dump")
    
    def __init__(self, ext, name, description):
        self.ext = ext
        self.display_name = name  # Éviter le conflit avec .name de Enum
        self.description = description


class ExportScope(Enum):
    """Export scope options."""
    ALL = "all"
    SELECTED = "selected"
    RANGE = "range"
    FILTERED = "filtered"


@dataclass
class ExportOptions:
    """Export configuration options."""
    format: ExportFormat
    scope: ExportScope
    file_path: str
    include_timestamp: bool = True
    include_raw_data: bool = True
    include_analysis: bool = False
    packet_range: tuple = (0, -1)
    compression: bool = False
    split_files: bool = False
    max_file_size_mb: int = 100
    selected_indices: List[int] = None  # Pour les paquets selectionnes


class ExportWorker(QThread):
    """Background export worker thread."""
    
    progress_updated = pyqtSignal(int, str)  # percentage, status
    export_completed = pyqtSignal(bool, str)  # success, message
    error_occurred = pyqtSignal(str)
    
    def __init__(self, packets, options: ExportOptions, facade=None):
        super().__init__()
        self.packets = packets
        self.options = options
        self.facade = facade
        self._is_cancelled = False
    
    def cancel(self):
        """Cancel the export operation."""
        self._is_cancelled = True
    
    def run(self):
        """Execute export in background."""
        try:
            self.progress_updated.emit(0, "Starting export...")
            
            # Filter packets based on scope
            packets_to_export = self._filter_packets()
            
            if not packets_to_export:
                self.export_completed.emit(False, "No packets to export")
                return
            
            self.progress_updated.emit(10, f"Exporting {len(packets_to_export)} packets...")
            
            # Check if cancelled
            if self._is_cancelled:
                self.export_completed.emit(False, "Export cancelled")
                return
            
            # Export based on format
            success = False
            if self.options.format == ExportFormat.PCAP:
                success = self._export_pcap(packets_to_export)
            elif self.options.format == ExportFormat.PCAPNG:
                success = self._export_pcapng(packets_to_export)
            elif self.options.format == ExportFormat.JSON:
                success = self._export_json(packets_to_export)
            elif self.options.format == ExportFormat.CSV:
                success = self._export_csv(packets_to_export)
            elif self.options.format == ExportFormat.TXT:
                success = self._export_txt(packets_to_export)
            elif self.options.format == ExportFormat.XML:
                success = self._export_xml(packets_to_export)
            elif self.options.format == ExportFormat.HEX:
                success = self._export_hex(packets_to_export)
            
            if self._is_cancelled:
                self.export_completed.emit(False, "Export cancelled")
                return
            
            self.progress_updated.emit(100, "Export completed")
            
            if success:
                self.export_completed.emit(True, f"Exported {len(packets_to_export)} packets to {self.options.file_path}")
            else:
                self.export_completed.emit(False, "Export failed")
                
        except Exception as e:
            self.error_occurred.emit(f"Export error: {str(e)}")
    
    def _filter_packets(self) -> List[Any]:
        """Filter packets based on export scope."""
        if self.options.scope == ExportScope.ALL:
            return self.packets
        
        elif self.options.scope == ExportScope.SELECTED:
            # Utiliser les indices selectionnes
            if self.options.selected_indices:
                return [self.packets[i] for i in self.options.selected_indices 
                       if 0 <= i < len(self.packets)]
            return []
        
        elif self.options.scope == ExportScope.RANGE:
            start, end = self.options.packet_range
            if end == -1:
                end = len(self.packets)
            return self.packets[start:end]
        
        else:
            return self.packets
    
    def _export_pcap(self, packets: List[Any]) -> bool:
        """Export to PCAP format."""
        if not SCAPY_AVAILABLE:
            self.error_occurred.emit("Scapy is not available for PCAP export")
            return False
        
        try:
            self.progress_updated.emit(50, "Writing PCAP file...")
            
            # Use facade if available
            if self.facade and hasattr(self.facade, 'export_pcap'):
                return self.facade.export_pcap(self.options.file_path, packets)
            else:
                # Fallback to scapy
                wrpcap(self.options.file_path, packets)
                return True
                
        except Exception as e:
            self.error_occurred.emit(f"PCAP export error: {str(e)}")
            return False
    
    def _export_pcapng(self, packets: List[Any]) -> bool:
        """Export to PCAPNG format."""
        try:
            self.progress_updated.emit(50, "Writing PCAPNG file...")
            
            # Use facade if available
            if self.facade and hasattr(self.facade, 'export_pcapng'):
                return self.facade.export_pcapng(self.options.file_path, packets)
            else:
                # Fallback - save as PCAP with .pcapng extension
                if SCAPY_AVAILABLE:
                    wrpcap(self.options.file_path, packets)
                    return True
                else:
                    self.error_occurred.emit("Scapy not available for PCAPNG export")
                    return False
                
        except Exception as e:
            self.error_occurred.emit(f"PCAPNG export error: {str(e)}")
            return False
    
    def _export_json(self, packets: List[Any]) -> bool:
        """Export to JSON format."""
        try:
            self.progress_updated.emit(50, "Converting to JSON...")
            
            json_data = {
                "export_info": {
                    "timestamp": datetime.now().isoformat(),
                    "packet_count": len(packets),
                    "format": "TECMP JSON Export",
                    "options": {
                        "include_timestamp": self.options.include_timestamp,
                        "include_raw_data": self.options.include_raw_data,
                        "include_analysis": self.options.include_analysis
                    }
                },
                "packets": []
            }
            
            for i, packet in enumerate(packets):
                if self._is_cancelled:
                    return False
                
                packet_data = {
                    "index": i,
                    "summary": str(packet) if hasattr(packet, 'summary') else str(packet)
                }
                
                if self.options.include_timestamp:
                    packet_data["timestamp"] = getattr(packet, 'time', time.time())
                
                if self.options.include_raw_data and hasattr(packet, 'hexdump'):
                    packet_data["raw_hex"] = packet.hexdump(dump=True) if callable(packet.hexdump) else str(packet)
                    packet_data["length"] = len(packet) if hasattr(packet, '__len__') else 0
                
                if self.options.include_analysis:
                    packet_data["layers"] = self._analyze_packet_layers(packet)
                
                json_data["packets"].append(packet_data)
                
                # Update progress
                if i % 100 == 0:
                    progress = 50 + (i / len(packets)) * 40
                    self.progress_updated.emit(int(progress), f"Processing packet {i+1}/{len(packets)}")
            
            # Write JSON file
            with open(self.options.file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"JSON export error: {str(e)}")
            return False
    
    def _export_csv(self, packets: List[Any]) -> bool:
        """Export to CSV format."""
        try:
            self.progress_updated.emit(50, "Writing CSV file...")
            
            import csv
            
            with open(self.options.file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Header
                headers = ["Index", "Summary", "Length"]
                if self.options.include_timestamp:
                    headers.append("Timestamp")
                if self.options.include_raw_data:
                    headers.append("Raw_Hex")
                
                writer.writerow(headers)
                
                # Data rows
                for i, packet in enumerate(packets):
                    if self._is_cancelled:
                        return False
                    
                    row = [i, str(packet), len(packet) if hasattr(packet, '__len__') else 0]
                    
                    if self.options.include_timestamp:
                        row.append(getattr(packet, 'time', time.time()))
                    
                    if self.options.include_raw_data and hasattr(packet, 'hexdump'):
                        hex_dump = packet.hexdump(dump=True) if callable(packet.hexdump) else ""
                        row.append(hex_dump.replace('\n', ' '))
                    
                    writer.writerow(row)
                    
                    # Update progress
                    if i % 100 == 0:
                        progress = 50 + (i / len(packets)) * 40
                        self.progress_updated.emit(int(progress), f"Writing row {i+1}/{len(packets)}")
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"CSV export error: {str(e)}")
            return False
    
    def _export_txt(self, packets: List[Any]) -> bool:
        """Export to text format."""
        try:
            self.progress_updated.emit(50, "Writing text file...")
            
            with open(self.options.file_path, 'w', encoding='utf-8') as f:
                f.write("TECMP Packet Export\n")
                f.write("=" * 50 + "\n")
                f.write(f"Export Date: {datetime.now()}\n")
                f.write(f"Packet Count: {len(packets)}\n\n")
                
                for i, packet in enumerate(packets):
                    if self._is_cancelled:
                        return False
                    
                    f.write(f"Packet #{i+1}\n")
                    f.write("-" * 20 + "\n")
                    f.write(f"Summary: {str(packet)}\n")
                    f.write(f"Length: {len(packet) if hasattr(packet, '__len__') else 0} bytes\n")
                    
                    if self.options.include_timestamp:
                        timestamp = getattr(packet, 'time', time.time())
                        f.write(f"Timestamp: {datetime.fromtimestamp(timestamp)}\n")
                    
                    if self.options.include_raw_data and hasattr(packet, 'hexdump'):
                        f.write("Hex Dump:\n")
                        f.write(packet.hexdump(dump=True) if callable(packet.hexdump) else str(packet))
                        f.write("\n")
                    
                    f.write("\n")
                    
                    # Update progress
                    if i % 50 == 0:
                        progress = 50 + (i / len(packets)) * 40
                        self.progress_updated.emit(int(progress), f"Writing packet {i+1}/{len(packets)}")
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Text export error: {str(e)}")
            return False
    
    def _export_xml(self, packets: List[Any]) -> bool:
        """Export to XML format."""
        try:
            self.progress_updated.emit(50, "Writing XML file...")
            
            import xml.etree.ElementTree as ET
            
            root = ET.Element("tecmp_export")
            
            # Export info
            info = ET.SubElement(root, "export_info")
            ET.SubElement(info, "timestamp").text = datetime.now().isoformat()
            ET.SubElement(info, "packet_count").text = str(len(packets))
            
            # Packets
            packets_elem = ET.SubElement(root, "packets")
            
            for i, packet in enumerate(packets):
                if self._is_cancelled:
                    return False
                
                packet_elem = ET.SubElement(packets_elem, "packet", index=str(i))
                ET.SubElement(packet_elem, "summary").text = str(packet)
                ET.SubElement(packet_elem, "length").text = str(len(packet) if hasattr(packet, '__len__') else 0)
                
                if self.options.include_timestamp:
                    timestamp = getattr(packet, 'time', time.time())
                    ET.SubElement(packet_elem, "timestamp").text = str(timestamp)
                
                if self.options.include_raw_data and hasattr(packet, 'hexdump'):
                    ET.SubElement(packet_elem, "raw_hex").text = packet.hexdump(dump=True) if callable(packet.hexdump) else ""
                
                # Update progress
                if i % 100 == 0:
                    progress = 50 + (i / len(packets)) * 40
                    self.progress_updated.emit(int(progress), f"Processing packet {i+1}/{len(packets)}")
            
            # Write XML
            tree = ET.ElementTree(root)
            tree.write(self.options.file_path, encoding='utf-8', xml_declaration=True)
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"XML export error: {str(e)}")
            return False
    
    def _export_hex(self, packets: List[Any]) -> bool:
        """Export raw hex dump."""
        try:
            self.progress_updated.emit(50, "Writing hex dump...")
            
            with open(self.options.file_path, 'w', encoding='utf-8') as f:
                f.write("TECMP Raw Hex Dump\n")
                f.write("=" * 50 + "\n\n")
                
                for i, packet in enumerate(packets):
                    if self._is_cancelled:
                        return False
                    
                    f.write(f"Packet #{i+1} ({len(packet) if hasattr(packet, '__len__') else 0} bytes)\n")
                    f.write("-" * 30 + "\n")
                    
                    if hasattr(packet, 'hexdump'):
                        f.write(packet.hexdump(dump=True) if callable(packet.hexdump) else str(packet))
                    else:
                        f.write("No hex dump available\n")
                    
                    f.write("\n\n")
                    
                    # Update progress
                    if i % 50 == 0:
                        progress = 50 + (i / len(packets)) * 40
                        self.progress_updated.emit(int(progress), f"Writing packet {i+1}/{len(packets)}")
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Hex export error: {str(e)}")
            return False
    
    def _analyze_packet_layers(self, packet: Any) -> List[Dict[str, Any]]:
        """Analyze packet layers for detailed export."""
        layers = []
        
        try:
            if not hasattr(packet, 'payload'):
                return layers
            
            current = packet
            while current:
                layer_info = {
                    'name': type(current).__name__,
                    'fields': {}
                }
                
                if hasattr(current, 'fields_desc'):
                    for field in current.fields_desc:
                        if hasattr(current, field.name):
                            layer_info['fields'][field.name] = str(getattr(current, field.name))
                
                layers.append(layer_info)
                current = getattr(current, 'payload', None)
                
                if len(layers) > 10:  # Prevent infinite loops
                    break
                    
        except Exception:
            pass
        
        return layers


class TECMPExportPanel(QWidget):
    """Professional export panel for TECMP trace data."""
    
    export_started = pyqtSignal()
    export_completed = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, facade=None, design_system=None, trace_view=None):
        super().__init__()
        self.facade = facade
        self.design_system = design_system
        self.trace_view = trace_view
        self.current_packets = []
        self.export_worker = None
        self._setup_ui()
        self._connect_trace_view()
        if design_system:
            self._apply_styling()
    
    def _setup_ui(self):
        """Setup export panel interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Header
        header_layout = QHBoxLayout()
        
        # Icone de sauvegarde (sans utiliser get_icon qui n'existe pas)
        export_icon = QLabel("??")  # Emoji comme placeholder
        export_icon.setFont(QFont("", 16))
        header_layout.addWidget(export_icon)
        
        title_label = QLabel("Export Packets")
        title_label.setFont(QFont("", 12, QFont.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Main export options
        options_layout = QHBoxLayout()
        
        # Format selection
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout(format_group)
        
        self.format_combo = QComboBox()
        for fmt in ExportFormat:
            self.format_combo.addItem(f"{fmt.display_name} - {fmt.description}", fmt)
        format_layout.addWidget(self.format_combo)
        
        options_layout.addWidget(format_group)
        
        # Scope selection
        scope_group = QGroupBox("Export Scope")
        scope_layout = QVBoxLayout(scope_group)
        
        self.scope_group = QButtonGroup()
        
        self.all_radio = QRadioButton("All packets")
        self.all_radio.setChecked(True)
        self.scope_group.addButton(self.all_radio, 0)
        scope_layout.addWidget(self.all_radio)
        
        self.selected_radio = QRadioButton("Selected packets")
        self.selected_radio.setEnabled(False)  # Desactive par defaut
        self.scope_group.addButton(self.selected_radio, 1)
        scope_layout.addWidget(self.selected_radio)
        
        range_layout = QHBoxLayout()
        self.range_radio = QRadioButton("Range:")
        self.scope_group.addButton(self.range_radio, 2)
        range_layout.addWidget(self.range_radio)
        
        self.start_spin = QSpinBox()
        self.start_spin.setMinimum(1)
        self.start_spin.setMaximum(999999)
        self.start_spin.setEnabled(False)
        range_layout.addWidget(self.start_spin)
        
        range_layout.addWidget(QLabel("to"))
        
        self.end_spin = QSpinBox()
        self.end_spin.setMinimum(1)
        self.end_spin.setMaximum(999999)
        self.end_spin.setEnabled(False)
        range_layout.addWidget(self.end_spin)
        
        scope_layout.addLayout(range_layout)
        options_layout.addWidget(scope_group)
        
        # Export options
        export_options_group = QGroupBox("Options")
        export_options_layout = QVBoxLayout(export_options_group)
        
        self.timestamp_check = QCheckBox("Include timestamps")
        self.timestamp_check.setChecked(True)
        export_options_layout.addWidget(self.timestamp_check)
        
        self.raw_data_check = QCheckBox("Include raw data")
        self.raw_data_check.setChecked(True)
        export_options_layout.addWidget(self.raw_data_check)
        
        self.analysis_check = QCheckBox("Include packet analysis")
        export_options_layout.addWidget(self.analysis_check)
        
        self.compression_check = QCheckBox("Compress output")
        self.compression_check.setEnabled(False)  # Non implemente
        export_options_layout.addWidget(self.compression_check)
        
        options_layout.addWidget(export_options_group)
        layout.addLayout(options_layout)
        
        # Progress and status
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready to export")
        progress_layout.addWidget(self.status_label)
        
        layout.addLayout(progress_layout)
        
        # Export button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_export)
        button_layout.addWidget(self.cancel_btn)
        
        self.export_btn = QPushButton("Export Packets")
        self.export_btn.clicked.connect(self._start_export)
        button_layout.addWidget(self.export_btn)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.scope_group.buttonClicked.connect(self._on_scope_changed)
        self.range_radio.toggled.connect(self._on_range_toggled)
    
    def _connect_trace_view(self):
        """Connect to trace view signals if available."""
        if self.trace_view:
            # Connecter le signal de selection de paquet
            if hasattr(self.trace_view, 'packet_selected'):
                self.trace_view.packet_selected.connect(self._on_trace_packet_selected)
            
            # Connecter le signal de chargement de trace
            if hasattr(self.trace_view, 'packet_table') and hasattr(self.trace_view.packet_table, 'itemSelectionChanged'):
                self.trace_view.packet_table.itemSelectionChanged.connect(self._update_selected_count)
            
            # Obtenir les paquets initiaux
            if hasattr(self.trace_view, 'current_packets'):
                self.set_packets(self.trace_view.current_packets)
    
    def _on_trace_packet_selected(self, packet):
        """Handle packet selection from trace view."""
        self._update_selected_count()
    
    def _update_selected_count(self):
        """Update the selected packets count."""
        if self.trace_view and hasattr(self.trace_view, 'packet_table'):
            selected_rows = set()
            for item in self.trace_view.packet_table.selectedItems():
                selected_rows.add(item.row())
            
            count = len(selected_rows)
            if count > 0:
                self.selected_radio.setEnabled(True)
                self.selected_radio.setText(f"Selected packets ({count})")
            else:
                self.selected_radio.setEnabled(False)
                self.selected_radio.setText("Selected packets")
    
    def _get_selected_indices(self) -> List[int]:
        """Get indices of selected packets from trace view."""
        if not self.trace_view or not hasattr(self.trace_view, 'packet_table'):
            return []
        
        selected_indices = []
        for item in self.trace_view.packet_table.selectedItems():
            index = item.data(Qt.UserRole)
            if index is not None and index not in selected_indices:
                selected_indices.append(index)
        
        return sorted(selected_indices)
    
    def set_packets(self, packets: List[Any]):
        """Set packets to export."""
        self.current_packets = packets
        self._update_packet_count()
    
    def _update_packet_count(self):
        """Update packet count display."""
        count = len(self.current_packets)
        self.status_label.setText(f"Ready to export ({count} packets available)")
        
        # Update range limits
        if count > 0:
            self.start_spin.setMaximum(count)
            self.end_spin.setMaximum(count)
            self.end_spin.setValue(count)
            self.range_radio.setEnabled(True)
        else:
            self.range_radio.setEnabled(False)
    
    def _on_format_changed(self):
        """Handle format selection change."""
        fmt = self.format_combo.currentData()
        if fmt:
            # Enable/disable options based on format
            if fmt in [ExportFormat.PCAP, ExportFormat.PCAPNG]:
                self.timestamp_check.setEnabled(False)
                self.raw_data_check.setEnabled(False)
                self.analysis_check.setEnabled(False)
            else:
                self.timestamp_check.setEnabled(True)
                self.raw_data_check.setEnabled(True)
                self.analysis_check.setEnabled(True)
    
    def _on_scope_changed(self):
        """Handle scope selection change."""
        self._on_range_toggled()
    
    def _on_range_toggled(self):
        """Handle range radio toggle."""
        is_range = self.range_radio.isChecked()
        self.start_spin.setEnabled(is_range)
        self.end_spin.setEnabled(is_range)
    
    def _start_export(self):
        """Start the export process."""
        if not self.current_packets:
            QMessageBox.warning(self, "No Packets", "No packets available for export.")
            return
        
        # Get export options
        fmt = self.format_combo.currentData()
        if not fmt:
            QMessageBox.warning(self, "No Format", "Please select an export format.")
            return
        
        # Get file path
        filters = {
            ExportFormat.PCAP: "PCAP Files (*.pcap)",
            ExportFormat.PCAPNG: "PCAPNG Files (*.pcapng)",
            ExportFormat.JSON: "JSON Files (*.json)",
            ExportFormat.CSV: "CSV Files (*.csv)",
            ExportFormat.TXT: "Text Files (*.txt)",
            ExportFormat.XML: "XML Files (*.xml)",
            ExportFormat.HEX: "Hex Files (*.hex)"
        }
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Packets",
            f"export.{fmt.ext}",
            f"{filters.get(fmt, 'All Files (*)')};;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Determine scope
        scope = ExportScope.ALL
        packet_range = (0, -1)
        selected_indices = None
        
        if self.selected_radio.isChecked():
            scope = ExportScope.SELECTED
            selected_indices = self._get_selected_indices()
            if not selected_indices:
                QMessageBox.warning(self, "No Selection", "No packets are selected.")
                return
        elif self.range_radio.isChecked():
            scope = ExportScope.RANGE
            packet_range = (self.start_spin.value() - 1, self.end_spin.value())
        
        # Create export options
        options = ExportOptions(
            format=fmt,
            scope=scope,
            file_path=file_path,
            include_timestamp=self.timestamp_check.isChecked(),
            include_raw_data=self.raw_data_check.isChecked(),
            include_analysis=self.analysis_check.isChecked(),
            packet_range=packet_range,
            compression=self.compression_check.isChecked(),
            selected_indices=selected_indices
        )
        
        # Start export worker
        self._start_export_worker(options)
    
    def _start_export_worker(self, options: ExportOptions):
        """Start background export worker."""
        self.export_worker = ExportWorker(self.current_packets, options, self.facade)
        
        # Connect signals
        self.export_worker.progress_updated.connect(self._on_progress_updated)
        self.export_worker.export_completed.connect(self._on_export_completed)
        self.export_worker.error_occurred.connect(self._on_export_error)
        
        # Update UI
        self.export_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Start export
        self.export_worker.start()
        self.export_started.emit()
    
    def _cancel_export(self):
        """Cancel ongoing export."""
        if self.export_worker and self.export_worker.isRunning():
            self.export_worker.cancel()
            self.status_label.setText("Cancelling export...")
    
    @pyqtSlot(int, str)
    def _on_progress_updated(self, percentage, status):
        """Handle export progress updates."""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(status)
    
    @pyqtSlot(bool, str)
    def _on_export_completed(self, success, message):
        """Handle export completion."""
        # Update UI
        self.export_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText(message)
        
        # Show result
        if success:
            QMessageBox.information(self, "Export Complete", message)
        else:
            if "cancelled" not in message.lower():
                QMessageBox.warning(self, "Export Failed", message)
        
        # Emit signal
        self.export_completed.emit(success, message)
        
        # Cleanup worker
        if self.export_worker:
            self.export_worker.deleteLater()
            self.export_worker = None
    
    @pyqtSlot(str)
    def _on_export_error(self, error_message):
        """Handle export errors."""
        self.export_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Export failed: {error_message}")
        
        QMessageBox.critical(self, "Export Error", error_message)
        
        if self.export_worker:
            self.export_worker.deleteLater()
            self.export_worker = None
    
    def _apply_styling(self):
        """Apply design system styling."""
        if not self.design_system:
            return
        
        try:
            palette = self.design_system.get_current_palette()
            
            self.setStyleSheet(f"""
                QWidget {{
                    background: {palette.surface};
                    color: {palette.on_surface};
                }}
                QGroupBox {{
                    font-weight: bold;
                    border: 2px solid {palette.outline};
                    border-radius: 8px;
                    margin-top: 6px;
                    padding-top: 10px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                    background: {palette.surface};
                }}
                QPushButton {{
                    background: {palette.primary};
                    color: {palette.on_primary};
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                    min-width: 100px;
                }}
                QPushButton:hover {{
                    background: {palette.primary_variant};
                }}
                QPushButton:disabled {{
                    background: {palette.surface_variant};
                    color: {palette.outline};
                }}
                QPushButton#cancel_btn {{
                    background: {palette.error};
                }}
                QComboBox {{
                    background: {palette.surface_variant};
                    color: {palette.on_surface_variant};
                    border: 1px solid {palette.outline};
                    border-radius: 4px;
                    padding: 6px;
                }}
                QCheckBox, QRadioButton {{
                    color: {palette.on_surface};
                    spacing: 8px;
                }}
                QSpinBox {{
                    background: {palette.surface_variant};
                    color: {palette.on_surface_variant};
                    border: 1px solid {palette.outline};
                    border-radius: 4px;
                    padding: 4px;
                }}
                QProgressBar {{
                    background: {palette.surface_variant};
                    border: 1px solid {palette.outline};
                    border-radius: 4px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: {palette.primary};
                    border-radius: 4px;
                }}
            """)
        except:
            pass  # Ignorer les erreurs de style