"""Safe parsing of user-entered custom waveform numeric arrays."""

import ast
from typing import List, Optional


def parse_waveform_array(text: str) -> Optional[List[float]]:
    """Parse a plain Python list/tuple of numbers (no eval).

    Args:
        text: e.g. ``"[0.0, 0.5, 1.0, 0.5, 0.0]"``

    Returns:
        List of floats, or None if text is empty.

    Raises:
        ValueError: If format is invalid or contains non-numeric values.
    """
    text = text.strip()
    if not text:
        return None

    if 'np.' in text or 'array' in text.lower():
        raise ValueError('Use a plain list format, e.g. [0.0, 0.5, 1.0]')

    data = ast.literal_eval(text)
    if isinstance(data, (list, tuple)):
        return [float(x) for x in data]
    if isinstance(data, (int, float)):
        return [float(data)]
    raise ValueError('Custom waveform must be a list of numbers')
