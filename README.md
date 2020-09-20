<img src="logo.png" width="200"/>

# Genius T
A Telegram bot that provides song and album lyrics along with their annotations on Genius.

## Table of Contents
> -   [Features](#features)
> -   [Requirements](#requirements)

## Features
> -   [Song Lyircs](#song-lyircs)
> -   [Album Lyrics](#album-lyrics)
> -   [Lyrics Customizations](#environment-variables)
> -   [Telegram features](#deploying-to-heroku)


### Song Lyrics
This bot provides the song lyrics using Telegram messages. The annotated fragments of songs are linked to their annotations which are uploaded by the bot in a separate channel meant for annotations.


### Album Lyrics
As for the albums, the bot provides the lyrics of their songs in three formats:
- PDF: A PDF containing the album description, a table of contents containing song titles linked to the page of the song lyrics, and the lyrics of all the songs in the album.
- ZIP: A ZIP file containing TXT files of each song's lyrics.
- TELEGRA.PH: Returns a link to a *telegra.ph* page which in turn has the album's description and links to other *telegra.ph* pages that each has the description and the lyrics of a song.


### Lyrics Customizations
The bot allows users to choose between including and excluding the annotations from the lyrics. Users can also choose not to include ASCII or non-ASCII characters in the lyrics. One of the uses of this could be to remove the English lines from songs that have been translated into Arabic or Persian so that only the translated lines remain.


### Telegram Features
Users can search songs and albums or use other features by navigating the Inline menu which is accessed using the `/start` command. Alternatively, they could navigate directly to the desired feature using the bot's commands:
- **start**
  start the bot
- **song_lyrics**:
  get song lyrics
- **album_lyrics**:
  get album lyrics
- **lyrics_language**:
  set lyrics language
- **include_annotations**:
  include annotations
- **cancel**:
  cancel the current task
- **stop**:
  stop and end the conversation
- **help**:
  more info about the bot
- **contact_us**:
  send us a message

Users can also perform searches by using the inline search feature. For example:
- searching songs: `@the_bot we will rock you`
- searching albums: `@the_bot hotel diablo @` - The `@` character makes the bot search for albums on Genius.
 

## Requirements
The bot has the following environment variables:
- **BOT_TOKEN**:
  Telegram bot token
- **DATABASE_URL**:
  URL of the database to connect to and save user customizations.
- **TELEGRAPH_TOKEN**:
  Telegraph token used to upload songs/albums on Telegraph.
- **GENIUS_TOKEN**:
  Genius token used to perform searches and scrape lyrics from Genius.
- **ANNOTATIONS_TELEGRAM_CHANNEL**:
  Username of the channel where the bot uploads the annotations (the string session at the bottom has to be an admin in the channel).
- **DEVELOPERS**:
  A list of Telegram IDs which will be notified when the bot faces an error.
- **SERVER_PORT**:
  port of the server where the bot operates on (used for the webhook).
- **SERVER_ADDRESS**:
  The address of the server (used for the webhook).
- **TELETHON_API_ID**:
  A Telegram API ID.
- **TELETHON_API_HASH**:
  A Telegram API hash.
- **TELETHON_SESSION_STRING**:
  A Telegram session string used to upload annotations faster.
