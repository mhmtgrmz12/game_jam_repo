# camera.py
import pygame
from utils import clamp
from config import SCREEN_W, SCREEN_H

class Camera:
    """
    Viewport-aware kamera.
    - world_w/world_h: dünya boyutu (piksel)
    - view_w/view_h: ekranda görünen mantıksal viewport boyutu (piksel)
    - smooth: takip yumuşatma katsayısı (0 = anında, 0.1–0.2 önerilir)
    """
    def __init__(self, world_w: int, world_h: int,
                 view_w: int | None = None, view_h: int | None = None,
                 smooth: float = 0.15):
        self.world_w = int(world_w)
        self.world_h = int(world_h)
        self.view_w  = int(view_w if view_w is not None else SCREEN_W)
        self.view_h  = int(view_h if view_h is not None else SCREEN_H)
        self.offset = pygame.Vector2(0, 0)
        self.smooth = float(smooth)

    # ---- public API ----
    def set_view_size(self, w: int, h: int) -> None:
        """Zoom/viewport değiştiğinde çağır."""
        self.view_w, self.view_h = int(w), int(h)
        self._clamp_offset()

    def set_world_size(self, w: int, h: int) -> None:
        """Dünya/harita boyutu değiştiğinde çağır."""
        self.world_w, self.world_h = int(w), int(h)
        self._clamp_offset()

    def follow(self, target_pos: pygame.Vector2, snap: bool = False) -> None:
        """Hedefi ekranın merkezinde tutar."""
        desired = pygame.Vector2(
            target_pos.x - self.view_w * 0.5,
            target_pos.y - self.view_h * 0.5
        )
        if snap or self.smooth <= 0:
            self.offset.update(desired)
        else:
            self.offset += (desired - self.offset) * self.smooth
        self._clamp_offset()

    def to_screen(self, world_pos: pygame.Vector2) -> pygame.Vector2:
        """Dünya -> ekran koordinatı."""
        return world_pos - self.offset

    def to_world(self, screen_pos: pygame.Vector2) -> pygame.Vector2:
        """Ekran -> dünya koordinatı (gerekirse)."""
        return screen_pos + self.offset

    # ---- internal ----
    def _clamp_offset(self) -> None:
        max_x = max(0, self.world_w - self.view_w)
        max_y = max(0, self.world_h - self.view_h)
        self.offset.x = clamp(self.offset.x, 0, max_x)
        self.offset.y = clamp(self.offset.y, 0, max_y)