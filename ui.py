import pygame
from config import SCREEN_W, SCREEN_H

def draw_menu(screen, bigfont, font, colors, items, idx):
    screen.fill(colors["bg"])
    title = bigfont.render("Tiger Rescue – The Footprint Maze", True, colors["ui"])
    screen.blit(title, (SCREEN_W//2 - title.get_width()//2, 120))
    for i, item in enumerate(items):
        col = colors["ui"] if i!=idx else colors["tiger"]
        txt = font.render(("> " if i==idx else "  ")+item, True, col)
        screen.blit(txt, (SCREEN_W//2 - 80, 240 + i*40))
    tip = font.render("Use ↑/↓ and Enter. Esc exits.", True, colors["ui"])
    screen.blit(tip, (SCREEN_W//2 - tip.get_width()//2, 520))

def draw_themes(screen, bigfont, font, colors, theme_name):
    screen.fill(colors["bg"])
    t = bigfont.render("Themes", True, colors["ui"])
    screen.blit(t, (SCREEN_W//2 - t.get_width()//2, 100))
    n = bigfont.render(theme_name, True, colors["tiger"])
    screen.blit(n, (SCREEN_W//2 - n.get_width()//2, 200))
    hint = font.render("← → to change theme, Enter/Esc to return", True, colors["ui"])
    screen.blit(hint, (SCREEN_W//2 - hint.get_width()//2, 280))

def draw_scores(screen, bigfont, font, colors, scores):
    screen.fill(colors["bg"])
    t = bigfont.render("Scores", True, colors["ui"])
    screen.blit(t, (SCREEN_W//2 - t.get_width()//2, 90))
    if not scores:
        msg = font.render("No scores yet. Play a game!", True, colors["ui"])
        screen.blit(msg, (SCREEN_W//2 - msg.get_width()//2, 180))
    else:
        y = 170
        headers = font.render("TimeLeft  Rescued  Caughts  Difficulty  Date", True, colors["ui"])
        screen.blit(headers, (120, y)); y+=28
        import time
        for s in scores:
            dt = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["timestamp"]))
            line = f"{s['time_left']:>7}     {s['rescued']:>3}       {s.get('caughts',0):>3}      {s.get('difficulty','Default'):<10}  {dt}"
            txt = font.render(line, True, colors["ui"])
            screen.blit(txt, (120, y)); y+=26
            if y>SCREEN_H-80: break
    hint = font.render("Press Esc/Enter to return to Menu", True, colors["ui"])
    screen.blit(hint, (SCREEN_W//2 - hint.get_width()//2, SCREEN_H-60))
