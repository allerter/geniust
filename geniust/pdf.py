import reportlab
from reportlab.platypus import Paragraph, Spacer, Image, PageBreak
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.platypus.frames import Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from rtl import reshaper
from bidi.algorithm import get_display
import re
from io import BytesIO
import requests
import string_funcs
import json

reportlab.rl_config.TTFSearchPath.append(r'Fonts')
font_regular = 'Regular'
font_bold = 'Bold'
font_persian = 'Persian'

# English fonts
pdfmetrics.registerFont(TTFont(font_regular, 'Barlow-Regular.ttf'))
pdfmetrics.registerFont(TTFont(font_bold, 'Barlow-Bold.ttf'))
pdfmetrics.registerFont(TTFont('barlow-italic', 'Barlow-Italic.ttf'))
pdfmetrics.registerFontFamily(font_regular, normal=font_regular,
                              bold=font_bold, italic='barlow-italic')

# Persian fonts
pdfmetrics.registerFont(TTFont(font_persian, 'Nahid.ttf'))
pdfmetrics.registerFont(TTFont('vazir-bold', 'Vazir-Bold.ttf'))
pdfmetrics.registerFont(TTFont('vazir-thin', 'Vazir-Thin.ttf'))
pdfmetrics.registerFontFamily(font_persian, normal=font_persian,
                              bold='vazir-bold', italic='vazir-thin')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='Song Lyrics', fontSize=14,
                          alignment=1, fontName=font_regular, leading=20))
styles.add(ParagraphStyle(name='Song Annotations', fontSize=10,
                          textColor='grey', fontName=font_regular, alignment=1))
styles.add(ParagraphStyle(name='Titles', fontSize=20,
                          alignment=1, leading=15, fontName=font_bold))
styles.add(ParagraphStyle(name='Songs', fontSize=30,
                          alignment=1, leading=15, fontName=font_bold))


class MyDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kw):
        self.allowSplitting = 0
        BaseDocTemplate.__init__(self, filename, **kw)
        frameT = Frame(self.leftMargin, self.bottomMargin,
                       self.width, self.height, id='normal')
        self.addPageTemplates([PageTemplate(id='First', frames=frameT, pagesize=self.pagesize),
                               PageTemplate(id='Later', frames=frameT, pagesize=self.pagesize)])

    def afterFlowable(self, flowable):
        """adds song title to bookmarks and the TOC"""
        "Registers TOC entries."
        if flowable.__class__.__name__ == 'Paragraph':
            text = flowable.getPlainText()
            style = flowable.style.name
            key = 'h2-%s' % self.seq.nextf('Song Lyrics')
            if style == 'Songs':
                self.canv.showOutline()
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, 0, 0)
                self.notify('TOCEntry', (0, text, self.page, key))


def get_farsi_text(text, long_text=False):
    """reshapes arabic/farsi words to be showed properly in the PDF"""
    if reshaper.has_arabic_letters(text):
        if long_text:
            words = text.split()
        else:
            words = text.split(r'(\W)')
        reshaped_words = []
        for word in words:
            if reshaper.has_arabic_letters(word):
                # for reshaping and concating words
                reshaped_text = reshaper.reshape(word)
                # for right to left
                bidi_text = get_display(reshaped_text)
                reshaped_words.append(bidi_text)
            else:
                reshaped_words.append(word)
        reshaped_words.reverse()
        return ' '.join(reshaped_words)
    return text


