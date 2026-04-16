from PyQt6.QtCore import Qt, QRectF, QPointF, QPoint, QRect, QSize
from PyQt6.QtGui import QTransform, QColor, QPainterPath, QBrush
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QGraphicsScene, QGraphicsItem, QLineEdit, \
    QSizePolicy, QStyle, QGraphicsView, QGraphicsProxyWidget, QCheckBox, QVBoxLayout

from ui_core import action_font, reasoning_font, reasoning_font_metrics, ContainerWidget


# A general-purpose function for navigating lists of elements
def find_element_by_degree(list_of_elements: list, degree: int):
    for el in list_of_elements:
        if el.get_degree() == degree:
            return el
    return None


# Do some dynamic programming to find an element based on its full degree
def find_element_by_full_degree(list_of_elements: list, full_degree: str):
    element = None
    search_space = list_of_elements  # Start at the top
    degree_path = [int(x) for x in full_degree.split(".")]

    for degree in degree_path:
        element = find_element_by_degree(search_space, degree)
        if not element:
            break
        search_space = element.child_elements  # Search its children for the next descendant

    return element


# Work out whether one string of degrees (a.b.c.d) should come before another (w.x.y.z) in an ordered list
def compare_degrees(first, second):
    first = [int(n) for n in first.split(".")]
    second = [int(n) for n in second.split(".")]

    # Go through the list until the degrees don't match, then return whether the first is smaller
    for f, s in zip(first, second):
        if f == s:
            continue
        else:
            return f < s

    # If all of the zipped numbers are the same, compare the two based on how high-order they are
    return len(first) < len(second)


# A little popup widget that captures justifications for coupling and uncoupling actions
class CouplingJustificationPopup(QGraphicsItem):
    def __init__(self, parent_scene, matrix, element1=None, element2=None, coupling=None):
        super().__init__()

        # The only legal combinations are two elements and no coupling or no elements and a coupling
        assert ((element1 and element2 and not coupling) or
                (not element1 and not element2 and coupling))

        self.parent_scene = parent_scene
        self.matrix = matrix
        self.element1 = element1
        self.element2 = element2
        self.coupling = coupling

        # Draw a triangular corner on the left side
        self.arrow_size = 15

        # Get icons from parent window
        TOADSIcons = self.parent_scene.parent.TOADSIcons

        # Make a UI (same setup as in DesignElement)
        container = ContainerWidget()
        self.layout = QHBoxLayout()
        container.setLayout(self.layout)
        self.layout.setContentsMargins(2, 2, 2, 2)

        # Buttons used when defining a child
        self.cancelButton = QPushButton()
        self.cancelButton.setIcon(TOADSIcons["Cancel"])
        self.cancelButton.setToolTip("Cancel coupling")
        self.cancelButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.cancelButton.clicked.connect(self.cancel)
        self.layout.addWidget(self.cancelButton)

        self.acceptButton = QPushButton()
        self.acceptButton.setIcon(TOADSIcons["Confirm"])
        self.acceptButton.setToolTip("Confirm coupling")
        self.acceptButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.acceptButton.clicked.connect(self.confirm)
        self.layout.addWidget(self.acceptButton)

        # A LineEdit used to select the name of a new child
        self.justification_field = QLineEdit()
        self.justification_field.setFont(reasoning_font)
        if self.coupling:
            self.justification_field.setPlaceholderText("Justify uncoupling")
        else:
            self.justification_field.setPlaceholderText("Justify coupling")
        self.justification_field.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        #self.justification_field.returnPressed.connect(self.confirm)   # TODO: These are causing crashes
        #self.justification_field.editingFinished.connect(self.cancel)
        self.layout.addWidget(self.justification_field)

        # Set this up in a QGraphicsProxyWidget
        self.UI_container = self.matrix.parent_scene.addWidget(container)
        self.UI_container.setParentItem(self)

        # Set its size to be as small as the layout will allow
        min_width = self.layout.minimumSize().width()
        min_height = self.layout.minimumSize().height() #self.justification_field.sizeHint().height() + self.layout.contentsMargins().top() + self.layout.contentsMargins().bottom()
        self.UI_container.setGeometry(QRectF(self.arrow_size, -min_height/2, min_width, min_height))

        # Counter-rotate the popup so it's always level
        self.setRotation(-parent_scene.views()[0].rotation)

    def boundingRect(self):
        return QRectF(0, -self.layout.minimumSize().height()/2, self.layout.minimumSize().width() + self.arrow_size, self.layout.minimumSize().height())

    # Draw a box with a triangular left side pointing at the click location
    def paint(self, painter, option, widget=None):
        path = QPainterPath()
        path.moveTo(QPointF(0, 0))
        path.lineTo(QPointF(self.arrow_size, self.boundingRect().top()))
        path.lineTo(self.boundingRect().topRight())
        path.lineTo(self.boundingRect().bottomRight())
        path.lineTo(QPointF(self.arrow_size, self.boundingRect().bottom()))
        path.lineTo(QPointF(0, 0))

        # Draw the path and its outline
        painter.fillPath(path, QBrush(QColor(255, 255, 255)))
        painter.drawPath(path)

    # Cancel the action
    def cancel(self):
        self.parent_scene.close_popup()

    # Confirm the action and close the popup
    def confirm(self):
        # Put together a SADDL statement and send it off (this popup can both couple and uncouple)
        if self.coupling:
            element1_name = self.coupling.element1.get_name()
            element2_name = self.coupling.element2.get_name()
            action = "UNCOUPLE " + element1_name + " from " + element2_name
        else:
            action = "COUPLE " + self.element1.get_name() + " to " + self.element2.get_name()
        reasoning = self.justification_field.text()

        if reasoning:   # Don't accept a response with no reasoning
            self.matrix.speak_to_manager(action + " because " + reasoning)
            self.parent_scene.close_popup()


