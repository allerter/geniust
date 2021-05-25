import textwrap
from dataclasses import dataclass, astuple
from typing import List, Optional, Tuple
from io import BytesIO

from PIL import Image, ImageEnhance, ImageFont, ImageDraw

from geniust import data_path


@dataclass
class Point:
    left: int
    top: int


DOUBLE_QUOTES_IMAGE = Image.open(data_path / "double-quotes.png")
FONT_PATH = str(data_path / "Programme-Regular.ttf")
LYRICS_FONT = ImageFont.truetype(FONT_PATH, 59)
COVER_ART_BRIGHTNESS = 0.8
METADATA_FONT_BIG = ImageFont.truetype(FONT_PATH, 37)
METADATA_FONT_SMALL = ImageFont.truetype(FONT_PATH, 30)
FEATURED_ARTIST_FONT_BIG = ImageFont.truetype(FONT_PATH, 32)
FEATURED_ARTIST_FONT_SMALL = ImageFont.truetype(FONT_PATH, 25)
LYRICS_TEXT_COLOR = "#000"
METADATA_TEXT_COLOR = "#fff"
BOX_COLOR = "#fff"
OFFSET = Point(18, 451)
TEXT_HEIGHT = LYRICS_FONT.getsize("LOREM IPSUM")[1]
BOX_HEIGHT = TEXT_HEIGHT + 15
LYRICS_BOX_OFFSET = Point(OFFSET.left + DOUBLE_QUOTES_IMAGE.width + 15, OFFSET.top)
LYRICS_OFFSET = Point(LYRICS_BOX_OFFSET.left + 5, LYRICS_BOX_OFFSET.top)


def change_brightness(im: Image, value: float) -> Image:
    enhancer = ImageEnhance.Brightness(im)
    return enhancer.enhance(value)


def add_double_quotes(im: Image, box: Point) -> None:
    im.paste(DOUBLE_QUOTES_IMAGE, astuple(box), mask=DOUBLE_QUOTES_IMAGE)


def add_line(draw: ImageDraw, lyric: str, last_box_pos: Point):
    for i, line in enumerate(textwrap.wrap(lyric, 30, drop_whitespace=True)):
        # Draw box
        width, _ = LYRICS_FONT.getsize(line)
        if i == 0:
            last_line_width = width
        else:
            # if the lines have a similar width (width <=20px or width >= 20px),
            # it's better to give them the same width
            if abs(width - last_line_width) < 20:
                width = last_line_width
            last_line_width = width
        box_start = Point(LYRICS_BOX_OFFSET.left, last_box_pos.top + 13)
        box_end = Point(box_start.left + width + 17, box_start.top + BOX_HEIGHT)
        draw.rectangle((astuple(box_start), astuple(box_end)), fill=BOX_COLOR)

        # Draw Lyrics
        top = last_box_pos.top
        pos = (LYRICS_OFFSET.left + 5, top + 15)
        draw.text(pos, line, fill=LYRICS_TEXT_COLOR, font=LYRICS_FONT)
        last_box_pos = box_end
    return last_box_pos


def add_lyrics(draw: ImageDraw, lyrics) -> Point:
    pos_end = LYRICS_BOX_OFFSET
    for line in lyrics.split("\n"):
        # add_line moves every box some pixels down,
        # but we don't want that for the first box
        # since it should be aligned with the quotes
        # so we move it the same number of pixels up
        last_box_pos = (
            Point(LYRICS_BOX_OFFSET.left, LYRICS_BOX_OFFSET.top - 13)
            if pos_end == LYRICS_BOX_OFFSET
            else pos_end
        )
        pos_end = add_line(draw, line, last_box_pos)
    return pos_end


def add_metadata(
    draw: ImageDraw,
    last_box_pos: Point,
    song_title: str,
    primary_artists: List[str],
    featured_artists: List[str],
):
    # Add main artists and song title
    pos_metadata = Point(LYRICS_BOX_OFFSET.left, last_box_pos.top + 35)
    text = " & ".join(primary_artists) + f' "{song_title}"'
    if len(text) > 42:
        if len(text) > 52:
            text = textwrap.fill(text, 52, drop_whitespace=True)
        metadata_font = METADATA_FONT_SMALL
        featured_font = FEATURED_ARTIST_FONT_SMALL
    else:
        metadata_font = METADATA_FONT_BIG
        featured_font = FEATURED_ARTIST_FONT_BIG
    _, height = metadata_font.getsize(text)
    draw.text(
        astuple(pos_metadata),
        text.upper(),
        fill=METADATA_TEXT_COLOR,
        font=metadata_font,
    )

    # Add featured artists
    pos_metadata = Point(pos_metadata.left, pos_metadata.top + height)
    if featured_artists:
        text = "FT. "
        if len(featured_artists) == 1:
            text += featured_artists[0]
        else:
            text += "{artists} & {last_artist}".format(
                artists=", ".join(featured_artists[:-1]),
                last_artist=featured_artists[-1],
            )
        text = textwrap.fill(text, 52)
        draw.text(
            astuple(pos_metadata),
            text.upper(),
            fill=METADATA_TEXT_COLOR,
            font=featured_font,
        )


def build_lyric_card(
    cover_art: BytesIO,
    lyrics: str,
    song_title: str,
    primary_artists: List[str],
    featured_artists: Optional[List[str]] = None,
    format: str = "PNG",
) -> BytesIO:
    im = Image.open(cover_art)
    im = change_brightness(im, COVER_ART_BRIGHTNESS)
    add_double_quotes(im, OFFSET)
    draw = ImageDraw.Draw(im)
    pos_end = add_lyrics(draw, lyrics)
    add_metadata(
        draw,
        pos_end,
        song_title,
        primary_artists,
        featured_artists if featured_artists else [],
    )
    lyric_card = BytesIO()
    im.save(lyric_card, format=format)
    return lyric_card
