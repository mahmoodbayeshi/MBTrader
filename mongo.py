import pymongo
from pymongo import ReturnDocument
from utils import logger,log,get_staging
from bson.objectid import ObjectId
import datetime
import inspect
import os
import pandas as pd

MONGO_URI = os.getenv('MONGO_URL','mongodb://localhost:27017/toptrader_local')

class Mongo():

    def __init__(self, uri, db=None):
        self.database = None
        self.client = None
        try:
            self.client = pymongo.MongoClient(uri, retryWrites=False)
            if self.client:
                if db is None:
                    self.database = self.client.get_default_database()
                else:
                    self.database = self.client[db]
        except Exception as e:
            logger.error(e, exc_info=True)

    def collection(self, collection, db=None):
        db_c = self.database
        if db:
            db_c = self.client[db]
        return db_c[collection]

    @property
    def db(self, db=None):
        if db:
            return self.database
        return self.client[db]

    def set_db(self, db):
        if db:
            self.database = self.client[db]
        return self.database

    def __getitem__(self, key):
        return self.collection(key)


ALLOWED_DATA_TYPES = [list, int, float, str, object, bool, dict,
                      {'name':"datetime","class":datetime.date},
                      {'name':"time","class":datetime.time},
                      {'name':"object_id","class":ObjectId}
                    ]


class Base():
    collection = ''
    base_fields = ['base_fields','collection','data']
    _id = 'object_id'

    def __init__(self, data=None,internal=False):
        self.data={}
        if data:
            if internal:
                self.data=dict(data).copy()
            else:
                for k, v in data.items():
                    self[k] = v

    @classmethod
    def fields(cls):
        fields={}
        for k,v in cls.__dict__.items():
            if k=='_id':
                fields[k]='object_id'
            else :
                if not k.startswith('_') \
                        and not callable(v)\
                        and not isinstance(v,classmethod)\
                        and not isinstance(v,staticmethod)\
                        and k not in cls.base_fields:
                    fields[k]=v
        return fields

    def validate(self, key, value, exception=False):
        fields = self.fields()
        if key == '_id':
            if isinstance(value, ObjectId):
                return value
        elif key in fields:
            valids = fields[key]
            if "nullable" in valids and not value:
                return None
            if isinstance(valids, list):
                if value in valids:
                    return value
            else:
                for t in ALLOWED_DATA_TYPES:
                    if isinstance(t,dict):
                        if 'name' in t and 'class' in t:
                            if isinstance(value,t['class']):
                                return  value
                    elif t.__name__ in valids:
                        if 'convert' in valids:
                            return t(value)
                        if isinstance(value, t):
                            return value

                if inspect.isclass(valids) and isinstance(value, valids.__class__):
                    return value
            if exception:
                raise ModelValueException('validation for {} failed. value={}'.format(key, value))
            return None
        if exception:
            raise NoExistsException('field "{}" not exists in model fields: {}'.format(key, list(fields.keys())))
        return None

    def __setitem__(self, key, value):
        if key in self.base_fields:
            raise ModelValueException('cannot set {}'.format(key))
        self.data[key] = self.validate(key, value, exception=True)

    def __getitem__(self, item):
        return self.data[item]

    def __dict__(self):
        return self.data.copy()


    def __contains__(self, item):
        return item in self.data

    def __iter__(self):
        yield from self.data.items()

    def __str__(self):
        return str(self.data)

    def __getattribute__(self, item):
        if item == 'fields' :
            return super(Base,self).__getattribute__(item)
        if item in self.fields():
            return item
        return super(Base,self).__getattribute__(item)

    def __setattr__(self, key, value):
        if key == 'fields' :
            return super(Base,self).__setattr__(key,value)
        if key in self.fields():
            return self.__setitem__(key,value)
        return super(Base,self).__setattr__(key,value)

    def get(self,key,default=None):
        return self.data.get(key,default)

    def setId(self, _id):
        self.data['_id'] = _id

    def update(self, values):
        for k, v in values.items():
            self.data[k] = self.validate(k, v, exception=True)

    def keys(self):
        self.fields().keys()

    def values(self):
        self.data.values()

    def save(self, **args):
        if not self.collection:
            raise CollectionException('collection field is not set.')
        if "_id" not in self.data:
            r = DB.collection(self.collection).insert_one(self.data, **args)
            self.setId(r.inserted_id)
            return r
        else:
            r = DB.collection(self.collection).update_one({"_id": self.data['_id']}, {'$set':self.data}, **args)
            return r

    def delete(self):
        if '_id' in self.data:
            return self.delete_one({"_id":self.data['_id']})
        return True

    @classmethod
    def find_one(cls, filter=None, **args):
        if isinstance(filter, str):
            filter = {"_id": ObjectId(filter)}
        r =DB.collection(cls.collection).find_one(filter=filter,**args)
        if not r:
            return None
        return cls(r,internal=True)

    @classmethod
    def find(cls, filter=None, **args):
        if isinstance(filter, str):
            filter = {"_id": ObjectId(filter)}
        a = DB.collection(cls.collection).find(filter=filter,**args)
        for r in a:
            yield cls(r,internal=True)

    @classmethod
    def find_or_insert(cls, filter, update, **args):
        if isinstance(filter, str):
            filter = {"_id": filter}
        return cls(DB.collection(cls.collection).find_one_and_update(filter, update,return_document=ReturnDocument.AFTER, **args))

    @classmethod
    def find_one_and_replace(cls, filter, replace, **args):
        if isinstance(filter, str):
            filter = {"_id": filter}
        return cls(DB.collection(cls.collection).find_one_and_replace(filter, replace,return_document=ReturnDocument.AFTER, **args))

    @classmethod
    def find_one_and_delete(cls, filter, update, **args):
        if isinstance(filter, str):
            filter = {"_id": filter}
        return DB.collection(cls.collection).find_one_and_delete(filter, update, **args)

    @classmethod
    def delete_many(cls, filter, **args):
        if isinstance(filter, str):
            filter = {"_id": filter}
        return DB.collection(cls.collection).delete_many(filter, **args)

    @classmethod
    def delete_one(cls, filter, **args):
        if isinstance(filter, str):
            filter = {"_id": filter}
        return DB.collection(cls.collection).delete_one(filter, **args)

    @classmethod
    def distinct(cls, field, **args):
        return DB.collection(cls.collection).distinct(field, **args)

    @classmethod
    def get_collection(cls):
        return DB.collection(cls.collection)

    def as_dict(self):
        return self.__dict__()

    @classmethod
    def as_dataframe(cls,a):
        r=pd.DataFrame([x.as_dict() for x in a])
        for f in cls.fields():
            if f not in r.columns :
                r[f] = None
        return r


class ModelValueException(Exception):
    pass


class CollectionException(Exception):
    pass


class NoExistsException(Exception):
    pass


DB = Mongo(MONGO_URI,'mbtrader_{}'.format(get_staging()))

log("DB_NAME",DB.database.name)