# TODO: Streamline sizing calculation/access for this and DesignElement
class NewElementItem(QGraphicsItem):
    def __init__(self, matrix, element_type):
        super().__init__()

        self.matrix = matrix                # The MultiMatrix this controls
        self.element_type = element_type    # The type of element this will add
        self.width = 180                     # Placeholder, set externally by matrix

        container = ContainerWidget()
        self.ui_layout = QHBoxLayout()
        self.ui_layout.setContentsMargins(2, 2, 2, 2)
        container.setLayout(self.ui_layout)
        #container.setStyleSheet("QWidget { background-color: rgba(0, 0, 0, 0); }")

        # Add in an editable description
        self.description = QLineEdit()
        self.description.setFont(reasoning_font)
        self.description.setPlaceholderText("Define a new " + element_type)
        self.description.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.description.returnPressed.connect(self.define_new_element)
        self.ui_layout.addWidget(self.description)

        # Set up the QProxyWidget container *after* the layout so it's sized correctly
        self.UI_container = self.matrix.parent_scene.addWidget(container)
        self.UI_container.setParentItem(self)

        # The height of this widget ultimately boils down to the height of this QLineEdit's box (and its margins)
        self.UI_container.setGeometry(QRectF(0, 0, self.width, self.minimum_height()))

    def boundingRect(self):
        return QRectF(0, 0, self.width, self.UI_container.boundingRect().height())

    def paint(self, painter, option, widget=None):
        pass

    def minimum_width(self):
        return self.ui_layout.minimumSize().width()

    def minimum_height(self):
        return self.description.sizeHint().height() + self.ui_layout.contentsMargins().top() + self.ui_layout.contentsMargins().bottom()

    # The width of the entire row across the multimatrix. Set by a MultiMatrix to expand the element to cover a new matrix shape
    def set_width(self, width):
        self.width = width
        self.UI_container.setGeometry(QRectF(0, 0, self.width, self.description.sizeHint().height()))

    # Send a command to the interaction manager to define a new element
    def define_new_element(self):
        degree = 1
        if len(self.matrix.elements[self.element_type]) > 0:
            degree += self.matrix.elements[self.element_type][-1].get_degree()

        # This widget does the review so the manager can just skip straight to execution and recording
        statement = "DEFINE " + self.element_type + str(degree) + " as " + self.description.text()
        self.matrix.speak_to_manager(statement)

        # Reset for the next one
        self.description.clear()


