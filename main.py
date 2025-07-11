import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import qrcode
import json
import os
import re
import logging
from PIL import Image, ImageTk

# --- Настройка логирования ---
logging.basicConfig(filename="app_errors.log", level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

HISTORY_FILE = "history.json"
API_URL = "https://api.tinyurl.com/create"
API_KEY = "Удалил так как репозиторий публичный"

def is_valid_url(url):
    pattern = re.compile(
        r'^(https?://)?'  # http:// или https:// (необязательно)
        r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'  # домен
        r'(:\d+)?'  # порт (необязательно)
        r'(\/\S*)?$'  # путь (необязательно)
    )
    return re.match(pattern, url) is not None

def check_url_alive(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=5)
        return r.status_code < 400
    except:
        return False

def shorten_url(long_url):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "url": long_url,
        "domain": "tinyurl.com"
    }
    response = requests.post(API_URL, headers=headers, json=data, timeout=10)
    if response.status_code in (200, 201):
        return response.json()["data"]["tiny_url"]
    else:
        raise Exception(f"Ошибка сокращения ссылки: {response.text}")

def save_history(record):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception as e:
            logging.error(f"Ошибка чтения истории: {e}")
            history = []

    history.append(record)

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Ошибка сохранения истории: {e}")

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Ошибка загрузки истории: {e}")
            return []
    return []

class QRShortenerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Генератор QR-кодов и коротких ссылок")
        self.root.geometry("600x700")
        self.root.resizable(False, False)

        self.output_folder = os.getcwd()

        # --- Ввод ссылки ---
        frame_url = ttk.LabelFrame(root, text="Введите длинную ссылку или текст для QR:")
        frame_url.pack(fill="x", padx=10, pady=10)

        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(frame_url, textvariable=self.url_var, font=("Arial", 12))
        self.url_entry.pack(fill="x", expand=True, padx=5, pady=5)
        self.url_entry.focus()

        # --- Кнопки действий ---
        frame_buttons = ttk.Frame(root)
        frame_buttons.pack(fill="x", padx=10, pady=5)

        self.shorten_btn = ttk.Button(frame_buttons, text="Сократить ссылку и сгенерировать QR", command=self.shorten_and_generate)
        self.shorten_btn.pack(fill="x", pady=5)

        self.qr_only_btn = ttk.Button(frame_buttons, text="Сгенерировать QR из текста", command=self.generate_qr_only)
        self.qr_only_btn.pack(fill="x", pady=5)

        # --- Отображение результата ---
        frame_result = ttk.LabelFrame(root, text="Результаты")
        frame_result.pack(fill="both", expand=True, padx=10, pady=10)

        self.result_text = tk.Text(frame_result, height=5, font=("Arial", 11))
        self.result_text.pack(fill="x", padx=5, pady=5)

        self.qr_label = ttk.Label(frame_result)
        self.qr_label.pack(pady=10)

        # --- Кнопка сохранения QR ---
        self.save_btn = ttk.Button(frame_result, text="Сохранить QR-код", command=self.save_qr_code, state="disabled")
        self.save_btn.pack(pady=5)

        # --- История ---
        frame_history = ttk.LabelFrame(root, text="История сокращённых ссылок")
        frame_history.pack(fill="both", expand=True, padx=10, pady=10)

        self.history_list = tk.Listbox(frame_history, height=8)
        self.history_list.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
        self.history_list.bind("<<ListboxSelect>>", self.on_history_select)

        scrollbar = ttk.Scrollbar(frame_history, orient="vertical", command=self.history_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.history_list.config(yscrollcommand=scrollbar.set)

        self.load_history_to_list()

        # --- Переменные ---
        self.current_qr_img = None
        self.current_short_url = None

        # Авто-вставка из буфера при старте
        self.auto_paste_on_start()

    def auto_paste_on_start(self):
        try:
            clipboard = self.root.clipboard_get()
            if clipboard and is_valid_url(clipboard):
                self.url_entry.insert(0, clipboard)
        except Exception:
            pass

    def shorten_and_generate(self):
        long_url = self.url_var.get().strip()
        if not long_url:
            messagebox.showwarning("Внимание", "Введите ссылку для сокращения.")
            return

        if not is_valid_url(long_url):
            messagebox.showwarning("Внимание", "Введённая ссылка имеет некорректный формат.")
            return

        # Проверяем, доступна ли ссылка
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "Проверяем доступность ссылки...\n")
        self.root.update()

        if not check_url_alive(long_url):
            messagebox.showwarning("Внимание", "Ссылка недоступна (не отвечает или неверный URL).")
            return

        try:
            self.result_text.insert(tk.END, "Сокращаем ссылку...\n")
            self.root.update()

            short_url = shorten_url(long_url)
            self.current_short_url = short_url

            self.result_text.insert(tk.END, f"Короткая ссылка: {short_url}\n")
            self.result_text.insert(tk.END, "Генерируем QR-код...\n")
            self.root.update()

            img = qrcode.make(short_url)
            self.display_qr(img)

            # Сохраняем в историю
            save_history({
                "original": long_url,
                "short": short_url
            })

            self.load_history_to_list()
            self.save_btn.config(state="normal")

            self.result_text.insert(tk.END, "Готово!\n")

        except Exception as e:
            logging.error(f"Ошибка в shorten_and_generate: {e}")
            messagebox.showerror("Ошибка", f"Произошла ошибка при сокращении ссылки:\n{e}")

    def generate_qr_only(self):
        text = self.url_var.get().strip()
        if not text:
            messagebox.showwarning("Внимание", "Введите текст для генерации QR-кода.")
            return
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "Генерируем QR-код...\n")
        self.root.update()
        try:
            img = qrcode.make(text)
            self.display_qr(img)
            self.current_short_url = None
            self.save_btn.config(state="normal")
            self.result_text.insert(tk.END, "Готово!\n")
        except Exception as e:
            logging.error(f"Ошибка в generate_qr_only: {e}")
            messagebox.showerror("Ошибка", f"Ошибка при генерации QR-кода:\n{e}")

    def display_qr(self, img):
        img = img.resize((250, 250))
        self.current_qr_img = ImageTk.PhotoImage(img)
        self.qr_label.config(image=self.current_qr_img)

    def save_qr_code(self):
        if not self.current_qr_img:
            messagebox.showwarning("Внимание", "Нет QR-кода для сохранения.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG images", "*.png")],
            initialdir=self.output_folder,
            title="Сохранить QR-код как..."
        )
        if filepath:
            try:
                if self.current_short_url:
                    img = qrcode.make(self.current_short_url)
                else:
                    text = self.url_var.get().strip()
                    img = qrcode.make(text)
                img.save(filepath)
                self.output_folder = os.path.dirname(filepath)
                messagebox.showinfo("Успех", f"QR-код сохранён: {filepath}")
            except Exception as e:
                logging.error(f"Ошибка при сохранении QR: {e}")
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")

    def load_history_to_list(self):
        self.history_list.delete(0, tk.END)
        history = load_history()
        for item in reversed(history):
            short = item.get("short", "N/A")
            original = item.get("original", "")
            display = f"{short}  ← {original[:40]}{'...' if len(original)>40 else ''}"
            self.history_list.insert(tk.END, display)

    def on_history_select(self, event):
        if not self.history_list.curselection():
            return
        index = self.history_list.curselection()[0]
        history = load_history()
        true_index = len(history) - 1 - index
        record = history[true_index]

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, f"Оригинал: {record.get('original')}\n")
        self.result_text.insert(tk.END, f"Сокращённая: {record.get('short')}\n")

        short_url = record.get('short')
        if short_url:
            self.root.clipboard_clear()
            self.root.clipboard_append(short_url)
            messagebox.showinfo("Копировано", "Короткая ссылка скопирована в буфер обмена!")

if __name__ == "__main__":
    root = tk.Tk()
    app = QRShortenerApp(root)
    root.mainloop()
