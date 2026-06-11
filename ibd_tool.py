#!/usr/bin/env python3
"""InnoDB on-disk page helpers for the --check-tables (PXB-3804/3807) tests.

The accessors below deliberately mirror the InnoDB C API (same names, same
offsets) so a reader who knows the engine can follow them at a glance:

    fil_page_get_type(page) == FIL_PAGE_INDEX
    btr_page_get_level(page)
    btr_page_get_index_id(page)
    rec_get_next_offs(page, rec_offset)

A "page" here is just the bytes object for one page; mach_read_from_N(buf, off)
is int.from_bytes(buf[off:off+N], 'big'), exactly like InnoDB's big-endian
mach_read_from_N(ptr). Offsets/constants come from
storage/innobase/include/{fil0types.h,page0types.h,fsp0types.h,rem0rec.h}.

It is driven from inc/common.sh via small subcommands, but is also a usable
standalone forensics tool from the terminal:

    # quick look at a tablespace (page size, page count, page-0 header)
    python3 ibd_tool.py t1.ibd

    # dump one page's FIL + index header fields
    python3 ibd_tool.py header t1.ibd 3

    # list every page (type; level/index-id/n_recs for INDEX pages)
    python3 ibd_tool.py scan t1.ibd

    # raw field access (big-endian); value may be 0x-hex on write
    python3 ibd_tool.py page-size t1.ibd
    python3 ibd_tool.py read  t1.ibd 0 38 4           # FSP_SPACE_FLAGS
    python3 ibd_tool.py write t1.ibd 5 24 0x0000 2    # corrupt FIL_PAGE_TYPE

    # B-tree navigation used by the tests
    python3 ibd_tool.py find-index-page      t1.ibd 0     # first leaf
    python3 ibd_tool.py clustered-pages      t1.ibd       # "MAXLEVEL L0 L1 L2"
    python3 ibd_tool.py leftmost-node-ptr    t1.ibd       # "ROOT OFF"
    python3 ibd_tool.py first-user-rec-origin t1.ibd 3

Every subcommand takes the tablespace file as its first argument. Commands that
need a page size accept an optional trailing override; omit it (or pass an
empty string) to read it from the FSP header on page 0. Run with -h/--help (or
no arguments) to print this usage. See main()/USAGE below for the full list.
"""

import os
import sys

# --- fil0types.h : file page header (the "FIL header") ----------------------
FIL_PAGE_OFFSET = 4        # page number of this page (4 bytes)
FIL_PAGE_PREV = 8          # previous page in the index (4 bytes)
FIL_PAGE_NEXT = 12         # next page in the index (4 bytes)
FIL_PAGE_LSN = 16          # LSN of the page's latest log record (8 bytes)
FIL_PAGE_TYPE = 24         # page type (2 bytes)
FIL_PAGE_DATA = 38         # start of the data / index header on the page
FIL_PAGE_INDEX = 0x45BF    # FIL_PAGE_TYPE value for a B-tree node

# FIL_PAGE_TYPE values (fil0fil.h), for human-readable dumps.
PAGE_TYPE_NAMES = {
    0: "ALLOCATED", 1: "UNUSED", 2: "UNDO_LOG", 3: "INODE",
    4: "IBUF_FREE_LIST", 5: "IBUF_BITMAP", 6: "SYS", 7: "TRX_SYS",
    8: "FSP_HDR", 9: "XDES", 10: "BLOB", 11: "ZBLOB", 12: "ZBLOB2",
    13: "UNKNOWN", 14: "COMPRESSED", 15: "ENCRYPTED",
    16: "COMPRESSED_AND_ENCRYPTED", 17: "ENCRYPTED_RTREE",
    18: "SDI_BLOB", 19: "SDI_ZBLOB",
    22: "LOB_INDEX", 23: "LOB_DATA", 24: "LOB_FIRST",
    25: "ZLOB_FIRST", 26: "ZLOB_DATA", 27: "ZLOB_INDEX",
    28: "ZLOB_FRAG", 29: "ZLOB_FRAG_ENTRY",
    0x45BD: "SDI", 0x45BE: "RTREE", 0x45BF: "INDEX",
}

