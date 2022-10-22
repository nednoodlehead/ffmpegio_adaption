from math import log10
from tempfile import TemporaryDirectory
from contextlib import contextmanager
import ffmpegio
import random
from os import path

# fs_choices = [44100]
fs_choices = [8000, 16000, 22050, 32000, 44100, 48000, 96000]
ext_choices = [".wav", ".flac", ".mp3", ".m4a", ".ogg"]
# layout_choices = [("mono", 1), ("stereo", 2)]
layout_choices = [("stereo", 2)]


@contextmanager
def testfiles(nfiles=1, max_duration=1.0, min_duration=0.1, use_rand=False):
    with TemporaryDirectory() as tmpdir:

        def generate(i):
            fs = random.choice(fs_choices)
            nb_samples = max(int(fs * random.uniform(min_duration, max_duration)), 1)

            def generate_expr(is_rand):
                if is_rand:
                    expr = f"-2+random({random.randint(0,2**31)})"
                else:
                    f0 = int(2 * 10 ** (random.uniform(2, min(3, log10(fs / 2)))))
                    expr = f"0.9*sin({f0}*2*PI*t)"
                return expr

            layout = random.choice(layout_choices)
            expr = "|".join((generate_expr(i % 2 if use_rand else 0) for j in range(layout[1])))

            ext = random.choice(ext_choices)
            file = path.join(tmpdir, f"{i}{ext}")

            #fmt: off
            fg = ffmpegio.FilterGraph(
                [[
                    ("aevalsrc", expr, {"d": nb_samples / fs, "s": fs, "c": layout[0]}),
                    ("aformat", "s16"),
                ]])
            #fmt: on

            print(fg)

            ffmpegio.transcode(fg, file, f_in="lavfi", show_log=False)

            return file

        yield [generate(i) for i in range(nfiles)]
