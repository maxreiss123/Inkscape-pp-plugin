"""Shared library for the Inkscape presentation plugin.

Importing this package registers the plugin XML namespace with inkex (when
available) so all metadata round-trips cleanly through save/reload.
"""

from . import constants as constants  # noqa: F401

constants.register_ns()
