import argparse
import struct
import ctypes
import zlib
import qcow2
import qcow2mod
import sys
import subprocess

"""
class Bitmap(ctypes.Structure):
    _fields_ = [
        ("values", ctypes.c_uint64 * 64)
    ]
    def calc_cluster_count(self, cluster_size_in_sector):
        for v in self.values:
            pass

def check_cluster_size(qf):
    offset = 0
    read512 = struct.Struct('q' * (512 / 8))
    sector = read512.unpack_from(bytes, offset)
    zero = True
    for qword in sector:
        if qword:
            zero = False
            break
    if zero:
        pass
"""



def compress(qf, qm, ratio):
    """

    :param qcow2.Qcow2File qf:
    :param qcow2mod.Qcow2Modifier qm:
    :return:
    """
    # TODO base file but no compression
    always_compression = qf.has_backing_file()
    offset = 0
    resize = 0
    appender = qm.begin_append_clusters(refcount_order=2)
    last = qf.get_last_cluster_number() * qf.get_cluster_size()
    waste = 0
    while offset < qf.get_image_size():
        sys.stdout.write("%d %% / 100%%\r" % (offset * 100 / last))
        sys.stdout.flush()
        appender.seek(offset)
        clusters = qf.read_l2_block(offset, True)
        if clusters:
            for cl in clusters:
                if cl is None:
                    appender.skip_cluster()
                    continue
                blank = appender.get_blank_size()
                threshold = int((blank + qf.get_cluster_size()) * ratio)
                if cl.compress or (always_compression and not cl.all_zero):
                    read = qf.read_from_cluster(cl)
                    cobj = zlib.compressobj(6, zlib.DEFLATED, -12, 9, zlib.Z_DEFAULT_STRATEGY)
                    buff = cobj.compress(read) + cobj.flush()
                    clen = len(buff)
                    if cl.size < clen and cl.size < threshold:
                        if cl.compress:
                            appender.append_compressed_cluster()
                        else:
                            appender.append_raw_cluster()
                        continue
                    elif clen < threshold:
                        appender.append_compressed_cluster(buff)
                        continue
                # TODO detect all zero if decrease cluster-size
                if cl.all_zero:
                    appender.append_zero_cluster()
                else:
                    waste += blank
                    appender.append_raw_cluster()

        offset += qf.get_cluster_size() * qf.get_l2_count_in_block()
    appender.close()


def squeeze(args):
    with qcow2.Qcow2File(args.src, args.deep) as qf:
        qm = qcow2mod.Qcow2Modifier(qf, args.dst)
        compress(qf, qm, args.ratio)
        qm.close()
#    subprocess.call(['qemu-img', ''])


def setup_subcmd(subparsers):
    squeeze_parser = subparsers.add_parser('squeeze', help='squeeze qcow2 image')
    squeeze_parser.add_argument('src', type=argparse.FileType('rb'))
    squeeze_parser.add_argument('dst', type=argparse.FileType('wb'))
#    squeeze_parser.add_argument('-z', '--zopfli', help='compress with zopfli')
#    squeeze_parser.add_argument('-u', '--unordered', help='unordered')
    squeeze_parser.add_argument('-r', '--ratio', type=float, help='change ratio for performance(0.95)', default=0.95)
    squeeze_parser.add_argument('-d', '--deep', help='use backing files', action='store_true')
#    squeeze_parser.add_argument('-x', '--exclude', nargs='+', type=argparse.FileType('r'),
#                               help='erase unreference areas')
#    squeeze_parser.add_argument('-c', '--common', nargs='+', type=argparse.FileType('r'), help='collect common areas')
    squeeze_parser.set_defaults(handler=squeeze)
