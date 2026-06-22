import threading
import tkinter as tk
import queue
import google.genai as genai
from google.genai import types
import winsound
import pyperclip
import time
import win32api
from PIL import Image, ImageDraw, ImageGrab
import pystray
import os
import re
from typing import Any, Literal, cast
import pygetwindow as gw
from win32.lib import win32con
import win32gui
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- Configuration Loading ---
# Set True for debug mode to read configuration files from the dist folder, False for release to read files from the compiled executable folder
IS_DEBUG = False
if IS_DEBUG:
    BASE_DIR = "dist"
else:
    BASE_DIR = ""

# API retry settings
AI_RETRY_ATTEMPTS = 15

current_chat_session = None  # Chat history
ai_client = None # Global AI client to keep sessions alive
tray_icon = None
ahk_process = None
window_queue = queue.Queue()
root = None

def create_window(title, text=None, is_chat=False, load_history=False):
    # Sends a request to the GUI thread to create a new window
    window_queue.put((title, text, is_chat, load_history))

def check_queue():
    # Processes the window creation queue in the GUI thread
    try:
        while True:
            title, text, is_chat, load_history = window_queue.get_nowait()
            ResultWindow(title, text, is_chat, load_history)
    except queue.Empty:
        pass
    finally:
        if root:
            # noinspection PyArgumentList
            root.after(100, check_queue)  # type: ignore

def get_full_path(filename):
    # Joins the base directory and filename with correct system slashes.
    return os.path.join(BASE_DIR, filename)

def load_config():
    # Loads API key and Model name from a text file, creates it if missing.
    filename = get_full_path("APIAndModel.txt")
    default_prompt = (
        "Відповідай ЗАВЖДИ українською мовою. "
        "Твої відповіді мають бути короткими, лаконічними та по суті."
        "PUNCTUATION LIMIT: ABSOLUTELY FORBID introducing new semicolons (;). Use periods or commas instead. Only allow semicolons if they were already present in the original input. For complex sentence joins, use a period."
    )
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            f.write("YOUR_API_KEY_HERE\n")
            f.write("YOUR_MODEL_NAME_HERE\n")
            f.write(f"{default_prompt}\n")
        return "YOUR_API_KEY_HERE", "YOUR_MODEL_NAME_HERE", default_prompt

    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            api_key = lines[0] if len(lines) > 0 else "YOUR_API_KEY_HERE"
            model_name = lines[1] if len(lines) > 1 else "YOUR_MODEL_NAME_HERE"
            chat_prompt = " ".join(lines[2:]) if len(lines) > 2 else default_prompt
            return api_key, model_name, chat_prompt
    except Exception as e:
        print(f"Error reading config: {e}")
        return "YOUR_API_KEY_HERE", "YOUR_MODEL_NAME_HERE", default_prompt

AI_API_KEY, MODEL_NAME, CHAT_PROMPT = load_config()

def get_ai_client():
    """Returns a persistent AI client instance."""
    global ai_client
    if ai_client is None and AI_API_KEY and AI_API_KEY != "YOUR_API_KEY_HERE":
        ai_client = genai.Client(
            api_key=AI_API_KEY,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=AI_RETRY_ATTEMPTS,
                )
            )
        )
    return ai_client

# Initialize AI API - just check the key
if not AI_API_KEY or AI_API_KEY == "YOUR_API_KEY_HERE":
    print("API Key not set correctly.")

# --- Prompts ---
PROMPT_FIX = (
    "You are a Senior QA/Developer editing technical notes. "
    "TASK: Minor grammar correction of the text in triple quotes. "
    "STRICT RULES: "
    "1. MINIMAL INTERVENTION: Only fix grammar and clarity. Do not change words like 'Old' to 'Legacy' if the meaning is clear. "
    "2. PRESERVE VOICE: If the text is a comment or a note, keep its original style and vocabulary. Do not 'sanitize' it into formal documentation. "
    "3. TECHNICAL CONTEXT: Do not hallucinate or add meaning. 'Old code knows' is a personification — keep it, don't change to 'includes'. "
    "4. TRANSLATION: If the input is Ukrainian, translate it into natural, professional English. "
    "5. ARTICLES ACCURACY: Pay special attention to articles (a, an, the). Ensure they are placed correctly according to English grammar rules, especially when translating from article-free languages, while keeping the technical context natural. "
    "6. PUNCTUATION LIMIT: ABSOLUTELY FORBID introducing new semicolons (;). Use periods or commas instead. Only allow semicolons if they were already present in the original input. For complex sentence joins, use a period. "
    "7. Output ONLY the refined text."
)

