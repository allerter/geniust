import pathlib
from setuptools import setup, find_packages


here = pathlib.Path(__file__).parent.resolve()

with open(here / 'requirements.txt', 'r') as f:
    requirements = f.read().split()

with open(here / 'runtime.txt', 'r') as f:
    runtime = f.read().replace('python-', '')


extras_require = {
    'checks': [
        'mypy==0.790',
        'black==20.8b1'
    ],
    'tests': [
        'pytest==6.1.2',
        'pytest-lazy-fixture==0.6.3',
    ]}

extras_require['dev'] = extras_require['checks'] + extras_require['tests']

setup(
    name="geniust",
    packages=find_packages(exclude=('tests', 'tests.*',)),
    install_requires=requirements,
    extras_require=extras_require,
    python_requires='>=' + runtime
)
