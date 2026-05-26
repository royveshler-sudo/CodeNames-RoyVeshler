# Codenames — Network Protocol

This document describes the wire protocol used between the Codenames
client and server. It covers framing, the RSA handshake, the encrypted
message format, every message type, and the session state machine.

---

## 1. Framing

TCP is a byte stream, not a message stream. Every payload on the wire is
preceded by a 4-byte **big-endian** length prefix:

```
+--------+------------------+
| 4 B    | N bytes          |
| length | payload          |
+--------+------------------+
```

Both plaintext frames (during the handshake) and encrypted frames (after
the handshake) use this format. The helper functions are
`shared/protocol.py::send_frame` and `recv_frame`.

---

## 2. Handshake (plaintext)

Each new TCP connection begins with a public-key exchange. Public keys
are, by definition, public — so this exchange does **not** need to be
encrypted.

```
client                                         server
  |                                              |
  |---  TCP connect  --------------------------->|
  |                                              |
  |<--  server public key (PEM, framed)  --------|
  |                                              |
  |---  client public key (PEM, framed)  ------->|
  |                                              |
  |==  encrypted JSON messages from here on  ==  |
```

After the handshake each side stores:
- its own **private key** (for decrypting incoming messages);
- the **remote side's public key** (for encrypting outgoing messages).

### Why two key pairs?

- The **server** has one identity, used by all clients, so it makes sense
  to save its key pair to disk (`data/private_key.pem`,
  `data/public_key.pem`) and reuse it across runs.
- Each **client** generates a fresh in-memory key pair on every startup.
  Saving client keys would cause file-name collisions when running
  multiple clients on the same computer for testing. The ~1–2-second
  startup delay for key generation is acceptable.

---

## 3. Encrypted messages (after handshake)

Every message after the handshake is a JSON object of the form:

```json
{ "type": "MESSAGE_TYPE", "data": { ... } }
```

It is then encoded as UTF-8, **chunk-encrypted** with the recipient's
RSA-2048 public key (OAEP padding, SHA-256), and sent as a single framed
payload.

### Why chunking?

RSA-2048 + OAEP-SHA256 can only encrypt up to **190 bytes** of plaintext
per single `encrypt()` call. Each encryption produces exactly **256
bytes** of ciphertext. So:

- **Sender**: split the plaintext into 190-byte pieces, encrypt each
  piece separately, and concatenate the 256-byte ciphertexts.
- **Receiver**: split the ciphertext into 256-byte pieces, decrypt each
  piece separately, and concatenate the plaintexts.

For example, a 500-byte plaintext becomes three 256-byte ciphertext
blocks (3 × 256 = 768 bytes) sent as one framed payload.

`shared/protocol.py::send_encrypted` and `recv_encrypted` wrap this
together with JSON encoding.

### What is **not** encrypted?

- Only the **public-key exchange in the handshake** is in plaintext, by
  design. Public keys are intended to be public.
- The 4-byte length prefix is also not encrypted — it has to be, so the
  receiver knows how many bytes to read.

