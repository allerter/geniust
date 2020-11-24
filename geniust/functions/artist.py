from telegram import InlineKeyboardButton as IButton
from telegram import InlineKeyboardMarkup as IBKeyboard

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
        callback_data = f"artist_{artist_id}"

        buttons.append([IButton(text, callback_data=callback_data)])

    update.message.reply_text(
        text='Choose an artist',
        reply_markup=IBKeyboard(buttons))

    return END


def display_artist(update, context):
    bot = context.bot
    if update.callback_query:
        chat_id = update.callback_query.message.chat.id
        artist_id = int(update.callback_query.data.split('_')[1])
        update.callback_query.answer()
        update.callback_query.edit_message_reply_markup(None)
    else:
        chat_id = update.message.chat.id
        artist_id = int(context.args[0].split('_')[1])

    artist = genius.artist(artist_id)['artist']
    cover_art = artist['image_url']
    caption = artist_caption(artist)

    buttons = [
        [IButton(
            "Songs (By Popularity)",
            callback_data=f"artist_{artist['id']}_songs_ppl")],
        [IButton(
            "Songs (By Release Date)",
            callback_data=f"artist_{artist['id']}_songs_rdt")],
        [IButton(
            "Songs (By Title)",
            callback_data=f"artist_{artist['id']}_songs_ttl")],
        [IButton(
            "Albums",
            callback_data=f"artist_{artist['id']}_albums")],
    ]

    bot.send_photo(
        chat_id,
        cover_art,
        caption,
        reply_markup=IBKeyboard(buttons))


def display_artist_albums(update, context):
    if update.callback_query:
        update.callback_query.answer()
        artist_id = int(update.callback_query.data.split('_')[1])
        message = update.callback_query.message
        chat_id = update.callback_query.message.chat.id
    else:
        chat_id = update.message.chat.id
        artist_id = int(context.args[0].split('_')[1])
        message = None
        chat_id = update.message.chat.id

    albums = []

    albums_list = genius.artist_albums(artist_id, per_page=50)
    for album in albums_list['albums']:
        text = f"""\n• {utils.deep_link(album)}</a>"""

        albums.append(text)

    if albums:
        artist = albums_list['albums'][0]['artist']['name']
        albums = f"\n<b>{artist}</b>'s Albums:\n{''.join(albums)}"
    else:
        artist = genius.artist(artist_id)['artist']['name']
        text = f'{artist} has no albums.'
        context.bot.send_message(chat_id, text)
        return END

    if message and len(message.caption) + len(albums) < 1024:
        update.callback_query.edit_message_caption(message.caption + albums)
    else:
        context.bot.send_message(chat_id, albums)

    return END


def display_artist_songs(update, context):
    if update.callback_query:
        update.callback_query.answer()
        data = update.callback_query.data.split('_')
        artist_id, sort = int(data[1]), data[3]
        message = update.callback_query.message
        chat_id = update.callback_query.message.chat.id
    else:
        artist_id = int(context.args[0].split('_')[1])
        message = None
        chat_id = update.message.chat.id

    songs = []

    if sort == 'ppl':
        sort = 'popularity'
    elif sort == 'rdt':
        sort = 'release_date'
    else:
        sort = 'title'

    songs_list = genius.artist_songs(artist_id, per_page=50, sort=sort)
    for song in songs_list['songs']:
        text = f"""\n• {utils.deep_link(song)}"""

        songs.append(text)

    if songs:
        artist = songs_list['songs'][0]['primary_artist']['name']
        songs = (f"\n<b>{artist}</b>'s Songs Sorted By {sort.capitalize()}:"
                 f"</b>\n{''.join(songs)}")
    else:
        artist = genius.artist(artist_id)['artist']['name']
        text = f'{artist} has no songs.'
        context.bot.send_message(chat_id, text)
        return END

    if message and len(message.caption) + len(songs) < 1024:
        update.callback_query.edit_message_caption(message.caption + songs)
    else:
        context.bot.send_message(chat_id, songs)

    return END


def artist_caption(artist, length_limit=1024):
    alternate_names = ''
    social_media = ''
    followers_count = ''
    social_media_links = []

    if artist.get('alternate_names'):
        alternate_names = (f"\n<b>Alternate Names</b>"
                           f"\n{', '.join(artist['alternate_names'])}")

    if artist.get('facebook_name'):
        url = f"https://www.facebook.com/{artist['facebook_name']}"
        social_media_links.append(f"""<a href="{url}">Facebook</a>""")
    if artist.get('instagram_name'):
        url = f"https://www.instagram.com/{artist['instagram_name']}"
        social_media_links.append(f"""<a href="{url}">Instagram</a>""")
    if artist.get('twitter_name'):
        url = f"https://www.twitter.com/{artist['twitter_name']}"
        social_media_links.append(f"""<a href="{url}">Twitter</a>""")
    if social_media_links:
        social_media = f'\n<b>Social Media:</b>\n{" | ".join(social_media_links)}'

    if artist.get('followers_count'):
        followers_count = utils.human_format(artist['followers_count'])
        followers_count = f"\n<b>Followers Count:</b>\n{followers_count}"

    description = utils.get_description(artist)

    string = (
        f"{artist['name']}\n"
        f"\n<b>Name:</b>\n{artist['name']}"
        f"{alternate_names}"
        f"{followers_count}"
        f"{social_media}"
        f"\n\n{description}"
    )
    string = string.strip()

    if length_limit == 1024 and len(string) > 1024:
        return string[:1021] + '...'
    elif length_limit == 4096:
        img = f"""<a href="{artist['image_url']}">&nbsp;</a>"""
        if len(img) + len(string) > 4096:
            string = string[:4096 - len(img) - 3]
        return img + string + '...'
    else:
        return string