# TODO: Switch to QGraphicsPolygonItem for cooler shapes
# A design element is a CN, FR, DP, or PV. Anything that might show up in a design matrix
class DesignElement(QGraphicsItem):
    def __init__(self, multi_matrix, element, degree, parent_element=None):
        super().__init__()

        self.matrix = multi_matrix              # The big interconnected matrix this is in
        self.element = element                  # Is this a CN, FR, DP, or PV?
        self.degree = degree                    # The number of this element. Is it DP 1, FR 4, etc.? x.y.z is inherited from parents' degrees
        self.parent_element = parent_element    # This element may be a sub-element/child of another element
        self.child_elements = []
        self.outgoing_couplings = []            # What is this element coupled to?
        self.accepted = False                   # Lowest-level PVs only: Is this element accepted by an Acceptor or does it need further work?
        self.supported = False                  # Everything else: are all this element's children and couplings accepted/supported?

        # Figure how many levels down the hierarchy this element is (only needs to be done on init)
        if self.parent_element:
            self.depth = self.parent_element.get_depth() + 1
        else:
            self.depth = 1

        # Just placeholder values, these'll be set by the matrix
        self.left_matrix_width = 0
        self.right_matrix_width = 0

        # Adding normal QWidgets requires a QProxyWidget to act as a container. To put the UI widgets in a layout, they
        # need to be further nested inside a QWidget. `container` provides this container and `self.UI_container` is the
        # proxy widget that actually sits in parent_scene
        container = ContainerWidget()

        # Get icons from parent window
        TOADSIcons = self.matrix.parent_scene.parent.TOADSIcons

        # Set up a layout for everything
        self.main_layout = QHBoxLayout()
        container.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(2, 2, 2, 2)   # Padding for UI elements goes here

        # Buttons used when editing this element (these are turned off when creating a child element)
        self.deleteButton = QPushButton()
        self.deleteButton.setIcon(TOADSIcons["Delete"])
        self.deleteButton.setToolTip("Delete this " + element)
        self.deleteButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.deleteButton.clicked.connect(self.set_mode_delete)
        self.main_layout.addWidget(self.deleteButton)

        self.childButton = QPushButton()
        self.childButton.setIcon(TOADSIcons["AddChild"])
        self.childButton.setToolTip("Add a child " + element)
        self.childButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.childButton.clicked.connect(self.set_mode_child)
        self.main_layout.addWidget(self.childButton)

        # A label to show the name of the element
        self.label = QLabel(self.element + " " + self.get_full_degree())
        self.label.setFont(action_font)
        self.main_layout.addWidget(self.label)

        # A description to show the reasoning behind the element
        self.description = QLineEdit()
        self.description.setFont(reasoning_font)
        self.description.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Maximum)
        self.description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.description.setReadOnly(True)
        self.main_layout.addWidget(self.description)

        # Put this all in a QProxyWidget to make it with in the scene. Do this last to get the sizing right
        self.main_UI_container = self.matrix.parent_scene.addWidget(container)
        self.main_UI_container.setParentItem(self)
        self.main_UI_container.setGeometry(QRectF(0, 0, self.minimum_width(), self.minimum_height()))

        ## Alternate UI mode for defining a new child element ##
        alt_container = ContainerWidget()
        alt_container.setStyleSheet(container.styleSheet())

        # Set up a layout for everything (copy the margins from main_layout)
        self.alt_layout = QHBoxLayout()
        alt_container.setLayout(self.alt_layout)
        m = self.main_layout.contentsMargins()
        self.alt_layout.setContentsMargins(m.top(), m.bottom(), m.left(), m.right())

        # Buttons used when defining a child
        self.cancelButton = QPushButton()
        self.cancelButton.setIcon(TOADSIcons["Cancel"])
        self.cancelButton.setToolTip("Cancel child " + element)
        self.cancelButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.cancelButton.clicked.connect(self.set_mode_normal)
        self.alt_layout.addWidget(self.cancelButton)

        self.acceptButton = QPushButton()
        self.acceptButton.setIcon(TOADSIcons["Confirm"])
        self.acceptButton.setToolTip("Confirm child " + element)
        self.acceptButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.acceptButton.clicked.connect(self.create_child)
        self.alt_layout.addWidget(self.acceptButton)

        # A LineEdit used to select the name of a new child
        self.new_element_field = QLineEdit()
        self.new_element_field.setFont(reasoning_font)
        self.new_element_field.setPlaceholderText("Enter a child name...")
        self.new_element_field.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.new_element_field.returnPressed.connect(self.create_child)
        self.new_element_field.editingFinished.connect(self.set_mode_normal)
        self.alt_layout.addWidget(self.new_element_field)

        # Set this up like the main UI (and force it to be the same size) but leave it turned off
        self.alt_UI_container = self.matrix.parent_scene.addWidget(alt_container)
        self.alt_UI_container.setParentItem(self)
        self.alt_UI_container.setGeometry(QRectF(0, 0, self.minimum_width(), self.minimum_height()))
        self.alt_UI_container.setVisible(False)

        ## Alternate UI mode for defining a new child element ##
        del_container = ContainerWidget()
        del_container.setStyleSheet(container.styleSheet())

        # Set up a layout for everything (copy the margins from main_layout)
        self.del_layout = QHBoxLayout()
        del_container.setLayout(self.del_layout)
        m = self.main_layout.contentsMargins()
        self.del_layout.setContentsMargins(m.top(), m.bottom(), m.left(), m.right())

        # Buttons used when deleting the element
        self.acceptDelButton = QPushButton()
        self.acceptDelButton.setIcon(TOADSIcons["Confirm"])
        self.acceptDelButton.setToolTip("Confirm deletion")
        self.acceptDelButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.acceptDelButton.clicked.connect(self.remove_element)
        self.del_layout.addWidget(self.acceptDelButton)

        self.cancelDelButton = QPushButton()
        self.cancelDelButton.setIcon(TOADSIcons["Cancel"])
        self.cancelDelButton.setToolTip("Cancel deletion")
        self.cancelDelButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.cancelDelButton.clicked.connect(self.set_mode_normal)
        self.del_layout.addWidget(self.cancelDelButton)

        # A LineEdit used to select the name of a new child
        self.deletion_reasoning = QLineEdit()
        self.deletion_reasoning.setFont(reasoning_font)
        self.deletion_reasoning.setPlaceholderText("Reason for deletion...")
        self.deletion_reasoning.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        # self.deletion_reasoning.returnPressed.connect(self.remove_element)  # TODO: This causes a crash
        self.del_layout.addWidget(self.deletion_reasoning)

        # Set this up like the main UI (and force it to be the same size) but leave it turned off
        self.del_UI_container = self.matrix.parent_scene.addWidget(del_container)
        self.del_UI_container.setParentItem(self)
        self.del_UI_container.setGeometry(QRectF(0, 0, self.minimum_width(), self.minimum_height()))
        self.del_UI_container.setVisible(False)

    # Allows DesignElements to use sorted(). Sort first by kind of element then by degree
    def __lt__(self, other):
        if self.element != other.element:
            order = ["CN", "FR", "DP", "PV"]
            return order.index(self.element) < order.index(other.element)
        else:
            return compare_degrees(self.get_full_degree(), other.get_full_degree())

    # Switch the UI to its alternate mode to support defining a child element
    def set_mode_child(self):
        self.main_UI_container.setVisible(False)
        self.alt_UI_container.setVisible(True)
        self.del_UI_container.setVisible(False)
        self.new_element_field.setFocus()

    # Switch the UI to a different alternate mode to delete this element
    def set_mode_delete(self):
        self.main_UI_container.setVisible(False)
        self.alt_UI_container.setVisible(False)
        self.del_UI_container.setVisible(True)
        self.deletion_reasoning.setFocus()

    # Turn off the alternate UIs
    def set_mode_normal(self):
        self.main_UI_container.setVisible(True)
        self.alt_UI_container.setVisible(False)
        self.del_UI_container.setVisible(False)
        self.new_element_field.clear()
        self.deletion_reasoning.clear()

    def get_element(self):
        return self.element

    def get_degree(self):
        return self.degree

    # Return the full degree (ex. FR 1.2.3.4) by recursively checking ancestors' degree
    def get_full_degree(self):
        full_degree = str(self.degree)
        if self.parent_element:
            full_degree = self.parent_element.get_full_degree() + "." + full_degree
        return full_degree

    # Return a pre-computed depth value
    def get_depth(self):
        return self.depth

    # Return a list of parents, grandparents, and so on
    def get_ancestors(self):
        if not self.parent_element:
            return []
        else:
            return [self.parent_element] + self.parent_element.get_ancestors()

    # Get all the descendants of this element
    def get_descendants(self):
        descendants = []
        for child in self.child_elements:
            descendants.append(child)
            descendants += child.get_descendants()
        return descendants

    # Mostly for debugging messages
    def get_name(self):
        return self.element + self.get_full_degree()

    # Change the degree of this element (and renumber children accordingly)
    def set_degree(self, new_degree):
        self.degree = new_degree
        self.label.setText(self.element + " " + str(self.get_full_degree()))
        for i, child in enumerate(self.child_elements):
            child.set_degree(i + 1)

    # Set description's text and adjust its minimum size accordingly
    def set_description(self, reasoning):
        self.description.setText(reasoning)
        rect = reasoning_font_metrics.boundingRect(reasoning)
        self.description.setMinimumSize(int(rect.width()), self.description.height())

    # Add a new child
    def add_child(self, element):
        self.child_elements.insert(element.get_degree() - 1, element)

    def height(self):
        return self.boundingRect().height()

    # Calculate the smallest width the UI_container could have before things get truncated
    def minimum_width(self):
        return self.main_layout.minimumSize().width()

    # The shortest this can be before things get truncated
    def minimum_height(self):
        height = self.description.sizeHint().height()
        height += self.main_layout.contentsMargins().top() + self.main_layout.contentsMargins().bottom()
        return height

    # Set the width of the UI_container
    def set_width(self, width):
        self.main_UI_container.setGeometry(QRectF(0, 0, width, self.minimum_height()))

    # The farthest left and right the label can be drawn without running into a matrix (or leaving the viewport)
    def set_matrix_widths(self, left, right):
        self.left_matrix_width = left
        self.right_matrix_width = right

    # The bounds of this encompass the UI widget and any matrices that go off to the left or right
    def boundingRect(self):
        width = self.main_UI_container.boundingRect().width()
        height = self.main_UI_container.boundingRect().height()
        return QRectF(-self.left_matrix_width, 0, self.left_matrix_width + width + self.right_matrix_width, height)

    def paint(self, painter, option, widget=None):
        # Fade in the background with increasing depth
        sat = min(255, int(64 + ((255 - 64) * self.depth/8)))
        bg_color = QColor()
        if self.accepted or self.supported:
            hue = 115
        else:
            hue = 215
        bg_color.setHsv(hue, sat, 205, 128)

        # Draw the outline and background color
        painter.fillRect(self.boundingRect(), bg_color)
        painter.drawRect(self.boundingRect())

    # Put together a SADDL statement that orders the deletion of this element
    def remove_element(self):
        action = "DELETE " + self.get_element() + self.get_full_degree()
        reasoning = self.deletion_reasoning.text()

        if reasoning:   # You have to show your work
            self.matrix.speak_to_manager(action + " because " + reasoning)
        self.set_mode_normal()

    # Define a new child element based on the input from the alternate UI
    def create_child(self):
        degree = len(self.child_elements) + 1
        action = "DEFINE " + self.get_element() + self.get_full_degree() + "." + str(degree)
        reasoning = self.new_element_field.text()

        if reasoning:   # Empty names aren't permitted
            self.matrix.speak_to_manager(action + " as " + reasoning)
        self.set_mode_normal()

    def remove_child(self, child):
        self.child_elements.remove(child)

    # Look through connections to other elements to work out this element's acceptance status
    # Support either comes from children or coupled elements. An element with children can only
    # be supported if all of its children are supported. A lowest-level element can only be
    # supported if everything it's coupled to is supported. An upper-level element will have both
    # children and couplings but the children taken precedence
    def check_support(self):
        if self.element == "PV" and len(self.child_elements) == 0:  # Lowest-level PVs only depend on their Acceptors
            return self.accepted

        # All child elements must be accepted or supported
        if len(self.child_elements) >= 1:
            self.supported = True
            for child in self.child_elements:
                if not child.check_support():
                    self.supported = False
                    break

        # If there are no children, make sure all the elements this is coupled to are supported
        elif len(self.outgoing_couplings) >=1 :
            self.supported = True
            for coupling in self.outgoing_couplings:
                if not coupling.element2.check_support():
                    self.supported = False
                    break

        # If neither are present, there's nothing to support this element
        else:
            self.supported = False

        return self.supported

    # Set the element as accepted and prevent it from being modified (support elements are flexible, accepted ones are locked)
    def accept(self):
        self.accepted = True
        self.childButton.setEnabled(False)
        self.deleteButton.setEnabled(False)
        self.childButton.setToolTip("Accepted elements are locked")
        self.deleteButton.setToolTip("Accepted elements are locked")

    # Clear the acceptance status and allow it to be modified again
    def clear(self):
        self.accepted = False
        self.childButton.setEnabled(True)
        self.deleteButton.setEnabled(True)
        self.childButton.setToolTip("Add a child PV")
        self.deleteButton.setToolTip("Delete this PV")


