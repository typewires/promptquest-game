# PromptQuest

PromptQuest is a **prompt-based, AI-generated adventure game**:
- You type a prompt (setting + vibe).
- The game generates a 3-level run: **maps, characters, items, and quests**.
- You explore a top‑down world and complete objectives (quest log + progress UI).

This project is **Python**: a small **Flask** web UI that generates the world, and a **Pygame** client that runs the game.

## Quick Start

1. Create + activate a virtualenv (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

2. Run:

```bash
python game_generator.py
```

3. In your browser (the page opened by Flask):
- Paste your `OPENAI_API_KEY`
- Enter a prompt
- Click **Generate**

Then return to the terminal and press **ENTER** to play.

## Controls
- `WASD` / Arrow keys: Move
- `SPACE`: Interact / talk / pick up / use
- `1`, `2`, `3`: Shop buy options (when in a shop)
- `R`: Restart run
- `ESC`: Quit

## Prompt Examples
- “A cozy forest village at sunrise, friendly wizard shopkeeper, mysterious ruins nearby.”
- “A desert oasis town at dusk with a sick princess in the palace and a bustling bazaar.”
- “A rainy seaside port with smugglers, lantern-lit alleys, and an ancient locked lighthouse.”

## Notes
- The game will call OpenAI to generate sprites and content. If image generation fails you may see fallback sprites.
- Generated sprite images are cached under `generated_sprites/` (ignored by git).

