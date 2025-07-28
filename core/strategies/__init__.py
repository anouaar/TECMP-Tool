# -*- coding: utf-8 -*-
"""
Strategies Package - TECMP Tool Implementation  
Author: TECMP-Tool Development Team
Description: Packet transmission strategies with working imports only
"""

# Import only what actually exists in sender_strategy.py
try:
    from core.strategies.sender_strategy import (
        StrategyStatus, SenderType, TransmissionProtocol, Priority,
        NetworkInterface, TransmissionTarget, SenderConfiguration,
        StrategyConfiguration, StrategyMetrics, Sender, BaseSender,
        SenderStrategy, UDPSender, TCPSender, FileSender, MockSender,
        SenderFactory, create_strategy_config, create_sender_config,
        create_mock_senders
    )
except ImportError as e:
    print(f"Warning: Some strategy components unavailable: {e}")
    StrategyStatus = SenderStrategy = None

# Import concrete strategies with fallbacks
try:
    from core.strategies.single import SinglePacketStrategy
except ImportError:
    SinglePacketStrategy = None

__all__ = ['SenderStrategy', 'StrategyStatus', 'MockSender', 'SenderFactory', 
           'SinglePacketStrategy', 'create_mock_senders']
__all__ = [name for name in __all__ if globals().get(name) is not None]
