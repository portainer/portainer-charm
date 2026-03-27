#!/usr/bin/env python3
# Copyright 2021 Portainer.io
# See LICENSE file for licensing details.

"""A utility module that provides supporting functions."""


def clean_nones(value: dict) -> dict:
    """Recursively remove all None values from dictionaries and lists.

    Returns: the result as a new dictionary or list.
    """
    if isinstance(value, list):
        return [clean_nones(x) for x in value if x is not None]
    elif isinstance(value, dict):
        return {key: clean_nones(val) for key, val in value.items() if val is not None}
    else:
        return value
