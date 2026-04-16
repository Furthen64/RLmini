from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QByteArray, Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.map_format import (
    MAP_EMPTY,
    MAP_FOOD,
    MAP_SPAWN,
    MAP_WALL,
    MapDocument,
    create_empty_map,
    load_map_document,
    save_map_document,
)
from app.settings_store import load_settings, save_settings
from app.ui.map_editor_widget import MapEditorWidget


class MapEditorWindow(QMainWindow):
    map_applied = Signal(object)

    def __init__(
        self,
        initial_path: str | None = None,
        initial_document: MapDocument | None = None,
        settings: dict | None = None,
        allow_apply: bool = False,
    ) -> None:
        super().__init__()
        self._external_settings = settings is not None
        self.settings = settings if settings is not None else load_settings()
        self.allow_apply = allow_apply
        self.current_path: Path | None = None
        self._dirty = False
        self._build_ui()
        self._build_menu()
        self.resize(1100, 760)
        self._restore_geometry()

        if initial_document is not None:
            self.load_document(initial_document, mark_clean=True)
        elif initial_path:
            self._load_path(Path(initial_path))
        else:
            self._new_map(force=True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_discard_changes():
            self._save_window_state()
            event.accept()
        else:
            event.ignore()

    def _build_ui(self) -> None:
        self.setWindowTitle("RLmini Map Editor")
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        top_row = QHBoxLayout()
        self.btn_new = QPushButton("New")
        self.btn_open = QPushButton("Open")
        self.btn_save = QPushButton("Save")
        self.btn_save_as = QPushButton("Save As")
        self.btn_resize = QPushButton("Resize")
        self.btn_apply = QPushButton("Apply To RLmini")
        self.btn_apply.setVisible(self.allow_apply)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Map name")

        self.sb_width = QSpinBox()
        self.sb_width.setRange(5, 100)
        self.sb_height = QSpinBox()
        self.sb_height.setRange(5, 100)

        top_row.addWidget(self.btn_new)
        top_row.addWidget(self.btn_open)
        top_row.addWidget(self.btn_save)
        top_row.addWidget(self.btn_save_as)
        top_row.addSpacing(12)
        top_row.addWidget(QLabel("Name:"))
        top_row.addWidget(self.name_edit, 1)
        top_row.addSpacing(12)
        top_row.addWidget(QLabel("Width:"))
        top_row.addWidget(self.sb_width)
        top_row.addWidget(QLabel("Height:"))
        top_row.addWidget(self.sb_height)
        top_row.addWidget(self.btn_resize)
        top_row.addWidget(self.btn_apply)
        layout.addLayout(top_row)

        tool_row = QHBoxLayout()
        tool_row.addWidget(QLabel("Tool:"))
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for label, token in [
            ("Empty", MAP_EMPTY),
            ("Wall", MAP_WALL),
            ("Food", MAP_FOOD),
            ("Spawn", MAP_SPAWN),
        ]:
            button = QToolButton()
            button.setText(label)
            button.setCheckable(True)
            if token == MAP_WALL:
                button.setChecked(True)
            self.tool_group.addButton(button, token)
            tool_row.addWidget(button)
        tool_row.addStretch()
        tool_row.addWidget(QLabel("Left click paints. Right click clears."))
        layout.addLayout(tool_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.editor = MapEditorWidget()
        self.scroll.setWidget(self.editor)
        layout.addWidget(self.scroll, 1)

        self.status_label = QLabel("Ready")
        status_bar = QStatusBar()
        status_bar.addPermanentWidget(self.status_label, 1)
        self.setStatusBar(status_bar)

        self.btn_new.clicked.connect(self._new_map)
        self.btn_open.clicked.connect(self._open_map)
        self.btn_save.clicked.connect(self._save_map)
        self.btn_save_as.clicked.connect(self._save_map_as)
        self.btn_resize.clicked.connect(self._resize_map)
        self.btn_apply.clicked.connect(self._apply_map)
        self.tool_group.idClicked.connect(self.editor.set_tool)
        self.name_edit.editingFinished.connect(self._commit_name)
        self.editor.document_changed.connect(self._on_document_changed)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        new_action = QAction("New", self)
        new_action.triggered.connect(self._new_map)
        file_menu.addAction(new_action)

        open_action = QAction("Open...", self)
        open_action.triggered.connect(self._open_map)
        file_menu.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self._save_map)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.triggered.connect(self._save_map_as)
        file_menu.addAction(save_as_action)

        if self.allow_apply:
            apply_action = QAction("Apply To RLmini", self)
            apply_action.triggered.connect(self._apply_map)
            file_menu.addAction(apply_action)

    def load_document(
        self,
        doc: MapDocument,
        *,
        mark_clean: bool = True,
        current_path: str | Path | None = None,
    ) -> None:
        self.editor.set_document(doc)
        self.current_path = Path(current_path) if current_path else None
        self._dirty = not mark_clean
        self._sync_controls_from_document()
        self._update_window_title()
        self._set_status(self._status_text())

    def _new_map(self, force: bool = False) -> None:
        if not force and not self._confirm_discard_changes():
            return
        width = self.sb_width.value() or 20
        height = self.sb_height.value() or 15
        self.load_document(
            create_empty_map(width, height, name="untitled"),
            mark_clean=True,
        )
        self._set_status("New map")

    def _open_map(self) -> None:
        if not self._confirm_discard_changes():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Map",
            self._default_file_dialog_path(),
            "RLmini Maps (*.map *.txt);;All Files (*)",
        )
        if path:
            self._load_path(Path(path))

    def _load_path(self, path: Path) -> None:
        try:
            doc = load_map_document(path)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to open map", str(exc))
            return
        self._remember_recent_path(path)
        self.load_document(doc, mark_clean=True, current_path=path)
        self._set_status(f"Loaded {path.name}")

    def _save_map(self) -> None:
        if self.current_path is None:
            self._save_map_as()
            return
        self._commit_name()
        try:
            save_map_document(self.editor.document, self.current_path)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to save map", str(exc))
            return
        self._dirty = False
        self._update_window_title()
        self._set_status(f"Saved {self.current_path.name}")

    def _save_map_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Map",
            self._default_save_path(),
            "RLmini Maps (*.map *.txt);;All Files (*)",
        )
        if not path:
            return
        self.current_path = Path(path)
        self._save_map()

    def _apply_map(self) -> None:
        self._commit_name()
        self.map_applied.emit(self.editor.document.copy())
        self._set_status(f"Applied {self.editor.document.metadata.get('name', 'map')} to RLmini")

    def _resize_map(self) -> None:
        self.editor.resize_document(self.sb_width.value(), self.sb_height.value())
        self._set_status(
            f"Resized map to {self.editor.document.width}x{self.editor.document.height}"
        )

    def _commit_name(self) -> None:
        self.editor.set_name(self.name_edit.text())

    def _on_document_changed(self) -> None:
        self._dirty = True
        self._sync_controls_from_document()
        self._update_window_title()
        self._set_status(self._status_text())

    def _sync_controls_from_document(self) -> None:
        doc = self.editor.document
        self.sb_width.blockSignals(True)
        self.sb_height.blockSignals(True)
        self.name_edit.blockSignals(True)
        self.sb_width.setValue(doc.width)
        self.sb_height.setValue(doc.height)
        self.name_edit.setText(doc.metadata.get("name", ""))
        self.sb_width.blockSignals(False)
        self.sb_height.blockSignals(False)
        self.name_edit.blockSignals(False)

    def _confirm_discard_changes(self) -> bool:
        if not self._dirty:
            return True
        result = QMessageBox.question(
            self,
            "Discard changes?",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _update_window_title(self) -> None:
        base = self.current_path.name if self.current_path else "Untitled"
        if self._dirty:
            base = f"{base} *"
        self.setWindowTitle(f"RLmini Map Editor - {base}")

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _status_text(self) -> str:
        doc = self.editor.document
        return (
            f"{doc.width}x{doc.height} | Food: {doc.count_tile(MAP_FOOD)} | "
            f"Spawns: {len(doc.spawn_positions)}"
        )

    def _default_file_dialog_path(self) -> str:
        if self.current_path is not None:
            return str(self.current_path)
        recent_path = self.settings.get("editor_recent_map_path")
        if recent_path:
            return recent_path
        return str(Path.cwd())

    def _default_save_path(self) -> str:
        if self.current_path is not None:
            return str(self.current_path.with_suffix(".map"))
        recent_path = self.settings.get("editor_recent_map_path")
        if recent_path:
            return str(Path(recent_path).with_suffix(".map"))
        return str(Path.cwd() / "untitled.map")

    def _remember_recent_path(self, path: Path) -> None:
        self.settings["editor_recent_map_path"] = str(path)
        if not self._external_settings:
            save_settings(self.settings)

    def _restore_geometry(self) -> None:
        geom_str = self.settings.get("editor_window_geometry")
        if not geom_str:
            return
        try:
            self.restoreGeometry(QByteArray.fromBase64(geom_str.encode()))
        except Exception:
            return

    def _save_window_state(self) -> None:
        self.settings["editor_window_geometry"] = self.saveGeometry().toBase64().data().decode()
        if self.current_path is not None:
            self.settings["editor_recent_map_path"] = str(self.current_path)
        save_settings(self.settings)