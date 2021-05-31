import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

from sqlalchemy import BigInteger, Boolean, Column, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.types import TypeDecorator

from geniust.utils import log

logger = logging.getLogger("geniust")
Base = declarative_base()
RT = TypeVar("RT")


def init_db(db_uri: str) -> scoped_session:
    """initializes db using db_uri

    Args:
        db_uri (str): URI of database.

    Returns:
        scoped_session: Session factory.
    """
    engine = create_engine(db_uri)
    Base.metadata.create_all(engine)
    return scoped_session(sessionmaker(bind=engine, expire_on_commit=False))


def get_session(func: Callable[..., RT]) -> Callable[..., RT]:
    """Returns a DB session for the wrapped functions"""

    @wraps(func)
    def wrapper(self, *args, **kwargs) -> RT:
        with self.Session() as session:
            try:
                res = func(
                    self,
                    *args,
                    session=session,
                    **kwargs,
                )
            except Exception as e:
                session.rollback()
                raise e
            else:
                session.commit()
            return res

    return wrapper


class DBList(TypeDecorator):
    impl = String

    def __init__(self, sep: str = ",", **kwargs):
        super().__init__(**kwargs)
        self.sep = sep

    def process_bind_param(
        self, value: Union[List[str], List[str]], dialect: Any
    ) -> str:
        """processes values for database

        Args:
            value (Union[Tuple[str, ...], List[str]]): List or tuple of
                strings which contain either genres or artists.
            dialect (Any): DBAPI dialect.

        Returns:
            str: self.sep seperated string for insertion into database.
        """
        return f"{self.sep}".join(value)

    def process_result_value(self, value: str, dialect: Any) -> List[str]:
        """processes values returned from database

        Args:
            value (str): self.sep seperated values.
            dialect (Any): DBAPI dialect.

        Returns:
            List[str]: List of artists or genres.
        """
        return value.split(self.sep) if value else []


class Users(Base):
    __tablename__ = "user_data"
    chat_id = Column(BigInteger, primary_key=True)
    include_annotations = Column(Boolean)
    lyrics_lang = Column(String)
    bot_lang = Column(String)
    genius_token = Column(String)
    spotify_token = Column(String)

    def __init__(
        self,
        chat_id: int,
        include_annotations: bool,
        lyrics_lang: str,
        bot_lang: str,
        genius_token: Optional[str],
        spotify_token: Optional[str],
    ):
        self.chat_id = chat_id
        self.include_annotations = include_annotations
        self.lyrics_lang = lyrics_lang
        self.bot_lang = bot_lang
        self.genius_token = genius_token
        self.spotify_token = spotify_token

    def __repr__(self):
        return (
            "User(chat_id={chat_id!r}, "
            "include_annotations={include_annotations!r}, "
            "lyrics_lang={lyrics_lang!r}, "
            "bot_lang={bot_lang!r}, "
            "genius_token={genius_token!r}, "
            "spotify_token={spotify_token!r})"
        ).format(
            chat_id=self.chat_id,
            include_annotations=self.include_annotations,
            lyrics_lang=self.lyrics_lang,
            bot_lang=self.bot_lang,
            genius_token=True if self.genius_token else False,
            spotify_token=True if self.spotify_token else False,
        )


class Preferences(Base):
    __tablename__ = "user_preferences"
    chat_id = Column(BigInteger, primary_key=True)
    genres = Column(DBList(sep=","))
    artists = Column(DBList(sep=","))

    def __init__(
        self,
        genres: Tuple[str, ...],
        artists: Tuple[str, ...],
        chat_id: Optional[int] = None,
    ):
        self.chat_id = chat_id
        self.genres = genres
        self.artists = artists

    def __repr__(self):
        return "Preferences(Genres=({genres}), Artists=({artists}))".format(
            genres=", ".join(self.genres),
            artists=", ".join(self.artists),
        )


