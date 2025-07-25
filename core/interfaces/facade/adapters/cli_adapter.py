#!/usr/bin/env python
# coding: utf-8
"""
CLI Adapter for TECMP-Tool.

This adapter provides a command-line interface that connects to the central
TECMPFacade, enabling all TECMP tool functionality via command line.
"""
import argparse
import logging
import sys
import os
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# Import the central facade
from core.interfaces.facade.tecmp_facade import TECMPFacade


class CLIAdapter:
    """
    Command-line interface adapter for the TECMP tool.
    
    This adapter provides a comprehensive CLI that connects to the TECMPFacade,
    allowing users to perform all operations via command line including:
    - Protocol stack management
    - TECMP encapsulation operations
    - Packet generation and analysis
    - Trace file operations
    - Configuration management
    """
    
    def __init__(self, facade: TECMPFacade):
        """
        Initialize the CLI adapter.
        
        Args:
            facade: Central TECMP facade instance
        """
        self.facade = facade
        self.logger = logging.getLogger("TECMP-Tool.CLIAdapter")
        
        # Output formatting options
        self.output_format = "text"  # text, json, csv
        self.verbose = False
        self.quiet = False
        
        # State tracking
        self.last_operation_success = True
        self.last_error_message = ""
        
        # Connect to facade signals for monitoring
        self._setup_facade_connections()
        
        self.logger.info("CLI Adapter initialized successfully")
    
    def _setup_facade_connections(self):
        """Setup connections to facade signals for monitoring."""
        self.facade.operation_completed.connect(self._on_operation_completed)
        self.facade.error_occurred.connect(self._on_error_occurred)
    
    def _on_operation_completed(self, success: bool, message: str):
        """Handle operation completion from facade."""
        self.last_operation_success = success
        if not success:
            self.last_error_message = message
    
    def _on_error_occurred(self, error_info):
        """Handle error occurrences from facade."""
        self.last_operation_success = False
        self.last_error_message = str(error_info) if error_info else "Unknown error"
    
    def set_output_format(self, format_type: str):
        """
        Set the output format for command results.
        
        Args:
            format_type: Output format ('text', 'json', 'csv')
        """
        if format_type in ['text', 'json', 'csv']:
            self.output_format = format_type
        else:
            self._print_error(f"Invalid output format: {format_type}")
    
    def set_verbosity(self, verbose: bool = False, quiet: bool = False):
        """
        Set verbosity level.
        
        Args:
            verbose: Enable verbose output
            quiet: Enable quiet mode (minimal output)
        """
        self.verbose = verbose
        self.quiet = quiet
        
        # Configure logging level
        if quiet:
            logging.getLogger().setLevel(logging.ERROR)
        elif verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)
    
    def _print_output(self, message: str, level: str = "info"):
        """
        Print output message based on verbosity settings.
        
        Args:
            message: Message to print
            level: Message level ('info', 'warning', 'error', 'success')
        """
        if self.quiet and level not in ['error', 'warning']:
            return
        
        # Color coding for terminals that support it
        colors = {
            'info': '\033[0m',      # Default
            'success': '\033[92m',  # Green
            'warning': '\033[93m',  # Yellow
            'error': '\033[91m',    # Red
            'reset': '\033[0m'      # Reset
        }
        
        if sys.stdout.isatty():  # Terminal supports colors
            color = colors.get(level, colors['info'])
            print(f"{color}{message}{colors['reset']}")
        else:
            print(message)
    
    def _print_success(self, message: str):
        """Print success message."""
        self._print_output(f"? {message}", "success")
    
    def _print_warning(self, message: str):
        """Print warning message."""
        self._print_output(f"? {message}", "warning")
    
    def _print_error(self, message: str):
        """Print error message."""
        self._print_output(f"? {message}", "error")
    
    def _print_info(self, message: str):
        """Print info message."""
        if not self.quiet:
            self._print_output(f"? {message}", "info")
    
    def _format_output(self, data: Any, title: str = "") -> str:
        """
        Format output data according to the selected format.
        
        Args:
            data: Data to format
            title: Optional title for the output
            
        Returns:
            Formatted string
        """
        if self.output_format == "json":
            return json.dumps(data, indent=2, default=str)
        elif self.output_format == "csv":
            return self._format_as_csv(data)
        else:  # text format
            return self._format_as_text(data, title)
    
    def _format_as_text(self, data: Any, title: str = "") -> str:
        """Format data as human-readable text."""
        if title:
            output = [title, "=" * len(title), ""]
        else:
            output = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    output.append(f"{key}:")
                    for sub_key, sub_value in value.items():
                        output.append(f"  {sub_key}: {sub_value}")
                elif isinstance(value, list):
                    output.append(f"{key}: {len(value)} items")
                    if self.verbose:
                        for i, item in enumerate(value):
                            output.append(f"  [{i}] {item}")
                else:
                    output.append(f"{key}: {value}")
        elif isinstance(data, list):
            output.append(f"Total items: {len(data)}")
            for i, item in enumerate(data):
                output.append(f"[{i}] {item}")
        else:
            output.append(str(data))
        
        return "\n".join(output)
    
    def _format_as_csv(self, data: Any) -> str:
        """Format data as CSV."""
        if isinstance(data, dict):
            # Convert dict to CSV rows
            lines = ["key,value"]
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                lines.append(f'"{key}","{value}"')
            return "\n".join(lines)
        elif isinstance(data, list):
            # Simple list to CSV
            return "\n".join([f'"{item}"' for item in data])
        else:
            return str(data)
    
    # Protocol management commands
    
    def cmd_list_protocols(self, args):
        """List current protocols in the stack."""
        protocols = self.facade.get_protocol_stack()
        
        if not protocols:
            self._print_info("No protocols in the current stack")
            return 0
        
        # Format protocol information
        protocol_info = []
        for i, protocol in enumerate(protocols):
            if isinstance(protocol, dict):
                name = protocol.get('name', f'Protocol {i+1}')
                config = protocol.get('config', {})
                protocol_info.append({
                    'index': i,
                    'name': name,
                    'config': config
                })
            else:
                protocol_info.append({
                    'index': i,
                    'name': str(protocol),
                    'config': {}
                })
        
        output = self._format_output(protocol_info, "Current Protocol Stack")
        print(output)
        
        return 0
    
    def cmd_add_protocol(self, args):
        """Add a protocol to the stack."""
        protocol_name = args.protocol
        config = {}
        
        # Parse configuration if provided
        if args.config:
            try:
                if args.config.startswith('{'):
                    config = json.loads(args.config)
                else:
                    # Parse key=value pairs
                    for pair in args.config.split(','):
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            config[key.strip()] = value.strip()
            except (json.JSONDecodeError, ValueError) as e:
                self._print_error(f"Invalid configuration format: {e}")
                return 1
        
        # Add protocol through facade
        success = self.facade.add_protocol(protocol_name, config)
        
        if success:
            self._print_success(f"Added protocol: {protocol_name}")
            
            if self.verbose:
                self.cmd_list_protocols(args)
            
            return 0
        else:
            self._print_error(f"Failed to add protocol: {protocol_name}")
            if self.last_error_message:
                self._print_error(f"Error: {self.last_error_message}")
            return 1
    
    def cmd_remove_protocol(self, args):
        """Remove a protocol from the stack."""
        index = args.index
        
        # Validate index
        protocols = self.facade.get_protocol_stack()
        if index < 0 or index >= len(protocols):
            self._print_error(f"Invalid protocol index: {index}")
            return 1
        
        # Get protocol name for feedback
        protocol_name = "Unknown"
        if isinstance(protocols[index], dict):
            protocol_name = protocols[index].get('name', f'Protocol {index}')
        
        # Remove protocol through facade
        success = self.facade.remove_protocol(index)
        
        if success:
            self._print_success(f"Removed protocol at index {index}: {protocol_name}")
            
            if self.verbose:
                self.cmd_list_protocols(args)
            
            return 0
        else:
            self._print_error(f"Failed to remove protocol at index {index}")
            if self.last_error_message:
                self._print_error(f"Error: {self.last_error_message}")
            return 1
    
    def cmd_move_protocol(self, args):
        """Move a protocol within the stack."""
        from_index = args.from_index
        to_index = args.to_index
        
        # Validate indices
        protocols = self.facade.get_protocol_stack()
        if from_index < 0 or from_index >= len(protocols):
            self._print_error(f"Invalid source index: {from_index}")
            return 1
        
        if to_index < 0 or to_index >= len(protocols):
            self._print_error(f"Invalid destination index: {to_index}")
            return 1
        
        # Move protocol through facade
        success = self.facade.move_protocol(from_index, to_index)
        
        if success:
            self._print_success(f"Moved protocol from index {from_index} to {to_index}")
            
            if self.verbose:
                self.cmd_list_protocols(args)
            
            return 0
        else:
            self._print_error(f"Failed to move protocol from {from_index} to {to_index}")
            if self.last_error_message:
                self._print_error(f"Error: {self.last_error_message}")
            return 1
    
    def cmd_clear_protocols(self, args):
        """Clear all protocols from the stack."""
        protocols = self.facade.get_protocol_stack()
        
        if not protocols:
            self._print_info("Protocol stack is already empty")
            return 0
        
        # Confirm if not forced
        if not args.force:
            response = input(f"Clear all {len(protocols)} protocols? [y/N]: ")
            if response.lower() not in ['y', 'yes']:
                self._print_info("Operation cancelled")
                return 0
        
        # Remove all protocols
        success_count = 0
        for i in range(len(protocols) - 1, -1, -1):
            if self.facade.remove_protocol(i):
                success_count += 1
        
        if success_count == len(protocols):
            self._print_success(f"Cleared all {success_count} protocols")
            return 0
        else:
            self._print_warning(f"Cleared {success_count} of {len(protocols)} protocols")
            return 1
    
    # TECMP encapsulation commands
    
    def cmd_tecmp_status(self, args):
        """Show TECMP encapsulation status."""
        is_encapsulated = self.facade.is_tecmp_encapsulated()
        
        status_info = {
            'encapsulated': is_encapsulated,
            'protocol_count': len(self.facade.get_protocol_stack())
        }
        
        if is_encapsulated:
            # Get additional TECMP info if available
            if hasattr(self.facade, 'get_tecmp_config'):
                config = self.facade.get_tecmp_config()
                status_info['tecmp_config'] = config
        
        output = self._format_output(status_info, "TECMP Encapsulation Status")
        print(output)
        
        return 0
    
    def cmd_tecmp_add(self, args):
        """Add TECMP encapsulation."""
        protocols = self.facade.get_protocol_stack()
        
        if not protocols:
            self._print_error("No protocols to encapsulate. Add protocols first.")
            return 1
        
        if self.facade.is_tecmp_encapsulated():
            self._print_warning("TECMP encapsulation already active")
            return 0
        
        # Add TECMP encapsulation
        success = self.facade.add_tecmp_encapsulation()
        
        if success:
            self._print_success("TECMP encapsulation added successfully")
            
            if self.verbose:
                self.cmd_tecmp_status(args)
            
            return 0
        else:
            self._print_error("Failed to add TECMP encapsulation")
            if self.last_error_message:
                self._print_error(f"Error: {self.last_error_message}")
            return 1
    
    def cmd_tecmp_remove(self, args):
        """Remove TECMP encapsulation."""
        if not self.facade.is_tecmp_encapsulated():
            self._print_warning("TECMP encapsulation is not active")
            return 0
        
        # Confirm if not forced
        if not args.force:
            response = input("Remove TECMP encapsulation? [y/N]: ")
            if response.lower() not in ['y', 'yes']:
                self._print_info("Operation cancelled")
                return 0
        
        # Remove TECMP encapsulation
        success = self.facade.remove_tecmp_encapsulation()
        
        if success:
            self._print_success("TECMP encapsulation removed successfully")
            
            if self.verbose:
                self.cmd_tecmp_status(args)
            
            return 0
        else:
            self._print_error("Failed to remove TECMP encapsulation")
            if self.last_error_message:
                self._print_error(f"Error: {self.last_error_message}")
            return 1
    
    # Packet operations
    
    def cmd_generate_packet(self, args):
        """Generate a packet from the current protocol stack."""
        protocols = self.facade.get_protocol_stack()
        
        if not protocols:
            self._print_error("No protocols defined. Add protocols first.")
            return 1
        
        try:
            # Generate packet
            if self.facade.is_tecmp_encapsulated():
                packet = self.facade.create_tecmp_packet()
            else:
                # For non-TECMP, we need packet building logic
                self._print_error("Direct packet generation not implemented. Use TECMP encapsulation.")
                return 1
            
            if packet:
                self.facade.set_current_packet(packet)
                self._print_success("Packet generated successfully")
                
                # Show packet info if verbose
                if self.verbose:
                    packet_bytes = self.facade.get_packet_bytes(packet)
                    if packet_bytes:
                        self._print_info(f"Packet size: {len(packet_bytes)} bytes")
                        
                        # Show hex preview
                        if len(packet_bytes) <= 64:  # Show full hex for small packets
                            hex_str = packet_bytes.hex()
                            formatted_hex = ' '.join([hex_str[i:i+2] for i in range(0, len(hex_str), 2)])
                            self._print_info(f"Hex: {formatted_hex}")
                        else:
                            # Show first 32 bytes
                            hex_str = packet_bytes[:32].hex()
                            formatted_hex = ' '.join([hex_str[i:i+2] for i in range(0, len(hex_str), 2)])
                            self._print_info(f"Hex (first 32 bytes): {formatted_hex}...")
                
                return 0
            else:
                self._print_error("Failed to generate packet")
                return 1
                
        except Exception as e:
            self._print_error(f"Error generating packet: {str(e)}")
            return 1
    
    def cmd_show_packet(self, args):
        """Show details of the current packet."""
        packet = self.facade.get_current_packet()
        
        if not packet:
            self._print_error("No current packet. Generate or load a packet first.")
            return 1
        
        try:
            # Get packet information
            packet_info = {
                'type': packet.__class__.__name__,
                'size': 0
            }
            
            # Get packet bytes
            packet_bytes = self.facade.get_packet_bytes(packet)
            if packet_bytes:
                packet_info['size'] = len(packet_bytes)
                packet_info['hex'] = packet_bytes.hex()
            
            # Get packet summary if available
            if hasattr(packet, 'summary'):
                packet_info['summary'] = packet.summary()
            elif hasattr(packet, '__str__'):
                packet_info['summary'] = str(packet)
            
            # Format output
            if args.hex_only:
                if packet_bytes:
                    print(packet_bytes.hex())
                else:
                    self._print_error("Could not get packet bytes")
                    return 1
            else:
                output = self._format_output(packet_info, "Current Packet Details")
                print(output)
            
            return 0
            
        except Exception as e:
            self._print_error(f"Error showing packet: {str(e)}")
            return 1
    
    # File operations
    
    def cmd_save_packet(self, args):
        """Save the current packet to a file."""
        packet = self.facade.get_current_packet()
        
        if not packet:
            self._print_error("No current packet to save. Generate or load a packet first.")
            return 1
        
        file_path = args.output
        file_type = args.format or "pcap"
        
        try:
            # Get packet data
            if file_type in ["pcap", "bin", "binary"]:
                packet_bytes = self.facade.get_packet_bytes(packet)
                if not packet_bytes:
                    self._print_error("Could not serialize packet")
                    return 1
                content = packet_bytes
            elif file_type == "json":
                # Convert packet to JSON representation
                packet_info = {
                    'type': packet.__class__.__name__,
                    'data': packet_bytes.hex() if packet_bytes else None,
                    'size': len(packet_bytes) if packet_bytes else 0
                }
                if hasattr(packet, 'summary'):
                    packet_info['summary'] = packet.summary()
                content = packet_info
            else:
                self._print_error(f"Unsupported format: {file_type}")
                return 1
            
            # Save file
            success, size = self.facade.save_file(file_path, content, file_type)
            
            if success:
                self._print_success(f"Packet saved to {file_path} ({size} bytes)")
                return 0
            else:
                self._print_error(f"Failed to save packet to {file_path}")
                return 1
                
        except Exception as e:
            self._print_error(f"Error saving packet: {str(e)}")
            return 1
    
    def cmd_load_project(self, args):
        """Load a project file."""
        file_path = args.input
        
        if not os.path.isfile(file_path):
            self._print_error(f"Project file not found: {file_path}")
            return 1
        
        try:
            # Load project
            success = self.facade.load_file(file_path, "project")
            
            if success:
                self._print_success(f"Project loaded from {file_path}")
                
                if self.verbose:
                    self.cmd_list_protocols(args)
                    self.cmd_tecmp_status(args)
                
                return 0
            else:
                self._print_error(f"Failed to load project from {file_path}")
                return 1
                
        except Exception as e:
            self._print_error(f"Error loading project: {str(e)}")
            return 1
    
    def cmd_save_project(self, args):
        """Save current state as a project file."""
        file_path = args.output
        
        try:
            # Create project data
            project_data = {
                "version": "1.0",
                "protocols": self.facade.get_protocol_stack(),
                "tecmp_encapsulated": self.facade.is_tecmp_encapsulated(),
                "timestamp": time.time()
            }
            
            # Save project
            success, size = self.facade.save_file(file_path, project_data, "project")
            
            if success:
                self._print_success(f"Project saved to {file_path} ({size} bytes)")
                return 0
            else:
                self._print_error(f"Failed to save project to {file_path}")
                return 1
                
        except Exception as e:
            self._print_error(f"Error saving project: {str(e)}")
            return 1
    
    # Trace operations
    
    def cmd_open_trace(self, args):
        """Open and analyze a trace file."""
        if hasattr(args, 'input') and args.input:
            # Load specific file
            file_path = args.input
            
            if not os.path.isfile(file_path):
                self._print_error(f"Trace file not found: {file_path}")
                return 1
            
            try:
                success = self.facade.load_file(file_path, "pcap")
                
                if success:
                    self._print_success(f"Trace loaded from {file_path}")
                    return 0
                else:
                    self._print_error(f"Failed to load trace from {file_path}")
                    return 1
                    
            except Exception as e:
                self._print_error(f"Error loading trace: {str(e)}")
                return 1
        else:
            # Use facade's file dialog
            success = self.facade.open_trace_file()
            
            if success:
                self._print_success("Trace file opened successfully")
                return 0
            else:
                self._print_error("Failed to open trace file")
                return 1
    
    def cmd_capture_packets(self, args):
        """Start packet capture."""
        interface = getattr(args, 'interface', None)
        count = getattr(args, 'count', 0)
        timeout = getattr(args, 'timeout', None)
        
        try:
            # Start capture
            success = self.facade.start_capture(interface, count, timeout)
            
            if success:
                self._print_success("Packet capture started")
                
                # Wait for capture to complete
                self._print_info("Capturing packets... Press Ctrl+C to stop early")
                
                try:
                    while self.facade.is_capturing():
                        time.sleep(0.5)
                except KeyboardInterrupt:
                    self._print_info("\nStopping capture...")
                    self.facade.stop_capture()
                
                self._print_success("Packet capture completed")
                return 0
            else:
                self._print_error("Failed to start packet capture")
                return 1
                
        except Exception as e:
            self._print_error(f"Error during packet capture: {str(e)}")
            return 1
    
    def cmd_analyze_trace(self, args):
        """Analyze the loaded trace."""
        try:
            # Get packets from facade (this would need to be implemented)
            # For now, simulate with empty analysis
            analysis_results = {
                'total_packets': 0,
                'protocols': {},
                'size_stats': {
                    'min': 0,
                    'max': 0,
                    'avg': 0
                }
            }
            
            if hasattr(self.facade, 'get_last_trace'):
                packets = self.facade.get_last_trace()
                if packets:
                    analysis_results = self.facade.analyze_packets(packets)
            
            output = self._format_output(analysis_results, "Trace Analysis Results")
            print(output)
            
            return 0
            
        except Exception as e:
            self._print_error(f"Error analyzing trace: {str(e)}")
            return 1
    
    # Information and utility commands
    
    def cmd_status(self, args):
        """Show overall application status."""
        try:
            status_info = {
                'facade_initialized': self.facade.is_initialized() if hasattr(self.facade, 'is_initialized') else True,
                'protocol_count': len(self.facade.get_protocol_stack()),
                'tecmp_encapsulated': self.facade.is_tecmp_encapsulated(),
                'current_packet': self.facade.get_current_packet() is not None,
                'capturing': self.facade.is_capturing(),
                'recent_files': len(self.facade.get_recent_files())
            }
            
            # Get facade status if available
            if hasattr(self.facade, 'get_status'):
                facade_status = self.facade.get_status()
                status_info.update(facade_status)
            
            output = self._format_output(status_info, "TECMP Tool Status")
            print(output)
            
            return 0
            
        except Exception as e:
            self._print_error(f"Error getting status: {str(e)}")
            return 1
    
    def cmd_list_available_protocols(self, args):
        """List available protocols that can be added."""
        # Standard protocols available
        available_protocols = [
            "Ethernet", "IPv4", "IPv6", "TCP", "UDP", "ICMP", "ICMPv6",
            "ARP", "VLAN", "HTTP", "HTTPS", "DNS", "DHCP", "SOME/IP",
            "CAN", "CAN-FD", "LIN", "FlexRay", "UART", "Analog", "Digital"
        ]
        
        output = self._format_output(available_protocols, "Available Protocols")
        print(output)
        
        return 0
    
    def cmd_help(self, args):
        """Show help information."""
        help_text = """
TECMP Network Packet Builder - Command Line Interface

Available Commands:

Protocol Management:
  list-protocols              List current protocols in the stack
  add-protocol <name>         Add a protocol to the stack
  remove-protocol <index>     Remove protocol at index
  move-protocol <from> <to>   Move protocol from one position to another
  clear-protocols             Clear all protocols from the stack
  list-available              List available protocols

TECMP Encapsulation:
  tecmp-status               Show TECMP encapsulation status
  tecmp-add                  Add TECMP encapsulation
  tecmp-remove               Remove TECMP encapsulation

Packet Operations:
  generate-packet            Generate packet from current stack
  show-packet                Show current packet details
  save-packet <file>         Save current packet to file

File Operations:
  load-project <file>        Load project from file
  save-project <file>        Save current state to project file
  open-trace <file>          Open and analyze trace file

Trace Operations:
  capture-packets            Start packet capture
  analyze-trace              Analyze loaded trace

Utility:
  status                     Show application status
  help                       Show this help message

Use --help with any command for detailed options.
"""
        print(help_text)
        return 0


