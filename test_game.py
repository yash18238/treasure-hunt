import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game import DIFFICULTY, Game, Leaderboard, distances, MAX_LEVEL, TRAP_PENALTY, DIRS


def solve(game):
    """Bot that plays perfectly: start -> key -> chest. Returns the move list."""
    plan, pos = [], game.pos
    for target, blocked in ((game.key_pos, "#X"), (game.chest_pos, "#")):
        dist = distances(game.grid, target, blocked)
        while pos != target:
            for name, (dr, dc) in DIRS.items():
                p = (pos[0] + dr, pos[1] + dc)
                if p in dist and dist[p] < dist[pos]:
                    plan.append(name)
                    pos = p
                    break
    return plan


class GameTests(unittest.TestCase):
    def test_every_level_is_solvable(self):
        for diff in DIFFICULTY:
            for seed in range(40):
                g = Game("T", diff, seed)
                for level in range(1, MAX_LEVEL + 1):
                    for d in solve(g):
                        g.move(d)
                    self.assertIn(g.status, ("level_complete", "won"), (diff, seed, level))
                    if g.status == "level_complete":
                        g.next_level()
                self.assertEqual(g.status, "won")

    def test_locked_chest_blocks_without_key(self):
        g = Game("T", "easy", 1)
        r, c = g.chest_pos
        g.pos = (r, c - 1) if c > 0 else (r, c + 1)
        g.grid[g.pos[0]][g.pos[1]] = "."
        before = g.moves_left
        ev = g.move("right" if c > 0 else "left")
        self.assertEqual(ev[0]["type"], "locked")
        self.assertEqual(g.moves_left, before)
        self.assertEqual(g.status, "playing")

    def test_running_out_of_moves_loses(self):
        g = Game("T", "easy", 3)
        g.moves_left = 1
        for d in DIRS:
            g.move(d)
            if g.status != "playing":
                break
        self.assertEqual(g.status, "lost")

    def test_trap_penalty_and_marked(self):
        g = Game("T", "easy", 5)
        r, c = g.pos
        for dname, (dr, dc) in DIRS.items():
            nr, nc = r + dr, c + dc
            if 0 <= nr < g.n and 0 <= nc < g.n and g.grid[nr][nc] not in "X#":
                g.grid[nr][nc] = "T"
                before = g.moves_left
                g.move(dname)
                self.assertEqual(g.moves_left, before - 1 - TRAP_PENALTY)
                self.assertIn((nr, nc), g.known_traps)
                return
        self.fail("no free neighbour")

    def test_fog_hides_unexplored_tiles(self):
        g = Game("T", "hard", 7)
        pub = g.public()
        self.assertEqual(pub["tiles"][g.chest_pos[0]][g.chest_pos[1]], "?")
        self.assertNotIn("chest", " ".join(pub.keys()))
        self.assertNotIn("T", "".join(pub["tiles"]))

    def test_clues_are_true(self):
        for seed in range(30):
            g = Game("T", "medium", seed)
            r, c = g.chest_pos
            v, h, exact = g.clue_pool
            self.assertIn("ABCDEFGHIJKL"[c], exact)
            mid = (g.n - 1) / 2
            self.assertEqual("NORTHERN" in v, r < mid)
            self.assertEqual("SOUTHERN" in v, r > mid)
            self.assertEqual("WESTERN" in h, c < mid)
            self.assertEqual("EASTERN" in h, c > mid)

    def test_leaderboard_sorted(self):
        with tempfile.TemporaryDirectory() as d:
            lb = Leaderboard(os.path.join(d, "lb.json"))
            lb.add("A", 100, "easy", 1, False)
            lb.add("B", 300, "hard", 3, True)
            lb.add("C", 200, "easy", 2, False)
            self.assertEqual([e["name"] for e in lb.top()], ["B", "C", "A"])

    def test_hint_costs_moves_and_points_right(self):
        g = Game("T", "easy", 2)
        before = g.moves_left
        ev = g.hint()
        self.assertEqual(ev[0]["type"], "hint")
        self.assertEqual(g.moves_left, before - 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
