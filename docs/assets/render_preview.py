"""Render public examples using invented text, without reading device screenshots.

Requires Pillow and a system Latin font; Chinese rendering also needs PingFang,
Heiti, or Noto Sans CJK. Run this file to regenerate both README illustrations.
"""

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve().parent
SIZE = (1600, 960)
SCALE = 2


@lru_cache(maxsize=None)
def font(size, bold=False, chinese=False):
    if chinese:
        candidates = list(Path('/System/Library/AssetsV2').glob(
            'com_apple_MobileAsset_Font*/**/PingFang.ttc'))
        candidates += [
            Path('/System/Library/Fonts/PingFang.ttc'),
            Path('/System/Library/Fonts/STHeiti Medium.ttc' if bold else
                 '/System/Library/Fonts/STHeiti Light.ttc'),
            Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc' if bold else
                 '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
        ]
    else:
        candidates = [
            Path('/System/Library/Fonts/SFNS.ttf'),
            Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        ]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise RuntimeError('Install Noto Sans CJK and DejaVu Sans to render the previews.')
    index = 0
    if path.name == 'PingFang.ttc':
        index = 11 if bold else 3
    elif path.name.startswith('NotoSansCJK-'):
        index = 2
    result = ImageFont.truetype(str(path), size * SCALE, index=index)
    try:
        result.set_variation_by_name('Bold' if bold else 'Regular')
    except (AttributeError, OSError, ValueError):
        pass
    return result


def box(coords):
    return tuple(round(v * SCALE) for v in coords)


def text(draw, xy, value, size, color, bold=False, chinese=False):
    draw.text(box(xy), value, font=font(size, bold, chinese), fill=color, anchor='lt')


def fit_title(value, width, size, chinese):
    face = font(size, True, chinese)
    if face.getlength(value) <= width * SCALE:
        return value
    while face.getlength(value + '…') > width * SCALE:
        value = value[:-1]
    return value.rstrip() + '…'


def bark_icon(draw, x, y, size):
    """Draw Bark's recognizable red notification icon as simple shapes."""
    draw.rounded_rectangle(box((x, y, x + size, y + size)), radius=22 * SCALE,
                           fill='#ff3b30', outline='#ff685c', width=SCALE)
    def shape(points):
        draw.polygon([box((x + a * size, y + b * size)) for a, b in points], fill='white')
    shape(((.10, .41), (.17, .38), (.17, .63)))
    shape(((.20, .34), (.36, .39), (.36, .61), (.20, .66)))
    shape(((.40, .43), (.64, .43), (.64, .57), (.40, .57)))
    shape(((.68, .39), (.84, .34), (.84, .66), (.68, .61)))
    shape(((.87, .38), (.94, .41), (.87, .63)))


