🛑 **IMPORTANT: READ BEFORE STARTING**
-----------------------------------------------
FixItAI does not work "out of the box" without an API key. It is a client interface that operates exclusively via the Google API. The application does not include built-in AI computational power; instead, it serves as a bridge between your system and Google's cloud-based models. To activate the application, you MUST complete these 2 steps (takes approximately 1 minute):

• Obtain a free API key: [Google AI Studio](https://aistudio.google.com/api-keys)

• Configuration: Open the APIAndModel.txt file in the application folder and paste the key into the first line.

-----------------------------------------------
🚀 **FixItAI** is a powerful Windows system assistant that integrates the latest Google AI models directly into your workflow. Eliminate the need to switch between browser tabs: manage text, images, code, and windows using hotkeys.

📺 Feature demonstration video
-----------------------------------------------


See the assistant in action: from real-time grammar correction to leveraging Vision capabilities for screenshot analysis.

[![FixItAI Video Demo](https://github.com/user-attachments/assets/4cd109cc-7fb9-4e1a-b2a6-115474b1667c)](https://youtu.be/xs3nJSyk-3c)

**Note on video speed:**

FixItAI utilizes reasoning models to ensure maximum accuracy. 

To save time, segments where the AI analyzes complex queries have been sped up by 3x. 

This allows you to observe the full processing workflow without unnecessary delays.

✨ **Key Features**
-----------------------------------------------
📝 **Smart Editing (Grammar Fix):** Corrects grammar, style, and spelling. If the input is in Ukrainian, it automatically translates it into professional "IT English."

🌍 **Translator:** Quickly translates any selected text into Ukrainian.

🔍 **AI Explain & Summary:** Highlight an unfamiliar term, abbreviation, or a long article, and FixItAI will provide a clear explanation or a concise summary.

📸 **Vision & OCR:** Extract text from images or use AI to describe the image content.

💬 **Persistent Chat:** A full-featured chat interface (built with tkinter) that maintains message history and conversation context.

🛠 **Productivity Tools:**

  • Template-based text insertion;
  
  • Centering and resizing of active windows;
  
  • System tray integration for quick access to settings;

  • Fine-grained system volume control with ±1% increments (instead of the standard 2%) to prevent abrupt changes in volume levels.

⌨️ **Hotkeys:**
-----------------------------------------------
`CapsLock` + `Num +`	  Grammar correction / Translate to English

`CapsLock` + `Num -`	  Translate to Ukrainian

`CapsLock` + `Num /`	  Insert template text

`CapsLock` + `Num *`	  Explain term/text/abbreviation

`CapsLock` + `Num 7`	  OCR: Extract text from clipboard image

`CapsLock` + `Num 4`	  OCR: Describe image (with interactive refinement)

`CapsLock` + `Num 6`	  Summarize selected text

`CapsLock` + `Num 8/9`	New chat / Continue previous chat

⚙️ **Configuration**
-----------------------------------------------
• Open the APIAndModel.txt file in the application directory.

• Add your Google AI API Key (you can generate one here: https://aistudio.google.com/api-keys), the model name (a list of models can be viewed via the "List Available Models" option in the system tray context menu), and a system prompt (which will serve as the baseline for all communication in any window where dialogue is enabled).

• Run FixItAI.exe.

• Use Shift + CapsLock to toggle the default CapsLock state.

🔒 **Privacy and Security**
-----------------------------------------------
• **Zero Data Collection:** FixItAI is an open-source client. The application does not collect, store, or transmit your data to any third-party servers.

• **Direct Connection:** All requests are sent directly from your local machine to Google Generative AI servers using your personal API key.

**Important Note Regarding Google API:**

• **Free Tier:** According to Google's policy, data submitted via the free API tier may be used by the company to train and improve its models.

• **Paid Tier (Pay-as-you-go):** If you use a paid plan through the Google Cloud Console, your data remains confidential, is not used for model training, and is protected by enterprise-grade privacy standards.

• **Local UI:** The entire user interface and hotkey processing are handled locally on your system.

🔨 **Build from Source**
-----------------------------------------------
To compile a custom executable after making code changes, use PyInstaller.

Prerequisites:
Ensure that all dependencies are installed and that the Icons folder containing the project icon is located in the root directory.

Build command:

`pyinstaller --noconfirm --onefile --windowed --name "FixItAI" --collect-submodules pynput --collect-submodules PIL --add-data "Icons;Icons" --icon="Icons/FixItAI.ico" FixItAI.py`

Key interception logic is implemented as a separate component to ensure stability and performance on Windows.

Customizing Hotkeys: To change the key combinations (e.g., using a different key instead of CapsLock), edit the source .ahk file located in the FixItAIHotkeysBlocker folder.

Recompilation: After modifying the hotkeys, recompile the file into an .exe using Ahk2Exe (found in the Compiler folder).

File Naming: The resulting file must be named FixItAIHotkeysBlocker.exe and placed in the appropriate subdirectory so the Python script can initialize it upon startup.

## ⚖️ Licensing & Commercial Use
This project is licensed under the **AGPL-3.0 License**. 

**IMPORTANT:** For-profit use or integration into proprietary (closed-source) software is strictly prohibited by the terms of this license unless you open-source your entire project. 

If you wish to use **FixItAI** for commercial purposes without opening your source code, you **MUST** obtain a commercial license from the author. 

Additionally, if you prefer, I can make this 100% local with unlimited tokens, provided your hardware can handle it. Feel free to contact me for collaboration.

Contact: email - gelonyrum@gmail.com or telegram - https://t.me/Gelonyrum
