# Tomoji

Tomoji is a command-line tool to extract accurate text subtitles (SRT format) from DVD and Blu-ray disc formats. DVD/Blu-ray discs store subtitle data as images, so converting them to text requires OCR (optical character recognition). Other tools for this purpose have had low-quality OCR that made them especially unsuitable for languages with complicated non-Latin scripts (e.g. Japanese).

Tomoji is implemented as a small Python wrapper/glue script; the real work is done by [MKVToolNix](https://mkvtoolnix.download/), [OGMRip](http://ogmrip.sourceforge.net/), and the [Google Cloud Vision API](https://cloud.google.com/vision/).

**NOTE: The Google Cloud Vision API is cheap but not free. So unfortunately to use tomoji for OCR you'll need to have a Google Cloud Platform account and provide your API key on the command line.**

## Usage

Tomoji requires an .mkv (Matroska video) file with embedded subtitle-image (VOBSUB) tracks as input, so you'll have to use a separate program to extract a DVD/Blu-ray disc to an .mkv file. [HandBrake](https://handbrake.fr/) is a free, open source, multi-platform tool that works well for this purpose (see below for tips on the right settings to use for HandBrake).

Installing the dependencies for tomoji can be a nightmare on Mac/Windows, so I've published a [Docker](https://www.docker.com/) image ([rsimmons/tomoji](https://hub.docker.com/rsimmons/tomoji/) that bundles them and lets you conveniently run tomoji on any platform supported by Docker. Input and output can be provided via stdin/stdout so that Docker volumes are not required:

```shell
$ docker run -i --rm rsimmons/tomoji list - < inputvideo.mkv
Available subtitle tracks (VOBSUB):
  #3: Japanese (jpn)
  #4: English (eng)
$ docker run -i --rm rsimmons/tomoji ocr -k *YOUR_GOOGLE_API_KEY* - 3 < inputvideo.mkv > outputsubs_ja.srt
```

On a recent version of Ubuntu, tomoji can be run like this:

```shell
$ sudo apt-get install -y ogmrip python3-venv
$ pyvenv env
$ ./env/bin/activate
(env) $ pip install pycountry requests
(env) $ python3 tomoji.py list inputvideo.mkv
Available subtitle tracks (VOBSUB):
  #3: Japanese (jpn)
  #4: English (eng)
(env) $ python3 tomoji.py ocr -k *YOUR_GOOGLE_API_KEY* inputvideo.mkv 3 > outputsubs_ja.srt
```

## Tips for Using HandBrake to Extract DVD/Blu-ray Discs

*Coming Soon*

## FAQ

### Why .mkv files instead of .mp4/etc?

At the time of this writing, ffmpeg can't extract VOBSUB tracks from .mp4 files, but mkvextract can extract them from .mkv files. Handbrake supports outputting .mkv files. So .mkv files end up being the best intermediate format for processing VOBSUB tracks.

## Related Projects

- [SubRip](http://zuggy.wz.cz/) is the original subtitle OCR app (Windows only).
- [SubExtractor](https://subextractor.codeplex.com/) is a Windows GUI app to do manually-assisted OCR of DVD/Blu-ray subtitles.
- [Avidemux](http://avidemux.sourceforge.net/) is a free cross-platform video editor designed for simple cutting, filtering and encoding tasks, and has support for OCR of DVD subtitles.
