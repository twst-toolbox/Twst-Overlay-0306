import tkinter as tk
import json
import os
import sys
import asyncio
import threading
import time
import ctypes
from io import BytesIO
from PIL import Image, ImageGrab

# 引入 Windows 原生 OCR 库
try:
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.globalization import Language
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
except ImportError:
    pass

# 设置 DPI 感知
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

class WindowsOCRHelper:
    def __init__(self):
        self.engine = None
        # 注意：OCR引擎最好在调用它的线程里初始化，或者确保线程安全
        # 我们会在工作线程里懒加载它

    def init_engine(self):
        if self.engine: return
        try:
            lang = Language("ja-JP")
            if not OcrEngine.is_language_supported(lang):
                self.engine = OcrEngine.try_create_from_user_profile_languages()
            else:
                self.engine = OcrEngine.try_create_from_language(lang)
        except Exception as e:
            print(f"引擎初始化失败: {e}")

    async def recognize_pil_image(self, pil_image):
        if not self.engine:
            self.init_engine()
        
        if not self.engine:
            return ""
        
        try:
            mem_stream = InMemoryRandomAccessStream()
            writer = DataWriter(mem_stream.get_output_stream_at(0))
            
            byte_io = BytesIO()
            pil_image.save(byte_io, format='PNG')
            writer.write_bytes(byte_io.getvalue())
            await writer.store_async()
            await writer.flush_async()
            
            decoder = await BitmapDecoder.create_async(mem_stream)
            software_bitmap = await decoder.get_software_bitmap_async()
            result = await self.engine.recognize_async(software_bitmap)
            return result.text
        except Exception as e:
            print(f"识别出错: {e}")
            return ""

class OverlayApp:
    def __init__(self, root, data_file):
        self.root = root
        self.root.title("Twst OCR Overlay")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.configure(bg="black")
        
        # 绑定退出键
        self.root.bind("<Escape>", lambda e: self.quit_app())

        self.ocr_helper = WindowsOCRHelper()
        self.labels = {}
        self.tasks = []
        self.running = True # 控制线程开关
        
        self.load_data(data_file)
        
        # --- 关键修改：启动一个后台线程专门做 OCR ---
        # daemon=True 表示主程序关闭时，这个线程也会自动死掉
        self.worker_thread = threading.Thread(target=self.start_worker, daemon=True)
        self.worker_thread.start()

    def quit_app(self):
        self.running = False
        self.root.destroy()

    def load_data(self, file_path):
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = data.get("tasks", [])
                
                for i, task in enumerate(self.tasks):
                    # 初始状态文字设为空，不显示 Waiting，免得挡视线
                    lbl = tk.Label(self.root, text="", 
                                   fg=task.get("text_color", "white"), 
                                   bg="black", 
                                   font=("Microsoft YaHei", 15, "bold"))
                    lbl.place(x=task["display_x"], y=task["display_y"])
                    self.labels[i] = lbl

    # 这是后台线程运行的函数，绝对不会卡住界面
    def start_worker(self):
        # 在线程里创建一个新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                # 运行 OCR 任务
                loop.run_until_complete(self.process_all_tasks())
                
                # 休息 1 秒 (避免 CPU 占用率太高)
                time.sleep(1) 
            except Exception as e:
                print(f"线程出错: {e}")
                time.sleep(1)

    async def process_all_tasks(self):
        for i, task in enumerate(self.tasks):
            if not self.running: break
            
            region = task["ocr_region"]
            keywords = task.get("keywords", {})
            
            # 1. 截图 (比较快)
            try:
                screenshot = ImageGrab.grab(bbox=(region[0], region[1], region[2], region[3]))
            except Exception:
                continue

            # 2. 识别 (最耗时的一步，现在在后台跑)
            text_result = await self.ocr_helper.recognize_pil_image(screenshot)
            
            # 3. 处理文本
            clean_text = text_result.replace(" ", "").replace("\n", "")
            
            # 如果识别出了文字，在控制台打印一下，方便你调试
            if clean_text:
                print(f"识别到 [{task.get('name')}]: {clean_text}")

            display_text = ""
            for ja_key, cn_value in keywords.items():
                if ja_key in clean_text:
                    display_text = cn_value
                    break
            
            # 如果没匹配到字典，但有字，显示原文以便调试 (你可以注释掉这行)
            if not display_text and clean_text:
                display_text = clean_text 

            # 4. 通知主界面更新 (线程安全的方式)
            # 我们不能直接在线程里改界面，要告诉主线程去改
            self.update_label_safe(i, display_text)

    def update_label_safe(self, index, text):
        # 使用 after(0) 可以在主线程里执行 GUI 更新
        self.root.after(0, lambda: self.labels[index].config(text=text))

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        app_path = os.path.dirname(sys.executable)
    else:
        app_path = os.path.dirname(os.path.abspath(__file__))
    
    json_path = os.path.join(app_path, "data.json")
    root = tk.Tk()
    app = OverlayApp(root, json_path)
    root.mainloop()
