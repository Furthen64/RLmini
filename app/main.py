import sys  

# import the QApplication class from PySide6 which manages application-wide resources
from PySide6.QtWidgets import QApplication  # Qt application object (event loop, settings)

# import the MainWindow class for the application's main user interface
from app.ui.main_window import MainWindow  # main window UI class defined in app.ui


def main() -> None:  # entry point function that creates and runs the Qt application
    app = QApplication(sys.argv)  # create QApplication with command-line arguments
    app.setApplicationName("RLmini")  # set a human-readable application name
    app.setOrganizationName("RLmini")  # set the organization name for settings/storage
    window = MainWindow()  # instantiate the application's main window
    window.show()  # make the main window visible on screen
    sys.exit(app.exec())  # start the Qt event loop and exit with its return code


if __name__ == "__main__":  # only run when this file is executed as a script
    main()  # call the main function to start the application