PROMPT_TRANSLATE = (
    "ACT AS A RIGID TRANSLATOR TO UKRAINIAN. "
    "TASK: Process the text provided inside the triple quotes. "
    "1. DESTINATION LANGUAGE: UKRAINIAN ONLY. "
    "2. MANDATORY RULE: Never return text in the source language. No matter what the input language is, the output MUST be in Ukrainian. "
    "3. FORMAT: Return ONLY the translated text."
    "4. REFINEMENT RULE: If the input is already in Ukrainian, act as a Senior Editor: "
    "   - Apply MINIMAL INTERVENTION: fix only grammar, punctuation, and clarity. "
    "   - PRESERVE VOICE: keep the original style, technical slang, and vocabulary. "
    "   - TECHNICAL CONTEXT: do not change technical metaphors or 'sanitize' the tone. "
    "5. PUNCTUATION LIMIT: ABSOLUTELY FORBID introducing new semicolons (;). Use periods or commas instead. Only allow semicolons if they were already present in the original input. For complex sentence joins, use a period. "
)

# --- Core Functions ---
def perform_auto_copy():
    # Simulates Ctrl+C to copy selected text to the clipboard.
    pyperclip.copy("")  # Clear clipboard to detect new data

    # Simulate Ctrl+C
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(0x43, 0, 0, 0)  # 'C' key
    time.sleep(0.1)  # Increased delay for Windows buffer
    win32api.keybd_event(0x43, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

    # Wait for the clipboard to actually receive the text
    stop_at = time.time() + 0.8  # Increased timeout to 0.8s
    while time.time() < stop_at:
        content = pyperclip.paste()
        if content and content.strip():
            return True
        time.sleep(0.05)
    return False

class ResultWindow(tk.Toplevel):
    """Smart window that adapts UI for translation or chat"""
    def __init__(self, _title, text=None, is_chat=False, load_history=False):
        super().__init__(root)
        self.title("FixItAI")
        self.attributes("-topmost", False)
        self.is_chat = is_chat

        bg_dark, text_bg, text_fg, accent = "#1e1e1e", "#252526", "#d4d4d4", "#2e7d32"

        w, h = 900, 800 if is_chat else 700
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{int(sw/2-w/2)}+{int(sh/2-h/2)}")
        self.configure(bg=bg_dark)

        # 1. Main Text Area
        self.txt_area = tk.Text(
            self, wrap=cast(Literal["none", "char", "word"], tk.WORD), font=("Consolas", 12),
            bg=text_bg, fg=text_fg, insertbackground="white",
            padx=15, pady=15, relief="flat", bd=0, highlightthickness=0
        )

        if self.is_chat:
            # --- CHAT MODE UI ---
            self.txt_area.pack(expand=True, fill='both', padx=15, pady=(15, 10))

            self.input_frame = tk.Frame(self, bg=bg_dark)
            self.input_frame.pack(fill='x', padx=15, pady=(0, 15))

            self.input_field = tk.Text(
                self.input_frame, font=("Segue UI", 12),
                bg="#3c3c3c", fg="white", insertbackground="white",
                relief="flat", height=6
            )
            self.input_field.pack(side=cast(Literal["left", "right", "top", "bottom"], tk.LEFT), expand=True, fill='x')

            # Bind Shift+Enter (new line) and Enter (send)
            self.input_field.bind("<Return>", self._handle_return)

            # Load history or show a welcome message
            if load_history and current_chat_session is not None:
                try:
                    # Fetch history from API
                    history = cast(Any, current_chat_session).get_history() or []
                    for message in history:
                        # Skip non-dialogue roles
                        if message.role not in ["user", "model"]:
                            continue

                        role = "You" if message.role == "user" else "Agent"
                        text_content = ""

                        if message.parts:
                            # Filter out parts that are marked as 'thought'
                            parts_to_join = []
                            for part in message.parts:
                                if hasattr(part, 'thought') and part.thought:
                                    continue
                                if hasattr(part, 'text') and part.text:
                                    parts_to_join.append(part.text)

                            text_content = "".join(parts_to_join)

                        if text_content.strip():
                            self.append_message(role, text_content)
                except Exception as e:
                    print(f"Error loading history: {e}")
            elif text:
                self.append_message("Agent", text)

        else:
            # --- TRANSLATE/FIX MODE UI ---
            self.txt_area.pack(expand=True, fill='both', padx=15, pady=(15, 85))
            if text:
                self.txt_area.insert(tk.INSERT, text)

            self.copy_btn = tk.Button(
                self, text="Copy & Close", command=self.copy_and_close,
                bg=accent, fg="white", font=("Segue UI", 11, "bold"),
                padx=30, pady=10, relief="flat", activebackground="#388e3c",
                activeforeground="white", cursor="hand2"
            )
            self.copy_btn.place(relx=0.5, rely=1.0, y=-25, anchor='s')

        # Core bindings
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.bind_all("<Control-Key>", self.handle_control_keys)

        if self.is_chat:
            self.input_field.focus_set()
        threading.Thread(target=lambda: force_focus_by_title("FixItAI"), daemon=True).start()

    # --- Shared Methods ---
    def close_window(self, _event=None):
        # Destroys the Toplevel window safely
        self.destroy()

    def copy_and_close(self, _event=None):
        # Copies text and safely closes the window.
        final_text = self.txt_area.get("1.0", tk.END).strip()
        pyperclip.copy(final_text)
        winsound.Beep(1200, 100)
        self.close_window()

    def handle_control_keys(self, event):
        # Routes control keys (to fix Ctrl+C, Ctrl+V, Ctrl+A, on UA layout)
        # Use keysym to be layout-independent for common characters
        char = event.keysym.lower()
        if char == 'c': return self.manual_copy()
        elif char == 'v': return self.manual_paste()
        elif char == 'x': return self.manual_cut()
        elif char == 'a': return self.select_all()
        
        # Check for Ukrainian layout equivalents in Tkinter (usually cyrillic characters)
        # c -> с (cyrillic s), v -> м (cyrillic m), x -> ч (cyrillic ch), a -> ф (cyrillic f)
        if char in ('с', 'м', 'ч', 'ф'):
            if char == 'с': return self.manual_copy()
            elif char == 'м': return self.manual_paste()
            elif char == 'ч': return self.manual_cut()
            elif char == 'ф': return self.select_all()

        # Fallback to keycode for specific cases if needed
        if event.keycode == 67: return self.manual_copy()
        elif event.keycode == 86: return self.manual_paste()
        elif event.keycode == 88: return self.manual_cut()
        elif event.keycode == 65: return self.select_all()
        return None

    def _handle_return(self, event):
        # If Shift+Enter is pressed, insert a line break.
        if event.state & 0x1:  # Shift key
            return None
        # If just Enter is pressed, send the message.
        self.send_chat_message()
        return "break"

    def manual_copy(self, _event=None):
        try:
            focused_widget = self.focus_get()
            if focused_widget == self.txt_area:
                selected = self.txt_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            elif self.is_chat and hasattr(self, 'input_field') and focused_widget == self.input_field:
                selected = self.input_field.get(tk.SEL_FIRST, tk.SEL_LAST)
            else:
                # Default to selection from txt_area if something else is focused or nothing selected in focused
                selected = self.txt_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            
            if selected:
                pyperclip.copy(selected)
        except tk.TclError:
            pass
        return "break"

    def manual_paste(self, _event=None):
        focused_widget = self.focus_get()
        clipboard_content = pyperclip.paste()
        
        if self.is_chat and hasattr(self, 'input_field') and focused_widget == self.input_field:
            self.input_field.insert(tk.INSERT, clipboard_content)
        elif focused_widget == self.txt_area:
            # Check if txt_area is editable
            if self.txt_area.cget("state") == tk.NORMAL:
                self.txt_area.insert(tk.INSERT, clipboard_content)
        else:
            # Fallback behavior
            if self.is_chat and hasattr(self, 'input_field'):
                self.input_field.insert(tk.INSERT, clipboard_content)
            elif self.txt_area.cget("state") == tk.NORMAL:
                self.txt_area.insert(tk.INSERT, clipboard_content)
                
        return "break"  # Stops further propagation of the event in Tkinter.

    def manual_cut(self, _event=None):
        focused_widget = self.focus_get()
        # Cut should only happen on editable widgets
        is_editable = False
        if focused_widget == self.txt_area:
            is_editable = (self.txt_area.cget("state") == tk.NORMAL)
        elif self.is_chat and hasattr(self, 'input_field') and focused_widget == self.input_field:
            is_editable = True

        if not is_editable:
            return "break"

        self.manual_copy()
        try:
            if focused_widget == self.input_field:
                self.input_field.delete(tk.SEL_FIRST, tk.SEL_LAST)
            else:
                self.txt_area.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass
        return "break"

    def select_all(self, _event=None):
        focused_widget = self.focus_get()

        if focused_widget == self.txt_area:
            self.txt_area.tag_add(tk.SEL, "1.0", tk.END)
            self.txt_area.mark_set(tk.INSERT, "1.0")
        elif self.is_chat and hasattr(self, 'input_field') and focused_widget == self.input_field:
            self.input_field.tag_add(tk.SEL, "1.0", tk.END)
            self.input_field.mark_set(tk.INSERT, "1.0")
        else:
            # Default to txt_area
            self.txt_area.tag_add(tk.SEL, "1.0", tk.END)
            self.txt_area.mark_set(tk.INSERT, "1.0")

        return "break"

    # --- Chat Specific Methods ---
    def append_message(self, sender, text):
        # Formats and appends messages to chat area.
        self.txt_area.config(state=cast(Literal["normal", "disabled"], tk.NORMAL))
        
        # 1. Header with sender name
        header = f"\n[{sender.upper()}]:\n"
        self.txt_area.insert(tk.END, header, "bold_font")

        # 2. Clean up text from Markdown symbols
        # Replace ### Title with Title
        text = re.sub(r'(?m)^#+\s*(.*)', r'\1', text)
        
        # --- MODIFIED: More careful list replacement to avoid breaking layout ---
        # Replace * or - at the start of line with • only if it's a simple list
        text = re.sub(r'(?m)^(\s*)[*-]\s+', r'\1• ', text)

        # Remove inline code backticks `text` -> text
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # --- LaTeX style symbols cleanup ---
        # Arrows
        text = re.sub(r'\\(?:rightarrow|to)\$?', '→', text)
        text = re.sub(r'\\leftarrow\$?', '←', text)
        text = re.sub(r'\\leftrightarrow\$?', '↔', text)
        text = re.sub(r'\\Rightarrow\$?', '⇒', text)
        text = re.sub(r'\\Leftarrow\$?', '⇐', text)
        text = re.sub(r'\\Leftrightarrow\$?', '⇔', text)

        # Math & Logic
        text = re.sub(r'\\le\$?', '≤', text)
        text = re.sub(r'\\ge\$?', '≥', text)
        text = re.sub(r'\\neq\$?', '≠', text)
        text = re.sub(r'\\approx\$?', '≈', text)
        text = re.sub(r'\\times\$?', '×', text)
        text = re.sub(r'\\div\$?', '÷', text)

        # Clean up remaining dollar signs that might surround these symbols
        text = text.replace('$', '')
        
        content = text.strip() + "\n"
        
        # 3. Process bold text **bold**
        # re.split keeps the delimiter if it's in parentheses
        parts = re.split(r'(\*\*.*?\*\*)', content)
        
        for part in parts:
            if not part: continue
            if part.startswith("**") and part.endswith("**"):
                # Remove stars and apply bold tag
                clean_part = part[2:-2]
                self.txt_area.insert(tk.END, clean_part, "bold_font")
            else:
                self.txt_area.insert(tk.END, part)

        # 4. Footer line
        self.txt_area.insert(tk.END, "-"*40 + "\n")
        
        # Apply formatting and scroll
        self.txt_area.tag_configure("bold_font", font=("Consolas", 12, "bold"))
        self.txt_area.config(state=cast(Literal["normal", "disabled"], tk.DISABLED))
        self.txt_area.see(tk.END)

    def send_chat_message(self):
        # Sends a message to AI chat
        global current_chat_session
        user_text = self.input_field.get("1.0", tk.END).strip()
        if not user_text or not current_chat_session: return

        self.input_field.delete("1.0", tk.END)
        self.append_message("You", user_text)

        def run_async():
            try:
                # Get the response from AI
                if current_chat_session is not None:
                    response = cast(Any, current_chat_session).send_message(user_text)
                    
                    # Filter out thoughts from the immediate response as well
                    clean_text = ""
                    if response and hasattr(response, 'candidates') and response.candidates:
                        content = response.candidates[0].content
                        clean_parts = [p.text for p in content.parts if not (hasattr(p, 'thought') and p.thought) and hasattr(p, 'text')]
                        clean_text = "".join(clean_parts)
                    elif response:
                        # Fallback for simpler responses
                        clean_text = response.text if response.text else ""

                    self.after(0, self.append_message, "Agent", clean_text)
                    winsound.Beep(800, 50)
            except Exception as e:
                error_str = str(e)
                self.after(0, self.append_message, "Error", error_str)

        threading.Thread(target=run_async, daemon=True).start()

def call_ai_chat(is_new=True):
    # Starts/resumes chat and uses the prompt from the config file
    global current_chat_session, MODEL_NAME, CHAT_PROMPT
    client = get_ai_client()
    if not client: return

    if is_new or current_chat_session is None:
        # Explicitly initialize with empty history to avoid prompt leaking
        current_chat_session = client.chats.create(
            model=MODEL_NAME,
            history=[],
            config={"system_instruction": CHAT_PROMPT}
        )

        msg, load_hist = "Чат розпочато. Чим я можу допомогти?", False
        winsound.Beep(440, 100)
    else:
        msg, load_hist = None, True
        winsound.Beep(660, 100)

    create_window("AI Chat", text=msg, is_chat=True, load_history=load_hist)

def call_ai(mode):
    # Calls the AI API to process the clipboard text
    global MODEL_NAME, AI_API_KEY
    client = get_ai_client()
    if not client:
        create_window("Error", "No API Key")
        return

    if not perform_auto_copy():
        # Optional: play a low beep if copy failed
        winsound.Beep(200, 100)
        return

    # Get the full text and preserve line breaks
    text = pyperclip.paste()
    winsound.Beep(400, 50)

    instruction = PROMPT_FIX if mode == "fix" else PROMPT_TRANSLATE

    def run_request():
        try:
            # Use the global client and generate content
            response = None
            if client is not None:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=f"INPUT_TEXT:\n{text}",
                    config={"system_instruction": instruction}
                )

            # Filter out 'thought' parts from the response
            if response and hasattr(response, 'candidates') and response.candidates:
                content = response.candidates[0].content
                clean_parts = []
                for part in content.parts:
                    if hasattr(part, 'thought') and part.thought:
                        continue
                    if hasattr(part, 'text') and part.text:
                        clean_parts.append(part.text)
                cleaned_res = "".join(clean_parts).strip()
            else:
                cleaned_res = response.text.strip() if response and hasattr(response, "text") and response.text else ""

            # Robust cleaning of AI-generated wrappers
            for wrapper in ["'''", '"""', "```"]:
                if cleaned_res.startswith(wrapper) and cleaned_res.endswith(wrapper):
                    cleaned_res = cleaned_res[len(wrapper):-len(wrapper)].strip()

            # Show result in UI (ensure this is called on the main thread via threading if needed)
            create_window(f"FixItAI ({MODEL_NAME})", cleaned_res)
        except Exception as e:
            error_str = str(e)
            print(f"AI API Error: {error_str}")
            create_window("API Error", error_str)

        # Start the request thread (removed the recursive call inside)
    threading.Thread(target=run_request, daemon=True).start()

