import os, tempfile, subprocess
import re
import sys
from math import log10, ceil
from itertools import chain
from concurrent.futures import ThreadPoolExecutor
from shlex import quote

CUTFILE_REGEX = r'^([0-9.]+) ([^/]+)$'

def cutaudio(*infiles, overwrite:bool=False, extension:str=None):
    '''
    Cut the original audio into more granular files with new names.
    With each audio file that is passed, the following is done.

    1. If a cut file does not exist alongside the original file,
       play the file and prompt for cuts. Cuts are saved to the cutfile.
    2. If an output directory does not exist alongside the original file,
       process the cut file to produce the output directory.

    Step 1 depends on mplayer, and step 2 depends on sox.

    For example,

        cutaudio 'audio/long raw audio file.mp3'

    Default extension of output files is that of the input file.
    You can use any extension that sox supports.

    You can edit the cut files yourself; they're text files where each
    line corresponds to an audio segment and where lines match this
    regular expression.

        %s

    The first group is the time at which the segment ends, in seconds,
    and the second group is the name of the segment.

    :param infiles: Audio file(s) to cut up
    :param bool overwrite: Overwrite the cut file if it exists.
    :param str extension: Change the extension of output audio files
    ''' % CUTFILE_REGEX
    has_dependencies = True
    for prog in ['sox', 'mplayer']:
        p = subprocess.Popen(['which', prog],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()
        if p.returncode != 0:
            sys.stderr.write('You need to install %s.' % prog)
            has_dependencies = False
    if not has_dependencies:
        sys.exit(1)

    if len(infiles) == 0:
        sys.stderr.write('You must specify at least one input file.\n')
        sys.exit(1)
    elif not all(map(os.path.isfile, infiles)):
        for fn in infiles:
            if not os.path.isfile(fn):
                sys.stderr.write('Not a file: %s\n' % fn)
        sys.exit(1)
    else:
        for infile in infiles:
            outdir, in_extension = os.path.splitext(infile)
            cutfile = outdir + '.cut'

            if extension:
                out_extension = '.' + extension.lstrip('.')
            else:
                out_extension = in_extension

            if overwrite or not os.path.isfile(cutfile):
                # Generate the cutfile.
                generate_cutfile(infile, cutfile)

            if not os.path.isdir(outdir):
                # Process the cutfile.
                with open(cutfile) as fp:
                    cuts = parse_cutfile(cutfile)
                process_cutfile(infile, cuts, outdir, out_extension)

def generate_cutfile(infile, cutfile):
    directions = '''
Name the present audio segment, then hit enter when the segment is over.
The audio segment specification will be saved in this file.

  %s

The session will end automatically when the file is done playing.
Press C^d to end early.
    '''.strip() % cutfile
    with open(cutfile, 'w') as fp:
        fp.write(infile + '\n')
        sys.stderr.write(directions + '\n\n')
        player = Player(infile)
        while player.playing:
            try:
                filename = input('Segment name: ')
            except EOFError:
                player.stop()
            else:
                if '/' in filename:
                    msg = 'Error: Name may not contain "/".\n'
                    sys.stderr.write(msg)
                else:
                    fp.write('  %f %s\n' % (player.position, filename))
                    fp.flush()

def parse_cutfile(fp):
    for line in fp:
        m = re.match(CUTFILE_REGEX, line)
        if m:
            yield float(m.group(1)), m.group(2)
        else:
            raise ValueError('Invalid line: %s' % line)


class Player(object):
    def __init__(self, infile):
        self.position = 0.0
        self.playing = True
        self._stop = False

        self.executor = ThreadPoolExecutor(2)
        self.future = self.executor.submit(self.play, infile)

    def stop(self):
        self._stop = True
        while self.future.running():
            pass

    def play(self, infile):
        p = subprocess.Popen(['mplayer', infile],
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        buffer=b''
        while True:
            code = p.poll()
            if self._stop:
                break
            elif code == None:
                pass
            elif code == 0:
                break
            else:
                msg = 'mplayer exited with %s.\n\n%s\n'
                raise EnvironmentError(msg % (code, p.stderr.read()))
            char=p.stdout.read(1)
            if char==b'\r':
                m = re.match(br'^[^(]+\(([0-9.]+).*$', buffer)
                if m:
                    self.position = float(m.group(1).decode('ascii'))
                buffer=b''
            else:
                buffer+=char
        self.playing = False

def process_cutfile(infile, cuts, outdir, out_extension):
    cuts=list(cuts)
    xs = chain(['0'], *([str(end), ':', 'newfile'] for end, _ in cuts))

    prefix=os.path.abspath('.tmp')
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        outfile = os.path.join(tmp, out_extension)

        cmd = ['sox', infile, outfile, 'trim'] + list(xs)
        p = subprocess.Popen(cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()

        if p.returncode == 0:
            zs = zip(sorted(os.listdir(tmp)), cuts)
            for intermediate, (_, name) in zs:
                final = intermediate.replace('.', '-' + name + '.')
                os.renames(os.path.join(tmp, intermediate),
                           os.path.join(outdir, final))
            os.makedirs(tmp, exist_ok = True) # undo os.renames cleanup
        else:
            cmd_str = ' \\ \n  '.join(map(quote, cmd))
            output =b''.join(p.communicate()).decode('utf-8')
            sys.stderr.write('$ %s\n%s\n' % (cmd_str, output))
            sys.exit(1)

if __name__ == '__main__':
    import horetu
    horetu.horetu(cutaudio)
