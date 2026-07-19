import sys
import time
import json
import os
from pathlib import Path

# ================= 自动修复 Qt 平台插件路径 =================
# 解决 PyCharm/conda 环境下 "no Qt platform plugin could be initialized" 问题
_qt_plugins = Path(__file__).parent / ".venv" / "Lib" / "site-packages" / "PyQt5" / "Qt5" / "plugins" / "platforms"
if _qt_plugins.exists() and "QT_QPA_PLATFORM_PLUGIN_PATH" not in os.environ:
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(_qt_plugins.parent)

from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QThread, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QFrame, QLabel, QStackedWidget, QButtonGroup, 
                             QPushButton, QSlider, QComboBox, QGraphicsOpacityEffect)
from PyQt5.QtGui import QFont, QMouseEvent, QIcon

# ================= 去除 Windows DWM 窗口白边/阴影 =================
if sys.platform == "win32":
    import ctypes

    # DWM 常量
    DWMWA_NCRENDERING_POLICY = 2   # 非客户区渲染策略
    DWMWA_BORDER_COLOR = 34         # 边框颜色 (Win10 1903+)
    DMNCRP_DISABLED = 1             # 禁用非客户区渲染

    _dwmapi = ctypes.windll.dwmapi

    def remove_window_border(hwnd):
        """禁用 DWM 边框渲染 + 透明边框"""
        policy = ctypes.c_int(DMNCRP_DISABLED)
        _dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_NCRENDERING_POLICY,
            ctypes.byref(policy), ctypes.sizeof(policy))
        # 边框颜色设为透明 (0xFFFFFFFF)
        color = ctypes.c_int(0xFFFFFFFF)
        _dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_BORDER_COLOR,
            ctypes.byref(color), ctypes.sizeof(color))
from pynput import mouse, keyboard

# ================= 获取标准的系统级用户配置路径 =================
def get_config_path():
    app_name = "MNKClicker"
    # Windows: %APPDATA%\MNKClicker
    base_dir = os.getenv('APPDATA', os.path.expanduser('~'))
    config_dir = os.path.join(base_dir, app_name)
    
    # 确保目录存在
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'config.json')

# ================= 全局输入监听中心 =================
class GlobalInputManager(QThread):
    sig_input = pyqtSignal(object)
    
    def run(self):
        def on_kb_press(key):
            self.sig_input.emit(key)
        def on_mouse_click(x, y, button, pressed):
            if pressed: self.sig_input.emit(button)

        with keyboard.Listener(on_press=on_kb_press) as k_listener, \
             mouse.Listener(on_click=on_mouse_click) as m_listener:
            k_listener.join()
            m_listener.join()

# ================= 连点器后台引擎 =================
class ClickerWorker(QThread):
    sig_stats = pyqtSignal(int)
    
    def __init__(self, mode='mouse'):
        super().__init__()
        self.mode = mode
        self.running = False
        self.clicks_per_second = 100
        self.target_mouse_btn = mouse.Button.left
        self.target_kb_key = keyboard.KeyCode.from_char('a')
        self.mouse_ctrl = mouse.Controller()
        self.kb_ctrl = keyboard.Controller()
        self.click_count = 0
        
    def run(self):
        while True:
            if self.running:
                delay = 1.0 / max(1, self.clicks_per_second)
                if self.mode == 'mouse':
                    self.mouse_ctrl.click(self.target_mouse_btn, 1)
                else:
                    self.kb_ctrl.press(self.target_kb_key)
                    self.msleep(int(min(20, delay * 500)))
                    self.kb_ctrl.release(self.target_kb_key)
                
                self.click_count += 1
                if self.click_count % max(1, int(self.clicks_per_second / 10)) == 0 or delay > 0.05:
                    self.sig_stats.emit(self.click_count)
                
                sleep_ms = int(max(1, (delay - (0.02 if self.mode == 'keyboard' else 0)) * 1000))
                self.msleep(sleep_ms)
            else:
                self.msleep(50)

