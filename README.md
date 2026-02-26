# TOADS (Totally Open Axiomatic Design Software)
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
