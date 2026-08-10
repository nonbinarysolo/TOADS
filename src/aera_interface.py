import os
import socket
import time
import tomllib
import struct

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication, QProgressDialog, QMessageBox

import saddl

# Include the compiled proto file. This might trip up some IDEs, especially with the TCPMessage class but everything
# should still compile fine so long as this is imported and compiled correctly.
from tcp_data_message_pb2 import *


# Messages start with an 8-byte (uint64) length indication
MSG_LENGTH_LEN = 8


# A pared-down Python version of the TCPConnection from AERA_Protobuf
class TCPConnection:
    def __init__(self, IP="", port=8080, timeout=5):
        self.timeout = timeout

        # Start up the server and connection object
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((IP, port))
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


# Convert the string name for a data type (from the TOML) to a Python datatype
commonName_to_pythonDataType = {
    "double": float,
    # "float" : float,
    # "int32" : int,
    "int64": int,
    # "uint32" : int,
    # "uint64" : int,
    "bool": bool,
    "string": str,
    "bytes": bytes,
    "communication_id": int,
}

# Create a reverse lookup for convenience
pythonDataType_to_commonName = {pythontype: name for name, pythontype in commonName_to_pythonDataType.items()}

# Convert the string name for a data type (from the TOML) to the actual VariableDescription.DataType
commonName_to_protoDataType = {
    "double": VariableDescription.DataType.DOUBLE,
    # "float" : VariableDescription.DataType.FLOAT,
    # "int32" : VariableDescription.DataType.INT32,
    "int64": VariableDescription.DataType.INT64,
    # "uint32" : VariableDescription.DataType.UINT32,
    # "uint64" : VariableDescription.DataType.UINT64,
    "bool": VariableDescription.DataType.BOOL,
    "string": VariableDescription.DataType.STRING,
    "bytes": VariableDescription.DataType.BYTES,
    "communication_id": VariableDescription.DataType.COMMUNICATION_ID,
}

# Create a reverse lookup for convenience
protoDataType_to_commonName = {proto: name for name, proto in commonName_to_protoDataType.items()}

# Convert the string name for a data type (from the TOML) to the format character used with the struct library
commonName_to_structFormatChar = {
    "double": "d",
    # "float" : "f",
    # "int32" : "l",
    "int64": "q",
    # "uint32" : "L",
    # "uint64" : "Q",
    "bool": "?",
    "string": "s",
    "bytes": "p",
    "communication_id": "q",
}

# Create a reverse lookup for convenience
structFormatChar_to_commonName = {formatchar: name for name, formatchar in commonName_to_structFormatChar.items()}


"""
A CommandInstance bridges the specification of a command that AERA and the TOML file uses with
the execution flow needed by the ROS node. It is a specific instance of a command as it pertains
to its parent entity; when one of these is executed, it's the system's way of saying the parent
entity executed the command. The CommandInstance holds a bunch of information about the command
and operates a few functions required to execute the command (by publishing something to a ROS
topic) and see if the command is done executing (by monitoring another ROS topic to see if its
value has reached some goal state with optional error bars). Takes the following parameters:

    ID                   -> The ID of this particular CommandInstance
    entityID             -> The ID of this command's parent entity (the one that 'performs' the command)
    name                 -> The name of this command as specified in the TOML
    dataType             -> The common name of the data type of this command's arguments
    dimensionality       -> How many arguments this command takes
    opcode_string_handle -> Like an internal datatype for AERA (Vec3, set, and so on). Only really need to
                            declare it if you need to report both 0 and null values since a 0 value will
                            simply not be injected.
    instanceMonitor      -> The PropertyInstance this command affects. It'll watch this to see if the command is done

Remember to run configureError() after initialization if you need to set up error bars!
"""
class CommandInstance:
    def __init__(self, ID, entityID, name, dataType, dimensionality, opcode_string_handle):
        self.ID = ID
        self.entityID = entityID
        self.name = name
        self.protoDataType = commonName_to_protoDataType[dataType.lower()]
        self.dimensionality = dimensionality
        self.opcode_string_handle = opcode_string_handle

    # Produce a CommandDescription of this command
    def generateCommandDescription(self):
        v = VariableDescription()  # Describe most of this CommandInstance object
        v.entityID = self.entityID
        v.ID = self.ID
        v.dataType = self.protoDataType
        v.dimensions.extend(self.dimensionality)
        v.opcode_string_handle = self.opcode_string_handle

        c = CommandDescription()  # Add the name
        c.description.CopyFrom(v)
        c.name = self.name
        return c


