import textwrap
from dataclasses import dataclass, astuple
from typing import Dict, List, Optional
from io import BytesIO

import arabic_reshaper
from PIL import Image, ImageEnhance, ImageFont, ImageDraw
from bidi.algorithm import get_display

from geniust import data_path


@dataclass
class Point:
    left: int
    top: int


# Assets and Image Configs
# The RTL setting changes the direction and also sets the font
# for Arabic/Persian characters
RTL = True
LTR = False
images: Dict[bool, Dict[str, Image.Image]] = {
    LTR: {"double_quotes": Image.open(data_path / "double-quotes.png")},
    RTL: {},
}
images[RTL]["double_quotes"] = images[LTR]["double_quotes"].transpose(
    Image.FLIP_LEFT_RIGHT
)
COVER_ART_BRIGHTNESS = 0.8

# Fonts
FONTS_PATH = data_path
NotoSans_SCMedium = str(FONTS_PATH / "NotoSans-SemiCondensedMedium.ttf")
NotoSansArabic_SCMedium = str(FONTS_PATH / "NotoSansArabic-SemiCondensedMedium.ttf")
# RTL changes the direction as well as the font to be used for Arabic/Persian glyphs.
fonts: Dict[bool, Dict[str, ImageFont.FreeTypeFont]] = {
    LTR: {
        "lyrics": ImageFont.truetype(NotoSans_SCMedium, 55),
        "metadata_big": ImageFont.truetype(NotoSans_SCMedium, 37),
        "metadata_small": ImageFont.truetype(NotoSans_SCMedium, 30),
        "featured_artists_big": ImageFont.truetype(NotoSans_SCMedium, 32),
        "featured_artists_small": ImageFont.truetype(NotoSans_SCMedium, 25),
    },
    RTL: {
        "lyrics": ImageFont.truetype(NotoSansArabic_SCMedium, 55),
        "metadata_big": ImageFont.truetype(NotoSansArabic_SCMedium, 37),
        "metadata_small": ImageFont.truetype(NotoSansArabic_SCMedium, 30),
        "featured_artists_big": ImageFont.truetype(NotoSansArabic_SCMedium, 32),
        "featured_artists_small": ImageFont.truetype(NotoSansArabic_SCMedium, 25),
    },
}

# Colors
LYRICS_TEXT_COLOR = "#000"
METADATA_TEXT_COLOR = "#fff"
BOX_COLOR = "#fff"

# Offsets
offsets: Dict[bool, Dict[str, Point]] = {
    LTR: {
        "offset": Point(18, 451),
        "text_height": fonts[LTR]["lyrics"].getsize("LOREM IPSUM")[1],
        "box_height": Point(0, fonts[LTR]["lyrics"].getsize("LOREM IPSUM")[1] + 15),
    },
    RTL: {
        "offset": Point(18, 451),
        "text_height": Point(0, fonts[RTL]["lyrics"].getsize("لورم ایپسوم")[1]),
        "box_height": Point(0, fonts[RTL]["lyrics"].getsize("لورم ایپسوم")[1] - 15),
    },
}
for direction in offsets:
    offsets[direction]["lyrics_box_offset"] = Point(
        offsets[direction]["offset"].left + images[LTR]["double_quotes"].width + 15,
        offsets[direction]["offset"].top,
    )
    offsets[direction]["lyrics_offset"] = Point(
        offsets[direction]["lyrics_box_offset"].left + 5,
        offsets[direction]["lyrics_box_offset"].top - 5,
    )


def change_brightness(im: Image, value: float) -> Image:
    enhancer = ImageEnhance.Brightness(im)
    return enhancer.enhance(value)


def add_double_quotes(im: Image, rtl: bool) -> None:
    double_quotes_image = images[rtl]["double_quotes"]
    box = offsets[rtl]["offset"]
    if rtl:
        box.left += 912
    im.paste(double_quotes_image, astuple(box), mask=double_quotes_image)


def fix_text_direction(text: str, rtl: bool) -> str:
    if rtl:
        reshaped_text = arabic_reshaper.reshape(text)
        text = get_display(reshaped_text)
    return text


