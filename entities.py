import math, random, pygame
from utils import clamp, px_to_grid, grid_to_px, line_of_sight
from config import TILE, FLOOR, WALL, CRATE, BUSH

class Player:
    def __init__(self, x, y, speed=210):
        self.pos = pygame.Vector2(x,y)
        self.radius = 12
        self.speed = speed
        self.hiding = False   # YENİ: barınağa girip saklanma durumu

    def move(self, dt, grid):
        if self.hiding:
            return

    def move(self, dt, grid):
        keys = pygame.key.get_pressed()
        v = pygame.Vector2(0,0)
        if keys[pygame.K_w]: v.y -= 1
        if keys[pygame.K_s]: v.y += 1
        if keys[pygame.K_a]: v.x -= 1
        if keys[pygame.K_d]: v.x += 1
        if v.length_squared(): v = v.normalize() * self.speed * dt
        self._move_axis(v.x, 0, grid)
        self._move_axis(0, v.y, grid)

    def _move_axis(self, dx, dy, grid):
        newx = self.pos.x + dx
        newy = self.pos.y + dy
        for ox, oy in self._nearby_tiles():
            if 0<=oy<len(grid) and 0<=ox<len(grid[0]):
                t = grid[oy][ox]
                if t in (WALL, CRATE):
                    tile_rect = pygame.Rect(ox*TILE, oy*TILE, TILE, TILE)
                    if tile_rect.collidepoint(newx, self.pos.y):
                        if dx>0: newx = tile_rect.left - 0.1
                        elif dx<0: newx = tile_rect.right + 0.1
                    if tile_rect.collidepoint(self.pos.x, newy):
                        if dy>0: newy = tile_rect.top - 0.1
                        elif dy<0: newy = tile_rect.bottom + 0.1
        self.pos.x = newx; self.pos.y = newy
        self.pos.x = clamp(self.pos.x, TILE, (len(grid[0])-1)*TILE)
        self.pos.y = clamp(self.pos.y, TILE, (len(grid)-1)*TILE)

    def _nearby_tiles(self):
        gx, gy = px_to_grid(self.pos.x, self.pos.y)
        for dy in (-1,0,1,2,-2):
            for dx in (-1,0,1,2,-2):
                yield gx+dx, gy+dy

    def draw(self, surf, cam, color):
        p = cam.to_screen(self.pos)
        pygame.draw.circle(surf, color, (int(p.x), int(p.y)), self.radius)

class Hunter:
    def __init__(self, x, y, outdoor=True):
        self.pos = pygame.Vector2(x,y)
        self.radius = 12
        self.state = "patrol"
        self.dir = pygame.Vector2(1,0)
        self.patrol_target = None
        self.outdoor = outdoor
        self.speed_patrol = 120 if outdoor else 100
        self.speed_chase  = 200 if outdoor else 170
        self.fov_deg   = 70 if outdoor else 60
        self.view_dist = 9*TILE if outdoor else 7*TILE
        self.search_timer = 0.0

        # perf: vision debounce & cos-threshold
        self.cos_fov = math.cos(math.radians(self.fov_deg/2))
        self.vision_tick = 0.0

    def update(self, dt, grid, player, stealth_factor):
        seen = False
        # Debounced vision checks (every ~0.06s)
        self.vision_tick -= dt
        if self.vision_tick <= 0:
            self.vision_tick = 0.06
            to_player = (player.pos - self.pos)
            dist = to_player.length()
            if dist < self.view_dist:
                v = self.dir if self.dir.length_squared()>0 else pygame.Vector2(1,0)
                v = v.normalize()
                u = to_player.normalize() if dist>0 else pygame.Vector2()
                cosang = v.x*u.x + v.y*u.y
                effective_view = self.view_dist * (1.0 - 0.6*stealth_factor)
                if cosang > self.cos_fov and dist < effective_view:
                    if line_of_sight(grid, self.pos, player.pos):
                        seen = True

        if seen:
            self.state = "chase"
            self.search_timer = 2.0

        if self.state == "chase":
            d = (player.pos - self.pos)
            if d.length():
                self.dir = d.normalize()
                step = self.dir * self.speed_chase * dt
                self._move_with_collisions(step, grid)
            self.search_timer -= dt
            if self.search_timer <= 0:
                self.state = "search"
                self.search_timer = 1.5

        elif self.state == "search":
            self._patrol(dt, grid, scale=0.6)
            self.search_timer -= dt
            if self.search_timer <= 0:
                self.state = "patrol"
        else:
            self._patrol(dt, grid)

    def _patrol(self, dt, grid, scale=1.0):
        if not self.patrol_target or (self.patrol_target - self.pos).length() < 8:
            gx, gy = px_to_grid(self.pos.x, self.pos.y)
            for _ in range(30):
                rx = max(2, min(len(grid[0])-3, gx + random.randint(-6,6)))
                ry = max(2, min(len(grid)-3, gy + random.randint(-6,6)))
                if grid[int(ry)][int(rx)] != 1:  # not WALL
                    self.patrol_target = pygame.Vector2(rx*TILE+TILE//2, ry*TILE+TILE//2)
                    break
        if self.patrol_target:
            d = self.patrol_target - self.pos
            if d.length():
                step = d.normalize() * self.speed_patrol * dt * scale
                self._move_with_collisions(step, grid)

    def _move_with_collisions(self, step, grid):
        nx = self.pos.x + step.x; ny = self.pos.y + step.y
        for ox, oy in self._nearby_tiles():
            if 0<=oy<len(grid) and 0<=ox<len(grid[0]):
                t = grid[oy][ox]
                if t in (WALL, CRATE):
                    tile_rect = pygame.Rect(ox*TILE, oy*TILE, TILE, TILE)
                    if tile_rect.collidepoint(nx, self.pos.y):
                        if step.x>0: nx = tile_rect.left - 0.1
                        elif step.x<0: nx = tile_rect.right + 0.1
                    if tile_rect.collidepoint(self.pos.x, ny):
                        if step.y>0: ny = tile_rect.top - 0.1
                        elif step.y<0: ny = tile_rect.bottom + 0.1
        self.pos.x = nx; self.pos.y = ny

    def _nearby_tiles(self):
        gx, gy = px_to_grid(self.pos.x, self.pos.y)
        for dy in (-1,0,1,2,-2):
            for dx in (-1,0,1,2,-2):
                yield gx+dx, gy+dy

    def draw(self, surf, cam, colors, show_fov=False):
        p = cam.to_screen(self.pos)
        pygame.draw.circle(surf, colors["hunter"], (int(p.x), int(p.y)), self.radius)
        if show_fov:
            pygame.draw.circle(surf, colors["fov"], (int(p.x), int(p.y)), int(self.view_dist), 1)