# A simple class to keep track of a single coupling between DesignElements
class CouplingElement(QGraphicsItem):
    def __init__(self, multi_matrix, element1, element2, value="X"):
        super().__init__()

        self.multi_matrix = multi_matrix
        self.element1 = element1
        self.element2 = element2
        self.value = value

        #self.textItem = QTextItem(value)

    def boundingRect(self):
        #return QRectF(0, 0, self.textItem.width(), self.textItem.ascent() + self.textItem.descent())
        return QRectF(0, 0, 20, 20)  # TODO: Make this dependent on value, font, etc.

    def paint(self, painter, option, widget=None):
        painter.drawText(5, 15, self.value)


# These widgets connect to PVs to mark whether they've been accepted and why/why not
class Acceptor(QGraphicsItem):
    def __init__(self, multi_matrix, connected_PV):
        super().__init__()

        self.matrix = multi_matrix
        self.connected_PV = connected_PV

        container = ContainerWidget()

        # Set up the layout for everything
        self.main_layout = QHBoxLayout()
        container.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(2, 2, 2, 2)

        # Set up the widgets
        self.accepted = QPushButton("Accept?")
        self.accepted.setCheckable(True)
        self.accepted.setFont(reasoning_font)
        self.accepted.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.accepted.clicked.connect(self._toggled)
        self.main_layout.addWidget(self.accepted)
        container.setStyleSheet("QCheckBox { padding: 0px; }")   # The QCheckBox is a bit taller than the QLineEdit

        self.justification = QLineEdit()
        self.justification.setFont(reasoning_font)
        self.justification.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Maximum)
        self.justification.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.justification.setPlaceholderText("Justification...")
        self.main_layout.addWidget(self.justification)

        # Convert the container to a QGraphicsProxyWidget
        self.UI_container = self.matrix.parent_scene.addWidget(container)
        self.UI_container.setParentItem(self)
        self.UI_container.setGeometry(QRectF(0, 0, self.minimum_width(), self.minimum_height()))

    def __lt__(self, other):
        return self.connected_PV < other.connected_PV

    # If checked or unchecked, communicate that accordingly
    def _toggled(self):
        if self.accepted.isChecked():
            if len(self.justification.text()) > 0:
                action = "ACCEPT " + self.connected_PV.get_element() + self.connected_PV.get_full_degree()
                reasoning = self.justification.text()
                self.matrix.speak_to_manager(action + " because " + reasoning)
            else:
                self.accepted.setChecked(False)
                # TODO: Report an error
        else:
            if len(self.justification.text()) > 0:
                action = "CLEAR " + self.connected_PV.get_element() + self.connected_PV.get_full_degree()
                reasoning = self.justification.text()
                self.matrix.speak_to_manager(action + " because " + reasoning)
            else:
                self.accepted.setChecked(True)
                # TODO: Report an error

    # Calculate the smallest width the UI_container could have before things get truncated
    def minimum_width(self):
        return self.main_layout.minimumSize().width()

    # The shortest this can be before things get truncated
    def minimum_height(self):
        height = self.justification.sizeHint().height()
        height += self.main_layout.contentsMargins().top() + self.main_layout.contentsMargins().bottom()
        return height

    # Use this if this widget starts getting too tall to line up with the PV DesignElements (requires layout tweaks)
    def set_height(self, height):
        pass #self.UI_container.setGeometry(QRectF(0, 0, self.minimum_width(), height))

    def boundingRect(self):
        #return QRectF(0, 0, self.minimum_width(), self.height) #self.minimum_height())
        return self.UI_container.boundingRect()

    def paint(self, painter, option, widget=None):
        # Fade in the background with increasing depth (with respect to PV depth)
        sat = min(255, int(64 + ((255 - 64) * self.connected_PV.depth / 8)))
        bg_color = QColor()
        if self.accepted.isChecked():
            hue = 115
        else:
            hue = 215
        bg_color.setHsv(hue, sat, 205, 128)

        # Draw the outline and background color
        painter.fillRect(self.boundingRect(), bg_color)
        painter.drawRect(self.boundingRect())

    # Hide or show the UI depending on whether the matrix wants this to be visible or not
    def hide(self):
        self.setVisible(False)
    def show(self):
        self.setVisible(True)


