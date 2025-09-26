import os, pygame
from config import AUDIO_DIR


class Audio:
    def __init__(self, settings):
        self.enabled_music = settings.get("music", True)
        self.enabled_sfx = settings.get("sfx", True)
        self.current = None
        self.current_channel = None  # Track the channel for music
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.ready = True
        except:
            self.ready = False

        self.music_map = {
            "menu": os.path.join(AUDIO_DIR, "menu.ogg"),
            "explore_outdoor": os.path.join(AUDIO_DIR, "music_explore_outdoor.ogg"),
            "explore_indoor": os.path.join(AUDIO_DIR, "music_explore_indoor.ogg"),
            "chase_outdoor": os.path.join(AUDIO_DIR, "music_chase_outdoor.ogg"),
            "chase_indoor": os.path.join(AUDIO_DIR, "music_chase_indoor.ogg"),
            "the_end": os.path.join(AUDIO_DIR, "the_end.ogg"),
        }

        # Pre-load music as Sound objects for instant playback
        self.preloaded_music = {}
        if self.ready:
            for key, path in self.music_map.items():
                if os.path.exists(path):
                    try:
                        self.preloaded_music[key] = pygame.mixer.Sound(path)
                    except Exception as e:
                        print(f"Failed to pre-load {key}: {e}")
                        self.preloaded_music[key] = None

        self.sfx = {}
        for key, fname in [
            ("rescue", "rescue.ogg"),
            ("bushes", "bushes.ogg"),  # << saklanma sesi
            ("caught", "sfx_caught.wav")
        ]:
            path = os.path.join(AUDIO_DIR, fname)
            if self.ready and os.path.exists(path):
                try:
                    s = pygame.mixer.Sound(path)
                    # Per-SFX ses seviyesi:
                    if key == "bushes":
                        s.set_volume(1.0)  # << maksimum
                    elif key == "rescue":
                        s.set_volume(0.9)
                    else:
                        s.set_volume(0.9)
                    self.sfx[key] = s
                except Exception as e:
                    print(f"[SFX ERR] {key} -> {path}: {e}")
            else:
                print(f"[SFX MISS] {key} -> {path}")
    def play_music(self, key, fade_ms=400):
        if not self.ready or not self.enabled_music:
            return
        if self.current == key:
            return

        sound = self.preloaded_music.get(key)
        if not sound:
            return

        try:
            # Stop current music if playing
            if self.current_channel and self.current_channel.get_busy():
                self.current_channel.fadeout(fade_ms)

            # Play the new music on any available channel
            self.current_channel = sound.play(-1, fade_ms=fade_ms)
            self.current = key
        except Exception as e:
            print(f"Error playing music {key}: {e}")

    def play_sfx(self, key):
        if not self.ready or not self.enabled_sfx:
            return

        sound = self.sfx.get(key)
        if not sound:
            return

        try:
            sound.play()
        except Exception as e:
            print(f"Error playing SFX {key}: {e}")