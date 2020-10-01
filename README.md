# eng-scripts
Scripts from MySQL Engineering Team

## Examples

### innodb_page_header.sh
Read information about FSP Flags from page0 header.
In case of encryption, it also displays encryption information:

```
./innodb_page_header.sh /work/mysql/bld/usr/local/mysql/data/test/sbtest1.ibd
Reading FSP_FLAGS of /work/mysql/bld/usr/local/mysql/data/test/sbtest1.ibd

FLAGS: 8225
ANTELOPE is 1
ZIP_SSIZE is 0
TABLESPACE is NOT ZIP COMPRESSED
ATOMIC_BLOBS is 1
PAGE_SSIZE is 0
UNCOMPRESSED_PAGE_SIZE is 16384
DATADIR is 0
SHARED_TABLESPACE is 0
TEMPORARY TABLESPACE is 0
ENCRYPTION is 1
SDI is 0

------ Encryption ------
ENCRYPTION_KEY_MAGIC: lCB
MASTER_KEY_ID: 00000000000000000000000000000001 ( 1 )
SERVER UUID: c1f12f66-01c3-11eb-b8f4-d45d6434
Key:
000028c1: 3761 3139 3e3c 5088 f37b 8301 a8d4 e229  7a19><P..{.....)
000028d1: 2350 f2be 0054 735e 6bf0 6aeb b2e3 a8e6  #P...Ts^k.j.....
iv:
000028e1: 02ba 423b e551 6764 5770 f5a9 18f3 d2a9  ..B;.QgdWp......
000028f1: 5a21 732a 7fd3 12d0 7b74 6ec2 dc36 a909  Z!s*....{tn..6..

### dump_space_ids.sh
Dumps tablespace_ids of all tablespaces (.ibd, .ibu, undo*, ibtmp*)

dump_space_ids.sh ./var/mysqld.1/data/
file name ./var/mysqld.1/data/satya/t3.ibd : space_id           9
file name ./var/mysqld.1/data/satya/t2.ibd : space_id           8
file name ./var/mysqld.1/data/satya/t1.ibd : space_id           7
file name ./var/mysqld.1/data/mysql.ibd : space_id  4294967294
file name ./var/mysqld.1/data/sys/sys_config.ibd : space_id           1
file name ./var/mysqld.1/data/test/t3.ibd : space_id           6
file name ./var/mysqld.1/data/test/t2.ibd : space_id           5
file name ./var/mysqld.1/data/test/t1.ibd : space_id           4
file name ./var/mysqld.1/data/mtr/test_suppressions.ibd : space_id           2
file name ./var/mysqld.1/data/mtr/global_suppressions.ibd : space_id           3
file name ./var/mysqld.1/data/undo_001 : space_id  4294967279
file name ./var/mysqld.1/data/undo_002 : space_id  4294967278
file name ./var/mysqld.1/data/ibtmp1 : space_id  4294967293
file name ./var/mysqld.1/data/ibdata1 : space_id           0

```
