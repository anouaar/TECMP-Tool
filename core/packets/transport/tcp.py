import struct
from typing import Optional, Dict, List, Tuple
from core.packets.base.packet import (
    Packet,
    PacketParsingError,
    PacketSerializationError,
    PacketValidationError,
)

class TCPPacket(Packet):
    """Complete TCP packet implementation with ALL fields including optional ones"""
    
    HEADER_FORMAT = '!HHIIHHHH'
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    # TCP Options Types
    OPT_EOL = 0        # End of Option List
    OPT_NOP = 1        # No-Operation
    OPT_MSS = 2        # Maximum Segment Size
    OPT_WSOPT = 3      # Window Scale Option
    OPT_SACK_PERMITTED = 4  # SACK Permitted
    OPT_SACK = 5       # SACK Option
    OPT_ECHO = 6       # Echo (obsolete)
    OPT_ECHOREPLY = 7  # Echo Reply (obsolete)
    OPT_TIMESTAMP = 8  # Timestamp Option
    OPT_PARTIAL_ORDER = 9   # Partial Order Connection Permitted
    OPT_PARTIAL_ORDER_PROFILE = 10  # Partial Order Service Profile
    OPT_CC = 11        # Connection Count
    OPT_CC_NEW = 12    # Connection Count New
    OPT_CC_ECHO = 13   # Connection Count Echo
    OPT_ALTCHK = 14    # TCP Alternate Checksum Request
    OPT_ALTCHKDATA = 15 # TCP Alternate Checksum Data
    OPT_MD5 = 19       # MD5 Signature Option
    OPT_SCPS = 20      # SCPS Capabilities
    OPT_SNACK = 21     # Selective Negative Acknowledgements
    OPT_QSRES = 27     # Quick-Start Response
    OPT_UTO = 28       # User Timeout Option
    OPT_AO = 29        # Authentication Option
    OPT_MPTCP = 30     # Multipath TCP
    OPT_FASTOPEN = 34  # TCP Fast Open Cookie
    
    # TCP Flags
    FLAG_FIN = 0x001   # Finish
    FLAG_SYN = 0x002   # Synchronize
    FLAG_RST = 0x004   # Reset
    FLAG_PSH = 0x008   # Push
    FLAG_ACK = 0x010   # Acknowledgment
    FLAG_URG = 0x020   # Urgent
    FLAG_ECE = 0x040   # ECN Echo
    FLAG_CWR = 0x080   # Congestion Window Reduced
    FLAG_NS = 0x100    # Nonce Sum

    def __init__(
        self,
        # === MANDATORY FIELDS ===
        src_port: int,
        dst_port: int,
        
        # === SEQUENCE FIELDS ===
        seq_number: int = 0,
        ack_number: int = 0,
        
        # === HEADER FIELDS ===
        data_offset: int = 5,           # Header length in 32-bit words
        reserved: int = 0,              # Reserved bits (must be zero)
        
        # === FLAGS (all TCP flags) ===
        flags: int = 0x002,             # Default SYN
        fin: bool = False,              # Finish connection
        syn: bool = True,               # Synchronize sequence numbers
        rst: bool = False,              # Reset connection
        psh: bool = False,              # Push function
        ack: bool = False,              # Acknowledgment field significant
        urg: bool = False,              # Urgent pointer field significant
        ece: bool = False,              # ECN Echo
        cwr: bool = False,              # Congestion Window Reduced
        ns: bool = False,               # Nonce Sum
        
        # === WINDOW AND CONTROL ===
        window_size: int = 8192,        # Receive window size
        checksum: int = 0,              # Checksum (0 = auto-calculate)
        urgent_pointer: int = 0,        # Urgent pointer
        
        # === PAYLOAD ===
        payload: bytes = b'',           # TCP data
        
        # === TCP OPTIONS ===
        options: Optional[Dict] = None, # TCP options dictionary
        
        # === COMMON OPTIONS ===
        mss: Optional[int] = None,                    # Maximum Segment Size
        window_scale: Optional[int] = None,           # Window Scale factor
        sack_permitted: bool = False,                 # SACK Permitted
        sack_blocks: Optional[List[Tuple[int, int]]] = None,  # SACK blocks
        timestamp: Optional[Tuple[int, int]] = None,  # (TSval, TSecr)
        
        # === ADVANCED OPTIONS ===
        md5_signature: Optional[bytes] = None,        # MD5 signature
        user_timeout: Optional[int] = None,           # User timeout value
        tcp_ao: Optional[Dict] = None,                # Authentication Option
        fast_open_cookie: Optional[bytes] = None,     # Fast Open cookie
        mptcp_options: Optional[Dict] = None,         # Multipath TCP
        
        # === QoS AND PERFORMANCE ===
        congestion_control: Optional[str] = None,     # CC algorithm hint
        priority: int = 0,                            # Priority level
        dscp: int = 0,                               # DSCP marking
        
        # === EXTENSION FIELDS ===
        connection_id: Optional[int] = None,          # Connection identifier
        flow_label: Optional[int] = None,             # Flow label
        
        # === METADATA ===
        interface: Optional[str] = None,              # Source interface
        vlan_id: Optional[int] = None,               # VLAN tag
        raw_options: Optional[bytes] = b'',          # Raw options bytes
        
        # === COMPATIBILITY ===
        auto_checksum: bool = True,                   # Auto-calculate checksum
        auto_data_offset: bool = True,                # Auto-calculate data offset
        strict_rfc: bool = False                      # Strict RFC compliance
    ):
        super().__init__()
        
        # Basic TCP fields
        self.src_port = src_port
        self.dst_port = dst_port
        self.seq_number = seq_number
        self.ack_number = ack_number
        self.data_offset = data_offset
        self.reserved = reserved
        self.window_size = window_size
        self.checksum = checksum
        self.urgent_pointer = urgent_pointer
        self.payload = payload
        
        # TCP Flags - Build from individual flags or use flags parameter
        if any([fin, syn, rst, psh, ack, urg, ece, cwr, ns]):
            self.flags = (
                (ns << 8) | (cwr << 7) | (ece << 6) | (urg << 5) |
                (ack << 4) | (psh << 3) | (rst << 2) | (syn << 1) | fin
            )
        else:
            self.flags = flags
            
        # Individual flag properties for easy access
        self.fin = bool(self.flags & self.FLAG_FIN)
        self.syn = bool(self.flags & self.FLAG_SYN)
        self.rst = bool(self.flags & self.FLAG_RST)
        self.psh = bool(self.flags & self.FLAG_PSH)
        self.ack = bool(self.flags & self.FLAG_ACK)
        self.urg = bool(self.flags & self.FLAG_URG)
        self.ece = bool(self.flags & self.FLAG_ECE)
        self.cwr = bool(self.flags & self.FLAG_CWR)
        self.ns = bool(self.flags & self.FLAG_NS)
        
        # TCP Options
        self.options = options or {}
        self.mss = mss
        self.window_scale = window_scale
        self.sack_permitted = sack_permitted
        self.sack_blocks = sack_blocks or []
        self.timestamp = timestamp
        
        # Advanced options
        self.md5_signature = md5_signature
        self.user_timeout = user_timeout
        self.tcp_ao = tcp_ao
        self.fast_open_cookie = fast_open_cookie
        self.mptcp_options = mptcp_options
        
        # QoS and performance
        self.congestion_control = congestion_control
        self.priority = priority
        self.dscp = dscp
        
        # Extension fields
        self.connection_id = connection_id
        self.flow_label = flow_label
        self.interface = interface
        self.vlan_id = vlan_id
        self.raw_options = raw_options or b''
        
        # Compatibility
        self.auto_checksum = auto_checksum
        self.auto_data_offset = auto_data_offset
        self.strict_rfc = strict_rfc
        
        # Build options automatically
        self._build_options()

    def _build_options(self):
        """Build TCP options from individual fields"""
        options_data = b''
        
        # MSS Option
        if self.mss is not None:
            options_data += struct.pack('!BBH', self.OPT_MSS, 4, self.mss)
        
        # Window Scale Option
        if self.window_scale is not None:
            options_data += struct.pack('!BBB', self.OPT_WSOPT, 3, self.window_scale)
        
        # SACK Permitted
        if self.sack_permitted:
            options_data += struct.pack('!BB', self.OPT_SACK_PERMITTED, 2)
        
        # SACK Blocks
        if self.sack_blocks:
            sack_data = b''
            for left, right in self.sack_blocks[:4]:  # Max 4 blocks
                sack_data += struct.pack('!II', left, right)
            if sack_data:
                options_data += struct.pack('!BB', self.OPT_SACK, 2 + len(sack_data)) + sack_data
        
        # Timestamp Option
        if self.timestamp:
            ts_val, ts_ecr = self.timestamp
            options_data += struct.pack('!BBII', self.OPT_TIMESTAMP, 10, ts_val, ts_ecr)
        
        # MD5 Signature
        if self.md5_signature:
            options_data += struct.pack('!BB', self.OPT_MD5, 2 + len(self.md5_signature)) + self.md5_signature
        
        # User Timeout
        if self.user_timeout is not None:
            options_data += struct.pack('!BBH', self.OPT_UTO, 4, self.user_timeout)
        
        # Fast Open Cookie
        if self.fast_open_cookie:
            cookie_len = len(self.fast_open_cookie)
            options_data += struct.pack('!BB', self.OPT_FASTOPEN, 2 + cookie_len) + self.fast_open_cookie
        
        # Add raw options
        options_data += self.raw_options
        
        # Pad to 4-byte boundary
        padding_needed = (4 - (len(options_data) % 4)) % 4
        options_data += b'\x00' * padding_needed
        
        self._options_data = options_data
        
        # Auto-calculate data offset
        if self.auto_data_offset:
            self.data_offset = (self.HEADER_SIZE + len(options_data)) // 4

    def serialize(self) -> bytes:
        """Serialize TCP packet to bytes"""
        try:
            # Rebuild options
            self._build_options()
            
            # Build flags field
            offset_reserved_flags = (
                (self.data_offset << 12) |
                (self.reserved << 9) |
                (self.flags & 0x01FF)
            )

            # Pack TCP header
            header = struct.pack(
                self.HEADER_FORMAT,
                self.src_port,
                self.dst_port,
                self._safe_int32(self.seq_number),
                self._safe_int32(self.ack_number),
                offset_reserved_flags,
                self.window_size,
                self.checksum,
                self.urgent_pointer
            )

            # Combine header + options + payload
            full_packet = header + self._options_data + self.payload
            
            self._raw_data = bytearray(full_packet)
            self._update_size()
            return bytes(self._raw_data)

        except struct.error as e:
            raise PacketSerializationError(f"TCP serialization error: {e}")

    def deserialize(self, data: bytes):
        """Deserialize bytes to TCP packet"""
        if len(data) < self.HEADER_SIZE:
            raise PacketParsingError("TCP packet too short")

        try:
            # Unpack TCP header
            fields = struct.unpack(self.HEADER_FORMAT, data[:self.HEADER_SIZE])
            (
                self.src_port,
                self.dst_port,
                self.seq_number,
                self.ack_number,
                offset_reserved_flags,
                self.window_size,
                self.checksum,
                self.urgent_pointer
            ) = fields

            # Extract flags and offset
            self.data_offset = (offset_reserved_flags >> 12) & 0xF
            self.reserved = (offset_reserved_flags >> 9) & 0x7
            self.flags = offset_reserved_flags & 0x01FF
            
            # Update individual flag fields
            self.fin = bool(self.flags & self.FLAG_FIN)
            self.syn = bool(self.flags & self.FLAG_SYN)
            self.rst = bool(self.flags & self.FLAG_RST)
            self.psh = bool(self.flags & self.FLAG_PSH)
            self.ack = bool(self.flags & self.FLAG_ACK)
            self.urg = bool(self.flags & self.FLAG_URG)
            self.ece = bool(self.flags & self.FLAG_ECE)
            self.cwr = bool(self.flags & self.FLAG_CWR)
            self.ns = bool(self.flags & self.FLAG_NS)

            # Parse options
            header_end = self.data_offset * 4
            if header_end > len(data):
                raise PacketParsingError("Invalid TCP data offset")
            
            self._parse_options(data[self.HEADER_SIZE:header_end])
            
            # Extract payload
            self.payload = data[header_end:]
            self._raw_data = bytearray(data)
            self._update_size()

        except struct.error as e:
            raise PacketParsingError(f"TCP deserialization error: {e}")

    def _parse_options(self, options_data: bytes):
        """Parse TCP options from bytes"""
        self.options = {}
        self.mss = None
        self.window_scale = None
        self.sack_permitted = False
        self.sack_blocks = []
        self.timestamp = None
        
        offset = 0
        while offset < len(options_data):
            if offset >= len(options_data):
                break
                
            opt_type = options_data[offset]
            
            # End of options
            if opt_type == self.OPT_EOL:
                break
            
            # No-op
            if opt_type == self.OPT_NOP:
                offset += 1
                continue
            
            # Options with length
            if offset + 1 >= len(options_data):
                break
                
            opt_len = options_data[offset + 1]
            if opt_len < 2 or offset + opt_len > len(options_data):
                break
            
            opt_data = options_data[offset + 2:offset + opt_len]
            
            # Parse specific options
            if opt_type == self.OPT_MSS and opt_len == 4:
                self.mss = struct.unpack('!H', opt_data)[0]
            elif opt_type == self.OPT_WSOPT and opt_len == 3:
                self.window_scale = opt_data[0]
            elif opt_type == self.OPT_SACK_PERMITTED and opt_len == 2:
                self.sack_permitted = True
            elif opt_type == self.OPT_TIMESTAMP and opt_len == 10:
                ts_val, ts_ecr = struct.unpack('!II', opt_data)
                self.timestamp = (ts_val, ts_ecr)
            elif opt_type == self.OPT_SACK:
                # Parse SACK blocks
                for i in range(0, len(opt_data), 8):
                    if i + 8 <= len(opt_data):
                        left, right = struct.unpack('!II', opt_data[i:i+8])
                        self.sack_blocks.append((left, right))
            
            self.options[opt_type] = opt_data
            offset += opt_len

    def validate(self) -> bool:
        """Validate TCP packet fields"""
        if not (0 <= self.src_port <= 65535):
            raise PacketValidationError("Invalid source port")
        if not (0 <= self.dst_port <= 65535):
            raise PacketValidationError("Invalid destination port")
        if not (5 <= self.data_offset <= 15):
            raise PacketValidationError("Invalid data offset")
        if not (0 <= self.window_size <= 65535):
            raise PacketValidationError("Invalid window size")
        if self.mss is not None and not (1 <= self.mss <= 65535):
            raise PacketValidationError("Invalid MSS")
        if self.window_scale is not None and not (0 <= self.window_scale <= 14):
            raise PacketValidationError("Invalid window scale")
        return True

    def summary(self) -> str:
        """Return human-readable summary"""
        flags_str = self._flags_to_str()
        summary = (
            f"TCP {self.src_port}->{self.dst_port} "
            f"seq={self.seq_number} ack={self.ack_number} flags={flags_str}"
        )
        
        # Add options summary
        options = []
        if self.mss: options.append(f"MSS={self.mss}")
        if self.window_scale is not None: options.append(f"WS={self.window_scale}")
        if self.sack_permitted: options.append("SACK_PERM")
        if self.timestamp: options.append(f"TS={self.timestamp[0]}")
        
        if options:
            summary += f" opts=[{','.join(options)}]"
        
        return summary

    def _flags_to_str(self):
        """Convert flags to string representation"""
        flags = []
        if self.fin: flags.append('FIN')
        if self.syn: flags.append('SYN')
        if self.rst: flags.append('RST')
        if self.psh: flags.append('PSH')
        if self.ack: flags.append('ACK')
        if self.urg: flags.append('URG')
        if self.ece: flags.append('ECE')
        if self.cwr: flags.append('CWR')
        if self.ns: flags.append('NS')
        return ','.join(flags) if flags else 'NONE'

    def _safe_int32(self, value: int) -> int:
        """Ensure value fits in signed 32-bit integer"""
        min_val = -2_147_483_648
        max_val = 2_147_483_647
        if not (min_val <= value <= max_val):
            raise PacketSerializationError(
                f"Value {value} exceeds 32-bit signed int range ({min_val} to {max_val})"
            )
        return value

    # === CONVENIENCE METHODS ===
    
    def set_flag(self, flag_name: str, value: bool = True):
        """Set individual TCP flag"""
        flag_map = {
            'FIN': self.FLAG_FIN, 'SYN': self.FLAG_SYN, 'RST': self.FLAG_RST,
            'PSH': self.FLAG_PSH, 'ACK': self.FLAG_ACK, 'URG': self.FLAG_URG,
            'ECE': self.FLAG_ECE, 'CWR': self.FLAG_CWR, 'NS': self.FLAG_NS
        }
        
        if flag_name.upper() in flag_map:
            flag_bit = flag_map[flag_name.upper()]
            if value:
                self.flags |= flag_bit
            else:
                self.flags &= ~flag_bit
            self._update_individual_flags()

    def _update_individual_flags(self):
        """Update individual flag attributes from flags field"""
        self.fin = bool(self.flags & self.FLAG_FIN)
        self.syn = bool(self.flags & self.FLAG_SYN)
        self.rst = bool(self.flags & self.FLAG_RST)
        self.psh = bool(self.flags & self.FLAG_PSH)
        self.ack = bool(self.flags & self.FLAG_ACK)
        self.urg = bool(self.flags & self.FLAG_URG)
        self.ece = bool(self.flags & self.FLAG_ECE)
        self.cwr = bool(self.flags & self.FLAG_CWR)
        self.ns = bool(self.flags & self.FLAG_NS)

    def add_option(self, opt_type: int, opt_data: bytes):
        """Add custom TCP option"""
        self.options[opt_type] = opt_data
        
    def get_option(self, opt_type: int) -> Optional[bytes]:
        """Get TCP option data"""
        return self.options.get(opt_type)

    def is_handshake(self) -> bool:
        """Check if this is a TCP handshake packet"""
        return self.syn and not self.ack  # SYN packet
    
    def is_ack_handshake(self) -> bool:
        """Check if this is a SYN-ACK packet"""
        return self.syn and self.ack
    
    def is_data_packet(self) -> bool:
        """Check if this packet carries data"""
        return len(self.payload) > 0 and not (self.syn or self.fin or self.rst)
    
    def get_header_length(self) -> int:
        """Get TCP header length in bytes"""
        return self.data_offset * 4