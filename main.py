"""Entry point: python main.py"""
from db_manager import init_database
from gui.app import SmartSalesApp


def main():
    init_database()
    app = SmartSalesApp()
    app.mainloop()


if __name__ == "__main__":
    main()
