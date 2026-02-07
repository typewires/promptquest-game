# PromptQuest (Work in Progress..)

PromptQuest is an AI-driven content generator whose output is a playable mini-RPG. The game is not the product — it exists to validate the generator. Each generated game is a test harness proving the system works. The focus is the generation pipeline and its properties: reliability, controllability, and cost-aware iteration from an underspecified prompt.

**What this project is:** An AI-first generator that converts a single text prompt into a complete, playable adventure run (maps, quests, dialogue, sprites). It combines procedural generation, LLM-generated narrative, and image generation into one cost-aware, cache-backed pipeline designed to be reproducible per run and cheaper on reruns.

**What this project is not:** A handcrafted game, a full RPG engine, or a showcase of deep level design or long-form progression.

In practice, you type a short prompt like *"a lantern-lit seaside town at dusk"*, choose how many levels you want (1–3), and the generator produces levels (maps + vibe), characters (player + NPCs), items and interactive props, and a goal stack per level with progress UI.

Under the hood it's a **Python** project: a tiny **Flask** web UI for entering your prompt + key and generating content, plus a **Pygame** client that runs the actual game loop and rendering.

---

## Quick Start

```bash
# 1. Create a virtual environment (recommended, required on macOS/Homebrew)
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# 2. Run the generator
python game_generator.py
```

Open the local page shown in the terminal (`http://127.0.0.1:5000`), paste your `OPENAI_API_KEY`, enter a prompt, choose number of levels, and click **Generate**. Then return to the terminal and press **ENTER** to start playing.

## Controls

| Key | Action |
|---|---|
| `WASD` / Arrow keys | Move |
| `SPACE` | Interact (talk, open, pick up, use, enter/exit buildings) |
| `1` / `2` / `3` | Buy items in shops |
| `N` / `ENTER` | Next level (after objective complete) |
| `R` | Restart / replay the same run (after finishing) |
| `ESC` | Quit |

---

## How Generation Works

Each level is produced in three layers:

| Layer | Source | What your prompt affects |
|---|---|---|
| **Map** | Procedural (code + seed) | Biome, time of day, layout style, themed decor |
| **Goals** | Fixed goal system (sampled or specified) | Goal stack per level via UI or prompt directives |
| **Story + Sprites** | AI (text + image) with caching and baked assets | Character/item names, dialogue, visual style |

### Prompt → Map Matching

The generator uses AI output plus a keyword-based "hint extractor" to align maps with your prompt. If your prompt implies a biome/time (e.g. *"desert oasis at night"*, *"ruined temple"*), the generator biases terrain, time-of-day palette, and themed decor accordingly.

**Themed decor examples:** desert → cacti, oasis water; beach/harbor → shells, coastline, crates; snow → snow piles; town/market/port → crates, `market_street` layout; ruins/temple/castle → statues, vines, `ruin_ring` layout; forest + night → mushrooms.

### What's Reused vs. Generated Fresh

| Reused across levels (cost saving) | New every run |
|---|---|
| Player sprite, shopkeeper/innkeeper sprites, baked core sprites (shop/inn NPCs, princess cure pair, key props) | Maps, placements, quest text, NPC names, some item sprites (depending on Quality) |

**Sprite load order** (fastest to slowest): baked `assets/sprites/` → local disk cache `generated_sprites/` → image API.

---

## Controlling Your Run

You have three surfaces for control — **prompt directives**, **UI controls**, and **implicit inference** — with a clear precedence: prompt directive > UI selection > inferred from prompt keywords > random.

### Biomes

Supported biomes: `meadow`, `forest`, `town`, `beach`, `snow`, `desert`, `ruins`, `castle`.

Set per level via UI dropdown or prompt directive (`Level N Biome: snow`). Unspecified levels get a random biome.

### Goals

Allowed goal types: `cure`, `key_and_door`, `lost_item`, `repair_bridge`.

**Three ways to set goals per level:**

1. **Prompt directives** (highest priority): `Level 1: cure` or `Level 2: cure, lost_item` (stacked).
2. **UI checkboxes**: Check one or more goals per level. Multiple checked goals are stacked.
3. **Implicit inference** (for unspecified levels): Keywords in your prompt text may trigger goals — "sick/cure/heal" → `cure`, "key/door/unlock" → `key_and_door`, "lost/missing/stolen" → `lost_item`, "bridge/repair" → `repair_bridge`.

If nothing is specified for a level, the generator picks a random valid goal stack, trying to avoid repeating the same goal type across levels.

### Time of Day and Character Style

- `Level N Time: day | dawn | sunset | night`
- `Hero look: ...` (applies to all levels)
- `Level N Quest NPC style: ...` (affects the primary quest NPC for that level only, not shopkeeper/innkeeper)

Global directives (no level number) default to Level 1. Levels 2/3 randomize unless explicitly set.

### Prompt Directive Reference

```text
Level 1: cure                          # goal
Level 2: cure, lost_item               # stacked goals
Level 1 Biome: snow                    # biome
Level 2 Time: dawn                     # time of day
Level 1 Quest NPC style: sick princess in a pale gown
Hero look: red scarf alchemist, dark blue coat, satchel
```

