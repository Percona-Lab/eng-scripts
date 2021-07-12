#!/bin/bash
# Dump information from page header
# Print information about encryption

DIR="$( dirname "$0" )"

. ${DIR}/innodb_common.sh

FILE=$1
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