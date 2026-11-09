"""
game.py - Core logic of the Treasure Hunt game (no web code in this file).

The island is a square grid. The player must:
    1. find the hidden KEY,
    2. then open the locked CHEST before the moves run out.
Along the way there are coins, clue scrolls, boulders and hidden mud traps.
Only tiles the player has explored are ever sent to the browser (fog of war),
so the treasure position cannot be discovered by inspecting network traffic.
"""
import json
import os
import random
import threading
from collections import deque
from datetime import datetime

DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}

# vision = how many tiles around the player are revealed
DIFFICULTY = {
    "easy":   {"size": 8,  "rock": 0.10, "traps": 3, "slack": 2.4, "vision": 2},
    "medium": {"size": 10, "rock": 0.16, "traps": 5, "slack": 2.0, "vision": 1},
    "hard":   {"size": 12, "rock": 0.20, "traps": 8, "slack": 1.7, "vision": 1},
}
MAX_LEVEL = 3
TRAP_PENALTY = 3      # moves lost when stepping on a mud trap
HINT_COST = 3         # moves lost when asking for a hint
COINS_PER_LEVEL = 5
SCROLLS_PER_LEVEL = 3
COL_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# tile codes: "." floor  "#" boulder  "C" coin  "S" scroll  "K" key
#             "X" chest  "T" mud trap (hidden until stepped on)  "?" unexplored


def distances(grid, src, blocked="#X"):
    """Breadth-first search: shortest step count from src to every reachable tile."""
    n = len(grid)
    dist = {src: 0}
    queue = deque([src])
    while queue:
        r, c = queue.popleft()
        for dr, dc in DIRS.values():
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n and (nr, nc) not in dist \
                    and grid[nr][nc] not in blocked:
                dist[(nr, nc)] = dist[(r, c)] + 1
                queue.append((nr, nc))
    return dist


