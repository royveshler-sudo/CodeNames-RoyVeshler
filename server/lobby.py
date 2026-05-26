"""Lobby: 4 seats (red/blue x spymaster/operative) and a ready flag per seat.

The lobby holds the connected clients (by username) and exposes helpers to
claim seats, toggle ready, and produce the LOBBY_STATE payload.

The ClientHandler owns the lock and calls into this object. The lobby does
NOT touch sockets — it only manages state. Broadcasts are done by the
handler iterating self.clients and using each client's public key.
"""


SEATS = [
    ("red", "spymaster"),
    ("red", "operative"),
    ("blue", "spymaster"),
    ("blue", "operative"),
]


def seat_key(team: str, role: str) -> str:
    return f"{team}_{role}"


class Lobby:
    """Holds the connected clients and their seat / ready state."""

    def __init__(self):
        # username -> ClientHandler (set by the handler when a client joins)
        self.clients = {}
        # seat_key(team, role) -> username | None
        self.seats = {seat_key(t, r): None for t, r in SEATS}
        # username -> bool
        self.ready = {}

    # -- membership --------------------------------------------------------

    def add_client(self, username: str, handler) -> None:
        self.clients[username] = handler
        self.ready.setdefault(username, False)

    def remove_client(self, username: str) -> None:
        self.clients.pop(username, None)
        self.ready.pop(username, None)
        for key, occupant in list(self.seats.items()):
            if occupant == username:
                self.seats[key] = None

    # -- actions -----------------------------------------------------------

    def choose_seat(self, username: str, team: str, role: str):
        """Claim a seat. Returns (ok, error)."""
        if (team, role) not in SEATS:
            return False, "Invalid seat"
        if username not in self.clients:
            return False, "Not in lobby"

        # If the seat is already taken by someone else, reject.
        target = seat_key(team, role)
        if self.seats[target] not in (None, username):
            return False, "Seat already taken"

        # Free any seat the user previously held.
        for key, occupant in self.seats.items():
            if occupant == username:
                self.seats[key] = None

        self.seats[target] = username
        # Changing seat un-readies the player; otherwise people could ready
        # in a seat, then swap into a different one without re-confirming.
        self.ready[username] = False
        return True, None

    def set_ready(self, username: str, ready: bool):
        if username not in self.clients:
            return False, "Not in lobby"
        # Can only ready while seated.
        if not any(occupant == username for occupant in self.seats.values()):
            return False, "Pick a seat first"
        self.ready[username] = bool(ready)
        return True, None

    # -- queries -----------------------------------------------------------

    def all_seated_and_ready(self) -> bool:
        if any(occupant is None for occupant in self.seats.values()):
            return False
        return all(self.ready.get(occupant, False) for occupant in self.seats.values())

    def seated_usernames(self) -> list:
        return [self.seats[seat_key(t, r)] for (t, r) in SEATS]

    def find_seat(self, username: str):
        """Return (team, role) for username, or None."""
        for key, occupant in self.seats.items():
            if occupant == username:
                team, role = key.split("_", 1)
                return team, role
        return None

    def to_payload(self) -> dict:
        """Serialize to the LOBBY_STATE data dict."""
        return {
            "seats": {key: occupant for key, occupant in self.seats.items()},
            "ready": dict(self.ready),
        }
