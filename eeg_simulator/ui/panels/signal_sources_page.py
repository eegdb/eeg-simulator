"""Signal source and coupling configuration page."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QMessageBox,
)

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


class SignalSourcesPage(NavigationPage):
    """Patch waveform and coupling setup."""

    def __init__(self, parent_simulator, parent=None):
        self.parent_simulator = parent_simulator
        super().__init__(
            title=tr('nav_signal_sources'),
            subtitle=tr('nav_signal_sources_subtitle'),
            parent=parent,
        )
        self._setup_content()

    def _setup_content(self):
        layout = self.get_content_layout()

        self.patch_group = QGroupBox(tr('panel_patch'))
        patch_layout = QVBoxLayout(self.patch_group)

        self.patch_btn = QPushButton(tr('btn_manage_patches'))
        self.patch_btn.setStyleSheet(get_primary_btn_style())
        self.patch_btn.clicked.connect(self._on_manage_patches)
        patch_layout.addWidget(self.patch_btn)

        self.patch_frame = QFrame()
        self.patch_frame.setStyleSheet(self._stats_frame_style('patch'))
        patch_stats_layout = QVBoxLayout(self.patch_frame)
        patch_stats_layout.setContentsMargins(16, 12, 16, 12)

        self.patch_count_label = QLabel(tr('label_patch_count', 0))
        self.patch_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        patch_stats_layout.addWidget(self.patch_count_label)

        self.patch_coverage_label = QLabel(tr('label_patch_coverage', 0, 0))
        self.patch_coverage_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        patch_stats_layout.addWidget(self.patch_coverage_label)

        patch_layout.addWidget(self.patch_frame)
        layout.addWidget(self.patch_group)

        self.coupling_group = QGroupBox(tr('panel_coupling'))
        coupling_layout = QVBoxLayout(self.coupling_group)

        self.mne_coupling_check = QCheckBox(tr('label_use_mne_coupling'))
        self.mne_coupling_check.setChecked(True)
        self.mne_coupling_check.stateChanged.connect(self._on_mne_coupling_toggled)
        coupling_layout.addWidget(self.mne_coupling_check)

        knn_layout = QHBoxLayout()
        self.knn_label = QLabel(tr('label_knn_k'))
        knn_layout.addWidget(self.knn_label)
        self.knn_spin = QSpinBox()
        self.knn_spin.setRange(1, 10)
        self.knn_spin.setValue(3)
        knn_layout.addWidget(self.knn_spin)
        coupling_layout.addLayout(knn_layout)

        decay_layout = QHBoxLayout()
        self.decay_label = QLabel(tr('label_decay_length'))
        decay_layout.addWidget(self.decay_label)
        self.decay_spin = QDoubleSpinBox()
        self.decay_spin.setRange(0.001, 0.1)
        self.decay_spin.setDecimals(3)
        self.decay_spin.setValue(0.02)
        self.decay_spin.setSuffix(' m')
        decay_layout.addWidget(self.decay_spin)
        coupling_layout.addLayout(decay_layout)

        self.manage_coupling_btn = QPushButton(tr('btn_manage_coupling'))
        self.manage_coupling_btn.setStyleSheet(get_primary_btn_style())
        self.manage_coupling_btn.clicked.connect(self._on_manage_coupling)
        coupling_layout.addWidget(self.manage_coupling_btn)

        self.coupling_frame = QFrame()
        self.coupling_frame.setStyleSheet(self._stats_frame_style())
        coupling_stats_layout = QVBoxLayout(self.coupling_frame)
        coupling_stats_layout.setContentsMargins(16, 12, 16, 12)

        self.coupling_count_label = QLabel(tr('coupling_count_zero'))
        self.coupling_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        coupling_stats_layout.addWidget(self.coupling_count_label)

        self.coupling_type_label = QLabel(tr('coupling_type_stats', 0, 0, 0))
        self.coupling_type_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        coupling_stats_layout.addWidget(self.coupling_type_label)

        coupling_layout.addWidget(self.coupling_frame)
        layout.addWidget(self.coupling_group)
        layout.addStretch()

        self.knn_spin.valueChanged.connect(self._on_mne_coupling_params_changed)
        self.decay_spin.valueChanged.connect(self._on_mne_coupling_params_changed)
        self._update_patch_stats()
        self._update_coupling_stats()

    @staticmethod
    def _stats_frame_style(kind='default'):
        bg = 'rgba(16, 185, 129, 0.1)' if kind == 'patch' else 'rgba(100, 100, 100, 0.1)'
        return f"""
            background-color: {bg};
            border-radius: 8px;
            border: 1px solid {get_color('border')};
        """

    def _on_manage_patches(self):
        from ..dialogs import PatchManagerDialog

        source_page = self.parent_simulator.source_page
        if source_page.loaded_src is None:
            QMessageBox.warning(self, tr('warning'), tr('msg_no_src_space'))
            return

        dialog = PatchManagerDialog(self.parent_simulator, parent=self)
        dialog.patch_created.connect(self._update_patch_stats)
        dialog.patch_modified.connect(self._update_patch_stats)
        dialog.patch_deleted.connect(self._update_patch_stats)
        dialog.exec()

    def _on_mne_coupling_toggled(self, state):
        self.parent_simulator._use_mne_coupling = (state == 2)

    def _on_mne_coupling_params_changed(self):
        if hasattr(self.parent_simulator, 'signal'):
            self.parent_simulator.signal.invalidate_mne_coupling_cache()

    def get_mne_coupling_settings(self) -> dict:
        return {
            'use_mne': self.mne_coupling_check.isChecked(),
            'knn_k': self.knn_spin.value(),
            'decay_length': self.decay_spin.value(),
        }

    def apply_mne_coupling_settings(self, settings: dict):
        if not settings:
            return
        if 'use_mne' in settings:
            self.mne_coupling_check.setChecked(bool(settings['use_mne']))
            self.parent_simulator._use_mne_coupling = bool(settings['use_mne'])
        if 'knn_k' in settings:
            self.knn_spin.setValue(int(settings['knn_k']))
        if 'decay_length' in settings:
            self.decay_spin.setValue(float(settings['decay_length']))
        if hasattr(self.parent_simulator, 'signal'):
            self.parent_simulator.signal.invalidate_mne_coupling_cache()

    def _on_manage_coupling(self):
        from ..dialogs import CouplingManagerDialog

        dialog = CouplingManagerDialog(self.parent_simulator, parent=self)
        dialog.coupling_changed.connect(self._update_coupling_stats)
        dialog.exec()

    def _update_coupling_stats(self):
        couplings = self.parent_simulator.patch_ops.coupling_models
        count = len(couplings)
        if count > 0:
            self.coupling_count_label.setText(tr('coupling_count_total', count))
            linear = sum(1 for c in couplings.values() if c.type == 'linear')
            nonlinear = sum(1 for c in couplings.values() if c.type == 'nonlinear')
            delayed = sum(1 for c in couplings.values() if c.type == 'delayed')
            self.coupling_type_label.setText(tr('coupling_type_stats', linear, nonlinear, delayed))
        else:
            self.coupling_count_label.setText(tr('coupling_count_zero'))
            self.coupling_type_label.setText(tr('coupling_type_stats', 0, 0, 0))

    def _update_patch_stats(self, *args):
        patches = self.parent_simulator.patches
        patch_count = len(patches)
        total_dipoles = sum(p.get_dipole_count() for p in patches.values())
        self.patch_count_label.setText(tr('label_patch_count', patch_count))
        self.patch_coverage_label.setText(tr('label_patch_coverage', total_dipoles, total_dipoles))

    def update_theme(self):
        super().update_theme()
        for group in [self.patch_group, self.coupling_group]:
            group.setStyleSheet(f"""
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
        for btn in [self.patch_btn, self.manage_coupling_btn]:
            btn.setStyleSheet(get_primary_btn_style())
        self.patch_frame.setStyleSheet(self._stats_frame_style('patch'))
        self.coupling_frame.setStyleSheet(self._stats_frame_style())
        self.patch_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        self.patch_coverage_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        self.coupling_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        self.coupling_type_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")

    def update_texts(self):
        self.set_title(tr('nav_signal_sources'))
        self.set_subtitle(tr('nav_signal_sources_subtitle'))
        self.patch_group.setTitle(tr('panel_patch'))
        self.coupling_group.setTitle(tr('panel_coupling'))
        self.patch_btn.setText(tr('btn_manage_patches'))
        self.mne_coupling_check.setText(tr('label_use_mne_coupling'))
        self.knn_label.setText(tr('label_knn_k'))
        self.decay_label.setText(tr('label_decay_length'))
        self.manage_coupling_btn.setText(tr('btn_manage_coupling'))
        self._update_patch_stats()
        self._update_coupling_stats()
