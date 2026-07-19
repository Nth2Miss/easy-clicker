# EasyClick

鼠标 & 键盘连点器

## 功能

- **鼠标连点** — 支持左键/右键/中键，可自定义点击速率
- **键盘连点** — 支持任意按键，可自定义触发速率
- **三种模式** — 快速 / 极速 / 自定义
- **全局热键** — 支持自定义启动/停止开关按键

## 使用

在 [releases](https://github.com/Nth2Miss/easy-clicker/releases/latest) 页面下载 `EasyClick.exe`，双击运行。

### 开发

```bash
# 安装依赖
.venv\Scripts\pip.exe install -r requirements.txt

# 运行
.venv\Scripts\python.exe clicker.py

# 打包
.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --icon icon.ico --add-data "icon.ico;." --name "EasyClick" clicker.py
```

## 技术栈

- Python 3.12 + PyQt5
- pynput（全局输入监听）
- PyInstaller（打包分发）
