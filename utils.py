import json, pygame, math
from config import TILE, FLOOR, WALL, CRATE

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def clamp(v, a, b): return max(a, min(b, v))

def grid_to_px(gx, gy): return gx * TILE + TILE//2, gy * TILE + TILE//2
def px_to_grid(x, y): return int(x//TILE), int(y//TILE)

def rect_from_grid(gx, gy): return pygame.Rect(gx*TILE, gy*TILE, TILE, TILE)

def heuristic(a,b): return abs(a[0]-b[0])+abs(a[1]-b[1])

def line_of_sight(grid, start, end):
    # Bresenham over tiles; blocks on WALL/CRATE
    x0, y0 = px_to_grid(*start); x1, y1 = px_to_grid(*end)
    dx = abs(x1-x0); dy = -abs(y1-y0)
    sx = 1 if x0<x1 else -1; sy = 1 if y0<y1 else -1
    err = dx+dy
    while True:
        if grid[y0][x0] in (WALL, CRATE):
            return False
        if x0==x1 and y0==y1: break
        e2 = 2*err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy
    return True

def astar(grid, start, goal, passables=(FLOOR,)):
    w, h = len(grid[0]), len(grid)
    pset = set(passables)
    open_set = {start}
    came = {}
    g = {start:0}
    f = {start:heuristic(start, goal)}
    while open_set:
        current = min(open_set, key=lambda n:f.get(n, 1e9))
        if current == goal:
            path = [current]
            while current in came:
                current=came[current]; path.append(current)
            path.reverse(); return path
        open_set.remove(current)
        x,y = current
        for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if 0<=nx<w and 0<=ny<h and grid[ny][nx] in pset:
                tentative = g[current]+1
                if tentative < g.get((nx,ny), 1e9):
                    came[(nx,ny)] = current
                    g[(nx,ny)] = tentative
                    f[(nx,ny)] = tentative + heuristic((nx,ny), goal)
                    open_set.add((nx,ny))
    return []
