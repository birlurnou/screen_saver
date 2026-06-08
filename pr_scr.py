import os
import sys
import configparser
from datetime import datetime
from PIL import Image, ImageGrab
from pynput import keyboard
import threading
import tkinter as tk
import ctypes

ctypes.windll.user32.SetProcessDPIAware()


class ScreenshotTool:
    def __init__(self):
        self.config_file = 'screenshot_config.ini'
        self.config = configparser.ConfigParser()
        self.load_config()
        self.setup_listener()

    def load_config(self):
        """Загрузка всех настроек из конфига"""
        if not os.path.exists(self.config_file):
            self.create_default_config()

        self.config.read(self.config_file, encoding='utf-8')

        # Общие настройки
        self.screenshot_path = self.config.get('Settings', 'save_path', fallback=self.get_default_path())
        self.behavior = self.config.get('Settings', 'behavior', fallback='save_file')

        # Настройки качества
        self.image_format = self.config.get('Quality', 'format', fallback='PNG')
        self.quality = self.config.getint('Quality', 'quality', fallback=95)
        self.compression = self.config.getint('Quality', 'compression', fallback=6)

        # Настройки внешнего вида
        self.overlay_alpha = self.config.getfloat('Appearance', 'overlay_alpha', fallback=0.3)
        self.selection_color = self.config.get('Appearance', 'selection_color', fallback='red')
        self.selection_width = self.config.getint('Appearance', 'selection_width', fallback=2)

        # Создаём папку для скриншотов
        if not os.path.exists(self.screenshot_path):
            os.makedirs(self.screenshot_path)

    def create_default_config(self):
        """Создание конфига с настройками по умолчанию"""
        self.config['Settings'] = {
            'save_path': self.get_default_path(),
            'behavior': 'save_file'
        }
        self.config['Quality'] = {
            'format': 'PNG',
            'quality': '95',
            'compression': '6'
        }
        self.config['Appearance'] = {
            'overlay_alpha': '0.3',
            'selection_color': 'red',
            'selection_width': '2'
        }

        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_default_path(self):
        """Путь по умолчанию"""
        return os.path.join(os.path.expanduser("~"), "Documents", "Screenshots")

    def get_unique_filename(self):
        """Генерация уникального имени файла"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        ext = 'png' if self.image_format == 'PNG' else 'jpg'
        return f"screenshot_{timestamp}.{ext}"

    def save_screenshot(self, image):
        """Сохранение скриншота"""
        if self.behavior == 'save_file':
            filepath = os.path.join(self.screenshot_path, self.get_unique_filename())

            if self.image_format == 'PNG':
                image.save(filepath, 'PNG', compress_level=self.compression)
            else:  # JPEG
                if image.mode in ('RGBA', 'LA', 'P'):
                    rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    rgb_image.save(filepath, 'JPEG', quality=self.quality)
                else:
                    image.save(filepath, 'JPEG', quality=self.quality)
            print(f"✅ Скриншот сохранён: {filepath}")
        else:
            self.copy_to_clipboard(image)
            print("✅ Скриншот скопирован в буфер")

    def copy_to_clipboard(self, image):
        """Копирование в буфер обмена"""
        try:
            import win32clipboard
            from PIL import ImageWin

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            ImageWin.Dib(image).save(win32clipboard)
            win32clipboard.CloseClipboard()
        except ImportError:
            print("⚠️ Установите pywin32: pip install pywin32")
            self.save_screenshot(image)

    def select_area(self):
        """Выделение области на экране"""
        if not hasattr(self, 'root'):
            self.root = tk.Tk()
            self.root.withdraw()

        self.selection_win = tk.Toplevel(self.root)
        self.selection_win.attributes('-fullscreen', True)
        self.selection_win.attributes('-alpha', self.overlay_alpha)
        self.selection_win.configure(bg='gray')
        self.selection_win.attributes('-topmost', True)

        canvas = tk.Canvas(self.selection_win, cursor="cross", bg='gray', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        rect = None
        start_x = start_y = 0

        def on_mouse_down(event):
            nonlocal rect, start_x, start_y
            start_x, start_y = event.x_root, event.y_root
            if rect:
                canvas.delete(rect)
            rect = canvas.create_rectangle(start_x, start_y, start_x, start_y,
                                           outline=self.selection_color,
                                           width=self.selection_width,
                                           fill='white', stipple='gray50')

        def on_mouse_move(event):
            nonlocal rect
            if start_x and start_y and rect:
                canvas.coords(rect, start_x, start_y, event.x_root, event.y_root)

        def on_mouse_up(event):
            if start_x and start_y and abs(event.x_root - start_x) > 5:
                x1, x2 = min(start_x, event.x_root), max(start_x, event.x_root)
                y1, y2 = min(start_y, event.y_root), max(start_y, event.y_root)
                self.selection_win.destroy()
                self.capture_area(x1, y1, x2, y2)
            else:
                self.selection_win.destroy()

        canvas.bind('<ButtonPress-1>', on_mouse_down)
        canvas.bind('<B1-Motion>', on_mouse_move)
        canvas.bind('<ButtonRelease-1>', on_mouse_up)
        self.selection_win.bind('<Escape>', lambda e: self.selection_win.destroy())
        self.selection_win.update()

    def capture_area(self, x1, y1, x2, y2):
        """Захват выделенной области"""
        try:
            cropped = ImageGrab.grab().crop((x1, y1, x2, y2))
            self.save_screenshot(cropped)
        except Exception as e:
            print(f"Ошибка: {e}")

    def take_screenshot(self):
        threading.Thread(target=self.select_area, daemon=True).start()

    def setup_listener(self):
        def on_press(key):
            if key == keyboard.Key.print_screen:
                print("📸 Print Screen нажат!")
                self.take_screenshot()

        def run_listener():
            with keyboard.Listener(on_press=on_press) as listener:
                listener.join()

        threading.Thread(target=run_listener, daemon=True).start()


def main():
    print("🖥️  Скриншейдер запущен")
    print("📸 Нажмите Print Screen для скриншота")

    tool = ScreenshotTool()

    if not hasattr(tool, 'root'):
        tool.root = tk.Tk()
        tool.root.withdraw()

    tool.root.mainloop()


if __name__ == "__main__":
    main()