def call_ai_vision():
    # Extracts text from a clipboard image using AI API
    try:
        client = get_ai_client()
        if not client:
            return
            
        # Use ImageGrab to get data from the clipboard
        img = ImageGrab.grabclipboard()

        # Check if the clipboard contains an image
        if img is None:
            create_window("Error", "No image in the Clipboard!")
            winsound.Beep(300, 400)
            return

        if not isinstance(img, Image.Image):
            create_window("Error", "No image found in clipboard (maybe it's text?)")
            winsound.Beep(300, 400)
            return

        winsound.Beep(400, 50)

        def run_vision_request():
            try:
                # System prompt optimized for OCR
                vision_instruction = "OCR this image. If you see a table, format it clearly. Return ONLY the text. No yapping."

                # Use global client
                if client is not None:
                    response = cast(Any, client).models.generate_content(
                        model=MODEL_NAME,
                        contents=img,
                        config={"system_instruction": vision_instruction}
                    )
                    res = response.text.strip() if response and hasattr(response, 'text') and response.text else ""
                else:
                    res = ""

                # Robust cleaning of AI-generated wrappers
                for wrapper in ["'''", '"""', "```"]:
                    if res.startswith(wrapper) and res.endswith(wrapper):
                        res = res[len(wrapper):-len(wrapper)].strip()

                pyperclip.copy(res)
                create_window(f"Vision OCR ({MODEL_NAME})", res)
                winsound.Beep(1000, 100)

            except Exception as vision_err:
                # Show API error in the UI window
                error_str = str(vision_err)
                v_ocr_err_msg = f"AI Vision API Error:\n{error_str}"
                create_window("API Error", v_ocr_err_msg)
                winsound.Beep(200, 600)

            # Start the request in a separate thread to keep the UI responsive
        threading.Thread(target=run_vision_request, daemon=True).start()

    except Exception as sys_err:
        # Show system/clipboard error in the UI window
        sys_ocr_err_msg = f"System Error during OCR:\n{str(sys_err)}"
        create_window("System Error", sys_ocr_err_msg)
        winsound.Beep(200, 600)

