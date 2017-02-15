from datetime import datetime
from mongoengine import *


def station(collection='radio'):

    class Station(Document):
        media_id = StringField(required=True, unique=True)
        cover = StringField()
        cover_full = StringField()
        title = StringField(required=True)
        description = StringField()
        genres = ListField(StringField(), default=list)
        country = StringField()
        city = StringField()
        language = StringField()
        band = StringField()
        contact = DictField(default=dict)
        streams = ListField(DictField(), default=list)
        updated_at = DateTimeField(default=datetime.now)
        referers = DictField(default=dict)
        extra = DictField(default=dict)

        meta = {
            'indexes': [
                {'fields': ['media_id']}
            ],
            'collection': collection
        }
    return Station

connect('radios')
