import logging
from functools import wraps
from typing import Any, List, TypeVar, Callable, Optional, Tuple, Union, Dict

import psycopg2

from geniust.constants import DATABASE_URL, Preferences
from geniust.utils import log

logging.getLogger('geniust').setLevel(logging.DEBUG)

RT = TypeVar("RT")


def get_cursor(func: Callable[..., RT]) -> Callable[..., RT]:
    """Returns a DB cursor for the wrapped functions"""

    @wraps(func)
    def wrapper(self, *args, **kwargs) -> RT:
        with psycopg2.connect(DATABASE_URL, sslmode="require") as con:
            with con.cursor() as cursor:
                return func(self, *args, **kwargs, cursor=cursor)

    return wrapper


class Database:
    """Database class for all communications with the database."""

    def __init__(self, data_table, preferences_table):
        self.preferences_table = preferences_table
        self.data_table = data_table

    @log
    def user(self, chat_id: int, user_data: dict) -> None:
        """Check for user in database, and create one if there's none

        This method will try to get user data from database and if it
        finds none, creates a user in the database and updates
        context.user_data wHich is passed through user_dict in both cases.

        Args:
            chat_id (int): Chat ID.
            user_data (dict): User data dictionary to update.
        """
        res = self.select(chat_id)
        if res:
            preferences = self.get_preferences(chat_id)
            res.update({'preferences': preferences})
            user_data.update(res)
        else:
            # create user data with default preferences
            include_annotations = True
            lyrics_language = "English + Non-English"
            bot_language = "en"
            genius_token = None
            spotify_token = None
            preferences = None
            user_data.update(
                {
                    "include_annotations": include_annotations,
                    "lyrics_lang": lyrics_language,
                    "bot_lang": bot_language,
                    "genius_token": genius_token,
                    "spotify_token": spotify_token,
                    "preferences": preferences
                }
            )
            self.insert(chat_id, include_annotations, lyrics_language, bot_language)
            logging.debug("created user")

    @log
    @get_cursor
    def insert(
        self,
        chat_id: int,
        *data: Tuple[bool, str, str, Optional[str]],
        table: str = 'user_data',
        cursor: Any
    ) -> None:
        """Inserts data into database.

        Args:
            chat_id (int): Chat ID.
            data (tuple): data fields for user.
            table (str): table to insert into.
            cursor (Any): database cursor.
        """
        values = (chat_id, *data)
        if table == self.data_table:
            query = f"""INSERT INTO {table} VALUES (%s, %s, %s, %s);"""
        else:
            query = f"""INSERT INTO {table} VALUES (%s, %s, %s);"""

        cursor.execute(query, values)

    @log
    @get_cursor
    def upsert(
        self,
        chat_id: int,
        *data: List,
        table: str = 'user_data',
        cursor: Any
    ) -> None:
        """Inserts data if chat_id is not duplicate, otherwise updates.

        Args:
            chat_id (int): Chat ID.
            data (tuple): data fields for user.
            table (str): table to insert into.
            cursor (Any): database cursor.
        """
        values = [chat_id, *data]
        if table == self.data_table:
            query = f"""INSERT INTO {table} VALUES (%s, %s, %s, %s)
              ON CONFLICT (chat_id) DO UPDATE
              SET include_annotations = excluded.include_annotations,
                  lyrics_lang = excluded.lyrics_lang
                  bot_lang = excluded.bot_lang;"""
        else:
            query = f"""INSERT INTO {table} VALUES (%s, %s, %s)
              ON CONFLICT (chat_id) DO UPDATE
              SET genres = excluded.genres,
                  artists = excluded.artists;"""

        cursor.execute(query, values)

    @log
    @get_cursor
    def select(
        self,
        chat_id: int,
        cursor: Any,
        column: str = "*",
        table: str = 'user_data'
    ) -> Dict[str, Any]:
        """Selects values from table.

        Args:
            chat_id (int): Chat ID.
            cursor (Any): Database cursor.
            column (str, optional): Column to get value from.
                Defaults to all columns ('*').

        Returns:
            Dict[str, Any]: User data.
        """
        query = f"""
        SELECT {column}
        FROM {table}
        WHERE chat_id = {chat_id};
        """

        # connect to database
        cursor.execute(query)
        res = cursor.fetchone()
        if res is not None:
            if column == "*":
                assert table, self.data_table
                res = {
                    "chat_id": res[0],
                    "include_annotations": res[1],
                    "lyrics_lang": res[2],
                    "bot_lang": res[3],
                    "genius_token": res[4],
                    "spotify_token": res[5],
                }
            elif len(column.split(',')) > 1:
                values = {}
                for i, column in enumerate(column.split(',')):
                    values[column] = res[i]
                res = values
            else:
                res = {column: res[0]}

        return res

    @log
    @get_cursor
    def update(
        self,
        chat_id: int,
        data: Union[bool, str, None],
        update: str,
        cursor: Any,
        table: str = 'user_data',
    ):
        """Updates user data.

        Args:
            chat_id (int): Chat ID.
            data (Union[bool, str, None]): New data.
            update (str): Column to update.
            cursor (Any): Database cursor.
        """
        if table == 'user_data':
            query = f"UPDATE {table} SET {update} = %s WHERE chat_id = {chat_id};"
            values = (data,)
        else:
            query = f"UPDATE {table} SET genres = %s, artists = %s WHERE chat_id = {chat_id};"
            values = data

        # connect to database
        cursor.execute(query, values)

    def update_include_annotations(self, chat_id: int, data: bool) -> None:
        """Updates inclusing annotations in lyrics.

        Args:
            chat_id (int): Chat ID.
            data (bool): True or False.
        """
        self.update(chat_id, data, "include_annotations")

    def update_lyrics_language(self, chat_id: int, data: str) -> None:
        """Updates the language of the lyrics.

        Args:
            chat_id (int): Chat ID.
            data (str): 'English', 'Non-English' or 'English + Non-English'.
        """
        self.update(chat_id, data, "lyrics_lang")

    def update_bot_language(self, chat_id: int, data: str) -> None:
        """Updates the language of the bot.

        Args:
            chat_id (int): Chat ID.
            data (str): 'en', 'fa' or etc (ISO 639-1 codes).
        """
        self.update(chat_id, data, "bot_lang")

    def update_token(self, chat_id: int, data: str, platform: str) -> None:
        """Updates user's token.

        Args:
            chat_id (int): Chat ID.
            data (str): Genius user token.
            platform (str): Platform token to update (e.g. genius).
        """
        column = f"{platform}_token"
        self.update(chat_id, data, column)

    def delete_token(self, chat_id: int, platform: str) -> None:
        """Removes user's token from database.

        Args:
            chat_id (int): Chat ID.
            platform (str): Platform token to delete (e.g. genius).
        """
        column = f"{platform}_token"
        self.update(chat_id, None, column)

    def get_token(self, chat_id: int, platform: str) -> str:
        """Gets user's token from database.

        Args:
            chat_id (int): Chat ID.
            platform (str): Platform token to get (e.g. genius).

        Returns:
            str: Genius user token.
        """
        column = f"{platform}_token"
        return self.select(chat_id, column=column).get(column)  # type: ignore

    def get_tokens(self, chat_id: int) -> Dict[str, Any]:
        """Gets user's tokens from database.

        Args:
            chat_id (int): Chat ID.

        Returns:
            str: Genius user token.
        """
        return self.select(chat_id, column="genius_token,spotify_token")  # type: ignore

    def get_language(self, chat_id: int) -> str:
        """Gets user's bot language.

        Args:
            chat_id (int): Chat ID.

        Returns:
            str: 'en', 'fa' or etc (ISO 639-1 codes).
        """
        return self.select(chat_id, column="bot_lang").get("bot_lang")  # type: ignore

    def get_preferences(self, chat_id: int) -> Optional[Preferences]:
        res = self.select(chat_id,
                          column='genres,artists',
                          table=self.preferences_table)

        if res is None or not res['genres']:
            return None
        else:
            return Preferences(res['genres'], res['artists'])

    def update_preferences(self, chat_id: int, user_preferences: Preferences) -> None:
        self.upsert(chat_id,
                    user_preferences.genres,
                    user_preferences.artists,
                    table=self.preferences_table)

    def delete_preferences(self, chat_id: int) -> None:
        self.update(chat_id,
                    data=(None, None),
                    update=None,
                    table=self.preferences_table)
