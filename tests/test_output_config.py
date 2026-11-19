from eeg_simulator.core.output_config import OutputConfig, create_output_sink
from eeg_simulator.core.output_sink import SimulationOutputSink
from eeg_simulator.core.biosignal_sink import BioSignalOutputSink


def test_output_settings_are_snapshotted():
    source = {'format': 'fif', 'sampling_rate': 256, 'duration': 30,
              'output_dir': '/tmp', 'filename': 'recording'}
    page = type('Page', (), {'get_output_config': lambda self: source})()
    config = OutputConfig.from_page(page)
    source['duration'] = 90
    assert config.duration == 30
    sink = create_output_sink(config, ['C3'])
    assert isinstance(sink, SimulationOutputSink)
    assert sink.channel_names == ['C3']


def test_biosignal_output_factory():
    config = OutputConfig(format='biosignal', sampling_rate=512, duration=0,
                          biosignal_mapping='C4,C3')
    sink = create_output_sink(config, ['C3', 'C4'])
    assert isinstance(sink, BioSignalOutputSink)
    assert sink.mapping == ['C4', 'C3']
