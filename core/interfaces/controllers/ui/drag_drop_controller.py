#!/usr/bin/env python
# coding: utf-8
"""
Controller for managing drag and drop operations in the TECMP Tool.

This controller manages all aspects of drag and drop operations:
- Protocol dragging from protocol lists to the encapsulation view
- Protocol reordering within the encapsulation view
- Visual feedback during drag operations
- Validation of drop operations
"""
import logging
from typing import Optional, Dict, Any, List, Tuple, Union

from PyQt5.QtCore import (
    QObject, pyqtSignal, QPoint, QSize, QMimeData, 
    Qt, QModelIndex, QEvent
)
from PyQt5.QtGui import (
    QDrag, QPixmap, QPainter, QColor, QFont, QFontMetrics, 
    QMouseEvent, QDragEnterEvent, QDragMoveEvent, QDropEvent
)
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTreeView, QTreeWidget, QListWidget,
    QMessageBox
)


class DragDropController(QObject):
    """
    Controller for managing drag and drop operations in the TECMP Tool.
    
    This controller handles:
    - Starting drag operations
    - Tracking drag state
    - Validating drop operations
    - Handling protocol moves and additions
    - Maintaining consistent state during drag operations
    
    It serves as a mediator between UI components and the protocol stack model.
    """
    
    # Signals
    protocol_dragged = pyqtSignal(str, QPoint)  # Protocol name, global position
    protocol_dropped = pyqtSignal(str, QPoint)  # Protocol name, global position
    protocol_move_requested = pyqtSignal(int, int)  # From index, to index
    invalid_drop = pyqtSignal(str)  # Error message
    
    def __init__(self, main_window=None, protocol_controller=None, tecmp_manager=None):
        """
        Initialize the drag and drop controller.
        
        Args:
            main_window: Main application window reference
            protocol_controller: Protocol stack controller reference
            tecmp_manager: TECMP encapsulation manager reference
        """
        super().__init__()
        self.logger = logging.getLogger("TECMP-Tool.DragDropController")
        
        # References to other components
        self.main_window = main_window
        self.protocol_controller = protocol_controller
        self.tecmp_manager = tecmp_manager
        
        # Drag state tracking
        self._drag_active = False
        self._drag_source = None
        self._drag_source_index = -1
        self._drag_source_item = None
        self._drag_start_pos = None
        self._drag_protocol_name = None
        
        # Protocol colors for visual feedback
        self.protocol_colors = {
            "Ethernet": "#4A90E2",
            "IPv4": "#5CB85C",
            "IPv6": "#50E3C2",
            "TCP": "#F0AD4E",
            "UDP": "#D9534F",
            "ICMP": "#5BC0DE",
            "ICMPv6": "#5BC0DE",
            "ARP": "#D4AC0D",
            "VLAN": "#8E44AD",
            "TECMP": "#BA68C8",
            "HTTP": "#FF5722",
            "DHCP": "#009688",
            "DNS": "#3F51B5",
            "SOME/IP": "#FF9800"
        }
        
        # Default color for protocols not in the dictionary
        self.default_protocol_color = "#BDBDBD"
        
        self.logger.info("DragDropController initialized")
    
    def install_event_filters(self, protocol_views, encapsulation_view):
        """
        Install event filters on relevant views to handle drag and drop.
        
        Args:
            protocol_views: List of protocol list views
            encapsulation_view: Encapsulation tree view
        """
        if not protocol_views:
            protocol_views = []
            
        # Install filter on protocol views
        for view in protocol_views:
            view.installEventFilter(self)
            self.logger.debug(f"Installed event filter on protocol view: {view.__class__.__name__}")
            
        # Install filter on encapsulation view
        if encapsulation_view:
            encapsulation_view.installEventFilter(self)
            self.logger.debug(f"Installed event filter on encapsulation view: {encapsulation_view.__class__.__name__}")
            
        # Store reference to encapsulation view
        self.encapsulation_view = encapsulation_view
    
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Filter events to handle drag and drop operations.
        
        Args:
            obj: Object that received the event
            event: The event
            
        Returns:
            True if event was handled, False otherwise
        """
        # Handle mouse press - potential start of drag
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            return self._handle_mouse_press(obj, event)
            
        # Handle mouse move - potential drag
        elif event.type() == QEvent.MouseMove and hasattr(event, 'buttons') and event.buttons() & Qt.LeftButton:
            return self._handle_mouse_move(obj, event)
            
        # Handle mouse release - end of drag
        elif event.type() == QEvent.MouseButtonRelease:
            self._reset_drag_state()
            return False  # Let the widget handle the release
            
        # Handle drag enter - validate drop
        elif event.type() == QEvent.DragEnter:
            return self._handle_drag_enter(obj, event)
            
        # Handle drag move - update visual feedback
        elif event.type() == QEvent.DragMove:
            return self._handle_drag_move(obj, event)
            
        # Handle drop - process the operation
        elif event.type() == QEvent.Drop:
            return self._handle_drop(obj, event)
            
        # Pass unhandled events to parent class
        return super().eventFilter(obj, event)
    
    def _handle_mouse_press(self, obj: QObject, event: QMouseEvent) -> bool:
        """
        Handle mouse press event - potential start of drag.
        
        Args:
            obj: Object that received the event
            event: Mouse press event
            
        Returns:
            True if event was handled, False otherwise
        """
        # Only handle if TECMP encapsulation is not active
        if self.tecmp_manager and self.tecmp_manager.is_encapsulation_active():
            return False
        
        # Store drag start information
        self._drag_start_pos = event.pos()
        self._drag_source = obj
        
        # Extract the item under the cursor
        if isinstance(obj, QTreeWidget):
            item = obj.itemAt(event.pos())
            if item:
                self._drag_source_item = item
                self._drag_protocol_name = item.text(0)
                
                # Get index if it's the encapsulation view
                if obj == self.encapsulation_view:
                    self._drag_source_index = obj.indexOfTopLevelItem(item)
                    
                    # Don't allow dragging Frame or non-top level items
                    if self._drag_protocol_name == "Frame" or item.parent():
                        self._reset_drag_state()
                        return False
        
        elif isinstance(obj, QListWidget):
            item = obj.itemAt(event.pos())
            if item:
                self._drag_source_item = item
                self._drag_protocol_name = item.text()
        
        # Continue normal event processing
        return False
    
    def _handle_mouse_move(self, obj: QObject, event: QMouseEvent) -> bool:
        """
        Handle mouse move event - potential drag.
        
        Args:
            obj: Object that received the event
            event: Mouse move event
            
        Returns:
            True if event was handled, False otherwise
        """
        # Check if we have a valid drag start
        if not self._drag_start_pos or not self._drag_protocol_name:
            return False
        
        # Check if the move is far enough to start a drag
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return False
        
        # Start the drag if we haven't already
        if not self._drag_active and self._drag_protocol_name:
            self._start_drag(obj, event)
            return True
        
        # Let the widget handle the move normally
        return False
    
    def _handle_drag_enter(self, obj: QObject, event: QDragEnterEvent) -> bool:
        """
        Handle drag enter event - validate drop target.
        
        Args:
            obj: Object that received the event
            event: Drag enter event
            
        Returns:
            True if event was handled, False otherwise
        """
        # Only handle drops in the encapsulation view
        if obj != self.encapsulation_view:
            event.ignore()
            return False
        
        # Check if TECMP encapsulation is active
        if self.tecmp_manager and self.tecmp_manager.is_encapsulation_active():
            event.ignore()
            self.invalid_drop.emit("Cannot modify protocol stack when TECMP encapsulation is active")
            return True
        
        # Accept if the mime data has text (protocol name)
        if event.mimeData().hasText():
            event.acceptProposedAction()
            return True
        
        # Ignore otherwise
        event.ignore()
        return False
    
    def _handle_drag_move(self, obj: QObject, event: QDragMoveEvent) -> bool:
        """
        Handle drag move event - update visual feedback.
        
        Args:
            obj: Object that received the event
            event: Drag move event
            
        Returns:
            True if event was handled, False otherwise
        """
        # Only handle in the encapsulation view
        if obj != self.encapsulation_view:
            event.ignore()
            return False
        
        # Accept if the mime data has text
        if event.mimeData().hasText():
            event.acceptProposedAction()
            return True
        
        # Ignore otherwise
        event.ignore()
        return False
    
    def _handle_drop(self, obj: QObject, event: QDropEvent) -> bool:
        """
        Handle drop event - process the drag operation.
        
        Args:
            obj: Object that received the event
            event: Drop event
            
        Returns:
            True if event was handled, False otherwise
        """
        # Only handle drops in the encapsulation view
        if obj != self.encapsulation_view:
            event.ignore()
            return False
        
        # Check if TECMP encapsulation is active
        if self.tecmp_manager and self.tecmp_manager.is_encapsulation_active():
            event.ignore()
            self.invalid_drop.emit("Cannot modify protocol stack when TECMP encapsulation is active")
            return True
        
        # Process the drop
        if event.mimeData().hasText():
            protocol_name = event.mimeData().text()
            
            # Handle protocol move within the encapsulation view
            if self._drag_source == obj and self._drag_source_index >= 0:
                # Get drop position
                item = obj.itemAt(event.pos())
                if item:
                    drop_index = obj.indexOfTopLevelItem(item)
                    if drop_index >= 0 and drop_index != self._drag_source_index:
                        # Emit signal for protocol move
                        self.protocol_move_requested.emit(self._drag_source_index, drop_index)
                        event.acceptProposedAction()
                        self._reset_drag_state()
                        return True
            
            # Handle protocol drop from protocol list
            else:
                # Emit signal for protocol dropped
                self.protocol_dropped.emit(protocol_name, event.pos())
                event.acceptProposedAction()
                self._reset_drag_state()
                return True
                
        # Ignore if not handled
        event.ignore()
        self._reset_drag_state()
        return False
    
    def _start_drag(self, obj: QObject, event: QMouseEvent) -> None:
        """
        Start a drag operation.
        
        Args:
            obj: Source object
            event: Mouse event that triggered the drag
        """
        # Mark drag as active
        self._drag_active = True
        
        # Create mime data
        mime_data = QMimeData()
        mime_data.setText(self._drag_protocol_name)
        
        # Create drag pixmap
        pixmap = self._create_drag_pixmap(self._drag_protocol_name)
        
        # Create and execute drag
        drag = QDrag(obj)
        drag.setMimeData(mime_data)
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        
        # Emit signal before starting drag
        self.protocol_dragged.emit(self._drag_protocol_name, QCursor.pos())
        
        # Execute drag
        result = drag.exec_(Qt.CopyAction)
        
        # Reset drag state after completion
        self._reset_drag_state()
    
    def _create_drag_pixmap(self, protocol_name: str) -> QPixmap:
        """
        Create a pixmap for drag visualization.
        
        Args:
            protocol_name: Name of the protocol being dragged
            
        Returns:
            QPixmap for drag visual feedback
        """
        # Calculate appropriate pixmap width based on text
        font = QFont()
        metrics = QFontMetrics(font)
        text_width = metrics.width(protocol_name) + 40  # Add padding
        pixmap_width = max(100, min(400, text_width))  # Between 100 and 400 pixels
        
        # Create dynamically sized drag pixmap
        pixmap = QPixmap(pixmap_width, 30)
        pixmap.fill(Qt.transparent)
        
        # Get background color based on protocol
        base_name = protocol_name.split(" ")[0]  # Get base name without suffixes
        bg_color = QColor(self.protocol_colors.get(base_name, self.default_protocol_color))
        
        # Draw protocol name on pixmap
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.black)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(0, 0, pixmap_width, 30, 5, 5)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, protocol_name)
        painter.end()
        
        return pixmap
    
    def _reset_drag_state(self) -> None:
        """Reset all drag state variables."""
        self._drag_active = False
        self._drag_source = None
        self._drag_source_index = -1
        self._drag_source_item = None
        self._drag_start_pos = None
        self._drag_protocol_name = None
    
    def is_drag_active(self) -> bool:
        """
        Check if a drag operation is currently active.
        
        Returns:
            bool: True if drag is active, False otherwise
        """
        return self._drag_active
    
    def get_protocol_color(self, protocol_name: str) -> QColor:
        """
        Get color associated with a protocol.
        
        Args:
            protocol_name: Name of the protocol
            
        Returns:
            QColor for the protocol
        """
        base_name = protocol_name.split(" ")[0]  # Get base name without suffixes
        return QColor(self.protocol_colors.get(base_name, self.default_protocol_color))
    
    def add_protocol_color(self, protocol_name: str, color: Union[str, QColor]) -> None:
        """
        Add or update a protocol color.
        
        Args:
            protocol_name: Name of the protocol
            color: Color string or QColor object
        """
        if isinstance(color, QColor):
            color = color.name()
        
        self.protocol_colors[protocol_name] = color
    
    def validate_protocol_move(self, from_index: int, to_index: int) -> bool:
        """
        Validate a protocol move operation.
        
        Args:
            from_index: Source index
            to_index: Destination index
            
        Returns:
            bool: True if move is valid, False otherwise
        """
        # Prevent moves if TECMP encapsulation is active
        if self.tecmp_manager and self.tecmp_manager.is_encapsulation_active():
            self.invalid_drop.emit("Cannot move protocols when TECMP encapsulation is active")
            return False
        
        # If protocol controller exists, delegate validation
        if self.protocol_controller:
            if hasattr(self.protocol_controller, 'validate_move'):
                return self.protocol_controller.validate_move(from_index, to_index)
        
        # Default to allowing the move
        return True





































































































































































































































































































































































































































































































