import re
import sys
import os
import subprocess
import json
import tempfile
import shutil
import base64
import argparse
import xml.etree.ElementTree as ET

import pycountry
import requests

RE_TRACK_NUMBER = re.compile(r'\|  \+ Track number: ([0-9]+).*')
RE_TRACK_TYPE = re.compile(r'\|  \+ Track type: (.*)')
RE_LANGUAGE = re.compile(r'\|  \+ Language: (.*)')
RE_CODEC_ID = re.compile(r'\|  \+ Codec ID: (.*)')

def fail(s):
    print('Error:', s, file=sys.stderr)
    sys.exit(1)

def mkv_timecode_to_ms(timecode):
    head, ms = timecode.split('.')
    hours, mins, seconds = map(int, head.split(':'))
    return 1000*((hours * 60 * 60) + (mins * 60) + seconds) + int(ms)

def ms_to_srt_timecode(t_ms):
    h, t_ms = divmod(t_ms, 1000*60*60)
    m, t_ms = divmod(t_ms, 1000*60)
    return '{0:02}:{1:02}:{2:06,}'.format(h, m, t_ms)

def parse_ebml_tracks(ebml_text):
    accum_tracks = []
    cur_track = None

    for line in ebml_text.split('\n'):
        line = line.strip()

        if not line.startswith('|  '):
            # End any open track
            if cur_track:
                accum_tracks.append(cur_track)
                cur_track = None

        if line == '| + A track':
            # Start new track
            cur_track = {}
        elif RE_TRACK_NUMBER.match(line):
            match = RE_TRACK_NUMBER.match(line)
            cur_track['tracknum'] = int(match.group(1))
        elif RE_TRACK_TYPE.match(line):
            match = RE_TRACK_TYPE.match(line)
            cur_track['type'] = match.group(1)
        elif RE_LANGUAGE.match(line):
            match = RE_LANGUAGE.match(line)
            cur_track['language'] = match.group(1)
        elif RE_CODEC_ID.match(line):
            match = RE_CODEC_ID.match(line)
            cur_track['codec_id'] = match.group(1)

    if cur_track:
        accum_tracks.append(cur_track)
        cur_track = None

    return accum_tracks

def list_vobsub_tracks(mkv_fn):
    mkvinfo_stdout = subprocess.check_output(['mkvinfo', mkv_fn])
    # TODO: handle exception

    tracks = parse_ebml_tracks(mkvinfo_stdout.decode('utf-8'))
    return [t for t in tracks if (t['type'] == 'subtitles') and (t['codec_id'] == 'S_VOBSUB')]

def extract_pngs(mkv_fn, tracknum, dest_dir):
    with tempfile.TemporaryDirectory() as vsdir:
        subprocess.check_call(['mkvextract', '-q', 'tracks', mkv_fn, '%d:%s' % (tracknum-1, os.path.join(vsdir, 'sub'))])
        _ = subprocess.check_output(['subp2png', os.path.join(vsdir, 'sub'), '-o', os.path.join(dest_dir, 'sub')])

def google_vision_ocr_png(png_fn, language, api_key):
    with open(png_fn, 'rb') as png_f:
        png_data = png_f.read()

    request_data = {
        'requests': [{
            'image': {
                'content': base64.b64encode(png_data).decode('ascii'),
            },
            'features': [{
                'type': 'TEXT_DETECTION',
            }],
            'imageContext': {
                'languageHints': [language],
            },
        }],
    }

    r = requests.post('https://vision.googleapis.com/v1/images:annotate?key=' + api_key, data=json.dumps(request_data), headers={'Content-Type': 'application/json'})
    rjson = r.json()

    try:
        return rjson['responses'][0]['textAnnotations'][0]['description']
    except:
        fail('Error calling Cloud Vision API')

def process_mkv(mkv_fn, args):
    vobsub_tracks = list_vobsub_tracks(mkv_fn)

    if args.command == 'list':
        print('Available subtitle tracks (VOBSUB):')
        for vt in vobsub_tracks:
            language_name = pycountry.languages.get(iso639_2T_code=vt['language']).name
            print('  #%d: %s (%s)' % (vt['tracknum'], language_name, vt['language']))
    elif args.command in ('extractpng', 'ocr'):
        vobsub_track_map = {t['tracknum']: t for t in vobsub_tracks}
        if args.tracknum not in vobsub_track_map:
            fail('Invalid track number')

        with tempfile.TemporaryDirectory() as pngdir:
            extract_pngs(mkv_fn, args.tracknum, pngdir)

            if args.command == 'extractpng':
                # zip up pngs to stdout
                subprocess.check_call('cd %s && zip -q - *' % (pngdir), shell=True)
            elif args.command == 'ocr':
                if not args.google_api_key:
                    fail('Google API key option is required for OCR')

                # convert from 3-letter to 2-letter language code
                language_639_1 = pycountry.languages.get(iso639_2T_code=vobsub_track_map[args.tracknum]['language']).iso639_1_code

                # parse XML list of subtitle metadata
                subs_meta = []
                tree = ET.parse(os.path.join(pngdir, 'sub.xml'))
                root = tree.getroot()
                for (zidx, sub_elem) in enumerate(root):
                    idx = int(sub_elem.get('id'))
                    start = mkv_timecode_to_ms(sub_elem.get('start'))
                    stop_str = sub_elem.get('stop') # stop might be missing
                    stop = mkv_timecode_to_ms(stop_str) if stop_str else None
                    pngfn = sub_elem.find('image').text
                    assert idx == (zidx+1) # sanity check

                    subs_meta.append({
                        'idx': idx,
                        'start': start,
                        'stop': stop,
                        'pngfn': pngfn,
                    })

                # fill in any misisng stop times
                for i, sm in enumerate(subs_meta):
                    if not sm['stop']:
                        assert (i < (len(subs_meta)-1)), 'Missing stop time on last subtitle'
                        sm['stop'] = subs_meta[i+1]['start'] - 1 # default stop time to start time of next sub minus 1 millisecond

                try:
                    for sm in subs_meta:
                        ocrd_text = google_vision_ocr_png(sm['pngfn'], language_639_1, args.google_api_key)
                        sys.stdout.flush()
                        sys.stdout.buffer.write('{0}\n{1} --> {2}\n{3}\n\n'.format(sm['idx'], ms_to_srt_timecode(sm['start']), ms_to_srt_timecode(sm['stop']), ocrd_text.rstrip()).encode('utf-8'))
                except KeyboardInterrupt:
                    fail('Interrupted')
            else:
                assert False
    else:
        fail('Unrecognized command: %s' % args.command)

def process_stdin(args):
    with tempfile.NamedTemporaryFile(suffix='.mkv') as tf:
        # write stdin to the tempfile
        shutil.copyfileobj(sys.stdin.buffer, tf)

        process_mkv(tf.name, args)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract text subtitles from .mkv files')

    subparsers = parser.add_subparsers(dest='command', title='subcommands')
    subparsers.required = True # fix for bug in argparse library

    subparser_list = subparsers.add_parser('list')
    subparser_list.add_argument('infile')

    subparser_extractpng = subparsers.add_parser('extractpng')
    subparser_extractpng.add_argument('infile')
    subparser_extractpng.add_argument('tracknum', type=int)

    subparser_ocr = subparsers.add_parser('ocr')
    subparser_ocr.add_argument('-k', '--google-api-key')
    subparser_ocr.add_argument('infile')
    subparser_ocr.add_argument('tracknum', type=int)

    args = parser.parse_args()

    if args.infile == '-':
        process_stdin(args)
    else:
        process_mkv(args.infile, args)
