// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers
// [OUTPUT]: 提供StyleEditorSheet 中的类型与接口
// [POS]: Mac 原生终端 - 格式编辑器控件、字体选择与本地示意预览
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

struct StyleEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var model: WordFormatLibraryModel
    let pack: PackManifest

    @State private var drafts: [StyleEditDraft]
    @State private var selectedDraftID: String?
    @State private var schemeName: String
    @State private var searchText = ""
    @State private var isSubmitting = false
    @State private var errorMessage = ""
    @State private var isShowingError = false
    @State private var isConfirmingDiscard = false
    @State private var isConfirmingResetAll = false
    @State private var resetHistory = StyleResetHistory()
    @State private var editorNotice: String?
    @State private var installedFontCatalog: InstalledFontCatalog
    private let templateLatinFonts: [TemplateFontOption]
    private let templateEastAsiaFonts: [TemplateFontOption]

    init(model: WordFormatLibraryModel, pack: PackManifest) {
        self.model = model
        self.pack = pack
        var editableFormats = pack.usedFormats
        if !editableFormats.contains(where: { $0.type == "table" }),
           let candidate = pack.tableStyleEditCandidate,
           candidate.type == "table",
           !editableFormats.contains(where: { $0.id == candidate.id }) {
            editableFormats.append(candidate)
        }
        let initialDrafts = editableFormats.map { StyleEditDraft(format: $0) }
        _drafts = State(initialValue: initialDrafts)
        _selectedDraftID = State(initialValue: initialDrafts.first?.id)
        _schemeName = State(initialValue: "\(pack.name) · 自定义")
        _installedFontCatalog = State(initialValue: .cachedSystem)
        templateLatinFonts = templateFontOptions(from: editableFormats, role: .latin)
        templateEastAsiaFonts = templateFontOptions(from: editableFormats, role: .eastAsia)
    }

    private var filteredDrafts: [StyleEditDraft] {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return drafts }
        return drafts.filter {
            $0.format.name.localizedCaseInsensitiveContains(query) ||
                $0.format.styleID.localizedCaseInsensitiveContains(query) ||
                styleTypeText($0.format).localizedCaseInsensitiveContains(query) ||
                ($0.format.inferenceLabel?.localizedCaseInsensitiveContains(query) ?? false)
        }
    }

    private var selectedIndex: Int? {
        guard let selectedDraftID else { return nil }
        guard filteredDrafts.contains(where: { $0.id == selectedDraftID }) else { return nil }
        return drafts.firstIndex(where: { $0.id == selectedDraftID })
    }

    private var editedStyleCount: Int {
        drafts.filter(\.isEdited).count
    }

    private var dirtyStyleCount: Int {
        drafts.filter(\.hasUserInput).count
    }

    private var editedFieldCount: Int {
        drafts.reduce(0) { $0 + $1.changedFieldCount }
    }

    private var firstValidationError: String? {
        drafts.compactMap(\.validationError).first
    }

    private var normalizedSchemeName: String {
        schemeName.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var nameValidationError: String? {
        if normalizedSchemeName.isEmpty { return "请填写新格式方案的名称。" }
        if normalizedSchemeName.count > 120 { return "格式方案名称最多允许 120 个字符。" }
        return nil
    }

    private var request: StyleEditRequest? {
        guard nameValidationError == nil, firstValidationError == nil else { return nil }
        let payloads = drafts.compactMap(\.payload)
        return payloads.isEmpty ? nil : StyleEditRequest(styles: payloads)
    }

    private var canSave: Bool {
        request != nil && !isSubmitting && !model.isBusy
    }

    var body: some View {
        VStack(spacing: 0) {
            editorHeader
            Divider().overlay(Palette.line)
            HStack(spacing: 0) {
                editorSidebar
                    .frame(width: 265)
                Divider().overlay(Palette.line)
                if let selectedIndex {
                    StyleEditControls(
                        draft: $drafts[selectedIndex],
                        installedFontCatalog: $installedFontCatalog,
                        templateLatinFonts: templateLatinFonts,
                        templateEastAsiaFonts: templateEastAsiaFonts
                    )
                        .frame(minWidth: 330, maxWidth: .infinity, maxHeight: .infinity)
                    Divider().overlay(Palette.line)
                    StyleEditLivePreview(
                        draft: drafts[selectedIndex],
                        installedFontCatalog: installedFontCatalog,
                        templateLatinFonts: templateLatinFonts,
                        templateEastAsiaFonts: templateEastAsiaFonts
                    )
                        .frame(width: 330)
                        .frame(maxHeight: .infinity)
                } else {
                    VStack(spacing: 10) {
                        Image(systemName: "textformat")
                            .font(.system(size: 28))
                        Text("选择一种格式开始调整")
                    }
                    .foregroundStyle(Palette.mutedInk)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            Divider().overlay(Palette.line)
            editorFooter
        }
        .frame(minWidth: 930, idealWidth: 1080, minHeight: 650, idealHeight: 740)
        .background(Palette.paper)
        .foregroundStyle(Palette.ink)
        .disabled(model.isBusy)
        .accessibilityHidden(model.isBusy)
        .overlay {
            if model.isBusy {
                BusyOverlay(
                    message: model.busyMessage,
                    canCancel: model.canCancelBusyOperation,
                    isCancelling: model.isCancelling,
                    cancel: model.cancelCurrentOperation
                )
            }
        }
        .alert("无法保存格式方案", isPresented: $isShowingError) {
            Button("好") { isShowingError = false }
        } message: {
            Text(errorMessage)
        }
        .alert("放弃这些调整？", isPresented: $isConfirmingDiscard) {
            Button("继续编辑", role: .cancel) { }
            Button("放弃调整", role: .destructive) { dismiss() }
        } message: {
            Text("已经修改的格式还没有保存。关闭后，本次调整会丢失，原格式方案不会受到影响。")
        }
        .alert("重置全部格式调整？", isPresented: $isConfirmingResetAll) {
            Button("继续编辑", role: .cancel) { }
            Button("重置全部", role: .destructive) {
                resetHistory.reset(&drafts)
                editorNotice = "全部格式属性已恢复为原方案。可撤销本次重置。"
            }
        } message: {
            Text("将清除当前全部格式属性的调整，方案名称保持不变。开始新的修改前，可以撤销这次重置。")
        }
        .onChange(of: searchText) { _ in
            selectedDraftID = FormatSelectionPolicy.selectedID(
                current: selectedDraftID,
                visibleIDs: filteredDrafts.map(\.id)
            )
        }
        .onChange(of: dirtyStyleCount) { count in
            if count > 0 { resetHistory.discardUndoAfterNewInput() }
        }
        .interactiveDismissDisabled(dirtyStyleCount > 0 || model.isBusy)
        .onAppear { model.isEditingFormat = true }
        .onDisappear { model.isEditingFormat = false }
        .task {
            if !installedFontCatalog.isLoaded {
                installedFontCatalog = await .refreshSystem()
            }
        }
    }

    private var editorHeader: some View {
        HStack(spacing: 16) {
            ZStack {
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .fill(Palette.mint)
                Image(systemName: "paintbrush.pointed.fill")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(Palette.green)
            }
            .frame(width: 42, height: 42)

            VStack(alignment: .leading, spacing: 3) {
                Text("编辑格式方案")
                    .font(.system(size: 19, weight: .bold, design: .rounded))
                Text("从「\(pack.name)」派生新方案，原方案始终保持不变")
                    .font(.system(size: 11.5))
                    .foregroundStyle(Palette.mutedInk)
                    .lineLimit(1)
            }
            Spacer(minLength: 18)
            VStack(alignment: .leading, spacing: 4) {
                Text("新方案名称")
                    .font(.system(size: 10.5, weight: .semibold))
                    .foregroundStyle(Palette.mutedInk)
                TextField("填写方案名称", text: $schemeName)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 280)
                    .accessibilityLabel("新格式方案名称")
            }
        }
        .padding(.horizontal, 22)
        .frame(height: 78)
        .background(Color.white.opacity(0.38))
    }

    private var editorSidebar: some View {
        VStack(spacing: 0) {
            TextField("搜索格式", text: $searchText)
                .textFieldStyle(.roundedBorder)
                .padding(14)
                .accessibilityLabel("搜索可编辑格式")
            Divider().overlay(Palette.line)
            ScrollView {
                LazyVStack(spacing: 7) {
                    ForEach(filteredDrafts) { draft in
                        Button {
                            selectedDraftID = draft.id
                        } label: {
                            HStack(spacing: 10) {
                                Image(systemName: draft.isTable ? "tablecells" : "textformat")
                                    .font(.system(size: 12, weight: .semibold))
                                    .foregroundStyle(Palette.green)
                                    .frame(width: 28, height: 28)
                                    .background(Palette.mint)
                                    .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(draft.format.name)
                                        .font(.system(size: 12.5, weight: .semibold))
                                        .lineLimit(1)
                                    Text(
                                        draft.isOptionalTableCandidate
                                            ? "可选表格方案 · 修改后启用"
                                            : styleTypeText(draft.format)
                                    )
                                        .font(.system(size: 10))
                                        .foregroundStyle(Palette.mutedInk)
                                }
                                Spacer(minLength: 4)
                                if draft.validationError != nil && draft.hasUserInput {
                                    Image(systemName: "exclamationmark.triangle.fill")
                                        .font(.system(size: 10))
                                        .foregroundStyle(Palette.amber)
                                } else if draft.isEdited {
                                    Text("已改 \(draft.changedFieldCount)")
                                        .font(.system(size: 9.5, weight: .bold))
                                        .foregroundStyle(Palette.green)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 3)
                                        .background(Palette.mint)
                                        .clipShape(Capsule())
                                }
                            }
                            .padding(.horizontal, 9)
                            .frame(maxWidth: .infinity, minHeight: 48, alignment: .leading)
                            .background(
                                selectedDraftID == draft.id
                                    ? Palette.mint.opacity(0.82)
                                    : Color.white.opacity(0.54)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                            .overlay {
                                RoundedRectangle(cornerRadius: 10, style: .continuous)
                                    .stroke(
                                        selectedDraftID == draft.id
                                            ? Palette.green.opacity(0.48)
                                            : Palette.line.opacity(0.75),
                                        lineWidth: 1
                                    )
                            }
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("编辑 \(draft.format.name)")
                        .accessibilityAddTraits(selectedDraftID == draft.id ? .isSelected : [])
                        .accessibilityValue(
                            draft.validationError != nil && draft.hasUserInput
                                ? "修改内容需要修正"
                                : (draft.isEdited ? "已修改 \(draft.changedFieldCount) 项" : "未修改")
                        )
                    }
                }
                .padding(10)
            }
            if filteredDrafts.isEmpty {
                Text("没有匹配的格式")
                    .font(.system(size: 11.5))
                    .foregroundStyle(Palette.mutedInk)
                    .padding(.bottom, 14)
            }
        }
        .background(Color.white.opacity(0.28))
    }

    private var editorFooter: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                if let error = nameValidationError ?? firstValidationError {
                    Label(error, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(Palette.amber)
                } else if let editorNotice {
                    Label(editorNotice, systemImage: "info.circle")
                        .foregroundStyle(Palette.mutedInk)
                } else if editedStyleCount > 0 {
                    Text("已修改 \(editedStyleCount) 种格式、\(editedFieldCount) 个属性")
                        .foregroundStyle(Palette.green)
                } else if dirtyStyleCount > 0 {
                    Text("当前填写内容与原方案相同，尚无需要保存的变化。")
                        .foregroundStyle(Palette.mutedInk)
                } else {
                    Text("选择格式并修改属性；空白字段会继承原方案。")
                        .foregroundStyle(Palette.mutedInk)
                }
            }
            .font(.system(size: 11.5, weight: .medium))
            .lineLimit(2)

            Spacer()
            if resetHistory.canUndo {
                Button("撤销重置") {
                    resetHistory.undo(&drafts)
                    editorNotice = "已恢复重置之前的格式调整。"
                }
                .buttonStyle(SecondaryButtonStyle())
                .disabled(model.isBusy)
            }
            Button("重置全部") {
                isConfirmingResetAll = true
            }
            .buttonStyle(SecondaryButtonStyle())
            .disabled(dirtyStyleCount == 0 || model.isBusy)

            Button("取消") {
                if dirtyStyleCount > 0 {
                    isConfirmingDiscard = true
                } else {
                    dismiss()
                }
            }
            .buttonStyle(SecondaryButtonStyle())
            .keyboardShortcut(.cancelAction)
            .disabled(model.isBusy)

            Button {
                saveDerivedPack()
            } label: {
                Label("保存为新方案", systemImage: "square.and.arrow.down")
            }
            .buttonStyle(PrimaryButtonStyle())
            .keyboardShortcut(.defaultAction)
            .disabled(!canSave)
            .opacity(canSave ? 1 : 0.48)
            .accessibilityHint("保存为一套新的格式方案，不会覆盖原方案")
        }
        .padding(.horizontal, 18)
        .frame(minHeight: 66)
        .background(Color.white.opacity(0.44))
    }

    private func saveDerivedPack() {
        guard !isSubmitting, !model.isBusy, let request else { return }
        isSubmitting = true
        editorNotice = nil
        Task {
            defer { isSubmitting = false }
            do {
                _ = try await model.derivePack(
                    from: pack,
                    named: normalizedSchemeName,
                    request: request
                )
                dismiss()
            } catch is CancellationError {
                editorNotice = "保存已取消；原格式方案和格式库均未被覆盖。"
            } catch {
                errorMessage = error.localizedDescription
                isShowingError = true
            }
        }
    }
}

