"""Render public examples using invented text, without reading device screenshots.

Requires Pillow and a system Latin font; Chinese rendering also needs PingFang,
Heiti, or Noto Sans CJK. Run this file to regenerate both README illustrations.
"""

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve().parent
SIZE = (1280, 560)
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
    draw.rounded_rectangle(box((x, y, x + size, y + size)), radius=round(size * .25 * SCALE),
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
    image = Image.new('RGBA', box(SIZE), '#f7f9fa')
    draw = ImageDraw.Draw(image)

    def centered_label(center, y, value):
        width = font(24, True).getlength(value) / SCALE
        text(draw, (center - width / 2, y), value, 24, '#344b56', True)

    def surface(bounds, top, bottom, radius):
        nonlocal image, draw
        x0, y0, x1, y1 = bounds
        width, height = box((x1 - x0, y1 - y0))
        panel = Image.new('RGBA', (width, height))
        pd = ImageDraw.Draw(panel)
        for y in range(height):
            t = y / max(1, height - 1)
            color = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,)
            pd.line((0, y, width, y), fill=color)
        mask = Image.new('L', panel.size)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height),
                                              radius=radius * SCALE, fill=255)
        image.paste(panel, box((x0, y0)), mask)
        draw = ImageDraw.Draw(image)

    centered_label(408, 24, 'iOS')
    centered_label(1034, 24, 'watchOS')

    # Compact side-by-side surfaces replace the oversized marketing hero.
    surface((26, 76, 790, 535), (44, 75, 89), (22, 43, 52), 32)
    surface((815, 76, 1254, 535), (238, 243, 246), (226, 234, 240), 32)
    text(draw, (57, 101), 'Bark', 30, '#f1f7f9')
    text(draw, (702, 110), '9:41', 19, '#d9e7ed')

    def phone_card(y, title, lines, timestamp):
        nonlocal image, draw
        height = 79 + 28 * len(lines)
        layer = Image.new('RGBA', image.size)
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle(box((44, y, 772, y + height)), radius=28 * SCALE,
                             fill=(211, 230, 237, 62), outline=(204, 229, 240, 102), width=SCALE)
        image = Image.alpha_composite(image, layer)
        draw = ImageDraw.Draw(image)
        bark_icon(draw, 67, y + (height - 58) / 2, 58)
        text(draw, (146, y + 21), fit_title(title, 500, 25, chinese),
             25, '#f6f9fa', True, chinese)
        width = font(18, chinese=chinese).getlength(timestamp) / SCALE
        text(draw, (748 - width, y + 25), timestamp, 18, '#c2d4dc', chinese=chinese)
        for index, line in enumerate(lines):
            text(draw, (146, y + 57 + 28 * index), line, 23, '#e5eef3', chinese=chinese)
        return y + height

    if chinese:
        bottom = phone_card(156, '演示会话 · 审批请求',
                            ['状态：审批请求', '项目：demo-app', '模型：gpt-6.1-sol', '工具：Bash'], '现在')
        phone_card(bottom + 16, '演示会话 · 本轮结束',
                   ['状态：本轮结束', '项目：demo-app', '模型：gpt-6.1-sol'], '2 分钟前')
    else:
        bottom = phone_card(156, 'demo-session · Approval requested',
                            ['Status: Approval requested', 'Project: demo-app',
                             'Model: gpt-6.1-sol', 'Tool: Bash'], 'now')
        phone_card(bottom + 16, 'demo-session · Turn ended',
                   ['Status: Turn ended', 'Project: demo-app', 'Model: gpt-6.1-sol'], '2m ago')
    draw.rounded_rectangle(box((338, 525, 478, 529)), radius=2 * SCALE, fill='#e7f0f4')

    # The Watch reference informs notification wrapping and the case silhouette.
    # All hardware, strap and notification pixels are drawn from scratch.
    def strap(y0, y1):
        draw.rounded_rectangle(box((950, y0, 1118, y1)), radius=13 * SCALE,
                               fill='#293139', outline='#3d454d', width=SCALE)
        for x in range(956, 1114, 7):
            draw.line(box((x, y0 + 5, x, y1 - 5)), fill='#374049', width=SCALE)
        for y in range(y0 + 6, y1 - 3, 6):
            draw.line(box((955, y, 1113, y)), fill='#222a31', width=SCALE)
    strap(84, 164)
    strap(438, 527)

    shadow = Image.new('RGBA', image.size)
    ImageDraw.Draw(shadow).rounded_rectangle(box((895, 139, 1175, 486)),
                                            radius=65 * SCALE, fill=(7, 22, 31, 90))
    image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(10 * SCALE)))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(box((1168, 233, 1185, 279)), radius=7 * SCALE,
                           fill='#2b3035', outline='#697078', width=SCALE)
    for y in range(240, 276, 5):
        draw.line(box((1175, y, 1183, y)), fill='#12171b', width=SCALE)
    draw.rounded_rectangle(box((1168, 306, 1176, 347)), radius=4 * SCALE, fill='#333a40')
    surface((893, 130, 1174, 481), (98, 107, 116), (30, 36, 42), 63)
    surface((896, 133, 1171, 478), (43, 48, 54), (8, 12, 16), 60)
    surface((909, 149, 1158, 462), (7, 15, 26), (5, 11, 18), 48)
    text(draw, (1087, 169), '9:41', 18, '#eef4fa')
    draw.rounded_rectangle(box((917, 222, 1150, 449)), radius=25 * SCALE,
                           fill='#263550', outline='#758cac', width=SCALE)
    bark_icon(draw, 925, 203, 38)
    timestamp = '现在' if chinese else 'now'
    width = font(17, chinese=chinese).getlength(timestamp) / SCALE
    text(draw, (1134 - width, 231), timestamp, 17, '#d1deef', chinese=chinese)
    title = ['演示会话 ·', '审批请求'] if chinese else ['demo-session ·', 'Approval requested']
    for index, line in enumerate(title):
        text(draw, (930, 264 + index * 28), line, 22, '#f2f6fb', True, chinese)
    body = ['状态：审批请求', '项目：demo-app'] if chinese else [
        'Status: Approval', 'requested', 'Project: demo-app…']
    for index, line in enumerate(body):
        text(draw, (930, 326 + index * 28), line, 22, '#e4edf7', chinese=chinese)
    draw.rounded_rectangle(box((1006, 453, 1059, 456)), radius=2 * SCALE, fill='#31435b')

    filename = 'notification-preview.zh-CN.png' if chinese else 'notification-preview.png'
    path = HERE / filename
    image.convert('RGB').resize(SIZE, Image.Resampling.LANCZOS).save(path, optimize=True)
    print(path)

if __name__ == '__main__':
    for language in ('en', 'zh'):
        render(language)
