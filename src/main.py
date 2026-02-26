import os.path
import sys

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QMainWindow, QApplication, QWidget, QHBoxLayout, QFileDialog, QLabel, QGraphicsView

import saddl
from ui_core import prepare_stylesheet, load_icons
from ui_matrix import MatrixScene, NavigableGraphicsView
from ui_history import TimelineScene

# Import plugins here
from plugins_core import TOADSPlugin


class InteractionManager:
    def __init__(self, parent):
        self.parent = parent
        self.history = None
        self.matrix = None
        self.plugins = []
        self.file = None

    # Execute a SADDL statement
    def _execute_statement(self, statement):
        verb, obj, ind_obj, reasoning = saddl.statement_to_key_terms(statement)

        # Execute the command on the matrix
        if verb == "DEFINE":
            return self.matrix.define_element(obj, reasoning)
        elif verb == "DELETE":
            return self.matrix.delete_element(obj)
        elif verb == "COUPLE":
            return self.matrix.couple_elements(obj, ind_obj)
        elif verb == "UNCOUPLE":
            return self.matrix.uncouple_elements(obj, ind_obj)
        elif verb == "ACCEPT":
            return self.matrix.accept_element(obj, reasoning)
        elif verb == "CLEAR":
            return self.matrix.clear_element(obj, reasoning)
        else:
            return False

    # Execute the opposite of a statement. Useful for undoing things
    def _execute_statement_opposite(self, statement):
        verb, obj, ind_obj, reasoning = saddl.statement_to_key_terms(statement)

        if verb == "DEFINE":
            new_verb = "DELETE"
        elif verb == "DELETE":
            new_verb = "DEFINE"
        elif verb == "COUPLE":
            new_verb = "UNCOUPLE"
        elif verb == "UNCOUPLE":
            new_verb = "COUPLE"
        elif verb == "ACCEPT":
            new_verb = "CLEAR"
        elif verb == "CLEAR":
            new_verb = "ACCEPT"

        if ind_obj:
            reversed_statement = new_verb + " " + obj + " and " + ind_obj + " because " + reasoning
        else:
            reversed_statement = new_verb + " " + obj + " because " + reasoning

        return self._execute_statement(reversed_statement)

    # Allow this object to control a design matrix
    def connect_matrix(self, matrix):
        self.matrix = matrix

    # Allow this object to control a design history
    def connect_history(self, history):
        self.history = history

    # Connect to a TOADSPlugin (do this before loading anything in)
    def connect_plugin(self, plugin: TOADSPlugin):
        self.plugins.append(plugin)

    # Start logging changes to a new file
    def start_new_file(self, path):
        self.matrix.reset()
        self.history.reset()
        self.file = open(path, "a+", buffering=1)   #  Set to line buffering so changes are written instantly

    # Load a .saddl file
    def load_from_file(self, path):
        assert (self.matrix and self.history)  # Don't load a file without connections to a matrix and history
        if not os.path.exists(path):  # Make sure this file exists
            return False

        # If a file is currently open, save everything before resetting
        if self.file:
            self.close_and_reset()

        # Read the file and modify the matrix/history accordingly
        self.file = open(path, "r+", buffering=1)  # Set to line buffering so changes are written instantly
        contents = self.file.read()
        for statement in contents.split("\n"):
            if statement == "" or statement.startswith("#"):  # Ignore blank lines and comments
                continue

            if not self._execute_statement(statement):
                print("Error loading file! Could not execute:", statement)
                return False
            else:
                self.commit_change(statement, save=False)

        # If the file doesn't end in a newline, add one
        if not contents.endswith("\n"):
            self.file.write("\n")

        return True

    # Force-save a file for peace of mind
    def save_file(self):
        if self.file:
            self.file.flush()
            return True
        return False

    # Save an existing design to a file
    def save_as_file(self, path):
        if not self.file:
            self.file = open(path, "a+", buffering=1)  # Set to line buffering so changes are written instantly

            for action in self.history.action_items:    # Not sure why this doesn't have to be reversed
                self.file.write(action.statement + "\n")

        self.file.flush()
        return True

    # Clean up the current session
    def close_and_reset(self):
        if self.file:
            self.file.close()
        self.matrix.reset()
        self.history.reset()

    # Take a SADDL statement with reasoning and apply the change to the system. This is used by the external
    # plugins and the new element widgets since those all implement their own review process and can skip
    # the review_user_proposed_change function.
    def apply_change_with_reasoning(self, statement):
        if not self._execute_statement(statement):
            return False

        # Record the action
        self.commit_change(statement)
        return True

    # Record a change and push it to any connected plugins (skip the save operation if this action is loaded from a file)
    def commit_change(self, statement, save=True):
        self.history.record_change(statement)
        for plugin in self.plugins:
            plugin.update_design_state(statement)

        if save and self.file:
            self.file.write(statement + "\n")


