// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers
// [OUTPUT]: 提供StyleInspector 中的类型与接口
// [POS]: Mac 原生终端 - 格式属性检查器及页面布局卡片
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

struct StyleInspector: View {
    let format: UsedFormat?
    let pageLayout: PageLayout

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("格式属性")
                    .font(.system(size: 16, weight: .bold))
                if let format {
                    VStack(alignment: .leading, spacing: 7) {
                        Text(format.sample)
                            .font(inspectorFont(format))
                            .fontWeight(format.bold == true ? .bold : .regular)
                            .italic(format.italic == true)
                            .foregroundStyle(format.colorHex.map(Color.init(hex:)) ?? Palette.ink)
                            .fixedSize(horizontal: false, vertical: true)
                        Text(format.name)
                            .font(.system(size: 11))
                            .foregroundStyle(Palette.mutedInk)
                    }
                    .frame(maxWidth: .infinity, minHeight: 84, alignment: .leading)
                    .padding(14)
                    .background(Color.white.opacity(0.78))
                    .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))

                    VStack(spacing: 0) {
                        PropertyRow(label: "类型", value: typeText(format))
                        PropertyRow(
                            label: "来源",
                            value: format.inferred == true
                                ? (format.inferenceLabel ?? "智能补全")
                                : "源文档实际使用 \(format.usageCount) 次"
                        )
                        PropertyRow(label: "中文字体", value: format.fontEastAsia ?? "继承主题")
                        PropertyRow(label: "西文字体", value: format.fontLatin ?? "继承主题")
                        PropertyRow(label: "字号", value: format.sizePt.map { "\(number($0)) pt" } ?? "继承")
                        PropertyRow(label: "字形", value: fontTraits(format))
                        PropertyRow(label: "颜色", value: format.colorHex.map { "#\($0)" } ?? "自动")
                        if format.type == "paragraph" {
                            PropertyRow(
                                label: "对齐",
                                value: paragraphAlignmentText(format.alignment)
                            )
                            PropertyRow(
                                label: "段前 / 段后",
                                value: paragraphSpacingText(
                                    before: format.spaceBeforePt,
                                    after: format.spaceAfterPt
                                )
                            )
                            PropertyRow(
                                label: "行距",
                                value: paragraphLineSpacingText(
                                    value: format.lineSpacing,
                                    rule: format.lineRule
                                )
                            )
                            PropertyRow(
                                label: "左 / 右缩进",
                                value: paragraphIndentSidesText(format)
                            )
                            PropertyRow(
                                label: "特殊缩进",
                                value: paragraphSpecialIndentText(format)
                            )
                            if let level = format.outlineLevel {
                                PropertyRow(label: "大纲级别", value: "\(level + 1) 级")
                            }
                            PropertyRow(
                                label: "编号",
                                value: format.numbered
                                    ? format.numberingExample.map { "是（示意：\($0)）" } ?? "是"
                                    : "否"
                            )
                        }
                        if format.type == "table" {
                            PropertyRow(label: "表格底色", value: hexText(format.tableFillHex))
                            PropertyRow(label: "强调色", value: hexText(format.tableAccentHex))
                        }
                    }
                    .background(Color.white.opacity(0.55))
                    .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
                } else {
                    Text("选择一张格式卡片查看详细属性。")
                        .font(.system(size: 12))
                        .foregroundStyle(Palette.mutedInk)
                }

                Divider().overlay(Palette.line)
                PageLayoutCard(layout: pageLayout)
            }
            .padding(20)
        }
    }

    private func inspectorFont(_ format: UsedFormat) -> Font {
        let size = min(max(format.sizePt ?? 14, 11), 24)
        if let name = format.fontEastAsia ?? format.fontLatin {
            return .custom(name, size: size)
        }
        return .system(size: size)
    }

    private func typeText(_ format: UsedFormat) -> String {
        if let level = format.outlineLevel { return "\(level + 1) 级标题" }
        switch format.type {
        case "character": return "字符样式"
        case "table": return "表格样式"
        default: return "段落样式"
        }
    }

    private func fontTraits(_ format: UsedFormat) -> String {
        var traits: [String] = []
        if format.bold == true { traits.append("粗体") }
        if format.italic == true { traits.append("斜体") }
        return traits.isEmpty ? "常规" : traits.joined(separator: "、")
    }

    private func hexText(_ value: String?) -> String {
        value.map { "#\($0)" } ?? "—"
    }
}

struct PropertyRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 9) {
            Text(label)
                .foregroundStyle(Palette.mutedInk)
            Spacer(minLength: 6)
            Text(value)
                .foregroundStyle(Palette.ink)
                .multilineTextAlignment(.trailing)
                .lineLimit(2)
        }
        .font(.system(size: 11))
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .overlay(alignment: .bottom) {
            Rectangle().fill(Palette.line.opacity(0.65)).frame(height: 1)
        }
    }
}

struct PageLayoutCard: View {
    let layout: PageLayout

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("页面设置")
                    .font(.system(size: 14, weight: .bold))
                Spacer()
                Text(layout.orientation == "landscape" ? "横向" : "纵向")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(Palette.green)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Palette.mint)
                    .clipShape(Capsule())
            }
            HStack(spacing: 14) {
                ZStack {
                    Rectangle()
                        .fill(Color.white)
                        .shadow(color: Palette.ink.opacity(0.12), radius: 4, y: 2)
                    RoundedRectangle(cornerRadius: 1)
                        .stroke(Palette.line, lineWidth: 1)
                        .padding(7)
                }
                .aspectRatio(pageAspect, contentMode: .fit)
                .frame(width: layout.orientation == "landscape" ? 74 : 52)
                VStack(alignment: .leading, spacing: 5) {
                    Text(pageSize)
                    Text("上 / 下：\(cm(layout.marginTopCM)) / \(cm(layout.marginBottomCM))")
                    Text("左 / 右：\(cm(layout.marginLeftCM)) / \(cm(layout.marginRightCM))")
                }
                .font(.system(size: 10.5))
                .foregroundStyle(Palette.mutedInk)
            }
        }
    }

    private var pageAspect: CGFloat {
        guard let width = layout.widthCM, let height = layout.heightCM, height > 0 else {
            return 0.707
        }
        return CGFloat(width / height)
    }

    private var pageSize: String {
        guard let width = layout.widthCM, let height = layout.heightCM else { return "使用文档默认页面" }
        return "\(number(width)) × \(number(height)) cm"
    }

    private func cm(_ value: Double?) -> String {
        value.map { "\(number($0)) cm" } ?? "—"
    }
}
