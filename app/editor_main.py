import sys

from PySide6.QtWidgets import QApplication

from app.ui.map_editor_window import MapEditorWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("RLmini Map Editor")
    app.setOrganizationName("RLmini")

    initial_path = sys.argv[1] if len(sys.argv) > 1 else None
    window = MapEditorWindow(initial_path=initial_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()