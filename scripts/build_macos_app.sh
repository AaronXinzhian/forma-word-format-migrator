#!/bin/zsh

set -euo pipefail

script_dir=${0:A:h}
project_root=${script_dir:h}
info_plist="$project_root/swift-app/Info.plist"
version=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$info_plist")
build_number=$(/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$info_plist")

python_version="3.14.6"
python_minor="3.14"
lxml_version="6.1.1"
python_pkg_hash="d3c9fff52214847e4fab03e9eaf53dd2a8e51e3534aa0b61f201b749f86bef28"
lxml_wheel_hash="19b7ab10b210b0b3ad7985d9ac4eb66ab09a90b20fe6e2f7ba55d01a234345d0"
python_pkg_url="https://www.python.org/ftp/python/${python_version}/python-${python_version}-macos11.pkg"
lxml_wheel_url="https://files.pythonhosted.org/packages/13/e2/2e325795566de01d0d7c3bb57d3c370616b2d07b01214e84eec5d3b10963/lxml-${lxml_version}-cp314-cp314-macosx_10_15_universal2.whl"

download_root="$project_root/build/downloads"
output_root="${FORMA_OUTPUT_DIR:-$project_root/../../outputs}"
python_pkg="$download_root/python-${python_version}-macos11.pkg"
lxml_wheel="$download_root/lxml-${lxml_version}-cp314-cp314-macosx_10_15_universal2.whl"
build_python="${FORMA_BUILD_PYTHON:-/usr/bin/python3}"
sign_identity="${MACOS_SIGNING_IDENTITY:--}"
notary_profile="${MACOS_NOTARY_PROFILE:-}"
require_release="${FORMA_REQUIRE_NOTARIZATION:-0}"
keep_build_root="${FORMA_KEEP_BUILD_ROOT:-0}"

mkdir -p "$project_root/build" "$download_root" "$output_root"
build_root=$(mktemp -d "$project_root/build/forma-fushi-${version}.XXXXXX")
build_succeeded=0
arm_dir="$build_root/arm64"
intel_dir="$build_root/x86_64"
release_root="$build_root/release/Forma 赋式"
app_dir="$release_root/Forma 赋式.app"
frameworks_dir="$app_dir/Contents/Frameworks"
resources_dir="$app_dir/Contents/Resources"
framework_root="$frameworks_dir/Python.framework"

function cleanup_build_root() {
  local exit_status=$?
  if [[ "$build_succeeded" == "1" && "$keep_build_root" != "1" ]]; then
    case "$build_root" in
      "$project_root/build/forma-fushi-${version}."*)
        find "$build_root" -depth -delete
        ;;
      *)
        print -u2 "拒绝清理无法确认的构建目录：$build_root"
        ;;
    esac
  elif [[ "$exit_status" != "0" ]]; then
    print -u2 "构建未完成，诊断文件保留在：$build_root"
  fi
  return "$exit_status"
}

trap cleanup_build_root EXIT

function download_verified() {
  local url="$1"
  local destination="$2"
  local expected_hash="$3"
  if [[ ! -f "$destination" ]]; then
    curl -fL --retry 3 -o "$destination" "$url"
  fi
  printf '%s  %s\n' "$expected_hash" "$destination" | shasum -a 256 -c -
}