"""
A PropertyInstance is a container for a property of an Entity. Properties that objects can have
are declared globally in the TOML file for the world. A PropertyInstance is how you attach one of
those properties to an object. For example, one could declare a velocity property but only have
some moving objects so only those objects would have an associated PropertyInstance. A property can
describe position, velocity, mass, light level, etc. Takes the following parameters:

    ID                   -> An integer representing the ID of the global property this corresponds to (assigned by World)
    entityID             -> An integer matching the ID of the entity this PropertyInstance is attached to
    name                 -> A descriptive name (should correspond to the ROS topic name it'll track)
    dataType             -> A string name for a VariableDescription.DataType describing the PropertyInstance's data type
    dimensionality       -> The number of dimensions this value has
    opcode_string_handle -> Like an internal datatype for AERA (Vec3, set, and so on). Only really need to
                            declare it if you need to report both 0 and null values since a 0 value will
                            simply not be injected.
"""
class PropertyInstance:
    def __init__(self, ID, entityID, name, dataType, dimensionality, opcode_string_handle):
        self.ID = ID
        self.entityID = entityID
        self.name = name
        self.pythonDataType = commonName_to_pythonDataType[dataType.lower()]
        self.protoDataType = commonName_to_protoDataType[dataType.lower()]
        self.dimensionality = dimensionality
        self.opcode_string_handle = opcode_string_handle

        self.value = None

    # Produce a VariableDescription of this property
    def generateVariableDescription(self):
        v = VariableDescription()
        v.entityID = self.entityID
        v.ID = self.ID
        v.dataType = self.protoDataType
        v.dimensions.extend(self.dimensionality)
        v.opcode_string_handle = self.opcode_string_handle
        return v

    # Setter for the value object (set by the interface during transmissions)
    def set_value(self, value):
        self.value = value

    # Getter for value object
    def get_value(self):
        return self.value


"""
A container for an entity (a thing in the world). Entities can have PropertyInstances and
some can be interacted with using CommandInstances. Entities must be initialized within a
World. They don't really do much besides being containers to organize their properties and
the commands they can perform. Takes the following parameters:

    ID                   -> A unique integer representing this entity
    name                 -> A descriptive name as specified in the TOML file
    properties           -> A dictionary (ID:PropertyInstance) of PropertyInstances that belong to this entity
    commands             -> A dictionary (ID:CommandInstance) of CommandInstances that this entity can run
"""
class Entity:
    def __init__(self, ID, name, properties, commands):
        self.ID = ID
        self.name = name
        self.properties = properties
        self.commands = commands


