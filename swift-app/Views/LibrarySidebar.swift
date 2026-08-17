import SwiftUI

/// 常驻格式库侧边栏。
///
/// 信息架构以 Windows 端为准：三个步骤里格式库始终可见可切换，
/// 「换一套格式」不再需要退回第一步。
struct LibrarySidebar: View {
    @ObservedObject var model: WordFormatLibraryModel
    @State private var packPendingDeletion: PackManifest?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text(UIStrings.Sidebar.title)
                    .font(.system(size: 16, weight: .bold))
                Text(UIStrings.Sidebar.hint)
                    .font(.system(size: 11))
                    .foregroundStyle(Palette.mutedInk)
            }
            .padding(.horizontal, 22)
            .padding(.top, 22)

            Button {
                if let url = FilePanels.chooseSource() {
                    Task { await model.importSource(url) }
                }
            } label: {
                Label(UIStrings.Sidebar.importButton, systemImage: "plus")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(model.isBusy)
            .padding(.horizontal, 22)
            .padding(.top, 16)

            HStack {
                Spacer()
                Button {
                    Task { await model.reloadLibrary() }
                } label: {
                    Label(UIStrings.Sidebar.refreshButton, systemImage: "arrow.clockwise")
                        .font(.system(size: 11.5, weight: .semibold))
                        .foregroundStyle(Palette.green)
                }
                .buttonStyle(.plain)
                .disabled(model.isBusy)
            }
            .padding(.horizontal, 22)
            .padding(.top, 10)

            if let notice = model.libraryNotice {
                Label(notice, systemImage: "exclamationmark.triangle")
                    .font(.system(size: 11))
                    .foregroundStyle(Palette.amber)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 22)
                    .padding(.top, 12)
            }

            if model.packs.isEmpty {
                Text(UIStrings.Sidebar.empty)
                    .font(.system(size: 12))
                    .foregroundStyle(Palette.mutedInk)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 22)
                    .padding(.top, 24)
                Spacer()
            } else {
                ScrollView {
                    VStack(spacing: 10) {
                        ForEach(model.packs, id: \.libraryIdentity) { pack in
                            SidebarPackCard(
                                pack: pack,
                                isSelected: model.selectedPack?.libraryIdentity == pack.libraryIdentity,
                                selectAction: { model.selectPack(pack) },
                                deleteAction: { packPendingDeletion = pack }
                            )
                            .disabled(model.isBusy)
                        }
                    }
                    .padding(.horizontal, 18)
                    .padding(.vertical, 16)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Palette.sidebar)
        .overlay(alignment: .trailing) {
            Rectangle()
                .fill(Palette.green)
                .frame(width: 3)
                .opacity(model.isLibraryHighlighted ? 1 : 0)
        }
        .animation(.easeInOut(duration: 0.25), value: model.isLibraryHighlighted)
        .alert(item: $packPendingDeletion) { pack in
            Alert(
                title: Text(UIStrings.Deletion.confirmTitle(name: pack.name)),
                message: Text(UIStrings.Deletion.confirmMessage),
                primaryButton: .destructive(Text(UIStrings.Deletion.confirmPrimary)) {
                    Task { await model.deletePack(pack) }
                },
                secondaryButton: .cancel(Text(UIStrings.Deletion.confirmCancel))
            )
        }
    }
}

private struct SidebarPackCard: View {
    let pack: PackManifest
    let isSelected: Bool
    let selectAction: () -> Void
    let deleteAction: () -> Void

    var body: some View {
        HStack(spacing: 0) {
            Button(action: selectAction) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(pack.name)
                        .font(.system(size: 13.5, weight: .bold))
                        .foregroundStyle(isSelected ? Palette.greenDeep : Palette.ink)
                        .lineLimit(1)
                    Text(summary)
                        .font(.system(size: 11))
                        .foregroundStyle(Palette.mutedInk)
                        .lineLimit(1)
                    Text(pack.createdDisplay)
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .lineLimit(1)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 12)
                .padding(.leading, 14)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            Button(role: .destructive, action: deleteAction) {
                Text(UIStrings.Sidebar.deleteButton)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(Palette.amber)
                    .frame(width: 46, height: 78)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .help(UIStrings.Deletion.confirmTitle(name: pack.name))
            .accessibilityLabel(UIStrings.Deletion.confirmTitle(name: pack.name))
        }
        .background(isSelected ? Palette.mint : Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .stroke(isSelected ? Palette.green : Palette.line, lineWidth: isSelected ? 1.6 : 1)
        }
    }

    private var summary: String {
        pack.inferredCount > 0
            ? UIStrings.Sidebar.packSummaryWithInferred(
                used: "\(pack.usedStyleCount)",
                inferred: "\(pack.inferredCount)"
            )
            : UIStrings.Sidebar.packSummary(used: "\(pack.usedStyleCount)")
    }
}
