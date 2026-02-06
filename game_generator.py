"""
GAME GENERATOR 
===============================================
- Varied quest types generated per world (cure, key+door, lost item)
- Animated characters + environment (bobbing, water shimmer, swaying)
- Code-drawn terrain with tile-like feel
- Fewer flashy effects during daytime
- Peaceful exploration, no combat
"""

import os
import json
import base64
import time
import random
import math
import hashlib
import re
import sys
from io import BytesIO
from flask import Flask, render_template_string, request, jsonify
import requests
import pygame
from PIL import Image

# Track quest variety across generations
LAST_QUEST_TYPE = None


# ============================================================
# CONFIG
# ============================================================

class Config:
    OPENAI_API_KEY = ""
    # Defaults favor cost-effective generation.
    # The UI can override these per-run (Quality dropdown).
    TEXT_MODEL = "gpt-4o-mini"
    IMAGE_MODEL = "gpt-image-1"
    IMAGE_QUALITY = "medium"  # high | medium | low
    # How many quest item sprites to generate per level (others use a generic icon).
    ITEM_SPRITES_PER_LEVEL = 1
    # Cost-saving: make cure quests use a consistent princess patient sprite.
    # When enabled, cure quests will bias/force the NPC to be "Princess ..." so baked princess sprites can be reused.
    FORCE_CURE_PRINCESS = True
    IMAGE_MAX_RETRIES = 4
    IMAGE_RETRY_BASE_DELAY = 1.5
    DEBUG_SPRITES = True
    TILE_SIZE = 72
    GAME_WIDTH = 1400
    GAME_HEIGHT = 900
    MAP_WIDTH = 16
    MAP_HEIGHT = 12
    PLAYER_SPEED = 4
    API_DELAY = 1.2
    ANIM_SPEED = 0.08
    IDLE_BOB = 0
    WALK_BOB = 0


ALLOWED_GOALS = ["cure", "key_and_door", "lost_item", "repair_bridge"]
ALLOWED_BIOMES = ["meadow", "forest", "town", "beach", "snow", "desert", "ruins", "castle"]
ALLOWED_TIMES = ["day", "dawn", "sunset", "night"]

BAKED_SPRITES_DIR = os.path.join("assets", "sprites")
BAKED_MANIFEST_PATH = os.path.join(BAKED_SPRITES_DIR, "manifest.json")


def _load_baked_manifest() -> dict:
    try:
        with open(BAKED_MANIFEST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_baked_sprite(key: str) -> Image.Image | None:
    """
    Load a baked sprite image from assets/sprites/ if present.
    Returns a PIL Image in RGBA or None.
    """
    manifest = _load_baked_manifest()
    fname = manifest.get(key, f"{key}.png")
    path = os.path.join(BAKED_SPRITES_DIR, fname)
    if not os.path.exists(path):
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def _looks_like_princess(npc: dict) -> bool:
    name = str(npc.get("name", "")).lower()
    desc = str(npc.get("sprite_desc", "")).lower()
    return ("princess" in name) or ("princess" in desc)


def parse_level_goal_overrides(prompt: str) -> dict[int, list[str]]:
    """
    Parse prompt directives like:
      "Level 1: cure"
      "level2 - key_and_door"
      "Level 3: cure, lost_item"
    Returns {1: ["cure"], 2: ["key_and_door"], 3: ["cure", "lost_item"], ...} (1-based levels).
    """
    if not prompt:
        return {}
    out: dict[int, list[str]] = {}
    p = str(prompt)

    goal_token_re = re.compile(r"(?i)\b(cure|key_and_door|lost_item|repair_bridge)\b")

    # Primary match: "level 1: cure, lost_item" / "level2 - key_and_door"
    pat = re.compile(r"(?im)\blevel\s*([1-3])\s*[:\-]\s*(.+)$")
    for m in pat.finditer(p):
        try:
            idx = int(m.group(1))
        except Exception:
            continue
        remainder = str(m.group(2) or "")
        found = goal_token_re.findall(remainder)
        opts: list[str] = []
        for raw in found:
            gt = normalize_goal_type(raw)
            if gt and gt not in opts:
                opts.append(gt)
        if idx and opts:
            out[idx] = opts

    # Secondary match for narrative lines like:
    # "Level 2 NPC looks like ..., goal is lost_item"
    for line in p.splitlines():
        lm = re.search(r"(?i)\blevel\s*([1-3])\b", line)
        if not lm:
            continue
        idx = int(lm.group(1))
        found = goal_token_re.findall(line)
        if not found:
            continue
        opts: list[str] = []
        for raw in found:
            gt = normalize_goal_type(raw)
            if gt and gt not in opts:
                opts.append(gt)
        if idx and opts and idx not in out:
            out[idx] = opts
    return out


def normalize_biome(value: str | None) -> str | None:
    """Return a canonical biome or None."""
    if not value:
        return None
    v = str(value).strip().lower()
    return v if v in ALLOWED_BIOMES else None


def parse_level_biome_overrides(prompt: str) -> dict[int, str]:
    """
    Parse prompt directives like:
      "Level 1 Biome: snow"
      "level2 biome - desert"
      "Level 3: ... Biome: ruins"
    Returns a 1-based map: {1: "snow", 2: "desert", 3: "ruins"}.
    """
    if not prompt:
        return {}
    out: dict[int, str] = {}
    lines = str(prompt).splitlines()
    direct_pat = re.compile(r"(?i)\blevel\s*([1-3])\s*biome\s*[:\-]\s*([a-z_]+)\b")
    level_pat = re.compile(r"(?i)\blevel\s*([1-3])\s*[:\-]\s*(.+)$")
    biome_pat = re.compile(r"(?i)\b(" + "|".join(ALLOWED_BIOMES) + r")\b")

    for line in lines:
        m = direct_pat.search(line)
        if m:
            idx = int(m.group(1))
            b = normalize_biome(m.group(2))
            if b:
                out[idx] = b
            continue

        lm = level_pat.search(line)
        if not lm:
            continue
        idx = int(lm.group(1))
        tail = str(lm.group(2) or "")
        bm = biome_pat.search(tail)
        if not bm:
            continue
        b = normalize_biome(bm.group(1))
        if b:
            out[idx] = b
    return out


def normalize_time_of_day(value: str | None) -> str | None:
    """Return canonical time of day or None."""
    if not value:
        return None
    v = str(value).strip().lower()
    aliases = {"dusk": "sunset", "twilight": "sunset", "sunrise": "dawn", "morning": "day", "afternoon": "day", "noon": "day"}
    v = aliases.get(v, v)
    return v if v in ALLOWED_TIMES else None


def parse_level_time_overrides(prompt: str) -> dict[int, str]:
    """
    Parse prompt directives like:
      "Level 2 Time: night"
      "level3 time - dawn"
    Returns {2: "night", 3: "dawn"}.
    """
    if not prompt:
        return {}
    out: dict[int, str] = {}
    lines = str(prompt).splitlines()
    pat = re.compile(r"(?i)\blevel\s*([1-3])\s*time\s*[:\-]\s*([a-z_]+)\b")
    for line in lines:
        m = pat.search(line)
        if not m:
            continue
        idx = int(m.group(1))
        t = normalize_time_of_day(m.group(2))
        if t:
            out[idx] = t
    return out


def strip_first_level_only_directives(prompt: str) -> str:
    """
    Remove global/Level-1-specific styling lines so follow-up levels can randomize those parts.
    Keeps level 2/3 explicit directives intact.
    """
    if not prompt:
        return ""
    out: list[str] = []
    for line in str(prompt).splitlines():
        s = line.strip()
        if not s:
            out.append(line)
            continue
        l = s.lower()
        if l.startswith("hero look:"):
            continue
        if l.startswith("npc look:"):
            continue
        if re.match(r"(?i)^time\s*:", s):
            continue
        if re.match(r"(?i)^level\s*1\s*:", s):
            continue
        if re.match(r"(?i)^level\s*1\s*biome\s*:", s):
            continue
        if re.match(r"(?i)^level\s*1\s*time\s*:", s):
            continue
        out.append(line)
    return "\n".join(out).strip()


def normalize_goal_type(value: str | None) -> str | None:
    """Return a canonical goal type or None."""
    if not value:
        return None
    v = str(value).strip().lower()
    if v in ALLOWED_GOALS:
        return v
    return None


def build_quest_plans(prompt: str, by_level_raw: list, level_count: int) -> list[list[str]]:
    """
    Build a per-level quest plan.
    Priority per level:
    1) Explicit prompt override (Level N: ...)
    2) UI-selected goals for that level (stacking)
    3) Prompt-inferred goals (all levels)
    4) Random fallback goal stack
    """
    level_count = max(1, min(3, int(level_count)))
    overrides = parse_level_goal_overrides(prompt)

    # Normalize UI selections into 1-based map.
    ui_by_level: dict[int, list[str]] = {}
    for i in range(min(3, len(by_level_raw or []))):
        opts: list[str] = []
        for raw in (by_level_raw[i] or []):
            gt = normalize_goal_type(raw)
            if gt and gt not in opts:
                opts.append(gt)
        if opts:
            ui_by_level[i + 1] = opts

    all_goals = list(ALLOWED_GOALS)
    used: list[str] = []
    plans: list[list[str]] = []
    inferred_goals = infer_goals_from_prompt(prompt)

    for lvl in range(1, level_count + 1):
        forced = overrides.get(lvl)
        if forced:
            plan = list(forced)
            plans.append(plan)
            used.extend([g for g in plan if g not in used])
            continue

        pool = ui_by_level.get(lvl, [])
        if pool:
            # Goal stacking: if multiple goals are checked for a level, you play all of them.
            plan = list(pool)
            plans.append(plan)
            used.extend([g for g in plan if g not in used])
            continue

        # If prompt implies one or more goal types, use those as preferred candidates for
        # every unspecified level (not just Level 1). Otherwise use all goals.
        candidates = list(inferred_goals) if inferred_goals else list(all_goals)

        # Random fallback supports goal stacking (1..2 goals per level).
        preferred = [g for g in candidates if g not in used]
        pool2 = preferred or list(candidates)
        max_stack = min(2, len(pool2))
        stack_n = 1 if max_stack <= 1 else random.randint(1, max_stack)
        plan = random.sample(pool2, k=stack_n)
        plans.append(plan)
        used.extend([g for g in plan if g not in used])

    return plans


def build_biome_plans(prompt: str, by_level_raw: list, level_count: int) -> list[str]:
    """
    Build a per-level biome plan.
    Priority per level:
    1) Explicit prompt override (Level N Biome: ...)
    2) UI-selected biome for that level
    3) Random fallback biome
    """
    level_count = max(1, min(3, int(level_count)))
    overrides = parse_level_biome_overrides(prompt)

    ui_by_level: dict[int, str] = {}
    for i in range(min(3, len(by_level_raw or []))):
        b = normalize_biome(by_level_raw[i])
        if b:
            ui_by_level[i + 1] = b

    plans: list[str] = []
    used: list[str] = []
    for lvl in range(1, level_count + 1):
        if overrides.get(lvl):
            b = overrides[lvl]
        elif ui_by_level.get(lvl):
            b = ui_by_level[lvl]
        else:
            candidates = [x for x in ALLOWED_BIOMES if x not in used] or list(ALLOWED_BIOMES)
            b = random.choice(candidates)
        plans.append(b)
        if b not in used:
            used.append(b)
    return plans


def build_time_plans(prompt: str, level_count: int, ui_time: str | None = None) -> list[str]:
    """
    Build per-level time-of-day values.
    - Level 1: prompt/UI hint can apply.
    - Levels 2/3: random unless explicitly overridden by `Level N Time: ...`.
    """
    level_count = max(1, min(3, int(level_count)))
    overrides = parse_level_time_overrides(prompt)
    hint_time = normalize_time_of_day((extract_env_hints(prompt) or {}).get("time_of_day")) or normalize_time_of_day(ui_time)

    plans: list[str] = []
    for lvl in range(1, level_count + 1):
        if overrides.get(lvl):
            plans.append(overrides[lvl])
            continue
        if lvl == 1 and hint_time:
            plans.append(hint_time)
            continue
        plans.append(random.choice(ALLOWED_TIMES))
    return plans


def parse_goal_plan(raw: str | None) -> list[str]:
    """
    Parse a comma-separated goal plan like: "cure,key_and_door,lost_item".
    Unknown values are ignored.
    """
    if not raw:
        return []
    out: list[str] = []
    for part in str(raw).split(","):
        gt = normalize_goal_type(part)
        if gt:
            out.append(gt)
    return out


def _normalize_quest_types(raw: list) -> list[str]:
    """Normalize, filter invalid, and deduplicate a list of goal type strings."""
    seen: set[str] = set()
    out: list[str] = []
    for g in raw:
        gt = normalize_goal_type(g)
        if gt and gt not in seen:
            seen.add(gt)
            out.append(gt)
    return out


def infer_goal_from_prompt(prompt: str) -> str | None:
    goals = infer_goals_from_prompt(prompt)
    return goals[0] if goals else None


def infer_goals_from_prompt(prompt: str) -> list[str]:
    """Infer zero or more goal types from prompt keywords, preserving priority order."""
    p = (prompt or "").lower()
    out: list[str] = []
    if any(k in p for k in ["heal", "cure", "sick", "remedy", "medicine"]):
        out.append("cure")
    if any(k in p for k in ["unlock", "key", "door", "gate", "sealed"]):
        out.append("key_and_door")
    if any(k in p for k in ["lost", "missing", "heirloom", "stolen", "memento"]):
        out.append("lost_item")
    if any(k in p for k in ["bridge", "repair", "fix", "planks", "rope", "nails"]):
        out.append("repair_bridge")
    return out


def _match_keywords(prompt_lower: str, keyword_map: list[tuple[str, list[str]]]) -> str | None:
    """Check keyword lists in order; return the first matching value."""
    for value, keywords in keyword_map:
        if any(k in prompt_lower for k in keywords):
            return value
    return None


# Lookup tables for extract_env_hints (keyword list -> value)
_TIME_KEYWORDS = [
    ("night", ["night", "midnight", "moonlit", "starlit"]),
    ("sunset", ["sunset", "dusk", "twilight"]),
    ("dawn", ["dawn", "sunrise", "early morning"]),
    ("day", ["day", "noon", "afternoon", "morning"]),
]
_TERRAIN_KEYWORDS = [
    ("meadow", ["meadow", "field", "fields", "plains", "grassland"]),
    ("desert", ["desert", "oasis", "dune", "sand"]),
    ("beach", ["beach", "coast", "seaside", "shore", "port", "harbor"]),
    ("snow", ["snow", "blizzard", "ice", "frost", "winter"]),
    ("town", ["town", "village", "city", "market", "bazaar", "street"]),
    ("castle", ["castle", "keep"]),
    ("ruins", ["ruins", "temple", "ancient", "dungeon"]),
    ("forest", ["forest", "woods", "grove", "jungle"]),
]
_LAYOUT_KEYWORDS = [
    ("winding_road", ["winding_road", "winding road"]),
    ("crossroads", ["crossroads"]),
    ("ring_road", ["ring_road", "ring road"]),
    ("lake_center", ["lake_center", "lake center", "central lake"]),
    ("islands", ["islands"]),
    ("ruin_ring", ["ruin_ring", "ruin ring"]),
    ("oasis", ["oasis"]),
    ("market_street", ["market", "bazaar", "street"]),
    ("plaza", ["plaza", "square", "courtyard"]),
    ("coastline", ["coast", "shore", "seaside"]),
    ("maze_grove", ["maze", "labyrinth"]),
    ("riverbend", ["river", "creek", "stream"]),
]
_THEME_TAG_KEYWORDS = [
    "oasis", "market", "bazaar", "ruins", "temple", "castle",
    "port", "harbor", "lantern", "festival", "mushroom", "vines", "statue",
]


def extract_env_hints(prompt: str) -> dict:
    """
    Heuristically extract environment intent from the user prompt so the generated map
    better matches the vibe even if the LLM returns generic terrain/features.
    """
    p = (prompt or "").lower()
    tod = _match_keywords(p, _TIME_KEYWORDS)
    terrain = _match_keywords(p, _TERRAIN_KEYWORDS)
    layout_style = _match_keywords(p, _LAYOUT_KEYWORDS)
    tags = {k for k in _THEME_TAG_KEYWORDS if k in p}
    if terrain:
        tags.add(terrain)
    if tod:
        tags.add(tod)

    return {
        "time_of_day": tod,
        "terrain": terrain,
        "layout_style": layout_style,
        "theme_tags": sorted(tags),
    }


# ============================================================
# PARTICLE EFFECTS
# ============================================================

class Particle:
    def __init__(self, x, y, color, vx=0, vy=0, life=30, size=4, gravity=0):
        self.x, self.y = x, y
        self.color = color
        self.vx = vx + random.uniform(-1, 1)
        self.vy = vy + random.uniform(-1, 1)
        self.life = life
        self.max_life = life
        self.size = size
        self.gravity = gravity
    
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.life -= 1
        return self.life > 0
    
    def draw(self, screen):
        size = max(1, int(self.size * (self.life / self.max_life)))
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), size)


class EffectsManager:
    def __init__(self, allow_flash: bool = True):
        self.particles = []
        self.flash = 0
        self.flash_color = (255, 255, 255)
        self.allow_flash = allow_flash
    
    def update(self):
        self.particles = [p for p in self.particles if p.update()]
        if self.flash > 0:
            self.flash -= 1
    
    def draw(self, screen):
        for p in self.particles:
            p.draw(screen)
        if self.flash > 0:
            s = pygame.Surface(screen.get_size())
            s.fill(self.flash_color)
            s.set_alpha(int(40 * (self.flash / 10)))
            screen.blit(s, (0, 0))
    
    def _emit(self, x, y, colors, count, speed_range, vy_offset, life_range, size_range, gravity, flash_dur=0, flash_color=None):
        """Spawn particles in a circle — shared by sparkle/pickup/complete/smoke."""
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(*speed_range)
            self.particles.append(Particle(
                x, y, random.choice(colors) if isinstance(colors, list) else colors,
                math.cos(angle) * speed, math.sin(angle) * speed + vy_offset,
                random.randint(*life_range), random.randint(*size_range), gravity
            ))
        if flash_dur and self.allow_flash:
            self.flash = flash_dur
            self.flash_color = flash_color

    def sparkle(self, x, y):
        colors = [(255, 255, 100), (100, 200, 255), (255, 100, 255), (255, 255, 255)]
        self._emit(x, y, colors, 20, (1, 4), -2, (25, 45), (3, 6), -0.05, 6, (255, 255, 200))

    def pickup(self, x, y):
        self._emit(x, y, (255, 230, 100), 15, (3, 3), -1, (20, 20), (5, 5), -0.1, 4, (255, 255, 150))

    def complete(self, x, y):
        colors = [(100, 255, 100), (200, 255, 200), (150, 255, 150)]
        self._emit(x, y, colors, 25, (2, 5), 0, (30, 50), (4, 7), 0, 8, (150, 255, 150))

    def smoke(self, x, y, color=(120, 255, 140)):
        self._emit(x, y, color, 25, (0.5, 2.5), -1.5, (25, 45), (4, 7), -0.03)


# ============================================================
# OPENAI CLIENT
# ============================================================

class OpenAIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        self.last_image_was_fallback = False
        self.last_image_error = None
    
    def generate_text(self, prompt: str) -> str:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=self.headers,
            json={
                "model": Config.TEXT_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a game designer. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2500,
                "temperature": 0.6
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def generate_image(self, prompt: str, role: str = "sprite", theme: str = "") -> Image.Image:
        """Generate a character/item sprite"""
        self.last_image_was_fallback = False
        self.last_image_error = None
        cache_dir = "generated_sprites"
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            cache_dir = None

        # Cache images by (model, quality, role, prompt) so repeated runs are cheaper.
        cache_key = None
        cache_path = None
        if cache_dir:
            h = hashlib.sha256()
            h.update((Config.IMAGE_MODEL + "|" + str(Config.IMAGE_QUALITY) + "|" + role + "|" + prompt).encode("utf-8"))
            cache_key = h.hexdigest()[:24]
            cache_path = os.path.join(cache_dir, f"cache_{cache_key}.png")
            if os.path.exists(cache_path):
                try:
                    return Image.open(cache_path).convert("RGBA")
                except Exception:
                    pass
        role_hint = {
            "player": "playable hero",
            "npc": "NPC character",
            "npc_healed": "NPC character (healed/happy)",
            "item": "collectible item",
            "key": "key item",
            "chest": "treasure chest prop",
            "door": "door prop",
            "cauldron": "alchemy cauldron prop",
            "prop": "interactive prop",
        }.get(role, "sprite")

        # Role-specific quality prompts to prevent vague blobs
        role_details = {
            "player": "Full-body single character. Clear face, hair, hands, boots. Distinct silhouette.",
            "npc": "Full-body single character. Clear face, hair, hands, boots. Distinct silhouette.",
            "npc_healed": "Full-body single character. Clear face, hair, hands, boots. Distinct silhouette.",
            "key": "Single ornate brass key with visible teeth and keyring hole. Crisp outline.",
            "chest": "Single wooden treasure chest with metal bands and latch. 3/4 top-down view.",
            "door": "Single wooden door or stone arch door with clear handle/lock. 3/4 top-down view.",
            "cauldron": "Single iron cauldron with glowing liquid and small details (runes, bubbles). 3/4 top-down view.",
            "item": "Single item only. Clean outline. Clear shape and material.",
        }
        detail = role_details.get(role, "Single prop only. Clean outline. Clear function.")
        subject = f"{prompt}. {detail} {role_hint}."

        styled_prompt = f"""Create a single video game {role} sprite in high-quality 32-bit pixel art style.
Style goals: clean outlines, readable silhouette, rich shading, cozy lighting, classic JRPG overworld look.
Reference: 32-bit RPG character style (crisp pixels, higher color depth, detailed clothing).
Avoid generic or blocky shapes. Use 8-16 distinct colors with strong contrast; do NOT be monochrome.
If character: include face, hair, layered clothing, and at least one accessory or motif that fits the theme.
If item/prop: make it unique, colorful, and readable at 128x128.
IMPORTANT: output a SINGLE character or item only. Do NOT include multiple poses, sprite sheets, or multiple characters.
Do NOT show multiple people in the image.
No watermark, no UI, no text, no logos.
No Minecraft/blocky style. No simple rectangles. No stick figures.
The sprite should be on a plain solid GREEN background (#00FF00 bright green for chroma key).
3/4 top-down or slight isometric view, centered in frame, full body visible.
Character should fill most of the frame (75-90% height), not tiny.
Sharp pixels, no blur.

Theme: {theme}
Subject: {subject}"""
        
        last_err = None
        for attempt in range(Config.IMAGE_MAX_RETRIES):
            extra = ""
            if attempt >= 1:
                extra = "\nSTRICT: exactly ONE subject only, centered. No duplicates. No second character."
            if attempt >= 2:
                extra += "\nSTRICT: close-up single subject. Fill the frame. Do not include background props."

            try:
                response = requests.post(
                    "https://api.openai.com/v1/images/generations",
                    headers=self.headers,
                    json={
                        "model": Config.IMAGE_MODEL,
                        "prompt": styled_prompt + extra,
                        "n": 1,
                        "size": "1024x1024",
                        "quality": Config.IMAGE_QUALITY,
                    }
                )
                response.raise_for_status()
                payload = response.json()
                data0 = payload.get("data", [{}])[0] if isinstance(payload.get("data"), list) else {}
                image_data = data0.get("b64_json")
                if not image_data and data0.get("url"):
                    # Some image models/endpoints may return a URL; we do not support downloading in this app.
                    raise RuntimeError("Image API returned a URL; expected base64. Try a GPT image model or update API settings.")
                if not image_data:
                    raise RuntimeError(f"Image API did not return b64_json (keys={list(data0.keys())})")
                img = Image.open(BytesIO(base64.b64decode(image_data)))

                # Resize and try to remove green background
                img = img.resize((128, 128), Image.NEAREST)
                img = self._remove_green_bg(img)

                areas = self._component_areas(img)
                img = self._crop_to_largest_component(img)
                img = self._extract_largest_sprite(img)
                img = self._fit_to_square(img, 128)

                # If it likely contained multiple large subjects, retry with stricter prompt.
                if len(areas) >= 2 and areas[1] > 0.45 * areas[0]:
                    last_err = f"multi-subject output (areas={areas[:3]})"
                    continue
                # If it still looks like a strip/spritesheet after cropping, retry
                if img.width > int(img.height * 1.25):
                    last_err = "spritesheet-like aspect ratio"
                    continue
                if self._nontransparent_pixels(img) < 350:
                    last_err = "too little sprite content"
                    continue
                if Config.DEBUG_SPRITES:
                    try:
                        os.makedirs("generated_sprites", exist_ok=True)
                        ts = int(time.time() * 1000)
                        img.save(os.path.join("generated_sprites", f"{ts}_{role}.png"))
                    except Exception:
                        pass
                # Save cache
                if cache_path:
                    try:
                        img.save(cache_path)
                    except Exception:
                        pass
                return img
            except requests.exceptions.HTTPError as e:
                last_err = str(e)
                status = getattr(getattr(e, "response", None), "status_code", None)
                try:
                    if getattr(e, "response", None) is not None and e.response.text:
                        last_err = f"{last_err} | {e.response.text[:240]}"
                except Exception:
                    pass
                # Backoff for transient server errors
                if status and status >= 500:
                    delay = Config.IMAGE_RETRY_BASE_DELAY * (attempt + 1)
                    time.sleep(delay)
                    continue
                break
            except Exception as e:
                last_err = str(e)
                delay = Config.IMAGE_RETRY_BASE_DELAY * (attempt + 1)
                time.sleep(delay)
                continue

        print(f"Image fallback for role={role}: {last_err}")
        self.last_image_was_fallback = True
        self.last_image_error = last_err
        return self._placeholder(prompt, role)
    
    def _remove_green_bg(self, img: Image.Image) -> Image.Image:
        """Remove bright green background"""
        img = img.convert("RGBA")
        pixels = img.load()
        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = pixels[x, y]
                # Remove bright greens (chroma key)
                if g > 200 and r < 160 and b < 160:
                    pixels[x, y] = (0, 0, 0, 0)
                # Remove near-exact #00FF00 and green spill
                elif r < 80 and g > 200 and b < 80:
                    pixels[x, y] = (0, 0, 0, 0)
                elif g > r + 110 and g > b + 110 and g > 170:
                    pixels[x, y] = (0, 0, 0, 0)
                # Remove medium-bright green halos that survive compositing.
                elif g > 150 and g > r + 70 and g > b + 70:
                    pixels[x, y] = (r, g, b, max(0, a - 220))
                # Also remove near-white/gray backgrounds
                elif r > 240 and g > 240 and b > 240:
                    pixels[x, y] = (0, 0, 0, 0)
                # Remove checkered pattern (common DALL-E artifact)
                elif abs(r - g) < 10 and abs(g - b) < 10 and r > 180:
                    pixels[x, y] = (0, 0, 0, 0)
        return img

    def _nontransparent_bbox(self, img: Image.Image):
        """Return (min_x, min_y, max_x, max_y) of non-transparent pixels, or None."""
        img = img.convert("RGBA")
        pixels = img.load()
        min_x, min_y = img.width, img.height
        max_x, max_y = 0, 0
        found = False
        for y in range(img.height):
            for x in range(img.width):
                if pixels[x, y][3] > 0:
                    found = True
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        return (min_x, min_y, max_x, max_y) if found else None

    def _connected_components(self, img: Image.Image) -> list[tuple[int, tuple]]:
        """Return [(area, (x0, y0, x1, y1)), ...] sorted largest-first."""
        img = img.convert("RGBA")
        w, h = img.size
        px = img.load()
        visited = [[False] * w for _ in range(h)]
        components = []
        for y in range(h):
            for x in range(w):
                if visited[y][x] or px[x, y][3] == 0:
                    continue
                stack = [(x, y)]
                visited[y][x] = True
                min_x, min_y, max_x, max_y = x, y, x, y
                area = 0
                while stack:
                    cx, cy = stack.pop()
                    area += 1
                    min_x, min_y = min(min_x, cx), min(min_y, cy)
                    max_x, max_y = max(max_x, cx), max(max_y, cy)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and px[nx, ny][3] > 0:
                            visited[ny][nx] = True
                            stack.append((nx, ny))
                components.append((area, (min_x, min_y, max_x + 1, max_y + 1)))
        components.sort(key=lambda c: c[0], reverse=True)
        return components

    def _fit_to_square(self, img: Image.Image, size: int = 128, pad: int = 4) -> Image.Image:
        """Crop to non-transparent pixels and scale to fill the square."""
        bbox = self._nontransparent_bbox(img)
        if not bbox:
            return img
        min_x, min_y, max_x, max_y = bbox
        crop = img.crop((min_x, min_y, max_x + 1, max_y + 1))
        target = max(1, size - pad * 2)
        scale = min(target / crop.width, target / crop.height)
        new_w = max(1, int(crop.width * scale))
        new_h = max(1, int(crop.height * scale))
        resized = crop.resize((new_w, new_h), Image.NEAREST)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ox = (size - new_w) // 2
        oy = (size - new_h) // 2
        canvas.paste(resized, (ox, oy), resized)
        return canvas

    def _crop_to_largest_component(self, img: Image.Image) -> Image.Image:
        """Crop to the largest connected non-transparent component."""
        components = self._connected_components(img)
        if components and components[0][0] > 30:
            return img.crop(components[0][1])
        return img

    def _component_areas(self, img: Image.Image) -> list:
        """Return connected-component areas (largest first)."""
        return [area for area, _ in self._connected_components(img)]

    def _extract_largest_sprite(self, img: Image.Image) -> Image.Image:
        """Heuristic: if image looks like a sprite sheet, crop the densest column."""
        bbox = self._nontransparent_bbox(img)
        if not bbox:
            return img
        min_x, min_y, max_x, max_y = bbox
        w = max_x - min_x + 1
        h = max_y - min_y + 1
        if w <= h * 1.2:
            return img

        # Sprite sheet likely: split into 3 or 4 columns and pick densest
        img = img.convert("RGBA")
        pixels = img.load()
        columns = 3 if w / h < 3.5 else 4
        best = None
        best_count = -1
        for i in range(columns):
            x0 = int(min_x + i * w / columns)
            x1 = int(min_x + (i + 1) * w / columns)
            count = sum(1 for y in range(min_y, max_y + 1) for x in range(x0, x1) if pixels[x, y][3] > 0)
            if count > best_count:
                best_count = count
                best = (x0, min_y, x1, max_y + 1)
        if best:
            return img.crop(best)
        return img

    def _nontransparent_pixels(self, img: Image.Image) -> int:
        img = img.convert("RGBA")
        pixels = img.load()
        return sum(1 for y in range(img.height) for x in range(img.width) if pixels[x, y][3] > 0)

    def _placeholder(self, prompt: str, role: str = "sprite") -> Image.Image:
        """Fallback pixel sprite with multiple colors (no purple blocks)."""
        p = prompt.lower()
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        px = img.load()

        def draw_rect(x0, y0, x1, y1, color):
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    px[x, y] = color

        def outline():
            img_copy = img.copy()
            p2 = img_copy.load()
            for y in range(64):
                for x in range(64):
                    if px[x, y][3] > 0:
                        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < 64 and 0 <= ny < 64 and px[nx, ny][3] == 0:
                                p2[nx, ny] = (25, 25, 35, 255)
            return img_copy

        # Item shapes: keyword -> list of (x0, y0, x1, y1, color) rects
        item_shapes = {
            "key": [(26,28,38,32,(240,210,80,255)), (22,26,26,34,(240,210,80,255)), (36,32,40,34,(200,170,60,255))],
            "chest": [(18,30,46,46,(150,90,50,255)), (18,28,46,33,(180,120,70,255)), (30,36,34,40,(230,200,90,255))],
            "door": [(20,18,44,52,(120,80,60,255)), (22,22,42,50,(150,100,70,255)), (38,34,40,36,(220,200,90,255))],
            "cauldron": [(22,34,42,48,(60,60,70,255)), (24,30,40,34,(120,255,140,255)), (28,32,30,34,(255,255,255,255))],
        }
        # Check for item keywords
        for keyword, rects in item_shapes.items():
            if keyword in p or (keyword == "cauldron" and "potion" in p):
                for x0, y0, x1, y1, color in rects:
                    draw_rect(x0, y0, x1, y1, color)
                return outline()
        # Generic item fallback
        if any(k in p for k in ["orb", "gem", "lantern"]):
            draw_rect(26, 28, 38, 40, (120, 180, 255, 255))
            draw_rect(28, 30, 36, 38, (200, 240, 255, 255))
            return outline()

        # Character placeholder
        skin = (240, 200, 170, 255)
        hair = (90, 60, 30, 255)
        outfit1 = (180, 120, 60, 255) if role in ["npc", "npc_healed"] else (70, 130, 220, 255)
        outfit2 = (90, 140, 90, 255) if role in ["npc", "npc_healed"] else (220, 80, 80, 255)

        # Head + hair (shared by all characters)
        for y in range(18, 28):
            for x in range(26, 38):
                px[x, y] = skin
        draw_rect(26, 18, 38, 21, hair)

        # Torso variants: keyword -> extra rects on top of the base outfit
        torso_extras = {
            "wizard": [(22,28,42,46,None), (30,28,34,46,None), (44,26,46,52,(120,80,50,255)), (42,24,48,28,(120,200,255,255))],
            "princess": [(22,28,42,46,None), (24,30,40,34,None), (28,14,36,18,(240,210,80,255)), (30,12,34,14,(240,210,80,255))],
            "king": [(22,28,42,44,None), (22,36,42,38,None), (28,14,36,18,(240,210,80,255)), (26,18,38,20,(200,50,50,255))],
        }
        matched = None
        for keyword in torso_extras:
            aliases = {"wizard": ["wizard", "mage", "robe"], "princess": ["princess", "queen"]}.get(keyword, [keyword])
            if any(a in p for a in aliases):
                matched = keyword
                break

        if matched:
            for i, (x0, y0, x1, y1, color) in enumerate(torso_extras[matched]):
                draw_rect(x0, y0, x1, y1, color or (outfit1 if i == 0 else outfit2))
        else:
            draw_rect(24, 28, 40, 40, outfit1)
            draw_rect(24, 34, 40, 35, outfit2)

        # Legs + boots (shared)
        draw_rect(26, 40, 31, 50, (60, 60, 80, 255))
        draw_rect(33, 40, 38, 50, (60, 60, 80, 255))
        draw_rect(25, 50, 31, 53, (90, 60, 40, 255))
        draw_rect(33, 50, 39, 53, (90, 60, 40, 255))

        return outline()


# ============================================================
# GAME DESIGNER
# ============================================================

class GameDesigner:
    def __init__(self, client: OpenAIClient):
        self.client = client

    def _pick_distinct_colors(self):
        # Keep it simple and readable; we inject these into sprite_desc to force variety.
        base = [
            "crimson and navy with gold accents",
            "teal and cream with copper accents",
            "forest green and brown with amber accents",
            "violet and black with silver accents",
            "white and sky-blue with gold accents",
            "orange and charcoal with turquoise accents",
        ]
        c1 = random.choice(base)
        c2 = random.choice([c for c in base if c != c1])
        return c1, c2

    def _pick_archetypes(self, user_prompt: str, quest_type: str):
        """Pick distinct fantasy archetypes, nudging toward what user asked for."""
        p = user_prompt.lower()
        pool = ["knight", "princess", "wizard", "king", "queen", "ranger", "rogue", "cleric", "bard", "alchemist"]
        # If the quest is a cure quest, bias toward a sick royal/patient NPC.
        if quest_type == "cure":
            npc = "princess" if random.random() < 0.7 else random.choice(["prince", "queen", "king", "cleric"])
            player = random.choice([a for a in ["alchemist", "wizard", "cleric"] if a != npc])
            return player, npc

        if "princess" in p:
            player = "princess"
        elif "king" in p:
            player = "knight"
        elif "wizard" in p or "mage" in p:
            player = "wizard"
        elif "alchemist" in p or "potion" in p:
            player = "alchemist"
        else:
            player = random.choice(pool)
        npc = random.choice([a for a in pool if a != player])
        return player, npc
    
    def design_game(self, user_prompt: str, quest_plan_override: list[str] | None = None) -> dict:
        global LAST_QUEST_TYPE
        quest_types = list(ALLOWED_GOALS)
        quest_plan_override = _normalize_quest_types(quest_plan_override or [])
        if quest_plan_override:
            quest_type_hint = quest_plan_override[0]
        elif LAST_QUEST_TYPE in quest_types:
            quest_types = [q for q in quest_types if q != LAST_QUEST_TYPE]
            quest_type_hint = random.choice(quest_types)
        else:
            quest_type_hint = random.choice(quest_types)
        LAST_QUEST_TYPE = quest_type_hint
        player_colors, npc_colors = self._pick_distinct_colors()
        # If the plan includes a cure goal, bias archetypes toward an alchemist/healer and a royal patient.
        archetype_hint = "cure" if (quest_plan_override and "cure" in quest_plan_override) else quest_type_hint
        player_arch, npc_arch = self._pick_archetypes(user_prompt, archetype_hint)
        design_prompt = f'''Create a peaceful exploration game based on: "{user_prompt}"

Return ONLY JSON:

{{
    "title": "Game Title (max 20 chars)",
    "story": "One sentence story hook",
    "time_of_day": "day/night/dawn/dusk/sunset",

    "player": {{
        "name": "Hero Name",
        "sprite_desc": "Create ONE {player_arch} hero. Include face, hair, and visible hands. Outfit must match: {player_arch}. Add iconic props (crown/staff/sword/cape) as appropriate. Use this color palette: {player_colors}. SINGLE character only.",
        "start_x": 2, "start_y": 8
    }},

    "npc": {{
        "name": "NPC Name",
        "sprite_desc": "Create ONE {npc_arch} NPC. Ensure they contrast strongly with the player (different silhouette, outfit type, and palette). Add iconic props (lantern/book/staff/keys) as appropriate. Use this color palette: {npc_colors}. SINGLE character only.",
        "x": 5, "y": 4,
        "dialogue_intro": "Short greeting that mentions the quest",
        "dialogue_hint": "Clear hint for the NEXT step",
        "dialogue_progress": "Short progress update",
        "dialogue_complete": "Clear completion line"
    }},

    "terrain": {{
        "type": "forest/desert/snow/castle/beach/meadow/town",
        "features": ["water", "trees", "rocks", "flowers", "path"]
    }},

    "quest": {{
        "type": "{quest_type_hint}",
        "goal": "Short objective text for the UI (creative, not generic)",
        "steps": ["Step 1", "Step 2", "Step 3 (clear actions)"],

        "items": [
            {{"id": "item1", "name": "Item 1 Name", "sprite_desc": "detailed item sprite description: shape, material, main color, highlight color. If potion: glass bottle with colored liquid.", "x": 10, "y": 3}},
            {{"id": "item2", "name": "Item 2 Name", "sprite_desc": "detailed item sprite description: shape, material, main color, highlight color. If ingredient: herb/flower/crystal with clear silhouette.", "x": 13, "y": 7}},
            {{"id": "item3", "name": "Item 3 Name", "sprite_desc": "detailed item sprite description: shape, material, main color, highlight color.", "x": 7, "y": 9}}
        ],

        "mix_station": {{
            "name": "Cauldron/Alchemy Table",
            "sprite_desc": "cauldron prop: iron cauldron with glowing liquid, bubbles, small runes",
            "x": 9, "y": 5
        }},

        "npc_healed_sprite_desc": "ONLY for type=cure: healed version of the NPC sprite",

        "chest": {{
            "name": "Old Chest",
            "sprite_desc": "treasure chest prop: wooden chest with metal bands and latch",
            "x": 12, "y": 4
        }},

        "key": {{
            "name": "Old Key",
            "sprite_desc": "key item: ornate brass key with visible teeth and keyring hole"
        }},

        "door": {{
            "name": "Locked Door",
            "sprite_desc": "door prop: wooden door or stone arch with visible lock and handle",
            "x": 14, "y": 6
        }}
    }}
}}

RULES:
- Map is 16x12 tiles
- Use the specified quest type: {quest_type_hint}
- For type=cure: items are ingredients, include mix_station and npc_healed_sprite_desc
- For type=key_and_door: include chest, key, and door; items can be empty or small extras
- For type=lost_item: include 1 item in items
- For type=repair_bridge: do NOT place a chest/door/key; the goal is to repair a broken bridge by buying materials (planks, rope, nails) from a shop, then using them at the bridge.
- Make sprite_desc very detailed (colors, outfit, pose, mood) and match the user_prompt theme
- Characters should be imaginative and distinct, not generic
- If the user_prompt does NOT specify the objective, invent a unique creative objective and steps.
- Player and NPC must look clearly different (color palette, silhouette, role).
- Dialogue must be 1-2 short sentences each (no cutoff), with clear direction for what to do next.
- The quest goal and steps must reference concrete nouns (NPC name, item names, place names) and be logically consistent.
- This is a peaceful exploration game, no combat'''

        print("Generating game design...")
        response = self.client.generate_text(design_prompt)
        
        response = response.strip()
        if "```" in response:
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        
        try:
            game = json.loads(response.strip())
            return self._normalize_game(game, user_prompt=user_prompt, quest_plan_override=quest_plan_override)
        except:
            return self._normalize_game(self._fallback(user_prompt, quest_type_hint), user_prompt=user_prompt, quest_plan_override=quest_plan_override)

    def _normalize_game(self, game: dict, user_prompt: str = "", quest_plan_override: list[str] | None = None) -> dict:
        """Ensure required quest fields exist and sanitize missing data."""
        # Seed used for terrain layout so each level can look distinct but stable.
        if "seed" not in game:
            game["seed"] = random.randint(1, 2_000_000_000)

        quest = game.get("quest") or {}

        # Normalize per-level goal plan.
        plan = _normalize_quest_types(quest_plan_override) if quest_plan_override else []
        if not plan:
            base = normalize_goal_type(quest.get("type"))
            plan = [base] if base in ALLOWED_GOALS else [random.choice(ALLOWED_GOALS)]
        quest["types"] = plan
        quest["type"] = plan[0]

        # Terrain defaults + variety knobs
        hints = extract_env_hints(user_prompt)
        terrain = game.get("terrain") or {}
        # If the prompt implies a strong biome, prefer it.
        ttype = str(terrain.get("type") or "meadow").lower()
        if hints.get("terrain"):
            ttype = hints["terrain"]
        terrain["type"] = ttype
        # Carry tags so TerrainRenderer can add themed decor.
        if hints.get("theme_tags"):
            terrain["theme_tags"] = hints["theme_tags"]
        if "features" not in terrain or not terrain.get("features"):
            # Pick a varied set of features based on biome.
            base = {
                "meadow": ["path", "flowers", "trees", "rocks", "water"],
                "forest": ["path", "trees", "flowers", "rocks", "water"],
                "town": ["path", "signs", "lamps", "trees", "flowers"],
                "beach": ["path", "water", "rocks", "flowers"],
                "snow": ["path", "rocks", "trees", "water"],
                "desert": ["path", "rocks", "ruins", "water"],
                "ruins": ["path", "ruins", "rocks", "water"],
                "castle": ["path", "ruins", "rocks", "water", "lamps"],
            }.get(ttype, ["path", "trees", "rocks", "flowers"])
            # Sample 3-5 features so it doesn't feel identical.
            k = random.randint(3, min(5, len(base)))
            terrain["features"] = random.sample(base, k=k)

        # Layout styles drastically change the feel of the map.
        if hints.get("layout_style"):
            terrain["layout_style"] = hints["layout_style"]
        elif "layout_style" not in terrain:
            styles_by_type = {
                "meadow": ["winding_road", "crossroads", "ring_road", "plaza"],
                "forest": ["winding_road", "maze_grove", "riverbend", "ring_road"],
                "town": ["plaza", "crossroads", "market_street", "ring_road"],
                "beach": ["coastline", "winding_road", "islands", "riverbend"],
                "snow": ["winding_road", "crossroads", "lake_center", "ring_road"],
                "desert": ["oasis", "ruin_ring", "winding_road", "riverbend"],
                "ruins": ["ruin_ring", "crossroads", "maze_grove", "riverbend"],
                "castle": ["plaza", "ring_road", "crossroads", "ruin_ring"],
            }
            terrain["layout_style"] = random.choice(styles_by_type.get(ttype, ["winding_road", "crossroads"]))

        game["terrain"] = terrain

        # Time of day: if prompt strongly implies it, prefer it.
        if hints.get("time_of_day"):
            game["time_of_day"] = hints["time_of_day"]

        # Build pickups and per-goal assets without clobbering other goals.
        # We keep a single world pickup list (quest["items"]) and tag each item with a kind.
        raw_items = quest.get("items") or game.get("items") or []
        if not isinstance(raw_items, list):
            raw_items = []
        raw_items = [it for it in raw_items if isinstance(it, dict)]

        def _fallback_item(idx: int) -> dict:
            base = [
                {"id": "item1", "name": "Crystal Herb", "sprite_desc": "glowing blue herb bundle with bright highlights", "x": 10, "y": 3},
                {"id": "item2", "name": "Sunleaf", "sprite_desc": "golden leaf with warm glow, crisp silhouette", "x": 12, "y": 6},
                {"id": "item3", "name": "Moondew", "sprite_desc": "small vial of shimmering dew in clear glass", "x": 7, "y": 9},
            ]
            return dict(base[min(idx, len(base) - 1)])

        types = list(quest.get("types") or [])

        cure_items: list[dict] = []
        if "cure" in types:
            cure_items = [dict(it) for it in raw_items[:3]] if len(raw_items) >= 3 else []
            while len(cure_items) < 3:
                cure_items.append(_fallback_item(len(cure_items)))
            for i, it in enumerate(cure_items):
                it.setdefault("id", f"ingredient{i+1}")
                it["kind"] = "ingredient"
            quest["cure_items"] = cure_items
        else:
            quest.pop("cure_items", None)

        lost_item: dict | None = None
        if "lost_item" in types:
            # Prefer a distinct item that is not one of the cure ingredients.
            candidate = None
            if raw_items:
                if "cure" in types and len(raw_items) >= 4:
                    candidate = raw_items[3]
                else:
                    candidate = raw_items[0]
            lost_item = dict(candidate) if isinstance(candidate, dict) else {
                "id": "lost_item",
                "name": "Lost Keepsake",
                "sprite_desc": "small ornate keepsake with clear silhouette and metallic highlights",
                "x": 9,
                "y": 6,
            }
            lost_item["id"] = "lost_item"
            lost_item["kind"] = "lost_item"
            quest["lost_item"] = lost_item
        else:
            quest.pop("lost_item", None)

        # World pickups list: cure ingredients + optional lost item.
        world_items: list[dict] = []
        world_items.extend(cure_items)
        if lost_item:
            world_items.append(lost_item)
        quest["items"] = world_items

        # Cure goal requirements
        if "cure" in types:
            # Force "sick" visuals for the NPC, and a clear healed variant.
            npc = game.get("npc", {})
            base_desc = npc.get("sprite_desc", "fantasy NPC")
            # Cost-saving + clarity: keep the cure patient consistent as "Princess ...".
            # This ensures baked princess sprites are reused and players immediately understand who is sick.
            if Config.FORCE_CURE_PRINCESS and npc:
                n = str(npc.get("name", "")).strip()
                if "princess" not in n.lower():
                    npc["name"] = f"Princess {n}" if n else "Princess"
                if "princess" not in base_desc.lower():
                    base_desc = f"princess in elegant dress with a small crown. {base_desc}"
                npc["sprite_desc"] = base_desc
            if npc and "sick" not in (npc.get("sprite_desc", "").lower()):
                npc["sprite_desc"] = base_desc + ". They look sick: pale skin, tired eyes, slumped posture, wrapped in a blanket or holding a stomach, with faint sweat."
            if not quest.get("mix_station"):
                quest["mix_station"] = {"name": "Cauldron", "sprite_desc": "small iron cauldron with green liquid", "x": 9, "y": 5}
            if not quest.get("npc_healed_sprite_desc"):
                # Keep "princess" in the healed description too so the baked healed sprite can be used.
                healed_base = base_desc
                if Config.FORCE_CURE_PRINCESS and "princess" not in healed_base.lower():
                    healed_base = f"princess in elegant dress with crown. {healed_base}"
                quest["npc_healed_sprite_desc"] = f"{healed_base}, now healthy and smiling with brighter colors and a relaxed posture"
        else:
            quest.pop("mix_station", None)
            quest.pop("npc_healed_sprite_desc", None)

        # Key and door requirements
        if "key_and_door" in types:
            if not quest.get("chest"):
                quest["chest"] = {"name": "Old Chest", "sprite_desc": "wooden treasure chest with metal trim", "x": 12, "y": 4}
            if not quest.get("key"):
                quest["key"] = {"name": "Old Key", "sprite_desc": "antique brass key with ornate teeth"}
            if not quest.get("door"):
                quest["door"] = {"name": "Locked Door", "sprite_desc": "stone doorway with iron bands", "x": 14, "y": 6}
        else:
            quest.pop("chest", None)
            quest.pop("key", None)
            quest.pop("door", None)

        # Repair bridge quest requirements
        if "repair_bridge" in types:
            quest["repair_materials"] = [
                {
                    "id": "planks",
                    "name": "Bridge Planks",
                    "sprite_desc": "stack of sturdy wooden bridge planks, slightly weathered, strapped with twine",
                },
                {
                    "id": "rope",
                    "name": "Hemp Rope Coil",
                    "sprite_desc": "thick coil of hemp rope with a knot, tan color, rugged fibers",
                },
                {
                    "id": "nails",
                    "name": "Iron Nails",
                    "sprite_desc": "small pouch of iron nails with a few nails visible, dark metal sheen",
                },
            ]
        else:
            quest.pop("repair_materials", None)

        # Combined goal + steps (always consistent with the engine).
        npc_name = game.get("npc", {}).get("name") or "the NPC"
        goal_bits: list[str] = []
        step_bits: list[str] = []
        if "cure" in types:
            goal_bits.append(f"Heal {npc_name}")
            step_bits.extend(["Talk to the patient", "Gather ingredients", "Brew the remedy", "Deliver it to the patient"])
        if "lost_item" in types:
            goal_bits.append("Find and return the lost item")
            step_bits.extend(["Search the area", "Recover the lost item", "Return it to the owner"])
        if "key_and_door" in types:
            goal_bits.append("Unlock the sealed door")
            step_bits.extend(["Open the chest", "Pick up the key", "Unlock the door"])
        if "repair_bridge" in types:
            goal_bits.append("Repair the broken bridge")
            step_bits.extend(["Visit the shop", "Buy planks, rope, and nails", "Repair the bridge"])
        if goal_bits:
            quest["goal"] = "Objectives: " + "; ".join(goal_bits)
        if step_bits:
            quest["steps"] = step_bits

        goal = quest.get("goal", "")
        if (not goal) or (len(goal) < 12) or any(bad in goal.lower() for bad in ["complete", "finish", "win", "quest"]):
            quest["goal"] = self._flavored_goal(game, quest)
        steps = quest.get("steps") or []
        if (not isinstance(steps, list)) or len(steps) < 3:
            quest["steps"] = self._flavored_steps(quest)

        game["quest"] = quest
        return game

    def _flavored_goal(self, game: dict, quest: dict) -> str:
        terrain = game.get("terrain", {}).get("type", "village")
        time_of_day = game.get("time_of_day", "day")
        npc_name = game.get("npc", {}).get("name", "the NPC")
        item_names = [it.get("name", "item") for it in (quest.get("items") or [])][:3]
        base = [
            f"Restore calm to the {terrain}",
            f"Help the {terrain} folk at {time_of_day}",
            f"Recover a sacred relic of the {terrain}",
            f"Complete the ritual before {time_of_day} ends",
            f"Rekindle the hope of the {terrain}",
        ]
        if quest.get("type") == "cure":
            base += [
                f"Cure {npc_name} with a handmade remedy",
                f"Brew a healing tonic using {', '.join(item_names) if item_names else 'rare ingredients'}",
                f"Mix a restorative elixir and deliver it to {npc_name}",
            ]
        if quest.get("type") == "key_and_door":
            base += [
                "Unseal the ancient gateway",
                "Unlock the forgotten passage",
                "Open the way to the hidden sanctuary",
            ]
        if quest.get("type") == "repair_bridge":
            base += [
                "Repair the broken bridge so travelers can pass",
                "Buy supplies and fix the bridge crossing",
                "Rebuild the bridge to reach the far side",
            ]
        if quest.get("type") == "lost_item":
            base += [
                f"Return the cherished keepsake to {npc_name}",
                f"Find the missing heirloom for {npc_name}",
                f"Recover the lost memento and bring it back to {npc_name}",
            ]
        return random.choice(base)

    _STEP_TEMPLATES = {
        "cure": ["Talk to the patient", "Find three ingredients", "Brew the remedy at the cauldron", "Deliver it to the patient"],
        "key_and_door": ["Ask for directions", "Open the old chest", "Claim the key", "Unlock the sealed door"],
        "lost_item": ["Ask what was lost", "Search the area", "Recover the item", "Return it to the owner"],
        "repair_bridge": ["Talk to the foreman", "Visit the shop and buy planks, rope, and nails", "Repair the bridge", "Cross safely"],
    }

    def _flavored_steps(self, quest: dict) -> list:
        return self._STEP_TEMPLATES.get(quest.get("type"), ["Explore the area", "Complete the objective"])
    
    _FALLBACK_BIOMES = [
        (["night", "dark", "moon", "spooky"], "night", "castle"),
        (["forest", "tree", "wood"], "day", "forest"),
        (["beach", "ocean", "sea"], "day", "beach"),
        (["snow", "ice", "winter"], "day", "snow"),
    ]

    def _fallback(self, prompt: str, quest_type: str = "cure") -> dict:
        prompt_lower = prompt.lower()
        time, terrain = "day", "meadow"
        for keywords, t, ter in self._FALLBACK_BIOMES:
            if any(w in prompt_lower for w in keywords):
                time, terrain = t, ter
                break
        
        base_game = {
            "title": f"Quest: {prompt[:12]}",
            "story": "An adventure awaits!",
            "time_of_day": time,
            "player": {"name": "Hero", "sprite_desc": "young adventurer with blue cape and brown boots", "start_x": 2, "start_y": 8},
            "npc": {"name": "Elder", "sprite_desc": "wise old sage with white beard and purple robe", "x": 5, "y": 4,
                    "dialogue_intro": "Welcome, traveler!", "dialogue_hint": "Seek the three treasures.",
                    "dialogue_progress": "You're doing well!", "dialogue_complete": "You did it!"},
            "terrain": {"type": terrain, "features": ["trees", "rocks", "path", "flowers"]},
        }

        if quest_type == "key_and_door":
            base_game["quest"] = {
                "type": "key_and_door",
                "goal": "Find the key and open the door",
                "steps": ["Open the chest", "Pick up the key", "Unlock the door"],
                "items": [{"id": "item1", "name": "Note", "sprite_desc": "small paper note", "x": 8, "y": 6}],
                "chest": {"name": "Old Chest", "sprite_desc": "wooden treasure chest", "x": 12, "y": 4},
                "key": {"name": "Old Key", "sprite_desc": "antique brass key"},
                "door": {"name": "Locked Door", "sprite_desc": "stone door with iron bands", "x": 14, "y": 6}
            }
        elif quest_type == "lost_item":
            base_game["quest"] = {
                "type": "lost_item",
                "goal": "Find the lost item",
                "steps": ["Find the item", "Return it to the NPC"],
                "items": [{"id": "item1", "name": "Lost Locket", "sprite_desc": "small golden locket", "x": 9, "y": 6}],
            }
        else:
            base_game["quest"] = {
                "type": "cure",
                "goal": "Brew a healing potion",
                "steps": ["Find 3 ingredients", "Mix the potion", "Heal the NPC"],
                "items": [
                    {"id": "item1", "name": "Crystal Herb", "sprite_desc": "glowing blue herb bundle", "x": 10, "y": 3},
                    {"id": "item2", "name": "Sunleaf", "sprite_desc": "golden leaf with warm glow", "x": 13, "y": 7},
                    {"id": "item3", "name": "Moondew", "sprite_desc": "small vial of shimmering dew", "x": 7, "y": 9}
                ],
                "mix_station": {"name": "Cauldron", "sprite_desc": "small iron cauldron with green liquid", "x": 9, "y": 5},
                "npc_healed_sprite_desc": "same NPC but healthy and smiling, brighter colors"
            }
        return base_game


# ============================================================
# SPRITE GENERATOR
# ============================================================

class SpriteGenerator:
    def __init__(self, client: OpenAIClient, delay: float = 0.5):
        self.client = client
        self.delay = delay

    def _gen(self, desc: str, role: str, theme: str) -> Image.Image:
        img = self.client.generate_image(desc, role=role, theme=theme)
        if self.client.last_image_was_fallback:
            print(f"    ⚠ fallback sprite for {role}: {self.client.last_image_error}")
        return img

    def _baked_or_gen(self, baked_key: str, desc: str, role: str, theme: str) -> Image.Image:
        """Load baked sprite when available; otherwise generate it."""
        baked = _load_baked_sprite(baked_key)
        return baked if baked is not None else self._gen(desc, role=role, theme=theme)

    def _baked_scene_or_gen(self, baked_key: str, desc: str, theme: str) -> Image.Image:
        """
        Deprecated for gameplay rendering. Kept only for backward compatibility.
        """
        baked = _load_baked_sprite(baked_key)
        if baked is not None:
            return baked
        return self._fallback_character("item")

    def _baked_reuse_or_gen(
        self,
        baked_key: str,
        reuse_img: Image.Image | None,
        desc: str,
        role: str,
        theme: str,
    ) -> Image.Image:
        """Load baked sprite first, then reuse, then generate."""
        baked = _load_baked_sprite(baked_key)
        if baked is not None:
            return baked
        if reuse_img is not None:
            return reuse_img
        return self._gen(desc, role=role, theme=theme)

    def _emit_sprite(self, sprites: dict, key: str, label: str, loader):
        """Small helper to keep sprite-generation flow readable."""
        print(f"  {label}...")
        sprites[key] = loader()
        time.sleep(self.delay)
    
    def generate_all(self, game: dict, reuse_player_sprite: Image.Image | None = None) -> dict:
        sprites = {}
        quest = game.get("quest", {})
        quest_types = _normalize_quest_types(
            quest.get("types") or ([quest.get("type")] if quest.get("type") else [])
        )
        items = quest.get("items", [])
        theme = f"{game.get('terrain', {}).get('type', '')} {game.get('time_of_day', 'day')} {game.get('story', '')}"
        
        if reuse_player_sprite is None:
            self._emit_sprite(
                sprites,
                "player",
                "Player",
                lambda: self._gen(game["player"]["sprite_desc"], role="player", theme=theme),
            )
        else:
            sprites["player"] = reuse_player_sprite
        
        self._emit_sprite(
            sprites,
            "npc",
            "NPC",
            lambda: self._gen(game["npc"]["sprite_desc"], role="npc", theme=theme),
        )

        # Indoor NPCs: reuse across levels when possible to reduce API calls.
        reuse_shop = game.get("_reuse_sprites", {}).get("npc_shop")
        reuse_inn = game.get("_reuse_sprites", {}).get("npc_inn")
        reuse_guest_a = game.get("_reuse_sprites", {}).get("npc_guest_a")
        reuse_guest_b = game.get("_reuse_sprites", {}).get("npc_guest_b")
        reuse_building_shop = game.get("_reuse_sprites", {}).get("building_shop")
        reuse_building_inn = game.get("_reuse_sprites", {}).get("building_inn")

        self._emit_sprite(
            sprites,
            "npc_shop",
            "npc_shop",
            lambda: self._baked_reuse_or_gen(
                baked_key="npc_shop",
                reuse_img=reuse_shop,
                desc="shopkeeper in layered robes and apron, potion vials on belt, kind face, distinctive hat or hood",
                role="npc",
                theme=theme,
            ),
        )

        self._emit_sprite(
            sprites,
            "npc_inn",
            "npc_inn",
            lambda: self._baked_reuse_or_gen(
                baked_key="npc_inn",
                reuse_img=reuse_inn,
                desc="innkeeper in warm tavern clothes (vest, rolled sleeves), friendly smile, holding a towel or mug, cozy vibe",
                role="npc",
                theme=theme,
            ),
        )

        # Inn guests to avoid repeated same-face NPCs in lobby.
        self._emit_sprite(
            sprites,
            "npc_guest_a",
            "npc_guest_a",
            lambda: self._baked_reuse_or_gen(
                baked_key="npc_guest_a",
                reuse_img=reuse_guest_a,
                desc="ONE full-body inn guest sprite, top-down RPG pixel style, unique outfit and silhouette, transparent background, no frame",
                role="npc",
                theme="retro-rpg-interior",
            ),
        )
        self._emit_sprite(
            sprites,
            "npc_guest_b",
            "npc_guest_b",
            lambda: self._baked_reuse_or_gen(
                baked_key="npc_guest_b",
                reuse_img=reuse_guest_b,
                desc="ONE full-body inn guest sprite, top-down RPG pixel style, different hair/clothes from guest A, transparent background, no frame",
                role="npc",
                theme="retro-rpg-interior",
            ),
        )

        # Building/interior set pieces (prefer baked).
        interior_style_theme = "retro-rpg-interior"
        env_props = [
            ("building_shop", "Shop exterior", "pixel-art top-down RPG shop building exterior with red roof, centered door, windows", reuse_building_shop),
            ("building_inn", "Inn exterior", "pixel-art top-down RPG inn building exterior, warm roof, large entrance, welcoming sign", reuse_building_inn),
            ("shop_counter", "Shop counter", "top-down pixel RPG shop counter, polished wood, books and potion bottles, transparent background"),
            ("shop_shelf", "Shop shelf", "top-down pixel RPG wall shelf full of colorful bottles and goods, transparent background"),
            ("inn_desk", "Inn desk", "top-down pixel RPG inn reception desk with bell and ledger, transparent background"),
            ("inn_bed", "Inn bed", "top-down pixel RPG inn bedroom bed with blanket and pillow, transparent background"),
            ("inn_room_door", "Inn room door", "top-down pixel RPG wooden room door with number plaque and handle, transparent background"),
        ]
        for row in env_props:
            if len(row) == 4:
                key, label, desc, reuse_img = row
            else:
                key, label, desc = row
                reuse_img = None
            self._emit_sprite(
                sprites,
                key,
                label,
                (
                    (lambda k=key, d=desc, rimg=reuse_img: self._baked_reuse_or_gen(
                        baked_key=k,
                        reuse_img=rimg,
                        desc=d,
                        role="item",
                        theme=interior_style_theme,
                    ))
                    if reuse_img is not None
                    else (lambda k=key, d=desc: self._baked_or_gen(
                        baked_key=k,
                        desc=d,
                        role="item",
                        theme=interior_style_theme,
                    ))
                ),
            )

        # We intentionally avoid full-scene generated backdrops in runtime rendering.
        # Interiors are drawn deterministically in engine so interactions always line up.
        
        # Quest items: generate up to N sprites based on Config.ITEM_SPRITES_PER_LEVEL.
        # Remaining items use a baked generic icon (if provided) or reuse the first generated sprite.
        baked_generic = _load_baked_sprite("item_generic")
        if items:
            if Config.ITEM_SPRITES_PER_LEVEL >= 1:
                self._emit_sprite(
                    sprites,
                    "item",
                    "Item",
                    lambda: self._gen(items[0]["sprite_desc"], role="item", theme=theme),
                )
            else:
                sprites["item"] = baked_generic if baked_generic is not None else self._gen("simple collectible item icon", role="item", theme=theme)
            if len(items) > 1:
                if Config.ITEM_SPRITES_PER_LEVEL >= 2:
                    self._emit_sprite(
                        sprites,
                        "item2",
                        "Second item",
                        lambda: self._gen(items[1]["sprite_desc"], role="item", theme=theme),
                    )
                else:
                    sprites["item2"] = baked_generic if baked_generic is not None else sprites.get("item")
        else:
            # Provide a default icon for indoor shelf displays.
            sprites["item"] = baked_generic if baked_generic is not None else self._gen("simple collectible item icon", role="item", theme=theme)
            sprites["item2"] = sprites["item"]
        # Reuse additional items by mirroring existing sprites (visual variety comes from placement).
        # This caps image calls while keeping gameplay intact.

        # Quest-specific props (supports stacked goals per level).
        if "cure" in quest_types:
            npc = game.get("npc", {}) or {}
            self._emit_sprite(
                sprites,
                "npc_sick",
                "Sick NPC",
                lambda: (
                    (_load_baked_sprite("npc_princess_sick") if _looks_like_princess(npc) else None)
                    or _load_baked_sprite("npc_sick")
                    or self._gen(
                        npc.get("sprite_desc", "sick fantasy NPC with pale skin and tired eyes"),
                        role="npc",
                        theme=theme,
                    )
                ),
            )

            mix = quest.get("mix_station", {})
            self._emit_sprite(
                sprites,
                "mix_station",
                "Mix station",
                lambda: self._baked_or_gen(
                    baked_key="mix_station",
                    desc=mix.get("sprite_desc", "small potion cauldron"),
                    role="cauldron",
                    theme=theme,
                ),
            )

            self._emit_sprite(
                sprites,
                "npc_healed",
                "Healed NPC",
                lambda: (
                    (_load_baked_sprite("npc_princess_healed") if _looks_like_princess(npc) else None)
                    or _load_baked_sprite("npc_healed")
                    or self._gen(
                        quest.get("npc_healed_sprite_desc", "healthy smiling villager"),
                        role="npc_healed",
                        theme=theme,
                    )
                ),
            )

        if "key_and_door" in quest_types:
            chest = quest.get("chest", {})
            self._emit_sprite(
                sprites,
                "chest",
                "Chest",
                lambda: self._baked_or_gen(
                    baked_key="chest",
                    desc=chest.get("sprite_desc", "old wooden chest"),
                    role="chest",
                    theme=theme,
                ),
            )

            key = quest.get("key", {})
            self._emit_sprite(
                sprites,
                "key",
                "Key",
                lambda: self._baked_or_gen(
                    baked_key="key",
                    desc=key.get("sprite_desc", "old brass key"),
                    role="key",
                    theme=theme,
                ),
            )

            door = quest.get("door", {})
            self._emit_sprite(
                sprites,
                "door",
                "Door",
                lambda: self._baked_or_gen(
                    baked_key="door",
                    desc=door.get("sprite_desc", "stone door"),
                    role="door",
                    theme=theme,
                ),
            )

        # Repair materials (used by the shop UI + visuals)
        if "repair_bridge" in quest_types:
            mats = {it.get("id"): it for it in (quest.get("repair_materials") or [])}
            mat_specs = [
                ("planks", "mat_planks", "Planks", "stack of wooden planks tied with rope"),
                ("rope", "mat_rope", "Rope", "coiled rope with a knot, tan color"),
                ("nails", "mat_nails", "Nails", "small pouch of iron nails with a few nails visible"),
            ]
            for mat_id, sprite_key, label, default_desc in mat_specs:
                if mat_id not in mats:
                    continue
                self._emit_sprite(
                    sprites,
                    sprite_key,
                    label,
                    lambda m=mats[mat_id], k=sprite_key, d=default_desc: self._baked_or_gen(
                        baked_key=k,
                        desc=m.get("sprite_desc", d),
                        role="item",
                        theme=theme,
                    ),
                )
            # Bridge visuals can be baked for consistent quality.
            self._emit_sprite(
                sprites,
                "bridge_broken",
                "Bridge (broken)",
                lambda: self._baked_or_gen(
                    baked_key="bridge_broken",
                    desc="top-down broken wooden bridge tile segment over water, snapped planks, gap in center, small debris, pixel art",
                    role="item",
                    theme=theme,
                ),
            )
            self._emit_sprite(
                sprites,
                "bridge_fixed",
                "Bridge (fixed)",
                lambda: self._baked_or_gen(
                    baked_key="bridge_fixed",
                    desc="top-down repaired wooden bridge tile segment over water, intact planks and side ropes, pixel art",
                    role="item",
                    theme=theme,
                ),
            )
        
        total_calls = len(sprites)
        print(f"\n  Total API calls: {total_calls}")
        return sprites


# ============================================================
# TERRAIN RENDERER (Code-drawn, top-down pixel adventure style)
# ============================================================

class TerrainRenderer:
    """Draws top-down pixel-adventure terrain with simple shapes and palettes."""
    
    # Color palettes for different times/terrains
    PALETTES = {
        "day_meadow": {
            "bg": (120, 200, 120),
            "grass_dark": (90, 170, 90),
            "grass_light": (140, 220, 140),
            "path": (210, 180, 140),
            "water": (100, 150, 255),
            "water_light": (140, 180, 255),
            "tree_trunk": (120, 80, 50),
            "tree_leaves": (60, 140, 60),
            "rock": (140, 140, 150),
            "flower1": (255, 100, 100),
            "flower2": (255, 255, 100),
            "flower3": (200, 100, 255),
        },
        "day_forest": {
            "bg": (80, 140, 80),
            "grass_dark": (60, 110, 60),
            "grass_light": (100, 160, 100),
            "path": (160, 130, 90),
            "water": (80, 130, 200),
            "water_light": (110, 160, 220),
            "tree_trunk": (100, 60, 40),
            "tree_leaves": (40, 100, 40),
            "rock": (120, 120, 130),
            "flower1": (255, 200, 200),
            "flower2": (200, 255, 200),
            "flower3": (200, 200, 255),
        },
        "night_castle": {
            "bg": (40, 40, 70),
            "grass_dark": (30, 50, 50),
            "grass_light": (50, 70, 70),
            "path": (80, 80, 100),
            "water": (40, 60, 120),
            "water_light": (60, 80, 140),
            "tree_trunk": (50, 40, 40),
            "tree_leaves": (30, 50, 50),
            "rock": (70, 70, 90),
            "flower1": (150, 100, 150),
            "flower2": (100, 100, 150),
            "flower3": (150, 150, 180),
        },
        "day_beach": {
            "bg": (240, 220, 180),
            "grass_dark": (200, 180, 140),
            "grass_light": (250, 235, 200),
            "path": (230, 210, 170),
            "water": (80, 180, 230),
            "water_light": (120, 210, 250),
            "tree_trunk": (140, 100, 60),
            "tree_leaves": (100, 180, 100),
            "rock": (180, 170, 160),
            "flower1": (255, 150, 150),
            "flower2": (150, 255, 200),
            "flower3": (255, 200, 150),
        },
        "day_town": {
            "bg": (110, 180, 110),
            "grass_dark": (80, 150, 80),
            "grass_light": (130, 200, 130),
            "path": (210, 180, 120),
            "water": (90, 150, 230),
            "water_light": (130, 180, 240),
            "tree_trunk": (130, 90, 60),
            "tree_leaves": (70, 150, 70),
            "rock": (150, 150, 160),
            "flower1": (255, 150, 150),
            "flower2": (255, 230, 120),
            "flower3": (170, 140, 255),
        },
        "day_snow": {
            "bg": (230, 240, 250),
            "grass_dark": (200, 220, 240),
            "grass_light": (245, 250, 255),
            "path": (210, 210, 220),
            "water": (150, 200, 255),
            "water_light": (180, 220, 255),
            "tree_trunk": (100, 80, 70),
            "tree_leaves": (60, 100, 80),
            "rock": (180, 185, 195),
            "flower1": (255, 200, 200),
            "flower2": (200, 220, 255),
            "flower3": (220, 200, 255),
        },
        "sunset_meadow": {
            "bg": (180, 140, 120),
            "grass_dark": (140, 110, 90),
            "grass_light": (200, 160, 130),
            "path": (200, 170, 140),
            "water": (150, 120, 180),
            "water_light": (180, 150, 200),
            "tree_trunk": (100, 70, 50),
            "tree_leaves": (120, 100, 70),
            "rock": (150, 130, 120),
            "flower1": (255, 150, 100),
            "flower2": (255, 200, 100),
            "flower3": (255, 130, 130),
        },
        "day_desert": {
            "bg": (225, 200, 150),
            "grass_dark": (200, 175, 125),
            "grass_light": (235, 210, 160),
            "path": (210, 185, 140),
            "water": (70, 160, 220),
            "water_light": (110, 190, 235),
            "tree_trunk": (160, 120, 70),
            "tree_leaves": (120, 170, 120),
            "rock": (175, 160, 150),
            "flower1": (255, 160, 120),
            "flower2": (255, 230, 120),
            "flower3": (200, 170, 255),
        },
        "night_desert": {
            "bg": (70, 60, 80),
            "grass_dark": (60, 55, 70),
            "grass_light": (85, 75, 95),
            "path": (95, 85, 105),
            "water": (40, 80, 150),
            "water_light": (60, 110, 175),
            "tree_trunk": (80, 60, 50),
            "tree_leaves": (50, 90, 80),
            "rock": (95, 90, 110),
            "flower1": (180, 120, 180),
            "flower2": (120, 120, 180),
            "flower3": (180, 180, 210),
        },
        "day_ruins": {
            "bg": (145, 150, 160),
            "grass_dark": (120, 125, 135),
            "grass_light": (160, 165, 175),
            "path": (175, 165, 150),
            "water": (80, 140, 210),
            "water_light": (120, 170, 230),
            "tree_trunk": (110, 80, 60),
            "tree_leaves": (85, 120, 85),
            "rock": (130, 130, 145),
            "flower1": (255, 180, 160),
            "flower2": (230, 230, 160),
            "flower3": (190, 170, 255),
        },
    }
    
    def __init__(self, game: dict, config: Config):
        self.config = config
        self.ts = config.TILE_SIZE
        self.mw = config.MAP_WIDTH
        self.mh = config.MAP_HEIGHT
        
        # Get palette
        time_of_day = game.get("time_of_day", "day")
        terrain_type = game.get("terrain", {}).get("type", "meadow")
        self.biome = str(terrain_type or "meadow").lower()
        self.time_of_day = str(time_of_day or "day").lower()
        palette_key = f"{time_of_day}_{terrain_type}"
        if palette_key not in self.PALETTES:
            # Biome/time fallback mapping
            fallbacks = [
                (lambda: "desert" in terrain_type, lambda: "night_desert" if "night" in time_of_day else "day_desert"),
                (lambda: "ruin" in terrain_type, lambda: "day_ruins"),
                (lambda: "night" in time_of_day, lambda: "night_castle"),
                (lambda: "sunset" in time_of_day or "dusk" in time_of_day, lambda: "sunset_meadow"),
            ]
            palette_key = "day_meadow"
            for check, result in fallbacks:
                if check():
                    palette_key = result()
                    break
        
        self.palette = self.PALETTES[palette_key]
        terrain = game.get("terrain", {}) or {}
        self.features = terrain.get("features", ["trees", "path"])
        self.layout_style = game.get("terrain", {}).get("layout_style", "winding_road")
        self.theme_tags = set([str(t).lower() for t in (terrain.get("theme_tags") or [])])
        self.seed = int(game.get("seed", random.randint(1, 2_000_000_000)))
        self.rng = random.Random(self.seed)
        self.visual_tile_cache = {}
        self.tile_cache_dir = os.path.join("generated_terrain_tiles")
        os.makedirs(self.tile_cache_dir, exist_ok=True)

        # Generate random terrain layout
        self.generate_layout()
        self._build_visual_tiles()

    @staticmethod
    def _mix_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        t = max(0.0, min(1.0, float(t)))
        return (
            int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t),
        )

    @staticmethod
    def _shift(c: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
        return (
            max(0, min(255, c[0] + delta)),
            max(0, min(255, c[1] + delta)),
            max(0, min(255, c[2] + delta)),
        )

    @staticmethod
    def _color_dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])

    def _tile_cache_path(self, key: str) -> str:
        safe_key = key.replace("/", "_")
        return os.path.join(self.tile_cache_dir, f"{safe_key}.png")

    def _load_or_build_tile(self, key: str, build_fn) -> pygame.Surface:
        path = self._tile_cache_path(key)
        if os.path.exists(path):
            try:
                return pygame.image.load(path).convert_alpha()
            except Exception:
                pass
        surf = build_fn().convert_alpha()
        try:
            pygame.image.save(surf, path)
        except Exception:
            pass
        return surf

    def _make_textured_tile(
        self,
        base: tuple[int, int, int],
        dark: tuple[int, int, int],
        light: tuple[int, int, int],
        edge_dark: int = 20,
        edge_light: int = 12,
    ) -> pygame.Surface:
        ts = self.ts
        surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
        # Vertical gradient keeps the top-down style less blocky.
        for y in range(ts):
            g = y / max(1, ts - 1)
            color = self._mix_color(light, base, g * 0.7)
            pygame.draw.line(surf, color, (0, y), (ts, y))
        # Noise-like speckles (seeded for deterministic look per map seed).
        trng = random.Random((self.seed * 31 + hash((base, dark, light, ts))) & 0xFFFFFFFF)
        for _ in range(max(18, ts // 2)):
            x = trng.randint(1, ts - 2)
            y = trng.randint(1, ts - 2)
            c = dark if trng.random() < 0.55 else light
            a = trng.randint(22, 52)
            surf.set_at((x, y), (c[0], c[1], c[2], a))
        # Soft edges and highlight to break hard block seams.
        pygame.draw.line(surf, self._shift(base, -edge_dark), (0, ts - 1), (ts, ts - 1), 1)
        pygame.draw.line(surf, self._shift(base, edge_light), (0, 0), (ts, 0), 1)
        return surf

    def _make_grass_tile(self, base: tuple[int, int, int], dark: tuple[int, int, int], light: tuple[int, int, int]) -> pygame.Surface:
        ts = self.ts
        surf = self._make_textured_tile(base, dark, light, edge_dark=6, edge_light=8)
        # Pixel micro-tiles to mimic classic RPG grass atlas feel.
        cell = max(4, ts // 12)
        rng = random.Random((self.seed * 57 + ts * 3) & 0xFFFFFFFF)
        for gy in range(0, ts, cell):
            for gx in range(0, ts, cell):
                jitter = rng.randint(-6, 8)
                c = self._shift(base, jitter)
                pygame.draw.rect(surf, c, (gx, gy, cell, cell))
                # Tiny blade marks.
                if rng.random() < 0.75:
                    bx = min(ts - 2, gx + rng.randint(1, max(1, cell - 2)))
                    by = min(ts - 2, gy + rng.randint(1, max(1, cell - 1)))
                    pygame.draw.line(surf, self._shift(c, 16), (bx, by), (bx, max(0, by - 2)), 1)
        return surf

    def _make_path_tile(self, base: tuple[int, int, int]) -> pygame.Surface:
        ts = self.ts
        light = self._shift(base, 12)
        dark = self._shift(base, -16)
        surf = self._make_textured_tile(base, dark, light, edge_dark=5, edge_light=8)
        # Brick pattern similar to retro town roads.
        row_h = max(6, ts // 8)
        brick_w = max(10, ts // 4)
        for y in range(2, ts - 2, row_h):
            offset = 0 if ((y // row_h) % 2 == 0) else brick_w // 2
            for x in range(2 + offset, ts - 2, brick_w):
                w = min(brick_w - 2, ts - x - 2)
                h = max(3, row_h - 1)
                if w <= 2:
                    continue
                pygame.draw.rect(surf, self._shift(base, 10), (x, y, w, h))
                pygame.draw.line(surf, self._shift(base, -14), (x, y + h - 1), (x + w, y + h - 1), 1)
        return surf

    def _make_water_tile(self) -> pygame.Surface:
        ts = self.ts
        base = self.palette["water"]
        light = self.palette["water_light"]
        deep = self._shift(base, -24)
        surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
        for y in range(ts):
            g = y / max(1, ts - 1)
            c = self._mix_color(light, deep, g)
            pygame.draw.line(surf, c, (0, y), (ts, y))
        trng = random.Random((self.seed * 131 + ts * 17) & 0xFFFFFFFF)
        # Horizontal ripple streaks.
        for _ in range(max(10, ts // 4)):
            y = trng.randint(2, ts - 3)
            x0 = trng.randint(0, ts // 2)
            x1 = min(ts - 1, x0 + trng.randint(ts // 5, ts // 2))
            pygame.draw.line(surf, self._shift(light, 8), (x0, y), (x1, y), 1)
        # Speckle highlights (retro water sparkle).
        for _ in range(max(6, ts // 10)):
            x = trng.randint(1, ts - 2)
            y = trng.randint(1, ts - 2)
            surf.set_at((x, y), (*self._shift(light, 16), 180))
        return surf

    def _neighbor_mask(self, tiles: set[tuple[int, int]], x: int, y: int) -> int:
        m = 0
        if (x, y - 1) in tiles:
            m |= 1  # N
        if (x + 1, y) in tiles:
            m |= 2  # E
        if (x, y + 1) in tiles:
            m |= 4  # S
        if (x - 1, y) in tiles:
            m |= 8  # W
        return m

    def _draw_edge_strip(self, screen, color: tuple[int, int, int], x: int, y: int, edge: str, w: int):
        ts = self.ts
        if edge == "N":
            pygame.draw.rect(screen, color, (x, y, ts, w))
        elif edge == "E":
            pygame.draw.rect(screen, color, (x + ts - w, y, w, ts))
        elif edge == "S":
            pygame.draw.rect(screen, color, (x, y + ts - w, ts, w))
        elif edge == "W":
            pygame.draw.rect(screen, color, (x, y, w, ts))

    def _build_visual_tiles(self):
        # Biome specific base tile families to keep each map distinct.
        biome = self.biome
        if "snow" in biome:
            base_ground = self._mix_color(self.palette["grass_light"], (250, 250, 255), 0.6)
        elif "desert" in biome or "beach" in biome:
            base_ground = self._mix_color(self.palette["path"], self.palette["grass_light"], 0.65)
        elif "ruin" in biome or "castle" in biome:
            base_ground = self._mix_color(self.palette["rock"], self.palette["grass_dark"], 0.45)
        else:
            base_ground = self.palette["grass_light"]

        key_base = f"{self.biome}_{self.time_of_day}_{self.ts}"
        self.visual_tile_cache["ground"] = self._load_or_build_tile(
            f"ground_{key_base}",
            lambda: self._make_grass_tile(
                base_ground,
                self.palette["grass_dark"],
                self._shift(base_ground, 16),
            ),
        )
        self.visual_tile_cache["ground_alt"] = self._load_or_build_tile(
            f"ground_alt_{key_base}",
            lambda: self._make_textured_tile(
                self._shift(base_ground, -8),
                self._shift(self.palette["grass_dark"], -8),
                self._shift(base_ground, 10),
            ),
        )
        self.visual_tile_cache["path"] = self._load_or_build_tile(
            f"path_{key_base}",
            lambda: self._make_path_tile(self.palette["path"]),
        )
        self.visual_tile_cache["water"] = self._load_or_build_tile(
            f"water_{key_base}",
            self._make_water_tile,
        )

        # One continuous overlay layer removes the "checkerboard grid" feel.
        overlay = pygame.Surface((self.mw * self.ts, self.mh * self.ts), pygame.SRCALPHA)
        orng = random.Random((self.seed * 97 + len(self.biome) * 13) & 0xFFFFFFFF)
        dots = max(120, (self.mw * self.mh) * 2)
        for _ in range(dots):
            x = orng.randint(0, self.mw * self.ts - 1)
            y = orng.randint(0, self.mh * self.ts - 1)
            r = orng.randint(1, max(2, self.ts // 10))
            if "snow" in self.biome:
                c = (*self._shift(self.palette["grass_light"], 14), orng.randint(20, 45))
            elif "desert" in self.biome or "beach" in self.biome:
                c = (*self._shift(self.palette["path"], 8), orng.randint(15, 38))
            elif "ruin" in self.biome or "castle" in self.biome:
                c = (*self._shift(self.palette["rock"], 8), orng.randint(15, 34))
            else:
                c = (*self._shift(self.palette["grass_light"], 10), orng.randint(12, 32))
            pygame.draw.circle(overlay, c, (x, y), r)
        self.ground_overlay = overlay

        # Global time tint improves smooth scene cohesion.
        tint = pygame.Surface((self.mw * self.ts, self.mh * self.ts), pygame.SRCALPHA)
        if self.time_of_day == "night":
            tint.fill((18, 28, 58, 70))
        elif self.time_of_day == "dawn":
            tint.fill((255, 180, 120, 30))
        elif self.time_of_day == "sunset":
            tint.fill((255, 120, 100, 38))
        else:
            tint.fill((255, 255, 255, 0))
        self.time_tint = tint
    
    def generate_layout(self):
        """Generate terrain features"""
        self.water_tiles = set()
        self.path_tiles = set()
        self.trees = []
        self.rocks = []
        self.flowers = []
        self.bushes = []
        self.lamps = []
        self.signs = []
        self.ruins = []
        self.fences = []
        self.cacti = []
        self.mushrooms = []
        self.shells = []
        self.snow_piles = []
        self.crates = []
        self.statues = []
        self.vines = []
        self.tile_variation = {}

        def rand(a, b):
            return self.rng.randint(a, b)

        def choice(seq):
            return self.rng.choice(seq)

        def chance(p):
            return self.rng.random() < p

        def add_pond(cx, cy, r=3):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if (dx * dx + dy * dy) <= (r * r) - 1:
                        x, y = cx + dx, cy + dy
                        if 0 <= x < self.mw and 0 <= y < self.mh:
                            self.water_tiles.add((x, y))

        def add_river(horizontal: bool):
            if horizontal:
                y = rand(2, self.mh - 3)
                x = 0
                while x < self.mw:
                    self.water_tiles.add((x, y))
                    if chance(0.25):
                        y = max(2, min(self.mh - 3, y + choice([-1, 0, 1])))
                    x += 1
            else:
                x = rand(2, self.mw - 3)
                y = 0
                while y < self.mh:
                    self.water_tiles.add((x, y))
                    if chance(0.25):
                        x = max(2, min(self.mw - 3, x + choice([-1, 0, 1])))
                    y += 1

        # PATH LAYOUTS (big impact on distinctness)
        if "path" in self.features:
            style = str(self.layout_style or "winding_road")
            if style == "crossroads":
                cx, cy = self.mw // 2, self.mh // 2
                for x in range(self.mw):
                    self.path_tiles.add((x, cy))
                    if chance(0.6):
                        self.path_tiles.add((x, cy + 1))
                for y in range(self.mh):
                    self.path_tiles.add((cx, y))
                    if chance(0.6):
                        self.path_tiles.add((cx + 1, y))
            elif style == "ring_road":
                for x in range(1, self.mw - 1):
                    self.path_tiles.add((x, 2))
                    self.path_tiles.add((x, self.mh - 3))
                for y in range(2, self.mh - 2):
                    self.path_tiles.add((1, y))
                    self.path_tiles.add((self.mw - 2, y))
            elif style == "plaza":
                cx, cy = self.mw // 2, self.mh // 2
                for y in range(cy - 2, cy + 3):
                    for x in range(cx - 3, cx + 4):
                        self.path_tiles.add((x, y))
                # Roads out
                for x in range(self.mw):
                    if chance(0.7):
                        self.path_tiles.add((x, cy))
                for y in range(self.mh):
                    if chance(0.7):
                        self.path_tiles.add((cx, y))
            elif style == "market_street":
                y = rand(2, self.mh - 3)
                for x in range(self.mw):
                    self.path_tiles.add((x, y))
                    if chance(0.4):
                        self.path_tiles.add((x, y + 1))
                # Side streets
                for _ in range(3):
                    sx = rand(3, self.mw - 4)
                    for yy in range(2, self.mh - 2):
                        if chance(0.75):
                            self.path_tiles.add((sx, yy))
            else:
                # winding_road default
                px, py = 0, self.mh // 2
                while px < self.mw:
                    self.path_tiles.add((px, py))
                    if chance(0.6):
                        self.path_tiles.add((px, py + 1))
                    px += 1
                    if chance(0.35):
                        py = max(2, min(self.mh - 3, py + choice([-1, 1])))

        # WATER LAYOUTS
        if "water" in self.features:
            style = str(self.layout_style or "")
            if style in ["coastline"]:
                # Large water band at one side.
                edge = choice(["top", "bottom", "left", "right"])
                if edge in ["top", "bottom"]:
                    y0 = 0 if edge == "top" else self.mh - 4
                    for y in range(y0, y0 + 4):
                        for x in range(self.mw):
                            self.water_tiles.add((x, y))
                else:
                    x0 = 0 if edge == "left" else self.mw - 4
                    for x in range(x0, x0 + 4):
                        for y in range(self.mh):
                            self.water_tiles.add((x, y))
            elif style in ["riverbend", "maze_grove"]:
                add_river(horizontal=chance(0.5))
                if chance(0.5):
                    add_pond(rand(4, self.mw - 5), rand(3, self.mh - 4), r=2)
            elif style in ["islands"]:
                for _ in range(rand(2, 4)):
                    add_pond(rand(3, self.mw - 4), rand(3, self.mh - 4), r=rand(2, 3))
            elif style in ["oasis"]:
                add_pond(self.mw // 2, rand(3, self.mh - 5), r=3)
            elif style in ["lake_center"]:
                add_pond(self.mw // 2, self.mh // 2, r=4)
            else:
                add_pond(rand(5, self.mw - 5), rand(3, self.mh - 4), r=3)

        # CLUSTERS: trees/rocks/bushes/flowers
        def scatter_cluster(kind: str, count: int, clusters: int):
            if count <= 0:
                return
            centers = [(rand(1, self.mw - 2), rand(1, self.mh - 2)) for _ in range(max(1, clusters))]
            for _ in range(count):
                cx, cy = choice(centers)
                x = max(0, min(self.mw - 1, cx + rand(-3, 3)))
                y = max(0, min(self.mh - 1, cy + rand(-3, 3)))
                if (x, y) in self.water_tiles or (x, y) in self.path_tiles:
                    continue
                if kind == "tree":
                    self.trees.append((x, y))
                elif kind == "rock":
                    self.rocks.append((x, y))
                elif kind == "bush":
                    self.bushes.append((x, y))

        if "trees" in self.features:
            scatter_cluster("tree", count=rand(5, 10), clusters=rand(2, 3))
        if "rocks" in self.features:
            scatter_cluster("rock", count=rand(3, 6), clusters=rand(2, 3))
        # Always some bushes, but more/less depending on style.
        scatter_cluster("bush", count=rand(4, 9), clusters=rand(2, 3))

        if "flowers" in self.features:
            for _ in range(rand(10, 20)):
                fx, fy = rand(0, self.mw - 1), rand(0, self.mh - 1)
                if (fx, fy) in self.water_tiles or (fx, fy) in self.path_tiles:
                    continue
                self.flowers.append((
                    fx * self.ts + rand(6, self.ts - 6),
                    fy * self.ts + rand(6, self.ts - 6),
                    choice(["flower1", "flower2", "flower3"]),
                    self.rng.uniform(0, math.pi * 2),
                ))

        # Lamps/signs/ruins/fences (distinct landmarks)
        for _ in range(rand(2, 4)):
            lx, ly = rand(1, self.mw - 2), rand(1, self.mh - 2)
            if (lx, ly) not in self.water_tiles and (lx, ly) in self.path_tiles:
                self.lamps.append((lx, ly))

        for _ in range(rand(1, 3)):
            sx, sy = rand(1, self.mw - 2), rand(1, self.mh - 2)
            if (sx, sy) not in self.water_tiles and (sx, sy) not in self.path_tiles:
                self.signs.append((sx, sy))

        # Ruins become more likely in certain layouts.
        if "ruins" in self.features or str(self.layout_style) in ["ruin_ring"]:
            for _ in range(rand(2, 4)):
                rx, ry = rand(1, self.mw - 2), rand(1, self.mh - 2)
                if (rx, ry) not in self.water_tiles and (rx, ry) not in self.path_tiles:
                    self.ruins.append((rx, ry))

        # Light fencing around some path edges for variety (non-solid visual).
        for _ in range(rand(5, 10)):
            fx, fy = rand(1, self.mw - 2), rand(1, self.mh - 2)
            if (fx, fy) in self.path_tiles and (fx, fy) not in self.water_tiles:
                if chance(0.35):
                    self.fences.append((fx, fy))

        # Tile variation map for subtle texture
        for y in range(self.mh):
            for x in range(self.mw):
                self.tile_variation[(x, y)] = self.rng.choice([0, 1, 2])

        # Theme-driven decor overlays (prompt alignment)
        def sprinkle(points: list, count: int, avoid_water=True, avoid_path=True):
            for _ in range(count):
                x = rand(1, self.mw - 2)
                y = rand(1, self.mh - 2)
                if avoid_water and (x, y) in self.water_tiles:
                    continue
                if avoid_path and (x, y) in self.path_tiles:
                    continue
                points.append((x, y))

        tags = self.theme_tags
        if "desert" in tags:
            sprinkle(self.cacti, count=rand(3, 6))
        if "beach" in tags:
            sprinkle(self.shells, count=rand(4, 8))
        if "snow" in tags:
            sprinkle(self.snow_piles, count=rand(3, 7))
        if "town" in tags or "market" in tags or "bazaar" in tags or "port" in tags or "harbor" in tags:
            sprinkle(self.crates, count=rand(2, 5), avoid_path=False)
        if "ruins" in tags or "temple" in tags or "castle" in tags:
            sprinkle(self.statues, count=rand(1, 3), avoid_path=False)
            sprinkle(self.vines, count=rand(4, 8), avoid_path=False)
        if "forest" in tags and ("night" in tags or "mushroom" in tags):
            sprinkle(self.mushrooms, count=rand(4, 8))
    
    def draw(self, screen, t: float = 0.0):
        ts = self.ts
        
        # Fill background
        map_rect = (0, 0, self.mw * ts, self.mh * ts)
        screen.fill(self.palette["bg"], map_rect)

        if str(getattr(Config, "TERRAIN_STYLE", "smooth")).lower() == "classic":
            self._draw_base_classic(screen, t)
        else:
            self._draw_base_smooth(screen, t)

        # Draw rocks
        for rx, ry in self.rocks:
            cx, cy = rx * ts + ts//2, ry * ts + ts//2
            pygame.draw.ellipse(screen, self.palette["rock"], (cx - 15, cy - 10, 30, 20))
            pygame.draw.ellipse(screen, (self.palette["rock"][0]+20, self.palette["rock"][1]+20, self.palette["rock"][2]+20),
                               (cx - 10, cy - 8, 15, 10))
            pygame.draw.ellipse(screen, (0, 0, 0), (cx - 16, cy + 6, 32, 8))

        # Draw bushes
        for bx, by in self.bushes:
            cx, cy = bx * ts + ts//2, by * ts + ts//2
            pygame.draw.circle(screen, self.palette["tree_leaves"], (cx - 8, cy + 2), 10)
            pygame.draw.circle(screen, self.palette["tree_leaves"], (cx + 6, cy + 4), 12)
            pygame.draw.circle(screen, self.palette["tree_leaves"], (cx, cy - 4), 12)
            pygame.draw.ellipse(screen, (0, 0, 0), (cx - 12, cy + 10, 26, 6))
        
        # Draw flowers
        for fx, fy, ftype, phase in self.flowers:
            sway = int(math.sin(t * 2 + phase) * 2)
            pygame.draw.circle(screen, self.palette[ftype], (fx + sway, fy), 4)
            pygame.draw.circle(screen, (255, 255, 200), (fx + sway, fy), 2)
        
        # Draw trees
        for tx, ty in self.trees:
            cx, cy = tx * ts + ts//2, ty * ts + ts//2
            leaf_sway = int(math.sin(t * 1.5 + tx) * 2)
            # Trunk
            pygame.draw.rect(screen, self.palette["tree_trunk"], (cx - 5, cy, 10, 20))
            # Leaves (overlapping circles)
            pygame.draw.circle(screen, self.palette["tree_leaves"], (cx + leaf_sway, cy - 10), 18)
            pygame.draw.circle(screen, self.palette["tree_leaves"], (cx - 10 + leaf_sway, cy), 14)
            pygame.draw.circle(screen, self.palette["tree_leaves"], (cx + 10 + leaf_sway, cy), 14)
            pygame.draw.ellipse(screen, (0, 0, 0), (cx - 14, cy + 16, 28, 8))

        # Draw lamps (glow at night)
        for lx, ly in self.lamps:
            cx, cy = lx * ts + ts//2, ly * ts + ts//2
            pygame.draw.rect(screen, self.palette["tree_trunk"], (cx - 2, cy - 8, 4, 18))
            pygame.draw.circle(screen, (255, 220, 120), (cx, cy - 10), 6)
            bg = self.palette.get("bg", (0, 0, 0))
            if sum(bg) / 3 < 120:
                pygame.draw.circle(screen, (255, 220, 140), (cx, cy - 10), 14, 1)

        # Draw signs
        for sx, sy in self.signs:
            cx, cy = sx * ts + ts//2, sy * ts + ts//2
            pygame.draw.rect(screen, (140, 100, 70), (cx - 10, cy - 6, 20, 12))
            pygame.draw.rect(screen, (120, 80, 50), (cx - 2, cy - 6, 4, 16))

        # Draw ruins (stones)
        for rx, ry in self.ruins:
            cx, cy = rx * ts + ts//2, ry * ts + ts//2
            pygame.draw.rect(screen, (120, 120, 130), (cx - 12, cy - 6, 24, 12))
            pygame.draw.rect(screen, (150, 150, 160), (cx - 6, cy - 10, 12, 6))

        # Theme decor overlays (prompt alignment)
        for fx, fy in getattr(self, "fences", []):
            cx, cy = fx * ts + ts // 2, fy * ts + ts // 2
            pygame.draw.line(screen, (90, 70, 50), (cx - 12, cy + 10), (cx + 12, cy + 10), 3)
            pygame.draw.line(screen, (90, 70, 50), (cx - 10, cy + 10), (cx - 10, cy - 2), 3)
            pygame.draw.line(screen, (90, 70, 50), (cx + 10, cy + 10), (cx + 10, cy - 2), 3)

        for x, y in getattr(self, "cacti", []):
            cx, cy = x * ts + ts // 2, y * ts + ts // 2
            pygame.draw.rect(screen, (70, 150, 90), (cx - 4, cy - 14, 8, 22), border_radius=4)
            pygame.draw.rect(screen, (70, 150, 90), (cx - 12, cy - 6, 8, 10), border_radius=4)
            pygame.draw.rect(screen, (70, 150, 90), (cx + 4, cy - 8, 8, 12), border_radius=4)
            pygame.draw.ellipse(screen, (0, 0, 0), (cx - 12, cy + 10, 26, 6))

        for x, y in getattr(self, "mushrooms", []):
            cx, cy = x * ts + ts // 2, y * ts + ts // 2
            cap = (200, 100, 255) if (x + y) % 2 == 0 else (255, 120, 160)
            pygame.draw.rect(screen, (220, 220, 230), (cx - 3, cy - 2, 6, 10), border_radius=3)
            pygame.draw.circle(screen, cap, (cx, cy - 6), 10)
            pygame.draw.circle(screen, (255, 255, 255), (cx - 4, cy - 8), 2)

        for x, y in getattr(self, "shells", []):
            cx, cy = x * ts + ts // 2, y * ts + ts // 2
            pygame.draw.ellipse(screen, (245, 230, 210), (cx - 10, cy - 4, 20, 10))
            pygame.draw.line(screen, (220, 200, 185), (cx - 8, cy), (cx + 8, cy), 1)

        for x, y in getattr(self, "snow_piles", []):
            cx, cy = x * ts + ts // 2, y * ts + ts // 2
            pygame.draw.circle(screen, (245, 250, 255), (cx - 6, cy + 4), 10)
            pygame.draw.circle(screen, (235, 240, 250), (cx + 6, cy + 6), 12)
            pygame.draw.ellipse(screen, (0, 0, 0), (cx - 14, cy + 14, 30, 6))

        for x, y in getattr(self, "crates", []):
            cx, cy = x * ts + ts // 2, y * ts + ts // 2
            pygame.draw.rect(screen, (130, 90, 60), (cx - 12, cy - 12, 24, 24), border_radius=4)
            pygame.draw.line(screen, (100, 70, 50), (cx - 12, cy - 12), (cx + 12, cy + 12), 2)
            pygame.draw.line(screen, (100, 70, 50), (cx + 12, cy - 12), (cx - 12, cy + 12), 2)

        for x, y in getattr(self, "statues", []):
            cx, cy = x * ts + ts // 2, y * ts + ts // 2
            pygame.draw.rect(screen, (150, 150, 165), (cx - 10, cy - 16, 20, 26), border_radius=4)
            pygame.draw.rect(screen, (120, 120, 140), (cx - 14, cy + 8, 28, 10), border_radius=4)
            pygame.draw.circle(screen, (170, 170, 185), (cx, cy - 10), 7)

        for x, y in getattr(self, "vines", []):
            cx, cy = x * ts + ts // 2, y * ts + ts // 2
            pygame.draw.line(screen, (60, 140, 80), (cx, cy - 14), (cx - 8, cy + 14), 3)
            pygame.draw.line(screen, (60, 140, 80), (cx + 4, cy - 12), (cx + 10, cy + 12), 2)

    def _draw_base_classic(self, screen, t: float = 0.0):
        ts = self.ts
        for y in range(self.mh):
            for x in range(self.mw):
                rect = (x * ts, y * ts, ts, ts)
                if (x, y) in self.water_tiles:
                    pygame.draw.rect(screen, self.palette["water"], rect)
                    pygame.draw.line(screen, self.palette["water_light"], (x * ts, y * ts), (x * ts + ts, y * ts), 1)
                    wave = int((t * 10 + (x * 3 + y * 5)) % ts)
                    pygame.draw.line(screen, self.palette["water_light"], (x * ts, y * ts + wave), (x * ts + ts, y * ts + wave), 2)
                elif (x, y) in self.path_tiles:
                    pygame.draw.rect(screen, self.palette["path"], rect)
                    v = self.tile_variation.get((x, y), 0)
                    if v == 0:
                        pygame.draw.circle(screen, self.palette["grass_dark"], (x * ts + 10, y * ts + 12), 2)
                    elif v == 1:
                        pygame.draw.circle(screen, self.palette["grass_dark"], (x * ts + 22, y * ts + 18), 2)
                    else:
                        pygame.draw.circle(screen, self.palette["grass_dark"], (x * ts + 16, y * ts + 26), 2)
                else:
                    v = self.tile_variation.get((x, y), 0)
                    color = self.palette["grass_light"] if v == 0 else self.palette["grass_dark"]
                    pygame.draw.rect(screen, color, rect)
                if (x + y) % 2 == 0:
                    pygame.draw.line(screen, (0, 0, 0), (x * ts, y * ts), (x * ts + ts, y * ts), 1)
                if (x + y) % 4 == 0:
                    pygame.draw.line(screen, (255, 255, 255), (x * ts, y * ts), (x * ts, y * ts + ts), 1)

    def _draw_base_smooth(self, screen, t: float = 0.0):
        ts = self.ts
        ground_tile = self.visual_tile_cache.get("ground")
        path_tile = self.visual_tile_cache.get("path")
        water_tile = self.visual_tile_cache.get("water")

        # Pass 1: ground base.
        for y in range(self.mh):
            for x in range(self.mw):
                px, py = x * ts, y * ts
                if ground_tile is not None:
                    screen.blit(ground_tile, (px, py))

        # Pass 2: water tiles with connected border logic.
        shore_light = self._shift(self.palette["water_light"], 16)
        shore_dark = self._shift(self.palette["water"], -24)
        edge_w = max(2, ts // 10)
        for (x, y) in self.water_tiles:
            px, py = x * ts, y * ts
            if water_tile is not None:
                screen.blit(water_tile, (px, py))
            wave = int((t * 14 + (x * 2 + y * 4)) % ts)
            pygame.draw.line(
                screen,
                self.palette["water_light"],
                (px + 4, py + wave),
                (px + ts - 4, py + wave),
                2,
            )
            mask = self._neighbor_mask(self.water_tiles, x, y)
            if not (mask & 1):
                self._draw_edge_strip(screen, shore_dark, px, py, "N", edge_w)
            if not (mask & 2):
                self._draw_edge_strip(screen, shore_dark, px, py, "E", edge_w)
            if not (mask & 4):
                self._draw_edge_strip(screen, shore_dark, px, py, "S", edge_w)
            if not (mask & 8):
                self._draw_edge_strip(screen, shore_dark, px, py, "W", edge_w)

        # Pass 3: path with neighbor-aware connectors.
        path_edge_dark = self._shift(self.palette["path"], -24)
        path_edge_light = self._shift(self.palette["path"], 14)
        conn_w = max(3, ts // 8)
        for (x, y) in self.path_tiles:
            px, py = x * ts, y * ts
            if path_tile is not None:
                screen.blit(path_tile, (px, py))
            mask = self._neighbor_mask(self.path_tiles, x, y)
            # Open edges get a darker trim; connected edges get slight bright center extension.
            if not (mask & 1):
                self._draw_edge_strip(screen, path_edge_dark, px, py, "N", conn_w)
            else:
                pygame.draw.rect(screen, path_edge_light, (px + ts // 4, py, ts // 2, conn_w))
            if not (mask & 2):
                self._draw_edge_strip(screen, path_edge_dark, px, py, "E", conn_w)
            else:
                pygame.draw.rect(screen, path_edge_light, (px + ts - conn_w, py + ts // 4, conn_w, ts // 2))
            if not (mask & 4):
                self._draw_edge_strip(screen, path_edge_dark, px, py, "S", conn_w)
            else:
                pygame.draw.rect(screen, path_edge_light, (px + ts // 4, py + ts - conn_w, ts // 2, conn_w))
            if not (mask & 8):
                self._draw_edge_strip(screen, path_edge_dark, px, py, "W", conn_w)
            else:
                pygame.draw.rect(screen, path_edge_light, (px, py + ts // 4, conn_w, ts // 2))

        # Pass 4: shoreline highlights on adjacent land tiles.
        for y in range(self.mh):
            for x in range(self.mw):
                if (x, y) in self.water_tiles:
                    continue
                px, py = x * ts, y * ts
                if (x, y - 1) in self.water_tiles:
                    self._draw_edge_strip(screen, shore_light, px, py, "N", 2)
                if (x + 1, y) in self.water_tiles:
                    self._draw_edge_strip(screen, shore_light, px, py, "E", 2)
                if (x, y + 1) in self.water_tiles:
                    self._draw_edge_strip(screen, shore_light, px, py, "S", 2)
                if (x - 1, y) in self.water_tiles:
                    self._draw_edge_strip(screen, shore_light, px, py, "W", 2)

        # Apply a single continuous texture layer so tiles read as connected terrain.
        if getattr(self, "ground_overlay", None) is not None:
            screen.blit(self.ground_overlay, (0, 0))

        # Apply time-of-day tint after terrain base pass.
        if getattr(self, "time_tint", None) is not None:
            screen.blit(self.time_tint, (0, 0))
    
    def get_solid_tiles(self) -> set:
        """Return tiles that block movement"""
        solid = set()
        solid.update(self.water_tiles)
        for tx, ty in self.trees:
            solid.add((tx, ty))
        for rx, ry in self.rocks:
            solid.add((rx, ry))
        return solid


class InteriorRenderer:
    """Simple interior map renderer (shop/house) with walls and floor."""
    # Theme colors: (floor, floor2, wall, wall2, shelf, accent)
    THEMES = {
        "apothecary": ((135,105,85), (125,95,78), (55,55,75), (75,75,105), (105,65,42), (120,200,255)),
        "inn":        ((155,125,95), (145,115,88), (65,60,70), (90,80,100), (120,80,55), (255,220,120)),
        "inn_lobby":  ((158,128,98), (146,116,90), (62,58,70), (88,78,96), (124,82,56), (255,220,120)),
        "inn_room":   ((170,150,128), (160,140,118), (66,64,76), (94,92,110), (130,92,68), (255,235,170)),
        "house":      ((150,135,115), (140,125,108), (70,70,85), (95,95,120), (125,85,58), (200,255,200)),
        "shop":       ((150,120,90), (140,110,85), (60,60,80), (80,80,110), (110,70,45), (120,200,255)),
    }
    _DEFAULT_THEME = ((140,130,120), (130,120,110), (70,70,90), (90,90,120), (120,80,55), (255,220,120))

    def __init__(self, config: Config, theme: str = "shop", door_x: int | None = None):
        self.config = config
        self.ts = config.TILE_SIZE
        self.mw = config.MAP_WIDTH
        self.mh = config.MAP_HEIGHT
        self.theme = theme
        self.door_x = door_x if door_x is not None else self.mw // 2
        self.floor, self.floor2, self.wall, self.wall2, self.shelf, self.accent = (
            self.THEMES.get(theme, self._DEFAULT_THEME)
        )

    def draw(self, screen, t: float = 0.0):
        ts = self.ts
        # Floor base (retro RPG wood/parlor style, less checkerboardy)
        for y in range(self.mh):
            for x in range(self.mw):
                c = self.floor if ((x + y) % 3 != 0) else self.floor2
                pygame.draw.rect(screen, c, (x * ts, y * ts, ts, ts))
                # Plank seams + tiny knots to avoid flat brown blocks.
                seam = (92, 74, 60)
                pygame.draw.line(screen, seam, (x * ts, y * ts + ts - 2), (x * ts + ts, y * ts + ts - 2), 1)
                if (x + y) % 4 == 0:
                    pygame.draw.circle(screen, (120, 96, 76), (x * ts + ts // 2, y * ts + ts // 2), 2)
        # Walls (border)
        for x in range(self.mw):
            pygame.draw.rect(screen, self.wall, (x * ts, 0, ts, ts))
            pygame.draw.rect(screen, self.wall, (x * ts, (self.mh - 1) * ts, ts, ts))
        for y in range(self.mh):
            pygame.draw.rect(screen, self.wall, (0, y * ts, ts, ts))
            pygame.draw.rect(screen, self.wall, ((self.mw - 1) * ts, y * ts, ts, ts))

        # Wall trim band
        pygame.draw.rect(screen, self.wall2, (ts, ts, (self.mw - 2) * ts, ts // 4))

        # Doorway on bottom wall
        dx = self.door_x
        pygame.draw.rect(screen, self.wall2, (dx * ts, (self.mh - 1) * ts, ts, ts))
        pygame.draw.rect(screen, (110, 70, 45), (dx * ts + 18, (self.mh - 1) * ts + 10, ts - 36, ts - 16), border_radius=6)
        pygame.draw.circle(screen, (240, 210, 80), (dx * ts + ts - 24, (self.mh - 1) * ts + ts // 2), 3)

        # Back wall detail
        for x in range(2, self.mw - 2):
            pygame.draw.rect(screen, self.wall2, (x * ts + 6, ts + 6, ts - 12, ts - 12), border_radius=4)

        # Theme decor
        if self.theme in ["shop", "apothecary"]:
            # Back wall shelves
            for x in range(2, self.mw - 2, 3):
                pygame.draw.rect(screen, self.shelf, (x * ts + 6, 2 * ts + 10, ts * 2 - 10, 10), border_radius=3)
                # Bottles
                bx = x * ts + 16
                by = 2 * ts + 2
                pygame.draw.rect(screen, self.accent, (bx, by + 14, 10, 14), border_radius=2)
                pygame.draw.rect(screen, (200, 120, 255), (bx + 22, by + 18, 10, 10), border_radius=2)
                pygame.draw.rect(screen, (120, 255, 180), (bx + 44, by + 16, 10, 12), border_radius=2)
                pygame.draw.rect(screen, (255, 210, 120), (bx + 60, by + 12, 8, 16), border_radius=2)

            # Main counter (classic RPG shop)
            pygame.draw.rect(screen, self.shelf, (4 * ts, 5 * ts, 8 * ts, ts + 6), border_radius=8)
            pygame.draw.rect(screen, (60, 40, 30), (4 * ts + 10, 5 * ts + 10, 8 * ts - 20, ts - 10), border_radius=6)
            # Rug + side barrels
            pygame.draw.rect(screen, (84, 96, 142), (5 * ts, 8 * ts, 6 * ts, ts * 2), border_radius=10)
            pygame.draw.rect(screen, (125, 90, 64), (2 * ts, 8 * ts + 8, ts, ts), border_radius=8)
            pygame.draw.rect(screen, (125, 90, 64), ((self.mw - 3) * ts, 8 * ts + 8, ts, ts), border_radius=8)
            # Wall accents
            pygame.draw.rect(screen, (190, 150, 110), (2 * ts, ts + 10, ts, ts // 2), border_radius=4)
            pygame.draw.rect(screen, (130, 170, 210), (self.mw * ts - 3 * ts, ts + 10, ts, ts // 2), border_radius=4)
        elif self.theme in ["inn", "inn_lobby"]:
            # Reception counter near top wall.
            pygame.draw.rect(screen, self.shelf, (5 * ts, 3 * ts, 6 * ts, ts), border_radius=6)
            pygame.draw.rect(screen, (80, 56, 38), (5 * ts + 8, 3 * ts + 8, 6 * ts - 16, ts - 14), border_radius=6)
            pygame.draw.rect(screen, (120, 84, 56), (self.mw // 2 * ts - 40, ts + 12, 80, 18), border_radius=4)
            txt = self._small_font().render("LODGING", True, (245, 228, 180))
            screen.blit(txt, (self.mw // 2 * ts - 32, ts + 15))
            # Hallway doors attached to upper wall.
            door_y = ts
            hall_xs = [6 * ts, 8 * ts, 10 * ts]
            for idx, dx in enumerate(hall_xs, start=2):
                pygame.draw.rect(screen, (104, 70, 48), (dx, door_y, ts - 10, int(ts * 1.1)), border_radius=6)
                pygame.draw.rect(screen, (74, 48, 34), (dx, door_y, ts - 12, int(ts * 1.2)), 2, border_radius=6)
                num = self._small_font().render(str(idx), True, (240, 230, 200))
                screen.blit(num, (dx + (ts // 2) - 8, door_y + 4))

            # Lounge rugs and tables.
            pygame.draw.rect(screen, (118, 64, 44), (2 * ts, 8 * ts, ts * 4, ts * 2), border_radius=10)
            pygame.draw.rect(screen, (94, 52, 36), (10 * ts, 8 * ts, ts * 4, ts * 2), border_radius=10)
            for tx in [4 * ts, 11 * ts]:
                pygame.draw.circle(screen, (120, 84, 56), (tx, 9 * ts), 18)
                pygame.draw.circle(screen, (90, 62, 44), (tx, 9 * ts), 18, 2)
                pygame.draw.circle(screen, (240, 214, 130), (tx + 2, 9 * ts - 2), 5)

            # Left/right decorative beds in lobby corners for RPG vibe.
            bed_color = (210, 210, 235)
            quilt = (150, 80, 70)
            pillow = (235, 235, 245)
            # Left bed
            pygame.draw.rect(screen, bed_color, (2 * ts, 3 * ts, ts * 4, ts * 2), border_radius=8)
            pygame.draw.rect(screen, quilt, (2 * ts + 10, 3 * ts + 18, ts * 4 - 20, ts * 2 - 28), border_radius=8)
            pygame.draw.rect(screen, pillow, (2 * ts + 16, 3 * ts + 12, ts, ts // 2), border_radius=6)
            # Right bed
            pygame.draw.rect(screen, bed_color, ((self.mw - 6) * ts, 3 * ts, ts * 4, ts * 2), border_radius=8)
            pygame.draw.rect(screen, (132, 92, 70), ((self.mw - 6) * ts + 10, 3 * ts + 18, ts * 4 - 20, ts * 2 - 28), border_radius=8)
            pygame.draw.rect(screen, pillow, ((self.mw - 6) * ts + 16, 3 * ts + 12, ts, ts // 2), border_radius=6)

            # Table + mug
            pygame.draw.rect(screen, self.shelf, (self.mw // 2 * ts - ts, 6 * ts, ts * 2, ts), border_radius=6)
            pygame.draw.circle(screen, (240, 210, 120), (self.mw // 2 * ts, 6 * ts + ts // 2), 6)

            # Rug
            pygame.draw.rect(screen, (120, 60, 40), (self.mw // 2 * ts - ts * 2, 8 * ts, ts * 4, ts * 2), border_radius=10)
            pygame.draw.rect(screen, (160, 90, 60), (self.mw // 2 * ts - ts * 2 + 10, 8 * ts + 10, ts * 4 - 20, ts * 2 - 20), border_radius=10)
        elif self.theme == "inn_room":
            # Cozy private room with one bed and a private door.
            pygame.draw.rect(screen, (190, 170, 142), (2 * ts, 2 * ts, self.mw * ts - 4 * ts, self.mh * ts - 4 * ts), border_radius=12)
            # Bed
            pygame.draw.rect(screen, (220, 220, 238), (4 * ts, 4 * ts, ts * 5, ts * 3), border_radius=10)
            pygame.draw.rect(screen, (148, 86, 70), (4 * ts + 12, 4 * ts + 28, ts * 5 - 24, ts * 3 - 40), border_radius=10)
            pygame.draw.rect(screen, (242, 242, 250), (4 * ts + 16, 4 * ts + 12, ts * 2, ts // 2), border_radius=6)
            # Side table + candle
            pygame.draw.rect(screen, (126, 88, 60), (10 * ts, 5 * ts, ts + 8, ts), border_radius=5)
            pygame.draw.circle(screen, (255, 220, 120), (10 * ts + ts // 2, 5 * ts + ts // 2), 6)
            # Fireplace + rug + wardrobe
            pygame.draw.rect(screen, (92, 78, 72), (2 * ts - 10, 2 * ts + 6, ts + 20, ts * 2), border_radius=6)
            pygame.draw.rect(screen, (230, 120, 60), (2 * ts + 8, 3 * ts - 2, ts - 16, ts - 12), border_radius=4)
            pygame.draw.ellipse(screen, (66, 48, 40), (2 * ts + 6, 4 * ts - 6, ts - 12, 12))
            pygame.draw.ellipse(screen, (210, 196, 172), (4 * ts - 4, 8 * ts - 6, ts * 5, ts * 2))
            pygame.draw.rect(screen, (108, 82, 60), (self.mw * ts - 3 * ts, 4 * ts, ts + 18, ts * 3), border_radius=8)
            # Room exit door
            pygame.draw.rect(screen, (108, 74, 50), (self.mw // 2 * ts - 16, (self.mh - 1) * ts + 8, 32, ts - 14), border_radius=6)

        # Warm light pool
        glow = pygame.Surface((self.mw * ts, self.mh * ts), pygame.SRCALPHA)
        cx, cy = (self.mw * ts) // 2, (self.mh * ts) // 2
        for r in range(220, 20, -20):
            a = int(20 * (r / 220))
            pygame.draw.circle(glow, (*self.accent, a), (cx, cy), r)
        screen.blit(glow, (0, 0))

    def get_solid_tiles(self) -> set:
        solid = set()
        for x in range(self.mw):
            solid.add((x, 0))
            solid.add((x, self.mh - 1))
        for y in range(self.mh):
            solid.add((0, y))
            solid.add((self.mw - 1, y))
        # Carve doorway
        solid.discard((self.door_x, self.mh - 1))

        # Theme-specific blocking decor (so interiors feel different)
        ts = self.ts
        if self.theme in ["shop", "apothecary"]:
            # Counter
            cx = self.mw // 2
            for x in range(cx - 2, cx + 2):
                solid.add((x, 6))
        elif self.theme in ["inn", "inn_lobby"]:
            # Beds block their tiles
            for x in range(2, 6):
                solid.add((x, 3))
                solid.add((x, 4))
            for x in range(self.mw - 6, self.mw - 2):
                solid.add((x, 3))
                solid.add((x, 4))
            # Table
            solid.add((self.mw // 2, 6))
            # Reception counter
            for x in range(5, 11):
                solid.add((x, 3))
            # Decorative tables
            for x in range(2, 6):
                solid.add((x, 8))
            for x in range(10, 14):
                solid.add((x, 8))
        elif self.theme == "inn_room":
            # Bed footprint
            for x in range(4, 9):
                for y in range(4, 7):
                    solid.add((x, y))
            # side table
            solid.add((10, 5))
        return solid

    def _small_font(self):
        return pygame.font.Font(None, 20)


# ============================================================
# GAME ENGINE
# ============================================================

class GameEngine:
    def __init__(self, levels: list, config: Config):
        self.levels = levels
        self.level_index = 0
        self.config = config
        self.running = True
        
        pygame.init()
        self.screen = pygame.display.set_mode((config.GAME_WIDTH, config.GAME_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.font_large = pygame.font.Font(None, 32)
        self.font_title = pygame.font.Font(None, 38)

        self.anim_time = 0.0
        self.entity_phase = {}
        self.surfaces = {}
        self.sprite_offsets = {}

        self.load_level(0)

    @staticmethod
    def _cleanup_sprite_rgba(img: Image.Image) -> Image.Image:
        """
        Final safety cleanup for generated/baked sprites.
        Removes residual green-screen pixels and trims green edge halos.
        """
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        px = img.load()
        w, h = img.size
        border_samples = []
        for x in range(w):
            border_samples.append(px[x, 0][:3])
            border_samples.append(px[x, h - 1][:3])
        for y in range(h):
            border_samples.append(px[0, y][:3])
            border_samples.append(px[w - 1, y][:3])
        # Pick a dominant border color bucket for flood-style background removal.
        bucket = {}
        for c in border_samples:
            key = (c[0] // 16, c[1] // 16, c[2] // 16)
            bucket[key] = bucket.get(key, 0) + 1
        dom_key = max(bucket.items(), key=lambda kv: kv[1])[0] if bucket else None
        dom_color = (dom_key[0] * 16 + 8, dom_key[1] * 16 + 8, dom_key[2] * 16 + 8) if dom_key else None

        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                # Hard chroma key removal.
                if g > 170 and g > r + 55 and g > b + 55:
                    px[x, y] = (0, 0, 0, 0)
                    continue
                # Remove green-ish matte even when it's not pure chroma green.
                if g > 120 and g > r * 1.25 and g > b * 1.25 and (r < 120 or b < 120):
                    na = max(0, a - 120)
                    if na < 30:
                        px[x, y] = (0, 0, 0, 0)
                    else:
                        px[x, y] = (r, int(g * 0.55), b, na)
                    continue
                # Remove border-colored matte if it resembles keyed background.
                if dom_color is not None and (x in [0, w - 1] or y in [0, h - 1]):
                    if (
                        TerrainRenderer._color_dist((r, g, b), dom_color) < 42
                        and (g > r + 40 or g > b + 40 or (r > 235 and g > 235 and b > 235))
                    ):
                        px[x, y] = (0, 0, 0, 0)
                        continue
                # Defringe semitransparent green spill on edges.
                if a < 255 and g > r + 25 and g > b + 25:
                    nr = min(255, int(r * 1.08))
                    nb = min(255, int(b * 1.08))
                    ng = int(g * 0.55)
                    na = max(0, min(255, a - 70))
                    px[x, y] = (nr, ng, nb, na)
        # Add slight dark outline around opaque body to unify style.
        out = img.copy()
        opx = out.load()
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if px[x, y][3] == 0:
                    # transparent pixel near opaque body -> outline pixel
                    neighbors = [
                        px[x - 1, y], px[x + 1, y], px[x, y - 1], px[x, y + 1],
                        px[x - 1, y - 1], px[x + 1, y - 1], px[x - 1, y + 1], px[x + 1, y + 1],
                    ]
                    if any(n[3] > 180 for n in neighbors):
                        opx[x, y] = (16, 20, 26, 140)
        return out

    def load_level(self, index: int):
        self.level_index = index
        level = self.levels[index]
        self.game = level["game"]
        sprites = level["sprites"]

        title = self.game.get("title", "Adventure")
        pygame.display.set_caption(f"{title} - Level {index + 1}/{len(self.levels)}")

        time_of_day = self.game.get("time_of_day", "day")
        allow_flash = time_of_day in ["night", "dusk", "sunset"]
        self.effects = EffectsManager(allow_flash=allow_flash)
        self.terrain = TerrainRenderer(self.game, self.config)
        self.interior = InteriorRenderer(self.config, theme="shop", door_x=self.config.MAP_WIDTH // 2)

        # Convert sprites
        self.surfaces = {}
        self.sprite_offsets = {}
        ts = self.config.TILE_SIZE
        for name, img in sprites.items():
            img = self._cleanup_sprite_rgba(img)
            surface = pygame.image.fromstring(img.tobytes(), img.size, "RGBA")
            scale = 1.0
            base_name = name.replace("_alt", "")
            if base_name.startswith("scene_"):
                # Full-room backdrop image (shop/inn scenes).
                map_w = self.config.MAP_WIDTH * ts
                map_h = self.config.MAP_HEIGHT * ts
                surf = pygame.transform.scale(surface, (map_w, map_h)).convert_alpha()
                self.surfaces[name] = surf
                self.sprite_offsets[name] = (0, 0)
                continue
            if base_name == "player" or base_name.startswith("npc"):
                scale = 1.75
            elif base_name in ["door"]:
                scale = 1.5
            elif base_name in ["chest", "mix_station"]:
                scale = 1.3
            elif base_name in ["key"]:
                scale = 1.1
            elif base_name in ["building_shop", "building_inn"]:
                scale = 2.5
            elif base_name in ["shop_counter", "shop_shelf", "inn_desk"]:
                scale = 1.8
            elif base_name in ["inn_bed", "inn_room_door"]:
                scale = 1.9
            size = max(1, int(ts * scale))
            surf = pygame.transform.scale(surface, (size, size)).convert_alpha()
            # Final hard fallback for any lingering pure-green matte.
            surf.set_colorkey((0, 255, 0))
            self.surfaces[name] = surf
            off_x = (ts - size) // 2
            off_y = ts - size
            self.sprite_offsets[name] = (off_x, off_y)

        self.anim_time = 0.0
        self.entity_phase = {}
        self.reset_game()
        self.msg(f"Level {index + 1}/{len(self.levels)}: {title}")
    
    def reset_game(self):
        ts = self.config.TILE_SIZE
        quest = self.game.get("quest", {})
        self.quest = quest
        self.quest_types = _normalize_quest_types(
            quest.get("types") or ([quest.get("type")] if quest.get("type") else [])
        )
        if not self.quest_types:
            self.quest_types = ["lost_item"]
        # Back-compat: some UI hints still reference a single quest_type.
        self.quest_type = self.quest_types[0]

        # Build collision map (outdoor) early so we can place buildings safely.
        self.solid_outdoor = self.terrain.get_solid_tiles()

        # World state
        self.scene = "outdoor"  # or "indoor"
        self.indoor_mode = "lobby"  # inn: lobby/room
        self.current_building = None
        self.money = 60
        self.sleeping = False
        self.sleep_end_ms = 0
        self.dialogue_state = {}

        # Repair bridge state
        self.bridge_repaired = False
        self.bridge_tiles = set()

        # Create 2 enterable buildings
        mh = self.config.MAP_HEIGHT
        entrance_shop = self._find_open_tile(3, mh // 2, solid=self.solid_outdoor)
        entrance_inn = self._find_open_tile(12, mh // 2, solid=self.solid_outdoor)
        door_x = self.config.MAP_WIDTH // 2

        shop_goods = [
            {"id": "planks", "name": "Bridge Planks (sturdy)", "price": 20},
            {"id": "rope", "name": "Hemp Rope Coil", "price": 15},
            {"id": "nails", "name": "Iron Nails (pouch)", "price": 10},
        ]
        # If this run doesn't include bridge repair, make shop items more general-purpose flavor.
        if "repair_bridge" not in self.quest_types:
            shop_goods = [
                {"id": "torch", "name": "Traveler's Torch", "price": 8},
                {"id": "bandage", "name": "Bandage Wraps", "price": 6},
                {"id": "map", "name": "Hand‑drawn Map", "price": 12},
            ]

        inn_goods = [
            {"id": "sleep", "name": "Rent a Bed (sleep)", "price": 12},
            {"id": "stew", "name": "Hearty Stew", "price": 6},
            {"id": "tea", "name": "Warm Tea", "price": 5},
        ]

        self.buildings = [
            {
                "name": "Shop",
                "theme": "shop",
                "npc": "Shopkeeper",
                "dialogue": "Welcome. Potions and herbs are on the shelf.",
                "smalltalk": [
                    "Fresh tonics came in at dawn. Desert nights spoil weak brews.",
                    "If you smell mint and iron, that's my anti-venom batch.",
                    "Travel light; sandstorms punish anyone carrying junk.",
                    "I label rare stock in blue glass so nobody confuses it with lamp oil.",
                ],
                "entrance": entrance_shop,
                "exit": (door_x, self.config.MAP_HEIGHT - 1),
                "npc_pos": (self.config.MAP_WIDTH // 2 + 2, 4),
                "npc_sprite_key": "npc_shop",
                "goods": shop_goods,
                "items": [],
            },
            {
                "name": "Inn",
                "theme": "inn",
                "npc": "Inn Host",
                "dialogue": "Welcome traveler. Rooms are 12g per night.",
                "smalltalk": [
                    "Mind the boots by the hearth; they belong to caravan guards.",
                    "The kitchen keeps stew warm until moonrise.",
                    "Most guests sleep lighter when the wind hits the shutters.",
                    "If you're headed out early, I can pack tea in a travel flask.",
                ],
                "entrance": entrance_inn,
                "exit": (door_x, self.config.MAP_HEIGHT - 1),
                "npc_pos": (self.config.MAP_WIDTH // 2, 3),
                "npc_sprite_key": "npc_inn",
                "goods": inn_goods,
                "bed_pos": (6, 5),
                "room_door": (self.config.MAP_WIDTH // 2, 1),
                "room_exit": (self.config.MAP_WIDTH // 2, self.config.MAP_HEIGHT - 1),
                "room_number": "3",
                "guest_npcs": [(3, 8), (11, 8)],
                "guest_profiles": [
                    {
                        "name": "Guest Mira",
                        "lines": [
                            "The soup is peppery tonight, just how I like it.",
                            "I trade silk by day and stories by candlelight.",
                            "The inn piano's out of tune, but nobody minds after supper.",
                        ],
                    },
                    {
                        "name": "Guest Rowan",
                        "lines": [
                            "I count steps between towns. Helps me remember the roads.",
                            "These floorboards creak less near the back stairs.",
                            "I've seen three comets from this very window.",
                        ],
                    },
                ],
                "room_paid": False,
                "room_unlocked": False,
                "items": [],
            },
        ]

        # Ensure outdoor entrances are reachable from player spawn side.
        start_tile_hint = (
            int(self.game.get("player", {}).get("start_x", self.config.MAP_WIDTH // 2)),
            int(self.game.get("player", {}).get("start_y", self.config.MAP_HEIGHT // 2)),
        )
        reachable_outdoor = self._compute_reachable(self.solid_outdoor, start_tile_hint)
        occupied_entrances: set[tuple[int, int]] = set()
        for b in self.buildings:
            ex, ey = b["entrance"]
            ex, ey = self._pick_free_reachable((ex, ey), reachable_outdoor, occupied_entrances, self.solid_outdoor)
            b["entrance"] = (ex, ey)
            occupied_entrances.add((ex, ey))

        # Place repair bridge on an actual water crossing reachable from the player's side.
        if "repair_bridge" in self.quest_types:
            water = set(getattr(self.terrain, "water_tiles", set()))
            path = set(getattr(self.terrain, "path_tiles", set()))
            w, h = self.config.MAP_WIDTH, self.config.MAP_HEIGHT

            def is_land(tx, ty):
                return (0 <= tx < w and 0 <= ty < h and (tx, ty) not in water and (tx, ty) not in self.solid_outdoor)

            candidates: list[tuple[int, set[tuple[int, int]]]] = []
            for x, y in water:
                # Horizontal span across water: [x,y] [x+1,y], banks at x-1 and x+2
                if (x + 1, y) in water and is_land(x - 1, y) and is_land(x + 2, y):
                    left_bank = (x - 1, y)
                    right_bank = (x + 2, y)
                    if left_bank in reachable_outdoor or right_bank in reachable_outdoor:
                        score = 0
                        if left_bank in path:
                            score += 2
                        if right_bank in path:
                            score += 2
                        score -= abs(y - start_tile_hint[1])
                        candidates.append((score, {(x, y), (x + 1, y)}))
                # Vertical span across water: [x,y] [x,y+1], banks at y-1 and y+2
                if (x, y + 1) in water and is_land(x, y - 1) and is_land(x, y + 2):
                    top_bank = (x, y - 1)
                    bot_bank = (x, y + 2)
                    if top_bank in reachable_outdoor or bot_bank in reachable_outdoor:
                        score = 0
                        if top_bank in path:
                            score += 2
                        if bot_bank in path:
                            score += 2
                        score -= abs(x - start_tile_hint[0])
                        candidates.append((score, {(x, y), (x, y + 1)}))

            if candidates:
                candidates.sort(key=lambda v: v[0], reverse=True)
                self.bridge_tiles = set(candidates[0][1])
            else:
                bx = self.config.MAP_WIDTH // 2
                by = self.config.MAP_HEIGHT // 2
                self.bridge_tiles = {(bx, by), (bx, by + 1)}

            for t in self.bridge_tiles:
                self.solid_outdoor.add(t)

        self.player_x = self.game["player"]["start_x"] * ts
        self.player_y = self.game["player"]["start_y"] * ts
        self.is_moving = False

        self.inventory = []
        self.items_collected = set()
        self.talked_to_npc = False
        self.message = self.game.get("story", "")
        self.message_timer = 300
        self.game_won = False
        self.quest_known = False

        # Quest state (stacked goals share a single level; items are world pickups).
        self.items = list(quest.get("items", []))
        self.mix_station = quest.get("mix_station")
        self.npc_healed = False
        self.mixed_potion = False
        self.potion_given = False

        self.chest = quest.get("chest")
        self.key = quest.get("key")
        self.door = quest.get("door")
        self.chest_opened = False
        self.key_spawned = False
        self.key_collected = False
        self.door_opened = False
        self.key_pos = None

        self.lost_item_found = False
        self.lost_item_returned = False

        for b in self.buildings:
            self.solid_outdoor.add((b["entrance"][0], b["entrance"][1]))

        # Ensure important entities are on open tiles
        self.solid = self.solid_outdoor
        self._ensure_entity_positions()

        # Add solid objects
        npc = self.game["npc"]
        self.solid.add((npc["x"], npc["y"]))
        if ("cure" in self.quest_types) and self.mix_station:
            self.solid.add((self.mix_station["x"], self.mix_station["y"]))
        if ("key_and_door" in self.quest_types) and self.chest and not self.chest_opened:
            self.solid.add((self.chest["x"], self.chest["y"]))
        if ("key_and_door" in self.quest_types) and self.door and not self.door_opened:
            self.solid.add((self.door["x"], self.door["y"]))

        # Indoor collision map (set on enter)
        self.solid_indoor = self.interior.get_solid_tiles()

        # Animation phases
        self.entity_phase = {
            "player": random.random() * 10,
            "npc": random.random() * 10,
        }
        for item in self.items:
            self.entity_phase[item["id"]] = random.random() * 10
        if self.chest:
            self.entity_phase["chest"] = random.random() * 10
        if self.door:
            self.entity_phase["door"] = random.random() * 10
        if self.mix_station:
            self.entity_phase["mix_station"] = random.random() * 10
        if self.key:
            self.entity_phase["key"] = random.random() * 10

    def _find_open_tile(self, x, y, solid: set | None = None):
        """Find a nearby open tile if the desired one is blocked."""
        solid_set = solid if solid is not None else getattr(self, "solid", set())
        if (x, y) not in solid_set:
            return x, y
        for r in range(1, 5):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.config.MAP_WIDTH and 0 <= ny < self.config.MAP_HEIGHT:
                        if (nx, ny) not in solid_set:
                            return nx, ny
        return x, y

    def _compute_reachable(self, solid_set: set[tuple[int, int]], start: tuple[int, int]) -> set[tuple[int, int]]:
        """Return set of tiles reachable via 4-neighborhood from start (excluding solid tiles)."""
        sx, sy = start
        if (sx, sy) in solid_set:
            # If the starting tile is blocked for some reason, treat it as reachable anyway so we can recover.
            solid_set = set(solid_set)
            solid_set.discard((sx, sy))
        w, h = self.config.MAP_WIDTH, self.config.MAP_HEIGHT
        q = [(sx, sy)]
        seen = {(sx, sy)}
        while q:
            x, y = q.pop(0)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in solid_set and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    def _pick_free_reachable(
        self,
        preferred: tuple[int, int],
        reachable: set[tuple[int, int]],
        occupied: set[tuple[int, int]],
        solid_set: set[tuple[int, int]],
    ) -> tuple[int, int]:
        """
        Pick a reachable, non-solid, non-occupied tile near preferred. Falls back to any reachable tile.
        This prevents items spawning in isolated pockets (e.g., behind water/rocks).
        """
        px, py = preferred
        if (px, py) in reachable and (px, py) not in solid_set and (px, py) not in occupied:
            return px, py
        w, h = self.config.MAP_WIDTH, self.config.MAP_HEIGHT
        for r in range(1, 12):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx, ny = px + dx, py + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        if (nx, ny) in reachable and (nx, ny) not in solid_set and (nx, ny) not in occupied:
                            return nx, ny
        # Last resort: pick any reachable tile.
        for nx, ny in reachable:
            if (nx, ny) not in solid_set and (nx, ny) not in occupied:
                return nx, ny
        return px, py

    def _ensure_entity_positions(self):
        """Clamp and adjust entity positions so they are playable."""
        def clamp_tile(tx, ty):
            tx = max(0, min(self.config.MAP_WIDTH - 1, int(tx)))
            ty = max(0, min(self.config.MAP_HEIGHT - 1, int(ty)))
            return tx, ty

        def place(entity, default_x, default_y):
            entity["x"], entity["y"] = clamp_tile(entity.get("x", default_x), entity.get("y", default_y))
            entity["x"], entity["y"] = self._find_open_tile(entity["x"], entity["y"])
            entity["x"], entity["y"] = self._pick_free_reachable((entity["x"], entity["y"]), reachable, occupied, solid_set)
            occupied.add((entity["x"], entity["y"]))

        # Ensure all critical entities are reachable from the player start.
        ts = self.config.TILE_SIZE
        start_tile = (int(self.player_x // ts), int(self.player_y // ts))
        solid_set = getattr(self, "solid", set())
        reachable = self._compute_reachable(solid_set, start_tile)
        occupied: set[tuple[int, int]] = {start_tile}

        npc = self.game.get("npc", {})
        if npc:
            place(npc, 5, 4)
        for item in self.items:
            place(item, 8, 6)
        for entity, dx, dy in [(self.mix_station, 9, 5), (self.chest, 12, 4), (self.door, 14, 6)]:
            if entity:
                place(entity, dx, dy)

    def _entity_bob(self, key: str, moving: bool = False):
        phase = self.entity_phase.get(key, 0.0)
        speed = 6 if moving else 3
        amp = self.config.WALK_BOB if moving else self.config.IDLE_BOB
        y = int(math.sin(self.anim_time * speed + phase) * amp)
        x = int(math.sin(self.anim_time * speed * 0.7 + phase) * 1)
        return x, y

    def _float_offset(self, key: str):
        phase = self.entity_phase.get(key, 0.0)
        y = int(math.sin(self.anim_time * 2 + phase) * 3) - 2
        return 0, y

    def _blit_sprite(self, key: str, tile_x: int, tile_y: int, extra=(0, 0)):
        surf = self.surfaces.get(key)
        if not surf:
            return
        ox, oy = self.sprite_offsets.get(key, (0, 0))
        ex, ey = extra
        px = tile_x * self.config.TILE_SIZE + ox + ex
        py = tile_y * self.config.TILE_SIZE + oy + ey
        self.screen.blit(surf, (px, py))

    def _blit_sprite_px(self, key: str, px: int, py: int, extra=(0, 0)):
        surf = self.surfaces.get(key)
        if not surf:
            return
        ox, oy = self.sprite_offsets.get(key, (0, 0))
        ex, ey = extra
        self.screen.blit(surf, (px + ox + ex, py + oy + ey))

    def _draw_building_exterior(self, center_x: int, center_y: int, theme: str, label: str):
        """Draw a consistent retro RPG-style building exterior."""
        ts = self.config.TILE_SIZE
        # Use deterministic code-drawn exteriors for consistent look across all runs.
        # Generated building sprites vary too much and can reintroduce matte artifacts.
        bw = int(ts * 2.7)
        bh = int(ts * 2.2)
        x0 = center_x - bw // 2
        y0 = center_y - bh + ts // 2

        if theme == "inn":
            roof_main = (140, 92, 65)
            roof_hi = (186, 130, 88)
            wall = (198, 182, 150)
            trim = (122, 92, 70)
            sign_bg = (98, 68, 44)
        else:  # shop
            roof_main = (118, 70, 50)
            roof_hi = (164, 102, 78)
            wall = (188, 170, 144)
            trim = (110, 84, 62)
            sign_bg = (86, 58, 40)

        # Ground apron/path near entrance.
        pygame.draw.rect(
            self.screen,
            (205, 178, 142),
            (x0 + 8, center_y + 4, bw - 16, 18),
            border_radius=6,
        )

        # Main walls.
        pygame.draw.rect(self.screen, wall, (x0 + 10, y0 + ts - 6, bw - 20, bh - ts + 6), border_radius=8)
        pygame.draw.rect(self.screen, trim, (x0 + 10, y0 + ts - 6, bw - 20, bh - ts + 6), 2, border_radius=8)

        # Roof body + top highlight tiles.
        pygame.draw.rect(self.screen, roof_main, (x0, y0 + 4, bw, ts + 6), border_radius=10)
        tile_w = max(10, ts // 5)
        for xx in range(x0 + 6, x0 + bw - 6, tile_w):
            pygame.draw.rect(self.screen, roof_hi, (xx, y0 + 10, tile_w - 2, 7), border_radius=2)
            pygame.draw.line(self.screen, self.terrain._shift(roof_main, -22), (xx, y0 + 18), (xx + tile_w - 2, y0 + 18), 1)

        # Windows.
        wx1 = x0 + 20
        wx2 = x0 + bw - 44
        wy = y0 + ts + 10
        for wx in [wx1, wx2]:
            pygame.draw.rect(self.screen, (86, 160, 210), (wx, wy, 22, 16), border_radius=3)
            pygame.draw.rect(self.screen, (235, 230, 170), (wx + 2, wy + 12, 18, 4), border_radius=2)
            pygame.draw.rect(self.screen, trim, (wx, wy, 22, 16), 2, border_radius=3)

        # Door centered on entrance.
        pygame.draw.rect(self.screen, (112, 78, 52), (center_x - 15, center_y - 20, 30, 42), border_radius=6)
        pygame.draw.rect(self.screen, (82, 56, 38), (center_x - 15, center_y - 20, 30, 42), 2, border_radius=6)
        pygame.draw.circle(self.screen, (238, 210, 98), (center_x + 9, center_y + 2), 3)

        # Sign plaque.
        pygame.draw.rect(self.screen, sign_bg, (x0 + 14, y0 + ts + 8, 50, 16), border_radius=4)
        txt = self.font.render(label, True, (238, 236, 226))
        self.screen.blit(txt, (x0 + 18, y0 + ts + 8))

    def _indoor_scene_key(self):
        # Scene backdrops are disabled in favor of deterministic in-engine interiors.
        return None

    def _draw_indoor_setpieces(self):
        # Intentionally disabled: generated indoor setpiece sprites can be oversized
        # and visually inconsistent. Interiors are rendered by InteriorRenderer only.
        return

    def _anim_key(self, base: str, moving: bool = False):
        alt = f"{base}_alt"
        if alt in self.surfaces:
            if moving:
                return alt if int(self.anim_time * 2) % 2 == 1 else base
            return base
        return base

    def _wrap_text(self, text: str, max_chars: int):
        words = text.split()
        lines = []
        current = []
        for w in words:
            if len(" ".join(current + [w])) <= max_chars:
                current.append(w)
            else:
                lines.append(" ".join(current))
                current = [w]
        if current:
            lines.append(" ".join(current))
        return lines

    def _wrap_text_px(self, text: str, max_width_px: int):
        """Word-wrap using pixel width (prevents clipping)."""
        words = text.split()
        if not words:
            return [""]
        lines = []
        cur = words[0]
        for w in words[1:]:
            candidate = f"{cur} {w}"
            if self.font.size(candidate)[0] <= max_width_px:
                cur = candidate
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines

    def _quest_progress(self):
        steps = self._quest_step_states()
        done = sum(1 for _, ok in steps if ok)
        total = len(steps)
        return done, total, f"{done}/{total} steps"

    def _quest_steps(self):
        # Render a compact view of the same underlying step state list.
        steps = self._quest_step_states()
        return [("✓ " if done else "→ ") + label for label, done in steps]

    def _all_goals_complete(self) -> bool:
        """Return True if every selected goal type for this level has been completed."""
        types = set(getattr(self, "quest_types", []) or [])
        done_flags = {
            "cure": bool(getattr(self, "npc_healed", False)),
            "lost_item": bool(getattr(self, "lost_item_returned", False)),
            "key_and_door": bool(getattr(self, "door_opened", False)),
            "repair_bridge": bool(getattr(self, "bridge_repaired", False)),
        }
        for goal in types:
            if goal in done_flags and not done_flags[goal]:
                return False
        return True

    def _quest_step_states(self):
        npc_name = self.game.get("npc", {}).get("name", "NPC")
        types = list(getattr(self, "quest_types", []) or [])
        steps: list[tuple[str, bool]] = []
        steps.append((f"Talk to {npc_name}", getattr(self, "talked_to_npc", False)))

        # Cure
        if "cure" in types:
            ingredient_ids = [it["id"] for it in self.items if str(it.get("kind") or "").lower() == "ingredient"]
            have = sum(1 for iid in ingredient_ids if iid in self.items_collected)
            steps.extend([
                ("Gather ingredients", (not ingredient_ids) or (have >= len(ingredient_ids))),
                ("Brew the remedy", getattr(self, "mixed_potion", False)),
                ("Heal the patient", getattr(self, "npc_healed", False)),
            ])

        # Lost item
        if "lost_item" in types:
            steps.extend([
                ("Find the lost item", getattr(self, "lost_item_found", False)),
                ("Return it to NPC", getattr(self, "lost_item_returned", False)),
            ])

        # Key and door
        if "key_and_door" in types:
            steps.extend([
                ("Open the chest", getattr(self, "chest_opened", False)),
                ("Pick up the key", getattr(self, "key_collected", False)),
                ("Unlock the door", getattr(self, "door_opened", False)),
            ])

        # Repair bridge
        if "repair_bridge" in types:
            steps.extend([
                ("Buy planks, rope, nails", self.has_materials()),
                ("Repair the bridge", getattr(self, "bridge_repaired", False)),
            ])

        return steps

    def _quest_summary(self):
        goal = self.quest.get("goal", "Complete the quest") if hasattr(self, "quest") else "Complete the quest"
        steps = self.quest.get("steps", []) if hasattr(self, "quest") else []
        if not steps:
            steps = [s.replace("✓ ", "").replace("→ ", "") for s in self._quest_steps()]
        short_steps = "; ".join(steps[:3])
        next_step = self._next_step_label()
        if short_steps:
            return f"Quest: {goal}. Steps: {short_steps}. Next: {next_step}."
        return f"Quest: {goal}. Next: {next_step}."

    def _next_step_label(self):
        for label, done in self._quest_step_states():
            if not done:
                return label
        return "Quest complete"

    def _level_complete(self):
        if self.level_index < len(self.levels) - 1:
            self.msg(f"Level {self.level_index + 1} complete! Press N for next level.")
        else:
            self.msg("All levels complete! Press R to replay.")
    
    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_r:
                        if self.game_won and self.level_index == len(self.levels) - 1:
                            # Replay the same generated 1-3 levels
                            self.load_level(0)
                        else:
                            self.reset_game()
                            self.terrain.generate_layout()
                            self.msg("Restarted!")
                    elif event.key in (pygame.K_n, pygame.K_RETURN):
                        if self.game_won and self.level_index < len(self.levels) - 1:
                            self.load_level(self.level_index + 1)
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        # Buy items while inside a building.
                        if self.scene == "indoor" and self.current_building:
                            # Only allow buying near the indoor NPC/counter.
                            nx, ny = self.current_building["npc_pos"]
                            ts = self.config.TILE_SIZE
                            px = int((self.player_x + ts//2) // ts)
                            py = int((self.player_y + ts//2) // ts)
                            if abs(nx - px) <= 2 and abs(ny - py) <= 2:
                                idx = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2}[event.key]
                                self.buy_good(idx)
                    elif event.key == pygame.K_SPACE or event.key == pygame.K_e:
                        # Sleeping: SPACE wakes early.
                        if getattr(self, "sleeping", False):
                            self._wake_from_sleep(early=True)
                        else:
                            self.interact()
            
            keys = pygame.key.get_pressed()
            if not getattr(self, "sleeping", False):
                dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
                dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
                self.move(dx * self.config.PLAYER_SPEED, dy * self.config.PLAYER_SPEED)
                if not self.game_won:
                    self.check_pickups()
            else:
                self.is_moving = False
            
            self.effects.update()
            self.anim_time += self.config.ANIM_SPEED
            if self.message_timer > 0:
                self.message_timer -= 1

            # Auto-wake after ~5 seconds.
            if getattr(self, "sleeping", False) and pygame.time.get_ticks() >= int(getattr(self, "sleep_end_ms", 0) or 0):
                self._wake_from_sleep(early=False)
            
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()
    
    def move(self, dx, dy):
        ts = self.config.TILE_SIZE
        mw = self.config.MAP_WIDTH * ts
        mh = self.config.MAP_HEIGHT * ts
        self.is_moving = dx != 0 or dy != 0
        
        new_x = self.player_x + dx
        if 0 <= new_x < mw - ts:
            tile_x = int((new_x + ts//2) // ts)
            tile_y = int((self.player_y + ts//2) // ts)
            if (tile_x, tile_y) not in self.solid:
                self.player_x = new_x
        
        new_y = self.player_y + dy
        if 0 <= new_y < mh - ts:
            tile_x = int((self.player_x + ts//2) // ts)
            tile_y = int((new_y + ts//2) // ts)
            if (tile_x, tile_y) not in self.solid:
                self.player_y = new_y

    def has_materials(self) -> bool:
        needed = {"planks", "rope", "nails"}
        return needed.issubset(set(self.items_collected))

    def _toggle_day_night(self) -> str:
        """Toggle between day and night (treat anything non-day as night)."""
        cur = (self.game.get("time_of_day") or "day").lower()
        nxt = "night" if cur == "day" else "day"
        return nxt

    def _apply_time_of_day(self, new_time: str):
        self.game["time_of_day"] = new_time
        # Update terrain palette and effects behavior.
        allow_flash = new_time in ["night", "dusk", "sunset"]
        self.effects = EffectsManager(allow_flash=allow_flash)
        self.terrain = TerrainRenderer(self.game, self.config)

    def _wake_from_sleep(self, early: bool = False):
        if not getattr(self, "sleeping", False):
            return
        self.sleeping = False
        self.sleep_end_ms = 0
        new_time = self._toggle_day_night()
        self._apply_time_of_day(new_time)
        self.effects.complete(self.player_x + self.config.TILE_SIZE // 2, self.player_y + self.config.TILE_SIZE // 2)
        if early:
            self.msg(f"You wake up early. It is now {new_time}.")
        else:
            self.msg(f"You wake up rested. It is now {new_time}.")

    def buy_good(self, idx: int):
        if not self.current_building:
            return
        goods = self.current_building.get("goods", [])
        if idx < 0 or idx >= len(goods):
            return
        g = goods[idx]
        item_id = g["id"]
        if item_id in self.items_collected:
            self.msg(f"Already bought {g['name']}.")
            return
        price = int(g.get("price", 0))
        if self.money < price:
            self.msg(f"Not enough gold. Need {price}g, you have {self.money}g.")
            return
        self.money -= price
        self.items_collected.add(item_id)
        self.inventory.append(g["name"])
        self.effects.pickup(self.player_x + self.config.TILE_SIZE // 2, self.player_y + self.config.TILE_SIZE // 2)
        self.msg(f"Bought {g['name']} for {price}g. Gold left: {self.money}g.")
    
    def check_pickups(self):
        ts = self.config.TILE_SIZE
        px = int((self.player_x + ts//2) // ts)
        py = int((self.player_y + ts//2) // ts)
        
        if self.scene == "outdoor":
            active_items = self.items
        else:
            active_items = self.current_building.get("items", []) if self.current_building else []
        for item in active_items:
            if item["id"] in self.items_collected:
                continue
            if item["x"] == px and item["y"] == py:
                self.items_collected.add(item["id"])
                self.inventory.append(item["name"])
                self.effects.pickup(self.player_x + ts//2, self.player_y + ts//2)
                kind = str(item.get("kind") or "").lower()
                if kind == "lost_item":
                    self.lost_item_found = True

                if kind == "ingredient":
                    ingredient_ids = [it["id"] for it in self.items if str(it.get("kind") or "").lower() == "ingredient"]
                    have = sum(1 for iid in ingredient_ids if iid in self.items_collected)
                    if ingredient_ids and have >= len(ingredient_ids):
                        self.msg("All ingredients found! Mix at the cauldron.")
                    else:
                        self.msg(f"Found {item['name']}! ({have}/{len(ingredient_ids)} ingredients)")
                else:
                    self.msg(f"Found {item['name']}!")

        # Key pickup (for key_and_door quest)
        if ("key_and_door" in getattr(self, "quest_types", [])) and self.key_spawned and not self.key_collected and self.key_pos:
            if self.key_pos[0] == px and self.key_pos[1] == py:
                self.key_collected = True
                key_name = self.key.get("name", "Key") if self.key else "Key"
                self.inventory.append(key_name)
                self.effects.pickup(self.player_x + ts//2, self.player_y + ts//2)
                self.msg(f"Picked up {key_name}!")
    
    def interact(self):
        ts = self.config.TILE_SIZE
        px = int((self.player_x + ts//2) // ts)
        py = int((self.player_y + ts//2) // ts)

        # Building transitions
        if self.scene == "outdoor":
            for b in self.buildings:
                ex, ey = b["entrance"]
                if abs(ex - px) <= 1 and abs(ey - py) <= 1:
                    self.current_building = b
                    interior_theme = "inn_lobby" if b.get("theme") == "inn" else b["theme"]
                    self.interior = InteriorRenderer(self.config, theme=interior_theme, door_x=b["exit"][0])
                    self.solid_indoor = self.interior.get_solid_tiles()
                    nx, ny = b["npc_pos"]
                    self.solid_indoor.add((nx, ny))
                    if b.get("theme") == "inn":
                        for gx, gy in b.get("guest_npcs", []):
                            self.solid_indoor.add((gx, gy))
                    self.indoor_mode = "lobby"

                    self.scene = "indoor"
                    self.solid = self.solid_indoor
                    exit_x, exit_y = b["exit"]
                    self.player_x = exit_x * ts
                    self.player_y = (exit_y - 2) * ts
                    self.msg(f"Entered {b['name']}. (SPACE near the door to exit)")
                    if b.get("goods"):
                        gtxt = ", ".join([f"{i+1}:{g['name']}({g['price']}g)" for i, g in enumerate(b["goods"][:3])])
                        self.msg(f"Entered {b['name']}. Buy: {gtxt}. Gold: {self.money}g.")
                    if b.get("theme") == "inn":
                        self.msg(f"Inn Host: 'Check in at the desk. Room {b.get('room_number', '3')} is 12g.'")
                    return
        else:
            ex, ey = self.current_building["exit"] if self.current_building else (self.config.MAP_WIDTH // 2, self.config.MAP_HEIGHT - 2)
            if self.current_building and self.current_building.get("theme") == "inn":
                # Lobby <-> room transitions + outside exit.
                if self.indoor_mode == "room":
                    rx, ry = self.current_building.get("room_exit", (self.config.MAP_WIDTH // 2, self.config.MAP_HEIGHT - 1))
                    if abs(rx - px) <= 1 and abs(ry - py) <= 1:
                        self.indoor_mode = "lobby"
                        self.interior = InteriorRenderer(self.config, theme="inn_lobby", door_x=self.current_building["exit"][0])
                        self.solid_indoor = self.interior.get_solid_tiles()
                        nx, ny = self.current_building["npc_pos"]
                        self.solid_indoor.add((nx, ny))
                        for gx, gy in self.current_building.get("guest_npcs", []):
                            self.solid_indoor.add((gx, gy))
                        self.solid = self.solid_indoor
                        self.player_x = rx * ts
                        self.player_y = (ry - 2) * ts
                        self.msg("You return to the inn lobby.")
                        return
                else:
                    if abs(ex - px) <= 1 and abs(ey - py) <= 1:
                        self.scene = "outdoor"
                        self.solid = self.solid_outdoor
                        ox, oy = self.current_building["entrance"] if self.current_building else (3, self.config.MAP_HEIGHT // 2)
                        self.player_x = ox * ts
                        self.player_y = (oy + 1) * ts
                        self.msg("Back outside.")
                        return
                    rdx, rdy = self.current_building.get("room_door", (self.config.MAP_WIDTH // 2, 5))
                    if abs(rdx - px) <= 1 and abs(rdy - py) <= 1:
                        if not self.current_building.get("room_unlocked", False):
                            self.msg("Room door is locked. Talk to the inn host at the desk.")
                            return
                        self.indoor_mode = "room"
                        self.interior = InteriorRenderer(self.config, theme="inn_room", door_x=self.current_building["room_exit"][0])
                        self.solid_indoor = self.interior.get_solid_tiles()
                        self.solid = self.solid_indoor
                        self.player_x = rdx * ts
                        self.player_y = (rdy + 2) * ts
                        self.msg(f"You unlock Room {self.current_building.get('room_number', '3')} and step inside.")
                        return
            else:
                if abs(ex - px) <= 1 and abs(ey - py) <= 1:
                    self.scene = "outdoor"
                    self.solid = self.solid_outdoor
                    ox, oy = self.current_building["entrance"] if self.current_building else (3, self.config.MAP_HEIGHT // 2)
                    self.player_x = ox * ts
                    self.player_y = (oy + 1) * ts
                    self.msg("Back outside.")
                    return

            # Indoor NPC dialogue
            if self.current_building:
                nx, ny = self.current_building["npc_pos"]
                if abs(nx - px) <= 1 and abs(ny - py) <= 1:
                    who = self.current_building.get("npc", "NPC")
                    if self.current_building.get("theme") == "inn":
                        if not self.current_building.get("room_paid", False):
                            price = 12
                            if self.money < price:
                                self.msg(f"{who}: 'A room is {price}g. You only have {self.money}g right now.'")
                            else:
                                self.money -= price
                                self.current_building["room_paid"] = True
                                self.current_building["room_unlocked"] = True
                                self.items_collected.add("inn_room_key")
                                self.msg(
                                    f"{who}: 'Thank you. Room {self.current_building.get('room_number', '3')} is yours tonight. "
                                    f"The key unlocks the hall door.' (-{price}g)"
                                )
                        else:
                            line = self._next_dialogue_line(
                                "inn_host_paid",
                                self.current_building.get("smalltalk", []),
                            )
                            self.msg(
                                f"{who}: 'Your room {self.current_building.get('room_number', '3')} is down the hall. "
                                f"{line}'"
                            )
                    else:
                        line = self._next_dialogue_line(
                            "shopkeeper_talk",
                            self.current_building.get("smalltalk", []) or [self.current_building.get("dialogue", "Hello!")],
                        )
                        self.msg(f'{who}: "{line}"')
                    return
                # Inn guest flavor dialogue.
                if self.current_building.get("theme") == "inn" and self.indoor_mode == "lobby":
                    for i, (gx, gy) in enumerate(self.current_building.get("guest_npcs", []), start=1):
                        if abs(gx - px) <= 1 and abs(gy - py) <= 1:
                            profiles = self.current_building.get("guest_profiles", [])
                            if profiles and i - 1 < len(profiles):
                                profile = profiles[i - 1]
                                gname = profile.get("name", f"Guest {i}")
                                glines = profile.get("lines", [])
                            else:
                                gname = f"Guest {i}"
                                glines = [
                                    "The common room feels warmer once the lamps are lit.",
                                    "I keep my boots by the hearth so they dry by morning.",
                                    "The innkeeper remembers every regular by name.",
                                ]
                            line = self._next_dialogue_line(f"guest_{i}", glines)
                            self.msg(f"{gname}: '{line}'")
                            return
        
        npc = self.game["npc"]
        if abs(npc["x"] - px) <= 1 and abs(npc["y"] - py) <= 1:
            did_progress = False

            if not self.talked_to_npc:
                self.talked_to_npc = True

            # Cure completion happens at the patient (NPC) after mixing the potion.
            if ("cure" in self.quest_types) and (not self.npc_healed):
                if self.mixed_potion:
                    self.potion_given = True
                    self.npc_healed = True
                    did_progress = True
                    self.effects.complete(self.player_x + ts//2, self.player_y + ts//2)
                    self.msg(f'{npc["name"]}: "{npc.get("dialogue_complete", "I feel better!")}"')

            # Lost item return happens at the NPC.
            if ("lost_item" in self.quest_types) and (not self.lost_item_returned):
                if self.lost_item_found:
                    self.lost_item_returned = True
                    did_progress = True
                    self.effects.complete(self.player_x + ts//2, self.player_y + ts//2)
                    self.msg(f'{npc["name"]}: "{npc.get("dialogue_complete", "You found it!")}"')

            if not did_progress:
                if self._all_goals_complete():
                    self.msg(f'{npc["name"]}: "{npc.get("dialogue_complete", "Well done!")}"')
                else:
                    # Rich quest-NPC dialogue with light guidance baked into tone.
                    qlines = [
                        npc.get("dialogue_intro", "You made it. I knew you would."),
                        "Keep your pace steady. Rushing creates mistakes.",
                        "When in doubt, trust what you've already learned on this road.",
                        f"If you are unsure, focus on this next step: {self._next_step_label()}.",
                    ]
                    self.msg(f'{npc["name"]}: "{self._next_dialogue_line("quest_npc", qlines)}"')

            if not self.quest_known:
                self.quest_known = True
                summary = self._quest_summary()
                if "Steps:" in summary:
                    parts = summary.split("Steps:", 1)
                    msg = f"{parts[0].strip()}\nSteps: {parts[1].strip()}"
                else:
                    msg = summary
                self.msg(msg[:160])

            # If that interaction completed the final objective, end the level.
            if did_progress and self._all_goals_complete():
                self.game_won = True
                self._level_complete()
            return

        # Indoor interactions (inn sleeping)
        if self.scene == "indoor" and self.current_building:
            if self.current_building.get("theme") == "inn":
                if getattr(self, "indoor_mode", "lobby") != "room":
                    return
                bed = self.current_building.get("bed_pos")
                if bed:
                    bx, by = bed
                    # Room sprites can cover multiple tiles; allow a wider interaction zone.
                    if abs(bx - px) <= 2 and abs(by - py) <= 2:
                        price = 12
                        if self.money < price:
                            self.msg(f"Not enough gold to rent a bed. Need {price}g.")
                            return
                        if getattr(self, "sleeping", False):
                            self.msg("Already sleeping...")
                            return
                        self.money -= price
                        # Snap to the bed tile and sleep for ~5 seconds (SPACE to wake early).
                        self.player_x = bx * ts
                        self.player_y = by * ts
                        self.sleeping = True
                        self.sleep_end_ms = pygame.time.get_ticks() + 5000
                        self.msg(f"You lie down... zzz (-{price}g). (SPACE to wake)")
                        return

        # Bridge interaction (repair_bridge goal)
        if ("repair_bridge" in self.quest_types) and self.bridge_tiles:
            # If you're adjacent to the bridge, you can repair it.
            for bx, by in self.bridge_tiles:
                if abs(bx - px) <= 1 and abs(by - py) <= 1:
                    if self.bridge_repaired:
                        self.msg("The bridge is sturdy now.")
                        return
                    if not self.has_materials():
                        self.msg("You need planks, rope, and nails. Buy them at the Shop.")
                        return
                    # Consume materials
                    for item_id in ["planks", "rope", "nails"]:
                        self.items_collected.discard(item_id)
                    self.bridge_repaired = True
                    # Open the bridge tiles
                    for t in self.bridge_tiles:
                        self.solid_outdoor.discard(t)
                    self.solid = self.solid_outdoor
                    self.effects.complete(self.player_x + ts//2, self.player_y + ts//2)
                    self.msg("Repaired the bridge!")
                    if self._all_goals_complete():
                        self.game_won = True
                        self._level_complete()
                    return

        # Mix station interaction (cure goal)
        if ("cure" in self.quest_types) and self.mix_station:
            if abs(self.mix_station["x"] - px) <= 1 and abs(self.mix_station["y"] - py) <= 1:
                if self.mixed_potion:
                    self.msg("The potion is ready.")
                else:
                    ingredient_ids = [it["id"] for it in self.items if str(it.get("kind") or "").lower() == "ingredient"]
                    have = sum(1 for iid in ingredient_ids if iid in self.items_collected)
                    if ingredient_ids and have >= len(ingredient_ids):
                        self.mixed_potion = True
                        self.inventory.append("Healing Potion")
                        self.effects.smoke(self.mix_station["x"] * ts + ts//2, self.mix_station["y"] * ts + ts//2)
                        self.msg("Quest update: potion mixed.")
                    else:
                        self.msg("Need more ingredients.")
                return

        # Chest / Key / Door interactions (key_and_door goal)
        if ("key_and_door" in self.quest_types) and self.chest:
            if abs(self.chest["x"] - px) <= 1 and abs(self.chest["y"] - py) <= 1:
                if not self.chest_opened:
                    self.chest_opened = True
                    self.key_spawned = True
                    self.key_pos = (self.chest["x"], self.chest["y"])
                    self.solid.discard((self.chest["x"], self.chest["y"]))
                    self.effects.smoke(self.chest["x"] * ts + ts//2, self.chest["y"] * ts + ts//2)
                    self.msg("Quest update: chest opened. A key appears.")
                else:
                    self.msg("The chest is empty.")
                return

        if ("key_and_door" in self.quest_types) and self.door:
            if abs(self.door["x"] - px) <= 1 and abs(self.door["y"] - py) <= 1:
                if self.door_opened:
                    self.msg("The door is open.")
                elif self.key_collected:
                    self.door_opened = True
                    self.solid.discard((self.door["x"], self.door["y"]))
                    self.effects.complete(self.player_x + ts//2, self.player_y + ts//2)
                    self.msg("Quest update: door unlocked!")
                    if self._all_goals_complete():
                        self.game_won = True
                        self._level_complete()
                else:
                    self.msg("The door is locked.")
                return

        self.msg("Nothing here... (SPACE to interact)")
    
    def msg(self, text):
        self.message = text
        self.message_timer = 250

    def _next_dialogue_line(self, key: str, lines: list[str]) -> str:
        if not lines:
            return "..."
        idx = self.dialogue_state.get(key, 0) % len(lines)
        self.dialogue_state[key] = idx + 1
        return lines[idx]
    
    def draw(self):
        ts = self.config.TILE_SIZE
        map_w = self.config.MAP_WIDTH * ts
        map_h = self.config.MAP_HEIGHT * ts
        
        # Draw terrain
        if self.scene == "outdoor":
            self.terrain.draw(self.screen, self.anim_time)
        else:
            scene_key = self._indoor_scene_key()
            if scene_key and scene_key in self.surfaces:
                self.screen.blit(self.surfaces[scene_key], (0, 0))
            else:
                self.interior.draw(self.screen, self.anim_time)
            self._draw_indoor_setpieces()

        # Draw broken/repaired bridge (outdoor)
        if self.scene == "outdoor" and self.bridge_tiles:
            ts = self.config.TILE_SIZE
            # Bridge is vertical (two tiles). Draw as a continuous structure.
            tiles = sorted(list(self.bridge_tiles), key=lambda t: (t[1], t[0]))
            for idx, (bx, by) in enumerate(tiles):
                x = bx * ts
                y = by * ts
                mid = y + ts // 2

                if self.bridge_repaired:
                    # Fixed bridge: wooden planks + side ropes
                    pygame.draw.rect(self.screen, (150, 110, 75), (x, mid - 12, ts, 24))
                    for px in range(x + 10, x + ts - 10, 12):
                        pygame.draw.line(self.screen, (120, 85, 55), (px, mid - 10), (px, mid + 10), 2)
                    # Side ropes
                    pygame.draw.line(self.screen, (210, 190, 140), (x + 6, mid - 14), (x + ts - 6, mid - 14), 2)
                    pygame.draw.line(self.screen, (210, 190, 140), (x + 6, mid + 14), (x + ts - 6, mid + 14), 2)
                else:
                    # Broken bridge: partial boards with a gap + rubble
                    pygame.draw.rect(self.screen, (95, 75, 60), (x, mid - 12, ts, 24))
                    # Missing center boards
                    pygame.draw.rect(self.screen, (35, 35, 45), (x + ts // 2 - 16, mid - 10, 32, 20), border_radius=4)
                    # Broken planks
                    pygame.draw.line(self.screen, (120, 85, 55), (x + 8, mid - 10), (x + ts // 2 - 18, mid - 10), 3)
                    pygame.draw.line(self.screen, (120, 85, 55), (x + ts // 2 + 18, mid + 10), (x + ts - 8, mid + 10), 3)
                    # Nails / debris specks
                    pygame.draw.circle(self.screen, (40, 40, 50), (x + ts // 2 - 6, mid + 4), 2)
                    pygame.draw.circle(self.screen, (40, 40, 50), (x + ts // 2 + 8, mid - 2), 2)
        
        # Draw items (outdoor pickups)
        for i, item in enumerate(self.items):
            if item["id"] in self.items_collected:
                continue
            sprite_key = "item" if i == 0 else "item2" if i == 1 else "item"
            ox, oy = self._float_offset(item["id"])
            if self.scene == "outdoor":
                self._blit_sprite(sprite_key, item["x"], item["y"], (ox, oy))

        # Indoor shop displays (visual only; buying happens via keys)
        if self.scene == "indoor" and self.current_building:
            goods = self.current_building.get("goods", [])
            # Draw 2-3 goods as floating icons near the shelves
            for gi, g in enumerate(goods[:3]):
                theme = self.current_building.get("theme")
                if theme == "shop":
                    # Put items on the back shelves (not the middle of the floor).
                    shelf_spots = [(3, 2), (7, 2), (11, 2), (4, 4), (10, 4)]
                    gx, gy = shelf_spots[gi % len(shelf_spots)]
                else:
                    # Avoid drawing random item icons in inn/other interiors.
                    continue
                ox, oy = self._float_offset(g["id"])
                sprite = "item"
                if g["id"] == "planks" and "mat_planks" in self.surfaces:
                    sprite = "mat_planks"
                elif g["id"] == "rope" and "mat_rope" in self.surfaces:
                    sprite = "mat_rope"
                elif g["id"] == "nails" and "mat_nails" in self.surfaces:
                    sprite = "mat_nails"
                self._blit_sprite(sprite, gx, gy, (ox, oy))

        # Draw key (key_and_door goal)
        if ("key_and_door" in self.quest_types) and self.key_spawned and not self.key_collected and self.key_pos:
            ox, oy = self._float_offset("key")
            self._blit_sprite("key", self.key_pos[0], self.key_pos[1], (ox, oy))
        
        # Draw chest
        if ("key_and_door" in self.quest_types) and self.chest and not self.chest_opened:
            self._blit_sprite("chest", self.chest["x"], self.chest["y"])

        # Draw door
        if ("key_and_door" in self.quest_types) and self.door and not self.door_opened:
            self._blit_sprite("door", self.door["x"], self.door["y"])

        # Draw mix station
        if ("cure" in self.quest_types) and self.mix_station:
            self._blit_sprite("mix_station", self.mix_station["x"], self.mix_station["y"])

        # Draw building entrance markers (outdoor)
        if self.scene == "outdoor":
            for i, b in enumerate(self.buildings):
                ex, ey = b["entrance"]
                cx = ex * ts + ts // 2
                cy = ey * ts + ts // 2
                label = "SHOP" if b["theme"] == "shop" else "INN"
                self._draw_building_exterior(cx, cy, b["theme"], label)
        
        # Draw NPC
        npc = self.game["npc"]
        if ("cure" in self.quest_types) and (not self.npc_healed) and self.surfaces.get("npc_sick"):
            npc_base = "npc_sick"
        else:
            npc_base = "npc_healed" if self.npc_healed and self.surfaces.get("npc_healed") else "npc"
        ox, oy = self._entity_bob("npc")
        if self.scene == "outdoor":
            self._blit_sprite(npc_base, npc["x"], npc["y"], (ox, oy))
        else:
            # Indoor NPC uses per-building unique sprite (generated at level creation).
            if self.current_building:
                if self.current_building.get("theme") == "inn" and getattr(self, "indoor_mode", "lobby") == "room":
                    # Private room mode: no host/guest NPCs inside the bedroom.
                    nx, ny = None, None
                else:
                    nx, ny = self.current_building["npc_pos"]
                if nx is not None:
                    key = self.current_building.get("npc_sprite_key", "npc")
                    if key not in self.surfaces:
                        key = "npc"
                    self._blit_sprite(key, nx, ny, (0, 0))
                # Inn lobby extra NPCs for life.
                if self.current_building.get("theme") == "inn" and getattr(self, "indoor_mode", "lobby") == "lobby":
                    for i, (gx, gy) in enumerate(self.current_building.get("guest_npcs", []), start=1):
                        gkey = "npc" if i % 2 == 0 else key
                        if gkey not in self.surfaces:
                            gkey = key
                        self._blit_sprite(gkey, gx, gy, (0, 0))
                    # Room door marker in lobby.
                    rdx, rdy = self.current_building.get("room_door", (self.config.MAP_WIDTH // 2, 5))
                    tag = pygame.draw.rect(self.screen, (75, 55, 40), (rdx * ts + 18, rdy * ts - 10, 34, 14), border_radius=3)
                    txt = self.font.render(f"R{self.current_building.get('room_number', '3')}", True, (235, 225, 200))
                    self.screen.blit(txt, (rdx * ts + 22, rdy * ts - 10))
        
        # Draw player
        moving = getattr(self, "is_moving", False)
        ox, oy = self._entity_bob("player", moving=moving)
        self._blit_sprite_px("player", self.player_x, self.player_y, (ox, oy))
        
        # Effects
        self.effects.draw(self.screen)

        # Sleeping overlay (inn)
        if getattr(self, "sleeping", False):
            overlay = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
            overlay.fill((10, 10, 20, 140))
            self.screen.blit(overlay, (0, 0))
            # Floating Zzz above the player
            z = self.font_title.render("Z z z", True, (230, 230, 255))
            self.screen.blit(z, (int(self.player_x + ts * 0.2), int(self.player_y - ts * 0.6)))
            sub = self.font.render("Sleeping... (SPACE to wake)", True, (230, 230, 255))
            self.screen.blit(sub, (12, map_h - 30))

        # Quest log (pinned)
        self.draw_quest_log(map_w)
        
        # UI Panel
        self.draw_ui(map_w)
        
        # Message box
        if self.message_timer > 0 and self.message:
            padding_x = 22
            max_text_w = (map_w - 24) - (padding_x * 2)

            raw_lines = self.message.split("\n")
            lines = []
            for raw in raw_lines:
                if raw.strip() == "":
                    continue
                lines.extend(self._wrap_text_px(raw, max_text_w))
            lines = lines[:4]
            box_h = 36 + 22 * len(lines)
            box_y = map_h - box_h - 12
            box_w = map_w - 24
            
            s = pygame.Surface((box_w, box_h))
            s.fill((20, 20, 35))
            s.set_alpha(235)
            self.screen.blit(s, (12, box_y))
            pygame.draw.rect(self.screen, (100, 100, 140), (12, box_y, box_w, box_h), 3, border_radius=5)
            
            for i, line in enumerate(lines):
                color = (255, 255, 255)
                if i == 0 and ":" in line[:22]:
                    color = (255, 230, 170)
                text = self.font.render(line, True, color)
                self.screen.blit(text, (padding_x, box_y + 10 + i * 22))
        
        pygame.display.flip()

    def draw_quest_log(self, map_w):
        x = 12
        y = 12
        w = min(360, map_w - 24)
        lines = []
        if not getattr(self, "quest_known", True):
            lines.append("Talk to the NPC to learn your quest.")
        else:
            goal = self.quest.get("goal", "Complete the quest") if hasattr(self, "quest") else "Complete the quest"
            lines.append(f"Goal: {goal}")
            for label, done in self._quest_step_states()[:4]:
                lines.append(("✓ " if done else "→ ") + label)
            lines.append("Next: " + self._next_step_label())
        h = 28 + 18 * len(lines) + 12

        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((15, 15, 25, 210))
        self.screen.blit(panel, (x, y))
        pygame.draw.rect(self.screen, (90, 90, 120), (x, y, w, h), 2, border_radius=4)

        self.screen.blit(self.font_large.render("QUEST LOG", True, (200, 200, 255)), (x + 10, y + 6))
        ty = y + 30
        for line in lines:
            self.screen.blit(self.font.render(line[:40], True, (220, 220, 220)), (x + 10, ty))
            ty += 18
    
    def draw_ui(self, panel_x):
        panel_w = self.config.GAME_WIDTH - panel_x
        
        pygame.draw.rect(self.screen, (25, 25, 40), (panel_x, 0, panel_w, self.config.GAME_HEIGHT))
        pygame.draw.line(self.screen, (60, 60, 90), (panel_x, 0), (panel_x, self.config.GAME_HEIGHT), 3)
        
        x = panel_x + 15
        y = 20
        
        # Title
        title = self.font_title.render(self.game.get("title", "Quest")[:16], True, (255, 215, 0))
        self.screen.blit(title, (x, y))
        y += 34
        level_text = self.font.render(f"Level {self.level_index + 1}/{len(self.levels)}", True, (180, 180, 200))
        self.screen.blit(level_text, (x, y))
        y += 24
        
        # Progress
        done, total, progress_label = self._quest_progress()
        self.screen.blit(self.font_large.render("PROGRESS", True, (150, 200, 255)), (x, y))
        y += 30
        
        # Progress bar
        bar_w = panel_w - 30
        pygame.draw.rect(self.screen, (50, 50, 70), (x, y, bar_w, 20), border_radius=4)
        if total > 0:
            fill_w = int(bar_w * (done / total))
            if fill_w > 0:
                pygame.draw.rect(self.screen, (100, 200, 100), (x, y, fill_w, 20), border_radius=4)
        progress_text = self.font.render(progress_label, True, (255, 255, 255))
        self.screen.blit(progress_text, (x + 5, y + 2))
        y += 40
        
        # Inventory
        self.screen.blit(self.font_large.render("INVENTORY", True, (255, 200, 100)), (x, y))
        y += 28
        
        if self.inventory:
            for item_name in self.inventory[:5]:
                self.screen.blit(self.font.render(f"✓ {item_name[:14]}", True, (150, 255, 150)), (x, y))
                y += 22
        else:
            self.screen.blit(self.font.render("(empty)", True, (100, 100, 120)), (x, y))
        
        y += 20

        # Money
        self.screen.blit(self.font_large.render("GOLD", True, (255, 230, 120)), (x, y))
        y += 24
        self.screen.blit(self.font.render(f"{getattr(self, 'money', 0)}g", True, (255, 230, 120)), (x, y))
        y += 26

        # Shop info (when indoors)
        if getattr(self, "scene", "outdoor") == "indoor" and getattr(self, "current_building", None):
            b = self.current_building
            goods = b.get("goods") or []
            if goods:
                self.screen.blit(self.font_large.render(b.get("name", "Shop").upper(), True, (150, 255, 220)), (x, y))
                y += 26
                hint = "Press 1/2/3 to buy items."
                if "repair_bridge" in self.quest_types:
                    hint = "Buy materials to repair the broken bridge. Press 1/2/3 to buy."
                elif b.get("theme") == "inn":
                    hint = "Inn: sleep by a bed (SPACE) to advance time. 1/2/3 buy snacks."
                else:
                    hint = "Shop items are helpful flavor (some quests require specific materials). Press 1/2/3 to buy."
                self.screen.blit(self.font.render(hint, True, (220, 220, 220)), (x, y))
                y += 20
                for i, g in enumerate(goods[:3]):
                    self.screen.blit(
                        self.font.render(f"{i+1}. {g['name']} ({g['price']}g)", True, (200, 200, 255)),
                        (x, y),
                    )
                    y += 20
                y += 6
        
        # Goal
        self.screen.blit(self.font_large.render("QUEST", True, (255, 150, 150)), (x, y))
        y += 26
        if not getattr(self, "quest_known", True):
            self.screen.blit(self.font.render("→ Talk to the NPC", True, (220, 220, 220)), (x, y))
            y += 20
        else:
            goal_text = self.quest.get("goal", "Complete the quest") if hasattr(self, "quest") else "Complete the quest"
            self.screen.blit(self.font.render(goal_text[:26], True, (220, 220, 220)), (x, y))
            y += 22
            for line in self._quest_steps()[:4]:
                self.screen.blit(self.font.render(line[:28], True, (200, 200, 200)), (x, y))
                y += 20
        
        # Controls
        y = self.config.GAME_HEIGHT - 140
        self.screen.blit(self.font_large.render("CONTROLS", True, (100, 180, 255)), (x, y))
        y += 25
        controls = ["WASD - Move", "SPACE - Interact", "1-3 - Buy (Indoor)", "N/ENTER - Next Level", "R - Restart", "ESC - Quit"]
        for ctrl in controls:
            self.screen.blit(self.font.render(ctrl, True, (120, 120, 150)), (x, y))
            y += 20


# ============================================================
# WEB INTERFACE
# ============================================================

app = Flask(__name__)
config = Config()

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>🎮 Game Generator</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh; color: white; padding: 20px;
        }
        .container { max-width: 700px; margin: 0 auto; }
        h1 {
            text-align: center; font-size: 2.2em; margin-bottom: 8px;
            background: linear-gradient(90deg, #4ade80, #22d3ee);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .subtitle { text-align: center; color: #888; margin-bottom: 25px; }
        .card {
            background: rgba(255,255,255,0.06); border-radius: 12px;
            padding: 20px; margin-bottom: 15px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        label { display: block; margin-bottom: 8px; color: #4ade80; font-weight: bold; }
        input[type="password"], input[type="text"], input[type="number"], textarea {
            width: 100%; padding: 12px; border: 2px solid #333;
            border-radius: 8px; background: #0f0f23; color: white; font-size: 15px;
        }
        input[type="checkbox"] {
            width: auto;
            padding: 0;
            margin: 0;
            accent-color: #4ade80;
            transform: scale(1.12);
            cursor: pointer;
        }
        label { cursor: pointer; }
        input:focus, textarea:focus { border-color: #4ade80; outline: none; }
        textarea { height: 80px; resize: none; }
        button {
            width: 100%; padding: 14px; font-size: 18px; font-weight: bold;
            border: none; border-radius: 8px; cursor: pointer;
            background: linear-gradient(90deg, #4ade80, #22d3ee); color: #1a1a2e;
        }
        button:hover { transform: scale(1.02); }
        button:disabled { background: #444; color: #888; transform: none; }
        .status { text-align: center; padding: 15px; font-size: 16px; }
        .examples { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
        .ex-btn {
            padding: 8px 12px; font-size: 13px; width: auto;
            background: rgba(74, 222, 128, 0.15); border: 1px solid #4ade80; color: #4ade80;
        }
        .rand-btn {
            margin-top: 8px;
            padding: 10px 12px;
            font-size: 14px;
            width: 100%;
            background: rgba(34, 211, 238, 0.2);
            border: 1px solid #22d3ee;
            color: #22d3ee;
        }
        .levels {
            display: flex;
            gap: 8px;
            align-items: center;
            margin-top: 10px;
        }
        .levels input {
            width: 80px;
            text-align: center;
        }
        .tag { background: #4ade80; color: #1a1a2e; padding: 3px 10px; border-radius: 4px; font-size: 12px; }
        .features { font-size: 14px; color: #aaa; line-height: 1.8; }
        .features b { color: #4ade80; }
        a { color: #22d3ee; }
        .spinner {
            display: inline-block; width: 18px; height: 18px;
            border: 3px solid #fff; border-top-color: transparent;
            border-radius: 50%; animation: spin 1s linear infinite; margin-right: 10px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .new { color: #22d3ee; font-size: 11px; margin-left: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 Game Generator</h1>
        <p class="subtitle">Prompt‑Driven Adventure Generator <span class="tag">NEW</span></p>
        
        <div class="card">
            <label>🔑 OpenAI API Key</label>
            <input type="password" id="apiKey" placeholder="sk-...">
            <small style="color:#666">Get key: <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com</a></small>
        </div>
        
        <div class="card">
            <label>✨ Describe Your World</label>
            <textarea id="prompt" placeholder="A peaceful forest village with a friendly wizard and hidden treasures..."></textarea>
            <div style="color:#93a4c0; font-size:12px; margin-top:8px; line-height:1.5">
                You can be high-level or detailed in the prompt.<br>
                High-level example: <code>a snowy kingdom at night</code>.<br>
                Detailed example: <code>Level 1 Biome: snow</code>, <code>Level 2: lost_item</code>, <code>Time: night</code>, hero and NPC look/style notes.
            </div>
            <div class="examples">
                <button class="ex-btn" onclick="setBiomeHint('meadow')">🌿 Meadow</button>
                <button class="ex-btn" onclick="setBiomeHint('forest')">🌲 Forest</button>
                <button class="ex-btn" onclick="setBiomeHint('town')">🏘️ Town</button>
                <button class="ex-btn" onclick="setBiomeHint('beach')">🏖️ Beach</button>
                <button class="ex-btn" onclick="setBiomeHint('snow')">❄️ Snow</button>
                <button class="ex-btn" onclick="setBiomeHint('desert')">🏜️ Desert</button>
                <button class="ex-btn" onclick="setBiomeHint('ruins')">🏛️ Ruins</button>
                <button class="ex-btn" onclick="setBiomeHint('castle')">🏰 Castle</button>
            </div>
            <div class="examples" style="margin-top:8px">
                <button class="ex-btn" onclick="setTimeHint('day')">☀️ Day</button>
                <button class="ex-btn" onclick="setTimeHint('dawn')">🌅 Dawn</button>
                <button class="ex-btn" onclick="setTimeHint('sunset')">🌇 Sunset</button>
                <button class="ex-btn" onclick="setTimeHint('night')">🌙 Night</button>
            </div>
            <div class="levels">
                <label style="margin:0; color:#22d3ee;">Time of Day</label>
                <select id="timeSelect" style="width:220px; padding:10px; border-radius:8px; background:#0f0f23; color:white; border:2px solid #333">
                    <option value="">Auto (from prompt/random)</option>
                    <option value="day">Day</option>
                    <option value="dawn">Dawn</option>
                    <option value="sunset">Sunset</option>
                    <option value="night">Night</option>
                </select>
                <span style="color:#888; font-size:12px;">(optional, applies to Level 1 unless Level N Time is set)</span>
            </div>
            <div style="color:#93a4c0; font-size:12px; margin-top:4px; line-height:1.5">
                Auto means you are not forcing a value here. Auto lets the generator decide unless the prompt explicitly sets it.
            </div>
            <button class="rand-btn" onclick="randomPrompt()">🎲 Generate Random Prompt</button>
            <div class="levels">
                <label style="margin:0; color:#22d3ee;">Levels</label>
                <input type="number" id="levels" min="1" max="3" value="3" onchange="syncLevelUI()">
                <span style="color:#888; font-size:12px;">(1-3)</span>
            </div>
            <div style="color:#93a4c0; font-size:12px; margin-top:6px; line-height:1.5">
                If you leave settings unspecified (in prompt or UI), the generator will create them for you automatically.
            </div>
            <div class="levels">
                <label style="margin:0; color:#22d3ee;">Quality</label>
                <select id="quality" style="width:160px; padding:10px; border-radius:8px; background:#0f0f23; color:white; border:2px solid #333">
                    <option value="low">Low (cheapest)</option>
                    <option value="medium" selected>Medium</option>
                    <option value="high">High (best)</option>
                </select>
                <span style="color:#888; font-size:12px;">(affects cost)</span>
            </div>
            <div class="levels">
                <label style="margin:0; color:#22d3ee;">Terrain Style</label>
                <select id="terrainStyle" style="width:180px; padding:10px; border-radius:8px; background:#0f0f23; color:white; border:2px solid #333">
                    <option value="smooth" selected>Smooth</option>
                    <option value="classic">Classic</option>
                </select>
                <span style="color:#888; font-size:12px;">(visual only)</span>
            </div>
            <div class="levels" style="margin-top:10px; display:block">
                <label style="margin:0; color:#22d3ee;">Goals (per level, optional)</label>
                <div style="color:#888; font-size:12px; margin-top:6px">
                    Pick goal options under each level. If you select multiple goals for a level, they are stacked. If a level is blank in both UI and prompt, goals for that level are auto-generated.
                </div>
                <div style="color:#7f8da8; font-size:12px; margin-top:4px">
                    Each <b>Level N biome</b> dropdown controls that level only.
                </div>
                <div style="display:flex; gap:10px; margin-top:8px">
                    <button class="ex-btn" onclick="clearGoals()" style="background:#0b1220">Clear Goal Selections</button>
                    <button class="ex-btn" onclick="randomGoals()" style="background:#0b1220">🎲 Randomize Goals</button>
                </div>

                <div id="goalLevels" style="margin-top:10px; display:flex; gap:10px; flex-wrap:wrap">
                    <div class="card" style="padding:12px; margin:0; width: 100%">
                        <div style="font-weight:800; color:#cbd5e1; margin-bottom:8px">Level 1 goals</div>
                        <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px">
                            <span style="color:#94a3b8; font-size:12px; min-width:96px">Level 1 biome</span>
                            <select id="biomeL1" style="width:180px; padding:8px; border-radius:8px; background:#0f0f23; color:white; border:2px solid #333">
                                <option value="">Auto</option>
                                <option value="meadow">Meadow</option>
                                <option value="forest">Forest</option>
                                <option value="town">Town</option>
                                <option value="beach">Beach</option>
                                <option value="snow">Snow</option>
                                <option value="desert">Desert</option>
                                <option value="ruins">Ruins</option>
                                <option value="castle">Castle</option>
                            </select>
                        </div>
                        <div style="display:flex; gap:10px; flex-wrap:wrap">
                            <label for="goal-l1-cure" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l1-cure" type="checkbox" class="goalOptL1" value="cure"> Cure
                            </label>
                            <label for="goal-l1-key" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l1-key" type="checkbox" class="goalOptL1" value="key_and_door"> Key+Door
                            </label>
                            <label for="goal-l1-lost" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l1-lost" type="checkbox" class="goalOptL1" value="lost_item"> Lost Item
                            </label>
                            <label for="goal-l1-bridge" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l1-bridge" type="checkbox" class="goalOptL1" value="repair_bridge"> Repair Bridge
                            </label>
                        </div>
                    </div>

                    <div id="goalL2" class="card" style="padding:12px; margin:0; width: 100%">
                        <div style="font-weight:800; color:#cbd5e1; margin-bottom:8px">Level 2 goals</div>
                        <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px">
                            <span style="color:#94a3b8; font-size:12px; min-width:96px">Level 2 biome</span>
                            <select id="biomeL2" style="width:180px; padding:8px; border-radius:8px; background:#0f0f23; color:white; border:2px solid #333">
                                <option value="">Auto</option>
                                <option value="meadow">Meadow</option>
                                <option value="forest">Forest</option>
                                <option value="town">Town</option>
                                <option value="beach">Beach</option>
                                <option value="snow">Snow</option>
                                <option value="desert">Desert</option>
                                <option value="ruins">Ruins</option>
                                <option value="castle">Castle</option>
                            </select>
                        </div>
                        <div style="display:flex; gap:10px; flex-wrap:wrap">
                            <label for="goal-l2-cure" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l2-cure" type="checkbox" class="goalOptL2" value="cure"> Cure
                            </label>
                            <label for="goal-l2-key" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l2-key" type="checkbox" class="goalOptL2" value="key_and_door"> Key+Door
                            </label>
                            <label for="goal-l2-lost" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l2-lost" type="checkbox" class="goalOptL2" value="lost_item"> Lost Item
                            </label>
                            <label for="goal-l2-bridge" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l2-bridge" type="checkbox" class="goalOptL2" value="repair_bridge"> Repair Bridge
                            </label>
                        </div>
                    </div>

                    <div id="goalL3" class="card" style="padding:12px; margin:0; width: 100%">
                        <div style="font-weight:800; color:#cbd5e1; margin-bottom:8px">Level 3 goals</div>
                        <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px">
                            <span style="color:#94a3b8; font-size:12px; min-width:96px">Level 3 biome</span>
                            <select id="biomeL3" style="width:180px; padding:8px; border-radius:8px; background:#0f0f23; color:white; border:2px solid #333">
                                <option value="">Auto</option>
                                <option value="meadow">Meadow</option>
                                <option value="forest">Forest</option>
                                <option value="town">Town</option>
                                <option value="beach">Beach</option>
                                <option value="snow">Snow</option>
                                <option value="desert">Desert</option>
                                <option value="ruins">Ruins</option>
                                <option value="castle">Castle</option>
                            </select>
                        </div>
                        <div style="display:flex; gap:10px; flex-wrap:wrap">
                            <label for="goal-l3-cure" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l3-cure" type="checkbox" class="goalOptL3" value="cure"> Cure
                            </label>
                            <label for="goal-l3-key" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l3-key" type="checkbox" class="goalOptL3" value="key_and_door"> Key+Door
                            </label>
                            <label for="goal-l3-lost" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l3-lost" type="checkbox" class="goalOptL3" value="lost_item"> Lost Item
                            </label>
                            <label for="goal-l3-bridge" style="display:flex; align-items:center; gap:6px; color:#cbd5e1; font-size:13px">
                                <input id="goal-l3-bridge" type="checkbox" class="goalOptL3" value="repair_bridge"> Repair Bridge
                            </label>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <button id="btn" onclick="generate()">🌟 Generate World!</button>
        <div id="status" class="status" style="display:none;"></div>
        
        <div class="card features">
            <b>✨ How Generation Works:</b><br>
            • Your prompt sets the world theme (biome/time/vibe) and character style, and can also set exact per-level controls.<br>
            • You can assign biome per level in prompt (<code>Level 1 Biome: snow</code>) or in UI (<code>Level 1 biome</code>, <code>Level 2 biome</code>, <code>Level 3 biome</code> dropdowns).<br>
            • You can assign goals per level in prompt (<code>Level 2: repair_bridge</code>) or in UI checkboxes under each level.<br>
            • Prompt <code>Time:</code>, <code>Hero look:</code>, and <code>NPC look:</code> apply to Level 1 by default. Levels 2/3 randomize those unless you set <code>Level N Time:</code>.<br>
            • If prompt and UI both set the same level value, prompt wins for that level.<br>
            • If a level is unspecified in both prompt and UI, that level biome/goals are auto-generated.<br>
            • If you check multiple goals for one level, they are stacked and all must be completed.<br>
            • Random Prompt samples only valid supported biomes/times/layouts/goals.<br>
        </div>
    </div>
    
    <script>
        function setEx(t) { document.getElementById('prompt').value = t; }
        function setBiomeHint(biome) {
            const el = document.getElementById('prompt');
            const p = (el.value || '').trim();
            if (!p) {
                el.value = `Biome: ${biome}.`;
                return;
            }
            if (/\\bBiome\\s*:/i.test(p)) {
                el.value = p.replace(/\\bBiome\\s*:\\s*[^.\\n]+/i, `Biome: ${biome}`);
            } else {
                el.value = `${p} Biome: ${biome}.`;
            }
        }
        function setTimeHint(tod) {
            const el = document.getElementById('prompt');
            const p = (el.value || '').trim();
            if (!p) {
                el.value = `Time: ${tod}.`;
                return;
            }
            if (/\\bTime\\s*:/i.test(p)) {
                el.value = p.replace(/\\bTime\\s*:\\s*[^.\\n]+/i, `Time: ${tod}`);
            } else {
                el.value = `${p} Time: ${tod}.`;
            }
        }
        function randomPrompt() {
            // These arrays are intentionally aligned with the README's "fixed (finite sets)" so the
            // randomizer can hit all supported biomes / times / layout styles and trigger themed decor.
            const biomes = [
                "meadow", "forest", "town", "beach", "snow", "desert", "ruins", "castle"
            ];
            const times = ["day", "dawn", "sunset", "night"];
            const layouts = [
                "winding_road", "crossroads", "ring_road", "plaza", "market_street",
                "coastline", "riverbend", "islands", "oasis", "lake_center",
                "maze_grove", "ruin_ring"
            ];
            const decorTags = [
                "cacti", "shells", "snow piles", "crates", "statues", "vines", "mushrooms", "lanterns", "harbor", "bazaar"
            ];
            const places = [
                "a quiet town", "a lantern-lit harbor", "an ancient temple ruin", "a cliffside castle courtyard",
                "a snowy mountain hamlet", "a windy beach coast", "a misty forest grove", "a sunlit meadow"
            ];
            const heroes = [
                "a red‑scarf alchemist’s apprentice", "a green‑cloaked ranger",
                "a sailor‑adventurer with a brass compass", "a traveling bard with a lute",
                "a young mage with a star brooch"
            ];
            const npcs = [
                "a gentle healer", "a shrine keeper", "a friendly innkeeper",
                "a wise librarian", "a village guard captain"
            ];
            const hooks = [
                "gather three rare ingredients to brew a remedy",
                "recover a lost heirloom hidden nearby",
                "unlock an ancient gate with a hidden key",
                "repair a broken bridge with materials from the shop",
                "return a lost item to someone worried"
            ];
            const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
            const biome = pick(biomes);
            const tod = pick(times);
            const layout = pick(layouts);
            const tag = pick(decorTags);
            const place = pick(places);
            // Include explicit tokens so the hint extractor/layout parser can lock onto them.
            const prompt = `Setting: ${place}. Biome: ${biome}. Time: ${tod}. Layout: ${layout}. Theme: ${tag}. ` +
                `The hero is ${pick(heroes)}. The NPC is ${pick(npcs)}. The quest is to ${pick(hooks)}.`;
            document.getElementById('prompt').value = prompt;
            // Randomize per-level goal options too (covers all allowed goal types over time).
            randomGoals();
        }

        function clearGoals() {
            document.querySelectorAll('.goalOptL1, .goalOptL2, .goalOptL3').forEach(e => { e.checked = false; });
        }

        function biomesByLevel() {
            return [
                document.getElementById('biomeL1').value || '',
                document.getElementById('biomeL2').value || '',
                document.getElementById('biomeL3').value || '',
            ];
        }

        function randomGoals() {
            clearGoals();
            const all = ['cure','key_and_door','lost_item','repair_bridge'];
            const pickN = (n) => {
                const c = all.slice().sort(() => Math.random() - 0.5);
                return new Set(c.slice(0, n));
            };
            // For each level, pick 1-2 candidate goals (stacking options per level).
            const l1 = pickN(1 + Math.floor(Math.random() * 2));
            const l2 = pickN(1 + Math.floor(Math.random() * 2));
            const l3 = pickN(1 + Math.floor(Math.random() * 2));
            document.querySelectorAll('.goalOptL1').forEach(e => { e.checked = l1.has(e.value); });
            document.querySelectorAll('.goalOptL2').forEach(e => { e.checked = l2.has(e.value); });
            document.querySelectorAll('.goalOptL3').forEach(e => { e.checked = l3.has(e.value); });
        }

        function syncLevelUI() {
            const levels = parseInt(document.getElementById('levels').value || '3', 10);
            const show2 = levels >= 2;
            const show3 = levels >= 3;
            document.getElementById('goalL2').style.display = show2 ? 'block' : 'none';
            document.getElementById('goalL3').style.display = show3 ? 'block' : 'none';
        }

        function goalsByLevel() {
            const grab = (cls) => {
                const out = [];
                document.querySelectorAll(cls).forEach(e => { if (e.checked) out.push(e.value); });
                return out;
            };
            return [grab('.goalOptL1'), grab('.goalOptL2'), grab('.goalOptL3')];
        }
        async function generate() {
            const key = document.getElementById('apiKey').value;
            let prompt = document.getElementById('prompt').value;
            const tod = document.getElementById('timeSelect').value || '';
            const levels = parseInt(document.getElementById('levels').value || '3', 10);
            const goalByLevel = goalsByLevel();
            const biomeByLevel = biomesByLevel();
            const quality = document.getElementById('quality').value || 'medium';
            const terrainStyle = document.getElementById('terrainStyle').value || 'smooth';
            if (!key) return alert('Enter API key!');
            if (!prompt) return alert('Describe your world!');
            if (tod && !/\\bTime\\s*:/i.test(prompt)) {
                prompt = `${prompt.trim()} Time: ${tod}.`;
            }
            document.getElementById('btn').disabled = true;
            const status = document.getElementById('status');
            status.style.display = 'block';
            status.innerHTML = '<span class="spinner"></span> Generating world (20-30 sec)...';
            try {
                const res = await fetch('/generate', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        apiKey: key,
                        prompt: prompt,
                        levels: levels,
                        goalByLevel: goalByLevel,
                        biomeByLevel: biomeByLevel,
                        timeOfDay: tod,
                        quality: quality,
                        terrainStyle: terrainStyle
                    })
                });
                const data = await res.json();
                status.innerHTML = data.success ? '✅ Done! Go to terminal and press ENTER!' : '❌ ' + data.error;
            } catch (e) { status.innerHTML = '❌ ' + e.message; }
            document.getElementById('btn').disabled = false;
        }
        // Initialize visibility
        syncLevelUI();
    </script>
</body>
</html>
'''

pending_game = {"ready": False, "levels": []}

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/generate', methods=['POST'])
def generate():
    global pending_game
    try:
        data = request.json
        config.OPENAI_API_KEY = data['apiKey']

        # Per-run model/quality selection (from UI)
        q = str(data.get("quality") or "medium").lower().strip()
        if q not in ["low", "medium", "high"]:
            q = "medium"
        Config.IMAGE_QUALITY = q
        # Text model choice by quality tier
        # - low/medium: cheaper model
        # - high: higher quality, higher cost
        Config.TEXT_MODEL = "gpt-4o-mini" if q in ["low", "medium"] else "gpt-4o"
        # Item sprite generation budget by quality.
        # - low: no per-quest item sprites (uses a generic icon)
        # - medium: generate 1 item sprite per level
        # - high: generate 2 item sprites per level
        Config.ITEM_SPRITES_PER_LEVEL = 0 if q == "low" else (2 if q == "high" else 1)
        terrain_style = str(data.get("terrainStyle") or "smooth").lower().strip()
        Config.TERRAIN_STYLE = terrain_style if terrain_style in ["smooth", "classic"] else "smooth"
        
        client = OpenAIClient(config.OPENAI_API_KEY)
        
        print("\n" + "="*50)
        print("PROMPTQUEST - AI PIXEL ADVENTURE")
        print("="*50)
        
        print("\n[1/2] Designing worlds...")
        designer = GameDesigner(client)
        levels = []
        level_count = int(data.get("levels", 3))
        level_count = max(1, min(3, level_count))

        prompt = data.get("prompt", "")
        by_level_raw = data.get("goalByLevel") or []
        biome_by_level_raw = data.get("biomeByLevel") or []
        ui_time = normalize_time_of_day(data.get("timeOfDay") or "")
        quest_plans = build_quest_plans(prompt=prompt, by_level_raw=by_level_raw, level_count=level_count)
        biome_plans = build_biome_plans(prompt=prompt, by_level_raw=biome_by_level_raw, level_count=level_count)
        time_plans = build_time_plans(prompt=prompt, level_count=level_count, ui_time=ui_time)
        followup_prompt_base = strip_first_level_only_directives(prompt)

        base_player = None
        base_player_sprite = None
        reuse_shop_npc = None
        reuse_inn_npc = None
        reuse_guest_a = None
        reuse_guest_b = None
        reuse_building_shop = None
        reuse_building_inn = None

        for i in range(level_count):
            level_prompt = (
                data["prompt"]
                if i == 0
                else f"{followup_prompt_base} -- New area {i+1} with different terrain, new NPC, and new objectives."
            )
            # Force/seed level biome from prompt or UI plan, with random fallback already resolved.
            level_prompt = f"{level_prompt} Level {i+1} Biome: {biome_plans[i]}. Level {i+1} Time: {time_plans[i]}."
            game = designer.design_game(level_prompt, quest_plan_override=quest_plans[i])
            if base_player is None:
                base_player = game["player"]
            else:
                game["player"] = base_player
            print(f"Level {i+1} Title: {game.get('title')}")
            print(f"Time: {game.get('time_of_day', 'day')}")
            print(f"Terrain: {game.get('terrain', {}).get('type', 'meadow')}")
            
            print("\n[2/2] Generating sprites...")
            # Reuse some sprites across levels to reduce image calls.
            game["_reuse_sprites"] = {
                "npc_shop": reuse_shop_npc,
                "npc_inn": reuse_inn_npc,
                "npc_guest_a": reuse_guest_a,
                "npc_guest_b": reuse_guest_b,
                "building_shop": reuse_building_shop,
                "building_inn": reuse_building_inn,
            }
            sprites = SpriteGenerator(client, config.API_DELAY).generate_all(game, reuse_player_sprite=base_player_sprite)
            if base_player_sprite is None:
                base_player_sprite = sprites.get("player")
            if reuse_shop_npc is None:
                reuse_shop_npc = sprites.get("npc_shop")
            if reuse_inn_npc is None:
                reuse_inn_npc = sprites.get("npc_inn")
            if reuse_guest_a is None:
                reuse_guest_a = sprites.get("npc_guest_a")
            if reuse_guest_b is None:
                reuse_guest_b = sprites.get("npc_guest_b")
            if reuse_building_shop is None:
                reuse_building_shop = sprites.get("building_shop")
            if reuse_building_inn is None:
                reuse_building_inn = sprites.get("building_inn")
            levels.append({"game": game, "sprites": sprites})
        
        pending_game = {"ready": True, "levels": levels}
        
        return jsonify({"success": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


def main():
    import webbrowser
    import threading
    
    # Bake core sprites and exit (used to commit high-quality sprites into the repo).
    if "--bake-core" in sys.argv:
        # Optional: --quality high|medium|low
        q = "high"
        if "--quality" in sys.argv:
            try:
                q = sys.argv[sys.argv.index("--quality") + 1]
            except Exception:
                q = "high"
        q = str(q).lower().strip()
        if q not in ["low", "medium", "high"]:
            q = "high"
        Config.IMAGE_QUALITY = q
        # Use a higher quality text model for bake-time prompts (not many calls here anyway).
        Config.TEXT_MODEL = "gpt-4o"

        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY".lower())
        if not api_key:
            api_key = input("OPENAI_API_KEY (will not be saved): ").strip()
        if not api_key:
            raise SystemExit("Missing OPENAI_API_KEY.")

        client = OpenAIClient(api_key)
        os.makedirs(BAKED_SPRITES_DIR, exist_ok=True)
        manifest: dict[str, str] = {}

        core = [
            ("npc_shop", "npc", "shopkeeper in layered robes and apron, potion vials on belt, kind face, distinctive hat or hood"),
            ("npc_inn", "npc", "innkeeper in warm tavern clothes (vest, rolled sleeves), friendly smile, holding a towel or mug, cozy vibe"),
            ("npc_princess_sick", "npc", "sick princess in elegant dress with crown, pale skin, tired eyes, slumped posture, wrapped in a blanket, clearly unwell"),
            ("npc_princess_healed", "npc_healed", "healthy princess in elegant dress with crown, bright eyes, warm smile, confident posture, glowing healthy complexion"),
            ("chest", "chest", "treasure chest prop: wooden chest with metal bands and latch"),
            ("key", "key", "key item: ornate brass key with visible teeth and keyring hole"),
            ("door", "door", "door prop: heavy wooden door with iron bands and visible lock and handle"),
            ("mix_station", "cauldron", "alchemy prop: iron cauldron with glowing liquid, bubbles, small runes"),
            ("mat_planks", "item", "stack of sturdy wooden bridge planks, slightly weathered, strapped with twine"),
            ("mat_rope", "item", "thick coil of hemp rope with a knot, tan color, rugged fibers"),
            ("mat_nails", "item", "small pouch of iron nails with a few nails visible, dark metal sheen"),
            ("item_generic", "item", "simple collectible item icon: small pouch or trinket with clear silhouette"),
            ("bridge_broken", "item", "top-down broken wooden bridge segment over water, snapped planks, visible central gap, small debris"),
            ("bridge_fixed", "item", "top-down repaired wooden bridge segment over water, clean plank deck and rope rails"),
            ("npc_guest_a", "npc", "ONE full-body inn guest sprite, top-down RPG pixel style, unique outfit and silhouette, transparent background, no frame"),
            ("npc_guest_b", "npc", "ONE full-body inn guest sprite, top-down RPG pixel style, different hair/clothes from guest A, transparent background, no frame"),
            ("building_shop", "item", "pixel-art top-down RPG shop building exterior with red roof, centered door, windows"),
            ("building_inn", "item", "pixel-art top-down RPG inn building exterior, warm roof, large entrance, welcoming sign"),
            ("shop_counter", "item", "top-down pixel RPG shop counter, polished wood, books and potion bottles, transparent background"),
            ("shop_shelf", "item", "top-down pixel RPG wall shelf full of colorful bottles and goods, transparent background"),
            ("inn_desk", "item", "top-down pixel RPG inn reception desk with bell and ledger, transparent background"),
            ("inn_bed", "item", "top-down pixel RPG inn bedroom bed with blanket and pillow, transparent background"),
            ("inn_room_door", "item", "top-down pixel RPG wooden room door with number plaque and handle, transparent background"),
        ]

        print(f"Baking core sprites to {BAKED_SPRITES_DIR} (quality={Config.IMAGE_QUALITY})...")
        for key, role, desc in core:
            img = client.generate_image(desc, role=role, theme="fantasy pixel adventure")
            out_name = f"{key}.png"
            out_path = os.path.join(BAKED_SPRITES_DIR, out_name)
            img.save(out_path)
            manifest[key] = out_name
            print(f"  wrote {out_path}")

        with open(BAKED_MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
        print(f"Wrote {BAKED_MANIFEST_PATH}")
        print("Done. Commit and push assets/sprites/ to GitHub to share baked sprites.")
        return

    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║          🎮 PromptQuest: AI Pixel Adventure 🎮                ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║                                                               ║
    ║  WHAT THIS IS:                                                ║
    ║  • Prompt → generates setting, characters, items, and quests   ║
    ║  • You explore a top-down map and complete objectives          ║
    ║  • Multi-level run: each level gets a different goal type      ║
    ║                                                               ║
    ║  HOW TO PLAY:                                                 ║
    ║  1. Browser → paste API key → describe your world             ║
    ║  2. Wait 20-30 seconds                                        ║
    ║  3. Press ENTER here → play!                                  ║
    ║                                                               ║
    ║  GOAL: Complete the quest shown in the UI                     ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    def run_flask():
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        app.run(debug=False, port=5000, threaded=True, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    webbrowser.open('http://127.0.0.1:5000')
    
    print("\n⏳ Waiting for you to generate a world...")
    print("   (Press Ctrl+C to quit)\n")
    
    while True:
        try:
            if pending_game["ready"]:
                print("\n" + "="*50)
                print("🌟 WORLD READY! Press ENTER to explore...")
                print("="*50)
                input()
                
                levels = pending_game["levels"]
                pending_game["ready"] = False
                
                engine = GameEngine(levels, config)
                engine.run()
                
                print("\n✨ Thanks for playing!")
                print("⏳ Generate another world, or Ctrl+C to quit...\n")
            
            time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
