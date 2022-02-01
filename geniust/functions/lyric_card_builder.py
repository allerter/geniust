import textwrap
from dataclasses import astuple, dataclass
from io import BytesIO
from typing import Dict, List, Optional, Union

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from geniust import data_path


@dataclass
class Point:
    left: int
    top: int


@dataclass(frozen=True)
class ImmutablePoint:
    left: int
    top: int


# Assets and Image Configs
# The RTL setting changes the direction and also sets the font
# for Arabic/Persian characters
RTL = True
LTR = False
IMAGES: Dict[bool, Dict[str, Image.Image]] = {
    LTR: {"double_quotes": Image.open(data_path / "double-quotes.png")},
    RTL: {},
}
IMAGES[RTL]["double_quotes"] = IMAGES[LTR]["double_quotes"].transpose(
    Image.FLIP_LEFT_RIGHT
)
COVER_ART_BRIGHTNESS = 0.8

# Fonts
FONTS_PATH = data_path
NotoSans = str(FONTS_PATH / "NotoSans-SemiBold.ttf")
PersianFont = str(FONTS_PATH / "Vazir-Medium.ttf")
# RTL changes the direction as well as the font to be used for Arabic/Persian glyphs.
FONTS: Dict[bool, Dict[str, ImageFont.FreeTypeFont]] = {
    LTR: {
        "lyrics": ImageFont.truetype(NotoSans, 55),
        "metadata_big": ImageFont.truetype(NotoSans, 37),
        "metadata_small": ImageFont.truetype(NotoSans, 30),
        "featured_artists_big": ImageFont.truetype(NotoSans, 32),
        "featured_artists_small": ImageFont.truetype(NotoSans, 25),
    },
    RTL: {
        "lyrics": ImageFont.truetype(PersianFont, 55),
        "metadata_big": ImageFont.truetype(PersianFont, 37),
        "metadata_small": ImageFont.truetype(PersianFont, 30),
        "featured_artists_big": ImageFont.truetype(PersianFont, 32),
        "featured_artists_small": ImageFont.truetype(PersianFont, 25),
    },
}
# Add glyphs of each font (needed in has_glyph)
for direction in FONTS:
    FONTS[direction]["glyphs"] = []
    for table in TTFont(FONTS[direction]["lyrics"].path)["cmap"].tables:
        FONTS[direction]["glyphs"].extend(table.cmap)

# Colors
LYRICS_TEXT_COLOR = "#000"
METADATA_TEXT_COLOR = "#fff"
BOX_COLOR = "#fff"

# Offsets
OFFSETS: Dict[bool, Dict[str, ImmutablePoint]] = {
    LTR: {
        "offset": ImmutablePoint(18, 451),
        "box_height": ImmutablePoint(
            0, FONTS[LTR]["lyrics"].getsize("LOREM IPSUM")[1] + 15
        ),
    },
    RTL: {
        "offset": ImmutablePoint(18, 451),
        "box_height": ImmutablePoint(0, FONTS[RTL]["lyrics"].getsize("لورم ایپسوم")[1]),
    },
}
for direction in OFFSETS:
    OFFSETS[direction]["lyrics_box_offset"] = ImmutablePoint(
        OFFSETS[direction]["offset"].left + IMAGES[LTR]["double_quotes"].width + 15,
        OFFSETS[direction]["offset"].top,
    )
    OFFSETS[direction]["lyrics_offset"] = ImmutablePoint(
        OFFSETS[direction]["lyrics_box_offset"].left + 5,
        OFFSETS[direction]["lyrics_box_offset"].top - 5,
    )
# All the offsets and font sizes are configured for a 1000x1000 image,
# so we'll resize the image to the builder image size and then resize it back to
# its original size
# The better solution is to use ratios from comparing cover art size to 1000x1000
# and adjust offsets and font sizes dynamically. For example:
# offset = Point(18, 451)
# image_size = im.size
# ratio = (image_size[0] / 1000, image_size[1] / 1000)
# adjusted_offset = Point(offset.left * ratio[0], offset.top * ratio[1])
# As I tested, this works fine for adjusting offsets and resizing the double quotes
# image, but for two reason I decided to go with resizing the image:
# 1. There may be some issues adjusting the font size e.g. it seems that
#    font size doesn't change linearly.
# 2. From what I've seen, most of Genius cover arts are available in 1000x1000.
BUILDER_IMAGE_SIZE = (1000, 1000)


def has_glyphs(font_glyphs: List[int], glyph: str) -> bool:
    # from https://stackoverflow.com/a/53829424
    return True if ord(glyph) in font_glyphs else False


def change_brightness(im: Image.Image, value: float) -> Image.Image:
    enhancer = ImageEnhance.Brightness(im)
    return enhancer.enhance(value)


def add_double_quotes(im: Image.Image, rtl: bool) -> None:
    double_quotes_image = IMAGES[rtl]["double_quotes"]
    box = OFFSETS[rtl]["offset"]
    if rtl:
        box = Point(box.left + 912, box.top)  # type: ignore
    im.paste(double_quotes_image, astuple(box), mask=double_quotes_image)


def fix_text_direction(text: str, rtl: bool) -> str:
    # For some reason the Heroku app doesn't need the text to be reshaped
    # if rtl:
    #     reshaped_text = arabic_reshaper.reshape(text)
    #     text = get_display(reshaped_text)
    return text


