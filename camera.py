import pygame
from utils import clamp
from config import SCREEN_W, SCREEN_H

class Camera:
    def __init__(self, world_w, world_h):
        self.world_w = world_w
        self.world_h = world_h
        self.offset = pygame.Vector2(0,0)
        self.smooth = 0.15

    def follow(self, target_pos):
        desired = pygame.Vector2(target_pos.x - SCREEN_W/2, target_pos.y - SCREEN_H/2)
        self.offset += (desired - self.offset) * self.smooth
        self.offset.x = clamp(self.offset.x, 0, max(0, self.world_w - SCREEN_W))
        self.offset.y = clamp(self.offset.y, 0, max(0, self.world_h - SCREEN_H))

    def to_screen(self, world_pos):
        return world_pos - self.offset
