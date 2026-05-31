


SEATS = [
    ("red", "spymaster"),
    ("red", "operative"),
    ("blue", "spymaster"),
    ("blue", "operative"),
]


def seat_key(team, role):
    return f"{team}_{role}"


class Lobby:

    def __init__(self):
        self.clients = {}
        self.seats = {seat_key(t, r): None for t, r in SEATS}
        self.ready = {}


    def add_client(self, username, handler) :
        self.clients[username] = handler
        self.ready.setdefault(username, False)

    def remove_client(self, username):
        self.clients.pop(username, None)
        self.ready.pop(username, None)
        for key, occupant in list(self.seats.items()):
            if occupant == username:
                self.seats[key] = None


    def choose_seat(self, username, team, role):
        if (team, role) not in SEATS:
            return False, "Invalid seat"
        if username not in self.clients:
            return False, "Not in lobby"

        target = seat_key(team, role)
        if self.seats[target] not in (None, username):
            return False, "Seat already taken"

        for key, occupant in self.seats.items():
            if occupant == username:
                self.seats[key] = None

        self.seats[target] = username
        self.ready[username] = False
        return True, None

    def set_ready(self, username, ready):
        if username not in self.clients:
            return False, "Not in lobby"
        # Can only ready while seated.
        if not any(occupant == username for occupant in self.seats.values()):
            return False, "Pick a seat first"
        self.ready[username] = bool(ready)
        return True, None


    def all_seated_and_ready(self) :
        if any(occupant is None for occupant in self.seats.values()):
            return False
        return all(self.ready.get(occupant, False) for occupant in self.seats.values())

    def seated_usernames(self):
        return [self.seats[seat_key(t, r)] for (t, r) in SEATS]

    def find_seat(self, username):
        for key, occupant in self.seats.items():
            if occupant == username:
                team, role = key.split("_", 1)
                return team, role
        return None

    def to_payload(self) :
        return {
            "seats": {key: occupant for key, occupant in self.seats.items()},
            "ready": dict(self.ready),
        }
