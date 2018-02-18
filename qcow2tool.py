import argparse
import qcow2
#from zopfli.zlib import compress
import zlib

parser = argparse.ArgumentParser(prog='qcow2tool')
subparsers = parser.add_subparsers()

import sub_chash

sub_chash.setup_subcmd(subparsers)

import sub_squeeze

sub_squeeze.setup_subcmd(subparsers)


def main():
#    qf = qcow2.Qcow2File('template-20180217.centos7.qcow2c', False)
    qf = qcow2.Qcow2File('test.qcow2', False)
    offset = 0
    while offset < qf.get_image_size():
        blocks = qf.read_l2_block(offset)
        if blocks:
            for cluster in blocks:
                if cluster and cluster.offset:
                    if cluster.compress:
                        bytes = qf.read_from_cluster(offset, cluster)
                        cobj = zlib.compressobj(9, zlib.DEFLATED, -12, 9, zlib.Z_DEFAULT_STRATEGY)
                        bytes = cobj.compress(bytes) + cobj.flush()
                        sector = ((cluster.offset + len(bytes) - 1) >> 9) - (cluster.offset >> 9)
                        size = ((sector + 1) << 9) - (cluster.offset & 511)
                        if cluster.size != size:
                            print("0x%x +%d => %d z:%s" % (cluster.offset, cluster.size, size, cluster.compress))
        offset += qf.get_cluster_size() * qf.get_l2_count_in_block()
        print("0x%x / 0x%x" % (offset, qf.get_image_size()))

main()