# The MultiMatrix is just a container for design elements. It manages drawing positions and rotations but isn't
# actually rendered itself
class MultiMatrix(QGraphicsItem):
    def __init__(self, parent_scene):
        super().__init__()

        self.parent_scene = parent_scene

        # Keep track of all the design elements and couplings
        self.elements = {"CN": [], "FR": [], "DP": [], "PV": []}
        self.couplings = []
        self.acceptors = {}     # Organized by PV:Acceptor

        # Make the buttons that'll add new top-level elements
        self.new_CN_field = NewElementItem(self, "CN")
        self.new_CN_field.setRotation(90)
        self.parent_scene.addItem(self.new_CN_field)

        self.new_FR_field = NewElementItem(self, "FR")
        self.parent_scene.addItem(self.new_FR_field)

        self.new_DP_field = NewElementItem(self, "DP")
        self.new_DP_field.setRotation(-90)
        self.parent_scene.addItem(self.new_DP_field)

        self.new_PV_field = NewElementItem(self, "PV")
        self.new_PV_field.setRotation(180)
        self.parent_scene.addItem(self.new_PV_field)

        # The edges of the MultiMatrix's boundingRect
        self.xMinExtent = 0
        self.yMaxExtent = 0
        self.xMaxExtent = 0
        self.yMinExtent = 0

        # Initialize extents and field positions
        self._update_matrix()

    def boundingRect(self):
        return QRectF(self.xMinExtent, self.yMinExtent, self.xMaxExtent, self.yMaxExtent)

    def paint(self, painter, option, widget=None):
        pass

    # Pass a SADDL statement (complete with reasoning) up and directly apply it
    def speak_to_manager(self, statement):
        return self.parent_scene.manager.apply_change_with_reasoning(statement)

    # Return all elements of a type (top-levels and descendants)
    def _get_all_elements(self, element_type):
        elements = []
        for toplevel in self.elements[element_type]:
            elements.append(toplevel)
            elements += toplevel.get_descendants()
        return elements

    # How high is the stack of CNs, FRs, etc.? How far does it stick out from the buffer?
    def _height_of_side(self, element_type):
        return sum(element.height() for element in self._get_all_elements(element_type))

    # Look at a stack of elements and return the minimum width to avoid truncation
    def _min_width_of_side(self, element_type):
        if element_type == "CN":
            width = self.new_CN_field.minimum_width()
        elif element_type == "FR":
            width = self.new_FR_field.minimum_width()
        elif element_type == "DP":
            width = self.new_DP_field.minimum_width()
        else:
            width = self.new_PV_field.minimum_width()

        for element in self._get_all_elements(element_type):
            if element.minimum_width() > width:
                width = element.minimum_width()     # The smallest this element is allowed to be
        return width

    # Every time the matrix is changed, all elements need to be moved and resized to accommodate the new element
    def _update_matrix(self):
        # Calculate the widest CNs, FRs, DPs, and PVs (just the UI bits) so things can be appropriately spaced
        # and then set the center of the MultiMatrix to make sure these fit in
        matrix_center_width = max(self._min_width_of_side("FR"), self._min_width_of_side("PV"))     # Horizontal elements
        matrix_center_height = max(self._min_width_of_side("CN"), self._min_width_of_side("DP"))    # Vertical elements

        # Set the height of all vertical elements and fields
        self.new_CN_field.set_width(matrix_center_height)
        self.new_DP_field.set_width(matrix_center_height)
        for element_type in ["CN", "DP"]:
            for element in self._get_all_elements(element_type):
                element.set_width(matrix_center_height)

        # Set the width of all horizontal elements and fields
        self.new_FR_field.set_width(matrix_center_width)
        self.new_PV_field.set_width(matrix_center_width)
        for element_type in ["FR", "PV"]:
            for element in self._get_all_elements(element_type):
                element.set_width(matrix_center_width)

        # Elements' distance from the center changes depending on where in the stack they are and how tall the
        # elements above them are. These blocks calculate the distance from the center for each element and
        # reposition everything accordingly.
        radial_distance = 0
        for el in self._get_all_elements("CN"):
            el.setPos(-radial_distance, 0)                      # Put this in the right position from the center
            radial_distance += el.height()                      # Account for the height of this element
        self.new_CN_field.setPos(QPointF(-radial_distance, 0))  # Move the field to the bottom of the stack

        radial_distance = matrix_center_height
        for el in self._get_all_elements("FR"):
            el.setPos(0, radial_distance)
            radial_distance += el.height()
        self.new_FR_field.setPos(QPointF(0, radial_distance))

        radial_distance = matrix_center_width
        for el in self._get_all_elements("DP"):
            el.setPos(radial_distance, matrix_center_height)
            radial_distance += el.height()
        self.new_DP_field.setPos(QPointF(radial_distance, matrix_center_height))

        radial_distance = 0
        for el in self._get_all_elements("PV"):
            el.setPos(matrix_center_width, -radial_distance)
            self.acceptors[el].setPos(0, -radial_distance)
            self.acceptors[el].set_height(el.height())
            radial_distance += el.height()
        self.new_PV_field.setPos(QPointF(matrix_center_width, -radial_distance))

        # Figure out how tall each stack of elements is
        CN_height = self._height_of_side("CN")
        FR_height = self._height_of_side("FR")
        DP_height = self._height_of_side("DP")
        PV_height = self._height_of_side("PV")

        # Recalculate extents for the MultiMatrix's boundingRect
        self.xMinExtent = -CN_height - self.new_CN_field.boundingRect().height()
        self.yMaxExtent = matrix_center_height + FR_height + self.new_FR_field.boundingRect().height()
        self.xMaxExtent = matrix_center_width + DP_height + self.new_DP_field.boundingRect().height()
        self.yMinExtent = -PV_height - self.new_PV_field.boundingRect().height()

        # Size the matrices where intersections should occur
        for element in self._get_all_elements("CN"):
            element.set_matrix_widths(0, FR_height)
        for element in self._get_all_elements("FR"):
            element.set_matrix_widths(CN_height, DP_height)
        for element in self._get_all_elements("DP"):
            element.set_matrix_widths(FR_height, PV_height)
        for element in self._get_all_elements("PV"):
            element.set_matrix_widths(DP_height, 0)

        # Figure out where to draw the coupling coefficients
        for coupling in self.couplings:
            # First element is on the left or right side of the matrix
            if coupling.element1.get_element() == "CN" or coupling.element1.get_element() == "DP":
                coupling_x = coupling.element1.scenePos().x()
                coupling_y = coupling.element2.scenePos().y()

            # First element is on the bottom of the matrix
            elif coupling.element1.get_element() == "FR":
                coupling_x = coupling.element2.scenePos().x()
                coupling_y = coupling.element1.scenePos().y()

            # Move the coupling to the appropriate position
            coupling.setPos(coupling_x, coupling_y)

        # Update the coloring and support status of the matrix
        self._check_all_supports()

        # Make sure only PVs with at the lowest-level of detail have visible acceptors
        for pv in self._get_all_elements("PV"):
            if len(pv.child_elements) > 0:
                self.acceptors[pv].hide()
            else:
                self.acceptors[pv].show()


    # Make sure each element's coloring and acceptance/support status is up to date
    def _check_all_supports(self):
        for el in self._get_all_elements("CN") + self._get_all_elements("FR") + self._get_all_elements("DP") + self._get_all_elements("PV"):
            el.check_support()

    # Add a DesignElement into the appropriate part of the matrix
    def _add_element(self, element, parent_element=None):
        # If this is a child element, assign it to its parent. If not, put it in the right spot in the top-level lists
        if parent_element:
            parent_element.add_child(element)
        else:
            self.elements[element.get_element()].insert(element.get_degree() - 1, element)

        # These blocks create a new element, rotate it for the appropriate side, and then add it to the right list
        if element.get_element() == "CN":
            element.setRotation(90)      # Left side
        elif element.get_element() == "FR":
            pass
        elif element.get_element() == "DP":
            element.setRotation(-90)     # Right side
        elif element.get_element() == "PV":
            element.setRotation(180)     # Top side

            acceptor = Acceptor(self, element)  # Add an acceptor while we're at it
            acceptor.setRotation(180)           #
            self.parent_scene.addItem(acceptor) #
            self.acceptors[element] = acceptor  #

        # Add the new element to the scene and update the matrix
        self.parent_scene.addItem(element)
        self._update_matrix()

    # Remove a CN, FR, DP, or PV
    def _remove_element(self, element_to_remove):
        # If it's a PV, remove its acceptor
        if element_to_remove.get_element() == "PV":
            self.parent_scene.removeItem(self.acceptors[element_to_remove])
            del self.acceptors[element_to_remove]

        # Check if it's coupled to anything
        couplings_to_remove = []
        for coupling in self.couplings:
            if coupling.element1 == element_to_remove or coupling.element2 == element_to_remove:
                couplings_to_remove.append(coupling)

        # Remove any couplings
        for coupling in couplings_to_remove:
            self._remove_coupling(coupling, force_remove=True)

        # Add child elements to the removal list
        elements_to_remove = []
        for child in element_to_remove.child_elements:
            elements_to_remove.append(child)

        # Remove those (if you don't copy them out first, the references
        # get all wonky and some things don't end up deleting properly)
        for el in elements_to_remove:
            self._remove_element(el)

        # If this element is a child, remove it from its parent's list. Otherwise, remove it from the top-level lists
        if element_to_remove.parent_element:
            element_to_remove.parent_element.remove_child(element_to_remove)
        else:
            self.elements[element_to_remove.get_element()].remove(element_to_remove)

        # Update the matrix accordingly
        self.parent_scene.removeItem(element_to_remove)
        self._update_matrix()

    # Add a coupling between two elements
    def _add_coupling(self, element1, element2):
        if element1.get_depth() != element2.get_depth():  # Coupling across LoDs doesn't make sense
            return False

        # Make sure they're in the order CN<FR<DP<PV
        element1, element2 = sorted([element1, element2])

        # Make sure that this coupling isn't already registered
        coupling_exists = False
        for c in self.couplings:
            if (c.element1 == element1) and (c.element2 == element2):
                coupling_exists = True

        # If it isn't, create it and add it to the list
        if not coupling_exists:
            coupling = CouplingElement(self, element1, element2)
            element1.outgoing_couplings.append(coupling)    # This is used to track support/acceptance

            # Rotate it if needed
            if element1.get_element() == "CN":
                coupling.setRotation(90)  # Left side
            elif element1.get_element() == "DP":
                coupling.setRotation(-90)  # Right side

            # If these elements have parents, couple them, too
            if element1.get_depth() > 1:
                self._add_coupling(element1.parent_element, element2.parent_element)

            self.couplings.append(coupling)
            self.parent_scene.addItem(coupling)
            self._update_matrix()
            return True

        else:
            return False

    # Remove a coupling between elements. This will automatically block the removal of a coupling
    # if an element's children are still coupled. If deleting an element, set force_remove=True
    def _remove_coupling(self, coupling_to_remove: CouplingElement, force_remove=False):
        # If there are coupled children, block the removal (must be done from the lower levels first)
        blocked = False
        if not force_remove:  # If deleting an element, all its couplings must be deleted at all levels
            for child in coupling_to_remove.element1.child_elements:
                for cp in self.couplings:
                    if cp.element1 == child:
                        counterpart_ancestors = cp.element2.get_ancestors()
                        if coupling_to_remove.element2 in counterpart_ancestors:
                            blocked = True
                            print("Cannot uncouple", coupling_to_remove.element1.get_name(), "and",
                                  coupling_to_remove.element2.get_name())
                            break

        # Remove the coupling
        if not blocked:
            self.couplings.remove(coupling_to_remove)
            coupling_to_remove.element1.outgoing_couplings.remove(coupling_to_remove)
            self.parent_scene.removeItem(coupling_to_remove)
            self._update_matrix()
            return True
        return False

    # Takes a SADDL name, validates it, and returns the element if it exists (or None otherwise)
    def _validate_and_retrieve(self, element_name):
        element_type, element_full_degree = element_name[:2], element_name[2:]
        assert (element_type in ["CN", "FR", "DP", "PV"])
        return find_element_by_full_degree(self.elements[element_type], element_full_degree)

    # The main interface for adding new FRs, DPs, etc. Takes a SADDL name ("FR1.2.3") and figures out where to
    # insert it in the matrix. If that particular element already exists, it returns False
    def define_element(self, name, reasoning=""):
        element_type, full_degree = name[:2], name[2:]
        assert (element_type in ["CN", "FR", "DP", "PV"])

        # Make sure the element doesn't already exist. If it does, return a failure
        for el in self._get_all_elements(element_type):
            if el.get_full_degree() == full_degree:
                print("Already exists")
                return False

        # Work out the parent's degree and find that element (assuming it exists)
        parent_degree = ".".join(full_degree.split(".")[:-1])
        if parent_degree != "":
            parent_element = find_element_by_full_degree(self.elements[element_type], parent_degree)
        else:
            parent_element = None

        # Create and add the element
        degree = [int(x) for x in full_degree.split(".")][-1]
        element = DesignElement(self, element_type, degree, parent_element)
        element.set_description(reasoning)
        self._add_element(element, parent_element)
        return True

    # The main interface for removing FRs, DPs, etc. Takes a SADDL name ("FR1.2.3") and removes it
    # If that particular element doesn't exist, it returns False
    # TODO: Crash when adding/deleting a bunch of DPs and then removing an FR with no children?
    def delete_element(self, name, skip_preview=False):
        # Retrieve the element (if it exists)
        element = self._validate_and_retrieve(name)
        if not element:
            return False

        # Remove it
        self._remove_element(element)
        return True

    # Couple elements given their SADDL names
    def couple_elements(self, element1_name, element2_name):
        element1 = self._validate_and_retrieve(element1_name)
        element2 = self._validate_and_retrieve(element2_name)
        if (not element1) or (not element2):
            return False

        # Make sure they're in the order CN<FR<DP<PV
        element1, element2 = sorted([element1, element2])

        # Perform the coupling
        return self._add_coupling(element1, element2)

    # Uncouple elements given their SADDL names
    def uncouple_elements(self, element1_name, element2_name):
        element1 = self._validate_and_retrieve(element1_name)
        element2 = self._validate_and_retrieve(element2_name)
        if (not element1) or (not element2):
            return False

        # Make sure they're in the order CN<FR<DP<PV
        element1, element2 = sorted([element1, element2])

        # Find the right CouplingElement
        coupling = None
        for cp in self.couplings:
            if cp.element1 == element1 and cp.element2 == element2:
                coupling = cp
        if not coupling:
            return False

        # Perform the uncoupling
        return self._remove_coupling(coupling)

    # Mark a PV as accepted
    def accept_element(self, element_name, reasoning):
        element = self._validate_and_retrieve(element_name)
        if not element or element.get_element() != "PV":     # Only PVs can be marked for acceptance
            return False

        # Mark the element as accepted and update everything accordingly
        element.accept()
        self.acceptors[element].justification.setText(reasoning)
        self.acceptors[element].accepted.setChecked(True)
        self._check_all_supports()
        return True

    # Clear a PV's acceptance
    def clear_element(self, element_name, reasoning):
        element = self._validate_and_retrieve(element_name)
        if not element or element.get_element() != "PV":  # Only PVs can be marked for acceptance
            return False

        # Clear the acceptance and update accordingly
        element.clear()
        self.acceptors[element].justification.setText(reasoning)
        self.acceptors[element].accepted.setChecked(False)
        self._check_all_supports()
        return True


