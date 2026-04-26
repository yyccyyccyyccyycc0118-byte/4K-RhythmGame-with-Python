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

# 逻辑显示尺寸（GPU 全屏模式下使用）
# 在 GPU 全屏模式下，real_screen 的尺寸为 (logical_w, SCREEN_HEIGHT)，
# 其中 logical_w 根据屏幕宽高比计算，使得 SCALED 缩放后无 letterbox 黑边
logical_w = 400
logical_h = 600

_cached_scaled_surf = None
_cached_scaled_size = (0, 0)
use_gpu_scale = False

# 真实屏幕背景封面（显示在两侧"黑边"区域）
real_bg_surf = None

# 背景脏标记：显示模式切换后设为 True，主菜单检测到后重新加载封面
bg_dirty = False

# 最后一次成功加载的封面信息（用于显示模式切换后自动恢复背景）
_last_bg_map_path = None
_last_bg_map_data = None

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
            "window_width": 1920,
            "window_height": 1080,
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
    global use_gpu_scale, real_bg_surf, logical_w, logical_h

    # 标记背景需要重新加载
    global bg_dirty
    bg_dirty = True

    if real_screen is not None:
        pygame.display.quit()
        pygame.display.init()
        pygame.display.set_caption("4K Rhythm Game")

    # 重置背景
    real_bg_surf = None

    if config.get("fullscreen", False):
        # === GPU 硬件加速全屏模式 ===
        use_gpu_scale = True
        info = pygame.display.Info()
        current_w = info.current_w
        current_h = info.current_h

        # 关键计算：逻辑显示尺寸，高度保持 SCREEN_HEIGHT(600)，
        # 宽度按屏幕比例扩展，使得 SCALED 缩放后无 letterbox 黑边
        # 例如：16:9 屏幕 → logical_w = 600 * 16/9 ≈ 1067
        screen_aspect = current_w / current_h
        logical_w = int(SCREEN_HEIGHT * screen_aspect)
        logical_h = SCREEN_HEIGHT
        # 安全保护：确保逻辑显示区域至少能够容纳 400x600 的游戏画面
        #（竖屏显示器上宽度可能不足，此时改为以宽度为基准计算高度）
        if logical_w < SCREEN_WIDTH:
            logical_w = SCREEN_WIDTH
            logical_h = int(SCREEN_WIDTH / screen_aspect)

        real_screen = pygame.display.set_mode(
            (logical_w, logical_h),
            pygame.FULLSCREEN | pygame.SCALED | pygame.DOUBLEBUF
        )
    else:
        # === CPU 缩放窗口模式 ===
        use_gpu_scale = False
        logical_w = SCREEN_WIDTH
        logical_h = SCREEN_HEIGHT
        current_w = config.get("window_width", 400)
        current_h = config.get("window_height", 600)
        flags = pygame.DOUBLEBUF
        info = pygame.display.Info()
        if current_w == info.current_w and current_h == info.current_h:
            flags |= pygame.NOFRAME
        real_screen = pygame.display.set_mode((current_w, current_h), flags)

    pygame.key.stop_text_input()

    # 如果之前成功加载过封面，在显示模式切换后自动恢复
    if _last_bg_map_path is not None and _last_bg_map_data is not None:
        set_real_background_from_original(_last_bg_map_path, _last_bg_map_data)

