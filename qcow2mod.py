import io
from ctypes import *
from qcow2struct import *
from qcow2 import *
from zlib import decompress
import os


class BackingFileFormatName(object):
    def __init__(self, fileobj, size):
        self.name = fileobj.read(size)


def load_feature_name_table(fileobj, size):
    return load_table(fileobj, 0, size, FeatureNameTableEntry)


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


class _PendingCluster(object):
    def __init__(self, offset, compressed_bytes=None, l2_offset=None):
        self.offset = offset
        self.size = len(compressed_bytes) if compressed_bytes else 0
        self.compressed_bytes = compressed_bytes
        self.l2_offset = l2_offset
        self.raw_cluster_count = 0


def reserve(fileobj, size):
    fileobj.seek(size, os.SEEK_CUR)
    fileobj.truncate()


def realign(fileobj, cluster_size):
    cur = fileobj.tell()
    skip = -cur & (cluster_size - 1)
    reserve(fileobj, skip)
    return cur + skip

_IGNORABLE_BLANK = 0
_MEM_LIMIT = 32*1024*1024


class _MapperCursor(object):
    def __init__(self, cluster_size, cluster_entry_bit_order, parent_map=None):
        self.file_offset = 0
        self.cover_size = cluster_size * ((cluster_size << 3) >> cluster_entry_bit_order)
        self.image_offset = -self.cover_size
        self.cluster_size = cluster_size
        self.parent_map = parent_map

    def map(self, fileobj, offset):
        gap = offset - self.image_offset
        if self.cover_size <= gap:
            self.image_offset = offset & -self.cover_size
            self.file_offset = 0
            gap = offset - self.image_offset
        if self.file_offset == 0:
            self.file_offset = realign(fileobj, self.cluster_size)
            if self.parent_map:
                self.parent_map(self.image_offset, self.file_offset)
            reserve(fileobj, self.cluster_size)
        index = gap / self.cluster_size
        return self.file_offset, index