# This is the main QGraphicsScene that renders and handles events for the central UI
class MatrixScene(QGraphicsScene):
    def __init__(self, parent, interaction_manager):
        super().__init__(parent)
        self.parent = parent
        self.manager = interaction_manager

        self.matrix = MultiMatrix(self)
        self.addItem(self.matrix)

        self.coupling_popup = None

        # Draw a coordinate origin for convenience
        # radius = 10
        # self.addEllipse(QRectF(-radius, -radius, radius*2, radius*2))
        # self.addLine(0, 0, radius, 0)
        # self.addLine(0, 0, 0, radius)

    # Return the matrix so it can be modified by something like an InteractionManager
    def get_matrix(self):
        return self.matrix

    # Delete the matrix and start a new one
    def reset_matrix(self):
        self.clear()
        self.setSceneRect(QRectF())

        self.matrix = MultiMatrix(self)
        self.addItem(self.matrix)
        return self.matrix

    # Close a coupling popup
    def close_popup(self):
        if self.coupling_popup:
            self.removeItem(self.coupling_popup)
            self.coupling_popup = None

    # QGraphicsScene: Handle mousePress events or pass them along as needed
    def mousePressEvent(self, event):
        # Check if the left button was pressed
        if event.button() == Qt.MouseButton.LeftButton:
            # Ignore any items not relevant for these mode switches
            filtered_items = []
            for item in self.items(event.scenePos(), deviceTransform=QTransform()):
                if isinstance(item, MultiMatrix) or isinstance(item, QGraphicsProxyWidget):
                    continue
                else:
                    filtered_items.append(item)

            # Get the topmost item in the mouse event
            if len(filtered_items) > 0:
                first_item = filtered_items[0]
            else:
                self.close_popup()
                first_item = None

            # If a coupling was clicked on, remove it and create a new justification popup
            if isinstance(first_item, CouplingElement):
                self.close_popup()
                self.coupling_popup = CouplingJustificationPopup(self, self.matrix, coupling=first_item)
                self.coupling_popup.setPos(event.scenePos())
                self.addItem(self.coupling_popup)
                event.accept()

            # If there's no coupling, try to make one
            elif isinstance(first_item, DesignElement):
                self.close_popup()  # Close any open popup

                # Get all design elements under the mouse click
                elements = list(filter(lambda i: isinstance(i, DesignElement), filtered_items))

                # Make sure it's possible to couple here
                if len(elements) == 2:
                    if elements[0].get_depth() == elements[1].get_depth():  # Only allow coupling at the same LoD
                        # Make sure they're in the order CN<FR<DP<PV
                        element1, element2 = sorted([elements[0], elements[1]])

                        # Create a popup to capture the reasoning for this coupling
                        self.close_popup()
                        self.coupling_popup = CouplingJustificationPopup(self, self.matrix, element1=element1, element2=element2)
                        self.coupling_popup.setPos(event.scenePos())
                        self.addItem(self.coupling_popup)
                    event.accept()

                # If a coupling isn't possible, pass the event along
                else:
                    super().mousePressEvent(event)

            # If the popup was clicked on, send the event there
            elif isinstance(first_item, CouplingJustificationPopup):
                super().mousePressEvent(event)

            # If it's another element, make sure the popup closes first
            elif isinstance(first_item, NewElementItem) or isinstance(first_item, Acceptor):
                self.close_popup()
                super().mousePressEvent(event)

            # End the event here in any other case
            else:
                event.accept()

        # Forward any other mouse events
        else:
            super().mousePressEvent(event)


