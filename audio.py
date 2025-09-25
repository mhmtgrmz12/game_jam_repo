import os, pygame
from config import AUDIO_DIR

class Audio:
    def __init__(self, settings):
        self.enabled_music = settings.get("music", True)
        self.enabled_sfx = settings.get("sfx", True)
        self.current = None
        try:
            pygame.mixer.init()
            self.ready = True
        except:
            self.ready = False

        self.music_map = {
            "menu": os.path.join(AUDIO_DIR, "music_menu.ogg"),
            "explore_outdoor": os.path.join(AUDIO_DIR, "music_explore_outdoor.ogg"),
            "explore_indoor": os.path.join(AUDIO_DIR, "music_explore_indoor.ogg"),
            "chase_outdoor": os.path.join(AUDIO_DIR, "music_chase_outdoor.ogg"),
            "chase_indoor": os.path.join(AUDIO_DIR, "music_chase_indoor.ogg"),
        }
        self.sfx = {}
        for key, fname in [("rescue","sfx_rescue.wav"), ("caught","sfx_caught.wav")]:
            path = os.path.join(AUDIO_DIR, fname)
            if self.ready and os.path.exists(path):
                try:
                    self.sfx[key] = pygame.mixer.Sound(path)
                except:
                    pass

    def play_music(self, key, fade_ms=400):
        if not self.ready or not self.enabled_music: return
        if self.current == key: return
        path = self.music_map.get(key)
        if not path or not os.path.exists(path): return
        try:
            pygame.mixer.music.fadeout(fade_ms)
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1, fade_ms=fade_ms)
            self.current = key
        except:
            pass

    def play_sfx(self, key):
        if not self.ready or not self.enabled_sfx: return
        s = self.sfx.get(key)
        if s:
            try: s.play()
            except: pass
