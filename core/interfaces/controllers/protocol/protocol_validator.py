#!/usr/bin/env python
# coding: utf-8
"""
Complete Protocol Validator for TECMP-Tool with Full Network Security Policies
Advanced protocol validation with comprehensive security policies for all network layers.

This validator includes security policies for:
- Ethernet (MAC filtering, anti-spoofing)
- VLAN (segmentation, default VLAN blocking)
- IPv4/IPv6 (IP range restrictions, geo-blocking, security checks)
- ARP (anti-poisoning, suspicious activity detection)
- TCP (port blocking, flag validation, service restrictions)
- UDP (service filtering, rate limiting indicators)

All policies integrate with zero impact on existing components.
"""

import logging
import re
import time
import copy
import json
import asyncio
import threading
from typing import Dict, Any, List, Optional, Set, Tuple, Callable, Union, AsyncGenerator
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from collections import defaultdict
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
import hashlib


class ValidationSeverity(Enum):
    """Severity levels for validation results."""
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class ValidationCategory(Enum):
    """Categories of validation issues."""
    DEPENDENCY = auto()
    CONFIGURATION = auto()
    FORMAT = auto()
    RANGE = auto()
    COMPATIBILITY = auto()
    PERFORMANCE = auto()
    SECURITY = auto()
    CUSTOM = auto()


@dataclass
class ValidationResult:
    """Comprehensive validation result with detailed information."""
    is_valid: bool
    severity: ValidationSeverity
    category: ValidationCategory
    message: str
    protocol_name: Optional[str] = None
    field_name: Optional[str] = None
    suggested_fix: Optional[str] = None
    error_code: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationResult':
        """Create from dictionary."""
        return cls(**data)


# === NETWORK POLICIES INJECTION ===
@dataclass
class NetworkPolicy:
    """Network policy definition - zero impact on existing code."""
    name: str
    description: str
    check_function: Callable[[List[Dict[str, Any]]], Optional[ValidationResult]]
    enabled: bool = True
    priority: int = 0  # Higher = checked first


