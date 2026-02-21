"""Branded HTML email templates for Ilm Atlas."""

# Brand colors (from frontend theme)
_BG = "#F7F6F4"
_PRIMARY = "#1A1816"
_TEXT = "#1A1816"
_MUTED = "#716B63"
_BORDER = "#E8E3DD"
_CARD_BG = "#FFFFFF"
_BUTTON_BG = "#1A1816"
_BUTTON_TEXT = "#F7F6F4"


def _base_template(content: str, preview_text: str) -> str:
    """Wrap email content in the branded base layout."""
    return f"""\
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>Ilm Atlas</title>
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings>
        <o:PixelsPerInch>96</o:PixelsPerInch>
      </o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <![endif]-->
</head>
<body style="margin:0;padding:0;background-color:{_BG};font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased;">
  <!-- Preview text (hidden) -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preview_text}</div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_BG};">
    <tr>
      <td align="center" style="padding:40px 16px;">

        <!-- Header -->
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">
          <tr>
            <td align="center" style="padding-bottom:24px;">
              <span style="font-size:22px;font-weight:700;color:{_PRIMARY};letter-spacing:0.5px;font-family:Georgia,'Times New Roman',serif;">Ilm Atlas</span>
            </td>
          </tr>
        </table>

        <!-- Card -->
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background-color:{_CARD_BG};border:1px solid {_BORDER};border-radius:12px;">
          <tr>
            <td style="padding:40px 36px;">
              {content}
            </td>
          </tr>
        </table>

        <!-- Footer -->
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">
          <tr>
            <td align="center" style="padding-top:28px;">
              <p style="margin:0;font-size:13px;color:{_MUTED};line-height:20px;">
                &copy; 2026 Ilm Atlas
              </p>
            </td>
          </tr>
        </table>

      </td>
    </tr>
  </table>
</body>
</html>"""


def _button(text: str, url: str) -> str:
    """Render a styled CTA button."""
    return f"""\
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:28px 0;">
  <tr>
    <td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center" style="background-color:{_BUTTON_BG};border-radius:8px;">
      <!--[if mso]>
      <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" href="{url}" style="height:48px;width:220px;v-text-anchor:middle;" arcsize="17%" fillcolor="{_BUTTON_BG}">
        <w:anchorlock/>
        <center style="color:{_BUTTON_TEXT};font-size:15px;font-weight:600;">{text}</center>
      </v:roundrect>
      <![endif]-->
      <!--[if !mso]><!-->
      <a href="{url}" target="_blank" style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:600;color:{_BUTTON_TEXT};text-decoration:none;border-radius:8px;background-color:{_BUTTON_BG};font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">{text}</a>
      <!--<![endif]-->
        </td>
      </tr>
    </table>
    </td>
  </tr>
</table>"""


def _heading(text: str) -> str:
    return f'<h2 style="margin:0 0 16px;font-size:20px;font-weight:600;color:{_TEXT};font-family:Georgia,\'Times New Roman\',serif;">{text}</h2>'


def _paragraph(text: str) -> str:
    return f'<p style="margin:0 0 14px;font-size:15px;line-height:24px;color:{_TEXT};">{text}</p>'


def _muted_paragraph(text: str, center: bool = False) -> str:
    align = "text-align:center;" if center else ""
    return f'<p style="margin:0 0 14px;font-size:13px;line-height:20px;color:{_MUTED};{align}">{text}</p>'


def _divider() -> str:
    return f'<hr style="border:none;border-top:1px solid {_BORDER};margin:24px 0;">'


def verification_email(name: str, verify_url: str, expire_hours: int) -> str:
    """Render the email verification email."""
    content = (
        _heading(f"Asalaamalikum {name},")
        + _paragraph("Welcome to Ilm Atlas! Please verify your email address to get started.")
        + _button("Verify Email Address", verify_url)
        + _muted_paragraph(f"This link expires in {expire_hours} hours.", center=True)
        + _divider()
        + _muted_paragraph("If you didn't create an account, you can safely ignore this email.")
    )
    return _base_template(content, preview_text="Verify your email to get started with Ilm Atlas")


def password_reset_email(name: str, reset_url: str, expire_hours: int) -> str:
    """Render the password reset email."""
    content = (
        _heading(f"Asalaamalikum {name},")
        + _paragraph("We received a request to reset your password. Use the button below to choose a new one.")
        + _button("Reset Password", reset_url)
        + _muted_paragraph(f"This link expires in {expire_hours} hour{'s' if expire_hours != 1 else ''}.", center=True)
        + _divider()
        + _muted_paragraph("If you didn't request this, you can safely ignore this email &mdash; your password will remain unchanged.")
    )
    return _base_template(content, preview_text="Reset your Ilm Atlas password")
