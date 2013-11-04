#!/bin/bash
kill $(cat twistd.pid)
venv/bin/twistd -y run.py