struct StyleEditControls: View {
    @Binding var draft: StyleEditDraft
    @Binding var installedFontCatalog: InstalledFontCatalog
    let templateLatinFonts: [TemplateFontOption]
    let templateEastAsiaFonts: [TemplateFontOption]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(draft.format.name)
                            .font(.system(size: 18, weight: .bold, design: .rounded))
                        Text("\(styleTypeText(draft.format)) · ID：\(draft.format.styleID)")
                            .font(.system(size: 10.5))
                            .foregroundStyle(Palette.mutedInk)
                            .lineLimit(1)
                    }
                    Spacer()
                    Button("重置此格式") { draft.reset() }
                        .buttonStyle(.plain)
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(Palette.green)
                        .disabled(!draft.hasUserInput)
                        .accessibilityHint("恢复这一个格式的全部属性")
                }

                Text("仅填写需要调整的属性；留空或选择“继承”会使用原方案。")
                    .font(.system(size: 11.5))
                    .foregroundStyle(Palette.mutedInk)
                    .padding(11)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Palette.mint.opacity(0.56))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))

                if draft.isOptionalTableCandidate {
                    Label(
                        "模板没有实际使用表格。只有修改并保存此方案后，它才会用于目标文档；不修改时仍保留目标表格外观。",
                        systemImage: "tablecells"
                    )
                    .font(.system(size: 11.5, weight: .medium))
                    .foregroundStyle(Palette.green)
                    .padding(11)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Palette.mint.opacity(0.68))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                }

                if draft.supportsTextFormatting {
                    StyleEditorSection(title: "字体", icon: "textformat") {
                        FontOverrideField(
                            label: "中文字体",
                            original: draft.format.fontEastAsia,
                            originalAliases: draft.format.fontEastAsiaAliases ?? [],
                            templateFonts: templateEastAsiaFonts,
                            value: $draft.fontEastAsiaOverride,
                            installedFontCatalog: $installedFontCatalog
                        )
                        FontOverrideField(
                            label: "西文字体",
                            original: draft.format.fontLatin,
                            originalAliases: draft.format.fontLatinAliases ?? [],
                            templateFonts: templateLatinFonts,
                            value: $draft.fontLatinOverride,
                            installedFontCatalog: $installedFontCatalog
                        )
                        HStack {
                            StyleEditorControlLabel("字号")
                            TextField(
                                draft.format.sizePt.map { "原方案 \(number($0)) pt" } ?? "继承原方案",
                                text: $draft.sizeOverride
                            )
                            .textFieldStyle(.roundedBorder)
                            .frame(maxWidth: 170)
                            .accessibilityLabel("字号")
                            Text("pt")
                                .font(.system(size: 11))
                                .foregroundStyle(Palette.mutedInk)
                        }
                        Text("支持 5–200 pt，并以 0.5 pt 递增。")
                            .font(.system(size: 10))
                            .foregroundStyle(Palette.mutedInk)
                            .padding(.leading, 98)
                    }

                    StyleEditorSection(title: "字形与颜色", icon: "bold") {
                        HStack {
                            StyleEditorControlLabel("粗细")
                            Picker("粗细", selection: $draft.boldChoice) {
                                ForEach(BoldEditChoice.allCases) { choice in
                                    Text(choice.label).tag(choice)
                                }
                            }
                            .labelsHidden()
                            .pickerStyle(.segmented)
                            .accessibilityLabel("字形粗细")
                        }
                        EditorColorField(
                            label: "文字颜色",
                            originalHex: draft.format.colorHex,
                            value: $draft.colorOverride,
                            fallbackHex: "19332F"
                        )
                    }

                    if draft.supportsParagraphFormatting {
                        if draft.supportsNumbering {
                            StyleEditorSection(title: "标题编号", icon: "list.number") {
                                HStack {
                                    StyleEditorControlLabel("数字形式")
                                    Picker("编号数字形式", selection: $draft.numberingFormatChoice) {
                                        ForEach(NumberingFormatEditChoice.allCases) { choice in Text(choice.label).tag(choice) }
                                    }.labelsHidden().pickerStyle(.menu)
                                }
                                HStack {
                                    StyleEditorControlLabel("格式与标点")
                                    TextField(draft.format.numberingPattern ?? "继承原方案", text: $draft.numberingPatternOverride)
                                        .textFieldStyle(.roundedBorder)
                                        .accessibilityLabel("编号格式与标点")
                                }
                                Text("当前层使用 %\((draft.format.numberingLevel ?? 0) + 1)，可引用上级编号；例如 %1.%2、（%2）或第%1章。")
                                    .font(.system(size: 10)).foregroundStyle(Palette.mutedInk)
                                ParagraphNumberField(label: "起始值", originalText: draft.format.numberingStart.map(String.init) ?? "原方案", value: $draft.numberingStartOverride, unit: "", accessibilityHint: "1 到 32767 的整数，留空不修改")
                                if (draft.format.numberingLevel ?? 0) > 0 {
                                    HStack {
                                        StyleEditorControlLabel("重启规则")
                                        Picker("编号重启规则", selection: $draft.numberingRestartChoice) {
                                            ForEach(NumberingRestartEditChoice.allCases) { choice in Text(choice.label).tag(choice) }
                                        }.labelsHidden().pickerStyle(.menu)
                                    }
                                }
                                EditorOriginalValue("原方案：\(draft.format.numberingExample ?? draft.format.numberingPattern ?? "已有编号")")
                            }
                        }
                        StyleEditorSection(title: "段落排列", icon: "text.alignleft") {
                            HStack(spacing: 8) {
                                StyleEditorControlLabel("对齐方式")
                                Picker("对齐方式", selection: $draft.alignmentChoice) {
                                    ForEach(ParagraphAlignmentEditChoice.allCases) { choice in
                                        Text(choice.label).tag(choice)
                                    }
                                }
                                .labelsHidden()
                                .pickerStyle(.menu)
                                .frame(maxWidth: 190)
                                .accessibilityLabel("段落对齐方式")
                                .accessibilityValue(
                                    draft.alignmentChoice == .unchanged
                                        ? "不修改，原方案\(paragraphAlignmentText(draft.format.alignment))"
                                        : draft.alignmentChoice.label
                                )
                                Spacer(minLength: 0)
                            }
                            EditorOriginalValue(
                                "原方案：\(paragraphAlignmentText(draft.format.alignment))"
                            )
                        }

                        StyleEditorSection(title: "间距与行距", icon: "line.3.horizontal") {
                            ParagraphNumberField(
                                label: "段前",
                                originalText: originalPointText(draft.format.spaceBeforePt),
                                value: $draft.spaceBeforeOverride,
                                unit: "pt",
                                accessibilityHint: "允许 0 到 1584 磅，留空保留原方案"
                            )
                            ParagraphNumberField(
                                label: "段后",
                                originalText: originalPointText(draft.format.spaceAfterPt),
                                value: $draft.spaceAfterOverride,
                                unit: "pt",
                                accessibilityHint: "允许 0 到 1584 磅，留空保留原方案"
                            )
                            HStack(spacing: 8) {
                                StyleEditorControlLabel("行距类型")
                                Picker("行距类型", selection: $draft.lineSpacingChoice) {
                                    ForEach(LineSpacingEditChoice.allCases) { choice in
                                        Text(choice.label).tag(choice)
                                    }
                                }
                                .labelsHidden()
                                .pickerStyle(.menu)
                                .frame(maxWidth: 190)
                                .accessibilityLabel("行距类型")
                                .accessibilityValue(
                                    draft.lineSpacingChoice == .unchanged
                                        ? "不修改，原方案\(paragraphLineSpacingText(value: draft.format.lineSpacing, rule: draft.format.lineRule))"
                                        : draft.lineSpacingChoice.label
                                )
                                Spacer(minLength: 0)
                            }
                            ParagraphNumberField(
                                label: "行距数值",
                                originalText: originalLineSpacingValue,
                                value: $draft.lineSpacingOverride,
                                unit: lineSpacingUnit,
                                accessibilityHint: lineSpacingHint
                            )
                            EditorOriginalValue(
                                "原方案：\(paragraphLineSpacingText(value: draft.format.lineSpacing, rule: draft.format.lineRule))"
                            )
                        }

                        StyleEditorSection(title: "缩进", icon: "arrow.left.and.right") {
                            HStack(spacing: 8) {
                                StyleEditorControlLabel("输入单位")
                                Picker("缩进输入单位", selection: $draft.indentUnit) {
                                    ForEach(ParagraphIndentUnit.allCases) { unit in
                                        Text(unit.fullLabel).tag(unit)
                                    }
                                }
                                .labelsHidden()
                                .pickerStyle(.segmented)
                                .frame(maxWidth: 190)
                                .accessibilityLabel("缩进输入单位")
                                .accessibilityValue(draft.indentUnit.fullLabel)
                                Spacer(minLength: 0)
                            }
                            ParagraphNumberField(
                                label: "左缩进",
                                originalText: originalIndentText(
                                    chars: draft.format.leftIndentChars,
                                    points: draft.format.leftIndentPt
                                ),
                                value: $draft.leftIndentOverride,
                                unit: draft.indentUnit.label,
                                accessibilityHint: indentSideHint
                            )
                            ParagraphNumberField(
                                label: "右缩进",
                                originalText: originalIndentText(
                                    chars: draft.format.rightIndentChars,
                                    points: draft.format.rightIndentPt
                                ),
                                value: $draft.rightIndentOverride,
                                unit: draft.indentUnit.label,
                                accessibilityHint: indentSideHint
                            )
                            HStack(spacing: 8) {
                                StyleEditorControlLabel("特殊格式")
                                Picker("特殊缩进格式", selection: $draft.specialIndentChoice) {
                                    ForEach(SpecialIndentEditChoice.allCases) { choice in
                                        Text(choice.label).tag(choice)
                                    }
                                }
                                .labelsHidden()
                                .pickerStyle(.menu)
                                .frame(maxWidth: 190)
                                .accessibilityLabel("特殊缩进格式")
                                .accessibilityValue(
                                    draft.specialIndentChoice == .unchanged
                                        ? "不修改，原方案\(paragraphSpecialIndentText(draft.format))"
                                        : draft.specialIndentChoice.label
                                )
                                Spacer(minLength: 0)
                            }
                            ParagraphNumberField(
                                label: "缩进值",
                                originalText: originalSpecialIndentValue,
                                value: $draft.specialIndentOverride,
                                unit: draft.indentUnit.label,
                                accessibilityHint: specialIndentHint,
                                isEnabled: draft.specialIndentChoice.requiresValue
                            )
                            EditorOriginalValue(
                                "原方案：\(paragraphIndentSidesText(draft.format))；\(paragraphSpecialIndentText(draft.format))"
                            )
                            Text(draft.indentUnitNotice ?? "字符单位可精确设置“首行缩进 2 字符”；切换单位会清空本次缩进输入，请按新单位重新填写。")
                                .font(.system(size: 10))
                                .foregroundStyle(Palette.mutedInk)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                } else if draft.isTable {
                    StyleEditorSection(title: "表格颜色", icon: "tablecells") {
                        EditorColorField(
                            label: "表格底色",
                            originalHex: draft.format.tableFillHex,
                            value: $draft.tableFillOverride,
                            fallbackHex: "FFFFFF"
                        )
                        EditorColorField(
                            label: "首行强调色",
                            originalHex: draft.format.tableAccentHex,
                            value: $draft.tableAccentOverride,
                            fallbackHex: "27685D"
                        )
                    }
                    StyleEditorSection(title: "表格边框", icon: "square.grid.3x3") {
                        HStack {
                            StyleEditorControlLabel("线型")
                            Picker("表格边框线型", selection: $draft.tableBorderChoice) {
                                ForEach(TableBorderEditChoice.allCases) { choice in Text(choice.label).tag(choice) }
                            }.labelsHidden().pickerStyle(.menu)
                        }
                        EditorColorField(label: "边框颜色", originalHex: draft.format.tableBorderColorHex, value: $draft.tableBorderColorOverride, fallbackHex: "000000")
                        ParagraphNumberField(label: "边框宽度", originalText: originalPointText(draft.format.tableBorderWidthPt), value: $draft.tableBorderWidthOverride, unit: "pt", accessibilityHint: "0.25 到 12 磅，0.125 磅递增")
                        Text("调整统一作用于外边框和内部横纵边框。留空的属性继续继承原方案。")
                            .font(.system(size: 10)).foregroundStyle(Palette.mutedInk)
                    }
                    StyleEditorSection(title: "单元格边距", icon: "arrow.up.left.and.arrow.down.right") {
                        ParagraphNumberField(label: "上边距", originalText: originalPointText(draft.format.tableCellMarginTopPt), value: $draft.tableMarginTopOverride, unit: "pt", accessibilityHint: "0 到 1584 磅，0.05 磅递增")
                        ParagraphNumberField(label: "下边距", originalText: originalPointText(draft.format.tableCellMarginBottomPt), value: $draft.tableMarginBottomOverride, unit: "pt", accessibilityHint: "0 到 1584 磅，0.05 磅递增")
                        ParagraphNumberField(label: "左边距", originalText: originalPointText(draft.format.tableCellMarginLeftPt), value: $draft.tableMarginLeftOverride, unit: "pt", accessibilityHint: "0 到 1584 磅，0.05 磅递增")
                        ParagraphNumberField(label: "右边距", originalText: originalPointText(draft.format.tableCellMarginRightPt), value: $draft.tableMarginRightOverride, unit: "pt", accessibilityHint: "0 到 1584 磅，0.05 磅递增")
                    }
                    Text("表格行高继续继承原方案；预览为示意，生成后请在 Word 中检查分页和表格布局。")
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    Label("此类格式暂不支持直接编辑。", systemImage: "lock")
                        .font(.system(size: 12))
                        .foregroundStyle(Palette.mutedInk)
                }

                if let error = draft.validationError {
                    Label(error, systemImage: "exclamationmark.triangle.fill")
                        .font(.system(size: 11.5, weight: .medium))
                        .foregroundStyle(Palette.amber)
                        .padding(11)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Palette.amberWash)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                }
            }
            .padding(20)
        }
        .background(Palette.paper.opacity(0.72))
    }

    private var originalLineSpacingValue: String {
        draft.format.lineSpacing.map(paragraphNumber) ?? "继承"
    }

    private var lineSpacingUnit: String {
        let rule = draft.lineSpacingChoice.encodedValue ??
            LineSpacingEditChoice.canonical(
                draft.format.lineRule,
                spacing: draft.format.lineSpacing
            ) ?? "auto"
        return rule == "auto" ? "倍" : "pt"
    }

    private var lineSpacingHint: String {
        lineSpacingUnit == "倍"
            ? "允许 0.5 到 10 倍，并以 0.01 递增；留空保留原方案"
            : "允许 1 到 1584 磅，并以 0.05 磅递增；留空保留原方案"
    }

    private var indentSideHint: String {
        draft.indentUnit == .characters
            ? "允许负 100 到 100 字符，并以 0.01 字符递增；留空保留原方案"
            : "允许负 1584 到 1584 磅，并以 0.05 磅递增；留空保留原方案"
    }

    private var specialIndentHint: String {
        draft.indentUnit == .characters
            ? "允许 0 到 100 字符，并以 0.01 字符递增"
            : "允许 0 到 1584 磅，并以 0.05 磅递增"
    }

    private var originalSpecialIndentValue: String {
        switch draft.originalSpecialIndentChoice {
        case .firstLine:
            return originalIndentText(
                chars: draft.format.firstLineIndentChars,
                points: draft.format.firstLineIndentPt
            )
        case .hanging:
            return originalIndentText(
                chars: draft.format.hangingIndentChars,
                points: draft.format.hangingIndentPt
            )
        case .none, .unchanged:
            return "无"
        }
    }

    private func originalPointText(_ value: Double?) -> String {
        value.map { "\(paragraphNumber($0)) pt" } ?? "继承"
    }

    private func originalIndentText(chars: Double?, points: Double?) -> String {
        if let chars { return "\(paragraphNumber(chars)) 字符" }
        if let points { return "\(paragraphNumber(points)) pt" }
        return "继承"
    }
}

