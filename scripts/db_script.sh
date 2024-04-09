# install postgres
 sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
 wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
 sudo apt-get update
 sudo apt-get -y install postgresql


# set up database
 sudo -i -u postgres

psql
\password 
CREATE TABLE user_data (
    chat_id BIGINT UNIQUE,
    include_annotations BOOLEAN DEFAULT True,
    lyrics_lang TEXT DEFAULT 'English + Non-English',
    bot_lang TEXT DEFAULT 'en',
    genius_token TEXT DEFAULT NULL,
    spotify_token TEXT DEFAULT NULL
)

