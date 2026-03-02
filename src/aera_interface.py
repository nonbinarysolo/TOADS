from PyQt6.QtCore import QSettings


class AERA_Interface:
    def __init__(self, manager):
        self.manager = manager                              # All interactions go through the manager
        self.settings = QSettings("Sierra-ACED", "TOADS")   # Configuration details stored here

        # UI elements the interface needs to be able to drive
        self._connect_action = None
        self._disconnect_action = None
        self._start_action = None
        self._stop_action = None
        self._status_label = None

    # Connect up toolbar actions from the main UI so the interface can handle activation and deactivation
    def connect_UI_and_configure(self, connect, disconnect, start, stop, status):
        self._connect_action = connect
        self._disconnect_action = disconnect
        self._start_action = start
        self._stop_action = stop
        self._status_label = status

        self.refresh()      # Read (new) settings and configure these UI elements accordingly

    # Re-read the settings file and reconfigure accordingly
    def refresh(self):
        self.settings = QSettings("Sierra-ACED", "TOADS")

        # Work out whether we're operating in local or remote mode (or if more configuration is needed)
        instance = self.settings.value("AERA Instance", "", type=str)
        if instance == "local":
            self.mode = "local"
            self._connect_action.setVisible(False)      # Turn off remote controls
            self._disconnect_action.setVisible(False)   #

            self._start_action.setVisible(True)         # Enable local controls
            self._start_action.setEnabled(True)         #
            self._stop_action.setVisible(True)          #
            self._stop_action.setEnabled(False)         #

        elif instance == "remote":
            self.mode = "remote"
            self._start_action.setVisible(False)        # Turn off local controls
            self._stop_action.setVisible(False)         #

            self._connect_action.setVisible(True)       # Enable remote controls
            self._connect_action.setEnabled(True)       #
            self._disconnect_action.setVisible(True)    #
            self._disconnect_action.setEnabled(False)   #

        else:
            self.mode = "unconfigured"
            self._connect_action.setVisible(False)      # Turn everything off until something is configured
            self._disconnect_action.setVisible(False)   #
            self._start_action.setVisible(False)        #
            self._stop_action.setVisible(False)         #

    # Connect to AERA but don't start it yet
    def connect_to_AERA(self):
        ip = self.settings.value("AERA IP address", "", type=str)
        port = self.settings.value("AERA Port number", 0, type=int)
        # TODO: Validate these
        # TODO: Connect to AERA
        self._connect_action.setEnabled(False)
        self._disconnect_action.setEnabled(True)

    # Disconnect the interface from AERA (stop AERA if necessary)
    def disconnect_from_AERA(self):
        # TODO: Disconnect from AERA
        self._connect_action.setEnabled(True)
        self._disconnect_action.setEnabled(False)

    # Start AERA on a certain seed program
    def start_AERA(self):
        # TODO: Start AERA
        self._start_action.setEnabled(False)
        self._stop_action.setEnabled(True)

    # Stop AERA but don't disconnect yet
    def stop_AERA(self):
        # TODO: Stop AERA
        self._start_action.setEnabled(True)
        self._stop_action.setEnabled(False)

"""
Request change flow
- User presses button on timeline
- Button calls request function in manager
- Manager forwards DM state and goal injection to interface
    - AERA does a thing (interface handles call and response)
    - Interface adjusts UI to reflect AERA's actions
- Interface calls manager.apply_change_with_reasoning if AERA has an answer
- Everything updated as normal, cycle repeats
"""