def create_cli_parser():
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="TECMP Network Packet Builder - Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Enable quiet mode (minimal output)')
    parser.add_argument('--format', choices=['text', 'json', 'csv'], default='text',
                       help='Output format')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Set logging level')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Protocol management commands
    subparsers.add_parser('list-protocols', help='List current protocols')
    
    add_protocol_parser = subparsers.add_parser('add-protocol', help='Add protocol')
    add_protocol_parser.add_argument('protocol', help='Protocol name')
    add_protocol_parser.add_argument('--config', help='Protocol configuration (JSON or key=value pairs)')
    
    remove_protocol_parser = subparsers.add_parser('remove-protocol', help='Remove protocol')
    remove_protocol_parser.add_argument('index', type=int, help='Protocol index')
    
    move_protocol_parser = subparsers.add_parser('move-protocol', help='Move protocol')
    move_protocol_parser.add_argument('from_index', type=int, help='Source index')
    move_protocol_parser.add_argument('to_index', type=int, help='Destination index')
    
    clear_protocols_parser = subparsers.add_parser('clear-protocols', help='Clear all protocols')
    clear_protocols_parser.add_argument('--force', action='store_true',
                                       help='Clear without confirmation')
    
    subparsers.add_parser('list-available', help='List available protocols')
    
    # TECMP commands
    subparsers.add_parser('tecmp-status', help='Show TECMP status')
    subparsers.add_parser('tecmp-add', help='Add TECMP encapsulation')
    
    tecmp_remove_parser = subparsers.add_parser('tecmp-remove', help='Remove TECMP encapsulation')
    tecmp_remove_parser.add_argument('--force', action='store_true',
                                    help='Remove without confirmation')
    
    # Packet commands
    subparsers.add_parser('generate-packet', help='Generate packet')
    
    show_packet_parser = subparsers.add_parser('show-packet', help='Show packet details')
    show_packet_parser.add_argument('--hex-only', action='store_true',
                                   help='Show only hex output')
    
    save_packet_parser = subparsers.add_parser('save-packet', help='Save packet')
    save_packet_parser.add_argument('output', help='Output file path')
    save_packet_parser.add_argument('--format', choices=['pcap', 'bin', 'json'],
                                   default='pcap', help='Output format')
    
    # File commands
    load_project_parser = subparsers.add_parser('load-project', help='Load project')
    load_project_parser.add_argument('input', help='Project file path')
    
    save_project_parser = subparsers.add_parser('save-project', help='Save project')
    save_project_parser.add_argument('output', help='Project file path')
    
    open_trace_parser = subparsers.add_parser('open-trace', help='Open trace file')
    open_trace_parser.add_argument('input', nargs='?', help='Trace file path')
    
    # Trace commands
    capture_parser = subparsers.add_parser('capture-packets', help='Capture packets')
    capture_parser.add_argument('--interface', help='Network interface')
    capture_parser.add_argument('--count', type=int, default=0,
                               help='Number of packets to capture (0=unlimited)')
    capture_parser.add_argument('--timeout', type=int,
                               help='Capture timeout in seconds')
    
    subparsers.add_parser('analyze-trace', help='Analyze trace')
    
    # Utility commands
    subparsers.add_parser('status', help='Show application status')
    subparsers.add_parser('help', help='Show help information')
    
    return parser


