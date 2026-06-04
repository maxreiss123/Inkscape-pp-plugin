"""Build a temporary playable SVG and open it in the default browser."""

import os
import tempfile
import webbrowser

from . import jsexport


def build_temp(pres, transition="fade", loop=False, start=0):
    fd, path = tempfile.mkstemp(prefix="pp-preview-", suffix=".svg")
    os.close(fd)
    jsexport.write(pres, path, transition=transition, loop=loop, start=start)
    return path


def open_in_browser(path):
    webbrowser.open("file://" + os.path.abspath(path))