class Qcow2ClusterAppender(object):
    def __init__(self, parent, unmap=False, available_gap=0):
        self.compressed_clusters = []
        self.compressed_size = 0
        self.available_gap = available_gap
        self.zero_clusters = [parent.original.get_image_size()]
        self.offset = 0
        self.cluster_size = 1 << parent.header.cluster_bits
        self.current_l2 = _MapperCursor(self.cluster_size, 6, lambda i, f: self.l1_entries.append((i, f)))
        self.current_refcounts = _MapperCursor(
            self.cluster_size, parent.header.refcount_order,
            lambda i, f: self.refs.append((i, f))
        )
        self.fileobj = parent.fileobj
        self.original = parent.original
        self.x = 62 - (parent.header.cluster_bits - 8)
        self.l1_entries = []
        self.refs = []
        self.close_redirect = lambda: parent.finish_clusters(self.l1_entries, self.refs)
        self.unmap = unmap
        self.refcounts_last_fileoffset = 0
        self.refcounts_order = parent.header.refcount_order

    def append_compressed_cluster(self, compressing_bytes=None):
        if not compressing_bytes:
            if self.cluster_size != self.original.get_cluster_size():
                raise IOError('cannot copy from different cluster size image')
            compressing_bytes = self.original.read_from_cluster(self.offset, extract=False)
        size = len(compressing_bytes)
        l2_offset = self._map_cluster(self.offset, -1)
        self.compressed_clusters.append(_PendingCluster(self.offset, compressing_bytes, l2_offset))
        self.compressed_size += size
        if (-self.compressed_size & (self.cluster_size - 1)) <= _IGNORABLE_BLANK:
            # fit alignment
            self.commit_compressed_clusters(True)
        else:
            while _MEM_LIMIT < self.compressed_size:
                self.commit_compressed_clusters()
        self.offset += self.cluster_size

    def get_blank_size(self):
        if self.available_gap:
            return 0
        return -self.compressed_size & (self.cluster_size - 1)

    def append_raw_cluster(self, raw_bytes=None):
        gap_cluster = self.available_gap / self.cluster_size - 1
        if self.compressed_clusters and gap_cluster <= self.compressed_clusters[0].raw_cluster_count:
            self.commit_compressed_clusters()
        # write direct
        self._map_cluster(self.offset, self.fileobj.tell())
        if not raw_bytes:
            self.original.seek(self.offset)
            raw_bytes = self.original.read(self.cluster_size)
        self.fileobj.write(raw_bytes)
        for cc in self.compressed_clusters:
            cc.raw_cluster_count += 1
        self.offset += self.cluster_size

    def append_zero_cluster(self):
        if not self.unmap:
            self.zero_clusters.append(self.offset)
        self.offset += self.cluster_size

    def skip_cluster(self):
        self.offset += self.cluster_size

    def seek(self, offset):
        if offset < self.offset:
            raise IOError('cannot decrease offset 0x%x < 0x%x' % (offset, self.offset))
        self.offset = offset

    def _copy_refcounts(self, image_offset, file_offset):
        count = self.cluster_size * 8 >> self.refcounts_order
        begin = image_offset & (self.cluster_size * count - 1)
        values = [RefCountEntries[self.refcounts_order]() for _ in range(count)]
        index = 0
        while index < len(values):
            block = self.original.read_refcount_block(begin)
            for b in block:
                values[index].set(b.get())
                index += 1
                if len(values) <= index:
                    break
            begin += self.cluster_size * 8 * len(block)
        self.fileobj.seek(file_offset)
        for v in values:
            self.fileobj.write(v)
        self.refcounts_last_fileoffset = file_offset

    def _alloc_cluster_entry(self, offset):
        off_index = self.current_refcounts.map(self.fileobj, offset)
        if self.refcounts_last_fileoffset != off_index[0]:
            self._copy_refcounts(offset, off_index[0])
        off_index = self.current_l2.map(self.fileobj, offset)
        return off_index[0] + sizeof(L2TableEntry) * off_index[1]

    def _write_cluster_entry(self, offset, entry):
        l2_offset = self._alloc_cluster_entry(offset)
        self.fileobj.seek(l2_offset)
        self.fileobj.write(entry)
        self.fileobj.seek(0, os.SEEK_END)
        return l2_offset

    def new_l2_entry(self, image_offset, file_offset, compressed=False, size=0):
        ref = self.original.get_refcount(image_offset)
        if compressed:
            desc = (((file_offset + size - 1) >> 9) - (file_offset >> 9)) << self.x | file_offset
            return L2TableEntry(1 if ref == 1 else 0, 1, desc)
        else:
            if file_offset % self.cluster_size:
                print("misalign 0x%x" % file_offset)
                raise IOError
            return L2TableEntry(1 if ref == 1 else 0, 0, file_offset)

    def _map_cluster(self, image_offset, file_offset=-1, compressed=False, size=0):
        while self.zero_clusters[0] < image_offset:
            offset = self.zero_clusters.pop(0)
            ref = self.original.read_refcount(offset)
            entry = L2TableEntry(1 if ref == 1 else 0, 0, 1)
            self._write_cluster_entry(offset, entry)
        if file_offset <= 0:
            return self._alloc_cluster_entry(image_offset)
        return self._write_cluster_entry(image_offset, self.new_l2_entry(image_offset, file_offset, compressed, size))

    def commit_compressed_clusters(self, commit_all=False):
        eoc = len(self.compressed_clusters)
        commit_size = self.compressed_size
        if not commit_all and self.available_gap:
            min_overhead = self.cluster_size
            size = self.compressed_size
            n = eoc - 1
            for cc in self.compressed_clusters[::-1]:
                size -= cc.size
                if self.available_gap < self.compressed_size - size:
                    break
                overhead = -size & (self.cluster_size - 1)
                if overhead < min_overhead:
                    eoc = n + 1
                    min_overhead = overhead
                    commit_size = size
                    if overhead == 0:
                        break
                n -= 1
            commit = self.compressed_clusters[0:eoc]
            self.compressed_clusters = self.compressed_clusters[eoc:]
            self.compressed_size -= commit_size
        else:
            commit = self.compressed_clusters
            self.compressed_clusters = []
            self.compressed_size = 0
        # TODO stretch must be in order if gap=0
        stretch = []
        for i in range(eoc):
            cc = commit[i]
            if (commit_size & (self.cluster_size - 1)) <= cc.size:
                stretch.append(i)
                commit_size -= cc.size
        file_offset = self.fileobj.tell()
        for index in stretch:
            cc = commit[index]
            self.fileobj.seek(cc.l2_offset)
            self.fileobj.write(self.new_l2_entry(cc.offset, file_offset))
            file_offset += self.cluster_size
        self.fileobj.seek(0, os.SEEK_END)
        for index in stretch:
            cc = commit[index]
            self.original.seek(cc.offset)
            self.fileobj.write(self.original.read(self.cluster_size))
        for index in stretch[::-1]:
            commit.pop(index)
        for cc in commit:
            file_offset = self.fileobj.tell()
            self.fileobj.write(cc.compressed_bytes)
            self.fileobj.seek(cc.l2_offset)
            self.fileobj.write(self.new_l2_entry(cc.offset, file_offset, True, cc.size))
            self.fileobj.seek(0, os.SEEK_END)
        realign(self.fileobj, self.cluster_size)

    def close(self):
        if self.compressed_clusters:
            self.commit_compressed_clusters(True)
        for offset in self.zero_clusters[:-1]:
            ref = self.original.read_refcount(offset)
            entry = L2TableEntry(1 if ref == 1 else 0, 0, 1)
            self._write_cluster_entry(offset, entry)

        self.close_redirect()


