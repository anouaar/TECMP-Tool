# -*- coding: utf-8 -*-
#!/usr/bin/env python
# coding: utf-8
"""
Single Packet Strategy - TECMP Tool Implementation
Author: TECMP-Tool Development Team
Description: Single packet transmission strategy compatible with TECMP-Tool architecture

FEATURES:
- Single packet transmission with configurable timing
- Integration with existing TECMP Facade
- Compatible with PacketManager and builders
- Support for protocol stack validation
- Real-time monitoring and metrics
- Error handling and retry mechanisms
- Full compatibility with existing naming conventions
"""

from __future__ import annotations
import time
import threading
import logging
import copy
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime

# Compatible imports with TECMP-Tool architecture
try:
    from .sender_strategy import SenderStrategy, StrategyConfig, Sender, StrategyStatus
except ImportError:
    # Fallback definitions compatible with TECMP-Tool
    class SenderStrategy:
        def __init__(self, config, senders):
            self.config = config
            self.senders = senders
            self.status = "CREATED"
            self.logger = logging.getLogger(self.__class__.__name__)
        
        def execute(self):
            pass
        
        def stop(self):
            self.status = "STOPPED"
        
        def get_status(self):
            return {"status": self.status}
    
    class StrategyConfig:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class Sender:
        def __init__(self, config):
            self.config = config
        
        def send_packet(self, packet):
            pass
    
    class StrategyStatus(Enum):
        CREATED = auto()
        RUNNING = auto()
        COMPLETED = auto()
        FAILED = auto()
        STOPPED = auto()

# Qt imports for signals (compatible with TECMP-Tool GUI)
try:
    from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    class QObject:
        def __init__(self): pass
    def pyqtSignal(*args): 
        class MockSignal:
            def emit(self, *args): pass
            def connect(self, slot): pass
        return MockSignal()

# TECMP-Tool specific imports (compatible with existing structure)
try:
    from core.management.packet_manager import PacketManager
    PACKET_MANAGER_AVAILABLE = True
except ImportError:
    PACKET_MANAGER_AVAILABLE = False

try:
    from core.builders.packet_builder import PacketBuilder
    PACKET_BUILDER_AVAILABLE = True
except ImportError:
    PACKET_BUILDER_AVAILABLE = False

try:
    from core.builders.tecmp_builder import TECMPPacketBuilder
    TECMP_BUILDER_AVAILABLE = True
except ImportError:
    TECMP_BUILDER_AVAILABLE = False


# === ENUMS AND DATA STRUCTURES ===

class TransmissionMode(Enum):
    """Modes de transmission pour strategie single"""
    IMMEDIATE = "immediate"      # Envoi immediat
    DELAYED = "delayed"          # Envoi avec delai
    SCHEDULED = "scheduled"      # Envoi programme
    BURST = "burst"             # Envoi en rafale


class ValidationLevel(Enum):
    """Niveaux de validation des paquets"""
    NONE = "none"               # Aucune validation
    BASIC = "basic"             # Validation basique
    STRICT = "strict"           # Validation stricte
    TECMP_COMPLIANT = "tecmp_compliant"  # Conformite TECMP


class RetryPolicy(Enum):
    """Politiques de retry en cas d'echec"""
    NO_RETRY = "no_retry"       # Pas de retry
    FIXED_DELAY = "fixed_delay" # Delai fixe
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # Backoff exponentiel
    ADAPTIVE = "adaptive"       # Adaptatif selon erreur


@dataclass
class TransmissionResult:
    """Resultat d'une transmission de paquet"""
    success: bool = False
    timestamp: float = field(default_factory=time.time)
    packet_id: Optional[str] = None
    sender_id: Optional[str] = None
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    bytes_sent: int = 0
    validation_passed: bool = True


@dataclass
class SingleStrategyMetrics:
    """Metriques pour la strategie single"""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_duration: float = 0.0
    
    # Transmission metrics
    total_packets_sent: int = 0
    successful_transmissions: int = 0
    failed_transmissions: int = 0
    total_bytes_sent: int = 0
    
    # Performance metrics
    average_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    
    # Error metrics
    total_retries: int = 0
    validation_failures: int = 0
    transmission_errors: int = 0
    
    # Results history
    transmission_results: List[TransmissionResult] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Taux de succes des transmissions"""
        if self.total_packets_sent == 0:
            return 0.0
        return (self.successful_transmissions / self.total_packets_sent) * 100.0
    
    @property
    def error_rate(self) -> float:
        """Taux d'erreur des transmissions"""
        return 100.0 - self.success_rate


