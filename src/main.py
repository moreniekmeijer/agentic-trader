from dotenv import load_dotenv

from controller.alpaca_controller import AlpacaController

load_dotenv()


if __name__ == "__main__":
    alpaca = AlpacaController()

    account = alpaca.get_account()
    print("Account status:", account.status)

    # print("Placing test order...")
    # order = alpaca.buy("AAPL", 1)

    # print("Order response:", order)

    positions = alpaca.get_positions()
    print("Positions:", positions)