struct StyleEditorSection<Content: View>: View {
    let title: String
    let icon: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            Label(title, systemImage: icon)
                .font(.system(size: 13.5, weight: .bold))
                .foregroundStyle(Palette.ink)
            content
        }
        .padding(15)
        .background(Color.white.opacity(0.76))
        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .stroke(Palette.line, lineWidth: 1)
        }
    }
}

struct StyleEditorControlLabel: View {
    let text: String

    init(_ text: String) {
        self.text = text
    }

    var body: some View {
        Text(text)
            .font(.system(size: 11.5, weight: .semibold))
            .foregroundStyle(Palette.mutedInk)
            .frame(width: 86, alignment: .leading)
    }
}

struct ParagraphNumberField: View {
    let label: String
    let originalText: String
    @Binding var value: String
    let unit: String
    let accessibilityHint: String
    var isEnabled = true

    var body: some View {
        HStack(spacing: 8) {
            StyleEditorControlLabel(label)
            TextField(
                isEnabled ? "原方案 \(originalText)" : "无需填写",
                text: $value
            )
            .textFieldStyle(.roundedBorder)
            .frame(maxWidth: 170)
            .disabled(!isEnabled)
            .accessibilityLabel("\(label)，单位\(unit)")
            .accessibilityValue(
                value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    ? (isEnabled ? "不修改，原方案 \(originalText)" : "无需填写")
                    : "\(value) \(unit)"
            )
            .accessibilityHint(accessibilityHint)
            Text(unit)
                .font(.system(size: 11))
                .foregroundStyle(Palette.mutedInk)
                .frame(minWidth: 24, alignment: .leading)
                .accessibilityHidden(true)
            if isEnabled && !value.isEmpty {
                Button {
                    value = ""
                } label: {
                    Image(systemName: "arrow.uturn.backward.circle")
                }
                .buttonStyle(.plain)
                .foregroundStyle(Palette.mutedInk)
                .help("恢复原方案")
                .accessibilityLabel("恢复\(label)原值")
            }
        }
    }
}

