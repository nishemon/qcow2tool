import argparse
import struct
import ctypes

class Bitmap(ctypes.Structure):
    _fields_ = [
        ("values", ctypes.c_uint64 * 64)
    ]
    def calc_cluster_count(self, cluster_size_in_sector):
        for v in self.values:
            bin(v).sp

def check_cluster_size(qf):
    read512 = struct.Struct('q' * (512 / 8))
    sector = read512.unpack_from(bytes, offset)
    zero = True
    for qword in sector:
        if qword:
            zero = False
            break
    if zero:


def squeeze(conf, args):
    pass


def setup_subcmd(subparsers):
    squeeze_parser = subparsers.add_parser('squeeze', help='squeeze qcow2 image')
    squeeze_parser.add_argument('src', type=argparse.FileType('r'), nargs=1)
    squeeze_parser.add_argument('dest', type=argparse.FileType('w'), nargs=1)
    squeeze_parser.add_argument('-z', '--zopfli', help='compress with zopfli')
    squeeze_parser.add_argument('-u', '--unordered', help='unordered')
    squeeze_parser.add_argument('-r', '--ratio', nargs=1, type=float, help='switch raito for performance(0.9)')
    squeeze_parser.add_argument('-d', '--deep', help='use backing files')
    squeeze_parser.add_argument('-x', '--exclude', nargs='+', type=argparse.FileType('r'),
                               help='erase unreference areas')
    squeeze_parser.add_argument('-c', '--common', nargs='+', type=argparse.FileType('r'), help='collect common areas')
    squeeze_parser.set_defaults(handler=squeeze)
