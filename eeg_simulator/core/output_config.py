"""Snapshot of output settings used during one simulation run."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OutputConfig:
    format: str
    sampling_rate: float
    duration: float
    output_dir: str | None = None
    filename: str = ''
    device_name: str = 'EEGSimulator'
    biosignal_port: str = ''
    biosignal_mapping: str = ''
    biosignal_range: str = '±8.333 mV'

    @classmethod
    def from_page(cls, page):
        data = page.get_output_config()
        return cls(**{name: data[name] for name in cls.__dataclass_fields__ if name in data})


def create_output_sink(config: OutputConfig, channel_names, on_error=None):
    if config.format == 'biosignal':
        from .biosignal_sink import BioSignalOutputSink
        return BioSignalOutputSink(
            channel_names, config.sampling_rate, port=config.biosignal_port,
            mapping=config.biosignal_mapping, output_range=config.biosignal_range,
            on_error=on_error,
        )
    from .output_sink import SimulationOutputSink
    return SimulationOutputSink(
        fmt=config.format, channel_names=channel_names,
        sampling_rate=config.sampling_rate, output_dir=config.output_dir,
        filename=config.filename, device_name=config.device_name,
    )
