"""Model preparation page: source space, montage, forward model and BEM."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from ..themes import get_color
from ..widgets.head_layout import HeadLayoutWidget
from ..widgets.navigation_view import NavigationPage
from ...utils import get_logger, tr
from ...utils.mne_loader import resolve_standard_montage

logger = get_logger(__name__)


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


class SourceConfigPage(NavigationPage):
    """Prepare the physical model used by the simulation."""

    def __init__(self, parent_simulator, parent=None):
        self.parent_simulator = parent_simulator
        super().__init__(
            title=tr('nav_source_config'),
            subtitle=tr('nav_source_config_subtitle'),
            parent=parent,
        )

        self.loaded_src = None
        self.loaded_src_path = None
        self.src_labels = {'lh': {}, 'rh': {}}
        self.label_source_map = {'lh': {}, 'rh': {}}
        self.subject = None
        self._montage_key = 'standard_1020'
        self._montage = resolve_standard_montage(self._montage_key)

        self._setup_content()

    def _setup_content(self):
        layout = self.get_content_layout()

        self.mne_group = QGroupBox(tr('panel_source_space'))
        src_layout = QVBoxLayout(self.mne_group)

        src_select_layout = QHBoxLayout()
        src_select_layout.addWidget(QLabel(tr('label_select_src')))

        self.src_combo = QComboBox()
        self.src_combo.setToolTip(tr('tooltip_select_src'))
        self._populate_src_combo()
        src_select_layout.addWidget(self.src_combo, 1)
        src_layout.addLayout(src_select_layout)

        self.sample_btn = QPushButton(tr('btn_load_sample'))
        self.sample_btn.setStyleSheet(get_primary_btn_style())
        self.sample_btn.setToolTip(tr('tooltip_load_sample'))
        self.sample_btn.clicked.connect(self._on_load_sample_src)
        src_layout.addWidget(self.sample_btn)

        self.src_info_label = QLabel(tr('not_loaded'))
        self.src_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        self.src_info_label.setWordWrap(True)
        src_layout.addWidget(self.src_info_label)
        layout.addWidget(self.mne_group)

        self.montage_group = QGroupBox(tr('panel_electrode_montage'))
        montage_layout = QVBoxLayout(self.montage_group)

        montage_row = QHBoxLayout()
        self.montage_label = QLabel(tr('label_electrode_layout'))
        montage_row.addWidget(self.montage_label)
        self.montage_combo = QComboBox()
        self.montage_combo.setToolTip(tr('tooltip_select_montage'))
        self._populate_montage_combo()
        self.montage_combo.currentIndexChanged.connect(self._on_montage_combo_changed)
        montage_row.addWidget(self.montage_combo, 1)
        montage_layout.addLayout(montage_row)

        self.montage_hint_label = QLabel(tr('montage_select_hint'))
        self.montage_hint_label.setWordWrap(True)
        self.montage_hint_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        montage_layout.addWidget(self.montage_hint_label)
        layout.addWidget(self.montage_group)

        self.fwd_group = QGroupBox(tr('panel_forward_model'))
        fwd_layout = QVBoxLayout(self.fwd_group)

        self.fwd_workflow_frame = QFrame()
        self.fwd_workflow_frame.setStyleSheet(self._hint_frame_style())
        fwd_workflow_inner = QVBoxLayout(self.fwd_workflow_frame)
        fwd_workflow_inner.setContentsMargins(12, 10, 12, 10)
        self.fwd_workflow_label = QLabel(tr('fwd_workflow_hint'))
        self.fwd_workflow_label.setWordWrap(True)
        self.fwd_workflow_label.setStyleSheet(f"color: {get_color('blue')}; font-size: 12px;")
        fwd_workflow_inner.addWidget(self.fwd_workflow_label)
        fwd_layout.addWidget(self.fwd_workflow_frame)

        self.compute_fwd_btn = QPushButton(tr('btn_compute_forward'))
        self.compute_fwd_btn.setStyleSheet(get_primary_btn_style())
        self.compute_fwd_btn.setToolTip(tr('tooltip_compute_forward'))
        self.compute_fwd_btn.clicked.connect(self._on_compute_forward)
        fwd_layout.addWidget(self.compute_fwd_btn)

        self.fwd_info_label = QLabel(tr('fwd_not_loaded'))
        self.fwd_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        self.fwd_info_label.setWordWrap(True)
        fwd_layout.addWidget(self.fwd_info_label)
        layout.addWidget(self.fwd_group)

        self.bem_group = QGroupBox(tr('bem_conductivity'))
        bem_layout = QVBoxLayout(self.bem_group)

        brain_layout = QHBoxLayout()
        self.brain_cond_label = QLabel(f"{tr('bem_conductivity_brain')} (S/m):")
        brain_layout.addWidget(self.brain_cond_label)
        self.brain_cond_spin = QDoubleSpinBox()
        self.brain_cond_spin.setRange(0.1, 2.0)
        self.brain_cond_spin.setDecimals(3)
        self.brain_cond_spin.setValue(0.3)
        brain_layout.addWidget(self.brain_cond_spin)
        bem_layout.addLayout(brain_layout)

        skull_layout = QHBoxLayout()
        self.skull_cond_label = QLabel(f"{tr('bem_conductivity_skull')} (S/m):")
        skull_layout.addWidget(self.skull_cond_label)
        self.skull_cond_spin = QDoubleSpinBox()
        self.skull_cond_spin.setRange(0.001, 0.1)
        self.skull_cond_spin.setDecimals(4)
        self.skull_cond_spin.setValue(0.00615)
        skull_layout.addWidget(self.skull_cond_spin)
        bem_layout.addLayout(skull_layout)

        scalp_layout = QHBoxLayout()
        self.scalp_cond_label = QLabel(f"{tr('bem_conductivity_scalp')} (S/m):")
        scalp_layout.addWidget(self.scalp_cond_label)
        self.scalp_cond_spin = QDoubleSpinBox()
        self.scalp_cond_spin.setRange(0.1, 2.0)
        self.scalp_cond_spin.setDecimals(3)
        self.scalp_cond_spin.setValue(0.3)
        scalp_layout.addWidget(self.scalp_cond_spin)
        bem_layout.addLayout(scalp_layout)

        self.make_bem_btn = QPushButton(tr('bem_make_model'))
        self.make_bem_btn.setStyleSheet(get_primary_btn_style())
        self.make_bem_btn.clicked.connect(self._on_make_bem_model)
        bem_layout.addWidget(self.make_bem_btn)
        layout.addWidget(self.bem_group)
        layout.addStretch()

    @staticmethod
    def _hint_frame_style():
        return f"""
            background-color: {get_color('bg_input')};
            border-radius: 8px;
            border: 1px solid {get_color('border')};
        """

    def _populate_src_combo(self):
        src_options = [
            ('sample-oct-6-src.fif', 'Oct-6'),
            ('sample-all-src.fif', 'All'),
            ('sample-oct-6-orig-src.fif', 'Oct-6 Orig'),
            ('volume-7mm-src.fif', 'Volume 7mm'),
            ('sample-fsaverage-ico-5-src.fif', 'FSAverage Ico-5'),
        ]
        for filename, display_name in src_options:
            self.src_combo.addItem(display_name, filename)

    def _populate_montage_combo(self):
        current = self._montage_key
        self.montage_combo.blockSignals(True)
        self.montage_combo.clear()
        for key, name in HeadLayoutWidget.get_available_montage_options().items():
            self.montage_combo.addItem(name, key)
        idx = self.montage_combo.findData(current)
        if idx >= 0:
            self.montage_combo.setCurrentIndex(idx)
        self.montage_combo.blockSignals(False)

    def _on_montage_combo_changed(self, _index: int):
        key = self.montage_combo.currentData()
        if key and key != self._montage_key:
            self.set_montage_key(key)

    def get_montage_key(self) -> str | None:
        return self._montage_key

    def get_current_montage(self):
        return self._montage

    def set_montage_key(self, montage_key: str, sync_combo: bool = True):
        if not montage_key:
            return
        try:
            self._montage = resolve_standard_montage(montage_key)
            self._montage_key = montage_key
        except Exception as e:
            logger.warning(f"Failed to load montage {montage_key}: {e}")
            return
        if sync_combo:
            self.montage_combo.blockSignals(True)
            idx = self.montage_combo.findData(montage_key)
            if idx >= 0:
                self.montage_combo.setCurrentIndex(idx)
            self.montage_combo.blockSignals(False)
        self.sync_montage_to_electrode_page()

    def sync_montage_to_electrode_page(self):
        sim = self.parent_simulator
        if hasattr(sim, 'electrode_channels_page'):
            ep = sim.electrode_channels_page
            if hasattr(ep, 'head_selector'):
                ep.head_selector.apply_montage_key(self._montage_key)
            ep._update_channel_list()
        if getattr(sim, 'mne_fwd', None) is not None and hasattr(sim, 'mne'):
            sim.mne.refresh_channel_mapping()
        self.update_forward_status()
        if hasattr(sim, 'ui'):
            sim.ui._sync_heatmap_montage()

    def _on_load_sample_src(self):
        import mne

        try:
            data_path = mne.datasets.sample.data_path()
            subjects_dir = os.path.join(data_path, 'subjects')
            self.subject = 'sample'

            src_filename = self.src_combo.currentData()
            src_path = os.path.join(subjects_dir, self.subject, 'bem', src_filename)
            logger.info(f"Loading source space: {src_filename}")

            if not os.path.exists(src_path):
                QMessageBox.warning(self, tr('error'), tr('msg_file_not_exist', src_path))
                return

            self.loaded_src = mne.read_source_spaces(src_path)
            self.loaded_src_path = src_path
            total_vertices = sum(s['nuse'] for s in self.loaded_src)
            self._load_labels(subjects_dir, self.subject)
            self.parent_simulator.subjects_dir = subjects_dir
            self.parent_simulator.mne.init_mne_coupling_engine(self.loaded_src, self.src_labels)

            self.src_info_label.setText(self._get_src_info_text(self.loaded_src))
            self.src_info_label.setStyleSheet(f"color: {get_color('accent')}; font-size: 12px;")

            if src_filename == 'sample-all-src.fif':
                QMessageBox.warning(self, tr('warning'), tr('msg_all_src_no_fwd', src_filename))

            QMessageBox.information(self, tr('success'), tr('msg_load_success', 'Sample', total_vertices))
        except Exception as e:
            logger.error(f"Source space load failed: {e}", exc_info=True)
            QMessageBox.critical(self, tr('error'), tr('msg_load_failed', str(e)))

    def _on_compute_forward(self):
        if self.loaded_src is None:
            QMessageBox.warning(self, tr('warning'), tr('msg_no_src_space'))
            return

        montage_key = self.get_montage_key()
        if not montage_key:
            QMessageBox.warning(self, tr('warning'), tr('msg_select_montage_first'))
            return

        progress = QProgressDialog(tr('msg_computing_forward'), None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            save_dir = self.parent_simulator.current_project_path
            fwd_path = self.parent_simulator.mne.compute_forward_from_montage(save_dir)
            import mne

            fwd = self.parent_simulator.mne_fwd
            n_eeg = len(mne.pick_types(fwd['info'], meg=False, eeg=True, exclude=[]))
            QMessageBox.information(
                self,
                tr('success'),
                tr('msg_fwd_computed', os.path.basename(fwd_path), montage_key, n_eeg),
            )
        except Exception as e:
            logger.error(f"Forward model computation failed: {e}", exc_info=True)
            QMessageBox.critical(self, tr('error'), tr('msg_fwd_compute_failed', str(e)))
        finally:
            progress.close()

    def update_forward_status(self):
        text, color = self._forward_status_text()
        self.fwd_info_label.setText(text)
        self.fwd_info_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _forward_status_text(self) -> tuple[str, str]:
        import mne

        sim = self.parent_simulator
        path = getattr(sim, 'mne_fwd_path', None)
        fwd = getattr(sim, 'mne_fwd', None)
        if fwd is None or not path:
            return tr('fwd_not_loaded'), get_color('text_muted')

        n_eeg = len(mne.pick_types(fwd['info'], meg=False, eeg=True, exclude=[]))
        lines = [tr('fwd_loaded_info', os.path.basename(path), n_eeg)]
        montage_key = self.get_montage_key() or ''
        if montage_key:
            lines.append(tr('fwd_status_montage', montage_key))
        return '\n'.join(lines), get_color('accent')

    def _load_labels(self, subjects_dir, subject):
        from ...utils.mne_loader import build_label_source_map

        labels_dir = os.path.join(subjects_dir, subject, 'label')
        if not os.path.exists(labels_dir):
            logger.warning(f"Label directory does not exist: {labels_dir}")
            return

        self.src_labels, self.label_source_map = build_label_source_map(
            self.loaded_src, subjects_dir, subject
        )

        lh_labels = list(self.label_source_map.get('lh', {}).keys())
        rh_labels = list(self.label_source_map.get('rh', {}).keys())
        a2009s_count = sum(1 for name in lh_labels + rh_labels if name.lower().startswith('a2009s.'))
        aparc_count = len(lh_labels) + len(rh_labels) - a2009s_count
        logger.info(
            f"Labels loaded: LH={len(lh_labels)}, RH={len(rh_labels)}, "
            f"aparc={aparc_count}, a2009s={a2009s_count}"
        )

    def _get_src_info_text(self, src):
        total = sum(s['nuse'] for s in src)
        lines = [tr('src_total_vertices', total)]
        for i, s in enumerate(src):
            if s['type'] == 'surf':
                hemi = tr('label_left') if i == 0 else tr('label_right')
                lines.append(f"  {hemi}: {s['nuse']} {tr('label_vertex')}")
        return "\n".join(lines)

    def _on_make_bem_model(self):
        import mne

        if not self.subject:
            QMessageBox.warning(self, tr('warning'), tr('msg_no_src_space'))
            return

        try:
            conductivity = self.get_bem_conductivity()
            bem_model = mne.make_bem_model(
                subject=self.subject,
                ico=4,
                conductivity=conductivity,
                subjects_dir=self.parent_simulator.subjects_dir,
            )
            self.parent_simulator.bem_model = bem_model
            self.parent_simulator.bem_conductivity = conductivity
            QMessageBox.information(self, tr('success'), tr('bem_model_created'))
        except Exception as e:
            QMessageBox.critical(self, tr('error'), tr('msg_bem_failed', str(e)))

    def get_bem_conductivity(self):
        return (
            self.brain_cond_spin.value(),
            self.skull_cond_spin.value(),
            self.scalp_cond_spin.value(),
        )

    def apply_bem_conductivity(self, conductivity):
        if not conductivity or len(conductivity) < 3:
            return
        self.brain_cond_spin.setValue(float(conductivity[0]))
        self.skull_cond_spin.setValue(float(conductivity[1]))
        self.scalp_cond_spin.setValue(float(conductivity[2]))

    def update_theme(self):
        super().update_theme()
        for group in [self.mne_group, self.montage_group, self.fwd_group, self.bem_group]:
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

        for btn in [self.sample_btn, self.compute_fwd_btn, self.make_bem_btn]:
            btn.setStyleSheet(get_primary_btn_style())

        if self.loaded_src:
            self.src_info_label.setStyleSheet(f"color: {get_color('accent')}; font-size: 12px;")
        else:
            self.src_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        self.fwd_workflow_frame.setStyleSheet(self._hint_frame_style())
        self.fwd_workflow_label.setStyleSheet(f"color: {get_color('blue')}; font-size: 12px;")
        self.update_forward_status()

    def update_texts(self):
        self.set_title(tr('nav_source_config'))
        self.set_subtitle(tr('nav_source_config_subtitle'))

        self.mne_group.setTitle(tr('panel_source_space'))
        self.montage_group.setTitle(tr('panel_electrode_montage'))
        self.fwd_group.setTitle(tr('panel_forward_model'))
        self.bem_group.setTitle(tr('bem_conductivity'))

        self.montage_label.setText(tr('label_electrode_layout'))
        self.montage_combo.setToolTip(tr('tooltip_select_montage'))
        self.montage_hint_label.setText(tr('montage_select_hint'))
        self._populate_montage_combo()

        self.brain_cond_label.setText(f"{tr('bem_conductivity_brain')} (S/m):")
        self.skull_cond_label.setText(f"{tr('bem_conductivity_skull')} (S/m):")
        self.scalp_cond_label.setText(f"{tr('bem_conductivity_scalp')} (S/m):")

        self.sample_btn.setText(tr('btn_load_sample'))
        self.sample_btn.setToolTip(tr('tooltip_load_sample'))
        self.fwd_workflow_label.setText(tr('fwd_workflow_hint'))
        self.compute_fwd_btn.setText(tr('btn_compute_forward'))
        self.compute_fwd_btn.setToolTip(tr('tooltip_compute_forward'))
        self.make_bem_btn.setText(tr('bem_make_model'))

        if self.loaded_src:
            self.src_info_label.setText(self._get_src_info_text(self.loaded_src))
        else:
            self.src_info_label.setText(tr('not_loaded'))
        self.update_forward_status()
