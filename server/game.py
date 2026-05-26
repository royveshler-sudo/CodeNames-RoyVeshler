"""Codenames game engine — pure Python, no networking.

The server's ClientHandler calls into this class to validate actions and
update state. Errors are raised as InvalidAction so the handler can convert
them into ERROR messages.
"""

import random


# Card type constants — match the "color" field exposed to clients.
RED = "red"
BLUE = "blue"
NEUTRAL = "neutral"
ASSASSIN = "assassin"


class InvalidAction(Exception):
    """Raised when a client tries to make an illegal move."""


class Game:
    """Codenames rules engine for a 4-player game.

    `players` maps (team, role) -> username for the 4 seats. Inside the
    engine we mostly identify players by their username (player_id).
    """

    def __init__(self, players: dict, word_pool: list, seed=None):
        if len(players) != 4:
            raise ValueError("Need exactly 4 players")

        self._rng = random.Random(seed)

        # players: dict mapping (team, role) tuples -> username
        # we also store the reverse lookup for convenience.
        self.players = dict(players)
        self.role_of = {username: (team, role)
                        for (team, role), username in players.items()}

        # Pick 25 words and shuffle the colors.
        if len(word_pool) < 25:
            raise ValueError("Word pool must contain at least 25 words")
        words = self._rng.sample(word_pool, 25)

        # Pick a starting team randomly: it gets 9, the other gets 8.
        self.starting_team = self._rng.choice([RED, BLUE])
        other = BLUE if self.starting_team == RED else RED
        colors = (
            [self.starting_team] * 9
            + [other] * 8
            + [NEUTRAL] * 7
            + [ASSASSIN] * 1
        )
        self._rng.shuffle(colors)

        # The board: list of 25 dicts, indexed 0..24 (row-major 5x5).
        self.board = [
            {"word": w, "color": c, "revealed": False}
            for w, c in zip(words, colors)
        ]

        self.current_team = self.starting_team
        self.current_clue = None          # {"word": str, "number": int} or None
        self.guesses_left = 0             # remaining guesses for the current clue
        self.guesses_made_this_turn = 0   # used to enforce "guess at least once"
        self.winner = None                # RED, BLUE, or None
        self.over_reason = None           # "all_words" or "assassin"
        # History of past clues (so the same clue word isn't repeated).
        self.past_clue_words = set()

    # -----------------------------------------------------------------
    # Views
    # -----------------------------------------------------------------

    def get_start_payload_for(self, username: str) -> dict:
        """Build the GAME_START data dict for a specific player."""
        team, role = self.role_of[username]
        payload = {
            "board": [{"word": card["word"]} for card in self.board],
            "your_role": role,
            "your_team": team,
            "starting_team": self.starting_team,
            "key": None,
        }
        if role == "spymaster":
            payload["key"] = [card["color"] for card in self.board]
        return payload

    def get_state_payload(self) -> dict:
        """Public state shared by everyone (no hidden colors)."""
        revealed = []
        for i, card in enumerate(self.board):
            if card["revealed"]:
                revealed.append({"index": i, "word": card["word"], "color": card["color"]})
        return {
            "revealed": revealed,
            "current_team": self.current_team,
            "current_clue": self.current_clue,
            "guesses_left": self.guesses_left,
            "red_remaining": self._remaining_for(RED),
            "blue_remaining": self._remaining_for(BLUE),
        }

    # -----------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------

    def give_clue(self, username: str, word: str, number) -> None:
        """Validate and record a clue. Resets the guess counter."""
        if self.is_over():
            raise InvalidAction("Game is over")

        team, role = self.role_of.get(username, (None, None))
        if team is None:
            raise InvalidAction("Unknown player")
        if role != "spymaster":
            raise InvalidAction("Only the spymaster can give a clue")
        if team != self.current_team:
            raise InvalidAction("Not your team's turn")
        if self.current_clue is not None:
            raise InvalidAction("A clue has already been given this turn")

        if not isinstance(number, int) or number < 0:
            raise InvalidAction("Number must be a non-negative integer")
        if not isinstance(word, str):
            raise InvalidAction("Clue must be a string")

        word_clean = word.strip()
        if not word_clean or " " in word_clean:
            raise InvalidAction("Clue must be exactly one word, no spaces")

        # Substring check against unrevealed grid words.
        clue_lower = word_clean.lower()
        for card in self.board:
            if card["revealed"]:
                continue
            grid_lower = card["word"].lower()
            if clue_lower == grid_lower or clue_lower in grid_lower or grid_lower in clue_lower:
                raise InvalidAction(
                    "Clue word may not be a substring of any unrevealed word")

        if clue_lower in self.past_clue_words:
            raise InvalidAction("That clue word has already been used")

        self.current_clue = {"word": word_clean, "number": number}
        self.past_clue_words.add(clue_lower)
        # N+1 guesses; N=0 means unlimited (we use a large sentinel).
        self.guesses_left = (number + 1) if number >= 1 else 10**6
        self.guesses_made_this_turn = 0

    def make_guess(self, username: str, index: int) -> dict:
        """Reveal a card. Returns the GUESS_RESULT payload."""
        if self.is_over():
            raise InvalidAction("Game is over")

        team, role = self.role_of.get(username, (None, None))
        if team is None:
            raise InvalidAction("Unknown player")
        if role != "operative":
            raise InvalidAction("Only the operative can guess")
        if team != self.current_team:
            raise InvalidAction("Not your team's turn")
        if self.current_clue is None:
            raise InvalidAction("Wait for your spymaster's clue first")

        if not isinstance(index, int) or index < 0 or index >= 25:
            raise InvalidAction("Guess index must be 0..24")
        card = self.board[index]
        if card["revealed"]:
            raise InvalidAction("That card has already been revealed")
        if self.guesses_left <= 0:
            raise InvalidAction("No guesses left for this clue")

        card["revealed"] = True
        self.guesses_left -= 1
        self.guesses_made_this_turn += 1

        result = {
            "index": index,
            "word": card["word"],
            "color": card["color"],
            "team_that_guessed": team,
        }

        # Resolve consequences.
        if card["color"] == ASSASSIN:
            self.winner = BLUE if team == RED else RED
            self.over_reason = "assassin"
            self._end_game()
            return result

        # Win-by-completion can happen even on a wrong-team guess.
        if self._remaining_for(RED) == 0:
            self.winner = RED
            self.over_reason = "all_words"
            self._end_game()
            return result
        if self._remaining_for(BLUE) == 0:
            self.winner = BLUE
            self.over_reason = "all_words"
            self._end_game()
            return result

        if card["color"] != team:
            # Wrong-team or neutral guess ends the turn immediately.
            self._pass_turn()
        elif self.guesses_left <= 0:
            # Hit the N+1 limit.
            self._pass_turn()

        return result

    def end_turn(self, username: str) -> None:
        """Operative voluntarily ends the turn."""
        if self.is_over():
            raise InvalidAction("Game is over")

        team, role = self.role_of.get(username, (None, None))
        if role != "operative":
            raise InvalidAction("Only the operative can end the turn")
        if team != self.current_team:
            raise InvalidAction("Not your team's turn")
        if self.current_clue is None:
            raise InvalidAction("No clue has been given yet")
        if self.guesses_made_this_turn < 1:
            raise InvalidAction("You must guess at least once before ending the turn")

        self._pass_turn()

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _remaining_for(self, team: str) -> int:
        return sum(1 for c in self.board if c["color"] == team and not c["revealed"])

    def _pass_turn(self) -> None:
        self.current_team = BLUE if self.current_team == RED else RED
        self.current_clue = None
        self.guesses_left = 0
        self.guesses_made_this_turn = 0

    def _end_game(self) -> None:
        self.current_clue = None
        self.guesses_left = 0

    def is_over(self) -> bool:
        return self.winner is not None
