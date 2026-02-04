# PromptQuest

PromptQuest is a **prompt‑driven, AI‑generated adventure game** (top‑down “RPG‑lite” exploration).

You type a short prompt like “a lantern‑lit seaside town at dusk”, choose how many levels you want, and the game generates:
- A run of **levels** (maps + vibe)
- **Characters** (player + NPCs)
- **Items + interactive props** (doors, chests, keys, shops, etc.)
- A **quest** per level (with a quest log + progress UI)

Under the hood it’s a **Python** project:
- A tiny **Flask** web UI for entering your prompt + key and generating content
- A **Pygame** client that runs the actual game loop and rendering

## Quick Start

1. Create a virtual environment (recommended on macOS/Homebrew because system pip is “externally managed”):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

2. Run the game generator:

```bash
python game_generator.py
```

3. Open the local page (shown in the terminal) and:
- Paste your `OPENAI_API_KEY`
- Enter a prompt
- Choose number of levels (1–6)
- Click **Generate**

Then return to the terminal and press **ENTER** to start playing.

## Controls
- `WASD` / Arrow keys: Move
- `SPACE`: Interact (talk, open, pick up, use)
- `1`, `2`, `3`: Buy options in shops (when you’re inside a shop)
- `R`: Restart / replay the same generated run (after finishing the last level)
- `ESC`: Quit

## What Prompts Change
Prompts primarily influence the **setting and vibe**:
- Terrain style (forest/town/desert/ruins, etc.)
- Time of day (day/sunset/night)
- Themed NPC + item flavor

Quests are chosen from a **set of allowed goal types** to keep gameplay reliable; if you don’t specify a goal, the game picks one and varies it across levels.

## Quest Types (Examples)
Each level picks one quest type (varied across the run):
- `cure`: Collect ingredients, mix a remedy, heal a sick NPC (the NPC sprite swaps to a “healed” version).
- `key_and_door`: Find a chest, open it, get a key, unlock a door.
- `lost_item`: Search the map for a missing item and return it.
- `repair_bridge`: Visit a shop, buy materials (planks/rope/nails) with in‑game money, then repair a broken bridge to reach the objective.

## Shops + Money
Some levels include enterable buildings (e.g., a shop/inn).
- Your money is shown in the UI.
- In a shop, press `SPACE` to talk to the shopkeeper and see buy instructions.
- Press `1`/`2`/`3` to buy items; the UI updates your remaining money and inventory.

## Repo Layout
- `game_generator.py`: everything (Flask UI + generator + Pygame engine)
- `generated_sprites/`: sprite cache (ignored by git)
- `.env.example`: example environment file (placeholder only)

## Security / Keys
- **Do not commit real API keys.**
- This repo ignores `.env` via `.gitignore`.
- `.env.example` contains placeholders (safe to commit).

## Troubleshooting

### `pip install` fails with “externally-managed-environment”
Use the virtualenv steps above (`python3 -m venv .venv` then install inside it).

### Browser shows a blank page
Make sure you’re visiting **HTTP**, not HTTPS:
- Use `http://127.0.0.1:5000` (not `https://...`).

### Image generation errors (500s / 400s)
If the image API fails, the game may fall back to simple placeholder sprites. Re-run generation or try again later.

## License
MIT (see `LICENSE`).
