#!/bin/bash

# Network menu script for polybar

# Check if rofi is installed
if ! command -v rofi >/dev/null 2>&1; then
    notify-send "Error" "Please install rofi first"
    exit 1
fi

# Check if nmcli is installed
if ! command -v nmcli >/dev/null 2>&1; then
    notify-send "Error" "Please install NetworkManager first"
    exit 1
fi

# Toggle wireless connection if connection name is passed as argument
if [[ $# -eq 1 ]]; then
    if [[ "$1" == "toggle" ]]; then
        wifi_status=$(nmcli radio wifi)
        if [[ "$wifi_status" == "enabled" ]]; then
            nmcli radio wifi off
            notify-send "WiFi" "Disabled"
        else
            nmcli radio wifi on
            notify-send "WiFi" "Enabled"
        fi
        exit 0
    fi
    
    if nmcli con show | grep -q "$1"; then
        nmcli con up "$1"
    else
        nmcli dev wifi connect "$1"
    fi
    exit 0
fi

# Get wireless status
function wireless_status() {
    wifi_status=$(nmcli radio wifi)
    if [[ "$wifi_status" == "enabled" ]]; then
        echo "WiFi: On"
    else
        echo "WiFi: Off"
    fi
}

# List available WiFi networks
function list_networks() {
    nmcli --fields IN-USE,SIGNAL,SECURITY,SSID dev wifi list | tail -n +2 | sed 's/^--//g' | sed 's/^ *//g'
}

# Generate menu options
function gen_options() {
    echo "$(wireless_status)"
    echo "󰖩 Toggle WiFi"
    echo "󰑓 Rescan Networks"
    echo "$(list_networks)"
}

# Show the menu with rofi
choice=$(gen_options | rofi -dmenu -i -p "Network" -theme-str 'window {width: 30%;} listview {lines: 10;}')

# Handle selection
if [[ "$choice" == "󰖩 Toggle WiFi" ]]; then
    $0 toggle
elif [[ "$choice" == "󰑓 Rescan Networks" ]]; then
    nmcli dev wifi rescan
    notify-send "WiFi" "Rescanning networks..."
elif [[ "$choice" == *"WiFi: "* ]]; then
    $0 toggle
else
    ssid=$(echo "$choice" | awk '{$1=$2=$3=""; print $0}' | sed 's/^ *//g')
    if [[ -n "$ssid" ]]; then
        $0 "$ssid" 
    fi
fi
