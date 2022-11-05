import threading
import time
from time import sleep
import ffmpegio
import pyaudio
from contextlib import contextmanager

from testfile_generator import testfiles


class Playback:
    ar = 44100  # playback sampling rate
    ac = 2  # number of channels
    width = 2  # signed 2-byte integer format
    sample_fmt = "s16"
    stream = None
    exited = threading.Event()
    # keeps track of active time played in the song
    pause = 0
    #
    timer = 0
    pause_list = []

    @contextmanager
    def pyaudio_stream(self, rate, channels, width=None, unsigned=False, format=None, *args, **kwargs):
        p = pyaudio.PyAudio()

        if format is None:
            if width is None:
                raise ValueError("Either width or format must be specified.")
            format = p.get_format_from_width(width, unsigned)

        try:
            self.stream = p.open(rate, channels, format, *args, **kwargs)
            try:
                self.stream.start_stream()
                yield self.stream
                self.stream.stop_stream()
            finally:
                self.stream.close()
        finally:
            p.terminate()

    def play(self, song):
        self.pause = time.time()
        self.pause_list.append(time.time() - self.pause)
        print(time.time() - self.pause)
        # open ffmpegio's stream-reader
        with ffmpegio.open(song, "ra", sample_fmt=self.sample_fmt, ac=self.ac, ar=self.ar, ss_in=sum(self.pause_list)) as f:  # sum(self.pause_list))\

            # define callback (2)
            def callback(_, nblk, *__):
                # read nblk samples from the ffmpeg and pass it onto pyaudio
                data = f.read(nblk)["buffer"]
                return data, pyaudio.paContinue


            with self.pyaudio_stream(
                    rate=self.ar,
                    channels=self.ac,
                    width=self.width,
                    output=True,
                    stream_callback=callback,
            ) as stream:
                # wait for stream to finish
                while stream.is_active():
                    self.exited.wait(0.1)


    def debug(self):
        print(self.stream.get_time())
        print(self.stream.is_active())

    def stop(self):
        print('stop?')
        self.pause_list.append(time.time() - self.pause)
        self.stream.stop_stream()
        self.exited.clear()

if __name__ == '__main__':
    mine = Playback()
    mus = r"F:\Punge Downloads\Downloads\American Football - I'll See You When We're Both Not So EmotionalJB4hFigwzNo.mp3"
    mine.play(mus)
# "F:\Punge Downloads\Downloads\American Football - I'll See You When We're Both Not So EmotionalJB4hFigwzNo.mp3"






