import socket

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication

from tcp_data_message_pb2 import *

# Messages start with an 8-byte (uint64) length indication
MSG_LENGTH_LEN = 8


# A pared-down Python version of the TCPConnection from AERA_Protobuf
class TCPConnection:
    def __init__(self, IP="", port=8080, timeout=5):
        self.timeout = timeout

        # Start up the server and connection object
        self.server = socket.create_server((IP, port), reuse_port=True)
        self.server.settimeout(timeout)
        self.server.listen(1)
        self.conn = None

    # Wait for a connection
    def wait_for_client(self):
        print("Listening for connections...")
        try:
            self.conn, addr = self.server.accept()
            self.conn.settimeout(self.timeout)
            print("Connected to", addr)
            return True
        except TimeoutError:
            self.conn = None
            return False

    # Get TCPMessages from AERA (blocking receive optional)
    def receive(self, block=False):
        # Receive the length of the message
        msg_len_buf = bytearray()

        while len(msg_len_buf) < MSG_LENGTH_LEN:
            try:
                received = self.conn.recv(MSG_LENGTH_LEN - len(msg_len_buf))

            except TimeoutError:  # Keep waiting or return nothing
                if block:
                    continue
                else:
                    return None

            except OSError:  # Connection lost, need to reestablish
                self.conn.close()
                return False

            if len(received) > 0:  # Append received data
                msg_len_buf += received
            else:  # No bytes means connection was likely closed/lost
                self.conn.close()

        # Convert length to LSB-first
        msg_len = int.from_bytes(msg_len_buf, 'little')

        # Receive the rest of the message
        msg_buf = bytearray()
        while len(msg_buf) < msg_len:
            received = self.conn.recv(msg_len - len(msg_buf))

            if len(received) > 0:  # Append received data
                msg_buf += received
            else:  # No bytes means connection was likely closed/lost
                self.conn.close()

        # Convert to a TCPMessage and return
        message = TCPMessage()
        message.ParseFromString(msg_buf)
        return message

    # Send a TCP message to AERA
    def send(self, message):
        msg_buf = bytearray(message.SerializeToString())
        msg_len = len(msg_buf)

        # Add the length of the message to the front of the buffer
        msg_buf = msg_len.to_bytes(MSG_LENGTH_LEN, 'little') + msg_buf

        # Send the message and make sure all bytes were sent (close otherwise)
        if self.conn.send(msg_buf) < msg_len + MSG_LENGTH_LEN:
            self.close()

    # Close the connection
    def close(self):
        if self.conn:
            self.conn.shutdown(socket.SHUT_RDWR)    # Close the connection
            self.conn.close()                       # Release the socket


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

        # The TCPConnection object used to communicate with AERA
        self.conn = None

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
        ip = self.settings.value("AERA IP address", "127.0.0.1", type=str)
        port = self.settings.value("AERA Port number", 8080, type=int)
        # TODO: Validate these

        # Indicate that this might take a moment
        self._status_label.setText("Connecting to AERA...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()

        # Connect to AERA
        self.conn = TCPConnection(ip, port)
        if not self.conn.wait_for_client():
            self._status_label.setText("AERA connection failed")

        # Update the UI
        else:
            self._status_label.setText("AERA connected")
            self._connect_action.setEnabled(False)
            self._disconnect_action.setEnabled(True)
        QApplication.restoreOverrideCursor()

    # Disconnect the interface from AERA and drop the connection
    def disconnect_from_AERA(self):
        if self.conn:
            self.conn.close()
            self.conn = None

        # Update the UI
        self._status_label.setText("AERA not connected")
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