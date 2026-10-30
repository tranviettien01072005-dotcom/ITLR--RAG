#!/bin/sh
# Schema and catalog changes are explicit release jobs; restarting serves traffic only.
set -eu
exec node dist/server.js