class Qcow2Modifier(object):
    def __init__(self, base_qcow2, output):
        """
        :param Qcow2File base_qcow2:
        """
        self.original = base_qcow2
        self.header = Header.from_buffer_copy(base_qcow2.header)
        # TODO: rename at last
        self.fileobj = open(output, 'wb') if isinstance(output, str) else output
        reserve(self.fileobj, sizeof(Header))
        self.header.backing_file_offset = self.fileobj.tell()
        self.header.backing_file_size = len(self.original.backingFile)
        self.fileobj.write(self.original.backingFile)

    def begin_append_clusters(self, last_cluster_offset=0, refcount_order=0, cluster_bits=0):
        if refcount_order:
            self.header.refcount_order = refcount_order
        if cluster_bits:
            self.header.cluster_bits = cluster_bits
        if last_cluster_offset:
            last_cluster_no = last_cluster_offset >> self.header.cluster_bits
        else:
            last_cluster_no = self.original.get_last_cluster_number()

        cluster_size = 1 << self.header.cluster_bits
        realign(self.fileobj, cluster_size)

        per_cluster = calc_refcounts_per_cluster(self.header.cluster_bits, self.header.refcount_order)
        rc_cluster_count = (last_cluster_no + per_cluster - 1) / per_cluster
        table_size = (rc_cluster_count * sizeof(RefcountTableEntry) + cluster_size - 1) >> self.header.cluster_bits
        self.header.refcount_table_clusters = table_size
        self.header.refcount_table_offset = self.fileobj.tell()
        reserve(self.fileobj, table_size << self.header.cluster_bits)

        l2_count_in_block = 1 << (self.header.cluster_bits - 3)
        l1_count = (last_cluster_no + l2_count_in_block - 1) / l2_count_in_block
        self.header.l1_size = l1_count
        self.header.l1_table_offset = self.fileobj.tell()
        reserve(self.fileobj, l1_count * sizeof(L1TableEntry))

        realign(self.fileobj, cluster_size)
        unmap = not self.header.backing_file_offset
        return Qcow2ClusterAppender(self, unmap, 0)

    def finish_clusters(self, l1_entries, refs):
        l2_clusters_size = 1 << (self.header.cluster_bits * 2 - 3)
        for image_offset, file_offset in l1_entries:
            index = image_offset / l2_clusters_size
            self.fileobj.seek(self.header.l1_table_offset + index * sizeof(L1TableEntry))
            self.fileobj.write(L1TableEntry(1, 0, file_offset))
        refs_clusters_size = 1 << (self.header.cluster_bits * 2 - self.header.refcount_order - 3)
        for image_offset, file_offset in refs:
            index = image_offset / refs_clusters_size
            self.fileobj.seek(self.header.refcount_table_offset + index * sizeof(RefcountTableEntry))
            self.fileobj.write(RefcountTableEntry(file_offset))

    def close(self):
        self.fileobj.seek(0)
        self.fileobj.write(self.header)
        self.fileobj.flush()
        self.fileobj.close()
