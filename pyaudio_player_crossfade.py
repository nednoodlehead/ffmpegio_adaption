from time import sleep
import ffmpegio
import pyaudio
from contextlib import contextmanager
from threading import Thread
from queue import Empty, Queue

from testfile_generator import testfiles

from ctypes import c_short
import numpy as np


def add_carrays(ArrayType, xbuf, ybuf):
    # x = np.frombuffer(xbuf,'i2')
    # y = np.frombuffer(ybuf,'i2')
    # print(len(x))
    # return (x+y).tobytes()
    x = ArrayType.from_buffer_copy(xbuf)
    y = ArrayType.from_buffer_copy(ybuf)
    return bytes(ArrayType(*(xi + yi for xi, yi in zip(x, y))))


@contextmanager
def pyaudio_stream(
    rate, channels, width=None, unsigned=False, format=None, *args, **kwargs
):
    p = pyaudio.PyAudio()

    if format is None:
        if width is None:
            raise ValueError("Either width or format must be specified.")
        format = p.get_format_from_width(width, unsigned)

    try:
        stream = p.open(rate, channels, format, *args, **kwargs)
        try:
            stream.start_stream()
            yield stream
            stream.stop_stream()
        finally:
            stream.close()
    finally:
        p.terminate()


ar = 44100  # playback sampling rate
ac = 2  # number of channels
layout = "stereo"
width = 2  # signed 2-byte integer format
sample_fmt = "s16"
bps = width * ac  # number of bytes per sample

tfade = 0.5  # cross-fade duration
curve = "qua"  # fading pattern
nfade = round(tfade * ar) # number of samples with fade effect = number of samples in each read block
nblk = nfade * bps  # number of bytes in each read block

que = Queue(2)  # ffmpegio-pyaudio data path, double buffered
buf = b""  # buffer for pyaudio callback

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
                        que.put(last_blk[: n], True, T)
                    last_blk = last_blk[n :] + (blk or b"")
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

    return


ncount = 0
def pyaudio_callback(_, nblk, *__):
    global buf, ncount

    # if not enough data in buffer, replenish from the reader thread
    nreq = nblk * bps  # requested number of bytes
    nbuf = len(buf)
    while nbuf < nreq:
        try:
            # wait longer if buffer is empty (only first time?)
            new_data = que.get(True, nblk / ar if nbuf else 1)
            if new_data is None:
                # end-of-stream reached
                return (b"", pyaudio.paComplete)

            buf = buf + new_data
            nbuf = len(buf)
        except Empty:
            print(f"failed to read data from FFmpeg")
            return (b"", pyaudio.paAbort)

    # enough data in the local buffer
    data = buf[:nreq]
    buf = buf[nreq:]

    # if last data, wait for end-of-stream None
    if len(data) < nblk:
        que.get(True, nblk / ar)

    ncount += len(data)

    return (data, pyaudio.paContinue)

nfiles = 4
with testfiles(nfiles, 2, 3) as files:

    reader = Thread(target=file_reader, args=[files])
    reader.start()

    with pyaudio_stream(
        rate=ar,
        channels=ac,
        width=width,
        output=True,
        stream_callback=pyaudio_callback,
    ) as stream:

        # wait for stream to finish
        while stream.is_active():
            sleep(0.1)

    reader.join()
