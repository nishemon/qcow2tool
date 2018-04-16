import io
from ctypes import *
from qcow2struct import *
import zlib
from cStringIO import StringIO


def calc_refcounts_per_cluster(cluster_bits, order):
    return 1 << (cluster_bits + 3 - order)


def load_table(fileobj, table_offset, size, entryType):
    if table_offset:
        fileobj.seek(table_offset)
    entries = []
    while 0 < size:
        entry = entryType()
        fileobj.readinto(entry)
        if hasattr(entry, "reserved") and entry.reserved:
            raise IOError('Unsupported %s', entry.__class__.__name__)
        if hasattr(entry, "is_valid") and not entry.is_valid():
            raise IOError('Unsupported or corrupted %s', entry.__class__.__name__)
        entries.append(entry)
        size -= sizeof(entryType)
    return entries


class BackingFileFormatName(object):
    def __init__(self, fileobj, size):
        self.name = fileobj.read(size)


def load_feature_name_table(fileobj, size):
    entries = load_table(fileobj, 0, size, FeatureNameTableEntry)
    return entries


def load_bitmaps_extension(fileobj, size):
    entry = BitmapsExtension()
    fileobj.readinto(entry)
    return entry


def load_full_disk_encryption_header_pointer(fileobj, size):
    entry = FullDiskEncryptionHeaderPointer()
    fileobj.readinto(entry)
    return entry


def load_extensions(fileobj):
    extension_define = [
        (0xE2792ACA, BackingFileFormatName),
        (0x6803f857, load_feature_name_table),
        (0x23852875, load_bitmaps_extension),
        (0x0537be77, load_full_disk_encryption_header_pointer)
    ]
    extensions = []
    while True:
        ext = HeaderExtensionHeader()
        fileobj.readinto(ext)
        off = fileobj.tell()
        if ext.magic == 0:
            break
        for etype in extension_define:
            if etype[0] == ext.magic:
                extensions.append(etype[1](fileobj, ext.len))
                break
        fileobj.seek(off + (ext.len + 7) & ~7)
    return extensions


class Cluster(object):
    def __init__(self, cluster_id, foffset, size=0, compress=False, all_zero=False):
        self.cluster_id = cluster_id
        self.offset = foffset
        self.size = size
        self.compress = compress
        self.all_zero = all_zero


#QCOW2FILE_BACKING_FILE_IGNORE
#QCOW2FILE_BACKING_FILE_
#QCOW2FILE_BACKING_FILE_IGNORE

