#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from core.interfaces.controllers.tecmp.tecmp_ui_controller import TECMPUIController
from core.factories.tecmp_factory import TECMPPacketFactory
from core.builders.tecmp_builder import TECMPPacketBuilder
from core.packets.tecmp.tecmp_packet import TECMPPacket, create_logging_packet
from core.packets.tecmp.constants import *
from core.packets.tecmp.tecmp_data import TECMPDataBuilder
from core.packets.tecmp.tecmp_engine import TECMPEngine, create_professional_engine
from core.packets.tecmp.coherence_engine import TECMPCoherenceEngine
from core.packets.tecmp.packet_injector import inject_all_features, inject_coherence

class BackendManager(QObject):
    packet_created = pyqtSignal(object)
    validation_complete = pyqtSignal(bool, dict)
    status_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = None
        self.engine = None
        self.data_builder = TECMPDataBuilder()
        self.coherence_engine = TECMPCoherenceEngine(auto_fix_enabled=True)
        self.packet_history = []
        self.metrics = {'packets_created': 0, 'validations': 0, 'auto_fixes': 0}
        
    def initialize_controller(self, device_id: int = 0x40):
        self.controller = TECMPUIController(self.parent())
        self.engine = create_professional_engine(device_id)
        
    def create_packet(self, config: Dict[str, Any]) -> Optional[TECMPPacket]:
        try:
            data_type = config.get('data_type', DataType.ETHERNET_EXT)
            
            # Utiliser le data builder pour construire le payload si nécessaire
            if 'payload' not in config:
                handler = self.data_builder.get_handler(data_type)
                if handler:
                    # Extraire les paramètres spécifiques au protocole
                    protocol_params = {k: v for k, v in config.items() 
                                     if k not in ['device_id', 'message_type', 'data_type', 
                                                  'interface_id', 'counter']}
                    payload, data_flags = self.data_builder.build_payload(data_type, **protocol_params)
                    config['payload'] = payload
                    config['data_flags'] = data_flags
            
            # Créer le packet
            packet = TECMPPacket(
                device_id=config.get('device_id', 0x40),
                counter=config.get('counter', 0),
                message_type=config.get('message_type', MessageType.LOGGING_STREAM),
                data_type=data_type,
                interface_id=config.get('interface_id', 0),
                payload=config.get('payload', b''),
                data_flags=config.get('data_flags', 0)
            )
            
            # Injecter les fonctionnalités avancées
            inject_all_features(packet)
            
            # Appliquer le timestamp synchronisé si disponible
            if self.engine:
                timestamp = self.engine.time_sync.get_synchronized_time()
                sync_flags = self.engine.time_sync.get_synchronization_flags()
                packet.set_timestamp_with_flags(timestamp | sync_flags)
            
            self.metrics['packets_created'] += 1
            self.packet_history.append(packet)
            self.packet_created.emit(packet)
            
            return packet
            
        except Exception as e:
            self.error_occurred.emit("PACKET_CREATION_ERROR", str(e))
            return None
    
    def validate_packet(self, packet: TECMPPacket) -> Tuple[bool, Dict[str, Any]]:
        report = self.coherence_engine.validate_complete_coherence(packet)
        self.metrics['validations'] += 1
        
        if report.auto_fixes_applied:
            self.metrics['auto_fixes'] += len(report.auto_fixes_applied)
        
        return report.is_coherent, report.__dict__

class TransportEthernetWidget(QWidget):
    configuration_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.dst_mac_edit = QLineEdit("01:00:5e:00:00:00")
        self.dst_mac_edit.textChanged.connect(self._on_change)
        layout.addRow("Destination MAC:", self.dst_mac_edit)
        
        self.src_mac_edit = QLineEdit("Auto-detected")
        self.src_mac_edit.setEnabled(False)
        layout.addRow("Source MAC:", self.src_mac_edit)
        
        self.vlan_externe = QLineEdit()
        self.vlan_externe.setPlaceholderText("Optional")
        self.vlan_externe.textChanged.connect(self._on_change)
        layout.addRow("VLAN Externe:", self.vlan_externe)
        
        self.vlan_interne = QLineEdit()
        self.vlan_interne.setPlaceholderText("Q-in-Q Optional")
        self.vlan_interne.textChanged.connect(self._on_change)
        layout.addRow("VLAN Interne:", self.vlan_interne)
        
        self.ethertype_label = QLabel(f"0x{TECMP_ETHERTYPE:04X}")
        self.ethertype_label.setStyleSheet("font-weight: bold; background: #E3F2FD; padding: 5px;")
        layout.addRow("EtherType:", self.ethertype_label)
        
    def _on_change(self):
        self.configuration_changed.emit(self.get_configuration())
        
    def get_configuration(self) -> Dict[str, Any]:
        config = {
            'dst_mac': self.dst_mac_edit.text(),
            'src_mac': self.src_mac_edit.text(),
            'ethertype': TECMP_ETHERTYPE
        }
        
        if self.vlan_externe.text():
            config['vlan_externe'] = int(self.vlan_externe.text())
        if self.vlan_interne.text():
            config['vlan_interne'] = int(self.vlan_interne.text())
            
        return config

