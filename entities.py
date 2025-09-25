import math, random, pygame
from utils import clamp, px_to_grid, grid_to_px, line_of_sight
from config import TILE, FLOOR, WALL, CRATE, BUSH, HIDE

class Player:
    def __init__(self, x, y, speed=210):
        self.pos = pygame.Vector2(x,y)
        self.radius = 12
        self.speed = speed
        self.hiding = False  # H tuşu ile kullanıyorsan game.py yönetiyor

    def move(self, dt, grid):
        if self.hiding:
            return
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

        # Görüş optimizasyonu
        self.cos_fov = math.cos(math.radians(self.fov_deg/2))
        self.vision_tick = 0.0

        # Takılma önleme
        self._last_pos = self.pos.copy()
        self._stuck_time = 0.0      # ne kadar süredir yer değiştirmedi
        self._repath_cool = 0.0

    def update(self, dt, grid, player, stealth_factor):
        # Oyuncu HIDE üzerinde mi?
        pgx, pgy = px_to_grid(player.pos.x, player.pos.y)
        player_on_hide = (0 <= pgy < len(grid) and 0 <= pgx < len(grid[0]) and grid[pgy][pgx] == HIDE)

        # --- Görüş (HIDE üzerindeyken kapalı) ---
        seen = False
        self.vision_tick -= dt
        if self.vision_tick <= 0:
            self.vision_tick = 0.06
            if not player_on_hide:
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
        else:
            if player_on_hide and self.state == "chase":
                self.state = "search"
                self.search_timer = 1.5

        moved = False

        if self.state == "chase":
            d = (player.pos - self.pos)
            if d.length():
                self.dir = d.normalize()
                step = self.dir * self.speed_chase * dt

                # HIDE yakınında geri dön
                if player_on_hide and d.length() < (self.radius + player.radius + 6):
                    away = (self.pos - player.pos)
                    if away.length():
                        step = away.normalize() * self.speed_patrol * dt * 1.2
                    self.state = "search"
                    self.search_timer = 1.2

                moved = self._move_smart(step, grid)

            self.search_timer -= dt
            if self.search_timer <= 0:
                self.state = "search"
                self.search_timer = 1.5

        elif self.state == "search":
            moved = self._patrol(dt, grid, scale=0.7)
            self.search_timer -= dt
            if self.search_timer <= 0:
                self.state = "patrol"

        else:  # patrol
            moved = self._patrol(dt, grid)

        # HIDE üstünde çakışma varsa hafif it
        if player_on_hide:
            diff = self.pos - player.pos
            if diff.length() < (self.radius + player.radius + 2):
                push = diff.normalize() if diff.length() else pygame.Vector2(1,0)
                self.pos += push * 40 * dt
                moved = True

        # --- Stuck algılama ---
        if (self.pos - self._last_pos).length() < 2.0:
            self._stuck_time += dt
        else:
            self._stuck_time = 0.0
        self._last_pos.update(self.pos)

        # Uzun süre hareket yoksa hedef ve yönü yenile
        if self._stuck_time > 0.6:
            self._stuck_time = 0.0
            self.patrol_target = None
            # rastgele bir yöne bak
            ang = random.uniform(0, 2*math.pi)
            self.dir = pygame.Vector2(math.cos(ang), math.sin(ang))

    # ---------------- movement helpers ----------------
    def _patrol(self, dt, grid, scale=1.0):
        # Hedef yoksa veya çok yakında ise yeni hedef üret
        if (not self.patrol_target) or (self.patrol_target - self.pos).length() < 10 or self._repath_cool > 0.0:
            if self._repath_cool > 0.0:
                self._repath_cool = max(0.0, self._repath_cool - dt)
            gx, gy = px_to_grid(self.pos.x, self.pos.y)
            for _ in range(40):
                rx = max(2, min(len(grid[0])-3, gx + random.randint(-6,6)))
                ry = max(2, min(len(grid)-3, gy + random.randint(-6,6)))
                if grid[int(ry)][int(rx)] != WALL and grid[int(ry)][int(rx)] != CRATE:
                    self.patrol_target = pygame.Vector2(rx*TILE+TILE//2, ry*TILE+TILE//2)
                    break

        moved = False
        if self.patrol_target:
            d = self.patrol_target - self.pos
            if d.length():
                self.dir = d.normalize()
                step = self.dir * self.speed_patrol * dt * scale
                moved = self._move_smart(step, grid)
                # Hedefe gidiş engellendiyse kısa süre sonra yeni hedef seç
                if not moved:
                    self._repath_cool = 0.2
        return moved

    def _move_smart(self, step, grid):
        """Eksen bazlı çarpışma + kayma + jitter. True dönerse anlamlı hareket var."""
        start = self.pos.copy()

        # 1) önce X sonra Y
        nx = self.pos.x + step.x
        ny = self.pos.y
        nx = self._solve_axis_collision(nx, self.pos.y, step.x, 0, grid)
        ny = self.pos.y + step.y
        ny = self._solve_axis_collision(nx, ny, 0, step.y, grid)
        self.pos.x, self.pos.y = nx, ny

        moved = (self.pos - start).length() > 0.5
        if moved:
            return True

        # 2) kayma denemesi (duvara paralel)
        # step'i dik yönde deneriz
        if abs(step.x) > abs(step.y):
            # X tıkalıysa Y yönünde hafif kay
            slip = pygame.Vector2(0, math.copysign(1, step.x)) * (abs(step.x) * 0.5)
        else:
            slip = pygame.Vector2(math.copysign(1, step.y), 0) * (abs(step.y) * 0.5)
        nx2 = start.x + slip.x
        ny2 = start.y
        nx2 = self._solve_axis_collision(nx2, ny2, slip.x, 0, grid)
        ny2 = start.y + slip.y
        ny2 = self._solve_axis_collision(nx2, ny2, 0, slip.y, grid)
        if (pygame.Vector2(nx2, ny2) - start).length() > 0.5:
            self.pos.x, self.pos.y = nx2, ny2
            return True

        # 3) küçük jitter (rastgele çok küçük adım)
        ang = random.uniform(0, 2*math.pi)
        jitter = pygame.Vector2(math.cos(ang), math.sin(ang)) * 8
        nx3 = start.x + jitter.x
        ny3 = start.y
        nx3 = self._solve_axis_collision(nx3, ny3, jitter.x, 0, grid)
        ny3 = start.y + jitter.y
        ny3 = self._solve_axis_collision(nx3, ny3, 0, jitter.y, grid)
        if (pygame.Vector2(nx3, ny3) - start).length() > 0.5:
            self.pos.x, self.pos.y = nx3, ny3
            return True

        return False

    def _solve_axis_collision(self, newx, newy, dx, dy, grid):
        """Tek eksen çarpışma çözümü: duvar/CRATE'te dur, HIDE/FLOOR geç."""
        x, y = newx, newy
        for ox, oy in self._nearby_tiles():
            if 0<=oy<len(grid) and 0<=ox<len(grid[0]):
                t = grid[oy][ox]
                if t in (WALL, CRATE):
                    tile_rect = pygame.Rect(ox*TILE, oy*TILE, TILE, TILE)
                    if tile_rect.collidepoint(x, self.pos.y):
                        if dx>0: x = tile_rect.left - 0.1
                        elif dx<0: x = tile_rect.right + 0.1
                    if tile_rect.collidepoint(self.pos.x, y):
                        if dy>0: y = tile_rect.top - 0.1
                        elif dy<0: y = tile_rect.bottom + 0.1
        return x if dy==0 else y

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