# ================= 颜色常量 =================
COLORS = {
    "bg_main":      "#F0F2F5",
    "bg_card":      "#FFFFFF",
    "bg_sidebar":   "#202223",
    "bg_sidebar_h": "#2A2C2E",
    "accent":       "#25AFF5",
    "accent_hover": "#1B9DE0",
    "accent_press": "#1488C7",
    "accent_light": "#E8F7FE",
    "text_dark":    "#1A1C1E",
    "text_mid":     "#5A5E62",
    "text_light":   "#8A8E92",
    "text_white":   "#FFFFFF",
    "border":       "#E0E3E6",
    "border_h":     "#C0C4C8",
    "red":          "#FF5F56",
    "yellow":       "#FFBD2E",
    "green":        "#27C93F",
    "danger":       "#E5484D",
    "danger_hover": "#CD2B31",
    "stop_bg":      "#E5484D",
    "stop_hover":   "#CD2B31",
    "stop_press":   "#B5252A",
}

def qss_rounded_frame(bg, border=None, radius=10):
    b = f"border: 1px solid {border};" if border else "border: none;"
    return f"QFrame {{ background-color: {bg}; border-radius: {radius}px; {b} }}"

# ================= UI：带有模式切换动画的通用连点页面 =================
class BaseClickerPage(QFrame):
    def __init__(self, title, icon, input_mgr, is_mouse_mode=True, parent=None):
        super().__init__(parent)
        self.is_mouse_mode = is_mouse_mode
        self.trigger_key = keyboard.Key.f8
        self.is_capturing = False
        self.capture_start_time = 0
        self.capture_type = None
        
        self.worker = ClickerWorker('mouse' if is_mouse_mode else 'keyboard')
        self.worker.sig_stats.connect(self.update_stats)
        self.worker.start()
        
        self.input_mgr = input_mgr
        self.input_mgr.sig_input.connect(self.handle_global_input)
        
        self.setup_ui(title, icon)
        self.connect_signals()

    def setup_ui(self, title, icon):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 8, 28, 28)

        # --- 主卡片 ---
        self.card = QFrame()
        self.card.setObjectName("MainCard")
        self.card.setStyleSheet(f"""
            QFrame#MainCard {{
                background-color: {COLORS['bg_card']};
                border-radius: 14px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(32, 24, 32, 28)
        card_layout.setSpacing(18)

        # --- 标题行 ---
        title_layout = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size: 22px; color: {COLORS['accent']}; background: transparent; border: none;")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLORS['accent']}; background: transparent; border: none;")
        title_layout.addWidget(icon_lbl)
        title_layout.addWidget(title_lbl)
        title_layout.addStretch(1)
        card_layout.addLayout(title_layout)

        # --- 分隔线 ---
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {COLORS['border']}; border: none;")
        card_layout.addWidget(line)

        # --- 模式选择器 ---
        self.modes_container = QFrame()
        self.modes_container.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_main']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        self.modes_container.setFixedHeight(56)
        
        self.mode_highlight = QFrame(self.modes_container)
        self.mode_highlight.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['accent_light']};
                border: 1px solid {COLORS['accent']};
                border-radius: 6px;
            }}
        """)
        
        modes_layout = QHBoxLayout(self.modes_container)
        modes_layout.setContentsMargins(4, 4, 4, 4)
        modes_layout.setSpacing(4)
        
        self.mode_group = QButtonGroup(self)
        self.btn_fast = QPushButton("⚡ 快速模式\n(1秒100次)")
        self.btn_extreme = QPushButton("🚀 极速模式\n(1秒200次)")
        self.btn_custom = QPushButton("⚙️ 自定义\n(拖动滑块)")
        
        mode_btn_qss = f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLORS['text_mid']};
                font-size: 13px;
                font-weight: bold;
                outline: none;
            }}
            QPushButton:checked {{
                color: {COLORS['accent']};
            }}
        """
        for i, btn in enumerate([self.btn_fast, self.btn_extreme, self.btn_custom]):
            btn.setStyleSheet(mode_btn_qss)
            btn.setCheckable(True)
            self.mode_group.addButton(btn, i)
            modes_layout.addWidget(btn)
        self.btn_fast.setChecked(True)
        card_layout.addWidget(self.modes_container)

        # --- 速度滑块 ---
        speed_layout = QVBoxLayout()
        speed_top = QHBoxLayout()
        lbl_spd = QLabel("点击速度:")
        lbl_spd.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 13px; background: transparent; border: none;")
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, 200)
        self.slider.setValue(100)
        self.slider.setStyleSheet(f"""
            QSlider {{
                background: {COLORS['bg_card']};
                border: none;
            }}
            QSlider::groove:horizontal {{
                border: none;
                height: 6px;
                background: {COLORS['border']};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {COLORS['accent']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {COLORS['bg_card']};
                border: 2px solid {COLORS['accent']};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {COLORS['accent_light']};
            }}
        """)
        speed_top.addWidget(lbl_spd)
        speed_top.addWidget(self.slider)
        
        self.lbl_speed_val = QLabel("100次/秒")
        self.lbl_speed_val.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 12px; padding-left: 65px; background: transparent; border: none;")
        speed_layout.addLayout(speed_top)
        speed_layout.addWidget(self.lbl_speed_val)
        card_layout.addLayout(speed_layout)

        # --- 按键设置行 ---
        settings_row = QHBoxLayout()
        lbl_trigger = QLabel("开关按键:")
        self.btn_trigger = QPushButton("F8键")
        self.btn_trigger.setFixedSize(110, 34)
        
        lbl_target = QLabel("点击模式:" if self.is_mouse_mode else "目标按键:")
        if self.is_mouse_mode:
            self.combo_target = QComboBox()
            self.combo_target.addItems(["左键单击", "右键单击", "中键单击"])
            self.combo_target.setFixedSize(110, 34)
            self.target_widget = self.combo_target
        else:
            self.btn_target = QPushButton("A键")
            self.btn_target.setFixedSize(110, 34)
            self.target_widget = self.btn_target

        setting_btn_qss = f"""
            QPushButton, QComboBox {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border_h']};
                border-radius: 6px;
                color: {COLORS['text_dark']};
                font-size: 13px;
                font-weight: bold;
                outline: none;
            }}
            QPushButton:hover, QComboBox:hover {{
                background-color: {COLORS['bg_main']};
                border-color: {COLORS['accent']};
            }}
            QPushButton:pressed {{
                padding-top: 2px;
                padding-left: 1px;
                background-color: {COLORS['border']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_light']};
                border-color: {COLORS['border']};
            }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
        """
        self.btn_trigger.setStyleSheet(setting_btn_qss)
        self.target_widget.setStyleSheet(setting_btn_qss)
        lbl_trigger.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 13px; background: transparent; border: none;")
        lbl_target.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 13px; background: transparent; border: none;")

        settings_row.addWidget(lbl_trigger)
        settings_row.addWidget(self.btn_trigger)
        settings_row.addStretch(1)
        settings_row.addWidget(lbl_target)
        settings_row.addWidget(self.target_widget)
        card_layout.addLayout(settings_row)

        # --- 启动/停止按钮 ---
        self.btn_toggle = QPushButton("▶  启动连点")
        self.btn_toggle.setFixedSize(160, 46)
        self.toggle_qss_start = f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: {COLORS['text_white']};
                border-radius: 10px;
                font-weight: bold;
                font-size: 15px;
                border: none;
                outline: none;
            }}
            QPushButton:hover {{ background-color: {COLORS['accent_hover']}; }}
            QPushButton:pressed {{ padding-top: 2px; background-color: {COLORS['accent_press']}; }}
        """
        self.toggle_qss_stop = f"""
            QPushButton {{
                background-color: {COLORS['stop_bg']};
                color: {COLORS['text_white']};
                border-radius: 10px;
                font-weight: bold;
                font-size: 15px;
                border: none;
                outline: none;
            }}
            QPushButton:hover {{ background-color: {COLORS['stop_hover']}; }}
            QPushButton:pressed {{ padding-top: 2px; background-color: {COLORS['stop_press']}; }}
        """
        self.btn_toggle.setStyleSheet(self.toggle_qss_start)
        card_layout.addWidget(self.btn_toggle, 0, Qt.AlignHCenter)

        # --- 测试区域 ---
        self.test_box = QLabel("将鼠标指针放置框内后开始点击" if self.is_mouse_mode else "在此处观察键盘连点效果")
        self.test_box.setAlignment(Qt.AlignCenter)
        self.test_box.setMinimumHeight(72)
        self.test_box.setStyleSheet(f"""
            QLabel {{
                border: 2px dashed {COLORS['accent']};
                border-radius: 10px;
                color: {COLORS['accent']};
                font-size: 13px;
                background: transparent;
            }}
        """)
        card_layout.addWidget(self.test_box)

        main_layout.addWidget(self.card)
        main_layout.addStretch(1)

    def connect_signals(self):
        self.slider.valueChanged.connect(self.on_speed_change)
        self.mode_group.idClicked.connect(self.on_mode_click)
        self.btn_toggle.clicked.connect(self.toggle_running)
        self.btn_trigger.clicked.connect(lambda: self.start_capture('trigger'))
        if self.is_mouse_mode:
            self.combo_target.currentIndexChanged.connect(self.on_mouse_mode_change)
        else:
            self.btn_target.clicked.connect(lambda: self.start_capture('target'))

    def showEvent(self, event):
        super().showEvent(event)
        self.init_highlight_pos()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.init_highlight_pos()

    def init_highlight_pos(self):
        checked_id = self.mode_group.checkedId()
        btn = self.mode_group.button(checked_id if checked_id != -1 else 0)
        if btn: 
            self.mode_highlight.setGeometry(btn.geometry())
            
    def animate_mode_highlight(self, index):
        target_btn = self.mode_group.button(index)
        if not target_btn: return
        self.anim = QPropertyAnimation(self.mode_highlight, b"geometry")
        self.anim.setDuration(300)
        self.anim.setStartValue(self.mode_highlight.geometry())
        self.anim.setEndValue(target_btn.geometry())
        self.anim.setEasingCurve(QEasingCurve.OutBack)
        self.anim.start()

    def on_speed_change(self, val):
        self.worker.clicks_per_second = val
        self.lbl_speed_val.setText(f"{val}次/秒")
        self.mode_group.blockSignals(True)
        new_id = 0 if val == 100 else (1 if val == 200 else 2)
        if self.mode_group.checkedId() != new_id:
            self.mode_group.button(new_id).setChecked(True)
            self.animate_mode_highlight(new_id)
        self.mode_group.blockSignals(False)

    def on_mode_click(self, btn_id):
        self.animate_mode_highlight(btn_id)
        if btn_id == 0: self.slider.setValue(100)
        elif btn_id == 1: self.slider.setValue(200)

    def format_key(self, key):
        """格式化按键名称显示，增加对纯 vk 码的兼容还原"""
        if isinstance(key, keyboard.KeyCode): 
            if key.char: 
                return key.char.upper()
            elif key.vk is not None:
                # 修复：如果 pynput 只认出了 vk 码，尝试将其转换回可读的英文字母或数字
                if 48 <= key.vk <= 57 or 65 <= key.vk <= 90:
                    return chr(key.vk).upper()
                return f"[{key.vk}]"
        elif isinstance(key, keyboard.Key): 
            return key.name.upper().replace('KEY.', '')
        elif hasattr(key, 'name'): 
            return f"鼠标 {key.name.upper()}"
        return str(key)

    def start_capture(self, capture_type):
        # 绑定按键时先停止连点
        if self.worker.running:
            self.worker.running = False
            self.btn_toggle.setText("▶  启动连点")
            self.btn_toggle.setStyleSheet(self.toggle_qss_start)
            self.test_box.setText("连点已停止")
            self.test_box.setStyleSheet(f"""
                QLabel {{
                    border: 2px solid {COLORS['border']};
                    background-color: transparent;
                    border-radius: 10px;
                    color: {COLORS['text_muted']};
                    font-size: 13px;
                }}
            """)
        self.is_capturing = True
        self.capture_type = capture_type
        self.capture_start_time = time.time()
        btn = self.btn_trigger if capture_type == 'trigger' else self.btn_target
        btn.setText("⏳ 请按键...")
        btn.setEnabled(False)

    def handle_global_input(self, key):
        if not self.isVisible(): return
        if self.is_capturing:
            if key == mouse.Button.left and (time.time() - self.capture_start_time) < 0.25:
                return
            self.is_capturing = False
            self._capture_cooldown = time.time() + 0.3  # 捕获后 0.3 秒内不触发连点
            btn = self.btn_trigger if self.capture_type == 'trigger' else self.btn_target
            if self.capture_type == 'trigger': self.trigger_key = key
            else: self.worker.target_kb_key = key
            btn.setText(f"{self.format_key(key)}键")
            btn.setEnabled(True)
            return
        if time.time() < getattr(self, '_capture_cooldown', 0): return  # 冷却期内跳过
        if key == self.trigger_key: self.toggle_running()

    def on_mouse_mode_change(self, index):
        btns = [mouse.Button.left, mouse.Button.right, mouse.Button.middle]
        self.worker.target_mouse_btn = btns[index]

    def toggle_running(self):
        if self.is_capturing: return
        self.worker.running = not self.worker.running
        if self.worker.running:
            self.worker.click_count = 0
            self.btn_toggle.setText("⏹  停止连点")
            self.btn_toggle.setStyleSheet(self.toggle_qss_stop)
            self.test_box.setText("连点执行中...")
            self.test_box.setStyleSheet(f"""
                QLabel {{
                    border: 2px solid {COLORS['accent']};
                    background-color: {COLORS['accent_light']};
                    border-radius: 10px;
                    color: {COLORS['accent']};
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
        else:
            self.btn_toggle.setText("▶  启动连点")
            self.btn_toggle.setStyleSheet(self.toggle_qss_start)
            self.test_box.setText("连点已停止")
            self.test_box.setStyleSheet(f"""
                QLabel {{
                    border: 2px dashed {COLORS['accent']};
                    border-radius: 10px;
                    color: {COLORS['accent']};
                    font-size: 13px;
                    background: transparent;
                }}
            """)

    def update_stats(self, count):
        self.test_box.setText(f"已触发连点: {count} 次")

    def serialize_key(self, key):
        if isinstance(key, keyboard.KeyCode): return {"type": "KeyCode", "vk": key.vk, "char": key.char}
        elif isinstance(key, keyboard.Key): return {"type": "Key", "name": key.name}
        elif hasattr(key, 'name'): return {"type": "Mouse", "name": key.name}
        return None

    def deserialize_key(self, data, default_key):
        """反序列化：完美还原 pynput 的 KeyCode 对象"""
        if not data: return default_key
        if data.get("type") == "KeyCode":
            vk, char = data.get("vk"), data.get("char")
            # 修复：必须同时传入 vk 和 char，防止字母变数字
            return keyboard.KeyCode(vk=vk, char=char)
        elif data.get("type") == "Key":
            name = data.get("name")
            if hasattr(keyboard.Key, name): return getattr(keyboard.Key, name)
        elif data.get("type") == "Mouse":
            name = data.get("name")
            if hasattr(mouse.Button, name): return getattr(mouse.Button, name)
        return default_key

    def get_config(self):
        return {
            "speed": self.slider.value(),
            "trigger_key": self.serialize_key(self.trigger_key),
            "target_kb_key": self.serialize_key(self.worker.target_kb_key) if not self.is_mouse_mode else None,
            "target_mouse_idx": self.combo_target.currentIndex() if self.is_mouse_mode else 0
        }

    def apply_config(self, config):
        if not config: return
        if "speed" in config:
            self.slider.setValue(config["speed"])
        if "trigger_key" in config:
            self.trigger_key = self.deserialize_key(config["trigger_key"], keyboard.Key.f8)
            self.btn_trigger.setText(f"{self.format_key(self.trigger_key)}键")
        
        if self.is_mouse_mode and "target_mouse_idx" in config:
            self.combo_target.setCurrentIndex(config["target_mouse_idx"])
        elif not self.is_mouse_mode and "target_kb_key" in config:
            self.worker.target_kb_key = self.deserialize_key(config["target_kb_key"], keyboard.KeyCode.from_char('a'))
            self.btn_target.setText(f"{self.format_key(self.worker.target_kb_key)}键")

# ================= 主窗口容器 =================
class EasyClickWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(780, 540)
        self.setMinimumSize(700, 480)
        self._is_tracking = False
        
        # 使用统一配置路径
        self.config_file = get_config_path()
        
        self.input_mgr = GlobalInputManager()
        self.input_mgr.start()
        
        self.setup_ui()
        self.load_config() 

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- 外层容器 ---
        self.container = QFrame()
        self.container.setObjectName("RootContainer")
        self.container.setStyleSheet(f"""
            QFrame#RootContainer {{
                background-color: {COLORS['bg_card']};
                border-radius: 14px;
                border: none;
            }}
        """)
        main_layout.addWidget(self.container)
        
        h_layout = QHBoxLayout(self.container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # ====== 左侧导航栏 ======
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(190)
        self.sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_sidebar']};
                border-top-left-radius: 14px;
                border-bottom-left-radius: 14px;
                border: none;
            }}
        """)
        
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 36, 0, 20)

        # Logo
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(20, 0, 0, 0)
        logo_icon = QLabel("⚡")
        logo_icon.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        logo_text = QLabel("EasyClick")
        logo_text.setStyleSheet(f"""
            color: {COLORS['text_white']};
            font-size: 18px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        logo_layout.addWidget(logo_icon)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()
        self.sidebar_layout.addLayout(logo_layout)
        self.sidebar_layout.addSpacing(28)

        # 导航按钮
        self.nav_group = QButtonGroup(self)
        self.btn_mouse = self.create_nav_btn("🖱  鼠标连点", 0, True)
        self.btn_keyboard = self.create_nav_btn("⌨  键盘连点", 1, False)
        self.sidebar_layout.addWidget(self.btn_mouse)
        self.sidebar_layout.addWidget(self.btn_keyboard)
        self.sidebar_layout.addStretch(1)
        
        # 导航指示条
        self.nav_indicator = QFrame(self.sidebar)
        self.nav_indicator.setFixedSize(3, 46)
        self.nav_indicator.setStyleSheet(f"""
            background-color: {COLORS['accent']};
            border-top-right-radius: 3px;
            border-bottom-right-radius: 3px;
        """)
        
        # ====== 右侧内容与控制栏 ======
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 标题栏（拖动区域 + 窗口控制按钮）
        title_bar = QFrame()
        title_bar.setFixedHeight(44)
        title_bar.setStyleSheet("background: transparent; border: none;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 12, 14, 0)
        title_layout.addStretch(1) 
        
        self.btn_min = QPushButton()
        self.btn_max = QPushButton()
        self.btn_close = QPushButton()
        
        for btn, color in zip([self.btn_min, self.btn_max, self.btn_close], [COLORS['yellow'], COLORS['green'], COLORS['red']]):
            btn.setFixedSize(13, 13)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border-radius: 6px;
                    border: none;
                }}
                QPushButton:hover {{
                    border: 1px solid rgba(0,0,0,0.2);
                }}
            """)
            title_layout.addWidget(btn)
            title_layout.addSpacing(6)
            
        self.btn_close.clicked.connect(self.close)
        self.btn_min.clicked.connect(self.showMinimized)

        # 页面堆栈
        self.stacked = QStackedWidget()
        self.page_mouse = BaseClickerPage("鼠标连点", "🖱️", self.input_mgr, True)
        self.page_kb = BaseClickerPage("键盘连点", "⌨️", self.input_mgr, False)
        self.stacked.addWidget(self.page_mouse)
        self.stacked.addWidget(self.page_kb)
        
        self.nav_group.idClicked.connect(self.switch_page)

        right_layout.addWidget(title_bar)
        right_layout.addWidget(self.stacked)

        h_layout.addWidget(self.sidebar)
        h_layout.addLayout(right_layout)

    def create_nav_btn(self, text, nav_id, is_checked):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setFixedHeight(46)
        btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding-left: 22px;
                color: {COLORS['text_light']};
                font-size: 14px;
                background: transparent;
                border: none;
                outline: none;
                border-top-right-radius: 10px;
                border-bottom-right-radius: 10px;
                margin-right: 10px;
            }}
            QPushButton:checked {{
                background-color: {COLORS['bg_sidebar_h']};
                color: {COLORS['text_white']};
                font-weight: bold;
            }}
            QPushButton:hover:!checked {{
                background-color: rgba(255, 255, 255, 0.06);
                color: {COLORS['text_white']};
            }}
        """)
        btn.setChecked(is_checked)
        self.nav_group.addButton(btn, nav_id)
        return btn

    def showEvent(self, event):
        super().showEvent(event)
        # 去除 Windows DWM 白边
        if sys.platform == "win32":
            remove_window_border(int(self.winId()))
        self.init_indicator_pos()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.init_indicator_pos()

    def init_indicator_pos(self):
        checked_id = self.nav_group.checkedId()
        btn = self.nav_group.button(checked_id if checked_id != -1 else 0)
        if btn:
            self.nav_indicator.move(0, btn.pos().y())

    def switch_page(self, index):
        if self.stacked.currentIndex() == index: return
        
        target_btn = self.nav_group.button(index)
        self.ind_anim = QPropertyAnimation(self.nav_indicator, b"pos")
        self.ind_anim.setDuration(250)
        self.ind_anim.setStartValue(self.nav_indicator.pos())
        self.ind_anim.setEndValue(QPoint(0, target_btn.pos().y()))
        self.ind_anim.setEasingCurve(QEasingCurve.OutBack)
        self.ind_anim.start()

        self.effect = QGraphicsOpacityEffect(self.stacked)
        self.stacked.setGraphicsEffect(self.effect)
        
        self.anim_out = QPropertyAnimation(self.effect, b"opacity")
        self.anim_out.setDuration(100)
        self.anim_out.setStartValue(1.0)
        self.anim_out.setEndValue(0.0)
        self.anim_out.setEasingCurve(QEasingCurve.OutQuad)
        
        def on_fade_out():
            self.stacked.setCurrentIndex(index)
            self.anim_in = QPropertyAnimation(self.effect, b"opacity")
            self.anim_in.setDuration(150)
            self.anim_in.setStartValue(0.0)
            self.anim_in.setEndValue(1.0)
            self.anim_in.setEasingCurve(QEasingCurve.InQuad)
            self.anim_in.finished.connect(lambda: self.stacked.setGraphicsEffect(None))
            self.anim_in.start()

        self.anim_out.finished.connect(on_fade_out)
        self.anim_out.start()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and event.pos().y() < 50:
            self._is_tracking = True
            self._start_pos = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_tracking:
            self.move(event.globalPos() - self._start_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._is_tracking = False

    # ================= 读写配置逻辑 (写入标准用户目录) =================
    def save_config(self):
        config = {
            "mouse_page": self.page_mouse.get_config(),
            "keyboard_page": self.page_kb.get_config(),
            "last_active_tab": self.stacked.currentIndex()
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置失败: {str(e)}")

    def load_config(self):
        if not os.path.exists(self.config_file): return
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            self.page_mouse.apply_config(config.get("mouse_page", {}))
            self.page_kb.apply_config(config.get("keyboard_page", {}))
            
            last_tab = config.get("last_active_tab", 0)
            if last_tab != 0:
                self.nav_group.button(last_tab).setChecked(True)
                self.stacked.setCurrentIndex(last_tab)
        except Exception as e:
            print(f"加载配置失败: {str(e)}")

    def closeEvent(self, event):
        self.save_config()
        self.page_mouse.worker.running = False
        self.page_kb.worker.running = False
        event.accept()

if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 9))
    
    # 设置窗口图标（兼容开发模式和 PyInstaller 打包模式）
    if getattr(sys, 'frozen', False):
        _base = Path(sys._MEIPASS)
    else:
        _base = Path(__file__).parent
    _icon = _base / "icon.png"
    if _icon.exists():
        app.setWindowIcon(QIcon(str(_icon)))
    
    window = EasyClickWindow()
    window.show()
    sys.exit(app.exec_())