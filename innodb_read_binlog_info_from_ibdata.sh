#!/bin/bash
# Dump information from binlog from ibdata
DIR="$( dirname "$0" )"

. ${DIR}/innodb_common.sh

FILE=$1


read_binlog_info_from_ibd() {
  if [[ ${SPACE} -ne 0 ]];
  then
    echo "Error: Binlog info is stored in ibdata1 - Space ID: 0"
    echo "File ${FILE} has Space ID: $((2#$SPACE))"
    exit 1
  fi


  TRX_SYS_MYSQL_LOG_MAGIC_N=873422344
  TRX_SYS=$((5* ${UNCOMPRESSED_PAGE_SIZE} + 38 + $((UNCOMPRESSED_PAGE_SIZE - 1000))))
  TRX_SYS_MYSQL_LOG_MAGIC_N_FLD=$(xxd -b -s $((${TRX_SYS})) -l4 $FILE |  awk '{print $2 $3 $4 $5}')
  TRX_SYS_MYSQL_LOG_MAGIC_N_FLD_D=$((2#$TRX_SYS_MYSQL_LOG_MAGIC_N_FLD))


  if [[ ${TRX_SYS_MYSQL_LOG_MAGIC_N_FLD_D} -ne ${TRX_SYS_MYSQL_LOG_MAGIC_N} ]];
  then
    echo "Binlog is not stored in ${FILE}"
    exit 0
  fi

  TRX_SYS_MYSQL_LOG_NAME_LEN=512
  TRX_SYS_MYSQL_LOG_NAME=12

  BINLOG_NAME=$(xxd -p -s $((${TRX_SYS} + ${TRX_SYS_MYSQL_LOG_NAME})) -l${TRX_SYS_MYSQL_LOG_NAME_LEN} $FILE | xxd -r -p |  tr -d '\0')

  TRX_SYS_MYSQL_LOG_OFFSET_HIGH=4
  TRX_SYS_MYSQL_LOG_OFFSET_LOW=8

  HIGH=$(xxd -b -s $((${TRX_SYS} + ${TRX_SYS_MYSQL_LOG_OFFSET_HIGH})) -l4 $FILE |  awk '{print $2 $3 $4 $5}')
  HIGH_D=$((2#$HIGH))
  LOW=$(xxd -b -s $((${TRX_SYS} + ${TRX_SYS_MYSQL_LOG_OFFSET_LOW})) -l4 $FILE |  awk '{print $2 $3 $4 $5}')
  LOW_D=$((2#$LOW))
  OFFSET=$HIGH_D
  ((OFFSET <<= 32))
  ((OFFSET|=LOW_D))

  echo "Binlog Name and Position : ${BINLOG_NAME} ${OFFSET}"
  exit 0
}

decode_page0_flags $FILE
read_binlog_info_from_ibd

