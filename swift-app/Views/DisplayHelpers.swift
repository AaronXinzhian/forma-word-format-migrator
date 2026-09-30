// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers
// [OUTPUT]: 提供DisplayHelpers 中的类型与接口
// [POS]: Mac 原生终端 - 格式属性展示和数值、颜色文字辅助
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

func paragraphAlignmentText(_ alignment: String?) -> String {
    switch ParagraphAlignmentEditChoice.canonical(alignment) {
    case "center": return "居中"
    case "right": return "右对齐"
    case "both": return "两端对齐"
    case "distribute": return "分散对齐"
    case "left": return "左对齐"
    case .some(let value): return "其他（\(value)）"
    case nil: return "继承"
    }
}

func paragraphSpacingText(before: Double?, after: Double?) -> String {
    let beforeText = before.map { "\(paragraphNumber($0)) pt" } ?? "继承"
    let afterText = after.map { "\(paragraphNumber($0)) pt" } ?? "继承"
    return "\(beforeText) / \(afterText)"
}

func paragraphLineSpacingText(value: Double?, rule: String?) -> String {
    guard let value else { return "继承" }
    switch LineSpacingEditChoice.canonical(rule, spacing: value) {
    case "exact": return "固定值 \(paragraphNumber(value)) pt"
    case "atLeast": return "最小值 \(paragraphNumber(value)) pt"
    case "auto", nil: return "\(paragraphNumber(value)) 倍"
    case .some(let raw): return "\(paragraphNumber(value)) pt（\(raw)）"
    }
}

func paragraphIndentSidesText(_ format: UsedFormat) -> String {
    paragraphIndentSidesText(
        left: preferredParagraphIndentMeasurement(
            chars: format.leftIndentChars,
            points: format.leftIndentPt
        ),
        right: preferredParagraphIndentMeasurement(
            chars: format.rightIndentChars,
            points: format.rightIndentPt
        )
    )
}

func paragraphIndentSidesText(
    left: ParagraphIndentMeasurement?,
    right: ParagraphIndentMeasurement?
) -> String {
    "左 \(left?.displayText ?? "继承")，右 \(right?.displayText ?? "继承")"
}

func paragraphSpecialIndentText(_ format: UsedFormat) -> String {
    if let measurement = preferredNonzeroParagraphIndentMeasurement(
        chars: format.firstLineIndentChars,
        points: format.firstLineIndentPt
    ) {
        return paragraphSpecialIndentText(choice: .firstLine, measurement: measurement)
    }
    if let measurement = preferredNonzeroParagraphIndentMeasurement(
        chars: format.hangingIndentChars,
        points: format.hangingIndentPt
    ) {
        return paragraphSpecialIndentText(choice: .hanging, measurement: measurement)
    }
    return "无"
}

func paragraphSpecialIndentText(
    choice: SpecialIndentEditChoice,
    measurement: ParagraphIndentMeasurement?
) -> String {
    switch choice {
    case .firstLine:
        return "首行 \(measurement?.displayText ?? "待填写")"
    case .hanging:
        return "悬挂 \(measurement?.displayText ?? "待填写")"
    case .none, .unchanged:
        return "无"
    }
}

func preferredParagraphIndentMeasurement(
    chars: Double?,
    points: Double?
) -> ParagraphIndentMeasurement? {
    if let chars {
        return ParagraphIndentMeasurement(value: chars, unit: .characters)
    }
    if let points {
        return ParagraphIndentMeasurement(value: points, unit: .points)
    }
    return nil
}

func preferredNonzeroParagraphIndentMeasurement(
    chars: Double?,
    points: Double?
) -> ParagraphIndentMeasurement? {
    if let chars, abs(chars) >= 0.0001 {
        return ParagraphIndentMeasurement(value: chars, unit: .characters)
    }
    if let points, abs(points) >= 0.0001 {
        return ParagraphIndentMeasurement(value: points, unit: .points)
    }
    return nil
}

func styleTypeText(_ format: UsedFormat) -> String {
    if let level = format.outlineLevel { return "标题 \(level + 1)" }
    switch format.type {
    case "paragraph": return "段落样式"
    case "character": return "字符样式"
    case "table": return "表格样式"
    default: return "\(format.type) 样式"
    }
}

func normalizedHexColor(_ raw: String) -> String? {
    let value = raw
        .trimmingCharacters(in: .whitespacesAndNewlines)
        .trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        .uppercased()
    guard value.count == 6,
          value.unicodeScalars.allSatisfy({
              CharacterSet(charactersIn: "0123456789ABCDEF").contains($0)
          }) else { return nil }
    return value
}

func hexString(from color: Color) -> String? {
    let native = NSColor(color)
    guard let rgb = native.usingColorSpace(.sRGB) else { return nil }
    return String(
        format: "%02X%02X%02X",
        Int((rgb.redComponent * 255).rounded()),
        Int((rgb.greenComponent * 255).rounded()),
        Int((rgb.blueComponent * 255).rounded())
    )
}

func number(_ value: Double) -> String {
    if value.rounded() == value { return String(Int(value)) }
    return String(format: "%.1f", value)
}

func paragraphNumber(_ value: Double) -> String {
    if abs(value.rounded() - value) < 0.000_001 {
        return String(Int(value.rounded()))
    }
    var rendered = String(
        format: "%.2f",
        locale: Locale(identifier: "en_US_POSIX"),
        value
    )
    while rendered.last == "0" { rendered.removeLast() }
    if rendered.last == "." { rendered.removeLast() }
    return rendered
}