"""
A World object keeps track of all Entities, their PropertyInstances, and their CommandInstances. It is
a useful container for tracking world state (fed in from the interface) and preparing messages to send off to
AERA using the tcp_data_message.proto format. It's mostly used as a container and to send these periodic
data messages. Takes in a path to a TOML file as a parameter.
"""
class World:
    def __init__(self, path_to_toml):
        self.entities = {}  # entityID:entity
        self.topics_to_pInstances = {}  # A map of things to subscribe to and properties to update
        self.cInstances_to_topics = {}  # A map of command instances and the topics they affect

        if not os.path.exists(path_to_toml):
            raise(Exception("TOML file not found!"))

        self._parseTOML(path_to_toml)

    # A TOML file specifies what objects this world should track
    def _parseTOML(self, path_to_toml):
        f = open(path_to_toml, 'rb')
        toml = tomllib.load(f)
        f.close()

        self.name = toml['title']

        # Start creating IDs
        ID = 0

        # Create a name:property dictionary for easier lookups and assign each a unique ID
        TOML_properties = {}
        for prop in toml['properties']:
            TOML_properties[prop['name']] = prop

            TOML_properties[prop['name']]['ID'] = ID
            ID += 1

        # Do the same for commands
        TOML_commands = {}
        for cmd in toml['commands']:
            TOML_commands[cmd['name']] = cmd

            TOML_commands[cmd['name']]['ID'] = ID
            ID += 1

        # Go through and create Entity, PropertyInstance, and CommandInstance objects for each entry in the file (and give them IDs)
        for new_entity in toml['entities']:
            eName = new_entity['name']
            eID = ID
            ID += 1

            # Process each entity's PropertyInstances. Link these back to a global property from the TOML
            properties = {}
            for pName in new_entity['properties']:
                if pName in TOML_properties:
                    pID = TOML_properties[pName]['ID']
                    p = PropertyInstance(
                        pID,
                        eID,
                        TOML_properties[pName]['name'],
                        TOML_properties[pName]['type'],
                        TOML_properties[pName]['dimensionality'],
                        TOML_properties[pName]['opcode_handle']
                    )

                    properties[pID] = p
                    ID += 1

                    # Auto-generate topic names that can be used to update this property instance from the ROS network
                    topicname = eName.lower() + "_" + p.name.lower()
                    self.topics_to_pInstances[topicname] = p

                else:
                    raise (Exception(
                        "Entity '" + eName + "' is supposed to have property '" + pName + "' but this property has not been defined!"))

                    # Process each entity's CommandInstances. Link these back to a global command from the TOML
            commands = {}
            if 'commands' in new_entity.keys():
                for cName in new_entity['commands']:
                    if cName in TOML_commands:
                        cID = TOML_commands[cName]['ID']

                        # Some commands are closed-loop and should monitor a specific PropertyInstance to see if their goal has been achieved
                        pInstance = None
                        if 'monitor' in TOML_commands[cName]:
                            for _, pI in properties.items():
                                if pI.name == TOML_commands[cName]['monitor']:
                                    pInstance = pI

                            # Make sure a closed-loop command actually has a property to monitor
                            if not pInstance:
                                pName = TOML_commands[cName]['monitor']
                                raise (Exception(
                                    "Command '" + cName + "' is supposed to monitor '" + pName + "' but entity '" + eName + "' does not have this property!"))

                        # Create the command instance
                        c = CommandInstance(
                            cID,
                            eID,
                            TOML_commands[cName]['name'],
                            TOML_commands[cName]['type'],
                            TOML_commands[cName]['dimensionality'],
                            TOML_commands[cName]['opcode_handle'] if 'opcode_handle' in TOML_commands[cName] else '', # Some commands don't have an opcode_handle
                        )

                        commands[cID] = c
                        ID += 1

                        # Auto-generate topic names that can be used to publish this command to the ROS network
                        topicname = eName.lower() + "_" + c.name.lower()
                        self.cInstances_to_topics[c] = topicname

                    else:
                        raise (Exception(
                            "Entity '" + eName + "' is supposed to have command '" + cName + "' but this command has not been defined!"))

            # Put all of this together into an Entity and add it to the list
            e = Entity(eID, eName, properties, commands)
            self.entities[eID] = e

        # Just in case we add anything more
        self.nextID = ID

    # Organize all this information into a SetupMessage to send to AERA
    # 1. Parse TOML file into dictionaries of entities (with properties) and commands
    # 2. Create a list of object names (entities, properties, and commands) and give each a unique ID
    # 3. Go through each entity and create a MetaData object for each of its properties. This should
    #    include entity ID, property name, data type, dimensions, and opcode handle. Do this for their
    #    commands as well.
    # 4. In the process, make a map of entities to a list of their properties for this node's use
    # 5. Start converting this data for transmission. Create a mapping of object names:IDs, entity names:IDs,
    #    and command names:IDs. Also create a list of CommandDescriptions (names and variables)
    # 6. Package these up and transmit
    # 7. Return entity:property mapping to node. This will be used to remember object IDs in DataMessages
    def generateSetupMessage(self):
        setup_msg = SetupMessage()  # Set up a blank message

        # Fill out the entities, objects, and commands maps
        for eID, e in self.entities.items():
            setup_msg.entities[e.name] = eID  # Add this to the entities map

            # Add properties to the objects map
            for pID, p in e.properties.items():
                setup_msg.objects[p.name] = pID

            # Add commands to the objects map (and add them to the commands map)
            for cID, c in e.commands.items():
                setup_msg.commands[c.name] = cID

        # Fill out the CommandDescriptions field
        for _, e in self.entities.items():
            for _, c in e.commands.items():
                setup_msg.commandDescriptions.append(c.generateCommandDescription())

        return setup_msg

    # Get a snapshot of the current world state and send it to AERA
    def generateDataMessage(self):
        data_msg = DataMessage()
        data_msg.timeSpan = 0  # TODO: Maybe this should be nonzero?

        # Get each property of each entity and store it in a ProtoVariable for transmission
        for _, e in self.entities.items():
            for _, p in e.properties.items():
                pv = ProtoVariable()
                pv.metaData.CopyFrom(p.generateVariableDescription())
                if p.get_value():
                    dataType = protoDataType_to_commonName[p.protoDataType]     # Figure out how to pack up this Protobuf type
                    if dataType == 'string':
                        pv.data = bytes(p.get_value(), "utf-8")
                    else:
                        formatchar = commonName_to_structFormatChar[dataType]       #
                        pv.data = struct.pack("<" + formatchar, p.get_value())  #

                data_msg.variables.append(pv)

        return data_msg


