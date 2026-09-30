// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers
// [OUTPUT]: 提供ApplyStepView 中的类型与接口
// [POS]: Mac 原生终端 - 目标选择、应用选项与结构处理结果
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

// MARK: - Step 3

struct ApplyStepView: View {
    @ObservedObject var model: WordFormatLibraryModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(UIStrings.ApplyStep.title)
                            .font(.system(size: 27, weight: .bold, design: .rounded))
                        Text(UIStrings.ApplyStep.subtitle)
                            .font(.system(size: 13))
                            .foregroundStyle(Palette.mutedInk)
                    }
                    Spacer()
                    Button {
                        model.currentStep = 2
                    } label: {
                        Label("返回检查格式", systemImage: "arrow.left")
                    }
                    .buttonStyle(SecondaryButtonStyle())
                }

                if let pack = model.selectedPack {
                    HStack(spacing: 14) {
                        Image(systemName: "text.book.closed.fill")
                            .font(.system(size: 22))
                            .foregroundStyle(Palette.green)
                            .frame(width: 48, height: 48)
                            .background(Palette.mint)
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        VStack(alignment: .leading, spacing: 3) {
                            Text("将应用：\(pack.name)")
                                .font(.system(size: 15, weight: .bold))
                            Text("包含 \(pack.formatCountSummary) · \(pack.sourceFileName ?? "来源内容已脱敏")")
                                .font(.system(size: 11.5))
                                .foregroundStyle(Palette.mutedInk)
                        }
                        Spacer()
                        Button("更换") { model.highlightLibrary() }
                            .buttonStyle(SecondaryButtonStyle())
                    }
                    .padding(16)
                    .background(Color.white.opacity(0.62))
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .stroke(Palette.line, lineWidth: 1)
                    }
                }

                HStack(alignment: .top, spacing: 20) {
                    TargetDocumentCard(model: model)
                        .frame(maxWidth: .infinity, minHeight: 255)
                    ApplyOptionsCard(model: model)
                        .frame(width: 355)
                }

                if let preflight = model.preflight {
                    PreflightCard(report: preflight)
                } else if model.targetURL != nil {
                    AppCard {
                        HStack {
                            Text("请完成当前文档与选项的预检后再应用格式。")
                            Spacer()
                            Button("重新预检") { Task { await model.refreshPreflight() } }
                                .buttonStyle(SecondaryButtonStyle())
                        }
                    }
                }

                if let report = model.applyReport {
                    SuccessCard(report: report, restart: {
                        model.clearTarget()
                    })
                }
            }
            .padding(28)
        }
        .onChange(of: model.applySourcePageLayout) { _ in
            Task { await model.refreshPreflight() }
        }
        .onChange(of: model.demoteHeadings) { _ in
            Task { await model.refreshPreflight() }
        }
    }
}

struct TargetDocumentCard: View {
    @ObservedObject var model: WordFormatLibraryModel

    var body: some View {
        AppCard {
            VStack(spacing: 15) {
                ZStack {
                    Circle().fill(Palette.mint)
                    Image(systemName: model.targetURL == nil ? "doc.badge.arrow.up" : "doc.fill")
                        .font(.system(size: 31, weight: .medium))
                        .foregroundStyle(Palette.green)
                }
                .frame(width: 66, height: 66)

                if let targetURL = model.targetURL {
                    Text(targetURL.lastPathComponent)
                        .font(.system(size: 16, weight: .bold))
                        .lineLimit(2)
                        .multilineTextAlignment(.center)
                    Text(targetURL.deletingLastPathComponent().path)
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Button("更换目标文件") { chooseTargetFile() }
                        .buttonStyle(SecondaryButtonStyle())
                } else {
                    Text("选择要修改格式的 Word 文件")
                        .font(.system(size: 17, weight: .bold))
                    Text("支持 DOCX 与保留宏的 DOCM")
                        .font(.system(size: 12))
                        .foregroundStyle(Palette.mutedInk)
                    Button {
                        chooseTargetFile()
                    } label: {
                        Label("选择目标文件", systemImage: "folder")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                }
            }
            .frame(maxWidth: .infinity, minHeight: 215)
        }
    }

    private func chooseTargetFile() {
        guard let url = FilePanels.chooseTarget() else { return }
        model.chooseTarget(url)
    }
}

struct ApplyOptionsCard: View {
    @ObservedObject var model: WordFormatLibraryModel

