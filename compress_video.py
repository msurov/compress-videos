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


__patterns = [
  re.compile(r'TAG\:encoder\s*=.+x265'),
  re.compile(r'codec_name\s*=\s*hevc'),
  re.compile(r'codec_long_name\s*=\s*H\.265')
]

def is_video_compressed(filepath):
  cmd = [
    'ffprobe',
    '-hide_banner',
    '-loglevel', 'panic',
    '-show_streams',
    filepath
  ]
  runresult = subprocess.run(cmd, capture_output=True, text=True)
  output = runresult.stdout
  for pat in __patterns:
    matched = re.search(pat, output)
    if matched:
      return True
  return False

def compress_video(inp : str, outp : str) -> bool:
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
    '-c:v', 'libx265',
    '-vtag', 'hvc1',
    '-crf', '25',
    '-x265-params', 'log-level=error',
    outp
  ]
  runresult = subprocess.run(cmd, capture_output=True, text=True)
  if runresult.returncode != 0:
    print(f'  - can\'t compress file {inp}, because of the error:')
    print(runresult.stderr)
    return False

  inpsz = getsize(inp)
  outpsz = getsize(outp)
  compression_ratio = outpsz / inpsz
  Mb = 1024**2
  if compression_ratio > 0.8 or inpsz - outpsz < 2 * Mb:
    print(f'  - the compression is too small: '
        f'from {inpsz/Mb:.1f}Mb to {outpsz/Mb:.1f}Mb, skpping')
    remove(outp)
    return False

  shutil.move(outp, inp)
  print(f'  - file compressed: {inpsz/Mb:.1f}Mb -> {outpsz/Mb:.1f}Mb')
  return True

def find_files(basedir : str, is_good : Callable[[str], bool]) -> List[str]:
  files = listdir(basedir)
  result = [join(basedir, f) for f in files if is_good(join(basedir, f))]
  for name in files:
    path = join(basedir, name)
    if not isdir(path):
      continue
    result += find_files(path, is_good)

  return result

def find_all_not_compressed_video(dirpath):
  extensions = ['.mp4', '.avi', '.mpeg', '.mpg', '.mov']

  def is_suitable_for_compress(path):
    return (splitext(path)[1] in extensions) and \
      isfile(path) and \
      not is_video_compressed(path)

  return find_files(dirpath, is_suitable_for_compress)

def check_ffmpeg_installed():
  cmd = ['ffmpeg', '-version']
  result = subprocess.run(cmd, capture_output=True, check=False)
  return result.returncode == 0

def main():
  parser = argparse.ArgumentParser(
      prog='compress_video.py',
      description='The program compresses video files found in subdirectories',
  )
  parser.add_argument('dirpath', default='./')
  args = parser.parse_args()
  inpdir = abspath(args.dirpath)

  if not check_ffmpeg_installed():
    print('  [error] Can\'t find ffmpeg, try to install it')
    exit(-1)

  dstpath = gettempdir()
  name = ''.join(sample(ascii_lowercase + ascii_uppercase + digits, k=12))
  dstpath = join(dstpath, name + '.mp4')

  files = find_all_not_compressed_video(inpdir)
  for f in files:
    print(f'[info] Processing {f}')
    compress_video(f, dstpath)

if __name__ == '__main__':
  main()