class AERA_Interface:
    def __init__(self, manager, parent_window, toml_path="./src/eda.toml"):
        self.manager = manager                              # All interactions go through the manager
        self.parent_window = parent_window                  # Used when showing progress dialogs
        self.settings = QSettings("Sierra-ACED", "TOADS")   # Configuration details stored here
        self.world = World(toml_path)                       # Configure the 'world' the AERA will see
        self.AERA_time = 0                                  # The interface's guess at AERA's current time

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

        # Try to connect to AERA
        self.conn = TCPConnection(ip, port)
        if not self.conn.wait_for_client():
            self._status_label.setText("AERA connection failed")
            QApplication.restoreOverrideCursor()
            return

        # Send AERA a setup message and wait until it's ready to start
        self._send_setup_message()
        response = self.conn.receive(block=True)
        if response == None or response == False or response.messageType != TCPMessage.Type.START:
            self._status_label.setText("Setup failed, restart AERA")
            self.conn = None
            QApplication.restoreOverrideCursor()
            return

        # Startup successful, update the UI
        self._status_label.setText("AERA connected")
        self._connect_action.setEnabled(False)
        self._disconnect_action.setEnabled(True)
        QApplication.restoreOverrideCursor()

        # TODO: Catch AERA up on a design in progress

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

    # Get the world to generate a SETUP message and send it to AERA
    def _send_setup_message(self):
        setup_msg = self.world.generateSetupMessage()

        # Package it up into a TCPMessage for transmission
        tcp_msg = TCPMessage()
        tcp_msg.messageType = TCPMessage.Type.SETUP
        tcp_msg.setupMessage.CopyFrom(setup_msg)
        tcp_msg.timestamp = self.AERA_time

        self.conn.send(tcp_msg)
        self.AERA_time += 100

    # Get a snapshot of the values of every property in the world
    def _send_data_message(self):
        data_msg = self.world.generateDataMessage()

        # Package it up into a TCPMessage for transmission
        tcp_msg = TCPMessage()
        tcp_msg.messageType = TCPMessage.Type.DATA
        tcp_msg.dataMessage.CopyFrom(data_msg)
        tcp_msg.timestamp = self.AERA_time

        self.conn.send(tcp_msg)
        self.AERA_time += 100

    # Conduct an interaction with AERA and show a progress dialog if needed
    def _interact_with_AERA(self, message):
        if not self.conn:
            return False

        # Set up a progress dialog in case this takes a while
        progress = QProgressDialog(self.parent_window)
        #progress.setMinimumDuration(2000)       # This doesn't do much for the moment since everything's in one thread
        progress.setWindowTitle("AERA Interface")
        progress.setModal(True)
        progress.setMinimum(0)
        progress.setMaximum(2)
        progress.show()
        QApplication.processEvents()

        # Send message to AERA
        progress.setValue(0)
        progress.setLabelText("Sending message...")
        QApplication.processEvents()
        self.conn.send(message)

        # Await response
        progress.setValue(1)
        progress.setLabelText("Awaiting response...")
        QApplication.processEvents()
        response = self.conn.receive()

        # Close the dialog and pass the response alog
        progress.setValue(2)
        progress.setLabelText("Response received")
        QApplication.processEvents()

        # If no response was received, consider the connection closed
        if not response:
            self.disconnect_from_AERA()
            dialog = QMessageBox(self.parent_window)
            dialog.setWindowTitle("Warning!")
            dialog.setText("Lost connection with AERA, recommend reinitializing")
            # TODO: Provide a button to start the reinitialization process
            dialog.exec()

        return response

    # Send a design statement to AERA and make sure the message got through
    def send_change_to_AERA(self, new_statement, effect):
        # Ignore this if AERA's not connected
        if not self.conn:
            return

        # Tokenize the statement
        tokens = saddl.tokenize(new_statement)

        # Transmit the human action token by token with all other properties silent
        for token in tokens:
            self.world.topics_to_pInstances["human_action"].set_value(token)
            self.world.topics_to_pInstances["design_readback"].set_value("")
            self.world.topics_to_pInstances["design_effect"].set_value("")
            self._send_data_message()
            time.sleep(0.2)     # This seems to help ensure AERA catches everything

        # Broadcast TOADS' "readback" of the message (this is for AERA's benefit, we know it's already been received)
        for token in tokens:
            self.world.topics_to_pInstances["human_action"].set_value("")
            self.world.topics_to_pInstances["design_readback"].set_value(token)
            self.world.topics_to_pInstances["design_effect"].set_value("")
            self._send_data_message()
            time.sleep(0.2)     # This seems to help ensure AERA catches everything

        # TODO: Tokenize and broadcast the effect

        # Read out the buffer from AERA, ignore any of its messages
        while self.conn.receive():
            pass # TODO: This might cause an infinite loop if AERA keeps sending stuff

        return True

    # Inject a goal to AERA and see what change it would make to the design
    def request_change_from_AERA(self):
        # TODO: Pack up a goal
        message = TCPMessage()

        # Send it off to AERA and see what happens
        response = self._interact_with_AERA(message)

        # Unpack the response
        if response:
            pass # TODO: Unpack into a statement
        else:
            return None

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
