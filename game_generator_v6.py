"""
GENIE GAME GENERATOR v6 - 16-Bit Style!
========================================
Better pixel art prompts + restart button + cleaner look.

CHANGES FROM v5:
- Better 16-bit style pixel art (like classic SNES/Genesis games)
- 64x64 sprites (bigger, more detail)
- Restart button (R key)
- Dark themed background
- Cleaner map without tiled spam

COST: ~$0.35 per game (7 sprites)
"""

import os
import json
import base64
import time
import random
import math
from io import BytesIO
from flask import Flask, render_template_string, request, jsonify
import requests
import pygame
from PIL import Image


# ============================================================
# CONFIG
# ============================================================

class Config:
    OPENAI_API_KEY = ""
    
    TILE_SIZE = 48  # Bigger tiles
    SPRITE_SIZE = 64  # Generate at 64x64 for more detail
    GAME_WIDTH = 1000
    GAME_HEIGHT = 700
    MAP_WIDTH = 16
    MAP_HEIGHT = 12
    PLAYER_SPEED = 4
    API_DELAY = 0.5
    
    PLAYER_MAX_HEALTH = 100
    ATTACK_COOLDOWN = 25
    ATTACK_RANGE = 1.8


# ============================================================
# PARTICLE EFFECTS (FREE)
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
    def __init__(self):
        self.particles = []
        self.flash = 0
        self.flash_color = (255, 255, 255)
    
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
    
    def blood(self, x, y):
        for _ in range(15):
            self.particles.append(Particle(
                x + random.randint(-8, 8), y + random.randint(-8, 8),
                (random.randint(180, 255), 0, 0),
                random.uniform(-3, 3), random.uniform(-4, 1),
                random.randint(15, 35), random.randint(3, 6), 0.2
            ))
    
    def explosion(self, x, y):
        colors = [(255, 100, 0), (255, 200, 0), (255, 50, 0)]
        for _ in range(30):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2, 7)
            self.particles.append(Particle(
                x, y, random.choice(colors),
                math.cos(angle) * speed, math.sin(angle) * speed,
                random.randint(20, 45), random.randint(4, 8), 0.1
            ))
        self.flash = 10
        self.flash_color = (255, 150, 50)
    
    def sparkle(self, x, y):
        colors = [(255, 255, 100), (100, 200, 255), (255, 100, 255)]
        for _ in range(25):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1, 4)
            self.particles.append(Particle(
                x, y, random.choice(colors),
                math.cos(angle) * speed, math.sin(angle) * speed - 2,
                random.randint(30, 55), random.randint(3, 6), -0.05
            ))
        self.flash = 6
        self.flash_color = (200, 200, 255)
    
    def heal(self, x, y):
        for _ in range(18):
            self.particles.append(Particle(
                x + random.randint(-15, 15), y + random.randint(-15, 15),
                (50, 255, 50),
                random.uniform(-0.5, 0.5), random.uniform(-2.5, -0.5),
                random.randint(25, 45), random.randint(4, 7), -0.1
            ))
        self.flash = 5
        self.flash_color = (50, 255, 50)
    
    def pickup(self, x, y):
        for _ in range(12):
            angle = random.uniform(0, 2 * math.pi)
            self.particles.append(Particle(
                x, y, (255, 255, 0),
                math.cos(angle) * 3, math.sin(angle) * 3,
                18, 5, 0
            ))


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
    
    def generate_text(self, prompt: str) -> str:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=self.headers,
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a game designer. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2500,
                "temperature": 0.8
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def generate_image(self, prompt: str) -> Image.Image:
        """Generate 16-bit style pixel art"""
        # Much better prompt for 16-bit style
        styled_prompt = f"""16-bit pixel art sprite for a video game, SNES/Genesis era style.
Single character or object on transparent background.
Clean pixel art with defined outlines, limited color palette (16-24 colors).
No anti-aliasing, sharp pixels, retro game aesthetic.
Subject: {prompt}
Style reference: Final Fantasy 6, Chrono Trigger, Secret of Mana"""
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/images/generations",
                headers=self.headers,
                json={
                    "model": "dall-e-3",
                    "prompt": styled_prompt,
                    "n": 1,
                    "size": "1024x1024",
                    "quality": "standard",
                    "response_format": "b64_json"
                }
            )
            response.raise_for_status()
            image_data = response.json()["data"][0]["b64_json"]
            img = Image.open(BytesIO(base64.b64decode(image_data)))
            # Resize to 64x64 with NEAREST for crisp pixels
            return img.resize((64, 64), Image.NEAREST)
        except Exception as e:
            print(f"Image error: {e}")
            return self._placeholder(prompt)
    
    def _placeholder(self, prompt: str) -> Image.Image:
        """Fallback pixel art placeholder"""
        colors = {
            "player": (100, 149, 237), "hero": (100, 149, 237), "knight": (192, 192, 192),
            "enemy": (178, 34, 34), "monster": (139, 69, 19), "skeleton": (245, 245, 220),
            "vampire": (75, 0, 130), "ghost": (200, 200, 255), "goblin": (50, 150, 50),
            "npc": (218, 165, 32), "wizard": (138, 43, 226), "princess": (255, 182, 193),
            "tree": (34, 100, 34), "rock": (105, 105, 105), "grass": (60, 120, 60),
            "chest": (139, 90, 43), "key": (255, 215, 0), "potion": (255, 0, 100),
            "sword": (192, 192, 192), "lantern": (255, 200, 50), "lamp": (255, 200, 50),
        }
        color = (128, 0, 128)
        for key, col in colors.items():
            if key in prompt.lower():
                color = col
                break
        
        # Create a simple but nicer placeholder
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        pixels = img.load()
        
        # Draw a simple character shape
        cx, cy = 32, 32
        for y in range(64):
            for x in range(64):
                dist = ((x - cx)**2 + (y - cy)**2) ** 0.5
                if dist < 24:
                    # Add some shading
                    shade = 1.0 - (dist / 40)
                    r = min(255, int(color[0] * shade))
                    g = min(255, int(color[1] * shade))
                    b = min(255, int(color[2] * shade))
                    pixels[x, y] = (r, g, b, 255)
                    # Outline
                    if 22 < dist < 26:
                        pixels[x, y] = (30, 30, 30, 255)
        return img


