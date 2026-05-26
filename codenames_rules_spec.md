# Codenames — Game Rules Specification

This document describes the complete rules of the word-association game **Codenames** in a form suitable as a specification for implementing the game in Python. It is written for the standard 4-player configuration (two teams of two).

---

## 1. Game Overview

Codenames is a word-association party game. Two teams compete to be the first to identify all of their secret words on a shared 5×5 grid of word cards. One player on each team (the **Spymaster**) knows which words belong to which team and gives single-word clues to help their teammate (the **Operative**) guess them. The clue-giver knows the secret identities; the guesser does not. The grid also contains words belonging to the opposing team, neutral words, and one fatal word called the **Assassin** — guessing the Assassin causes an instant loss.

---

## 2. Players and Roles

The game is played by exactly **4 players**, divided into **2 teams of 2**:

- **Red team** = 1 Spymaster + 1 Operative
- **Blue team** = 1 Spymaster + 1 Operative

Each team has the following two roles:

| Role | Knows secret identities? | Action each turn |
|---|---|---|
| **Spymaster** | Yes — sees the full Key Card | Gives a one-word clue and a number |
| **Operative** | No — sees only the words | Guesses words on the grid based on the clue |

Spymasters from both teams sit on the same side of the table and share the same Key Card; Operatives sit opposite and see only the word grid (without the color overlay).

---

## 3. Components

The game requires the following components (these map directly to data structures in implementation):

### 3.1 Word Cards
- A pool of word cards, each containing a single word or short phrase (the original game uses ~400 words).
- For each game, **25 words are randomly selected** and arranged in a **5×5 grid**.

### 3.2 Key Card (Map Card)
- A 5×5 grid corresponding to the layout of the word cards.
- Each of the 25 cells is colored as one of four types:
  - **Red** — belongs to the Red team
  - **Blue** — belongs to the Blue team
  - **Neutral** (tan/beige) — belongs to no one (a "bystander")
  - **Assassin** (black) — instant-loss word
- The Key Card also indicates which team starts (see §3.3).

### 3.3 Card Distribution
For each game the 25 cards are distributed exactly as follows:

| Card type | Count |
|---|---|
| Starting team's words | **9** |
| Second team's words | **8** |
| Neutral words | **7** |
| Assassin | **1** |
| **Total** | **25** |

The **starting team** is determined by the Key Card itself (each Key Card has colored borders on two edges indicating which team begins). In an implementation, the starting team can be randomly selected, and that team is assigned 9 words while the other team is assigned 8.

### 3.4 Cover Cards
When an Operative guesses a word, a cover card matching the word's true color is placed on top of it, revealing its identity to everyone and marking it as already-guessed. Implementation: each word card has a `revealed` flag and, once revealed, displays its color.

---

## 4. Setup

1. Randomly draw 25 word cards from the word pool and arrange them face-up in a 5×5 grid.
2. Randomly generate a Key Card with the distribution from §3.3:
   - 9 cells for the starting team
   - 8 cells for the other team
   - 7 neutral cells
   - 1 Assassin cell
   - Cells are shuffled into a random 5×5 arrangement.
3. Determine the starting team (random or from the Key Card border).
4. Each team chooses its Spymaster and Operative.
5. Show the Key Card only to the two Spymasters. The Operatives see only the words.
6. Score: each team's score starts at 0; the target score equals the number of agents that team must find (9 for the starting team, 8 for the other team).

---

## 5. Game Flow

Play alternates between the two teams, starting with the team that has 9 words. Each turn consists of two phases: **the Spymaster gives a clue**, then **the Operative makes guesses**.

### 5.1 Turn Structure (high level)

```
While no team has won and the Assassin has not been revealed:
    Current team's Spymaster gives a clue (word, number)
    Current team's Operative makes one or more guesses
    Turn ends (either voluntarily, by hitting the guess limit, or by guessing a non-team word)
    If the game has not ended, pass turn to the other team
```

### 5.2 Spymaster's Clue

On their team's turn, the Spymaster gives a clue consisting of:

1. **Exactly one word** (a single English word — see §6 for full restrictions).
2. **A non-negative integer N**, indicating how many words on the grid relate to the clue.

