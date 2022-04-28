# ffmpeg-helper

ffmpeg-helper is a simple GUI to aid in the interaction with ffmpeg for a few specific (and simple) use cases.  
It helps you to crop, scale and cut a video. It supports a few video and audio codecs and containers.  
It was made to be used in Windows, and assumes you have ffmpeg installed and in your PATH.  
It also lets you probe the input file (with ffprobe) to check it's streams info.    
That's it.  
  
![fmpeg-helper GUI](https://i.ibb.co/0hsGdwN/Captura-de-pantalla-2022-04-25-214508.png)  
  
---  
  
# TODO  

## General feature  
* **If ffmpeg exits on error, show what the error was.**  
* Add automatic probe and show streams with names and positions.  
* ~~Maintein output file name.~~  
* ~~Define output filename before calling ffadapter.~~  
* Start processing file right after output filename has been selected. (maybe)  
* Add mp3 (or other audio) output without video (codec:video -> no video).  
* Add mp4 (and or other video formats) for additional audio input.  
* Add fade-in/fade-out support (for video).  
* Add rotate support.  
* Add subtitle stream support.  
* Add subtitle burning video filter.  
* ~~Add cancel encode option.~~
* Add metadata input.  
* Add 1 image loop video option.  
* Add log of executed command.  
* Add play sound when finished.  
* Show ffmpeg error message in error window message.  
* **Check aditional audio position in ffmpeg command**  
* Add 2-pass encoding support  

## GUI Design  
* ~~Show output file size in finished process message.~~  
* ~~Add other audio input options eg: wav, aac ,etc~~ Added mp3, aac, opus, ogg and wav.  
* ~~Add OGG vorbis input in aditional audio filechooser.~~  
* Check if aditional audio is selected before Apply.  
* ~~Make progressbar the same with as the statusbar.~~  
* Select correct container when new file is selected and video codec is 'copy'.  

## GUI Behaviour  
* ~~Set default audio codec combo when video codec is selected~~ Done.  
* Not necesary - Set automatic video bitrate when video codec is selected (or default?)  
* **If the main window is closed and ffmpeg is running, ask to stop process.**  