class Database:
    """Database class for all communications with the database."""

    def __init__(self, db_uri: str):
        self.Session = init_db(db_uri)

    @log
    @get_session
    def user(self, chat_id: int, user_data: dict, session=None) -> None:
        """Check for user in database, and create one if there's none

        This method will try to get user data from database and if it
        finds none, creates a user in the database and updates
        context.user_data wHich is passed through user_dict in both cases.

        Args:
            chat_id (int): Chat ID.
            user_data (dict): User data dictionary to update.
        """
        user = session.get(Users, chat_id)
        if user:
            preferences = self.get_preferences(chat_id)
        else:
            # create user data with default preferences
            user = Users(
                chat_id=chat_id,
                include_annotations=True,
                lyrics_lang="English + Non-English",
                bot_lang="en",
                genius_token=None,
                spotify_token=None,
            )
            preferences = None
            session.add(user)
            logger.debug("created user")
        user_data.update(
            {
                "include_annotations": user.include_annotations,
                "lyrics_lang": user.lyrics_lang,
                "bot_lang": user.bot_lang,
                "genius_token": user.genius_token,
                "spotify_token": user.spotify_token,
                "preferences": preferences,
            }
        )

    @get_session
    def update_include_annotations(
        self, chat_id: int, data: bool, session=None
    ) -> None:
        """Updates inclusing annotations in lyrics.

        Args:
            chat_id (int): Chat ID.
            data (bool): True or False.
        """
        session.query(Users).filter(Users.chat_id == chat_id).update(
            {Users.include_annotations: data}, synchronize_session=False
        )

    @get_session
    def update_lyrics_language(self, chat_id: int, data: str, session=None) -> None:
        """Updates the language of the lyrics.

        Args:
            chat_id (int): Chat ID.
            data (str): 'English', 'Non-English' or 'English + Non-English'.
        """
        session.query(Users).filter(Users.chat_id == chat_id).update(
            {Users.lyrics_lang: data}, synchronize_session=False
        )

    @get_session
    def update_bot_language(self, chat_id: int, data: str, session=None) -> None:
        """Updates the language of the bot.

        Args:
            chat_id (int): Chat ID.
            data (str): 'en', 'fa' or etc (ISO 639-1 codes).
        """
        session.query(Users).filter(Users.chat_id == chat_id).update(
            {Users.bot_lang: data}, synchronize_session=False
        )

    @get_session
    def update_token(
        self, chat_id: int, data: str, platform: str = None, session=None
    ) -> None:
        """Updates user's token.

        Args:
            chat_id (int): Chat ID.
            data (str): Genius user token.
            platform (str): Platform token to update (e.g. genius).
        """
        column = f"{platform}_token"
        session.query(Users).filter(Users.chat_id == chat_id).update(
            {column: data}, synchronize_session=False
        )

    @get_session
    def delete_token(self, chat_id: int, platform: str = None, session=None) -> None:
        """Removes user's token from database.

        Args:
            chat_id (int): Chat ID.
            platform (str): Platform token to delete (e.g. genius).
        """
        column = f"{platform}_token"
        session.query(Users).filter(Users.chat_id == chat_id).update(
            {column: None}, synchronize_session=False
        )

    @get_session
    def get_token(self, chat_id: int, platform: str, session=None) -> str:
        """Gets user's token from database.

        Args:
            chat_id (int): Chat ID.
            platform (str): Platform token to get (e.g. genius).

        Returns:
            str: Genius user token.
        """
        column = f"{platform}_token"
        return (
            session.query(getattr(Users, column))
            .filter(Users.chat_id == chat_id)
            .one()[0]
        )

    @get_session
    def get_tokens(self, chat_id: int, session=None) -> Dict[str, Optional[str]]:
        """Gets user's tokens from database.

        Args:
            chat_id (int): Chat ID.

        Returns:
            Dict[str, Optional[str]]: Dict with two keys.
                If key value is None, that token is not available.
        """
        res = (
            session.query(Users.genius_token, Users.spotify_token)
            .filter(Users.chat_id == chat_id)
            .one()
        )
        return dict(genius_token=res[0], spotify_token=res[1])

    @get_session
    def get_language(self, chat_id: int, session=None) -> str:
        """Gets user's bot language.

        Args:
            chat_id (int): Chat ID.

        Returns:
            str: 'en', 'fa' or etc (ISO 639-1 codes).
        """
        return session.query(Users.bot_lang).filter(Users.chat_id == chat_id).one()[0]

    @get_session
    def get_preferences(self, chat_id: int, session=None) -> Optional[Preferences]:
        """returns user's preferences

        Args:
            chat_id (int): Chat ID.

        Returns:
            Optional[Preferences]: User's preferences if user has some, else None.
        """
        return session.get(Preferences, chat_id)

    @get_session
    def update_preferences(
        self, chat_id: int, user_preferences: Preferences, session=None
    ) -> None:
        """Upserts user preferences

        If user has preferences, updates them. Otherwise creates new preferences
        entry for user.

        Args:
            chat_id (int): Chat ID.
            user_preferences (Preferences): User preferences.
        """
        pref = session.get(Preferences, chat_id)
        if pref is None:
            preferences = Preferences(
                chat_id=chat_id,
                genres=user_preferences.genres,
                artists=user_preferences.artists,
            )
            session.add(preferences)
        else:
            update = dict(
                genres=user_preferences.genres, artists=user_preferences.artists
            )
            session.query(Preferences).filter(Preferences.chat_id == chat_id).update(
                update, synchronize_session=False
            )

    @get_session
    def delete_preferences(self, chat_id: int, session=None) -> None:
        """Deletes user preferences from database

        Args:
            chat_id (int): Chat ID.
        """
        session.query(Preferences).filter(Preferences.chat_id == chat_id).delete()
