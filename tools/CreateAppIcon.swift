/**
 * [INPUT]: 依赖 AppKit, Foundation
 * [OUTPUT]: 提供 roundedRect
 * [POS]: 生成 Mac 应用品牌图标及图标集
 * [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
import AppKit
import Foundation

let output = CommandLine.arguments.dropFirst().first ?? "WordFormatIcon.png"
let canvas = NSSize(width: 1024, height: 1024)
let image = NSImage(size: canvas)
image.lockFocus()

guard let context = NSGraphicsContext.current?.cgContext else {
    fatalError("无法创建图标画布")
}

context.clear(CGRect(origin: .zero, size: canvas))
let background = CGPath(
    roundedRect: CGRect(x: 72, y: 72, width: 880, height: 880),
    cornerWidth: 210,
    cornerHeight: 210,
    transform: nil
)
context.saveGState()
context.addPath(background)
context.clip()
let colors = [
    NSColor(calibratedRed: 0.055, green: 0.255, blue: 0.235, alpha: 1).cgColor,
    NSColor(calibratedRed: 0.102, green: 0.470, blue: 0.420, alpha: 1).cgColor,
] as CFArray
let gradient = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1])!
context.drawLinearGradient(
    gradient,
    start: CGPoint(x: 180, y: 900),
    end: CGPoint(x: 890, y: 120),
    options: []
)

// Quiet contour lines suggest a reusable library without cluttering the mark.
context.setStrokeColor(NSColor.white.withAlphaComponent(0.075).cgColor)
context.setLineWidth(18)
for inset in stride(from: CGFloat(10), through: 190, by: 45) {
    context.strokeEllipse(in: CGRect(x: 620 - inset, y: 620 - inset, width: 500 + inset * 2, height: 500 + inset * 2))
}
context.restoreGState()

func roundedRect(_ rect: CGRect, radius: CGFloat, color: NSColor, shadow: Bool = false) {
    context.saveGState()
    if shadow {
        context.setShadow(offset: CGSize(width: 0, height: -22), blur: 36, color: NSColor.black.withAlphaComponent(0.25).cgColor)
    }
    context.setFillColor(color.cgColor)
    context.addPath(CGPath(roundedRect: rect, cornerWidth: radius, cornerHeight: radius, transform: nil))
    context.fillPath()
    context.restoreGState()
}

// Two sheets: the format source behind, the reusable format card in front.
context.saveGState()
context.translateBy(x: 512, y: 512)
context.rotate(by: -0.10)
roundedRect(CGRect(x: -265, y: -285, width: 530, height: 610), radius: 48, color: NSColor.white.withAlphaComponent(0.70), shadow: true)
context.restoreGState()

context.saveGState()
context.translateBy(x: 512, y: 500)
context.rotate(by: 0.055)
roundedRect(CGRect(x: -280, y: -300, width: 560, height: 640), radius: 54, color: NSColor(calibratedWhite: 0.99, alpha: 1), shadow: true)

let ink = NSColor(calibratedRed: 0.065, green: 0.245, blue: 0.225, alpha: 1)
let title = NSAttributedString(
    string: "Aa",
    attributes: [
        .font: NSFont.systemFont(ofSize: 156, weight: .bold),
        .foregroundColor: ink,
        .kern: -8,
    ]
)
title.draw(at: CGPoint(x: -205, y: 86))

let chipColors = [
    NSColor(calibratedRed: 0.086, green: 0.365, blue: 0.330, alpha: 1),
    NSColor(calibratedRed: 0.185, green: 0.333, blue: 0.592, alpha: 1),
    NSColor(calibratedRed: 0.440, green: 0.225, blue: 0.075, alpha: 1),
]
let widths: [CGFloat] = [338, 275, 385]
for index in 0..<3 {
    roundedRect(
        CGRect(x: -205, y: 8 - CGFloat(index) * 88, width: widths[index], height: 34),
        radius: 17,
        color: chipColors[index].withAlphaComponent(index == 0 ? 0.92 : 0.76)
    )
}

// Small library tab makes the icon read as a saved style collection.
roundedRect(CGRect(x: 118, y: 222, width: 92, height: 92), radius: 26, color: ink)
let check = CGMutablePath()
check.move(to: CGPoint(x: 140, y: 264))
check.addLine(to: CGPoint(x: 158, y: 244))
check.addLine(to: CGPoint(x: 190, y: 282))
context.addPath(check)
context.setStrokeColor(NSColor.white.cgColor)
context.setLineWidth(13)
context.setLineCap(.round)
context.setLineJoin(.round)
context.strokePath()
context.restoreGState()

image.unlockFocus()
guard
    let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let png = bitmap.representation(using: .png, properties: [:])
else {
    fatalError("无法导出图标")
}
try png.write(to: URL(fileURLWithPath: output), options: .atomic)
