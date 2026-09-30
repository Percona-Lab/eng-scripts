DIR="$( dirname "$0" )"

. ${DIR}/innodb_common.sh

FLAGS=$1

if [ $# -ne 1 ]; then
    echo "Usage: $0 <number>"
    exit 1
fi

# The argument is a valid number, proceed with your script logic
FLAGS=$1

echo "Input space flags is " $FLAGS

decode_flags $FLAGS
print_decoded_flags
