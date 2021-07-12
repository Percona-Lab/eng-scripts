#!/bin/bash
# Common functions from innodb

decode_page0_flags()
{
  FILE=$1
  FLAGS=$(xxd -b -s54 -l4 $FILE | awk '{print $2 $3 $4 $5}')
  #other way. Depends on od have --endian option. Not all od versions have it
  #FLAGS=$(od -An -j 54 -D -N4  --endian=big $FILE')// For 4 bytes, use -D
  #LSN=$(od -An -j 16 -L -N8  --endian=big $FILE') // For 8 bytes, use -L
  FLAGS=`echo "ibase=2; $FLAGS" | bc`

  export FLAGS
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

  export ANTELOPE=$(($FLAGS & 1))

  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_POST_ANTELOPE))
  export ZIP_SSIZE=$(($FLAGS & $BIT4_MASK))

  PHY_SIZE=0
  if [ $ZIP_SSIZE != 0 ]; then
   COMPRESSED_PAGE_SIZE=$((512 << $ZIP_SSIZE))
   PHY_SIZE=$COMPRESSED_PAGE_SIZE
  fi

  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_ZIP_SSIZE))
  export ATOMIC_BLOBS=$(($FLAGS & 1))

  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_ATOMIC_BLOBS))
  export PAGE_SSIZE=$(($FLAGS & $BIT4_MASK))

  if [ $PAGE_SSIZE != 0 ]; then
   export UNCOMPRESSED_PAGE_SIZE=$((512 << $PAGE_SSIZE))
  else
   export UNCOMPRESSED_PAGE_SIZE=16384
  fi

  if [ $PHY_SIZE == 0 ]; then
     PHY_SIZE=$UNCOMPRESSED_PAGE_SIZE
  fi
  export PHY_SIZE
  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_PAGE_SSIZE))
  export DATA_DIR=$(($FLAGS & 1))

  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_DATA_DIR))
  export SHARED=$(($FLAGS & 1))

  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_SHARED))
  export TEMPORARY=$(($FLAGS & 1))

  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_TEMPORARY))
  export ENCRYPTION=$(($FLAGS & 1))

  FLAGS=$(($FLAGS >> $S_FSP_FLAGS_WIDTH_ENCRYPTION))
  export SDI=$(($FLAGS & 1))

}