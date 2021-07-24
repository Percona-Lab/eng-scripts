#!/bin/bash

FILE=$1
OS_FILE_LOG_BLOCK_SIZE=512
LOG_HEADER_CREATOR=16
LOG_HEADER_CREATOR_END=$(($LOG_HEADER_CREATOR + 32))
LOG_ENCRYPTION=$(( 2 * $OS_FILE_LOG_BLOCK_SIZE))
OFFSET=$(($LOG_ENCRYPTION + $LOG_HEADER_CREATOR_END))
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