# --- page0types.h : index page header (starts at PAGE_HEADER) ----------------
PAGE_HEADER = FIL_PAGE_DATA
PAGE_N_DIR_SLOTS = 0       # number of page-directory slots (2 bytes)
PAGE_HEAP_TOP = 2          # offset of the heap top (2 bytes)
PAGE_N_HEAP = 4            # records in the heap; bit15 = compact format
PAGE_N_RECS = 16           # number of user records (2 bytes)
PAGE_LEVEL = 26            # B-tree level, 0 == leaf (2 bytes)
PAGE_INDEX_ID = 28         # index id this page belongs to (8 bytes)
PAGE_NEW_INFIMUM = 99      # infimum record origin on a COMPACT page

# --- rem0rec.h ---------------------------------------------------------------
REC_NEXT = 2               # the 2-byte "next" field sits at rec_origin - REC_NEXT

# --- fsp0types.h : the FSP header on page 0 ---------------------------------
FSP_HEADER_OFFSET = FIL_PAGE_DATA
FSP_SPACE_ID = 0           # space id (4 bytes) -> absolute offset 38
FSP_SPACE_FLAGS = 16       # FSP_SPACE_FLAGS (4 bytes) -> absolute offset 54

# Byte offset of the encryption info (MAGIC/key/iv) within page 0, keyed by the
# PHYSICAL page size. Mirrors innodb_page_header.sh; it is FSP_HEADER + the XDES
# array, which grows with the page size.
ENCRYPTION_INFO_OFFSET = {
    1024: 790, 2048: 1430, 4096: 2710, 8192: 5270,
    16384: 10390, 32768: 20630, 65536: 41110,
}
ENCRYPTION_MAGIC_LEN = 3   # "lCA"/"lCB"/"lCC" version magic
ENCRYPTION_KEY_LEN = 32
ENCRYPTION_SERVER_UUID_LEN = 36


# ---------------------------------------------------------------------------
# mach_read_from_N(buf, off): big-endian field reads, like the InnoDB C macros.
# ---------------------------------------------------------------------------
def mach_read_from_1(b, off):
    return b[off]


def mach_read_from_2(b, off):
    return int.from_bytes(b[off:off + 2], "big")


def mach_read_from_4(b, off):
    return int.from_bytes(b[off:off + 4], "big")


def mach_read_from_8(b, off):
    return int.from_bytes(b[off:off + 8], "big")


def mach_read_from_n(b, off, n):
    return int.from_bytes(b[off:off + n], "big")


# ---------------------------------------------------------------------------
# Page-header accessors, named after their InnoDB counterparts. Each takes a
# whole-page bytes object ("page").
# ---------------------------------------------------------------------------
def fil_page_get_type(page):
    return mach_read_from_2(page, FIL_PAGE_TYPE)


def fil_page_index_page_check(page):
    return fil_page_get_type(page) == FIL_PAGE_INDEX


def page_get_page_no(page):
    return mach_read_from_4(page, FIL_PAGE_OFFSET)


def fil_page_get_prev(page):
    return mach_read_from_4(page, FIL_PAGE_PREV)


def fil_page_get_next(page):
    return mach_read_from_4(page, FIL_PAGE_NEXT)


def fil_page_get_lsn(page):
    return mach_read_from_8(page, FIL_PAGE_LSN)


def page_header_get_field(page, field):
    return mach_read_from_2(page, PAGE_HEADER + field)


def page_header_get_offs(page, field):     # PAGE_HEAP_TOP / PAGE_FREE ...
    return page_header_get_field(page, field)


def btr_page_get_level(page):
    return page_header_get_field(page, PAGE_LEVEL)


def btr_page_get_index_id(page):
    return mach_read_from_8(page, PAGE_HEADER + PAGE_INDEX_ID)


def page_get_n_recs(page):
    return page_header_get_field(page, PAGE_N_RECS)


def page_dir_get_n_slots(page):
    return page_header_get_field(page, PAGE_N_DIR_SLOTS)


def rec_get_next_offs(page, rec_offset):
    """Offset of the record after the one at rec_offset (COMPACT page).

    Like InnoDB: the 2-byte value at rec_offset - REC_NEXT is a page-relative
    delta that wraps within the page (page sizes divide 65536, so a plain
    modulo reproduces the signed-16 wrap). 0 means "no next record".
    """
    field = mach_read_from_2(page, rec_offset - REC_NEXT)
    return 0 if field == 0 else (rec_offset + field) % len(page)


