import glob  
from os.path import (
  abspath, join, getsize, 
  isfile, isdir, splitext
)
from os import remove, listdir
from tempfile import gettempdir, gettempprefix
from random import choice, sample
from string import ascii_lowercase, ascii_uppercase, digits
import subprocess
import re
import argparse
import shutil
from typing import Callable, List
import time


def find_files(basedir : str, is_good : Callable[[str], bool]) -> List[str]:
  files = listdir(basedir)
  result = [join(basedir, f) for f in files if is_good(join(basedir, f))]
  for name in files:
    path = join(basedir, name)
    if not isdir(path):
      continue
    result += find_files(path, is_good)
  return result


class CompressVideoFiles:
  __codecs = [
    ['-c:v', 'hevc_nvenc'],
    ['-c:v', 'libx265', '-crf', '25'],
    ['-c:v', 'hevc', '-crf', '25'],
  ]
  __tag_encoder_265 = re.compile(r'TAG\:encoder\s*\=.+x265')
  __duration = re.compile(r'duration\=([\d\.\+\-eE]+)')
  __extensions = ['.mp4', '.avi', '.mpeg', '.mpg', '.mov']


  def __init__(self):
    parser = argparse.ArgumentParser(
        prog='compress_video.py',
        description='The program compresses video files found in subdirectories of a given path',
    )
    parser.add_argument('dirpath', default='./')
    args = parser.parse_args()
    self.inpdir = abspath(args.dirpath)

    if not self.check_ffmpeg_installed():
      print('  [error] Can\'t find ffmpeg, try to install it')
      exit(-1)

    self.codec = None

  def run(self):
    dstpath = gettempdir()
    name = ''.join(sample(ascii_lowercase + ascii_uppercase + digits, k=12))
    dstpath = join(dstpath, name + '.mp4')

    files = self.find_all_non_compressed_video()

    if len(files) == 0:
      print('[info] There are no files to compress')
      return 0

    nfiles = len(files)

    for i, f in enumerate(files, start=1):
      print(f'[{i}/{nfiles}] Processing {f}')
      self.compress_video(f, dstpath)

    return 0

  def is_video_compressed(self, filepath):
    cmd = [
      'ffprobe',
      '-hide_banner',
      '-loglevel', 'panic',
      '-show_streams',
      filepath
    ]
    runresult = subprocess.run(cmd, capture_output=True, text=True)
    output = runresult.stdout

    matched = re.search(self.__tag_encoder_265, output)
    if matched:
      return True

    matched = re.search(self.__duration, output)
    if matched:
      duration = float(matched.group(1))
      inpsz = getsize(filepath)
      Mb = 1024**2
      if inpsz / duration < 0.3 * Mb:
        return True

    return False

  def is_suitable_for_compression(self, path):
    return (splitext(path)[1] in self.__extensions) and \
      isfile(path) and \
      not self.is_video_compressed(path)

  def find_all_non_compressed_video(self):
    if isfile(self.inpdir):
      return [self.inpdir]
    return find_files(self.inpdir, self.is_suitable_for_compression)

  @staticmethod
  def check_ffmpeg_installed():
    cmd = ['ffmpeg', '-version']
    result = subprocess.run(cmd, capture_output=True, check=False)
    return result.returncode == 0
  
  @staticmethod
  def run_ffmpeg_compress(inp : str, outp : str, codec : list) -> bool:
    R"""
      Execute the command
        ffmpeg -hide_banner -loglevel panic -y -i "$1" 
              -c:v libx265 -vtag hvc1 -crf 2 -x265-params log-level=error "$2"
    """
    cmd = [
      'ffmpeg', 
      '-hide_banner',
      '-loglevel', 'panic',
      '-y',
      '-i', inp,
      *codec,
      '-vtag', 'hvc1',
      outp
    ]
    return subprocess.run(cmd, capture_output=True, text=True)

  def compress_video(self, inp : str, outp : str) -> bool:
    R"""
      Run ffmpeg with all the codecs until it success
    """
    tstart = time.time()

    if self.codec is None:
      for codec in self.__codecs:
        runresult = self.run_ffmpeg_compress(inp, outp, codec)
        if runresult.returncode == 0:
          self.codec = codec
          print('  [info] using codec parameters: ', *self.codec)
          break
    else:
      runresult = self.run_ffmpeg_compress(inp, outp, self.codec)

    if runresult.returncode != 0:
      print(f'  [error] can\'t compress file {inp}, because of the error:')
      print(runresult.stderr)
      return False

    inpsz = getsize(inp)
    outpsz = getsize(outp)
    compression_ratio = outpsz / inpsz
    Mb = 1024**2
    if compression_ratio > 0.9 or inpsz - outpsz < 2 * Mb:
      print(f'  [info] the compression is too small: '
          f'from {inpsz/Mb:.1f}Mb to {outpsz/Mb:.1f}Mb, skpping')
      remove(outp)
      return False

    shutil.move(outp, inp)
    print(f'  [info] file compressed: {inpsz/Mb:.1f}Mb -> {outpsz/Mb:.1f}Mb')
    tend = time.time()
    print(f'  [info] done in {tend - tstart:.1f}sec')
    return True

if __name__ == '__main__':
  compress = CompressVideoFiles()
  compress.run()
