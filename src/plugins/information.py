from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget, QFormLayout, QScrollArea, \
    QHBoxLayout, QDoubleSpinBox, QComboBox, QLayout, QSizePolicy, QTabWidget, QSplitter

import numpy as np
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from scipy.stats import norm
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from plugins_core import TOADSPlugin
from ui_core import action_font
import saddl

"""
There's a lot of nesting to keep track of. Objects marked with a * are accessible directly

InformationContentCalculator
	|
	+- Container/VBoxLayout
		|
		+-- Information content (QLabel)
		|
		|
		+-- /QGridLayout
			|
			+-- QScrollArea
			|	|
			|	+-- tolerances_widget*/QFormLayout
			|		|
			|		+-- label:ToleranceWidget
			|		+-- label:ToleranceWidget
			|		+-- ...
			|	
			+-- QScrollArea
			|	|
			|	+-- distros_widget*/QFormLayout
			|		|
			|		+-- label:DistroWidget
			|		+-- label:DistroWidget
			|		+-- ...
			|
			+-- QScrollArea
				|
				+-- plots_widget*/QVBoxLayout
					|
					+-- PlotWidget
					+-- PlotWidget
					+-- ...
"""

# Collect a set of minimum, target, and maximum values for an FR
# TODO: Validate these value ranges
class ToleranceWidget(QWidget):
    def __init__(self, parent, update_handler):
        super().__init__(parent)
        self.update_handler = update_handler    # Call this when an input changes

        # Put together the layout
        layout = QHBoxLayout()
        self.setLayout(layout)

        # The minimum value of this FR...
        self.minimum_value = QDoubleSpinBox(self)
        self.minimum_value.setRange(-1e4, 1e4)
        self.minimum_value.setValue(-1)
        self.minimum_value.valueChanged.connect(self._value_changed)
        layout.addWidget(self.minimum_value)

        # ...is less than...
        less_than_label1 = QLabel("≤", self)
        less_than_label1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(less_than_label1)

        # ...the target value of this FR...
        self.target_value = QDoubleSpinBox(self)
        self.target_value.setRange(-1e4, 1e4)
        self.target_value.setValue(0)
        self.target_value.valueChanged.connect(self._value_changed)
        layout.addWidget(self.target_value)

        # ...which is less than...
        less_than_label2 = QLabel("≤", self)
        less_than_label2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(less_than_label2)

        # ...it's maximum value
        self.maximum_value = QDoubleSpinBox(self)
        self.maximum_value.setRange(-1e4, 1e4)
        self.maximum_value.setValue(1)
        self.maximum_value.valueChanged.connect(self._value_changed)
        layout.addWidget(self.maximum_value)

    def _value_changed(self, i):
        self.update_handler()


# Collect a distribution type, mean, and variance for a coupling
class DistroWidget(QWidget):
    def __init__(self, parent, update_handler):
        super().__init__(parent)
        self.update_handler = update_handler    # Call this when an input changes

        # Put together the layout
        layout = QFormLayout()
        self.setLayout(layout)

        self.distro_type = QComboBox(self)
        self.distro_type.addItem("Normal")
        self.distro_type.currentTextChanged.connect(self._value_changed)
        layout.addRow("Distribution:", self.distro_type)

        self.mean = QDoubleSpinBox(self)
        self.mean.setRange(-1e4, 1e4)
        self.mean.setValue(0)
        self.mean.valueChanged.connect(self._value_changed)
        layout.addRow("Mean:", self.mean)

        self.variance = QDoubleSpinBox(self)
        self.variance.setRange(-1e4, 1e4)
        self.variance.setValue(1)
        self.variance.valueChanged.connect(self._value_changed)
        layout.addRow("Variance:", self.variance)

    def _value_changed(self, i):
        self.update_handler()


