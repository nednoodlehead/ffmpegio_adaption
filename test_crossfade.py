import ffmpegio
from threading import Thread
from queue import Empty, Queue

from testfile_generator import testfiles

from ctypes import c_short
import numpy as np
import io
from matplotlib import pyplot as plt

import simpleaudio as sa

def add_carrays(ArrayType, xbuf, ybuf):
    x = np.frombuffer(xbuf, "i2")
    y = np.frombuffer(ybuf, "i2")
    return (x + y).tobytes()
    # x = ArrayType.from_buffer_copy(xbuf)
    # y = ArrayType.from_buffer_copy(ybuf)
    # return bytes(ArrayType(*(xi + yi for xi, yi in zip(x, y))))


ar = 44100  # playback sampling rate
ac = 2  # number of channels
layout = "stereo"
width = 2  # signed 2-byte integer format
sample_fmt = "s16"
bps = width * ac  # number of bytes per sample

tfade = 0.5  # cross-fade duration
curve = "iqsin"  # fading pattern, default tri causes saturation
nfade = round(
    tfade * ar
)  # number of samples with fade effect = number of samples in each read block
nblk = nfade * bps  # number of bytes in each read block

que = Queue()  # ffmpegio-pyaudio data path, double buffered

ShortArray = c_short * (nfade * ac)


def file_reader(files):
    # open ffmpegio's stream-reader
    def process_file(file, fout_data):

        # grab the duration
        T = float(
            ffmpegio.probe.audio_streams_basic(file, 0, ["duration"])[0]["duration"]
        )

        # form the filterchain
        af = (
            f"aformat={sample_fmt}:{ar}:{layout}"
            f",afade=in:d={tfade}:curve={curve}"
            f",afade=out:st={T-tfade}:d={tfade}:curve={curve}"
        )
        print(af)

        # read data
        with ffmpegio.open(
            file,
            "ra",
            af=af,
            blocksize=nfade,
            sample_fmt=sample_fmt,
            ac=ac,
            ar=ar,
            # show_log=True,
        ) as f:
            # read first block and combine with fout_data
            blk = f.read(nfade)["buffer"]
            if blk is None:
                # empty data?
                return b""

            # align the cross-fade blocks
            nfin = 0 if blk is None else len(blk)
            nfout = len(fout_data)
            if nfout < nblk:
                # last file shorter than tfade
                fout_data = fout_data + b"\0" * (nblk - nfout)
            if nfin < nblk:
                # this file shorter than tfade
                blk = b"\0" * (nblk - nfin) + (blk or b"")

            # mix fade-out and fade-in blocks for the crossfade effect
            last_blk = add_carrays(ShortArray, fout_data, blk)

            # process the rest of the data blocks from the file
            for frame in f:
                if frame is None:
                    return last_blk

                blk = frame["buffer"]  # nblk bytes of data
                n = len(blk)
                if n < nblk:
                    # this is the last block of this file
                    # keep the last nblk bytes (nfade samples) and queue the earlier
                    if nblk - n:
                        que.put(last_blk[:n], True, T)
                    last_blk = last_blk[n:] + (blk or b"")
                    break  # just in case
                else:
                    que.put(last_blk, True, T)
                    last_blk = blk

            # last nfade-sample block containes the fade-out effect
            # return it so the block can be mixed with the fade-in block of
            # the subsequent file
            return last_blk

    fout_data = b"\0" * nblk  # fade-out block, initialize to all 0
    for file in files:
        fout_data = process_file(file, fout_data)
    que.put(fout_data, True, tfade)  # queue last fade-out block
    que.put(None, True, 2 * tfade)  # queue end-of-stream


nfiles = 2
with testfiles(nfiles, 2, 3) as files:

    reader = Thread(target=file_reader, args=[files])
    reader.start()
    reader.join()

    _, x = ffmpegio.audio.read(files[1], ac=ac, ar=ar, sample_fmt=sample_fmt)
    x = np.frombuffer(x["buffer"], "i2").reshape(-1, ac)

xbuf = io.BytesIO()
while not que.empty():
    blk = que.get_nowait()
    if blk is not None:
        xbuf.write(blk)


y = np.frombuffer(xbuf.getvalue(), "i2").reshape(-1, ac)

# sa.play_buffer(y,ac,width,ar)
sa.play_buffer(x,ac,width,ar)

# plt.plot(np.arange(x.shape[0]) / ar, x)
plt.plot(np.arange(y.shape[0]) / ar, y[:,0])
plt.figure()
plt.specgram(y[:,0], ar)
plt.show()
