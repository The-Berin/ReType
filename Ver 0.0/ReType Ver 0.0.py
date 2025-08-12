import tkinter as tk
import pyautogui
import time



# Def Section

def quit():
    root.destroy()

def TempPrint():
    global ReadyText
    ReadyText = input.get()
    print(ReadyText)

def StartWriting():
    time.sleep(3)
    pyautogui.typewrite(ReadyText, interval=0.01)

root=tk.Tk()

root.title("ReType Alpha Ver 0.0")

root.geometry("500x200")

input = tk.StringVar()

TextEntry = tk.Entry(width="40", textvariable=input)

button2 = tk.Button(text="Initilize Text", command=TempPrint)

button3 = tk.Button(text="Print Text", command=StartWriting)

QuitButton = tk.Button(text ="Quit", command=quit)

# Pack

TextEntry.pack(pady=5)

button2.pack(padx=5, pady=5)

button3.pack(padx=5, pady=5)

QuitButton.pack(padx=20, pady=5)

root.mainloop()
