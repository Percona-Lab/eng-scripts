#!/bin/bash
# Dump information from page header
# Print information about encryption


FILE=$1
decode_encryption() {
  echo
  echo "------ Encryption ------"
  ENCRYPTION_KEY_MAGIC=$(xxd -p -s10390 -l3 $FILE | xxd -r -p)
  echo "ENCRYPTION_KEY_MAGIC: $ENCRYPTION_KEY_MAGIC"
  MASTER_KEY_ID=$(xxd -b -s10393 -l4 $FILE |  awk '{print $2 $3 $4 $5}')
  echo "MASTER_KEY_ID: $MASTER_KEY_ID ( $((2#$MASTER_KEY_ID)) )"
  SERVER_UUID=$(xxd -p -s10397 -l36 $FILE | xxd -r -p | tr -d '\0')
  echo "SERVER UUID: $SERVER_UUID"
  echo "Key":
  xxd -s10433 -l32 $FILE
  echo "iv: "
  xxd -s10465 -l32 $FILE
}
decode_flags() {
  FLAGS=$1
  S_FSP_FLAGS_WIDTH_POST_ANTELOPE=1
  S_FSP_FLAGS_WIDTH_ZIP_SSIZE=4
  S_FSP_FLAGS_WIDTH_ATOMIC_BLOBS=1
  S_FSP_FLAGS_WIDTH_PAGE_SSIZE=4
  S_FSP_FLAGS_WIDTH_DATA_DIR=1
  S_FSP_FLAGS_WIDTH_SHARED=1
  S_FSP_FLAGS_WIDTH_TEMPORARY=1
  S_FSP_FLAGS_WIDTH_ENCRYPTION=1
  S_FSP_FLAGS_WIDTH_SDI=1
  BIT4_MASK=$(($((1<<4)) - 1))
  ANTELOPE=$(($FLAGS & 1))
  echo "ANTELOPE is $ANTELOPE"
  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_POST_ANTELOPE))
  ZIP_SSIZE=$(($FLAGS & $BIT4_MASK))
  echo "ZIP_SSIZE is $ZIP_SSIZE"
  if [ $ZIP_SSIZE != 0 ]; then
   COMPRESSED_PAGE_SIZE=$((512 << $ZIP_SSIZE))
   echo "COMPRESSED_PAGE_SIZE is $COMPRESSED_PAGE_SIZE"
  else
   echo "TABLESPACE is NOT ZIP COMPRESSED"
  fi
  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_ZIP_SSIZE))
  ATOMIC_BLOBS=$(($FLAGS & 1))
  echo "ATOMIC_BLOBS is $ATOMIC_BLOBS"
  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_ATOMIC_BLOBS))
  PAGE_SSIZE=$(($FLAGS & $BIT4_MASK))
  echo "PAGE_SSIZE is $PAGE_SSIZE"
  if [ $PAGE_SSIZE != 0 ]; then
   UNCOMPRESSED_PAGE_SIZE=$((512 << $PAGE_SSIZE))
   echo "UNCOMPRESSED_PAGE_SIZE is $UNCOMPRESSED_PAGE_SIZE"
  else
   echo "UNCOMPRESSED_PAGE_SIZE is 16384"
  fi
  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_PAGE_SSIZE))
  DATA_DIR=$(($FLAGS & 1))
  echo "DATADIR is $DATA_DIR"
  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_DATA_DIR))
  SHARED=$(($FLAGS & 1))
  echo "SHARED_TABLESPACE is $SHARED"
  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_SHARED))
  TEMPORARY=$(($FLAGS & 1))
  echo "TEMPORARY TABLESPACE is $TEMPORARY"
  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_TEMPORARY))
  ENCRYPTION=$(($FLAGS & 1))
  echo "ENCRYPTION is $ENCRYPTION"
  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_ENCRYPTION))
  SDI=$(($FLAGS & 1))
  echo "SDI is $SDI"
 
  if [[ $ENCRYPTION -eq "1" ]]; then
    decode_encryption
  fi
}
echo "Reading FSP_FLAGS of ${FILE}"
echo
FLAGS=$(xxd -b -s54 -l4 $FILE | awk '{print $2 $3 $4 $5}')
#other way. Depends on od have --endian option. Not all od versions has it
#FLAGS=$(od -An -j 54 -d -N4  --endian=big $FILE |awk '{print $2}')
FLAGS=`echo "ibase=2; $FLAGS" | bc`
echo "FLAGS: $FLAGS"
decode_flags $FLAGS
