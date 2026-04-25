import pygame
import sys
import os
import glob
import json
import subprocess
import sonic_python
import global_state as g

def play_game(map_path):
    
    LANES = [50, 150, 250, 350]
    
    song_rate = g.config.get("song_rate", 1.0)
    
    PERFECT_WINDOW = 60 * song_rate
    GREAT_WINDOW = 90 * song_rate
    MISS_WINDOW = 120 * song_rate
    
    speed = g.config["scroll_speed"]
    eff_speed = speed / song_rate
    global_offset = g.config["global_offset"]
    
    with open(map_path, "r", encoding="utf-8") as f:
        map_data = json.load(f)

    notes_data = map_data["notes"]
    # 确保音符严格按照时间先后排序，这对于后续每一帧的性能剔除算法至关重要
    notes_data.sort(key=lambda x: x["time"])
    
    for note in notes_data:
        note["hit"] = False
        note["missed"] = False
        if note.get("type") == "hold":
            note["holding"] = False

    try:
        # 将谱面中的相对音频路径转换为与 json 所在真实文件夹的绝对/相对拼接路径
        audio_file = os.path.abspath(os.path.join(os.path.dirname(map_path), map_data["meta"]["song"]))
        
        # 核心：使用纯正 CType 包装的 sonic 动态生成变速音频文件
        if song_rate != 1.0:
            temp_base_name = f".temp_{song_rate}x_{os.path.basename(audio_file)}"
            # 使用 wav 后缀以确保被 pygame 支持
            temp_audio_file = os.path.abspath(os.path.join(os.path.dirname(map_path), os.path.splitext(temp_base_name)[0] + ".wav"))
            
            # 显示正在生成的提示
            g.screen.fill((30, 30, 30))
            gen_text = g.small_font.render(f"Applying {song_rate}x Rate using sonic...", True, (200, 200, 200))
            g.screen.blit(gen_text, (g.SCREEN_WIDTH // 2 - gen_text.get_width() // 2, g.SCREEN_HEIGHT // 2))
            g.update_display()
            
            # 只有文件不存在时才生成，加速重复游玩
            if not os.path.exists(temp_audio_file):
                # 使用 sonic-python 加载并变形音频
                sonic_python.generate_stretched_audio(audio_file, temp_audio_file, song_rate)
            
            audio_to_load = temp_audio_file
        else:
            audio_to_load = audio_file
        
        pygame.mixer.music.load(audio_to_load)
        music_started = False
    except Exception as e:
        print(f"Warning: {e}")
        music_started = True

    start_time = pygame.time.get_ticks() 
    map_offset = map_data["meta"].get("offset", 0)
    LEAD_IN_TIME = 3000

    score = 0
    combo = 0
    perfect_count = 0
    good_count = 0
    miss_count = 0
    
    # 修复：长条本身提供头尾两次判定，应该将其计为2个判定元素，以修正可能超过100%的ACC以及结算信息
    total_judgments = sum(2 if n.get("type", "tap") == "hold" else 1 for n in notes_data)
    
    # 计算谱面的总时长，以便实现游玩进度条
    total_duration = 1.0 # 提供一个默认避免除零
    if len(notes_data) > 0:
        total_duration = max([n.get("end_time", n.get("time")) for n in notes_data])

    active_idx = 0

    while True:
        g.screen.fill((30, 30, 30)) # 背景深灰色
        
        # 加入图谱特定的偏移与玩家自身的全局偏移，另外通过LEAD_IN_TIME预留出3秒游戏内部时间，从而让原本挤在这个时候的音符被推迟，先慢慢往下落
        real_elapsed_time = pygame.time.get_ticks() - start_time
        current_time = real_elapsed_time * song_rate - map_offset - global_offset - LEAD_IN_TIME
        
        # 音频随缘触发
        if current_time >= 0 and not music_started:
            pygame.mixer.music.play()
            music_started = True
        
        # --- 事件处理 ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    g.show_fps = not g.show_fps
                    
                elif event.key == pygame.K_ESCAPE:
                    if music_started:
                        pygame.mixer.music.pause()
                    pause_start_time = pygame.time.get_ticks()
                    
                    options = ["继续 (Continue)", "重来 (Restart)", "退出 (Exit)"]
                    selected_opt = 0
                    action = None
                    
                    while True:
                        g.screen.fill((40, 40, 60))
                        title = g.font.render("=== PAUSED ===", True, (255, 255, 255))
                        g.screen.blit(title, (g.SCREEN_WIDTH // 2 - title.get_width() // 2, 100))
                        
                        y_off = 200
                        for i, opt in enumerate(options):
                            color = (0, 255, 100) if i == selected_opt else (150, 150, 150)
                            prefix = ">> " if i == selected_opt else "   "
                            opt_surf = g.font.render(prefix + opt, True, color)
                            g.screen.blit(opt_surf, (g.SCREEN_WIDTH // 2 - opt_surf.get_width() // 2, y_off))
                            y_off += 50
                            
                        if g.show_fps:
                            fps_text = g.small_font.render(f"FPS: {int(g.clock.get_fps())}", True, (255, 100, 100))
                            g.screen.blit(fps_text, (10, g.SCREEN_HEIGHT - 30))
                        
                        g.update_display()
                        
                        for p_event in pygame.event.get():
                            if p_event.type == pygame.QUIT:
                                pygame.quit()
                                sys.exit()
                            elif p_event.type == pygame.KEYDOWN:
                                if p_event.key == pygame.K_UP:
                                    selected_opt = (selected_opt - 1) % len(options)
                                elif p_event.key == pygame.K_DOWN:
                                    selected_opt = (selected_opt + 1) % len(options)
                                elif p_event.key == pygame.K_RETURN:
                                    action = options[selected_opt]
                                    break
                                elif p_event.key == pygame.K_ESCAPE:
                                    action = options[0] # 按ESC默认继续
                                    break
                                elif p_event.key == pygame.K_f and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                                    g.show_fps = not g.show_fps
                        
                        if action:
                            break
                        g.clock.tick(60)
                        
                    if "Exit" in action:
                        pygame.mixer.music.stop()
                        return "exit"
                    elif "Restart" in action:
                        pygame.mixer.music.stop()
                        return "restart"
                    else: # Continue
                        # 继续有三秒倒计时
                        count_start = pygame.time.get_ticks()
                        while True:
                            now = pygame.time.get_ticks()
                            elp = now - count_start
                            if elp >= 3000:
                                break
                                
                            g.screen.fill((30, 30, 30))
                            for x in LANES:
                                pygame.draw.line(g.screen, (100, 100, 100), (x, 0), (x, g.SCREEN_HEIGHT), 2)
                            pygame.draw.line(g.screen, (255, 0, 0), (0, 500), (g.SCREEN_WIDTH, 500), 5)
                            
                            # 渲染暂停时刻的音符（不包含漏判变化逻辑，纯粹静态渲染屏幕上可见的音符）
                            for i in range(active_idx, len(notes_data)):
                                note = notes_data[i]
                                if (note["time"] - current_time) * eff_speed > g.SCREEN_HEIGHT + 100:
                                    break
                                
                                if not note["hit"]:
                                    note_type = note.get("type", "tap")
                                    x = LANES[note["lane"]]
                                    
                                    if note_type == "tap":
                                        y = 500 - (note["time"] - current_time) * eff_speed
                                        if -50 < y < g.SCREEN_HEIGHT:
                                            color = (100, 100, 100) if note["missed"] else (0, 200, 255)
                                            pygame.draw.rect(g.screen, color, (x - 40, y - 10, 80, 20))
                                            
                                    elif note_type == "hold":
                                        if "stuck_y" in note:
                                            if note.get("holding"):
                                                head_y = note["stuck_y"]
                                            elif "release_time" in note:
                                                head_y = note["stuck_y"] + (current_time - note["release_time"]) * eff_speed
                                            else:
                                                head_y = 500 - (note["time"] - current_time) * eff_speed
                                        else:
                                            head_y = 500 - (note["time"] - current_time) * eff_speed
                                        
                                        tail_y = 500 - (note["end_time"] - current_time) * eff_speed
                                        
                                        # 强转为整型以避免浮点数在 pygame 矩形渲染时引发的边框 1 像素上下抖动
                                        int_head_y = int(head_y)
                                        int_tail_y = int(tail_y)
                                        
                                        rect_y = int_tail_y
                                        rect_h = int_head_y - int_tail_y
                                        
                                        if rect_h > 0 and int_tail_y < g.SCREEN_HEIGHT and int_head_y > -50:
                                            if note.get("holding"):
                                                color = (150, 255, 150)
                                            elif note["missed"]:
                                                color = (80, 100, 80)
                                            else:
                                                color = (0, 255, 100)
                                            pygame.draw.rect(g.screen, color, (x - 40, rect_y, 80, rect_h))

                            # 顶部横幅UI（由于谱面可能出现在顶部，也需要遮挡一下）
                            pygame.draw.rect(g.screen, (0, 0, 0), (0, 0, g.SCREEN_WIDTH, 40))
                            pygame.draw.line(g.screen, (200, 200, 200), (0, 40), (g.SCREEN_WIDTH, 40), 2)
                            
                            # 在重新开始倒数阶段也绘制进度条
                            progress_percentage = min(1.0, max(0.0, current_time / total_duration))
                            progress_width = int(g.SCREEN_WIDTH * progress_percentage)
                            pygame.draw.rect(g.screen, (50, 50, 50), (0, 0, g.SCREEN_WIDTH, 4))
                            pygame.draw.rect(g.screen, (100, 200, 255), (0, 0, progress_width, 4))
                            
                            cnum = 3 - (elp // 1000)
                            if cnum > 0:
                                text = g.font.render(str(cnum), True, (255, 255, 255))
                                g.screen.blit(text, (g.SCREEN_WIDTH // 2 - text.get_width() // 2, g.SCREEN_HEIGHT // 2 - text.get_height() // 2))
                                
                            if g.show_fps:
                                fps_text = g.small_font.render(f"FPS: {int(g.clock.get_fps())}", True, (255, 100, 100))
                                g.screen.blit(fps_text, (10, g.SCREEN_HEIGHT - 30))
                                
                            g.update_display()
                            for ev in pygame.event.get():
                                if ev.type == pygame.QUIT:
                                    pygame.quit()
                                    sys.exit()
                            g.clock.tick(60)
                        
                        # 修正在暂停和倒计时期间流逝的时间
                        pause_end_time = pygame.time.get_ticks()
                        start_time += (pause_end_time - pause_start_time)
                        
                        # 同步current_time否则刚刚过去一帧可能会突变
                        real_elapsed_time = pygame.time.get_ticks() - start_time
                        current_time = real_elapsed_time * song_rate - map_offset - global_offset - LEAD_IN_TIME
                        
                        if current_time >= 0 and music_started:
                            pygame.mixer.music.unpause()
                        # 需要跳过这个事件循环中由于暂停产生的堆积事件，可以直接continue跳过剩下的KEYDOWN处理
                        continue

                # 判断按键是否是有效键
                elif event.key in g.KEY_MAP:
                    lane_pressed = g.KEY_MAP[event.key]
                    
                    # 过滤出该轨道的可用音符, 且不要把正在按住(holding)的长条再次判定
                    valid_notes = []
                    for i in range(active_idx, len(notes_data)):
                        n = notes_data[i]
                        if n["lane"] == lane_pressed and not n["hit"] and not n["missed"] and not n.get("holding", False):
                            valid_notes.append(n)
                            # 考虑到音符已经整体排序，我们只需要看距离当前最近的少数几个就行了，不必完全遍历
                            if len(valid_notes) > 3:
                                break
                    valid_notes.sort(key=lambda x: x["time"])
                    
                    if valid_notes:
                        target_note = valid_notes[0]
                        time_diff = abs(target_note["time"] - current_time)
                        
                        if time_diff <= MISS_WINDOW:
                            if time_diff <= PERFECT_WINDOW:
                                judgement_text = "PERFECT"
                                score += 1000
                                perfect_count += 1
                            elif time_diff <= GREAT_WINDOW:
                                judgement_text = "GREAT"
                                score += 750
                                good_count += 1
                            elif time_diff <= MISS_WINDOW:
                                judgement_text = "MISS"
                                combo = 0
                                target_note["missed"] = True
                                miss_count += 1
                                
                            if not target_note["missed"]:
                                combo += 1
                                if target_note.get("type", "tap") == "tap":
                                    target_note["hit"] = True
                                elif target_note.get("type") == "hold":
                                    target_note["holding"] = True # 长条变成了被按住的状态
                                    # 记录按下的瞬间底部的Y坐标
                                    target_note["stuck_y"] = 500 - (target_note["time"] - current_time) * eff_speed

            elif event.type == pygame.KEYUP:
                if event.key in g.KEY_MAP:
                    lane_released = g.KEY_MAP[event.key]
                    
                    # 寻找该轨道正在被按住（holding）的长条音符
                    holding_notes = [notes_data[i] for i in range(active_idx, len(notes_data)) if notes_data[i].get("holding") and notes_data[i]["lane"] == lane_released and not notes_data[i]["hit"] and not notes_data[i]["missed"]]
                    if holding_notes:
                        target_note = holding_notes[0]
                        target_note["holding"] = False # 解除按住状态
                        
                        # 检查松手的时机是否接近长条结尾
                        time_diff = abs(target_note["end_time"] - current_time)
                        if time_diff <= PERFECT_WINDOW:
                            judgement_text = "PERFECT"
                            score += 1000
                            perfect_count += 1
                            combo += 1
                            target_note["hit"] = True 
                        elif time_diff <= GREAT_WINDOW:
                            judgement_text = "GREAT"
                            score += 750
                            good_count += 1
                            combo += 1
                            target_note["hit"] = True 
                        else:
                            judgement_text = "MISS"
                            combo = 0
                            miss_count += 1
                            target_note["missed"] = True
                            target_note["release_time"] = current_time # 记录断开的时间，为了让它从冻结的位置继续掉落

        # 画 4 条轨道线
        for x in LANES:
            pygame.draw.line(g.screen, (100, 100, 100), (x, 0), (x, g.SCREEN_HEIGHT), 2)
        
        # 画判定线
        pygame.draw.line(g.screen, (255, 0, 0), (0, 500), (g.SCREEN_WIDTH, 500), 5)

        # --- 核心：处理底漏与渲染音符 ---
        # 性能优化1：剔除那些已经玩过（被接住或者漏掉）且已经完全掉出屏幕外的陈年老音符
        while active_idx < len(notes_data):
            old_note = notes_data[active_idx]
            nt = old_note.get("end_time", old_note["time"])
            # 如果它已经被判定过，并且以当前速度下落已经远远超过并离开屏幕视口（屏幕高600，落到800外即为不可见）
            if (old_note["hit"] or old_note["missed"]) and (current_time - nt) * eff_speed > 300:
                active_idx += 1
            else:
                break
                
        for i in range(active_idx, len(notes_data)):
            note = notes_data[i]
            
            # 性能优化2：对于几秒之后远在天边的未来音符，不进行任何坐标和遮挡计算，直接打断当帧计算循环
            # 这项优化保证了一帧 300Hz 的循环从计算 3000 次骤降到只算屏幕里的几十次
            if (note["time"] - current_time) * eff_speed > g.SCREEN_HEIGHT + 100:
                break

            note_type = note.get("type", "tap")
            
            # 底部漏判检测
            if note_type == "tap":
                if not note["hit"] and not note["missed"] and current_time - note["time"] > MISS_WINDOW:
                    note["missed"] = True
                    judgement_text = "MISS"
                    combo = 0
                    miss_count += 1
                    
            elif note_type == "hold":
                if not note["hit"]:
                    # 如果没接住长条头
                    if not note["missed"] and not note.get("holding") and current_time - note["time"] > MISS_WINDOW:
                        note["missed"] = True
                        judgement_text = "MISS"
                        combo = 0
                        miss_count += 1

                    # 如果长条按穿（按超时）还没有松手，视为通过或是完美判定
                    elif note.get("holding") and current_time >= note["end_time"]:
                        note["hit"] = True 
                        note["holding"] = False
                        judgement_text = "PERFECT"
                        score += 1000
                        perfect_count += 1
                        combo += 1
                
            # 渲染 (即便是 miss 的音符，只要没流出屏幕也继续渲染)
            if not note["hit"]:
                x = LANES[note["lane"]]
                
                if note_type == "tap":
                    y = 500 - (note["time"] - current_time) * eff_speed
                    if -50 < y < g.SCREEN_HEIGHT:
                        # 如果错过了，可以画得暗一点表示它被 miss 了
                        color = (100, 100, 100) if note["missed"] else (0, 200, 255)
                        pygame.draw.rect(g.screen, color, (x - 40, y - 10, 80, 20))
                        
                elif note_type == "hold":
                    # 如果长条按下了，用按下瞬间锁死的 Y 坐标；如果中途松手 miss 了，让剩下来的一小截从松手位置以正常速度掉出屏幕外
                    if "stuck_y" in note:
                        if note.get("holding"):
                            head_y = note["stuck_y"]
                        elif "release_time" in note:
                            head_y = note["stuck_y"] + (current_time - note["release_time"]) * eff_speed
                        else:
                            head_y = 500 - (note["time"] - current_time) * eff_speed
                    else:
                        head_y = 500 - (note["time"] - current_time) * eff_speed
                    
                    # 计算长条尾部的位置，由于松手与否不影响长条本身的物理时常，它照常流逝即可
                    tail_y = 500 - (note["end_time"] - current_time) * eff_speed
                    
                    # 强转为整型以避免浮点数在 pygame 矩形渲染时引发的边框 1 像素上下抖动
                    int_head_y = int(head_y)
                    int_tail_y = int(tail_y)
                    
                    rect_y = int_tail_y
                    rect_h = int_head_y - int_tail_y
                    
                    # 防越界绘制反向矩形 (只要还没有吃到头就画)
                    if rect_h > 0 and int_tail_y < g.SCREEN_HEIGHT and int_head_y > -50:
                        # 被按住的时候高亮，miss掉的时候变灰，正常掉落的时候是绿色
                        if note.get("holding"):
                            color = (150, 255, 150) # 更亮
                        elif note["missed"]:
                            color = (80, 100, 80) # 灰绿
                        else:
                            color = (0, 255, 100) # 正常绿
                        pygame.draw.rect(g.screen, color, (x - 40, rect_y, 80, rect_h))

        # --- 顶部横幅UI显示 (黑条防遮挡) ---
        pygame.draw.rect(g.screen, (0, 0, 0), (0, 0, g.SCREEN_WIDTH, 40)) # 顶部黑色背景条
        pygame.draw.line(g.screen, (200, 200, 200), (0, 40), (g.SCREEN_WIDTH, 40), 2) # 分界线
        
        combo_display = g.small_font.render(f"Combo: {combo}", True, (255, 255, 0))
        g.screen.blit(combo_display, (10, 10))
        
        processed_notes = perfect_count + good_count + miss_count
        acc = (score / (processed_notes * 1000) * 100) if processed_notes > 0 else 100.0
        acc_display = g.small_font.render(f"ACC: {acc:.2f}%", True, (0, 255, 255))
        g.screen.blit(acc_display, (g.SCREEN_WIDTH - acc_display.get_width() - 10, 10))

        # 进度条
        progress_percentage = min(1.0, max(0.0, current_time / total_duration))
        progress_width = int(g.SCREEN_WIDTH * progress_percentage)
        # 底色
        pygame.draw.rect(g.screen, (50, 50, 50), (0, 0, g.SCREEN_WIDTH, 4))
        # 实际进度
        pygame.draw.rect(g.screen, (100, 200, 255), (0, 0, progress_width, 4))
        
        # --- 游玩前倒计时的核心屏幕文字渲染 ---
        if current_time < 0:
            import math
            countdown_num = math.ceil(abs(current_time) / 1000)
            if countdown_num > 0:
                text = g.font.render(str(countdown_num), True, (255, 255, 255))
                g.screen.blit(text, (g.SCREEN_WIDTH // 2 - text.get_width() // 2, g.SCREEN_HEIGHT // 2 - text.get_height() // 2))

        # 渲染判定文字 (居中显示在上方)
        if "judgement_text" in locals() and judgement_text:
            judge_display = g.font.render(judgement_text, True, (0, 255, 100))
            g.screen.blit(judge_display, (g.SCREEN_WIDTH // 2 - judge_display.get_width() // 2, 200))

        if g.show_fps:
            fps_text = g.small_font.render(f"FPS: {int(g.clock.get_fps())}", True, (255, 100, 100))
            g.screen.blit(fps_text, (10, g.SCREEN_HEIGHT - 30))

        g.update_display() # 刷新屏幕
        g.clock.tick(0) # 彻底解除帧率限制，让游戏火力全开飙到多高是多高 (0表示不限速)

        # 检查游戏是否结束 (只需要判定剔除指针是不是推到了最后即可，这可以彻底省去每秒90万次的 all() 迭代)
        if active_idx == len(notes_data) and len(notes_data) > 0:
            if current_time > total_duration + 1500: # 留 1.5 秒余量
                break

    import datetime
    
    # === 结算界面 ===
    # 提取以备显示使用的乐曲基础名字
    base_song_name = os.path.splitext(os.path.basename(map_path))[0]
    bg_surf = g.load_bg_image(map_path, map_data)
    
    # === 记录历史成绩 ===
    acc = (score / (total_judgments * 1000) * 100.0) if total_judgments > 0 else 100.0
    rel_path = os.path.relpath(map_path, start=os.getcwd()).replace("\\", "/")
    
    if rel_path not in g.history_data:
        g.history_data[rel_path] = []
        
    record = {
        "score": score,
        "acc": acc,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rate": song_rate
    }
    
    g.history_data[rel_path].append(record)
    # 按分数从高到低排序，保留前 10 个
    g.history_data[rel_path].sort(key=lambda x: x["score"], reverse=True)
    if len(g.history_data[rel_path]) > 10:
        g.history_data[rel_path] = g.history_data[rel_path][:10]
        
    g.save_history()
    
    while True:
        # 改成实色背景
        g.screen.fill((40, 40, 60))
            
        title = g.font.render("=== 结算 ===", True, (255, 255, 255))
        # 将标题稍微往上挪，避免和接下来的曲绘图片挤在一起
        g.screen.blit(title, (g.SCREEN_WIDTH // 2 - title.get_width() // 2, 15))
        
        # 增加初始的高度偏移量，给图片留出宽裕的排版像素
        y_offset = 70
        
        if bg_surf:
            bg_x = g.SCREEN_WIDTH // 2 - bg_surf.get_width() // 2
            g.screen.blit(bg_surf, (bg_x, y_offset))
            # 画一个小边框
            pygame.draw.rect(g.screen, (200, 200, 200), (bg_x, y_offset, bg_surf.get_width(), bg_surf.get_height()), 2)
            y_offset += bg_surf.get_height() + 15
        else:
            y_offset += 20
        
        acc = (score / (total_judgments * 1000) * 100) if total_judgments > 0 else 100.0
        
        # Determine the color of Rate based on normal or edited
        rate_str = f"{song_rate:.1f}x"
        
        lines = [
            f"谱面: {base_song_name}",
            f"倍速: {rate_str}",
            f"Score: {score}",
            f"ACC: {acc:.2f}%",
            f"PERFECT 完美: {perfect_count}",
            f"GOOD 良好: {good_count}",
            f"MISS: {miss_count}",
            "",
            "Press ENTER to return"
        ]
        
        # 使用跑马灯渲染所有文本，防止覆盖或超出屏幕
        for line in lines:
            if not line:
                y_offset += 32
                continue
                
            if "谱面:" in line:
                g.draw_marquee_text(g.screen, line, g.tiny_font, (150, 200, 255), g.SCREEN_WIDTH // 2, y_offset, g.SCREEN_WIDTH - 40)
                y_offset += 32
            else:
                if "倍速:" in line:
                    color = (255, 200, 200) if song_rate != 1.0 else (200, 200, 200)
                else:
                    color = (200, 255, 200) if "Score" in line or "ACC" in line else (200, 200, 200)
                
                g.draw_marquee_text(g.screen, line, g.small_font, color, g.SCREEN_WIDTH // 2, y_offset, g.SCREEN_WIDTH - 40)
                y_offset += 32
            
        if g.show_fps:
            fps_text = g.small_font.render(f"FPS: {int(g.clock.get_fps())}", True, (255, 100, 100))
            g.screen.blit(fps_text, (10, g.SCREEN_HEIGHT - 30))
            
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    g.show_fps = not g.show_fps
                if event.key == pygame.K_RETURN:
                    return
        
        g.update_display()
        g.clock.tick(60)

