# TOADS (Totally Open Axiomatic Design Software)
![An icon of a wise toad helping with engineering design](resources/TOADS%20Icon.png)

TOADS is an open source Axiomatic Design (AD) tool designed to facilitate parts of the design process.
At the moment, that means an interactive design multi-matrix and an in-development calculator for design
information content. TOADS was originally intended to act as a tool for teaching and interacting with
an AI agent so as to teach it some basic AD concepts. However, it was realized that it's actually
quite useful on its own and so it was developed into its own standalone system called TOADS.

## Getting Started with TOADS
TOADS is a local application using Python 3 and PyQt6. Installing and running TOADS is as simple as
cloning this repository, extracting it anywhere you like, and running `python3 src/main.py` to start
it up. There are example designs in the `examples` folder and more documentation to come.


## TOADS' Interface
TOADS is primarily built around a multi-matrix, a concatenation of AD's design matrices into one
end-to-end representation of a design. In the multi-matrix, Customer Needs (CNs) can be mapped to 
Functional Requirements (FRs) which map to Design Parameters (DPs) and onwards to Process Variables
(PVs). All this can make a multi-matrix pretty information-dense so, of course, there are options to
pan, zoom, and rotate your view around the matrix. As you work through an AD process, you can fill
out the multi-matrix to capture these elements of the design; it is possible to add/remove elements,
add/remove child elements, couple/uncouple pairs of elements, and mark PVs as acceptable or not.

This final operation activates one of TOADS' more useful features: when a PV is marked as acceptable
and requiring no further work, it turns green. TOADS will then use the couplings in the multi-matrix
to propagate this acceptance through coupled DPs, FRs, and CNs indicating that these elements are
satisfactory and do not require any further work. When the entire matrix and all its CNs are green,
your design is complete!


## Plugins to TOADS
At the moment, TOADS sports a rudimentary plugin system allowing the design analysis functionality to
be expanded beyond just the multi-matrix and history views. Functionally, these plugins operate as
dock widgets that receive the same SADDL story information that the multi-matrix does. For now, plugins
can only read and analyze this data but future updates will look into plugins that can modify the
design as well. Also worth noting is that, if you want to run without plugins and all their dependencies,
you can always launch TOADS with the `--no-plugins` flag.

Functionally, plugins are written in the `src/plugins` folder as extensions of the `TOADSPlugin` class.
These plugins are then imported and instantiated in `src/main.py` in the `Window.__init__` function and
linked to the core `InteractionManager` accordingly. Finally, this initialization will also add any
toolbar options the plugins may have to the main window.

### The Information Calculator
The information calculator plugin is designed to help users handle some of the more mathematical side of
Axiomatic Design methodologies. This calculator takes in target values and tolerances for each defined FR
as well as success probability distributions for each coupling. The calculator will then use these values
to work out the total information content of the design and display this at the bottom of the window. It
will also plot the intersections between the design ranges and system ranges for each FR.

#### Limitations
At the moment, the information calculator is very simple and so cannot fully perform the complexity
calculations for a large-scale design with intricate couplings. As it is, the calculator assumes a
fully uncoupled design with no alternatives to compare against. While this does limit its application
somewhat, there are a few tricks to get around this:
 - Some couplings may require multivariate distributions with conditional probabilities. Until these are properly implemented, they can be simulated by selecting fixed values for all but one variable and entering the now-univariate slice of the remaining variable into the calculator
 - When comparing design alternatives and their respective information values, it is recommended to duplicate the design file and compare both versions using multiple instances of TOADS

We understand that this is inconvenient so future work will directly target native implementations of these
features!
