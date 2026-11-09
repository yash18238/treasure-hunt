# Treasure Hunt - Quest of the Lost Isle

Mini project (VSEC), Department of Information Technology, NMIET, A.Y. 2026-27
Shreyas Vyawahare (U251E125) and Yash Rathod (U251E131)

A web-based treasure hunt game written in Python (Flask) with an HTML/CSS/JavaScript interface.
Explore a foggy island, collect clues and coins, avoid hidden mud traps, find the golden key and
open the chest before your moves run out. Clear 3 levels to win.

## Run it

    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000 in your browser.

## Controls

| Key | Action |
|-----|--------|
| Arrow keys / W A S D | Move (1 move per step) |
| H | Hint (costs 3 moves) |
| On-screen D-pad | Move on phones and tablets |

## Project structure

    app.py            Flask server and JSON API
    game.py           Game engine: level generator, rules, fog of war, scoring, leaderboard
    templates/        index.html (start screen, game screen, result dialog)
    static/           style.css (UI theme), game.js (board drawing, HUD, keyboard input)
    tests/            test_game.py (8 unit tests)
    leaderboard.json  created automatically when the first game ends

## Run the tests

    python tests/test_game.py

## Optional environment variables

* `TH_SECRET` - Flask session secret (a random one is used if not set)
* `TH_DEBUG=1` - allows a fixed `seed` in /api/new (used only for testing and screenshots)
