import datetime
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QTextEdit, QPushButton, QApplication,
)
from PySide6.QtCore import Qt, QTimer

from app.enums import Action, CreatureMode
from app.models import Creature

ACTION_NAMES: dict[int, str] = {
    Action.UP: "UP",
    Action.DOWN: "DOWN",
    Action.LEFT: "LEFT",
    Action.RIGHT: "RIGHT",
    Action.IDLE: "IDLE",
}

MODE_NAMES: dict[int, str] = {
    CreatureMode.FOOD_DIRECT: "FOOD_DIRECT",
    CreatureMode.MEMORY_REPLAY: "MEMORY_REPLAY",
    CreatureMode.EXPLORE: "EXPLORE",
}

TILE_SHORT: dict[int, str] = {0: "E", 1: "W", 2: "F", 3: "C"}


def _sv_str(sv: list[int]) -> str:
    return "[" + ",".join(TILE_SHORT.get(v, "?") for v in sv) + "]" if sv else "-"


class DetailsWindow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Creature Details")
        self.setMinimumSize(360, 520)
        self.creature: Creature | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.title_label = QLabel("No creature selected")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.title_label)

        # State
        state_group = QGroupBox("State")
        state_layout = QVBoxLayout(state_group)
        self.pos_label = QLabel("Position: -")
        self.mode_label = QLabel("Mode: -")
        self.action_label = QLabel("Current action: -")
        self.last_action_label = QLabel("Last action: -")
        self.score_label = QLabel("Food score: 0")
        self.match_score_label = QLabel("Last match score: -")
        self.replay_fail_label = QLabel("Replay fail: -")
        for lbl in [
            self.pos_label, self.mode_label, self.action_label,
            self.last_action_label, self.score_label,
            self.match_score_label, self.replay_fail_label,
        ]:
            state_layout.addWidget(lbl)
        layout.addWidget(state_group)

        # Sense vector
        sense_group = QGroupBox("Sense Vector")
        sense_layout = QVBoxLayout(sense_group)
        self.sense_label = QLabel("-")
        self.sense_label.setWordWrap(True)
        sense_layout.addWidget(self.sense_label)
        layout.addWidget(sense_group)

        # Recent steps
        steps_group = QGroupBox("Recent Steps (last 4)")
        steps_layout = QVBoxLayout(steps_group)
        self.steps_text = QTextEdit()
        self.steps_text.setReadOnly(True)
        self.steps_text.setFixedHeight(90)
        steps_layout.addWidget(self.steps_text)
        layout.addWidget(steps_group)

        # Active memory
        active_group = QGroupBox("Active Memory")
        active_layout = QVBoxLayout(active_group)
        self.active_mem_label = QLabel("-")
        self.active_mem_label.setWordWrap(True)
        active_layout.addWidget(self.active_mem_label)
        layout.addWidget(active_group)

        # Stored memories
        mem_group = QGroupBox("Stored Memories")
        mem_layout = QVBoxLayout(mem_group)
        self.memories_text = QTextEdit()
        self.memories_text.setReadOnly(True)
        mem_layout.addWidget(self.memories_text)
        layout.addWidget(mem_group)

        # Copy to clipboard button
        self.copy_btn = QPushButton("Copy Creature to Clipboard")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        layout.addWidget(self.copy_btn)

        layout.addStretch()

    def update_creature(self, creature: Creature | None) -> None:
        self.creature = creature
        if creature is None:
            self.title_label.setText("No creature selected")
            self.pos_label.setText("Position: -")
            self.mode_label.setText("Mode: -")
            self.action_label.setText("Current action: -")
            self.last_action_label.setText("Last action: -")
            self.score_label.setText("Food score: 0")
            self.match_score_label.setText("Last match score: -")
            self.replay_fail_label.setText("Replay fail: -")
            self.sense_label.setText("-")
            self.steps_text.setPlainText("")
            self.active_mem_label.setText("-")
            self.memories_text.setPlainText("")
            return

        self.title_label.setText(f"Creature #{creature.id}")
        self.pos_label.setText(f"Position: ({creature.position.row}, {creature.position.col})")
        self.mode_label.setText(f"Mode: {MODE_NAMES.get(creature.mode, str(creature.mode))}")
        self.action_label.setText(
            f"Current action: {ACTION_NAMES.get(creature.current_action, '-')}"
        )
        self.last_action_label.setText(
            f"Last action: {ACTION_NAMES.get(creature.last_action, '-')}"
        )
        self.score_label.setText(f"Food score: {creature.food_score}")
        self.match_score_label.setText(f"Last match score: {creature.last_match_score:.3f}")
        self.replay_fail_label.setText(
            f"Replay fail: {creature.last_replay_fail_reason or '-'}"
        )

        self.sense_label.setText(_sv_str(creature.current_sense_vector))

        # Recent steps
        lines = []
        for i, step in enumerate(creature.recent_steps):
            pos, sv_i, act = step[0], step[1], step[2]
            mem_idx = step[3] if len(step) > 3 else None
            mem_tag = f" mem={mem_idx}" if mem_idx is not None else ""
            lines.append(
                f"  {i}: pos=({pos.row},{pos.col}) "
                f"sv={_sv_str(sv_i)} "
                f"act={ACTION_NAMES.get(act, '?')}"
                f"{mem_tag}"
            )
        self.steps_text.setPlainText("\n".join(lines) if lines else "(none)")

        # Active memory
        if creature.active_memory_idx is not None and creature.active_step_idx is not None:
            mem = creature.memories[creature.active_memory_idx]
            step = mem.steps[creature.active_step_idx]
            self.active_mem_label.setText(
                f"Memory {creature.active_memory_idx}, "
                f"step {creature.active_step_idx}\n"
                f"sv={_sv_str(step.sense_vector)} "
                f"act={ACTION_NAMES.get(step.action, '?')}"
            )
        else:
            self.active_mem_label.setText("-")

        # Stored memories
        mem_lines = []
        for m_idx, mem_seq in enumerate(creature.memories):
            mem_lines.append(f"Memory {m_idx} ({len(mem_seq.steps)} steps):")
            for s_idx, step in enumerate(mem_seq.steps):
                mem_lines.append(
                    f"  [{s_idx}] sv={_sv_str(step.sense_vector)} "
                    f"act={ACTION_NAMES.get(step.action, '?')}"
                )
        self.memories_text.setPlainText(
            "\n".join(mem_lines) if mem_lines else "(no memories)"
        )

    def refresh(self) -> None:
        if self.creature is not None:
            self.update_creature(self.creature)

    def _build_creature_report(self) -> str:
        c = self.creature
        if c is None:
            return "(no creature selected)"

        lines: list[str] = []
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"=== Creature #{c.id} Report  [{ts}] ===")
        lines.append("")

        # State
        lines.append("[State]")
        lines.append(f"  Position      : ({c.position.row}, {c.position.col})")
        lines.append(f"  Mode          : {MODE_NAMES.get(c.mode, str(c.mode))}")
        lines.append(f"  Current action: {ACTION_NAMES.get(c.current_action, '-')}")
        lines.append(f"  Last action   : {ACTION_NAMES.get(c.last_action, '-')}")
        lines.append(f"  Food score    : {c.food_score}")
        lines.append(f"  Match score   : {c.last_match_score:.3f}")
        lines.append(f"  Replay fail   : {c.last_replay_fail_reason or '-'}")
        lines.append("")

        # Sense vector
        lines.append("[Current Sense Vector]")
        lines.append(f"  {_sv_str(c.current_sense_vector)}")
        lines.append("")

        # Recent steps
        lines.append("[Recent Steps (last 4)]")
        if c.recent_steps:
            for i, step in enumerate(c.recent_steps):
                pos, sv_i, act = step[0], step[1], step[2]
                mem_idx = step[3] if len(step) > 3 else None
                mem_tag = f"  mem={mem_idx}" if mem_idx is not None else ""
                lines.append(
                    f"  [{i}] pos=({pos.row},{pos.col})"
                    f"  sv={_sv_str(sv_i)}"
                    f"  act={ACTION_NAMES.get(act, '?')}"
                    f"{mem_tag}"
                )
        else:
            lines.append("  (none)")
        lines.append("")

        # Active memory
        lines.append("[Active Memory]")
        if c.active_memory_idx is not None and c.active_step_idx is not None:
            mem = c.memories[c.active_memory_idx]
            step = mem.steps[c.active_step_idx]
            lines.append(
                f"  Memory {c.active_memory_idx}, step {c.active_step_idx}"
                f"  sv={_sv_str(step.sense_vector)}"
                f"  act={ACTION_NAMES.get(step.action, '?')}"
            )
        else:
            lines.append("  -")
        lines.append("")

        # All stored memories
        lines.append(f"[Stored Memories ({len(c.memories)} total)]")
        if c.memories:
            for m_idx, mem_seq in enumerate(c.memories):
                lines.append(f"  Memory {m_idx} ({len(mem_seq.steps)} steps):")
                for s_idx, s in enumerate(mem_seq.steps):
                    lines.append(
                        f"    [{s_idx}] sv={_sv_str(s.sense_vector)}"
                        f"  act={ACTION_NAMES.get(s.action, '?')}"
                    )
        else:
            lines.append("  (no memories)")

        return "\n".join(lines)

    def _copy_to_clipboard(self) -> None:
        report = self._build_creature_report()

        # Copy to system clipboard
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(report)

        # Save to a text file in the user's home directory
        if self.creature is not None:
            filename = f"creature_{self.creature.id}_report.txt"
            save_path = os.path.join(os.path.expanduser("~"), filename)
            try:
                with open(save_path, "w", encoding="utf-8") as fh:
                    fh.write(report)
                self._set_btn_feedback(f"Copied! Saved → ~/{filename}")
            except PermissionError:
                self._set_btn_feedback("Copied! (Save failed: permission denied)")
            except OSError as exc:
                self._set_btn_feedback(f"Copied! (Save failed: {exc.strerror})")
        else:
            self._set_btn_feedback("No creature selected")

    def _set_btn_feedback(self, text: str) -> None:
        """Show feedback text on the copy button, then restore the original label."""
        self.copy_btn.setText(text)
        QTimer.singleShot(3000, lambda: self.copy_btn.setText("Copy Creature to Clipboard"))