def set_real_background_from_original(map_path, map_data):
    """从原始封面图片直接 cover 填充至背景层。

    在 GPU 全屏模式下，填充至 (logical_w, SCREEN_HEIGHT) 逻辑显示区域，
    使得两侧"黑边"也能显示封面。
    在窗口 CPU 模式下，填充至 (current_w, current_h) 物理窗口。
    加载失败或 bg 为空时自动清除背景。
    """
    global real_bg_surf, _last_bg_map_path, _last_bg_map_data
    bg_name = map_data.get("meta", {}).get("bg", "")
    if not bg_name:
        real_bg_surf = None
        return

    bg_path = os.path.abspath(os.path.join(os.path.dirname(map_path), bg_name))
    if not os.path.exists(bg_path):
        real_bg_surf = None
        return

    try:
        img = pygame.image.load(bg_path).convert()
        img_w, img_h = img.get_size()

        if use_gpu_scale:
            # GPU 模式：封面覆盖整个逻辑显示区域（无黑边）
            target_w = logical_w
            target_h = logical_h
        else:
            # CPU 模式（窗口）：封面覆盖整个物理窗口
            target_w = current_w
            target_h = current_h

        # cover 模式：等比缩放至填满目标区域，多余部分居中裁剪
        scale = max(target_w / img_w, target_h / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        scaled = pygame.transform.smoothscale(img, (new_w, new_h))

        crop_x = (new_w - target_w) // 2
        crop_y = (new_h - target_h) // 2
        if crop_x == 0 and crop_y == 0:
            real_bg_surf = scaled
        else:
            real_bg_surf = scaled.subsurface((crop_x, crop_y, target_w, target_h)).copy()

        # 缓存成功加载的封面信息，用于显示模式切换后自动恢复
        _last_bg_map_path = map_path
        _last_bg_map_data = map_data
    except:
        real_bg_surf = None

def clear_real_background():
    """清除背景封面（同时清除缓存，防止 set_display_mode 自动恢复）"""
    global real_bg_surf, _last_bg_map_path, _last_bg_map_data
    real_bg_surf = None
    _last_bg_map_path = None
    _last_bg_map_data = None

def update_display():
    global real_screen, current_w, current_h, screen, SCREEN_WIDTH, SCREEN_HEIGHT
    global _cached_scaled_surf, _cached_scaled_size, use_gpu_scale, real_bg_surf, logical_w

    if use_gpu_scale:
        # === GPU 硬件加速渲染路径 ===
        # pygame.SCALED 自动将 (logical_w, logical_h) GPU 缩放至全屏
        # 由于 logical_w/logical_h 与屏幕同比例，SDL2 不会添加 letterbox 黑边
        # 1) 封面作为底层背景填入整个逻辑显示区域
        if real_bg_surf is not None:
            real_screen.blit(real_bg_surf, (0, 0))
        else:
            real_screen.fill((0, 0, 0))

        # 2) 将 400x600 的游戏画面居中叠加在逻辑显示区域上
        # 两侧多出的区域（原黑边区）显示封面背景
        x_offset = (logical_w - SCREEN_WIDTH) // 2
        y_offset = (logical_h - SCREEN_HEIGHT) // 2
        real_screen.blit(screen, (x_offset, y_offset))
        pygame.display.flip()
        return

    # === CPU 缩放模式（窗口模式） ===
    if real_bg_surf is not None:
        real_screen.blit(real_bg_surf, (0, 0))
    else:
        real_screen.fill((0, 0, 0))

    # 手动缩放游戏画面到窗口中心
    scale_w = current_w / SCREEN_WIDTH
    scale_h = current_h / SCREEN_HEIGHT
    scale = min(scale_w, scale_h)
    new_w = int(SCREEN_WIDTH * scale)
    new_h = int(SCREEN_HEIGHT * scale)

    if _cached_scaled_size != (new_w, new_h):
        _cached_scaled_size = (new_w, new_h)
        _cached_scaled_surf = pygame.Surface((new_w, new_h))

    pygame.transform.scale(screen, (new_w, new_h), _cached_scaled_surf)

    x_offset = (current_w - new_w) // 2
    y_offset = (current_h - new_h) // 2
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
        paths_to_try = [
            os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath("."), filename),
            os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), filename),
            os.path.join(os.path.abspath("."), filename)
        ]
        for p in paths_to_try:
            if os.path.exists(p):
                return p
        return filename

    font_path = get_font_path("SourceHanSansCN-Bold.otf")

    try:
        font = pygame.font.Font(font_path, 36)
        small_font = pygame.font.Font(font_path, 24)
        tiny_font = pygame.font.Font(font_path, 18)
    except Exception as e:
        print(f"字体加载失败: {e}, 尝试使用系统缺省")
        try:
            font = pygame.font.SysFont("simhei", 36)
            small_font = pygame.font.SysFont("simhei", 24)
            tiny_font = pygame.font.SysFont("simhei", 18)
        except Exception:
            font = pygame.font.Font(None, 36)
            small_font = pygame.font.Font(None, 24)
            tiny_font = pygame.font.Font(None, 18)

    update_key_map()

def load_fill_bg(map_path, map_data):
    """加载封面图片并将其缩放填充至整个 400x600 屏幕（cover 模式，居中裁剪）"""
    bg_name = map_data.get("meta", {}).get("bg", "")
    if not bg_name:
        return None

    bg_path = os.path.abspath(os.path.join(os.path.dirname(map_path), bg_name))
    if not os.path.exists(bg_path):
        return None

    try:
        img = pygame.image.load(bg_path).convert()
        img_w, img_h = img.get_size()
        scale = max(SCREEN_WIDTH / img_w, SCREEN_HEIGHT / img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        scaled = pygame.transform.smoothscale(img, (new_w, new_h))
        crop_x = (new_w - SCREEN_WIDTH) // 2
        crop_y = (new_h - SCREEN_HEIGHT) // 2
        if crop_x == 0 and crop_y == 0:
            return scaled
        cropped = scaled.subsurface((crop_x, crop_y, SCREEN_WIDTH, SCREEN_HEIGHT))
        return cropped.copy()
    except Exception as e:
        print(f"Failed to load background image {bg_path}: {e}")
        return None

def load_bg_image(map_path, map_data):
    """加载封面缩略图（用于结算/预览界面展示）"""
    bg_name = map_data.get("meta", {}).get("bg", "")
    if not bg_name:
        return None

    bg_path = os.path.abspath(os.path.join(os.path.dirname(map_path), bg_name))
    if not os.path.exists(bg_path):
        return None

    try:
        img = pygame.image.load(bg_path).convert()
        img_w, img_h = img.get_size()
        max_w, max_h = 280, 160
        scale = min(max_w / img_w, max_h / img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        thumb_surf = pygame.transform.smoothscale(img, (new_w, new_h))
        return thumb_surf
    except Exception as e:
        print(f"Failed to load background image {bg_path}: {e}")
        return None

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

        cycle_duration = (total_w / speed * 1000) + 1500
        current_time_in_cycle = ms % cycle_duration

        if current_time_in_cycle < 1500:
            offset = 0
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
