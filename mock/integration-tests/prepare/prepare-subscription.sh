#! /bin/bash

sudo dnf install -y subscription-manager

sudo subscription-manager register

sudo subscription-manager attach --pool 8a85f9815a1e73d7015a1ea519bc254a
