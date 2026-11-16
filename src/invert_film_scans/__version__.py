##############################################################################
#
# Name: __version__.py
#
# Function:
#       Provide the package version from pyproject.toml metadata
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

try:
    from importlib.metadata import version as _version

    __version__ = _version("invert-film-scans")
except Exception:
    # package not installed: use a development version
    __version__ = "0.0.0.dev0"