struct EditorOriginalValue: View {
    let text: String

    init(_ text: String) {
        self.text = text
    }

    var body: some View {
        Text(text)
            .font(.system(size: 10))
            .foregroundStyle(Palette.mutedInk)
            .padding(.leading, 98)
            .fixedSize(horizontal: false, vertical: true)
    }
}

struct FontOverrideField: View {
    let label: String
    let original: String?
    let originalAliases: [String]
    let templateFonts: [TemplateFontOption]
    @Binding var value: String
    @Binding var installedFontCatalog: InstalledFontCatalog
    @State private var isShowingPicker = false
    @State private var searchText = ""

    private var allTemplateFonts: [TemplateFontOption] {
        guard let original = normalizedFontName(original) else { return templateFonts }
        let key = fontStrictLookupKey(original)
        if templateFonts.contains(where: { $0.id == key }) { return templateFonts }
        return ([TemplateFontOption(name: original, aliases: originalAliases)] + templateFonts)
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    private var activeName: String? {
        normalizedFontName(value) ?? normalizedFontName(original)
    }

    private var activeAliases: [String] {
        guard let activeName else { return [] }
        if fontStrictLookupKey(activeName) == fontStrictLookupKey(original ?? "") {
            return originalAliases
        }
        return allTemplateFonts.first {
            fontStrictLookupKey($0.name) == fontStrictLookupKey(activeName)
        }?.aliases ?? []
    }

    private var activeMatch: InstalledFontMatch {
        installedFontCatalog.match(name: activeName, aliases: activeAliases)
    }

    private var originalMatch: InstalledFontMatch {
        installedFontCatalog.match(name: original, aliases: originalAliases)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 8) {
                StyleEditorControlLabel(label)
                TextField(
                    original.map { "原方案 \($0)" } ?? "继承主题字体",
                    text: $value
                )
                .textFieldStyle(.roundedBorder)
                .accessibilityLabel(label)
                Button {
                    searchText = ""
                    isShowingPicker = true
                } label: {
                    Image(systemName: "magnifyingglass")
                        .frame(width: 22, height: 22)
                }
                .buttonStyle(.borderless)
                .frame(width: 28)
                .help("搜索模板字体、本机字体或 PostScript 名")
                .accessibilityLabel("搜索并选择\(label)")
                .popover(isPresented: $isShowingPicker, arrowEdge: .bottom) {
                    FontPickerPopover(
                        label: label,
                        original: original,
                        originalAliases: originalAliases,
                        templateFonts: allTemplateFonts,
                        value: $value,
                        installedFontCatalog: $installedFontCatalog,
                        searchText: $searchText,
                        isPresented: $isShowingPicker
                    )
                }
                if !value.isEmpty {
                    Button {
                        value = ""
                    } label: {
                        Image(systemName: "arrow.uturn.backward.circle")
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(Palette.mutedInk)
                    .help("恢复原方案")
                    .accessibilityLabel("恢复\(label)原值")
                }
            }

            HStack(spacing: 6) {
                Text(original.map { "原方案：\($0)" } ?? "原方案：继承主题字体")
                    .lineLimit(1)
                FontRegistrationBadge(match: originalMatch)
            }
            .font(.system(size: 10))
            .foregroundStyle(Palette.mutedInk)
            .padding(.leading, 98)
            .accessibilityElement(children: .combine)

            if !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                HStack(spacing: 6) {
                    Text("当前选择：\(activeName ?? value)")
                        .lineLimit(1)
                    FontRegistrationBadge(match: activeMatch)
                }
                .font(.system(size: 10))
                .foregroundStyle(Palette.mutedInk)
                .padding(.leading, 98)
                .accessibilityElement(children: .combine)

                if activeMatch.kind == .ambiguous &&
                    !activeMatch.candidateFamilyNames.isEmpty {
                    Text("候选字体：\(activeMatch.candidateFamilyNames.joined(separator: "、"))")
                        .font(.system(size: 10))
                        .foregroundStyle(Palette.amber)
                        .padding(.leading, 98)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }
}

struct FontPickerPopover: View {
    let label: String
    let original: String?
    let originalAliases: [String]
    let templateFonts: [TemplateFontOption]
    @Binding var value: String
    @Binding var installedFontCatalog: InstalledFontCatalog
    @Binding var searchText: String
    @Binding var isPresented: Bool
    @FocusState private var isSearchFocused: Bool
    @State private var isRefreshingFonts = false

    private var filteredTemplateFonts: [TemplateFontOption] {
        let originalKey = normalizedFontName(original).map(fontStrictLookupKey)
        return templateFonts.filter {
            $0.id != originalKey && $0.matches(searchText)
        }
    }

    private var filteredInstalledFonts: [InstalledFontFamily] {
        let matches = installedFontCatalog.search(searchText)
        guard let originalKey = normalizedFontName(original).map(fontStrictLookupKey) else {
            return matches
        }
        return matches.filter {
            fontStrictLookupKey($0.canonicalFamilyName) != originalKey
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                TextField("搜索字体、中文名或 PostScript 名", text: $searchText)
                    .textFieldStyle(.roundedBorder)
                    .accessibilityLabel("搜索\(label)")
                    .focused($isSearchFocused)
                Button {
                    isRefreshingFonts = true
                    Task {
                        installedFontCatalog = await .refreshSystem()
                        isRefreshingFonts = false
                    }
                } label: {
                    if isRefreshingFonts { ProgressView().controlSize(.small) }
                    else { Image(systemName: "arrow.clockwise") }
                }
                .disabled(isRefreshingFonts)
                .buttonStyle(.borderless)
                .help("刷新本机字体")
                .accessibilityLabel("刷新本机字体")
            }
            .padding(12)

            Divider().overlay(Palette.line)

            Label(
                "本机未注册的字体可能仅由 Microsoft Word 提供；可保留原名，但程序预览会使用系统字体。",
                systemImage: "info.circle"
            )
            .font(.system(size: 10))
            .foregroundStyle(Palette.mutedInk)
            .padding(.horizontal, 12)
            .padding(.vertical, 9)
            .frame(maxWidth: .infinity, alignment: .leading)

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 7) {
                    FontPickerSectionLabel("原方案")
                    FontChoiceButton(
                        title: original ?? "继承主题字体",
                        detail: "保持模板中的原始设置，不重写字体名称",
                        match: installedFontCatalog.match(
                            name: original,
                            aliases: originalAliases
                        ),
                        isSelected: value.isEmpty
                    ) {
                        value = ""
                        isPresented = false
                    }

                    if !filteredTemplateFonts.isEmpty {
                        FontPickerSectionLabel("模板中使用的字体")
                        ForEach(filteredTemplateFonts) { option in
                            FontChoiceButton(
                                title: option.name,
                                detail: option.aliases.isEmpty
                                    ? "保留模板原始字体名称"
                                    : "别名：\(option.aliases.joined(separator: "、"))",
                                match: installedFontCatalog.match(
                                    name: option.name,
                                    aliases: option.aliases
                                ),
                                isSelected: fontStrictLookupKey(value) == option.id
                            ) {
                                value = option.name
                                isPresented = false
                            }
                        }
                    }

                    FontPickerSectionLabel("本机已安装字体")
                    if filteredInstalledFonts.isEmpty {
                        Text("没有匹配的本机字体。仍可直接输入模板字体名称。")
                            .font(.system(size: 11))
                            .foregroundStyle(Palette.mutedInk)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 10)
                    } else {
                        ForEach(filteredInstalledFonts) { family in
                            FontChoiceButton(
                                title: family.displayName,
                                detail: family.secondaryDescription,
                                match: InstalledFontMatch(
                                    kind: .installed,
                                    canonicalFamilyName: family.canonicalFamilyName,
                                    postScriptName: family.preferredPostScriptName,
                                    candidateFamilyNames: [family.canonicalFamilyName]
                                ),
                                isSelected: fontStrictLookupKey(value) ==
                                    fontStrictLookupKey(family.canonicalFamilyName)
                            ) {
                                // OOXML expects a family name.  PostScript names remain
                                // searchable aliases and are used only for local preview.
                                value = family.canonicalFamilyName
                                isPresented = false
                            }
                        }
                    }
                }
                .padding(10)
            }
        }
        .frame(width: 430, height: 520)
        .background(Palette.paper)
        .onAppear { isSearchFocused = true }
        .onExitCommand { isPresented = false }
    }
}