function remove_build_tree() {
  local target="$1"
  case "$target" in
    "$framework_root"/*) ;;
    *)
      print -u2 "拒绝清理不属于本次 Python 构建目录的路径：$target"
      return 1
      ;;
  esac
  if [[ -e "$target" || -L "$target" ]]; then
    find "$target" -depth -delete
  fi
}

function is_signable_macho() {
  local description
  description=$(file -b "$1")
  [[ "$description" == *"Mach-O"* ]] && \
    [[ "$description" == *"executable"* || \
       "$description" == *"dynamically linked shared library"* || \
       "$description" == *"bundle"* ]]
}

function sign_item() {
  local item="$1"
  if [[ "$sign_identity" == "-" ]]; then
    codesign --force --sign - "$item"
  else
    codesign --force --options runtime --timestamp --sign "$sign_identity" "$item"
  fi
}

function source_fingerprint() {
  (
    cd "$project_root"
    {
      print -r -- "README.md"
      print -r -- "scripts/build_macos_app.sh"
      print -r -- "style_pack_manager.py"
      print -r -- "word_style_transfer.py"
      print -r -- "swift-app/Info.plist"
      print -r -- "swift-app/WordFormatLibraryApp.swift"
      print -r -- "build-assets/WordFormatIcon.icns"
      find tests -maxdepth 1 -type f \( \
        -name '*.py' -o -name '*.swift' \
      \) -print
      find tests/fixtures -maxdepth 1 -type f \( \
        -name '*.docx' -o -name '*.docm' -o \
        -name '*.dotx' -o -name '*.dotm' -o -name '*.png' \
      \) -print
    } | LC_ALL=C sort -u | while IFS= read -r source_path; do
      shasum -a 256 "$source_path"
    done
  )
}

source_manifest_start="$build_root/source-inputs-start.sha256"
source_fingerprint > "$source_manifest_start"

if [[ ! -x "$build_python" ]]; then
  print -u2 "找不到用于构建测试的 Python：$build_python"
  exit 1
fi
if ! "$build_python" -c 'import lxml' >/dev/null 2>&1; then
  print -u2 "构建测试环境缺少 lxml：$build_python"
  exit 1
fi
if [[ "$require_release" == "1" && ( "$sign_identity" == "-" || -z "$notary_profile" ) ]]; then
  print -u2 "正式发布要求同时设置 MACOS_SIGNING_IDENTITY 与 MACOS_NOTARY_PROFILE。"
  exit 1
fi
if [[ -n "$notary_profile" && "$sign_identity" == "-" ]]; then
  print -u2 "公证前必须设置 Developer ID Application 签名身份。"
  exit 1
fi

print "[1/8] 运行文档处理回归测试"
(
  cd "$project_root"
  "$build_python" -m unittest discover -s tests -p 'test_*.py' -v
)

mkdir -p \
  "$arm_dir" \
  "$intel_dir" \
  "$build_root/module-cache-deletion-tests" \
  "$build_root/module-cache-arm64" \
  "$build_root/module-cache-x86_64" \
  "$app_dir/Contents/MacOS" \
  "$frameworks_dir" \
  "$resources_dir/runtime/bin" \
  "$release_root/第三方许可"

print "[2/8] 编译并运行 Mac 删除安全测试"
xcrun swiftc \
  -D WORD_FORMAT_LIBRARY_TESTING \
  -parse-as-library \
  -module-cache-path "$build_root/module-cache-deletion-tests" \
  "$project_root/swift-app/WordFormatLibraryApp.swift" \
  "$project_root/tests/PackDeletionPolicyTests.swift" \
  -o "$build_root/PackDeletionPolicyTests"
"$build_root/PackDeletionPolicyTests"

print "[3/8] 编译 Universal Mac 应用"
xcrun swiftc \
  -O \
  -parse-as-library \
  -target arm64-apple-macos13.0 \
  -file-prefix-map "$project_root=." \
  -debug-prefix-map "$project_root=." \
  -module-cache-path "$build_root/module-cache-arm64" \
  "$project_root/swift-app/WordFormatLibraryApp.swift" \
  -o "$arm_dir/WordFormatLibrary"

xcrun swiftc \
  -O \
  -parse-as-library \
  -target x86_64-apple-macos13.0 \
  -file-prefix-map "$project_root=." \
  -debug-prefix-map "$project_root=." \
  -module-cache-path "$build_root/module-cache-x86_64" \
  "$project_root/swift-app/WordFormatLibraryApp.swift" \
  -o "$intel_dir/WordFormatLibrary"

lipo -create \
  "$arm_dir/WordFormatLibrary" \
  "$intel_dir/WordFormatLibrary" \
  -output "$app_dir/Contents/MacOS/WordFormatLibrary"
lipo "$app_dir/Contents/MacOS/WordFormatLibrary" -verify_arch arm64 x86_64

install -m 644 "$info_plist" "$app_dir/Contents/Info.plist"
install -m 644 "$project_root/build-assets/WordFormatIcon.icns" \
  "$resources_dir/WordFormatIcon.icns"
install -m 644 "$project_root/style_pack_manager.py" \
  "$resources_dir/style_pack_manager.py"
install -m 644 "$project_root/word_style_transfer.py" \
  "$resources_dir/word_style_transfer.py"
install -m 644 "$project_root/README.md" "$release_root/使用说明.md"

print "[4/8] 组装固定版本的 Universal Python 与 lxml"
download_verified "$python_pkg_url" "$python_pkg" "$python_pkg_hash"
download_verified "$lxml_wheel_url" "$lxml_wheel" "$lxml_wheel_hash"

python_pkg_expanded="$build_root/python-pkg"
pkgutil --expand-full "$python_pkg" "$python_pkg_expanded"
python_payload="$python_pkg_expanded/Python_Framework.pkg/Payload"
python_version_root="$framework_root/Versions/$python_minor"
if [[ ! -d "$python_payload/Versions/$python_minor" ]]; then
  print -u2 "Python 安装包结构与预期不符：缺少 Versions/$python_minor。"
  exit 1
fi
ditto "$python_payload" "$framework_root"
unzip -q "$lxml_wheel" -d "$python_version_root/lib/python${python_minor}/site-packages"

# 文档引擎不使用测试库、IDLE、Tk 或安装器。移除它们可以缩小应用，也减少
# 正式签名时不必要的嵌套框架；所有目标均严格限制在本次临时构建目录内。
remove_build_tree "$python_version_root/lib/python${python_minor}/test"
remove_build_tree "$python_version_root/lib/python${python_minor}/idlelib"
remove_build_tree "$python_version_root/lib/python${python_minor}/tkinter"
remove_build_tree "$python_version_root/lib/python${python_minor}/turtledemo"
remove_build_tree "$python_version_root/lib/python${python_minor}/ensurepip"
remove_build_tree "$python_version_root/Frameworks/Tk.framework"
remove_build_tree "$python_version_root/Frameworks/Tcl.framework"
find "$python_version_root/lib/python${python_minor}/lib-dynload" \
  -maxdepth 1 -name '_tkinter*.so' -delete

original_python_link="/Library/Frameworks/Python.framework/Versions/$python_minor/Python"
embedded_python_link="@rpath/Python.framework/Versions/$python_minor/Python"
while IFS= read -r -d '' candidate; do
  if is_signable_macho "$candidate" && \
     otool -L "$candidate" 2>/dev/null | grep -Fq "$original_python_link"; then
    install_name_tool -change "$original_python_link" "$embedded_python_link" "$candidate"
  fi
done < <(find "$framework_root" -type f -print0)

python_library="$python_version_root/Python"
python_cli="$python_version_root/bin/python${python_minor}"
python_app="$python_version_root/Resources/Python.app/Contents/MacOS/Python"
install_name_tool -id "$embedded_python_link" "$python_library"
install_name_tool -add_rpath '@executable_path/../../../..' "$python_cli"
install_name_tool -add_rpath '@executable_path/../../../../../../..' "$python_app"
ln -s "../../../Frameworks/Python.framework/Versions/$python_minor/bin/python3" \
  "$resources_dir/runtime/bin/python3"

install -m 644 "$python_version_root/lib/python${python_minor}/LICENSE.txt" \
  "$release_root/第三方许可/Python-LICENSE.txt"
mkdir -p "$release_root/第三方许可/lxml"
ditto \
  "$python_version_root/lib/python${python_minor}/site-packages/lxml-${lxml_version}.dist-info/licenses" \
  "$release_root/第三方许可/lxml"

lipo "$python_library" -verify_arch arm64 x86_64
lipo "$python_cli" -verify_arch arm64 x86_64
lxml_binary=$(find \
  "$python_version_root/lib/python${python_minor}/site-packages/lxml" \
  -name 'etree*.so' -print -quit)
if [[ -z "$lxml_binary" ]]; then
  print -u2 "内置 lxml 不完整：找不到 etree 扩展。"
  exit 1
fi
lipo "$lxml_binary" -verify_arch arm64 x86_64

print "[5/8] 对嵌套运行环境和应用逐层签名"
xattr -cr "$app_dir"
while IFS= read -r -d '' candidate; do
  if is_signable_macho "$candidate"; then
    sign_item "$candidate" >/dev/null
  fi
done < <(find "$framework_root" -type f -print0)
sign_item "$python_version_root/Resources/Python.app" >/dev/null
sign_item "$framework_root" >/dev/null
sign_item "$app_dir/Contents/MacOS/WordFormatLibrary" >/dev/null
sign_item "$app_dir" >/dev/null
codesign --verify --deep --strict --verbose=2 "$app_dir"

print "[6/8] 验证内置运行环境与真实格式迁移"
bundled_python="$resources_dir/runtime/bin/python3"
"$bundled_python" -B -E -s -c \
  "import lxml, platform; assert lxml.__version__ == '$lxml_version'; print(platform.machine(), lxml.__version__)"
if /usr/bin/arch -x86_64 /usr/bin/true >/dev/null 2>&1; then
  /usr/bin/arch -x86_64 "$bundled_python" -B -E -s -c \
    "import lxml, platform; assert platform.machine() == 'x86_64'; assert lxml.__version__ == '$lxml_version'"
else
  print "提示：本机没有 Rosetta，已完成 x86_64 架构检查，但未运行 Intel 进程测试。"
fi

smoke_root=$(mktemp -d "$build_root/runtime-smoke.XXXXXX")
smoke_pack="$smoke_root/smoke.wfstyle"
smoke_output="$smoke_root/result.docx"
"$bundled_python" -B -E -s "$resources_dir/style_pack_manager.py" create-pack \
  --source "$project_root/tests/fixtures/source.docx" \
  --out "$smoke_pack" \
  --name "构建验证" > "$smoke_root/create.json"
"$bundled_python" -B -E -s "$resources_dir/style_pack_manager.py" apply-pack \
  --pack "$smoke_pack" \
  --target "$project_root/tests/fixtures/target.docx" \
  --out "$smoke_output" \
  --force > "$smoke_root/apply.json"
"$bundled_python" -B -E -s -c \
  'import json, pathlib, sys; data=json.loads(pathlib.Path(sys.argv[1]).read_text()); assert data["ok"] is True; assert pathlib.Path(data["output"]).is_file()' \
  "$smoke_root/apply.json"
if find "$resources_dir" -name '*.pyc' -print -quit | grep -q .; then
  print -u2 "内置运行测试向应用资源写入了 Python 缓存，已停止发布。"
  exit 1
fi
# Smoke runs after signing, so verify again to catch accidental cache/log writes
# inside the sealed application before an archive can be published.
codesign --verify --deep --strict --verbose=2 "$app_dir"

if [[ -n "$notary_profile" ]]; then
  print "[7/8] 提交 Apple 公证并附加票据"
  notary_archive="$build_root/Forma-Fushi-notary.zip"
  ditto -c -k --sequesterRsrc --keepParent "$app_dir" "$notary_archive"
  xcrun notarytool submit "$notary_archive" \
    --keychain-profile "$notary_profile" \
    --wait
  xcrun stapler staple "$app_dir"
  xcrun stapler validate "$app_dir"
  spctl --assess --type execute --verbose=2 "$app_dir"
else
  print "[7/8] 未设置公证凭据；本次生成可本机验证的签名构建。"
fi

print "[8/8] 生成发布包、校验和与构建清单"
source_manifest_end="$build_root/source-inputs-end.sha256"
source_fingerprint > "$source_manifest_end"
if ! cmp -s "$source_manifest_start" "$source_manifest_end"; then
  print -u2 "构建期间源码或测试输入发生变化，已停止生成可能混合版本的发布包："
  diff -u "$source_manifest_start" "$source_manifest_end" >&2 || true
  exit 1
fi

if [[ -n "$notary_profile" ]]; then
  archive_suffix=""
  build_channel="Developer ID 签名并经 Apple 公证"
elif [[ "$sign_identity" == "-" ]]; then
  archive_suffix="-local-adhoc"
  build_channel="本机测试构建（ad-hoc 签名，未公证）"
else
  archive_suffix="-local-unnotarized"
  build_channel="本机测试构建（Developer ID 签名，未公证）"
fi

manifest="$release_root/构建信息.txt"
/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$info_plist" | \
  awk -v version="$version" -v build="$build_number" \
      -v python="$python_version" -v lxml="$lxml_version" -v channel="$build_channel" \
      '{print "Forma 赋式 " version " (" build ")\n构建类型: " channel "\nBundle ID: " $0 "\nPython: " python " universal2\nlxml: " lxml " universal2"}' \
      > "$manifest"

archive_name="Forma赋式-Mac-v${version}${archive_suffix}.zip"
temporary_archive="$build_root/$archive_name"
final_archive="$output_root/$archive_name"
ditto -c -k --sequesterRsrc --keepParent "$release_root" "$temporary_archive"
unzip -tq "$temporary_archive" >/dev/null
archive_check_root=$(mktemp -d "$build_root/archive-check.XXXXXX")
ditto -x -k "$temporary_archive" "$archive_check_root"
archive_app="$archive_check_root/Forma 赋式/Forma 赋式.app"
codesign --verify --deep --strict --verbose=2 "$archive_app"
"$archive_app/Contents/Resources/runtime/bin/python3" -B -E -s -c \
  "import lxml; assert lxml.__version__ == '$lxml_version'"
if strings "$archive_app/Contents/MacOS/WordFormatLibrary" | \
   grep -Fq "$project_root"; then
  print -u2 "发布二进制泄露了本机构建路径，已停止输出。"
  exit 1
fi

# Only replace an existing artifact after the new archive, extracted app,
# signature and embedded runtime have all passed verification.
mv -f "$temporary_archive" "$final_archive"
(
  cd "$output_root"
  shasum -a 256 "$archive_name" > "$archive_name.sha256"
)

print "Archive: $final_archive"
print "SHA-256: $(awk '{print $1}' "$final_archive.sha256")"
if [[ -z "$notary_profile" ]]; then
  print "发布提示：当前机器没有使用 Apple 公证凭据，外部分发前请设置签名身份和公证配置重新构建。"
fi
build_succeeded=1
