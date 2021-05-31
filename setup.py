import pathlib

from setuptools import find_packages, setup

here = pathlib.Path(__file__).parent.resolve()

with open(here / "runtime.txt", "r") as f:
    runtime = f.read().replace("python-", "")


with open(here / "geniust" / "VERSION") as version_file:
    version = version_file.read().strip()

readme_file = here / "README.md"

extras_require = {
    "checks": [
        "tox==3.23.1",
        "mypy==0.812",
        "black==21.5b2",
        "isort==5.8.0",
        "flake8==3.9.2",
        "flake8-bugbear==21.4.3",
        "sqlalchemy-stubs==0.4",
    ],
    "tests": [
        "pytest==6.2.4",
        "pytest-asyncio==0.15.1",
        "pytest-lazy-fixture==0.6.3",
        "coverage==5.5",
        "requests-mock==1.9.3",
    ],
}

extras_require["dev"] = extras_require["checks"] + extras_require["tests"]

setup(
    name="geniust",
    author="allerter",
    license="MIT",
    description="Genius T gets you music info and lyrics on Telegram.",
    long_description=readme_file.read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/allerter/geniust",
    version=version,
    packages=find_packages(
        exclude=(
            "tests",
            "tests.*",
        )
    ),
    extras_require=extras_require,
    python_requires=">=" + runtime,
)
