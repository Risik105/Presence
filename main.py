import sys

from PySide6.QtWidgets import QApplication

from window import AutoClicker

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setOrganizationName("Presence")
    app.setApplicationName("Presence")

    window = AutoClicker()
    window.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
    