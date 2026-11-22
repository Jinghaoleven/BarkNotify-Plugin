"""Render a credential-free illustration of the plugin's notification payloads."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve().parent
SCALE = 2
SIZE = (1440, 660)
FONT_DIR = Path('/usr/share/fonts/truetype/dejavu')


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')), size * SCALE)


def box(coords):
    return tuple(round(value * SCALE) for value in coords)


def label(draw, xy, value, size, color, bold=False):
    draw.text((xy[0] * SCALE, xy[1] * SCALE), value, font=font(size, bold), fill=color)


image = Image.new('RGB', tuple(v * SCALE for v in SIZE), '#f4f5f7')
draw = ImageDraw.Draw(image)

# Soft background and a stylized iOS notification surface.
for y in range(SIZE[1] * SCALE):
    ratio = y / (SIZE[1] * SCALE)
    draw.line((0, y, SIZE[0] * SCALE, y), fill=(round(246 - ratio * 6), round(248 - ratio * 7), round(250 - ratio * 6)))

draw.rounded_rectangle(box((66, 72, 276, 112)), radius=20 * SCALE, fill='#e1e8ee')
label(draw, (85, 81), 'CODEX CLI  /  SSH', 17, '#3d5262', True)
label(draw, (66, 154), 'Remote sessions.', 47, '#162632', True)
label(draw, (66, 216), 'Timely updates.', 47, '#162632', True)
label(draw, (69, 310), 'Bark notifications on iOS', 23, '#4d606d')
label(draw, (69, 347), 'for remote Codex CLI sessions.', 23, '#4d606d')

# Small terminal cue, without any user content or infrastructure identifiers.
draw.rounded_rectangle(box((69, 431, 565, 557)), radius=18 * SCALE, fill='#e8edf1')
label(draw, (93, 452), '> codex', 20, '#264f63', True)
label(draw, (93, 491), 'Stay informed away from the terminal.', 18, '#52646f')

shadow = Image.new('RGBA', image.size)
sd = ImageDraw.Draw(shadow)
sd.rounded_rectangle(box((654, 46, 1376, 614)), radius=34 * SCALE, fill=(12, 30, 49, 45))
shadow = shadow.filter(ImageFilter.GaussianBlur(18 * SCALE))
image = Image.alpha_composite(image.convert('RGBA'), shadow)
draw = ImageDraw.Draw(image)
draw.rounded_rectangle(box((642, 38, 1368, 602)), radius=32 * SCALE, fill='#1e3548')
label(draw, (678, 65), 'iOS notification preview', 18, '#bdceda')
label(draw, (1195, 64), '9:41', 20, '#eaf2f8', True)


def card(y, title, lines):
    height = 184 if len(lines) == 2 else 202
    draw.rounded_rectangle(box((674, y, 1336, y + height)), radius=22 * SCALE, fill='#f2f5f7')
    draw.rounded_rectangle(box((694, y + 17, 727, y + 50)), radius=9 * SCALE, fill='#49677a')
    # A neutral bell indicates the notification app; this is an illustration.
    draw.arc(box((703, y + 23, 718, y + 39)), 180, 360, fill='white', width=2 * SCALE)
    draw.line(box((703, y + 31, 703, y + 41)), fill='white', width=2 * SCALE)
    draw.line(box((718, y + 31, 718, y + 41)), fill='white', width=2 * SCALE)
    draw.line(box((700, y + 41, 721, y + 41)), fill='white', width=2 * SCALE)
    draw.ellipse(box((708, y + 44, 713, y + 47)), fill='white')
    label(draw, (741, y + 23), 'BARK', 15, '#5b6b76', True)
    label(draw, (1277, y + 23), 'now', 15, '#7b8790')
    label(draw, (694, y + 63), title, 24, '#172b39', True)
    for index, line in enumerate(lines):
        label(draw, (694, y + 105 + index * 27), line, 18, '#455762')


card(123, 'training · Turn ended', ['Status: Turn ended', 'Project: training'])
card(335, 'training · Approval requested', ['Status: Approval requested', 'Project: training', 'Tool: exec_command'])
label(draw, (678, 568), 'Illustration · Actual presentation depends on iOS settings.', 15, '#c1d0db')
image.convert('RGB').resize(SIZE, Image.Resampling.LANCZOS).save(HERE / 'notification-preview.png', optimize=True)
