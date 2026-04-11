from dotenv import load_dotenv

from agentic_trader.controller.alpaca_controller import AlpacaController

load_dotenv()


if __name__ == "__main__":
    alpaca = AlpacaController()

    account = alpaca.get_account()
    print("Account status:", account.status)

    positions = alpaca.get_positions()
    print("Positions:", positions)

    orders = alpaca.get_orders()
    print("Orders:", orders)
