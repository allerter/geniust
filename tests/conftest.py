import pytest

from geniust import api


@pytest.fixture(scope='session')
def song_id():
    return 4589365


@pytest.fixture(scope='session')
def song_url():
    return 'https://genius.com/Machine-gun-kelly-glass-house-lyrics'


@pytest.fixture(scope='session')
def genius():
    return api.GeniusT()
