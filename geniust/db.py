import logging
from functools import wraps

import psycopg2

from geniust.constants import DATABASE_URL
from geniust.utils import log


logging.getLogger().setLevel(logging.DEBUG)


def get_cursor(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with psycopg2.connect(DATABASE_URL, sslmode='require') as con:
            with con.cursor() as cursor:
                return func(self, *args, **kwargs, cursor=cursor)
    return wrapper


class Database:

    def __init__(self, table):
        self.table = table

    @log
    def user(self, chat_id, user_data):
        """Check for user in database, and create one if there's none"""
        res = self.select(chat_id)
        if res:
            user_data.update(res)
        else:
            # create user data with default preferences
            include_annotations = True
            lyrics_language = 'English + Non-English'
            bot_language = 'en'
            user_data.update(
                {'include_annotations': include_annotations,
                 'lyrics_lang': lyrics_language,
                 'bot_lang': bot_language,
                 'token': None
                 }
            )
            self.insert(
                chat_id,
                include_annotations,
                lyrics_language,
                bot_language
            )
            logging.debug('created user')

    @log
    @get_cursor
    def insert(self, chat_id, *data, cursor):
        include_annotations, lyrics_lang, bot_language = data
        values = (chat_id, include_annotations, lyrics_lang, bot_language)
        query = f"""INSERT INTO {self.table} VALUES (%s, %s, %s, %s);"""

        cursor.execute(query, values)

    @log
    @get_cursor
    def select(self, chat_id, cursor, column='*'):
        res = ''
        query = f"""
        SELECT {column}
        FROM {self.table}
        WHERE chat_id = {chat_id};
        """

        # connect to database
        cursor.execute(query)
        res = cursor.fetchall()
        if res:
            res = res[0]
            if column == '*':
                res = {'chat_id': res[0],
                       'include_annotations': res[1],
                       'lyrics_lang': res[2],
                       'bot_lang': res[3],
                       'token': res[4]}
            else:
                res = {column: res[0]}
        return res

    @log
    @get_cursor
    def update(self, chat_id, data, update, cursor):

        query = f"UPDATE {self.table} SET {update} = %s WHERE chat_id = {chat_id};"
        values = (data,)

        # connect to database
        cursor.execute(query, values)

    def update_include_annotations(self, chat_id, data):
        self.update(chat_id, data, 'include_annotations')

    def update_lyrics_language(self, chat_id, data):
        self.update(chat_id, data, 'lyrics_lang')

    def update_bot_language(self, chat_id, data):
        self.update(chat_id, data, 'bot_lang')

    def update_token(self, chat_id, data):
        self.update(chat_id, data, 'token')

    def delete_token(self, chat_id):
        self.update(chat_id, None, 'token')

    def get_token(self, chat_id):
        return self.select(chat_id, column='token').get('token')

    def get_language(self, chat_id):
        return self.select(chat_id, column='bot_lang').get('bot_lang')
