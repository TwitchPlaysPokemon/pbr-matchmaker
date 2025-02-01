import os
from setuptools import setup, find_packages


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
__version__ = open(os.path.join(ROOT_DIR, 'matchmaker', 'VERSION')).read().strip()


setup(
    name="pbrmatchmaker",
    version=__version__,
    packages=find_packages(),
    package_dir={"matchmaker": "matchmaker"},
    package_data={"matchmaker": ["./*.json", "utils/*.json", "config/**/*.yaml", "VERSION"]},
    install_requires=['pymongo', 'rainbow-logging-handler', 'gevent',
                      'pokecat @ git+https://github.com/TwitchPlaysPokemon/pokecat.git@v1.6.3#egg=pokecat'],

    author="ferraro2",
    description="Library to generate matches for TwitchPlaysPokemon.",
    url="https://github.com/TwitchPlaysPokemon/pbr-matchmaker",
)