def fsp_flags_get_page_size(flags):
    """Logical page size from FSP_SPACE_FLAGS (PAGE_SSIZE field)."""
    ssize = (flags >> 6) & 0xF      # after POST_ANTELOPE(1)+ZIP_SSIZE(4)+ATOMIC_BLOBS(1)
    return 16384 if ssize == 0 else (512 << ssize)


# ---------------------------------------------------------------------------
# File-level operations used by the tests.
# ---------------------------------------------------------------------------
def get_page_size(path):
    with open(path, "rb") as f:
        head = f.read(FSP_HEADER_OFFSET + FSP_SPACE_FLAGS + 4)
    return fsp_flags_get_page_size(
        mach_read_from_4(head, FSP_HEADER_OFFSET + FSP_SPACE_FLAGS))


def read_page(path, page_no, page_size):
    with open(path, "rb") as f:
        f.seek(page_no * page_size)
        return f.read(page_size)


def mach_read_field(path, page_no, offset, n, page_size):
    """Read an n-byte big-endian field at page_no:offset (mirrors mach_read_from_n)."""
    return mach_read_from_n(read_page(path, page_no, page_size), offset, n)


def mach_write_field(path, page_no, offset, value, n, page_size):
    """Write value as an n-byte big-endian field at page_no:offset (mirrors mach_write_to_n)."""
    with open(path, "r+b") as f:
        f.seek(page_no * page_size + offset)
        f.write(value.to_bytes(n, "big"))


def iter_index_pages(path, page_size):
    """Scan the file page by page, yielding (page_no, level, index_id) for
    every INDEX page -- the test-side equivalent of walking the btr pages."""
    n_pages = os.path.getsize(path) // page_size
    with open(path, "rb") as f:
        for page_no in range(n_pages):
            page = f.read(page_size)
            if fil_page_index_page_check(page):
                yield (page_no,
                       btr_page_get_level(page),
                       btr_page_get_index_id(page))


def find_index_page(path, page_size, want_level):
    for page_no, level, _ in iter_index_pages(path, page_size):
        if level == want_level:
            return page_no
    return None


def find_clustered_pages_by_level(path, page_size):
    """(max_level, {level: page_no}) for the clustered index -- the index whose
    root has the deepest level."""
    pages = list(iter_index_pages(path, page_size))
    max_level = max(level for _, level, _ in pages)
    clustered_id = next(idx for _, level, idx in pages if level == max_level)
    at_level = {}
    for page_no, level, idx in pages:
        if idx == clustered_id:
            at_level.setdefault(level, page_no)
    return max_level, at_level


def find_leftmost_node_ptr(path, page_size):
    """(root_page_no, child_page_no_field_offset) for the leftmost node pointer
    on the clustered-index root, or None if the tree is single-level."""
    pages = list(iter_index_pages(path, page_size))
    max_level = max((level for _, level, _ in pages), default=-1)
    if max_level < 1:
        return None
    root = next(page_no for page_no, level, _ in pages if level == max_level)
    first = rec_get_next_offs(read_page(path, root, page_size), PAGE_NEW_INFIMUM)
    # clustered node pointer record = [ PK (4 bytes) ][ child page no (4 bytes) ]
    return root, first + 4


def find_first_user_rec_origin(path, page_no, page_size):
    """In-page offset of the first user record (infimum -> next), COMPACT page."""
    return rec_get_next_offs(read_page(path, page_no, page_size), PAGE_NEW_INFIMUM)


# ---------------------------------------------------------------------------
# Human-readable views (terminal use).
# ---------------------------------------------------------------------------
def _page_type_name(t):
    return PAGE_TYPE_NAMES.get(t, "?")


