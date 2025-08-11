#!/bin/bash

SCRIPTPATH="$(
    cd "$(dirname "$0")" || exit >/dev/null 2>&1
    pwd -P
)"

# shellcheck disable=SC1091
source "$SCRIPTPATH/env.sh"

gcloud artifacts repositories create "${REPOSITORY_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Repository for Kubernetes webhook images"