"""
GENIE GAME GENERATOR v5 - Effects & Optimized!
===============================================
Visual effects when you interact + smart sprite limits.

OPTIMIZATIONS:
- Only 8 unique sprites generated (saves ~$0.32 per game)
- Reuses sprites for similar things (all enemies share 1 sprite)
- Effects are code-generated (no API cost!)

VISUAL EFFECTS:
- Blood splatter when hitting enemies
- Magic sparkles when opening chests
- Heal glow when picking up potions
- Death explosion when enemies die
- Item pickup flash

COST: ~$0.35 per game (8 sprites × $0.04 + text)

HOW TO RUN:
1. cd ~/Desktop/game_gen
2. source game_env/bin/activate  
3. python game_generator_v5.py
4. Open http://localhost:5000
5. Paste OpenAI key, enter prompt, play!
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
    
    TILE_SIZE = 32
    GAME_WIDTH = 850
    GAME_HEIGHT = 600
    MAP_WIDTH = 20
    MAP_HEIGHT = 15
    PLAYER_SPEED = 4
    API_DELAY = 0.5
    
    PLAYER_MAX_HEALTH = 100
    ATTACK_COOLDOWN = 25
    ATTACK_RANGE = 1.5
    
    # SPRITE LIMITS - Only generate these (saves money!)
    # Everything else reuses these or uses code-generated effects
    MAX_SPRITES = 8


# ============================================================
# PARTICLE SYSTEM - Visual effects (FREE - no API!)
# ============================================================

class Particle:
    """A single particle for effects"""
    def __init__(self, x, y, color, vx=0, vy=0, life=30, size=4, gravity=0):
        self.x = x
        self.y = y
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
        alpha = int(255 * (self.life / self.max_life))
        size = max(1, int(self.size * (self.life / self.max_life)))
        # Draw circle
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), size)


class EffectsManager:
    """Manages all visual effects - NO API COST!"""
    
    def __init__(self):
        self.particles = []
        self.screen_flash = 0
        self.flash_color = (255, 255, 255)
    
    def update(self):
        """Update all particles"""
        self.particles = [p for p in self.particles if p.update()]
        if self.screen_flash > 0:
            self.screen_flash -= 1
    
    def draw(self, screen):
        """Draw all particles"""
        for p in self.particles:
            p.draw(screen)
        
        # Screen flash effect
        if self.screen_flash > 0:
            flash_surface = pygame.Surface(screen.get_size())
            flash_surface.fill(self.flash_color)
            flash_surface.set_alpha(int(50 * (self.screen_flash / 10)))
            screen.blit(flash_surface, (0, 0))
    
    def blood_splatter(self, x, y):
        """Red particles when hitting enemy"""
        for _ in range(12):
            self.particles.append(Particle(
                x + random.randint(-5, 5),
                y + random.randint(-5, 5),
                color=(random.randint(150, 255), 0, 0),
                vx=random.uniform(-3, 3),
                vy=random.uniform(-4, 1),
                life=random.randint(15, 30),
                size=random.randint(2, 5),
                gravity=0.2
            ))
    
    def death_explosion(self, x, y):
        """Big explosion when enemy dies"""
        colors = [(255, 100, 0), (255, 200, 0), (255, 50, 0), (200, 0, 0)]
        for _ in range(25):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2, 6)
            self.particles.append(Particle(
                x, y,
                color=random.choice(colors),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                life=random.randint(20, 40),
                size=random.randint(3, 7),
                gravity=0.1
            ))
        self.screen_flash = 8
        self.flash_color = (255, 100, 0)
    
    def magic_sparkles(self, x, y):
        """Sparkles when opening chest/using magic"""
        colors = [(255, 255, 100), (100, 200, 255), (255, 100, 255), (100, 255, 200)]
        for _ in range(20):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1, 4)
            self.particles.append(Particle(
                x, y,
                color=random.choice(colors),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed - 2,
                life=random.randint(30, 50),
                size=random.randint(2, 5),
                gravity=-0.05  # Float upward
            ))
        self.screen_flash = 5
        self.flash_color = (200, 200, 255)
    
    def heal_effect(self, x, y):
        """Green glow when healing"""
        for _ in range(15):
            self.particles.append(Particle(
                x + random.randint(-10, 10),
                y + random.randint(-10, 10),
                color=(50, 255, 50),
                vx=random.uniform(-0.5, 0.5),
                vy=random.uniform(-2, -0.5),
                life=random.randint(20, 40),
                size=random.randint(3, 6),
                gravity=-0.1
            ))
        self.screen_flash = 4
        self.flash_color = (50, 255, 50)
    
    def item_pickup(self, x, y):
        """Quick flash when picking up item"""
        colors = [(255, 255, 0), (255, 200, 100)]
        for _ in range(10):
            angle = random.uniform(0, 2 * math.pi)
            self.particles.append(Particle(
                x, y,
                color=random.choice(colors),
                vx=math.cos(angle) * 3,
                vy=math.sin(angle) * 3,
                life=15,
                size=4,
                gravity=0
            ))
    
    def dust_poof(self, x, y):
        """Dust when walking/landing"""
        for _ in range(5):
            self.particles.append(Particle(
                x + random.randint(-5, 5),
                y + 10,
                color=(150, 140, 120),
                vx=random.uniform(-1, 1),
                vy=random.uniform(-1, 0),
                life=15,
                size=3,
                gravity=0.1
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
        styled_prompt = f"32x32 pixel art game sprite, retro 16-bit style, simple colors, black outline: {prompt}"
        
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
            return img.resize((32, 32), Image.NEAREST)
        except Exception as e:
            print(f"Image error: {e}")
            return self._placeholder(prompt)
    
    def _placeholder(self, prompt: str) -> Image.Image:
        colors = {
            "player": (0, 150, 255), "hero": (0, 150, 255), "warrior": (0, 150, 255),
            "tree": (34, 139, 34), "rock": (128, 128, 128), "water": (64, 164, 223),
            "grass": (100, 200, 100), "key": (255, 215, 0), "gold": (255, 215, 0),
            "door": (139, 69, 19), "chest": (160, 82, 45), "potion": (255, 0, 255),
            "health": (255, 50, 50), "enemy": (200, 30, 30), "monster": (200, 30, 30),
            "npc": (255, 200, 100), "wizard": (100, 100, 200),
        }
        color = (128, 0, 128)
        for key, col in colors.items():
            if key in prompt.lower():
                color = col
                break
        return Image.new("RGB", (32, 32), color)


# ============================================================
# GAME DESIGNER - Simplified for fewer sprites
# ============================================================

class GameDesigner:
    def __init__(self, client: OpenAIClient):
        self.client = client
    
    def design_game(self, user_prompt: str) -> dict:
        num_enemies = random.randint(2, 4)
        
        # Simplified prompt - fewer unique things = fewer sprites needed
        design_prompt = f'''Create a simple 2D adventure game: "{user_prompt}"

Return ONLY JSON:

{{
    "title": "Creative Title",
    "story": "One sentence hook",
    "theme_color": "red/blue/green/purple",
    
    "player": {{
        "name": "Hero Name",
        "sprite_desc": "hero description 5 words max",
        "start_x": 2, "start_y": 12,
        "attack_power": 20
    }},
    
    "enemy_type": {{
        "name": "Enemy Type Name",
        "sprite_desc": "enemy description 5 words max",
        "health": 30,
        "damage": 10
    }},
    
    "enemy_positions": [
        {{"x": 12, "y": 5}},
        {{"x": 8, "y": 8}},
        {{"x": 15, "y": 3}}
    ],
    
    "npc": {{
        "name": "NPC Name",
        "sprite_desc": "npc description 5 words max",
        "x": 5, "y": 6,
        "dialogue_hint": "Helpful hint about the quest",
        "dialogue_win": "Congratulations message"
    }},
    
    "quest_item": {{
        "name": "Item Name",
        "sprite_desc": "item description 4 words",
        "x": 14, "y": 4
    }},
    
    "chest": {{
        "name": "Chest Name",
        "sprite_desc": "chest or container",
        "x": 17, "y": 5
    }},
    
    "objectives": [
        {{"id": 1, "task": "Defeat {num_enemies} enemies", "type": "kill", "target": {num_enemies}}},
        {{"id": 2, "task": "Find the item", "type": "find", "target": "quest_item"}},
        {{"id": 3, "task": "Open the chest", "type": "use", "target": "chest"}}
    ]
}}

RULES:
- Keep sprite descriptions SHORT (5 words max)
- Only describe unique things (all enemies look the same)
- Map is 20x15 tiles
- Be creative with names!'''

        print("Generating game design...")
        response = self.client.generate_text(design_prompt)
        
        response = response.strip()
        if "```" in response:
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        
        try:
            return json.loads(response.strip())
        except:
            return self._fallback(user_prompt, num_enemies)
    
    def _fallback(self, prompt: str, num_enemies: int) -> dict:
        return {
            "title": f"Quest: {prompt[:15]}",
            "story": "Defeat enemies and find treasure!",
            "theme_color": "red",
            "player": {"name": "Hero", "sprite_desc": "brave knight armor", "start_x": 2, "start_y": 12, "attack_power": 20},
            "enemy_type": {"name": "Monster", "sprite_desc": "scary dark creature", "health": 30, "damage": 10},
            "enemy_positions": [{"x": 12, "y": 5}, {"x": 8, "y": 8}, {"x": 15, "y": 3}][:num_enemies],
            "npc": {"name": "Sage", "sprite_desc": "old wise wizard", "x": 5, "y": 6, "dialogue_hint": "Defeat the monsters first!", "dialogue_win": "You are victorious!"},
            "quest_item": {"name": "Magic Key", "sprite_desc": "golden glowing key", "x": 14, "y": 4},
            "chest": {"name": "Treasure Chest", "sprite_desc": "wooden treasure chest", "x": 17, "y": 5},
            "objectives": [
                {"id": 1, "task": f"Defeat {num_enemies} enemies", "type": "kill", "target": num_enemies},
                {"id": 2, "task": "Find the key", "type": "find", "target": "quest_item"},
                {"id": 3, "task": "Open the chest", "type": "use", "target": "chest"}
            ]
        }


# ============================================================
# SPRITE GENERATOR - Limited to 8 sprites!
# ============================================================

class SpriteGenerator:
    """
    Only generates 8 sprites to save money:
    1. Player
    2. Enemy (shared by all enemies)
    3. NPC
    4. Quest item
    5. Chest
    6. Grass
    7. Tree
    8. Health potion (code-generated, not API)
    
    Cost: 7 API calls × $0.04 = $0.28
    """
    
    def __init__(self, client: OpenAIClient, delay: float = 0.5):
        self.client = client
        self.delay = delay
    
    def generate_all(self, game: dict) -> dict:
        sprites = {}
        generated = 0
        max_gen = 7  # Only 7 API calls!
        
        # 1. Player (required)
        print(f"  [{generated+1}/{max_gen}] Player...")
        sprites["player"] = self.client.generate_image(game["player"]["sprite_desc"])
        generated += 1
        time.sleep(self.delay)
        
        # 2. Enemy (shared by ALL enemies)
        print(f"  [{generated+1}/{max_gen}] Enemy...")
        sprites["enemy"] = self.client.generate_image(game["enemy_type"]["sprite_desc"])
        generated += 1
        time.sleep(self.delay)
        
        # 3. NPC
        print(f"  [{generated+1}/{max_gen}] NPC...")
        sprites["npc"] = self.client.generate_image(game["npc"]["sprite_desc"])
        generated += 1
        time.sleep(self.delay)
        
        # 4. Quest item
        print(f"  [{generated+1}/{max_gen}] Item...")
        sprites["quest_item"] = self.client.generate_image(game["quest_item"]["sprite_desc"])
        generated += 1
        time.sleep(self.delay)
        
        # 5. Chest
        print(f"  [{generated+1}/{max_gen}] Chest...")
        sprites["chest"] = self.client.generate_image(game["chest"]["sprite_desc"])
        generated += 1
        time.sleep(self.delay)
        
        # 6. Grass (simple)
        print(f"  [{generated+1}/{max_gen}] Grass...")
        sprites["grass"] = self.client.generate_image("green grass ground tile")
        generated += 1
        time.sleep(self.delay)
        
        # 7. Tree/obstacle
        print(f"  [{generated+1}/{max_gen}] Tree...")
        sprites["tree"] = self.client.generate_image("pixel art tree")
        generated += 1
        
        # 8. Health potion - CODE GENERATED (free!)
        print("  [FREE] Health potion (code-generated)...")
        sprites["potion"] = self._make_potion()
        
        # Rock - CODE GENERATED (free!)
        print("  [FREE] Rock (code-generated)...")
        sprites["rock"] = self._make_rock()
        
        print(f"\n  Total API calls: {generated} (~${generated * 0.04:.2f})")
        return sprites
    
    def _make_potion(self) -> Image.Image:
        """Code-generated potion sprite (FREE!)"""
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        pixels = img.load()
        # Simple potion bottle shape
        for y in range(8, 28):
            for x in range(10, 22):
                if 12 <= x <= 19 and 10 <= y <= 26:
                    # Bottle body
                    pixels[x, y] = (255, 50, 100, 255)
                if 14 <= x <= 17 and 8 <= y <= 11:
                    # Bottle neck
                    pixels[x, y] = (200, 40, 80, 255)
        # Outline
        for y in range(32):
            for x in range(32):
                if pixels[x, y][3] > 0:
                    for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                        nx, ny = x+dx, y+dy
                        if 0 <= nx < 32 and 0 <= ny < 32 and pixels[nx, ny][3] == 0:
                            pixels[nx, ny] = (0, 0, 0, 255)
        return img
    
    def _make_rock(self) -> Image.Image:
        """Code-generated rock sprite (FREE!)"""
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        pixels = img.load()
        # Simple rock shape
        for y in range(10, 28):
            for x in range(6, 26):
                dist = ((x - 16)**2 + (y - 20)**2) ** 0.5
                if dist < 10 + random.randint(-2, 2):
                    shade = random.randint(100, 140)
                    pixels[x, y] = (shade, shade, shade + 10, 255)
        return img


# ============================================================
# GAME ENGINE - With effects!
# ============================================================

class GameEngine:
    def __init__(self, game: dict, sprites: dict, config: Config):
        self.game = game
        self.config = config
        
        pygame.init()
        self.screen = pygame.display.set_mode((config.GAME_WIDTH, config.GAME_HEIGHT))
        pygame.display.set_caption(game.get("title", "Adventure"))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 22)
        self.font_large = pygame.font.Font(None, 28)
        
        # Effects system!
        self.effects = EffectsManager()
        
        # Convert sprites
        self.surfaces = {}
        for name, img in sprites.items():
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            surface = pygame.image.fromstring(img.tobytes(), img.size, "RGBA")
            self.surfaces[name] = pygame.transform.scale(surface, (config.TILE_SIZE, config.TILE_SIZE))
        
        # Player
        self.player_x = game["player"]["start_x"] * config.TILE_SIZE
        self.player_y = game["player"]["start_y"] * config.TILE_SIZE
        self.player_health = config.PLAYER_MAX_HEALTH
        self.player_attack = game["player"].get("attack_power", 20)
        self.attack_cooldown = 0
        self.last_move = 0
        
        # State
        self.inventory = []
        self.completed = set()
        self.enemies_killed = 0
        self.chest_opened = False
        self.message = game.get("story", "")
        self.message_timer = 240
        self.game_over = False
        self.game_won = False
        
        # Enemies
        self.enemies = []
        for i, pos in enumerate(game.get("enemy_positions", [])):
            self.enemies.append({
                "id": i,
                "px": pos["x"] * config.TILE_SIZE,
                "py": pos["y"] * config.TILE_SIZE,
                "health": game["enemy_type"]["health"],
                "max_health": game["enemy_type"]["health"],
                "damage": game["enemy_type"]["damage"],
                "dir": random.choice([-1, 1]),
                "timer": 0
            })
        
        # Health potions (random positions)
        self.potions = [
            {"x": random.randint(3, 17), "y": random.randint(3, 12), "collected": False},
            {"x": random.randint(3, 17), "y": random.randint(3, 12), "collected": False},
        ]
        
        # Terrain (random trees and rocks)
        self.terrain = []
        for _ in range(8):
            self.terrain.append({"type": "tree", "x": random.randint(0, 19), "y": random.randint(0, 5)})
        for _ in range(4):
            self.terrain.append({"type": "rock", "x": random.randint(5, 15), "y": random.randint(6, 12)})
        
        self.build_collisions()
    
    def build_collisions(self):
        self.solid = set()
        for t in self.terrain:
            self.solid.add((t["x"], t["y"]))
        if not self.chest_opened:
            self.solid.add((self.game["chest"]["x"], self.game["chest"]["y"]))
    
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
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
                
                moved = self.move(dx * self.config.PLAYER_SPEED, dy * self.config.PLAYER_SPEED)
                
                # Dust effect when moving
                self.last_move += 1
                if moved and self.last_move > 10:
                    self.effects.dust_poof(self.player_x + 16, self.player_y + 28)
                    self.last_move = 0
                
                self.update_enemies()
                self.check_pickups()
                self.check_damage()
                
                if self.attack_cooldown > 0:
                    self.attack_cooldown -= 1
                
                if self.player_health <= 0:
                    self.game_over = True
                    self.msg("YOU DIED! Press ESC")
                
                if len(self.completed) >= len(self.game["objectives"]):
                    self.game_won = True
                    self.msg("🎉 YOU WIN!")
            
            # Update effects
            self.effects.update()
            
            if self.message_timer > 0:
                self.message_timer -= 1
            
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()
    
    def move(self, dx, dy):
        ts = self.config.TILE_SIZE
        moved = False
        
        new_x = self.player_x + dx
        if 0 <= new_x < self.config.MAP_WIDTH * ts - ts:
            if (int(new_x // ts), int(self.player_y // ts)) not in self.solid:
                self.player_x = new_x
                if dx != 0: moved = True
        
        new_y = self.player_y + dy
        if 0 <= new_y < self.config.MAP_HEIGHT * ts - ts:
            if (int(self.player_x // ts), int(new_y // ts)) not in self.solid:
                self.player_y = new_y
                if dy != 0: moved = True
        
        return moved
    
    def update_enemies(self):
        ts = self.config.TILE_SIZE
        for e in self.enemies:
            if e["health"] <= 0:
                continue
            dist = ((self.player_x - e["px"])**2 + (self.player_y - e["py"])**2) ** 0.5
            if dist < ts * 5:
                # Chase
                if self.player_x > e["px"]: e["px"] += 1.5
                elif self.player_x < e["px"]: e["px"] -= 1.5
                if self.player_y > e["py"]: e["py"] += 1.5
                elif self.player_y < e["py"]: e["py"] -= 1.5
            else:
                # Patrol
                e["timer"] += 1
                if e["timer"] > 60:
                    e["dir"] = random.choice([-1, 1])
                    e["timer"] = 0
                e["px"] += e["dir"]
                e["px"] = max(ts, min(e["px"], (self.config.MAP_WIDTH - 2) * ts))
    
    def check_damage(self):
        ts = self.config.TILE_SIZE
        for e in self.enemies:
            if e["health"] <= 0:
                continue
            dist = ((self.player_x - e["px"])**2 + (self.player_y - e["py"])**2) ** 0.5
            if dist < ts * 0.7:
                self.player_health -= max(1, e["damage"] // 20)
                # Small blood effect on player
                if random.random() < 0.3:
                    self.effects.blood_splatter(self.player_x + 16, self.player_y + 16)
    
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
                
                # BLOOD EFFECT!
                self.effects.blood_splatter(e["px"] + 16, e["py"] + 16)
                
                if e["health"] <= 0:
                    self.enemies_killed += 1
                    # DEATH EXPLOSION!
                    self.effects.death_explosion(e["px"] + 16, e["py"] + 16)
                    self.msg(f"Defeated {self.game['enemy_type']['name']}!")
                    self.check_objective("kill", self.enemies_killed)
                else:
                    self.msg(f"Hit! (-{self.player_attack})")
                
                self.attack_cooldown = self.config.ATTACK_COOLDOWN
                return
        
        if not hit:
            self.msg("*swing* Miss!")
            self.attack_cooldown = 10
    
    def check_pickups(self):
        ts = self.config.TILE_SIZE
        px, py = int(self.player_x // ts), int(self.player_y // ts)
        
        # Potions
        for p in self.potions:
            if p["collected"]:
                continue
            if p["x"] == px and p["y"] == py:
                p["collected"] = True
                heal = 30
                self.player_health = min(self.config.PLAYER_MAX_HEALTH, self.player_health + heal)
                # HEAL EFFECT!
                self.effects.heal_effect(self.player_x + 16, self.player_y + 16)
                self.msg(f"+{heal} HP!")
        
        # Quest item
        item = self.game["quest_item"]
        if "quest_item" not in self.inventory:
            if item["x"] == px and item["y"] == py:
                self.inventory.append("quest_item")
                # ITEM PICKUP EFFECT!
                self.effects.item_pickup(self.player_x + 16, self.player_y + 16)
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
                # MAGIC SPARKLES!
                self.effects.magic_sparkles(chest["x"] * ts + 16, chest["y"] * ts + 16)
                self.msg(f"Opened {chest['name']}! ✨")
                self.check_objective("use", "chest")
                self.build_collisions()
            elif self.chest_opened:
                self.msg("Already opened!")
            else:
                self.msg(f"Need {self.game['quest_item']['name']} first!")
        else:
            self.msg("Nothing to use here.")
    
    def check_objective(self, obj_type, target):
        for obj in self.game["objectives"]:
            if obj["id"] in self.completed:
                continue
            if obj["type"] == obj_type:
                if obj_type == "kill" and self.enemies_killed >= obj["target"]:
                    self.completed.add(obj["id"])
                    self.msg("✓ " + obj["task"])
                elif obj_type == "find" and target == obj["target"]:
                    self.completed.add(obj["id"])
                    self.msg("✓ " + obj["task"])
                elif obj_type == "use" and target == obj["target"]:
                    self.completed.add(obj["id"])
                    self.msg("✓ " + obj["task"])
    
    def msg(self, text):
        self.message = text
        self.message_timer = 180
    
    def draw(self):
        ts = self.config.TILE_SIZE
        
        # Grass
        grass = self.surfaces.get("grass")
        for x in range(self.config.MAP_WIDTH):
            for y in range(self.config.MAP_HEIGHT):
                if grass:
                    self.screen.blit(grass, (x * ts, y * ts))
                else:
                    pygame.draw.rect(self.screen, (100, 180, 100), (x * ts, y * ts, ts, ts))
        
        # Terrain
        for t in self.terrain:
            surface = self.surfaces.get(t["type"])
            if surface:
                self.screen.blit(surface, (t["x"] * ts, t["y"] * ts))
        
        # Chest (if not opened)
        if not self.chest_opened:
            chest = self.game["chest"]
            surface = self.surfaces.get("chest")
            if surface:
                self.screen.blit(surface, (chest["x"] * ts, chest["y"] * ts))
        
        # Potions
        for p in self.potions:
            if not p["collected"]:
                surface = self.surfaces.get("potion")
                if surface:
                    self.screen.blit(surface, (p["x"] * ts, p["y"] * ts))
        
        # Quest item
        if "quest_item" not in self.inventory:
            item = self.game["quest_item"]
            surface = self.surfaces.get("quest_item")
            if surface:
                self.screen.blit(surface, (item["x"] * ts, item["y"] * ts))
        
        # Enemies
        for e in self.enemies:
            if e["health"] <= 0:
                continue
            surface = self.surfaces.get("enemy")
            if surface:
                self.screen.blit(surface, (e["px"], e["py"]))
            # Health bar
            bar_w = ts
            pct = e["health"] / e["max_health"]
            pygame.draw.rect(self.screen, (80, 0, 0), (e["px"], e["py"] - 6, bar_w, 4))
            pygame.draw.rect(self.screen, (0, 200, 0), (e["px"], e["py"] - 6, int(bar_w * pct), 4))
        
        # NPC
        npc = self.game["npc"]
        surface = self.surfaces.get("npc")
        if surface:
            self.screen.blit(surface, (npc["x"] * ts, npc["y"] * ts))
        
        # Player
        surface = self.surfaces.get("player")
        if surface:
            self.screen.blit(surface, (self.player_x, self.player_y))
        
        # DRAW EFFECTS!
        self.effects.draw(self.screen)
        
        self.draw_ui()
        pygame.display.flip()
    
    def draw_ui(self):
        ts = self.config.TILE_SIZE
        panel_x = self.config.MAP_WIDTH * ts
        panel_w = self.config.GAME_WIDTH - panel_x
        
        pygame.draw.rect(self.screen, (25, 25, 35), (panel_x, 0, panel_w, self.config.GAME_HEIGHT))
        
        y = 10
        
        # Title
        title = self.font_large.render(self.game.get("title", "Game")[:18], True, (255, 215, 0))
        self.screen.blit(title, (panel_x + 10, y))
        y += 35
        
        # Health
        self.screen.blit(self.font.render("HEALTH:", True, (255, 100, 100)), (panel_x + 10, y))
        y += 18
        bar_w = panel_w - 20
        pct = max(0, self.player_health / self.config.PLAYER_MAX_HEALTH)
        pygame.draw.rect(self.screen, (80, 0, 0), (panel_x + 10, y, bar_w, 14))
        pygame.draw.rect(self.screen, (220, 50, 50), (panel_x + 10, y, int(bar_w * pct), 14))
        hp_text = self.font.render(f"{max(0, self.player_health)}/{self.config.PLAYER_MAX_HEALTH}", True, (255, 255, 255))
        self.screen.blit(hp_text, (panel_x + 15, y))
        y += 25
        
        # Enemies
        alive = len([e for e in self.enemies if e["health"] > 0])
        self.screen.blit(self.font.render(f"Enemies: {alive} left", True, (255, 150, 150)), (panel_x + 10, y))
        y += 28
        
        # Objectives
        self.screen.blit(self.font.render("OBJECTIVES:", True, (150, 150, 255)), (panel_x + 10, y))
        y += 20
        for obj in self.game["objectives"]:
            done = obj["id"] in self.completed
            color = (100, 255, 100) if done else (200, 200, 200)
            prefix = "✓" if done else "○"
            self.screen.blit(self.font.render(f"{prefix} {obj['task'][:20]}", True, color), (panel_x + 10, y))
            y += 18
        
        y += 10
        
        # Inventory
        self.screen.blit(self.font.render("INVENTORY:", True, (255, 200, 100)), (panel_x + 10, y))
        y += 20
        if self.inventory:
            for item_id in self.inventory:
                name = self.game["quest_item"]["name"] if item_id == "quest_item" else item_id
                self.screen.blit(self.font.render(f"• {name[:16]}", True, (200, 200, 200)), (panel_x + 10, y))
                y += 16
        else:
            self.screen.blit(self.font.render("(empty)", True, (100, 100, 100)), (panel_x + 10, y))
        
        # Controls
        y = self.config.GAME_HEIGHT - 120
        for line in ["CONTROLS:", "WASD - Move", "F - Attack", "SPACE - Talk", "E - Use item", "ESC - Quit"]:
            color = (100, 200, 255) if "CONTROLS" in line else (120, 120, 120)
            self.screen.blit(self.font.render(line, True, color), (panel_x + 10, y))
            y += 16
        
        # Message
        if self.message_timer > 0 and self.message:
            box_h = 40
            box_y = self.config.MAP_HEIGHT * ts - box_h - 10
            box_w = self.config.MAP_WIDTH * ts - 20
            s = pygame.Surface((box_w, box_h))
            s.fill((0, 0, 0))
            s.set_alpha(220)
            self.screen.blit(s, (10, box_y))
            self.screen.blit(self.font.render(self.message[:65], True, (255, 255, 255)), (20, box_y + 10))


# ============================================================
# WEB INTERFACE
# ============================================================

app = Flask(__name__)
config = Config()

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>🎮 Game Generator v5</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #0f0f1a, #1a1a2e);
            min-height: 100vh; color: white; padding: 20px;
        }
        .container { max-width: 700px; margin: 0 auto; }
        h1 {
            text-align: center; font-size: 2em; margin-bottom: 5px;
            background: linear-gradient(90deg, #ff6b6b, #ffd93d);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .subtitle { text-align: center; color: #888; margin-bottom: 20px; }
        .card {
            background: rgba(255,255,255,0.08); border-radius: 12px;
            padding: 18px; margin-bottom: 15px;
        }
        label { display: block; margin-bottom: 5px; color: #ffd93d; font-weight: bold; }
        input, textarea {
            width: 100%; padding: 11px; border: 2px solid #333;
            border-radius: 8px; background: #1a1a2e; color: white; font-size: 15px;
        }
        textarea { height: 70px; margin-top: 5px; }
        button {
            width: 100%; padding: 13px; font-size: 17px; font-weight: bold;
            border: none; border-radius: 8px; cursor: pointer;
            background: linear-gradient(90deg, #ff6b6b, #ffd93d); color: #1a1a2e;
        }
        button:disabled { background: #444; color: #888; }
        .status { text-align: center; padding: 12px; }
        .examples { display: flex; gap: 6px; flex-wrap: wrap; margin: 10px 0; }
        .ex-btn {
            padding: 7px 10px; font-size: 12px; width: auto;
            background: rgba(255, 217, 61, 0.15); border: 1px solid #ffd93d; color: #ffd93d;
        }
        .tag { background: #ff6b6b; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
        .features { font-size: 13px; color: #aaa; line-height: 1.7; }
        .features b { color: #ffd93d; }
        a { color: #6bcfff; }
        .spinner {
            display: inline-block; width: 16px; height: 16px;
            border: 3px solid #fff; border-top-color: transparent;
            border-radius: 50%; animation: spin 1s linear infinite; margin-right: 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .cost { background: #1a3a1a; padding: 10px; border-radius: 8px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 Game Generator v5</h1>
        <p class="subtitle">Visual Effects + Optimized! <span class="tag">NEW</span></p>
        
        <div class="card">
            <label>🔑 OpenAI API Key</label>
            <input type="password" id="apiKey" placeholder="sk-...">
            <small style="color:#666">Get key: <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com</a></small>
        </div>
        
        <div class="card">
            <label>✨ Describe Your Adventure</label>
            <textarea id="prompt" placeholder="A cursed temple with snake guardians and golden idol..."></textarea>
            <div class="examples">
                <button class="ex-btn" onclick="setEx('A haunted mansion with ghost butler and cursed painting')">👻 Haunted</button>
                <button class="ex-btn" onclick="setEx('A volcano lair with fire imps and dragon egg')">🌋 Volcano</button>
                <button class="ex-btn" onclick="setEx('An ice cave with frost wolves and frozen crown')">❄️ Ice</button>
                <button class="ex-btn" onclick="setEx('A jungle ruins with snake warriors and jade mask')">🌴 Jungle</button>
            </div>
        </div>
        
        <button id="btn" onclick="generate()">⚔️ Generate Adventure!</button>
        <div id="status" class="status" style="display:none;"></div>
        
        <div class="card features">
            <b>✨ New Effects:</b><br>
            💥 Blood splatter when hitting enemies<br>
            💀 Explosion when enemies die<br>
            ✨ Magic sparkles when opening chests<br>
            💚 Green glow when healing<br>
            🌟 Flash when picking up items<br><br>
            
            <div class="cost">
                <b>💰 Cost Optimized:</b><br>
                Only 7 API sprites generated (~$0.28)<br>
                Effects are code-generated (FREE!)<br>
                <b>Total: ~$0.30 per game</b>
            </div>
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
            status.innerHTML = '<span class="spinner"></span> Generating (30-45 sec)...';
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

@app.route('/')
def index():
    return render_template_string(HTML)

# Global storage for game data (to pass between web and main thread)
pending_game = {"ready": False, "game": None, "sprites": None}

@app.route('/generate', methods=['POST'])
def generate():
    global pending_game
    try:
        data = request.json
        config.OPENAI_API_KEY = data['apiKey']
        
        client = OpenAIClient(config.OPENAI_API_KEY)
        
        print("\n" + "="*50)
        print("GAME GENERATOR v5 - Effects Edition!")
        print("="*50)
        
        print("\n[1/2] Designing game...")
        designer = GameDesigner(client)
        game = designer.design_game(data['prompt'])
        print(f"Title: {game.get('title')}")
        
        print("\n[2/2] Generating sprites (7 API calls)...")
        sprites = SpriteGenerator(client, config.API_DELAY).generate_all(game)
        
        # Store for main thread to pick up
        pending_game = {"ready": True, "game": game, "sprites": sprites}
        
        return jsonify({"success": True, "message": "Game ready! Check your terminal and press Enter to start."})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


def main():
    import webbrowser
    import threading
    
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║          🎮 GAME GENERATOR v5 - Effects Edition! 🎮           ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║                                                               ║
    ║  NEW: Visual Effects!                                         ║
    ║  💥 Blood splatter    💀 Death explosions                     ║
    ║  ✨ Magic sparkles    💚 Heal glow                            ║
    ║                                                               ║
    ║  OPTIMIZED: Only 7 sprites (~$0.28)                           ║
    ║  Effects are code-generated (FREE!)                           ║
    ║                                                               ║
    ║  HOW TO USE:                                                  ║
    ║  1. Browser opens → paste API key → enter prompt              ║
    ║  2. Click Generate and wait 30-45 sec                         ║
    ║  3. When done, come back here and press ENTER to play!        ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Run Flask in background thread (web server)
    def run_flask():
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)  # Quieter logs
        app.run(debug=False, port=5000, threaded=True, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    webbrowser.open('http://127.0.0.1:5000')
    
    # Main loop - wait for game to be ready, then run Pygame on main thread
    print("\n⏳ Waiting for you to generate a game in the browser...")
    print("   (Press Ctrl+C to quit)\n")
    
    while True:
        try:
            if pending_game["ready"]:
                print("\n" + "="*50)
                print("🎮 GAME READY! Press ENTER to start playing...")
                print("="*50)
                input()
                
                # Run game on main thread (REQUIRED for Mac!)
                game = pending_game["game"]
                sprites = pending_game["sprites"]
                pending_game["ready"] = False
                
                engine = GameEngine(game, sprites, config)
                engine.run()
                
                print("\n✨ Game finished!")
                print("⏳ Generate another game in browser, or Ctrl+C to quit...\n")
            
            time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
