#!/bin/bash
# Dump innodb redo log block header


PARENT_DIR=$(dirname "${BASH_SOURCE[0]}")
. $PARENT_DIR/common.sh

FILE=$1

FILE_SIZE=$(stat -c%s "$FILE")
echo "File Size: $FILE_SIZE"
TOTAL_BLOCKS=$((($FILE_SIZE - $LOG_FILE_HDR_SIZE) / $OS_FILE_LOG_BLOCK_SIZE))
echo "Total Blocks: $TOTAL_BLOCKS"
FILE_START_LSN=$(od -j$((0+8))  -N8 -An -L --endian=big $FILE | awk '{print $1}')
echo "File Start LSN: $FILE_START_LSN"

function print_block() {
  BLOCK_NR=$1
  OFFSET=$(($LOG_FILE_HDR_SIZE + ($BLOCK_NR * $OS_FILE_LOG_BLOCK_SIZE)))
  echo "Block: $BLOCK_NR"
  echo "Offset: $OFFSET"
  BLOCK_IN_FILE_BINARY=$(xxd -b -s$OFFSET -l4 $FILE | awk '{print $2 $3 $4 $5}')
  BLOCK_IN_FILE_DECIMAL=$((2#$BLOCK_IN_FILE_BINARY))
  echo "Block Nr in File hdr: $BLOCK_IN_FILE_DECIMAL"
}

function dump_all_blocks() {
  CURRENT_BLOCK_START=0
  while [ $CURRENT_BLOCK_START -lt $TOTAL_BLOCKS ]; do
    print_block $CURRENT_BLOCK_START
    CURRENT_BLOCK_START=$(($CURRENT_BLOCK_START + 1))
  done
}

function find_block_jump() {
  CURRENT_BLOCK_START=0
  LAST_BLOCK_IN_FILE_DECIMAL=0
  while [ $CURRENT_BLOCK_START -lt $TOTAL_BLOCKS ]; do
    OFFSET=$(($LOG_FILE_HDR_SIZE + ($CURRENT_BLOCK_START * $OS_FILE_LOG_BLOCK_SIZE)))
    BLOCK_IN_FILE_BINARY=$(xxd -b -s$OFFSET -l4 $FILE | awk '{print $2 $3 $4 $5}')
    BLOCK_IN_FILE_DECIMAL=$((2#$BLOCK_IN_FILE_BINARY))
    if [ $BLOCK_IN_FILE_DECIMAL -ne $((LAST_BLOCK_IN_FILE_DECIMAL+1)) -a $LAST_BLOCK_IN_FILE_DECIMAL -ne 0 ]; then
      echo "Block Jump Found"
      echo "*** Previous Block:"
      print_block $((CURRENT_BLOCK_START-1))
      echo "*** Current Block:"
      print_block $CURRENT_BLOCK_START
      break
    fi
    LAST_BLOCK_IN_FILE_DECIMAL=$BLOCK_IN_FILE_DECIMAL
    CURRENT_BLOCK_START=$(($CURRENT_BLOCK_START + 1))
  done
}




find_block_jump