def add_line(draw: ImageDraw, lyric: str, last_box_pos: Point, rtl: bool) -> Point:
    lyrics_box_offset = offsets[rtl]["lyrics_box_offset"]
    box_height = offsets[rtl]["box_height"].top
    lyrics_offset = offsets[rtl]["lyrics_offset"]
    lyrics_font = fonts[rtl]["lyrics"]
    for i, line in enumerate(textwrap.wrap(lyric, 30, drop_whitespace=True)):
        # Draw box
        line = fix_text_direction(line, rtl)
        width, _ = fonts[rtl]["lyrics"].getsize(line)
        if i == 0:
            last_line_width = width
        else:
            # if the lines have a similar width (width <=20px or width >= 20px),
            # it's better to give them the same width
            if abs(width - last_line_width) < 20:
                width = last_line_width
            last_line_width = width
        box_start = Point(lyrics_box_offset.left, last_box_pos.top + 10)
        box_end = Point(box_start.left + width + 15, box_start.top + box_height - 5)
        if rtl:
            box_end.top -= 7
            box_start.left += 820 - width
            box_end.left += 820 - width
        draw.rectangle((astuple(box_start), astuple(box_end)), fill=BOX_COLOR)

        # Draw Lyrics
        top = last_box_pos.top
        pos = Point(lyrics_offset.left + 2, top + 5)
        if rtl:
            pos.top -= 20
            pos.left += 820 - width
        draw.text(astuple(pos), line, fill=LYRICS_TEXT_COLOR, font=lyrics_font)
        last_box_pos = box_end
    return last_box_pos


def add_lyrics(draw: ImageDraw, lyrics: str, rtl: bool) -> Point:
    pos_end = lyrics_box_offset = offsets[rtl]["lyrics_box_offset"]
    for line in lyrics.split("\n"):
        # add_line moves every box some pixels down,
        # but we don't want that for the first box
        # since it should be aligned with the quotes
        # so we move it the same number of pixels up
        last_box_pos = (
            Point(lyrics_box_offset.left, lyrics_box_offset.top - 10)
            if pos_end == lyrics_box_offset
            else pos_end
        )
        pos_end = add_line(draw, line, last_box_pos, rtl=rtl)
    return pos_end


def add_metadata(
    draw: ImageDraw,
    last_box_pos: Point,
    song_title: str,
    primary_artists: List[str],
    featured_artists: List[str],
    rtl: bool,
):
    lyrics_box_offset = offsets[rtl]["lyrics_box_offset"]
    lang_fonts = fonts[rtl]
    if rtl:
        artist_sep = "و"
        comma = "،"
        featuring = "به همراه "
    else:
        artist_sep = "&"
        comma = ","
        featuring = "FT. "
    # Add main artists and song title
    pos_metadata = Point(lyrics_box_offset.left, last_box_pos.top + 35)
    text = f" {artist_sep} ".join(primary_artists)
    text += f" «{song_title}»" if rtl else f' "{song_title}"'
    if len(text) > 42:
        if len(text) > 52:
            text = textwrap.fill(text, 52, drop_whitespace=True)
        metadata_font = lang_fonts["metadata_small"]
        featured_font = lang_fonts["featured_artists_small"]
    else:
        metadata_font = lang_fonts["metadata_big"]
        featured_font = lang_fonts["featured_artists_big"]
    text = fix_text_direction(text.upper(), rtl)
    width, height = metadata_font.getsize(text)
    if rtl:
        pos_metadata.left += 820 - width
    draw.text(
        astuple(pos_metadata),
        text,
        fill=METADATA_TEXT_COLOR,
        font=metadata_font,
    )

    # Add featured artists
    pos_metadata = Point(lyrics_box_offset.left, pos_metadata.top + height - 10)
    if featured_artists:
        text = featuring
        if len(featured_artists) == 1:
            text += featured_artists[0]
        else:
            text += "{artists} {sep} {last_artist}".format(
                artists=f"{comma} ".join(featured_artists[:-1]),
                sep=artist_sep,
                last_artist=featured_artists[-1],
            )
        text = textwrap.fill(text, 52)
        text = fix_text_direction(text.upper(), rtl)
        width, _ = featured_font.getsize(text)
        if rtl:
            pos_metadata.left += 820 - width
        draw.text(
            astuple(pos_metadata),
            text,
            fill=METADATA_TEXT_COLOR,
            font=featured_font,
        )


def build_lyric_card(
    cover_art: BytesIO,
    lyrics: str,
    song_title: str,
    primary_artists: List[str],
    featured_artists: Optional[List[str]] = None,
    rtl: bool = False,
    format: str = "PNG",
) -> BytesIO:
    im = Image.open(cover_art)
    im = change_brightness(im, COVER_ART_BRIGHTNESS)
    add_double_quotes(im, rtl=rtl)
    draw = ImageDraw.Draw(im)
    pos_end = add_lyrics(draw, lyrics, rtl=rtl)
    add_metadata(
        draw,
        pos_end,
        song_title,
        primary_artists,
        featured_artists if featured_artists else [],
        rtl=rtl,
    )
    im = change_brightness(im, 1)
    lyric_card = BytesIO()
    im.save(lyric_card, format=format)
    return lyric_card
