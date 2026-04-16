from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal


class ControlsPanel(QWidget):
    start_requested = Signal()
    pause_requested = Signal()
    step_requested = Signal()
    reset_epoch_requested = Signal()
    reset_sim_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.btn_start = QPushButton("▶ Start")
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_step = QPushButton("⏭ Step")
        self.btn_reset_epoch = QPushButton("↺ Reset Epoch")
        self.btn_reset_sim = QPushButton("⟳ Reset Sim")

        self.btn_start.clicked.connect(self.start_requested)
        self.btn_pause.clicked.connect(self.pause_requested)
        self.btn_step.clicked.connect(self.step_requested)
        self.btn_reset_epoch.clicked.connect(self.reset_epoch_requested)
        self.btn_reset_sim.clicked.connect(self.reset_sim_requested)

        for btn in [
            self.btn_start,
            self.btn_pause,
            self.btn_step,
            self.btn_reset_epoch,
            self.btn_reset_sim,
        ]:
            layout.addWidget(btn)

        layout.addStretch()
