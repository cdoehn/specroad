"""Project test bootstrap; not imported by the SpecRoad Core."""

import sys

# Tests inspect real filesystem effects; bytecode is not part of the fixtures.
sys.dont_write_bytecode = True
