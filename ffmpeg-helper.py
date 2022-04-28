#!C:\msys64\mingw64\bin\python3.9.exe
"""
class FFmpegGui
    Main gui for this simple FFmpeg helper program.

class StreamsWindow
    Dialog window showing the file's streams information

Helper functions:
    filesize
        return formatted string of the order of magnitude of the file size
    
    start_log
        set up & start logging
"""

from multiprocessing import Process, Pipe, freeze_support
import ctypes
import logging
import os

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gtk, GLib, Gdk, Pango

# settings = Gtk.Settings.get_default()
# settings.set_property("gtk-theme-name", "Windows10")
# settings.set_property("gtk-application-prefer-dark-theme", False)

import ffadapter

GLADE_PATH = "ui/"
FFMPEG_HELPER_ID = u'dalejfer.ffmpeghelper.0.5'

class FFmpegGui:
    """Class representing the programs gui."""

    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_file(GLADE_PATH + "main.glade")
        builder.connect_signals(self)
        # declare class attributes - gui widgets
        self.window = builder.get_object("window")
        self.filechooser = builder.get_object("filechooserbutton")
        self.video_codec_combo = builder.get_object("combo_videocodec")
        self.container_combo = builder.get_object("combo_container")
        self.crf_spin = builder.get_object("spin_crf")
        self.preset_combo = builder.get_object("combo_preset")
        self.video_bitrate_entry = builder.get_object("entry_video_bitrate")
        self.video_bitrate_order = builder.get_object("combo_video_bitrate_order")
        self.frame_rate_combo = builder.get_object("combo_frame_rate")
        self.scale_switch = builder.get_object("switch_scale")
        self.scale_height_entry = builder.get_object("entry_scale_height")
        self.cut_switch = builder.get_object("switch_cut")
        self.cut_start_entry = builder.get_object("entry_cut_start")
        self.cut_end_entry = builder.get_object("entry_cut_end")
        self.crop_switch = builder.get_object("switch_crop")
        self.crop_width_entry = builder.get_object("entry_crop_width")
        self.crop_height_entry = builder.get_object("entry_crop_height")
        self.crop_x_entry = builder.get_object("entry_crop_x")
        self.crop_y_entry = builder.get_object("entry_crop_y")
        self.audio_switch = builder.get_object("switch_audio")
        self.audio_filechooser = builder.get_object("filechooser_audio")
        self.audio_codec_combo = builder.get_object("combo_audiocodec")
        self.audio_bitrate_entry = builder.get_object("entry_audio_bitrate")
        self.audio_birtare_order = builder.get_object("combo_audio_bitrate_order")
        self.output_switch = builder.get_object("switch_output")
        self.output = builder.get_object("button_name")
        self.apply_button = builder.get_object("button_apply")
        self.cancel_button = builder.get_object("button_cancel")
        self.statusbar = builder.get_object("statusbar")
        self.probe_button = builder.get_object("button_probe")
        self.progressbar = builder.get_object("progressbar")
        self.streams_window = None

        self.apply_button.set_always_show_image(True)
        self.cancel_button.set_always_show_image(True)

        # add css for statusbar
        screen = Gdk.Screen.get_default()
        css_provider = Gtk.CssProvider()
        # css_provider.load_from_path("./themes/Default/gtk-3.0/gtk.css")
        css_provider.load_from_path(".\\css\\main.css")
        context = Gtk.StyleContext()
        context.add_provider_for_screen(screen, css_provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.context = self.statusbar.get_context_id("main")
        self.statusbar.push(self.context, "Ready...")
        self._set_statusbar_bg("ready") # only changes css

        self.scale_switch.connect("notify::active", self.on_scale_activate)
        self.cut_switch.connect("notify::active", self.on_cut_activate)
        self.crop_switch.connect("notify::active", self.on_crop_activate)
        self.audio_switch.connect("notify::active", self.on_audio_activate)
        self.output_switch.connect("notify::active", self.on_output_activate)
        self.window.connect("delete-event", Gtk.main_quit)

        output_button_label = self.output.get_child()
        output_button_label.set_line_wrap(True)
        output_button_label.set_max_width_chars(30)
        output_button_label.set_ellipsize(Pango.EllipsizeMode.END)

        logging.info("Main - Show window.")
        self.conn1 = None
        self.window.show()

    def on_btn_cancel_clicked(self, button):
        """Make worker process call sigterm on ffmpeg subproces."""
        # send message
        if self.conn1 is not None:
            self.conn1.send("Cancel")
            # ocultar cartel
            button.set_sensitive(False)

    def on_apply_clicked(self, button, data=None):
        """Check all user input, then call ffmpeg as separate process."""
        # check input filename
        in_filename = self.filechooser.get_filename()
        if not in_filename:
            self._simple_message_dialog("You must select an input file.", 2)
            return

        options = {}
        options["input"] = in_filename
        # check video codec and its configs
        videocodec = self._combo_get_selected(self.video_codec_combo, 1)
        options["videocodec"] = videocodec
        options["container"] = self._combo_get_selected(self.container_combo)
        if videocodec != "copy":
            # bitrate only necessary for vp8 and vp9
            if videocodec == "libvpx":
                options["vbitrate"] = str(self.video_bitrate_entry.get_text()) + \
                                      self._combo_get_selected(self.video_bitrate_order, 1)
            elif videocodec == "livpx-vp9":
                options["vbitrate"] = "0" # must be 0 to use crf for vp9
            # crf
            options["crf"] = str(self.crf_spin.get_value_as_int())
            # preset
            if videocodec in ("libx264", "libx265"):
                options["preset"] = self._combo_get_selected(self.preset_combo, 1)
            # framerate
            framerate = self._combo_get_selected(self.frame_rate_combo)
            if framerate != "none":
                options["framerate"] = framerate
            # scale
            if self.scale_switch.get_active():
                # if switch IS active, get scale hieght value
                options["scale"] = self.scale_height_entry.get_text()
            # crop
            if self.crop_switch.get_active():
                options["crop"] = {"width": self.crop_width_entry.get_text(),
                                   "height": self.crop_height_entry.get_text(),
                                   "x": self.crop_x_entry.get_text(),
                                   "y": self.crop_y_entry.get_text()}
        # cut video filter can be used without re-encoding (video codec)
        if self.cut_switch.get_active():
            # TODO: check if end - start > 0
            options["cut"] = {"start": self.cut_start_entry.get_text(),
                              "end": self.cut_end_entry.get_text()}
        # check if aditional audio is selected
        if self.audio_switch.get_active():
            audio_in = self.audio_filechooser.get_filename()
            if not audio_in:
                msg = "You toggeled the additional audio switch but didn't select a file."
                self._simple_message_dialog("Wait", 1, msg)
                return
            else:
                options["in_audio"] = audio_in
        # check audio codec (and bitrate if selected)
        audiocodec = self._combo_get_selected(self.audio_codec_combo, 1)
        options["audiocodec"] = audiocodec
        if audiocodec not in ("copy", "an"):
            if self.audio_bitrate_entry.get_text() == "":
                self._simple_message_dialog("You must enter a bitrate for audio.", 2)
                return
            options["abitrate"] = self.audio_bitrate_entry.get_text() + \
                                  self._combo_get_selected(self.audio_birtare_order, 1)
        # output file name
        if self.output_switch.get_active():
            if self.output.get_label() == "file":
                self._simple_message_dialog("You must select an output file.", 2,
                                            "Output switch is ON, turn OFF for" + \
                                            " automatic file naming.")
                return
            options["output"] = self.output.get_label()
        else:
            # select automatic name from input filename and container
            options["output"] = ffadapter.generate_output_filename(options["input"],
                                                                   options["container"])

        logging.info("Options dictionary: %s", options)
        # print("gui.py options")
        # print(options)

        self.probe_button.set_sensitive(False)
        self.apply_button.set_visible(False)
        self.cancel_button.set_visible(True)

        logging.info("Calling ffadapter.py")
        self.conn1, conn2 = Pipe()
        process = Process(target=ffadapter.ffmpeg_encode, args=(options, conn2))
        process.start()
        self._set_statusbar_bg("working")
        self.statusbar.push(self.context, "Working...")
        GLib.timeout_add(100, self._check_process, process, self.conn1, options["output"])

    def progressbar_increment(self, increment):
        """progresbar increment implementation"""
        if isinstance(increment, str):
            self.progressbar.pulse()
        else:
            self.progressbar.set_fraction(increment)

    def _check_process(self, process, conn, out_file):
        """checks the ffmpeg process"""
        if process.is_alive():
            if conn.poll():
                try:
                    message = conn.recv()
                    logging.debug("GUI process: Message received: %s", message)
                    self.progressbar_increment(message)
                except EOFError as error:
                    logging.error("Error getting message from conn. %s", error)
                return True
            else: # nothing to receive, check again later
                # logging.debug("conn.poll is False")
                return True
        else:
            self.probe_button.set_sensitive(True)
            self.apply_button.set_visible(True)
            self.cancel_button.set_visible(False)
            self.cancel_button.set_sensitive(True)
            self._pop_statusbar()
            # self.output_switch.set_active(False)
            # self.name_button.set_label("file")
            if process.exitcode == 0:
                self.progressbar_increment(1.0)
                self.set_status("Done :)", "done", pop_it=False)
                # get output file's size
                size_msg = "New file's size is: {}".format(filesize(out_file))
                self._simple_message_dialog("File processed succesfuly",
                                            extra_text=size_msg)
                self._pop_statusbar()
                self.set_status("Ready...", pop_it=False)
                self.progressbar_increment(0.0)
            else:
                self.set_status("Error :(", status="error", pop_it=False)
                self._simple_message_dialog("File transcoding failed.", 1,
                                            "Exit code: {}".format(process.exitcode))
                self._pop_statusbar()
                self.set_status("Ready...", pop_it=False)
                self.progressbar_increment(0.0)
            return False

    def on_video_codec_selected(self, combo, data=None):
        """on video codec combo selected"""
        # the combo is a model-view widget, the view is what appears on the screen
        # the model is the data managed by gtk
        # the model is in this case a liststore (list of lists of 2 items)
        # the first item (0) is the viewing name, the second (1) the value needed
        selected = self._combo_get_selected(combo, 1)
        logging.info("the selected item is: %s", selected)
        if selected == "copy" or selected == "novideo":
            # should de-sensitivize + clear fields? + deactivate switched
            self.crf_spin.set_sensitive(False)
            self.preset_combo.set_sensitive(False)
            self.video_bitrate_entry.set_text("")
            self.video_bitrate_entry.set_sensitive(False)
            self.video_bitrate_order.set_sensitive(False)
            self.frame_rate_combo.set_sensitive(False)
            self.scale_switch.set_sensitive(False)
            self.scale_height_entry.set_text("")
            self.scale_height_entry.set_sensitive(False)
            self.crop_switch.set_active(False)
            self.crop_switch.set_sensitive(False)
        else:
            # TODO: set crf range for selected codec
            if selected =="libvpx":
                self.video_bitrate_entry.set_sensitive(True)
                self.video_bitrate_order.set_sensitive(True)
                self.preset_combo.set_sensitive(False)
                self.container_combo.set_active_id("webm")
                self.audio_codec_combo.set_active_id("vorbis")
                self.crf_spin.set_range(4, 63)
                self.crf_spin.set_value(10)
            elif selected == "libvpx-vp9":
                self.preset_combo.set_sensitive(False)
                self.video_bitrate_entry.set_sensitive(False)
                self.video_bitrate_order.set_sensitive(False)
                self.container_combo.set_active_id("webm")
                self.audio_codec_combo.set_active_id("opus")
                self.crf_spin.set_range(0, 63)
                self.crf_spin.set_value(31)
            elif selected in ("libx264", "libx265"):
                self.preset_combo.set_sensitive(True)
                self.video_bitrate_entry.set_sensitive(False)
                self.video_bitrate_order.set_sensitive(False)
                self.container_combo.set_active_id("mp4")
                self.crf_spin.set_range(0, 51)
                self.crf_spin.set_value(20)

            # enable whatever selected is
            self.crf_spin.set_sensitive(True)
            self.frame_rate_combo.set_sensitive(True)
            self.scale_switch.set_sensitive(True)
            self.crop_switch.set_sensitive(True)

    def on_scale_activate(self, switch, data=None):
        """on scale switch activate"""
        if switch.get_active():
            self.scale_height_entry.set_sensitive(True)
        else:
            self.scale_height_entry.set_sensitive(False)

    def on_cut_activate(self, switch, data=None):
        """on cut switch activate"""
        if switch.get_active():
            self.cut_start_entry.set_sensitive(True)
            self.cut_end_entry.set_sensitive(True)
        else:
            self.cut_start_entry.set_sensitive(False)
            self.cut_start_entry.set_text("0:00:00")
            self.cut_end_entry.set_sensitive(False)
            self.cut_end_entry.set_text("0:00:00")

    def on_crop_activate(self, switch, data=None):
        """on crop switch activate"""
        if switch.get_active():
            self.crop_width_entry.set_sensitive(True)
            self.crop_height_entry.set_sensitive(True)
            self.crop_x_entry.set_sensitive(True)
            self.crop_y_entry.set_sensitive(True)
        else:
            self.crop_width_entry.set_sensitive(False)
            self.crop_height_entry.set_sensitive(False)
            self.crop_x_entry.set_sensitive(False)
            self.crop_y_entry.set_sensitive(False)

    def on_audio_activate(self, switch, data=None):
        """on audio switch activate"""
        if switch.get_active():
            self.audio_filechooser.set_sensitive(True)
        else:
            self.audio_filechooser.set_sensitive(False)

    def on_filechooserbutton_file_set(self, widget, data=None):
        """on filechooserbutton file set docstring"""
        pass

    def on_output_activate(self, switch, data=None):
        """on output switch activated"""
        # enable name button
        if switch.get_active():
            self.output.set_sensitive(True)
        else:
            self.output.set_sensitive(False)

    def on_button_name_clicked(self, button, data=None):
        """Let the user select a new file name for output with a filechoosedialog.

        As this method does not ensure an output file name to be set,
        it's recomended to check later on if the filename given by the
        name_button.label is a valid filename. The check should consist
        of whether the label's text is still 'file' or not.
        """
        if self.filechooser.get_filename() is None:
            self.set_status("You must select a input file first.", "error")
            return
        fcd = Gtk.FileChooserDialog("Save a file", self.window,
                                    Gtk.FileChooserAction.SAVE,
                                    (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                     Gtk.STOCK_OK, Gtk.ResponseType.OK))
        fcd.set_filename(self.filechooser.get_filename())
        # fcd.set_current_name("Untitled.{}".format(self._combo_get_selected(self.container_combo)))
        fcd.set_do_overwrite_confirmation(True)

        response = fcd.run()
        if response == Gtk.ResponseType.OK:
            button.set_label(fcd.get_filename())
        elif response == Gtk.ResponseType.CANCEL:
            # stays as it was
            pass
        fcd.destroy()

    def on_audio_codec_selected(self, combo, data=None):
        """on audio codec combo selected"""
        selected = self._combo_get_selected(combo, 1)
        logging.info("the selected item is: %s", selected)
        if selected in ("copy", "an"):
            self.audio_bitrate_entry.set_text("")
            self.audio_bitrate_entry.set_sensitive(False)
            self.audio_birtare_order.set_sensitive(False)
        else:
            self.audio_bitrate_entry.set_sensitive(True)
            self.audio_bitrate_entry.set_text("128")
            self.audio_birtare_order.set_sensitive(True)

    def on_button_probe_clicked(self, button, data=None):
        """on probe butto clicked"""
        infile = self.filechooser.get_filename()
        if infile is None:
            self._simple_message_dialog("You must select a file first", 2)
            return
        # call subprocess
        conn1, conn2 = Pipe()
        process = Process(target=ffadapter.probe, args=(infile, conn2))
        process.start()
        button.set_sensitive(False)
        self.set_status("Working...", status="working", pop_it=False)
        GLib.timeout_add(300, self._check_probe, process, conn1)

    def _check_probe(self, process, conn):
        """check input file probe"""
        if process.is_alive():
            return True
        else:
            # ffprobe has finished
            # self.probe_button.set_sensitive(True)
            self._pop_statusbar()
            if process.exitcode == 0:
                try:
                    streams = conn.recv()
                except EOFError as error:
                    logging.error("Failed getting info from probe process. %s", error)
                    return False
                # show Streams window
                self.set_status("Done :)", status="done")
                StreamsWindow(self.window, streams, self.on_streams_window_destroyed)
            else:
                self.set_status("Error :(", status="error")
                self._simple_message_dialog("Probe failed", 1,
                                            "FFprobe exit code: {}".format(process.exitcode))
            return False

    def on_streams_window_destroyed(self):
        """What to do when Streams window is destroyed"""
        self.probe_button.set_sensitive(True)

    def _set_statusbar_bg(self, status="ready"):
        """set new css that changes the sb background color and caption"""
        name = "sb_{}".format(status)
        self.statusbar.set_name(name)
        # screen = Gdk.Screen.get_default()
        # css_provider = Gtk.CssProvider()
        # css_provider.load_from_path(".\\css\\{}.css".format(status))
        # context = Gtk.StyleContext()
        # context.add_provider_for_screen(screen, css_provider,
        #                                 Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def _simple_message_dialog(self, message, msg_type=0, extra_text=""):
        """Simple message dialog.

        type 0 -> INFO
        type 1 -> ERROR
        type 2 -> WARNING
        """
        if msg_type == 0:
            msg_type = Gtk.MessageType.INFO
        elif msg_type == 1:
            msg_type = Gtk.MessageType.ERROR
        elif msg_type == 2:
            msg_type = Gtk.MessageType.WARNING

        dialog = Gtk.MessageDialog(parent=self.window, flags=0, message_type=msg_type,
                                   buttons=Gtk.ButtonsType.OK, text=message)
        if extra_text:
            dialog.format_secondary_text(extra_text)
        dialog.run()
        dialog.destroy()

    def _combo_get_selected(self, combo, column=0):
        """returns combobox selected item"""
        liststore = combo.get_model()
        return liststore[combo.get_active_iter()][column]

    def _pop_statusbar(self, ready=True):
        """pops last statusbar message, if ready=True sets statusbar to Ready"""
        self.statusbar.pop(self.context)
        if ready:
            self.set_status("Ready...", status="ready", pop_it=False)

    def set_status(self, msg, status="ready", pop_it=True, timeout=2):
        """Set status bar message, and auto pop after 2 seconds."""
        self._set_statusbar_bg(status) # background color
        self.statusbar.push(self.context, msg)
        if pop_it:
            GLib.timeout_add_seconds(timeout, self._pop_statusbar)

class StreamsWindow:
    """Manages Streams info window"""
    def __init__(self, parent, streams, callback):
        self.parent_callback = callback
        builder = Gtk.Builder()
        builder.add_from_file(GLADE_PATH + "streams.glade")
        builder.connect_signals(self)
        window = builder.get_object("streams_window")
        stream_box = builder.get_object("streams_box")
        if streams:
            for index, stream in enumerate(streams):
                label = Gtk.Label()
                label.set_markup("<b>Stream #{}</b>\n{}".format(index, stream))
                label.set_xalign(0.0)
                stream_box.pack_start(label, False, False, 4)
        window.set_transient_for(parent)
        window.show_all()

    def on_streams_window_destroy(self, *args):
        """On destroy, call parent callback"""
        self.parent_callback()

def filesize(out_file):
    """Get output file's size and order of magnitude."""
    try:
        size = os.path.getsize(out_file)
    except OSError as err:
        logging.warning("Could not get output file size. %s", err)
        return u"Could not get output file size."
    if size < 1024:
        return u"{:.2f} bytes".format(size)
    elif size > 1024 and size < 1048576:
        return u"{:.2f} KiB".format(size / 1024)
    elif size > 1048576 and size < 1073741824:
        return u"{:.2f} MiB".format(size / 1048576)
    elif size > 1073741824:
        return u"{:.2f} GiB".format(size / 1073741824)

def main():
    """main fn"""
    start_log("debug")
    # start_log("info")
    logging.info("----------Starting-program----------")
    # set app user model id for taskbar icon resolution (Windows)
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(FFMPEG_HELPER_ID)
    dummy_gui = FFmpegGui()
    Gtk.main()
    logging.info("----------Ending-program----------")

def start_log(level="info"):
    """set up logging"""
    if level == "debug":
        # logging information wont be saved to a file
        logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s',
                            datefmt='%H:%M:%S', level=logging.DEBUG)
    elif level == "info":
        # logging info will be saved to a file
        logging.basicConfig(filename='log.txt', filemode='a',
                            format='%(asctime)s - %(levelname)s: %(message)s',
                            datefmt='%H:%M:%S', level=logging.INFO)

if __name__ == "__main__":
    # https://docs.python.org/3.9/library/multiprocessing.html#multiprocessing.freeze_support
    freeze_support() # needed for freezing with pyinstaller
    main()
