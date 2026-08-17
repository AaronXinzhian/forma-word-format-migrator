#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CSPROJ="$PROJECT_ROOT/windows-app/FormaFushi.Windows/FormaFushi.Windows.csproj"

# 版本号只在 csproj 里维护一处，和 macOS 脚本读 Info.plist 的做法对齐。
VERSION="$(sed -n 's:.*<Version>\(.*\)</Version>.*:\1:p' "$CSPROJ" | head -n 1)"
if [ -z "$VERSION" ]; then
  echo "无法从 $CSPROJ 读取 <Version>，请检查工程文件。" >&2
  exit 1
fi

PYTHON_VERSION="3.14.6"
LXML_VERSION="6.1.1"
DOTNET_VERSION="10.0.302"
DOTNET_HASH="b2286dec9177e8b5543ff2fe95c84db358b87ec2a36a0d34a29033d70279940fd1134af56c4299648f8950db2d6ce35237698cf2818d9abc670c2c1664c92ac0"
PYTHON_HASH="df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c"
LXML_HASH="b2d444f2e66624d68e9c6b211e28a76e22fff5fcabcfff4deac18b529b7d4137"

BUILD_ROOT="$PROJECT_ROOT/build/windows"
DOWNLOAD_ROOT="$PROJECT_ROOT/build/downloads"
TOOLCHAIN_ROOT="$PROJECT_ROOT/build/toolchains/dotnet"
DOTNET_ARCHIVE="$PROJECT_ROOT/build/toolchains/dotnet-sdk.tar.gz"
PUBLISH_ROOT="$BUILD_ROOT/publish"
PACKAGE_NAME="Forma赋式-Windows-x64-v${VERSION}"
PACKAGE_ROOT="$BUILD_ROOT/portable/$PACKAGE_NAME"
OUTPUT_ROOT="${FORMA_OUTPUT_DIR:-$PROJECT_ROOT/../../outputs}"
ZIP_PATH="$OUTPUT_ROOT/$PACKAGE_NAME.zip"

mkdir -p "$DOWNLOAD_ROOT" "$PROJECT_ROOT/build/toolchains" "$OUTPUT_ROOT"

if [ ! -x "$TOOLCHAIN_ROOT/dotnet" ]; then
  mkdir -p "$TOOLCHAIN_ROOT"
  curl -fL --retry 3 -o "$DOTNET_ARCHIVE" \
    "https://builds.dotnet.microsoft.com/dotnet/Sdk/${DOTNET_VERSION}/dotnet-sdk-${DOTNET_VERSION}-osx-arm64.tar.gz"
  printf '%s  %s\n' "$DOTNET_HASH" "$DOTNET_ARCHIVE" | shasum -a 512 -c -
  tar -xzf "$DOTNET_ARCHIVE" -C "$TOOLCHAIN_ROOT"
fi
INSTALLED_DOTNET_VERSION="$("$TOOLCHAIN_ROOT/dotnet" --version)"
if [ "$INSTALLED_DOTNET_VERSION" != "$DOTNET_VERSION" ]; then
  echo "构建工具版本不匹配：需要 .NET SDK $DOTNET_VERSION，当前为 $INSTALLED_DOTNET_VERSION。" >&2
  echo "请移走 build/toolchains/dotnet 后重新运行。" >&2
  exit 1
fi

PYTHON_ARCHIVE="$DOWNLOAD_ROOT/python-${PYTHON_VERSION}-embed-amd64.zip"
if [ ! -f "$PYTHON_ARCHIVE" ]; then
  curl -fL --retry 3 -o "$PYTHON_ARCHIVE" \
    "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip"
fi
printf '%s  %s\n' "$PYTHON_HASH" "$PYTHON_ARCHIVE" | shasum -a 256 -c -

LXML_WHEEL="$DOWNLOAD_ROOT/lxml-${LXML_VERSION}-cp314-cp314-win_amd64.whl"
if [ ! -f "$LXML_WHEEL" ]; then
  curl -fL --retry 3 -o "$LXML_WHEEL" \
    "https://files.pythonhosted.org/packages/b8/ce/3cf9a827342269f54d405a6202397de63f07c69cbd6ce7d183a3f0cba1e9/lxml-${LXML_VERSION}-cp314-cp314-win_amd64.whl"
fi
printf '%s  %s\n' "$LXML_HASH" "$LXML_WHEEL" | shasum -a 256 -c -