struct FontPickerSectionLabel: View {
    let title: String

    init(_ title: String) {
        self.title = title
    }

    var body: some View {
        Text(title)
            .font(.system(size: 10.5, weight: .semibold))
            .foregroundStyle(Palette.mutedInk)
            .padding(.horizontal, 8)
            .padding(.top, 8)
            .accessibilityAddTraits(.isHeader)
    }
}

struct FontChoiceButton: View {
    let title: String
    let detail: String
    let match: InstalledFontMatch
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(isSelected ? Palette.green : Palette.mutedInk)
                    .frame(width: 18)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(Palette.ink)
                        .lineLimit(1)
                    if !detail.isEmpty {
                        Text(detail)
                            .font(.system(size: 9.5))
                            .foregroundStyle(Palette.mutedInk)
                            .lineLimit(2)
                    }
                    if match.kind == .ambiguous && !match.candidateFamilyNames.isEmpty {
                        Text("候选：\(match.candidateFamilyNames.joined(separator: "、"))")
                            .font(.system(size: 9.5))
                            .foregroundStyle(Palette.amber)
                            .lineLimit(2)
                    }
                }
                Spacer(minLength: 6)
                FontRegistrationBadge(match: match)
            }
            .padding(.horizontal, 9)
            .padding(.vertical, 8)
            .background(isSelected ? Palette.mint.opacity(0.8) : Color.white.opacity(0.62))
            .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(title)
        .accessibilityValue(
            [
                isSelected ? "已选择" : nil,
                fontRegistrationText(match),
                detail.isEmpty ? nil : detail,
                match.kind == .ambiguous && !match.candidateFamilyNames.isEmpty
                    ? "候选\(match.candidateFamilyNames.joined(separator: "、"))"
                    : nil
            ]
            .compactMap { $0 }
            .joined(separator: "，")
        )
    }
}

