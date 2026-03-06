import tkinter as tk
import json
import os
import sys
import asyncio
import ctypes
from io import BytesIO
from PIL import Image, ImageGrab

# 引入 Windows 原生 OCR 库
# 如果报错，说明打包时没装 winsdk，但我们会在 build.yml 里解决
try:
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.globalization import Language
    from winsdk.windows.graphics.imaging import BitmapDecoder, SoftwareBitmap
    from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
except ImportError:
    print("请确保安装了 winsdk 库")

# 设置 DPI 感知，防止截图位置偏移（高分屏必备）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

class WindowsOCRHelper:
    def __init__(self):
        # 尝试初始化日语引擎
        lang = Language("ja-JP")
        if not OcrEngine.is_language_supported(lang):
            print("警告：你的电脑可能没装日语语音包！将尝试使用默认语言。")
            self.engine = OcrEngine.try_create_from_user_profile_languages()
        else:
            self.engine = OcrEngine.try_create_from_language(lang)

    async def recognize_pil_image(self, pil_image):
        if not self.engine:
            return ""
        
        # 将 PIL 图片转换为 Windows 能读的 SoftwareBitmap
        # 这是一个比较繁琐的过程，但必须这么做
        mem_stream = InMemoryRandomAccessStream()
        writer = DataWriter(mem_stream.get_output_stream_at(0))
        
        # 把图片存入内存流
        byte_io = BytesIO()
        pil_image.save(byte_io, format='PNG')
        writer.write_bytes(byte_io.getvalue())
        await writer.store_async()
        await writer.flush_async()
        
        # 解码并识别
        decoder = await BitmapDecoder.create_async(mem_stream)
        software_bitmap = await decoder.get_software_bitmap_async()
        result = await self.engine.recognize_async(software_bitmap)
        
        return result.text

class OverlayApp:
    def __init__(self, root, data_file):
        self.root = root
        self.root.title("Twst OCR Overlay")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.configure(bg="black")
        
        try:
            self.root.bind("<Escape>", lambda e: self.root.destroy())
        except: pass

        self.ocr_helper = WindowsOCRHelper()
        self.labels = {} # 存储显示的标签控件
        self.tasks = []
        
        self.load_data(data_file)
        
        # 开启自动循环任务：每 2 秒扫描一次
        self.root.after(2000, self.update_ocr_loop)

    def load_data(self, file_path):
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = data.get("tasks", [])
                
                # 初始化标签
                for i, task in enumerate(self.tasks):
                    lbl = tk.Label(self.root, text="Waiting...", 
                                   fg=task.get("text_color", "white"), 
                                   bg="black", 
                                   font=("Microsoft YaHei", 15, "bold"))
                    # 先把标签藏起来，识别到了再显示
                    lbl.place(x=task["display_x"], y=task["display_y"])
                    self.labels[i] = lbl

    def update_ocr_loop(self):
        # 这是一个异步转同步的小技巧，为了在 tkinter 里跑异步代码
        asyncio.run(self.process_all_tasks())
        # 继续下一轮循环
        self.root.after(2000, self.update_ocr_loop)

    async def process_all_tasks(self):
        for i, task in enumerate(self.tasks):
            region = task["ocr_region"] # [左, 上, 右, 下]
            keywords = task.get("keywords", {})
            
            # 1. 截图
            # 注意：ImageGrab 截取的是 (左, 上, 右, 下)
            screenshot = ImageGrab.grab(bbox=(region[0], region[1], region[2], region[3]))
            
            # 2. OCR 识别
            text_result = await self.ocr_helper.recognize_pil_image(screenshot)
            
            # 3. 匹配关键词（只要包含关键词就翻译）
            display_text = ""
            # 去掉空格和换行，方便匹配
            clean_text = text_result.replace(" ", "").replace("\n", "")
            
            print(f"区域 {task['name']} 识别结果: {clean_text}") # 调试用，控制台可见

            for ja_key, cn_value in keywords.items():
                if ja_key in clean_text:
                    display_text = cn_value
                    break
            
            # 如果没匹配到字典，你可以选择显示原文，或者什么都不显示
            # 这里我设置为：如果识别到了文字但没匹配到，就显示原文（方便你测试区域对不对）
            if not display_text and clean_text:
                display_text = clean_text 

            # 4. 更新界面
            if display_text:
                self.labels[i].config(text=display_text)
            else:
                self.labels[i].config(text="") # 没字就清空

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        app_path = os.path.dirname(sys.executable)
    else:
        app_path = os.path.dirname(os.path.abspath(__file__))
    
    json_path = os.path.join(app_path, "data.json")
    root = tk.Tk()
    app = OverlayApp(root, json_path)
    root.mainloop()