# This version QGraphicsView includes panning, zooming, and rotation controls as well as an infinite canvas
class NavigableGraphicsView(QGraphicsView):
    def __init__(self, parent, scene):
        super().__init__(scene)

        self.parent_window = parent

        # Turn off scrollbars and set drag mode
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)  # This has a custom implementation

        # Make the scene arbitrarily large so the user can pan beyond the edge of the matrix
        canvas_size = 4000
        self.setSceneRect(QRectF(-canvas_size // 2, -canvas_size // 2, canvas_size, canvas_size))

        # Helpers for dragging/panning and zooming
        self.drag_start = QPoint(0, 0)
        self.dragging = False
        self.ctrl_down = False
        self._net_zoom = 1
        self.rotation = 0

    # It's important that the zoom factors multiply together to 1 otherwise, you'll build up error over time
    def zoom_in(self):
        self._net_zoom *= 1.25
        self.scale(1.25, 1.25)

    def zoom_out(self):
        self._net_zoom *= 0.8
        self.scale(0.80, 0.80)

    def view_reset(self):
        self.scale(1/self._net_zoom, 1/self._net_zoom)
        self._net_zoom = 1

        self.rotate(-self.rotation)
        self.rotation = 0

    def rotate_cw(self):
        self.rotate(90)
        self.rotation += 90

    def rotate_ccw(self):
        self.rotate(-90)
        self.rotation += -90

    def rotate_diamond(self):
        if self.rotation % 90 != 45:
            self.rotate(45)
            self.rotation += 45
        else:
            self.rotate(-45)
            self.rotation -= 45

    def mousePressEvent(self, event):
        # If the left button was clicked, make sure there's nothing underneath before starting a drag command
        if event.button() == Qt.MouseButton.LeftButton:
            items = self.scene().items(self.mapToScene(event.pos()), deviceTransform=self.transform())
            if not items or (len(items) == 1 and isinstance(items[0], MultiMatrix)):
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.dragging = True
                self.drag_start = event.pos()
                event.accept()
            else:
                super().mousePressEvent(event)

        # If it's just the middle button, you can do that anywhere
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self.dragging = True
            self.drag_start = event.pos()
            event.accept()

        # TODO: I think I can delete this
        # If a drag command is detected, settle the event here (pass it on otherwise)
        # if self.dragging:
        #    self.drag_start = event.pos()
        #    event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            drag = event.pos() - self.drag_start
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - drag.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - drag.y())

            # Middle mouse behaves like scrolling the viewport, left mouse is more like dragging around the scene
            # (making every move relative to the last turns it from a scroll to a drag)
            if True or event.buttons() == Qt.MouseButton.LeftButton:  # disabled for now
                self.drag_start = event.pos()
            event.accept()

            # TODO: If applicable, send the new viewport boundaries to the matrix

            """
            # If the cursor is moving over the background, change it to an open hand to indicate dragging is possible
            elif not self.dragging:
                items = self.scene().items(self.mapToScene(event.pos()), deviceTransform=self.transform())
                if not items or (len(items) == 1 and isinstance(items[0], MultiMatrix)):
                    self.setCursor(Qt.CursorShape.OpenHandCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
                    super().mouseMoveEvent(event)
            """
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # Handle mouse wheel scrolling
    def wheelEvent(self, event):
        if self.ctrl_down or True:
            if event.angleDelta().y() > 0:  # Vertical scroll zooms in and out
                self.zoom_in()
            elif event.angleDelta().y() < 0:  #
                self.zoom_out()
            elif event.angleDelta().x() > 0:  # Horizontal scroll rotates the view because why not?
                self.rotate(-9)
                self.rotation += -9
            elif event.angleDelta().x() < 0:  # TODO: Make this snappy by tracking angle and slewing to that
                self.rotate(9)
                self.rotation += 9
            event.accept()
        else:
            super().wheelEvent(event)

    # Report resize events to the main window so the history view can be moved accordingly
    def resizeEvent(self, event):
        self.parent_window.move_timeline_view(event.size())
        super().resizeEvent(event)
