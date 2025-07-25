# -*- coding: utf-8 -*-
# validator.py - CORRECTED VERSION FOR OFFICIAL TECMP FORMAT
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass, field
import time
import logging
from core.exceptions.exceptions import TECMPValidationError


def validate_can_id(can_id: int, is_extended: bool = False) -> bool:
    if can_id is None:
        return False
    if is_extended:
        return 0 <= can_id <= 0x1FFFFFFF
    else:
        return 0 <= can_id <= 0x7FF

def validate_timestamp(timestamp_ns: int, allow_zero: bool = False) -> bool:
    if timestamp_ns is None:
        return False
    if timestamp_ns < 0:
        return False
    if not allow_zero and timestamp_ns == 0:
        return False
    return timestamp_ns < (1 << 62)


@dataclass
class InterfaceState:
    """State tracking per interface"""
    last_counter: Optional[int] = None
    last_timestamp: Optional[int] = None
    packet_count: int = 0
    device_id: Optional[int] = None
    first_seen: float = field(default_factory=time.time)
    event_cache: Dict[int, float] = field(default_factory=dict)


class TECMPValidator:
    VALID_VERSIONS = [1, 2, 3]
    VALID_MESSAGE_TYPES = {
        0x00: "Control",
        0x01: "Status/Notification",
        0x02: "Command Response",
        0x03: "Logging Stream",
        0x0A: "Replay Data"
    }
    VALID_DATA_TYPES = {
        0x01: "Logging Message",
        0x02: "CAN",
        0x03: "CAN-FD",
        0x04: "LIN",
        0x08: "FlexRay",
        0x10: "UART/RS232",
        0x20: "Analog",
        0x40: "Digital",
        0x80: "Ethernet II",
        0x0080: "Ethernet II"
    }
    
    FLAG_EOS = 0x01
    FLAG_SOS = 0x02
    FLAG_SPY = 0x04
    FLAG_MULTI_FRAME = 0x08
    
    KNOWN_DEVICE_IDS = {
        0x0091: "CM 1000 High 1",
        0x0080: "Standard TECMP Device"
    }
    
    @staticmethod
    def validate_header(packet) -> bool:
        if packet.version not in TECMPValidator.VALID_VERSIONS:
            raise TECMPValidationError(f"Unsupported version: {packet.version}")
        
        if packet.message_type not in TECMPValidator.VALID_MESSAGE_TYPES:
            raise TECMPValidationError(f"Invalid message type: 0x{packet.message_type:02X}")
        
        norm_data_type = packet.data_type
        if packet.data_type == 0x0080:
            norm_data_type = 0x80
            
        if norm_data_type not in TECMPValidator.VALID_DATA_TYPES:
            raise TECMPValidationError(f"Unknown data type: 0x{packet.data_type:04X}")
        
        if hasattr(packet, "device_id") and packet.device_id not in TECMPValidator.KNOWN_DEVICE_IDS:
            import logging
            logging.getLogger("TECMP-Tool.TECMPValidator").warning(
                f"Unknown device ID: 0x{packet.device_id:04X}"
            )
        
        if hasattr(packet, "timestamp") and packet.timestamp is not None:
            if not validate_timestamp(packet.timestamp, allow_zero=True):
                raise TECMPValidationError(f"Invalid timestamp: {packet.timestamp}")
        
        if hasattr(packet, "timestamp_sync_status"):
            if packet.timestamp_sync_status not in [0, 1]:
                raise TECMPValidationError(
                    f"Invalid timestamp sync status: {packet.timestamp_sync_status} (must be 0 or 1)"
                )
        
        return True
    
    @staticmethod
    def validate_payload(data) -> bool:
        if data is None:
            return True
        
        if hasattr(data, "validate"):
            return data.validate()
            
        if not hasattr(data, "data_type") or not hasattr(data, "data_flags"):
            raise TECMPValidationError("TECMP data missing required attributes: data_type, data_flags")
        
        data_type = int(data.data_type)
        norm_data_type = data_type
        if data_type == 0x0080:
            norm_data_type = 0x80
            
        if norm_data_type not in TECMPValidator.VALID_DATA_TYPES:
            raise TECMPValidationError(f"Invalid data type: 0x{data_type:04X}")
        
        data_flags = int(data.data_flags)
        if data_flags < 0 or data_flags > 0xFFFF:
            raise TECMPValidationError(f"Invalid data flags: 0x{data_flags:X} (must be 0-0xFFFF)")
        
        if norm_data_type in [0x02, 0x03]:
            if hasattr(data, "can_id"):
                ide = bool(getattr(data, "ide", False))
                if not validate_can_id(data.can_id, ide):
                    raise TECMPValidationError(f"Invalid CAN ID: 0x{data.can_id:X}")
                    
            if hasattr(data, "payload"):
                max_len = 64 if norm_data_type == 0x03 else 8
                if len(data.payload) > max_len:
                    raise TECMPValidationError(
                        f"Payload too large for CAN/CAN-FD: {len(data.payload)} > {max_len} bytes"
                    )
                    
        elif norm_data_type == 0x08:
            for field in ["cycle", "channel", "frame_id"]:
                if not hasattr(data, field) or getattr(data, field) is None:
                    raise TECMPValidationError(f"Missing required FlexRay field: {field}")
            
            if hasattr(data, "cycle") and not (0 <= data.cycle <= 63):
                raise TECMPValidationError(f"Invalid FlexRay cycle: {data.cycle} (must be 0-63)")
                
            if hasattr(data, "channel") and not (0 <= data.channel <= 1):
                raise TECMPValidationError(f"Invalid FlexRay channel: {data.channel} (must be 0-1)")
                
            if hasattr(data, "frame_id") and not (0 <= data.frame_id <= 2047):
                raise TECMPValidationError(f"Invalid FlexRay frame ID: {data.frame_id} (must be 0-2047)")
        
        return True
    
    @staticmethod
    def check_segment_flags(packet) -> Tuple[bool, bool]:
        is_end = (packet.device_flags & TECMPValidator.FLAG_EOS) != 0
        is_start = (packet.device_flags & TECMPValidator.FLAG_SOS) != 0
        return (is_start, is_end)
    
    @staticmethod
    def validate_packet(packet) -> Tuple[bool, List[str]]:
        errors = []
        
        try:
            TECMPValidator.validate_header(packet)
        except TECMPValidationError as e:
            errors.append(f"Header validation error: {str(e)}")
        
        if hasattr(packet, "data") and packet.data is not None:
            try:
                if not TECMPValidator.validate_payload(packet.data):
                    errors.append("Payload validation failed")
            except Exception as e:
                errors.append(f"Payload validation error: {str(e)}")
        
        if hasattr(packet, "data") and packet.data is not None:
            if hasattr(packet.data, "data_type"):
                header_dt = packet.data_type
                payload_dt = packet.data.data_type
                
                if header_dt != payload_dt:
                    if not ((header_dt == 0x80 and payload_dt == 0x0080) or 
                             (header_dt == 0x0080 and payload_dt == 0x80)):
                        errors.append(f"Data type mismatch: header=0x{header_dt:04X}, payload=0x{payload_dt:04X}")
        
        return len(errors) == 0, errors