# ============================================================
# GAME DESIGNER
# ============================================================

class GameDesigner:
    def __init__(self, client: OpenAIClient):
        self.client = client
    
    def design_game(self, user_prompt: str) -> dict:
        num_enemies = random.randint(2, 4)
        
        design_prompt = f'''Create a 16-bit style adventure game based on: "{user_prompt}"

Return ONLY JSON:

{{
    "title": "Epic Game Title",
    "story": "One dramatic sentence",
    "time_of_day": "night/day/dawn/dusk/sunset",
    "background_color": [R, G, B],
    
    "player": {{
        "name": "Hero Name",
        "sprite_desc": "medieval knight with glowing lantern and sword, heroic pose",
        "start_x": 2, "start_y": 9,
        "attack_power": 20
    }},
    
    "enemy_type": {{
        "name": "Enemy Name",
        "sprite_desc": "menacing creature with glowing eyes, attack stance",
        "health": 35,
        "damage": 12
    }},
    
    "enemy_positions": [
        {{"x": 10, "y": 4}},
        {{"x": 7, "y": 6}},
        {{"x": 12, "y": 8}}
    ],
    
    "npc": {{
        "name": "Helpful Character",
        "sprite_desc": "wise old wizard with staff and robes, friendly",
        "x": 4, "y": 5,
        "dialogue_hint": "Seek the ancient key to unlock your destiny...",
        "dialogue_win": "You have proven yourself a true hero!"
    }},
    
    "quest_item": {{
        "name": "Quest Item",
        "sprite_desc": "glowing magical key or artifact, mystical aura",
        "x": 11, "y": 3
    }},
    
    "chest": {{
        "name": "Treasure Chest",
        "sprite_desc": "ornate wooden treasure chest with gold trim",
        "x": 14, "y": 5
    }},
    
    "objectives": [
        {{"id": 1, "task": "Defeat {num_enemies} enemies", "type": "kill", "target": {num_enemies}}},
        {{"id": 2, "task": "Find the key", "type": "find", "target": "quest_item"}},
        {{"id": 3, "task": "Open the chest", "type": "use", "target": "chest"}}
    ]
}}

IMPORTANT:
- sprite_desc should describe the character/item in detail for pixel art
- Include pose, mood, distinguishing features
- time_of_day: pick based on the prompt mood (night for spooky, day for adventure, dawn/dusk for mystery)
- background_color: match the time_of_day:
  - night: dark blues/purples [20-40, 20-40, 40-70]
  - day: bright greens/blues [100-150, 180-220, 100-150]
  - dawn: pink/orange tints [80-120, 60-90, 80-110]
  - dusk: orange/purple [70-100, 50-80, 80-120]
  - sunset: warm oranges [120-160, 80-110, 60-90]
- Map is 16x12 tiles'''

        print("Generating game design...")
        response = self.client.generate_text(design_prompt)
        
        response = response.strip()
        if "```" in response:
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        
        try:
            game = json.loads(response.strip())
            # Ensure we have the right number of enemies
            while len(game.get("enemy_positions", [])) < num_enemies:
                game["enemy_positions"].append({"x": random.randint(6, 13), "y": random.randint(3, 9)})
            return game
        except:
            return self._fallback(user_prompt, num_enemies)
    
    def _fallback(self, prompt: str, num_enemies: int) -> dict:
        # Detect time from prompt
        prompt_lower = prompt.lower()
        if any(w in prompt_lower for w in ["night", "dark", "midnight", "moon", "haunted", "spooky", "vampire", "ghost"]):
            time_of_day = "night"
            bg_color = [25, 25, 45]
        elif any(w in prompt_lower for w in ["dawn", "morning", "fog", "mist", "early"]):
            time_of_day = "dawn"
            bg_color = [90, 70, 90]
        elif any(w in prompt_lower for w in ["dusk", "evening", "twilight"]):
            time_of_day = "dusk"
            bg_color = [80, 60, 100]
        elif any(w in prompt_lower for w in ["sunset", "golden", "orange"]):
            time_of_day = "sunset"
            bg_color = [140, 90, 70]
        else:
            time_of_day = "day"
            bg_color = [120, 180, 120]
        
        return {
            "title": f"Quest of {prompt[:15]}",
            "story": "An adventure awaits...",
            "time_of_day": time_of_day,
            "background_color": bg_color,
            "player": {"name": "Knight", "sprite_desc": "armored knight with sword and shield, battle ready", "start_x": 2, "start_y": 9, "attack_power": 20},
            "enemy_type": {"name": "Shadow Beast", "sprite_desc": "dark creature with red eyes, menacing claws", "health": 35, "damage": 12},
            "enemy_positions": [{"x": 10, "y": 4}, {"x": 7, "y": 7}, {"x": 13, "y": 6}][:num_enemies],
            "npc": {"name": "Sage", "sprite_desc": "elderly wizard with long beard and magic staff", "x": 4, "y": 5, "dialogue_hint": "Find the key...", "dialogue_win": "Victory!"},
            "quest_item": {"name": "Ancient Key", "sprite_desc": "ornate golden key with magical glow", "x": 11, "y": 3},
            "chest": {"name": "Treasure Chest", "sprite_desc": "wooden chest with iron bands", "x": 14, "y": 5},
            "objectives": [
                {"id": 1, "task": f"Defeat {num_enemies} enemies", "type": "kill", "target": num_enemies},
                {"id": 2, "task": "Find the key", "type": "find", "target": "quest_item"},
                {"id": 3, "task": "Open the chest", "type": "use", "target": "chest"}
            ]
        }


