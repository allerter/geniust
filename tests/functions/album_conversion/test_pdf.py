from io import BytesIO
from os.path import join
from unittest.mock import patch, MagicMock

import pytest

from geniust.functions import album_conversion


@pytest.mark.parametrize('text, arabic', [('test', False), ('تست', True)])
def test_get_farsi_text(text, arabic):

    res_text, res_arabic = album_conversion.pdf.get_farsi_text(text)

    assert res_arabic == arabic


@pytest.fixture(scope='module')
def cover_art(data_path):
    with open(join(data_path, 'cover_art.jpg'), 'rb') as f:
        return f.read()


@pytest.mark.parametrize('user_data', [{'lyrics_lang': 'English',
                                        'include_annotations': True},
                                       {'lyrics_lang': 'Non-English',
                                        'include_annotations': False}
                                       ])
def test_create_pdf(full_album, user_data, cover_art):
    request = MagicMock()
    request().content = cover_art

    with patch('requests.get', request):
        res = album_conversion.create_pdf(full_album, user_data)

    assert isinstance(res, BytesIO)
    assert res.tell() == 0
    assert res.name.endswith('.pdf')