def create_pdf(data, user_data):
    """creates a PDF file from the data applyting user_data, and returns an in-memory file"""
    bio = BytesIO()
    doc = MyDocTemplate(bio, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    Story = []
    check_char = re.compile(r'[^\x00-\x7F]')  # Check for Non-English chars
    # Title
    page_break = PageBreak()
    album_artist = data['artist']
    album_title = data['album_title']
    translation = False
    persian = False
    bio.name = f'{album_artist} - {album_title}.pdf'
    if 'ترجمه' in album_title:
        persian = True
    if 'Genius' in album_artist:
        sep = album_title.find('-')
        bio.name = f'{album_title}.pdf'
        album_artist = get_farsi_text(album_title[:sep - 1])
        album_title = get_farsi_text(album_title[sep + 1:])
        translation = True
    album_artist = f'<font name="{font_persian if persian else font_regular}" size="{25 if len(album_title) < 20 else 20}">{album_artist}</font>'
    Story.append(Paragraph(album_artist, styles['Titles']))
    Story.append(Spacer(1, 12))

    album_title = f'<font name="{font_persian if persian else font_regular}" size="{40 if len(album_title) < 20 else 30}">{album_title}</font>'
    Story.append(Paragraph(album_title, styles["Titles"]))
    Story.append(Spacer(1, 50))
    # Image
    album_art = requests.get(data['album_art']).content
    im = Image(BytesIO(album_art), width=A4[0], height=A4[0])
    Story.append(im)
    Story.append(page_break)

    # Bio
    if not persian:
        ptext = f'<font name={font_bold} size="25">Biography</font>'
        Story.append(Paragraph(ptext, styles['Titles']))
        Story.append(Spacer(1, 20))
        biography = get_farsi_text(data['album_description'])
        font = font_persian if check_char.search(biography) else font_regular
        Story.append(Paragraph(biography, ParagraphStyle(name='Biography', fontName=font, leading=15,
                                                         embeddedHyphenation=1, alignment=4, fontSize=14,)))
        Story.append(page_break)

    # Tracklist TODO
    ptext = f'<font name="{font_bold}" size="25">Tracklist</font>'
    Story.append(Paragraph(ptext, styles['Titles']))
    Story.append(Spacer(1, 12))

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(fontName=font_regular, fontSize=20, name='Songs',
                       leftIndent=20, firstLineIndent=-20, spaceBefore=10, leading=16),
        ParagraphStyle(fontName=font_persian, fontSize=20, name='Persian Songs',
                       leftIndent=20, firstLineIndent=-20, spaceBefore=10, leading=16)]
    Story.append(toc)
    Story.append(page_break)

    # Songs
    format_title = re.compile(r'^[\S\s]*-\s|\([^\x00-\x7F][\s\S]*')
    lyrics_language = user_data['lyrics_lang']
    include_annotations = user_data['include_annotations']
    for song in data['songs']:
        lyrics = song['lyrics']
        title = song['title']
        if translation:
            sep = title.find('-')
            if title[sep + 1] == ' ':
                sep += 1
            title = format_title.sub('', title[sep + 1:])
            title = get_farsi_text(title)
        Story.append(Paragraph(title, styles['Songs']))
        Story.append(Spacer(1, 50))
        # format annotations
        lyrics = string_funcs.format_annotations(lyrics, song['annotations'], include_annotations,
                                                 format_type='pdf', lyrics_language=lyrics_language)
        # lyrics
        lyrics = string_funcs.format_language(lyrics, lyrics_language)
        lyrics = get_farsi_text(lyrics).replace('\n', '<br/>')
        for line in lyrics.split('<br/>'):
            if not len(line):
                Story.append(Spacer(1, 12))
            elif '!--!' in line:
                line = line.replace('!--!', '')
                if check_char.search(line):
                    line = f'<font name={font_persian}>{line}</font>'
                Story.append(Paragraph(line, styles['Song Annotations']))
            else:
                if check_char.search(line):
                    line = f'<font size="12" name={font_persian}>{line}</font>'
                Story.append(Paragraph(line, styles['Song Lyrics']))
        Story.append(page_break)
    doc.multiBuild(Story)
    bio.seek(0)
    return bio


def test(json_file, lyrics_language, include_annotations):
    with open(json_file, 'r') as f:
        data = json.loads(f.read())
    file = create_pdf(data, {'lyrics_lang': lyrics_language,
                             'include_annotations': include_annotations})
    with open('test.pdf', 'wb') as f:
        f.write(file.getvalue())
