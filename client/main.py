

from client.login_window import LoginWindow
from client.lobby_window import LobbyWindow
from client.game_window import GameWindow


def main():
    login = LoginWindow()
    username, network = login.run()
    if username is None:
        print("Login cancelled. Exiting.")
        return

    try:
        lobby = LobbyWindow(network, username)
        start_payload = lobby.run()
        if start_payload is None:
            print("Lobby closed before the game started. Exiting.")
            return

        game = GameWindow(network, username, start_payload)
        game.run()
    finally:
        network.close()


if __name__ == "__main__":
    main()
