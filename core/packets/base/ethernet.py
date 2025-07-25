# -*- coding: utf-8 -*-
"""
Full Ethernet II frame implementation for the TECMP-Tool project.

 MacAddress : gestion simple d'adresses MAC (6 octets).
 EthernetPacket :
     En-tte 14 octets, sans VLAN.
     (D)srialisation big-endian.
     Validation des MAC, EtherType, longueur.
     Padding  60 octets (64 avec FCS) si ncessaire.
"""

from __future__ import annotations
import struct
from typing import Optional, Union
from core.exceptions.exceptions import EthernetValidationError
from .packet import Packet


# --------------------------------------------------------------------------- #
# Helper : adresse MAC
# --------------------------------------------------------------------------- #
class MacAddress:
    """Reprsente une adresse MAC sur 6 octets."""

    LENGTH = 6

    def __init__(self, addr: Union[bytes, str]):
        if isinstance(addr, bytes):
            if len(addr) != self.LENGTH:
                raise ValueError("MAC bytes must be 6 bytes long")
            self._bytes = addr
        else:  # chane  aa:bb:cc:dd:ee:ff 
            parts = addr.split(":")
            if len(parts) != self.LENGTH:
                raise ValueError("MAC string must have 6 octets")
            self._bytes = bytes(int(p, 16) for p in parts)

    def __bytes__(self) -> bytes:
        return self._bytes

    def __str__(self) -> str:
        return ":".join(f"{b:02x}" for b in self._bytes)

    # Flags utiles
    def is_multicast(self) -> bool:
        return bool(self._bytes[0] & 0x01)

    def is_broadcast(self) -> bool:
        return self._bytes == b"\xff\xff\xff\xff\xff\xff"

    def is_unicast(self) -> bool:
        return not self.is_multicast() and not self.is_broadcast()


# --------------------------------------------------------------------------- #
# Trame Ethernet II
# --------------------------------------------------------------------------- #
class EthernetPacket(Packet):
    """Ethernet II frame (14-byte header, no VLAN)."""

    _FMT = "!6s6sH"
    _HDR_LEN = 14
    MIN_FRAME = 64
    MAX_FRAME = 1518

    def __init__(
        self,
        src_mac: Optional[Union[MacAddress, str]] = None,
        dst_mac: Optional[Union[MacAddress, str]] = None,
        ether_type: int = 0x0000,
        payload: Optional[Packet] = None,
    ) -> None:
        super().__init__()
        
        # Convertir les strings en MacAddress si nécessaire
        if src_mac is not None:
            self.src_mac = src_mac if isinstance(src_mac, MacAddress) else MacAddress(src_mac)
        else:
            self.src_mac = None
            
        if dst_mac is not None:
            self.dst_mac = dst_mac if isinstance(dst_mac, MacAddress) else MacAddress(dst_mac)
        else:
            self.dst_mac = None
            
        self.ether_type = ether_type
        self._payload = payload

    # --------------------------------------------------------------------- #
    #  Mthode de compatibilit avec l'ancienne factory
    # --------------------------------------------------------------------- #
    def set_mac_addresses(self, src: Union[MacAddress, str], dst: Union[MacAddress, str]) -> None:
        """Dfinit les adresses MAC source et destination."""
        self.src_mac = src if isinstance(src, MacAddress) else MacAddress(src)
        self.dst_mac = dst if isinstance(dst, MacAddress) else MacAddress(dst)

    # ---------------------------- Encapsulation --------------------------- #
    def encapsulate(self, payload: Packet) -> None:
        self._payload = payload
        if hasattr(payload, "ETHER_TYPE"):
            self.ether_type = payload.ETHER_TYPE

    def decapsulate(self) -> Optional[Packet]:
        return self._payload

    # ------------------------- (De)serialisation -------------------------- #
    def _header(self) -> bytes:
        if not (self.src_mac and self.dst_mac):
            raise EthernetValidationError("Source and destination MAC must be set")
        return struct.pack(
            self._FMT, bytes(self.dst_mac), bytes(self.src_mac), self.ether_type
        )

    def serialize(self) -> bytes:
        payload_bytes = self._payload.serialize() if self._payload else b""
        frame = self._header() + payload_bytes

        # padding jusqu' 60 octets (hors FCS)
        if len(frame) < self.MIN_FRAME - 4:
            frame += b"\x00" * (self.MIN_FRAME - 4 - len(frame))

        self._raw_data = bytearray(frame)
        self._update_size()
        return self.raw_data

    def deserialize(self, data: bytes) -> None:
        if len(data) < self._HDR_LEN:
            raise EthernetValidationError("Frame too short")
        dst, src, self.ether_type = struct.unpack(self._FMT, data[: self._HDR_LEN])
        self.dst_mac, self.src_mac = MacAddress(dst), MacAddress(src)
        self._raw_data = bytearray(data)
        self._update_size()
        # le dcapsulage du payload se fera plus haut

    # ------------------------------ Validation --------------------------- #
    def validate(self) -> bool:
        if not (self.src_mac and self.dst_mac):
            raise EthernetValidationError("Missing MAC addresses")

        if not self.src_mac.is_unicast():
            raise EthernetValidationError("Source MAC must be unicast")

        if not (0x0600 <= self.ether_type <= 0xFFFF):
            raise EthernetValidationError(f"Invalid EtherType 0x{self.ether_type:04x}")

        if not (self.MIN_FRAME <= self.size <= self.MAX_FRAME):
            raise EthernetValidationError("Frame length out of bounds")

        if self._payload and not self._payload.validate():
            return False
        return True

    # ------------------------------ Utils -------------------------------- #
    def summary(self) -> str:
        return (
            f"ETH {self.src_mac}->{self.dst_mac} "
            f"type=0x{self.ether_type:04x} len={self.size}"
        )