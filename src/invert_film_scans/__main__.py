##############################################################################
#
# Name: __main__.py
#
# Function:
#       Entry point for the invert-film-scans command
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import sys


def main() -> int:
    """Create the App and run it; report user errors without a traceback."""
    from invert_film_scans.app import App

    try:
        return App().run()
    except KeyboardInterrupt:
        print("Exited due to keyboard interrupt", file=sys.stderr)
        return 130
    except App.Error as e:
        print(f"{App.PROGNAME}: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
