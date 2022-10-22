import time
from pydub import playback
from pyaudio_player import Playback
import pydub
import tkinter as tk
import threading

mine = Playback()
mus = r"F:\Downloads folder\cashier.mp4"
mus2 = r"F:\Punge Downloads\Downloads\Empire! Empire! (i was a lonely estate) - Everything is Connected and Everything Matters A Temporary Solution to a Permanent ProblemjUP-x4dZIgI5.mp3"


def bruh():
    mine.play(mus2)

def play_thr():
    print('asdjn')
    the = threading.Thread(target=bruh)
    the.start()
    print('asdhusadh')

def play_thr2():
    segment = pydub.AudioSegment.from_file(mus2)
    the = threading.Thread(target=playback._play_with_simpleaudio(segment))
    the.start()



root = tk.Tk()
root.geometry("400x400")
# play_thr(mus)
tk.Button(root, text="play", command=play_thr).pack()
tk.Button(root, text='stop', command=mine.stop).pack()
tk.Button(root, text='debug', command=mine.debug).pack()

root.mainloop()