class Qcow2File(io.BufferedIOBase):
    def __init__(self, filename_or_obj, backing=True):
        super(Qcow2File, self).__init__()
        fileobj = open(filename_or_obj, 'rb') if isinstance(filename_or_obj, str) else filename_or_obj
        header = Header()
        fileobj.readinto(header)
        if header.magic != 'QFI\xfb':
            raise IOError('Not QCOW2 format')
        if header.version == 2:
            header.incompatible_features = 0
            header.compatible_features = 0
            header.refcount_order = 4
            header.header_length = 72
        elif header.version != 3:
            raise IOError('Unsupported version %d' % header.version)
        self.header = header
        self.fileobj = fileobj
        self.extensions = load_extensions(fileobj)
        self.backingFile = None
        self.backingFile = self.get_backing_file()
        # TODO: backing is not only qcow2 format
        self.backing = Qcow2File(self.backingFile) if backing and self.backingFile else None
        cluster_size = 1 << header.cluster_bits
        self.refcounts = load_table(fileobj, header.refcount_table_offset,
                                   header.refcount_table_clusters * cluster_size, RefcountTableEntry)
        self.l1 = load_table(fileobj, header.l1_table_offset, header.l1_size * sizeof(L1TableEntry), L1TableEntry)
        # TODO: snapshots
        self.cache_last_l2_block_offset = -1
        self.cache_last_l2_block = None
        # for Image Read
        self.image_pointer = 0

    def has_backing_file(self):
        return bool(self.backingFile)

    def get_image_size(self):
        return self.header.size

    def get_cluster_size(self):
        return 1 << self.header.cluster_bits

    def get_refcount_size(self):
        return 1 << (1 << self.header.refcount_order)

    def read_refcount_block(self, offset):
        count_in_block = 1 << (self.header.cluster_bits - (self.header.refcount_order - 3))
        cluster = offset >> self.header.cluster_bits
        t = self.refcounts[cluster / count_in_block]
        entry_class = RefCountEntries[self.header.refcount_order]
        return load_table(self.fileobj, t.offset, self.get_cluster_size(), entry_class)

    def get_l2_count_in_block(self):
        return 1 << (self.header.cluster_bits - 3)

    def get_last_cluster_number(self):
        # TODO
        return self.header.l1_size * self.get_l2_count_in_block()

    def read_l2_block(self, offset, none_if_unallocated=False):
        count_in_block = self.get_l2_count_in_block()
        cluster = offset >> self.header.cluster_bits
        l1_index = cluster / count_in_block
        cluster_id = l1_index * count_in_block

        t = self.l1[l1_index] if l1_index < len(self.l1) else None
        if not t or not t.offset:
            if self.backingFile:
                if not self.backing:
                    return None
                if offset < self.backing.get_image_size():
                    return self.backing.read_l2_block(offset)
            if none_if_unallocated:
                return None
            return [Cluster(i, 0) for i in range(cluster_id, cluster_id + count_in_block)]
        if self.cache_last_l2_block_offset == t.offset:
            return self.cache_last_l2_block

        l2 = load_table(self.fileobj, t.offset, self.get_cluster_size(), L2TableEntry)
        clusters = []
        for c in l2:
            if c.compressed:
                x = 62 - (self.header.cluster_bits - 8)
                off = c.descriptor & ((1 << x) - 1)
                sectors = (c.descriptor >> x) + 1
                cl = Cluster(cluster_id, off, (sectors << 9) - (off & 511), True)
            else:
                off = c.descriptor & (((1 << 47) - 1) << 9)
                if 1 < (c.descriptor ^ off) or off % self.get_cluster_size():
                    raise IOError('Unknown L2 entry format 0x%x' % c.descriptor)
                if c.descriptor & 1:
                    cl = Cluster(cluster_id, off, self.get_cluster_size() if off else 0, all_zero=True)
                elif off:
                    cl = Cluster(cluster_id, off, self.get_cluster_size())
                else:
                    if not self.backingFile or (self.backing and self.backing.get_image_size() <= offset):
                        cl = Cluster(cluster_id, 0, self.get_cluster_size(), all_zero=True)
                    elif self.backing:
                        # wrong
                        cl = self.backing.read_l2(len(clusters))
                    else:
                        cl = None
            cluster_id += 1
            clusters.append(cl)
        self.cache_last_l2_block_offset = t.offset
        self.cache_last_l2_block = clusters
        return clusters

    def read_l2(self, offset):
        entries = self.read_l2_block(offset, True)
        cluster_id = offset >> self.header.cluster_bits
        if not entries:
            return Cluster(cluster_id, 0, self.get_cluster_size(), all_zero=True)
        return entries[cluster_id % len(entries)]

    def get_refcount(self, offset):
        entries = self.read_refcount_block(offset)
        index = offset % (len(entries) * 8)
        return entries[index / 8].get()[offset & 7]

    def read_from_cluster(self, offset_or_cluster, extract=True):
        cluster = offset_or_cluster if isinstance(offset_or_cluster, Cluster) else None
        if not cluster:
            cluster = self.read_l2(offset_or_cluster)
        self.fileobj.seek(cluster.offset)
        read = self.fileobj.read(cluster.size)
        if cluster.compress and extract:
            dobj = zlib.decompressobj(-12)
            read = dobj.decompress(read, self.get_cluster_size())
            if 0 < len(dobj.unconsumed_tail):
                raise IOError('Too long compressed block')
            dobj.flush()
            cluster.size -= len(dobj.unused_data)
        return read

    def get_backing_file(self):
        off = self.header.backing_file_offset
        if off == 0:
            return None
        if self.backingFile:
            return self.backingFile
        self.fileobj.seek(off)
        return self.fileobj.read(self.header.backing_file_size)

    def close(self):
        if self.backing:
            self.backing.close()
        self.fileobj.close()

    def read(self, size=-1):
        buff = StringIO()
        cluster_size = self.get_cluster_size()
        if size < 0:
            size = self.get_image_size() - self.image_pointer
        while buff.tell() != size:
            offset = (self.image_pointer + buff.tell()) & (cluster_size - 1)
            cluster_bytes = self.read_from_cluster(self.image_pointer)
            buff.write(cluster_bytes[offset:(size if 0 < size else cluster_size)])
        self.image_pointer += buff.tell()
        return buff.getvalue()

    def seek(self, pos):
        self.image_pointer = pos

    def get_header(self):
        return self.header