struct FontRegistrationBadge: View {
    let match: InstalledFontMatch

    var body: some View {
        Label(fontRegistrationText(match), systemImage: fontRegistrationIcon(match))
            .font(.system(size: 9, weight: .semibold))
            .foregroundStyle(fontRegistrationColor(match))
            .lineLimit(1)
    }
}

func fontRegistrationText(_ match: InstalledFontMatch) -> String {
    switch match.kind {
    case .loading: return "正在读取本机字体"
    case .inherited:
        return "继承主题"
    case .installed:
        return "已安装"
    case .alias:
        return match.canonicalFamilyName.map { "别名匹配：\($0)" } ?? "别名匹配"
    case .ambiguous:
        return "匹配冲突"
    case .missing:
        return "本机未注册"
    }
}

func fontRegistrationIcon(_ match: InstalledFontMatch) -> String {
    switch match.kind {
    case .loading: return "hourglass"
    case .inherited: return "arrow.triangle.branch"
    case .installed: return "checkmark.circle.fill"
    case .alias: return "link.circle.fill"
    case .ambiguous: return "exclamationmark.triangle.fill"
    case .missing: return "arrow.triangle.2.circlepath.circle"
    }
}

func fontRegistrationColor(_ match: InstalledFontMatch) -> Color {
    switch match.kind {
    case .loading: return Palette.mutedInk
    case .inherited: return Palette.mutedInk
    case .installed, .alias: return Palette.green
    case .ambiguous: return Palette.amber
    case .missing: return Palette.mutedInk
    }
}

struct EditorColorField: View {
    let label: String
    let originalHex: String?
    @Binding var value: String
    let fallbackHex: String

    private var effectiveHex: String {
        normalizedHexColor(value) ?? normalizedHexColor(originalHex ?? "") ?? fallbackHex
    }

    private var colorBinding: Binding<Color> {
        Binding(
            get: { Color(hex: effectiveHex) },
            set: { value = hexString(from: $0) ?? effectiveHex }
        )
    }

    var body: some View {
        HStack(spacing: 8) {
            StyleEditorControlLabel(label)
            ColorPicker("选择\(label)", selection: colorBinding, supportsOpacity: false)
                .labelsHidden()
                .frame(width: 28)
            TextField(
                originalHex.map { "原方案 #\($0)" } ?? "继承原方案",
                text: $value
            )
            .textFieldStyle(.roundedBorder)
            .frame(maxWidth: 150)
            .accessibilityLabel("\(label)十六进制值")
            Text("#RRGGBB")
                .font(.system(size: 9.5, design: .monospaced))
                .foregroundStyle(Palette.mutedInk)
            if !value.isEmpty {
                Button {
                    value = ""
                } label: {
                    Image(systemName: "arrow.uturn.backward.circle")
                }
                .buttonStyle(.plain)
                .foregroundStyle(Palette.mutedInk)
                .help("恢复原方案")
                .accessibilityLabel("恢复\(label)原值")
            }
        }
    }
}

struct StyleEditLivePreview: View {
    let draft: StyleEditDraft
    let installedFontCatalog: InstalledFontCatalog
    let templateLatinFonts: [TemplateFontOption]
    let templateEastAsiaFonts: [TemplateFontOption]

