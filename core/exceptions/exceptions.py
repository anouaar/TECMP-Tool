# -*- coding: utf-8 -*-
"""
core/exceptions/exceptions.py
Exception classes for TECMP-Tool - Fixed version
"""

class PacketError(Exception):
    """Base class for all packet-related errors."""
    pass


class PacketParsingError(PacketError):
    """Error raised when packet deserialization fails."""
    pass


class PacketSerializationError(PacketError):
    """Error raised when packet serialization fails."""
    pass


class PacketValidationError(PacketError):
    """Error raised when packet validation fails."""
    pass


class EthernetValidationError(PacketValidationError):
    """Specific validation error for Ethernet frames."""
    pass


class TECMPValidationError(PacketValidationError):
    """Exception raised when a TECMP packet is invalid."""
    
    def __init__(self, message: str, field: str = None, timestamp: int = None) -> None:
        super().__init__(message)
        self.field = field
        self.timestamp = timestamp