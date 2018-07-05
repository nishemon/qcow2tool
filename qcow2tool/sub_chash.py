import argparse
import hashlib
import qcow2
import sys
import sets
hasher_base = None


def hash_cluster(content):
    global hasher_base
    hasher = hasher_base.copy()
    hasher.update(content)
    return hasher.digest()


def hash_zero(size):
    global hasher_base
    hasher = hasher_base.copy()
    hasher.update(bytearray(size))
    return hasher.digest()


def xor(list_value, str_value):
    return map(lambda x, y: (x ^ ord(y)), list_value, str_value)


def chash(args):
    global hasher_base
    hasher_base = hashlib.new(args.algo)
    zero_cluster = 0
    clsize = 0
    with qcow2.Qcow2File(args.src, True) as qf:
        offset = 0
        calc = None
        while offset < qf.get_image_size():
            clusters = qf.read_l2_block(offset, True)
            if clusters:
                for cl in clusters:
                    if cl.all_zero or cl.offset == 0:
                        zero_cluster += 1
                    else:
                        content = qf.read_from_cluster(cl)
                        h = hash_cluster(content)
                        calc = xor(calc, h) if calc else [ord(x) for x in h]
            offset += qf.get_cluster_size() * qf.get_l2_count_in_block()
            sys.stdout.write("0x%x / 0x%x\r" % (offset, qf.get_image_size()))
            sys.stdout.flush()
        if zero_cluster & 1:
            h = hash_zero(qf.get_cluster_size())
            calc = xor(calc, h) if calc else [ord(x) for x in h]
        clsize = qf.get_cluster_size()
    print("%s %s (cluster size:%d)" % (''.join(['%02x' % x for x in calc]), args.src.name, clsize))


def setup_subcmd(subparsers):
    chash_parser = subparsers.add_parser('chash', formatter_class=argparse.RawDescriptionHelpFormatter,
                                         description='''\
 Calculate a value like hash for snapshot images.
 chash method is:
   value = clusters.map(md5).reduce(xor)
''', help='sum of all cluster hashes')
    chash_parser.add_argument('src', type=argparse.FileType('rb'))
    chash_parser.add_argument('-b', '--backing', metavar='CHASH', help='give chash of backing file')
    chash_parser.add_argument('-a', '--algo', choices=['md5', 'sha1'], default='md5', help='set base hash')
    chash_parser.set_defaults(handler=chash)