def call_ai_vision_translate():
    """Extracts text from an image and translates it to Ukrainian."""
    try:
        client = get_ai_client()
        if not client: return

        img = ImageGrab.grabclipboard()
        if img is None or not isinstance(img, Image.Image):
            create_window("Error", "No image in the Clipboard!")
            winsound.Beep(300, 400)
            return

        winsound.Beep(400, 50)

        def run_vision_translate_request():
            try:
                # System prompt for OCR + Translation
                instruction = (
                    "OCR this image and TRANSLATE the extracted text to UKRAINIAN. "
                    "Return ONLY the translated text. Maintain formatting if possible. No yapping."
                )

                if client is not None:
                    response = cast(Any, client).models.generate_content(
                        model=MODEL_NAME,
                        contents=img,
                        config={"system_instruction": instruction}
                    )
                    res = response.text.strip() if response and hasattr(response, 'text') and response.text else ""
                else:
                    res = ""

                # Clean wrappers
                for wrapper in ["'''", '"""', "```"]:
                    if res.startswith(wrapper) and res.endswith(wrapper):
                        res = res[len(wrapper):-len(wrapper)].strip()

                pyperclip.copy(res)
                create_window(f"Vision Translate ({MODEL_NAME})", res)
                winsound.Beep(1000, 100)
            except Exception as vt_err:
                error_str = str(vt_err)
                create_window("API Error", error_str)
                winsound.Beep(200, 600)

        threading.Thread(target=run_vision_translate_request, daemon=True).start()
    except Exception as vts_err:
        vt_sys_error_msg = str(vts_err)
        create_window("System Error", vt_sys_error_msg)