    var body: some View {
        AppCard {
            VStack(alignment: .leading, spacing: 17) {
                Text("应用选项")
                    .font(.system(size: 16, weight: .bold))
                Toggle(isOn: $model.applySourcePageLayout) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("同步格式源的页面设置")
                            .font(.system(size: 13, weight: .semibold))
                        Text("包含纸张、方向与页边距")
                            .font(.system(size: 10.5))
                            .foregroundStyle(Palette.mutedInk)
                    }
                }
                .toggleStyle(.switch)
                .tint(Palette.green)

                Divider().overlay(Palette.line)
                Toggle(isOn: $model.demoteHeadings) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("所有标题向下调整一级")
                            .font(.system(size: 13, weight: .semibold))
                        Text("标题一→标题二，标题八→标题九")
                            .font(.system(size: 10.5))
                            .foregroundStyle(Palette.mutedInk)
                    }
                }
                .toggleStyle(.switch)
                .tint(Palette.green)
                Text("标题九受 Word 上限保持不变；若再次对已处理文件勾选，会再向下一级。")
                    .font(.system(size: 10.5))
                    .foregroundStyle(Palette.mutedInk)
                    .fixedSize(horizontal: false, vertical: true)

                Divider().overlay(Palette.line)
                VStack(alignment: .leading, spacing: 8) {
                    OptionLine(icon: "checkmark.circle", text: "保留正文、图片、表格与页眉页脚内容")
                    OptionLine(icon: "eraser", text: "清理旧样式与手工视觉格式")
                    if (model.selectedPack?.inferredStyleCount ?? 0) > 0 {
                        OptionLine(
                            icon: "wand.and.stars",
                            text: "用标题一至标题三的设计逻辑补全标题四、标题五"
                        )
                    }
                    OptionLine(icon: "doc.on.doc", text: "始终另存为新文件")
                    if model.selectedPack?.usedFormats.contains(where: {
                        $0.type == "paragraph" && $0.outlineLevel != nil && $0.numbered
                    }) == true {
                        OptionLine(
                            icon: "list.number",
                            text: "同步标题多级编号，例如 1、1.1、1.1.1"
                        )
                        OptionLine(
                            icon: "checkmark.circle",
                            text: "自动清理与层级计数一致的手工序号，例如“第三章”“3.1”"
                        )
                    }
                    if model.selectedPack?.usedFormats.contains(where: { $0.type == "table" }) == false {
                        OptionLine(
                            icon: "tablecells",
                            text: "格式库没有表格样式：保留表格外观，并用稳定样式取消单元格的两字符首行缩进"
                        )
                    }
                }
                Spacer(minLength: 2)
                Button {
                    chooseDestinationAndApply()
                } label: {
                    Label(model.outputURL == nil ? "选择保存位置并应用" : "重新生成", systemImage: "wand.and.stars")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(!model.canApplyPreflight)
                .opacity(model.canApplyPreflight ? 1 : 0.48)
            }
            .frame(minHeight: 215)
        }
    }

    private func chooseDestinationAndApply() {
        guard let targetURL = model.targetURL else { return }
        let panel = NSSavePanel()
        panel.title = "另存处理后的 Word 文档"
        panel.prompt = "应用并保存"
        panel.canCreateDirectories = true
        panel.allowedContentTypes = [UTType(filenameExtension: targetURL.pathExtension)].compactMap { $0 }
        panel.nameFieldStringValue = "\(targetURL.deletingPathExtension().lastPathComponent)-已套用格式.\(targetURL.pathExtension)"
        panel.directoryURL = targetURL.deletingLastPathComponent()
        guard panel.runModal() == .OK, let destination = panel.url else { return }
        Task { await model.applyPack(savingTo: destination) }
    }
}

struct PreflightCard: View {
    let report: DocumentPreflight
    @State private var fontCatalog = InstalledFontCatalog.cachedSystem

