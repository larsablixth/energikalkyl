#!/bin/bash
read -s -p "Klistra in din ENTSO-E API-nyckel: " key
echo
echo "$key" > ~/projects/elpriser/.entsoe_key
chmod 600 ~/projects/elpriser/.entsoe_key
echo "Nyckel sparad i .entsoe_key"