def dump_page_header(path, page_no, page_size):
    """Multi-line dump of a page's FIL header (and index header for INDEX pages)."""
    page = read_page(path, page_no, page_size)
    t = fil_page_get_type(page)
    out = ["page %d of %s" % (page_no, path),
           "  FIL_PAGE_OFFSET (page no) : %d" % page_get_page_no(page),
           "  FIL_PAGE_TYPE             : %d (%s)" % (t, _page_type_name(t)),
           "  FIL_PAGE_PREV             : %d" % fil_page_get_prev(page),
           "  FIL_PAGE_NEXT             : %d" % fil_page_get_next(page),
           "  FIL_PAGE_LSN              : %d" % fil_page_get_lsn(page)]
    if fil_page_index_page_check(page):
        out += ["  PAGE_LEVEL                : %d" % btr_page_get_level(page),
                "  PAGE_INDEX_ID             : %d" % btr_page_get_index_id(page),
                "  PAGE_N_RECS               : %d" % page_get_n_recs(page),
                "  PAGE_N_DIR_SLOTS          : %d" % page_dir_get_n_slots(page),
                "  PAGE_HEAP_TOP             : %d" % page_header_get_offs(page, PAGE_HEAP_TOP)]
    return "\n".join(out)


def scan_pages(path, page_size):
    """One line per page: number, type, and (for INDEX pages) level/index-id/n_recs."""
    n_pages = os.path.getsize(path) // page_size
    rows = []
    with open(path, "rb") as f:
        for page_no in range(n_pages):
            page = f.read(page_size)
            t = fil_page_get_type(page)
            row = "%6d  %-26s" % (page_no, "%d (%s)" % (t, _page_type_name(t)))
            if fil_page_index_page_check(page):
                row += "  level=%d index_id=%d n_recs=%d" % (
                    btr_page_get_level(page), btr_page_get_index_id(page),
                    page_get_n_recs(page))
            rows.append(row)
    return "\n".join(rows)


def summary(path):
    """Page size, page count, and the page-0 header -- the bare-filename view."""
    psz = get_page_size(path)
    n_pages = os.path.getsize(path) // psz
    return "%s: page_size=%d, pages=%d\n%s" % (
        path, psz, n_pages, dump_page_header(path, 0, psz))


def read_space_id(path):
    """Space id from FSP_SPACE_ID on page 0 (FSP header)."""
    with open(path, "rb") as f:
        head = f.read(FSP_HEADER_OFFSET + FSP_SPACE_ID + 4)
    return mach_read_from_4(head, FSP_HEADER_OFFSET + FSP_SPACE_ID)


def decode_fsp_flags(flags):
    """Decode FSP_SPACE_FLAGS into its named bit-fields (fsp0types.h)."""
    f = flags
    post_antelope = f & 1;            f >>= 1
    zip_ssize = f & 0xF;              f >>= 4
    atomic_blobs = f & 1;             f >>= 1
    page_ssize = f & 0xF;             f >>= 4
    data_dir = f & 1;                 f >>= 1
    shared = f & 1;                   f >>= 1
    temporary = f & 1;                f >>= 1
    encryption = f & 1;               f >>= 1
    sdi = f & 1
    logical = 16384 if page_ssize == 0 else (512 << page_ssize)
    physical = (512 << zip_ssize) if zip_ssize else logical
    return {
        "POST_ANTELOPE": post_antelope, "ZIP_SSIZE": zip_ssize,
        "ATOMIC_BLOBS": atomic_blobs, "PAGE_SSIZE": page_ssize,
        "DATA_DIR": data_dir, "SHARED": shared, "TEMPORARY": temporary,
        "ENCRYPTION": encryption, "SDI": sdi,
        "PHYSICAL_PAGE_SIZE": physical, "LOGICAL_PAGE_SIZE": logical,
        "COMPRESSED": zip_ssize != 0,
    }


def dump_flags(path):
    """Human-readable FSP_SPACE_FLAGS breakdown for page 0 (like decode_flags)."""
    with open(path, "rb") as f:
        head = f.read(FSP_HEADER_OFFSET + FSP_SPACE_FLAGS + 4)
    flags = mach_read_from_4(head, FSP_HEADER_OFFSET + FSP_SPACE_FLAGS)
    d = decode_fsp_flags(flags)
    lines = ["FSP_SPACE_FLAGS of %s: 0x%X (%d)" % (path, flags, flags)]
    for k in ("POST_ANTELOPE", "ZIP_SSIZE", "ATOMIC_BLOBS", "PAGE_SSIZE",
              "DATA_DIR", "SHARED", "TEMPORARY", "ENCRYPTION", "SDI",
              "COMPRESSED", "PHYSICAL_PAGE_SIZE", "LOGICAL_PAGE_SIZE"):
        lines.append("  %-18s: %s" % (k, d[k]))
    return "\n".join(lines)


