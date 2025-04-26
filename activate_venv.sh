#!/usr/bin/env bash

CUR_FILE="${BASH_SOURCE[${#BASH_SOURCE[@]} - 1]}"

if [ -z "$PS1" ] ; then
    echo "This script must be sourced. Use \"source ${CUR_FILE}\" instead."
    exit
fi

SCRIPT_PATH=$(dirname $(realpath $CUR_FILE))
VENV_SCRIPT=${SCRIPT_PATH}/pyvenv.py
VENV_PATH=${VIRTUAL_ENV:-${SCRIPT_PATH}/.venv}
ACTIVATE_SH=${VENV_PATH}/bin/activate

python3 $VENV_SCRIPT --min-version 3.6 -r requirements.txt --path $VENV_PATH && source $ACTIVATE_SH