# A simple window to house everything
class Window(QMainWindow):
    def __init__(self):
        # Set up the GUI
        super(Window, self).__init__()
        self.setWindowTitle("TOADS")
        self.setMinimumSize(640, 480)
        # self.setWindowFlag(Qt.WindowType.FramelessWindowHint)

        # Load icon PNGs into QIcons for use
        self.TOADSIcons = load_icons()

        # Start up a toolbar
        self.toolbar = self.addToolBar("Toolbar")
        self.toolbar.setMovable(False)

        # Set up a status bar with three slots
        self.current_file = QLabel("Work not being saved")
        status = self.statusBar()
        status.addPermanentWidget(self.current_file, 0)

        # The interaction manager keeps track of changes
        self.manager = InteractionManager(self)

        # The two scenes and views are contained by the central widget
        self.central = QWidget()
        self.layout = QHBoxLayout()      # Can be any kind of layout
        self.central.setLayout(self.layout)
        self.setCentralWidget(self.central)

        # Create the matrix scene and view
        self.matrix_scene = MatrixScene(self, self.manager)
        self.matrix_view = NavigableGraphicsView(self.matrix_scene)
        self.layout.addWidget(self.matrix_view)

        # Create the timeline scene and view
        self.timeline_scene = TimelineScene(self, self.manager)
        self.timeline_view = QGraphicsView(self.timeline_scene)
        self.timeline_view.setStyleSheet("background-color: rgba(192, 192, 192, 96); border: 0px")
        self.timeline_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.timeline_view.setParent(self.central)
        # TODO: Ensure this updates so dock widgets don't draw over the timeline

        # Set up plugins as needed
        # ...

        # Hide all plugin windows at the start
        for plugin_window in self.manager.plugins:
            plugin_window.setVisible(False)

        # Connect everything to the manager
        self.manager.connect_matrix(self.matrix_scene.matrix)
        self.manager.connect_history(self.timeline_scene.history)

        # Put the toolbar together
        self._build_file_toolbar()
        self.toolbar.addSeparator()
        self._build_view_toolbar()

        # Add plugin toolbars if applicable (there's always at least one hide/show action per plugin)
        for plugin in self.manager.plugins:
            self.toolbar.addSeparator()
            for action in plugin.get_toolbar_actions():
                self.toolbar.addAction(action)

        # Show the GUI
        status.showMessage("TOADS ready", 5000)
        self.show()

    # Create some file actions and add them to the toolbar
    def _build_file_toolbar(self):
        new_action = QAction("Start new design", self)
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.setIcon(self.TOADSIcons["NewFile"])
        new_action.triggered.connect(self.prompt_for_new_file)
        self.toolbar.addAction(new_action)

        open_action = QAction("Open existing design", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.setIcon(self.TOADSIcons["OpenFile"])
        open_action.triggered.connect(self.prompt_for_existing_file)
        self.toolbar.addAction(open_action)

        save_action = QAction("Save design", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.setIcon(self.TOADSIcons["SaveFile"])
        save_action.triggered.connect(self.save_file)
        self.toolbar.addAction(save_action)

    # Create some view actions and add them to the toolbar
    def _build_view_toolbar(self):
        zoom_home_action = QAction("View reset", self)
        zoom_home_action.setShortcut(QKeySequence("Ctrl+0"))
        zoom_home_action.setIcon(self.TOADSIcons["ViewHome"])
        zoom_home_action.triggered.connect(self.matrix_view.view_reset)
        self.toolbar.addAction(zoom_home_action)

        rotate_ccw_action = QAction("Rotate CCW", self)
        rotate_ccw_action.setShortcut(QKeySequence("Ctrl+Left"))
        rotate_ccw_action.setIcon(self.TOADSIcons["RotateCounterClockwise"])
        rotate_ccw_action.triggered.connect(self.matrix_view.rotate_ccw)
        self.toolbar.addAction(rotate_ccw_action)

        rotate_diamond_action = QAction("Rotate 45°", self)
        rotate_diamond_action.setShortcut(QKeySequence("Ctrl+D"))
        rotate_diamond_action.setIcon(self.TOADSIcons["DiamondView"])
        rotate_diamond_action.setCheckable(True)
        rotate_diamond_action.triggered.connect(self.matrix_view.rotate_diamond)
        self.toolbar.addAction(rotate_diamond_action)

        rotate_cw_action = QAction("Rotate CW", self)
        rotate_cw_action.setShortcut(QKeySequence("Ctrl+Right"))
        rotate_cw_action.setIcon(self.TOADSIcons["RotateClockwise"])
        rotate_cw_action.triggered.connect(self.matrix_view.rotate_cw)
        self.toolbar.addAction(rotate_cw_action)

        zoom_in_action = QAction("Zoom in", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl+Equals"))
        zoom_in_action.setIcon(self.TOADSIcons["ZoomIn"])
        zoom_in_action.triggered.connect(self.matrix_view.zoom_in)
        self.toolbar.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom out", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+Minus"))
        zoom_out_action.setIcon(self.TOADSIcons["ZoomOut"])
        zoom_out_action.triggered.connect(self.matrix_view.zoom_out)
        self.toolbar.addAction(zoom_out_action)

    # Take an absolute path to a .saddl file, clean it up, and set the title bar accordingly
    def _display_filename_in_title(self, path_to_file):
        TOADS_root = os.path.split(os.getcwd())[0]
        relpath = os.path.relpath(path_to_file, TOADS_root)
        self.setWindowTitle("TOADS (" + relpath + ")")

    # Prompt the user for a new file path and start saving work there
    def prompt_for_new_file(self):
        self.manager.close_and_reset()
        path = QFileDialog.getSaveFileName(self, "Create new design", "./examples", "SADDL Files (*.saddl)", options=QFileDialog.Option.DontUseNativeDialog)[0]

        if path:
            self.manager.start_new_file(path)
            self._display_filename_in_title(path)
            self.statusBar().showMessage("File opened successfully", 5000)
            self.current_file.setText("Autosave enabled")

    # Prompt the user for a path to an existing file and start working on that
    def prompt_for_existing_file(self):
        path = QFileDialog.getOpenFileName(self, "Open design", "./examples", "SADDL Files (*.saddl)", options=QFileDialog.Option.DontUseNativeDialog)[0]

        if path:
            self.manager.load_from_file(path)
            # self.matrix_scene.views()[0].fitInView(self.matrix_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._display_filename_in_title(path)
            self.statusBar().showMessage("File loaded successfully", 5000)
            self.current_file.setText("Autosave enabled")

    # Force-save a file or save existing work as a file
    def save_file(self):
        if not self.manager.file:
            path = QFileDialog.getSaveFileName(self, "Save design as...", "./examples", "SADDL Files (*.saddl)", options=QFileDialog.Option.DontUseNativeDialog)[0]
            if path:
                self.manager.save_as_file(path)
                self._display_filename_in_title(path)
                self.statusBar().showMessage("File saved successfully", 5000)
                self.current_file.setText("Autosave enabled")

        elif self.manager.save_file():
            self.statusBar().showMessage("File saved successfully", 5000)

    # When the window closes, make sure to save the file
    def closeEvent(self, event):
        self.manager.close_and_reset()
        super().closeEvent(event)

    # When the window is resized, make sure the timeline view stays in the right spot
    def resizeEvent(self, event):
        margins = self.layout.contentsMargins()
        width = int(self.timeline_scene.sceneRect().width())
        x = int(self.central.geometry().width() - width - margins.right())
        y = margins.top()
        height = self.central.geometry().height() - (margins.top() + margins.bottom())

        self.timeline_view.setGeometry(QRect(x, y, width, height))
        super().resizeEvent(event)


if __name__ == "__main__":
    os.environ["QT_SCALE_FACTOR"] = '1.25'  # Makes the icons less blurry
    app = QApplication(sys.argv)

    # Preprocessing the stylesheet allows the use of variable values
    stylesheet = prepare_stylesheet("./resources/stylesheet.qss")
    app.setStyleSheet(stylesheet)

    GUI = Window()
    sys.exit(app.exec())
