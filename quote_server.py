import json
import random

from errors import *

# In the future, maybe make this a sort of generic class that works on a given .json
# document. The class shall only work on one file at a time but the user has to
# instantiate an object of it with a path to that file.
# This could be especially useful, if I ever want to add multiple language support
# (a separate json file for every language)
# I would recommend to use a singleton pattern for this. In python, there is the
# singleton-decorator lib on PyPi - maybe use that one.


class QuoteServer:
    filename: str = 'quotes.json'

    # load all the data from the json file
    with open(filename, encoding='utf-8') as json_file:
        quotes = json.load(json_file)


    @classmethod
    def get_quote(cls, quote_path: str) -> str:
        choices = cls.get_choices(quote_path)
        return random.choice(choices)


    @classmethod
    def get_choices(cls, quote_path: str) -> list[str]:
        path_nodes: list[str] = quote_path.split('/')
        results = cls.quotes

        for node in path_nodes:
            # get the next node, which will either be a dict (json object) or a list (json array)
            results = results.get(node)

            # if results is none, then the given key didn't exist in the dictionary
            if results is None:
                raise QuoteServerException(f'Invalid JSON path! Node "{node}" does not exist in {cls.filename}',
                                           Cause.INVALID_JSON_PATH, quote_path=quote_path, error_node=node)

            # if results is of type list now, we arrived at our
            if isinstance(results, list):
                # choose random entry in list and return it
                return results

        # final node in path was not a list -> check if there is a 'default' list
        if default := results.get("default") is not None:
            return default

        # if we reached this part of the code, then all nodes were valid keys but didn't lead to a list of quotes
        raise QuoteServerException(f'Given path "{quote_path}" does not lead to a collection of strings!',
                                   Cause.NOT_AN_ENDPOINT, quote_path=quote_path, error_node='')
