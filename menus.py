import pygame
import sys
import os
import glob
import json
import subprocess
import global_state as g

def load_songs():
    songs_dir = "songs"
    if not os.path.exists(songs_dir):
        try:
            os.makedirs(songs_dir)
        except:
            pass
        
    songs = []
    if os.path.exists(songs_dir):
        for folder_name in os.listdir(songs_dir):
            folder_path = os.path.join(songs_dir, folder_name)
            if os.path.isdir(folder_path):
                jsons = glob.glob(os.path.join(folder_path, "*.json"))
                if jsons:
                    songs.append({
                        "dir_name": folder_name,
                        "path": folder_path,
                        "jsons": sorted(jsons),
                        "selected_diff": 0
                    })
                    
    # 如果没在歌曲目录找到，尝试返回根目录谱面作为兜底
    if not songs:
        all_jsons = glob.glob("*.json")
        map_files = [f for f in all_jsons if f not in ["config.json", "map_export.json"]]
        if not map_files:
            map_files = ["map.json"]
        songs.append({
            "dir_name": "默认根目录谱面",
            "path": ".",
            "jsons": sorted(map_files),
            "selected_diff": 0
        })
        
    return sorted(songs, key=lambda x: x["dir_name"])

def get_first_map_data(song):
    """从歌曲中获取第一个谱面的 JSON 数据和路径"""
    if not song["jsons"]:
        return None, None
    first_json = song["jsons"][0]
    try:
        with open(first_json, "r", encoding="utf-8") as f:
            map_data = json.load(f)
        return first_json, map_data
    except:
        return None, None

