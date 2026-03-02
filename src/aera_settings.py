from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QAction, QDoubleValidator
from PyQt6.QtWidgets import QDialog, QGroupBox, QGridLayout, QFormLayout, QVBoxLayout, QLineEdit, QStyle, QButtonGroup, \
    QFileDialog, QSpinBox, QHBoxLayout, QPushButton


# Display a small settings window for the AERA_Interface object
class AERA_Configuration(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AERA Configuration")
        self.setModal(True)

        # These settings are stored between sessions. Default values are loaded from here
        self.settings = QSettings("Sierra-ACED", "TOADS")

        # Different AERA instances have different settings, group them accordingly
        self.localGroup = QGroupBox("Use a local AERA instance")
        self.localGroup.setCheckable(True)
        self.remoteGroup = QGroupBox("Connect to a remote AERA instance")
        self.remoteGroup.setCheckable(True)

        # Make these options mutually-exclusive
        self.localGroup.clicked.connect(self._selectLocalInstance)
        self.remoteGroup.clicked.connect(self._selectRemoteInstance)

        # Put together the settings for a local AERA instance
        localLayout = QFormLayout()
        self.localGroup.setLayout(localLayout)

        # Get the path to an AERA instance (add an action to bring up a file selection dialog)
        self._AERApathLineEdit = QLineEdit()
        AERApathBrowseAction = QAction("Browse", self)
        AERApathBrowseAction.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        AERApathBrowseAction.triggered.connect(self.prompt_for_AERA_path)
        self._AERApathLineEdit.addAction(AERApathBrowseAction, QLineEdit.ActionPosition.TrailingPosition)
        localLayout.addRow("Path to AERA executable:", self._AERApathLineEdit)

        # Get the path to a settings.xml file (add an action to bring up a file selection dialog)
        self._settingsPathLineEdit = QLineEdit()
        settingsPathBrowseAction = QAction("Browse", self)
        settingsPathBrowseAction.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        settingsPathBrowseAction.triggered.connect(self.prompt_for_settings_path)
        self._settingsPathLineEdit.addAction(settingsPathBrowseAction, QLineEdit.ActionPosition.TrailingPosition)
        localLayout.addRow("Path to settings.xml:", self._settingsPathLineEdit)

        # Put together the settings for a remote AERA instance
        remoteLayout = QFormLayout()
        self.remoteGroup.setLayout(remoteLayout)

        # Get an IP address to connect to
        self._AERAIPaddressLineEdit = QLineEdit()
        self._AERAIPaddressLineEdit.setInputMask("900.900.900.900")     # Force IPv4 format
        remoteLayout.addRow("AERA IP address:", self._AERAIPaddressLineEdit)

        # Get a port to connect to
        self._AERAportSpinBox = QSpinBox()
        self._AERAportSpinBox.setMinimum(1024)
        self._AERAportSpinBox.setMaximum(65535)
        remoteLayout.addRow("AERA port:", self._AERAportSpinBox)

        # Add the cancel and apply buttons
        buttonLayout = QHBoxLayout()

        rejectPushButton = QPushButton("Cancel")
        rejectPushButton.clicked.connect(self.reject)
        buttonLayout.addWidget(rejectPushButton)

        acceptPushButton = QPushButton("Apply")
        acceptPushButton.clicked.connect(self.save_settings_and_accept)
        acceptPushButton.setDefault(True)
        buttonLayout.addWidget(acceptPushButton)

        # Put the layouts together
        layout = QVBoxLayout()
        layout.addWidget(self.localGroup)
        layout.addWidget(self.remoteGroup)
        layout.addLayout(buttonLayout)
        self.setLayout(layout)

        # Load last state (or default values) from settings
        self.restore_settings()

    # Switch the UI to configure the local instance
    def _selectLocalInstance(self):
        self.localGroup.setChecked(True)
        self.remoteGroup.setChecked(False)

    # Switch the UI to configure the remote instance
    def _selectRemoteInstance(self):
        self.localGroup.setChecked(False)
        self.remoteGroup.setChecked(True)

    # Prompt the user for a path to an AERA executable (use the last known path as a starting point)
    def prompt_for_AERA_path(self):
        last_path = self._AERApathLineEdit.text()
        path = QFileDialog.getSaveFileName(self, "Select AERA instance", last_path, "Executable Files (*.exe)")[0]

        if path:
            self._AERApathLineEdit.setText(path)
            self.settings.setValue("Path to AERA executable", path)

    # Prompt the user for a path to a settings.xml file (use the last known path as a starting point)
    def prompt_for_settings_path(self):
        last_path = self._settingsPathLineEdit.text()
        path = QFileDialog.getSaveFileName(self, "Select settings.xml for AERA", last_path, "XML Files (*.xml)")[0]

        if path:
            self._settingsPathLineEdit.setText(path)
            self.settings.setValue("Path to settings.xml", path)

    # Restore settings from a settings file (if available)
    def restore_settings(self):
        # Restore the local/remote setting switch
        if self.settings.value("AERA Instance", "local", type=str) == "local":
            self._selectLocalInstance()
        else:
            self._selectRemoteInstance()

        # Restore field values
        self._AERApathLineEdit.setText(self.settings.value("Path to AERA executable", ".", type=str))
        self._settingsPathLineEdit.setText(self.settings.value("Path to settings.xml", ".", type=str))
        self._AERAIPaddressLineEdit.setText(self.settings.value("AERA IP address", "127.0.0.1", type=str))
        self._AERAportSpinBox.setValue(self.settings.value("AERA port", "8080", type=int))

    # Save the settings when "Apply" is pushed
    def save_settings_and_accept(self):
        # Save the local/remote setting switch
        if self.localGroup.isChecked():
            self.settings.setValue("AERA Instance", "local")
        else:
            self.settings.setValue("AERA Instance", "remote")

        # Save the field values
        self.settings.setValue("Path to AERA executable", self._AERApathLineEdit.text())
        self.settings.setValue("Path to settings.xml", self._settingsPathLineEdit.text())
        self.settings.setValue("AERA IP address", self._AERAIPaddressLineEdit.text())
        self.settings.setValue("AERA port", self._AERAportSpinBox.value())

        # Accept and close the dialog
        self.accept()
