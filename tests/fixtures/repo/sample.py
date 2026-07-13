"""A tiny sample module for the Python AST parser."""

import os
from collections import OrderedDict


class Widget:
    """Represents a widget."""

    def render(self):
        return "widget"


def build_widget():
    return Widget()
