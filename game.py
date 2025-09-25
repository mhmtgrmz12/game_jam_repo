import time, random, pygame
from config import *
from utils import load_json, save_json, grid_to_px, px_to_grid
from audio import Audio
from camera import Camera
from tilemap import TileMap
from entities import Player, Hunter
from footprints import Footprints
from states import State
from ui import draw_menu, draw_themes, draw_scores

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Tiger Rescue – The Footprint Maze")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        # Fog of War base surface
        self.darkness_base = pygame.Surface((SCREEN_W, SCREEN_H), flags=pygame.SRCALPHA)
        self.darkness_base.fill((0,0,0,255))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 22)
        self.bigfont = pygame.font.SysFont("arial", 40, bold=True)

        self.settings = load_json(SETTINGS_PATH, DEFAULT_SETTINGS.copy())
        self.theme_name = self.settings.get("theme","Classic Jungle")
        self.colors = THEMES.get(self.theme_name, THEMES["Classic Jungle"])

        self.audio = Audio(self.settings)

        self.state = State.MENU
        self.running = True

        self.menu_items = ["Games", "Scores", "Themes", "Quit"]
        self.menu_idx = 0
        self.theme_names = list(THEMES.keys())
        self.theme_idx = self.theme_names.index(self.theme_name) if self.theme_name in self.theme_names else 0

        self.scores = load_json(SCORES_PATH, [])

        # Music debounce
        self.chase_hold = 1.8
        self.chase_hold_t = 0.0
        self.music_mode = None

        # Footprint timing
        self.fp_timer = 0.0
        self.fp_interval_out = 0.8
        self.fp_interval_in  = 0.6

        # Scene transition protections (fix flicker)
        self.scene_cooldown = 0.0      # seconds; blocks rapid enter/exit
        self.indoor_exit_tile = (1, 1) # indoor tile to exit from
        self.left_entry_tile = True    # require leaving entry tile before exit allowed

        self.audio.play_music("menu")
        self.reset_world()

    # ---------------- World/Scenes ----------------
    def reset_world(self):
        self.overworld = TileMap(80, 60, self.colors, kind="overworld")
        self.warehouses = [TileMap(41,31,self.colors,kind="warehouse") for _ in self.overworld.doors]

        self.player = Player(*grid_to_px(self.overworld.w_tiles//2, self.overworld.h_tiles//2))
        self.cam = Camera(self.overworld.w_tiles*TILE, self.overworld.h_tiles*TILE)

        self.indoor_idx = None
        self.indoor_entry_grid = None

        self.hunters_out = []
        self.hunters_in = [ [] for _ in self.warehouses ]

        for _ in range(3):
            if self.overworld.spawn_points:
                gx,gy = random.choice(self.overworld.spawn_points)
                x,y = grid_to_px(gx,gy)
                self.hunters_out.append(Hunter(x,y,outdoor=True))

        self.timer_total = 9*60
        self.timer = self.timer_total

        self.tigers_remaining = sum(len(w.tiger_positions) for w in self.warehouses)
        self.tigers_rescued = 0

        self.footprints = Footprints(self.colors["footprint"])
        self.update_outdoor_footprints()

        self.any_chase = False
        self.in_indoor = False
        self.scene_cooldown = 0.0
        self.left_entry_tile = True
        self.update_music()

    def update_outdoor_footprints(self):
        pg = px_to_grid(self.player.pos.x, self.player.pos.y)
        target = None; bestd=1e9
        for i, door in enumerate(self.overworld.doors):
            if len(self.warehouses[i].tiger_positions)>0:
                d = abs(pg[0]-door[0]) + abs(pg[1]-door[1])
                if d<bestd: bestd=d; target=door
        passables = (FLOOR, BUSH, DOOR, EXIT, CRATE, SPAWN)
        self.footprints.compute_from_to(self.overworld.grid, pg, target, passables)

    def update_indoor_footprints(self):
        wmap = self.warehouses[self.indoor_idx]
        pg = px_to_grid(self.player.pos.x, self.player.pos.y)
        target = None; bestd=1e9
        for tg in wmap.tiger_positions:
            d = abs(pg[0]-tg[0]) + abs(pg[1]-tg[1])
            if d<bestd: bestd=d; target=tg
        passables = (FLOOR, CRATE, SPAWN, HIDE)
        self.footprints.compute_from_to(wmap.grid, pg, target, passables)

    def enter_warehouse_if_needed(self):
        """Enter only if cooldown is 0; after entering, set cooldown and require leaving the entry tile once before exit can trigger."""
        if self.scene_cooldown > 0:
            return False
        pg = px_to_grid(self.player.pos.x, self.player.pos.y)
        for i, door in enumerate(self.overworld.doors):
            if pg == door and len(self.warehouses[i].tiger_positions)>0:
                self.in_indoor = True
                self.indoor_idx = i
                self.indoor_entry_grid = door
                wmap = self.warehouses[i]
                # pick a walkable indoor entry near (1,1)
                entry = (1,1)
                for y in range(1, wmap.h_tiles-1):
                    for x in range(1, wmap.w_tiles-1):
                        if wmap.grid[y][x]==FLOOR:
                            entry=(x,y); break
                    else: continue
                    break
                self.player.pos = pygame.Vector2(*grid_to_px(*entry))
                self.cam = Camera(wmap.w_tiles*TILE, wmap.h_tiles*TILE)
                if len(self.hunters_in[i])==0:
                    for _ in range(2):
                        if wmap.spawn_points:
                            gx,gy = random.choice(wmap.spawn_points)
                            x,y = grid_to_px(gx,gy)
                            self.hunters_in[i].append(Hunter(x,y,outdoor=False))
                self.update_indoor_footprints()
                # after entering, start cooldown and reset exit guard
                self.scene_cooldown = 0.6
                self.left_entry_tile = False
                return True
        return False

    def exit_warehouse_if_needed(self):
        """Exit only if cooldown is 0 and the player has LEFT the entry tile (1,1) at least once."""
        if self.indoor_idx is None:
            return False
        if self.scene_cooldown > 0:
            return False
        wmap = self.warehouses[self.indoor_idx]
        pg = px_to_grid(self.player.pos.x, self.player.pos.y)
        # mark that player has left the entry tile at least once
        if not self.left_entry_tile and pg != self.indoor_exit_tile:
            self.left_entry_tile = True
        # allow exit only after player left and re-entered exit tile
        if self.left_entry_tile and pg == self.indoor_exit_tile:
            self.in_indoor = False
            door = self.indoor_entry_grid
            self.player.pos = pygame.Vector2(*grid_to_px(*door))
            self.cam = Camera(self.overworld.w_tiles*TILE, self.overworld.h_tiles*TILE)
            self.update_outdoor_footprints()
            self.indoor_idx=None
            # start cooldown after exiting
            self.scene_cooldown = 0.6
            return True
        return False

    def rescue_if_possible(self):
        if self.in_indoor and self.indoor_idx is not None:
            wmap = self.warehouses[self.indoor_idx]
            pg = px_to_grid(self.player.pos.x, self.player.pos.y)
            if pg in wmap.tiger_positions:
                wmap.tiger_positions.remove(pg)
                self.tigers_rescued += 1
                self.tigers_remaining -= 1
                self.audio.play_sfx("rescue")
                self.double_hunters()
                self.update_indoor_footprints()
                self.timer = min(self.timer + 20, self.timer_total + 60)

    def double_hunters(self):
        # Outdoor
        to_add_out = min(len(self.hunters_out), MAX_HUNTERS_OUT - len(self.hunters_out))
        for _ in range(max(0, to_add_out)):
            if self.overworld.spawn_points:
                gx,gy = random.choice(self.overworld.spawn_points)
                x,y = grid_to_px(gx,gy)
                self.hunters_out.append(Hunter(x,y,outdoor=True))
        # Indoor current
        if self.indoor_idx is not None:
            cur_list = self.hunters_in[self.indoor_idx]
            cap = MAX_HUNTERS_IN - len(cur_list)
            to_add_in = min(len(cur_list), cap)
            wmap = self.warehouses[self.indoor_idx]
            for _ in range(max(0, to_add_in)):
                if wmap.spawn_points:
                    gx,gy = random.choice(wmap.spawn_points)
                    x,y = grid_to_px(gx,gy)
                    cur_list.append(Hunter(x,y,outdoor=False))

    # ---------------- Music debounce ----------------
    def update_music(self):
        if self.state != State.PLAY:
            desired = "menu"
        else:
            chasing = self.any_chase or (self.chase_hold_t > 0)
            if self.in_indoor:
                desired = "chase_indoor" if chasing else "explore_indoor"
            else:
                desired = "chase_outdoor" if chasing else "explore_outdoor"
        if desired != self.music_mode:
            self.audio.play_music(desired)
            self.music_mode = desired

    # ---------------- Scores ----------------
    def add_score(self, time_left, rescued, caughts, difficulty="Default"):
        entry = {
            "timestamp": int(time.time()),
            "time_left": int(time_left),
            "rescued": rescued,
            "caughts": caughts,
            "difficulty": difficulty
        }
        self.scores.append(entry)
        self.scores = sorted(self.scores, key=lambda e:e["time_left"], reverse=True)[:10]
        save_json(SCORES_PATH, self.scores)

    # ---------------- Main loop ----------------
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)/1000.0
            # tick down scene cooldown each frame
            self.scene_cooldown = max(0.0, self.scene_cooldown - dt)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running=False
                elif e.type == pygame.KEYDOWN:
                    if self.state==State.MENU:
                        if e.key in (pygame.K_DOWN, pygame.K_s):
                            self.menu_idx = (self.menu_idx+1)%len(self.menu_items)
                        elif e.key in (pygame.K_UP, pygame.K_w):
                            self.menu_idx = (self.menu_idx-1)%len(self.menu_items)
                        elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self.handle_menu_select()
                    elif self.state==State.THEMES:
                        if e.key in (pygame.K_RIGHT, pygame.K_d):
                            self.theme_idx = (self.theme_idx+1)%len(self.theme_names)
                            self.apply_theme(self.theme_names[self.theme_idx])
                        elif e.key in (pygame.K_LEFT, pygame.K_a):
                            self.theme_idx = (self.theme_idx-1)%len(self.theme_names)
                            self.apply_theme(self.theme_names[self.theme_idx])
                        elif e.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_RETURN):
                            self.state = State.MENU
                            self.audio.play_music("menu")
                    elif self.state==State.SCORES:
                        if e.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_RETURN):
                            self.state = State.MENU
                            self.audio.play_music("menu")
                    elif self.state==State.PLAY:
                        if e.key==pygame.K_ESCAPE:
                            self.state = State.PAUSE
                        elif e.key==pygame.K_e:
                            self.rescue_if_possible()
                        elif e.key==pygame.K_h:
                            # HIDE toggle only indoor while on HIDE tile
                            if self.in_indoor and self.indoor_idx is not None:
                                wmap = self.warehouses[self.indoor_idx]
                                pg = px_to_grid(self.player.pos.x, self.player.pos.y)
                                if wmap.grid[pg[1]][pg[0]] == HIDE:
                                    self.player.hiding = not self.player.hiding
                    elif self.state==State.PAUSE:
                        if e.key==pygame.K_ESCAPE:
                            self.state = State.PLAY
                        elif e.key==pygame.K_r:
                            self.reset_world()
                        elif e.key==pygame.K_m:
                            self.state = State.MENU
                            self.audio.play_music("menu")

            if self.state==State.MENU:
                draw_menu(self.screen, self.bigfont, self.font, self.colors, self.menu_items, self.menu_idx)
            elif self.state==State.THEMES:
                draw_themes(self.screen, self.bigfont, self.font, self.colors, self.theme_names[self.theme_idx])
            elif self.state==State.SCORES:
                draw_scores(self.screen, self.bigfont, self.font, self.colors, self.scores)
            elif self.state==State.PLAY:
                self.update_play(dt)
                self.draw_play()
            elif self.state==State.PAUSE:
                self.draw_play(show_pause=True)

            pygame.display.flip()

        pygame.quit()

    # ---------------- State handlers ----------------
    def handle_menu_select(self):
        sel = self.menu_items[self.menu_idx]
        if sel=="Games":
            self.reset_world()
            self.state = State.PLAY
            self.update_music()
        elif sel=="Scores":
            self.state = State.SCORES
            self.audio.play_music("menu")
        elif sel=="Themes":
            self.state = State.THEMES
            self.audio.play_music("menu")
        elif sel=="Quit":
            self.running=False

    def apply_theme(self, name):
        self.theme_name = name
        self.colors = THEMES[name]
        self.settings["theme"]=name
        save_json(SETTINGS_PATH, self.settings)

    # ---------------- Play loop ----------------
    def update_play(self, dt):
        # Timer
        self.timer -= dt
        if self.timer <= 0:
            self.audio.play_sfx("caught")
            self.add_score(0, self.tigers_rescued, 1)
            self.state = State.SCORES
            self.audio.play_music("menu")
            return

        # Scene switching
        if not self.in_indoor:
            # Overworld
            self.player.move(dt, self.overworld.grid)
            pg = px_to_grid(self.player.pos.x, self.player.pos.y)
            if self.overworld.exit_pos and pg == self.overworld.exit_pos and self.tigers_remaining==0:
                self.add_score(self.timer, self.tigers_rescued, 0)
                self.state = State.SCORES
                self.audio.play_music("menu")
                return
            if self.enter_warehouse_if_needed():
                return

            # Hunters outdoor
            self.any_chase = False
            stealth_factor = 1.0 if self.overworld.grid[pg[1]][pg[0]]==BUSH else 0.0
            for h in self.hunters_out:
                h.update(dt, self.overworld.grid, self.player, stealth_factor)
                if h.state=="chase": self.any_chase=True
                if (self.player.pos - h.pos).length() < (self.player.radius + h.radius):
                    self.audio.play_sfx("caught")
                    self.add_score(0, self.tigers_rescued, 1)
                    self.state = State.SCORES
                    self.audio.play_music("menu")
                    return

            self.cam.follow(self.player.pos)

        else:
            # Indoor
            wmap = self.warehouses[self.indoor_idx]
            self.player.move(dt, wmap.grid)
            if self.exit_warehouse_if_needed():
                return
            self.any_chase = False
            pg = px_to_grid(self.player.pos.x, self.player.pos.y)

            # Stealth: CRATE (1.0), HIDE (0.4 without hiding, 1.2 when hiding)
            stealth_factor = 0.0
            if wmap.grid[pg[1]][pg[0]] == CRATE:
                stealth_factor = 1.0
            if wmap.grid[pg[1]][pg[0]] == HIDE:
                stealth_factor = 1.2 if self.player.hiding else 0.4

            for h in self.hunters_in[self.indoor_idx]:
                h.update(dt, wmap.grid, self.player, stealth_factor)
                if h.state=="chase": self.any_chase=True
                if (self.player.pos - h.pos).length() < (self.player.radius + h.radius):
                    self.audio.play_sfx("caught")
                    self.add_score(0, self.tigers_rescued, 1)
                    self.state = State.SCORES
                    self.audio.play_music("menu")
                    return

            self.cam.follow(self.player.pos)

        # ---- Debounced chase → music logic (once per frame) ----
        if self.any_chase:
            self.chase_hold_t = self.chase_hold
        else:
            self.chase_hold_t = max(0.0, self.chase_hold_t - dt)
        self.update_music()

        # Footprints interval update
        self.fp_timer -= dt
        if self.fp_timer <= 0:
            if not self.in_indoor:
                self.update_outdoor_footprints()
                self.fp_timer = self.fp_interval_out
            else:
                self.update_indoor_footprints()
                self.fp_timer = self.fp_interval_in

    def draw_play(self, show_pause=False):
        self.screen.fill(self.colors["bg"])
        if not self.in_indoor:
            self.overworld.draw(self.screen, self.cam, self.colors)
        else:
            self.warehouses[self.indoor_idx].draw(self.screen, self.cam, self.colors)

        # Footprints
        self.footprints.draw(self.screen, self.cam)

        # Tigers indoors
        if self.in_indoor:
            wmap = self.warehouses[self.indoor_idx]
            for gx,gy in wmap.tiger_positions:
                cx, cy = grid_to_px(gx,gy)
                p = self.cam.to_screen(pygame.Vector2(cx,cy))
                pygame.draw.circle(self.screen, self.colors["tiger"], (int(p.x), int(p.y)), 10)

        # Hunters
        if not self.in_indoor:
            for h in self.hunters_out:
                h.draw(self.screen, self.cam, self.colors, show_fov=False)
        else:
            for h in self.hunters_in[self.indoor_idx]:
                h.draw(self.screen, self.cam, self.colors, show_fov=False)

        # Player
        self.player.draw(self.screen, self.cam, self.colors["player"])
        self.draw_fog_of_war()

        # HUD
        total_tigers = self.tigers_rescued + self.tigers_remaining

        hud = f"Tigers: {self.tigers_rescued}/{total_tigers}   Hunters: {len(self.hunters_out) + sum(len(lst) for lst in self.hunters_in)}   Time: {int(self.timer//60):02d}:{int(self.timer%60):02d}"
        txt = self.font.render(hud, True, self.colors["ui"])
        self.screen.blit(txt, (16, 12))
        pass


        # Hidden tag (indoor)
        if self.in_indoor and getattr(self.player, "hiding", False):
            tag = self.font.render("(Hidden)", True, self.colors["hide"])
            self.screen.blit(tag, (16, 36))

        if show_pause:
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0,0,0,130))
            self.screen.blit(overlay, (0,0))
            t = self.bigfont.render("PAUSED", True, self.colors["ui"])
            self.screen.blit(t, (SCREEN_W//2 - t.get_width()//2, 160))
            msg = self.font.render("[Esc] Resume   [R] Restart   [M] Menu", True, self.colors["ui"])
            self.screen.blit(msg, (SCREEN_W//2 - msg.get_width()//2, 220))


    # game.py  — Game sınıfı içine ekle
    def draw_fog_of_war(self):
        import pygame
        from config import SCREEN_W, SCREEN_H, TILE

        # Lazily create darkness base once (tamamen siyah, %100 karanlık)
        if not hasattr(self, "darkness_base"):
            self.darkness_base = pygame.Surface((SCREEN_W, SCREEN_H), flags=pygame.SRCALPHA)
            self.darkness_base.fill((0, 0, 0, 255))

        darkness = self.darkness_base.copy()

        # Oyuncunun ekran koordinatı (piksel)
        px = int(self.player.pos.x - self.cam.offset.x + TILE // 2)
        py = int(self.player.pos.y - self.cam.offset.y + TILE // 2)

        # İstediğin halkalar (yarıçap karo cinsinden, karanlık oranı 0..1)
        # 5 kareye kadar %0 (tam görünür), 6: %75, 7: %85, 8: %95,
        # 8'den sonrası zaten base: %100 karanlık.
        rings = [
            (8, 0.95),
            (7, 0.85),
            (6, 0.75),
            (5, 0.00),
        ]

        # Dıştan içe doğru çiz (daha içteki değerler üstüne yazar)
        for radius_tiles, darkness_ratio in rings:
            alpha = int(max(0.0, min(1.0, darkness_ratio)) * 255)
            r_px = int(radius_tiles * TILE)
            pygame.draw.circle(darkness, (0, 0, 0, alpha), (px, py), r_px)

        # Katmanı en üste bas
        self.screen.blit(darkness, (0, 0))
