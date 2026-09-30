#!/bin/bash
# Dump information from page header
# Print information about encryption

DIR="$( dirname "$0" )"

. ${DIR}/innodb_common.sh

FILE=$1
OFFSET=0
echo "============ Export tablespace dump ============"

echo "============ START HEADER ============"

#Version
VERSION=$(od -An -D -N4 --endian=big $FILE | awk '{print $1}')
OFFSET=$(($OFFSET + 4))
echo "CFG Version: ${VERSION}"
if [[  "${VERSION}" -ne "7" ]];
then
  echo "Currently only CFG version 7 supported"
  exit 1
fi

#Hostname
HOSTNAME_LEN=$(od -An -D -j${OFFSET} -N4 --endian=big $FILE | awk '{print $1}')
echo "Hostname len: ${HOSTNAME_LEN}"
OFFSET=$(($OFFSET + 4))
HOSTNAME=$(xxd -p -s${OFFSET} -l${HOSTNAME_LEN} $FILE | xxd -r -p | tr -d '\0')
echo "Hostname: ${HOSTNAME}"
OFFSET=$(($OFFSET + ${HOSTNAME_LEN}))

#Table
TABLE_LEN=$(od -An -D -j${OFFSET} -N4 --endian=big $FILE | awk '{print $1}')
echo "Table len: ${TABLE_LEN}"
OFFSET=$(($OFFSET + 4))
TABLE=$(xxd -p -s${OFFSET} -l${TABLE_LEN} $FILE | xxd -r -p | tr -d '\0')
echo "Table: ${TABLE}"
OFFSET=$(($OFFSET + ${TABLE_LEN}))

#AutoInc
AUTOINC=$(od -An -D -j${OFFSET} -N8 --endian=big $FILE | awk '{print $1}')
echo "Next Autoinc: ${AUTOINC}"
OFFSET=$(($OFFSET + 8))

#Page Size
PAGESIZE=$(od -An -D -j${OFFSET} -N4 --endian=big $FILE | awk '{print $1}')
echo "Page Size (bytes): ${PAGESIZE}"
OFFSET=$(($OFFSET + 4))

#Table Flags
FLAGS=$(xxd -b -s${OFFSET} -l4 $FILE | awk '{print $2 $3 $4 $5}')
echo "Table Flags: ${FLAGS}"
decode_flags ${FLAGS}
print_decoded_flags
OFFSET=$(($OFFSET + 4))

#Number of Columns
N_OF_COLUMNS=$(od -An -D -j${OFFSET} -N4 --endian=big $FILE | awk '{print $1}')
echo "Number of Columns: ${N_OF_COLUMNS}"
OFFSET=$(($OFFSET + 4))

#Null Columns before 1st INSTANT
N_OF_NULL_COLUMNS=$(od -An -D -j${OFFSET} -N4 --endian=big $FILE | awk '{print $1}')
echo "Number of NULL Columns: ${N_OF_NULL_COLUMNS}"
OFFSET=$(($OFFSET + 4))

#Instant metadata
INITIAL_COL_COUNT=$(od -An -D -j${OFFSET} -N4 --endian=big $FILE | awk '{print $1}')
echo "Initial Column Count: ${INITIAL_COL_COUNT}"
OFFSET=$(($OFFSET + 4))
CURRENT_COL_COUNT=$(od -An -D -j${OFFSET} -N4 --endian=big $FILE | awk '{print $1}')
echo "Current Column Count: ${CURRENT_COL_COUNT}"
OFFSET=$(($OFFSET + 4))
TOTAL_COL_COUNT=$(od -An -D -j${OFFSET} -N4 --endian=big $FILE | awk '{print $1}')
echo "Total Column Count: ${TOTAL_COL_COUNT}"
OFFSET=$(($OFFSET + 4))
INSTANT_DROP_COLS=$(od -An -D -j${OFFSET} -N4 --endian=big $FILE | awk '{print $1}')
echo "Instant Dropped Columns: ${INSTANT_DROP_COLS}"
OFFSET=$(($OFFSET + 4))
CURRENT_ROW_VERSION=$(od -An -D -j${OFFSET} -N4 --endian=big $FILE | awk '{print $1}')
echo "Current Row Version: ${CURRENT_ROW_VERSION}"
OFFSET=$(($OFFSET + 4))