def call_ai_describe_image():
    # Describes the content of an image from the clipboard and starts a chat
    global current_chat_session, MODEL_NAME, CHAT_PROMPT
    try:
        client = get_ai_client()
        if not client: return

        img = ImageGrab.grabclipboard()
        if img is None or not isinstance(img, Image.Image):
            threading.Thread(target=lambda: ResultWindow("Error", "No image in the Clipboard!"), daemon=True).start()
            winsound.Beep(300, 400)
            return

        winsound.Beep(400, 50)

        def run_describe_request():
            global current_chat_session
            try:
                # System instruction for vision chat
                instruction = (
                    f"{CHAT_PROMPT}\n\n"
                    "Ти — універсальний AI-аналітик зображень. Твоє завдання — об'єктивно, детально та структуровано описати вміст завантаженого файлу.\n\n"
                    "АЛГОРИТМ АНАЛІЗУ:\n"
                    "1. Визнач загальний контекст: що це за тип зображення (скріншот інтерфейсу, фотографія, художній арт, ілюстрація, схема тощо).\n"
                    "2. Проаналізуй головні елементи: виділи ключові об'єкти, персонажів, текстові блоки або деталі.\n"
                    "СТРУКТУРА ВІДПОВІДІ:\n"
                    "- **Тип контенту та загальна суть:** (Коротке визначення того, що перед тобою)\n"
                    "- **Детальний розбір вмісту:** (Покроковий опис усіх ключових об'єктів, елементів, тексту чи деталей, які видно на зображенні)\n"
                )

                # Create a new chat session for this image
                if client is not None:
                    current_chat_session = client.chats.create(
                        model=MODEL_NAME,
                        history=[],
                        config={"system_instruction": instruction}
                    )

                    # Send the image as the first message
                    prompt = "Проаналізуй цей скріншот:"
                    response = cast(Any, current_chat_session).send_message(message=[prompt, img])
                    res = response.text.strip() if response else ""
                else:
                    res = ""

                # Open Chat Window with the response
                create_window(f"AI Image Chat ({MODEL_NAME})", text=res, is_chat=True, load_history=True)
                winsound.Beep(1000, 100)
            except Exception as desc_err:
                desc_api_error_msg = f"AI Vision Error:\n{str(desc_err)}"
                create_window("API Error", desc_api_error_msg)
                winsound.Beep(200, 600)

        threading.Thread(target=run_describe_request, daemon=True).start()
    except Exception as desc_sys_err:
        desc_sys_error_msg = str(desc_sys_err)
        create_window("System Error", desc_sys_error_msg)

