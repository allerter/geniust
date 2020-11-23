from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard
from telegram.utils.helpers import create_deep_linked_url

from geniust.constants import (
    TYPING_ARTIST, END,
)
from geniust import (
    genius, utils,
)


def type_artist(update, context):
    # user has entered the function through the main menu
    if update.callback_query:
        update.callback_query.answer()
        msg = 'Enter artist name.'
        update.callback_query.edit_message_text(msg)
    else:
        chat_id = update.message.chat.id
        context.user_data['chat_id'] = chat_id

        msg = 'Enter artist name.'
        update.message.reply_text(msg)

    return TYPING_ARTIST


def search_artists(update, context):
    """Checks artist link or return search results, or prompt user for format"""
    text = update.message.text

    res = genius.search_artists(text)
    buttons = []
    for i, hit in enumerate(res['sections'][0]['hits']):
        artist = hit['result']
        artist_id = artist['id']
        text = artist['name']
        callback = f"artist_{artist_id}"

        buttons.append([IBKeyboard(text, callback)])

    update.message.reply_text(
        text='Choose an artist',
        reply_markup=IBKeyboard(buttons))

    return END


def display_artist(update, context):
    bot = context.bot
    chat_id = update.callback_query.message.chat.id
    artist_id = int(update.callback_query.data.split('_')[1])
    language = context.user_data['menu_lang']

    update.callback_query.edit_message_reply_markup()

    artist = genius.artist(artist_id)['artist']
    cover_art = artist['image_url']
    caption = artist_caption(artist, language)

    buttons = [
        [IButton(
            "List Songs (By Popularity)",
            callback_data=f"artist_{artist['id']}_songs_ppl")],
        [IButton(
            "List Songs (By Release Date)",
            callback_data=f"artist_{artist['id']}_songs_rdt")],
        [IButton(
            "List Songs (By Title)",
            callback_data=f"artist_{artist['id']}_songs_ttl")],
        [IButton(
            "List Albums",
            callback_data=f"artist_{artist['id']}_albums")],
    ]

    bot.send_photo(
        chat_id,
        cover_art,
        caption,
        reply_markup=IBKeyboard(buttons))


def display_artist_albums(update, context):
    artist_id = int(update.callback_query.data.split('_')[1])
    message = update.callback_query.message
    chat_id = update.callback_query.message.chat.id
    albums = []
    username = context.bot.get_me().username

    albums_list = genius.artist_albums(artist_id, per_page=50)
    for album in albums_list['albums']:
        album_id = album['id']
        album_name = album['name']
        url = create_deep_linked_url(username, f'album_{album_id}')
        text = f"""\n• <a href="{url}">{album_name}"""

        albums.append(text)

    if albums:
        artist = albums_list[0]['artist']['name']
        albums = f"\n<b>{artist}'s Albums</b>\n{''.join(albums)}"
    else:
        artist = genius.artist(artist_id)['artist']['name']
        text = f'{artist} has no albums.'
        context.bot.send_message(chat_id, text)
        return END

    if len(message.text) + len(albums) < 1024:
        update.callback_query.edit_message_caption(message.text + albums)
    else:
        context.bot.send_message(chat_id, albums)

    return END


def display_artist_songs(update, context):
    data = update.callback_query.data.split('_')
    artist_id, sort = int(data[1]), data[3]
    message = update.callback_query.message
    chat_id = update.callback_query.message.chat.id
    songs = []
    username = context.bot.get_me().username

    if sort == 'ppl':
        sort = 'popularity'
    elif sort == 'rdt':
        sort = 'release_date'
    else:
        sort = 'title'

    songs_list = genius.artist_songs(artist_id, per_page=50, sort=sort)
    for song in songs_list['songs']:
        song_id = song['id']
        song_name = song['name']
        url = create_deep_linked_url(username, f'song_{song_id}')
        text = f"""\n• <a href="{url}">{song_name}"""

        songs.append(text)

    if songs:
        artist = songs_list[0]['primary_artist']['name']
        songs = (f"\n<b>{artist}'s Songs Sorted By {sort.capitilize()}:"
                 f"</b>\n{''.join(songs)}")
    else:
        artist = genius.artist(artist_id)['artist']['name']
        text = f'{artist} has no songs.'
        context.bot.send_message(chat_id, text)
        return END

    if len(message.text) + len(songs) < 1024:
        update.callback_query.edit_message_caption(message.text + songs)
    else:
        context.bot.send_message(chat_id, songs)

    return END


def artist_caption(artist, length_limit=1024):
    alternate_names = ''
    social_media = ''
    social_media_links = []

    if artist['alternate_names']:
        alternate_names = (f"\n<b>Alternate Names</b>"
                           f"\n{', '.join(artist['alternate_names'])}")

    if artist['facebook_name']:
        url = f"https://www.facebook.com/{artist['facebook_name']}"
        social_media_links.append(f"""<a href="{url}">Facebook</a>""")
    if artist['instagram_name']:
        url = f"https://www.instagram.com/{artist['instagram_name']}"
        social_media_links.append(f"""<a href="{url}">Instagram</a>""")
    if artist['twitter_name']:
        url = f"https://www.twitter.com/{artist['twitter_name']}"
        social_media_links.append(f"""<a href="{url}">Twitter</a>""")
    if social_media_links:
        social_media = f'\n<b>Social Media:</b>\n{" | ".join(social_media_links)}'

    followers_count = utils.human_format(artist['followers_count'])

    description = artist['description_annotation']['annotations'][0]['body']['html']

    string = (
        f"{artist['name']}\n"
        f"\n<b>Name:</b>\n{artist['name']}"
        f"{alternate_names}"
        f"\n<b>Followers Count:</b>\n{followers_count}"
        f"{social_media}"
        f"\n\n{description}"
    )
    string = string.strip()

    if length_limit == 1024 and len(string) > 1024:
        return f'{string[:1021]}...'
    elif length_limit == 4096:
        img = f"""<a href="{artist['image_url']}">&#8709</a>"""
        if len(string) > 4096:
            string = img + string
            return f'{string[:4093]}...'
        else:
            return string + img
