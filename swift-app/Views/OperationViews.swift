// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers
// [OUTPUT]: 提供OperationViews 中的类型与接口
// [POS]: Mac 原生终端 - 处理通知与可取消的忙碌覆盖层
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

struct OperationNoticeBanner: View {
    let message: String
    let dismiss: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "info.circle.fill")
                .foregroundStyle(Palette.green)
            Text(message)
                .font(.system(size: 12.5, weight: .semibold))
            Spacer(minLength: 18)
            Button(action: dismiss) {
                Image(systemName: "xmark")
                    .font(.system(size: 10, weight: .bold))
                    .frame(width: 24, height: 24)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("关闭提示")
        }
        .padding(.horizontal, 14)
        .frame(maxWidth: 620, minHeight: 44)
        .background(.ultraThickMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(Palette.green.opacity(0.28), lineWidth: 1)
        }
        .shadow(color: .black.opacity(0.12), radius: 15, y: 6)
    }
}

struct BusyOverlay: View {
    let message: String
    let canCancel: Bool
    let isCancelling: Bool
    let cancel: () -> Void

    var body: some View {
        ZStack {
            Color.black.opacity(0.16).ignoresSafeArea()
            VStack(spacing: 12) {
                ProgressView()
                    .controlSize(.large)
                    .tint(Palette.green)
                Text(message)
                    .font(.system(size: 13, weight: .semibold))
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 330)
                Text(isCancelling ? "正在等待当前写入安全结束。" : "全程在本机处理，原文件不会被覆盖。")
                    .font(.system(size: 10.5))
                    .foregroundStyle(Palette.mutedInk)
                    .multilineTextAlignment(.center)
                if canCancel || isCancelling {
                    Button(isCancelling ? "正在停止…" : "取消处理") {
                        cancel()
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    .disabled(isCancelling)
                    .keyboardShortcut(.cancelAction)
                }
            }
            .padding(.horizontal, 30)
            .padding(.vertical, 22)
            .frame(minWidth: 360, minHeight: 150)
            .background(.ultraThickMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .shadow(color: .black.opacity(0.16), radius: 24, y: 10)
        }
    }
}
