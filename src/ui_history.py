from PyQt6.QtCore import QRectF, Qt, QPoint, QRect
from PyQt6.QtGui import QBrush, QColor, QPen, QFontMetricsF
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene

from ui_core import action_font, reasoning_font, action_font_metrics, reasoning_font_metrics
import saddl


# A DesignAction is a visual representation of a SADDL statement that's been applied to a MultiMatrix
class DesignAction(QGraphicsItem):
    def __init__(self, history, statement):
        super().__init__()
        self.history = history
        self.statement = statement

        self.action, self.reasoning = saddl.statement_to_action_reasoning(statement)

        self.text_width = max(
            action_font_metrics.size(Qt.TextFlag.TextSingleLine, self.action).width(),
            reasoning_font_metrics.size(Qt.TextFlag.TextSingleLine, self.reasoning).width())

        self.left_padding = 8   # Distance between text and timeline

    def __str__(self):
        return self.statement

    def boundingRect(self):
        return QRectF(0, 0, self.text_width + self.left_padding, 30)

    def paint(self, painter, option, widget=None):
        # Draw in the action and reasoning
        text_rect = QRectF(self.left_padding, 0, self.boundingRect().width(), self.boundingRect().height())
        painter.setFont(action_font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.action)
        painter.setFont(reasoning_font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, self.reasoning)

        # Draw a line that separates the action from the reasoning
        line_y = int(self.boundingRect().center().y())
        painter.drawLine(0, line_y, int(self.boundingRect().right()), line_y)


# The DesignHistory renders a timeline and tracks DesignActions
class DesignHistory(QGraphicsItem):
    def __init__(self, parent_scene):
        super().__init__()
        self.parent_scene = parent_scene

        self.action_items = []

        self.node_radius = 4    # The radius of the little nodes that connect items to the timeline
        self.spacing = 10       # Pixels between action items when drawing the tree
        self.padding = 10       # Padding around the edges of the tree
        self.right_pad = 20     # A little extra to make room from the scrollbar

        self.min_y = 0          # The top of the tree
        self.max_y = 600        # The bottom of the tree (changes as tree is modified)
        self.max_width = 120    # Width of the widest DesignAction

        # Drawing utilities
        self.timeline_pen = QPen()
        self.timeline_pen.setWidth(2)

        self.node_brush = QBrush(Qt.BrushStyle.SolidPattern)
        self.node_brush.setColor(QColor(0, 0, 0))

    # Record a change and create a new DesignAction item
    def record_change(self, statement):
        action_item = DesignAction(self, statement)

        self.action_items.append(action_item)
        self.parent_scene.addItem(action_item)
        self._update_history_tree()

    # Reset the history (useful for loading in a new design)
    def reset(self):
        for item in self.action_items:
            self.parent_scene.removeItem(item)
        self.action_items = []
        self.max_y = 600
        self.max_width = 120

    # Account for changes to timeline by recalculating positions
    def _update_history_tree(self):
        y = 0
        for item in reversed(self.action_items):
            item.setPos(0, y)
            y += item.boundingRect().height() + self.spacing
            self.max_width = max(self.max_width, item.boundingRect().width())
        self.max_y = y

        # If the width increased or decreased, widen the scene's view and shift it accordingly
        view_geometry = self.scene().views()[0].geometry()
        width_difference = int(self.boundingRect().width() - view_geometry.width())
        if abs(width_difference) > 0:
            self.scene().views()[0].setGeometry(QRect(
                view_geometry.x() - width_difference,
                view_geometry.y(),
                view_geometry.width() + width_difference,
                view_geometry.height())
            )
            self.scene().views()[0].update()

        # Scroll to the very top
        if self.action_items:
            self.scene().views()[0].ensureVisible(self.action_items[-1].boundingRect())

    def boundingRect(self):
        return QRectF(
            -self.padding - self.node_radius,
            self.min_y - self.padding,
            self.max_width + self.padding + self.right_pad + self.node_radius,
            self.max_y - self.min_y)

    # Paint in the timeline that connects everything together
    def paint(self, painter, option, widget=None):
        painter.setBrush(self.node_brush)       # Fill in the nodes' ellipses
        x = 0 - self.timeline_pen.width() // 2  # Everything is drawn on the same x coordinate

        # Draw the nodes that connect items to the timeline
        for item in self.action_items:
            pos = QPoint(x, int(item.scenePos().y() + item.boundingRect().height() / 2))
            painter.drawEllipse(pos, self.node_radius, self.node_radius)

        # Draw the tail at the end of the timeline (but only if there are items on the timeline)
        if len(self.action_items) > 0:
            start_y = int(self.action_items[-1].scenePos().y() + self.action_items[-1].boundingRect().height()/2)
            end_y = int(self.action_items[0].scenePos().y() + self.action_items[0].boundingRect().height()+self.spacing)

            # Draw the big vertical line
            start = QPoint(x, start_y)
            end = QPoint(x, end_y)
            painter.setPen(self.timeline_pen)
            painter.drawLine(start, end)

            # Do a little crossbar at the bottom
            start = QPoint(x - self.padding // 2, end_y)
            end = QPoint(x + self.padding // 2, end_y)
            painter.drawLine(start, end)

        self.scene().update()


# A scene that helps render a DesignHistory object as a scrollable vertical timeline
class TimelineScene(QGraphicsScene):
    def __init__(self, parent, interaction_manager):
        super().__init__()
        self.parent = parent
        self.manager = interaction_manager

        self.history = DesignHistory(self)
        self.addItem(self.history)

        # Draw a coordinate origin for convenience
        # radius = 10
        # self.addEllipse(QRectF(-radius, -radius, radius*2, radius*2))
        # self.addLine(0, 0, radius, 0)
        # self.addLine(0, 0, 0, radius)

    # Delete the timeline and start a new one
    def reset_history(self):
        self.clear()
        self.setSceneRect(QRectF())

        self.history = DesignHistory(self)
        self.addItem(self.history)
        return self.history
