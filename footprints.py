# footprints.py
import pygame
import math
from collections import deque
from config import TILE, FLOOR


class Footprints:
    """
    Mevcut oyun mimarisiyle uyumlu ayak izi yönlendirmesi.
    - compute_from_to(grid, start_g, goal_g, passables): BFS ile grid üstünde yol hesaplar.
    - draw(surf, cam): yolu kaplan patisi simgesiyle çizer (PNG varsa onu, yoksa prosedürel).
    """

    def __init__(self, color=(200, 160, 120)):
        self.color = color
        self.step_tiles = 7
        self.points: list[tuple[int, int]] = []  # grid noktaları (gx, gy)
        self._rot_cache: dict[int, pygame.Surface] = {}
        self._paw_base: pygame.Surface | None = None
        self._load_or_build_paw()

    # ---------- public API ----------
    def compute_from_to(self, grid, start_g, goal_g, passables):
        """
        grid: 2D list (grid[y][x])
        start_g, goal_g: (gx, gy)
        passables: geçilebilir tile id'leri (örn: (FLOOR, BUSH, ...))
        """
        if not goal_g or not start_g:
            self.points = []
            return

        sx, sy = start_g
        gx, gy = goal_g
        h = len(grid)
        w = len(grid[0]) if h > 0 else 0

        def in_bounds(x, y):
            return 0 <= x < w and 0 <= y < h

        def is_passable(x, y):
            return in_bounds(x, y) and (grid[y][x] in passables or (x, y) == (gx, gy))

        # Klasik BFS
        came_from = {(sx, sy): None}
        q = deque([(sx, sy)])
        found = False

        while q:
            x, y = q.popleft()
            if (x, y) == (gx, gy):
                found = True
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) not in came_from and is_passable(nx, ny):
                    came_from[(nx, ny)] = (x, y)
                    q.append((nx, ny))

        if not found:
            self.points = []
            return

        # Yol rekonstrüksiyonu
        path = []
        cur = (gx, gy)
        while cur is not None:
            path.append(cur)
            cur = came_from[cur]
        path.reverse()

        # Başlangıç karesini çizmek istemiyorsan ilkini atabilirsin:
        # if path and path[0] == (sx, sy): path = path[1:]

        self.points = path

    def draw(self, surf: pygame.Surface, cam):
        """İzleri her 7 karede bir (self.step_tiles) çizer."""
        if not self.points or self._paw_base is None:
            return

        paw = self._paw_base
        alpha = 190
        step = getattr(self, "step_tiles", 7)
        n = len(self.points)

        for i in range(0, n, step):
            gx, gy = self.points[i]

            # ekran merkezi
            px = gx * TILE + TILE // 2 - int(cam.offset.x)
            py = gy * TILE + TILE // 2 - int(cam.offset.y)

            # yön: bir SONRAKİ hedefe bak (mümkünse i+step), yoksa yakın komşu
            if i + step < n:
                nx, ny = self.points[i + step]
            elif i + 1 < n:
                nx, ny = self.points[i + 1]
            elif i - 1 >= 0:
                nx, ny = self.points[i - 1]
            else:
                nx, ny = gx, gy

            dx, dy = (nx - gx), (ny - gy)
            if dx == 0 and dy == 0:
                angle_deg = 0
            else:
                angle_deg = math.degrees(math.atan2(-dy, dx))  # sağa 0°

            img = self._get_rotated_cached(paw, angle_deg)
            img.set_alpha(alpha)
            rect = img.get_rect(center=(px, py))
            surf.blit(img, rect)

    # ---------- internal helpers ----------
    def _load_or_build_paw(self):
        """assets/paw.png varsa kullan; yoksa prosedürel patik yap."""
        size = int(TILE * 0.7)
        try:
            img = pygame.image.load("assets/images/paw.png").convert_alpha()
            self._paw_base = pygame.transform.smoothscale(img, (size, size))
        except Exception:
            self._paw_base = self._make_procedural_paw(size)

    def _get_rotated_cached(self, base: pygame.Surface, angle_deg: float) -> pygame.Surface:
        """15° adımlarına yuvarlayıp cache’ten döndür."""
        step = 15
        key = (int(round(angle_deg / step)) * step) % 360
        if key not in self._rot_cache:
            # Saat yönü pozitif olsun diye eksi veriyoruz (pygame rotate CCW)
            self._rot_cache[key] = pygame.transform.rotate(base, -key)
        return self._rot_cache[key]

    def _make_procedural_paw(self, size: int) -> pygame.Surface:
        """
        Şeffaf arkaplanlı basit bir kaplan patisi: ana yastık + 4 parmak.
        Renk: koyu gri; alfa: hafif saydam.
        """
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2

        # ana yastık
        pad_w, pad_h = int(size * 0.68), int(size * 0.45)
        pad = pygame.Rect(0, 0, pad_w, pad_h)
        pad.center = (cx, int(cy + size * 0.10))
        pygame.draw.ellipse(s, (40, 40, 40, 230), pad)

        # 4 parmak
        r = int(size * 0.14)
        offsets = [
            (-int(size * 0.20), -int(size * 0.10)),
            (-int(size * 0.07), -int(size * 0.18)),
            (int(size * 0.07), -int(size * 0.18)),
            (int(size * 0.20), -int(size * 0.10)),
        ]
        for ox, oy in offsets:
            pygame.draw.circle(s, (40, 40, 40, 230), (cx + ox, cy + oy), r)

        return s
