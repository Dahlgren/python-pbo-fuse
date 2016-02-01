#!/usr/bin/env python

from errno import ENOENT
import os
from stat import S_IFDIR, S_IFREG
from sys import argv, exit
from time import time

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn, fuse_get_context

from pbo import PBOFile

def split_path(path):
  path = os.path.normpath(path)
  path = path.split(os.sep)
  path = filter(len, path)
  return path

def create_directory_node(name, timestamp):
  return dict(
    attributes=dict(
      st_atime=timestamp,
      st_ctime=timestamp,
      st_mtime=timestamp,
      st_mode=(S_IFDIR | 0755),
      st_nlink=2
    ),
    files=dict(),
    name=name
  )

def create_file_node(name, file):
  return dict(
    attributes=dict(
      st_atime=file.timestamp,
      st_ctime=file.timestamp,
      st_mtime=file.timestamp,
      st_mode=(S_IFREG | 0444),
      st_nlink=2,
      st_size=file.data_size
    ),
    file=file,
    name=name
  )

class PBOFuse(LoggingMixIn, Operations):

  def __init__(self, path):
    self.pbo = PBOFile(path)
    self.pbo.load()
    self.create_file_tree()

  def create_file_tree(self):
    self.tree = create_directory_node(None, time())

    for file in self.pbo.files:
      path = split_path(file.filename.replace('\\', '/'))
      self.add_file_node(path, file)

  def add_file_node(self, path, file):
    node = self.tree

    while len(path) > 1:
      directory_name = path[0]

      if not directory_name in node:
        node['files'][directory_name] = create_directory_node(directory_name, time())

      node = node['files'][directory_name]

      path.pop(0)

    filename = path[0]

    node['files'][filename] = create_file_node(filename, file)

  def get_node(self, path):
    if (path == '/'):
      return self.tree

    node = self.tree
    path = split_path(path)

    while len(path) > 1:
      node = node['files'][path[0]]
      path.pop(0)

    filename = path[0]

    if filename in node['files']:
      return node['files'][filename]

    return None

  def getattr(self, path, fh=None):
    uid, gid, pid = fuse_get_context()
    node = self.get_node(path)

    if node:
      return node['attributes']

    raise RuntimeError('unexpected path: %r' % path)

  def read(self, path, length, offset, fh):
    uid, gid, pid = fuse_get_context()
    node = self.get_node(path)
    entry = node['file']
    return self.pbo.read(entry, offset, length)

  def readdir(self, path, fh):
    base = ['.', '..'];
    node = self.get_node(path)
    if node:
      return base + map(lambda x: x['name'], node['files'].values())

    raise RuntimeError('unexpected path: %r' % path)

  # Disable unused operations:
  access = None
  flush = None
  getxattr = None
  listxattr = None
  open = None
  opendir = None
  release = None
  releasedir = None
  statfs = None

if __name__ == '__main__':
  if len(argv) != 3:
    print('usage: %s <file> <mountpoint>' % argv[0])
    exit(1)

  fuse = FUSE(PBOFuse(argv[1]), argv[2], foreground=True, ro=True)
