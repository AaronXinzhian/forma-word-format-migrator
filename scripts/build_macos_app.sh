#!/bin/zsh

set -euo pipefail

script_dir=${0:A:h}
project_root=${script_dir:h}
info_plist="$project_root/swift-app/Info.plist"
version=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$info_plist")

mkdir -p "$project_root/build"
build_root=$(mktemp -d "$project_root/build/forma-fushi-${version}.XXXXXX")
arm_dir="$build_root/arm64"
intel_dir="$build_root/x86_64"
release_root="$build_root/release/Forma 赋式"
app_dir="$release_root/Forma 赋式.app"

mkdir -p \
  "$arm_dir" \
  "$intel_dir" \
  "$build_root/module-cache-arm64" \
  "$build_root/module-cache-x86_64" \
  "$app_dir/Contents/MacOS" \
  "$app_dir/Contents/Resources"

xcrun swiftc \
  -O \
  -parse-as-library \
  -target arm64-apple-macos13.0 \
  -module-cache-path "$build_root/module-cache-arm64" \
  "$project_root/swift-app/WordFormatLibraryApp.swift" \
  -o "$arm_dir/WordFormatLibrary"

xcrun swiftc \
  -O \
  -parse-as-library \
  -target x86_64-apple-macos13.0 \
  -module-cache-path "$build_root/module-cache-x86_64" \
  "$project_root/swift-app/WordFormatLibraryApp.swift" \
  -o "$intel_dir/WordFormatLibrary"

lipo -create \
  "$arm_dir/WordFormatLibrary" \
  "$intel_dir/WordFormatLibrary" \
  -output "$app_dir/Contents/MacOS/WordFormatLibrary"

install -m 644 "$info_plist" "$app_dir/Contents/Info.plist"
install -m 644 "$project_root/build-assets/WordFormatIcon.icns" \
  "$app_dir/Contents/Resources/WordFormatIcon.icns"
install -m 644 "$project_root/style_pack_manager.py" \
  "$app_dir/Contents/Resources/style_pack_manager.py"
install -m 644 "$project_root/word_style_transfer.py" \
  "$app_dir/Contents/Resources/word_style_transfer.py"
install -m 644 "$project_root/README.md" "$release_root/使用说明.md"

xattr -cr "$app_dir"
codesign --force --deep --sign - "$app_dir"
codesign --verify --deep --strict --verbose=2 "$app_dir"

archive="$build_root/Forma赋式-Mac-v${version}.zip"
ditto -c -k --sequesterRsrc --keepParent "$release_root" "$archive"

print "App: $app_dir"
print "Archive: $archive"
