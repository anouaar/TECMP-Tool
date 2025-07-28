#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Packet exceptions"""

class PacketError(Exception):
    """Base exception for packet operations"""
    pass

class PacketParsingError(PacketError):
    """Exception for packet parsing errors"""
    pass

class PacketValidationError(PacketError):
    """Exception for packet validation errors"""
    pass

class PacketSerializationError(PacketError):
    """Exception for packet serialization errors"""
    pass