# ============================================================
# SPRITE GENERATOR
# ============================================================

class SpriteGenerator:
    def __init__(self, client: OpenAIClient, delay: float = 0.5):
        self.client = client
        self.delay = delay
    
    def generate_all(self, game: dict) -> dict:
        sprites = {}
        time_of_day = game.get("time_of_day", "night")
        
        # Ground tile description based on time
        ground_descs = {
            "night": "dark stone floor tile, moonlit dungeon, blue-gray cobblestone",
            "day": "bright grass and dirt path, sunny meadow, green field tile",
            "dawn": "misty stone path, early morning fog, pink-tinted cobblestone",
            "dusk": "shadowy grass tile, purple evening light, twilight ground",
            "sunset": "warm golden grass, orange sunlit path, evening meadow"
        }
        ground_desc = ground_descs.get(time_of_day, ground_descs["night"])
        
        # Obstacle description based on time
        obstacle_descs = {
            "night": "stone pillar or broken wall, dark dungeon obstacle",
            "day": "oak tree or wooden fence, sunny forest obstacle",
            "dawn": "misty boulder or dead tree, foggy morning obstacle",
            "dusk": "shadowy ruins or twisted tree, twilight obstacle",
            "sunset": "golden hay bale or wooden cart, sunset farm obstacle"
        }
        obstacle_desc = obstacle_descs.get(time_of_day, obstacle_descs["night"])
        
        # 1. Player - most important
        print("  [1/7] Player...")
        sprites["player"] = self.client.generate_image(game["player"]["sprite_desc"])
        time.sleep(self.delay)
        
        # 2. Enemy
        print("  [2/7] Enemy...")
        sprites["enemy"] = self.client.generate_image(game["enemy_type"]["sprite_desc"])
        time.sleep(self.delay)
        
        # 3. NPC
        print("  [3/7] NPC...")
        sprites["npc"] = self.client.generate_image(game["npc"]["sprite_desc"])
        time.sleep(self.delay)
        
        # 4. Quest item
        print("  [4/7] Item...")
        sprites["quest_item"] = self.client.generate_image(game["quest_item"]["sprite_desc"])
        time.sleep(self.delay)
        
        # 5. Chest
        print("  [5/7] Chest...")
        sprites["chest"] = self.client.generate_image(game["chest"]["sprite_desc"])
        time.sleep(self.delay)
        
        # 6. Ground tile (time-based)
        print(f"  [6/7] Ground ({time_of_day})...")
        sprites["ground"] = self.client.generate_image(ground_desc)
        time.sleep(self.delay)
        
        # 7. Obstacle (time-based)
        print(f"  [7/7] Obstacle ({time_of_day})...")
        sprites["obstacle"] = self.client.generate_image(obstacle_desc)
        
        # Code-generated extras (FREE)
        print("  [FREE] Potion...")
        sprites["potion"] = self._make_potion()
        
        print(f"\n  Total API calls: 7 (~$0.28)")
        return sprites
    
    def _make_potion(self) -> Image.Image:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        pixels = img.load()
        # Simple potion bottle
        for y in range(16, 52):
            for x in range(20, 44):
                # Bottle shape
                if 24 <= x <= 40 and 20 <= y <= 48:
                    dist_from_center = abs(x - 32)
                    if dist_from_center < 10 - (y - 34) * 0.1:
                        shade = 200 + random.randint(-20, 20)
                        pixels[x, y] = (shade, 30, 80, 255)
                # Neck
                if 28 <= x <= 36 and 16 <= y <= 22:
                    pixels[x, y] = (180, 25, 70, 255)
        # Outline
        for y in range(64):
            for x in range(64):
                if pixels[x, y][3] > 0:
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < 64 and 0 <= ny < 64 and pixels[nx, ny][3] == 0:
                            pixels[nx, ny] = (20, 20, 20, 255)
        return img