Example: `"Animal 3"` means "I am pointing at 3 words on the grid that all relate to 'animal'."

The number N tells the Operative how many of the team's still-unrevealed words the Spymaster intends to point to with this clue. The Operative may then guess up to **N + 1** words this turn (the "+1" represents previously unused guesses, and is always allowed regardless of N — including special cases described in §6.3).

### 5.3 Operative's Guessing

After receiving the clue, the Operative:

1. Selects an unrevealed word on the grid and announces it as their guess.
2. The Spymaster (or system) reveals the word's true color:
   - **Own team's color** → the word is correctly identified. A team-colored cover card is placed on it. The Operative may either **continue guessing** (up to the N+1 limit) or **stop voluntarily** and end the turn.
   - **Neutral** → cover with neutral marker. **Turn ends immediately.**
   - **Opposing team's color** → cover with opposing team's color. **Turn ends immediately.** The opposing team gets credit for that word (it counts toward their win condition).
   - **Assassin** → cover with the Assassin marker. The current team **loses the game immediately**.
3. The Operative is required to make **at least one guess** per turn (they cannot pass without guessing at all), unless they have already guessed at least once this turn — in which case stopping is allowed.
4. The Operative cannot guess a word that has already been revealed.

### 5.4 Turn-end Conditions

A turn ends as soon as **any** of the following occurs:

- The Operative guesses a word that is not their team's color (neutral or opposing).
- The Operative guesses the Assassin (game also ends — see §7).
- The Operative voluntarily stops guessing after having made at least one guess this turn.
- The Operative reaches the guess limit of **N + 1** for this clue.

After the turn ends (if the game is not over), play passes to the other team.

---

## 6. Clue Rules (Detailed)

The Spymaster's clue must follow strict rules. The implementation should validate these (and/or rely on an honor system, depending on the implementation choice):

### 6.1 Form of the Clue

- The clue must be **exactly one word**.
- The clue must be given together with a **number**.
- The clue word must **not be**, or contain, any of the words currently visible (unrevealed) on the grid. Revealed words are allowed to appear inside clues.
  - Example: if `BREAK` is on the grid, the Spymaster cannot give `BREAKFAST` or `BREAK` as a clue.
- The clue must relate to the **meaning** of the target words, not to their **spelling, letters, length, or position** on the board.
  - Disallowed: "Starts with B, 3", "Rhymes with cat, 2", "Top-row, 2".
- Proper nouns are generally allowed (table consensus); abbreviations and acronyms are allowed if pronounceable as a word; compound words written as one word are allowed.

### 6.2 Number Rules

The number N may be:

- A **positive integer** (typically 1–9). The Operative may guess up to N + 1 words.
- **Zero** (`0` or "unlimited"): special clue meaning "this clue relates to none of your remaining words; do not guess anything related to it." When N = 0, the Operative may guess **any number of words** (no upper bound besides remaining unrevealed words). This is used defensively to steer the Operative away from a dangerous word.
- **Infinity / "Unlimited"**: same effect as 0 — unlimited guesses. (Some rule variants combine these; the implementation may simply support `0` as "unlimited.")

### 6.3 Guess Limits Summary

| Clue number | Max guesses this turn |
|---|---|
| N ≥ 1 | N + 1 |
| 0 / unlimited | unlimited (until turn ends by miss or voluntary stop) |

### 6.4 Disallowed Clues (examples)

- `"Cat-like, 2"` — hyphenated multi-word phrases are not allowed (one word only).
- `"Sounds like X, 1"` — sound/spelling-based clues are forbidden.
- A clue word identical to or contained in an unrevealed grid word.
- Any clue referencing positions on the board ("the two on the left").

The implementation may enforce these to varying degrees; at minimum, it should check that:

- The clue is a single token (no spaces).
- The clue is not a substring of, or superstring of, any unrevealed grid word (case-insensitive). A stricter check may also enforce no shared word stems.

---

## 7. End of Game

The game ends as soon as **any** of the following occurs:

1. **A team identifies all of its words** → that team **wins**.
   - Starting team needs all 9 of its words revealed.
   - Other team needs all 8 of its words revealed.