# A widget to display a small matplotlib plot
# TODO: See about nesting a FigureCanvasQTAgg inside a QWidget for easier layout handling
class PlotWidget(FigureCanvasQTAgg):
    def __init__(self, parent, FR_name):
        self.FR_name = FR_name
        figure = Figure(figsize=(5, 3), dpi=100)
        self.axes = figure.add_subplot(111)
        super().__init__(figure)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(300, 200))    # Only thing keeping the charts from being tiny

    # When redrawing, reset these details because they seem to be getting wiped
    def set_up_figure(self):
        self.axes.set_title("$p_{success}$(" + self.FR_name + ")")
        self.axes.set_xlabel("FR Value")
        self.axes.set_ylabel("p")
        self.axes.set_ylim(0, 1)
        self.axes.set_facecolor("#a1a8b3")
        self.figure.patch.set_facecolor("#717d8e")
        self.figure.subplots_adjust(left=0.2, right=0.9, bottom=0.25, top=0.8)


# A widget to help calculate information content (ultimately extends QDockWidget)
class InformationContentCalculator(TOADSPlugin):
    def __init__(self, parent_window, manager):
        super().__init__(parent_window, manager)
        self.setWindowTitle("Information Content Calculator")
        self.setDockLocation(Qt.DockWidgetArea.RightDockWidgetArea)

        # Store direct references to form widgets for convenience
        self.tolerances = {}    # Keep track of ToleranceWidgets    (FR name:ToleranceWidget)
        self.distros = {}       # Keep track of DistroWidgets       (coupling text:DistroWidget)
        self.plots = {}         # Keep track of PlotWidgets         (FR name:PlotWidget)

        # Make the information content label
        self.info_content_label = QLabel(self)
        self.info_content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_content_label.setFont(action_font)
        self._display_information_content(0)

        # Everything in the calculator
        calculator_layout = QSplitter()     # This creates an adjustable side-by-side layout for the inputs and outputs
        input_tabs = QTabWidget()           # This organizes the inputs into FR tolerances and coupling distributions
        input_tabs.setTabPosition(QTabWidget.TabPosition.West)

        # This widget will hold a form to specify FR tolerance inputs
        self.tolerances_widget = QWidget(self)
        tolerances_layout = QFormLayout()
        # TODO: Get these size constraints to have a reasonable minimum size
        tolerances_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.tolerances_widget.setLayout(tolerances_layout)

        # Place tolerances_widget in a scroll area
        tolerances_scroll = QScrollArea(self)
        tolerances_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tolerances_scroll.setWidget(self.tolerances_widget)
        input_tabs.addTab(tolerances_scroll, "FR Tolerances")

        # This widget will hold a form to specify probability distribution inputs
        self.distros_widget = QWidget(self)
        distros_layout = QFormLayout()
        distros_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.distros_widget.setLayout(distros_layout)

        # Place distros_widget in a scroll area
        distros_scroll = QScrollArea(self)
        distros_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        distros_scroll.setWidget(self.distros_widget)
        input_tabs.addTab(distros_scroll, "Coupling Distributions")

        # This widget will hold a list of information content plots
        self.plots_widget = QWidget(self)
        plots_layout = QVBoxLayout()
        plots_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.plots_widget.setLayout(plots_layout)

        # Place the plots widget in a scroll area
        plots_scroll = QScrollArea(self)
        plots_scroll.setWidget(self.plots_widget)
        plots_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Put all this in a central widget
        container = QWidget()
        self.setWidget(container)

        # Put together the calculator layout
        calculator_layout.addWidget(input_tabs)
        calculator_layout.addWidget(plots_scroll)

        # Set the central widget's layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(calculator_layout, 1)
        main_layout.addWidget(self.info_content_label)
        container.setLayout(main_layout)

    # Update the GUI when the design state changes
    def _update(self, new_statement):
        verb, obj, ind_obj, reasoning = saddl.statement_to_key_terms(new_statement)

        # If a new FR is defined, add a ToleranceWidget and PlotWidget for it
        if verb == "DEFINE" and "FR" in obj:
            tolerance = ToleranceWidget(self, self.redo_calculations)
            plot = PlotWidget(self, obj)
            plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            self.tolerances[obj] = tolerance
            self.plots[obj] = plot

            self.tolerances_widget.layout().addRow(obj, tolerance)
            self.plots_widget.layout().addWidget(plot)

        # If an FR is deleted, get rid of its tolerance and plot widgets
        elif verb == "DELETE" and "FR" in obj:
            tolerance_to_remove = self.tolerances[obj]
            plot_to_remove = self.plots[obj]

            self.tolerances_widget.layout().removeRow(tolerance_to_remove)
            self.plots_widget.layout().removeWidget(plot_to_remove)

            # If this FR was coupled to anything, remove those distros
            distros_to_remove = []
            for string, distro_widget in self.distros.items():
                if obj in string:
                    self.distros_widget.layout().removeRow(distro_widget)
                    distros_to_remove.append(string)

            for string in distros_to_remove:
                del self.distros[string]

            del self.tolerances[obj]
            del self.plots[obj]

        # If a DP is deleted, remove any coupling distros it might've been associated with
        elif verb == "DELETE" and "DP" in obj:
            distros_to_remove = []
            for string, distro_widget in self.distros.items():
                if obj in string:
                    self.distros_widget.layout().removeRow(distro_widget)
                    distros_to_remove.append(string)

            for string in distros_to_remove:
                del self.distros[string]

        # If a coupling is defined, add a distro widget for it
        elif verb == "COUPLE" and ("FR" in obj and "DP" in ind_obj):
            string = obj + "↔" + ind_obj
            distro = DistroWidget(self, self.redo_calculations)

            self.distros[string] = distro
            self.distros_widget.layout().addRow(string, distro)

        # If a coupling is removed, delete the corresponding DistroWidget
        elif verb == "UNCOUPLE" and ("FR" in obj and "DP" in ind_obj):
            string = obj + "↔" + ind_obj
            distro_to_remove = self.distros[string]
            self.distros_widget.layout().removeRow(distro_to_remove)
            del self.distros[string]

        # Update calculations and plots
        self.redo_calculations()

    # Return an action that hides and shows the calculator window
    def get_toolbar_actions(self):
        toggle_view_action = self.toggleViewAction()
        toggle_view_action.setIcon(self.parent_window.TOADSIcons["InfoCalculator"])

        return [toggle_view_action]

    def _display_information_content(self, bits):
        self.info_content_label.setText("<b>Information Content: {bits:.3f} bits</b>".format(bits=bits))

    # Whenever an input changes, this is called to update everything
    def redo_calculations(self):
        total_information_content = 0

        for coupling, distro_widget in self.distros.items():
            FR_name, DP = coupling.split("↔")
            FR_tolerances = self.tolerances[FR_name]
            plot = self.plots[FR_name]

            # Retrieve inputs for calculations from input widgets
            mean = distro_widget.mean.value()
            stddev = distro_widget.variance.value()**0.5
            lower = FR_tolerances.minimum_value.value()
            upper = FR_tolerances.maximum_value.value()

            # Calculate the information content from the tolerances and coupling distro
            prob = norm.cdf(upper, mean, stddev) - norm.cdf(lower, mean, stddev)
            total_information_content += -np.emath.log2(prob)

            # Generate plot data
            x = np.linspace(mean - 3*stddev, mean + 3*stddev, 100)
            y = norm.pdf(x, mean, stddev)
            design_range = (x >= lower) & (x <= upper)

            # Update the plot
            plot.axes.cla()
            plot.axes.plot(x, y, 'b-')
            plot.axes.fill_between(x, 0, y, where=design_range, color='cyan', alpha=0.25, label="Design Range")
            plot.set_up_figure()
            plot.draw()

        self._display_information_content(total_information_content)
