### Define InnoDB Common macros
###
### Please Add new entries here as below:
### Link to GitHub (Use Tag so if the line moves we are still good)
### Description of the macro
### Macro


# Redo Log

# https://github.com/mysql/mysql-server/blob/mysql-8.2.0/storage/innobase/include/os0file.h#L195
# Size of the redo log block.
OS_FILE_LOG_BLOCK_SIZE=512

# https://github.com/mysql/mysql-server/blob/mysql-8.2.0/storage/innobase/include/log0constants.h#L172
# Size of log file's header (2048).
LOG_FILE_HDR_SIZE=$((4 * $OS_FILE_LOG_BLOCK_SIZE))


# https://github.com/mysql/mysql-server/blob/mysql-8.2.0/storage/innobase/include/log0constants.h#L188
#  LSN of the start of data in this log file (with format version 1 and 2).
LOG_HEADER_START_LSN=8