def add_line(
    draw: ImageDraw.ImageDraw,
    lyric: str,
    last_box_pos: Union[ImmutablePoint, Point],
    rtl: bool,
) -> Union[ImmutablePoint, Point]:
    lyrics_box_offset = OFFSETS[rtl]["lyrics_box_offset"]
    box_height = OFFSETS[rtl]["box_height"].top
    lyrics_offset = OFFSETS[rtl]["lyrics_offset"]
    lyrics_font = FONTS[rtl]["lyrics"]
    for i, line in enumerate(textwrap.wrap(lyric, 30, drop_whitespace=True)):
        # Remove unsupported glyphs from line
        line = "".join(
            char
            for char in line
            if char == "\n" or has_glyphs(FONTS[rtl]["glyphs"], char)
        )
        # Draw box
        line = fix_text_direction(line, rtl)
        width, _ = FONTS[rtl]["lyrics"].getsize(line)
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
            box_end.top -= 8
            box_start.left += 820 - width
            box_end.left += 820 - width
        draw.rectangle((astuple(box_start), astuple(box_end)), fill=BOX_COLOR)

        # Draw Lyrics
        top = last_box_pos.top
        pos = Point(lyrics_offset.left + 2, top + 5)
        if rtl:
            pos.top -= 10
            pos.left += 820 - width
        draw.text(astuple(pos), line, fill=LYRICS_TEXT_COLOR, font=lyrics_font)
        last_box_pos = box_end
    return last_box_pos


def add_lyrics(
    draw: ImageDraw.ImageDraw, lyrics: str, rtl: bool
) -> Union[ImmutablePoint, Point]:
    pos_end = lyrics_box_offset = OFFSETS[rtl]["lyrics_box_offset"]  # type: ignore
    for line in lyrics.split("\n"):
        # add_line moves every box some pixels down,
        # but we don't want that for the first box
        # since it should be aligned with the quotes
        # so we move it the same number of pixels up
        last_box_pos = (  # type: ignore
            Point(lyrics_box_offset.left, lyrics_box_offset.top - 10)
            if pos_end == lyrics_box_offset
            else pos_end
        )
        pos_end = add_line(draw, line, last_box_pos, rtl=rtl)  # type: ignore
    return pos_end


def add_metadata(
    draw: ImageDraw.ImageDraw,
    last_box_pos: Union[ImmutablePoint, Point],
    song_title: str,
    primary_artists: List[str],
    featured_artists: List[str],
    rtl: bool,
):
    lyrics_box_offset = OFFSETS[rtl]["lyrics_box_offset"]
    lang_fonts = FONTS[rtl]
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
    # Remove unsupported glyphs from text
    text = "".join(
        char for char in text if char == "\n" or has_glyphs(lang_fonts["glyphs"], char)
    )
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
        # Remove unsupported glyphs from text
        text = "".join(
            char
            for char in text
            if char == "\n" or has_glyphs(lang_fonts["glyphs"], char)
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
    rtl_lyrics: bool = False,
    rtl_metadata: bool = False,
    format: str = "PNG",
) -> BytesIO:
    """Builds lyric card

    Cover arts that aren't 1000x1000 will be upscaled and then downscaled
    after the build is done.

    Args:
        cover_art (BytesIO): Cover art of the song (1000x1000 recommended).
        lyrics (str): Lyrics to be put on the card.
        song_title (str): Title of the song.
        primary_artists (List[str]): Primary artists of the song.
        featured_artists (Optional[List[str]], optional): Featured artists
            of the song. Defaults to None.
        rtl_lyrics (bool, optional): Whether the lyrics are Right-To-Left or not.
            Also changes the fonts to one with Arabic/Persian glyphs. Basically
            `True` means that the lyrics are Arabic/Persian. Defaults to False.
        rtl_metadata (bool, optional): Whether the metadata are Right-To-Left or not.
            Also changes the fonts to one with Arabic/Persian glyphs. Basically
            `True` means that the metadata are Arabic/Persian or have
            characters of said languages. Defaults to False.
        format (str, optional): Format of the final card passed to
            `PIL.Image.Image.save`. Defaults to "PNG".

    Returns:
        BytesIO: The lyric card in an in-memory file.
    """
    im = Image.open(cover_art).convert("RGB")
    im = change_brightness(im, COVER_ART_BRIGHTNESS)
    original_size = im.size
    if original_size != BUILDER_IMAGE_SIZE:
        im = im.resize(BUILDER_IMAGE_SIZE, Image.BOX)
    add_double_quotes(im, rtl=rtl_lyrics)
    draw = ImageDraw.Draw(im)
    pos_end = add_lyrics(draw, lyrics, rtl=rtl_lyrics)
    add_metadata(
        draw,
        pos_end,
        song_title,
        primary_artists,
        featured_artists if featured_artists else [],
        rtl=rtl_metadata,
    )
    if original_size != BUILDER_IMAGE_SIZE:
        im = im.resize(original_size, Image.CUBIC)
    lyric_card = BytesIO()
    lyric_card.size = im.size  # type: ignore
    im.save(lyric_card, format=format)
    lyric_card.seek(0)
    return lyric_card
