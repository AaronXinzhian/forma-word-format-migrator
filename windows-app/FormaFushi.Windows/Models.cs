using System.Text.Json.Serialization;
using FormaFushi.Windows.Generated;

namespace FormaFushi.Windows;

/// <summary>可以直接呈现给用户的失败，对应 Swift 侧的 AppFailure。</summary>
internal sealed class AppFailure(string message) : Exception(message);

internal sealed class ManagerEnvelope
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("error")]
    public string? Error { get; set; }

    [JsonPropertyName("pack")]
    public PackManifest? Pack { get; set; }

    [JsonPropertyName("packs")]
    public List<PackManifest>? Packs { get; set; }

    [JsonPropertyName("output")]
    public string? Output { get; set; }

    [JsonPropertyName("errors")]
    public List<LibraryReadError>? Errors { get; set; }

    [JsonPropertyName("stats")]
    public TransferStats? Stats { get; set; }
}

internal sealed class LibraryReadError
{
    [JsonPropertyName("path")]
    public string Path { get; set; } = "";

    [JsonPropertyName("error")]
    public string Error { get; set; } = "";
}

internal sealed class PackManifest
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = "";

    // 引擎必定输出 name/sample，Swift 侧对应字段也是非可选的；
    // 这里的空串只是 C# 需要的初始值，不是会被用户看到的兜底文案。
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("created_at")]
    public string? CreatedAt { get; set; }

    [JsonPropertyName("used_formats")]
    public List<UsedFormat> UsedFormats { get; set; } = [];

    [JsonPropertyName("used_style_count")]
    public int UsedStyleCount { get; set; }

    [JsonPropertyName("inferred_style_count")]
    public int? InferredStyleCount { get; set; }

    [JsonPropertyName("defined_style_count")]
    public int? DefinedStyleCount { get; set; }

    [JsonPropertyName("hidden_style_count")]
    public int? HiddenStyleCount { get; set; }

    [JsonPropertyName("heading_numbering_conflicts")]
    public List<string>? HeadingNumberingConflicts { get; set; }

    [JsonPropertyName("heading_completion_warnings")]
    public List<string>? HeadingCompletionWarnings { get; set; }

    [JsonPropertyName("manual_formatting")]
    public ManualFormatting ManualFormatting { get; set; } = new();

    [JsonPropertyName("document_summary")]
    public DocumentSummary DocumentSummary { get; set; } = new();

    [JsonPropertyName("page_layout")]
    public PageLayout PageLayout { get; set; } = new();

    [JsonPropertyName("pack_path")]
    public string? PackPath { get; set; }

    public string LibraryIdentity => PackPath ?? Id;

    public int InferredCount => InferredStyleCount ?? 0;

    public int HiddenCount => HiddenStyleCount
        ?? Math.Max(0, (DefinedStyleCount ?? UsedStyleCount) - UsedStyleCount);

    public bool HasNumberedHeadings =>
        UsedFormats.Any(format => format.Type == "paragraph" && format.OutlineLevel.HasValue && format.Numbered);

    public bool HasTableStyles => UsedFormats.Any(format => format.Type == "table");

    public string CreatedDisplay
    {
        get
        {
            if (DateTimeOffset.TryParse(CreatedAt, out var value))
            {
                return value.ToLocalTime().ToString("yyyy/MM/dd");
            }

            return UIStrings.Sidebar.PackDateUnknown;
        }
    }

    public void Normalize()
    {
        UsedFormats ??= [];
        ManualFormatting ??= new ManualFormatting();
        DocumentSummary ??= new DocumentSummary();
        PageLayout ??= new PageLayout();
    }
}

internal sealed class UsedFormat
{
    [JsonPropertyName("style_id")]
    public string StyleId { get; set; } = "";

    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("usage_count")]
    public int UsageCount { get; set; }

    [JsonPropertyName("inferred")]
    public bool? Inferred { get; set; }

    [JsonPropertyName("inference_label")]
    public string? InferenceLabel { get; set; }

    [JsonPropertyName("sample")]
    public string Sample { get; set; } = "";

    [JsonPropertyName("font_latin")]
    public string? FontLatin { get; set; }

    [JsonPropertyName("font_east_asia")]
    public string? FontEastAsia { get; set; }

    [JsonPropertyName("size_pt")]
    public double? SizePt { get; set; }

    [JsonPropertyName("bold")]
    public bool? Bold { get; set; }

    [JsonPropertyName("italic")]
    public bool? Italic { get; set; }

    [JsonPropertyName("color_hex")]
    public string? ColorHex { get; set; }

    [JsonPropertyName("alignment")]
    public string? Alignment { get; set; }

    [JsonPropertyName("space_before_pt")]
    public double? SpaceBeforePt { get; set; }

    [JsonPropertyName("space_after_pt")]
    public double? SpaceAfterPt { get; set; }

    [JsonPropertyName("line_spacing")]
    public double? LineSpacing { get; set; }

    [JsonPropertyName("line_rule")]
    public string? LineRule { get; set; }

    [JsonPropertyName("outline_level")]
    public int? OutlineLevel { get; set; }

    [JsonPropertyName("numbered")]
    public bool Numbered { get; set; }

    [JsonPropertyName("numbering_level")]
    public int? NumberingLevel { get; set; }

    [JsonPropertyName("numbering_format")]
    public string? NumberingFormat { get; set; }

    [JsonPropertyName("numbering_pattern")]
    public string? NumberingPattern { get; set; }

    [JsonPropertyName("numbering_example")]
    public string? NumberingExample { get; set; }

    [JsonPropertyName("table_fill_hex")]
    public string? TableFillHex { get; set; }

    [JsonPropertyName("table_accent_hex")]
    public string? TableAccentHex { get; set; }

    public string Identity => $"{Type}:{StyleId}";
}

internal sealed class ManualFormatting
{
    [JsonPropertyName("paragraph_count")]
    public int ParagraphCount { get; set; }

    [JsonPropertyName("run_count")]
    public int RunCount { get; set; }
}

internal sealed class DocumentSummary
{
    [JsonPropertyName("paragraph_count")]
    public int ParagraphCount { get; set; }

    [JsonPropertyName("run_count")]
    public int RunCount { get; set; }

    [JsonPropertyName("table_count")]
    public int TableCount { get; set; }

    [JsonPropertyName("section_count")]
    public int SectionCount { get; set; }
}

internal sealed class PageLayout
{
    [JsonPropertyName("width_cm")]
    public double? WidthCm { get; set; }

    [JsonPropertyName("height_cm")]
    public double? HeightCm { get; set; }

    [JsonPropertyName("orientation")]
    public string? Orientation { get; set; }

    [JsonPropertyName("margin_top_cm")]
    public double? MarginTopCm { get; set; }

    [JsonPropertyName("margin_bottom_cm")]
    public double? MarginBottomCm { get; set; }

    [JsonPropertyName("margin_left_cm")]
    public double? MarginLeftCm { get; set; }

    [JsonPropertyName("margin_right_cm")]
    public double? MarginRightCm { get; set; }
}

internal sealed class TransferStats
{
    [JsonPropertyName("warnings")]
    public List<string>? Warnings { get; set; }
}
