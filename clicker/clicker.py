import customtkinter as ctk
from tkinter import messagebox, PhotoImage
import threading
import time
from pynput import mouse, keyboard
import json
import os
import sys
from PIL import ImageTk


class ProfessionalClicker:
    def __init__(self):
        # 设置CustomTkinter外观模式和颜色主题
        ctk.set_appearance_mode("Light")  # 明亮主题
        ctk.set_default_color_theme("blue")  # 蓝色主题

        self.root = ctk.CTk()
        self.root.title("键鼠连点器")
        self.root.geometry("500x500")
        self.root.resizable(False, False)

        # 设置窗口图标
        # 获取图标文件路径（支持打包后从资源中读取）
        icon_path = self.resource_path('icon.png')
        
        # 更安全的方式加载图标
        try:
            # 创建PhotoImage对象
            self.iconpath = ImageTk.PhotoImage(file=icon_path)
            # 先调用wm_iconbitmap
            self.root.wm_iconbitmap()
            # 再设置iconphoto
            self.root.iconphoto(False, self.iconpath)
        except Exception as e:
            # 如果无法加载图标，使用默认设置
            print(f"设置图标时发生错误：{e}")

        # 控制器
        self.mouse_ctrl = mouse.Controller()
        self.kb_ctrl = keyboard.Controller()

        # 核心变量
        self.running = False
        self.mode = ctk.StringVar(value="mouse")  # 'mouse' 或 'keyboard'
        self.target_mouse_btn = mouse.Button.left
        self.target_kb_key = keyboard.KeyCode.from_char('a')  # 默认设置为字符'a'
        self.hotkey = keyboard.Key.f8
        self.click_count = 0

        self.setup_ui()

        # 加载配置（在UI创建后调用）
        self.load_config()

        # 启动线程
        threading.Thread(target=self.click_worker, daemon=True).start()
        threading.Thread(target=self.start_hotkey_listener, daemon=True).start()

        # 注册窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        # 主框架
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=10)
        self.main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        # 标题
        title_label = ctk.CTkLabel(
            self.main_frame,
            text="🖱️ 键鼠连点器",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#1F6AA5"
        )
        title_label.pack(pady=(15, 10))

        # 第一排：模式选择和间隔设置
        row1_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row1_frame.pack(pady=5, padx=20, fill="x")

        # 左侧：模式选择
        mode_frame = ctk.CTkFrame(row1_frame, corner_radius=10)
        mode_frame.pack(side="left", padx=(0, 10), fill="both", expand=True)

        mode_label = ctk.CTkLabel(
            mode_frame,
            text="🖱️模式选择",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        mode_label.pack(pady=(10, 5), padx=10, fill="x")

        mode_buttons_frame = ctk.CTkFrame(mode_frame, fg_color="transparent")
        mode_buttons_frame.pack(pady=5, padx=10, fill="x")

        self.mouse_mode_button = ctk.CTkRadioButton(
            mode_buttons_frame,
            text="🖱️鼠标",
            variable=self.mode,
            value="mouse",
            font=ctk.CTkFont(size=12),
            command=self.on_mode_change
        )
        self.mouse_mode_button.pack(side="left", padx=(0, 10))

        self.keyboard_mode_button = ctk.CTkRadioButton(
            mode_buttons_frame,
            text="⌨️键盘",
            variable=self.mode,
            value="keyboard",
            font=ctk.CTkFont(size=12),
            command=self.on_mode_change
        )
        self.keyboard_mode_button.pack(side="left")

        # 右侧：间隔设置
        delay_frame = ctk.CTkFrame(row1_frame, corner_radius=10)
        delay_frame.pack(side="right", padx=(10, 0), fill="both", expand=True)

        delay_label = ctk.CTkLabel(
            delay_frame,
            text="⏱️ 间隔设置",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        delay_label.pack(pady=(10, 5), padx=10, fill="x")

        delay_input_frame = ctk.CTkFrame(delay_frame, fg_color="transparent")
        delay_input_frame.pack(pady=5, padx=10, fill="x")

        ctk.CTkLabel(
            delay_input_frame,
            text="间隔(s):",
            font=ctk.CTkFont(size=12)
        ).pack(side="left")

        self.entry_delay = ctk.CTkEntry(
            delay_input_frame,
            width=70,
            justify="center",
            font=ctk.CTkFont(size=12)
        )
        self.entry_delay.insert(0, "0.1")
        self.entry_delay.pack(side="right")

        # 第二排：按键设置
        key_frame = ctk.CTkFrame(self.main_frame, corner_radius=10)
        key_frame.pack(pady=10, padx=20, fill="x")

        key_label = ctk.CTkLabel(
            key_frame,
            text="🔑 按键设置",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        key_label.pack(pady=(10, 5), padx=10, fill="x")

        # 当前配置显示
        self.label_current = ctk.CTkLabel(
            key_frame,
            text="当前配置: 鼠标左键",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1F6AA5"
        )
        self.label_current.pack(pady=5)

        # 录制按钮
        self.btn_capture = ctk.CTkButton(
            key_frame,
            text="⏺️ 录制按键",
            command=self.capture_key,
            height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8
        )
        self.btn_capture.pack(pady=10, padx=15, fill="x")

        # 第三排：运行状态
        status_frame = ctk.CTkFrame(self.main_frame, corner_radius=10)
        status_frame.pack(pady=10, padx=20, fill="x")

        status_label = ctk.CTkLabel(
            status_frame,
            text="📊 运行状态",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        status_label.pack(pady=(10, 5), padx=10, fill="x")

        # 状态指示器和控制按钮在同一行
        status_control_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        status_control_frame.pack(pady=10, padx=10, fill="x")

        # 状态指示器
        self.status_indicator = ctk.CTkLabel(
            status_control_frame,
            text="🔴 已停止",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#E74C3C"
        )
        self.status_indicator.pack(side="left")

        # 快捷键提示
        hotkey_label = ctk.CTkLabel(
            status_control_frame,
            text="(F8切换)",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        hotkey_label.pack(side="left", padx=(5, 0))

        # 控制按钮
        self.toggle_button = ctk.CTkButton(
            status_control_frame,
            text="▶️ 开始",
            command=self.toggle_running,
            width=80,
            height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8,
            fg_color="#2ECC71",
            hover_color="#27AE60"
        )
        self.toggle_button.pack(side="right")

        # 底部：统计信息和提示
        footer_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        footer_frame.pack(pady=(10, 5), fill="x")

        self.stats_label = ctk.CTkLabel(
            footer_frame,
            text="已点击: 0 次",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.stats_label.pack(side="left", padx=20)

        # 添加保存配置按钮
        save_button = ctk.CTkButton(
            footer_frame,
            text="💾 保存配置",
            command=lambda: self.save_config(True),
            width=80,
            height=25,
            font=ctk.CTkFont(size=12),
            corner_radius=6
        )
        save_button.pack(side="right", padx=20)

    def on_mode_change(self):
        """当模式改变时的回调函数"""
        pass  # 可以在这里添加模式切换时的逻辑

    def toggle_running(self):
        """切换运行状态"""
        self.running = not self.running
        if self.running:
            self.toggle_button.configure(
                text="⏹️ 停止",
                fg_color="#E74C3C",
                hover_color="#C0392B"
            )
            self.status_indicator.configure(
                text="🟢 运行中",
                text_color="#2ECC71"
            )
        else:
            self.toggle_button.configure(
                text="▶️ 开始",
                fg_color="#2ECC71",
                hover_color="#27AE60"
            )
            self.status_indicator.configure(
                text="🔴 已停止",
                text_color="#E74C3C"
            )

    def capture_key(self):
        """根据当前模式录制特定的按键"""
        mode = self.mode.get()
        self.btn_capture.configure(text=f"⏳ 请按键...", state="disabled")

        def on_press(key):
            if self.mode.get() == 'keyboard':
                self.target_kb_key = key
                # 处理不同类型的按键显示
                if isinstance(key, keyboard.KeyCode):
                    key_name = key.char if key.char else str(key)
                else:
                    key_name = key.name if hasattr(key, 'name') else str(key).replace('Key.', '')
                self.root.after(0, lambda: self.update_display(f"⌨️ 键盘键: {key_name}"))
            return False

        def on_click(x, y, button, pressed):
            if pressed and self.mode.get() == 'mouse':
                self.target_mouse_btn = button
                self.root.after(0, lambda: self.update_display(f"🖱️ 鼠标键: {button.name}"))
                return False

        # 根据模式开启不同的监听器
        if mode == 'keyboard':
            keyboard.Listener(on_press=on_press).start()
        else:
            mouse.Listener(on_click=on_click).start()

    def update_display(self, text):
        self.label_current.configure(text=text)
        self.btn_capture.configure(text="⏺️ 录制按键", state="normal")

    def click_worker(self):
        """执行点击逻辑"""
        while True:
            if self.running:
                try:
                    delay = float(self.entry_delay.get())
                except:
                    delay = 0.1

                if self.mode.get() == 'mouse':
                    self.mouse_ctrl.click(self.target_mouse_btn, 1)
                else:
                    # 修改部分：增加按键维持时间
                    self.kb_ctrl.press(self.target_kb_key)
                    # 给游戏引擎留出反应时间，通常 0.03-0.05秒 足够
                    time.sleep(0.05)
                    self.kb_ctrl.release(self.target_kb_key)

                # 更新点击次数
                self.click_count += 1
                self.root.after(0, lambda: self.stats_label.configure(text=f"已点击: {self.click_count} 次"))

                # 确保总间隔减去维持时间，防止频率变慢
                sleep_time = max(0.001, delay - 0.05 if self.mode.get() == 'keyboard' else delay)
                time.sleep(sleep_time)
            else:
                time.sleep(0.1)

    def start_hotkey_listener(self):
        with keyboard.Listener(on_press=self.handle_hotkey) as listener:
            listener.join()

    def handle_hotkey(self, key):
        if key == self.hotkey:
            self.toggle_running()

    def save_config(self, show_message=True):
        """保存配置到文件"""
        # 准备键盘按键的序列化表示
        kb_key_data = {}
        if isinstance(self.target_kb_key, keyboard.KeyCode):
            kb_key_data = {
                "type": "KeyCode",
                "vk": self.target_kb_key.vk,
                "char": self.target_kb_key.char
            }
        else:  # Key 类型
            kb_key_data = {
                "type": "Key",
                "name": self.target_kb_key.name if hasattr(self.target_kb_key, 'name') else str(
                    self.target_kb_key).replace('Key.', '')
            }

        config = {
            "mode": self.mode.get(),
            "delay": self.entry_delay.get(),
            "target_kb_key": kb_key_data,
            "target_mouse_btn_name": self.target_mouse_btn.name if hasattr(self.target_mouse_btn, 'name') else 'left'
        }

        try:
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            # 只有在show_message为True时才显示消息框
            if show_message:
                messagebox.showinfo("成功", "配置已保存!")
        except Exception as e:
            # 只有在show_message为True时才显示错误消息框
            if show_message:
                messagebox.showerror("错误", f"保存配置失败: {str(e)}")
            else:
                print(f"保存配置失败: {str(e)}")

    def load_config(self):
        """从文件加载配置"""
        if not os.path.exists('config.json'):
            # 设置默认显示
            self.label_current.configure(text="当前配置: 鼠标左键")
            return

        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 加载配置
            self.mode.set(config.get("mode", "mouse"))
            self.entry_delay.delete(0, "end")
            self.entry_delay.insert(0, config.get("delay", "0.1"))

            # 加载鼠标按键设置
            mouse_btn_name = config.get("target_mouse_btn_name", "left")
            if hasattr(mouse.Button, mouse_btn_name):
                self.target_mouse_btn = getattr(mouse.Button, mouse_btn_name)
            else:
                self.target_mouse_btn = mouse.Button.left

            # 加载键盘按键设置
            kb_key_data = config.get("target_kb_key", {})
            if kb_key_data:
                if kb_key_data.get("type") == "KeyCode":
                    vk = kb_key_data.get("vk")
                    char = kb_key_data.get("char")
                    if vk is not None:
                        self.target_kb_key = keyboard.KeyCode.from_vk(vk)
                    elif char:
                        self.target_kb_key = keyboard.KeyCode.from_char(char)
                    else:
                        self.target_kb_key = keyboard.KeyCode.from_char('a')
                elif kb_key_data.get("type") == "Key":
                    key_name = kb_key_data.get("name", "f8")
                    if hasattr(keyboard.Key, key_name):
                        self.target_kb_key = getattr(keyboard.Key, key_name)
                    else:
                        self.target_kb_key = keyboard.Key.f8
                else:
                    self.target_kb_key = keyboard.KeyCode.from_char('a')

            # 更新显示
            mode = self.mode.get()
            if mode == "mouse":
                self.label_current.configure(text=f"当前配置: 鼠标{self.target_mouse_btn.name}键")
            else:
                # 显示键盘按键
                if isinstance(self.target_kb_key, keyboard.KeyCode):
                    key_name = self.target_kb_key.char if self.target_kb_key.char else str(self.target_kb_key)
                else:
                    key_name = self.target_kb_key.name if hasattr(self.target_kb_key, 'name') else str(
                        self.target_kb_key).replace('Key.', '')
                self.label_current.configure(text=f"当前配置: 键盘{key_name}")

        except Exception as e:
            print(f"加载配置失败: {str(e)}")
            # 使用默认值
            self.mode.set("mouse")
            self.entry_delay.delete(0, "end")
            self.entry_delay.insert(0, "0.1")
            self.target_mouse_btn = mouse.Button.left
            self.target_kb_key = keyboard.KeyCode.from_char('a')
            self.label_current.configure(text="当前配置: 鼠标左键")

    def resource_path(self, relative_path):
        """获取资源的绝对路径，用于支持PyInstaller打包后的资源访问"""
        try:
            # PyInstaller创建临时文件夹，并将路径存储在_MEIPASS中
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        
        return os.path.join(base_path, relative_path)

    def on_closing(self):
        """窗口关闭事件"""
        self.save_config(show_message=False)
        self.root.destroy()

def main():
    app = ProfessionalClicker()
    app.root.mainloop()


if __name__ == "__main__":
    main()