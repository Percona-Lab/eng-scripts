# eng-scripts
Scripts from Percona Engineering Team

## Examples

### innodb_page_header.sh
Read information about FSP Flags from page0 header.
In case of encryption, it also displays encryption information:

```
./innodb_page_header.sh ./var/mysqld.1/data/test/t1.ibd
Reading FSP_FLAGS of ./var/mysqld.1/data/test/t1.ibd
SPACE_ID of tablespace:           5

FLAGS: 24609
ANTELOPE: 1
COMPRESSED: NO
ATOMIC_BLOBS: 1
DATADIR: 0
SHARED_TABLESPACE: 0
TEMPORARY TABLESPACE: 0
ENCRYPTION: 1
SDI: 1
PHYSICAL_PAGE_SIZE: 16384
UNCOMP_PAGE_SIZE  : 16384
ENCRYPTION OFFSET : 10390

------ Encryption ------
ENCRYPTION_KEY_MAGIC: lCC
MASTER_KEY_ID: 00000000000000000000000000000001 ( 1 )
SERVER UUID: caf6e3c6-0460-11eb-9f20-70c94eede3ef
Key:
000028c1: 4078 4a03 f336 606b 230c b10e 4004 f274  @xJ..6`k#...@..t
000028d1: 57bf f9e2 35a4 cf3e 178d 50ef fdda 1c70  W...5..>..P....p
iv:
000028e1: 736f c272 f86d 553b 2683 a8af 4eb3 2fd0  so.r.mU;&...N./.
000028f1: c88d 3532 15cd 334b 6fef 98c2 476b b72b  ..52..3Ko...Gk.+
```

### dump_space_ids.sh
Dumps tablespace_ids of all tablespaces (.ibd, .ibu, undo*, ibtmp*)

```
./dump_space_ids.sh ./var/mysqld.1/data/
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
