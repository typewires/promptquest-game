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

Quests are chosen from a **set of allowed goal types** to keep gameplay reliable:
- The *type* of quest is selected by code from a small list (see “Goal Types” below).
- The AI fills in the *flavor*: names, dialogue, item descriptions, and visual style.

If you don’t specify goals, the game picks them and varies them across levels.

## Goal Types (And Exactly How They’re Selected)

**Allowed goal types** (hard-coded in `game_generator.py`):
- `cure`
- `key_and_door`
- `lost_item`
- `repair_bridge`

### How goal selection works
You have three ways to influence goals:

1. **Select a goal pool (all levels)** — optional UI checkboxes “Goal Pool”
   - Check the goals you want included in this run (ex: only `cure` + `lost_item`).
   - The game will **only sample from the selected pool** across all levels.
   - If you select none, the game samples from all allowed goals.

2. **Implicit goal (Level 1 only)** — inferred from your prompt text
   - If your prompt contains keywords like “sick / cure / heal”, Level 1 becomes `cure`.
   - If your prompt contains “key / door / unlock”, Level 1 becomes `key_and_door`.
   - If your prompt contains “lost / missing / stolen”, Level 1 becomes `lost_item`.
   - If your prompt contains “bridge / repair”, Level 1 becomes `repair_bridge`.

3. **No goal specified** — fully automatic
   - The game samples goals from the allowed list.
   - It avoids repeats **until the pool is exhausted**, then repeats are allowed.

### Are later levels AI-generated goals?
Later levels are **not free-form “invented” by the AI**. Instead:
- Code selects a goal type for each level (using the rules above).
- The AI generates the level’s **content** consistent with that selected goal type (NPC flavor, items, dialogue, look).

## Quest Types (Examples)
Each level picks one quest type (varied across the run):
- `cure`: Collect ingredients, mix a remedy, heal a sick NPC (the NPC sprite swaps to a “healed” version).
- `key_and_door`: Find a chest, open it, get a key, unlock a door.
- `lost_item`: Search the map for a missing item and return it.
- `repair_bridge`: Visit a shop, buy materials (planks/rope/nails) with in‑game money, then repair a broken bridge to reach the objective.

## How To Complete Each Goal

### `cure` (Heal a Sick NPC)
What you’ll see:
- An NPC appears on the map in a “sick” state.
- A few ingredient items appear (collectibles).
- A mixing station appears (interactive).

How to finish:
1. Talk to the NPC (`SPACE`) to learn what’s wrong and what you need.
2. Collect the ingredients by walking over them / interacting (`SPACE`).
3. Use the mixing station (`SPACE`) once you have ingredients.
4. Return to the sick NPC and interact (`SPACE`) to heal them.
5. The NPC sprite swaps to a “healed” version and the quest completes.

### `key_and_door` (Chest → Key → Door)
What you’ll see:
- A closed chest, a locked door, and often a short hint from the NPC.

How to finish:
1. Find and open the chest (`SPACE`).
2. Pick up the key that appears.
3. Go to the door and unlock it (`SPACE`) to finish the level objective.

### `lost_item` (Find and Return)
What you’ll see:
- An NPC missing something.
- A “lost” item somewhere on the map.

How to finish:
1. Talk to the NPC (`SPACE`) to learn what’s missing.
2. Search the map for the item, then pick it up.
3. Return to the NPC and interact to complete the quest.

### `repair_bridge` (Shop → Buy Materials → Repair)
What you’ll see:
- A broken bridge area that blocks traversal.
- An enterable shop selling materials (planks/rope/nails).

How to finish:
1. Enter the shop and buy needed materials (see “Shops + Money” below).
2. Leave the shop and go to the broken bridge.
3. Interact at the bridge (`SPACE`) to repair it (if you have materials).
4. Cross the bridge and finish the level objective.

## Shops + Money
Some levels include enterable buildings (e.g., a shop/inn).
- Your money is shown in the UI.
- In a shop, press `SPACE` to talk to the shopkeeper and see buy instructions.
- Press `1`/`2`/`3` to buy items; the UI updates your remaining money and inventory.

### Entering and leaving buildings
- Approach a building’s **door** from outside.
- Press `SPACE` to enter.
- Inside, press `SPACE` near the door to exit back to the same outdoor map.

### How buying ties into goals
- `repair_bridge` uses the shop to sell required materials.
- Other goal types may still spawn shops (for flavor and future expansion), but `repair_bridge` is the one that currently depends on buying items.

## Repo Layout
- `game_generator.py`: everything (Flask UI + generator + Pygame engine)
- `generated_sprites/`: sprite cache (ignored by git)
- `.env.example`: example environment file (placeholder only)

## Troubleshooting

### `pip install` fails with “externally-managed-environment”
Use the virtualenv steps above (`python3 -m venv .venv` then install inside it).

### Browser shows a blank page
Make sure you’re visiting **HTTP**, not HTTPS:
- Use `http://127.0.0.1:5000` (not `https://...`).

### “Bad Request” in the terminal when you open the page
If you see `Bad request version` logs, it usually means your browser (or an extension) tried to speak **HTTPS** to the local **HTTP** server.
Use `http://127.0.0.1:5000` explicitly.

### Image generation errors (500s / 400s)
If the image API fails, the game may fall back to simple placeholder sprites. Re-run generation or try again later.

## License
MIT (see `LICENSE`).
