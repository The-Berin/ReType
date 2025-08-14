import tkinter as tk
import pyautogui
import time
import random
import math

index = 0

stopchance = 0

errorchance = 0

#ShortPause = 50

RandomErrors = ['jj', 'gh', 'ik', 'il', 'l;']

typo = random.choice(RandomErrors)

# Def Section

def quit():
    root.destroy()

def StartWriting():
    global index
    global ReadyText
    ReadyText = TextEntry.get("1.0",tk.END).strip()
    print(ReadyText)
    index = 0
    root.after(3000, TypeNextChar)

def ClrText():
    TextEntry.delete(1.0, tk.END)

def StopChance():
    global stopchance
    global errorchance
    stopchance = random.randint(1,10)
    print(f"Stop Chance: {stopchance}, Error Chance: {errorchance}")
    root.after(1000, StopChance)

def ErrorGen():
    global errorchance
    global ErrorCheck
    #ErrorCheckVar = ErrorCheckVar.get()
    if ErrorCheckVar.get() == True:
        errorchance = random.randint(1,100)
    else: errorchance = 0
    root.after(1000, ErrorGen)

def TypeNextChar():
    global ShortPause
    global stopchance
    global errorchance
    global index
    global typo
    global CurrentSpeedVar
    CurrentSpeedVar = CurrentSpeed.get()
    if stopchance == 10:
        ShortPause = 3000
    else:
        ShortPause = CurrentSpeedVar

    if ShortPause == 0:
        pyautogui.typewrite(ReadyText[index:])
        index = len(ReadyText)

    if index < len(ReadyText):
        pyautogui.typewrite(ReadyText[index])
        index += 1
        root.after(ShortPause, TypeNextChar)

    if errorchance == 100:
        pyautogui.typewrite(typo, 0.2)
        time.sleep(1)
        pyautogui.press('backspace')
        time.sleep(0.1)
        pyautogui.press('backspace')
        root.after(50, TypeNextChar)

def ErrorCheckToggleMessage(): # DEBUG, Erase this for final version and reference in ErrorCheck tk
    print("Error Check Toggled")

root=tk.Tk()

root.title("ReType Alpha Ver 0.0")

root.geometry("500x600")

root.iconbitmap(r"C:\Users\Baron\Desktop\ReType\ReType.ico")

input = tk.StringVar()

frame = tk.Frame()

TextEntry = tk.Text(frame, width="40", height="10")

button3 = tk.Button(frame, text="Print Text", command=StartWriting)

clrbtn = tk.Button(frame, text="Clear Text", command=ClrText)

SpeedSliderLabel = tk.Label(text="Typing Speed")

CurrentSpeed = tk.Scale(from_=10000, to=0, orient=tk.HORIZONTAL, showvalue=False)

ErrorCheckVar = tk.BooleanVar()
ErrorCheck = tk.Checkbutton(text="Errors", variable=ErrorCheckVar, command=ErrorCheckToggleMessage)

QuitButton = tk.Button(frame, text ="Quit", command=quit, fg="red", relief="groove", font=("TimesNewRoman", 12, 'bold')) # Leave Times New Roman there, it doesnt work without it for some reason

# Pack

frame.pack()

TextEntry.pack(pady=5, padx=5, expand=True, fill='both')

button3.pack(padx=5, pady=5, ipadx=10)

clrbtn.pack(pady=10, padx=10, ipadx=9)

SpeedSliderLabel.pack()

CurrentSpeed.pack()
CurrentSpeed.set(50)

ErrorCheck.pack()

QuitButton.pack(padx=20, pady=5, ipady=5, ipadx=22, side="bottom")

# Loops

root.after(1000, StopChance)

ErrorGen()

root.mainloop()