def call_ai_explain():
    # Copies text and asks AI to explain it
    global current_chat_session, MODEL_NAME, CHAT_PROMPT
    client = get_ai_client()
    if not client: return

    if not perform_auto_copy():
        winsound.Beep(200, 100)
        return

    selected_text = pyperclip.paste().strip()
    winsound.Beep(400, 50)

    # Combined instruction for the system role
    explain_system_prompt = (
        f"{CHAT_PROMPT}\n\n"
        "TASK: Explain the provided text. If it contains abbreviations, terms, or slang, decode them and explain their meaning."
    )

    # Create a session with a clean history
    current_chat_session = client.chats.create(
        model=MODEL_NAME,
        history=[],
        config={"system_instruction": explain_system_prompt}
    )

    def run_explain():
        try:
            # Sending the specific text to explain
            response = current_chat_session.send_message(f"Explain this:\n{selected_text}")
            # Opening the chat window with the result
            create_window("AI Chat (Explanation)", text=response.text, is_chat=True, load_history=True)
            winsound.Beep(800, 50)
        except Exception as e:
            error_str = str(e)
            create_window("Error", error_str)

    threading.Thread(target=run_explain, daemon=True).start()

def call_ai_summary():
    # Summarizes the selected text
    global current_chat_session, MODEL_NAME, CHAT_PROMPT
    client = get_ai_client()
    if not client: return

    if not perform_auto_copy():
        winsound.Beep(200, 100)
        return

    selected_text = pyperclip.paste().strip()
    winsound.Beep(400, 50)

    summary_system_prompt = (
        f"{CHAT_PROMPT}\n\n"
        "TASK: Create a very short and concise summary of the provided text. Use bullet points if necessary. Focus on the key facts."
    )

    current_chat_session = client.chats.create(
        model=MODEL_NAME,
        history=[],
        config={"system_instruction": summary_system_prompt}
    )

    def run_summary():
        try:
            response = current_chat_session.send_message(f"Summarize this:\n{selected_text}")
            create_window("AI Chat (Summary)", text=response.text, is_chat=True, load_history=True)
            winsound.Beep(800, 50)
        except Exception as e:
            error_str = str(e)
            create_window("Error", error_str)

    threading.Thread(target=run_summary, daemon=True).start()