def dump_encryption(path):
    """Dump the page-0 encryption info (MAGIC, master key id, server uuid, key,
    iv) for an encrypted tablespace -- the decode_encryption use case."""
    with open(path, "rb") as f:
        head = f.read(FSP_HEADER_OFFSET + FSP_SPACE_FLAGS + 4)
        flags = mach_read_from_4(head, FSP_HEADER_OFFSET + FSP_SPACE_FLAGS)
        d = decode_fsp_flags(flags)
        if not d["ENCRYPTION"]:
            return "%s: tablespace is not encrypted (ENCRYPTION flag = 0)" % path
        phys = d["PHYSICAL_PAGE_SIZE"]
        off = ENCRYPTION_INFO_OFFSET.get(phys)
        if off is None:
            return "%s: cannot locate encryption info for physical page size %d" % (path, phys)
        f.seek(off)
        blob = f.read(ENCRYPTION_MAGIC_LEN + 4 + ENCRYPTION_SERVER_UUID_LEN +
                      2 * ENCRYPTION_KEY_LEN)
    p = 0
    magic = blob[p:p + ENCRYPTION_MAGIC_LEN].decode("latin1");  p += ENCRYPTION_MAGIC_LEN
    master_key_id = int.from_bytes(blob[p:p + 4], "big");       p += 4
    uuid = blob[p:p + ENCRYPTION_SERVER_UUID_LEN].rstrip(b"\0").decode("latin1")
    p += ENCRYPTION_SERVER_UUID_LEN
    key = blob[p:p + ENCRYPTION_KEY_LEN].hex();                 p += ENCRYPTION_KEY_LEN
    iv = blob[p:p + ENCRYPTION_KEY_LEN].hex()
    return ("%s: encryption info @ offset %d\n"
            "  MAGIC         : %s\n"
            "  MASTER_KEY_ID : %d\n"
            "  SERVER_UUID   : %s\n"
            "  KEY (hex)     : %s\n"
            "  IV  (hex)     : %s" %
            (path, off, magic, master_key_id, uuid, key, iv))


def dump_space_ids(directory):
    """List the space id of every tablespace file under a directory (dump_space_ids)."""
    import fnmatch
    patterns = ("*.ibd", "undo_[0-9][0-9][0-9]", "ibdata*",
                "*ibtmp*", "*.ibu", "*.new")
    found = []
    for root, _dirs, files in os.walk(directory):
        for name in files:
            if any(fnmatch.fnmatch(name, pat) for pat in patterns):
                path = os.path.join(root, name)
                try:
                    found.append((read_space_id(path), path))
                except (OSError, ValueError):
                    pass
    return "\n".join("%d  %s" % (sid, path) for sid, path in sorted(found))


# ---------------------------------------------------------------------------
# CLI dispatch. The data-only subcommands (read/write/find-*) are called from
# inc/common.sh; header/scan and the bare-filename summary are for terminal use.
# A trailing, possibly-empty page-size argument lets callers pass an exported
# PAGE_SIZE override; when empty it is read from the FSP header.
# ---------------------------------------------------------------------------
USAGE = """ibd_tool.py -- read / scan / edit InnoDB tablespace pages.

Usage:
  python3 ibd_tool.py <file.ibd>                          summary (page size, page count, page-0 header)
  python3 ibd_tool.py header <file> <page_no>             dump a page's FIL/index header fields
  python3 ibd_tool.py scan   <file>                       list every page (type; level/index-id for INDEX)
  python3 ibd_tool.py page-size <file>                     logical page size (from FSP_SPACE_FLAGS)
  python3 ibd_tool.py flags  <file>                        decode FSP_SPACE_FLAGS (encryption/SDI/zip/...)
  python3 ibd_tool.py encryption <file>                    dump page-0 encryption info (magic/key/iv)
  python3 ibd_tool.py space-id   <file>                    space id (FSP_SPACE_ID on page 0)
  python3 ibd_tool.py space-ids  <dir>                     space id of every tablespace file under <dir>
  python3 ibd_tool.py read    <file> <page> <off> <nbytes> [psz]   big-endian unsigned field
  python3 ibd_tool.py write   <file> <page> <off> <value> <nbytes> [psz]   write field (value may be 0x-hex)
  python3 ibd_tool.py find-index-page       <file> <level> [psz]
  python3 ibd_tool.py clustered-pages       <file> [psz]   -> "MAXLEVEL L0 L1 L2"
  python3 ibd_tool.py leftmost-node-ptr     <file> [psz]   -> "ROOT OFF"
  python3 ibd_tool.py first-user-rec-origin <file> <page> [psz]

[psz] is an optional page-size override; omit it (or pass "") to read it from page 0.

Examples:
  python3 ibd_tool.py t1.ibd
  python3 ibd_tool.py header t1.ibd 3
  python3 ibd_tool.py scan   t1.ibd
  python3 ibd_tool.py read   t1.ibd 0 38 4          # FSP_SPACE_FLAGS
  python3 ibd_tool.py write  t1.ibd 5 24 0x0000 2   # corrupt FIL_PAGE_TYPE
"""

