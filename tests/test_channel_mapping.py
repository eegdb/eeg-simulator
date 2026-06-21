"""build_eeg_channel_mapping 单元测试"""

import mne
import pytest

from eeg_simulator.utils.mne_loader import build_eeg_channel_mapping


@pytest.fixture(scope="module")
def sample_eeg_fwd():
    data_path = mne.datasets.sample.data_path()
    path = f"{data_path}/MEG/sample/sample_audvis-eeg-oct-6-fwd.fif"
    return mne.read_forward_solution(path)


def test_standard_1020_maps_fp1(sample_eeg_fwd):
    montage = mne.channels.make_standard_montage('standard_1020')
    mapping = build_eeg_channel_mapping(sample_eeg_fwd, montage)
    assert mapping.get('Fp1', '').startswith('EEG ')
    assert mapping.get('Cz', '').startswith('EEG ')


def test_biosemi64_uses_montage_positions(sample_eeg_fwd):
    montage = mne.channels.make_standard_montage('biosemi64')
    mapping = build_eeg_channel_mapping(sample_eeg_fwd, montage)
    assert 'Fp1' in mapping
    assert mapping['Fp1'].startswith('EEG ')


def test_exact_name_match(sample_eeg_fwd):
    """前向模型通道名与 montage 完全一致时直接映射"""
    montage = mne.channels.make_standard_montage('standard_1020')
    mapping = build_eeg_channel_mapping(sample_eeg_fwd, montage)
    for ui_name, fwd_name in mapping.items():
        if ui_name in sample_eeg_fwd['info']['ch_names']:
            assert fwd_name == ui_name
