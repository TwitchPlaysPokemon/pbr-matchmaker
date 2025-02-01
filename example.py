from gevent import monkey; monkey.patch_all()  # monkeypatch everything to enable gevent magic
import sys
import pymongo
import logging.handlers
import os
from rainbow_logging_handler import RainbowLoggingHandler

from matchmaker import *
from matchmaker.utils.pokemondb import PokemonSetRepository


# set up the logger
log = logging.getLogger()
log.setLevel(logging.DEBUG)
# set up the file logger
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matchmaker.log")
formatter = logging.Formatter(
    "[%(asctime)s] %(name)s %(funcName)s():%(lineno)d %(levelname)s\t%(message)s")  # same as default
handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=1024 * 1024 * 100, backupCount=5, encoding='utf-8')
handler.setFormatter(formatter)
log.addHandler(handler)
# set up the console logger
formatter = logging.Formatter("%(name)s %(funcName)s():%(lineno)d %(levelname)s\t%(message)s")
console_handler = RainbowLoggingHandler(sys.stdout, color_funcName=('black', 'yellow', True))
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
log.addHandler(console_handler)

# Initialize mongo db client
mongodb_uri = "mongodb://localhost:27017/"
database_name = "tpp3"
log.info("setting up database connection (connection uri <%s>, database name: %s)",
         mongodb_uri, database_name)
mongodb_client = pymongo.MongoClient(mongodb_uri)
db = mongodb_client[database_name]

# Populate the db with pokesets
pokemon_sets = PokemonSetRepository(db, "pbr")

# Load matchmaker
log.info("setting up matchmaker")
matchmaker = Matchmaker('standard', pokemon_sets, 'pbr', bet_bonus_enabled=True)

# Make a sample match and print it
match = matchmaker.make()
log.info(match)
