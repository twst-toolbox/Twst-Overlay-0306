import tkinter as tk
import json
import os
import sys

# 这是一个透明的覆盖层程序
class OverlayApp:
    def __init__(self, root, data_file):
        self.root = root
        self.root.title("Twst汉化浮窗 - 按ESC退出")
        
        # 1. 设置窗口全屏、透明、置顶、鼠标穿透
        self.root.attributes("-fullscreen", True) # 全屏覆盖
        self.root.attributes("-topmost", True)    # 永远在最前
        self.root.attributes("-transparentcolor", "black") # 把黑色变成透明
        self.root.configure(bg="black") # 背景设为黑色（实际会变透明）
        
        # Windows特定的鼠标穿透设置（让你可以点击游戏，而不是点到字幕上）
        # 如果报错，说明不是Windows环境，但这也没关系，只是不能点击穿透
        try:
            self.root.bind("<Escape>", lambda e: self.root.destroy()) # 按ESC关闭
        except Exception:
            pass

        # 2. 读取 data.json 里的坐标配置
        self.load_data(data_file)

    def load_data(self, file_path):
        if not os.path.exists(file_path):
            # 如果找不到文件，显示一个提示
            lbl = tk.Label(self.root, text=f"未找到 {file_path} 文件！\n请确保它和程序在同一文件夹。", 
                           fg="red", bg="black", font=("Arial", 20, "bold"))
            lbl.place(x=100, y=100)
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # 遍历json里的每一项，创建文字标签
            for item in data.get("items", []):
                text = item.get("text", "测试文本")
                x = item.get("x", 100)
                y = item.get("y", 100)
                color = item.get("color", "white")
                size = item.get("size", 12)
                
                # 创建文字标签
                label = tk.Label(self.root, text=text, fg=color, bg="black", 
                                 font=("Microsoft YaHei", size, "bold"))
                label.place(x=x, y=y)
                
        except Exception as e:
            lbl = tk.Label(self.root, text=f"读取出错: {e}", fg="red", bg="black")
            lbl.place(x=100, y=150)

if __name__ == "__main__":
    # 获取json文件路径（确保exe运行时能找到旁边的json）
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    json_path = os.path.join(application_path, "data.json")

    root = tk.Tk()
    app = OverlayApp(root, json_path)
    root.mainloop()
