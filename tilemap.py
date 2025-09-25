import random, pygame
from config import TILE, FLOOR, WALL, BUSH, DOOR, EXIT, TIGER_SPAWN, SPAWN, HIDE
from utils import grid_to_px

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
            self._gen_warehouse_2wide_maze_with_hides()

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
        # Spawns
        for _ in range(10):
            sx = random.randint(2, self.w_tiles-3)
            sy = random.randint(2, self.h_tiles-3)
            if self.grid[sy][sx] == FLOOR:
                self.grid[sy][sx]=SPAWN
                self.spawn_points.append((sx,sy))

    # ------------------ WAREHOUSE (exact 2-wide + HIDE) ------------------
    def _gen_warehouse_2wide_maze_with_hides(self):
        """
        Perfect maze on a cell grid, each cell carved as 2x2 FLOOR (corridors = 2 tiles wide).
        Adds small 1x1 HIDE tiles that do NOT block corridors.
        """
        W, H = self.w_tiles, self.h_tiles
        self.grid = [[WALL for _ in range(W)] for __ in range(H)]

        # Cell grid mapping: base = (1 + cx*3, 1 + cy*3), 2x2 floors, 1-thick walls
        cw = max(2, (W - 2) // 3)
        ch = max(2, (H - 2) // 3)

        def base(cx, cy):
            return 1 + cx*3, 1 + cy*3  # top-left of 2x2 block

        def carve_cell(cx, cy):
            bx, by = base(cx, cy)
            for dy in (0,1):
                for dx in (0,1):
                    x, y = bx+dx, by+dy
                    if 0 <= x < W and 0 <= y < H:
                        self.grid[y][x] = FLOOR

        # Carve all cells
        for cy in range(ch):
            for cx in range(cw):
                carve_cell(cx, cy)

        # DFS on cell graph, open 2x1 / 1x2 gates
        dirs = [(1,0),(-1,0),(0,1),(0,-1)]
        stack = [(0,0)]
        visited = {(0,0)}
        while stack:
            cx, cy = stack[-1]
            nbrs = [(cx+dx, cy+dy, dx, dy)
                    for dx,dy in dirs
                    if 0 <= cx+dx < cw and 0 <= cy+dy < ch and (cx+dx,cy+dy) not in visited]
            random.shuffle(nbrs)
            if not nbrs:
                stack.pop()
                continue
            nx, ny, dx, dy = nbrs.pop()
            bx, by   = base(cx, cy)
            nbx, nby = base(nx, ny)
            if dx == 1:   # right
                wx = bx + 2
                for t in (0,1):
                    x, y = wx, by + t
                    if 0 <= x < W and 0 <= y < H: self.grid[y][x] = FLOOR
            elif dx == -1:  # left
                wx = nbx + 2
                for t in (0,1):
                    x, y = wx, nby + t
                    if 0 <= x < W and 0 <= y < H: self.grid[y][x] = FLOOR
            elif dy == 1:  # down
                wy = by + 2
                for t in (0,1):
                    x, y = bx + t, wy
                    if 0 <= x < W and 0 <= y < H: self.grid[y][x] = FLOOR
            elif dy == -1: # up
                wy = nby + 2
                for t in (0,1):
                    x, y = nbx + t, wy
                    if 0 <= x < W and 0 <= y < H: self.grid[y][x] = FLOOR
            visited.add((nx,ny))
            stack.append((nx,ny))

        # Keep indoor entrance corner open (around (1,1))
        for yy in range(1, min(H, 4)):
            for xx in range(1, min(W, 4)):
                self.grid[yy][xx] = FLOOR

        # ---- Place HIDE tiles (single-tile shelters) ----
        # Rules: on FLOOR, not near (1,1), do not cluster, keep corridor flow.
        area = W * H
        target_hides = max(3, area // 550)
        placed = 0
        tries = 0
        while placed < target_hides and tries < 4000:
            tries += 1
            x = random.randint(3, W-4)
            y = random.randint(3, H-4)
            if self.grid[y][x] != FLOOR:
                continue
            # Not too close to indoor entry
            if x < 6 and y < 6:
                continue
            # Avoid placing next to another HIDE; avoid turning a 2-wide into a choke
            neighbor_hides = 0
            floor_neighbors = 0
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                tid = self.grid[y+dy][x+dx]
                if tid == HIDE:
                    neighbor_hides += 1
                if tid == FLOOR:
                    floor_neighbors += 1
            if neighbor_hides > 0:
                continue
            if floor_neighbors < 2:
                # likely a cul-de-sac; skip to avoid blocking feel
                continue
            self.grid[y][x] = HIDE
            placed += 1

        # Tigers (1–2) on floor
        self.tiger_positions = []
        t_goal = random.randint(1,2)
        tries = 0
        while len(self.tiger_positions) < t_goal and tries < 3000:
            tries += 1
            x = random.randint(2, W-3)
            y = random.randint(2, H-3)
            if self.grid[y][x] == FLOOR:
                self.grid[y][x] = TIGER_SPAWN
                self.tiger_positions.append((x,y))

        # Hunter spawns (6) on floor
        self.spawn_points = []
        s_goal = 6
        tries = 0
        while len(self.spawn_points) < s_goal and tries < 4000:
            tries += 1
            x = random.randint(2, W-3)
            y = random.randint(2, H-3)
            if self.grid[y][x] == FLOOR:
                self.grid[y][x] = SPAWN
                self.spawn_points.append((x,y))

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
                elif tid==DOOR:  pygame.draw.rect(surf, colors["door"], rr)
                elif tid==EXIT:  pygame.draw.rect(surf, colors["exit"], rr)
                elif tid==HIDE:  pygame.draw.rect(surf, colors.get("hide", colors["floor"]), rr)
                elif tid in (TIGER_SPAWN, SPAWN):
                    pygame.draw.rect(surf, colors["floor"], rr)