_SUBCOMMANDS = {
    "page-size", "read", "write", "header", "scan",
    "flags", "encryption", "space-id", "space-ids",
    "find-index-page", "clustered-pages", "leftmost-node-ptr",
    "first-user-rec-origin",
}


def _opt(rest, i):
    """Optional positional arg: rest[i] if present, else "" (so [psz] can be omitted)."""
    return rest[i] if i < len(rest) else ""


def _psz(path, arg):
    return int(arg) if arg else get_page_size(path)


def main(argv):
    # No args or an explicit help request: print usage.
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(USAGE)
        return

    # Convenience: `ibd_tool.py <file> [page_no]` (first arg is a file, not a
    # subcommand) -> summary, or that page's header.
    if argv[1] not in _SUBCOMMANDS and os.path.exists(argv[1]):
        path = argv[1]
        if len(argv) >= 3:
            print(dump_page_header(path, int(argv[2]), get_page_size(path)))
        else:
            print(summary(path))
        return

    if argv[1] not in _SUBCOMMANDS:
        print(USAGE)
        sys.exit("ibd_tool.py: unknown subcommand or missing file %r" % argv[1])

    cmd, path, rest = argv[1], argv[2], argv[3:]

    if cmd == "page-size":
        print(get_page_size(path))

    elif cmd == "header":
        print(dump_page_header(path, int(rest[0]), _psz(path, _opt(rest, 1))))

    elif cmd == "scan":
        print(scan_pages(path, _psz(path, _opt(rest, 0))))

    elif cmd == "flags":
        print(dump_flags(path))

    elif cmd == "encryption":
        print(dump_encryption(path))

    elif cmd == "space-id":
        print(read_space_id(path))

    elif cmd == "space-ids":
        print(dump_space_ids(path))      # here "path" is a directory

    elif cmd == "read":
        page_no, offset, n = int(rest[0]), int(rest[1]), int(rest[2])
        print(mach_read_field(path, page_no, offset, n, _psz(path, _opt(rest, 3))))

    elif cmd == "write":
        page_no, offset = int(rest[0]), int(rest[1])
        value, n = int(rest[2], 0), int(rest[3])     # value may be 0x-hex
        mach_write_field(path, page_no, offset, value, n, _psz(path, _opt(rest, 4)))

    elif cmd == "find-index-page":
        page_no = find_index_page(path, _psz(path, _opt(rest, 1)), int(rest[0]))
        if page_no is not None:
            print(page_no)

    elif cmd == "clustered-pages":
        max_level, at = find_clustered_pages_by_level(path, _psz(path, _opt(rest, 0)))
        print("%d %s %s %s" % (max_level, at.get(0, "NONE"),
                               at.get(1, "NONE"), at.get(2, "NONE")))

    elif cmd == "leftmost-node-ptr":
        res = find_leftmost_node_ptr(path, _psz(path, _opt(rest, 0)))
        print("ERR not enough levels" if res is None else "%d %d" % res)

    elif cmd == "first-user-rec-origin":
        print(find_first_user_rec_origin(path, int(rest[0]), _psz(path, _opt(rest, 1))))


if __name__ == "__main__":
    main(sys.argv)