    private var eastAsiaMatch: InstalledFontMatch {
        installedFontCatalog.match(
            name: draft.effectiveFontEastAsia,
            aliases: templateAliases(
                for: draft.effectiveFontEastAsia,
                in: templateEastAsiaFonts
            )
        )
    }

    private var latinMatch: InstalledFontMatch {
        installedFontCatalog.match(
            name: draft.effectiveFontLatin,
            aliases: templateAliases(
                for: draft.effectiveFontLatin,
                in: templateLatinFonts
            )
        )
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("实时示意")
                        .font(.system(size: 16, weight: .bold, design: .rounded))
                    Text("用于比较视觉方向；最终效果以 Word 生成结果为准。")
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if draft.isTable {
                    tablePreview
                } else {
                    textPreview
                }

                VStack(spacing: 0) {
                    PreviewPropertyRow(label: "格式", value: draft.format.name)
                    if draft.supportsTextFormatting {
                        PreviewPropertyRow(
                            label: "中文字体",
                            value: draft.effectiveFontEastAsia ?? "继承主题"
                        )
                        PreviewPropertyRow(
                            label: "西文字体",
                            value: draft.effectiveFontLatin ?? "继承主题"
                        )
                        PreviewPropertyRow(
                            label: "中文预览",
                            value: localPreviewDescription(
                                requestedName: draft.effectiveFontEastAsia,
                                match: eastAsiaMatch
                            )
                        )
                        PreviewPropertyRow(
                            label: "英文预览",
                            value: localPreviewDescription(
                                requestedName: draft.effectiveFontLatin,
                                match: latinMatch
                            )
                        )
                        PreviewPropertyRow(
                            label: "字号",
                            value: draft.effectiveSize.map { "\(number($0)) pt" } ?? "继承"
                        )
                        PreviewPropertyRow(
                            label: "字形",
                            value: draft.effectiveBold == true ? "粗体" : "常规"
                        )
                        PreviewPropertyRow(
                            label: "文字颜色",
                            value: draft.effectiveColorHex.map { "#\($0)" } ?? "自动"
                        )
                        if draft.supportsParagraphFormatting {
                            if draft.supportsNumbering {
                                PreviewPropertyRow(label: "编号格式", value: draft.numberingPatternOverride.isEmpty ? (draft.format.numberingPattern ?? "继承") : draft.numberingPatternOverride)
                                PreviewPropertyRow(label: "编号起始", value: draft.numberingStartOverride.isEmpty ? (draft.format.numberingStart.map(String.init) ?? "继承") : draft.numberingStartOverride)
                                PreviewPropertyRow(label: "编号数字", value: draft.numberingFormatChoice == .unchanged ? (draft.format.numberingFormat ?? "继承") : draft.numberingFormatChoice.label)
                            }
                            PreviewPropertyRow(
                                label: "对齐",
                                value: paragraphAlignmentText(draft.effectiveAlignment)
                            )
                            PreviewPropertyRow(
                                label: "段前 / 段后",
                                value: paragraphSpacingText(
                                    before: draft.effectiveSpaceBeforePt,
                                    after: draft.effectiveSpaceAfterPt
                                )
                            )
                            PreviewPropertyRow(
                                label: "行距",
                                value: paragraphLineSpacingText(
                                    value: draft.effectiveLineSpacing,
                                    rule: draft.effectiveLineRule
                                )
                            )
                            PreviewPropertyRow(
                                label: "左 / 右缩进",
                                value: paragraphIndentSidesText(
                                    left: draft.effectiveLeftIndent,
                                    right: draft.effectiveRightIndent
                                )
                            )
                            PreviewPropertyRow(
                                label: "特殊缩进",
                                value: paragraphSpecialIndentText(
                                    choice: draft.effectiveSpecialIndentChoice,
                                    measurement: draft.effectiveSpecialIndent
                                )
                            )
                        }
                    } else if draft.isTable {
                        PreviewPropertyRow(
                            label: "表格底色",
                            value: draft.effectiveTableFillHex.map { "#\($0)" } ?? "继承"
                        )
                        PreviewPropertyRow(
                            label: "首行强调",
                            value: draft.effectiveTableAccentHex.map { "#\($0)" } ?? "继承"
                        )
                        PreviewPropertyRow(label: "边框线型", value: draft.tableBorderChoice == .unchanged ? (draft.format.tableBorderStyle ?? "继承") : draft.tableBorderChoice.label)
                        PreviewPropertyRow(label: "边框宽度", value: draft.tableBorderWidthOverride.isEmpty ? (draft.format.tableBorderWidthPt.map { "\(number($0)) pt" } ?? "继承") : "\(draft.tableBorderWidthOverride) pt")
                        PreviewPropertyRow(label: "单元格边距", value: "上 \(draft.tableMarginTopOverride.isEmpty ? originalMargin(draft.format.tableCellMarginTopPt) : draft.tableMarginTopOverride) · 下 \(draft.tableMarginBottomOverride.isEmpty ? originalMargin(draft.format.tableCellMarginBottomPt) : draft.tableMarginBottomOverride) · 左 \(draft.tableMarginLeftOverride.isEmpty ? originalMargin(draft.format.tableCellMarginLeftPt) : draft.tableMarginLeftOverride) · 右 \(draft.tableMarginRightOverride.isEmpty ? originalMargin(draft.format.tableCellMarginRightPt) : draft.tableMarginRightOverride) pt")
                    }
                }
                .background(Color.white.opacity(0.64))
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

                if draft.isEdited {
                    Label(
                        "此格式已修改 \(draft.changedFieldCount) 个属性",
                        systemImage: "checkmark.circle.fill"
                    )
                    .font(.system(size: 11.5, weight: .semibold))
                    .foregroundStyle(Palette.green)
                }
            }
            .padding(20)
        }
        .background(Color.white.opacity(0.32))
    }

    private var textPreview: some View {
        let size = min(max(draft.effectiveSize ?? 16, 11), 34)
        return VStack(alignment: .leading, spacing: 11) {
            if draft.supportsParagraphFormatting {
                ParagraphStyleTextPreview(
                    draft: draft,
                    installedFontCatalog: installedFontCatalog,
                    templateLatinFonts: templateLatinFonts,
                    templateEastAsiaFonts: templateEastAsiaFonts
                )
                    .frame(maxWidth: .infinity, minHeight: 138, maxHeight: 168)
                    .accessibilityHidden(true)
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    previewTextLine(
                        "中文字体预览示意",
                        match: eastAsiaMatch,
                        size: size
                    )
                    previewTextLine(
                        "English Typography Aa 123",
                        match: latinMatch,
                        size: size
                    )
                }
                .frame(maxWidth: .infinity, minHeight: 94, alignment: .leading)
            }
            Rectangle()
                .fill(Palette.line)
                .frame(height: 1)
            Text("Forma 赋式 · Typography Preview")
                .font(.system(size: 10.5))
                .foregroundStyle(Palette.mutedInk)
        }
        .padding(17)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(Palette.line, lineWidth: 1)
        }
        .shadow(color: Palette.ink.opacity(0.06), radius: 10, y: 4)
    }

    private func originalMargin(_ value: Double?) -> String {
        value.map(number) ?? "继承"
    }

    private func previewTextLine(
        _ text: String,
        match: InstalledFontMatch,
        size: Double
    ) -> some View {
        Text(text)
            .font(
                match.postScriptName.map { .custom($0, size: size) } ??
                    .system(size: size)
            )
            .fontWeight(draft.effectiveBold == true ? .bold : .regular)
            .italic(draft.format.italic == true)
            .foregroundStyle(draft.effectiveColorHex.map(Color.init(hex:)) ?? Palette.ink)
            .lineLimit(2)
    }

    private var tablePreview: some View {
        let fill = Color(hex: draft.effectiveTableFillHex ?? "FFFFFF")
        let accent = Color(hex: draft.effectiveTableAccentHex ?? "27685D")
        return VStack(spacing: 1) {
            previewTableRow(values: ["项目", "说明", "状态"], fill: accent, isHeader: true)
            previewTableRow(values: ["标题", "格式规范", "完成"], fill: fill, isHeader: false)
            previewTableRow(values: ["正文", "字体与颜色", "检查"], fill: fill, isHeader: false)
        }
        .padding(1)
        .background(Palette.line)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(Palette.line, lineWidth: 1)
        }
    }

    private func previewTableRow(values: [String], fill: Color, isHeader: Bool) -> some View {
        HStack(spacing: 1) {
            ForEach(values, id: \.self) { value in
                Text(value)
                    .font(.system(size: 10.5, weight: isHeader ? .bold : .regular))
                    .foregroundStyle(isHeader ? Color.white : Palette.ink)
                    .frame(maxWidth: .infinity, minHeight: 38)
                    .background(fill)
            }
        }
    }
}

