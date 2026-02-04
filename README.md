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
- Choose number of levels (1–3)
- Click **Generate**

Then return to the terminal and press **ENTER** to start playing.

## Example Prompt (With Per-Level Goals)
Try pasting this into the prompt box:

```
A lantern-lit harbor town at night with wet cobblestone streets, crates by the docks, and a cozy inn.
Level 1: lost_item
Level 2: key_and_door
Level 3: repair_bridge
```

What you’ll typically get (varies run-to-run):
- Level 1 (lost_item): an NPC asks for a missing item; the item is somewhere on the map; return it to finish the level.
- Level 2 (key_and_door): a chest spawns; opening it reveals a key; the key unlocks a door.
- Level 3 (repair_bridge): a broken bridge blocks an area; buy materials in the shop; repair the bridge (visual changes) and cross.

## Controls
- `WASD` / Arrow keys: Move
- `SPACE`: Interact (talk, open, pick up, use)
- `1`, `2`, `3`: Buy options in shops (when you’re inside a shop)
- `R`: Restart / replay the same generated run (after finishing the last level)
- `ESC`: Quit

## What Prompts Change
Prompts primarily influence the **setting and vibe**:
- Terrain style (forest/town/desert/ruins/castle/beach/snow, etc.)
- Time of day (day/dawn/sunset/night)
- Themed NPC + item flavor

Quests are chosen from a **set of allowed goal types** to keep gameplay reliable:
- The *type* of quest is selected by code from a small list (see “Goal Types” below).
- The AI fills in the *flavor*: names, dialogue, item descriptions, and visual style.

If you don’t specify goals, the game picks them and varies them across levels.

### Prompt → Map Matching
The game uses a mix of:
- AI output (terrain type/features returned by the world JSON)
- A prompt “hint extractor” (keyword-based) to strongly align the map with your prompt

If your prompt clearly implies a biome/time (e.g. “desert oasis at night”, “harbor town”, “ruined temple”), the generator will bias/override the terrain/time-of-day and add themed decor so the level looks distinct and on-theme.

### Are levels infinite?
The generator has **finite, hard-coded map building blocks** (biomes, time-of-day palettes, and layout styles), but you can mix-and-match them with your prompt for lots of variety.

What’s fixed (finite sets):
- **Biomes (terrain types)**: `meadow`, `forest`, `town`, `beach`, `snow`, `desert`, `ruins`, `castle`
- **Time of day** (affects palette + lighting): `day`, `dawn`, `sunset`, `night`
- **Layout styles** (big structural differences):
  - `winding_road`, `crossroads`, `ring_road`, `plaza`, `market_street`
  - `coastline`, `riverbend`, `islands`, `oasis`, `lake_center`
  - `maze_grove`, `ruin_ring`

What’s flexible (varies widely):
- Where paths/water/trees/rocks/etc. are placed (seeded per level)
- NPC/item flavor text + AI-generated sprites

### Theme Decor You Might See
Based on prompt keywords + biome, the map renderer can add extra themed decor such as:
- Desert: **cacti**, oasis-like water layouts
- Beach/harbor prompts: **shells**, coastline water bands, crates near paths
- Snow: **snow piles**
- Town/market/bazaar/port/harbor: **crates** and busier street layouts (`market_street`)
- Ruins/temple/castle: **statues** and **vines**, ruin-like layouts (`ruin_ring`)
- Forest + night/mushroom vibe: **mushrooms**

## Goal Types (And Exactly How They’re Selected)

**Allowed goal types** (hard-coded in `game_generator.py`):
- `cure`
- `key_and_door`
- `lost_item`
- `repair_bridge`

### How goal selection works (UI + prompt directives)
This version supports **up to 3 levels** per run.

You have three ways to influence goals:

1. **Per-level goal options (UI checkboxes)** — “Goals (per level, optional)”
   - Each level has its own set of goal checkboxes.
   - If you check multiple goals under a level, that level will **randomly pick one** of the checked goals (this is “stacking options”, not multi-quests).
   - If you leave a level blank, it will be randomized from all allowed goals.
   - The generator tries to **avoid repeating** the same goal type across levels when possible.

