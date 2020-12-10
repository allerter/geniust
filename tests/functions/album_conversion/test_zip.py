from zipfile import ZipFile
from io import BytesIO

import pytest

from geniust.functions import album_conversion


users = [
    {"lyrics_lang": "English", "include_annotations": True},
    {"lyrics_lang": "Non-English", "include_annotations": False},
]


@pytest.fixture(params=users)
def files(request, full_album):
    user_data = request.param
    res = album_conversion.create_zip(full_album, user_data)

    assert isinstance(res, BytesIO)
    assert res.tell() == 0
    assert res.name.endswith(".zip")

    with ZipFile(res) as zip_file:
        yield user_data, zip_file


def test_create_zip(full_album, files):
    user_data, zip_file = files
    include_annotations = user_data["include_annotations"]

    songs = zip_file.namelist()

    assert len(songs) == len(full_album["tracks"])
    for i, file in enumerate(songs):
        with zip_file.open(file) as song:
            lyrics = str(song.read())
            annotations_count = lyrics.count("!--!")
            if include_annotations:
                assert annotations_count == len(
                    full_album["tracks"][i]["song"]["annotations"]
                )
            else:
                assert annotations_count == 0
