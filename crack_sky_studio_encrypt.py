import io
import json
import os
import shutil
import subprocess
import time
import chardet
import easyocr
import numpy as np
from PIL import Image
from platformdirs import user_desktop_dir

resultList = []
falseCount = 0
# 检查各区域是否满足条件
background_color = (24, 24, 24)  # #181818 的 RGB 值
sheet_input_direct = r"D:\Desktop\encrypted"
mumu_direct = r"C:\Users\WindH\Documents\MuMu共享文件夹"

# 检查 ADB 是否安装
def check_adb():
    try:
        subprocess.run(["adb", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print("ADB 已安装。")
    except FileNotFoundError:
        print("请先安装 ADB 并确保其加入环境变量。")
        exit(1)

# 检查设备是否连接
def check_device():
    result = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    devices = result.stdout.strip().split("\n")[1:]  # 第一行为表头
    connected_devices = [line.split("\t")[0] for line in devices if "device" in line]
    if not connected_devices:
        print("未检测到任何设备，请确保设备已连接并启用调试模式。")
        exit(1)
    print(f"检测到设备：{connected_devices[0]}")
    return connected_devices[0]

def screenshot_and_check_colors_optimized(device, areas):
    screenshot_path = "/sdcard/screen.png"
    global falseCount
    # 在设备中截图
    subprocess.run(["adb", "-s", device, "shell", "screencap", "-p", screenshot_path], check=True)
    result = subprocess.run(
        ["adb", "-s", device, "exec-out", f"cat {screenshot_path}"],
        stdout=subprocess.PIPE,
        check=True
    )
    subprocess.run(["adb", "-s", device, "shell", "rm", screenshot_path], check=True)

    # 打开截图并转换为 RGB
    img = Image.open(io.BytesIO(result.stdout)).convert("RGB")
    pixels = img.load()

    key_status = {}

    for key, area in areas.items():
        x1, y1, x2, y2 = area
        has_non_background = False
        for x in range(x1, x2):
            for y in range(y1, y2):
                if pixels[x, y] != background_color:
                    has_non_background = True
                    break
            if has_non_background:
                break
        key_status[key] = has_non_background
        if not any(key_status.values()):
            falseCount += 1
        else:
            falseCount = 0
        print(falseCount)
    return key_status


def screenshot_and_ocr_bmp_number(device, area):
    screenshot_path = "/sdcard/screen.png"
    subprocess.run(["adb", "-s", device, "shell", "screencap", "-p", screenshot_path], check=True)
    result = subprocess.run(
        ["adb", "-s", device, "exec-out", f"cat {screenshot_path}"],
        stdout=subprocess.PIPE,
        check=True
    )
    subprocess.run(["adb", "-s", device, "shell", "rm", screenshot_path], check=True)
    # 打开截图并转换为 RGB
    img = Image.open(io.BytesIO(result.stdout)).convert("RGB")
    x1, y1, x2, y2 = area
    cropped_img = img.crop((x1, y1, x2, y2))
    # 将 PIL 图像转换为 NumPy 数组
    cropped_img_np = np.array(cropped_img)
    # 使用 EasyOCR 进行数字识别
    reader = easyocr.Reader(['en'])  # 只加载英文模型
    result = reader.readtext(cropped_img_np, detail=0, allowlist='0123456789')  # 这里加 allowlist
    return result


def detect_encoding(file_path):
    """检测文件编码"""
    with open(file_path, 'rb') as f:
        raw_data = f.read(1024)  # 读取部分数据进行检测
    result = chardet.detect(raw_data)
    return result['encoding']

# 点击设备屏幕的指定位置 (x, y)
def next_button(device):
    subprocess.run(["adb", "-s", device, "shell", "input", "tap", str(240.7), str(429.3)], check=True)

def parse_result_list(result_list, bpm):
    # 每节拍时长（毫秒）
    beat_duration_ms = (60 / bpm) * 1000  # 将秒转化为毫秒
    parsed_result = []

    # 解析结果
    for i, beat in enumerate(result_list):
        active_keys = [key for key, is_active in beat.items() if is_active]

        # 如果有多个按键同时按下，时间戳相同
        if active_keys:
            timestamp = round(i * beat_duration_ms)
            key_count = len(active_keys)  # 统计当前时间点的按键数量
            for key in active_keys:
                parsed_result.append({
                    "time": timestamp,  # 所有按键的时间戳相同
                    "key": f"{key_count}Key{key.replace('key', '')}"  # 格式化为 "NKeyX"（N是按键数量，X是按键编号）
                })
    # 按时间戳排序
    parsed_result.sort(key=lambda x: x['time'])
    return parsed_result


def main():
    check_adb()
    device = check_device()

    # 定义各按键的区域
    key_areas = {
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
    }

    # 定义固定按钮
    menu_buttons = {
        "open_sheet": (441.7, 354.5),
        "import_sheet": (1191.0, 333.5),
        "import_sheet_more": (61.9, 95.9),
        "import_sheet_mumu_shared": (215.6, 597.5),
        "import_sheet_file_select": (203.6, 967.2),
        "go_to_in_sheet": (368.7, 347.5),
        "end_options": (1194.0, 424.3),
        "end_exit_to_main": (647.5, 510.2),
        "end_exit_to_main_confirm": (517.5, 271.6),
        "bpm_area": (91.9, 586.2, 137.8, 607.2),
    }

    files = os.listdir(sheet_input_direct)
    # 逐个复制文件
    for file_name in files:
        source_file = os.path.join(sheet_input_direct, file_name)

        encoding = detect_encoding(source_file)
        if encoding is None:
            print(f"无法检测编码，跳过文件: {source_file}")
            continue

        with open(source_file, 'r', encoding=encoding) as f:
            data = json.load(f)
        songName = data[0].get("name")
        if songName is None:
            print("没有获取到歌曲名字 跳过")
            continue

        print(f"开始处理文件{songName}")
        destination_file = os.path.join(mumu_direct, file_name)
        shutil.copy(source_file, destination_file)
        subprocess.run(["adb", "-s", device, "shell", "input", "tap", str(menu_buttons["open_sheet"][0]), str(menu_buttons["open_sheet"][1])], check=True)
        time.sleep(0.5)
        subprocess.run(["adb", "-s", device, "shell", "input", "tap", str(menu_buttons["import_sheet"][0]), str(menu_buttons["import_sheet"][1])], check=True)
        time.sleep(1.5)
        subprocess.run(["adb", "-s", device, "shell", "input", "tap", str(menu_buttons["import_sheet_more"][0]), str(menu_buttons["import_sheet_more"][1])], check=True)
        time.sleep(2)
        subprocess.run(["adb", "-s", device, "shell", "input", "tap", str(menu_buttons["import_sheet_mumu_shared"][0]), str(menu_buttons["import_sheet_mumu_shared"][1])], check=True)
        time.sleep(2)
        subprocess.run(["adb", "-s", device, "shell", "input", "tap", str(menu_buttons["import_sheet_file_select"][0]), str(menu_buttons["import_sheet_file_select"][1])], check=True)
        time.sleep(1.5)
        subprocess.run(["adb", "-s", device, "shell", "input", "tap", str(menu_buttons["go_to_in_sheet"][0]), str(menu_buttons["go_to_in_sheet"][1])], check=True)
        time.sleep(0.5)
        ocr = screenshot_and_ocr_bmp_number(device, menu_buttons["bpm_area"])
        if len(ocr) != 1:
            continue

        bpm = ocr[0]
        while True:
            key_status = screenshot_and_check_colors_optimized(device, key_areas)
            resultList.append(key_status)
            next_button(device)
            if falseCount >= 200:
                break
        print(resultList)
        output = [
            {
              "name": songName,
              "author": "crack for WindHide",
              "transcribedBy": "WindHide crack",
              "bpm": bpm,
              "bitsPerPage": 15,
              "pitchLevel": 0,
              "isComposed": True,
              "songNotes": parse_result_list(resultList, bpm),  # 将解析后的结果放入 songNotes 字段
              "isEncrypted": False,
            }
        ]
        output_file = os.path.join(user_desktop_dir(), "crack" , f"{songName}.txt")
        with open(output_file, "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=4)
        os.remove(destination_file)

if __name__ == "__main__":
    main()
