import random, pygame
from utils import astar, grid_to_px

class Footprints:
    def __init__(self, color):
        self.points = []
        self.decoys = []
        self.color = color

    def compute_from_to(self, grid, start_g, target_g, passables):
        if not target_g: self.points=[]; self.decoys=[]; return
        path = astar(grid, start_g, target_g, passables=passables)
        self._sample_path(path)
        self._make_decoys(grid)

    def _sample_path(self, path):
        self.points=[]
        for i,(gx,gy) in enumerate(path):
            if i%2==0:
                cx, cy = grid_to_px(gx, gy)
                self.points.append((cx,cy))

    def _make_decoys(self, grid):
        self.decoys=[]
        for _ in range(8):
            gx = random.randint(2, len(grid[0])-3)
            gy = random.randint(2, len(grid)-3)
            if grid[gy][gx] in (0,2,5):  # FLOOR, BUSH, CRATE
                cx, cy = grid_to_px(gx, gy)
                self.decoys.append((cx + random.randint(-6,6), cy + random.randint(-6,6)))

    def draw(self, surf, cam):
        for (x,y) in self.points:
            p = cam.to_screen(pygame.Vector2(x,y))
            pygame.draw.circle(surf, self.color, (int(p.x), int(p.y)), 4)
        for (x,y) in self.decoys:
            p = cam.to_screen(pygame.Vector2(x,y))
            pygame.draw.circle(surf, self.color, (int(p.x), int(p.y)), 3, 1)
