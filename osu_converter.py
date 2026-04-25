import json
import math
import sys
import os
import re
import tkinter as tk
import tkinter as tk
from tkinter import filedialog, messagebox
import locale
locale.setlocale(locale.LC_ALL, '')


# Monkey-patch messagebox for native Linux zenity
import subprocess
import shutil

_orig_showerror = messagebox.showerror
_orig_showwarning = messagebox.showwarning
_orig_showinfo = messagebox.showinfo

def _native_dialog(msg_type, title, text):
    if sys.platform.startswith('linux') and shutil.which('zenity'):
        try:
            zenity_type = f"--{msg_type}" if msg_type in ["info", "warning", "error"] else "--info"
            subprocess.run([
                'zenity', zenity_type,
                f"--title={title}",
                f"--text={text}",
                "--no-wrap"
            ])
            return
        except Exception:
            pass
            
    # root needs to exist
    root = tk._default_root if getattr(tk, "_default_root", None) else tk.Tk()
    if root and hasattr(root, "withdraw"): root.withdraw()
    
    if msg_type == "error": return _orig_showerror(title, text)
    if msg_type == "warning": return _orig_showwarning(title, text)
    return _orig_showinfo(title, text)

messagebox.showerror = lambda title, text: _native_dialog("error", title, text)
messagebox.showwarning = lambda title, text: _native_dialog("warning", title, text)
messagebox.showinfo = lambda title, text: _native_dialog("info", title, text)

def unescape_unicode(s):
    # 将由于某些不规范的抓取或生成工具留在 .osu 中的 \uXXXX 字符转回正常的中文/Unicode字符
    return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)