class TECMPPolicyValidator:
    """Policy validator with state management - CORRECTED for official TECMP format"""
    
    DEVICE_RANGES = {
        "LIN Combo": range(0x30, 0x40),
        "CAN Combo": range(0x40, 0x50), 
        "100 High": range(0x50, 0x60),
        "Eth Combo": range(0x60, 0x70),
        "1000 High": range(0x70, 0x80)
    }
    
    MAX_UNSEGMENTED_SIZE = 800
    SYNC_TIMEOUT_NS = 375_000_000
    STATE_CLEANUP_INTERVAL = 3600
    
    def __init__(self):
        self._interface_states: Dict[int, InterfaceState] = {}
        self._last_cleanup = time.time()
        self.logger = logging.getLogger("TECMP-Tool.PolicyValidator")
    
    def _cleanup_old_states(self):
        now = time.time()
        if now - self._last_cleanup < self.STATE_CLEANUP_INTERVAL:
            return
            
        cutoff = now - self.STATE_CLEANUP_INTERVAL
        self._interface_states = {
            iface_id: state for iface_id, state in self._interface_states.items()
            if state.first_seen > cutoff
        }
        self._last_cleanup = now
    
    def _get_interface_state(self, interface_id: int) -> InterfaceState:
        if interface_id not in self._interface_states:
            self._interface_states[interface_id] = InterfaceState()
        return self._interface_states[interface_id]
    
    def _validate_counter_policy(self, packet) -> List[str]:
        """Validate counter monotonicity policy"""
        errors = []
        
        if not hasattr(packet, 'interface_id') or not hasattr(packet, 'counter'):
            return errors
            
        state = self._get_interface_state(packet.interface_id)
        
        if state.last_counter is not None:
            expected = (state.last_counter + 1) & 0xFFFF
            
            if packet.counter == state.last_counter:
                errors.append("Counter should increment between packets")
            elif packet.counter != expected:
                if packet.counter < state.last_counter:
                    errors.append("Counter went backwards, packets may be out of order")
                else:
                    errors.append(f"Counter jumped from {state.last_counter} to {packet.counter}")
        
        state.last_counter = packet.counter
        state.packet_count += 1
        return errors
    
    def _validate_device_id_policy(self, packet) -> List[str]:
        """Validate device ID range policy"""
        errors = []
        
        if not hasattr(packet, 'device_id'):
            return errors
            
        device_id = packet.device_id
        
        valid_range = False
        for module_type, id_range in self.DEVICE_RANGES.items():
            if device_id in id_range:
                valid_range = True
                break
                
        if not valid_range and device_id not in [0x0080, 0x0091]:
            errors.append("Device ID outside standard TECMP ranges")
            
        return errors
    
    def _validate_segmentation_policy(self, packet) -> List[str]:
        """Validate segmentation policy for large payloads"""
        errors = []
        
        if not hasattr(packet, 'payload') or not hasattr(packet, 'device_flags'):
            return errors
            
        payload_size = len(packet.payload) if packet.payload else 0
        
        if payload_size > self.MAX_UNSEGMENTED_SIZE:
            has_sos = bool(packet.device_flags & 0x02)
            has_eos = bool(packet.device_flags & 0x01)
            
            if has_sos and has_eos:
                errors.append("Payload too large, should be segmented")
                
        return errors
    
    def _validate_timestamp_policy(self, packet) -> List[str]:
        """Validate timestamp policy"""
        errors = []
        
        if not hasattr(packet, 'timestamp') or not hasattr(packet, 'interface_id'):
            return errors
            
        state = self._get_interface_state(packet.interface_id)
        
        if packet.timestamp == 0:
            errors.append("Timestamp should not be zero for capture data")
            
        if state.last_timestamp is not None:
            if packet.timestamp < state.last_timestamp:
                errors.append("Timestamp went backwards")
            elif packet.timestamp == state.last_timestamp:
                errors.append("Timestamp should advance between packets")
                
        if hasattr(packet, 'timestamp_sync_status'):
            sync_status = packet.timestamp_sync_status
            if sync_status not in [0, 1]:
                errors.append("Invalid timestamp synchronization status")
                
        state.last_timestamp = packet.timestamp
        return errors
    
    def _validate_device_flags_policy(self, packet) -> List[str]:
        """
        ?? CORRECTED: Validate device flags combinations
        ? Official TECMP format uses 0x000F (EOS|SOS|SPY|MULTI_FRAME)
        ? This combination is VALID according to official documentation
        """
        errors = []
        
        if not hasattr(packet, 'device_flags'):
            return errors
            
        flags = packet.device_flags
        has_sos = bool(flags & 0x02)
        has_eos = bool(flags & 0x01)
        has_spy = bool(flags & 0x04)
        has_multi = bool(flags & 0x08)
        
        # ?? CORRECTION: Official TECMP format accepts 0x000F
        # The combination EOS+SOS+SPY+MULTI_FRAME is VALID and used in official traces
        # Original problematic line was:
        # if has_sos and has_eos and has_spy and has_multi:
        #     errors.append("Unusual device flags combination detected")
        
        # ? New validation: Only flag invalid combinations that are truly problematic
        # Reserved bits validation
        if flags & 0xFFF0:  # Check for reserved bits being set
            errors.append("Reserved device flag bits should not be set")
            
        return errors
    
    def _validate_crc_policy(self, packet) -> List[str]:
        """Validate CRC integrity for CAN/FlexRay"""
        errors = []
        
        if not hasattr(packet, 'data') or not packet.data:
            return errors
            
        data_type = packet.data_type
        if data_type == 0x0080:
            data_type = 0x80
            
        if data_type in [0x02, 0x03]:
            if hasattr(packet.data, 'data_flags') and (packet.data.data_flags & 0x0004):
                errors.append("CRC error detected in CAN data")
                
            if hasattr(packet.data, 'crc') and packet.data.crc is not None:
                if data_type == 0x02 and packet.data.crc == 0:
                    errors.append("CAN CRC should not be zero")
                elif data_type == 0x03 and packet.data.crc == 0:
                    errors.append("CAN-FD CRC should not be zero")
                    
        elif data_type == 0x08:
            if hasattr(packet.data, 'data_flags') and (packet.data.data_flags & 0x0004):
                errors.append("CRC error detected in FlexRay data")
                
        return errors
    
    def _validate_analog_thresholds(self, packet) -> List[str]:
        """Validate temperature/voltage ranges"""
        errors = []
        
        if not hasattr(packet, 'data_type') or packet.data_type != 0x20:
            return errors
            
        if not hasattr(packet, 'data') or not packet.data:
            return errors
            
        payload = getattr(packet.data, 'payload', b'')
        if len(payload) >= 4:
            try:
                temp = int.from_bytes(payload[0:2], 'big')
                voltage = int.from_bytes(payload[2:4], 'big')
                
                if temp < -40 or temp > 125:
                    errors.append("Temperature outside automotive range (-40C to +125C)")
                    
                if voltage < 6000 or voltage > 16000:
                    errors.append("Voltage outside automotive range (6V to 16V)")
                    
            except Exception:
                pass
                
        return errors
    
    def _validate_buffer_policy(self, packet) -> List[str]:
        """Validate buffer fill levels"""
        errors = []
        
        if hasattr(packet, 'device_flags') and (packet.device_flags & 0x10):
            errors.append("Device buffer overflow detected")
            
        if hasattr(packet, 'message_type') and packet.message_type == 0x01:
            if hasattr(packet, 'data') and packet.data:
                payload = getattr(packet.data, 'payload', b'')
                if len(payload) >= 2:
                    try:
                        fill_level = payload[0]
                        if fill_level > 95:
                            errors.append("Buffer fill level critical (>95%)")
                        elif fill_level > 85:
                            errors.append("Buffer fill level high (>85%)")
                    except Exception:
                        pass
                        
        return errors
    
    def _validate_link_quality(self, packet) -> List[str]:
        """Validate network link quality"""
        errors = []
        
        if hasattr(packet, 'message_type') and packet.message_type == 0x02:
            if hasattr(packet, 'data') and packet.data:
                payload = getattr(packet.data, 'payload', b'')
                if len(payload) >= 4:
                    try:
                        link_quality = payload[2] if len(payload) > 2 else 5
                        if link_quality < 2:
                            errors.append("Link quality poor (below threshold)")
                        elif link_quality < 3:
                            errors.append("Link quality degraded")
                    except Exception:
                        pass
                        
        return errors
    
    def _validate_event_alerting(self, packet) -> List[str]:
        """Validate event deduplication"""
        errors = []
        
        if not hasattr(packet, 'interface_id') or not hasattr(packet, 'timestamp'):
            return errors
            
        state = self._get_interface_state(packet.interface_id)
        
        if not hasattr(state, 'event_cache'):
            state.event_cache = {}
            
        if hasattr(packet, 'device_flags'):
            has_sos = bool(packet.device_flags & 0x02)
            has_eos = bool(packet.device_flags & 0x01)
            
            if has_sos and has_eos:
                if hasattr(packet, 'data') and packet.data:
                    payload = getattr(packet.data, 'payload', b'')
                    event_hash = hash(payload[:16])
                    
                    current_time = packet.timestamp / 1e9
                    
                    if event_hash in state.event_cache:
                        last_seen = state.event_cache[event_hash]
                        if current_time - last_seen < 1.0:
                            errors.append("Duplicate event within deduplication window")
                    
                    state.event_cache[event_hash] = current_time
                    
                    state.event_cache = {
                        h: t for h, t in state.event_cache.items() 
                        if current_time - t < 60.0
                    }
                    
        return errors
    
    def validate_policies(self, packet) -> List[str]:
        """Validate all TECMP policies"""
        self._cleanup_old_states()
        
        policy_errors = []
        
        try:
            policy_errors.extend(self._validate_counter_policy(packet))
            policy_errors.extend(self._validate_device_id_policy(packet))
            policy_errors.extend(self._validate_segmentation_policy(packet))
            policy_errors.extend(self._validate_timestamp_policy(packet))
            policy_errors.extend(self._validate_device_flags_policy(packet))  # ? CORRECTED
            policy_errors.extend(self._validate_crc_policy(packet))
            policy_errors.extend(self._validate_analog_thresholds(packet))
            policy_errors.extend(self._validate_buffer_policy(packet))
            policy_errors.extend(self._validate_link_quality(packet))
            policy_errors.extend(self._validate_event_alerting(packet))
        except Exception as e:
            self.logger.warning(f"Policy validation error: {e}")
            
        return policy_errors
    
    def reset_state(self):
        """Reset all interface states"""
        self._interface_states.clear()
        
    def reset_interface_state(self, interface_id: int):
        """Reset specific interface state"""
        self._interface_states.pop(interface_id, None)


