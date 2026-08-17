#!/bin/zsh

set -euo pipefail

script_dir=${0:A:h}
project_root=${script_dir:h}
info_plist="$project_root/swift-app/Info.plist"
version=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$info_plist")

# 源码已按 Models / Bridge / Theme / Views 分目录，这里按目录收集而不是列单个文件。
sources=("$project_root"/swift-app/**/*.swift)
if (( ${#sources} == 0 )); then
  print -u2 "swift-app 下没有找到任何 .swift 源文件。"
  exit 1
fi

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
  "${sources[@]}" \
  -o "$arm_dir/WordFormatLibrary"

xcrun swiftc \
  -O \
  -parse-as-library \
  -target x86_64-apple-macos13.0 \
  -module-cache-path "$build_root/module-cache-x86_64" \
  "${sources[@]}" \
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
