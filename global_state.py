import pygame
import sys
import os
import json
import ctypes

try:
    if os.name == 'nt':
        ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

config = {}
history_data = {}
show_fps = False
KEY_MAP = {}
clock = None

SCREEN_WIDTH = 400
SCREEN_HEIGHT = 600
screen = None
real_screen = None
current_w = 400
current_h = 600

_cached_scaled_surf = None
_cached_scaled_size = (0, 0)
use_gpu_scale = False

font = None
small_font = None


def load_history():
    global history_data
    history_path = "history.json"
    if not os.path.exists(history_path):
        history_data = {}
        save_history()
    else:
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except:
            history_data = {}

def save_history():
    with open("history.json", "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=4)

def load_config():
    load_history()
    global config
    config_path = "config.json"
    if not os.path.exists(config_path):
        default_config = {
            "scroll_speed": 0.6,
            "global_offset": 0,
            "key_bindings": ["d", "f", "j", "k"],
            "window_width": 400,
            "window_height": 600,
            "fullscreen": False
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4)
        config = default_config
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

def save_config():
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

def update_key_map():
    global KEY_MAP
    KEY_MAP.clear()
    bindings = config.get("key_bindings", ["d", "f", "j", "k"])
    for i, key_str in enumerate(bindings):
        if hasattr(pygame, f"K_{key_str}"):
            KEY_MAP[getattr(pygame, f"K_{key_str}")] = i

def set_display_mode():
    global real_screen, current_w, current_h, screen, SCREEN_WIDTH, SCREEN_HEIGHT
    global use_gpu_scale

    if real_screen is not None:
        pygame.display.quit()
        pygame.display.init()
        pygame.display.set_caption("4K Rhythm Game")
    
    flags = pygame.DOUBLEBUF | pygame.HWSURFACE
    
    use_gpu_scale = False
    
    if config.get("fullscreen", False):
        flags |= (pygame.FULLSCREEN | pygame.SCALED)
        current_w = SCREEN_WIDTH
        current_h = SCREEN_HEIGHT
        use_gpu_scale = True
    else:
        current_w = config.get("window_width", 400)
        current_h = config.get("window_height", 600)
        # Windows 特定：如果窗口开了显示器原生分辨率，消除边框
        info = pygame.display.Info()
        if current_w == info.current_w and current_h == info.current_h:
            flags |= pygame.NOFRAME

    real_screen = pygame.display.set_mode((current_w, current_h), flags)
    pygame.key.stop_text_input()

def update_display():
    global real_screen, current_w, current_h, screen, SCREEN_WIDTH, SCREEN_HEIGHT
    global _cached_scaled_surf, _cached_scaled_size, use_gpu_scale
    
    if use_gpu_scale:
        real_screen.blit(screen, (0, 0))
        pygame.display.flip()
        return
        
    # 纯 CPU 软件渲染模式（借助 _cached_scaled_surf 极速内存覆盖优化，支持稳定 500+FPS）
    scale_w = current_w / SCREEN_WIDTH
    scale_h = current_h / SCREEN_HEIGHT
    scale = min(scale_w, scale_h)
    new_w = int(SCREEN_WIDTH * scale)
    new_h = int(SCREEN_HEIGHT * scale)
    
    if _cached_scaled_size != (new_w, new_h):
        _cached_scaled_size = (new_w, new_h)
        _cached_scaled_surf = pygame.Surface((new_w, new_h))
        real_screen.fill((0, 0, 0))

    # CPU 直接将 screen 逐像素缩放并填入申请好的 _cached_scaled_surf
    pygame.transform.scale(screen, (new_w, new_h), _cached_scaled_surf)

    x_offset = (current_w - new_w) // 2
    y_offset = (current_h - new_h) // 2
    
    if x_offset > 0:
        pygame.draw.rect(real_screen, (0,0,0), (0, 0, x_offset, current_h))
        pygame.draw.rect(real_screen, (0,0,0), (current_w - x_offset, 0, x_offset, current_h))
    if y_offset > 0:
        pygame.draw.rect(real_screen, (0,0,0), (0, 0, current_w, y_offset))
        pygame.draw.rect(real_screen, (0,0,0), (0, current_h - y_offset, current_w, y_offset))
        
    real_screen.blit(_cached_scaled_surf, (x_offset, y_offset))
    pygame.display.flip()

def init_globals():
    global screen, clock, font, small_font, tiny_font
    pygame.init()
    pygame.mixer.init()
    load_config()
    load_history()
    screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    set_display_mode()
    pygame.key.stop_text_input()
    pygame.display.set_caption("4K Rhythm Game")
    clock = pygame.time.Clock()
    
    import sys
    def get_font_path(filename):
        # 依次尝试以下几个可能的路径
        paths_to_try = [
            # 1. 如果你在打包后，把字体文件放在了 exe 同级目录
            os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath("."), filename),
            # 2. 如果你在打包时用了 --add-data 把字体打包进了 exe 内部 (解压在 _MEIPASS)
            os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), filename),
            # 3. 相对路径 / 当前工作目录
            os.path.join(os.path.abspath("."), filename)
        ]
        
        for p in paths_to_try:
            if os.path.exists(p):
                return p
        return filename # 最后兜底丢给 pygame 让它去报错或加载
        
    font_path = get_font_path("SourceHanSansCN-Bold.otf")
    
    try:
        font = pygame.font.Font(font_path, 36)
        small_font = pygame.font.Font(font_path, 24)
        tiny_font = pygame.font.Font(font_path, 18)
    except Exception as e:
        print(f"字体加载失败: {e}, 尝试使用系统缺省")
        # 找不到思源字体时，不要用 None (不支持中文)，尝试抓取系统里别的默认中文字体
        try:
            font = pygame.font.SysFont("simhei", 36)
            small_font = pygame.font.SysFont("simhei", 24)
            tiny_font = pygame.font.SysFont("simhei", 18)
        except Exception:
            font = pygame.font.Font(None, 36)
            small_font = pygame.font.Font(None, 24)
            tiny_font = pygame.font.Font(None, 18)
                
    update_key_map()
