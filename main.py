import os
import sys
import configparser
from datetime import datetime
from PIL import Image, ImageGrab
import keyboard
import threading
import tkinter as tk
import ctypes
from queue import Queue

ctypes.windll.user32.SetProcessDPIAware()


class ScreenshotTool:
    def __init__(self):
        self.config_file = 'screenshot_config.ini'
        self.config = configparser.ConfigParser()
        self.load_config()
        self.task_queue = Queue()
        self.root = None
        self.setup_hotkey()
        self.process_tasks()

    def load_config(self):
        if not os.path.exists(self.config_file):
            self.create_default_config()

        self.config.read(self.config_file, encoding='utf-8')

        self.screenshot_path = self.config.get('Settings', 'save_path', fallback=self.get_default_path())
        self._copy = self.config.get('Settings', 'copy', fallback=1)
        self._save = self.config.get('Settings', 'save', fallback=1)
        self.hotkey = self.config.get('Hotkeys', 'screenshot_hotkey', fallback='print screen')

        self.image_format = self.config.get('Quality', 'format', fallback='PNG')
        self.quality = self.config.getint('Quality', 'quality', fallback=95)
        self.compression = self.config.getint('Quality', 'compression', fallback=6)

        self.overlay_alpha = self.config.getfloat('Appearance', 'overlay_alpha', fallback=0.3)
        self.selection_color = self.config.get('Appearance', 'selection_color', fallback='red')
        self.selection_width = self.config.getint('Appearance', 'selection_width', fallback=2)

        if not os.path.exists(self.screenshot_path):
            os.makedirs(self.screenshot_path)

    def create_default_config(self):
        self.config['Settings'] = {
            'save_path': self.get_default_path(),
            'save': 1,
            'copy': 1
        }
        self.config['Hotkeys'] = {
            'screenshot_hotkey': 'alt+z+x'
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
        return os.path.join(os.path.expanduser('~'), 'Documents', 'Screenshots')

    def get_unique_filename(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        ext = 'png' if self.image_format == 'PNG' else 'jpg'
        return f'screenshot_{timestamp}.{ext}'

    def save_screenshot(self, image):
        if int(self._save) == 1:
            filepath = os.path.join(self.screenshot_path, self.get_unique_filename())

            if self.image_format == 'PNG':
                image.save(filepath, 'PNG', compress_level=self.compression)
            else:
                if image.mode in ('RGBA', 'LA', 'P'):
                    rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    rgb_image.save(filepath, 'JPEG', quality=self.quality)
                else:
                    image.save(filepath, 'JPEG', quality=self.quality)

            print(f'Скриншот сохранён: {filepath}')
        if int(self._copy) == 1:
            self.copy_to_clipboard(image)

    def copy_to_clipboard(self, image):
        try:
            from io import BytesIO
            import win32clipboard

            output = BytesIO()
            image.save(output, 'BMP')
            data = output.getvalue()[14:]
            output.close()

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            print('Скриншот скопирован в буфер обмена')
        except:
            self.save_screenshot(image)

    def select_area(self):

        def wait_for_esc():
            keyboard.wait('esc')
            self.selection_win.destroy()
        threading.Thread(target=wait_for_esc, daemon=True).start()

        if self.root is None:
            self.root = tk.Tk()
            self.root.withdraw()

        self.selection_win = tk.Toplevel(self.root)
        self.selection_win.attributes('-fullscreen', True)
        self.selection_win.attributes('-alpha', self.overlay_alpha)
        self.selection_win.configure(bg='gray')
        self.selection_win.attributes('-topmost', True)

        canvas = tk.Canvas(self.selection_win, cursor='cross', bg='gray', highlightthickness=0)
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

    def capture_area(self, x1, y1, x2, y2):
        try:
            cropped = ImageGrab.grab().crop((x1, y1, x2, y2))
            self.save_screenshot(cropped)
        except Exception as e:
            print(f'Ошибка: {e}')

    def take_screenshot(self):
        self.task_queue.put(self.select_area)

    def process_tasks(self):
        try:
            while not self.task_queue.empty():
                task = self.task_queue.get_nowait()
                task()
        except:
            pass

        if self.root is not None:
            self.root.after(100, self.process_tasks)

    def setup_hotkey(self):
        keyboard.add_hotkey(self.hotkey, self.take_screenshot)
        print(f'Горячая клавиша: {self.hotkey}')


def main():
    tool = ScreenshotTool()

    tool.root = tk.Tk()
    tool.root.withdraw()
    tool.process_tasks()

    print('Программа запущена. Нажмите Esc для выхода.')

    tool.root.mainloop()


if __name__ == '__main__':
    main()