def main_menu():
    songs = load_songs()
    selected_index = 0

    camera_y = 0
    
    # 背景缓存
    prev_selected_index = -1
    
    while True:
        # 如果选中歌曲变更 或 显示模式切换后需要重新加载背景
        if selected_index != prev_selected_index or g.bg_dirty:
            g.bg_dirty = False
            prev_selected_index = selected_index
            song = songs[selected_index]
            first_json, map_data = get_first_map_data(song)
            if first_json and map_data:
                g.set_real_background_from_original(first_json, map_data)
            else:
                g.clear_real_background()
        
        g.screen.fill((40, 40, 60))
        
        # 渲染标题和设置提示 (Fixed Header)
        title = g.font.render("=== 选歌菜单 ===", True, (255, 255, 255))
        g.screen.blit(title, (g.SCREEN_WIDTH // 2 - title.get_width() // 2, 40))
        
        speed_text = g.small_font.render(f"Speed: {g.config['scroll_speed']:.2f} (< / >)", True, (200, 200, 200))
        offset_text = g.small_font.render(f"Offset: {g.config.get('global_offset', 0)}ms (A / D)", True, (200, 200, 200))
        rate_val = g.config.get("song_rate", 1.0)
        rate_text = g.small_font.render(f"Rate: {rate_val:.2f}x (W/E)", True, (255, 200, 200))
        
        g.screen.blit(speed_text, (20, 80))
        g.screen.blit(offset_text, (20, 110))
        g.screen.blit(rate_text, (20, 140))
        
        # 预先计算所有曲目的高度和 Y 轴坐标，以便计算滚动视口
        sim_y = 0
        item_bounds = []
        for i, song in enumerate(songs):
            display_name = (">> " if i == selected_index else "   ") + song["dir_name"]
            
            # 使用逐字防爆宽容换行计算高度
            lines_curr = []
            cur_line = ""
            for char in display_name:
                test_line = cur_line + char
                if g.small_font.size(test_line)[0] < g.SCREEN_WIDTH - 40:
                    cur_line = test_line
                else:
                    if cur_line: lines_curr.append(cur_line)
                    cur_line = "      " + char
            if cur_line: lines_curr.append(cur_line)
            
            item_h = len(lines_curr) * 25 + 5
            item_bounds.append({"y": sim_y, "h": item_h, "lines": lines_curr})
            sim_y += item_h
            
        # 设定摄像机滚动目标：让选中的曲目尽量居中
        target_item = item_bounds[selected_index]
        target_camera_y = target_item["y"] + target_item["h"] / 2 - (g.SCREEN_HEIGHT - 170 - 80) / 2
        # 约束滚动边界
        max_scroll = max(0, sim_y - (g.SCREEN_HEIGHT - 170 - 80))
        target_camera_y = max(0, min(target_camera_y, max_scroll))
        
        # 平滑滚动
        camera_y += (target_camera_y - camera_y) * 0.15
        if abs(camera_y - target_camera_y) < 1.0:
            camera_y = target_camera_y

        # 因为 Rate 选项占用了 Y=140，且字体加上行距大概二十多，为防止重叠，把列表绘制的顶线往下推到 Y=175
        clip_rect = pygame.Rect(0, 175, g.SCREEN_WIDTH, g.SCREEN_HEIGHT - 175 - 70)
        g.screen.set_clip(clip_rect)
        
        # 渲染计算好的曲目列表
        draw_y = 185 - camera_y
        for i, bound in enumerate(item_bounds):
            if draw_y + bound["h"] > 175 and draw_y < g.SCREEN_HEIGHT - 70:
                color = (0, 255, 100) if i == selected_index else (150, 150, 150)
                item_y = draw_y
                for count, line in enumerate(bound["lines"]):
                    item_text = g.small_font.render(line, True, color)
                    x_pos = 20 if count == 0 else 40
                    g.screen.blit(item_text, (x_pos, item_y))
                    item_y += 25
            draw_y += bound["h"]

        # 解除剪裁保护，准备渲染底部菜单
        g.screen.set_clip(None)
        
        # 底部透明渐边/横线遮挡效果（可选）
        pygame.draw.line(g.screen, (100, 100, 150), (0, 175), (g.SCREEN_WIDTH, 175), 2)
        pygame.draw.line(g.screen, (100, 100, 150), (0, g.SCREEN_HEIGHT - 70), (g.SCREEN_WIDTH, g.SCREEN_HEIGHT - 70), 2)

        settings_tip = g.small_font.render("Press S for Settings", True, (200, 255, 200))

        # Blit the text on screen (Centered)
        g.screen.blit(settings_tip, (g.SCREEN_WIDTH // 2 - settings_tip.get_width() // 2, g.SCREEN_HEIGHT - 45))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    g.show_fps = not g.show_fps
                    
                if event.key == pygame.K_s:
                    settings_menu()
                    
                if event.key == pygame.K_UP:
                    selected_index = (selected_index - 1) % len(songs)
                elif event.key == pygame.K_DOWN:
                    selected_index = (selected_index + 1) % len(songs)
                

                    
                # 逗号/句号 ( < / > ) 用于调节流速
                elif event.key == pygame.K_COMMA:
                    step = 0.01 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 0.05
                    g.config["scroll_speed"] = max(0.1, g.config["scroll_speed"] - step)
                elif event.key == pygame.K_PERIOD:
                    step = 0.01 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 0.05
                    g.config["scroll_speed"] += step
                    
                # A/D 键调节全局延迟
                elif event.key == pygame.K_a:
                    step = 1 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 5
                    g.config["global_offset"] -= step
                elif event.key == pygame.K_d:
                    step = 1 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 5
                    g.config["global_offset"] += step
                    
                # W/E 键调节播放倍速
                elif event.key == pygame.K_w:
                    step = 0.01 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 0.1
                    current_rate = g.config.get("song_rate", 1.0)
                    g.config["song_rate"] = max(0.5, round(current_rate - step, 2))
                elif event.key == pygame.K_e:
                    step = 0.01 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 0.1
                    current_rate = g.config.get("song_rate", 1.0)
                    g.config["song_rate"] = min(2.0, round(current_rate + step, 2))

                # F 键全屏，R 键分辨率
                elif event.key == pygame.K_f and not (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    g.config["fullscreen"] = not g.config.get("fullscreen", False)
                    g.set_display_mode()
                    # 切换模式后 real_bg_surf 被重置，强制下一帧重新加载背景
                    prev_selected_index = -1
                elif event.key == pygame.K_r and not (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    g.config["fullscreen"] = False
                    current_res = (g.config.get("window_width", 400), g.config.get("window_height", 600))
                    available_res = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440)]
                    try:
                        idx = available_res.index(current_res)
                        next_res = available_res[(idx + 1) % len(available_res)]
                    except ValueError:
                        next_res = available_res[0]
                    g.config["window_width"] = next_res[0]
                    g.config["window_height"] = next_res[1]
                    g.set_display_mode()
                    # 分辨率变更后强制重新加载背景
                    prev_selected_index = -1
                    
                elif event.key == pygame.K_RETURN:
                    g.save_config()
                    # 返回整个曲包信息给详细界面
                    song = songs[selected_index]
                    return song
                
                elif event.key == pygame.K_ESCAPE:
                    exit_confirm()

        if g.show_fps:
            fps_text = g.small_font.render(f"FPS: {int(g.clock.get_fps())}", True, (255, 100, 100))
            g.screen.blit(fps_text, (10, g.SCREEN_HEIGHT - 30))

        g.update_display()
        g.clock.tick(60)

# --- 2.2 设置界面 ---

def settings_menu():
    
    
    # 状态：-1标识不在改键，0~3代表正在修改第1~4个按键
    binding_index = -1 
    
    while True:
        g.screen.fill((50, 40, 60))
        
        title = g.font.render("=== 游戏设置 ===", True, (255, 255, 255))
        g.screen.blit(title, (g.SCREEN_WIDTH // 2 - title.get_width() // 2, 50))
        
        hint = g.small_font.render("按 [1] [2] [3] [4] 修改对应列键位" if binding_index == -1 else f"请按下新的键位用于第 {binding_index+1} 键...", True, (255, 200, 200))
        g.screen.blit(hint, (g.SCREEN_WIDTH // 2 - hint.get_width() // 2, 100))
        
        y_offset = 180
        for i in range(4):
            key_name = g.config["key_bindings"][i].upper()
            color = (0, 255, 255) if i == binding_index else (200, 200, 200)
            text_str = f"[{i+1}] 轨道 {i+1} 按键: {key_name}"
            
            item_text = g.small_font.render(text_str, True, color)
            g.screen.blit(item_text, (50, y_offset))
            y_offset += 40
            
        fs_status = "开" if g.config.get("fullscreen", False) else "关"
        fs_text = g.small_font.render(f"[F] 全屏模式: {fs_status}", True, (200, 255, 200))
        g.screen.blit(fs_text, (50, y_offset + 20))
        
        res_text = g.small_font.render(f"[R] 窗口分辨率: {g.config.get('window_width', 400)}x{g.config.get('window_height', 600)}", True, (200, 255, 200))
        g.screen.blit(res_text, (50, y_offset + 60))
            
        exit_hint = g.small_font.render("按 [ESC] 返回主界面保存", True, (150, 150, 150))
        g.screen.blit(exit_hint, (g.SCREEN_WIDTH // 2 - exit_hint.get_width() // 2, g.SCREEN_HEIGHT - 60))

        if g.show_fps:
            fps_text = g.small_font.render(f"FPS: {int(g.clock.get_fps())}", True, (255, 100, 100))
            g.screen.blit(fps_text, (10, g.SCREEN_HEIGHT - 30))

        g.update_display()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    g.show_fps = not g.show_fps
                    continue
                    
                if binding_index != -1:
                    # 如果正在改某一个键，拦截键盘按键名字
                    new_key = pygame.key.name(event.key)
                    if len(new_key) > 0 and hasattr(pygame, f"K_{new_key.lower()}"):
                        g.config["key_bindings"][binding_index] = new_key.lower()
                    binding_index = -1
                else:
                    if event.key == pygame.K_ESCAPE:
                        # 保存返回
                        g.save_config()
                        # 
        # json.dump(g.config, f, indent=4)
                        g.update_key_map()
                        return
                    elif event.key == pygame.K_1:
                        binding_index = 0
                    elif event.key == pygame.K_2:
                        binding_index = 1
                    elif event.key == pygame.K_3:
                        binding_index = 2
                    elif event.key == pygame.K_4:
                        binding_index = 3
                    elif event.key == pygame.K_f:
                        g.config["fullscreen"] = not g.config.get("fullscreen", False)
                        g.set_display_mode()
                        g.bg_dirty = True  # 标记背景需要重新加载
                    elif event.key == pygame.K_r:
                        g.config["fullscreen"] = False
                        current_res = (g.config.get("window_width", 400), g.config.get("window_height", 600))
                        available_res = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440)]
                        try:
                            idx = available_res.index(current_res)
                            next_res = available_res[(idx + 1) % len(available_res)]
                        except ValueError:
                            next_res = available_res[0]
                        g.config["window_width"] = next_res[0]
                        g.config["window_height"] = next_res[1]
                        g.set_display_mode()
                        g.bg_dirty = True  # 标记背景需要重新加载
                        
        g.clock.tick(60)

# --- 2.5 谱面信息预览 ---
def exit_confirm():
    import pygame
    import sys
    import global_state as g
    
    while True:
        # We can draw over the current screen, giving it a semi-transparent overlay or just a prompt
        overlay = pygame.Surface((g.SCREEN_WIDTH, g.SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        g.screen.blit(overlay, (0, 0))
        
        box = pygame.Rect(g.SCREEN_WIDTH // 2 - 150, g.SCREEN_HEIGHT // 2 - 80, 300, 160)
        pygame.draw.rect(g.screen, (50, 50, 70), box)
        pygame.draw.rect(g.screen, (255, 255, 255), box, 2)
        
        msg = g.font.render("Quit Game?", True, (255, 255, 255))
        msg2 = g.small_font.render("[ENTER] 确认  [ESC] 取消", True, (200, 200, 200))
        
        g.screen.blit(msg, (g.SCREEN_WIDTH // 2 - msg.get_width() // 2, g.SCREEN_HEIGHT // 2 - 40))
        g.screen.blit(msg2, (g.SCREEN_WIDTH // 2 - msg2.get_width() // 2, g.SCREEN_HEIGHT // 2 + 20))
        
        g.update_display()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    pygame.quit()
                    sys.exit()
                elif event.key == pygame.K_ESCAPE:
                    return