@dataclass
class ValidationStatistics:
    """Statistics for validation operations."""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    warnings_issued: int = 0
    errors_found: int = 0
    dependency_checks: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    average_validation_time: float = 0.0
    session_start_time: float = field(default_factory=time.time)
    async_validations: int = 0
    plugin_validations: int = 0
    policy_violations: int = 0  # Added for policy tracking
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class ValidationPlugin(ABC):
    """Abstract base class for validation plugins."""
    
    @abstractmethod
    def validate(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate protocol configuration."""
        pass
    
    @abstractmethod
    def get_supported_protocols(self) -> List[str]:
        """Get list of protocols supported by this plugin."""
        pass
    
    @abstractmethod
    def get_plugin_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        pass


class ValidationReporter:
    """Enhanced reporting and export functionality."""
    
    def __init__(self):
        self.logger = logging.getLogger("TECMP-Tool.ValidationReporter")
    
    def generate_html_report(self, results: List[ValidationResult], title: str = "Validation Report") -> str:
        """Generate HTML validation report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 10px; border-radius: 5px; }}
                .result {{ margin: 10px 0; padding: 10px; border-left: 4px solid; }}
                .error {{ border-left-color: #d32f2f; background-color: #ffebee; }}
                .warning {{ border-left-color: #f57c00; background-color: #fff3e0; }}
                .info {{ border-left-color: #1976d2; background-color: #e3f2fd; }}
                .critical {{ border-left-color: #7b1fa2; background-color: #f3e5f5; }}
                .protocol {{ font-weight: bold; color: #333; }}
                .message {{ margin: 5px 0; }}
                .fix {{ font-style: italic; color: #666; }}
                .timestamp {{ font-size: 0.8em; color: #999; }}
                .policy {{ background-color: #fffde7; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{title}</h1>
                <p>Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Total Results: {len(results)}</p>
            </div>
        """
        
        for result in results:
            severity_class = result.severity.name.lower()
            policy_class = "policy" if result.error_code and result.error_code.startswith("POLICY_") else ""
            html += f"""
            <div class="result {severity_class} {policy_class}">
                <div class="protocol">{result.protocol_name or 'General'}</div>
                <div class="message">{result.message}</div>
                {f'<div class="fix">Suggested fix: {result.suggested_fix}</div>' if result.suggested_fix else ''}
                <div class="timestamp">{time.strftime('%H:%M:%S', time.localtime(result.timestamp))}</div>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        return html
    
    def generate_json_report(self, results: List[ValidationResult]) -> str:
        """Generate JSON validation report."""
        report_data = {
            "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "total_results": len(results),
            "summary": {
                "errors": len([r for r in results if r.severity == ValidationSeverity.ERROR]),
                "warnings": len([r for r in results if r.severity == ValidationSeverity.WARNING]),
                "critical": len([r for r in results if r.severity == ValidationSeverity.CRITICAL]),
                "info": len([r for r in results if r.severity == ValidationSeverity.INFO]),
                "policy_violations": len([r for r in results if r.error_code and r.error_code.startswith("POLICY_")])
            },
            "results": [result.to_dict() for result in results]
        }
        return json.dumps(report_data, indent=2)
    
    def generate_csv_report(self, results: List[ValidationResult]) -> str:
        """Generate CSV validation report."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "Timestamp", "Protocol", "Severity", "Category", "Message", 
            "Field", "Error Code", "Suggested Fix", "Is Policy"
        ])
        
        # Data
        for result in results:
            is_policy = "Yes" if result.error_code and result.error_code.startswith("POLICY_") else "No"
            writer.writerow([
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result.timestamp)),
                result.protocol_name or '',
                result.severity.name,
                result.category.name,
                result.message,
                result.field_name or '',
                result.error_code or '',
                result.suggested_fix or '',
                is_policy
            ])
        
        return output.getvalue()


class ProtocolValidator:
    """
    Advanced protocol validator with comprehensive validation capabilities.
    
    This validator provides extensive protocol validation including:
    - Protocol stack dependency validation
    - Individual protocol configuration validation
    - Extensible validation framework with plugin support
    - Performance optimization with caching
    - Detailed error reporting and suggestions
    - Asynchronous validation for large stacks
    - Export/Import of validation configurations
    - Integration with TECMP-Tool ecosystem
    - Comprehensive network security policies for all layers
    """
    
    def __init__(self, strict_mode: bool = False, enable_caching: bool = True, 
                 max_workers: int = 4):
        """
        Initialize the protocol validator.
        
        Args:
            strict_mode: Whether to use strict validation (errors vs warnings)
            enable_caching: Whether to enable validation result caching
            max_workers: Maximum number of worker threads for async validation
        """
        self.logger = logging.getLogger("TECMP-Tool.ProtocolValidator")
        
        # Validation configuration
        self._strict_validation = strict_mode
        self._enable_caching = enable_caching
        self._enable_dependency_warnings = True
        self._max_stack_depth = 20
        self._max_workers = max_workers
        
        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Protocol dependencies mapping
        self._protocol_dependencies = {
            # Network Layer Dependencies
            "TCP": ["IPv4", "IPv6"],
            "UDP": ["IPv4", "IPv6"],
            "SCTP": ["IPv4", "IPv6"],
            "ICMP": ["IPv4"],
            "ICMPv6": ["IPv6"],
            
            # Internet Layer Dependencies
            "IPv4": ["Ethernet", "PPP", "SLIP"],
            "IPv6": ["Ethernet", "PPP"],
            "ARP": ["Ethernet"],
            "RARP": ["Ethernet"],
            
            # Application Layer Dependencies
            "HTTP": ["TCP"],
            "HTTPS": ["TCP"],
            "FTP": ["TCP"],
            "SMTP": ["TCP"],
            "DNS": ["UDP", "TCP"],
            "DHCP": ["UDP"],
            "SNMP": ["UDP"],
            "TFTP": ["UDP"],
            
            # Automotive Protocols
            "SOME/IP": ["UDP", "TCP"],
            "SOME/IP-SD": ["UDP"],
            "DoIP": ["TCP", "UDP"],
            "UDS": ["TCP", "CAN", "CAN-FD"],
            
            # CAN Protocol Family
            "CAN-TP": ["CAN"],
            "J1939": ["CAN"],
            "CANopen": ["CAN"],
            
            # FlexRay Dependencies
            "FlexRay-TP": ["FlexRay"],
            
            # VLAN Dependencies
            "VLAN": ["Ethernet"],
            
            # TECMP Dependencies
            "TECMP": []  # TECMP can encapsulate any protocol
        }
        
        # Protocol mutual exclusions (protocols that cannot coexist)
        self._protocol_exclusions = {
            "IPv4": ["IPv6"],  # Typically not both in same packet
            "CAN": ["CAN-FD"],  # Cannot have both classical CAN and CAN-FD
            "HTTP": ["HTTPS"]   # Cannot have both HTTP and HTTPS
        }
        
        # Protocol order preferences (optimal ordering)
        self._preferred_order = [
            # Physical/Data Link Layer
            "Ethernet", "WiFi", "PPP", "SLIP",
            # VLAN comes after Ethernet
            "VLAN",
            # Network Layer  
            "ARP", "RARP", "IPv4", "IPv6",
            # Transport Layer
            "TCP", "UDP", "SCTP", "ICMP", "ICMPv6",
            # Application Layer
            "HTTP", "HTTPS", "FTP", "SMTP", "DNS", "DHCP",
            # Automotive
            "SOME/IP", "SOME/IP-SD", "DoIP", "UDS",
            # CAN Family
            "CAN", "CAN-FD", "CAN-TP", "J1939", "CANopen",
            # Others
            "FlexRay", "FlexRay-TP", "LIN", "UART",
            # TECMP (usually last as it encapsulates)
            "TECMP"
        ]
        
        # Validation cache
        self._validation_cache = {} if enable_caching else None
        self._cache_ttl = 300  # 5 minutes
        self._cache_lock = threading.RLock()
        
        # Statistics
        self._statistics = ValidationStatistics()
        self._stats_lock = threading.RLock()
        
        # Plugin system
        self._plugins: Dict[str, ValidationPlugin] = {}
        
        # Network Policies System (zero-impact injection)
        self._network_policies: Dict[str, NetworkPolicy] = {}
        self._enable_network_policies = True
        self._initialize_default_policies()
        self._initialize_comprehensive_network_policies()
        
        # Core validators registry
        self._protocol_validators = {
            "Ethernet": self._validate_ethernet_config,
            "VLAN": self._validate_vlan_config,
            "IPv4": self._validate_ipv4_config,
            "IPv6": self._validate_ipv6_config,
            "ARP": self._validate_arp_config,
            "TCP": self._validate_tcp_config,
            "UDP": self._validate_udp_config,
            "TECMP": self._validate_tecmp_config,
            "CAN": self._validate_can_config,
            "CAN-FD": self._validate_canfd_config,
            "FlexRay": self._validate_flexray_config,
            "LIN": self._validate_lin_config,
            "UART": self._validate_uart_config,
            "SOME/IP": self._validate_someip_config,
            "DoIP": self._validate_doip_config,
            "HTTP": self._validate_http_config,
            "DNS": self._validate_dns_config,
            "HTTPS": self._validate_https_config,
            "FTP": self._validate_ftp_config,
            "SMTP": self._validate_smtp_config,
            "DHCP": self._validate_dhcp_config,
            "SNMP": self._validate_snmp_config,
            "J1939": self._validate_j1939_config,
            "UDS": self._validate_uds_config
        }
        
        # Error recovery and suggestions
        self._error_suggestions = {
            "MISSING_DEPENDENCY": "Add required dependency protocol before this protocol",
            "INVALID_ORDER": "Reorder protocols according to network stack hierarchy",
            "MUTUAL_EXCLUSION": "Remove conflicting protocol or choose alternative",
            "INVALID_FORMAT": "Check format specification and correct the value",
            "OUT_OF_RANGE": "Ensure value is within valid range",
            "INCOMPATIBLE_CONFIG": "Review protocol compatibility requirements",
            "SECURITY_RISK": "Review security implications and apply recommended fixes",
            "PERFORMANCE_WARNING": "Consider performance optimization suggestions",
            "POLICY_VIOLATION": "Review organizational security policies"
        }
        
        # Reporter
        self._reporter = ValidationReporter()
        
        self.logger.info(f"ProtocolValidator initialized (strict_mode: {strict_mode}, "
                        f"caching: {enable_caching}, max_workers: {max_workers})")
    
    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
    
    # === NETWORK POLICIES SYSTEM (ZERO IMPACT) ===

    def _initialize_default_policies(self) -> None:
        """Initialize built-in network security policies."""
        # Policy 1: No unencrypted HTTP without TLS
        self.register_network_policy(NetworkPolicy(
            name="NO_CLEAR_HTTP",
            description="HTTP requires TLS/HTTPS encryption",
            check_function=lambda stack: self._check_http_encryption_policy(stack)
        ))
        
        # Policy 2: No telnet/FTP without secure alternative
        self.register_network_policy(NetworkPolicy(
            name="NO_LEGACY_INSECURE",
            description="Legacy insecure protocols forbidden",
            check_function=lambda stack: self._check_legacy_protocols_policy(stack)
        ))
        
        # Policy 3: Automotive security requirements
        self.register_network_policy(NetworkPolicy(
            name="AUTOMOTIVE_SEC_REQUIRED",
            description="Automotive protocols require security layer",
            check_function=lambda stack: self._check_automotive_security_policy(stack)
        ))

    def _initialize_comprehensive_network_policies(self) -> None:
        """Initialize comprehensive security policies for all network layers."""
        
        # === ETHERNET POLICIES ===
        self.register_network_policy(NetworkPolicy(
            name="ETHERNET_MAC_SECURITY",
            description="Ethernet MAC address security checks",
            check_function=lambda stack: self._check_ethernet_mac_security(stack),
            priority=90
        ))
        
        self.register_network_policy(NetworkPolicy(
            name="ETHERNET_BROADCAST_LIMIT",
            description="Limit broadcast MAC usage",
            check_function=lambda stack: self._check_ethernet_broadcast_policy(stack),
            priority=85
        ))
        
        # === VLAN POLICIES ===
        self.register_network_policy(NetworkPolicy(
            name="VLAN_DEFAULT_FORBIDDEN",
            description="Default VLAN 1 forbidden in production",
            check_function=lambda stack: self._check_vlan_default_policy(stack),
            priority=95
        ))
        
        self.register_network_policy(NetworkPolicy(
            name="VLAN_SEGMENTATION",
            description="VLAN segmentation enforcement",
            check_function=lambda stack: self._check_vlan_segmentation_policy(stack),
            priority=93
        ))
        
        # === IPv4/IPv6 POLICIES ===
        self.register_network_policy(NetworkPolicy(
            name="IP_PRIVATE_RANGE_CONTROL",
            description="Control private IP range usage",
            check_function=lambda stack: self._check_ip_private_range_policy(stack),
            priority=88
        ))
        
        self.register_network_policy(NetworkPolicy(
            name="IP_RESERVED_FORBIDDEN",
            description="Forbid reserved IP addresses",
            check_function=lambda stack: self._check_ip_reserved_policy(stack),
            priority=87
        ))
        
        self.register_network_policy(NetworkPolicy(
            name="IPV6_TUNNELING_CONTROL",
            description="Control IPv6 tunneling",
            check_function=lambda stack: self._check_ipv6_tunneling_policy(stack),
            priority=86
        ))
        
        self.register_network_policy(NetworkPolicy(
            name="IP_TTL_SECURITY",
            description="IP TTL security checks",
            check_function=lambda stack: self._check_ip_ttl_policy(stack),
            priority=84
        ))
        
        # === ARP POLICIES ===
        self.register_network_policy(NetworkPolicy(
            name="ARP_POISONING_DETECTION",
            description="ARP poisoning detection",
            check_function=lambda stack: self._check_arp_poisoning_policy(stack),
            priority=92
        ))
        
        self.register_network_policy(NetworkPolicy(
            name="ARP_GRATUITOUS_CONTROL",
            description="Control gratuitous ARP",
            check_function=lambda stack: self._check_arp_gratuitous_policy(stack),
            priority=91
        ))
        
        # === TCP POLICIES ===
        self.register_network_policy(NetworkPolicy(
            name="TCP_PORT_RESTRICTIONS",
            description="TCP port security restrictions",
            check_function=lambda stack: self._check_tcp_port_policy(stack),
            priority=89
        ))
        
        self.register_network_policy(NetworkPolicy(
            name="TCP_FLAG_VALIDATION",
            description="TCP flag combination validation",
            check_function=lambda stack: self._check_tcp_flag_policy(stack),
            priority=88
        ))
        
        self.register_network_policy(NetworkPolicy(
            name="TCP_PRIVILEGED_PORTS",
            description="TCP privileged port control",
            check_function=lambda stack: self._check_tcp_privileged_ports(stack),
            priority=87
        ))
        
        # === UDP POLICIES ===
        self.register_network_policy(NetworkPolicy(
            name="UDP_SERVICE_RESTRICTIONS",
            description="UDP service access control",
            check_function=lambda stack: self._check_udp_service_policy(stack),
            priority=86
        ))
        
        self.register_network_policy(NetworkPolicy(
            name="UDP_AMPLIFICATION_PREVENTION",
            description="UDP amplification attack prevention",
            check_function=lambda stack: self._check_udp_amplification_policy(stack),
            priority=85
        ))
        
        self.register_network_policy(NetworkPolicy(
            name="UDP_FRAGMENTATION_CONTROL",
            description="UDP fragmentation control",
            check_function=lambda stack: self._check_udp_fragmentation_policy(stack),
            priority=84
        ))

    # === ETHERNET POLICY IMPLEMENTATIONS ===
    
    def _check_ethernet_mac_security(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check Ethernet MAC address security issues."""
        for protocol in stack:
            if protocol.get("name") == "Ethernet":
                config = protocol.get("config", {})
                src_mac = config.get("src_mac", "")
                dst_mac = config.get("dst_mac", "")
                
                # Check for same source and destination (loop)
                if src_mac and dst_mac and src_mac == dst_mac:
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.SECURITY,
                        message="Source and destination MAC are identical (potential loop)",
                        protocol_name="Ethernet",
                        field_name="src_mac/dst_mac",
                        suggested_fix="Ensure source and destination MACs are different",
                        error_code="POLICY_MAC_LOOP_DETECTED"
                    )
                
                # Check for multicast source MAC (invalid)
                if src_mac and src_mac.startswith(('01:', '33:', '01-', '33-')):
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.SECURITY,
                        message="Multicast address used as source MAC (invalid)",
                        protocol_name="Ethernet",
                        field_name="src_mac",
                        suggested_fix="Use unicast address for source MAC",
                        error_code="POLICY_INVALID_SOURCE_MAC"
                    )
        return None
    
    def _check_ethernet_broadcast_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check Ethernet broadcast usage policy."""
        for protocol in stack:
            if protocol.get("name") == "Ethernet":
                config = protocol.get("config", {})
                dst_mac = config.get("dst_mac", "").upper().replace("-", ":")
                
                # Check for broadcast MAC in production
                if dst_mac in ["FF:FF:FF:FF:FF:FF", "FFFFFFFFFFFF"]:
                    # Check if this is a legitimate broadcast protocol
                    protocols = [p.get("name") for p in stack]
                    if not any(p in ["ARP", "DHCP"] for p in protocols):
                        return ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.WARNING,
                            category=ValidationCategory.SECURITY,
                            message="Broadcast MAC used without ARP/DHCP context",
                            protocol_name="Ethernet",
                            field_name="dst_mac",
                            suggested_fix="Use unicast or multicast address unless necessary",
                            error_code="POLICY_UNNECESSARY_BROADCAST"
                        )
        return None
    
    # === VLAN POLICY IMPLEMENTATIONS ===
    
    def _check_vlan_default_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check for default VLAN usage."""
        for protocol in stack:
            if protocol.get("name") == "VLAN":
                config = protocol.get("config", {})
                vlan_id = config.get("vlan_id", 0)
                
                if vlan_id == 1:
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.SECURITY,
                        message="Default VLAN 1 not allowed in production environment",
                        protocol_name="VLAN",
                        field_name="vlan_id",
                        suggested_fix="Use dedicated VLAN (10-4094) for production traffic",
                        error_code="POLICY_DEFAULT_VLAN_FORBIDDEN"
                    )
        return None
    
    def _check_vlan_segmentation_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check VLAN segmentation policies."""
        for protocol in stack:
            if protocol.get("name") == "VLAN":
                config = protocol.get("config", {})
                vlan_id = config.get("vlan_id", 0)
                
                # Define VLAN ranges and policies
                # Guest VLANs: 300-399
                # IoT VLANs: 200-299
                # Corporate VLANs: 100-199
                # Management VLANs: 10-20
                
                # Check IoT VLAN accessing corporate resources
                if 200 <= vlan_id <= 299:
                    # Check if accessing corporate services
                    for p in stack:
                        if p.get("name") == "TCP":
                            tcp_config = p.get("config", {})
                            dst_port = tcp_config.get("dst_port", 0)
                            # Corporate services ports
                            if dst_port in [389, 636, 3389, 1433, 3306]:  # LDAP, RDP, SQL
                                return ValidationResult(
                                    is_valid=False,
                                    severity=ValidationSeverity.ERROR,
                                    category=ValidationCategory.SECURITY,
                                    message=f"IoT VLAN {vlan_id} attempting to access corporate service on port {dst_port}",
                                    protocol_name="VLAN",
                                    suggested_fix="IoT devices must not access corporate services directly",
                                    error_code="POLICY_VLAN_SEGMENTATION_VIOLATION"
                                )
        return None
    
    # === IPv4/IPv6 POLICY IMPLEMENTATIONS ===
    
    def _check_ip_private_range_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check private IP range usage policies."""
        for protocol in stack:
            if protocol.get("name") == "IPv4":
                config = protocol.get("config", {})
                src_ip = config.get("src_ip", "")
                dst_ip = config.get("dst_ip", "")
                
                # Check if private IP is going to public IP (potential NAT issue)
                def is_private_ip(ip):
                    parts = ip.split('.')
                    if len(parts) != 4:
                        return False
                    try:
                        # 10.0.0.0/8
                        if int(parts[0]) == 10:
                            return True
                        # 172.16.0.0/12
                        if int(parts[0]) == 172 and 16 <= int(parts[1]) <= 31:
                            return True
                        # 192.168.0.0/16
                        if int(parts[0]) == 192 and int(parts[1]) == 168:
                            return True
                    except ValueError:
                        pass
                    return False
                
                def is_public_ip(ip):
                    return not is_private_ip(ip) and not ip.startswith(('127.', '169.254.', '224.', '255.'))
                
                if is_private_ip(src_ip) and is_public_ip(dst_ip):
                    # Check if NAT is properly configured (would need additional context)
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.SECURITY,
                        message="Private IP address communicating directly with public IP",
                        protocol_name="IPv4",
                        suggested_fix="Ensure proper NAT configuration for private to public communication",
                        error_code="POLICY_PRIVATE_IP_LEAK"
                    )
        return None
    
    def _check_ip_reserved_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check for reserved IP address usage."""
        for protocol in stack:
            if protocol.get("name") in ["IPv4", "IPv6"]:
                config = protocol.get("config", {})
                
                if protocol.get("name") == "IPv4":
                    src_ip = config.get("src_ip", "")
                    dst_ip = config.get("dst_ip", "")
                    
                    # Check for APIPA addresses (169.254.x.x)
                    for ip in [src_ip, dst_ip]:
                        if ip.startswith("169.254.") and not ip.endswith(".0.0"):
                            return ValidationResult(
                                is_valid=False,
                                severity=ValidationSeverity.WARNING,
                                category=ValidationCategory.SECURITY,
                                message=f"APIPA address {ip} detected (indicates DHCP failure)",
                                protocol_name="IPv4",
                                suggested_fix="Check DHCP configuration or assign static IP",
                                error_code="POLICY_APIPA_ADDRESS"
                            )
                    
                    # Check for test/documentation addresses
                    test_ranges = ["192.0.2.", "198.51.100.", "203.0.113."]
                    for ip in [src_ip, dst_ip]:
                        if any(ip.startswith(range) for range in test_ranges):
                            return ValidationResult(
                                is_valid=False,
                                severity=ValidationSeverity.ERROR,
                                category=ValidationCategory.SECURITY,
                                message=f"Test/documentation IP address {ip} used in production",
                                protocol_name="IPv4",
                                suggested_fix="Use valid production IP addresses",
                                error_code="POLICY_TEST_IP_IN_PRODUCTION"
                            )
        return None
    
    def _check_ipv6_tunneling_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check IPv6 tunneling policies."""
        protocols = [p.get("name") for p in stack]
        
        # Check for IPv6 over IPv4 tunneling
        if "IPv6" in protocols and "IPv4" in protocols:
            # Check if this is unauthorized tunneling
            ipv6_idx = next(i for i, p in enumerate(stack) if p.get("name") == "IPv6")
            ipv4_idx = next(i for i, p in enumerate(stack) if p.get("name") == "IPv4")
            
            if ipv4_idx < ipv6_idx:  # IPv4 encapsulating IPv6
                # Check for known tunnel protocols
                has_tunnel_protocol = any(p in protocols for p in ["6to4", "Teredo", "ISATAP"])
                if not has_tunnel_protocol:
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.SECURITY,
                        message="IPv6 tunneling over IPv4 detected without explicit tunnel protocol",
                        protocol_name="IPv6",
                        suggested_fix="Use authorized tunneling protocols or native IPv6",
                        error_code="POLICY_UNAUTHORIZED_IPV6_TUNNEL"
                    )
        return None
    
    def _check_ip_ttl_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check IP TTL security policies."""
        for protocol in stack:
            if protocol.get("name") in ["IPv4", "IPv6"]:
                config = protocol.get("config", {})
                
                if protocol.get("name") == "IPv4":
                    ttl = config.get("ttl", 64)
                    if ttl < 5:
                        return ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.WARNING,
                            category=ValidationCategory.SECURITY,
                            message=f"Suspiciously low TTL value: {ttl} (possible reconnaissance)",
                            protocol_name="IPv4",
                            field_name="ttl",
                            suggested_fix="Use standard TTL values (64, 128, 255)",
                            error_code="POLICY_LOW_TTL_SUSPICIOUS"
                        )
                elif protocol.get("name") == "IPv6":
                    hop_limit = config.get("hop_limit", 64)
                    if hop_limit < 5:
                        return ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.WARNING,
                            category=ValidationCategory.SECURITY,
                            message=f"Suspiciously low hop limit: {hop_limit} (possible reconnaissance)",
                            protocol_name="IPv6",
                            field_name="hop_limit",
                            suggested_fix="Use standard hop limit values (64, 128, 255)",
                            error_code="POLICY_LOW_HOP_LIMIT_SUSPICIOUS"
                        )
        return None
    
    # === ARP POLICY IMPLEMENTATIONS ===
    
    def _check_arp_poisoning_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check for ARP poisoning indicators."""
        for protocol in stack:
            if protocol.get("name") == "ARP":
                config = protocol.get("config", {})
                operation = config.get("operation", 1)  # 1=request, 2=reply
                
                # Check for unsolicited ARP reply (operation=2 without request)
                if operation == 2:
                    # In real implementation, would check against ARP request tracking
                    # For now, flag all ARP replies as potentially suspicious
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.SECURITY,
                        message="ARP reply detected - verify against ARP request tracking",
                        protocol_name="ARP",
                        suggested_fix="Implement ARP inspection to prevent poisoning",
                        error_code="POLICY_ARP_REPLY_INSPECTION"
                    )
                
                # Check for ARP targeting gateway
                target_ip = config.get("target_ip", "")
                if target_ip.endswith(".1") or target_ip.endswith(".254"):
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.SECURITY,
                        message=f"ARP targeting potential gateway IP: {target_ip}",
                        protocol_name="ARP",
                        suggested_fix="Monitor gateway ARP activity for poisoning attempts",
                        error_code="POLICY_ARP_GATEWAY_TARGET"
                    )
        return None
    
    def _check_arp_gratuitous_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check gratuitous ARP policy."""
        for protocol in stack:
            if protocol.get("name") == "ARP":
                config = protocol.get("config", {})
                sender_ip = config.get("sender_ip", "")
                target_ip = config.get("target_ip", "")
                
                # Gratuitous ARP: sender IP = target IP
                if sender_ip and target_ip and sender_ip == target_ip:
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.INFO,
                        category=ValidationCategory.SECURITY,
                        message="Gratuitous ARP detected (sender IP = target IP)",
                        protocol_name="ARP",
                        suggested_fix="Limit gratuitous ARP to 1 per minute per host",
                        error_code="POLICY_GRATUITOUS_ARP"
                    )
        return None
    
    # === TCP POLICY IMPLEMENTATIONS ===
    
    def _check_tcp_port_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check TCP port security policies."""
        for protocol in stack:
            if protocol.get("name") == "TCP":
                config = protocol.get("config", {})
                dst_port = config.get("dst_port", 0)
                src_port = config.get("src_port", 0)
                
                # Blocked ports list
                blocked_ports = {
                    23: ("Telnet", "Use SSH (port 22) instead"),
                    135: ("RPC/DCE", "Windows RPC - block at firewall"),
                    139: ("NetBIOS", "Legacy SMB - use port 445 with SMBv3"),
                    445: ("SMB", "Restrict to internal network only"),
                    1433: ("MS SQL", "Should not be exposed to internet"),
                    3389: ("RDP", "Use VPN for remote desktop access"),
                    5900: ("VNC", "Use secure remote access solution"),
                    5985: ("WinRM HTTP", "Use WinRM HTTPS (5986) instead"),
                    8080: ("HTTP Alternate", "Often targeted, use standard HTTPS"),
                    9200: ("Elasticsearch", "Should not be exposed without auth")
                }
                
                if dst_port in blocked_ports:
                    service, suggestion = blocked_ports[dst_port]
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.SECURITY,
                        message=f"Blocked port {dst_port} ({service}) detected",
                        protocol_name="TCP",
                        field_name="dst_port",
                        suggested_fix=suggestion,
                        error_code=f"POLICY_BLOCKED_PORT_{dst_port}"
                    )
                
                # Check for port 0 (invalid)
                if dst_port == 0 or src_port == 0:
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.SECURITY,
                        message="TCP port 0 is invalid and often used in OS fingerprinting",
                        protocol_name="TCP",
                        suggested_fix="Use valid port numbers (1-65535)",
                        error_code="POLICY_INVALID_PORT_ZERO"
                    )
        return None
    
    def _check_tcp_flag_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check TCP flag combination policies."""
        for protocol in stack:
            if protocol.get("name") == "TCP":
                config = protocol.get("config", {})
                flags = config.get("flags", {})
                
                if isinstance(flags, dict):
                    syn = flags.get("syn", False)
                    fin = flags.get("fin", False)
                    rst = flags.get("rst", False)
                    psh = flags.get("psh", False)
                    ack = flags.get("ack", False)
                    urg = flags.get("urg", False)
                    
                    # Check for NULL scan (no flags)
                    if not any([syn, fin, rst, psh, ack, urg]):
                        return ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.SECURITY,
                            message="TCP NULL scan detected (no flags set)",
                            protocol_name="TCP",
                            suggested_fix="Block packets with no TCP flags",
                            error_code="POLICY_TCP_NULL_SCAN"
                        )
                    
                    # Check for XMAS scan (FIN, PSH, URG)
                    if fin and psh and urg and not syn and not ack:
                        return ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.SECURITY,
                            message="TCP XMAS scan detected (FIN+PSH+URG)",
                            protocol_name="TCP",
                            suggested_fix="Block suspicious flag combinations",
                            error_code="POLICY_TCP_XMAS_SCAN"
                        )
                    
                    # Check for SYN+FIN (invalid)
                    if syn and fin:
                        return ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.SECURITY,
                            message="Invalid TCP flags: SYN+FIN",
                            protocol_name="TCP",
                            suggested_fix="Block invalid flag combinations",
                            error_code="POLICY_TCP_INVALID_FLAGS"
                        )
        return None
    
    def _check_tcp_privileged_ports(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check TCP privileged port usage."""
        for protocol in stack:
            if protocol.get("name") == "TCP":
                config = protocol.get("config", {})
                src_port = config.get("src_port", 0)
                
                # Check source port in privileged range (1-1023)
                if 1 <= src_port <= 1023:
                    # Common legitimate uses
                    legitimate_services = {
                        20: "FTP-DATA", 21: "FTP", 22: "SSH", 25: "SMTP",
                        53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
                        443: "HTTPS", 465: "SMTPS", 587: "SMTP-SUB",
                        993: "IMAPS", 995: "POP3S"
                    }
                    
                    if src_port not in legitimate_services:
                        return ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.WARNING,
                            category=ValidationCategory.SECURITY,
                            message=f"Non-standard use of privileged source port {src_port}",
                            protocol_name="TCP",
                            field_name="src_port",
                            suggested_fix="Use ephemeral ports (49152-65535) for client connections",
                            error_code="POLICY_PRIVILEGED_PORT_MISUSE"
                        )
        return None
    
    # === UDP POLICY IMPLEMENTATIONS ===
    
    def _check_udp_service_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check UDP service access policies."""
        for protocol in stack:
            if protocol.get("name") == "UDP":
                config = protocol.get("config", {})
                dst_port = config.get("dst_port", 0)
                
                # Restricted UDP services
                restricted_services = {
                    53: ("DNS", "Use internal DNS servers only"),
                    67: ("DHCP Server", "DHCP server ports should be protected"),
                    69: ("TFTP", "TFTP is insecure, use secure file transfer"),
                    123: ("NTP", "Use internal NTP servers"),
                    137: ("NetBIOS Name", "Legacy protocol, should be disabled"),
                    161: ("SNMP", "Use SNMPv3 with authentication"),
                    1900: ("SSDP/UPnP", "Often exploited for DDoS"),
                    5353: ("mDNS", "Multicast DNS should be limited to local network"),
                    11211: ("Memcached", "Should never be exposed to internet")
                }
                
                if dst_port in restricted_services:
                    service, recommendation = restricted_services[dst_port]
                    
                    # Special handling for DNS
                    if dst_port == 53:
                        # Check if going to authorized DNS servers
                        for p in stack:
                            if p.get("name") == "IPv4":
                                dst_ip = p.get("config", {}).get("dst_ip", "")
                                # Example: only allow 8.8.8.8, 8.8.4.4, or internal 10.0.0.x
                                if not (dst_ip in ["8.8.8.8", "8.8.4.4"] or dst_ip.startswith("10.0.0.")):
                                    return ValidationResult(
                                        is_valid=False,
                                        severity=ValidationSeverity.WARNING,
                                        category=ValidationCategory.SECURITY,
                                        message=f"DNS query to unauthorized server {dst_ip}",
                                        protocol_name="UDP",
                                        suggested_fix="Use authorized DNS servers only",
                                        error_code="POLICY_UNAUTHORIZED_DNS"
                                    )
                    else:
                        return ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.WARNING,
                            category=ValidationCategory.SECURITY,
                            message=f"Restricted UDP service {service} on port {dst_port}",
                            protocol_name="UDP",
                            field_name="dst_port",
                            suggested_fix=recommendation,
                            error_code=f"POLICY_RESTRICTED_UDP_{dst_port}"
                        )
        return None
    
    def _check_udp_amplification_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check for UDP amplification attack vectors."""
        for protocol in stack:
            if protocol.get("name") == "UDP":
                config = protocol.get("config", {})
                dst_port = config.get("dst_port", 0)
                
                # Ports commonly used in amplification attacks
                amplification_ports = {
                    19: ("Chargen", 358.8),
                    53: ("DNS", 28.7),
                    111: ("RPC", 7.0),
                    123: ("NTP", 556.9),
                    137: ("NetBIOS", 3.8),
                    161: ("SNMP", 6.3),
                    389: ("LDAP", 46.0),
                    1900: ("SSDP", 30.8),
                    11211: ("Memcached", 10000.0)
                }
                
                if dst_port in amplification_ports:
                    service, amplification_factor = amplification_ports[dst_port]
                    
                    # Check if source IP might be spoofed (simplified check)
                    for p in stack:
                        if p.get("name") == "IPv4":
                            src_ip = p.get("config", {}).get("src_ip", "")
                            # Check for obviously spoofed addresses
                            if src_ip.startswith(("0.", "255.", "224.")):
                                return ValidationResult(
                                    is_valid=False,
                                    severity=ValidationSeverity.CRITICAL,
                                    category=ValidationCategory.SECURITY,
                                    message=f"Potential amplification attack: {service} (factor {amplification_factor}x) with suspicious source IP",
                                    protocol_name="UDP",
                                    suggested_fix="Implement rate limiting and source IP validation",
                                    error_code="POLICY_AMPLIFICATION_ATTACK"
                                )
                    
                    if amplification_factor > 100:
                        return ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.WARNING,
                            category=ValidationCategory.SECURITY,
                            message=f"High amplification risk service {service} (factor {amplification_factor}x)",
                            protocol_name="UDP",
                            suggested_fix="Implement strict rate limiting for this service",
                            error_code="POLICY_HIGH_AMPLIFICATION_RISK"
                        )
        return None
    
    def _check_udp_fragmentation_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Check UDP fragmentation policies."""
        for protocol in stack:
            if protocol.get("name") == "UDP":
                config = protocol.get("config", {})
                length = config.get("length", 0)
                
                # Check for excessive UDP packet size that would cause fragmentation
                # MTU is typically 1500, minus IP header (20) and UDP header (8)
                if length > 1472:
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.SECURITY,
                        message=f"UDP packet size {length} will cause fragmentation",
                        protocol_name="UDP",
                        field_name="length",
                        suggested_fix="Keep UDP packets under 1472 bytes to avoid fragmentation",
                        error_code="POLICY_UDP_FRAGMENTATION"
                    )
                
                # Check for suspicious tiny fragments
                if 0 < length < 8:
                    return ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.SECURITY,
                        message=f"Suspiciously small UDP packet size: {length}",
                        protocol_name="UDP",
                        field_name="length",
                        suggested_fix="UDP packets should be at least 8 bytes (header size)",
                        error_code="POLICY_UDP_TINY_FRAGMENT"
                    )
        return None

    # === BUILT-IN POLICY IMPLEMENTATIONS (original ones) ===

    def _check_http_encryption_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Policy: HTTP must have TLS/HTTPS."""
        protocols = [p.get("name", "").split()[0] for p in stack]
        
        if "HTTP" in protocols and "HTTPS" not in protocols:
            # Check if TLS is present
            has_tls = any(p in protocols for p in ["TLS", "SSL"])
            if not has_tls:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.SECURITY,
                    message="HTTP detected without encryption (TLS/HTTPS)",
                    protocol_name="HTTP",
                    suggested_fix="Use HTTPS or add TLS layer",
                    error_code="POLICY_NO_CLEAR_HTTP"
                )
        return None

    def _check_legacy_protocols_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Policy: Block legacy insecure protocols."""
        protocols = [p.get("name", "").split()[0] for p in stack]
        
        forbidden = {
            "TELNET": "Use SSH instead",
            "FTP": "Use SFTP or FTPS instead",
            "RLOGIN": "Use SSH instead",
            "TFTP": "Use secure file transfer protocol"
        }
        
        for protocol, suggestion in forbidden.items():
            if protocol in protocols:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.SECURITY,
                    message=f"Legacy insecure protocol {protocol} is not allowed",
                    protocol_name=protocol,
                    suggested_fix=suggestion,
                    error_code=f"POLICY_FORBIDDEN_{protocol}"
                )
        return None

    def _check_automotive_security_policy(self, stack: List[Dict[str, Any]]) -> Optional[ValidationResult]:
        """Policy: Automotive protocols need security."""
        protocols = [p.get("name", "").split()[0] for p in stack]
        
        automotive_protocols = ["DoIP", "UDS", "SOME/IP"]
        security_protocols = ["TLS", "SecOC", "IPSec"]
        
        has_automotive = any(p in protocols for p in automotive_protocols)
        has_security = any(p in protocols for p in security_protocols)
        
        if has_automotive and not has_security:
            affected = [p for p in automotive_protocols if p in protocols]
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.SECURITY,
                message=f"Automotive protocol(s) {affected} detected without security layer",
                protocol_name=affected[0] if affected else "Automotive",
                suggested_fix="Add TLS, SecOC, or IPSec for secure communication",
                error_code="POLICY_AUTOMOTIVE_NO_SECURITY"
            )
        return None

    def register_network_policy(self, policy: NetworkPolicy) -> None:
        """Register a network policy - can be called externally."""
        self._network_policies[policy.name] = policy
        self.logger.debug(f"Registered network policy: {policy.name}")

    def unregister_network_policy(self, name: str) -> None:
        """Remove a network policy."""
        if name in self._network_policies:
            del self._network_policies[name]
            self.logger.debug(f"Unregistered network policy: {name}")

    def set_network_policies_enabled(self, enabled: bool) -> None:
        """Enable/disable all network policies."""
        self._enable_network_policies = enabled

    def _check_network_policies(self, stack: List[Dict[str, Any]]) -> List[ValidationResult]:
        """Check all registered network policies - integrates seamlessly."""
        if not self._enable_network_policies:
            return []
        
        results = []
        
        # Sort by priority
        sorted_policies = sorted(
            self._network_policies.values(),
            key=lambda p: p.priority,
            reverse=True
        )
        
        for policy in sorted_policies:
            if not policy.enabled:
                continue
                
            try:
                result = policy.check_function(stack)
                if result:
                    # Ensure error code includes POLICY prefix
                    if not result.error_code or not result.error_code.startswith("POLICY_"):
                        result.error_code = f"POLICY_{policy.name}"
                    results.append(result)
                    
                    # Update statistics
                    with self._stats_lock:
                        self._statistics.policy_violations += 1
            except Exception as e:
                self.logger.error(f"Policy {policy.name} check failed: {e}")
        
        return results

    # === DYNAMIC POLICY LOADER ===

    def load_network_policies_from_dict(self, policies_config: Dict[str, Any]) -> None:
        """Load policies from configuration dict - for external config files."""
        for policy_name, policy_def in policies_config.items():
            if "enabled" in policy_def and not policy_def["enabled"]:
                continue
                
            # Create lambda from rule definition
            rules = policy_def.get("rules", [])
            
            def make_checker(rules_list):
                def check(stack):
                    protocols = [p.get("name", "").split()[0] for p in stack]
                    for rule in rules_list:
                        if rule["type"] == "forbidden":
                            if rule["protocol"] in protocols:
                                return ValidationResult(
                                    is_valid=False,
                                    severity=ValidationSeverity[rule.get("severity", "ERROR")],
                                    category=ValidationCategory.SECURITY,
                                    message=rule.get("message", f"{rule['protocol']} is forbidden"),
                                    protocol_name=rule["protocol"],
                                    suggested_fix=rule.get("fix", "Remove this protocol"),
                                    error_code=f"POLICY_{policy_name}"
                                )
                        elif rule["type"] == "requires":
                            if rule["protocol"] in protocols:
                                required = rule["requires"]
                                if not any(req in protocols for req in required):
                                    return ValidationResult(
                                        is_valid=False,
                                        severity=ValidationSeverity[rule.get("severity", "WARNING")],
                                        category=ValidationCategory.SECURITY,
                                        message=rule.get("message", f"{rule['protocol']} requires {required}"),
                                        protocol_name=rule["protocol"],
                                        suggested_fix=rule.get("fix", f"Add one of {required}"),
                                        error_code=f"POLICY_{policy_name}"
                                    )
                    return None
                return check
            
            policy = NetworkPolicy(
                name=policy_name,
                description=policy_def.get("description", ""),
                check_function=make_checker(rules),
                priority=policy_def.get("priority", 0)
            )
            
            self.register_network_policy(policy)
    
    # === PLUGIN SYSTEM ===
    
    def register_plugin(self, plugin: ValidationPlugin) -> None:
        """
        Register a validation plugin.
        
        Args:
            plugin: ValidationPlugin instance
        """
        try:
            plugin_info = plugin.get_plugin_info()
            plugin_name = plugin_info.get('name', 'unknown')
            
            # Register supported protocols
            for protocol in plugin.get_supported_protocols():
                self._plugins[protocol] = plugin
                self.logger.debug(f"Registered plugin '{plugin_name}' for protocol '{protocol}'")
            
            self.logger.info(f"Plugin '{plugin_name}' registered successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to register plugin: {e}")
    
    def unregister_plugin(self, protocol_name: str) -> None:
        """
        Unregister a plugin for a specific protocol.
        
        Args:
            protocol_name: Name of the protocol
        """
        if protocol_name in self._plugins:
            del self._plugins[protocol_name]
            self.logger.debug(f"Unregistered plugin for protocol '{protocol_name}'")
    
    def get_registered_plugins(self) -> Dict[str, str]:
        """Get mapping of protocols to their plugin names."""
        result = {}
        for protocol, plugin in self._plugins.items():
            try:
                plugin_info = plugin.get_plugin_info()
                result[protocol] = plugin_info.get('name', 'unknown')
            except Exception:
                result[protocol] = 'error'
        return result
    
    # === ASYNC VALIDATION METHODS ===
    
    async def validate_protocol_stack_async(self, stack: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Asynchronously validate the protocol stack.
        
        Args:
            stack: List of protocol dictionaries
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            with self._stats_lock:
                self._statistics.async_validations += 1
            
            # Run validation in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, 
                self.validate_protocol_stack, 
                stack
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Async stack validation error: {e}")
            return (False, f"Async validation error: {e}")
    
    async def validate_large_stack_batch(self, stacks: List[List[Dict[str, Any]]]) -> List[Tuple[bool, str]]:
        """
        Validate multiple stacks in parallel.
        
        Args:
            stacks: List of protocol stacks to validate
            
        Returns:
            List of validation results
        """
        tasks = [self.validate_protocol_stack_async(stack) for stack in stacks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                final_results.append((False, f"Validation exception: {result}"))
            else:
                final_results.append(result)
        
        return final_results
    
    # === CONFIGURATION METHODS ===
    
    def set_strict_validation(self, strict: bool) -> None:
        """
        Set strict validation mode.
        
        Args:
            strict: Whether to use strict validation (errors vs warnings)
        """
        self._strict_validation = strict
        self.logger.info(f"Strict validation {'enabled' if strict else 'disabled'}")
    
    def is_strict_validation(self) -> bool:
        """Check if strict validation is enabled."""
        return self._strict_validation
    
    def enable_dependency_warnings(self, enable: bool) -> None:
        """Enable or disable dependency warnings in non-strict mode."""
        self._enable_dependency_warnings = enable
        self.logger.debug(f"Dependency warnings {'enabled' if enable else 'disabled'}")
    
    def set_max_stack_depth(self, depth: int) -> None:
        """Set maximum allowed stack depth."""
        if depth > 0:
            self._max_stack_depth = depth
            self.logger.debug(f"Maximum stack depth set to {depth}")
    
    def clear_cache(self) -> None:
        """Clear the validation cache."""
        with self._cache_lock:
            if self._validation_cache is not None:
                self._validation_cache.clear()
                self.logger.debug("Validation cache cleared")
    
    def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration to dictionary."""
        return {
            "strict_validation": self._strict_validation,
            "enable_caching": self._enable_caching,
            "enable_dependency_warnings": self._enable_dependency_warnings,
            "max_stack_depth": self._max_stack_depth,
            "max_workers": self._max_workers,
            "protocol_dependencies": self._protocol_dependencies.copy(),
            "protocol_exclusions": self._protocol_exclusions.copy(),
            "preferred_order": self._preferred_order.copy(),
            "cache_ttl": self._cache_ttl,
            "network_policies_enabled": self._enable_network_policies,
            "network_policies_count": len(self._network_policies),
            "active_policies": [name for name, p in self._network_policies.items() if p.enabled]
        }
    
    def import_configuration(self, config: Dict[str, Any]) -> None:
        """Import configuration from dictionary."""
        try:
            if "strict_validation" in config:
                self._strict_validation = config["strict_validation"]
            if "enable_dependency_warnings" in config:
                self._enable_dependency_warnings = config["enable_dependency_warnings"]
            if "max_stack_depth" in config:
                self._max_stack_depth = config["max_stack_depth"]
            if "protocol_dependencies" in config:
                self._protocol_dependencies = config["protocol_dependencies"]
            if "protocol_exclusions" in config:
                self._protocol_exclusions = config["protocol_exclusions"]
            if "preferred_order" in config:
                self._preferred_order = config["preferred_order"]
            if "cache_ttl" in config:
                self._cache_ttl = config["cache_ttl"]
            if "network_policies_enabled" in config:
                self._enable_network_policies = config["network_policies_enabled"]
            
            self.logger.info("Configuration imported successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to import configuration: {e}")
    
    def save_configuration_to_file(self, filepath: str) -> None:
        """Save configuration to JSON file."""
        try:
            config = self.export_configuration()
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            self.logger.info(f"Configuration saved to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
    
    def load_configuration_from_file(self, filepath: str) -> None:
        """Load configuration from JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.import_configuration(config)
            self.logger.info(f"Configuration loaded from {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
    
    # === MAIN VALIDATION METHODS ===
    
    def validate_protocol_stack(self, stack: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Validate the protocol stack order and dependencies with enhanced checking.
        
        Args:
            stack: List of protocol dictionaries with 'name' and 'config' keys
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        start_time = time.time()
        
        try:
            with self._stats_lock:
                self._statistics.total_validations += 1
                self._statistics.dependency_checks += 1
            
            # Check cache first
            cache_key = self._generate_stack_cache_key(stack)
            if self._enable_caching and cache_key in self._validation_cache:
                with self._cache_lock:
                    cached_result = self._validation_cache[cache_key]
                    if time.time() - cached_result['timestamp'] < self._cache_ttl:
                        with self._stats_lock:
                            self._statistics.cache_hits += 1
                        return cached_result['result']
                    else:
                        # Cache expired
                        del self._validation_cache[cache_key]
            
            with self._stats_lock:
                self._statistics.cache_misses += 1
            
            # Validate stack
            validation_results = []
            
            # Basic checks
            if not stack:
                result = (True, "")
                self._cache_result(cache_key, result)
                return result
            
            if len(stack) > self._max_stack_depth:
                error_msg = f"Stack depth {len(stack)} exceeds maximum {self._max_stack_depth}"
                result = (False, error_msg)
                self._cache_result(cache_key, result)
                return result
            
            # Extract protocol names
            stack_protocols = [p.get("name", "").split(" ")[0] for p in stack]
            
            # Check for duplicate protocols
            duplicate_result = self._check_duplicate_protocols(stack_protocols)
            if duplicate_result:
                validation_results.append(duplicate_result)
            
            # Check protocol dependencies
            dependency_results = self._check_protocol_dependencies(stack_protocols)
            validation_results.extend(dependency_results)
            
            # Check mutual exclusions
            exclusion_results = self._check_mutual_exclusions(stack_protocols)
            validation_results.extend(exclusion_results)
            
            # Check protocol order optimality
            order_results = self._check_protocol_order(stack_protocols)
            validation_results.extend(order_results)
            
            # Check individual protocol configurations
            config_results = self._validate_stack_configurations(stack)
            validation_results.extend(config_results)
            
            # Security validation
            security_results = self._check_security_issues(stack)
            validation_results.extend(security_results)
            
            # Check network policies (zero-impact injection)
            policy_results = self._check_network_policies(stack)
            validation_results.extend(policy_results)
            
            # Analyze results
            has_errors = any(r.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] 
                           for r in validation_results)
            has_warnings = any(r.severity == ValidationSeverity.WARNING for r in validation_results)
            
            # In strict mode, warnings become errors
            if self._strict_validation and has_warnings:
                has_errors = True
            
            # Generate final message
            if has_errors:
                error_messages = [r.message for r in validation_results 
                                if r.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] or
                                   (self._strict_validation and r.severity == ValidationSeverity.WARNING)]
                final_message = "; ".join(error_messages)
                with self._stats_lock:
                    self._statistics.failed_validations += 1
                    self._statistics.errors_found += len([r for r in validation_results 
                                                        if r.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]])
            else:
                if has_warnings:
                    warning_messages = [r.message for r in validation_results 
                                      if r.severity == ValidationSeverity.WARNING]
                    final_message = f"Warnings: {'; '.join(warning_messages)}"
                    with self._stats_lock:
                        self._statistics.warnings_issued += len(warning_messages)
                else:
                    final_message = ""
                with self._stats_lock:
                    self._statistics.successful_validations += 1
            
            # Update timing statistics
            validation_time = time.time() - start_time
            self._update_timing_statistics(validation_time)
            
            result = (not has_errors, final_message)
            self._cache_result(cache_key, result)
            
            self.logger.debug(f"Stack validation completed in {validation_time:.3f}s: {'PASS' if result[0] else 'FAIL'}")
            return result
            
        except Exception as e:
            with self._stats_lock:
                self._statistics.failed_validations += 1
            error_msg = f"Stack validation error: {e}"
            self.logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    def validate_protocol_config(self, protocol_name: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a protocol's configuration with comprehensive checking.
        
        Args:
            protocol_name: Name of the protocol
            config: Protocol configuration to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        start_time = time.time()
        
        try:
            with self._stats_lock:
                self._statistics.total_validations += 1
            
            # Check cache
            cache_key = f"{protocol_name}:{self._hash_config(config)}"
            if self._enable_caching and cache_key in self._validation_cache:
                with self._cache_lock:
                    cached_result = self._validation_cache[cache_key]
                    if time.time() - cached_result['timestamp'] < self._cache_ttl:
                        with self._stats_lock:
                            self._statistics.cache_hits += 1
                        return cached_result['result']
                    else:
                        del self._validation_cache[cache_key]
            
            with self._stats_lock:
                self._statistics.cache_misses += 1
            
            # Get base protocol name
            base_name = protocol_name.split(" ")[0]
            
            # Check for plugin validator first
            if base_name in self._plugins:
                try:
                    plugin = self._plugins[base_name]
                    validation_results = plugin.validate(config)
                    with self._stats_lock:
                        self._statistics.plugin_validations += 1
                except Exception as e:
                    self.logger.error(f"Plugin validation error for {base_name}: {e}")
                    validation_results = [ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.CUSTOM,
                        message=f"Plugin validation failed: {e}",
                        protocol_name=base_name
                    )]
            # Use built-in validator
            elif base_name in self._protocol_validators:
                validator = self._protocol_validators[base_name]
                try:
                    validation_results = validator(config)
                    
                    # Handle legacy format
                    if isinstance(validation_results, tuple) and len(validation_results) == 2:
                        is_valid, message = validation_results
                        if not is_valid:
                            validation_results = [ValidationResult(
                                is_valid=False,
                                severity=ValidationSeverity.ERROR,
                                category=ValidationCategory.CONFIGURATION,
                                message=message,
                                protocol_name=base_name
                            )]
                        else:
                            validation_results = []
                    
                except Exception as e:
                    error_msg = f"Error validating {base_name} config: {str(e)}"
                    self.logger.error(error_msg, exc_info=True)
                    validation_results = [ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.CONFIGURATION,
                        message=error_msg,
                        protocol_name=base_name
                    )]
            else:
                # No specific validator available
                if self._strict_validation:
                    message = f"No validator available for protocol: {base_name}"
                    self.logger.warning(message)
                    validation_results = [ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.CONFIGURATION,
                        message=message,
                        protocol_name=base_name
                    )]
                else:
                    validation_results = []
            
            # Process results
            has_errors = any(r.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] 
                           for r in validation_results)
            has_warnings = any(r.severity == ValidationSeverity.WARNING for r in validation_results)
            
            if self._strict_validation and has_warnings:
                has_errors = True
            
            if has_errors:
                error_messages = [r.message for r in validation_results 
                                if r.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] or
                                   (self._strict_validation and r.severity == ValidationSeverity.WARNING)]
                message = "; ".join(error_messages)
                is_valid = False
                with self._stats_lock:
                    self._statistics.failed_validations += 1
                    self._statistics.errors_found += len([r for r in validation_results 
                                                        if r.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]])
            else:
                if has_warnings:
                    warning_messages = [r.message for r in validation_results 
                                      if r.severity == ValidationSeverity.WARNING]
                    message = f"Warnings: {'; '.join(warning_messages)}"
                    with self._stats_lock:
                        self._statistics.warnings_issued += len(warning_messages)
                else:
                    message = ""
                is_valid = True
                with self._stats_lock:
                    self._statistics.successful_validations += 1
            
            result = (is_valid, message)
            
            # Update timing
            validation_time = time.time() - start_time
            self._update_timing_statistics(validation_time)
            
            # Cache result
            self._cache_result(cache_key, result)
            
            return result
            
        except Exception as e:
            with self._stats_lock:
                self._statistics.failed_validations += 1
            error_msg = f"Protocol validation error: {e}"
            self.logger.error(error_msg, exc_info=True)
            return (False, error_msg)
    
    # === ADDITIONAL PROTOCOL VALIDATORS ===
    
    def _validate_vlan_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate VLAN configuration."""
        results = []
        
        # Validate VLAN ID
        if "vlan_id" in config:
            vlan_id = config["vlan_id"]
            if not isinstance(vlan_id, int) or vlan_id < 0 or vlan_id > 4094:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="VLAN ID must be between 0 and 4094",
                    field_name="vlan_id",
                    suggested_fix="Use valid VLAN ID (1-4094 for normal VLANs)",
                    error_code="OUT_OF_RANGE"
                ))
            elif vlan_id == 0:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONFIGURATION,
                    message="VLAN ID 0 is reserved for priority tagging",
                    field_name="vlan_id",
                    suggested_fix="Use VLAN ID 1-4094 for normal VLANs",
                    error_code="RESERVED_VLAN"
                ))
            elif vlan_id == 4095:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONFIGURATION,
                    message="VLAN ID 4095 is reserved",
                    field_name="vlan_id",
                    suggested_fix="Use VLAN ID 1-4094 for normal VLANs",
                    error_code="RESERVED_VLAN"
                ))
        
        # Validate priority
        if "priority" in config:
            priority = config["priority"]
            if not isinstance(priority, int) or priority < 0 or priority > 7:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="VLAN priority must be between 0 and 7",
                    field_name="priority",
                    suggested_fix="Use priority value 0-7 (0=lowest, 7=highest)",
                    error_code="OUT_OF_RANGE"
                ))
        
        return results
    
    def _validate_arp_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate ARP configuration."""
        results = []
        
        # Validate operation
        if "operation" in config:
            operation = config["operation"]
            if not isinstance(operation, int) or operation not in [1, 2]:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message="ARP operation must be 1 (request) or 2 (reply)",
                    field_name="operation",
                    suggested_fix="Use 1 for ARP request, 2 for ARP reply",
                    error_code="INVALID_ARP_OPERATION"
                ))
        
        # Validate hardware type
        if "hw_type" in config:
            hw_type = config["hw_type"]
            if not isinstance(hw_type, int) or hw_type != 1:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Non-standard hardware type: {hw_type} (expected 1 for Ethernet)",
                    field_name="hw_type",
                    suggested_fix="Use hardware type 1 for Ethernet",
                    error_code="NON_STANDARD_HW_TYPE"
                ))
        
        # Validate protocol type
        if "proto_type" in config:
            proto_type = config["proto_type"]
            if not isinstance(proto_type, int) or proto_type != 0x0800:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Non-standard protocol type: {proto_type:#06x} (expected 0x0800 for IPv4)",
                    field_name="proto_type",
                    suggested_fix="Use protocol type 0x0800 for IPv4",
                    error_code="NON_STANDARD_PROTO_TYPE"
                ))
        
        # Validate MAC addresses
        mac_fields = ["sender_mac", "target_mac"]
        for field in mac_fields:
            if field in config:
                mac = config[field]
                if isinstance(mac, str):
                    # Simple MAC validation
                    if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', mac):
                        results.append(ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.FORMAT,
                            message=f"Invalid MAC address format for {field}: {mac}",
                            field_name=field,
                            suggested_fix="Use format XX:XX:XX:XX:XX:XX",
                            error_code="INVALID_MAC_FORMAT"
                        ))
        
        # Validate IP addresses
        ip_fields = ["sender_ip", "target_ip"]
        for field in ip_fields:
            if field in config:
                ip = config[field]
                if isinstance(ip, str):
                    # Simple IPv4 validation
                    parts = ip.split('.')
                    if len(parts) != 4:
                        results.append(ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.FORMAT,
                            message=f"Invalid IP address format for {field}: {ip}",
                            field_name=field,
                            suggested_fix="Use format X.X.X.X",
                            error_code="INVALID_IP_FORMAT"
                        ))
        
        return results
    
    def _validate_https_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate HTTPS configuration."""
        results = []
        
        # Inherit HTTP validation
        results.extend(self._validate_http_config(config))
        
        # HTTPS specific validation
        if "tls_version" in config:
            tls_version = config["tls_version"]
            supported_versions = ["1.0", "1.1", "1.2", "1.3"]
            if not isinstance(tls_version, str) or tls_version not in supported_versions:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.SECURITY,
                    message=f"Invalid TLS version: {tls_version}",
                    field_name="tls_version",
                    suggested_fix=f"Use one of: {', '.join(supported_versions)}",
                    error_code="INVALID_TLS_VERSION"
                ))
            elif tls_version in ["1.0", "1.1"]:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.SECURITY,
                    message=f"TLS version {tls_version} is deprecated and insecure",
                    field_name="tls_version",
                    suggested_fix="Use TLS 1.2 or 1.3 for better security",
                    error_code="DEPRECATED_TLS_VERSION"
                ))
        
        # Check certificate validation
        if "verify_cert" in config and not config["verify_cert"]:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.SECURITY,
                message="Certificate verification is disabled",
                field_name="verify_cert",
                suggested_fix="Enable certificate verification for security",
                error_code="CERT_VERIFICATION_DISABLED"
            ))
        
        return results
    
    def _validate_ftp_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate FTP configuration."""
        results = []
        
        # Check for passive/active mode
        if "mode" in config:
            mode = config["mode"]
            if isinstance(mode, str) and mode.lower() not in ["passive", "active"]:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Invalid FTP mode: {mode}",
                    field_name="mode",
                    suggested_fix="Use 'passive' or 'active'",
                    error_code="INVALID_FTP_MODE"
                ))
        
        # Security warning for plain FTP
        if config.get("encryption", "none").lower() == "none":
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.SECURITY,
                message="Plain FTP transmits credentials in clear text",
                suggested_fix="Consider using FTPS or SFTP for encrypted transfer",
                error_code="INSECURE_FTP"
            ))
        
        return results
    
    def _validate_smtp_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate SMTP configuration."""
        results = []
        
        # Validate port
        if "port" in config:
            port = config["port"]
            standard_ports = [25, 465, 587, 2525]
            if not isinstance(port, int) or port < 1 or port > 65535:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="SMTP port must be between 1 and 65535",
                    field_name="port",
                    suggested_fix="Use valid port number",
                    error_code="OUT_OF_RANGE"
                ))
            elif port not in standard_ports:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Non-standard SMTP port: {port}",
                    field_name="port",
                    suggested_fix=f"Standard ports are: {standard_ports}",
                    error_code="NON_STANDARD_PORT"
                ))
        
        # Check authentication
        if "auth_method" in config:
            auth_method = config["auth_method"]
            valid_methods = ["PLAIN", "LOGIN", "CRAM-MD5", "DIGEST-MD5", "NTLM", "OAUTH2"]
            if not isinstance(auth_method, str) or auth_method.upper() not in valid_methods:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Invalid SMTP auth method: {auth_method}",
                    field_name="auth_method",
                    suggested_fix=f"Use one of: {', '.join(valid_methods)}",
                    error_code="INVALID_AUTH_METHOD"
                ))
        
        return results
    
    def _validate_dhcp_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate DHCP configuration."""
        results = []
        
        # Validate message type
        if "message_type" in config:
            msg_type = config["message_type"]
            valid_types = [1, 2, 3, 4, 5, 6, 7, 8]  # DISCOVER, OFFER, REQUEST, etc.
            if not isinstance(msg_type, int) or msg_type not in valid_types:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message=f"Invalid DHCP message type: {msg_type}",
                    field_name="message_type",
                    suggested_fix=f"Use one of: {valid_types}",
                    error_code="INVALID_MESSAGE_TYPE"
                ))
        
        # Validate lease time
        if "lease_time" in config:
            lease_time = config["lease_time"]
            if not isinstance(lease_time, int) or lease_time < 0:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="DHCP lease time must be a non-negative integer",
                    field_name="lease_time",
                    suggested_fix="Use positive integer for lease time in seconds",
                    error_code="INVALID_LEASE_TIME"
                ))
        
        return results
    
    def _validate_snmp_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate SNMP configuration."""
        results = []
        
        # Validate version
        if "version" in config:
            version = config["version"]
            valid_versions = ["1", "2c", "3"]
            if not isinstance(version, str) or version not in valid_versions:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Invalid SNMP version: {version}",
                    field_name="version",
                    suggested_fix=f"Use one of: {', '.join(valid_versions)}",
                    error_code="INVALID_SNMP_VERSION"
                ))
            elif version in ["1", "2c"]:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.SECURITY,
                    message=f"SNMP version {version} has security limitations",
                    field_name="version",
                    suggested_fix="Consider using SNMP v3 for better security",
                    error_code="WEAK_SNMP_VERSION"
                ))
        
        # Validate community string for v1/v2c
        version = config.get("version", "1")
        if version in ["1", "2c"] and "community" in config:
            community = config["community"]
            if isinstance(community, str) and community.lower() in ["public", "private"]:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.SECURITY,
                    message=f"Default community string '{community}' is insecure",
                    field_name="community",
                    suggested_fix="Use a strong, unique community string",
                    error_code="DEFAULT_COMMUNITY"
                ))
        
        return results
    
    def _validate_j1939_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate J1939 configuration."""
        results = []
        
        # Inherit CAN validation
        results.extend(self._validate_can_config(config))
        
        # Validate PGN (Parameter Group Number)
        if "pgn" in config:
            pgn = config["pgn"]
            if not isinstance(pgn, int) or pgn < 0 or pgn > 0x1FFFF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="J1939 PGN must be a 17-bit integer (0-131071)",
                    field_name="pgn",
                    suggested_fix="Use value between 0 and 0x1FFFF",
                    error_code="OUT_OF_RANGE"
                ))
        
        # Validate source address
        if "source_address" in config:
            sa = config["source_address"]
            if not isinstance(sa, int) or sa < 0 or sa > 253:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="J1939 source address must be between 0 and 253",
                    field_name="source_address",
                    suggested_fix="Use value between 0 and 253",
                    error_code="OUT_OF_RANGE"
                ))
        
        # Validate priority
        if "priority" in config:
            priority = config["priority"]
            if not isinstance(priority, int) or priority < 0 or priority > 7:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="J1939 priority must be between 0 and 7",
                    field_name="priority",
                    suggested_fix="Use value between 0 and 7",
                    error_code="OUT_OF_RANGE"
                ))
        
        return results
    
    def _validate_uds_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate UDS (Unified Diagnostic Services) configuration."""
        results = []
        
        # Validate service ID
        if "service_id" in config:
            sid = config["service_id"]
            if not isinstance(sid, int) or sid < 0 or sid > 0xFF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="UDS service ID must be an 8-bit integer (0-255)",
                    field_name="service_id",
                    suggested_fix="Use value between 0 and 255",
                    error_code="OUT_OF_RANGE"
                ))
        
        # Validate common service IDs
        common_services = {
            0x10: "DiagnosticSessionControl",
            0x11: "ECUReset",
            0x22: "ReadDataByIdentifier",
            0x23: "ReadMemoryByAddress",
            0x27: "SecurityAccess",
            0x2E: "WriteDataByIdentifier",
            0x31: "RoutineControl",
            0x34: "RequestDownload",
            0x36: "TransferData",
            0x37: "RequestTransferExit"
        }
        
        if "service_id" in config:
            sid = config["service_id"]
            if isinstance(sid, int) and sid not in common_services:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.COMPATIBILITY,
                    message=f"Non-standard UDS service ID: {sid:#04x}",
                    field_name="service_id",
                    suggested_fix=f"Common services: {list(common_services.keys())}",
                    error_code="NON_STANDARD_SERVICE"
                ))
        
        # Validate addressing
        if "target_address" in config:
            addr = config["target_address"]
            if not isinstance(addr, int) or addr < 0 or addr > 0x7FF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="UDS target address must be an 11-bit integer (0-2047)",
                    field_name="target_address",
                    suggested_fix="Use value between 0 and 0x7FF",
                    error_code="OUT_OF_RANGE"
                ))
        
        return results
    
    # === SECURITY VALIDATION ===
    
    def _check_security_issues(self, stack: List[Dict[str, Any]]) -> List[ValidationResult]:
        """Check for security issues in protocol stack."""
        results = []
        
        # Check for unencrypted protocols
        unencrypted_protocols = ["HTTP", "FTP", "TELNET", "SNMP"]
        for protocol_dict in stack:
            protocol_name = protocol_dict.get("name", "").split(" ")[0]
            if protocol_name in unencrypted_protocols:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.SECURITY,
                    message=f"Protocol {protocol_name} transmits data in clear text",
                    protocol_name=protocol_name,
                    suggested_fix=f"Consider using encrypted alternative (HTTPS, FTPS, SSH, SNMPv3)",
                    error_code="UNENCRYPTED_PROTOCOL"
                ))
        
        # Check for deprecated protocols
        deprecated_protocols = {"SSL": "TLS", "WEP": "WPA2/WPA3", "MD5": "SHA-256"}
        for protocol_dict in stack:
            protocol_name = protocol_dict.get("name", "").split(" ")[0]
            if protocol_name in deprecated_protocols:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.SECURITY,
                    message=f"Protocol {protocol_name} is deprecated and insecure",
                    protocol_name=protocol_name,
                    suggested_fix=f"Use {deprecated_protocols[protocol_name]} instead",
                    error_code="DEPRECATED_PROTOCOL"
                ))
        
        return results
    
    # === EXISTING VALIDATION METHODS (keeping the original ones) ===
    
    def _check_protocol_dependencies(self, stack_protocols: List[str]) -> List[ValidationResult]:
        """Check protocol dependencies in the stack."""
        results = []
        
        for i, protocol in enumerate(stack_protocols):
            if protocol in self._protocol_dependencies:
                required_deps = self._protocol_dependencies[protocol]
                
                if required_deps:  # Only check if dependencies exist
                    # Check if any required dependency exists before this protocol
                    found_dependency = False
                    for req in required_deps:
                        if req in stack_protocols[:i]:
                            found_dependency = True
                            break
                    
                    if not found_dependency:
                        severity = ValidationSeverity.ERROR if self._strict_validation else ValidationSeverity.WARNING
                        suggested_fix = f"Add one of {required_deps} before {protocol}"
                        
                        results.append(ValidationResult(
                            is_valid=False,
                            severity=severity,
                            category=ValidationCategory.DEPENDENCY,
                            message=f"Protocol {protocol} requires one of {required_deps} before it",
                            protocol_name=protocol,
                            suggested_fix=suggested_fix,
                            error_code="MISSING_DEPENDENCY",
                            context={
                                'protocol_index': i,
                                'required_dependencies': required_deps,
                                'available_protocols': stack_protocols[:i]
                            }
                        ))
        
        return results
    
    def _check_duplicate_protocols(self, stack_protocols: List[str]) -> Optional[ValidationResult]:
        """Check for duplicate protocols in the stack."""
        seen = set()
        for protocol in stack_protocols:
            if protocol in seen:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Duplicate protocol found: {protocol}",
                    protocol_name=protocol,
                    suggested_fix="Remove duplicate protocol",
                    error_code="DUPLICATE_PROTOCOL"
                )
            seen.add(protocol)
        return None
    
    def _check_mutual_exclusions(self, stack_protocols: List[str]) -> List[ValidationResult]:
        """Check for mutually exclusive protocols."""
        results = []
        
        for protocol, exclusions in self._protocol_exclusions.items():
            if protocol in stack_protocols:
                for exclusion in exclusions:
                    if exclusion in stack_protocols:
                        severity = ValidationSeverity.WARNING  # Usually not critical
                        results.append(ValidationResult(
                            is_valid=False,
                            severity=severity,
                            category=ValidationCategory.COMPATIBILITY,
                            message=f"Protocols {protocol} and {exclusion} are typically mutually exclusive",
                            protocol_name=protocol,
                            suggested_fix=f"Consider removing either {protocol} or {exclusion}",
                            error_code="MUTUAL_EXCLUSION",
                            context={'conflicting_protocol': exclusion}
                        ))
        
        return results
    
    def _check_protocol_order(self, stack_protocols: List[str]) -> List[ValidationResult]:
        """Check if protocols are in optimal order."""
        results = []
        
        # Create a mapping of protocol to its preferred position
        position_map = {proto: i for i, proto in enumerate(self._preferred_order)}
        
        # Check each consecutive pair
        for i in range(len(stack_protocols) - 1):
            current_proto = stack_protocols[i]
            next_proto = stack_protocols[i + 1]
            
            current_pos = position_map.get(current_proto, 999)
            next_pos = position_map.get(next_proto, 999)
            
            # If next protocol should come before current protocol
            if next_pos < current_pos:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.PERFORMANCE,
                    message=f"Protocol {next_proto} typically comes before {current_proto} in network stack",
                    protocol_name=current_proto,
                    suggested_fix=f"Consider reordering: place {next_proto} before {current_proto}",
                    error_code="SUBOPTIMAL_ORDER",
                    context={
                        'current_index': i,
                        'next_index': i + 1,
                        'suggested_order': f"{next_proto} before {current_proto}"
                    }
                ))
        
        return results
    
    def _validate_stack_configurations(self, stack: List[Dict[str, Any]]) -> List[ValidationResult]:
        """Validate configurations of all protocols in the stack."""
        results = []
        
        for i, protocol_dict in enumerate(stack):
            protocol_name = protocol_dict.get("name", "")
            config = protocol_dict.get("config", {})
            
            # Validate individual protocol config
            is_valid, message = self.validate_protocol_config(protocol_name, config)
            
            if not is_valid and message:
                # Convert to ValidationResult
                severity = ValidationSeverity.ERROR if "Error" in message else ValidationSeverity.WARNING
                results.append(ValidationResult(
                    is_valid=False,
                    severity=severity,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"{protocol_name}: {message}",
                    protocol_name=protocol_name,
                    context={'protocol_index': i, 'config': config}
                ))
        
        return results
    
    # === PROTOCOL-SPECIFIC VALIDATORS (keeping original ones) ===
    
    def _validate_ethernet_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate Ethernet configuration."""
        results = []
        
        # Check required fields
        required_fields = ["src_mac", "dst_mac"]
        for field in required_fields:
            if field not in config:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Missing required field: {field}",
                    field_name=field,
                    suggested_fix=f"Add {field} to configuration",
                    error_code="MISSING_FIELD"
                ))
                continue
        
        # Validate MAC address format
        mac_regex = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        
        for field in ["src_mac", "dst_mac"]:
            if field in config:
                mac_value = config[field]
                if isinstance(mac_value, str):
                    # Check standard format or compact format
                    if not re.match(mac_regex, mac_value):
                        compact_mac = mac_value.replace(":", "").replace("-", "")
                        if not re.match(r'^[0-9A-Fa-f]{12}$', compact_mac):
                            results.append(ValidationResult(
                                is_valid=False,
                                severity=ValidationSeverity.ERROR,
                                category=ValidationCategory.FORMAT,
                                message=f"Invalid MAC address format for {field}: {mac_value}",
                                field_name=field,
                                suggested_fix="Use format XX:XX:XX:XX:XX:XX or XXXXXXXXXXXX",
                                error_code="INVALID_MAC_FORMAT"
                            ))
        
        # Validate EtherType if present
        if "ether_type" in config:
            ether_type = config["ether_type"]
            if not isinstance(ether_type, int) or ether_type < 0 or ether_type > 0xFFFF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="EtherType must be a 16-bit integer (0-65535)",
                    field_name="ether_type",
                    suggested_fix="Use value between 0 and 65535",
                    error_code="OUT_OF_RANGE"
                ))
        
        return results
    
    def _validate_ipv4_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate IPv4 configuration."""
        results = []
        
        # Check required fields
        required_fields = ["src_ip", "dst_ip"]
        for field in required_fields:
            if field not in config:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Missing required field: {field}",
                    field_name=field,
                    suggested_fix=f"Add {field} to configuration",
                    error_code="MISSING_FIELD"
                ))
        
        # Validate IP address format
        ipv4_regex = r'^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        
        for field in ["src_ip", "dst_ip"]:
            if field in config:
                ip_value = config[field]
                if isinstance(ip_value, str) and not re.match(ipv4_regex, ip_value):
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.FORMAT,
                        message=f"Invalid IPv4 address format for {field}: {ip_value}",
                        field_name=field,
                        suggested_fix="Use format X.X.X.X where X is 0-255",
                        error_code="INVALID_IP_FORMAT"
                    ))
        
        # Validate optional fields
        int_fields = {
            "ttl": (0, 255, "8-bit"),
            "protocol": (0, 255, "8-bit"),
            "version": (4, 4, "IPv4 version"),
            "ihl": (5, 15, "Internet Header Length")
        }
        
        for field, (min_val, max_val, description) in int_fields.items():
            if field in config:
                value = config[field]
                if not isinstance(value, int) or value < min_val or value > max_val:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.RANGE,
                        message=f"{field} must be a {description} integer ({min_val}-{max_val})",
                        field_name=field,
                        suggested_fix=f"Use value between {min_val} and {max_val}",
                        error_code="OUT_OF_RANGE"
                    ))
        
        return results
    
    def _validate_ipv6_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate IPv6 configuration."""
        results = []
        
        # Check required fields
        required_fields = ["src_ip", "dst_ip"]
        for field in required_fields:
            if field not in config:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Missing required field: {field}",
                    field_name=field,
                    suggested_fix=f"Add {field} to configuration",
                    error_code="MISSING_FIELD"
                ))
        
        # IPv6 address validation (simplified)
        ipv6_patterns = [
            r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$',  # Full format
            r'^::$',  # All zeros
            r'^::1$',  # Loopback
            r'^([0-9a-fA-F]{1,4}:){1,7}:$',  # Compressed format ending with ::
            r'^:([0-9a-fA-F]{1,4}:){1,7}$',  # Compressed format starting with ::
            r'^([0-9a-fA-F]{1,4}:){0,6}([0-9a-fA-F]{1,4}:){0,1}([0-9a-fA-F]{1,4})$',  # Mixed
            r'^::([0-9a-fA-F]{1,4}:){0,5}([0-9a-fA-F]{1,4})$'  # Compressed with content
        ]
        
        for field in ["src_ip", "dst_ip"]:
            if field in config:
                ip_value = config[field]
                if isinstance(ip_value, str):
                    valid = any(re.match(pattern, ip_value) for pattern in ipv6_patterns)
                    if not valid:
                        results.append(ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.FORMAT,
                            message=f"Invalid IPv6 address format for {field}: {ip_value}",
                            field_name=field,
                            suggested_fix="Use valid IPv6 format (e.g., 2001:db8::1)",
                            error_code="INVALID_IP_FORMAT"
                        ))
        
        # Validate optional fields
        int_fields = {
            "hop_limit": (0, 255, "8-bit"),
            "next_header": (0, 255, "8-bit"),
            "version": (6, 6, "IPv6 version"),
            "traffic_class": (0, 255, "8-bit")
        }
        
        for field, (min_val, max_val, description) in int_fields.items():
            if field in config:
                value = config[field]
                if not isinstance(value, int) or value < min_val or value > max_val:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.RANGE,
                        message=f"{field} must be a {description} integer ({min_val}-{max_val})",
                        field_name=field,
                        suggested_fix=f"Use value between {min_val} and {max_val}",
                        error_code="OUT_OF_RANGE"
                    ))
        
        return results
    
    def _validate_tcp_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate TCP configuration."""
        results = []
        
        # Check required fields
        required_fields = ["src_port", "dst_port"]
        for field in required_fields:
            if field not in config:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Missing required field: {field}",
                    field_name=field,
                    suggested_fix=f"Add {field} to configuration",
                    error_code="MISSING_FIELD"
                ))
        
        # Validate port ranges
        for field in ["src_port", "dst_port"]:
            if field in config:
                port = config[field]
                if not isinstance(port, int) or port < 1 or port > 65535:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.RANGE,
                        message=f"{field} must be between 1 and 65535",
                        field_name=field,
                        suggested_fix="Use port number between 1 and 65535",
                        error_code="OUT_OF_RANGE"
                    ))
        
        # Validate optional TCP fields
        int_fields = {
            "seq_num": (0, 0xFFFFFFFF, "32-bit sequence number"),
            "ack_num": (0, 0xFFFFFFFF, "32-bit acknowledgment number"),
            "window_size": (0, 65535, "16-bit window size"),
            "urgent_ptr": (0, 65535, "16-bit urgent pointer")
        }
        
        for field, (min_val, max_val, description) in int_fields.items():
            if field in config:
                value = config[field]
                if not isinstance(value, int) or value < min_val or value > max_val:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.RANGE,
                        message=f"{field} must be a {description} ({min_val}-{max_val})",
                        field_name=field,
                        suggested_fix=f"Use value between {min_val} and {max_val}",
                        error_code="OUT_OF_RANGE"
                    ))
        
        return results
    
    def _validate_udp_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate UDP configuration."""
        results = []
        
        # Check required fields
        required_fields = ["src_port", "dst_port"]
        for field in required_fields:
            if field not in config:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Missing required field: {field}",
                    field_name=field,
                    suggested_fix=f"Add {field} to configuration",
                    error_code="MISSING_FIELD"
                ))
        
        # Validate port ranges
        for field in ["src_port", "dst_port"]:
            if field in config:
                port = config[field]
                if not isinstance(port, int) or port < 1 or port > 65535:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.RANGE,
                        message=f"{field} must be between 1 and 65535",
                        field_name=field,
                        suggested_fix="Use port number between 1 and 65535",
                        error_code="OUT_OF_RANGE"
                    ))
        
        # Validate length if present
        if "length" in config:
            length = config["length"]
            if not isinstance(length, int) or length < 8 or length > 65535:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="UDP length must be between 8 and 65535",
                    field_name="length",
                    suggested_fix="Use length between 8 and 65535",
                    error_code="OUT_OF_RANGE"
                ))
        
        return results
    
    def _validate_tecmp_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate TECMP configuration."""
        results = []
        
        # Check required fields
        required_fields = ["device_id", "counter", "version", "message_type", "data_type", "interface_id"]
        for field in required_fields:
            if field not in config:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Missing required field: {field}",
                    field_name=field,
                    suggested_fix=f"Add {field} to configuration",
                    error_code="MISSING_FIELD"
                ))
        
        # Validate numeric fields
        int_fields = {
            "device_id": (0, 0xFFFF, "16-bit device ID"),
            "counter": (0, 0xFFFF, "16-bit counter"),
            "version": (0, 15, "4-bit version"),
            "message_type": (0, 255, "8-bit message type"),
            "data_type": (0, 0xFFFF, "16-bit data type"),
            "interface_id": (0, 0xFFFFFFFF, "32-bit interface ID"),
            "device_flags": (0, 0xFFFF, "16-bit device flags"),
            "data_flags": (0, 0xFFFF, "16-bit data flags")
        }
        
        for field, (min_val, max_val, description) in int_fields.items():
            if field in config:
                value = config[field]
                if not isinstance(value, int) or value < min_val or value > max_val:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.RANGE,
                        message=f"{field} must be a {description} ({min_val}-{max_val})",
                        field_name=field,
                        suggested_fix=f"Use value between {min_val} and {max_val}",
                        error_code="OUT_OF_RANGE"
                    ))
        
        # Validate message type values
        valid_message_types = [0x00, 0x01, 0x02, 0x03, 0x0A]
        if "message_type" in config:
            msg_type = config["message_type"]
            if isinstance(msg_type, int) and msg_type not in valid_message_types:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.COMPATIBILITY,
                    message=f"Unusual message_type: {msg_type:#04x}. Common values are {[hex(x) for x in valid_message_types]}",
                    field_name="message_type",
                    suggested_fix=f"Consider using one of: {[hex(x) for x in valid_message_types]}",
                    error_code="UNUSUAL_VALUE"
                ))
        
        # Validate data type values
        valid_data_types = [0x01, 0x02, 0x03, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x0080]
        if "data_type" in config:
            data_type = config["data_type"]
            if isinstance(data_type, int) and data_type not in valid_data_types:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.COMPATIBILITY,
                    message=f"Unusual data_type: {data_type:#06x}. Common values are {[hex(x) for x in valid_data_types]}",
                    field_name="data_type",
                    suggested_fix=f"Consider using one of: {[hex(x) for x in valid_data_types]}",
                    error_code="UNUSUAL_VALUE"
                ))
        
        return results
    
    def _validate_can_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate CAN configuration."""
        results = []
        
        # Check required fields
        if "can_id" not in config:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.CONFIGURATION,
                message="Missing required field: can_id",
                field_name="can_id",
                suggested_fix="Add can_id to configuration",
                error_code="MISSING_FIELD"
            ))
            return results
        
        # Validate CAN ID based on IDE flag
        can_id = config["can_id"]
        ide = config.get("ide", False)
        
        if ide:
            # Extended CAN ID (29 bits)
            if not isinstance(can_id, int) or can_id < 0 or can_id > 0x1FFFFFFF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="Extended CAN ID must be a 29-bit integer (0-536870911)",
                    field_name="can_id",
                    suggested_fix="Use value between 0 and 0x1FFFFFFF",
                    error_code="OUT_OF_RANGE"
                ))
        else:
            # Standard CAN ID (11 bits)
            if not isinstance(can_id, int) or can_id < 0 or can_id > 0x7FF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="Standard CAN ID must be an 11-bit integer (0-2047)",
                    field_name="can_id",
                    suggested_fix="Use value between 0 and 0x7FF",
                    error_code="OUT_OF_RANGE"
                ))
        
        # Validate DLC
        if "dlc" in config:
            dlc = config["dlc"]
            if not isinstance(dlc, int) or dlc < 0 or dlc > 8:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="DLC must be between 0 and 8",
                    field_name="dlc",
                    suggested_fix="Use DLC value between 0 and 8",
                    error_code="OUT_OF_RANGE"
                ))
        
        return results
    
    def _validate_canfd_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate CAN-FD configuration."""
        results = []
        
        # First validate basic CAN fields
        results.extend(self._validate_can_config(config))
        
        # CAN-FD specific validation
        if "dlc" in config:
            dlc = config["dlc"]
            if isinstance(dlc, int) and dlc > 8:
                # CAN-FD allows DLC up to 15
                if dlc > 15:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.RANGE,
                        message="CAN-FD DLC must be between 0 and 15",
                        field_name="dlc",
                        suggested_fix="Use DLC value between 0 and 15",
                        error_code="OUT_OF_RANGE"
                    ))
        
        # Validate BRS flag
        if "brs" in config and not isinstance(config["brs"], bool):
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.FORMAT,
                message="BRS flag must be a boolean",
                field_name="brs",
                suggested_fix="Use true or false for BRS flag",
                error_code="INVALID_TYPE"
            ))
        
        # Validate ESI flag
        if "esi" in config and not isinstance(config["esi"], bool):
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.FORMAT,
                message="ESI flag must be a boolean",
                field_name="esi",
                suggested_fix="Use true or false for ESI flag",
                error_code="INVALID_TYPE"
            ))
        
        return results
    
    def _validate_flexray_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate FlexRay configuration."""
        results = []
        
        # Check required fields
        required_fields = ["cycle", "channel", "frame_id"]
        for field in required_fields:
            if field not in config:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Missing required field: {field}",
                    field_name=field,
                    suggested_fix=f"Add {field} to configuration",
                    error_code="MISSING_FIELD"
                ))
        
        # Validate numeric fields
        int_fields = {
            "cycle": (0, 63, "6-bit cycle"),
            "channel": (0, 1, "channel (0=A, 1=B)"),
            "frame_id": (0, 2047, "11-bit frame ID"),
            "frame_flags": (0, 0xFFFF, "16-bit frame flags")
        }
        
        for field, (min_val, max_val, description) in int_fields.items():
            if field in config:
                value = config[field]
                if not isinstance(value, int) or value < min_val or value > max_val:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.RANGE,
                        message=f"{field} must be a {description} ({min_val}-{max_val})",
                        field_name=field,
                        suggested_fix=f"Use value between {min_val} and {max_val}",
                        error_code="OUT_OF_RANGE"
                    ))
        
        return results
    
    def _validate_lin_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate LIN configuration."""
        results = []
        
        # Check required fields
        if "id" not in config:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.CONFIGURATION,
                message="Missing required field: id",
                field_name="id",
                suggested_fix="Add id to configuration",
                error_code="MISSING_FIELD"
            ))
        
        # Validate ID (6 bits)
        if "id" in config:
            lin_id = config["id"]
            if not isinstance(lin_id, int) or lin_id < 0 or lin_id > 0x3F:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="LIN ID must be a 6-bit integer (0-63)",
                    field_name="id",
                    suggested_fix="Use value between 0 and 63",
                    error_code="OUT_OF_RANGE"
                ))
        
        # Validate optional fields
        int_fields = {
            "length": (0, 8, "data length"),
            "checksum": (0, 0xFF, "8-bit checksum")
        }
        
        for field, (min_val, max_val, description) in int_fields.items():
            if field in config:
                value = config[field]
                if not isinstance(value, int) or value < min_val or value > max_val:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.RANGE,
                        message=f"{field} must be a {description} ({min_val}-{max_val})",
                        field_name=field,
                        suggested_fix=f"Use value between {min_val} and {max_val}",
                        error_code="OUT_OF_RANGE"
                    ))
        
        return results
    
    def _validate_uart_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate UART/RS232 configuration."""
        results = []
        
        # Validate baud rate
        if "baud_rate" in config:
            baud_rate = config["baud_rate"]
            if not isinstance(baud_rate, int) or baud_rate <= 0:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="Baud rate must be a positive integer",
                    field_name="baud_rate",
                    suggested_fix="Use positive integer for baud rate",
                    error_code="OUT_OF_RANGE"
                ))
            elif baud_rate > 1000000:  # 1 Mbps warning
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.PERFORMANCE,
                    message=f"Very high baud rate: {baud_rate}. Verify hardware capability",
                    field_name="baud_rate",
                    suggested_fix="Ensure hardware supports this baud rate",
                    error_code="HIGH_BAUD_RATE"
                ))
        
        # Validate data bits
        if "data_bits" in config:
            data_bits = config["data_bits"]
            if not isinstance(data_bits, int) or data_bits < 5 or data_bits > 9:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="Data bits must be between 5 and 9",
                    field_name="data_bits",
                    suggested_fix="Use value between 5 and 9",
                    error_code="OUT_OF_RANGE"
                ))
        
        # Validate stop bits
        if "stop_bits" in config:
            stop_bits = config["stop_bits"]
            if not isinstance(stop_bits, int) or stop_bits < 1 or stop_bits > 2:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="Stop bits must be 1 or 2",
                    field_name="stop_bits",
                    suggested_fix="Use 1 or 2 stop bits",
                    error_code="OUT_OF_RANGE"
                ))
        
        # Validate parity
        if "parity" in config:
            parity = config["parity"]
            valid_parity = ["none", "even", "odd", "mark", "space"]
            if not isinstance(parity, str) or parity.lower() not in valid_parity:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.FORMAT,
                    message=f"Parity must be one of: {', '.join(valid_parity)}",
                    field_name="parity",
                    suggested_fix=f"Use one of: {', '.join(valid_parity)}",
                    error_code="INVALID_PARITY"
                ))
        
        return results
    
    def _validate_someip_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate SOME/IP configuration."""
        results = []
        
        # Check required fields
        required_fields = ["service_id", "method_id", "client_id", "session_id"]
        for field in required_fields:
            if field not in config:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Missing required field: {field}",
                    field_name=field,
                    suggested_fix=f"Add {field} to configuration",
                    error_code="MISSING_FIELD"
                ))
        
        # Validate numeric fields
        int_fields = {
            "service_id": (0, 0xFFFF, "16-bit service ID"),
            "method_id": (0, 0xFFFF, "16-bit method ID"),
            "client_id": (0, 0xFFFF, "16-bit client ID"),
            "session_id": (0, 0xFFFF, "16-bit session ID"),
            "protocol_version": (0, 0xFF, "8-bit protocol version"),
            "interface_version": (0, 0xFFFFFFFF, "32-bit interface version"),
            "message_type": (0, 0xFF, "8-bit message type"),
            "return_code": (0, 0xFF, "8-bit return code")
        }
        
        for field, (min_val, max_val, description) in int_fields.items():
            if field in config:
                value = config[field]
                if not isinstance(value, int) or value < min_val or value > max_val:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.RANGE,
                        message=f"{field} must be a {description} ({min_val}-{max_val})",
                        field_name=field,
                        suggested_fix=f"Use value between {min_val} and {max_val}",
                        error_code="OUT_OF_RANGE"
                    ))
        
        return results
    
    def _validate_doip_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate DoIP (Diagnostic over IP) configuration."""
        results = []
        
        # Check required fields
        required_fields = ["protocol_version", "payload_type"]
        for field in required_fields:
            if field not in config:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONFIGURATION,
                    message=f"Missing required field: {field}",
                    field_name=field,
                    suggested_fix=f"Add {field} to configuration",
                    error_code="MISSING_FIELD"
                ))
        
        # Validate protocol version (typically 0x02 for ISO 13400-2)
        if "protocol_version" in config:
            version = config["protocol_version"]
            if not isinstance(version, int) or version < 0 or version > 0xFF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="Protocol version must be an 8-bit integer (0-255)",
                    field_name="protocol_version",
                    suggested_fix="Use value between 0 and 255 (typically 0x02)",
                    error_code="OUT_OF_RANGE"
                ))
            elif version != 0x02:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.COMPATIBILITY,
                    message=f"Unusual protocol version: {version:#04x}. Standard version is 0x02",
                    field_name="protocol_version",
                    suggested_fix="Consider using standard version 0x02",
                    error_code="NON_STANDARD_VERSION"
                ))
        
        # Validate payload type
        valid_payload_types = [
            0x0000, 0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0006, 0x0007,
            0x8001, 0x8002, 0x8003
        ]
        if "payload_type" in config:
            payload_type = config["payload_type"]
            if not isinstance(payload_type, int) or payload_type < 0 or payload_type > 0xFFFF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="Payload type must be a 16-bit integer (0-65535)",
                    field_name="payload_type",
                    suggested_fix="Use value between 0 and 65535",
                    error_code="OUT_OF_RANGE"
                ))
            elif payload_type not in valid_payload_types:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.COMPATIBILITY,
                    message=f"Unknown payload type: {payload_type:#06x}",
                    field_name="payload_type",
                    suggested_fix=f"Use standard payload type from: {[hex(x) for x in valid_payload_types]}",
                    error_code="UNKNOWN_PAYLOAD_TYPE"
                ))
        
        return results
    
    def _validate_http_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate HTTP configuration."""
        results = []
        
        # Validate method
        if "method" in config:
            method = config["method"]
            valid_methods = ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH", "TRACE"]
            if not isinstance(method, str) or method.upper() not in valid_methods:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.FORMAT,
                    message=f"Invalid HTTP method: {method}",
                    field_name="method",
                    suggested_fix=f"Use one of: {', '.join(valid_methods)}",
                    error_code="INVALID_HTTP_METHOD"
                ))
        
        # Validate version
        if "version" in config:
            version = config["version"]
            valid_versions = ["1.0", "1.1", "2.0"]
            if not isinstance(version, str) or version not in valid_versions:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.COMPATIBILITY,
                    message=f"Unusual HTTP version: {version}",
                    field_name="version",
                    suggested_fix=f"Consider using: {', '.join(valid_versions)}",
                    error_code="UNUSUAL_VERSION"
                ))
        
        # Validate status code (for responses)
        if "status_code" in config:
            status_code = config["status_code"]
            if not isinstance(status_code, int) or status_code < 100 or status_code > 599:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="HTTP status code must be between 100 and 599",
                    field_name="status_code",
                    suggested_fix="Use valid HTTP status code (100-599)",
                    error_code="INVALID_STATUS_CODE"
                ))
        
        return results
    
    def _validate_dns_config(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate DNS configuration."""
        results = []
        
        # Validate query ID
        if "query_id" in config:
            query_id = config["query_id"]
            if not isinstance(query_id, int) or query_id < 0 or query_id > 0xFFFF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="DNS query ID must be a 16-bit integer (0-65535)",
                    field_name="query_id",
                    suggested_fix="Use value between 0 and 65535",
                    error_code="OUT_OF_RANGE"
                ))
        
        # Validate query type
        if "query_type" in config:
            query_type = config["query_type"]
            valid_types = [1, 2, 5, 6, 12, 15, 16, 28, 33, 43, 46, 47, 48, 50, 51, 52]  # Common DNS types
            if not isinstance(query_type, int) or query_type < 0 or query_type > 0xFFFF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="DNS query type must be a 16-bit integer (0-65535)",
                    field_name="query_type",
                    suggested_fix="Use value between 0 and 65535",
                    error_code="OUT_OF_RANGE"
                ))
            elif query_type not in valid_types:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.COMPATIBILITY,
                    message=f"Unusual DNS query type: {query_type}",
                    field_name="query_type",
                    suggested_fix=f"Common types: {valid_types}",
                    error_code="UNUSUAL_QUERY_TYPE"
                ))
        
        # Validate query class
        if "query_class" in config:
            query_class = config["query_class"]
            if not isinstance(query_class, int) or query_class < 0 or query_class > 0xFFFF:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    message="DNS query class must be a 16-bit integer (0-65535)",
                    field_name="query_class",
                    suggested_fix="Use value between 0 and 65535 (typically 1 for IN)",
                    error_code="OUT_OF_RANGE"
                ))
            elif query_class != 1:  # IN class is most common
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.COMPATIBILITY,
                    message=f"Unusual DNS query class: {query_class}. Standard class is 1 (IN)",
                    field_name="query_class",
                    suggested_fix="Consider using class 1 (IN) for Internet",
                    error_code="UNUSUAL_QUERY_CLASS"
                ))
        
        return results
    
    # === EXTENSIBILITY METHODS ===
    
    def add_protocol_dependency(self, protocol: str, dependencies: List[str]) -> None:
        """
        Add or update a protocol dependency.
        
        Args:
            protocol: Protocol name
            dependencies: List of protocols that must come before this one
        """
        self._protocol_dependencies[protocol] = dependencies
        self.logger.debug(f"Updated dependencies for {protocol}: {dependencies}")
    
    def get_protocol_dependencies(self, protocol: str) -> List[str]:
        """
        Get dependencies for a protocol.
        
        Args:
            protocol: Protocol name
            
        Returns:
            List of protocol dependencies or empty list if none
        """
        return self._protocol_dependencies.get(protocol, [])
    
    def register_protocol_validator(self, protocol_name: str, validator_func: Callable) -> None:
        """
        Register a custom validator function for a protocol.
        
        Args:
            protocol_name: Name of the protocol
            validator_func: Function that takes config dict and returns List[ValidationResult] or (bool, str)
        """
        self._protocol_validators[protocol_name] = validator_func
        self.logger.debug(f"Registered custom validator for {protocol_name}")
    
    def add_protocol_exclusion(self, protocol: str, exclusions: List[str]) -> None:
        """
        Add mutual exclusions for a protocol.
        
        Args:
            protocol: Protocol name
            exclusions: List of protocols that cannot coexist with this protocol
        """
        self._protocol_exclusions[protocol] = exclusions
        self.logger.debug(f"Added exclusions for {protocol}: {exclusions}")
    
    def set_preferred_order(self, order: List[str]) -> None:
        """
        Set the preferred protocol order.
        
        Args:
            order: List of protocol names in preferred order
        """
        self._preferred_order = order.copy()
        self.logger.debug(f"Updated preferred protocol order: {len(order)} protocols")
    
    def add_custom_error_suggestion(self, error_code: str, suggestion: str) -> None:
        """
        Add custom error suggestion.
        
        Args:
            error_code: Error code identifier
            suggestion: Suggested fix message
        """
        self._error_suggestions[error_code] = suggestion
        self.logger.debug(f"Added custom suggestion for {error_code}")
    
    # === ADVANCED VALIDATION METHODS ===
    
    def validate_protocol_compatibility(self, protocols: List[str]) -> List[ValidationResult]:
        """
        Check compatibility between protocols without validating order.
        
        Args:
            protocols: List of protocol names
            
        Returns:
            List of compatibility issues
        """
        results = []
        
        # Check mutual exclusions
        results.extend(self._check_mutual_exclusions(protocols))
        
        # Check if dependencies can be satisfied
        for protocol in protocols:
            if protocol in self._protocol_dependencies:
                required_deps = self._protocol_dependencies[protocol]
                if required_deps:
                    available_deps = [dep for dep in required_deps if dep in protocols]
                    if not available_deps:
                        results.append(ValidationResult(
                            is_valid=False,
                            severity=ValidationSeverity.WARNING,
                            category=ValidationCategory.DEPENDENCY,
                            message=f"Protocol {protocol} requires one of {required_deps} but none are present",
                            protocol_name=protocol,
                            suggested_fix=f"Add one of: {required_deps}",
                            error_code="UNSATISFIED_DEPENDENCY"
                        ))
        
        return results
    
    def suggest_protocol_order(self, protocols: List[str]) -> List[str]:
        """
        Suggest an optimal order for a list of protocols.
        
        Args:
            protocols: List of protocol names
            
        Returns:
            List of protocols in suggested order
        """
        try:
            # Create position mapping
            position_map = {proto: i for i, proto in enumerate(self._preferred_order)}
            
            # Sort by preferred position, maintaining original order for unknowns
            def sort_key(protocol):
                base_name = protocol.split()[0]
                return position_map.get(base_name, 999)
            
            sorted_protocols = sorted(protocols, key=sort_key)
            
            return sorted_protocols
        except Exception as e:
            self.logger.error(f"Error suggesting protocol order: {e}")
            return protocols
    
    def get_validation_suggestions(self, results: List[ValidationResult]) -> Dict[str, List[str]]:
        """
        Get organized validation suggestions by category.
        
        Args:
            results: List of validation results
            
        Returns:
            Dictionary of suggestions organized by severity
        """
        suggestions = {
            "critical": [],
            "errors": [],
            "warnings": [],
            "info": []
        }
        
        for result in results:
            if result.suggested_fix:
                severity_key = result.severity.name.lower()
                if severity_key == "critical":
                    suggestions["critical"].append(result.suggested_fix)
                elif severity_key == "error":
                    suggestions["errors"].append(result.suggested_fix)
                elif severity_key == "warning":
                    suggestions["warnings"].append(result.suggested_fix)
                else:
                    suggestions["info"].append(result.suggested_fix)
        
        return suggestions
    
    def validate_with_detailed_results(self, stack: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate stack with comprehensive detailed results.
        
        Args:
            stack: Protocol stack to validate
            
        Returns:
            Detailed validation report
        """
        start_time = time.time()
        
        # Validate stack
        is_valid, message = self.validate_protocol_stack(stack)
        
        # Get detailed results for individual components
        detailed_results = []
        stack_protocols = [p.get("name", "").split(" ")[0] for p in stack]
        
        # Individual protocol validations
        for protocol_dict in stack:
            protocol_name = protocol_dict.get("name", "")
            config = protocol_dict.get("config", {})
            
            proto_valid, proto_message = self.validate_protocol_config(protocol_name, config)
            detailed_results.append({
                "protocol": protocol_name,
                "valid": proto_valid,
                "message": proto_message,
                "config": config
            })
        
        # Dependency analysis
        dependency_results = self._check_protocol_dependencies(stack_protocols)
        
        # Compatibility analysis
        compatibility_results = self.validate_protocol_compatibility(stack_protocols)
        
        # Security analysis
        security_results = self._check_security_issues(stack)
        
        # Performance analysis
        performance_results = self._check_protocol_order(stack_protocols)
        
        # Policy analysis (NEW)
        policy_results = self._check_network_policies(stack)
        
        # Generate comprehensive report
        validation_time = time.time() - start_time
        
        return {
            "summary": {
                "overall_valid": is_valid,
                "message": message,
                "validation_time": validation_time,
                "protocol_count": len(stack),
                "timestamp": time.time(),
                "policy_violations": len([r for r in policy_results if r.error_code and r.error_code.startswith("POLICY_")])
            },
            "protocols": detailed_results,
            "dependencies": [result.to_dict() for result in dependency_results],
            "compatibility": [result.to_dict() for result in compatibility_results],
            "security": [result.to_dict() for result in security_results],
            "performance": [result.to_dict() for result in performance_results],
            "policies": [result.to_dict() for result in policy_results],
            "suggested_order": self.suggest_protocol_order(stack_protocols),
            "suggestions": self.get_validation_suggestions(
                dependency_results + compatibility_results + security_results + performance_results + policy_results
            ),
            "statistics": self.get_statistics().to_dict()
        }
    
    # === REPORTING METHODS ===
    
    def generate_validation_report(self, results: List[ValidationResult], 
                                 format_type: str = "json") -> str:
        """
        Generate validation report in specified format.
        
        Args:
            results: List of validation results
            format_type: Report format ("json", "html", "csv", "text")
            
        Returns:
            Formatted report string
        """
        try:
            if format_type.lower() == "html":
                return self._reporter.generate_html_report(results)
            elif format_type.lower() == "csv":
                return self._reporter.generate_csv_report(results)
            elif format_type.lower() == "text":
                return self._generate_text_report(results)
            else:  # Default to JSON
                return self._reporter.generate_json_report(results)
        except Exception as e:
            self.logger.error(f"Error generating {format_type} report: {e}")
            return f"Error generating report: {e}"
    
    def _generate_text_report(self, results: List[ValidationResult]) -> str:
        """Generate plain text validation report."""
        lines = []
        lines.append("TECMP PROTOCOL VALIDATION REPORT")
        lines.append("=" * 40)
        lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Total Results: {len(results)}")
        
        # Count policy violations
        policy_violations = len([r for r in results if r.error_code and r.error_code.startswith("POLICY_")])
        lines.append(f"Policy Violations: {policy_violations}")
        lines.append("")
        
        # Summary
        errors = len([r for r in results if r.severity == ValidationSeverity.ERROR])
        warnings = len([r for r in results if r.severity == ValidationSeverity.WARNING])
        critical = len([r for r in results if r.severity == ValidationSeverity.CRITICAL])
        info = len([r for r in results if r.severity == ValidationSeverity.INFO])
        
        lines.append("SUMMARY:")
        lines.append(f"  Critical: {critical}")
        lines.append(f"  Errors:   {errors}")
        lines.append(f"  Warnings: {warnings}")
        lines.append(f"  Info:     {info}")
        lines.append("")
        
        # Detailed results
        lines.append("DETAILED RESULTS:")
        lines.append("-" * 20)
        
        for i, result in enumerate(results, 1):
            is_policy = " [POLICY]" if result.error_code and result.error_code.startswith("POLICY_") else ""
            lines.append(f"{i}. [{result.severity.name}]{is_policy} {result.protocol_name or 'General'}")
            lines.append(f"   Message: {result.message}")
            if result.field_name:
                lines.append(f"   Field: {result.field_name}")
            if result.suggested_fix:
                lines.append(f"   Fix: {result.suggested_fix}")
            if result.error_code:
                lines.append(f"   Code: {result.error_code}")
            lines.append("")
        
        return "\n".join(lines)
    
    def export_validation_results(self, results: List[ValidationResult], 
                                filepath: str, format_type: str = "json") -> None:
        """
        Export validation results to file.
        
        Args:
            results: List of validation results
            filepath: Output file path
            format_type: Export format
        """
        try:
            report = self.generate_validation_report(results, format_type)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            self.logger.info(f"Validation results exported to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to export validation results: {e}")
    
    # === UTILITY METHODS ===
    
    def _generate_stack_cache_key(self, stack: List[Dict[str, Any]]) -> str:
        """Generate a cache key for a protocol stack."""
        try:
            # Create a string representation that captures the essential structure
            stack_repr = []
            for protocol in stack:
                name = protocol.get("name", "")
                config = protocol.get("config", {})
                config_hash = self._hash_config(config)
                stack_repr.append(f"{name}:{config_hash}")
            
            combined = "|".join(stack_repr)
            return f"stack:{hashlib.md5(combined.encode()).hexdigest()}"
        except Exception:
            return f"stack:{time.time()}"  # Fallback to timestamp
    
    def _hash_config(self, config: Dict[str, Any]) -> str:
        """Generate hash for configuration dictionary."""
        try:
            # Sort items for consistent hashing
            config_str = str(sorted(config.items()))
            return hashlib.md5(config_str.encode()).hexdigest()[:8]
        except Exception:
            return str(hash(str(config)))[:8]
    
    def _cache_result(self, cache_key: str, result: Tuple[bool, str]) -> None:
        """Cache a validation result."""
        if self._validation_cache is not None:
            with self._cache_lock:
                self._validation_cache[cache_key] = {
                    'result': result,
                    'timestamp': time.time()
                }
                
                # Clean old entries if cache is getting large
                if len(self._validation_cache) > 1000:
                    self._cleanup_cache()
    
    def _cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        try:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._validation_cache.items():
                if current_time - entry['timestamp'] > self._cache_ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._validation_cache[key]
                
            self.logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
        except Exception as e:
            self.logger.debug(f"Error cleaning cache: {e}")
    
    def _update_timing_statistics(self, validation_time: float) -> None:
        """Update timing statistics."""
        try:
            with self._stats_lock:
                total_validations = self._statistics.total_validations
                if total_validations > 0:
                    # Update running average
                    current_avg = self._statistics.average_validation_time
                    new_avg = ((current_avg * (total_validations - 1)) + validation_time) / total_validations
                    self._statistics.average_validation_time = new_avg
        except Exception as e:
            self.logger.debug(f"Error updating timing statistics: {e}")
    
    # === STATISTICS AND MONITORING ===
    
    def get_statistics(self) -> ValidationStatistics:
        """Get validation statistics."""
        with self._stats_lock:
            return copy.deepcopy(self._statistics)
    
    def reset_statistics(self) -> None:
        """Reset validation statistics."""
        with self._stats_lock:
            self._statistics = ValidationStatistics()
        self.logger.info("Validation statistics reset")
    
    def get_supported_protocols(self) -> List[str]:
        """Get list of supported protocols."""
        supported = list(self._protocol_validators.keys())
        supported.extend(self._plugins.keys())
        return sorted(list(set(supported)))
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get the complete dependency graph."""
        return copy.deepcopy(self._protocol_dependencies)
    
    def get_network_policies_summary(self) -> Dict[str, Any]:
        """Get summary of network policies."""
        return {
            "enabled": self._enable_network_policies,
            "total_policies": len(self._network_policies),
            "active_policies": len([p for p in self._network_policies.values() if p.enabled]),
            "policies": {
                name: {
                    "description": policy.description,
                    "enabled": policy.enabled,
                    "priority": policy.priority
                }
                for name, policy in self._network_policies.items()
            }
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics."""
        stats = self.get_statistics()
        cache_size = len(self._validation_cache) if self._validation_cache else 0
        
        return {
            "validation_performance": {
                "total_validations": stats.total_validations,
                "average_time": stats.average_validation_time,
                "success_rate": (stats.successful_validations / max(1, stats.total_validations)) * 100,
                "cache_hit_rate": (stats.cache_hits / max(1, stats.cache_hits + stats.cache_misses)) * 100
            },
            "cache_metrics": {
                "cache_size": cache_size,
                "cache_hits": stats.cache_hits,
                "cache_misses": stats.cache_misses,
                "cache_enabled": self._enable_caching
            },
            "validation_breakdown": {
                "successful": stats.successful_validations,
                "failed": stats.failed_validations,
                "dependency_checks": stats.dependency_checks,
                "async_validations": stats.async_validations,
                "plugin_validations": stats.plugin_validations,
                "policy_violations": stats.policy_violations
            },
            "session_info": {
                "session_duration": time.time() - stats.session_start_time,
                "strict_mode": self._strict_validation,
                "max_stack_depth": self._max_stack_depth,
                "max_workers": self._max_workers,
                "network_policies_enabled": self._enable_network_policies
            }
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive validator status."""
        try:
            return {
                'type': 'ProtocolValidator',
                'version': '3.0.0',  # Updated version with full policies
                'initialized': True,
                'configuration': {
                    'strict_mode': self._strict_validation,
                    'caching_enabled': self._enable_caching,
                    'dependency_warnings_enabled': self._enable_dependency_warnings,
                    'max_stack_depth': self._max_stack_depth,
                    'max_workers': self._max_workers,
                    'cache_ttl': self._cache_ttl,
                    'network_policies_enabled': self._enable_network_policies
                },
                'supported_features': {
                    'async_validation': True,
                    'plugin_system': True,
                    'security_validation': True,
                    'performance_analysis': True,
                    'export_formats': ['json', 'html', 'csv', 'text'],
                    'configuration_import_export': True,
                    'network_policies': True,
                    'comprehensive_policies': True  # NEW
                },
                'protocol_support': {
                    'built_in_validators': len(self._protocol_validators),
                    'plugin_validators': len(self._plugins),
                    'total_supported': len(self.get_supported_protocols()),
                    'known_dependencies': len(self._protocol_dependencies),
                    'mutual_exclusions': len(self._protocol_exclusions)
                },
                'network_policies': self.get_network_policies_summary(),
                'runtime_status': {
                    'cache_size': len(self._validation_cache) if self._validation_cache else 0,
                    'thread_pool_active': not self._executor._shutdown,
                    'statistics': self.get_statistics().to_dict()
                }
            }
        except Exception as e:
            return {
                'type': 'ProtocolValidator',
                'initialized': False,
                'error': str(e)
            }
    
    # === BATCH PROCESSING ===
    
    def validate_multiple_stacks(self, stacks: List[List[Dict[str, Any]]], 
                                use_async: bool = False) -> List[Tuple[bool, str]]:
        """
        Validate multiple protocol stacks.
        
        Args:
            stacks: List of protocol stacks
            use_async: Whether to use async validation
            
        Returns:
            List of validation results
        """
        if use_async and len(stacks) > 1:
            # Use async validation for better performance
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(self.validate_large_stack_batch(stacks))
                return results
            finally:
                loop.close()
        else:
            # Synchronous validation
            return [self.validate_protocol_stack(stack) for stack in stacks]
    
    def validate_from_file(self, filepath: str) -> Dict[str, Any]:
        """
        Validate protocol stack(s) from JSON file.
        
        Args:
            filepath: Path to JSON file containing stack definition(s)
            
        Returns:
            Validation results
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle single stack or multiple stacks
            if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                # Single stack
                is_valid, message = self.validate_protocol_stack(data)
                return {
                    "type": "single_stack",
                    "valid": is_valid,
                    "message": message,
                    "stack": data
                }
            elif isinstance(data, dict) and "stacks" in data:
                # Multiple stacks
                stacks = data["stacks"]
                results = self.validate_multiple_stacks(stacks)
                return {
                    "type": "multiple_stacks",
                    "results": [
                        {"valid": valid, "message": msg, "stack": stack}
                        for (valid, msg), stack in zip(results, stacks)
                    ]
                }
            else:
                return {
                    "type": "error",
                    "message": "Invalid file format. Expected protocol stack or {'stacks': [...]}"
                }
                
        except Exception as e:
            self.logger.error(f"Error validating from file {filepath}: {e}")
            return {
                "type": "error",
                "message": f"File validation error: {e}"
            }
    
    def load_network_policies_from_file(self, filepath: str) -> None:
        """
        Load network policies from JSON file.
        
        Args:
            filepath: Path to JSON file containing policies
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "network_policies" in data:
                self.load_network_policies_from_dict(data["network_policies"])
                self.logger.info(f"Loaded network policies from {filepath}")
            else:
                self.logger.warning(f"No 'network_policies' key found in {filepath}")
                
        except Exception as e:
            self.logger.error(f"Failed to load policies from file: {e}")
    
    # === HEALTH CHECK ===
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on validator.
        
        Returns:
            Health status report
        """
        health = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "3.0.0",
            "checks": {}
        }
        
        try:
            # Test basic validation
            test_stack = [
                {"name": "Ethernet", "config": {"src_mac": "00:11:22:33:44:55", "dst_mac": "66:77:88:99:AA:BB"}},
                {"name": "IPv4", "config": {"src_ip": "192.168.1.1", "dst_ip": "192.168.1.2"}},
                {"name": "UDP", "config": {"src_port": 1234, "dst_port": 5678}}
            ]
            
            start_time = time.time()
            is_valid, message = self.validate_protocol_stack(test_stack)
            validation_time = time.time() - start_time
            
            health["checks"]["basic_validation"] = {
                "status": "pass" if is_valid else "fail",
                "time": validation_time,
                "message": message if not is_valid else "OK"
            }
            
            # Test cache functionality
            if self._enable_caching:
                # Second validation should hit cache
                start_time = time.time()
                self.validate_protocol_stack(test_stack)
                cache_time = time.time() - start_time
                
                health["checks"]["cache_functionality"] = {
                    "status": "pass" if cache_time < validation_time else "warning",
                    "time": cache_time,
                    "speedup": f"{validation_time/cache_time:.2f}x" if cache_time > 0 else "N/A"
                }
            
            # Test plugin system
            health["checks"]["plugin_system"] = {
                "status": "pass",
                "registered_plugins": len(self._plugins),
                "plugin_protocols": list(self._plugins.keys())
            }
            
            # Test network policies
            health["checks"]["network_policies"] = {
                "status": "pass" if self._enable_network_policies else "disabled",
                "total_policies": len(self._network_policies),
                "active_policies": len([p for p in self._network_policies.values() if p.enabled]),
                "policy_categories": {
                    "ethernet": len([p for p in self._network_policies.keys() if "ETHERNET" in p]),
                    "vlan": len([p for p in self._network_policies.keys() if "VLAN" in p]),
                    "ip": len([p for p in self._network_policies.keys() if "IP" in p]),
                    "arp": len([p for p in self._network_policies.keys() if "ARP" in p]),
                    "tcp": len([p for p in self._network_policies.keys() if "TCP" in p]),
                    "udp": len([p for p in self._network_policies.keys() if "UDP" in p]),
                    "other": len([p for p in self._network_policies.keys() 
                              if not any(x in p for x in ["ETHERNET", "VLAN", "IP", "ARP", "TCP", "UDP"])])
                }
            }
            
            # Test thread pool
            health["checks"]["thread_pool"] = {
                "status": "pass" if not self._executor._shutdown else "fail",
                "max_workers": self._max_workers,
                "active": not self._executor._shutdown
            }
            
            # Overall status
            failed_checks = [name for name, check in health["checks"].items() 
                           if check.get("status") == "fail"]
            if failed_checks:
                health["status"] = "unhealthy"
                health["failed_checks"] = failed_checks
            elif any(check.get("status") == "warning" for check in health["checks"].values()):
                health["status"] = "degraded"
            
        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
            self.logger.error(f"Health check failed: {e}")
        
        return health


# === CONVENIENCE FUNCTIONS ===

def create_protocol_validator(strict_mode: bool = False, enable_caching: bool = True,
                            max_workers: int = 4) -> ProtocolValidator:
    """
    Create and configure a protocol validator instance.
    
    Args:
        strict_mode: Whether to use strict validation
        enable_caching: Whether to enable result caching
        max_workers: Maximum worker threads for async operations
        
    Returns:
        Configured ProtocolValidator instance
    """
    return ProtocolValidator(
        strict_mode=strict_mode,
        enable_caching=enable_caching,
        max_workers=max_workers
    )


def validate_simple_stack(protocols: List[str], strict: bool = False) -> Tuple[bool, str]:
    """
    Simple validation for a list of protocol names.
    
    Args:
        protocols: List of protocol names
        strict: Whether to use strict validation
        
    Returns:
        Validation result tuple
    """
    validator = create_protocol_validator(strict_mode=strict)
    
    # Convert to full stack format
    stack = [{"name": proto, "config": {}} for proto in protocols]
    
    return validator.validate_protocol_stack(stack)


def validate_stack_from_dict(stack_dict: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
    """
    Validate stack from dictionary and return detailed results.
    
    Args:
        stack_dict: Stack configuration dictionary
        strict: Whether to use strict validation
        
    Returns:
        Detailed validation results
    """
    validator = create_protocol_validator(strict_mode=strict)
    
    # Extract stack from dictionary
    if "stack" in stack_dict:
        stack = stack_dict["stack"]
    elif "protocols" in stack_dict:
        stack = stack_dict["protocols"]
    elif isinstance(stack_dict.get("data"), list):
        stack = stack_dict["data"]
    else:
        return {
            "valid": False,
            "error": "Invalid stack format. Expected 'stack', 'protocols', or 'data' key"
        }
    
    return validator.validate_with_detailed_results(stack)


# === EXAMPLE PLUGIN IMPLEMENTATION ===

class CustomProtocolPlugin(ValidationPlugin):
    """Example plugin for custom protocol validation."""
    
    def __init__(self, protocol_name: str):
        self.protocol_name = protocol_name
        self.logger = logging.getLogger(f"TECMP-Tool.Plugin.{protocol_name}")
    
    def validate(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate custom protocol configuration."""
        results = []
        
        # Example validation logic
        if "custom_field" not in config:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.CUSTOM,
                message=f"Custom field missing for {self.protocol_name}",
                field_name="custom_field",
                suggested_fix="Add custom_field to configuration",
                error_code="MISSING_CUSTOM_FIELD"
            ))
        
        return results
    
    def get_supported_protocols(self) -> List[str]:
        """Get supported protocols."""
        return [self.protocol_name]
    
    def get_plugin_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            "name": f"CustomPlugin_{self.protocol_name}",
            "version": "1.0.0",
            "description": f"Custom validation plugin for {self.protocol_name}",
            "supported_protocols": self.get_supported_protocols()
        }


# === MAIN EXECUTION ===

if __name__ == "__main__":
    # Example usage and testing
    logging.basicConfig(level=logging.INFO)
    
    print("=== PROTOCOL VALIDATOR WITH COMPREHENSIVE NETWORK POLICIES ===")
    print("Version: 3.0.0 with full security policies for all network layers\n")
    
    # Create validator
    validator = create_protocol_validator(strict_mode=False, enable_caching=True)
    
    # Get policy summary
    policy_summary = validator.get_network_policies_summary()
    print(f"Network Policies: {policy_summary['total_policies']} total, {policy_summary['active_policies']} active")
    print("\nActive policies by category:")
    for category in ["ETHERNET", "VLAN", "IP", "ARP", "TCP", "UDP"]:
        count = len([p for p in policy_summary['policies'] if category in p])
        print(f"  - {category}: {count} policies")
    
    # === TEST 1: Basic stack validation ===
    print("\n=== TEST 1: BASIC VALIDATION ===")
    test_stack = [
        {
            "name": "Ethernet",
            "config": {
                "src_mac": "00:11:22:33:44:55",
                "dst_mac": "66:77:88:99:AA:BB",
                "ether_type": 0x0800
            }
        },
        {
            "name": "IPv4",
            "config": {
                "src_ip": "192.168.1.1",
                "dst_ip": "192.168.1.2",
                "ttl": 64,
                "protocol": 17
            }
        },
        {
            "name": "UDP",
            "config": {
                "src_port": 1234,
                "dst_port": 5678,
                "length": 100
            }
        }
    ]
    
    is_valid, message = validator.validate_protocol_stack(test_stack)
    print(f"Valid: {is_valid}")
    print(f"Message: {message}")
    
    # === TEST 2: TCP port blocking ===
    print("\n=== TEST 2: TCP PORT BLOCKING POLICY ===")
    blocked_port_stack = [
        {"name": "Ethernet", "config": {"src_mac": "AA:BB:CC:DD:EE:FF", "dst_mac": "11:22:33:44:55:66"}},
        {"name": "IPv4", "config": {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2"}},
        {"name": "TCP", "config": {"src_port": 12345, "dst_port": 23}}  # Telnet port
    ]
    
    is_valid, message = validator.validate_protocol_stack(blocked_port_stack)
    print(f"Valid: {is_valid}")
    print(f"Message: {message}")
    
    # === TEST 3: VLAN policies ===
    print("\n=== TEST 3: VLAN DEFAULT POLICY ===")
    vlan_stack = [
        {"name": "Ethernet", "config": {"src_mac": "AA:BB:CC:DD:EE:FF", "dst_mac": "11:22:33:44:55:66"}},
        {"name": "VLAN", "config": {"vlan_id": 1, "priority": 0}},  # Default VLAN
        {"name": "IPv4", "config": {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2"}}
    ]
    
    is_valid, message = validator.validate_protocol_stack(vlan_stack)
    print(f"Valid: {is_valid}")
    print(f"Message: {message}")
    
    # === TEST 4: ARP poisoning detection ===
    print("\n=== TEST 4: ARP POISONING DETECTION ===")
    arp_stack = [
        {"name": "Ethernet", "config": {"src_mac": "AA:BB:CC:DD:EE:FF", "dst_mac": "FF:FF:FF:FF:FF:FF"}},
        {"name": "ARP", "config": {
            "operation": 2,  # Reply
            "sender_mac": "AA:BB:CC:DD:EE:FF",
            "sender_ip": "192.168.1.100",
            "target_mac": "00:00:00:00:00:00",
            "target_ip": "192.168.1.1"  # Gateway IP
        }}
    ]
    
    is_valid, message = validator.validate_protocol_stack(arp_stack)
    print(f"Valid: {is_valid}")
    print(f"Message: {message}")
    
    # === TEST 5: UDP amplification risk ===
    print("\n=== TEST 5: UDP AMPLIFICATION RISK ===")
    udp_amplification_stack = [
        {"name": "Ethernet", "config": {"src_mac": "AA:BB:CC:DD:EE:FF", "dst_mac": "11:22:33:44:55:66"}},
        {"name": "IPv4", "config": {"src_ip": "0.0.0.0", "dst_ip": "8.8.8.8"}},  # Spoofed source
        {"name": "UDP", "config": {"src_port": 12345, "dst_port": 11211}}  # Memcached
    ]
    
    is_valid, message = validator.validate_protocol_stack(udp_amplification_stack)
    print(f"Valid: {is_valid}")
    print(f"Message: {message}")
    
    # === TEST 6: Ethernet security ===
    print("\n=== TEST 6: ETHERNET MAC SECURITY ===")
    ethernet_loop_stack = [
        {"name": "Ethernet", "config": {
            "src_mac": "AA:BB:CC:DD:EE:FF",
            "dst_mac": "AA:BB:CC:DD:EE:FF"  # Same as source (loop)
        }},
        {"name": "IPv4", "config": {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2"}}
    ]
    
    is_valid, message = validator.validate_protocol_stack(ethernet_loop_stack)
    print(f"Valid: {is_valid}")
    print(f"Message: {message}")
    
    # === TEST 7: IPv4 private to public ===
    print("\n=== TEST 7: IPv4 PRIVATE TO PUBLIC POLICY ===")
    ip_leak_stack = [
        {"name": "Ethernet", "config": {"src_mac": "AA:BB:CC:DD:EE:FF", "dst_mac": "11:22:33:44:55:66"}},
        {"name": "IPv4", "config": {
            "src_ip": "192.168.1.100",  # Private IP
            "dst_ip": "8.8.8.8",        # Public IP
            "ttl": 64
        }}
    ]
    
    is_valid, message = validator.validate_protocol_stack(ip_leak_stack)
    print(f"Valid: {is_valid}")
    print(f"Message: {message}")
    
    # === Detailed validation with all policies ===
    print("\n=== DETAILED VALIDATION WITH ALL POLICIES ===")
    complex_stack = [
        {"name": "Ethernet", "config": {"src_mac": "AA:BB:CC:DD:EE:FF", "dst_mac": "11:22:33:44:55:66"}},
        {"name": "VLAN", "config": {"vlan_id": 200, "priority": 0}},  # IoT VLAN
        {"name": "IPv4", "config": {"src_ip": "10.0.200.50", "dst_ip": "10.0.100.10", "ttl": 3}},  # Low TTL
        {"name": "TCP", "config": {"src_port": 12345, "dst_port": 3389, "flags": {}}}  # RDP + NULL scan
    ]
    
    detailed = validator.validate_with_detailed_results(complex_stack)
    print(f"Overall Valid: {detailed['summary']['overall_valid']}")
    print(f"Policy Violations: {detailed['summary']['policy_violations']}")
    
    if detailed['policies']:
        print("\nPolicy violations found:")
        for policy in detailed['policies']:
            print(f"  - [{policy['severity']}] {policy['message']}")
            if policy.get('suggested_fix'):
                print(f"    Fix: {policy['suggested_fix']}")
    
    # === Health check ===
    print("\n=== HEALTH CHECK ===")
    health = validator.health_check()
    print(f"Status: {health['status']}")
    print(f"Version: {health['version']}")
    print(f"Network Policies Status: {health['checks']['network_policies']}")
    
    # === Performance metrics ===
    print("\n=== PERFORMANCE METRICS ===")
    metrics = validator.get_performance_metrics()
    print(f"Total Validations: {metrics['validation_breakdown']['successful'] + metrics['validation_breakdown']['failed']}")
    print(f"Policy Violations: {metrics['validation_breakdown']['policy_violations']}")
    print(f"Success Rate: {metrics['validation_performance']['success_rate']:.1f}%")
    print(f"Cache Hit Rate: {metrics['validation_performance']['cache_hit_rate']:.1f}%")
    
    # === Example policy configuration file ===
    print("\n=== EXAMPLE COMPREHENSIVE POLICY CONFIGURATION ===")
    comprehensive_policies = {
        "network_policies": {
            "DMZ_RESTRICTIONS": {
                "description": "DMZ network restrictions",
                "enabled": True,
                "priority": 100,
                "rules": [
                    {
                        "type": "vlan_range",
                        "vlan_start": 50,
                        "vlan_end": 59,
                        "requires_encryption": True,
                        "severity": "ERROR",
                        "message": "DMZ traffic must be encrypted",
                        "fix": "Add IPSec or TLS encryption"
                    }
                ]
            },
            "COMPLIANCE_PORTS": {
                "description": "Regulatory compliance port restrictions",
                "enabled": True,
                "priority": 90,
                "rules": [
                    {
                        "type": "tcp_ports",
                        "ports": [21, 23, 69, 135, 139, 445],
                        "action": "block",
                        "severity": "ERROR",
                        "message": "Port {port} blocked by compliance policy",
                        "fix": "Use approved secure alternatives"
                    }
                ]
            },
            "NETWORK_HYGIENE": {
                "description": "General network hygiene policies",
                "enabled": True,
                "priority": 50,
                "rules": [
                    {
                        "type": "ip_ttl",
                        "min_ttl": 5,
                        "severity": "WARNING",
                        "message": "Low TTL detected - possible scan",
                        "fix": "Investigate source of low TTL packets"
                    },
                    {
                        "type": "mac_validation",
                        "forbid_multicast_source": True,
                        "severity": "ERROR",
                        "message": "Invalid source MAC address",
                        "fix": "Source MAC must be unicast"
                    }
                ]
            }
        }
    }
    
    print(json.dumps(comprehensive_policies, indent=2))
    
    print("\n=== VALIDATION COMPLETE ===")
    print("All network security policies are active with ZERO impact!")
    print("The validator now enforces comprehensive security policies for:")
    print("  ? Ethernet (MAC security, broadcast control)")
    print("  ? VLAN (segmentation, default VLAN blocking)")
    print("  ? IPv4/IPv6 (private ranges, reserved IPs, TTL checks)")
    print("  ? ARP (poisoning detection, gratuitous ARP)")
    print("  ? TCP (port blocking, flag validation, privileged ports)")
    print("  ? UDP (service restrictions, amplification prevention)")
    print("\nAll validations flow through the same pipeline - other modules unchanged!")