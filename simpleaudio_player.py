import ffmpegio
import simpleaudio as sa
from pprint import pprint

from testfile_generator import testfiles

with testfiles() as files:
    file = files[0]
        
    # grab the file info
    info = ffmpegio.probe.full_details(file)
    sinfo = next((s for s in info["streams"] if s["codec_type"] == "audio"))
    pprint(sinfo)

    sample_rate = int(sinfo["sample_rate"])
    num_channels = 2  # int(sinfo["channels"]) # force stereo
    sample_fmt = "s16"  # force signed 16-bit (simpleaudio only supports integer-multiple byte formats)
    bytes_per_sample = 2  # s16 = 2 bytes/sample

    # estimate the number of samples (try stream duration first, if not available use container duration)
    nb_samples = int(
        float(sinfo.get("duration", info["format"].get("duration")) * sample_rate)
    )

    # preallocate the buffer
    ntotal = nb_samples * num_channels  # total data size in number of bytes
    audio_data = bytearray(ntotal)  # playback buffer

    # open ffmpegio's stream-reader to read nblk samples at a time
    nblk = sample_rate  # 1 second (you can use any number you wish)
    with ffmpegio.open(
        file, "ra", sample_fmt=sample_fmt, ac=num_channels, blocksize=nblk
    ) as f:

        # read the first block of data and place them on the playback buffer
        data = f.read(nblk)["buffer"]
        nwritten = len(data)
        audio_data[:nwritten] = data

        # start the audio player (before finish loading the data)
        play_obj = sa.play_buffer(audio_data, num_channels, bytes_per_sample, sample_rate)

        # queue up rest of the data while playing
        for block in f:  # process one block at a time
            # make sure not to overflow the playback buffer
            data = block["buffer"]
            n = len(data)
            nend = min(nwritten + n, ntotal)
            audio_data[nwritten:nend] = data[: nend - nwritten]
            nwritten = nend  # update bytes written

    play_obj.wait_done()
    