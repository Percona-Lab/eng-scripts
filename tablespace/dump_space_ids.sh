#!/bin/bash
# Dump space_ids of .ibds, undo*, ibdata* and ibtmp* from a dir
# Usage: ./dump_space_ids /path/to/datadir/
DIR=$1
dump_space_id_low() {
	DIR=$1
	PATTERN=$2
	format=`find $DIR -type f -name "$PATTERN" -exec echo "{}" \;`
	for i in $format
	do
		SPACE_ID=$(od -An -j38 -D -N4 --endian=big $i)
		echo "file name $i : space_id $SPACE_ID"
	done
}

dump_space_ids() {
	DIR=$1
	dump_space_id_low $DIR "*.ibd"
	dump_space_id_low $DIR "undo*"
	dump_space_id_low $DIR "*ibtmp*"
	dump_space_id_low $DIR "*.ibu"
	dump_space_id_low $DIR "ibdata*"
}

dump_space_ids $DIR