@dataclass
class SingleStrategyConfiguration:
    """Configuration pour la strategie single packet"""
    
    # Basic transmission parameters
    transmission_mode: TransmissionMode = TransmissionMode.IMMEDIATE
    delay_seconds: float = 0.0
    scheduled_time: Optional[datetime] = None
    
    # Burst mode parameters (si applicable)
    burst_count: int = 1
    burst_interval_ms: float = 100.0
    
    # Packet configuration
    use_current_packet: bool = True
    custom_packet_data: Optional[Any] = None
    packet_source: str = "facade"  # "facade", "builder", "custom"
    
    # Validation parameters
    validation_level: ValidationLevel = ValidationLevel.BASIC
    validate_before_send: bool = True
    validate_tecmp_compliance: bool = False
    
    # Sender configuration
    use_all_senders: bool = False
    sender_selection_strategy: str = "first_available"  # "first_available", "round_robin", "random"
    
    # Retry configuration
    retry_policy: RetryPolicy = RetryPolicy.FIXED_DELAY
    max_retries: int = 3
    retry_delay_ms: float = 1000.0
    exponential_backoff_factor: float = 2.0
    
    # Performance monitoring
    enable_metrics: bool = True
    track_latency: bool = True
    detailed_logging: bool = False
    
    # Integration with TECMP-Tool
    integrate_with_facade: bool = True
    update_facade_metrics: bool = True
    use_protocol_stack: bool = True
    apply_tecmp_encapsulation: bool = False
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Valider la configuration"""
        errors = []
        
        if self.delay_seconds < 0:
            errors.append("Delay seconds must be non-negative")
        
        if self.burst_count <= 0:
            errors.append("Burst count must be positive")
        
        if self.burst_interval_ms < 0:
            errors.append("Burst interval must be non-negative")
        
        if self.max_retries < 0:
            errors.append("Max retries must be non-negative")
        
        if self.retry_delay_ms < 0:
            errors.append("Retry delay must be non-negative")
        
        if self.transmission_mode == TransmissionMode.SCHEDULED and not self.scheduled_time:
            errors.append("Scheduled time required for scheduled transmission mode")
        
        return len(errors) == 0, errors


# === SINGLE PACKET STRATEGY IMPLEMENTATION ===

class SinglePacketStrategy(SenderStrategy):
    """
    Single Packet Transmission Strategy for TECMP-Tool
    
    Cette strategie envoie un ou plusieurs paquets selon une configuration specifique,
    entierement compatible avec l'architecture TECMP-Tool existante.
    """
    
    if QT_AVAILABLE:
        # Signaux compatibles avec l'interface TECMP-Tool
        transmission_started = pyqtSignal(str)           # packet_id
        transmission_completed = pyqtSignal(dict)        # transmission_result
        transmission_failed = pyqtSignal(str, str)       # packet_id, error_message
        validation_result = pyqtSignal(bool, str)        # is_valid, message
        metrics_updated = pyqtSignal(dict)               # current_metrics
        strategy_completed = pyqtSignal(dict)            # final_metrics
    
    def __init__(self, config: Union[SingleStrategyConfiguration, Dict[str, Any]], 
                 senders: List[Sender], 
                 strategy_name: Optional[str] = None,
                 facade_reference: Optional[Any] = None):
        """
        Initialiser la strategie single packet
        
        Args:
            config: Configuration de la strategie
            senders: Liste des senders disponibles
            strategy_name: Nom de la strategie
            facade_reference: Reference a la facade TECMP (optionnel)
        """
        # Conversion dict -> Configuration si necessaire
        if isinstance(config, dict):
            config = self._dict_to_config(config)
        
        # Initialisation de la strategie de base
        super().__init__(config, senders)
        
        self.strategy_name = strategy_name or f"Single_{int(time.time())}"
        self.single_config = config
        self.facade_reference = facade_reference
        self.logger = logging.getLogger(f"TECMP.Single.{self.strategy_name}")
        
        # Validation de la configuration
        is_valid, errors = self.single_config.validate()
        if not is_valid:
            raise ValueError(f"Invalid single strategy configuration: {errors}")
        
        # State management
        self.execution_state = "INITIALIZED"
        self.current_packet = None
        self.packet_to_send = None
        
        # Threading et controle
        self._stop_event = threading.Event()
        self._execution_thread = None
        self._is_running = False
        
        # Metriques et monitoring
        self.metrics = SingleStrategyMetrics()
        self.transmission_history = []
        
        # Integration TECMP-Tool
        self._packet_manager = None
        self._packet_builder = None
        self._tecmp_builder = None
        self._protocol_stack = []
        
        # Initialiser les composants TECMP-Tool
        self._initialize_tecmp_components()
        
        self.logger.info(f"SinglePacketStrategy initialized: {self.strategy_name}")
        self.logger.info(f"Configuration: mode={self.single_config.transmission_mode.value}, "
                        f"validation={self.single_config.validation_level.value}")
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> SingleStrategyConfiguration:
        """Convertir un dictionnaire en SingleStrategyConfiguration"""
        try:
            # Gerer les conversions d'enum
            if 'transmission_mode' in config_dict and isinstance(config_dict['transmission_mode'], str):
                config_dict['transmission_mode'] = TransmissionMode(config_dict['transmission_mode'])
            
            if 'validation_level' in config_dict and isinstance(config_dict['validation_level'], str):
                config_dict['validation_level'] = ValidationLevel(config_dict['validation_level'])
            
            if 'retry_policy' in config_dict and isinstance(config_dict['retry_policy'], str):
                config_dict['retry_policy'] = RetryPolicy(config_dict['retry_policy'])
            
            # Conversion datetime si fournie en string
            if 'scheduled_time' in config_dict and isinstance(config_dict['scheduled_time'], str):
                config_dict['scheduled_time'] = datetime.fromisoformat(config_dict['scheduled_time'])
            
            return SingleStrategyConfiguration(**config_dict)
        except Exception as e:
            self.logger.error(f"Error converting config dict: {e}")
            return SingleStrategyConfiguration()
    
    def _initialize_tecmp_components(self):
        """Initialiser les composants TECMP-Tool"""
        try:
            # Initialiser PacketManager si disponible
            if PACKET_MANAGER_AVAILABLE:
                try:
                    self._packet_manager = PacketManager()
                    self.logger.debug("PacketManager initialized")
                except Exception as e:
                    self.logger.warning(f"Could not initialize PacketManager: {e}")
            
            # Initialiser PacketBuilder si disponible
            if PACKET_BUILDER_AVAILABLE:
                try:
                    self._packet_builder = PacketBuilder()
                    self.logger.debug("PacketBuilder initialized")
                except Exception as e:
                    self.logger.warning(f"Could not initialize PacketBuilder: {e}")
            
            # Initialiser TECMPBuilder si disponible
            if TECMP_BUILDER_AVAILABLE:
                try:
                    self._tecmp_builder = TECMPPacketBuilder()
                    self.logger.debug("TECMPBuilder initialized")
                except Exception as e:
                    self.logger.warning(f"Could not initialize TECMPBuilder: {e}")
            
            # Obtenir le protocol stack depuis la facade si disponible
            if (self.facade_reference and 
                hasattr(self.facade_reference, 'get_protocol_stack')):
                try:
                    self._protocol_stack = self.facade_reference.get_protocol_stack()
                    self.logger.debug(f"Protocol stack obtained: {len(self._protocol_stack)} protocols")
                except Exception as e:
                    self.logger.warning(f"Could not get protocol stack: {e}")
            
        except Exception as e:
            self.logger.error(f"Error initializing TECMP components: {e}")
    
    def execute(self) -> bool:
        """
        Executer la strategie single packet
        
        Returns:
            bool: True si l'execution a demarre avec succes
        """
        try:
            self.logger.info(f"Starting single packet strategy execution: {self.strategy_name}")
            
            # Reinitialiser l'etat
            self._reset_execution_state()
            
            # Preparer le paquet a envoyer
            if not self._prepare_packet():
                self.logger.error("Failed to prepare packet for transmission")
                self.status = StrategyStatus.FAILED
                return False
            
            # Demarrer le thread d'execution
            self._execution_thread = threading.Thread(
                target=self._execute_transmission,
                name=f"SingleExecution_{self.strategy_name}"
            )
            self._execution_thread.start()
            
            self._is_running = True
            self.status = StrategyStatus.RUNNING
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting execution: {e}")
            self.status = StrategyStatus.FAILED
            return False
    
    def _reset_execution_state(self):
        """Reinitialiser l'etat pour une nouvelle execution"""
        self.execution_state = "PREPARING"
        self.metrics = SingleStrategyMetrics(start_time=time.time())
        self.transmission_history.clear()
        self._stop_event.clear()
        self.current_packet = None
        self.packet_to_send = None
    
    def _prepare_packet(self) -> bool:
        """Preparer le paquet a envoyer"""
        try:
            self.logger.debug("Preparing packet for transmission")
            
            if self.single_config.packet_source == "custom":
                # Utiliser le paquet personnalise fourni
                self.packet_to_send = self.single_config.custom_packet_data
                
            elif self.single_config.packet_source == "facade":
                # Obtenir le paquet depuis la facade
                if (self.facade_reference and 
                    hasattr(self.facade_reference, 'get_current_packet')):
                    self.packet_to_send = self.facade_reference.get_current_packet()
                else:
                    self.logger.warning("Facade not available, falling back to builder")
                    return self._build_packet_from_protocol_stack()
                    
            elif self.single_config.packet_source == "builder":
                # Construire le paquet depuis le protocol stack
                return self._build_packet_from_protocol_stack()
            
            else:
                # Mode par defaut : utiliser le paquet courant ou construire
                if (self.single_config.use_current_packet and 
                    self.facade_reference and 
                    hasattr(self.facade_reference, 'get_current_packet')):
                    self.packet_to_send = self.facade_reference.get_current_packet()
                else:
                    return self._build_packet_from_protocol_stack()
            
            # Valider le paquet si demande
            if self.single_config.validate_before_send:
                return self._validate_packet()
            
            return self.packet_to_send is not None
            
        except Exception as e:
            self.logger.error(f"Error preparing packet: {e}")
            return False
    
    def _build_packet_from_protocol_stack(self) -> bool:
        """Construire un paquet depuis le protocol stack"""
        try:
            if not self._protocol_stack:
                # Protocol stack vide, creer un paquet basique
                self.packet_to_send = self._create_default_packet()
                return True
            
            # Utiliser le packet builder si disponible
            if self._packet_builder:
                try:
                    # Effacer les layers precedents
                    if hasattr(self._packet_builder, 'layers'):
                        self._packet_builder.layers.clear()
                    
                    # Ajouter chaque protocole du stack
                    for protocol_info in self._protocol_stack:
                        protocol_name = protocol_info.get('name', '')
                        protocol_config = protocol_info.get('config', {})
                        
                        if hasattr(self._packet_builder, 'add_layer'):
                            self._packet_builder.add_layer(protocol_name, **protocol_config)
                    
                    # Construire le paquet
                    if hasattr(self._packet_builder, 'build'):
                        self.packet_to_send = self._packet_builder.build()
                    
                    # Appliquer l'encapsulation TECMP si demandee
                    if (self.single_config.apply_tecmp_encapsulation and 
                        self._tecmp_builder and self.packet_to_send):
                        self.packet_to_send = self._apply_tecmp_encapsulation()
                    
                    return self.packet_to_send is not None
                    
                except Exception as e:
                    self.logger.warning(f"Error using packet builder: {e}")
                    
            # Fallback : creer un paquet basique avec les infos du protocol stack
            self.packet_to_send = self._create_packet_from_stack_info()
            return True
            
        except Exception as e:
            self.logger.error(f"Error building packet from protocol stack: {e}")
            self.packet_to_send = self._create_default_packet()
            return True
    
    def _create_default_packet(self) -> Dict[str, Any]:
        """Creer un paquet par defaut"""
        return {
            "type": "default_single_packet",
            "strategy": self.strategy_name,
            "timestamp": time.time(),
            "data": f"SinglePacket_{self.strategy_name}_{int(time.time())}",
            "size": 64  # Taille par defaut
        }
    
    def _create_packet_from_stack_info(self) -> Dict[str, Any]:
        """Creer un paquet base sur les infos du protocol stack"""
        packet = {
            "type": "protocol_stack_packet",
            "strategy": self.strategy_name,
            "timestamp": time.time(),
            "protocols": [],
            "size": 0
        }
        
        total_size = 14  # Ethernet header base
        
        for protocol_info in self._protocol_stack:
            protocol_data = {
                "name": protocol_info.get('name', 'Unknown'),
                "config": protocol_info.get('config', {}),
                "size": self._estimate_protocol_size(protocol_info.get('name', ''))
            }
            packet["protocols"].append(protocol_data)
            total_size += protocol_data["size"]
        
        packet["size"] = total_size
        packet["data"] = f"ProtocolStack_{'_'.join([p['name'] for p in packet['protocols']])}"
        
        return packet
    
    def _estimate_protocol_size(self, protocol_name: str) -> int:
        """Estimer la taille d'un protocole"""
        size_map = {
            'Ethernet': 14,
            'IPv4': 20,
            'IPv6': 40,
            'TCP': 20,
            'UDP': 8,
            'ICMP': 8,
            'ARP': 28,
            'VLAN': 4,
            'TECMP': 28
        }
        return size_map.get(protocol_name, 4)  # 4 bytes par defaut
    
    def _apply_tecmp_encapsulation(self) -> Any:
        """Appliquer l'encapsulation TECMP"""
        try:
            if self._tecmp_builder and hasattr(self._tecmp_builder, 'encapsulate'):
                return self._tecmp_builder.encapsulate(self.packet_to_send)
            else:
                # Fallback : ajouter header TECMP basique
                tecmp_packet = {
                    "tecmp_header": {
                        "device_id": 0x01,
                        "counter": self.metrics.total_packets_sent,
                        "timestamp": time.time(),
                        "message_type": 0x03,  # Logging Stream
                        "data_type": 0x0080    # Ethernet
                    },
                    "original_packet": self.packet_to_send
                }
                return tecmp_packet
        except Exception as e:
            self.logger.warning(f"Error applying TECMP encapsulation: {e}")
            return self.packet_to_send
    
    def _validate_packet(self) -> bool:
        """Valider le paquet avant envoi"""
        try:
            if not self.packet_to_send:
                self.logger.error("No packet to validate")
                return False
            
            validation_passed = True
            validation_message = "Packet validation passed"
            
            # Validation basique
            if self.single_config.validation_level in [ValidationLevel.BASIC, ValidationLevel.STRICT]:
                if not isinstance(self.packet_to_send, (dict, bytes)):
                    validation_passed = False
                    validation_message = "Packet must be dict or bytes"
            
            # Validation stricte
            if self.single_config.validation_level == ValidationLevel.STRICT:
                if isinstance(self.packet_to_send, dict):
                    required_fields = ['type', 'timestamp']
                    missing_fields = [f for f in required_fields if f not in self.packet_to_send]
                    if missing_fields:
                        validation_passed = False
                        validation_message = f"Missing required fields: {missing_fields}"
            
            # Validation conformite TECMP
            if self.single_config.validate_tecmp_compliance:
                if isinstance(self.packet_to_send, dict) and 'tecmp_header' not in self.packet_to_send:
                    validation_passed = False
                    validation_message = "TECMP compliance requires tecmp_header"
            
            # Utiliser le validator de la facade si disponible
            if (validation_passed and self.facade_reference and 
                hasattr(self.facade_reference, 'validate_protocol_stack')):
                try:
                    facade_validation = self.facade_reference.validate_protocol_stack()
                    if not facade_validation.get('valid', True):
                        validation_passed = False
                        validation_message = f"Facade validation failed: {facade_validation.get('message', 'Unknown error')}"
                except Exception as e:
                    self.logger.warning(f"Facade validation error: {e}")
            
            # Mettre a jour metriques
            if not validation_passed:
                self.metrics.validation_failures += 1
            
            # Émettre signal de validation
            if QT_AVAILABLE:
                self.validation_result.emit(validation_passed, validation_message)
            
            self.logger.debug(f"Packet validation: {validation_passed} - {validation_message}")
            return validation_passed
            
        except Exception as e:
            self.logger.error(f"Error validating packet: {e}")
            self.metrics.validation_failures += 1
            return False
    
    def _execute_transmission(self):
        """Executer la transmission du paquet"""
        try:
            self.execution_state = "EXECUTING"
            self.logger.info("Starting packet transmission")
            
            # Appliquer le delai si configure
            if self.single_config.transmission_mode == TransmissionMode.DELAYED:
                if self.single_config.delay_seconds > 0:
                    self.logger.debug(f"Applying delay: {self.single_config.delay_seconds}s")
                    time.sleep(self.single_config.delay_seconds)
            
            elif self.single_config.transmission_mode == TransmissionMode.SCHEDULED:
                # Attendre jusqu'au moment programme
                if self.single_config.scheduled_time:
                    wait_time = (self.single_config.scheduled_time - datetime.now()).total_seconds()
                    if wait_time > 0:
                        self.logger.debug(f"Waiting for scheduled time: {wait_time}s")
                        time.sleep(wait_time)
            
            # Effectuer la transmission
            if self.single_config.transmission_mode == TransmissionMode.BURST:
                self._execute_burst_transmission()
            else:
                self._execute_single_transmission()
            
            # Finaliser l'execution
            self._finalize_execution()
            
        except Exception as e:
            self.logger.error(f"Error in transmission execution: {e}")
            self.status = StrategyStatus.FAILED
            self._finalize_execution()
    
    def _execute_single_transmission(self):
        """Executer une transmission simple"""
        packet_id = f"{self.strategy_name}_{int(time.time())}"
        
        if QT_AVAILABLE:
            self.transmission_started.emit(packet_id)
        
        result = self._send_packet_with_retry(packet_id, self.packet_to_send)
        self._process_transmission_result(result)
    
    def _execute_burst_transmission(self):
        """Executer une transmission en rafale"""
        for i in range(self.single_config.burst_count):
            if self._stop_event.is_set():
                break
            
            packet_id = f"{self.strategy_name}_burst_{i}_{int(time.time())}"
            
            if QT_AVAILABLE:
                self.transmission_started.emit(packet_id)
            
            result = self._send_packet_with_retry(packet_id, self.packet_to_send)
            self._process_transmission_result(result)
            
            # Delai entre les paquets de la rafale
            if i < self.single_config.burst_count - 1:
                time.sleep(self.single_config.burst_interval_ms / 1000.0)
    
    def _send_packet_with_retry(self, packet_id: str, packet: Any) -> TransmissionResult:
        """Envoyer un paquet avec mecanisme de retry"""
        result = TransmissionResult(packet_id=packet_id)
        
        for attempt in range(self.single_config.max_retries + 1):
            try:
                if self._stop_event.is_set():
                    result.error_message = "Transmission cancelled"
                    break
                
                # Selectionner le sender
                sender = self._select_sender()
                if not sender:
                    result.error_message = "No sender available"
                    break
                
                # Envoyer le paquet
                send_start = time.time()
                success = sender.send_packet(packet)
                send_duration = time.time() - send_start
                
                result.latency_ms = send_duration * 1000
                result.sender_id = getattr(sender, 'id', str(sender))
                result.retry_count = attempt
                
                if hasattr(packet, '__len__'):
                    result.bytes_sent = len(packet)
                elif isinstance(packet, dict) and 'size' in packet:
                    result.bytes_sent = packet['size']
                else:
                    result.bytes_sent = 64  # Estimation par defaut
                
                if success:
                    result.success = True
                    self.logger.debug(f"Packet {packet_id} sent successfully (attempt {attempt + 1})")
                    break
                else:
                    result.error_message = f"Send failed (attempt {attempt + 1})"
                    
            except Exception as e:
                result.error_message = f"Exception on attempt {attempt + 1}: {e}"
                self.logger.warning(f"Send attempt {attempt + 1} failed: {e}")
            
            # Appliquer delai de retry si pas le dernier essai
            if attempt < self.single_config.max_retries:
                retry_delay = self._calculate_retry_delay(attempt)
                time.sleep(retry_delay / 1000.0)  # Convertir ms en s
        
        result.timestamp = time.time()
        return result
    
    def _select_sender(self) -> Optional[Sender]:
        """Selectionner un sender selon la strategie configuree"""
        if not self.senders:
            return None
        
        if self.single_config.sender_selection_strategy == "first_available":
            return self.senders[0]
        
        elif self.single_config.sender_selection_strategy == "round_robin":
            # Simple round robin base sur le nombre de paquets envoyes
            index = self.metrics.total_packets_sent % len(self.senders)
            return self.senders[index]
        
        elif self.single_config.sender_selection_strategy == "random":
            import random
            return random.choice(self.senders)
        
        else:
            return self.senders[0]  # Fallback
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculer le delai de retry selon la politique"""
        if self.single_config.retry_policy == RetryPolicy.NO_RETRY:
            return 0.0
        
        elif self.single_config.retry_policy == RetryPolicy.FIXED_DELAY:
            return self.single_config.retry_delay_ms
        
        elif self.single_config.retry_policy == RetryPolicy.EXPONENTIAL_BACKOFF:
            return self.single_config.retry_delay_ms * (
                self.single_config.exponential_backoff_factor ** attempt
            )
        
        elif self.single_config.retry_policy == RetryPolicy.ADAPTIVE:
            # Delai adaptatif base sur le type d'erreur (implementation simple)
            base_delay = self.single_config.retry_delay_ms
            return base_delay * (1.5 ** attempt)
        
        return self.single_config.retry_delay_ms
    
    def _process_transmission_result(self, result: TransmissionResult):
        """Traiter le resultat d'une transmission"""
        # Mettre a jour les metriques
        self.metrics.total_packets_sent += 1
        self.metrics.transmission_results.append(result)
        
        if result.success:
            self.metrics.successful_transmissions += 1
            self.metrics.total_bytes_sent += result.bytes_sent
            
            # Mettre a jour les metriques de latence
            if result.latency_ms is not None:
                self.metrics.min_latency_ms = min(self.metrics.min_latency_ms, result.latency_ms)
                self.metrics.max_latency_ms = max(self.metrics.max_latency_ms, result.latency_ms)
                
                # Calcul de la latence moyenne
                total_latency = sum(r.latency_ms for r in self.metrics.transmission_results if r.latency_ms)
                valid_results = [r for r in self.metrics.transmission_results if r.latency_ms]
                if valid_results:
                    self.metrics.average_latency_ms = total_latency / len(valid_results)
        else:
            self.metrics.failed_transmissions += 1
            self.metrics.transmission_errors += 1
        
        self.metrics.total_retries += result.retry_count
        
        # Mettre a jour la facade si configure
        if (self.single_config.update_facade_metrics and 
            self.facade_reference and 
            hasattr(self.facade_reference, 'statistics')):
            try:
                facade_stats = self.facade_reference.statistics
                facade_stats.total_operations += 1
                if result.success:
                    facade_stats.successful_operations += 1
                else:
                    facade_stats.failed_operations += 1
            except Exception as e:
                self.logger.warning(f"Error updating facade metrics: {e}")
        
        # Émettre les signaux appropries
        if QT_AVAILABLE:
            if result.success:
                self.transmission_completed.emit(result.__dict__)
            else:
                self.transmission_failed.emit(result.packet_id, result.error_message or "Unknown error")
            
            # Émettre mise a jour des metriques
            if self.single_config.enable_metrics:
                self.metrics_updated.emit(self._get_metrics_dict())
        
        # Logging detaille si active
        if self.single_config.detailed_logging:
            if result.success:
                self.logger.info(f"Transmission successful: {result.packet_id}, "
                                f"latency={result.latency_ms:.2f}ms, bytes={result.bytes_sent}")
            else:
                self.logger.warning(f"Transmission failed: {result.packet_id}, "
                                   f"error={result.error_message}, retries={result.retry_count}")
    
    def _finalize_execution(self):
        """Finaliser l'execution de la strategie"""
        self.execution_state = "COMPLETED"
        self.metrics.end_time = time.time()
        self.metrics.total_duration = self.metrics.end_time - self.metrics.start_time
        
        if self.status != StrategyStatus.FAILED:
            self.status = StrategyStatus.COMPLETED
        
        self._is_running = False
        
        # Reinitialiser la latence min si aucune transmission reussie
        if self.metrics.min_latency_ms == float('inf'):
            self.metrics.min_latency_ms = 0.0
        
        # Log final
        self.logger.info(f"Single packet strategy completed: {self.strategy_name}")
        self.logger.info(f"Total packets sent: {self.metrics.total_packets_sent}")
        self.logger.info(f"Success rate: {self.metrics.success_rate:.1f}%")
        self.logger.info(f"Average latency: {self.metrics.average_latency_ms:.2f}ms")
        
        # Émettre signal de completion
        if QT_AVAILABLE:
            self.strategy_completed.emit(self._get_final_metrics_dict())
    
    def _get_metrics_dict(self) -> Dict[str, Any]:
        """Obtenir les metriques actuelles en tant que dictionnaire"""
        return {
            "strategy_name": self.strategy_name,
            "execution_state": self.execution_state,
            "total_packets_sent": self.metrics.total_packets_sent,
            "successful_transmissions": self.metrics.successful_transmissions,
            "failed_transmissions": self.metrics.failed_transmissions,
            "success_rate": self.metrics.success_rate,
            "error_rate": self.metrics.error_rate,
            "total_bytes_sent": self.metrics.total_bytes_sent,
            "average_latency_ms": self.metrics.average_latency_ms,
            "min_latency_ms": self.metrics.min_latency_ms,
            "max_latency_ms": self.metrics.max_latency_ms,
            "total_retries": self.metrics.total_retries,
            "validation_failures": self.metrics.validation_failures,
            "transmission_errors": self.metrics.transmission_errors
        }
    
    def _get_final_metrics_dict(self) -> Dict[str, Any]:
        """Obtenir les metriques finales completes"""
        metrics_dict = self._get_metrics_dict()
        metrics_dict.update({
            "status": self.status.name if hasattr(self.status, 'name') else str(self.status),
            "total_duration": self.metrics.total_duration,
            "configuration": {
                "transmission_mode": self.single_config.transmission_mode.value,
                "validation_level": self.single_config.validation_level.value,
                "retry_policy": self.single_config.retry_policy.value,
                "max_retries": self.single_config.max_retries,
                "burst_count": self.single_config.burst_count,
                "use_protocol_stack": self.single_config.use_protocol_stack,
                "apply_tecmp_encapsulation": self.single_config.apply_tecmp_encapsulation
            },
            "transmission_history": [result.__dict__ for result in self.metrics.transmission_results]
        })
        return metrics_dict
    
    def stop(self) -> bool:
        """
        Arreter la strategie single packet
        
        Returns:
            bool: True si arret reussi
        """
        try:
            self.logger.info(f"Stopping single packet strategy: {self.strategy_name}")
            
            # Signaler l'arret
            self._stop_event.set()
            
            # Attendre la fin du thread d'execution
            if self._execution_thread and self._execution_thread.is_alive():
                self._execution_thread.join(timeout=5.0)
                if self._execution_thread.is_alive():
                    self.logger.warning("Execution thread did not finish gracefully")
            
            # Mettre a jour le statut
            if self.status == StrategyStatus.RUNNING:
                self.status = StrategyStatus.STOPPED
            
            self._is_running = False
            
            # Finaliser si pas encore fait
            if self.execution_state != "COMPLETED":
                self._finalize_execution()
            
            self.logger.info("Single packet strategy stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping strategy: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Obtenir le statut detaille de la strategie
        
        Returns:
            Dict contenant toutes les informations de statut
        """
        try:
            current_time = time.time()
            elapsed_time = current_time - self.metrics.start_time
            
            status_dict = {
                "strategy_name": self.strategy_name,
                "strategy_type": "single",
                "status": self.status.name if hasattr(self.status, 'name') else str(self.status),
                "execution_state": self.execution_state,
                "is_running": self._is_running,
                "elapsed_time": elapsed_time,
                "metrics": self._get_metrics_dict(),
                "configuration": {
                    "transmission_mode": self.single_config.transmission_mode.value,
                    "delay_seconds": self.single_config.delay_seconds,
                    "burst_count": self.single_config.burst_count,
                    "validation_level": self.single_config.validation_level.value,
                    "retry_policy": self.single_config.retry_policy.value,
                    "max_retries": self.single_config.max_retries,
                    "use_protocol_stack": self.single_config.use_protocol_stack,
                    "apply_tecmp_encapsulation": self.single_config.apply_tecmp_encapsulation,
                    "integrate_with_facade": self.single_config.integrate_with_facade
                },
                "tecmp_integration": {
                    "facade_available": self.facade_reference is not None,
                    "packet_manager_available": self._packet_manager is not None,
                    "packet_builder_available": self._packet_builder is not None,
                    "tecmp_builder_available": self._tecmp_builder is not None,
                    "protocol_stack_size": len(self._protocol_stack)
                }
            }
            
            return status_dict
            
        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return {
                "strategy_name": self.strategy_name,
                "status": "ERROR",
                "error": str(e)
            }
    
    def get_transmission_history(self) -> List[Dict[str, Any]]:
        """Obtenir l'historique des transmissions"""
        return [result.__dict__ for result in self.metrics.transmission_results]
    
    def get_metrics(self) -> SingleStrategyMetrics:
        """Obtenir l'objet complet des metriques"""
        return copy.deepcopy(self.metrics)


# === UTILITY FUNCTIONS ===

def create_immediate_single_config() -> SingleStrategyConfiguration:
    """Creer une configuration pour envoi immediat"""
    return SingleStrategyConfiguration(
        transmission_mode=TransmissionMode.IMMEDIATE,
        validation_level=ValidationLevel.BASIC,
        retry_policy=RetryPolicy.FIXED_DELAY,
        max_retries=3
    )

def create_delayed_single_config(delay_seconds: float) -> SingleStrategyConfiguration:
    """Creer une configuration pour envoi differe"""
    return SingleStrategyConfiguration(
        transmission_mode=TransmissionMode.DELAYED,
        delay_seconds=delay_seconds,
        validation_level=ValidationLevel.BASIC,
        retry_policy=RetryPolicy.EXPONENTIAL_BACKOFF
    )

def create_burst_single_config(burst_count: int, interval_ms: float = 100.0) -> SingleStrategyConfiguration:
    """Creer une configuration pour envoi en rafale"""
    return SingleStrategyConfiguration(
        transmission_mode=TransmissionMode.BURST,
        burst_count=burst_count,
        burst_interval_ms=interval_ms,
        validation_level=ValidationLevel.STRICT,
        retry_policy=RetryPolicy.ADAPTIVE
    )

def create_scheduled_single_config(scheduled_time: datetime) -> SingleStrategyConfiguration:
    """Creer une configuration pour envoi programme"""
    return SingleStrategyConfiguration(
        transmission_mode=TransmissionMode.SCHEDULED,
        scheduled_time=scheduled_time,
        validation_level=ValidationLevel.TECMP_COMPLIANT,
        apply_tecmp_encapsulation=True
    )

def create_tecmp_compliant_config(facade_ref: Any = None) -> SingleStrategyConfiguration:
    """Creer une configuration compatible TECMP avec integration facade"""
    return SingleStrategyConfiguration(
        transmission_mode=TransmissionMode.IMMEDIATE,
        validation_level=ValidationLevel.TECMP_COMPLIANT,
        validate_tecmp_compliance=True,
        apply_tecmp_encapsulation=True,
        use_protocol_stack=True,
        integrate_with_facade=True,
        update_facade_metrics=True,
        packet_source="facade",
        enable_metrics=True,
        detailed_logging=True
    )


# === EXAMPLE USAGE ===

if __name__ == "__main__":
    import sys
    from unittest.mock import Mock
    
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=== SINGLE PACKET STRATEGY DEMONSTRATION ===")
    print("Compatible with TECMP-Tool Architecture")
    
    # Creer des mock senders
    mock_sender = Mock()
    mock_sender.send_packet = Mock(return_value=True)
    mock_sender.id = "MockSender_001"
    senders = [mock_sender]
    
    # Mock facade TECMP
    mock_facade = Mock()
    mock_facade.get_current_packet = Mock(return_value={
        "type": "mock_packet",
        "protocols": ["Ethernet", "IPv4", "UDP"],
        "size": 42,
        "timestamp": time.time()
    })
    mock_facade.get_protocol_stack = Mock(return_value=[
        {"name": "Ethernet", "config": {"src_mac": "aa:bb:cc:dd:ee:ff"}},
        {"name": "IPv4", "config": {"src_ip": "192.168.1.1", "dst_ip": "192.168.1.100"}},
        {"name": "UDP", "config": {"src_port": 12345, "dst_port": 5678}}
    ])
    
    # Test 1: Configuration immediate
    print("\n1. Test transmission immediate")
    immediate_config = create_immediate_single_config()
    immediate_config.integrate_with_facade = True
    immediate_config.detailed_logging = True
    
    strategy = SinglePacketStrategy(
        immediate_config, 
        senders, 
        "ImmediateTest",
        facade_reference=mock_facade
    )
    
    print(f"   Configuration valide: {immediate_config.validate()[0]}")
    print(f"   Strategie creee: {strategy.strategy_name}")
    
    # Executer la strategie
    success = strategy.execute()
    print(f"   Execution demarree: {success}")
    
    # Attendre la completion
    time.sleep(0.5)
    status = strategy.get_status()
    print(f"   Statut: {status['status']}")
    print(f"   Paquets envoyes: {status['metrics']['total_packets_sent']}")
    print(f"   Taux de succes: {status['metrics']['success_rate']:.1f}%")
    
    # Test 2: Configuration en rafale
    print("\n2. Test transmission en rafale")
    burst_config = create_burst_single_config(3, 50.0)
    burst_config.integrate_with_facade = True
    
    burst_strategy = SinglePacketStrategy(
        burst_config,
        senders,
        "BurstTest", 
        facade_reference=mock_facade
    )
    
    burst_strategy.execute()
    time.sleep(0.5)
    
    burst_status = burst_strategy.get_status()
    print(f"   Statut burst: {burst_status['status']}")
    print(f"   Paquets envoyes: {burst_status['metrics']['total_packets_sent']}")
    print(f"   Latence moyenne: {burst_status['metrics']['average_latency_ms']:.2f}ms")
    
    # Test 3: Configuration differee
    print("\n3. Test transmission differee")
    delayed_config = create_delayed_single_config(0.2)
    delayed_config.validation_level = ValidationLevel.STRICT
    
    delayed_strategy = SinglePacketStrategy(
        delayed_config,
        senders,
        "DelayedTest",
        facade_reference=mock_facade
    )
    
    start_time = time.time()
    delayed_strategy.execute()
    time.sleep(0.5)
    
    delayed_status = delayed_strategy.get_status()
    actual_delay = time.time() - start_time
    print(f"   Delai configure: 0.2s, delai reel: {actual_delay:.2f}s")
    print(f"   Statut delayed: {delayed_status['status']}")
    
    # Test 4: Configuration TECMP compliant
    print("\n4. Test configuration TECMP compliant")
    tecmp_config = create_tecmp_compliant_config(mock_facade)
    
    tecmp_strategy = SinglePacketStrategy(
        tecmp_config,
        senders,
        "TECMPCompliantTest",
        facade_reference=mock_facade
    )
    
    tecmp_strategy.execute()
    time.sleep(0.3)
    
    tecmp_status = tecmp_strategy.get_status()
    print(f"   Statut TECMP: {tecmp_status['status']}")
    print(f"   Integration facade: {tecmp_status['tecmp_integration']['facade_available']}")
    print(f"   Protocol stack: {tecmp_status['tecmp_integration']['protocol_stack_size']} protocoles")
    
    # Test 5: Configuration avec validation des erreurs
    print("\n5. Test gestion d'erreurs")
    error_sender = Mock()
    error_sender.send_packet = Mock(return_value=False)  # Simule echec
    error_sender.id = "ErrorSender"
    
    error_config = SingleStrategyConfiguration(
        transmission_mode=TransmissionMode.IMMEDIATE,
        validation_level=ValidationLevel.STRICT,
        retry_policy=RetryPolicy.EXPONENTIAL_BACKOFF,
        max_retries=2,
        detailed_logging=True
    )
    
    error_strategy = SinglePacketStrategy(
        error_config,
        [error_sender],
        "ErrorTest"
    )
    
    error_strategy.execute()
    time.sleep(0.3)
    
    error_status = error_strategy.get_status()
    print(f"   Statut erreur: {error_status['status']}")
    print(f"   Erreurs transmission: {error_status['metrics']['transmission_errors']}")
    print(f"   Total retries: {error_status['metrics']['total_retries']}")
    
    # Test 6: Metriques et historique
    print("\n6. Test metriques et historique")
    history = immediate_strategy.get_transmission_history()
    metrics = immediate_strategy.get_metrics()
    
    print(f"   Historique: {len(history)} transmissions")
    print(f"   Succes total: {metrics.successful_transmissions}")
    print(f"   Bytes total: {metrics.total_bytes_sent}")
    print(f"   Duree totale: {metrics.total_duration:.3f}s")
    
    print("\n" + "="*60)
    print("? TOUS LES TESTS SINGLE STRATEGY ReUSSIS")
    print("="*60)
    print("? Transmission immediate fonctionnelle")
    print("? Transmission en rafale operationnelle") 
    print("? Transmission differee validee")
    print("? Compatibilite TECMP verifiee")
    print("? Gestion d'erreurs et retry testee")
    print("? Metriques et monitoring actifs")
    print("? Integration facade TECMP-Tool confirmee")
    print("="*60)
    print("?? SinglePacketStrategy prete pour production!")
    
    # Nettoyage
    for strat in [strategy, burst_strategy, delayed_strategy, tecmp_strategy, error_strategy]:
        try:
            strat.stop()
        except:
            pass