# ============================================================
# GAME ENGINE
# ============================================================

class GameEngine:
    def __init__(self, game: dict, sprites: dict, config: Config):
        self.game = game
        self.config = config
        self.running = True
        
        pygame.init()
        self.screen = pygame.display.set_mode((config.GAME_WIDTH, config.GAME_HEIGHT))
        pygame.display.set_caption(game.get("title", "Adventure"))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.font_large = pygame.font.Font(None, 32)
        self.font_title = pygame.font.Font(None, 40)
        
        self.effects = EffectsManager()
        
        # Convert sprites to pygame surfaces
        self.surfaces = {}
        ts = config.TILE_SIZE
        for name, img in sprites.items():
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            surface = pygame.image.fromstring(img.tobytes(), img.size, "RGBA")
            self.surfaces[name] = pygame.transform.scale(surface, (ts, ts))
        
        # Background color from game design
        self.bg_color = tuple(game.get("background_color", [30, 30, 50]))
        
        self.reset_game()
    
    def reset_game(self):
        """Reset game state for restart"""
        ts = self.config.TILE_SIZE
        
        self.player_x = self.game["player"]["start_x"] * ts
        self.player_y = self.game["player"]["start_y"] * ts
        self.player_health = self.config.PLAYER_MAX_HEALTH
        self.player_attack = self.game["player"].get("attack_power", 20)
        self.attack_cooldown = 0
        
        self.inventory = []
        self.completed = set()
        self.enemies_killed = 0
        self.chest_opened = False
        self.message = self.game.get("story", "")
        self.message_timer = 300
        self.game_over = False
        self.game_won = False
        
        # Enemies
        self.enemies = []
        for i, pos in enumerate(self.game.get("enemy_positions", [])):
            self.enemies.append({
                "id": i,
                "px": pos["x"] * ts,
                "py": pos["y"] * ts,
                "health": self.game["enemy_type"]["health"],
                "max_health": self.game["enemy_type"]["health"],
                "damage": self.game["enemy_type"]["damage"],
                "dir": random.choice([-1, 1]),
                "timer": 0
            })
        
        # Potions
        self.potions = [
            {"x": random.randint(3, 12), "y": random.randint(3, 9), "collected": False},
            {"x": random.randint(3, 12), "y": random.randint(3, 9), "collected": False},
        ]
        
        # Obstacles (random pillars/walls)
        self.obstacles = []
        for _ in range(6):
            ox, oy = random.randint(4, 13), random.randint(2, 9)
            # Don't place on important spots
            if not self._is_important_spot(ox, oy):
                self.obstacles.append({"x": ox, "y": oy})
        
        self.build_collisions()
    
    def _is_important_spot(self, x, y):
        """Check if this spot has something important"""
        px, py = self.game["player"]["start_x"], self.game["player"]["start_y"]
        if abs(x - px) <= 1 and abs(y - py) <= 1:
            return True
        if x == self.game["quest_item"]["x"] and y == self.game["quest_item"]["y"]:
            return True
        if x == self.game["chest"]["x"] and y == self.game["chest"]["y"]:
            return True
        if x == self.game["npc"]["x"] and y == self.game["npc"]["y"]:
            return True
        return False
    
    def build_collisions(self):
        self.solid = set()
        for obs in self.obstacles:
            self.solid.add((obs["x"], obs["y"]))
        if not self.chest_opened:
            self.solid.add((self.game["chest"]["x"], self.game["chest"]["y"]))
    
    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_r:
                        # RESTART
                        self.reset_game()
                        self.msg("Game restarted!")
                    elif event.key == pygame.K_SPACE:
                        self.talk()
                    elif event.key == pygame.K_e:
                        self.use()
                    elif event.key == pygame.K_f:
                        self.attack()
            
            if not self.game_over and not self.game_won:
                keys = pygame.key.get_pressed()
                dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
                dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
                self.move(dx * self.config.PLAYER_SPEED, dy * self.config.PLAYER_SPEED)
                
                self.update_enemies()
                self.check_pickups()
                self.check_damage()
                
                if self.attack_cooldown > 0:
                    self.attack_cooldown -= 1
                
                if self.player_health <= 0:
                    self.game_over = True
                    self.msg("YOU DIED! Press R to restart")
                
                if len(self.completed) >= len(self.game["objectives"]):
                    self.game_won = True
                    self.msg("VICTORY! Press R to play again")
            
            self.effects.update()
            if self.message_timer > 0:
                self.message_timer -= 1
            
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()
    
    def move(self, dx, dy):
        ts = self.config.TILE_SIZE
        mw = self.config.MAP_WIDTH * ts
        mh = self.config.MAP_HEIGHT * ts
        
        new_x = self.player_x + dx
        if 0 <= new_x < mw - ts:
            if (int(new_x // ts), int(self.player_y // ts)) not in self.solid:
                self.player_x = new_x
        
        new_y = self.player_y + dy
        if 0 <= new_y < mh - ts:
            if (int(self.player_x // ts), int(new_y // ts)) not in self.solid:
                self.player_y = new_y
    
    def update_enemies(self):
        ts = self.config.TILE_SIZE
        for e in self.enemies:
            if e["health"] <= 0:
                continue
            dist = ((self.player_x - e["px"])**2 + (self.player_y - e["py"])**2) ** 0.5
            if dist < ts * 6:
                # Chase player
                speed = 1.5
                if self.player_x > e["px"]:
                    e["px"] += speed
                elif self.player_x < e["px"]:
                    e["px"] -= speed
                if self.player_y > e["py"]:
                    e["py"] += speed
                elif self.player_y < e["py"]:
                    e["py"] -= speed
            else:
                # Patrol
                e["timer"] += 1
                if e["timer"] > 60:
                    e["dir"] = random.choice([-1, 1])
                    e["timer"] = 0
                e["px"] += e["dir"] * 0.5
                e["px"] = max(ts, min(e["px"], (self.config.MAP_WIDTH - 2) * ts))
    
    def check_damage(self):
        ts = self.config.TILE_SIZE
        for e in self.enemies:
            if e["health"] <= 0:
                continue
            dist = ((self.player_x - e["px"])**2 + (self.player_y - e["py"])**2) ** 0.5
            if dist < ts * 0.6:
                dmg = max(1, e["damage"] // 20)
                self.player_health -= dmg
                if random.random() < 0.2:
                    self.effects.blood(self.player_x + ts//2, self.player_y + ts//2)
    
    def attack(self):
        if self.attack_cooldown > 0:
            return
        
        ts = self.config.TILE_SIZE
        hit = False
        
        for e in self.enemies:
            if e["health"] <= 0:
                continue
            dist = ((self.player_x - e["px"])**2 + (self.player_y - e["py"])**2) ** 0.5
            if dist < self.config.ATTACK_RANGE * ts:
                e["health"] -= self.player_attack
                hit = True
                self.effects.blood(e["px"] + ts//2, e["py"] + ts//2)
                
                if e["health"] <= 0:
                    self.enemies_killed += 1
                    self.effects.explosion(e["px"] + ts//2, e["py"] + ts//2)
                    self.msg(f"Defeated {self.game['enemy_type']['name']}!")
                    self.check_objective("kill", self.enemies_killed)
                else:
                    self.msg(f"Hit! (-{self.player_attack} HP)")
                
                self.attack_cooldown = self.config.ATTACK_COOLDOWN
                return
        
        if not hit:
            self.msg("*swing*")
            self.attack_cooldown = 12
    
    def check_pickups(self):
        ts = self.config.TILE_SIZE
        px, py = int(self.player_x // ts), int(self.player_y // ts)
        
        for p in self.potions:
            if p["collected"]:
                continue
            if p["x"] == px and p["y"] == py:
                p["collected"] = True
                heal = 30
                self.player_health = min(self.config.PLAYER_MAX_HEALTH, self.player_health + heal)
                self.effects.heal(self.player_x + ts//2, self.player_y + ts//2)
                self.msg(f"+{heal} HP!")
        
        item = self.game["quest_item"]
        if "quest_item" not in self.inventory:
            if item["x"] == px and item["y"] == py:
                self.inventory.append("quest_item")
                self.effects.pickup(self.player_x + ts//2, self.player_y + ts//2)
                self.msg(f"Got {item['name']}!")
                self.check_objective("find", "quest_item")
    
    def talk(self):
        ts = self.config.TILE_SIZE
        px, py = int(self.player_x // ts), int(self.player_y // ts)
        npc = self.game["npc"]
        
        if abs(npc["x"] - px) <= 1 and abs(npc["y"] - py) <= 1:
            if self.game_won:
                self.msg(f'{npc["name"]}: "{npc["dialogue_win"]}"')
            else:
                self.msg(f'{npc["name"]}: "{npc["dialogue_hint"]}"')
        else:
            self.msg("No one nearby.")
    
    def use(self):
        ts = self.config.TILE_SIZE
        px, py = int(self.player_x // ts), int(self.player_y // ts)
        chest = self.game["chest"]
        
        if abs(chest["x"] - px) <= 1 and abs(chest["y"] - py) <= 1:
            if "quest_item" in self.inventory and not self.chest_opened:
                self.chest_opened = True
                self.effects.sparkle(chest["x"] * ts + ts//2, chest["y"] * ts + ts//2)
                self.msg(f"Opened {chest['name']}! ✨")
                self.check_objective("use", "chest")
                self.build_collisions()
            elif self.chest_opened:
                self.msg("Already opened!")
            else:
                self.msg(f"Need {self.game['quest_item']['name']}!")
        else:
            self.msg("Nothing here.")
    
    def check_objective(self, obj_type, target):
        for obj in self.game["objectives"]:
            if obj["id"] in self.completed:
                continue
            if obj["type"] == obj_type:
                if obj_type == "kill" and self.enemies_killed >= obj["target"]:
                    self.completed.add(obj["id"])
                    self.msg("✓ " + obj["task"])
                elif obj_type in ["find", "use"] and target == obj["target"]:
                    self.completed.add(obj["id"])
                    self.msg("✓ " + obj["task"])
    
    def msg(self, text):
        self.message = text
        self.message_timer = 200
    
    def draw(self):
        ts = self.config.TILE_SIZE
        map_w = self.config.MAP_WIDTH * ts
        map_h = self.config.MAP_HEIGHT * ts
        
        # Dark background
        self.screen.fill(self.bg_color)
        
        # Ground tiles (only in play area)
        ground = self.surfaces.get("ground")
        for x in range(self.config.MAP_WIDTH):
            for y in range(self.config.MAP_HEIGHT):
                if ground:
                    self.screen.blit(ground, (x * ts, y * ts))
                else:
                    pygame.draw.rect(self.screen, (40, 40, 55), (x * ts, y * ts, ts, ts))
                    pygame.draw.rect(self.screen, (30, 30, 45), (x * ts, y * ts, ts, ts), 1)
        
        # Obstacles
        obs_surf = self.surfaces.get("obstacle")
        for obs in self.obstacles:
            if obs_surf:
                self.screen.blit(obs_surf, (obs["x"] * ts, obs["y"] * ts))
            else:
                pygame.draw.rect(self.screen, (60, 60, 70), (obs["x"] * ts, obs["y"] * ts, ts, ts))
        
        # Chest
        if not self.chest_opened:
            chest = self.game["chest"]
            surf = self.surfaces.get("chest")
            if surf:
                self.screen.blit(surf, (chest["x"] * ts, chest["y"] * ts))
        
        # Potions
        for p in self.potions:
            if not p["collected"]:
                surf = self.surfaces.get("potion")
                if surf:
                    self.screen.blit(surf, (p["x"] * ts, p["y"] * ts))
        
        # Quest item
        if "quest_item" not in self.inventory:
            item = self.game["quest_item"]
            surf = self.surfaces.get("quest_item")
            if surf:
                self.screen.blit(surf, (item["x"] * ts, item["y"] * ts))
        
        # Enemies
        for e in self.enemies:
            if e["health"] <= 0:
                continue
            surf = self.surfaces.get("enemy")
            if surf:
                self.screen.blit(surf, (e["px"], e["py"]))
            # Health bar
            bar_w = ts - 8
            pct = e["health"] / e["max_health"]
            pygame.draw.rect(self.screen, (60, 0, 0), (e["px"] + 4, e["py"] - 8, bar_w, 6))
            pygame.draw.rect(self.screen, (0, 200, 0), (e["px"] + 4, e["py"] - 8, int(bar_w * pct), 6))
        
        # NPC
        npc = self.game["npc"]
        surf = self.surfaces.get("npc")
        if surf:
            self.screen.blit(surf, (npc["x"] * ts, npc["y"] * ts))
        
        # Player
        surf = self.surfaces.get("player")
        if surf:
            self.screen.blit(surf, (self.player_x, self.player_y))
        
        # Effects
        self.effects.draw(self.screen)
        
        # UI Panel
        self.draw_ui(map_w)
        
        # Message box
        if self.message_timer > 0 and self.message:
            box_h = 50
            box_y = map_h - box_h - 15
            box_w = map_w - 30
            s = pygame.Surface((box_w, box_h))
            s.fill((15, 15, 25))
            s.set_alpha(230)
            self.screen.blit(s, (15, box_y))
            pygame.draw.rect(self.screen, (100, 100, 150), (15, box_y, box_w, box_h), 2)
            text = self.font.render(self.message[:70], True, (255, 255, 255))
            self.screen.blit(text, (25, box_y + 15))
        
        pygame.display.flip()
    
    def draw_ui(self, panel_x):
        panel_w = self.config.GAME_WIDTH - panel_x
        
        # Panel background
        pygame.draw.rect(self.screen, (20, 20, 30), (panel_x, 0, panel_w, self.config.GAME_HEIGHT))
        pygame.draw.line(self.screen, (60, 60, 80), (panel_x, 0), (panel_x, self.config.GAME_HEIGHT), 2)
        
        x = panel_x + 15
        y = 15
        
        # Title
        title = self.font_title.render(self.game.get("title", "Game")[:14], True, (255, 215, 0))
        self.screen.blit(title, (x, y))
        y += 45
        
        # Health
        self.screen.blit(self.font.render("HEALTH", True, (255, 100, 100)), (x, y))
        y += 22
        bar_w = panel_w - 30
        pct = max(0, self.player_health / self.config.PLAYER_MAX_HEALTH)
        pygame.draw.rect(self.screen, (60, 0, 0), (x, y, bar_w, 18))
        pygame.draw.rect(self.screen, (200, 50, 50), (x, y, int(bar_w * pct), 18))
        pygame.draw.rect(self.screen, (100, 100, 100), (x, y, bar_w, 18), 1)
        hp = self.font.render(f"{max(0, self.player_health)}/{self.config.PLAYER_MAX_HEALTH}", True, (255, 255, 255))
        self.screen.blit(hp, (x + 5, y + 1))
        y += 35
        
        # Enemies
        alive = len([e for e in self.enemies if e["health"] > 0])
        self.screen.blit(self.font.render(f"Enemies: {alive}", True, (255, 150, 150)), (x, y))
        y += 35
        
        # Objectives
        self.screen.blit(self.font_large.render("OBJECTIVES", True, (150, 150, 255)), (x, y))
        y += 28
        for obj in self.game["objectives"]:
            done = obj["id"] in self.completed
            color = (100, 255, 100) if done else (180, 180, 180)
            prefix = "✓" if done else "○"
            text = self.font.render(f"{prefix} {obj['task'][:18]}", True, color)
            self.screen.blit(text, (x, y))
            y += 22
        
        y += 15
        
        # Inventory
        self.screen.blit(self.font_large.render("INVENTORY", True, (255, 200, 100)), (x, y))
        y += 28
        if self.inventory:
            for item_id in self.inventory:
                name = self.game["quest_item"]["name"] if item_id == "quest_item" else item_id
                self.screen.blit(self.font.render(f"• {name[:15]}", True, (200, 200, 200)), (x, y))
                y += 20
        else:
            self.screen.blit(self.font.render("(empty)", True, (100, 100, 100)), (x, y))
        
        # Controls at bottom
        y = self.config.GAME_HEIGHT - 160
        self.screen.blit(self.font_large.render("CONTROLS", True, (100, 180, 255)), (x, y))
        y += 25
        controls = ["WASD - Move", "F - Attack", "SPACE - Talk", "E - Use item", "R - Restart", "ESC - Quit"]
        for ctrl in controls:
            self.screen.blit(self.font.render(ctrl, True, (120, 120, 140)), (x, y))
            y += 18


# ============================================================
# WEB INTERFACE
# ============================================================

app = Flask(__name__)
config = Config()

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>🎮 Game Generator v6</title>
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
            background: linear-gradient(90deg, #e94560, #ff6b6b);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .subtitle { text-align: center; color: #888; margin-bottom: 25px; }
        .card {
            background: rgba(255,255,255,0.06); border-radius: 12px;
            padding: 20px; margin-bottom: 15px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        label { display: block; margin-bottom: 8px; color: #e94560; font-weight: bold; }
        input, textarea {
            width: 100%; padding: 12px; border: 2px solid #333;
            border-radius: 8px; background: #0f0f23; color: white; font-size: 15px;
        }
        input:focus, textarea:focus { border-color: #e94560; outline: none; }
        textarea { height: 80px; margin-top: 5px; resize: none; }
        button {
            width: 100%; padding: 14px; font-size: 18px; font-weight: bold;
            border: none; border-radius: 8px; cursor: pointer;
            background: linear-gradient(90deg, #e94560, #ff6b6b); color: white;
            transition: transform 0.1s;
        }
        button:hover { transform: scale(1.02); }
        button:disabled { background: #444; transform: none; }
        .status { text-align: center; padding: 15px; font-size: 16px; }
        .examples { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
        .ex-btn {
            padding: 8px 12px; font-size: 13px; width: auto;
            background: rgba(233, 69, 96, 0.15); border: 1px solid #e94560; color: #e94560;
        }
        .tag { background: #e94560; padding: 3px 10px; border-radius: 4px; font-size: 12px; }
        .features { font-size: 14px; color: #aaa; line-height: 1.8; }
        .features b { color: #ff6b6b; }
        a { color: #6bcfff; }
        .spinner {
            display: inline-block; width: 18px; height: 18px;
            border: 3px solid #fff; border-top-color: transparent;
            border-radius: 50%; animation: spin 1s linear infinite; margin-right: 10px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .new { color: #4ade80; font-size: 12px; margin-left: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 Game Generator v6</h1>
        <p class="subtitle">16-Bit Style Pixel Art <span class="tag">NEW</span></p>
        
        <div class="card">
            <label>🔑 OpenAI API Key</label>
            <input type="password" id="apiKey" placeholder="sk-...">
            <small style="color:#666">Get key: <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com</a></small>
        </div>
        
        <div class="card">
            <label>✨ Describe Your Adventure</label>
            <textarea id="prompt" placeholder="A dark castle at midnight with skeleton knights guarding ancient treasure..."></textarea>
            <div class="examples">
                <button class="ex-btn" onclick="setEx('A haunted graveyard with ghost knights and cursed treasure')">👻 Haunted</button>
                <button class="ex-btn" onclick="setEx('A dragon lair with kobold minions and stolen gold')">🐉 Dragon</button>
                <button class="ex-btn" onclick="setEx('A vampire castle with bat swarms and holy artifacts')">🧛 Vampire</button>
                <button class="ex-btn" onclick="setEx('A wizard tower with animated armor and magic scrolls')">🧙 Wizard</button>
            </div>
        </div>
        
        <button id="btn" onclick="generate()">⚔️ Generate Adventure!</button>
        <div id="status" class="status" style="display:none;"></div>
        
        <div class="card features">
            <b>✨ v6 Improvements:</b><br>
            • Better 16-bit pixel art style (SNES/Genesis era)<span class="new">NEW</span><br>
            • Larger sprites with more detail<span class="new">NEW</span><br>
            • Press R to restart<span class="new">NEW</span><br>
            • Dark dungeon atmosphere<br>
            • Particle effects (blood, sparkles, explosions)<br><br>
            <b>💰 Cost:</b> ~$0.30 per game (7 sprites)
        </div>
    </div>
    
    <script>
        function setEx(t) { document.getElementById('prompt').value = t; }
        async function generate() {
            const key = document.getElementById('apiKey').value;
            const prompt = document.getElementById('prompt').value;
            if (!key) return alert('Enter API key!');
            if (!prompt) return alert('Describe your game!');
            document.getElementById('btn').disabled = true;
            const status = document.getElementById('status');
            status.style.display = 'block';
            status.innerHTML = '<span class="spinner"></span> Generating 16-bit sprites (30-45 sec)...';
            try {
                const res = await fetch('/generate', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({apiKey: key, prompt: prompt})
                });
                const data = await res.json();
                status.innerHTML = data.success ? '✅ Done! Go to terminal and press ENTER to play!' : '❌ ' + data.error;
            } catch (e) { status.innerHTML = '❌ ' + e.message; }
            document.getElementById('btn').disabled = false;
        }
    </script>
</body>
</html>
'''

pending_game = {"ready": False, "game": None, "sprites": None}

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/generate', methods=['POST'])
def generate():
    global pending_game
    try:
        data = request.json
        config.OPENAI_API_KEY = data['apiKey']
        
        client = OpenAIClient(config.OPENAI_API_KEY)
        
        print("\n" + "="*50)
        print("GAME GENERATOR v6 - 16-Bit Style!")
        print("="*50)
        
        print("\n[1/2] Designing game...")
        designer = GameDesigner(client)
        game = designer.design_game(data['prompt'])
        print(f"Title: {game.get('title')}")
        
        print("\n[2/2] Generating 16-bit sprites...")
        sprites = SpriteGenerator(client, config.API_DELAY).generate_all(game)
        
        pending_game = {"ready": True, "game": game, "sprites": sprites}
        
        return jsonify({"success": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


def main():
    import webbrowser
    import threading
    
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║          🎮 GAME GENERATOR v6 - 16-Bit Style! 🎮              ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║                                                               ║
    ║  NEW IN v6:                                                   ║
    ║  • Better 16-bit pixel art (SNES/Genesis style)               ║
    ║  • Press R to restart                                         ║
    ║  • Dark dungeon atmosphere                                    ║
    ║  • Larger, more detailed sprites                              ║
    ║                                                               ║
    ║  HOW TO PLAY:                                                 ║
    ║  1. Browser opens → paste API key → describe game             ║
    ║  2. Click Generate (wait 30-45 sec)                           ║
    ║  3. Come back here → press ENTER → play!                      ║
    ║                                                               ║
    ║  CONTROLS: WASD=Move, F=Attack, SPACE=Talk, E=Use, R=Restart  ║
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
    
    print("\n⏳ Waiting for you to generate a game in the browser...")
    print("   (Press Ctrl+C to quit)\n")
    
    while True:
        try:
            if pending_game["ready"]:
                print("\n" + "="*50)
                print("🎮 GAME READY! Press ENTER to start...")
                print("="*50)
                input()
                
                game = pending_game["game"]
                sprites = pending_game["sprites"]
                pending_game["ready"] = False
                
                engine = GameEngine(game, sprites, config)
                engine.run()
                
                print("\n✨ Game finished!")
                print("⏳ Generate another in browser, or Ctrl+C to quit...\n")
            
            time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
