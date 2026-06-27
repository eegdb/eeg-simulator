"""Noise and artifact configuration page."""

from PyQt6.QtWidgets import QFrame, QGroupBox, QLabel, QPushButton, QVBoxLayout

from ..themes import get_color
from ..widgets.navigation_view import NavigationPage
from ...utils import tr


def get_primary_btn_style():
    return f"""
        QPushButton {{
            background-color: {get_color('accent')};
            color: {get_color('text_inverse')};
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            min-height: 36px;
        }}
        QPushButton:hover {{
            background-color: {get_color('accent_hover')};
        }}
    """


class NoiseArtifactsPage(NavigationPage):
    """Sensor noise and physiological artifact setup."""

    def __init__(self, parent_simulator, parent=None):
        self.parent_simulator = parent_simulator
        self.active_noise_configs = []
        super().__init__(
            title=tr('nav_noise_artifacts'),
            subtitle=tr('nav_noise_artifacts_subtitle'),
            parent=parent,
        )
        self._setup_content()

    def _setup_content(self):
        layout = self.get_content_layout()

        self.noise_group = QGroupBox(tr('noise_settings'))
        noise_layout = QVBoxLayout(self.noise_group)

        self.manage_noise_btn = QPushButton(tr('btn_manage_noise'))
        self.manage_noise_btn.setStyleSheet(get_primary_btn_style())
        self.manage_noise_btn.clicked.connect(self._on_manage_noise)
        noise_layout.addWidget(self.manage_noise_btn)

        self.noise_frame = QFrame()
        self.noise_frame.setStyleSheet(self._stats_frame_style())
        noise_stats_layout = QVBoxLayout(self.noise_frame)
        noise_stats_layout.setContentsMargins(16, 12, 16, 12)

        self.noise_count_label = QLabel(tr('noise_count_zero'))
        self.noise_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        noise_stats_layout.addWidget(self.noise_count_label)

        self.noise_type_label = QLabel(tr('noise_type_stats', 0, 0, 0, 0))
        self.noise_type_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        noise_stats_layout.addWidget(self.noise_type_label)

        self.noise_amp_label = QLabel(tr('noise_total_amp', 0))
        self.noise_amp_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        noise_stats_layout.addWidget(self.noise_amp_label)

        noise_layout.addWidget(self.noise_frame)
        layout.addWidget(self.noise_group)
        layout.addStretch()
        self._update_noise_stats()

    @staticmethod
    def _stats_frame_style():
        return f"""
            background-color: rgba(100, 100, 100, 0.1);
            border-radius: 8px;
            border: 1px solid {get_color('border')};
        """

    def _on_manage_noise(self):
        from ..dialogs import NoiseManagerDialog

        dialog = NoiseManagerDialog(
            existing_configs=self.active_noise_configs,
            parent=self,
        )
        dialog.noise_config_changed.connect(self._on_noise_config_changed)
        dialog.exec()

    def _on_noise_config_changed(self, noise_configs):
        self.active_noise_configs = noise_configs
        self._update_noise_stats()
        if hasattr(self.parent_simulator, 'patch_ops'):
            self.parent_simulator.patch_ops.set_noise_configs(noise_configs)

    def _update_noise_stats(self):
        count = len(self.active_noise_configs)
        if count > 0:
            self.noise_count_label.setText(tr('noise_count_total', count))
            basic = sum(1 for c in self.active_noise_configs if c['type'] in ['white', 'pink', '1f', 'brown'])
            physio = sum(1 for c in self.active_noise_configs if c['type'] in ['eog', 'emg', 'ecg'])
            line = sum(1 for c in self.active_noise_configs if c['type'] == 'line')
            other = count - basic - physio - line
            self.noise_type_label.setText(tr('noise_type_stats', basic, physio, line, other))
            total_amp = sum(c['amplitude'] for c in self.active_noise_configs)
            self.noise_amp_label.setText(tr('noise_total_amp', total_amp))
        else:
            self.noise_count_label.setText(tr('noise_count_zero'))
            self.noise_type_label.setText(tr('noise_type_stats', 0, 0, 0, 0))
            self.noise_amp_label.setText(tr('noise_total_amp', 0))

    def update_theme(self):
        super().update_theme()
        self.noise_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {get_color('bg_card')};
                color: {get_color('text_main')};
                border: 1px solid {get_color('border')};
                margin-top: 10px;
                border-radius: 8px;
                padding-top: 10px;
                font-weight: bold;
            }}
        """)
        self.manage_noise_btn.setStyleSheet(get_primary_btn_style())
        self.noise_frame.setStyleSheet(self._stats_frame_style())
        self.noise_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        self.noise_type_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        self.noise_amp_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")

    def update_texts(self):
        self.set_title(tr('nav_noise_artifacts'))
        self.set_subtitle(tr('nav_noise_artifacts_subtitle'))
        self.noise_group.setTitle(tr('noise_settings'))
        self.manage_noise_btn.setText(tr('btn_manage_noise'))
        self._update_noise_stats()
