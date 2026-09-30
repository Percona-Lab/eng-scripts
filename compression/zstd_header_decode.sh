#!/bin/bash
# Dump information from zstd header


FILE=$1

#Magic Number
OFFSET=0
MAGIC_NUMBER=$(xxd -p -s$OFFSET -l4 $FILE )
OFFSET=$(($OFFSET + 4))
echo "MAGIC_NUMBER: $MAGIC_NUMBER"

#Frame_Header_Descriptor
FRAME_HEADER_DESCRIPTOR=$(xxd -b -s$OFFSET -l1 $FILE | awk '{print $2}')
OFFSET=$(($OFFSET + 1))
echo "FRAME_HEADER_DESCRIPTOR: $FRAME_HEADER_DESCRIPTOR"
BIT4_MASK=$(($((1<<4)) - 1))
echo "Frame_Content_Size_flag: $Frame_Content_Size_flag"
FRAME_HEADER_DESCRIPTOR=$(($FRAME_HEADER_DESCRIPTOR >> 2))
export DATA_DIR=$(($FLAGS & 1))