_policy_validator = TECMPPolicyValidator()


class TECMPValidatorExtended:
    @staticmethod
    def validate_packet(packet) -> Tuple[bool, List[str]]:
        basic_valid, basic_errors = TECMPValidator._original_validate_packet(packet)
        
        policy_errors = _policy_validator.validate_policies(packet)
        
        all_errors = basic_errors + policy_errors
        all_valid = basic_valid and len(policy_errors) == 0
        
        return all_valid, all_errors
    
    @staticmethod
    def reset_policy_state():
        _policy_validator.reset_state()
        
    @staticmethod
    def reset_interface_policy_state(interface_id: int):
        _policy_validator.reset_interface_state(interface_id)


def _patch_tecmp_validator():
    """Patch existing TECMPValidator to include policies"""
    try:
        if not hasattr(TECMPValidator, '_original_validate_packet'):
            TECMPValidator._original_validate_packet = TECMPValidator.validate_packet
            
        TECMPValidator.validate_packet = TECMPValidatorExtended.validate_packet
        TECMPValidator.reset_policy_state = TECMPValidatorExtended.reset_policy_state
        TECMPValidator.reset_interface_policy_state = TECMPValidatorExtended.reset_interface_policy_state
        
    except Exception as e:
        logging.getLogger("TECMP-Tool.PolicyValidator").warning(
            f"Could not patch TECMPValidator: {e}, policies available via TECMPValidatorExtended"
        )


# ? Apply the patch
_patch_tecmp_validator()


# ?? SUMMARY OF CORRECTIONS:
# ===========================
# 
# ?? MAIN FIX: _validate_device_flags_policy() method (lines ~301-302)
#    - REMOVED: Rejection of 0x000F flag combination 
#    - REASON: Official TECMP format uses EOS|SOS|SPY|MULTI_FRAME = 0x000F
#    - RESULT: Now accepts official TECMP traces without "Unusual device flags" error
#
# ? COMPATIBILITY:
#    - Maintains all other validations
#    - Still validates reserved bits (0xFFF0)
#    - Preserves policy validation architecture
#    - Backward compatible with existing code
#