2. **The Assassin is guessed** → the team that guessed it **loses immediately**, and the other team wins.

Note that a team can win on the opposing team's turn: if the opposing Operative accidentally guesses one of your team's words and that completes your set, your team wins.

---

## 8. Suggested Data Model (for implementation)

This section is non-normative; it sketches data structures a Python implementation might use.

```python
from enum import Enum
from dataclasses import dataclass, field

class Team(Enum):
    RED = "red"
    BLUE = "blue"

class CardType(Enum):
    RED = "red"
    BLUE = "blue"
    NEUTRAL = "neutral"
    ASSASSIN = "assassin"

@dataclass
class Card:
    word: str
    type: CardType
    revealed: bool = False

@dataclass
class Clue:
    word: str
    number: int  # 0 means unlimited

@dataclass
class GameState:
    board: list[Card]                  # length 25, indexed 0..24 (row-major 5x5)
    starting_team: Team
    current_team: Team
    current_clue: Clue | None = None
    guesses_made_this_turn: int = 0
    winner: Team | None = None
    history: list = field(default_factory=list)  # log of clues and guesses
```

### 8.1 Core Operations

- `new_game(word_pool, seed=None) -> GameState` — sample 25 words, build Key Card, set starting team.
- `give_clue(state, clue: Clue) -> None` — validate clue (§6) and store it; reset guess counter.
- `make_guess(state, card_index: int) -> GuessResult` — reveal the card, update score, decide whether turn continues or ends; if Assassin or all team-words revealed, set winner.
- `end_turn(state) -> None` — Operative voluntarily ends the turn (only legal after at least one guess this turn).
- `is_game_over(state) -> bool` and `winner(state) -> Team | None`.

### 8.2 Validation Responsibilities

- Clue word does not appear (whole-word or substring, case-insensitive) in any unrevealed grid word.
- Clue is a single token (no whitespace).
- Number is a non-negative integer.
- Guess index points to an unrevealed card.
- Operative cannot end the turn before guessing at least once.
- Operative cannot exceed the guess limit (`N + 1` for `N ≥ 1`; unbounded for `N = 0`).

### 8.3 Information Hiding

- Spymasters can call a function like `get_spymaster_view(state, team) -> Board` that returns words plus their `CardType`.
- Operatives call `get_operative_view(state) -> Board` that returns words and, for revealed cards only, their type.
- The implementation must never leak unrevealed `CardType` to the Operative-facing interface.

---

## 9. Edge Cases and Clarifications

- **Spymasters cannot communicate** anything to their Operative besides the clue word and number (no facial expressions, hints, gestures). In a digital implementation this is enforced by the interface.
- A word counted by a clue does not have to be guessed this turn — the Operative may stop early, and the same target words can be hinted at again in a future turn with a different clue.
- An Operative may guess a word **not** related to the current clue if they reason it was hinted at in a previous turn ("the +1 guess" is often used this way).
- Repeating the same clue word exactly is generally disallowed in the same game; variants of the word (different stems or forms) are also typically disallowed by table consensus.
- If a team runs out of all of its words because the **opposing** Operative guessed them, that team still wins.
- When `N = 0` (unlimited), the Operative still must guess at least one word before ending the turn voluntarily, and the turn still ends on any wrong guess.

---

## 10. Suggested Order of Implementation

For a Python implementation, the following milestones are a sensible build order:

1. **Word pool + board generation** — load words, sample 25, generate Key Card with proper distribution.
2. **Game state + view filtering** — implement `GameState` with separate Spymaster and Operative views.
3. **Turn engine** — `give_clue`, `make_guess`, `end_turn`, with full guess-limit and turn-ending logic.
4. **Clue validator** — single-token check, substring check against unrevealed words.
5. **End-game detection** — win/loss on every guess.
6. **Player interfaces** — CLI or web UI for each of the 4 roles, respecting information hiding.
7. **(Optional) AI players** — automated Spymaster (semantic similarity over a word embedding to find clues that link own words and avoid opponent / neutral / Assassin words) and automated Operative (semantic similarity ranking unrevealed words against the clue).

---

*End of specification.*
