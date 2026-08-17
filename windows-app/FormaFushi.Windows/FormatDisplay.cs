using System.Globalization;
using FormaFushi.Windows.Generated;

namespace FormaFushi.Windows;

/// <summary>
/// 格式属性的取值逻辑，与 swift-app/Views/StyleInspector.swift 的 FormatDisplay 一一对应。
/// 两端只要有一边改了取值规则，另一边就必须同步改这里。
/// </summary>
internal static class FormatDisplay
{
    public static string Number(double value)
    {
        return Math.Abs(value - Math.Round(value)) < 0.0001
            ? ((int)Math.Round(value)).ToString(CultureInfo.InvariantCulture)
            : value.ToString("0.#", CultureInfo.InvariantCulture);
    }

    public static string Usage(UsedFormat format)
    {
        return format.Inferred == true
            ? Fallback(format.InferenceLabel, UIStrings.FormatList.UsageInferred)
            : UIStrings.FormatList.UsageCount(format.UsageCount.ToString(CultureInfo.InvariantCulture));
    }

    public static string Source(UsedFormat format)
    {
        return format.Inferred == true
            ? Fallback(format.InferenceLabel, UIStrings.FormatList.UsageInferred)
            : UIStrings.Inspector.SourceUsedCount(format.UsageCount.ToString(CultureInfo.InvariantCulture));
    }

    public static string Type(UsedFormat format)
    {
        if (format.OutlineLevel.HasValue)
        {
            return UIStrings.Inspector.TypeHeading(
                (format.OutlineLevel.Value + 1).ToString(CultureInfo.InvariantCulture));
        }

        return format.Type switch
        {
            "character" => UIStrings.Inspector.TypeCharacter,
            "table" => UIStrings.Inspector.TypeTable,
            _ => UIStrings.Inspector.TypeParagraph
        };
    }

    public static string Traits(UsedFormat format)
    {
        var traits = new List<string>();
        if (format.Bold == true)
        {
            traits.Add(UIStrings.Inspector.TraitBold);
        }

        if (format.Italic == true)
        {
            traits.Add(UIStrings.Inspector.TraitItalic);
        }

        return traits.Count == 0
            ? UIStrings.Inspector.TraitRegular
            : string.Join(UIStrings.Inspector.TraitSeparator, traits);
    }

    public static string Alignment(string? value) => value switch
    {
        "center" => UIStrings.Inspector.AlignCenter,
        "right" or "end" => UIStrings.Inspector.AlignRight,
        "both" => UIStrings.Inspector.AlignJustify,
        "distribute" => UIStrings.Inspector.AlignDistribute,
        "left" or "start" => UIStrings.Inspector.AlignLeft,
        _ => UIStrings.Inspector.Inherit
    };

    public static string Spacing(UsedFormat format)
    {
        if (!format.SpaceBeforePt.HasValue && !format.SpaceAfterPt.HasValue)
        {
            return UIStrings.Inspector.Inherit;
        }

        return UIStrings.Inspector.SpacingValue(
            Number(format.SpaceBeforePt ?? 0),
            Number(format.SpaceAfterPt ?? 0));
    }

    public static string LineSpacing(UsedFormat format)
    {
        if (!format.LineSpacing.HasValue)
        {
            return UIStrings.Inspector.Inherit;
        }

        var value = Number(format.LineSpacing.Value);
        return format.LineRule is null or "auto"
            ? UIStrings.Inspector.LineSpacingMultiple(value)
            : UIStrings.Inspector.LineSpacingExact(value);
    }

    public static string Numbering(UsedFormat format)
    {
        if (!format.Numbered)
        {
            return UIStrings.Inspector.NumberingNone;
        }

        var example = Fallback(format.NumberingExample, format.NumberingPattern ?? "");
        return string.IsNullOrWhiteSpace(example)
            ? UIStrings.Inspector.NumberingPlain
            : UIStrings.Inspector.NumberingWithExample(example);
    }

    public static string Size(double? value)
    {
        return value.HasValue
            ? UIStrings.Inspector.SizeValue(Number(value.Value))
            : UIStrings.Inspector.Inherit;
    }

    public static string FontSummary(UsedFormat format)
    {
        var family = Fallback(
            format.FontEastAsia,
            Fallback(format.FontLatin, UIStrings.FormatList.InheritFont));
        var size = format.SizePt.HasValue
            ? UIStrings.Inspector.SizeValue(Number(format.SizePt.Value))
            : UIStrings.FormatList.InheritSize;
        return $"{family} / {size}";
    }

    public static string NumberingCell(UsedFormat format)
    {
        return format.Numbered
            ? Fallback(format.NumberingExample, Fallback(format.NumberingPattern, UIStrings.Inspector.NumberingPlain))
            : "—";
    }

    public static string Hex(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? UIStrings.Inspector.Inherit : $"#{value}";
    }

    public static string Optional(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? UIStrings.Inspector.Inherit : value;
    }

    public static string Orientation(string? value)
    {
        return value == "landscape"
            ? UIStrings.Inspector.PageOrientationLandscape
            : UIStrings.Inspector.PageOrientationPortrait;
    }

    public static string PageSize(PageLayout layout)
    {
        return layout.WidthCm.HasValue && layout.HeightCm.HasValue
            ? UIStrings.Inspector.PageSizeValue(Number(layout.WidthCm.Value), Number(layout.HeightCm.Value))
            : UIStrings.Inspector.PageSizeDefault;
    }

    public static string Centimeters(double? value)
    {
        return value.HasValue
            ? UIStrings.Inspector.CentimeterValue(Number(value.Value))
            : UIStrings.Inspector.Inherit;
    }

    private static string Fallback(string? value, string fallback)
    {
        return string.IsNullOrWhiteSpace(value) ? fallback : value;
    }
}

/// <summary>
/// 处理说明按格式包内容动态生成，规则与 swift-app/Views/ApplyStepView.swift 的 ApplyNotes 相同。
/// </summary>
internal static class ApplyNotes
{
    public static IReadOnlyList<string> For(PackManifest? pack)
    {
        var notes = new List<string>
        {
            UIStrings.ApplyStep.NoteKeepContent,
            UIStrings.ApplyStep.NoteCleanup
        };

        if ((pack?.InferredCount ?? 0) > 0)
        {
            notes.Add(UIStrings.ApplyStep.NoteInferredHeadings);
        }

        notes.Add(UIStrings.ApplyStep.NoteSaveAsNew);

        if (pack?.HasNumberedHeadings == true)
        {
            notes.Add(UIStrings.ApplyStep.NoteNumbering);
            notes.Add(UIStrings.ApplyStep.NoteManualPrefix);
        }

        if (pack is not null && !pack.HasTableStyles)
        {
            notes.Add(UIStrings.ApplyStep.NoteTableFallback);
        }

        return notes;
    }
}
