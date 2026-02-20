from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget

import ui_core


# A generic class to standardize TOADS plugins
class TOADSPlugin(QDockWidget):
    def __init__(self, parent_window, manager):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.manager = manager
        self.statements = []    # The design story in order from first statement to last (managed by manager)

        # Configure the docking aspects
        # Because of an issue with Wayland, we can't have floating QDockWidgets for now (https://github.com/Slicer/Slicer/issues/8980)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)

    # Call the manager to change the design
    def _change_design(self, statement):
        """ Call the manager to change the design. DO NOT update statements from here, let the manager
        do that in update_design_state. Updating before calling this method will result in duplication """
        self.manager.apply_change_with_reasoning(statement)

    # Called by the manager to update this plugin when a new statement is added to the design
    def update_design_state(self, statement):
        self.statements.append(statement)
        self._update(statement)

    # Override this: Update the widget with any design changes
    def _update(self, new_statement):
        return False

    # Override this: If this plugin adds anything to the toolbar, put that together here
    def get_toolbar_actions(self):
        return []