import pygame
import os
import global_state as g

def load_bg_image(map_path, map_data):
    bg_name = map_data.get("meta", {}).get("bg", "")
    if not bg_name:
        return None
        
    bg_path = os.path.abspath(os.path.join(os.path.dirname(map_path), bg_name))
    if not os.path.exists(bg_path):
        return None
        
    try:
        img = pygame.image.load(bg_path).convert()
        # 改为生成一张缩略图 (限制最大宽高如 280 x 160)
        img_w, img_h = img.get_size()
        max_w, max_h = 280, 160
        scale = min(max_w / img_w, max_h / img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        
        # 平滑缩放缩略图
        thumb_surf = pygame.transform.smoothscale(img, (new_w, new_h))
        return thumb_surf
    except Exception as e:
        print(f"Failed to load background image {bg_path}: {e}")
        return None

# We can append it to global_state.py

def draw_marquee_text(surface, text, font, color, center_x, y, max_width):
    if not text:
        return
    text_surf = font.render(text, True, color)
    text_w = text_surf.get_width()
    
    if text_w <= max_width:
        x_pos = center_x - text_w // 2
        surface.blit(text_surf, (x_pos, y))
    else:
        speed = 60.0
        gap = 100 
        total_w = text_w + gap
        
        import pygame
        ms = pygame.time.get_ticks()
        
        # 每轮停顿 1.5 秒
        cycle_duration = (total_w / speed * 1000) + 1500
        current_time_in_cycle = ms % cycle_duration
        
        if current_time_in_cycle < 1500:
            offset = 0 # 停顿
        else:
            offset = ((current_time_in_cycle - 1500) / 1000.0) * speed

        x_start = center_x - max_width // 2
        clip_rect = pygame.Rect(x_start, y, max_width, text_surf.get_height())
        old_clip = surface.get_clip()
        
        if old_clip:
            clip_rect = clip_rect.clip(old_clip)
            
        surface.set_clip(clip_rect)
        
        draw_x = x_start - offset
        surface.blit(text_surf, (draw_x, y))
        if draw_x + text_w < x_start + max_width:
            surface.blit(text_surf, (draw_x + total_w, y))
            
        surface.set_clip(old_clip)
