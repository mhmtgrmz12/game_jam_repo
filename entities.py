import math, random, heapq, pygame
from utils import clamp, px_to_grid, grid_to_px, line_of_sight
from config import TILE, FLOOR, WALL, CRATE, BUSH, HIDE, TIGER_SPAWN, SPAWN

# ---------------- Grid helpers ----------------
PASSABLE = {FLOOR, BUSH, HIDE, TIGER_SPAWN, SPAWN}  # yürünebilir karo tipleri

def is_passable(grid, gx, gy):
    if gy < 0 or gy >= len(grid) or gx < 0 or gx >= len(grid[0]):
        return False
    return grid[gy][gx] in PASSABLE

def neighbors4(grid, node):
    x,y = node
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx,ny = x+dx, y+dy
        if is_passable(grid, nx, ny):
            yield (nx,ny)

def manhattan(a,b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def a_star(grid, start, goal, max_expand=2500):
    """Basit ve hızlı A*; yol yoksa None döner."""
    if start == goal:
        return [start]
    openh=[]; heapq.heappush(openh, (manhattan(start,goal), 0, start, None))
    came={}; gscore={start:0}
    expanded=0
    while openh and expanded<max_expand:
        _, g, node, parent = heapq.heappop(openh)
        if node in came:
            continue
        came[node]=parent
        if node==goal: break
        expanded+=1
        for nb in neighbors4(grid, node):
            ng=g+1
            if nb not in gscore or ng<gscore[nb]:
                gscore[nb]=ng
                f=ng+manhattan(nb,goal)
                heapq.heappush(openh,(f,ng,nb,node))
    if goal not in came:
        return None
    # reconstruct
    path=[]; cur=goal
    while cur is not None:
        path.append(cur); cur=came[cur]
    path.reverse()
    return path

def grid_center(gx, gy):
    return pygame.Vector2(gx*TILE + TILE//2, gy*TILE + TILE//2)

def vec_to_card(v):
    if abs(v.x)>=abs(v.y):
        return pygame.Vector2(1 if v.x>=0 else -1, 0)
    else:
        return pygame.Vector2(0, 1 if v.y>=0 else -1)

# ---------------- Player ----------------
class Player:
    def __init__(self, x, y, speed=210):
        self.pos = pygame.Vector2(x,y)
        self.radius = 12
        self.speed = speed
        self.hiding = False  # game.py H tuşu ile toggleyebilir

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
        self._clamp_to_grid(grid)

    def _move_axis(self, dx, dy, grid):
        nx = self.pos.x + dx
        ny = self.pos.y + dy
        gx,gy = px_to_grid(nx, ny)
        # duvar/CRATE'e çarpma kontrolü (yakındaki karolar)
        rng = range(-2,3)
        for oy in rng:
            for ox in rng:
                tx,ty = gx+ox, gy+oy
                if 0<=ty<len(grid) and 0<=tx<len(grid[0]) and grid[ty][tx] in (WALL, CRATE):
                    r = pygame.Rect(tx*TILE, ty*TILE, TILE, TILE)
                    if r.collidepoint(nx, self.pos.y):
                        if dx>0: nx = r.left - 0.1
                        elif dx<0: nx = r.right + 0.1
                    if r.collidepoint(self.pos.x, ny):
                        if dy>0: ny = r.top - 0.1
                        elif dy<0: ny = r.bottom + 0.1
        self.pos.x, self.pos.y = nx, ny

    def _clamp_to_grid(self, grid):
        self.pos.x = clamp(self.pos.x, TILE, (len(grid[0])-1)*TILE)
        self.pos.y = clamp(self.pos.y, TILE, (len(grid)-1)*TILE)

    def draw(self, surf, cam, color):
        p = cam.to_screen(self.pos)
        pygame.draw.circle(surf, color, (int(p.x), int(p.y)), self.radius)

# ---------------- Hunter with A* Patrol & Chase ----------------
class Hunter:
    def __init__(self, x, y, outdoor=True):
        self.pos = pygame.Vector2(x,y)
        self.radius = 12
        self.outdoor = outdoor

        # hızlar
        self.speed_patrol = 120 if outdoor else 110
        self.speed_chase  = 200 if outdoor else 180

        # görüş
        self.fov_deg   = 75 if outdoor else 60
        self.view_dist = 9*TILE if outdoor else 7*TILE
        self.cos_fov = math.cos(math.radians(self.fov_deg/2))
        self.vision_tick = 0.0

        # durum
        self.state = "patrol"  # patrol/search/chase
        self.dir = pygame.Vector2(1,0)
        self.search_timer = 0.0

        # PATROL için A* rota
        self.patrol_goal = None      # grid (gx,gy)
        self.patrol_path = None      # grid listesi
        self.patrol_i = 0
        self.patrol_repath_cd = 0.0
        self.patrol_pick_cd = 0.0

        # CHASE için A* rota
        self.path = None
        self.path_i = 0
        self.repath_cd = 0.0

        # anti-stuck
        self._last_pos = self.pos.copy()
        self._stuck_t = 0.0

    # ---------- public update ----------
    def update(self, dt, grid, player, stealth_factor):
        # HIDE üzerinde mi?
        pgx, pgy = px_to_grid(player.pos.x, player.pos.y)
        player_on_hide = (0 <= pgy < len(grid) and 0 <= pgx < len(grid[0]) and grid[pgy][pgx] == HIDE)

        # Görüş (HIDE'da kapalı)
        seen = False
        self.vision_tick -= dt
        if self.vision_tick <= 0:
            self.vision_tick = 0.08
            if not player_on_hide:
                to_p = player.pos - self.pos
                dist = to_p.length()
                if dist < self.view_dist:
                    fwd = self.dir if self.dir.length_squared()>0 else pygame.Vector2(1,0)
                    fwd = fwd.normalize()
                    u = to_p.normalize() if dist>0 else pygame.Vector2()
                    if fwd.dot(u) > self.cos_fov:
                        eff_view = self.view_dist * (1.0 - 0.55*stealth_factor)
                        if dist < eff_view and line_of_sight(grid, self.pos, player.pos):
                            seen = True

        # Durum değişimi (kovalamayı bırakma koşulları dahil)
        if seen:
            self.state = "chase"
            self.repath_cd = 0.0  # hemen rota çıkarabilir
            self.search_timer = 2.0
        else:
            # HIDE'taysan anında bırak
            if player_on_hide and self.state == "chase":
                self.state = "search"
                self.search_timer = 1.25

        # Güncellemeler
        if self.state == "chase":
            self._update_chase(dt, grid, player, player_on_hide)
            # 6 karo uzaklığa çıkarsa kovalamayı bırak
            s = px_to_grid(self.pos.x, self.pos.y)
            g = px_to_grid(player.pos.x, player.pos.y)
            if manhattan(s, g) > 6:
                self.state = "search"
                self.search_timer = 1.0
                self.path = None
        elif self.state == "search":
            # patrol gibi dolan ama biraz yavaş, kısa süre sonra patrol
            self._update_patrol(dt, grid, speed_scale=0.9, range_cells=10)
            self.search_timer -= dt
            if self.search_timer <= 0:
                self.state = "patrol"
        else:
            # normal devriye — A* ile hedefe git
            self._update_patrol(dt, grid, speed_scale=1.0, range_cells=14)

        # HIDE üstünde üst üste binmeyi hafif iterek engelle
        if player_on_hide:
            diff = self.pos - player.pos
            if diff.length() < (self.radius + player.radius + 2):
                push = diff.normalize() if diff.length() else pygame.Vector2(1,0)
                self.pos += push * 60 * dt

        # sınır kelepçesi
        self._clamp_to_grid(grid)

        # stuck algılama → rota & hedef yenile
        if (self.pos - self._last_pos).length() < 0.8:
            self._stuck_t += dt
        else:
            self._stuck_t = 0.0
        self._last_pos.update(self.pos)
        if self._stuck_t > 0.8:
            self._stuck_t = 0.0
            if self.state == "chase":
                self.path = None
            else:
                self.patrol_path = None
                self.patrol_pick_cd = 0.0
                self.patrol_repath_cd = 0.0

    # ---------- PATROL: A* ile doğal dolaşma ----------
    def _update_patrol(self, dt, grid, speed_scale=1.0, range_cells=12):
        self.patrol_repath_cd -= dt
        self.patrol_pick_cd   -= dt

        s = px_to_grid(self.pos.x, self.pos.y)

        # Hedef yoksa/ulaşıldıysa yeni hedef seç
        need_goal = (self.patrol_goal is None or self.patrol_path is None or self.patrol_i >= len(self.patrol_path))
        if need_goal and self.patrol_pick_cd <= 0:
            self.patrol_goal = self._pick_patrol_goal(grid, s, range_cells)
            self.patrol_path = None
            self.patrol_i = 0
            self.patrol_pick_cd = 0.3  # çok sık hedef seçme

        # Rota yoksa ya da süresi dolduysa üret
        if self.patrol_goal and (self.patrol_path is None or self.patrol_repath_cd <= 0):
            p = a_star(grid, s, self.patrol_goal)
            if p and len(p) >= 2:
                self.patrol_path = p
                self.patrol_i = 1
                self.patrol_repath_cd = 0.6
            else:
                # seçilen hedefe yol yoksa yeni hedef seç
                self.patrol_goal = None
                self.patrol_path = None
                self.patrol_i = 0
                return

        # Rotayı takip et
        speed = self.speed_patrol * speed_scale * dt
        if self.patrol_path:
            tgt_g = self.patrol_path[self.patrol_i]
            tgt_c = grid_center(*tgt_g)
            to_t = tgt_c - self.pos
            if to_t.length() < 2.0:
                if self.patrol_i < len(self.patrol_path)-1:
                    self.patrol_i += 1
                    tgt_g = self.patrol_path[self.patrol_i]
                    tgt_c = grid_center(*tgt_g)
                    to_t = tgt_c - self.pos
                else:
                    # hedefe varıldı → yeni hedefe geç
                    self.patrol_goal = None
                    self.patrol_path = None
                    self.patrol_i = 0
                    return
            if to_t.length() > 0:
                self.dir = vec_to_card(to_t)
                self._step_axis(speed, grid, self.dir)

    def _pick_patrol_goal(self, grid, s, R):
        """s etrafında R yarıçapında rastgele yürünebilir bir hedef seç."""
        W = len(grid[0]); H = len(grid)
        sx, sy = s
        for _ in range(60):
            gx = max(1, min(W-2, sx + random.randint(-R, R)))
            gy = max(1, min(H-2, sy + random.randint(-R, R)))
            if is_passable(grid, gx, gy) and manhattan((sx,sy),(gx,gy)) >= 4:
                return (gx,gy)
        # fallback: en yakın açık komşu
        for nb in neighbors4(grid, s):
            return nb
        return s

    # ---------- CHASE: A* + kaçırma koşulları ----------
    def _update_chase(self, dt, grid, player, player_on_hide):
        # çok yakında ve HIDE ise geri çekil
        d = player.pos - self.pos
        if player_on_hide and d.length() < (self.radius + player.radius + 10):
            self.dir = -vec_to_card(self.dir)
            self._step_axis(self.speed_patrol*dt, grid, self.dir)
            return

        s = px_to_grid(self.pos.x, self.pos.y)
        g = px_to_grid(player.pos.x, player.pos.y)

        # path yenileme
        self.repath_cd -= dt
        if self.path is None or self.path_i >= len(self.path) or self.repath_cd <= 0:
            p = a_star(grid, s, g)
            if p and len(p) >= 2:
                self.path = p
                self.path_i = 1
                self.repath_cd = 0.35
            else:
                self.path = None

        speed = self.speed_chase * dt
        moved=False
        if self.path:
            tgt_g = self.path[self.path_i]
            tgt_c = grid_center(*tgt_g)
            to_t = tgt_c - self.pos
            if to_t.length() < 2.0:
                if self.path_i < len(self.path)-1:
                    self.path_i += 1
                    tgt_g = self.path[self.path_i]
                    tgt_c = grid_center(*tgt_g)
                    to_t = tgt_c - self.pos
            if to_t.length() > 0:
                self.dir = vec_to_card(to_t)
                moved = self._step_axis(speed, grid, self.dir)
        if not moved:
            # fallback küçük kardinal adım
            dx = 1 if d.x>0 else -1
            dy = 1 if d.y>0 else -1
            primary_h = abs(d.x) >= abs(d.y)
            if primary_h:
                if not self._step_axis(speed, grid, pygame.Vector2(dx,0)):
                    if not self._step_axis(speed, grid, pygame.Vector2(0,dy)):
                        self._step_axis(speed, grid, pygame.Vector2(-dx,0))
            else:
                if not self._step_axis(speed, grid, pygame.Vector2(0,dy)):
                    if not self._step_axis(speed, grid, pygame.Vector2(dx,0)):
                        self._step_axis(speed, grid, pygame.Vector2(0,-dy))

    # ---------- Movement & Collisions ----------
    def _step_axis(self, step_len, grid, dirv):
        """Eksen ayrık hareket; duvara çarpmadan önce frenler."""
        start = self.pos.copy()
        step = dirv * step_len

        # X
        nx = self.pos.x + step.x
        ny = self.pos.y
        nx, ny = self._solve_axis(nx, ny, step.x, 0, grid)
        # Y
        ny = ny + step.y
        nx, ny = self._solve_axis(nx, ny, 0, step.y, grid)

        self.pos.x, self.pos.y = nx, ny
        self._clamp_to_grid(grid)
        return (self.pos - start).length() > 0.1

    def _solve_axis(self, newx, newy, dx, dy, grid):
        x,y = newx, newy
        gx, gy = px_to_grid(x, y)
        rng = range(-2,3)
        for oy in rng:
            for ox in rng:
                tx,ty = gx+ox, gy+oy
                if 0<=ty<len(grid) and 0<=tx<len(grid[0]) and grid[ty][tx] in (WALL, CRATE):
                    r = pygame.Rect(tx*TILE, ty*TILE, TILE, TILE)
                    # önden “frenleme” (duvara girmeden önce dur)
                    if r.collidepoint(x, self.pos.y):
                        if dx>0: x = min(x, r.left - 0.1)
                        elif dx<0: x = max(x, r.right + 0.1)
                    if r.collidepoint(self.pos.x, y):
                        if dy>0: y = min(y, r.top - 0.1)
                        elif dy<0: y = max(y, r.bottom + 0.1)
        return x,y

    def _clamp_to_grid(self, grid):
        self.pos.x = clamp(self.pos.x, TILE, (len(grid[0])-1)*TILE)
        self.pos.y = clamp(self.pos.y, TILE, (len(grid)-1)*TILE)

    # ---------- Draw ----------
    def draw(self, surf, cam, colors, show_fov=False):
        p = cam.to_screen(self.pos)
        pygame.draw.circle(surf, colors["hunter"], (int(p.x), int(p.y)), self.radius)
        if show_fov:
            pygame.draw.circle(surf, colors["fov"], (int(p.x), int(p.y)), int(self.view_dist), 1)
