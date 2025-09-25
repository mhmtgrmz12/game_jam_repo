import random, pygame
from config import TILE, FLOOR, WALL, BUSH, DOOR, EXIT, CRATE, TIGER_SPAWN, SPAWN
from utils import grid_to_px

# HIDE desteğini opsiyonel yap (config'te yoksa hata vermesin)
try:
    from config import HIDE
    HAVE_HIDE = True
except Exception:
    HIDE = None
    HAVE_HIDE = False


class TileMap:
    def __init__(self, w_tiles, h_tiles, theme, kind="overworld"):
        self.w_tiles = w_tiles
        self.h_tiles = h_tiles
        self.theme = theme
        self.kind = kind
        self.grid = [[FLOOR for _ in range(w_tiles)] for __ in range(h_tiles)]
        self.doors = []           # overworld: entrances to warehouses
        self.exit_pos = None      # overworld exit
        self.tiger_positions = [] # indoor: tiger positions (grid)
        self.spawn_points = []    # hunter spawns (both worlds)
        self.generate()

    def generate(self):
        if self.kind == "overworld":
            self._gen_overworld()
        else:
            self._gen_warehouse_maze_two_wide()

    # ------------------ OVERWORLD ------------------
    def _gen_overworld(self):
        for y in range(self.h_tiles):
            for x in range(self.w_tiles):
                if x in (0, self.w_tiles-1) or y in (0, self.h_tiles-1):
                    self.grid[y][x] = WALL
                else:
                    r = random.random()
                    if r < 0.05:   self.grid[y][x]=WALL
                    elif r < 0.11: self.grid[y][x]=BUSH
                    else:          self.grid[y][x]=FLOOR
        # Doors (warehouses)
        door_count = random.randint(2,3)
        placed = 0
        while placed < door_count:
            x = random.randint(3, self.w_tiles-4)
            y = random.randint(3, self.h_tiles-4)
            if self.grid[y][x] == FLOOR:
                self.grid[y][x] = DOOR
                self.doors.append((x,y))
                placed += 1
        # Exit
        for _ in range(1000):
            ex = random.randint(2, self.w_tiles-3)
            ey = random.randint(2, self.h_tiles-3)
            if self.grid[ey][ex] == FLOOR:
                self.grid[ey][ex]=EXIT
                self.exit_pos = (ex,ey)
                break
        # Outdoor hunter spawns
        for _ in range(10):
            sx = random.randint(2, self.w_tiles-3)
            sy = random.randint(2, self.h_tiles-3)
            if self.grid[sy][sx] == FLOOR:
                self.grid[sy][sx]=SPAWN
                self.spawn_points.append((sx,sy))

    # ------------------ WAREHOUSE (maze → widen to 2 tiles) ------------------
    def _gen_warehouse_maze_two_wide(self):
        """
        1) odd koordinatlarda klasik DFS ile tek genişlikte labirent üret.
        2) Yolu genişlet (dilate) ederek 2 tile genişliğe çıkar.
        3) İçerik: CRATE, HIDE (opsiyonel), TIGER, SPAWN.
        """
        w, h = self.w_tiles, self.h_tiles

        # 1) Tümü duvarla başla
        self.grid = [[WALL for _ in range(w)] for __ in range(h)]

        # Odd grid boyutlarını güvenceye al
        if w < 7: w = 7
        if h < 7: h = 7

        # Odd koordinatları "düğümler" gibi düşün (1,1), (1,3), ... (w-2,h-2)
        def neighbors_odd(cx, cy):
            for dx,dy in ((2,0),(-2,0),(0,2),(0,-2)):
                nx, ny = cx+dx, cy+dy
                if 1 <= nx < self.w_tiles-1 and 1 <= ny < self.h_tiles-1:
                    yield nx, ny

        # DFS
        start = (1,1)
        stack = [start]
        visited = {start}
        # Başlangıç hücreyi ve yolunu aç
        self.grid[1][1] = FLOOR

        while stack:
            cx, cy = stack[-1]
            nbrs = [n for n in neighbors_odd(cx,cy) if n not in visited]
            random.shuffle(nbrs)
            if not nbrs:
                stack.pop()
                continue
            nx, ny = nbrs.pop()
            visited.add((nx,ny))
            # aradaki duvar (midpoint)
            mx, my = (cx+nx)//2, (cy+ny)//2
            self.grid[my][mx] = FLOOR
            self.grid[ny][nx] = FLOOR
            stack.append((nx,ny))

        # 2) YOL GENİŞLETME: mevcut FLOOR'ların 4-neighborhood'ını da FLOOR yap (dilate 1)
        to_floor = []
        for y in range(1, self.h_tiles-1):
            for x in range(1, self.w_tiles-1):
                if self.grid[y][x] == FLOOR:
                    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx, ny = x+dx, y+dy
                        if self.grid[ny][nx] == WALL:
                            to_floor.append((nx,ny))
        for (x,y) in to_floor:
            self.grid[y][x] = FLOOR

        # İç giriş bölgesini güvenli yap (1..3 arası açık)
        for yy in range(1, min(h, 4)):
            for xx in range(1, min(w, 4)):
                self.grid[yy][xx] = FLOOR

        # 3) İçerik serpiştir
        # CRATE (engeller)
        area = self.w_tiles * self.h_tiles
        for _ in range(area // 90):
            x = random.randint(2, self.w_tiles-3)
            y = random.randint(2, self.h_tiles-3)
            if self.grid[y][x] == FLOOR:
                self.grid[y][x] = CRATE

        # HIDE barınakları (opsiyonel)
        if HAVE_HIDE:
            target_hides = max(2, area // 500)
            placed = 0
            tries = 0
            while placed < target_hides and tries < 2000:
                tries += 1
                x = random.randint(3, self.w_tiles-4)
                y = random.randint(3, self.h_tiles-4)
                if self.grid[y][x] != FLOOR:
                    continue
                # girişe çok yakın olmasın
                if x < 6 and y < 6:
                    continue
                # çevresi biraz açık olsun (tıkamasın)
                ok = True
                for yy in range(y-1, y+2):
                    for xx in range(x-1, x+2):
                        if self.grid[yy][xx] in (CRATE,):
                            ok = False; break
                    if not ok: break
                if not ok: continue
                self.grid[y][x] = HIDE
                placed += 1

        # Kaplanlar (1–2)
        self.tiger_positions = []
        t_count = random.randint(1, 2)
        attempts = 0
        while len(self.tiger_positions) < t_count and attempts < 2000:
            attempts += 1
            x = random.randint(2, self.w_tiles-3)
            y = random.randint(2, self.h_tiles-3)
            if self.grid[y][x] == FLOOR:
                self.grid[y][x] = TIGER_SPAWN
                self.tiger_positions.append((x, y))

        # Avcı spawn noktaları (6 adet kadar)
        self.spawn_points = []
        s_goal = 6
        tries = 0
        while len(self.spawn_points) < s_goal and tries < 3000:
            tries += 1
            x = random.randint(2, self.w_tiles-3)
            y = random.randint(2, self.h_tiles-3)
            if self.grid[y][x] == FLOOR:
                self.grid[y][x] = SPAWN
                self.spawn_points.append((x, y))

    # ------------------ DRAW ------------------
    def draw(self, surf, cam, colors):
        from config import SCREEN_W, SCREEN_H
        left = int(cam.offset.x//TILE)-2
        top  = int(cam.offset.y//TILE)-2
        right= left + SCREEN_W//TILE + 4
        bottom=top + SCREEN_H//TILE + 4

        for gy in range(max(0,top), min(self.h_tiles,bottom)):
            for gx in range(max(0,left), min(self.w_tiles,right)):
                tid = self.grid[gy][gx]
                rr = pygame.Rect(gx*TILE, gy*TILE, TILE, TILE).move(-cam.offset.x, -cam.offset.y)
                if   tid==FLOOR: pygame.draw.rect(surf, colors["floor"], rr)
                elif tid==WALL:  pygame.draw.rect(surf, colors["wall"], rr)
                elif tid==BUSH:  pygame.draw.rect(surf, colors["bush"], rr)
                elif tid==CRATE: pygame.draw.rect(surf, colors["crate"], rr)
                elif tid==DOOR:  pygame.draw.rect(surf, colors["door"], rr)
                elif tid==EXIT:  pygame.draw.rect(surf, colors["exit"], rr)
                elif HAVE_HIDE and tid==HIDE:
                    pygame.draw.rect(surf, colors.get("hide", colors["crate"]), rr)
                elif tid in (TIGER_SPAWN, SPAWN):
                    pygame.draw.rect(surf, colors["floor"], rr)
