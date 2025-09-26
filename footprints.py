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
        self.target_position: tuple[int, int] | None = None  # Store the target entrance position
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
            self.target_position = None
            return

        # Store the target position for direction calculations
        self.target_position = goal_g
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
            self.target_position = None
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

    def draw(self, surf: pygame.Surface, cam, player_pos=None):
        """Draw paw prints positioned 3 units away from player toward the entrance."""
        if self._paw_base is None or self.target_position is None:
            return

        # If no player position provided, fall back to old path-based system
        if player_pos is None:
            self._draw_path_based(surf, cam)
            return

        paw = self._paw_base
        alpha = 190
        
        # Convert player position to grid coordinates
        from utils import px_to_grid
        player_gx, player_gy = px_to_grid(player_pos.x, player_pos.y)
        target_x, target_y = self.target_position

        # Calculate direction from player to entrance
        dx = target_x - player_gx
        dy = target_y - player_gy
        
        if dx == 0 and dy == 0:
            return  # No direction to show
            
        # Normalize the direction vector
        distance_to_target = math.sqrt(dx * dx + dy * dy)
        if distance_to_target == 0:
            return
            
        # Don't show paws if we're too close to the target (within 5 units)
        if distance_to_target <= 5.0:
            return
            
        dir_x = dx / distance_to_target
        dir_y = dy / distance_to_target
        
        # Calculate angle for paw rotation (paw points UP by default)
        angle_deg = math.degrees(math.atan2(dy, dx)) + 90

        # Create natural paw prints with alternating left/right pattern
        # Only place paws that don't exceed the distance to target (leave 3 units buffer)
        max_distance = min(23.0, distance_to_target - 3.0)
        distances = [d for d in [3.0, 7.0, 11.0, 15.0, 19.0, 23.0] if d <= max_distance]
        
        if not distances:  # No paws to place
            return
        
        # Calculate perpendicular direction for left/right offset
        perp_x = -dir_y  # Perpendicular to direction vector
        perp_y = dir_x
        
        for i, dist in enumerate(distances):
            # Calculate base paw position along the main direction
            base_gx = player_gx + dir_x * dist
            base_gy = player_gy + dir_y * dist
            
            # Alternate between left and right paws
            is_left = (i % 2 == 0)
            side_offset = 0.3 if is_left else -0.3  # Small offset to left or right
            
            # Add slight forward/backward variation for more natural gait
            forward_variation = 0.1 if is_left else -0.1
            
            # Apply offsets for natural paw placement
            paw_gx = base_gx + perp_x * side_offset + dir_x * forward_variation
            paw_gy = base_gy + perp_y * side_offset + dir_y * forward_variation
            
            # Convert to screen coordinates
            px = paw_gx * TILE + TILE // 2 - int(cam.offset.x)
            py = paw_gy * TILE + TILE // 2 - int(cam.offset.y)
            
            # Check if paw is visible on screen
            if -50 < px < surf.get_width() + 50 and -50 < py < surf.get_height() + 50:
                img = self._get_rotated_cached(paw, angle_deg)
                img.set_alpha(alpha)
                rect = img.get_rect(center=(int(px), int(py)))
                surf.blit(img, rect)

    def _draw_path_based(self, surf: pygame.Surface, cam):
        """Fallback: old path-based drawing system."""
        if not self.points:
            return
            
        paw = self._paw_base
        alpha = 190
        step = getattr(self, "step_tiles", 7)
        n = len(self.points)
        target_x, target_y = self.target_position

        for i in range(0, n, step):
            gx, gy = self.points[i]
            px = gx * TILE + TILE // 2 - int(cam.offset.x)
            py = gy * TILE + TILE // 2 - int(cam.offset.y)

            dx = target_x - gx
            dy = target_y - gy
            angle_deg = math.degrees(math.atan2(dy, dx)) + 90 if (dx != 0 or dy != 0) else 0

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
