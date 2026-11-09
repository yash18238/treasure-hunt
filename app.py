"""app.py - Flask web server for the Treasure Hunt game."""
import os
import re
import uuid

from flask import Flask, jsonify, render_template, request, session

from game import DIFFICULTY, Game, Leaderboard

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = os.environ.get("TH_SECRET", os.urandom(24))
board = Leaderboard(os.path.join(BASE, "leaderboard.json"))
GAMES = {}                       # game id -> Game (kept in server memory)
MAX_GAMES = 500


def current_game():
    return GAMES.get(session.get("gid"))


def reply(game, events=None):
    """Build the JSON reply; save the score to the leaderboard once the game ends."""
    state = game.public()
    state["events"] = events or []
    finished = game.status in ("won", "lost")
    if finished and not game.recorded:
        game.recorded = True
        state["rank"] = board.add(game.name, game.score, game.difficulty,
                                  game.level, game.status == "won")
    if finished or game.status == "level_complete":
        state["leaderboard"] = board.top(5)
    return jsonify(state)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/leaderboard")
def leaderboard():
    return jsonify(board.top(5))


@app.route("/api/new", methods=["POST"])
def new_game():
    data = request.get_json(silent=True) or {}
    name = re.sub(r"[^\w .-]", "", str(data.get("name", "")))[:16].strip() or "Explorer"
    difficulty = data.get("difficulty")
    if difficulty not in DIFFICULTY:
        difficulty = "medium"
    seed = None
    if os.environ.get("TH_DEBUG") and isinstance(data.get("seed"), int):
        seed = data["seed"]          # fixed seeds are only allowed in debug mode
    if len(GAMES) >= MAX_GAMES:
        GAMES.pop(next(iter(GAMES)))
    gid = uuid.uuid4().hex
    GAMES[gid] = Game(name, difficulty, seed)
    session["gid"] = gid
    return reply(GAMES[gid])


@app.route("/api/state")
def state():
    game = current_game()
    if not game:
        return jsonify({"error": "no game"}), 404
    return reply(game)


@app.route("/api/move", methods=["POST"])
def move():
    game = current_game()
    if not game:
        return jsonify({"error": "no game"}), 404
    direction = (request.get_json(silent=True) or {}).get("dir")
    return reply(game, game.move(direction))


@app.route("/api/hint", methods=["POST"])
def hint():
    game = current_game()
    if not game:
        return jsonify({"error": "no game"}), 404
    return reply(game, game.hint())


@app.route("/api/next", methods=["POST"])
def next_level():
    game = current_game()
    if not game:
        return jsonify({"error": "no game"}), 404
    game.next_level()
    return reply(game)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