class ProtocolWidget(QWidget):
    configuration_changed = pyqtSignal(dict)
    validation_changed = pyqtSignal(bool, dict)
    
    def __init__(self, backend: BackendManager, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.current_protocol = None
        self.field_widgets = {}
        self.validation_indicators = {}
        self.setup_ui()
        
    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.main_layout.addWidget(self.scroll_area)
        
    def adapt_to_protocol(self, data_type: int):
        if self.current_protocol == data_type:
            return
            
        self.current_protocol = data_type
        self._clear_widgets()
        
        if data_type == DataType.CAN:
            self._create_can_widgets(False)
        elif data_type == DataType.CAN_FD:
            self._create_can_widgets(True)
        elif data_type == DataType.LIN:
            self._create_lin_widgets()
        elif data_type == DataType.FLEXRAY:
            self._create_flexray_widgets()
        elif data_type in [DataType.ETHERNET, DataType.ETHERNET_EXT]:
            self._create_ethernet_widgets()
            
    def _create_can_widgets(self, is_fd: bool):
        id_group = QGroupBox(f"CAN{'-FD' if is_fd else ''} Configuration")
        id_layout = QFormLayout(id_group)
        
        self.can_id_edit = QLineEdit("0x123")
        self.can_id_edit.textChanged.connect(self._on_change)
        id_layout.addRow("CAN ID:", self.can_id_edit)
        self.field_widgets['can_id'] = self.can_id_edit
        
        self.ide_check = QCheckBox("Extended ID (29 bits)")
        self.ide_check.toggled.connect(self._on_change)
        id_layout.addRow(self.ide_check)
        self.field_widgets['ide'] = self.ide_check
        
        self.id_indicator = QLabel("?")
        id_layout.addRow("Validation:", self.id_indicator)
        self.validation_indicators['can_id'] = self.id_indicator
        
        self.scroll_layout.addWidget(id_group)
        
        flags_group = QGroupBox("Data Flags")
        flags_grid = QGridLayout(flags_group)
        
        transmission_group = QGroupBox("Transmission")
        trans_layout = QVBoxLayout(transmission_group)
        
        self.ack_check = QCheckBox("ACK")
        self.ack_check.setChecked(True)
        self.ack_check.toggled.connect(self._on_change)
        trans_layout.addWidget(self.ack_check)
        self.field_widgets['ack'] = self.ack_check
        
        if not is_fd:
            self.rtr_check = QCheckBox("RTR")
            self.rtr_check.toggled.connect(self._on_change)
            trans_layout.addWidget(self.rtr_check)
            self.field_widgets['rtr'] = self.rtr_check
        
        self.tx_check = QCheckBox("TX")
        self.tx_check.toggled.connect(self._on_change)
        trans_layout.addWidget(self.tx_check)
        self.field_widgets['tx'] = self.tx_check
        
        if is_fd:
            self.brs_check = QCheckBox("BRS")
            self.brs_check.setChecked(True)
            self.brs_check.toggled.connect(self._on_change)
            trans_layout.addWidget(self.brs_check)
            self.field_widgets['brs'] = self.brs_check
            
            self.esi_check = QCheckBox("ESI")
            self.esi_check.toggled.connect(self._on_change)
            trans_layout.addWidget(self.esi_check)
            self.field_widgets['esi'] = self.esi_check
        
        flags_grid.addWidget(transmission_group, 0, 0)
        
        error_group = QGroupBox("Erreurs")
        error_layout = QVBoxLayout(error_group)
        
        error_flags = ['err', 'bit_stuff_error', 'crc_del_error', 'ack_del_error', 
                      'eof_error', 'crc_error', 'overflow']
        
        for flag in error_flags:
            check = QCheckBox(flag.replace('_', ' ').title())
            check.toggled.connect(self._on_change)
            error_layout.addWidget(check)
            self.field_widgets[flag] = check
        
        flags_grid.addWidget(error_group, 0, 1)
        self.scroll_layout.addWidget(flags_group)
        
        data_group = QGroupBox("Data")
        data_layout = QFormLayout(data_group)
        
        self.can_data_edit = QLineEdit("01 02 03 04")
        self.can_data_edit.textChanged.connect(self._on_change)
        data_layout.addRow("Data (hex):", self.can_data_edit)
        self.field_widgets['data'] = self.can_data_edit
        
        self.dlc_label = QLabel("DLC: 4")
        data_layout.addRow(self.dlc_label)
        
        self.scroll_layout.addWidget(data_group)
        
    def _create_ethernet_widgets(self):
        mac_group = QGroupBox("Ethernet Addresses")
        mac_layout = QFormLayout(mac_group)
        
        self.dst_mac_edit = QLineEdit("FF:FF:FF:FF:FF:FF")
        self.dst_mac_edit.textChanged.connect(self._on_change)
        mac_layout.addRow("Destination MAC:", self.dst_mac_edit)
        self.field_widgets['dst_mac'] = self.dst_mac_edit
        
        self.src_mac_edit = QLineEdit("00:11:22:33:44:55")
        self.src_mac_edit.textChanged.connect(self._on_change)
        mac_layout.addRow("Source MAC:", self.src_mac_edit)
        self.field_widgets['src_mac'] = self.src_mac_edit
        
        self.scroll_layout.addWidget(mac_group)
        
        proto_group = QGroupBox("Protocol")
        proto_layout = QFormLayout(proto_group)
        
        self.ether_type_combo = QComboBox()
        self.ether_type_combo.setEditable(True)
        self.ether_type_combo.addItems(["0x0800 - IPv4", "0x86DD - IPv6", "0x8100 - VLAN"])
        self.ether_type_combo.currentTextChanged.connect(self._on_change)
        proto_layout.addRow("EtherType:", self.ether_type_combo)
        self.field_widgets['ether_type'] = self.ether_type_combo
        
        self.scroll_layout.addWidget(proto_group)
        
        data_group = QGroupBox("Payload")
        data_layout = QFormLayout(data_group)
        
        self.eth_data_edit = QTextEdit()
        self.eth_data_edit.setMaximumHeight(100)
        self.eth_data_edit.setPlainText("TECMP Payload")
        self.eth_data_edit.textChanged.connect(self._on_change)
        data_layout.addRow("Data:", self.eth_data_edit)
        self.field_widgets['data'] = self.eth_data_edit
        
        self.size_label = QLabel("Size: 0 bytes")
        data_layout.addRow(self.size_label)
        
        self.scroll_layout.addWidget(data_group)
        
        flags_group = QGroupBox("Flags")
        flags_layout = QHBoxLayout(flags_group)
        
        self.crc_error_check = QCheckBox("CRC Error")
        self.crc_error_check.toggled.connect(self._on_change)
        flags_layout.addWidget(self.crc_error_check)
        self.field_widgets['crc_error'] = self.crc_error_check
        
        self.tx_check_eth = QCheckBox("TX")
        self.tx_check_eth.toggled.connect(self._on_change)
        flags_layout.addWidget(self.tx_check_eth)
        self.field_widgets['tx'] = self.tx_check_eth
        
        self.overflow_check = QCheckBox("Overflow")
        self.overflow_check.toggled.connect(self._on_change)
        flags_layout.addWidget(self.overflow_check)
        self.field_widgets['overflow'] = self.overflow_check
        
        self.scroll_layout.addWidget(flags_group)
        
    def _create_lin_widgets(self):
        id_group = QGroupBox("LIN Configuration")
        layout = QFormLayout(id_group)
        
        self.lin_id_spin = QSpinBox()
        self.lin_id_spin.setRange(0, 0x3F)
        self.lin_id_spin.setValue(0x20)
        self.lin_id_spin.setDisplayIntegerBase(16)
        self.lin_id_spin.valueChanged.connect(self._on_change)
        layout.addRow("LIN ID:", self.lin_id_spin)
        self.field_widgets['lin_id'] = self.lin_id_spin
        
        self.lin_data_edit = QLineEdit("AA BB CC DD")
        self.lin_data_edit.textChanged.connect(self._on_change)
        layout.addRow("Data (hex):", self.lin_data_edit)
        self.field_widgets['data'] = self.lin_data_edit
        
        self.scroll_layout.addWidget(id_group)
        
        flags_group = QGroupBox("LIN Flags")
        flags_layout = QHBoxLayout(flags_group)
        
        lin_flags = ['collision_error', 'parity_error', 'no_slave_response', 
                     'wup', 'short_wup', 'sleep', 'checksum_error', 'tx', 'overflow']
        
        for flag in lin_flags:
            check = QCheckBox(flag.replace('_', ' ').title())
            check.toggled.connect(self._on_change)
            flags_layout.addWidget(check)
            self.field_widgets[flag] = check
        
        self.scroll_layout.addWidget(flags_group)
        
    def _create_flexray_widgets(self):
        timing_group = QGroupBox("FlexRay Timing")
        layout = QFormLayout(timing_group)
        
        self.cycle_spin = QSpinBox()
        self.cycle_spin.setRange(0, 63)
        self.cycle_spin.valueChanged.connect(self._on_change)
        layout.addRow("Cycle:", self.cycle_spin)
        self.field_widgets['cycle'] = self.cycle_spin
        
        self.frame_id_spin = QSpinBox()
        self.frame_id_spin.setRange(0, 2047)
        self.frame_id_spin.valueChanged.connect(self._on_change)
        layout.addRow("Frame ID:", self.frame_id_spin)
        self.field_widgets['frame_id'] = self.frame_id_spin
        
        self.fr_data_edit = QLineEdit("11 22 33 44")
        self.fr_data_edit.textChanged.connect(self._on_change)
        layout.addRow("Data (hex):", self.fr_data_edit)
        self.field_widgets['data'] = self.fr_data_edit
        
        self.scroll_layout.addWidget(timing_group)
        
    def _clear_widgets(self):
        for widget in self.field_widgets.values():
            widget.setParent(None)
        self.field_widgets.clear()
        self.validation_indicators.clear()
        
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
    def _on_change(self):
        config = self.get_configuration()
        self._validate_configuration(config)
        self.configuration_changed.emit(config)
        
    def _validate_configuration(self, config: Dict[str, Any]):
        config['data_type'] = self.current_protocol
        
        # Validation spécifique au protocole
        validation_errors = []
        
        # CAN: Vérifier RTR + data
        if self.current_protocol == DataType.CAN:
            if config.get('rtr', False) and len(config.get('data', b'')) > 0:
                validation_errors.append("RTR frame cannot have data")
        
        # CAN-FD: Vérifier DLC valide
        elif self.current_protocol == DataType.CAN_FD:
            data_len = len(config.get('data', b''))
            if data_len > 8 and data_len not in CANFD_DLC_TO_LENGTH.values():
                validation_errors.append(f"CAN-FD invalid DLC for {data_len} bytes")
        
        # LIN: Vérifier longueur
        elif self.current_protocol == DataType.LIN:
            data_len = len(config.get('data', b''))
            if data_len not in LIN_VALID_LENGTHS and data_len != 0:
                validation_errors.append(f"LIN data must be 0,1,2,4 or 8 bytes")
        
        # Ethernet: Vérifier replay interdit
        elif self.current_protocol in [DataType.ETHERNET, DataType.ETHERNET_EXT]:
            if self.parent().message_combo.currentData() == MessageType.REPLAY_DATA:
                validation_errors.append("Ethernet replay not supported by TECMP v1.7")
        
        # Afficher les erreurs locales
        if validation_errors:
            for indicator in self.validation_indicators.values():
                indicator.setText("??")
                indicator.setStyleSheet("color: orange; font-weight: bold;")
                indicator.setToolTip("\n".join(validation_errors))
        
        # Validation complète via backend
        packet = self.backend.create_packet(config)
        
        if packet:
            is_valid, report = self.backend.validate_packet(packet)
            
            # Mise à jour des indicateurs spécifiques
            for field, indicator in self.validation_indicators.items():
                violations = [v for v in report.get('violations', []) if v['field'] == field]
                if violations:
                    indicator.setText("?")
                    indicator.setStyleSheet("color: red; font-weight: bold;")
                    indicator.setToolTip(violations[0]['message'])
                elif not validation_errors:  # Pas d'erreur locale
                    indicator.setText("?")
                    indicator.setStyleSheet("color: green; font-weight: bold;")
                    indicator.setToolTip("Valid")
            
            # Mise à jour des labels dynamiques
            if hasattr(self, 'dlc_label'):
                data_len = len(config.get('data', b''))
                self.dlc_label.setText(f"DLC: {data_len}")
                
                if self.current_protocol == DataType.CAN and data_len > 8:
                    self.dlc_label.setStyleSheet("color: red;")
                    self.dlc_label.setToolTip("Classic CAN max 8 bytes")
                elif self.current_protocol == DataType.CAN_FD and data_len not in CANFD_DLC_TO_LENGTH.values():
                    self.dlc_label.setStyleSheet("color: orange;")
                    self.dlc_label.setToolTip(f"CAN-FD DLC will be adjusted")
                else:
                    self.dlc_label.setStyleSheet("color: green;")
                    self.dlc_label.setToolTip("")
                    
            if hasattr(self, 'size_label'):
                data = config.get('data', b'')
                self.size_label.setText(f"Size: {len(data)} bytes")
                
                if self.current_protocol in [DataType.ETHERNET, DataType.ETHERNET_EXT]:
                    if len(data) < 46:
                        self.size_label.setStyleSheet("color: orange;")
                        self.size_label.setToolTip("Ethernet frame will be padded to 64 bytes minimum")
                    elif len(data) > 1500:
                        self.size_label.setStyleSheet("color: red;")
                        self.size_label.setToolTip("Exceeds Ethernet MTU (1500 bytes)")
                    else:
                        self.size_label.setStyleSheet("color: green;")
                        self.size_label.setToolTip("")
                        
            self.validation_changed.emit(is_valid and not validation_errors, report)
            
    def get_configuration(self) -> Dict[str, Any]:
        config = {}
        
        for field, widget in self.field_widgets.items():
            if isinstance(widget, QLineEdit):
                text = widget.text().strip()
                
                if field in ['can_id', 'cycle', 'frame_id']:
                    try:
                        config[field] = int(text, 16) if text.startswith('0x') else int(text)
                    except ValueError:
                        config[field] = 0
                        
                elif field == 'data':
                    try:
                        config[field] = bytes.fromhex(text.replace(' ', ''))
                    except ValueError:
                        config[field] = b''
                        
                elif field in ['dst_mac', 'src_mac']:
                    try:
                        config[field] = bytes.fromhex(text.replace(':', '').replace('-', ''))
                    except ValueError:
                        config[field] = b'\x00' * 6
                        
                else:
                    config[field] = text
                    
            elif isinstance(widget, QSpinBox):
                config[field] = widget.value()
                
            elif isinstance(widget, QCheckBox):
                config[field] = widget.isChecked()
                
            elif isinstance(widget, QComboBox):
                text = widget.currentText()
                if field == 'ether_type':
                    try:
                        config[field] = int(text.split(' ')[0], 16)
                    except:
                        config[field] = 0x0800
                else:
                    config[field] = text
                    
            elif isinstance(widget, QTextEdit):
                text = widget.toPlainText()
                if field == 'data':
                    config[field] = text.encode('utf-8')
                else:
                    config[field] = text
                    
        return config

class TECMPInterface(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TECMP v1.7 Configuration Interface")
        self.setMinimumSize(1600, 900)
        
        self.backend = BackendManager(self)
        self.current_config = {}
        self.generated_packets = []
        
        self.setup_ui()
        self.connect_signals()
        self.initialize_backend()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        
        main_layout = QHBoxLayout()
        
        left_panel = self.create_basic_panel()
        main_layout.addWidget(left_panel, 1)
        
        self.protocol_widget = ProtocolWidget(self.backend)
        main_layout.addWidget(self.protocol_widget, 2)
        
        right_panel = self.create_actions_panel()
        main_layout.addWidget(right_panel, 1)
        
        layout.addLayout(main_layout)
        
        self.create_status_bar()
        
    def create_basic_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        transport_group = QGroupBox("Section A: Transport Ethernet")
        self.transport_widget = TransportEthernetWidget()
        transport_layout = QVBoxLayout(transport_group)
        transport_layout.addWidget(self.transport_widget)
        layout.addWidget(transport_group)
        
        header_group = QGroupBox("Section B: Header TECMP")
        header_layout = QFormLayout(header_group)
        
        self.device_combo = QComboBox()
        self.populate_device_combo()
        header_layout.addRow("Device ID:", self.device_combo)
        
        counter_widget = QWidget()
        counter_layout = QHBoxLayout(counter_widget)
        self.counter_spin = QSpinBox()
        self.counter_spin.setRange(0, 65535)
        counter_layout.addWidget(self.counter_spin)
        self.counter_auto = QCheckBox("Auto")
        self.counter_auto.setChecked(True)
        counter_layout.addWidget(self.counter_auto)
        header_layout.addRow("Counter:", counter_widget)
        
        self.version_label = QLabel(str(TECMP_VERSION))
        self.version_label.setStyleSheet("background: #E8F5E9; padding: 5px; font-weight: bold;")
        header_layout.addRow("Version:", self.version_label)
        
        self.message_combo = QComboBox()
        for msg_type in MessageType:
            self.message_combo.addItem(f"0x{msg_type:02X} - {msg_type.name}", msg_type)
        # Sélectionner LOGGING_STREAM par défaut
        index = self.message_combo.findData(MessageType.LOGGING_STREAM)
        if index >= 0:
            self.message_combo.setCurrentIndex(index)
        header_layout.addRow("Message Type:", self.message_combo)
        
        self.data_type_combo = QComboBox()
        header_layout.addRow("Data Type:", self.data_type_combo)
        
        layout.addWidget(header_group)
        
        device_flags_group = QGroupBox("Section C: Device Flags")
        flags_layout = QHBoxLayout(device_flags_group)
        
        self.eos_check = QCheckBox("EOS")
        self.eos_check.setEnabled(False)
        self.eos_check.setToolTip("End of Segment - Automatic based on size")
        flags_layout.addWidget(self.eos_check)
        
        self.sos_check = QCheckBox("SOS")
        self.sos_check.setEnabled(False)
        self.sos_check.setToolTip("Start of Segment - Automatic based on size")
        flags_layout.addWidget(self.sos_check)
        
        self.spy_check = QCheckBox("SPY")
        self.spy_check.setToolTip("Spy mode - Automatic for LOGGING_STREAM")
        flags_layout.addWidget(self.spy_check)
        
        self.multi_frame_check = QCheckBox("Multi-Frame")
        self.multi_frame_check.setEnabled(False)
        self.multi_frame_check.setToolTip("Automatic if payload > 800 bytes")
        flags_layout.addWidget(self.multi_frame_check)
        
        self.overflow_check = QCheckBox("Overflow")
        self.overflow_check.setEnabled(False)
        self.overflow_check.setToolTip("Automatically detected by hardware monitor")
        self.overflow_check.setStyleSheet("QCheckBox:checked { color: red; }")
        flags_layout.addWidget(self.overflow_check)
        
        layout.addWidget(device_flags_group)
        
        payload_header_group = QGroupBox("Section D: Payload Header")
        payload_layout = QFormLayout(payload_header_group)
        
        self.interface_combo = QComboBox()
        self.interface_combo.setEditable(True)
        payload_layout.addRow("Interface ID:", self.interface_combo)
        
        timestamp_widget = QWidget()
        timestamp_layout = QHBoxLayout(timestamp_widget)
        self.timestamp_label = QLabel("Auto-generated")
        timestamp_layout.addWidget(self.timestamp_label)
        self.sync_check = QCheckBox("Sync Lost")
        self.sync_check.setEnabled(False)
        timestamp_layout.addWidget(self.sync_check)
        self.recalc_check = QCheckBox("Recalc")
        self.recalc_check.setEnabled(False)
        timestamp_layout.addWidget(self.recalc_check)
        payload_layout.addRow("Timestamp:", timestamp_widget)
        
        self.length_label = QLabel("Auto-calculated")
        self.length_label.setStyleSheet("font-weight: bold;")
        payload_layout.addRow("Length:", self.length_label)
        
        layout.addWidget(payload_header_group)
        
        layout.addStretch()
        return panel
        
    def create_actions_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        validation_group = QGroupBox("Validation")
        validation_layout = QVBoxLayout(validation_group)
        
        self.validation_status = QLabel("? Waiting...")
        self.validation_status.setStyleSheet("padding: 10px; border: 2px solid #ddd; border-radius: 5px;")
        validation_layout.addWidget(self.validation_status)
        
        btn_validate = QPushButton("Validate Configuration")
        btn_validate.clicked.connect(self.validate_configuration)
        validation_layout.addWidget(btn_validate)
        
        layout.addWidget(validation_group)
        
        generation_group = QGroupBox("Generation")
        generation_layout = QVBoxLayout(generation_group)
        
        self.generate_btn = QPushButton("Generate Packet")
        self.generate_btn.clicked.connect(self.generate_packet)
        generation_layout.addWidget(self.generate_btn)
        
        layout.addWidget(generation_group)
        
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        
        self.packets_list = QListWidget()
        self.packets_list.setMaximumHeight(200)
        results_layout.addWidget(self.packets_list)
        
        self.hex_display = QTextEdit()
        self.hex_display.setMaximumHeight(100)
        self.hex_display.setReadOnly(True)
        self.hex_display.setFont(QFont("Consolas", 9))
        results_layout.addWidget(self.hex_display)
        
        layout.addWidget(results_group)
        
        layout.addStretch()
        return panel
        
    def create_status_bar(self):
        status_bar = self.statusBar()
        
        self.status_main = QLabel("Ready")
        status_bar.addWidget(self.status_main)
        
        self.status_packets = QLabel("Packets: 0")
        status_bar.addPermanentWidget(self.status_packets)
        
    def populate_device_combo(self):
        self.device_combo.clear()
        
        for range_name, range_values in DEVICE_ID_RANGES.items():
            if isinstance(range_values, range):
                for device_id in range_values:
                    name = get_device_type_name(device_id)
                    self.device_combo.addItem(f"0x{device_id:04X} - {name}", device_id)
            else:
                for device_id in range_values:
                    name = get_device_type_name(device_id)
                    self.device_combo.addItem(f"0x{device_id:04X} - {name}", device_id)
                    
    def connect_signals(self):
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        self.message_combo.currentIndexChanged.connect(self.on_message_type_changed)
        self.data_type_combo.currentIndexChanged.connect(self.on_data_type_changed)
        self.interface_combo.currentTextChanged.connect(self.on_config_changed)
        
        self.transport_widget.configuration_changed.connect(self.on_transport_changed)
        self.protocol_widget.configuration_changed.connect(self.on_protocol_changed)
        self.protocol_widget.validation_changed.connect(self.on_validation_changed)
        
        self.backend.packet_created.connect(self.on_packet_created)
        self.backend.error_occurred.connect(self.on_error)
        
        self.counter_auto.toggled.connect(lambda checked: self.counter_spin.setEnabled(not checked))
        
    def initialize_backend(self):
        device_id = self.device_combo.currentData() or 0x40
        self.backend.initialize_controller(device_id)
        
        # Déclencher les mises à jour initiales
        self.on_device_changed()
        
        # Présélectionner des valeurs cohérentes
        if 0x30 <= device_id <= 0x3F:  # LIN
            self.data_type_combo.setCurrentIndex(0)  # LIN
            self.message_combo.setCurrentIndex(0)  # LOGGING_STREAM par défaut
        elif 0x40 <= device_id <= 0x4F:  # CAN
            self.data_type_combo.setCurrentIndex(0)  # CAN
            self.message_combo.setCurrentIndex(0)  # LOGGING_STREAM par défaut
        elif device_id in [0x80, 0x91]:  # Ethernet
            self.data_type_combo.setCurrentIndex(0)  # Ethernet
            # Pour Ethernet, éviter REPLAY_DATA
            index = self.message_combo.findData(MessageType.LOGGING_STREAM)
            if index >= 0:
                self.message_combo.setCurrentIndex(index)
                
        self.on_message_type_changed()
        self.on_data_type_changed()
        
    def on_device_changed(self):
        device_id = self.device_combo.currentData()
        if not device_id:
            return
            
        self.data_type_combo.clear()
        
        if 0x30 <= device_id <= 0x3F:
            self.data_type_combo.addItem(f"0x{DataType.LIN:04X} - LIN", DataType.LIN)
        elif 0x40 <= device_id <= 0x4F:
            self.data_type_combo.addItem(f"0x{DataType.CAN:04X} - CAN", DataType.CAN)
            self.data_type_combo.addItem(f"0x{DataType.CAN_FD:04X} - CAN-FD", DataType.CAN_FD)
        elif 0x50 <= device_id <= 0x5F or 0x70 <= device_id <= 0x7F:
            self.data_type_combo.addItem(f"0x{DataType.FLEXRAY:04X} - FlexRay", DataType.FLEXRAY)
        elif device_id == 0x80 or device_id == 0x91:
            self.data_type_combo.addItem(f"0x{DataType.ETHERNET_EXT:04X} - Ethernet", DataType.ETHERNET_EXT)
        else:
            for dt in DataType:
                self.data_type_combo.addItem(f"0x{dt:04X} - {get_data_type_name(dt)}", dt)
                
        self.on_config_changed()
        
    def on_message_type_changed(self):
        msg_type = self.message_combo.currentData()
        
        special_interfaces = {
            MessageType.CONTROL: SPECIAL_INTERFACE_IDS['CONTROL'],
            MessageType.STATUS_DEVICE: SPECIAL_INTERFACE_IDS['STATUS_DEVICE'],
            MessageType.STATUS_BUS: SPECIAL_INTERFACE_IDS['STATUS_BUS'],
            MessageType.STATUS_CONFIG: SPECIAL_INTERFACE_IDS['STATUS_CONFIG']
        }
        
        if msg_type in special_interfaces:
            interface_id = special_interfaces[msg_type]
            self.interface_combo.clear()
            self.interface_combo.addItem(f"0x{interface_id:08X} - {get_interface_id_name(interface_id)}")
            self.interface_combo.setEnabled(False)
        else:
            self.interface_combo.setEnabled(True)
            self._update_interface_suggestions()
            
        if msg_type == MessageType.LOGGING_STREAM:
            self.spy_check.setChecked(True)
            
        self.on_config_changed()
        
    def on_data_type_changed(self):
        data_type = self.data_type_combo.currentData()
        if data_type:
            self.protocol_widget.adapt_to_protocol(data_type)
            self._update_interface_suggestions()
            self._filter_message_types(data_type)
            
        self.on_config_changed()
        
    def _filter_message_types(self, data_type: int):
        """Filtre les message types selon le data type selectionne"""
        current_msg_type = self.message_combo.currentData()
        self.message_combo.clear()
        
        # Règles de cohérence data_type -> message_type
        if data_type == DataType.LOG_MESSAGE:
            # Log messages pour Control/Status uniquement
            allowed_types = [MessageType.CONTROL, MessageType.STATUS_DEVICE, 
                           MessageType.STATUS_BUS, MessageType.STATUS_CONFIG]
        elif data_type in [DataType.ETHERNET, DataType.ETHERNET_EXT]:
            # Ethernet ne supporte pas REPLAY_DATA
            allowed_types = [MessageType.LOGGING_STREAM, MessageType.CONTROL,
                           MessageType.STATUS_DEVICE, MessageType.STATUS_BUS, 
                           MessageType.STATUS_CONFIG]
        else:
            # CAN/LIN/FlexRay supportent tout sauf status (sauf si log message)
            allowed_types = [MessageType.LOGGING_STREAM, MessageType.REPLAY_DATA]
        
        # Ajouter les types autorisés
        for msg_type in MessageType:
            if msg_type in allowed_types:
                self.message_combo.addItem(f"0x{msg_type:02X} - {msg_type.name}", msg_type)
        
        # Restaurer la sélection si toujours valide
        if current_msg_type in allowed_types:
            index = self.message_combo.findData(current_msg_type)
            if index >= 0:
                self.message_combo.setCurrentIndex(index)
        
    def _update_interface_suggestions(self):
        if not self.interface_combo.isEnabled():
            return
            
        data_type = self.data_type_combo.currentData()
        if not data_type:
            return
            
        self.interface_combo.clear()
        
        suggestions = {
            DataType.CAN: ["0x00001000 - CAN Channel 1", "0x00001100 - CAN Channel 2"],
            DataType.CAN_FD: ["0x00001200 - CAN-FD Channel 1", "0x00001300 - CAN-FD Channel 2"],
            DataType.LIN: ["0x00002000 - LIN Channel 1", "0x00002100 - LIN Channel 2"],
            DataType.FLEXRAY: ["0x00003000 - FlexRay A", "0x00003100 - FlexRay B"],
            DataType.ETHERNET_EXT: ["0x0070128a - Ethernet Capture", "0x00004000 - Ethernet 1"]
        }
        
        items = suggestions.get(data_type, ["0x00000000 - Default"])
        self.interface_combo.addItems(items)
        
    def on_config_changed(self):
        self.current_config = {
            'device_id': self.device_combo.currentData() or 0x40,
            'message_type': self.message_combo.currentData() or MessageType.LOGGING_STREAM,
            'data_type': self.data_type_combo.currentData() or DataType.ETHERNET_EXT,
            'interface_id': self.extract_interface_id()
        }
        
        if self.counter_auto.isChecked():
            self.current_config['counter'] = self.backend.metrics['packets_created'] % 65536
        else:
            self.current_config['counter'] = self.counter_spin.value()
            
    def extract_interface_id(self) -> int:
        text = self.interface_combo.currentText()
        try:
            return int(text.split(' ')[0], 16)
        except:
            return 0x00000000
            
    def on_transport_changed(self, config: Dict[str, Any]):
        pass
        
    def on_protocol_changed(self, config: Dict[str, Any]):
        self.current_config.update(config)
        
        # Calculer la taille totale du payload
        if 'payload' in config:
            size = len(config['payload'])
        elif 'data' in config:
            size = len(config.get('data', b''))
        else:
            size = 0
            
        self.length_label.setText(f"{size} bytes")
        
        # Gestion automatique de la segmentation
        if size <= MAX_UNSEGMENTED_SIZE:
            self.eos_check.setChecked(True)
            self.sos_check.setChecked(True)
            self.multi_frame_check.setChecked(False)
            self.length_label.setStyleSheet("color: green; font-weight: bold;")
            self.length_label.setToolTip("Single packet")
        else:
            # Calcul de la segmentation
            num_segments = (size + MAX_UNSEGMENTED_SIZE - 1) // MAX_UNSEGMENTED_SIZE
            self.eos_check.setChecked(False)
            self.sos_check.setChecked(False)
            self.multi_frame_check.setChecked(True)
            self.length_label.setStyleSheet("color: orange; font-weight: bold;")
            self.length_label.setToolTip(f"Segmentation required: {num_segments} segments")
            
            # Afficher info segmentation
            self.show_segmentation_info(size, num_segments)
            
    def show_segmentation_info(self, total_size: int, num_segments: int):
        """Affiche les informations de segmentation"""
        info = f"?? Automatic segmentation:\n"
        info += f"- Total size: {total_size} bytes\n"
        info += f"- Number of segments: {num_segments}\n"
        info += f"- Size per segment: {MAX_UNSEGMENTED_SIZE} bytes\n"
        info += f"- Last segment: {total_size % MAX_UNSEGMENTED_SIZE or MAX_UNSEGMENTED_SIZE} bytes"
        
        # Mettre à jour le status
        self.status_main.setText(f"Segmentation: {num_segments} segments")
        self.validation_status.setToolTip(info)
                
    def on_validation_changed(self, is_valid: bool, report: Dict[str, Any]):
        if is_valid:
            self.validation_status.setText("? Valid Configuration")
            self.validation_status.setStyleSheet("padding: 10px; border: 2px solid #4CAF50; border-radius: 5px; background-color: #E8F5E9;")
        else:
            violations = report.get('violations', [])
            critical = len([v for v in violations if v.get('severity') == 1])
            self.validation_status.setText(f"? {critical} Critical Violations")
            self.validation_status.setStyleSheet("padding: 10px; border: 2px solid #F44336; border-radius: 5px; background-color: #FFEBEE;")
            
    @pyqtSlot(object)
    def on_packet_created(self, packet: TECMPPacket):
        self.generated_packets.append(packet)
        
        protocol = get_data_type_name(packet.data_type)
        device = get_device_type_name(packet.device_id)
        size = packet.size
        
        item_text = f"#{len(self.generated_packets)} - {protocol} from {device} ({size} bytes)"
        self.packets_list.addItem(item_text)
        
        packet_bytes = packet.serialize()
        hex_str = ' '.join([f'{b:02X}' for b in packet_bytes])
        self.hex_display.setPlainText(hex_str)
        
        self.status_packets.setText(f"Packets: {len(self.generated_packets)}")
        
        if hasattr(packet, 'timestamp_sync_status'):
            self.sync_check.setChecked(packet.timestamp_sync_status != 0)
        if hasattr(packet, 'timestamp_recalc_flag'):
            self.recalc_check.setChecked(packet.timestamp_recalc_flag)
            
        self.timestamp_label.setText(f"{packet.timestamp/1e9:.6f}s")
        
    @pyqtSlot(str, str)
    def on_error(self, error_type: str, message: str):
        QMessageBox.warning(self, f"Error: {error_type}", message)
        
    def validate_configuration(self):
        config = self.current_config.copy()
        config.update(self.protocol_widget.get_configuration())
        
        packet = self.backend.create_packet(config)
        
        if packet:
            is_valid, report = self.backend.validate_packet(packet)
            
            if is_valid:
                QMessageBox.information(self, "Validation", "Configuration valid!")
            else:
                violations = report.get('violations', [])
                msg = f"Configuration has {len(violations)} violations:\n\n"
                for v in violations[:5]:
                    msg += f"- {v['field']}: {v['message']}\n"
                if len(violations) > 5:
                    msg += f"\n... and {len(violations) - 5} more"
                    
                QMessageBox.warning(self, "Validation Failed", msg)
                
    def generate_packet(self):
        config = self.current_config.copy()
        config.update(self.protocol_widget.get_configuration())
        
        if self.spy_check.isChecked():
            config['spy_mode'] = True
            
        packet = self.backend.create_packet(config)
        
        if packet:
            packet.ensure_coherence()
            
            # Vérifier si segmentation nécessaire
            if packet.needs_segmentation():
                segments = packet.segment()
                
                # Afficher info segmentation
                msg = f"?? Packet segmented into {len(segments)} parts:\n"
                for i, seg in enumerate(segments):
                    msg += f"  - Segment {i+1}: {len(seg.payload)} bytes"
                    if i == 0:
                        msg += " (SOS)"
                    elif i == len(segments) - 1:
                        msg += " (EOS)"
                    msg += "\n"
                
                QMessageBox.information(self, "Automatic Segmentation", msg)
                
                # Ajouter tous les segments à la liste
                for i, seg in enumerate(segments):
                    self.generated_packets.append(seg)
                    item_text = f"#{len(self.generated_packets)} - Segment {i+1}/{len(segments)} - {seg.size} bytes"
                    self.packets_list.addItem(item_text)
                
                # Afficher le premier segment dans hex
                self.hex_display.setPlainText(segments[0].serialize().hex())
                
            else:
                # Packet unique
                self.status_main.setText(f"Packet generated: {get_data_type_name(packet.data_type)}")
            
            if self.counter_auto.isChecked():
                self.counter_spin.setValue((self.counter_spin.value() + 1) % 65536)

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    app.setStyleSheet("""
        QMainWindow { background-color: #F5F5F5; }
        QGroupBox { font-weight: bold; border: 2px solid #CCCCCC; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; }
        QPushButton { background-color: #2196F3; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }
        QPushButton:hover { background-color: #1976D2; }
        QPushButton:pressed { background-color: #0D47A1; }
    """)
    
    window = TECMPInterface()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()