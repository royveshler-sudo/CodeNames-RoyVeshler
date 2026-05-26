"""Client entry point: login (tkinter) -> lobby (pygame) -> game (pygame).

Run from the project root:
    python -m client.main
"""

from client.login_window import LoginWindow
from client.lobby_window import LobbyWindow
from client.game_window import GameWindow


def main():
    # 1. Login
    login = LoginWindow()
    username, network = login.run()
    if username is None:
        print("Login cancelled. Exiting.")
        return

    try:
        # 2. Lobby — returns the GAME_START payload when the server starts a game.
        lobby = LobbyWindow(network, username)
        start_payload = lobby.run()
        if start_payload is None:
            print("Lobby closed before the game started. Exiting.")
            return

        # 3. Game
        game = GameWindow(network, username, start_payload)
        game.run()
    finally:
        network.close()


if __name__ == "__main__":
    main()