### Example Prompts

**Minimal (let the generator decide everything):**
```text
A peaceful mountain kingdom under moonlight with warm inns and old stone roads.
```

**Per-level goals only:**
```text
A lantern-lit harbor town at night with wet cobblestone streets, crates by the docks, and a cozy inn.
Level 1: lost_item
Level 2: key_and_door
Level 3: repair_bridge
```

**Fully specified:**
```text
A lantern-lit fantasy world with high-detail character portraits.
Level 1 Time: night
Level 1 Biome: snow
Level 1 Quest NPC style: sick princess in a pale gown; goal is cure
Level 2 Time: dawn
Level 2 Biome: ruins
Level 2 Quest NPC style: old archivist in cracked stone robes; goal is lost_item
Level 3 Time: sunset
Level 3 Biome: beach
Level 3 Quest NPC style: gate warden in a blue steel cloak; goal is key_and_door
Hero look: red scarf alchemist, dark blue coat, satchel.
```

The same setup works as plain language — the generator can infer intent — but explicit directives guarantee exact results.

---

## Quest Types: How to Complete Each One

### `cure` — Heal a Sick NPC
A sick NPC, ingredient items, and a mixing station appear on the map. Talk to the NPC → collect ingredients → use the mixing station → return to heal the NPC. The NPC sprite swaps from "sick" to "healed."

### `key_and_door` — Chest → Key → Door
A closed chest and a locked door appear. Open the chest → pick up the key → unlock the door.

### `lost_item` — Find and Return
An NPC is missing something; the item is hidden on the map. Talk to the NPC → find the item → return it.

### `repair_bridge` — Shop → Buy → Repair
A broken bridge blocks an area; a shop sells materials (planks/rope/nails). Buy materials → go to the bridge → interact to repair → cross.

---

## Buildings: Shops and Inns

Some levels include enterable buildings. Approach a door from outside and press `SPACE` to enter; press `SPACE` near the door inside to exit.

**Shops:** Press `SPACE` to talk to the shopkeeper, then `1`/`2`/`3` to buy. Your money and inventory update in the UI. The `repair_bridge` quest depends on buying materials here; other quests may still spawn shops for flavor.

**Inns:** Check in at the front desk (`SPACE` near inn host, costs money) → enter your numbered room → interact near the bed to sleep. Sleep toggles time of day (`day ↔ night`) and updates the outdoor palette. Press `SPACE` to wake early. The inn lobby includes ambient guest NPCs.

---

## Cost and Quality

The UI **Quality** dropdown controls both text and image model quality:

| Quality | Text Model | Image Quality | Cost |
|---|---|---|---|
| Low | `gpt-4o-mini` | `gpt-image-1` low | Cheapest |
| Medium (default) | `gpt-4o-mini` | `gpt-image-1` medium | Moderate |
| High | `gpt-4o` | `gpt-image-1` high | Most expensive |

### Cost reduction mechanisms

**Sprite reuse:** Player, shopkeeper, and innkeeper sprites are generated once per run and reused across levels. Baked sprites (see below) skip generation entirely.

**Disk caching:** All generated sprites are cached in `generated_sprites/` (keyed on model, quality, role, and prompt text). Reruns with the same parameters skip API calls. Terrain preview tiles are cached in `generated_terrain_tiles/`.

### Pre-Baking Core Sprites (Optional, Recommended)

You can bake 14 core sprite PNGs at High quality once and commit them, so the default experience has great-looking assets with fewer API calls.

**What gets baked:** shopkeeper, innkeeper, princess sick/healed pair, chest, key, door, mix station, bridge materials (planks/rope/nails), bridge states (broken/fixed), generic item icon — plus a `manifest.json` mapping sprite keys to filenames.

```bash
export OPENAI_API_KEY="sk-..."
python game_generator.py --bake-core --quality high

# Commit baked sprites (optional, for repo distribution)
git add assets/sprites
git commit -m "Add baked core sprites (high quality)"
git push
```

At runtime, the game checks `assets/sprites/manifest.json` first. If a baked sprite exists for a key, it's used; otherwise it falls back to disk cache, then API generation.

---

## Repo Layout

| Path | Purpose |
|---|---|
| `game_generator.py` | Everything: Flask UI + generator + Pygame engine |
| `assets/sprites/` | Baked core sprites + manifest |
| `generated_sprites/` | Sprite disk cache (git-ignored) |
| `generated_terrain_tiles/` | Terrain tile cache |
| `.env.example` | Example environment file |

## Troubleshooting

- **`pip install` fails with "externally-managed-environment":** Use the virtualenv steps in Quick Start.
- **Browser shows blank page:** Use `http://127.0.0.1:5000` (HTTP, not HTTPS).
- **"Bad request version" in terminal:** Your browser tried HTTPS on the HTTP server. Use `http://` explicitly.
- **Image generation errors (500s/400s):** The game falls back to placeholder sprites. Re-run or try again later.

## License

Apache-2.0 (see `LICENSE`).
