import os
import sys
import configparser
from datetime import datetime
from PIL import Image, ImageGrab
import keyboard
import threading
import tkinter as tk
import ctypes
import ctypes.wintypes
from queue import Queue
import time

ctypes.windll.user32.SetProcessDPIAware()


class ScreenshotTool:
    def __init__(self):
        self.config_file = 'config.ini'
        self.config = configparser.ConfigParser()
        self.load_config()
        self.task_queue = Queue()
        self.root = None
        self.select_count = 0
        self.setup_hotkey()
        self.process_tasks()
        threading.Thread(target=self.health_check, daemon=True).start()
        threading.Thread(target=self.config_watcher, daemon=True).start()

    def config_watcher(self):
        last_time = os.path.getmtime(self.config_file) if os.path.exists(self.config_file) else 0
        while True:
            time.sleep(3)
            if os.path.exists(self.config_file):
                current_time = os.path.getmtime(self.config_file)
                if current_time != last_time:
                    self.load_config()
                    last_time = current_time
            else:
                if not os.path.exists(self.config_file):
                    self.create_default_config()

    def health_check(self):
        while True:
            time.sleep(10)
            with keyboard._pressed_events_lock:
                if keyboard._pressed_events:
                    print("Залипшие клавиши очищены")
                    keyboard._pressed_events.clear()

    def load_config(self):
        if not os.path.exists(self.config_file):
            self.create_default_config()

        self.config.read(self.config_file, encoding='utf-8')

        self.screenshot_path = self.config.get('Settings', 'save_path', fallback=self.get_default_path())
        self.extension_path = self.config.get('Settings', 'extension_path', fallback='')
        self.filename_mask = self.config.get('Settings', 'filename_mask', fallback='ymd_hms')
        self.datetime_structure = self.config.get('Settings', 'datetime_structure', fallback=1)
        self._copy = self.config.get('Settings', 'copy', fallback=1)
        self._save = self.config.get('Settings', 'save', fallback=1)
        self.hotkey = self.config.get('Hotkeys', 'screenshot_hotkey', fallback='print screen')

        self.image_format = self.config.get('Quality', 'format', fallback='PNG')
        self.quality = self.config.getint('Quality', 'quality', fallback=100)
        self.compression = self.config.getint('Quality', 'compression', fallback=0)

        self.overlay_color = self.config.get('Appearance', 'overlay_color', fallback='black')
        self.overlay_alpha = self.config.getfloat('Appearance', 'overlay_alpha', fallback=0.4)

        self.selection_border_color = self.config.get('Appearance', 'selection_border_color', fallback='black')
        self.selection_border_width = self.config.getint('Appearance', 'selection_border_width', fallback=1)

        self.selection_fill_color = self.config.get('Appearance', 'selection_fill_color', fallback='white')

        self.cursor_type = self.config.get('Appearance', 'cursor_type', fallback='tcross')

        if not os.path.exists(self.screenshot_path):
            os.makedirs(self.screenshot_path)

        try:
            keyboard.remove_all_hotkeys()
        except:
            pass
        keyboard.add_hotkey(self.hotkey, self.take_screenshot)

    def create_default_config(self):
        self.config['Settings'] = {
            'save_path': self.get_default_path(),
            'extension_path': '',
            'filename_mask': '_ymd-hMs',
            'datetime_structure': 1,
            'save': 1,
            'copy': 1
        }
        self.config['Hotkeys'] = {
            'screenshot_hotkey': 'alt+z+x'
        }
        self.config['Quality'] = {
            'format': 'PNG',
            'quality': '100',
            'compression': '0'
        }
        self.config['Appearance'] = {
            'overlay_color': 'black',
            'overlay_alpha': '0.4',
            'selection_border_color': 'black',
            'selection_border_width': '1',
            'selection_fill_color': 'white',
            'cursor_type': 'tcross'
        }

        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_default_path(self):
        return os.path.join(os.path.expanduser('~'), 'Documents', 'Screenshots')

    def get_unique_filename(self):

        filename_strftime = ''
        for l in self.filename:
            match l:
                case 'y': filename_strftime += '%Y'
                case 'm': filename_strftime += '%m'
                case 'd': filename_strftime += '%d'
                case 'h': filename_strftime += '%H'
                case 'M': filename_strftime += '%M'
                case 's': filename_strftime += '%S%f'
                case '-': filename_strftime += '-'
                case '_': filename_strftime += '_'

        timestamp = datetime.now().strftime(filename_strftime)
        if '%S%f' in filename_strftime:
            timestamp = timestamp[:-6]
        ext = 'png' if self.image_format == 'PNG' else 'jpg'
        return f'{timestamp}.{ext}'

    def save_screenshot(self, image):
        if int(self._save) == 1:
            full_path = self.screenshot_path + self.extension_path
            if int(self.datetime_structure) == 1:
                full_path += fr'\{datetime.now().strftime('%Y-%m')}' + fr'\{datetime.now().strftime('%Y-%m-%d')}'

            filepath = os.path.join(full_path, self.get_unique_filename())

            if not os.path.exists(full_path):
                os.makedirs(full_path)

            if self.image_format == 'PNG':
                image.save(filepath, 'PNG', compress_level=self.compression)
            else:
                if image.mode in ('RGBA', 'LA', 'P'):
                    rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    rgb_image.save(filepath, 'JPEG', quality=self.quality)
                else:
                    image.save(filepath, 'JPEG', quality=self.quality)
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
        except:
            self.save_screenshot(image)

    def select_area(self):
        def wait_for_esc():
            try:
                keyboard.wait('esc')
                if hasattr(self, 'selection_win') and self.selection_win:
                    self.selection_win.destroy()
                self.select_count = 0
            except:
                pass

        threading.Thread(target=wait_for_esc, daemon=True).start()

        if self.root is None:
            self.root = tk.Tk()
            self.root.withdraw()
            self.select_count += 1

        user32 = ctypes.windll.user32
        virtual_left = user32.GetSystemMetrics(76)
        virtual_top = user32.GetSystemMetrics(77)
        virtual_width = user32.GetSystemMetrics(78)
        virtual_height = user32.GetSystemMetrics(79)

        self.selection_win = tk.Toplevel(self.root)
        self.selection_win.overrideredirect(True)
        self.selection_win.geometry(f"{virtual_width}x{virtual_height}+{virtual_left}+{virtual_top}")
        self.selection_win.attributes('-alpha', self.overlay_alpha)
        self.selection_win.configure(bg=self.overlay_color)
        self.selection_win.attributes('-topmost', True)

        canvas = tk.Canvas(self.selection_win, cursor='tcross', bg=self.overlay_color, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        rect = None
        start_x = start_y = 0

        def on_mouse_down(event):
            nonlocal rect, start_x, start_y
            start_x, start_y = event.x_root, event.y_root
            if rect:
                canvas.delete(rect)
            rect = canvas.create_rectangle(
                start_x - virtual_left, start_y - virtual_top,
                start_x - virtual_left, start_y - virtual_top,
                outline=self.selection_border_color,
                width=self.selection_border_width,
                fill=self.selection_fill_color
            )

        def on_mouse_move(event):
            nonlocal rect
            if start_x and start_y and rect:
                x1 = start_x - virtual_left
                y1 = start_y - virtual_top
                x2 = event.x_root - virtual_left
                y2 = event.y_root - virtual_top
                canvas.coords(rect, x1, y1, x2, y2)

        def on_mouse_up(event):
            if start_x and start_y and abs(event.x_root - start_x) > 5:
                x1 = min(start_x, event.x_root)
                y1 = min(start_y, event.y_root)
                x2 = max(start_x, event.x_root)
                y2 = max(start_y, event.y_root)
                self.selection_win.destroy()
                self.capture_area(x1, y1, x2, y2)
            else:
                self.selection_win.destroy()
            self.select_count = 0

        canvas.bind('<ButtonPress-1>', on_mouse_down)
        canvas.bind('<B1-Motion>', on_mouse_move)
        canvas.bind('<ButtonRelease-1>', on_mouse_up)

    def capture_area(self, x1, y1, x2, y2):
        try:

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            width = int(abs(x2 - x1))
            height = int(abs(y2 - y1))

            if width == 0 or height == 0:
                return

            hdcScreen = user32.GetDC(None)
            hdcMem = gdi32.CreateCompatibleDC(hdcScreen)
            hbm = gdi32.CreateCompatibleBitmap(hdcScreen, width, height)
            gdi32.SelectObject(hdcMem, hbm)

            gdi32.BitBlt(hdcMem, 0, 0, width, height, hdcScreen, int(x1), int(y1), 0x00CC0020)

            bmp = ctypes.create_string_buffer(width * height * 4)
            gdi32.GetBitmapBits(hbm, width * height * 4, bmp)

            img = Image.frombuffer('RGBA', (width, height), bmp, 'raw', 'BGRA', 0, 1).convert('RGB')

            gdi32.DeleteObject(hbm)
            gdi32.DeleteDC(hdcMem)
            user32.ReleaseDC(None, hdcScreen)

            self.save_screenshot(img)
        except Exception as e:
            print(f'Ошибка захвата: {e}')
        finally:
            self.select_count = 0

    def take_screenshot(self):
        print(self.select_count)
        if self.select_count == 0:
            self.task_queue.put(self.select_area)
            self.select_count += 1

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


def main():
    tool = ScreenshotTool()

    tool.root = tk.Tk()
    tool.root.withdraw()
    tool.process_tasks()
    tool.root.mainloop()


if __name__ == '__main__':
    main()
