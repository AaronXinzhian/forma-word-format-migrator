namespace FormaFushi.Windows;

/// <summary>
/// 带自定义按钮文案的确认框。
///
/// <see cref="MessageBox"/> 只能用系统的「确定 / 取消」，无法呈现「移到回收站」这种
/// 明确说明后果的动词，而 Mac 端的 NSAlert 可以。为了两端确认对话框的语义一致，
/// 这里自己画一个。
/// </summary>
internal static class ConfirmDialog
{
    public static bool Show(
        IWin32Window owner,
        string title,
        string message,
        string confirmText,
        string cancelText,
        bool destructive = false)
    {
        using var form = new Form
        {
            Text = title,
            FormBorderStyle = FormBorderStyle.FixedDialog,
            StartPosition = FormStartPosition.CenterParent,
            MinimizeBox = false,
            MaximizeBox = false,
            ShowInTaskbar = false,
            ClientSize = new Size(460, 196),
            BackColor = Color.White,
            Font = Theme.UiFont
        };

        var heading = Theme.Label(title, 12, FontStyle.Bold);
        heading.AutoSize = false;
        heading.SetBounds(24, 22, 412, 28);

        var body = Theme.Label(message, 9.5f, color: Theme.MutedInk);
        body.AutoSize = false;
        body.SetBounds(24, 56, 412, 76);

        var confirm = destructive ? Theme.SecondaryButton(confirmText) : Theme.PrimaryButton(confirmText);
        confirm.AutoSize = false;
        confirm.Size = new Size(140, 38);
        confirm.Location = new Point(296, 142);
        confirm.DialogResult = DialogResult.OK;
        if (destructive)
        {
            confirm.ForeColor = Theme.Amber;
        }

        var cancel = Theme.SecondaryButton(cancelText);
        cancel.AutoSize = false;
        cancel.Size = new Size(110, 38);
        cancel.Location = new Point(176, 142);
        cancel.DialogResult = DialogResult.Cancel;

        form.Controls.Add(heading);
        form.Controls.Add(body);
        form.Controls.Add(confirm);
        form.Controls.Add(cancel);
        form.AcceptButton = cancel;
        form.CancelButton = cancel;

        return form.ShowDialog(owner) == DialogResult.OK;
    }
}
