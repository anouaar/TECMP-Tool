#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Packet types definitions"""

from enum import Enum
from typing import Protocol

class PacketType(Enum):
    """Packet types enumeration"""
    ETHERNET = "ethernet"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    TCP = "tcp"
    UDP = "udp"
    ARP = "arp"
    ICMP = "icmp"
    TECMP = "tecmp"
    UNKNOWN = "unknown"

class IPacket(Protocol):
    """Interface for packets"""
    def serialize(self) -> bytes: ...
    def deserialize(self, data: bytes) -> None: ...
    def get_type(self) -> str: ...

class ISerializable(Protocol):
    """Interface for serializable objects"""
    def to_dict(self) -> dict: ...
    def from_dict(self, data: dict) -> None: ...