SPACE_FLAGS=$(xxd -b -s${OFFSET} -l4 $FILE | awk '{print $2 $3 $4 $5}')
echo "Space flags: ${SPACE_FLAGS}"
decode_flags ${FLAGS}
print_decoded_flags
OFFSET=$(($OFFSET + 4))

COMPRESSION_TYPE=$(od -An -D -j${OFFSET} -N1 --endian=big $FILE | awk '{print $1}')
echo "Compression type: ${COMPRESSION_TYPE}"
OFFSET=$(($OFFSET + 1))

echo "============ END HEADER ============"



echo "============ START TABLE ============"

if [[ "${CURRENT_ROW_VERSION}" -eq "0" ]];
then
  NUMBER_OF_COLUMNS=
fi

exit 0;










decode_encryption() {
  PHY_SIZE=$1
  OFFSET=0
  case $PHY_SIZE in
  65536)
    OFFSET=41110
    ;;
  32768)
    OFFSET=20630
    ;;
  16384)
    OFFSET=10390
    ;;
  8192)
    OFFSET=5270
    ;;
  4096)
    OFFSET=2710
    ;;
  2048)
    OFFSET=1430
    ;;
  1024)
    OFFSET=790
    ;;
esac

  if [ $OFFSET == 0 ]; then
   echo "Invalid Page Size found. Cannot decode encryption information from Page 0"
   return;
  fi

  echo "ENCRYPTION OFFSET : $OFFSET"

  echo
  echo "------ Encryption ------"
  ENCRYPTION_KEY_MAGIC=$(xxd -p -s$OFFSET -l3 $FILE | xxd -r -p)
  echo "ENCRYPTION_KEY_MAGIC: $ENCRYPTION_KEY_MAGIC"
  OFFSET=$(($OFFSET + 3))
  MASTER_KEY_ID=$(xxd -b -s$OFFSET -l4 $FILE |  awk '{print $2 $3 $4 $5}')
  echo "MASTER_KEY_ID: $MASTER_KEY_ID ( $((2#$MASTER_KEY_ID)) )"
  OFFSET=$(($OFFSET + 4))
  SERVER_UUID=$(xxd -p -s$OFFSET -l36 $FILE | xxd -r -p | tr -d '\0')
  echo "SERVER UUID: $SERVER_UUID"
  echo "Key:"
  OFFSET=$(($OFFSET + 36))
  xxd -s$OFFSET -l32 $FILE
  OFFSET=$(($OFFSET + 32))
  echo "iv:"
  xxd -s$OFFSET -l32 $FILE
}

print_decoded_flags() {
  echo "FLAGS: $FLAGS"
  echo "ANTELOPE: $ANTELOPE"

  if [ $ZIP_SSIZE != 0 ]; then
   echo "COMPRESSED: YES"
  else
   echo "COMPRESSED: NO"
  fi

  echo "ATOMIC_BLOBS: $ATOMIC_BLOBS"

  echo "DATADIR: $DATA_DIR"

  echo "SHARED_TABLESPACE: $SHARED"

  echo "TEMPORARY TABLESPACE: $TEMPORARY"

  echo "ENCRYPTION: $ENCRYPTION"

  echo "SDI: $SDI"

  echo "PHYSICAL_PAGE_SIZE: $PHY_SIZE"
  echo "UNCOMP_PAGE_SIZE  : $UNCOMPRESSED_PAGE_SIZE"

  if [[ $ENCRYPTION -eq "1" ]]; then
    decode_encryption $PHY_SIZE
  fi
}
echo "Reading FSP_FLAGS of ${FILE}"
SPACE_ID=$(od -An -j38 -D -N4 --endian=big $FILE)
echo "SPACE_ID of tablespace: $SPACE_ID"

echo
decode_page0_flags $FILE
print_decoded_flags