def run_cli(args=None):
    """
    Run the CLI application.
    
    Args:
        args: Optional command line arguments (for testing)
    """
    # Parse arguments
    parser = create_cli_parser()
    parsed_args = parser.parse_args(args)
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, parsed_args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and initialize facade
    facade = TECMPFacade()
    success = facade.initialize()
    
    if not success:
        print("Error: Failed to initialize TECMP facade", file=sys.stderr)
        return 1
    
    # Create CLI adapter
    cli = CLIAdapter(facade)
    cli.set_output_format(parsed_args.format)
    cli.set_verbosity(parsed_args.verbose, parsed_args.quiet)
    
    # Handle command
    command = parsed_args.command
    
    if not command:
        # No command specified, show help
        return cli.cmd_help(parsed_args)
    
    # Map commands to methods
    command_map = {
        'list-protocols': cli.cmd_list_protocols,
        'add-protocol': cli.cmd_add_protocol,
        'remove-protocol': cli.cmd_remove_protocol,
        'move-protocol': cli.cmd_move_protocol,
        'clear-protocols': cli.cmd_clear_protocols,
        'list-available': cli.cmd_list_available_protocols,
        'tecmp-status': cli.cmd_tecmp_status,
        'tecmp-add': cli.cmd_tecmp_add,
        'tecmp-remove': cli.cmd_tecmp_remove,
        'generate-packet': cli.cmd_generate_packet,
        'show-packet': cli.cmd_show_packet,
        'save-packet': cli.cmd_save_packet,
        'load-project': cli.cmd_load_project,
        'save-project': cli.cmd_save_project,
        'open-trace': cli.cmd_open_trace,
        'capture-packets': cli.cmd_capture_packets,
        'analyze-trace': cli.cmd_analyze_trace,
        'status': cli.cmd_status,
        'help': cli.cmd_help
    }
    
    # Execute command
    if command in command_map:
        try:
            return command_map[command](parsed_args)
        except KeyboardInterrupt:
            cli._print_info("\nOperation interrupted by user")
            return 130  # Standard exit code for Ctrl+C
        except Exception as e:
            cli._print_error(f"Unexpected error: {str(e)}")
            if parsed_args.verbose:
                import traceback
                traceback.print_exc()
            return 1
        finally:
            # Cleanup facade
            if hasattr(facade, 'shutdown'):
                facade.shutdown()
    else:
        cli._print_error(f"Unknown command: {command}")
        cli.cmd_help(parsed_args)
        return 1


if __name__ == "__main__":
    sys.exit(run_cli())