import os

# Screen / timing
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60
TILE = 32
VISION_TILES = 10

# Fog visibility rings: (radius in tiles, darkness 0..1)
FOG_RINGS = [
    (5, 0.00),  # fully visible
    (6, 0.75),
    (7, 0.85),
    (8, 0.95),
]
  # visibility radius in tiles

# Paths
DATA_DIR = "data"
ASSETS_DIR = "assets"
AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

# Settings
DEFAULT_SETTINGS = {
    "theme": "Classic Jungle",
    "music": True,
    "sfx": True
}

# Themes (colors)
THEMES = {
    "Classic Jungle": {
        "bg": (12, 18, 12),
        "floor": (26, 42, 26),
        "wall": (62, 82, 44),
        "bush": (38, 98, 58),
        "crate": (110, 90, 60),
        "door": (210, 190, 90),
        "exit": (180, 220, 140),
        "ui": (230, 240, 230),
        "player": (230, 230, 255),
        "hunter": (240, 120, 120),
        "tiger": (255, 165, 60),
        "footprint": (240, 210, 120),
        "fov": (255, 160, 160),
        "hide": (90, 150, 200)
    },
    "Night Ops": {
        "bg": (6, 10, 18),
        "floor": (16, 24, 40),
        "wall": (40, 56, 84),
        "bush": (30, 80, 80),
        "crate": (70, 70, 90),
        "door": (150, 150, 200),
        "exit": (100, 220, 220),
        "ui": (220, 230, 255),
        "player": (230, 230, 255),
        "hunter": (255, 120, 160),
        "tiger": (255, 180, 80),
        "footprint": (210, 200, 180),
        "fov": (255, 150, 200),
        "hide": (120, 140, 220)
    },
    "Dry Savanna": {
        "bg": (28, 22, 10),
        "floor": (66, 54, 20),
        "wall": (120, 90, 40),
        "bush": (120, 110, 40),
        "crate": (140, 110, 60),
        "door": (200, 180, 80),
        "exit": (200, 230, 120),
        "ui": (240, 230, 210),
        "player": (250, 240, 200),
        "hunter": (240, 120, 120),
        "tiger": (255, 170, 60),
        "footprint": (230, 210, 130),
        "fov": (255, 180, 160),
        "hide": (160, 160, 90)
    }
}

# Tile IDs
FLOOR=0; WALL=1; BUSH=2; DOOR=3; EXIT=4; CRATE=5; TIGER_SPAWN=6; SPAWN=7; HIDE=8

# AI caps
MAX_HUNTERS_OUT = 48
MAX_HUNTERS_IN  = 12

# Score files
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
SCORES_PATH   = os.path.join(DATA_DIR, "scores.json")
