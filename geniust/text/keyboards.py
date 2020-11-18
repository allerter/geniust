from telegram import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def IButton(text, callback_data=None, **kwargs):
    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        **kwargs
    )


def IBKeyboard(buttons, **kwargs):
    return InlineKeyboardMarkup(
        buttons,
        **kwargs
    )


main_menu_buttons = [[
    InlineKeyboardButton(text='Song Lyrics',
                         callback_data=str(CHECK_GENIUS_SONG)),
    InlineKeyboardButton(text='Album Lyrics',
                         callback_data=str(CHECK_GENIUS_ALBUM))
],
    [
    InlineKeyboardButton(text='Customize Lyrics',
                         callback_data=str(CUSTOMIZE_GENIUS))
],
    [
    InlineKeyboardButton(text='Done',
                         callback_data=str(END))
]]
main_menu = InlineKeyboardMarkup(main_menu_buttons)

# ----------------------------------------------------------

customize_menu_buttons = [
    [InlineKeyboardButton(text='Lyrics Language', callback_data=str(LYRICS_LANG))],
    [InlineKeyboardButton(text='Annotations', callback_data=str(INCLUDE))],
    [InlineKeyboardButton(text='Back', callback_data=str(END))],
]
customize_menu = InlineKeyboardMarkup(customize_menu_buttons)

# ----------------------------------------------------------

set_lang_buttons = [
    [InlineKeyboardButton(
        text='Only English (ASCII)',
        callback_data=str(OPTION1))],
    [InlineKeyboardButton(
        text='Only non-English (non-ASCII)',
        callback_data=str(OPTION2))],
    [InlineKeyboardButton(
        text='English + non-English',
        callback_data=str(OPTION3))],
    [InlineKeyboardButton(
        text='Back',
        callback_data=str(END))]
]
set_lang = InlineKeyboardMarkup(set_lang_buttons)

# ----------------------------------------------------------

album_formats_buttons = [[
    InlineKeyboardButton(text='PDF', callback_data=album_id + str(OPTION1)),
],
    [
    InlineKeyboardButton(text='ZIP', callback_data=album_id + str(OPTION2))
],
    [
    InlineKeyboardButton(text='TELEGRA.PH', callback_data=album_id + str(OPTION3))
]]
album_formats = InlineKeyboardMarkup(album_formats_buttons)

# ----------------------------------------------------------