Everything inside the encrypted payload (usernames, passwords, lobby
state, the spymaster's secret key card, clues, guesses) is encrypted.

---

## 4. Message types

Each message has a `type` (one of the constants in
`shared/protocol.py`) and a `data` object whose shape is fixed per type.

### Client → Server

| Type           | Data fields                                         | Description |
|----------------|------------------------------------------------------|-------------|
| `SIGNUP`       | `username` (str), `password` (str)                  | Create a new account. |
| `LOGIN`        | `username` (str), `password` (str)                  | Authenticate an existing account. |
| `JOIN_LOBBY`   | *(none)*                                            | Enter the lobby after login. |
| `CHOOSE_SEAT`  | `team` ("red" \| "blue"), `role` ("spymaster" \| "operative") | Claim a seat. |
| `READY`        | `ready` (bool)                                      | Toggle the player's ready state. |
| `GIVE_CLUE`    | `word` (str), `number` (int)                        | Spymaster gives a clue. |
| `GUESS_CARD`   | `index` (int, 0..24)                                | Operative reveals a card. |
| `END_TURN`     | *(none)*                                            | Operative voluntarily ends the turn. |
| `LEAVE`        | *(none)*                                            | Disconnect cleanly. |

### Server → Client

| Type            | Data fields                                                       | Description |
|-----------------|-------------------------------------------------------------------|-------------|
| `SIGNUP_RESULT` | `ok` (bool), `error` (str \| null)                                | Result of a signup attempt. |
| `LOGIN_RESULT`  | `ok` (bool), `error` (str \| null)                                | Result of a login attempt. |
| `LOBBY_STATE`   | `seats` (dict), `ready` (dict)                                    | Full lobby snapshot, broadcast on every change. |
| `GAME_START`    | `board` (25 × {word}), `your_role`, `your_team`, `starting_team`, `key` (25 colors **for spymasters only**, else null) | Personalized start packet. |
| `GAME_STATE`    | `revealed` (list), `current_team`, `current_clue`, `guesses_left`, `red_remaining`, `blue_remaining` | Public game state, broadcast after every action. |
| `CLUE_GIVEN`    | `team`, `word`, `number`                                          | Log entry for the chat/sidebar. |
| `GUESS_RESULT`  | `index`, `word`, `color`, `team_that_guessed`                     | Outcome of one guess. |
| `GAME_OVER`     | `winner` ("red" \| "blue"), `reason` ("all_words" \| "assassin")  | Game has ended. |
| `ERROR`         | `message` (str)                                                   | Sent only to the offending client when an action is invalid. |

---

## 5. Session state machine

```
   (TCP connect)
        |
        v
  [HANDSHAKE]  --  public keys exchanged in plaintext
        |
        v
  [AUTH]       --  client sends SIGNUP and/or LOGIN
        |              SIGNUP_RESULT / LOGIN_RESULT
        | (LOGIN_RESULT.ok = true)
        v
  [LOBBY]      --  client sends JOIN_LOBBY
        |          server broadcasts LOBBY_STATE on changes
        |          client may CHOOSE_SEAT and READY repeatedly
        | (all 4 seated and ready)
        v
  [GAME]       --  server sends GAME_START (personalized) to each player
        |          then GAME_STATE after every action
        |
        |   Repeat:
        |     spymaster -> GIVE_CLUE  -> server: CLUE_GIVEN + GAME_STATE
        |     operative -> GUESS_CARD -> server: GUESS_RESULT + GAME_STATE
        |     operative -> END_TURN   -> server: GAME_STATE
        |
        | (assassin guessed OR a team has revealed all its words)
        v
  [GAME OVER]  --  server broadcasts GAME_OVER, then resets to LOBBY
                   (game cleared, ready flags reset)
```

If a player disconnects mid-game, the server aborts the current game
and returns the remaining players to the lobby.

---

## 6. Validation rules (server-side)

The server is authoritative. Every client action is validated against
the rules; a violation produces an `ERROR` message back to the
offending client (not a broadcast). See `server/game.py` for the
exact checks. Highlights:

- The clue is exactly one word (no whitespace) and is not a substring of
  any unrevealed grid word (case-insensitive).
- The number is a non-negative integer; `0` means unlimited guesses.
- It is the correct team's turn and the correct player's role.
- A guess index is in `0..24` and not already revealed.
- The operative may not call `END_TURN` before guessing at least once.
- The operative may not exceed `N + 1` guesses for clue number `N >= 1`.

---

## 7. Security notes

- This protocol is intentionally simple, suitable for a school project.
  It is **not** TLS — there is no certificate validation, no forward
  secrecy, no signed messages.
- The handshake is vulnerable to a classic man-in-the-middle attack
  (an attacker between client and server could substitute their own
  public keys). A real system would solve this with PKI; here it is out
  of scope. The teacher's PDF accepts this trade-off.
- Passwords are sent inside the RSA-encrypted channel and stored on the
  server as `sha256(salt + password)` with a per-user random 16-byte
  salt.
- The server runs on `127.0.0.1` by default; exposing it on a LAN means
  any host on that LAN can attempt logins and could perform the MITM
  attack above.