    private var missingFonts: [String] {
        guard fontCatalog.isLoaded else { return [] }
        return report.fontNames.filter { fontCatalog.match(name: $0).kind == .missing }
    }

    private var headingSummary: String {
        (1...9).compactMap { level in
            guard let count = report.headingLevelCounts[String(level)], count > 0 else { return nil }
            return "标题\(level)：\(count)"
        }.joined(separator: " · ")
    }

    var body: some View {
        AppCard {
            VStack(alignment: .leading, spacing: 11) {
                Label("应用前预检", systemImage: "checklist")
                    .font(.system(size: 16, weight: .bold))
                Text("\(report.summary.paragraphCount) 个段落 · \(report.summary.tableCount) 个表格 · \(report.summary.characterCount) 字符")
                Text(headingSummary.isEmpty ? "未识别到标题层级" : headingSummary)
                Text("向下调整一级：\(report.headingDemotionCount) 个标题")
                if let direct = report.manualFormatting {
                    Text("发现直接格式：\(direct.paragraphCount) 个段落、\(direct.runCount) 个文字片段；将按方案整理，其中列表和表格保护规则继续生效。")
                }
                if let levels = report.runtimeInferredHeadingLevels, !levels.isEmpty {
                    Text("本次将按方案逻辑补全：" + levels.map { "标题\($0)" }.joined(separator: "、"))
                }
                Text(report.tableAction == "preserve_target_remove_two_character_indent"
                     ? "表格：保留目标外观，清除单元格两字符缩进"
                     : "表格：应用格式方案的表格样式")
                Text(report.pageLayoutAction == "preserve_target" ? "页面：保留目标设置" : "页面：同步格式方案设置")
                if !report.fontNames.isEmpty {
                    Text("方案字体：" + report.fontNames.joined(separator: "、"))
                    if !fontCatalog.isLoaded {
                        Text("正在检查本机字体…").foregroundStyle(Palette.mutedInk)
                    } else if !missingFonts.isEmpty {
                        Label("本机未注册：" + missingFonts.joined(separator: "、") + "。Word 可能使用自带字体或替代字体，请检查最终显示。", systemImage: "exclamationmark.triangle")
                            .foregroundStyle(Palette.amber)
                    }
                }
                Text("将清理旧样式及手工视觉格式；正文、图片与表格内容保留。应用时会再次校验本次预检的两个文件。")
                    .font(.system(size: 11))
                    .foregroundStyle(Palette.mutedInk)
                ForEach(Array(report.warnings.enumerated()), id: \.offset) { _, warning in
                    Label(warning, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(Palette.amber)
                }
            }
            .font(.system(size: 12))
            .frame(maxWidth: .infinity, alignment: .leading)
            .textSelection(.enabled)
        }
        .task {
            if !fontCatalog.isLoaded { fontCatalog = await .refreshSystem() }
        }
    }
}

struct OptionLine: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(Palette.green)
                .frame(width: 16)
            Text(text)
                .font(.system(size: 11.5))
                .foregroundStyle(Palette.mutedInk)
        }
    }
}

struct SuccessCard: View {
    let report: ApplyReport
    let restart: () -> Void
    @State private var didCopyReport = false

