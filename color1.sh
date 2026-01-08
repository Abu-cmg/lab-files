#!/usr/bin/env bash

# Set text color + background
echo -e "\e[37;44m"   # white text on blue background

echo "This text is colored"
echo "So is this"
echo "Everything until reset"

# Reset to normal
echo -e "\e[0m"