def list_models_action():
    # Fetches available Google AI models and displays them in a ResultWindow.
    def fetch_and_show():
        client = get_ai_client()
        if not client:
            create_window("Error", "Please set your API Key in APIAndModel.txt first.")
            return

        try:
            # Use global client
            models = client.models.list()

            # Formatting the header
            output = [
                "--- AVAILABLE MODELS ---\n",
                "Copy the ID (e.g., 'gemma-3-27b-it') and paste it into APIAndModel.txt\n",
                "Then restart FixItAI to apply changes.\n",
                "=" * 50 + "\n"
            ]

            for m in models:
                if hasattr(m, 'name') and hasattr(m, 'display_name'):
                    # Formatting each entry for easy reading/copying
                    output.append(f"ID: {m.name}\nName: {m.display_name}\n")
                    output.append("-" * 30 + "\n")

            full_text = "".join(output)
            # Invoke the existing ResultWindow class
            create_window("Google Models List", full_text)

        except Exception as e:
            create_window("API Error", f"Failed to retrieve models: {str(e)}")

    # Run in a separate thread to keep the Tray Menu responsive
    threading.Thread(target=fetch_and_show, daemon=True).start()

def resize_and_center_window():
    # Resizes the active window and centers it on the screen.
    try:
        window = gw.getActiveWindow()
        if window:
            target_w = 1500
            target_h = 1100

            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)

            new_x = (screen_w - target_w) // 2
            new_y = (screen_h - target_h) // 2

            window.resizeTo(target_w, target_h)
            window.moveTo(new_x, new_y)

            winsound.Beep(1000, 50)
        else:
            winsound.Beep(300, 100)
    except Exception as e:
        print(f"Window Error: {e}")

