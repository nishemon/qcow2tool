import argparse
import hashlib

hasher_base = None


def hash_cluster(algo, image):
    global hasher_base
    hasher = hasher_base.copy()
    hasher.update()
    return hasher.digest()


def hash_zero(algo, size):
    global hasher_base
    hasher = hasher_base.copy()
    hasher.update(bytearray(size))
    return hasher.digest()


def xor(a, b):
    return map(lambda x, y: x ^ y, a, b)


def chash(conf, args):
    global hasher_base
    zero_cluster = 0
    hasher_base = conf.algo
    calc = hash_cluster()
    if zero_cluster & 1:
        calc = xor(calc, hash_zero())


def setup_subcmd(subparsers):
    chash_parser = subparsers.add_parser('chash', help='calc cluster hash')
    chash_parser.add_argument('src', type=argparse.FileType('r'), nargs=1)
    chash_parser.add_argument('-b', '--back', nargs=1, help='consider hash as backing file')
    chash_parser.add_argument('-a', '--algo', nargs=1, choices=['md5', 'sha1'])
    chash_parser.set_defaults(handler=chash)
