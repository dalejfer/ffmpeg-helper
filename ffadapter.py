"""
FFmpeg addapter module

helper functions
"""

import sys
import os
import time
import re
import logging
from datetime import datetime
from subprocess import Popen, PIPE, CREATE_NO_WINDOW
import shutil

def generate_output_filename(in_file, container):
    """generate an output file to prevent original overwrite

        check if available without generating new
            meaning, maybe available with new extension
            filename.avi -> filename.mp4
            would be ok
        if not available, generate"""
    logging.info("Generating output file.")
    input_file_path = os.path.dirname(in_file)
    input_file_name = os.path.splitext(os.path.basename(in_file))[0]
    base_file = os.path.join(input_file_path, input_file_name)
    # TODO check if all this concatenating is the proper way to do this
    if not os.path.exists(base_file + os.path.extsep + container):
        return base_file + os.path.extsep + container
    else:
        return base_file + "-" + time.strftime("%H%M%S") + os.path.extsep + container

def prepare_command(options):
    """refine command"""
    logging.info("Prepairing command.")
    # TODO: use config file with path to ffmpeg.exe
    command = [shutil.which("ffmpeg"), "-y"]
    # check if file exists
    in_file = options["input"]
    if os.path.exists(in_file):
        command.extend(["-i", in_file])
    else:
        logging.error("Error: Input file path does not exist")
        return False
    if "in_audio" in options:
        # set up to override the input video's audio if any
        # TODO: this assumes that the first input's video stream is 0:0 and its audio
        # stream is 0:1
        command.extend(["-i", options["in_audio"], "-map", "0:0", "-map", "1:0"])
    # video options will always be added
    command.extend(["-c:v", options["videocodec"]])
    if "crf" in options:
        command.extend(["-crf", options["crf"]])
    if "preset" in options:
        command.extend(["-preset", options["preset"]])
    if "vbitrate" in options:
        command.extend(["-b:v", options["vbitrate"]])
    if "framerate" in options:
        command.extend(["-r", options["framerate"]])
    # video filters
    video_filters = []
    if "crop" in options:
        video_filters.append("crop={}:{}:{}:{}".format(options["crop"]["width"],
                                                       options["crop"]["height"],
                                                       options["crop"]["x"],
                                                       options["crop"]["y"]))
    if "scale" in options:
        video_filters.append("scale=-1:{}".format(options["scale"]))
    if video_filters:
        command.extend(["-vf", '{}'.format(",".join(video_filters))])
    if "cut" in options:
        command.extend(["-ss", options["cut"]["start"],
                        "-to", options["cut"]["end"]])
    # codec:audio
    if options["audiocodec"] == "an":
        command.append("-an") # no audio
    else:
        command.extend(["-c:a", options["audiocodec"]]) # copy or re-encode
    if "abitrate" in options:
        command.extend(["-b:a", options["abitrate"]])
    # output file name
    if "output" in options:
        if os.path.exists(options["output"]): # unlikely, but possible
            logging.error("Error: Output file already exists.")
            return False
        else:
            command.append(options["output"])
    else:
        command.append(generate_output_filename(options["input"],
                                                options["container"]))
    logging.info("FFmpeg command done: %s", command)
    print("FFmpeg command done: ", command)
    return command

def time_difference(start, end):
    """get time difference between two timestamp strings in seconds"""
    logging.info("Getting time difference for cut.")
    # pattern1 = hh:mm:ss
    pattern1 = re.compile("^([0-9]|0[0-9]|1[0-9]|2[0-3]):[0-5]?[0-9]:[0-5]?[0-9]$")
    # pattern2 = hh:mm:ss.ms
    pattern2 = re.compile("^([0-9]|0[0-9]|1[0-9]|2[0-3]):[0-5]?[0-9]:[0-5]?[0-9].[0-9]*$")
    datetimes = []
    for timestamp in [start, end]:
        if pattern1.match(timestamp) is not None:
            datetimes.append(datetime.strptime(timestamp, "%H:%M:%S"))
        elif pattern2.match(timestamp) is not None:
            datetimes.append(datetime.strptime(timestamp, "%H:%M:%S.%f"))
        else:
            logging.error("Error: Timestamp doesn't match either pattern. %s",
                          str(timestamp))
            return False
    delta = datetimes[1] - datetimes[0]
    if delta.total_seconds() < 0:
        logging.error("Error: delta is negative, ffmpeg will fail.")
        return False
    return delta.total_seconds()

def get_output_duration(options):
    """return duration in seconds of output media"""
    logging.info("Obtaining output media duration (to calculate execution percentage.")
    # if cut option is set, duration is end - start
    if "cut" in options:
        return time_difference(options["cut"]["start"], options["cut"]["end"])
    # else duration is input file duration
    else:
        # get the media duration -> format duration -> container duration
        command = ["C:\\ffmpeg\\bin\\ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                   "default=noprint_wrappers=1:nokey=1", "-sexagesimal", options["input"]]
        with Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                   universal_newlines=True, env=os.environ) as ffprobe:
            # stdout should be just 1 line
            for line in ffprobe.stdout:
                try:
                    format_duration = line[:-1] # remove carrige return "0:01:40.200\n"
                    return time_difference("0:00:00", format_duration)
                except IndexError as error:
                    logging.error("Error getting file media duration. %s", error)
                    return False

def ffmpeg_encode(options, conn):
    """Encode with ffmpeg"""
    logging.info("ffmpeg_encode function start")
    # calculate duration of output media -> progressbar
    duration = get_output_duration(options)

    command = prepare_command(options)
    if command:
        with Popen(command, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW) as ffmpeg:
            for line in ffmpeg.stderr:
                if "time=" in line:
                    elapsed_str = line[line.index("time=")+5:line.index("time=")+16]
                    if duration:
                        # if we have duration, we can calculate percentage
                        elapsed = time_difference("0:00:00", elapsed_str)
                        percentage = elapsed / duration
                        # send percentage
                        logging.debug("FFmpeg process, percentage sent: %s",
                                      round(percentage, 3))
                        conn.send(round(percentage, 3))
                    else: # activity mode
                        # send pulse
                        conn.send(elapsed_str)
                if conn.poll():
                    try:
                        from_gui = conn.recv()
                        if from_gui == "Cancel":
                            ffmpeg.terminate() # send terminate signal
                    except IOError:
                        print("Error receiving message from gui thread on worker process")
        logging.info("FFmpeg returncode: %s", ffmpeg.returncode)
        sys.exit(ffmpeg.returncode)
    else:
        sys.exit(1)

def probe(infile, conn):
    """runs ffprobe on the file to get it's streams info

    ffprobe, unlike ffmpeg, send its output through stdout
    """
    logging.debug("Starting file probe with FFprobe.")
    command = [shutil.which("ffprobe"), "-v", "error", "-show_entries",
               "stream=codec_type,duration,codec_name,width,height,bit_rate,language",
               "-of", "default=noprint_wrappers=0:nokey=0", "-sexagesimal", "-i", infile]
    streams = []
    stream_info = ""
    with Popen(command, stdout=PIPE, universal_newlines=True) as ffprobe:
        for line in ffprobe.stdout:
            if "[STREAM]" in line:
                pass
            elif "[/STREAM]" in line:
                streams.append(stream_info)
                stream_info = ""
            else:
                stream_info += line
    logging.debug("returncode: %s", ffprobe.returncode)
    # print("ffadapter.py ffprobe results: ", streams)
    conn.send(streams)
    sys.exit(ffprobe.returncode)
