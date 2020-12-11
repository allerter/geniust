<h1 align="center"><img src="logo.png" width="200" align="center"/>Genius T</h1>

![status](https://img.shields.io/uptimerobot/status/m786636302-b2fa3edeb9237ae327f70d06)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/Allerter/geniust)
![build](https://github.com/Allerter/geniust/workflows/build/badge.svg)
[![Test Coverage](https://api.codeclimate.com/v1/badges/74d5611d77cb26f4ed16/test_coverage)](https://codeclimate.com/github/Allerter/geniust/test_coverage)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A Telegram bot that provides music data and lyrics from Genius.

## Features
> -   [Music Data](#music-data)
> -   [Logging Into Genius](#logging-into-genius)
> -   [Song Lyircs](#song-lyircs)
> -   [Album Lyrics](#album-lyrics)
> -   [Telegram features](#deploying-to-heroku)


### Music Data
GeniusT allows searching for songs, albums and artists. Furthermore you can access tracks in albums, information about those tracks, view the artist info of those tracks and about any information that you could want! All entities (albums, artists and songs) are deep-linked; for example you can view the artist of a song just by clicking on the artist's name and from there you can go on to viewing that artist's songs, albums, the features on those songs and all that you can discover!

### Logging Into Genius
Using Genius's OAuth2, you can easily log into Genius in the bot and view your account's details (including unread messages) and even vote on album/song descriptions when you view them.

### Song Lyrics
The bot provides song lyrics using Telegram messages. The annotated fragments of songs are linked to their annotations which are uploaded by the bot in a separate channel meant for annotations. Meaning when you view lyrics for a song, you can click on highlighted lyrics that will lead you to their annotations right in Telegram.


### Album Lyrics
As for the albums, you can either view the tracks and their lyrics one-by-one (as you normally would) or you could have the lyrics of all the tracks all in one place in three formats:
- PDF: A PDF containing the album description, a table of contents containing song titles linked to the page of the song lyrics, and the lyrics of all the songs in the album.
- ZIP: A ZIP file containing TXT files of each song's lyrics.
- TELEGRA.PH: Returns a link to a *telegra.ph* page which in turn has the album's description and links to other *telegra.ph* pages that each has the description and the lyrics of a song.
This feature isn't maintained like other parts of the bot, so some things might look off.

### Lyrics Customizations
The bot allows users to choose between including and excluding the annotations from the lyrics. Users can also choose not to include ASCII or non-ASCII characters in the lyrics. One of the uses of this could be to remove English lines from songs that have been translated into Arabic or Persian so that only the translated lines remain.


### Telegram Features
Users can search Genius navigating the iline menu which can be accessed using the `/start` command. Alternatively, you could directly reach to the desired feature using commands:
- **/start**
  start the bot
- **/song**:
  search for a song
- **/album**:
  search for an album
- **/artist**:
  search for an artist
- **/lyrics_language**:
  set lyrics language
- **/include_annotations**:
  include annotations
- **/bot_language**:
  set bot language
- **/cancel**:
  cancel the current task
- **/help**:
  more info about the bot
- **/contact_us**:
  send us a message

You can also perform searches by using the inline search feature. For example:
Just type in the bot's username like `@the_bot ` to get a help menu. Alternatively:
- searching songs: `@the_bot .song we will rock you`
- searching albums: `@the_bot .album hotel diablo`
- searching artists: `@the_bot .artist Queen`