def insert_text_template():
    # Pastes content from a predefined text template.
    filename = get_full_path("TextTemplate.txt")
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()

            old_clipboard = pyperclip.paste()
            pyperclip.copy(content)
            time.sleep(0.05)

            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(0x56, 0, 0, 0)  # V key
            time.sleep(0.05)
            win32api.keybd_event(0x56, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

            time.sleep(0.2)
            pyperclip.copy(old_clipboard)

            winsound.Beep(800, 50)
        except Exception as e:
            print(f"Error in template: {e}")
    else:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("Environment: Windows 11\nSteps to reproduce:\n1. ")
        winsound.Beep(300, 200)

def force_focus_by_title(_target_title="FixItAI"):
    # Forcibly activates the window and steals focus from the OS
    # Allow the window 0.1 seconds for full initialization.
    time.sleep(0.1)

    hwnd = win32gui.FindWindow(None, "FixItAI")
    if hwnd:
        # Fucking elven magic...
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32gui.SetForegroundWindow(hwnd)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

# --- Listeners ---
class CommandHandler(BaseHTTPRequestHandler):
    # noinspection PyPep8Naming
    def do_GET(self):
        # Extract the command name from the URL (e.g., /fix)
        action = self.path.strip("/")
        print(f"Received command: {action}")

        # Dispatch table: maps action name to (function, arguments)
        actions = {
            "fix": (call_ai, ("fix",)),
            "translate": (call_ai, ("translate",)),
            "template": (insert_text_template, ()),
            "center_window": (resize_and_center_window, ()),
            "vision": (call_ai_vision, ()),
            "ocr_translate": (call_ai_vision_translate, ()),
            "describe_img": (call_ai_describe_image, ()),
            "chat_new": (call_ai_chat, (True,)),
            "chat_resume": (call_ai_chat, (False,)),
            "explain": (call_ai_explain, ()),
            "summary": (call_ai_summary, ())
        }

        if action in actions:
            target_func, args = actions[action]
            # Run in a separate thread to avoid blocking the server.
            threading.Thread(target=target_func, args=args, daemon=True).start()
            winsound.Beep(440, 50)

        self.send_response(200)
        self.end_headers()

    def log_message(self, _format, *args):
        return # Disable console log spam

def run_command_server():
    try:
        server = HTTPServer(('127.0.0.1', 41769), cast(Any, CommandHandler))
        print("Server started on http://127.0.0.1:41769")
        server.serve_forever()
    except Exception as e:
        print(f"Failed to start server: {e}")
        # Try any interface if 127.0.0.1 fails for some reason
        try:
            server = HTTPServer(('0.0.0.0', 41769), cast(Any, CommandHandler))
            print("Server started on http://0.0.0.0:41769")
            server.serve_forever()
        except Exception as e2:
            print(f"Critical server error: {e2}")

# --- Tray Icon Logic ---
def create_image():
    # Creates a basic image for the tray icon.
    width, height = 64, 64
    image = Image.new('RGB', (width, height), color=(46, 125, 50))
    d = ImageDraw.Draw(image)
    d.text((10, 10), "AI", fill=(255, 255, 255), font_size=48)
    return image

def open_config_file():
    # Opens the API and Model config file.
    filename = get_full_path("APIAndModel.txt")
    if not os.path.exists(filename):
        load_config()
    os.startfile(filename)

def open_template_file():
    # Opens the template text file or creates it if missing.
    filename = get_full_path("TextTemplate.txt")
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            f.write("Environment: Windows 11\nSteps:\n1. ")
    os.startfile(filename)

def show_help():
    # Displays the help menu in a ResultWindow.
    help_text = (
        "FixItAI QUICK GUIDE\n"
        "----------------------------------\n\n"
        "CapsLock + [+]    : Correct the grammar or translate to English\n"
        "CapsLock + [-]    : Translate text to Ukrainian\n"
        "CapsLock + [*]    : Explain selected text and terms\n"
        "CapsLock + [/]    : Insert text from Template\n"
        "CapsLock + [Num5] : Resize the window to 1500x1100 and center it\n"
        "CapsLock + [Num1] : Extract and translate text from image to Ukrainian\n"
        "CapsLock + [Num4] : Describe image from Clipboard\n"
        "CapsLock + [Num7] : Extract text from Clipboard image\n"
        "CapsLock + [Num6] : Quick summary of selected text\n"
        "CapsLock + [Num8] : Start a new AI chat (previous chat history will be cleared)\n"
        "CapsLock + [Num9] : Resume previous AI chat\n"
        "\nShift + CapsLock  : To toggle CapsLock state\n"
        "\n"
        f"Current Model: {MODEL_NAME}\n"
    )
    create_window("FixItAI Help", help_text)
    winsound.Beep(600, 50)

def on_quit(current_icon, _item):
    # Gracefully shuts down the application.
    print("Closing FixItAI...")
    # Force to close existing AHK blocker instance.
    subprocess.run(["taskkill", "/F", "/IM", "FixItAIHotkeysBlocker.exe", "/T"],
                   capture_output=True, text=True, check=False)
    current_icon.stop()
    os._exit(0)

def setup_tray():
    # Initializes and runs the system tray.
    global tray_icon
    from pystray import MenuItem as Item

    # Creating the menu with new functional items
    menu = pystray.Menu(
        Item('List Available Models', list_models_action),
        Item('Open Config File', open_config_file),
        pystray.Menu.SEPARATOR,
        Item('Open Template File', open_template_file),
        Item('Help', show_help),
        Item('Exit', on_quit)
    )

    tray_icon = pystray.Icon(
        "FixItAI",
        icon=create_image(),
        title="FixItAI Assistant",
        menu=menu
    )
    tray_icon.run()

if __name__ == "__main__":
    # Force to close existing AHK blocker instance (if any).
    print("Terminating existing Hotkeys Blocker...")
    subprocess.run(["taskkill", "/F", "/IM", "FixItAIHotkeysBlocker.exe", "/T"],
                   capture_output=True, text=True, check=False)

    ahk_path = get_full_path(os.path.join("FixItAIHotkeysBlocker", "FixItAIHotkeysBlocker.exe"))

    if os.path.exists(ahk_path):
        print(f"Starting AHK from: {ahk_path}")
        ahk_process = subprocess.Popen(ahk_path)
        print(f"AHK process started with PID: {ahk_process.pid}")
    else:
        print(f"ERROR: AHK file not found at {ahk_path}")

    # Initialize the single Tkinter root
    root = tk.Tk()
    root.withdraw() # Hide the main root window
    check_queue() # Start processing the window creation queue

    threading.Thread(target=setup_tray, daemon=True).start()
    threading.Thread(target=run_command_server, daemon=True).start()

    print(f"FixItAI started. Waiting for AHK commands on port 41769...")
    root.mainloop()