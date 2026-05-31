

import pygame

from shared import protocol as P
from shared.protocol import make_message

from client.text_utils import make_font


# Window layout
WIDTH = 800
HEIGHT = 600
BG = (30, 30, 36)
FG = (235, 235, 240)
RED_BG = (170, 60, 60)
BLUE_BG = (60, 90, 170)
SEAT_FREE = (90, 90, 100)
SEAT_TAKEN = (140, 140, 150)
BUTTON_BG = (70, 130, 70)
BUTTON_BG_DISABLED = (70, 70, 70)
BUTTON_BG_READY = (160, 110, 50)


SEAT_BOXES = {
    ("red", "spymaster"):  pygame.Rect(60,  120, 320, 140),
    ("red", "operative"):  pygame.Rect(60,  280, 320, 140),
    ("blue", "spymaster"): pygame.Rect(420, 120, 320, 140),
    ("blue", "operative"): pygame.Rect(420, 280, 320, 140),
}

READY_BUTTON = pygame.Rect(300, 470, 200, 60)


class LobbyWindow:


    def __init__(self, network, username):
        self.network = network
        self.username = username

        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(f"Codenames — Lobby ({username})")

        self.font_big = make_font(28, bold=True)
        self.font_mid = make_font(20)
        self.font_small = make_font(16)
        self.clock = pygame.time.Clock()


        self.seats = {f"{t}_{r}": None for (t, r) in SEAT_BOXES}
        self.ready = {}
        self.status = "Joining lobby..."

        self.game_start_payload = None
        self.quit = False

        self.network.send(make_message(P.JOIN_LOBBY))



    def _my_seat(self):
        for key, occupant in self.seats.items():
            if occupant == self.username:
                team, role = key.split("_", 1)
                return team, role
        return None

    def _i_am_ready(self) :
        return bool(self.ready.get(self.username, False))


    def _on_click(self, pos):
        for (team, role), rect in SEAT_BOXES.items():
            if rect.collidepoint(pos):
                self.network.send(make_message(P.CHOOSE_SEAT, team=team, role=role))
                return
        if READY_BUTTON.collidepoint(pos):
            if self._my_seat() is None:
                self.status = "Pick a seat before pressing Ready."
                return
            self.network.send(make_message(P.READY, ready=not self._i_am_ready()))

    def _handle_message(self, msg):
        msg_type = msg.get("type")
        data = msg.get("data", {}) or {}

        if msg_type == P.LOBBY_STATE:
            self.seats = data.get("seats", self.seats)
            self.ready = data.get("ready", {})
            self.status = "Waiting for all players to ready up..."

        elif msg_type == P.GAME_START:
            self.game_start_payload = data
            self.quit = True

        elif msg_type == P.ERROR:
            self.status = f"Error: {data.get('message')}"



    def _draw_seat(self, team, role, rect):
        occupant = self.seats.get(f"{team}_{role}")
        bg = RED_BG if team == "red" else BLUE_BG
        if occupant is None:
            bg = tuple(max(0, c - 40) for c in bg)

        pygame.draw.rect(self.screen, bg, rect, border_radius=12)
        pygame.draw.rect(self.screen, FG, rect, width=2, border_radius=12)

        title = self.font_big.render(f"{team.capitalize()} {role.capitalize()}", True, FG)
        self.screen.blit(title, (rect.x + 16, rect.y + 14))

        if occupant is None:
            label = self.font_mid.render("(click to claim)", True, FG)
        else:
            ready_mark = " ✓" if self.ready.get(occupant) else ""
            label = self.font_mid.render(f"{occupant}{ready_mark}", True, FG)
        self.screen.blit(label, (rect.x + 16, rect.y + 70))

    def _draw(self):
        self.screen.fill(BG)

        title = self.font_big.render(f"Lobby — {self.username}", True, FG)
        self.screen.blit(title, ((WIDTH - title.get_width()) // 2, 30))

        for (team, role), rect in SEAT_BOXES.items():
            self._draw_seat(team, role, rect)

        if self._my_seat() is None:
            ready_color = BUTTON_BG_DISABLED
            ready_text = "Ready"
        elif self._i_am_ready():
            ready_color = BUTTON_BG_READY
            ready_text = "Cancel Ready"
        else:
            ready_color = BUTTON_BG
            ready_text = "Ready"
        pygame.draw.rect(self.screen, ready_color, READY_BUTTON, border_radius=10)
        label = self.font_mid.render(ready_text, True, FG)
        self.screen.blit(label, (
            READY_BUTTON.x + (READY_BUTTON.width - label.get_width()) // 2,
            READY_BUTTON.y + (READY_BUTTON.height - label.get_height()) // 2,
        ))

        status_lbl = self.font_small.render(self.status, True, FG)
        self.screen.blit(status_lbl, (20, HEIGHT - 28))

        pygame.display.flip()


    def run(self):
        while not self.quit:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit = True
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._on_click(event.pos)

            while True:
                msg = self.network.get_message()
                if msg is None:
                    break
                self._handle_message(msg)
            if self.network.error is not None:
                self.status = f"Disconnected: {self.network.error}"
                self._draw()
                pygame.time.wait(1500)
                self.quit = True
                break

            self._draw()
            self.clock.tick(30)

        return self.game_start_payload
