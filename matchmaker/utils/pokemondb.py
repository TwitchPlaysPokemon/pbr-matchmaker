# -*- coding: utf-8 -*-
# source code owned by Twitch Plays Pokemon AUTHORIZED USE ONLY see LICENSE.MD
import logging
from os import path
from datetime import datetime, timedelta

from bson.son import SON
from pymongo import UpdateOne

from .pbrpokemondb import get_pbr_pokemon_db

log = logging.getLogger(__name__)

_root_dir = path.dirname(path.abspath(__file__))
default_dir_path = path.join(_root_dir, "..", "..")

_POKEMON_DB_LOADERS = {
    "pbr": get_pbr_pokemon_db,
}

MAX_COOLDOWN = timedelta(weeks=4)


class PokemonSetRepository:
    def __init__(self, db, game_id, dir_path=default_dir_path):
        self.game_id = game_id
        log.info("loading pokemon db for game_id %s...", game_id)
        pokemon_db = _POKEMON_DB_LOADERS[game_id](dir_path=dir_path)
        log.info("loading pokemon db for game_id %s finished!", game_id)
        log.info("Length of pbr pokemon db: %d", len(pokemon_db))
        self.sets = db["pokesets"]
        log.info("preparing to update pokemon db data in database...")
        # first, mark every set as disabled
        self.sets.update_many({}, {"$set": {"enabled": False}})
        # upsert each pokemon set into db
        operations = []
        for pokeset in pokemon_db:
            pokeset_id = make_pokeset_db_id(pokeset)
            operations.append(UpdateOne(
                {"_id": pokeset_id},
                {
                    "$setOnInsert": {
                        "last_match": None,
                        "last_match_at": None,
                        "appearances": 0,
                    },
                    "$set": {
                        "data": pokeset,
                        "enabled": True,  # mark updated sets as enabled again
                    },
                },
                upsert=True,
            ))
        log.info("updating pokemon db data in database...")
        if operations:
            self.sets.bulk_write(operations, ordered=False)
        log.info("updating pokemon db data in database finished!")

    def get_by_id_components(self, species_id, setname):
        """Get the pokeset with these id components."""
        result = self.sets.find_one({"_id.species": species_id, "_id.setname": setname, "enabled": True})
        if not result:
            return None
        return result["data"]

    def get_by_species_id(self, species_id):
        return [p["data"] for p in self.sets.find({"_id.species": species_id, "enabled": True})]

    def get_by_species_id_and_tags(self, species_id, tags):
        return [p["data"] for p in
                self.sets.find({"_id.species": species_id, "enabled": True, "data.tags": {"$in": tags}})]

    def get_by_tags(self, tags):
        return [p["data"] for p in self.sets.find({"data.tags": {"$in": tags}})]


    def get_by(self, species_id=None, setname=None,
               tags_none=None, tags_any=None, tags_all=None,
               not_sets=None, not_species_ids=None,
               mixable=None, biddable=None, shinies=None, hidden=None):
        """Get a list of pokesets meeting the desired criteria."""
        if not_sets is None:
            not_sets = list()
        if not_species_ids is None:
            not_species_ids = list()
        and_queries = []
        query = {'enabled': True}
        if hidden is not None:
            query['data.hidden'] = hidden
        tags_query = {}
        if biddable is not None:
            query['biddable'] = biddable
        if mixable is not None:
            query['mixable'] = mixable
        if species_id is not None:
            query['_id.species'] = species_id
        if tags_none:
            tags_query["$nin"] = tags_none
        if tags_any:
            tags_query["$in"] = tags_any
        if tags_all:
            tags_query["$all"] = tags_all
        if shinies is not None:
            if shinies:
                query['data.shiny'] = True
            else:
                query['data.shiny'] = False
        if tags_query:
            query['data.tags'] = tags_query
        and_queries.append(query)

        for pokeset in not_sets:
            not_queries = []
            not_queries.append({'_id.species': {"$ne": pokeset['species']['id']}})
            not_queries.append({'_id.setname': {"$ne": pokeset['setname']}})
            and_queries.append({"$or": not_queries})

        for species_id in not_species_ids:
            and_queries.append({"_id.species": {"$ne": species_id}})

        query = {'$and': and_queries}
        sets = self.sets.find(query)
        if setname:
            sets = (s for s in sets if s['data']['setname'].lower() == setname.lower())
        return list(sets)

    def find(self, query=None, **kw):
        if query is None:
            query = {}
        return self.sets.find({**query, **{"enabled": True}}, **kw)

    def update_rarities(self):
        species_data = self.sets.aggregate([
            {"$match": {"enabled": True}},
            {"$group": {
                "_id": "$_id.species",
                "count": {"$sum": 1},
                "last_match_at": {"$max": "$last_match_at"},
            }},
        ])
        species_modifiers = {}
        now = datetime.utcnow()
        for species in species_data:
            last_match_date = species["last_match_at"]
            last_match_time = now - last_match_date if last_match_date else MAX_COOLDOWN
            modifier = last_match_time.total_seconds() / MAX_COOLDOWN.total_seconds()
            modifier = min(modifier, 1.0)
            species_modifiers[species["_id"]] = modifier / species["count"]
        bulk_ops = []
        for pokeset in self.find():
            species_id = pokeset["_id"]["species"]
            modifier = species_modifiers[species_id]
            bulk_ops.append(UpdateOne(
                {"_id": make_pokeset_db_id(pokeset["data"])},
                {"$set": {"effective_rarity": pokeset["data"]["rarity"] * modifier}}))
        self.sets.bulk_write(bulk_ops)

    def update_set_appearance(self, set_id, match_id, match_started_at):
        self.sets.update_one(
            {"_id": set_id},
            {
                "$set": {
                    "last_match": match_id,
                    "last_match_at": match_started_at,
                },
                "$inc": {"appearances": 1}
            },
            upsert=True,
        )

    def get_last_match_date_for_species(self, species_id):
        """Returns the last match document from the database matching
        the give pokemon id."""
        result = self.sets.find_one({"_id.species": species_id, "enabled": True}, sort=[("last_match_at", -1)])
        if result:
            return result["last_match_at"]


def make_pokeset_db_id(pokeset):
    pokeset_id = SON()
    pokeset_id["setname"] = pokeset["setname"]
    pokeset_id["species"] = pokeset["species"]["id"]
    return pokeset_id
