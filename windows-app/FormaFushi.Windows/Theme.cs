/**
 * [INPUT]: 依赖 System.ComponentModel, System.Drawing.Drawing2D
 * [OUTPUT]: 提供 Theme, CardPanel
 * [POS]: 提供 Windows 统一视觉样式与卡片
 * [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
using System.ComponentModel;
using System.Drawing.Drawing2D;

namespace FormaFushi.Windows;

internal static class Theme
{
    public static readonly Color Ink = ColorTranslator.FromHtml("#19332F");
    public static readonly Color MutedInk = ColorTranslator.FromHtml("#687873");
    public static readonly Color Green = ColorTranslator.FromHtml("#27685D");
    public static readonly Color GreenDeep = ColorTranslator.FromHtml("#184D45");
    public static readonly Color Mint = ColorTranslator.FromHtml("#DDEBE5");
    public static readonly Color Paper = ColorTranslator.FromHtml("#F5F2EA");
    public static readonly Color Card = Color.White;
    public static readonly Color Line = ColorTranslator.FromHtml("#D8DED9");
    public static readonly Color Amber = ColorTranslator.FromHtml("#B96B2C");
    public static readonly Color AmberWash = ColorTranslator.FromHtml("#FFF0DB");
    public static readonly Color Success = ColorTranslator.FromHtml("#2B735C");
    public static readonly Color Sidebar = ColorTranslator.FromHtml("#EEEFE9");
    public static readonly Font UiFont = CreateFont(9.5f);

    public static Font CreateFont(
        float pointSize,
        FontStyle style = FontStyle.Regular,
        string family = "Microsoft YaHei UI")
    {
        const float pixelsPerPointAt96Dpi = 96f / 72f;
        return new Font(family, pointSize * pixelsPerPointAt96Dpi, style, GraphicsUnit.Pixel);
    }

    public static Button PrimaryButton(string text)
    {
        var button = BaseButton(text);
        button.BackColor = Green;
        button.ForeColor = Color.White;
        button.FlatAppearance.BorderSize = 0;
        return button;
    }

    public static Button SecondaryButton(string text)
    {
        var button = BaseButton(text);
        button.BackColor = Color.White;
        button.ForeColor = GreenDeep;
        button.FlatAppearance.BorderColor = Line;
        button.FlatAppearance.BorderSize = 1;
        return button;
    }

    public static Button TextButton(string text)
    {
        var button = BaseButton(text);
        button.BackColor = Color.Transparent;
        button.ForeColor = Green;
        button.FlatAppearance.BorderSize = 0;
        return button;
    }

    private static Button BaseButton(string text)
    {
        return new Button
        {
            Text = text,
            Font = CreateFont(9.5f, FontStyle.Bold),
            Height = 38,
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            Padding = new Padding(15, 0, 15, 0),
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
            UseVisualStyleBackColor = false
        };
    }

    public static Label Label(string text, float size = 9.5f, FontStyle style = FontStyle.Regular, Color? color = null)
    {
        return new Label
        {
            Text = text,
            AutoSize = true,
            Font = CreateFont(size, style),
            ForeColor = color ?? Ink,
            BackColor = Color.Transparent
        };
    }

    public static void DrawRoundedRectangle(Graphics graphics, Rectangle bounds, int radius, Color fill, Color? border = null)
    {
        using var path = RoundedPath(bounds, radius);
        graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using var brush = new SolidBrush(fill);
        graphics.FillPath(brush, path);
        if (border.HasValue)
        {
            using var pen = new Pen(border.Value);
            graphics.DrawPath(pen, path);
        }
    }

    private static GraphicsPath RoundedPath(Rectangle bounds, int radius)
    {
        var diameter = radius * 2;
        var path = new GraphicsPath();
        path.AddArc(bounds.Left, bounds.Top, diameter, diameter, 180, 90);
        path.AddArc(bounds.Right - diameter, bounds.Top, diameter, diameter, 270, 90);
        path.AddArc(bounds.Right - diameter, bounds.Bottom - diameter, diameter, diameter, 0, 90);
        path.AddArc(bounds.Left, bounds.Bottom - diameter, diameter, diameter, 90, 90);
        path.CloseFigure();
        return path;
    }
}

internal sealed class CardPanel : Panel
{
    [DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
    public Color BorderColor { get; set; } = Theme.Line;

    [DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
    public int Radius { get; set; } = 12;

    public CardPanel()
    {
        BackColor = Theme.Card;
        Padding = new Padding(18);
        DoubleBuffered = true;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        Theme.DrawRoundedRectangle(e.Graphics, new Rectangle(0, 0, Width - 1, Height - 1), Radius, BackColor, BorderColor);
    }
}