rm -rf "$PUBLISH_ROOT" "$PACKAGE_ROOT"
mkdir -p "$PUBLISH_ROOT" "$PACKAGE_ROOT/runtime/Lib/site-packages" "$PACKAGE_ROOT/resources" "$PACKAGE_ROOT/第三方许可"

"$TOOLCHAIN_ROOT/dotnet" publish \
  "$PROJECT_ROOT/windows-app/FormaFushi.Windows/FormaFushi.Windows.csproj" \
  --configuration Release \
  --runtime win-x64 \
  --self-contained true \
  --output "$PUBLISH_ROOT"

for required_file in FormaFushi.exe FormaFushi.dll FormaFushi.runtimeconfig.json hostfxr.dll coreclr.dll System.Windows.Forms.dll; do
  if [ ! -f "$PUBLISH_ROOT/$required_file" ]; then
    echo "Windows 自包含运行环境不完整：缺少 $required_file。" >&2
    exit 1
  fi
done
if ! grep -q '"includedFrameworks"' "$PUBLISH_ROOT/FormaFushi.runtimeconfig.json"; then
  echo "Windows 发布结果不是自包含部署，已停止打包。" >&2
  exit 1
fi

cp -R "$PUBLISH_ROOT/." "$PACKAGE_ROOT/"
unzip -q "$PYTHON_ARCHIVE" -d "$PACKAGE_ROOT/runtime"
cp "$PROJECT_ROOT/windows-app/runtime/python314._pth" "$PACKAGE_ROOT/runtime/python314._pth"
unzip -q "$LXML_WHEEL" -d "$PACKAGE_ROOT/runtime/Lib/site-packages"
cp "$PROJECT_ROOT/style_pack_manager.py" "$PACKAGE_ROOT/resources/style_pack_manager.py"
cp "$PROJECT_ROOT/word_style_transfer.py" "$PACKAGE_ROOT/resources/word_style_transfer.py"
cp "$PROJECT_ROOT/windows-app/README-Windows.md" "$PACKAGE_ROOT/使用说明.md"

if [ -f "$PACKAGE_ROOT/runtime/LICENSE.txt" ]; then
  cp "$PACKAGE_ROOT/runtime/LICENSE.txt" "$PACKAGE_ROOT/第三方许可/Python-LICENSE.txt"
fi
if [ -f "$PACKAGE_ROOT/runtime/Lib/site-packages/lxml-${LXML_VERSION}.dist-info/licenses/LICENSES.txt" ]; then
  cp "$PACKAGE_ROOT/runtime/Lib/site-packages/lxml-${LXML_VERSION}.dist-info/licenses/LICENSES.txt" "$PACKAGE_ROOT/第三方许可/lxml-LICENSES.txt"
fi
if [ -f "$PACKAGE_ROOT/runtime/Lib/site-packages/lxml-${LXML_VERSION}.dist-info/licenses/LICENSE.txt" ]; then
  cp "$PACKAGE_ROOT/runtime/Lib/site-packages/lxml-${LXML_VERSION}.dist-info/licenses/LICENSE.txt" "$PACKAGE_ROOT/第三方许可/lxml-LICENSE.txt"
fi
if [ -f "$TOOLCHAIN_ROOT/ThirdPartyNotices.txt" ]; then
  cp "$TOOLCHAIN_ROOT/ThirdPartyNotices.txt" "$PACKAGE_ROOT/第三方许可/dotnet-ThirdPartyNotices.txt"
fi
if [ -f "$TOOLCHAIN_ROOT/LICENSE.txt" ]; then
  cp "$TOOLCHAIN_ROOT/LICENSE.txt" "$PACKAGE_ROOT/第三方许可/dotnet-LICENSE.txt"
fi

find "$PACKAGE_ROOT" -name '.DS_Store' -delete
rm -f "$ZIP_PATH" "$ZIP_PATH.sha256"
(
  cd "$(dirname "$PACKAGE_ROOT")"
  COPYFILE_DISABLE=1 /usr/bin/bsdtar -a -cf "$ZIP_PATH" "$PACKAGE_NAME"
)
(
  cd "$OUTPUT_ROOT"
  shasum -a 256 "$PACKAGE_NAME.zip" > "$PACKAGE_NAME.zip.sha256"
)

echo "Windows 便携包：$ZIP_PATH"
echo "SHA-256：$(awk '{print $1}' "$ZIP_PATH.sha256")"