    private let metricColumns = Array(
        repeating: GridItem(.flexible(), spacing: 10),
        count: 4
    )

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack(spacing: 15) {
                ZStack {
                    Circle().fill(Palette.success)
                    Image(systemName: "checkmark")
                        .font(.system(size: 19, weight: .bold))
                        .foregroundStyle(.white)
                }
                .frame(width: 44, height: 44)
                VStack(alignment: .leading, spacing: 3) {
                    Text("格式已经应用完成")
                        .font(.system(size: 15, weight: .bold))
                    Text(report.outputURL.path)
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                Spacer()
                Button {
                    copyReport()
                } label: {
                    Label(
                        didCopyReport ? "已复制报告" : "复制处理报告",
                        systemImage: didCopyReport ? "checkmark" : "doc.on.doc"
                    )
                }
                .buttonStyle(SecondaryButtonStyle())
                Button("在 Finder 中显示") {
                    NSWorkspace.shared.activateFileViewerSelecting([report.outputURL])
                }
                .buttonStyle(SecondaryButtonStyle())
                Button("打开结果") {
                    NSWorkspace.shared.open(report.outputURL)
                }
                .buttonStyle(PrimaryButtonStyle(compact: true))
            }

            LazyVGrid(columns: metricColumns, spacing: 10) {
                SuccessMetric(
                    label: "已处理段落",
                    value: report.stats.paragraphsSeen,
                    icon: "text.alignleft"
                )
                SuccessMetric(
                    label: "样式重映射",
                    value: report.stats.stylesRemapped,
                    icon: "arrow.triangle.2.circlepath"
                )
                SuccessMetric(
                    label: "清理旧格式属性",
                    value: report.stats.directPropertiesRemoved,
                    icon: "eraser"
                )
                SuccessMetric(
                    label: "应用标题编号",
                    value: report.stats.headingNumbersApplied,
                    icon: "list.number"
                )
                SuccessMetric(
                    label: "保留正文列表",
                    value: report.stats.bodyListParagraphsPreserved,
                    icon: "list.bullet"
                )
                SuccessMetric(
                    label: "清理表格缩进",
                    value: report.stats.tableParagraphIndentsCleared,
                    icon: "tablecells"
                )
                SuccessMetric(
                    label: report.stats.tableFormatsPreserved > 0
                        ? "保留表格外观"
                        : "已处理表格",
                    value: report.stats.tableFormatsPreserved > 0
                        ? report.stats.tableFormatsPreserved
                        : report.stats.tablesSeen,
                    icon: "rectangle.grid.2x2"
                )
            }

            if !report.stats.uniqueWarnings.isEmpty {
                VStack(alignment: .leading, spacing: 7) {
                    Label("需要留意", systemImage: "exclamationmark.triangle.fill")
                        .font(.system(size: 12.5, weight: .bold))
                        .foregroundStyle(Palette.amber)
                    ForEach(report.stats.uniqueWarnings, id: \.self) { warning in
                        HStack(alignment: .top, spacing: 7) {
                            Circle()
                                .fill(Palette.amber)
                                .frame(width: 4, height: 4)
                                .padding(.top, 6)
                            Text(warning)
                                .font(.system(size: 11.5))
                                .foregroundStyle(Palette.ink)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Palette.amberWash.opacity(0.8))
                .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
            }

            HStack {
                Label(
                    report.stats.uniqueWarnings.isEmpty
                        ? "文档结构与处理统计已校验。请用 Word 检查编号、分页及表格外观。"
                        : "文档结构已校验。请结合上述提示，用 Word 检查编号、分页及表格外观。",
                    systemImage: report.stats.uniqueWarnings.isEmpty
                        ? "checkmark.shield"
                        : "doc.text.magnifyingglass"
                )
                .font(.system(size: 11.5, weight: .medium))
                .foregroundStyle(Palette.mutedInk)
                Spacer()
                Button("处理下一份") { restart() }
                    .buttonStyle(.plain)
                    .font(.system(size: 11.5, weight: .semibold))
                    .foregroundStyle(Palette.green)
            }
        }
        .padding(17)
        .background(Palette.mint.opacity(0.74))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(Palette.success.opacity(0.4), lineWidth: 1)
        }
    }

    private func copyReport() {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(report.plainText, forType: .string)
        didCopyReport = true
        Task {
            try? await Task.sleep(nanoseconds: 1_800_000_000)
            didCopyReport = false
        }
    }
}

struct SuccessMetric: View {
    let label: String
    let value: Int
    let icon: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Palette.green)
                .frame(width: 25, height: 25)
                .background(Color.white.opacity(0.75))
                .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
            VStack(alignment: .leading, spacing: 1) {
                Text("\(value)")
                    .font(.system(size: 17, weight: .bold, design: .rounded))
                Text(label)
                    .font(.system(size: 10.5))
                    .foregroundStyle(Palette.mutedInk)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 11)
        .frame(height: 49)
        .background(Color.white.opacity(0.55))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}
