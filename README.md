<div align="center">

<img src="assets/logo.png" alt="Forma 赋式 logo" width="200">

# Forma 赋式 — 智能文档格式引擎

**简体中文**

> 一份范本，万卷同式。

</div>

> 格式是一套可复用的系统，不是一份文档的私有属性。把它从范本里抽出来，它就能套用到任何一份文档上。

Forma 赋式把一个 Word 文档的样式、多级标题编号、表格、主题和页面设置抽取成可复用的**格式方案**（`.wfstyle`），保存在本机格式库里，之后一键套用到其他 Word 文档，不必反复翻找当初那份范本。

它只提取格式，不保存正文——这条边界不是配置项，是设计约束，见[隐私边界](#隐私边界)。

Mac 与 Windows 双端提供原生客户端（SwiftUI / WinForms）：**操作流程、信息架构、按钮位置与全部界面文案完全一致，视觉上各自保留平台惯例**。文案由 [`shared/ui-strings.json`](shared/ui-strings.json) 单一来源生成，CI 校验，不靠人工对齐。

## 可用版本

| 平台 | 要求 | 运行时 |
|------|------|--------|
| **Mac** | macOS 13+，Apple Silicon 与 Intel 通用 | 使用系统 Python 3 与 `lxml`。若提示缺少文档解析组件，先 `xcode-select --install`，仍有提示再 `/usr/bin/python3 -m pip install --user lxml` |
| **Windows** | Windows 10 / 11 x64（ARM64 走系统 x64 兼容层） | 便携包已内置 .NET、Python 与 `lxml`，无需装开发环境。请**完整解压** ZIP 后再运行 `FormaFushi.exe` |

## 三步使用

| 步骤 | 做什么 | 结果 |
|------|--------|------|
| **1. 导入格式源** | 选一个 `.docx` / `.docm` / `.dotx` / `.dotm` 作为范本 | 程序分析出其中**实际使用过**的格式，存入格式库 |
| **2. 查看已用格式** | 确认样式、编号、页面设置 | 只列真正用过的，未使用样式不干扰选择 |
| **3. 应用到文档** | 选目标 `.docx` / `.docm`，指定保存位置 | 生成新文件，原文件不受影响 |

「我的格式库」是一条**常驻侧边栏**，三步中始终可见——随时换用另一套格式，不必退回第一步。格式源导入后可以移动或删除，已保存的格式方案照常可用。

每套格式右侧有独立删除按钮。确认后只把对应的 `.wfstyle` 移到 macOS 废纸篓或 Windows 回收站，不碰原范本、目标文件和已生成的文档；误删可恢复。

## 六个设计要点

1. **只呈现实际用过的格式，不是样式列表的全量倾倒。** Word 文档里定义了几十上百个样式，绝大多数从未使用。程序只列出真正出现在正文里的段落样式、字符样式和表格样式，并标注使用次数。为保证 Word 的继承关系、主题与编号仍然有效，内部会保留必要的格式依赖，但不会把它们混进用户要选择的列表。

2. **标题四、五可以从前三层推导，但推导有前提。** 只有当范本**实际、连续**使用了标题一至三、且没有实际使用标题四五时，才会补全。仅仅"定义过但没用过"的标题四五被视为无效默认值，不参与推导。补全结果单独标记为「智能补全」、使用次数为 0，不冒充范本真实用过的格式——这是诚实性问题，不是显示细节。

3. **手工格式不是样式，不会被伪造成样式。** 范本里手工加粗、改字号的地方，程序会提示数量，但不会把每一处手工改动保存成独立样式。表格上手工画的边框底纹同理——想复用这套表格外观，请先在 Word 里存成表格样式。程序不会凭外观猜测语义。

4. **编号只在能可靠判断时才清理。** 目标标题开头已有手工序号（「第三章」「3.1」）时，只有在标题级别、数字分量、父子路径和预计计数**全部一致**时才清理这段前缀，再交给自动编号。正文里的数字、版本号、日期以及无法可靠判断的前缀一律不动。编号文字含「章、节、款」等无法推导的语义单位时，不擅自编造。

5. **范本没有表格样式时，保留目标表格原样。** 这种情况下不覆盖目标的边框、底纹、列宽、合并关系，只把明确的「两字符首行缩进」归零，并应用一个隐藏的「表格正文（无首行缩进）」样式——这样在 Word 里新增行、粘贴内容或清除直接格式后，不会再次从正文样式继承那两个字符。

6. **双端一致靠机制，不靠自觉。** 界面文案集中在一份 JSON 里，构建期生成两端强类型常量；写错 key 在编译期就报错，而不是变成线上界面的一块空白。删除策略、格式展示逻辑、导航语义两端各有实现但共用同一套测试基准。

## 隐私边界

`.wfstyle` 只包含经过白名单处理的格式 XML 和预览索引：样式、主题颜色、字体映射、编号规则、部分格式设置与页面布局。

**不保存**：源文档正文、页眉页脚文字、批注、图片、宏、嵌入对象、嵌入字体、源文件名。预览里看到的示例文字由程序生成，不是源文档摘录。

格式方案名称默认取源文件名，可在导入时修改。自定义样式的名称本身属于 Word 格式信息，会保留。

格式库位置：

```text
# macOS
~/Library/Application Support/FormaFushi/style-packs/

# Windows
%LOCALAPPDATA%\FormaFushi\style-packs\
```

2.7.0 之前的 macOS 版本用的是 `WordFormatMigrator` 目录。新版本首次启动时整体迁移到 `FormaFushi`，并留下 `.migrated-from-WordFormatMigrator` 标记；迁移失败时继续使用旧目录——宁可保留旧目录名，也不能让格式库凭空消失。

## 应用到目标文档时

**会替换**：

- Word 样式系统：标题 1/2/3、正文、自定义样式和表格样式。
- 主题颜色、主题字体、字体表和编号定义。
- 范本实际使用的标题多级编号（「1」「1.1」「1.1.1」）。目标标题开头的重复手工序号按设计要点 4 的规则清理，标题正文不变。
- 标题段落的 Left、首行和悬挂设置，取自范本实际使用值。编号定义里的制表位与定位数据仍保留，但不会把三级编号的 `0.49"` 错当成标题段落 Left。
- 目标从「第三章」等非 1 章节开始时，保留起始章号，后续自动编号继续显示为「3」「3.1」「3.1.1」。
- 范本只用到标题一至三时：采用智能补全的标题四五，目标原先随意设置的四五级直接格式被清理。
- 目标文字与段落上的手工直接格式（字体、字号、粗体、颜色、底纹、对齐、缩进、间距、边框、编号）。
- 范本实际使用了表格样式时：清除目标表格的直接边框、底纹和边距并采用范本表格样式；普通单元格段落仍防止继承正文的两字符首行缩进。
- 纸张、方向、页边距、分栏和页面边框（可关闭此选项）。
- 可选「所有标题向下调整一级」：标题一→二，依次到标题八→九；标题九受 Word 九级上限保持不变。格式库只有前三层时，会按同一设计逻辑在本次应用中补全所需的标题六至九。

**会保留**：

- 目标文档的文字、图片、表格结构、超链接、批注、脚注、尾注和嵌入对象。
- 页眉页脚内容及其关联关系。
- 表格列宽、合并单元格、重复标题行等结构信息。
- 范本没用过表格样式时：目标表格的样式、边框、底纹、列宽、边距、合并关系、单元格属性，以及单元格段落原有的对齐、间距、编号和左右缩进。仅把明确的「两字符首行缩进」改成零；Word 只在段落上留 `firstLine=240` 磅值又同时从正文样式继承「两字符」的情况，两种单位一起归零。带自动编号、悬挂缩进或大纲级别的表格段落保护其列表结构，除非段落本身明确保存了两字符首行缩进。
- 上下标、公式标记、语言、从右到左书写、隐藏文字等带内容语义的属性。
- `.docm` 目标里的宏；生成文件仍必须是 `.docm`。

目标中找不到对应源样式的段落，按同级标题、同名样式或正文样式匹配。

## 需要注意

- 建议在 Word 中把重要格式定义为「标题 1」「标题 2」「正文」或自定义样式，并使用「多级列表/自动编号」。程序处理的是样式系统，手工排版越多可复用的越少。
- 目标里的四五级标题需已标记为 Word 的「标题 4」「标题 5」或对应大纲级别。仅靠手工加粗放大的普通正文无法可靠判断是四级还是五级。
- 「所有标题向下调整一级」是结构操作，默认关闭。把已处理过的结果再次作为目标并重新勾选，标题会再下调一级。
- 2.4.0 之前保存的格式库仍可使用，应用时会自动修复分散的多级编号并补齐智能生成标题遗漏的序号字体；但旧文件没保存标题段落实际用过的缩进，程序不会猜测。建议用新版本重新导入一次范本。
- 老式 `.doc`、加密或密码保护的文件需先在 Word 中转换或解锁。
- 图片自身、图表、SmartArt 和嵌入对象内部的视觉设计不会被重绘。
- 生成后建议用 Word 打开，更新目录、交叉引用和域，并快速检查分页。
- 首次打开若 macOS 提示来源不明，在 Finder 中右键应用选「打开」。Windows 便携版暂未使用商业代码签名证书，首次启动前请核对发布包 SHA-256；如 SmartScreen 拦截，确认来源后选「更多信息」→「仍要运行」。

## 命令行方式（可选）

引擎独立于两个客户端，可以单独使用：

```bash
python3 style_pack_manager.py create-pack \
  --source 范本.docx \
  --out 我的格式.wfstyle \
  --name 我的格式

# 或只给格式库目录，由引擎决定文件名并在 JSON 里回传。
# 两端客户端走的就是这条路径，因此命名规则只有一份实现。
python3 style_pack_manager.py create-pack \
  --source 范本.docx \
  --dir ~/Library/Application\ Support/FormaFushi/style-packs \
  --name 我的格式

python3 style_pack_manager.py apply-pack \
  --pack 我的格式.wfstyle \
  --target 目标.docx \
  --out 目标-格式已替换.docx
```

保留目标原有纸张与页边距加 `--preserve-page-layout`；把正文所有标题下调一级加 `--demote-headings`。

## 组件

```
forma-word-format-migrator/
├── word_style_transfer.py       # 引擎核心:OOXML 解析、样式迁移、编号合成
├── style_pack_manager.py        # 引擎 CLI:create-pack / pack-info / apply-pack
├── shared/ui-strings.json       # 双端界面文案的唯一来源(203 条)
├── scripts/gen_ui_strings.py    # 文案代码生成器 + CI 同步性校验
├── swift-app/                   # Mac 客户端(SwiftUI)
│   ├── Models/                  #   数据模型、应用状态、删除策略
│   ├── Bridge/                  #   引擎调用、格式库定位与迁移
│   ├── Theme/                   #   配色与可复用控件
│   ├── Views/                   #   三步流程、常驻侧边栏、属性检查器
│   └── Generated/UIStrings.swift  # 生成物,勿手改
├── windows-app/FormaFushi.Windows/  # Windows 客户端(WinForms)
│   └── Generated/UIStrings.g.cs     # 生成物,勿手改
├── scripts/build_macos_app.sh   # 签名 .app + 通用二进制 + ZIP
├── scripts/build_windows_app.sh # 自包含便携包(内嵌 .NET/Python/lxml)
└── tests/                       # Python 回归 + Swift 与 C# 行为测试
```

两端客户端只做 UI 与 bridge，格式逻辑全部在引擎里——这条边界是刻意维持的，见[路线](#路线)。

## 开发与验证

装依赖。运行时只要 `lxml`；回归测试另需 `python-docx` 和 `Pillow` 生成夹具：

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

| 检查 | 命令 | 覆盖 |
|------|------|------|
| 引擎回归 | `python3 -m unittest discover -s tests -p 'test_*.py' -v` | 93 项：样式迁移、编号合成、表格保真、隐私边界、格式包命名契约 |
| Mac 行为测试 | 见下方脚本 | 12 项删除策略 + 8 项格式库目录迁移 |
| Windows 行为测试 | `dotnet run --project tests\WindowsPackDeletionPolicyTests\WindowsPackDeletionPolicyTests.csproj -c Release -- --strict` | 12 项，与 Mac 侧逐条对应 |
| 文案同步性 | `python3 scripts/gen_ui_strings.py --check` | 生成物是否与 JSON 一致 |

Swift 测试每个套件自带 `@main`，需各编各的可执行文件：

```bash
for suite in PackDeletionPolicyTests LibraryLocationTests; do
  xcrun swiftc -parse-as-library -D WORD_FORMAT_LIBRARY_TESTING \
    $(find swift-app -name '*.swift' | sort) "tests/$suite.swift" \
    -o "build/$suite"
  "./build/$suite"
done
```

Windows 那 12 项必须在真实 Windows 上跑（涉及回收站与符号链接）。`--strict` 表示不允许因环境不支持而跳过任何一项，CI 用这个开关。

以上全部检查加两端客户端编译，由 [`.github/workflows/ci.yml`](.github/workflows/ci.yml) 在每次 push 和 PR 时执行。

### 界面文案的单一来源

两端全部中文文案在 [`shared/ui-strings.json`](shared/ui-strings.json)，由生成器产出强类型常量：

```bash
python3 scripts/gen_ui_strings.py            # 改完 JSON 重新生成
python3 scripts/gen_ui_strings.py --check    # 校验同步性
```

生成物是 `swift-app/Generated/UIStrings.swift` 和 `windows-app/FormaFushi.Windows/Generated/UIStrings.g.cs`，不要手工编辑。

选代码生成而不是运行时读 JSON，是为了让写错的 key 在**编译期**报错，而不是变成线上界面里的一块空白。平台变体只允许用于真正的系统术语差异（废纸篓/回收站、Finder/文件夹），不允许拿来放任两端表达随意漂移。

### 构建分发包

```bash
./scripts/build_macos_app.sh    # 签名 .app（Apple Silicon + Intel）与 ZIP
./scripts/build_windows_app.sh  # 在 Mac 上交叉构建 Windows x64 便携包
```

Windows 脚本会校验并组装固定版本的 .NET、Windows Embeddable Python 与 `lxml`，生成 UTF-8 文件名兼容的 ZIP 和 SHA-256。两个脚本都从工程文件读版本号（`swift-app/Info.plist` 与 `FormaFushi.Windows.csproj`），不再各自硬编码。构建产物写入 `build/` 和 `outputs/`，不进 Git。

## 项目状态与适用边界

**适合**：需要把一套排版规范反复套用到大量文档的场景——公文、标书、论文、技术手册；范本本身用 Word 样式系统而非手工排版做出来的项目；需要 Mac 与 Windows 协同、且希望两边行为一致的团队。

**慎用或暂不适合**：范本靠手工排版堆出来的文档——程序迁移的是样式系统，手工格式越多可复用的越少；需要保留目标文档原有样式并只做局部调整的场景——这是整套格式替换，不是差量合并；`.doc` 等老格式与加密文件需先在 Word 中转换。

**验证程度，如实陈述**：93 项 Python 引擎回归覆盖样式迁移、编号合成与表格保真，在 Linux / macOS / Windows 三平台执行；两端删除策略各 12 项对照检查、格式库迁移 8 项检查，全部在 CI 中真实运行（Windows 侧回收站与符号链接不允许跳过）。**尚无大规模生产文档的长期数据**——复杂的真实文档总能找出程序判断不了的情形，遇到请开 issue 并附上能复现的最小样本。

## 路线

引擎目前是 Python，两个客户端各自通过 bridge 调用。下一步计划把引擎换成 Rust 静态库，Swift 走 C ABI、C# 走 P/Invoke，替换范围仅限两个 `PythonBridge` 文件——本轮双端一致性改造刻意把改动限制在 UI 与 bridge 层，就是为了不推翻这条路径。届时 Mac 不再依赖用户自装 `lxml`，Windows 便携包可以去掉整个内嵌 Python 运行时。现有 93 项测试作为移植的验收基准。

## License

[MIT](LICENSE)
