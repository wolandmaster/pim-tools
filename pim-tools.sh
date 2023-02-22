#!/bin/bash -e
# Copyright (c) 2022-2023 Sandor Balazsi (sandor.balazsi@gmail.com)

TOOL="$1"
if [[ -z "${TOOL}" ]]; then
  SCRIPT=$(basename $0)
  echo -e "usage: ./${SCRIPT} <tool>\n" >&2
  echo -e "available tools:" >&2
  find tools -mindepth 1 -maxdepth 1 -type f -executable -printf '- %P\n' >&2
  exit 1
fi
shift

docker build --tag pim-tools:latest .
xhost +local:
docker run \
  --tty --interactive --rm \
  --volume "$(pwd)/tools:/workdir" \
  --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
  --env DISPLAY="${DISPLAY}" \
  --env TZ="$(cat /etc/timezone)" \
  pim-tools:latest "${TOOL}" "$@"