def render(language):
    chinese = language == 'zh'
    image = Image.new('RGB', box(SIZE))
    draw = ImageDraw.Draw(image)
    for y in range(image.height):
        ratio = y / image.height
        draw.line((0, y, image.width, y), fill=(round(246 - 7 * ratio),
                                               round(249 - 7 * ratio),
                                               round(250 - 6 * ratio)))

    # Product copy is outside the simulated iOS surface.
    draw.rounded_rectangle(box((80, 98, 350, 143)), radius=22 * SCALE, fill='#e2eceb')
    text(draw, (101, 112), 'BARKNOTIFY  /  CODEX', 18, '#315c5b', True)
    heading = ('会话动态，', '手机可见。') if chinese else ('Your Codex session.', 'On your iPhone.')
    for index, line in enumerate(heading):
        text(draw, (80, 215 + 80 * index), line, 56 if chinese else 51,
             '#172d34', True, chinese)
    description = ('本轮结束或需要审批时，', '通过 Bark 在 iPhone 上接收通知。') if chinese else (
        'Turn ends. Approval requests.', 'Delivered through Bark.')
    for index, line in enumerate(description):
        text(draw, (84, 426 + index * 38), line, 24, '#52676e', chinese=chinese)

    draw.rounded_rectangle(box((84, 579, 578, 726)), radius=24 * SCALE, fill='#e6edee')
    text(draw, (110, 606), '> codex', 25, '#2e595d', True)
    text(draw, (110, 658), '离开终端，也能及时回来。' if chinese else
         'Step away. Stay in the loop.', 23, '#52676e', chinese=chinese)
    text(draw, (84, 820), '中文 / English' if chinese else 'English / 中文',
         22, '#52676e', chinese=True)

    # Abstract wallpaper is generated here. No pixels from a private screenshot
    # or wallpaper, status-bar identity, or notification history are retained.
    panel_size = (840 * SCALE, 864 * SCALE)
    panel = Image.new('RGB', panel_size)
    pd = ImageDraw.Draw(panel)
    for y in range(panel.height):
        t = y / panel.height
        pd.line((0, y, panel.width, y), fill=(round(36 - 20 * t),
                                            round(66 - 35 * t),
                                            round(79 - 40 * t)))
    glow = Image.new('RGBA', panel_size)
    gd = ImageDraw.Draw(glow)
    gd.ellipse(box((-240, 240, 560, 1160)), fill=(103, 150, 142, 95))
    gd.ellipse(box((400, -80, 1050, 610)), fill=(140, 182, 204, 60))
    glow = glow.filter(ImageFilter.GaussianBlur(95 * SCALE))
    panel = Image.alpha_composite(panel.convert('RGBA'), glow)
    mask = Image.new('L', panel_size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *panel_size), radius=48 * SCALE, fill=255)
    shadow = Image.new('RGBA', image.size)
    ImageDraw.Draw(shadow).rounded_rectangle(box((704, 62, 1544, 926)),
                                            radius=48 * SCALE, fill=(16, 39, 48, 52))
    image = Image.alpha_composite(image.convert('RGBA'),
                                 shadow.filter(ImageFilter.GaussianBlur(16 * SCALE)))
    image.paste(panel, box((700, 48)), mask)
    draw = ImageDraw.Draw(image)

    text(draw, (745, 83), '9:41', 25, '#f4f7f8', True)
    for i, height in enumerate((8, 12, 17, 22)):
        draw.rounded_rectangle(box((1390 + i * 8, 110 - height, 1395 + i * 8, 110)),
                               radius=2 * SCALE, fill='#f4f7f8')
    draw.rounded_rectangle(box((1450, 88, 1493, 110)), radius=6 * SCALE,
                           outline='#d6e0e4', width=2 * SCALE)
    draw.rounded_rectangle(box((1454, 92, 1484, 106)), radius=3 * SCALE, fill='#f4f7f8')
    draw.rectangle(box((1495, 95, 1498, 103)), fill='#d6e0e4')
    text(draw, (745, 159), 'Bark', 41, '#f5f7f8')
    draw.rounded_rectangle(box((1351, 148, 1456, 205)), radius=28 * SCALE,
                           fill='#496472', outline='#73919e', width=SCALE)
    text(draw, (1373, 168), '收起' if chinese else 'Less', 22, '#f3f7f8', chinese=chinese)
    draw.ellipse(box((1470, 148, 1527, 205)), fill='#496472', outline='#73919e', width=SCALE)
    for coords in ((1488, 166, 1508, 186), (1508, 166, 1488, 186)):
        draw.line(box(coords), fill='#f3f7f8', width=3 * SCALE)

    def card(y, title, lines, timestamp):
        nonlocal draw, image
        height = 112 + 40 * len(lines)
        layer = Image.new('RGBA', image.size)
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle(box((724, y, 1516, y + height)), radius=39 * SCALE,
                             fill=(206, 224, 231, 61), outline=(204, 230, 239, 110), width=SCALE)
        image = Image.alpha_composite(image, layer)
        draw = ImageDraw.Draw(image)
        bark_icon(draw, 750, y + (height - 80) / 2, 80)
        text(draw, (854, y + 28), fit_title(title, 496, 32, chinese),
             32, '#f4f7f8', True, chinese)
        time_font = font(22, chinese=chinese)
        time_width = time_font.getlength(timestamp) / SCALE
        text(draw, (1482 - time_width, y + 33), timestamp, 22, '#bacdd6', chinese=chinese)
        for index, line in enumerate(lines):
            text(draw, (854, y + 73 + index * 40), line, 29, '#e5eef2', chinese=chinese)
        return y + height

    if chinese:
        bottom = card(237, '演示会话 · 审批请求',
                      ['状态：审批请求', '项目：demo-app', '模型：gpt-6.1-sol', '工具：Bash'], '现在')
        card(bottom + 20, '演示会话 · 本轮结束',
             ['状态：本轮结束', '项目：demo-app', '模型：gpt-6.1-sol'], '2 分钟前')
    else:
        bottom = card(237, 'demo-session · Approval requested',
                      ['Status: Approval requested', 'Project: demo-app',
                       'Model: gpt-6.1-sol', 'Tool: Bash'], 'now')
        card(bottom + 20, 'demo-session · Turn ended',
             ['Status: Turn ended', 'Project: demo-app', 'Model: gpt-6.1-sol'], '2m ago')
    draw.rounded_rectangle(box((1005, 875, 1235, 883)), radius=4 * SCALE, fill='#edf4f5')
    caption = '按真实 Bark 显示重绘 · 示例信息' if chinese else 'Redrawn from Bark on iOS · Example content'
    text(draw, (744, 824), caption, 19, '#bbced5', chinese=chinese)
    filename = 'notification-preview.zh-CN.png' if chinese else 'notification-preview.png'
    path = HERE / filename
    image.convert('RGB').resize(SIZE, Image.Resampling.LANCZOS).save(path, optimize=True)
    print(path)


if __name__ == '__main__':
    for language in ('en', 'zh'):
        render(language)
