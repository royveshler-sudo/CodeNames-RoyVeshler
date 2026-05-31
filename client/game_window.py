_author_ = 'Roy'

import pygame

from shared import protocol as P
from shared.protocol import make_message

from client.text_utils import make_font



DEFAULT_WIDTH = 1100
DEFAULT_HEIGHT = 720
MIN_WIDTH = 900
MIN_HEIGHT = 600

BG = (24, 24, 30)
FG = (235, 235, 240)


BOARD_MARGIN = 30
CARD_GAP = 8
SIDEBAR_GAP = 20
CARD_ASPECT = 1.6


COLOR_FULL = {
    "red":      (190, 70, 70),
    "blue":     (70, 90, 190),
    "neutral":  (215, 200, 160),
    "assassin": (30, 30, 30),
}

COLOR_TINT = {
    "red":      (110, 70, 70),
    "blue":     (70, 80, 110),
    "neutral":  (130, 120, 100),
    "assassin": (40, 40, 50),
}
CARD_UNREVEALED = (210, 200, 190)
CARD_TEXT = (20, 20, 24)
CARD_TEXT_LIGHT = (240, 240, 240)


class GameWindow:
    def __init__(self, network, username, start_payload):
        self.network = network
        self.username = username

        # GAME_START data
        self.board = start_payload["board"]
        self.role = start_payload["your_role"]
        self.team = start_payload["your_team"]
        self.key = start_payload.get("key")


        self.current_team = start_payload["starting_team"]
        self.current_clue = None
        self.guesses_left = 0
        self.red_remaining = 9 if self.current_team == "red" else 8
        self.blue_remaining = 9 if self.current_team == "blue" else 8
        self.revealed = {}


        self.log = []
        self._add_log(f"You are the {self.team.upper()} {self.role.upper()}")
        self._add_log(f"{self.current_team.upper()} team starts.")


        self.winner = None
        self.over_reason = None


        self.clue_input = ""
        self.clue_number = 1
        self.clue_input_active = False
        self.guess_count_this_turn = 0

        pygame.init()
        self.screen = pygame.display.set_mode(
            (DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(f"Codenames — {self.team} {self.role} ({username})")


        self.font_side = make_font(18)
        self.font_small = make_font(14)
        self.font_big = make_font(28, bold=True)
        self.clock = pygame.time.Clock()




        self._recompute_layout()



    def _recompute_layout(self):
        w, h = self.screen.get_size()
        self.width = w
        self.height = h

        sidebar_w = max(220, min(320, int(w * 0.25)))
        avail_w = w - 2 * BOARD_MARGIN - sidebar_w - SIDEBAR_GAP
        avail_h = h - 2 * BOARD_MARGIN

        card_w_by_width = (avail_w - 4 * CARD_GAP) / 5
        card_w_by_height = ((avail_h - 4 * CARD_GAP) / 5) * CARD_ASPECT
        card_w = max(60, min(card_w_by_width, card_w_by_height))
        self.card_w = int(card_w)
        self.card_h = int(card_w / CARD_ASPECT)

        board_w = 5 * self.card_w + 4 * CARD_GAP
        board_h = 5 * self.card_h + 4 * CARD_GAP
        self.board_left = BOARD_MARGIN + max(0, (avail_w - board_w) // 2)
        self.board_top = BOARD_MARGIN + max(0, (avail_h - board_h) // 4)

        self.side_left = BOARD_MARGIN + avail_w + SIDEBAR_GAP
        self.side_w = w - self.side_left - BOARD_MARGIN

        self.clue_box = pygame.Rect(
            self.side_left, h - 360, self.side_w, 36)
        self.minus_button = pygame.Rect(
            self.side_left + 130, h - 310, 36, 36)
        self.plus_button = pygame.Rect(
            self.side_left + 200, h - 310, 36, 36)
        self.send_clue_button = pygame.Rect(
            self.side_left, h - 260, self.side_w, 44)
        self.end_turn_button = pygame.Rect(
            self.side_left, h - 260, self.side_w, 44)

        self.font_card = make_font(max(10, int(self.card_h * 0.18)), bold=True)
        self.font_card_sm = make_font(max(9, int(self.card_h * 0.15)), bold=True)

    def _card_rect(self, index):
        row, col = divmod(index, 5)
        return pygame.Rect(
            self.board_left + col * (self.card_w + CARD_GAP),
            self.board_top + row * (self.card_h + CARD_GAP),
            self.card_w,
            self.card_h,
        )

    # -- helpers -----------------------------------------------------------

    def _add_log(self, line):
        self.log.append(line)
        if len(self.log) > 12:
            self.log = self.log[-12:]

    def _is_my_turn(self) :
        return self.current_team == self.team and self.winner is None

    def _is_active_spymaster(self) :
        return (self._is_my_turn() and self.role == "spymaster"
                and self.current_clue is None)

    def _is_active_operative(self) :
        return (self._is_my_turn() and self.role == "operative"
                and self.current_clue is not None)

    # -- events ------------------------------------------------------------

    def _on_click(self, pos):
        if self.winner is not None:
            return

        if self._is_active_operative():
            for i in range(25):
                if self._card_rect(i).collidepoint(pos) and i not in self.revealed:
                    self.network.send(make_message(P.GUESS_CARD, index=i))
                    return

        if self._is_active_spymaster():
            if self.clue_box.collidepoint(pos):
                self.clue_input_active = True
                return
            if self.minus_button.collidepoint(pos):
                self.clue_number = max(0, self.clue_number - 1)
                return
            if self.plus_button.collidepoint(pos):
                self.clue_number = min(9, self.clue_number + 1)
                return
            if self.send_clue_button.collidepoint(pos):
                self._submit_clue()
                return
            self.clue_input_active = False
            return

        if self._is_active_operative() and self.guess_count_this_turn >= 1:
            if self.end_turn_button.collidepoint(pos):
                self.network.send(make_message(P.END_TURN))

    def _on_key(self, event):
        if not (self._is_active_spymaster() and self.clue_input_active):
            return
        if event.key == pygame.K_RETURN:
            self._submit_clue()
        elif event.key == pygame.K_BACKSPACE:
            self.clue_input = self.clue_input[:-1]
        else:
            ch = event.unicode
            if ch.isalpha() and len(self.clue_input) < 18:
                self.clue_input += ch

    def _submit_clue(self):
        word = self.clue_input.strip()
        if not word:
            self._add_log("Type a clue word first.")
            return
        self.network.send(make_message(P.GIVE_CLUE, word=word, number=self.clue_number))


    def _handle_message(self, msg):
        msg_type = msg.get("type")
        data = msg.get("data", {}) or {}

        if msg_type == P.GAME_STATE:
            old_team = self.current_team
            for r in data.get("revealed", []):
                self.revealed[r["index"]] = r["color"]
            self.current_team = data.get("current_team", self.current_team)
            self.current_clue = data.get("current_clue")
            self.guesses_left = data.get("guesses_left", 0)
            self.red_remaining = data.get("red_remaining", self.red_remaining)
            self.blue_remaining = data.get("blue_remaining", self.blue_remaining)

            if old_team != self.current_team:
                self.guess_count_this_turn = 0
                self.clue_input = ""
                self.clue_number = 1

        elif msg_type == P.CLUE_GIVEN:
            team = data.get("team")
            word = data.get("word")
            n = data.get("number")
            self._add_log(f"{team.upper()} spymaster: {word.upper()} — {n}")

        elif msg_type == P.GUESS_RESULT:
            word = data.get("word")
            color = data.get("color")
            guesser = data.get("team_that_guessed")
            self._add_log(f"{guesser.upper()} guessed {word.upper()} → {color.upper()}")
            if guesser == self.team and self.role == "operative":
                self.guess_count_this_turn += 1

        elif msg_type == P.GAME_OVER:
            self.winner = data.get("winner")
            self.over_reason = data.get("reason")
            self._add_log(f"GAME OVER — {self.winner.upper()} wins ({self.over_reason})")

        elif msg_type == P.ERROR:
            self._add_log(f"Error: {data.get('message')}")


    def _card_background(self, index):
        """Return (fill_color, text_color) for a card."""
        if index in self.revealed:
            color = self.revealed[index]
            text = CARD_TEXT_LIGHT if color in ("red", "blue", "assassin") else CARD_TEXT
            return COLOR_FULL[color], text

        if self.role == "spymaster" and self.key is not None:
            return COLOR_TINT[self.key[index]], CARD_TEXT_LIGHT

        return CARD_UNREVEALED, CARD_TEXT

    def _draw_board(self):
        for i, card in enumerate(self.board):
            rect = self._card_rect(i)
            bg, text_color = self._card_background(i)
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            pygame.draw.rect(self.screen, (15, 15, 18), rect, width=2, border_radius=8)

            word = card["word"]
            font = (self.font_card
                    if self.font_card.size(word)[0] < self.card_w - 16
                    else self.font_card_sm)
            label = font.render(word, True, text_color)
            self.screen.blit(label, (
                rect.x + (rect.width - label.get_width()) // 2,
                rect.y + (rect.height - label.get_height()) // 2,
            ))

    def _draw_sidebar(self):
        x = self.side_left
        y = 30

        title_color = COLOR_FULL["red"] if self.team == "red" else COLOR_FULL["blue"]
        title = self.font_big.render(f"{self.team.upper()} {self.role.upper()}", True, title_color)
        self.screen.blit(title, (x, y))
        y += 50

        turn_color = COLOR_FULL[self.current_team]
        turn_lbl = self.font_side.render(
            f"Turn: {self.current_team.upper()}", True, turn_color)
        self.screen.blit(turn_lbl, (x, y))
        y += 28

        red_lbl = self.font_side.render(f"Red left: {self.red_remaining}", True, COLOR_FULL["red"])
        blue_lbl = self.font_side.render(f"Blue left: {self.blue_remaining}", True, COLOR_FULL["blue"])
        self.screen.blit(red_lbl, (x, y))
        self.screen.blit(blue_lbl, (x + 160, y))
        y += 32

        if self.current_clue:
            clue_text = f"Clue: {self.current_clue['word'].upper()} — {self.current_clue['number']}"
            guesses = self.font_side.render(
                f"Guesses left: {self.guesses_left}", True, FG)
        else:
            clue_text = "Clue: (waiting)"
            guesses = self.font_side.render("", True, FG)
        clue_lbl = self.font_side.render(clue_text, True, FG)
        self.screen.blit(clue_lbl, (x, y))
        y += 26
        self.screen.blit(guesses, (x, y))
        y += 36

        # Log box (last few lines)
        for line in self.log:
            log_lbl = self.font_small.render(line, True, FG)
            self.screen.blit(log_lbl, (x, y))
            y += 18
        if self._is_active_spymaster():
            input_color = (60, 60, 80) if self.clue_input_active else (40, 40, 50)
            pygame.draw.rect(self.screen, input_color, self.clue_box, border_radius=6)
            pygame.draw.rect(self.screen, FG, self.clue_box, width=1, border_radius=6)
            text = self.clue_input + ("|" if self.clue_input_active else "")
            text_lbl = self.font_side.render(text or "Type clue word...", True,
                                             FG if self.clue_input else (140, 140, 150))
            self.screen.blit(text_lbl, (self.clue_box.x + 8, self.clue_box.y + 6))

            num_label = self.font_side.render(f"Words: {self.clue_number}", True, FG)
            self.screen.blit(num_label, (self.side_left, self.minus_button.y + 6))
            pygame.draw.rect(self.screen, (80, 80, 90), self.minus_button, border_radius=6)
            pygame.draw.rect(self.screen, (80, 80, 90), self.plus_button, border_radius=6)
            for rect, text in [(self.minus_button, "-"), (self.plus_button, "+")]:
                lbl = self.font_side.render(text, True, FG)
                self.screen.blit(lbl, (
                    rect.x + (rect.width - lbl.get_width()) // 2,
                    rect.y + (rect.height - lbl.get_height()) // 2,
                ))

            pygame.draw.rect(self.screen, (70, 130, 70), self.send_clue_button, border_radius=8)
            send_lbl = self.font_side.render("Send Clue", True, FG)
            self.screen.blit(send_lbl, (
                self.send_clue_button.x + (self.send_clue_button.width - send_lbl.get_width()) // 2,
                self.send_clue_button.y + (self.send_clue_button.height - send_lbl.get_height()) // 2,
            ))

        elif self._is_active_operative():
            enabled = self.guess_count_this_turn >= 1
            color = (160, 110, 50) if enabled else (60, 60, 70)
            pygame.draw.rect(self.screen, color, self.end_turn_button, border_radius=8)
            end_lbl = self.font_side.render("End Turn", True, FG)
            self.screen.blit(end_lbl, (
                self.end_turn_button.x + (self.end_turn_button.width - end_lbl.get_width()) // 2,
                self.end_turn_button.y + (self.end_turn_button.height - end_lbl.get_height()) // 2,
            ))

        if self.winner is not None:
            banner = pygame.Rect(
                self.side_left, self.height - 110, self.side_w, 80)
            color = COLOR_FULL[self.winner]
            pygame.draw.rect(self.screen, color, banner, border_radius=10)
            text = f"{self.winner.upper()} wins!"
            label = self.font_big.render(text, True, FG)
            self.screen.blit(label, (
                banner.x + (banner.width - label.get_width()) // 2,
                banner.y + 8,
            ))
            sub = self.font_small.render(f"({self.over_reason})", True, FG)
            self.screen.blit(sub, (
                banner.x + (banner.width - sub.get_width()) // 2,
                banner.y + 48,
            ))

    def _draw(self):
        self.screen.fill(BG)
        self._draw_board()
        self._draw_sidebar()
        pygame.display.flip()


    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._on_click(event.pos)
                elif event.type == pygame.KEYDOWN:
                    self._on_key(event)
                elif event.type == pygame.VIDEORESIZE:
                    new_w = max(MIN_WIDTH, event.w)
                    new_h = max(MIN_HEIGHT, event.h)
                    self.screen = pygame.display.set_mode(
                        (new_w, new_h), pygame.RESIZABLE)
                    self._recompute_layout()

            while True:
                msg = self.network.get_message()
                if msg is None:
                    break
                self._handle_message(msg)
            if self.network.error is not None:
                self._add_log(f"Disconnected: {self.network.error}")
                self._draw()
                pygame.time.wait(2000)
                break

            self._draw()
            self.clock.tick(30)
