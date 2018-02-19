import argparse
import qcow2
#from zopfli.zlib import compress
import zlib


def analyze(args):
    with qcow2.Qcow2File(args.src, False) as qf:
        offset = 0
        while offset < qf.get_image_size():
            blocks = qf.read_l2_block(offset)
            if blocks:
                for cluster in blocks:
                    if cluster and cluster.offset:
                        if cluster.compress:
                            read = qf.read_from_cluster(cluster)
                            cobj = zlib.compressobj(9, zlib.DEFLATED, -12, 9, zlib.Z_DEFAULT_STRATEGY)
                            read = cobj.compress(read) + cobj.flush()
                            sector = ((cluster.offset + len(read) - 1) >> 9) - (cluster.offset >> 9)
                            size = ((sector + 1) << 9) - (cluster.offset & 511)
                            if cluster.size != size:
                                print("0x%x +%d => %d z:%s" % (cluster.offset, cluster.size, size, cluster.compress))
            offset += qf.get_cluster_size() * qf.get_l2_count_in_block()
            print("0x%x / 0x%x" % (offset, qf.get_image_size()))


def setup_subcmd(subparsers):
    analyze_parser = subparsers.add_parser('analyze', help='analyze qcow2 image')
    analyze_parser.add_argument('src', type=argparse.FileType('rb'))
    analyze_parser.set_defaults(handler=analyze)