def generate_level(level, difficulty, rng):
    """Build a random island that is always solvable (start -> key -> chest)."""
    cfg = DIFFICULTY[difficulty]
    n = cfg["size"] + level - 1
    traps = cfg["traps"] + level - 1
    for _ in range(1000):
        grid = [["#" if rng.random() < cfg["rock"] else "." for _ in range(n)]
                for _ in range(n)]
        start = rng.choice([(0, 0), (0, n - 1), (n - 1, 0), (n - 1, n - 1)])
        grid[start[0]][start[1]] = "."

        # place the chest far from the start
        dist = distances(grid, start, blocked="#")
        far = [p for p, d in dist.items() if d >= n]
        if not far:
            continue
        chest = rng.choice(far)
        grid[chest[0]][chest[1]] = "X"

        # the key must be reachable WITHOUT passing through the locked chest
        dist = distances(grid, start)
        mid = [p for p, d in dist.items() if d >= n // 2 and p != start]
        if not mid:
            continue
        key = rng.choice(mid)
        key_dist = distances(grid, key)
        near_chest = [key_dist[(chest[0] + dr, chest[1] + dc)]
                      for dr, dc in DIRS.values()
                      if (chest[0] + dr, chest[1] + dc) in key_dist]
        if not near_chest:
            continue

        spots = [p for p in dist if p not in (start, key)]
        need = COINS_PER_LEVEL + SCROLLS_PER_LEVEL + traps
        if len(spots) < need:
            continue
        rng.shuffle(spots)
        grid[key[0]][key[1]] = "K"
        idx = 0
        for code, count in (("C", COINS_PER_LEVEL), ("S", SCROLLS_PER_LEVEL), ("T", traps)):
            for _ in range(count):
                r, c = spots[idx]
                grid[r][c] = code
                idx += 1

        path = dist[key] + min(near_chest) + 1
        slack = cfg["slack"] - 0.15 * (level - 1)
        moves = int(path * slack) + 6
        return {"grid": grid, "n": n, "start": start, "key": key,
                "chest": chest, "moves": moves, "path": path}
    raise RuntimeError("could not generate a level")


def make_clues(chest, n):
    """Three truthful clues about the chest position (revealed one per scroll)."""
    r, c = chest
    mid = (n - 1) / 2
    if r < mid:
        v = "The chest is buried in the NORTHERN half of the island."
    elif r > mid:
        v = "The chest is buried in the SOUTHERN half of the island."
    else:
        v = "The chest lies on the MIDDLE row of the island."
    if c < mid:
        h = "The chest is hidden in the WESTERN half of the island."
    elif c > mid:
        h = "The chest is hidden in the EASTERN half of the island."
    else:
        h = "The chest lies in the MIDDLE column of the island."
    exact = "Follow column %s - the chest is somewhere along it." % COL_LABELS[c]
    return [v, h, exact]


class Leaderboard:
    """Stores the best scores in a small JSON file (thread-safe)."""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return []

    def top(self, count=10):
        with self._lock:
            return self._read()[:count]

    def add(self, name, score, difficulty, level, won):
        entry = {"name": name, "score": score, "difficulty": difficulty,
                 "level": level, "won": won,
                 "date": datetime.now().strftime("%d %b %Y")}
        with self._lock:
            data = self._read()
            data.append(entry)
            data.sort(key=lambda e: e["score"], reverse=True)
            data = data[:10]
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return data.index(entry) + 1 if entry in data else None


class Game:
    def __init__(self, name, difficulty="medium", seed=None):
        self.name = name
        self.difficulty = difficulty
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.level = 1
        self.score = 0
        self.steps = 0
        self.status = "playing"   # playing | level_complete | won | lost
        self.recorded = False
        self.last_bonus = 0
        self._start_level()

    # ---- level set-up ---------------------------------------------------
    def _start_level(self):
        rng = random.Random(self.seed * 31 + self.level)
        data = generate_level(self.level, self.difficulty, rng)
        self.grid = data["grid"]
        self.n = data["n"]
        self.pos = data["start"]
        self.key_pos = data["key"]
        self.chest_pos = data["chest"]
        self.moves_total = self.moves_left = data["moves"]
        self.has_key = False
        self.coins = 0
        self.clue_pool = make_clues(self.chest_pos, self.n)
        self.clues = []
        self.known_traps = set()
        self.revealed = set()
        self.vision = DIFFICULTY[self.difficulty]["vision"]
        self.status = "playing"
        self._reveal()

    def next_level(self):
        if self.status == "level_complete":
            self.level += 1
            self._start_level()

    def _reveal(self):
        r0, c0 = self.pos
        for r in range(r0 - self.vision, r0 + self.vision + 1):
            for c in range(c0 - self.vision, c0 + self.vision + 1):
                if 0 <= r < self.n and 0 <= c < self.n:
                    self.revealed.add((r, c))

    # ---- actions --------------------------------------------------------
    def move(self, direction):
        """Try to move one tile. Returns a list of event dicts for the UI."""
        if self.status != "playing" or direction not in DIRS:
            return []
        dr, dc = DIRS[direction]
        r, c = self.pos[0] + dr, self.pos[1] + dc
        if not (0 <= r < self.n and 0 <= c < self.n):
            return [{"type": "blocked", "text": "Deep ocean ahead - you cannot swim that far!"}]
        tile = self.grid[r][c]
        if tile == "#":
            return [{"type": "blocked", "text": "A huge boulder blocks your path."}]
        if tile == "X" and not self.has_key:
            return [{"type": "locked", "text": "The chest is locked! Find the key first."}]

        self.pos = (r, c)
        self.moves_left -= 1
        self.steps += 1
        events = []
        if tile == "C":
            self.coins += 1
            self.score += 10
            self.grid[r][c] = "."
            events.append({"type": "coin", "text": "+10  You found a gold coin!"})
        elif tile == "S":
            clue = self.clue_pool[len(self.clues)]
            self.clues.append(clue)
            self.score += 5
            self.grid[r][c] = "."
            events.append({"type": "scroll", "text": "+5  Clue found: " + clue})
        elif tile == "K":
            self.has_key = True
            self.score += 20
            self.grid[r][c] = "."
            events.append({"type": "key", "text": "+20  You picked up the golden key!"})
        elif tile == "T":
            self.moves_left = max(0, self.moves_left - TRAP_PENALTY)
            self.known_traps.add((r, c))
            self.grid[r][c] = "."
            events.append({"type": "trap", "text": "Mud trap! You lose %d moves." % TRAP_PENALTY})
        self._reveal()

        if tile == "X":
            self.last_bonus = 100 * self.level + self.moves_left * 3
            self.score += self.last_bonus
            self.status = "won" if self.level == MAX_LEVEL else "level_complete"
            events.append({"type": "chest", "text": "You opened the treasure chest!"})
        elif self.moves_left <= 0:
            self.status = "lost"
            events.append({"type": "lost", "text": "You ran out of moves."})
        return events

    def hint(self):
        """Point towards the next objective (key, then chest) for a small price."""
        if self.status != "playing":
            return []
        if self.moves_left <= HINT_COST:
            return [{"type": "blocked", "text": "Not enough moves left to buy a hint."}]
        target = self.chest_pos if self.has_key else self.key_pos
        dist = distances(self.grid, target, blocked="#" if target == self.chest_pos else "#X")
        best, best_d = None, None
        for name, (dr, dc) in DIRS.items():
            p = (self.pos[0] + dr, self.pos[1] + dc)
            if p in dist and (best_d is None or dist[p] < best_d):
                best, best_d = name, dist[p]
        if self.pos == target or best is None:
            return []
        self.moves_left -= HINT_COST
        return [{"type": "hint", "dir": best,
                 "text": "Hint (-%d moves): head %s." % (HINT_COST, best.upper())}]

    # ---- information for the browser -----------------------------------
    def hot_cold(self):
        d = abs(self.pos[0] - self.chest_pos[0]) + abs(self.pos[1] - self.chest_pos[1])
        percent = round(100 * (1 - d / (2 * (self.n - 1))))
        if percent >= 85:
            label = "Burning hot!"
        elif percent >= 70:
            label = "Hot"
        elif percent >= 55:
            label = "Warm"
        elif percent >= 40:
            label = "Cool"
        else:
            label = "Freezing"
        return {"label": label, "percent": percent}

    def public(self):
        """State sent to the browser. Unexplored tiles are hidden as '?'."""
        rows = []
        for r in range(self.n):
            row = ""
            for c in range(self.n):
                if (r, c) not in self.revealed:
                    row += "?"
                elif (r, c) in self.known_traps:
                    row += "T"
                else:
                    ch = self.grid[r][c]
                    row += "." if ch == "T" else ch
            rows.append(row)
        return {
            "name": self.name, "difficulty": self.difficulty,
            "level": self.level, "max_level": MAX_LEVEL,
            "score": self.score, "moves_left": self.moves_left,
            "moves_total": self.moves_total, "size": self.n,
            "pos": list(self.pos), "vision": self.vision, "tiles": rows,
            "has_key": self.has_key, "coins": self.coins,
            "coins_total": COINS_PER_LEVEL, "clues": self.clues,
            "status": self.status, "hot": self.hot_cold(),
            "bonus": self.last_bonus, "steps": self.steps,
            "col_labels": COL_LABELS[:self.n],
        }