def convert_osu_to_json(osu_file_path):
    if not os.path.exists(osu_file_path):
        messagebox.showerror("错误", f"找不到文件 {osu_file_path}")
        return

    try:
        with open(osu_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        messagebox.showerror("读取错误", f"无法读取文件: {e}")
        return

    meta = {
        "song": "audio.mp3",
        "bg": "",
        "offset": 0,    
        "bpm": 120     
    }
    notes = []

    current_section = None
    circle_size = 4
    found_bpm = False

    for line in lines:
        line = line.strip()
        # 清理类似 \u5f55 的纯字符串形式 unicode 转义序列
        line = unescape_unicode(line)
        
        if not line or line.startswith('//'):
            continue
        
        if line.startswith('['):
            current_section = line
            continue

        if current_section == '[General]':
            if line.startswith('AudioFilename:'):
                meta["song"] = line.split(':', 1)[1].strip()

        elif current_section == '[Difficulty]':
            if line.startswith('CircleSize:'):
                circle_size = int(float(line.split(':')[1].strip()))

        elif current_section == '[Events]':
            parts = line.split(',')
            if len(parts) >= 3 and parts[0] == '0' and parts[1] == '0':
                bg_name = parts[2].strip('"')
                meta["bg"] = bg_name

        elif current_section == '[TimingPoints]':
            parts = line.split(',')
            if len(parts) >= 2 and not found_bpm:
                beat_length = float(parts[1])
                if beat_length > 0:
                    bpm = round(60000 / beat_length, 2)
                    meta["bpm"] = bpm
                    found_bpm = True 

        elif current_section == '[HitObjects]':
            parts = line.split(',')
            if len(parts) >= 5:
                x = int(float(parts[0]))
                time = int(float(parts[2]))
                note_type_flag = int(parts[3])
                
                lane = math.floor((x * circle_size) / 512)
                lane = max(0, min(lane, circle_size - 1))

                is_hold = (note_type_flag & 128) > 0
                
                if is_hold and len(parts) >= 6:
                    end_time_str = parts[5].split(':')[0]
                    notes.append({
                        "type": "hold",
                        "time": time,
                        "end_time": int(float(end_time_str)),
                        "lane": lane
                    })
                else:
                    notes.append({
                        "type": "tap",
                        "time": time,
                        "lane": lane
                    })

    # 包装最终字典
    map_data = {
        "meta": meta,
        "notes": notes
    }

    base_name = os.path.splitext(osu_file_path)[0]
    output_json_path = f"{base_name}.json"

    try:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(map_data, f, indent=4, ensure_ascii=False)
            
        return {
            "success": True,
            "song": meta['song'],
            "bg": meta.get('bg', '无'),
            "notes_count": len(notes),
            "output_json": os.path.basename(output_json_path),
            "circle_size": circle_size
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

import zipfile
import shutil
import subprocess

def show_native_dialog(msg_type, title, text):
    # msg_type: "info", "warning", "error"
    if sys.platform.startswith('linux') and shutil.which('zenity'):
        try:
            # zenity doesn't use the same newline behavior reliably without --no-wrap, 
            # and --text needs to be clean.
            zenity_type = f"--{msg_type}" if msg_type in ["info", "warning", "error"] else "--info"
            subprocess.run([
                'zenity', zenity_type,
                f"--title={title}",
                f"--text={text}",
                "--no-wrap"
            ])
            return
        except Exception:
            pass
            
    # Fallback to tkinter
    # 确保主窗口环境存在
    root = tk._default_root if tk._default_root else tk.Tk()
    if root: root.withdraw()
        
    if msg_type == "error":
        messagebox.showerror(title, text)
    elif msg_type == "warning":
        messagebox.showwarning(title, text)
    else:
        messagebox.showinfo(title, text)

def handle_osu_file(file_path):
    result = convert_osu_to_json(file_path)
    if result and result.get("success"):
        msg = f"✨ 成功转换 osu 谱面!\n\n目标音乐: {result['song']}\n背景图片: {result['bg']}\n音符数量: {result['notes_count']}\n输出文件: {result['output_json']}"
        if result['circle_size'] != 4:
            msg += f"\n\n警告: 这是一个 {result['circle_size']}K 的谱面，可能会出现越界。"
        messagebox.showinfo("转换成功", msg)
    elif result:
        messagebox.showerror("保存错误", f"保存 JSON 失败: {result.get('error')}")

def handle_osz_file(file_path):
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # 默认解压到当前目录的 songs 文件夹下
    songs_dir = os.path.join(os.getcwd(), "songs")
    if not os.path.exists(songs_dir):
        os.makedirs(songs_dir)
        
    target_dir = os.path.join(songs_dir, base_name)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
    except Exception as e:
        messagebox.showerror("解压错误", f"无法解压 .osz 文件: {e}")
        return

    osu_files = [f for f in os.listdir(target_dir) if f.endswith('.osu')]
    if not osu_files:
        messagebox.showwarning("警告", f"在 {base_name} 中没有找到任何 .osu 谱面文件！")
        return
        
    success_count = 0
    for osu_file in osu_files:
        osu_full_path = os.path.join(target_dir, osu_file)
        res = convert_osu_to_json(osu_full_path)
        if res and res.get("success"):
            success_count += 1
            
    messagebox.showinfo("批量转换成功", f"✨ 成功导入曲包！\n\n曲包名: {base_name}\n成功转换难度数: {success_count}/{len(osu_files)}\n\n曲包已存放至: songs/{base_name}")

import subprocess
import shutil

def select_and_convert():
    # 提前初始化 Tk root 并隐藏，防止后续使用 messagebox 时弹出空白主窗口
    root = tk.Tk()
    root.withdraw()
    
    file_path = None
    zenity_attempted = False
    
    # 优先在 Linux 上使用原生的 Zenity/GTK 对话框
    if sys.platform.startswith('linux') and shutil.which('zenity'):
        try:
            zenity_attempted = True
            result = subprocess.run([
                'zenity', '--file-selection', 
                '--title=选择 .osz 或 .osu 谱面文件',
                '--file-filter=osu map files | *.osz *.osu',
                '--file-filter=All files | *'
            ], capture_output=True, text=True)
            if result.returncode == 0:
                file_path = result.stdout.strip()
        except Exception:
            # 如果崩溃了可以再让 Tkinter 顶上
            zenity_attempted = False

    # 如果没有 Zenity 或者是在 Windows/Mac 上，亦或是 Zenity 启动失败，才回退使用 Tkinter
    # 注意：如果 zenity 启动成功但用户自己点了【取消】，也不应该再弹 Tkinter 了
    if not zenity_attempted and not file_path:
        file_path = filedialog.askopenfilename(
            title="选择 .osz 或 .osu 谱面文件",
            filetypes=[("osu map files", "*.osz *.osu"), ("All files", "*.*")]
        )
        
    if not file_path:
        root.destroy()
        return
        
    if file_path.lower().endswith('.osz') or file_path.lower().endswith('.zip'):
        handle_osz_file(file_path)
    else:
        handle_osu_file(file_path)
    
    # 保持主循环直到弹窗结束
    root.destroy()

if __name__ == "__main__":
    select_and_convert()
