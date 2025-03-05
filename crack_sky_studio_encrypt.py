import io
import json
import os
import shutil
import subprocess
import time
import chardet
import numpy as np
from PIL import Image
from platformdirs import user_desktop_dir

# 全局变量
resultList = []
falseCount = 0
background_color = (24, 24, 24)  # #181818 的 RGB 值
sheet_input_direct = r"D:\Desktop\encrypted"
mumu_direct = r"C:\Users\WindH\Documents\MuMu共享文件夹"

def delete_files_in_directory(directory):
    # 遍历指定目录下的所有文件和文件夹
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            # 删除文件
            os.remove(file_path)

def run_adb(command):
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)


def check_adb():
    try:
        run_adb(["adb", "--version"])
        print("ADB 已安装。")
    except FileNotFoundError:
        print("请先安装 ADB 并确保其加入环境变量。")
        exit(1)


def check_device():
    result = run_adb(["adb", "devices"])
    devices = [line.split("\t")[0] for line in result.stdout.strip().split("\n")[1:] if "device" in line]
    if not devices:
        print("未检测到任何设备，请确保设备已连接并启用调试模式。")
        exit(1)
    print(f"检测到设备：{devices[0]}")
    return devices[0]


def capture_screenshot(device):
    screenshot_path = "/sdcard/screen.png"
    subprocess.run(["adb", "-s", device, "shell", "screencap", "-p", screenshot_path], check=True)

    result = subprocess.run(["adb", "-s", device, "exec-out", f"cat {screenshot_path}"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    if not result.stdout:
        raise RuntimeError("Failed to capture screenshot: empty output")

    try:
        img = Image.open(io.BytesIO(result.stdout)).convert("RGB")
    except Exception as e:
        raise RuntimeError(f"Error loading image: {e}")

    return img


def screenshot_and_check_colors(device, areas):
    """ 截取屏幕并检查特定区域的颜色 """
    global falseCount
    img = capture_screenshot(device)
    pixels = img.load()
    key_status = {key: pixels[(x1 + x2) // 2, (y1 + y2) // 2] != background_color for key, (x1, y1, x2, y2) in areas.items()}
    falseCount = falseCount + 15 if not any(key_status.values()) else 0
    return key_status

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        return chardet.detect(f.read(1024))['encoding']


def next_button(device):
    run_adb(["adb", "-s", device, "shell", "input", "tap", "240", "429"])


def parse_result_list(result_list, bpm):
    beat_duration_ms = (60 / bpm) * 1000
    parsed_result = []
    for i, beat in enumerate(result_list):
        active_keys = [key for key, is_active in beat.items() if is_active]
        if active_keys:
            timestamp = round(i * beat_duration_ms)
            for key in active_keys:
                parsed_result.append({"time": timestamp, "key": f"{len(active_keys)}Key{key.replace('key', '')}"})
    return sorted(parsed_result, key=lambda x: x['time'])


def process_files(device, key_areas, menu_buttons):
    files = os.listdir(sheet_input_direct)
    global resultList
    global falseCount
    for file_name in files:
        resultList = []
        falseCount = 0
        source_file = os.path.join(sheet_input_direct, file_name)
        encoding = detect_encoding(source_file)
        if not encoding:
            print(f"无法检测编码，跳过文件: {source_file}")
            continue
        try:
            with open(source_file, 'r', encoding=encoding) as f:
                data = json.load(f)
        except Exception as e:
            print(f"跳过本文件处理错误 -> {source_file}")
            continue

        songName = data[0].get("name")
        if not songName:
            print("没有获取到歌曲名字 跳过")
            continue
        bpm = data[0].get("bpm")
        if not bpm:
            print("没有获取到bpm 跳过")
            continue

        print(f"开始处理文件 {songName}")
        destination_file = os.path.join(mumu_direct, file_name)
        shutil.copy(source_file, destination_file)

        for key in ["open_sheet", "import_sheet", "import_sheet_more", "import_sheet_mumu_shared", "import_sheet_file_select", "go_to_in_sheet"]:
            run_adb(["adb", "-s", device, "shell", "input", "tap", str(menu_buttons[key][0]), str(menu_buttons[key][1])])
            time.sleep(1)


        while True:
            key_status = screenshot_and_check_colors(device, key_areas)
            resultList.append(key_status)
            next_button(device)
            if falseCount >= 280:
                break

        output_file = os.path.join(user_desktop_dir(), "crack", f"{songName}.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump([{ "name": songName, "author": "crack for WindHide", "transcribedBy": "WindHide crack", "bpm": int(bpm), "bitsPerPage": 15, "pitchLevel": 0, "isComposed": True, "songNotes": parse_result_list(resultList, int(bpm)), "isEncrypted": False }], f, ensure_ascii=False, indent=4)

        delete_files_in_directory(mumu_direct)
        print(f"处理完成->{songName}")
        for key in ["end_options", "end_exit_to_main", "end_exit_to_main_confirm"]:
            time.sleep(1)
            run_adb(["adb", "-s", device, "shell", "input", "tap", str(menu_buttons[key][0]), str(menu_buttons[key][1])])
            time.sleep(1)

def main():
    check_adb()
    device = check_device()
    key_areas =  {
        "key0": (381, 381, 410, 399),   # y
        "key1": (508, 379, 532, 398),   # u
        "key2": (625, 379, 655, 399),   # i
        "key3": (746, 379, 772, 399),   # o
        "key4": (868, 379, 889, 399),   # p
        "key5": (385, 500, 414, 520),   # h
        "key6": (508, 500, 533, 520),   # j
        "key7": (630, 500, 657, 520),   # k
        "key8": (752, 500, 772, 520),   # l
        "key9": (863, 500, 893, 520),  # ;
        "key10": (384, 617, 416, 639),  # n
        "key11": (506, 617, 536, 639),  # m
        "key12": (628, 617, 655, 639),  # ,
        "key13": (750, 617, 771, 639),  # .
        "key14": (866, 617, 896, 639)   # /
    }  # 按键区域
    menu_buttons = {
        "open_sheet": (441.7, 354.5),
        "import_sheet": (1191.0, 333.5),
        "import_sheet_more": (61.9, 95.9),
        "import_sheet_mumu_shared": (215.6, 597.5),
        "import_sheet_file_select": (203.6, 967.2),
        "go_to_in_sheet": (368.7, 347.5),
        "end_options": (1194.0, 424.3),
        "end_exit_to_main": (647.5, 510.2),
        "end_exit_to_main_confirm": (517.5, 271.6)
    }  # 菜单按钮区域
    process_files(device, key_areas, menu_buttons)


if __name__ == "__main__":
    start_time = time.time()  # 记录开始时间
    main()
    end_time = time.time()  # 记录结束时间
    execution_time = end_time - start_time  # 计算执行时间
