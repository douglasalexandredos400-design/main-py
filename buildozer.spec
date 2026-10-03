[app]

title = JARVIS
package.name = jarvis
package.domain = org.jarvis

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,json,txt,wav,mp3

version = 4.2

requirements = python3,kivy,requests

orientation = portrait

fullscreen = 0

android.api = 35
android.minapi = 23
android.ndk = 27c
android.archs = arm64-v8a

android.permissions = INTERNET,ACCESS_NETWORK_STATE

# Arquivo principal
entrypoint = main.py

[buildozer]

log_level = 2
warn_on_root = 1