struct ParagraphStyleTextPreview: NSViewRepresentable {
    let draft: StyleEditDraft
    let installedFontCatalog: InstalledFontCatalog
    let templateLatinFonts: [TemplateFontOption]
    let templateEastAsiaFonts: [TemplateFontOption]

    func makeNSView(context: Context) -> NSTextView {
        let textView = NSTextView(frame: .zero)
        textView.isEditable = false
        textView.isSelectable = false
        textView.drawsBackground = false
        textView.textContainerInset = .zero
        textView.textContainer?.lineFragmentPadding = 0
        textView.textContainer?.widthTracksTextView = true
        textView.isHorizontallyResizable = false
        textView.isVerticallyResizable = true
        textView.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        return textView
    }

    func updateNSView(_ textView: NSTextView, context: Context) {
        let size = min(max(draft.effectiveSize ?? 16, 11), 34)
        let eastAsiaFont = previewFont(
            requestedName: draft.effectiveFontEastAsia,
            aliases: templateAliases(
                for: draft.effectiveFontEastAsia,
                in: templateEastAsiaFonts
            ),
            size: size
        )
        let latinFont = previewFont(
            requestedName: draft.effectiveFontLatin,
            aliases: templateAliases(
                for: draft.effectiveFontLatin,
                in: templateLatinFonts
            ),
            size: size
        )

        let paragraphStyle = NSMutableParagraphStyle()
        paragraphStyle.alignment = nsTextAlignment(draft.effectiveAlignment)
        paragraphStyle.paragraphSpacingBefore = CGFloat(
            min(max(draft.effectiveSpaceBeforePt ?? 0, 0), 42)
        )
        paragraphStyle.paragraphSpacing = CGFloat(
            min(max(draft.effectiveSpaceAfterPt ?? 0, 0), 42)
        )

        if let lineSpacing = draft.effectiveLineSpacing {
            switch draft.effectiveLineRule ?? "auto" {
            case "exact":
                let height = CGFloat(min(max(lineSpacing, 1), 80))
                paragraphStyle.minimumLineHeight = height
                paragraphStyle.maximumLineHeight = height
            case "atLeast":
                paragraphStyle.minimumLineHeight = CGFloat(min(max(lineSpacing, 1), 80))
            default:
                paragraphStyle.lineHeightMultiple = CGFloat(min(max(lineSpacing, 0.5), 3))
            }
        }

        let left = previewIndentPoints(draft.effectiveLeftIndent, fontSize: size)
        let right = max(0, previewIndentPoints(draft.effectiveRightIndent, fontSize: size))
        let special = max(0, previewIndentPoints(draft.effectiveSpecialIndent, fontSize: size))
        paragraphStyle.headIndent = CGFloat(left)
        paragraphStyle.firstLineHeadIndent = CGFloat(left)
        paragraphStyle.tailIndent = CGFloat(-right)
        switch draft.effectiveSpecialIndentChoice {
        case .firstLine:
            paragraphStyle.firstLineHeadIndent = CGFloat(left + special)
        case .hanging:
            paragraphStyle.headIndent = CGFloat(left + special)
        case .none, .unchanged:
            break
        }

        let eastAsiaText = "中文标题与正文格式示意。这是一段用于观察自动换行和缩进的文字。"
        let latinText = "English typography preview Aa 123. Compare spacing and line height."
        let previewText = eastAsiaText + "\n" + latinText
        let color = draft.effectiveColorHex.flatMap(nsColorFromHex) ?? NSColor.labelColor
        let attributed = NSMutableAttributedString(
            string: previewText,
            attributes: [
                .foregroundColor: color,
                .paragraphStyle: paragraphStyle
            ]
        )
        attributed.addAttribute(
            .font,
            value: eastAsiaFont,
            range: NSRange(location: 0, length: (eastAsiaText as NSString).length)
        )
        let latinLocation = (eastAsiaText as NSString).length + 1
        attributed.addAttribute(
            .font,
            value: latinFont,
            range: NSRange(
                location: latinLocation,
                length: (latinText as NSString).length
            )
        )
        textView.textStorage?.setAttributedString(attributed)
    }

    private func previewFont(
        requestedName: String?,
        aliases: [String],
        size: Double
    ) -> NSFont {
        let match = installedFontCatalog.match(name: requestedName, aliases: aliases)
        var font = match.postScriptName.flatMap {
            NSFont(name: $0, size: CGFloat(size))
        } ?? NSFont.systemFont(ofSize: CGFloat(size))
        if draft.effectiveBold == true {
            font = NSFontManager.shared.convert(font, toHaveTrait: .boldFontMask)
        }
        if draft.format.italic == true {
            font = NSFontManager.shared.convert(font, toHaveTrait: .italicFontMask)
        }
        return font
    }

    private func previewIndentPoints(
        _ measurement: ParagraphIndentMeasurement?,
        fontSize: Double
    ) -> Double {
        guard let measurement else { return 0 }
        return min(max(measurement.previewPoints(fontSize: fontSize), -24), 120)
    }

    private func nsTextAlignment(_ value: String?) -> NSTextAlignment {
        switch ParagraphAlignmentEditChoice.canonical(value) {
        case "center": return .center
        case "right": return .right
        case "both", "distribute": return .justified
        default: return .left
        }
    }

    private func nsColorFromHex(_ value: String) -> NSColor? {
        guard let normalized = normalizedHexColor(value),
              let rgb = UInt64(normalized, radix: 16) else { return nil }
        return NSColor(
            red: CGFloat((rgb >> 16) & 0xFF) / 255,
            green: CGFloat((rgb >> 8) & 0xFF) / 255,
            blue: CGFloat(rgb & 0xFF) / 255,
            alpha: 1
        )
    }
}

struct PreviewPropertyRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(label).foregroundStyle(Palette.mutedInk)
            Spacer(minLength: 8)
            Text(value)
                .foregroundStyle(Palette.ink)
                .lineLimit(2)
                .multilineTextAlignment(.trailing)
        }
        .font(.system(size: 10.5))
        .padding(.horizontal, 11)
        .padding(.vertical, 8)
        .overlay(alignment: .bottom) {
            Rectangle().fill(Palette.line.opacity(0.65)).frame(height: 1)
        }
    }
}
