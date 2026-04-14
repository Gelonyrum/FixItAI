#Requires AutoHotkey v2.0
#NoTrayIcon

SetCapsLockState "AlwaysOff"

; Allow toggling CapsLock via Shift + CapsLock
+CapsLock::
{
    if GetKeyState("CapsLock", "T")
        SetCapsLockState "AlwaysOff"
    else
        SetCapsLockState "AlwaysOn"
}

; Global Hotkeys
CapsLock & NumpadAdd::  SendCmd("fix")            ; Alt + [+]
CapsLock & NumpadSub::  SendCmd("translate")      ; Alt + [-]
CapsLock & NumpadMult:: SendCmd("explain")        ; Alt + [*]
CapsLock & NumpadDiv::  SendCmd("template")       ; Alt + [/]
CapsLock & Numpad5::    SendCmd("center_window")  ; Alt + [Num5]
CapsLock & Numpad4::    SendCmd("describe_img")   ; Alt + [Num4]
CapsLock & Numpad7::    SendCmd("vision")         ; Alt + [Num7]
CapsLock & Numpad6::    SendCmd("summary")        ; Alt + [Num6]
CapsLock & Numpad8::    SendCmd("chat_new")       ; Alt + [Num8]
CapsLock & Numpad9::    SendCmd("chat_resume")    ; Alt + [Num9]

SendCmd(action) {
    static lastClick := 0
    currentTime := A_TickCount
    
    if (currentTime - lastClick < 500) {
        return
    }
    lastClick := currentTime
    
    ; RunHide запускає команду у фоні (без вікна консолі)
    ; curl просто смикає URL і відразу закривається
    Run('curl -s "http://127.0.0.1:41769/' . action . '"', , "Hide")
}

; Volume Control (Step 1%)
Volume_Up::   SoundSetVolume "+1"
Volume_Down:: SoundSetVolume "-1"