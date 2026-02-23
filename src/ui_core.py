import os
import re

from PyQt6.QtGui import QFont, QFontMetricsF, QIcon
from PyQt6.QtWidgets import QWidget

action_font = QFont("Courier", 9)
reasoning_font = QFont("Arial", 10)

action_font_metrics = QFontMetricsF(action_font)
reasoning_font_metrics = QFontMetricsF(reasoning_font)

# Variables are defined in comments like this: /* DEFINE --name AS value */
declaration_pattern = "/\\* DEFINE --\\w+ AS .+ \\*/"
declaration_expression = re.compile(declaration_pattern)

# Variables are used like this: --name
use_pattern = "--\\w+;"
use_expression = re.compile(use_pattern)

# Read in a stylesheet and convert sub in all variable values
def prepare_stylesheet(path_to_stylesheet):
    stylesheet = open(path_to_stylesheet).read()
    matches = declaration_expression.findall(stylesheet)

    # Process all the variable matches into name:value pairs
    variables = {}
    for match in matches:
        match = match[10:-3]
        name, value = match.split(" AS ")

        if not name.startswith("--"):
            raise(Exception("Stylesheet could not be parsed: Variable" + name + "must begin with '--' to prevent confusion"))
        else:
            variables[name] = value

    # Scan for any variables that haven't been declared properly
    matches = use_expression.findall(stylesheet)
    for match in matches:
        name = match[:-1]
        if name not in variables.keys():
            raise(Exception("Stylesheet could not be parsed: Undeclared variable " + name))

    # Apply the changes (do it twice so variables can nest a bit)
    for _ in range(2):
        for name, value in variables.items():
            stylesheet = stylesheet.replace(name, value)

    return stylesheet


# Load up a bunch of icons
def load_icons(directory="./resources/icons", resolution="128x128"):
    TOADSIcons = {}
    icon_files = filter(lambda x: x.endswith(resolution + ".png"), os.listdir(directory))
    for filename in icon_files:
        name = filename[:filename.index("-" + resolution + ".png")]
        words = name.split("-")
        proper_name = "".join([w.title() for w in words])
        TOADSIcons[proper_name] = QIcon(os.path.join(directory, filename))

    return TOADSIcons


# A blank widget subclass that allows styling the widgets used in DesignElement, etc. UI containers
class ContainerWidget(QWidget):
    def __init__(self):
        super().__init__()