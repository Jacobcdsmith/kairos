"""Imports the sample module, to exercise cross-file import resolution."""

import sample


def use_it():
    return sample.build_widget()