2. **Per-level explicit goals (inside your prompt)** — takes precedence
   - You can force goals with text like:
     - `Level 1: cure`
     - `Level 2: key_and_door`
     - `Level 3: repair_bridge`
   - “Takes precedence” means: if you specify a goal for a level in the prompt, that level will use it even if you clicked different goals in the UI.

3. **Implicit goal (Level 1 only)** — inferred from your prompt text
   - If Level 1 isn’t explicitly set, the game may infer it from keywords:
     - “sick / cure / heal” → `cure`
     - “key / door / unlock” → `key_and_door`
     - “lost / missing / stolen” → `lost_item`
     - “bridge / repair” → `repair_bridge`
   - Inference is only used when it makes sense for the level’s available options.

### Prompt Directive Syntax (All Levels)
You can explicitly set goals for any of the supported levels by writing these lines anywhere in your prompt:
- `Level 1: cure | key_and_door | lost_item | repair_bridge`
- `Level 2: cure | key_and_door | lost_item | repair_bridge`
- `Level 3: cure | key_and_door | lost_item | repair_bridge`

These are optional. If you omit a level directive, that level’s goal will be chosen from your UI selections (or randomized if left blank).

## Cost / Quality Settings
The generator UI has a **Quality** dropdown:
- **Low (cheapest)**: `TEXT_MODEL=gpt-4o-mini`, `IMAGE_MODEL=gpt-image-1` with `quality=low`
- **Medium (default)**: `TEXT_MODEL=gpt-4o-mini`, `IMAGE_MODEL=gpt-image-1` with `quality=medium`
- **High (best)**: `TEXT_MODEL=gpt-4o`, `IMAGE_MODEL=gpt-image-1` with `quality=high`

### What the dropdown actually changes
- The dropdown is sent to the backend as `quality` in the `/generate` request.
- The server sets:
  - `Config.TEXT_MODEL` (for world/quest/dialogue JSON)
  - `Config.IMAGE_QUALITY` (for `gpt-image-1` sprite generation)

### Sprite reuse (fewer image calls)
To reduce cost within a multi-level run:
- The **player sprite** is reused across all levels (consistent protagonist).
- The **shop** and **inn** NPC sprites are generated once and reused across levels.

### Sprite caching (disk)
Sprite images are cached on disk so reruns can be much cheaper.
- Cache directory: `generated_sprites/`
- Cache key includes: image model, image quality, sprite role, and the prompt text for that sprite.
- If a cache hit exists, the game loads the `.png` from disk and skips the OpenAI image call.

Note: `generated_sprites/` is ignored by git by default (it’s a local cache).

## Pre-Generating Core Sprites (Ship With GitHub)
If you want to keep costs low for users, you can “bake” a set of core sprites once at **High** quality and commit them to the repo.

What gets baked (recommended):
- Shopkeeper + Innkeeper NPC sprites (`npc_shop`, `npc_inn`)
- Core props: `chest`, `key`, `door`, `mix_station`
- Bridge material icons: `mat_planks`, `mat_rope`, `mat_nails`
- A generic item icon used when item-sprite budget is low: `item_generic`

### Bake command
From the repo root:

```bash
export OPENAI_API_KEY="sk-..."
python game_generator.py --bake-core --quality high
```

This writes PNGs to `assets/sprites/` and a `assets/sprites/manifest.json`.

### Commit and push baked sprites
```bash
git add assets/sprites
git commit -m "Add baked core sprites"
git push
```

When `assets/sprites/` contains baked sprites, the game will automatically load and reuse them instead of calling image generation for those keys.

## Quest Types (Examples)
Each level picks one quest type (varied across the run):
- `cure`: Collect ingredients, mix a remedy, heal a sick NPC (NPC starts with a “sick” sprite and swaps to a “healed” sprite on completion).
- `key_and_door`: Find a chest, open it, get a key, unlock a door.
- `lost_item`: Search the map for a missing item and return it.
- `repair_bridge`: Visit a shop, buy materials (bridge planks/rope/nails) with in‑game money, then repair a broken bridge (visual changes from broken → fixed) to reach the objective.

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

### Inn Sleeping (Time Change)
The inn is also interactive:
- Walk up to a bed and press `SPACE` to rent a bed (costs gold).
- When you exit back outside, time toggles (`day ↔ night`) and the map palette updates.

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
