"""MRI axial slice display helpers for overlaying source-space vertices on T1."""

import numpy as np


def prepare_axial_slice(t1_volume: np.ndarray, z: int) -> np.ndarray:
    """Return axial T1 slice in radiological view (A up, P down, R left, L right)."""
    return np.flipud(np.rot90(t1_volume[:, :, z]))


def vox_to_display_xy(vox_pos) -> tuple:
    """Map FreeSurfer voxel [x, y, z] to scatter coords on ``prepare_axial_slice`` output."""
    return float(vox_pos[0]), float(vox_pos[1])
