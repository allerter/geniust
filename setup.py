import pathlib
from setuptools import setup, find_packages


here = pathlib.Path(__file__).parent.resolve()

with open(here / 'requirements.txt', 'r') as f:
    requirements = f.read().split()

with open(here / 'runtime.txt', 'r') as f:
    runtime = f.read().replace('python-', '')


extras_require = {
    'tests': [
        'pytest==6.1.2',
        'pytest-lazy-fixture==0.6.3',
    ]}

setup(
    name="geniust",
    packages=find_packages(exclude=('tests', 'tests.*',)),
    install_requires=requirements,
    extras_require=extras_require,
    python_requires='>=' + runtime
)
