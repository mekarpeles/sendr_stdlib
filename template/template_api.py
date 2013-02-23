
from functools import partial
from copy import deepcopy
import datetime
from decimal import Decimal
import web
from json import JSONEncoder

class API_Template(object):
    
    DB = None
    SCHEMA = {}
    TABLE = ""
    PRIMARY_KEY = ""

    def __init__(self, obj_id=None, raw_data=None, db=None, primary_key=None, table=None, schema=None):
        self.primary_key = primary_key
        self.schema = schema
        self.table = table
        self.obj_id = obj_id
        self._raw_data = raw_data
        self._construct_obj()

    def _construct_obj(self):
        """ Builds object according to parameters set in __init__ """
        if self.obj_id:
            self._construct_obj_from_id()
        elif self._raw_data:
            self._construct_obj_from_data()
        else:
            self._construct_obj_from_defaults()

    def _construct_obj_from_id(self):
        """ Load data for object with primary key = obj_id """
        self._raw_data = self._get_query(self.obj_id, db=self.DB)
        self._set_data(self._raw_data)


    def _construct_obj_from_data(self):
        """
        Load-hook to get_all and dynamically compose objects using a
        map over the constructor.

        """
        if self.primary_key in self._raw_data:
            self.obj_id = self._raw_data[self.primary_key]
        else:
            self.obj_id = None
        self._set_data(self._raw_data)

    def _construct_obj_from_defaults(self):
        """
        This private method can be overloaded in the child class to
        accommodate the need to very specific object defaults (certain
        default values for certain keys)

        If object is being initialized without raw_data or obj_id,
        fallback to default: initialize self to have property for
        every key in SCHEMA with empty values

        """
        for key in self.schema:
            db_field = self.schema[key]
            setattr(self, key, None)
        self._inject_custom_keys()

    def _set_data(self, raw_data):
        """
        Assumes we have our object_id + raw_data (storage object data
        from db). Sets data for the correct keys as properties.

        VERBOSE: For each key in SCHEMA, creates a property and, using
        the SCHEMA mapping, assigns the correct corresponding property
        value according to the contents of the fetched (self_data)
        storage object db data

        """
        for key, db_key in self.schema.items():
            if db_key in raw_data:
                setattr(self, key, raw_data[db_key])
        self._inject_custom_keys(raw_data)

    def _clean_keys(self, db_operation=False, safe=False, JSON=False):
        """
        Returns a dictionary containing only the keys from the table
        schema (minus the primary key)

        """
        attrs = {}            

        # loop through SCHEMA
        for skey in self.schema:
            val = getattr(self, self.schema[skey], None)
            if val:
                attrs[skey] = val

        if db_operation and self.primary_key in attrs:
            del attrs[self.primary_key]

        # XXX WARNING: This should only be done if 'created' and
        # 'modified' aren't already set. What if this item already
        # exists in the db? We don't want its created time modified if
        # this is the case.
        if 'created' in self.schema:
            timestamp = str(datetime.datetime.utcnow())
            attrs[self.schema['created']] = timestamp
        if 'modified' in self.schema:
            attrs[self.schema['modified']] = timestamp

        if safe and 'password' in self.schema:
            del attrs['password']
            del attrs['salt']

        return attrs

    def _json_serializable(self, safe=True):
        """I think this is for the most part the right idea but it should
        really be overridden on a per-class basis.
        """
        attrs = {}
        for key in self.schema:
            val = getattr(self, self.schema[key], None)
            if val:
                if not safe or (safe and not (key == 'password' or key == 'salt')):
                    attrs[key] = str(val)
        return attrs

    def update(self):
        """
        TODO: Use the object's current (possibly modified since init)
        property values and use them to update the object's db entry

        """        
        self._validate()
        pkey = getattr(self, self.primary_key, None)
        if pkey:
            attrs = self._clean_keys(db_operation=True)
            where = "%s=%s" % (self.primary_key, pkey)
            with self.DB.transaction():
                if self.DB.update(self.table, where=where, **attrs):
                    return self.primary_key
        return None

    def insert(self):
        """
        The insert method might be used when an object was created
        via self._set_defaults() - it creates a new entry entry in the
        db from its property values

        """
        self._validate()
        pkey = getattr(self, self.primary_key, None)        
        if not pkey:            
            attrs = self._clean_keys(db_operation=True)
            t = self.DB.transaction()
            try:
                entry_id = self.DB.insert(self.table, **attrs)
            except Exception as e:
                t.rollback()
                raise e
            else:
                t.commit()
                setattr(self, self.primary_key, entry_id)
                return entry_id
        return False

    def _validate(self):
        """
        Validate the object, make sure all values are legal and types
        are compliant to all contracts.

        Use case: Before an update or insert is performed, require
        that constraints are met. This should be overriden if your
        class has specific constraints which should prevent insertion
        or updating from succeeding.

        Example:
        >>> u = User(1)
        >>> u.email
        "bademail@"
        >>> u.update() # this should throw an exception (ValueError or
                       # TypeError) does not perform update since constraints
                       # not met

        """
        pass
    
    def delete(self):
        """
        Removes this object/entry from the database, where referenced
        by primary_key

        """
        where = {self.primary_key: self.obj_id}
        return self.DB.delete(self.table, where="%s=%s" % (self.primary_key, self.obj_id))

    @classmethod
    def construct(cls, cls_data):
        """
        Called as
        >>> my_object_list = map(cls.construct, list(db.select(cls.table)))
        """
        return cls(raw_data=cls_data)

    def _inject_custom_keys(self, obj=None):
        """
        This method exists purely to be overloaded. This logic is
        overloaded in order to insert additional keys into the
        query. The default behaviour is to return the original object,
        unmodified.
        
        e.g:
        The Product class for Marketplace does a join on 2 tables but
        also includes additional keys like 'img' to be updated to a
        value after the query is performed. This will take the storage
        object from the query and insert additional keys, values

        """
        return obj

    @classmethod 
    def get_by(cls, attribute, value, **kwargs):
        """
        Retrieves a user object
        """
        db = kwargs.get('db', cls.DB)
        where = { cls.SCHEMA[attribute]: value }
        try:
            obj = db.where(cls.TABLE, **where)[0]
        except IndexError:
            return None
        return cls(raw_data=obj, db=db)
        

    @classmethod
    def get_where(cls, attribute, value):
        return cls.get_by(attribute, value)
    
    @classmethod
    def _get_query(cls, obj_id, **kwargs):
        """
        It is recommended that the following be overloaded to allow
        for more complex queries to build data required for the
        get_all() operation

        """
        db = kwargs.get('db', cls.DB)
        where={cls.PRIMARY_KEY: obj_id}
        try:
            obj = db.where(cls.TABLE, **where)[0]
        except IndexError:
            return None
        return obj

    @classmethod
    def get(cls, obj_id, **kwargs):
        """
        Preprocessing stage, at time of construction, get class's  entry
        from the db and return it as self.data. All properties will
        ref this data by key
        """
        return cls._get_query(obj_id, **kwargs)

    @classmethod
    def _get_all_query(cls, **kwargs):
        """
        It is recommended that the following be overloaded to allow
        for more complex queries to build data required for the
        get_all() operation
       
        """
        db = kwargs.get('db', cls.DB)
        what = kwargs.get('what', "*")
        objs = db.select(cls.TABLE, what=what)
        return objs

    @classmethod
    def get_all(cls, **kwargs):
        """
        """        
        querier = cls._get_all_query
        if kwargs:
            querier = partial(querier,  **kwargs)
        return list(map(cls.construct, querier()))

    @classmethod
    def loads(cls, **cls_params):
        """
        XXX Incomplete
        """
        #could construct a default obj and then override fields
        #using the supplied kwargs
        #p = self.self._construct_obj_from_defaults()
        #return cls(raw_data=cls_params)
        pass

    @classmethod
    def exists(cls, obj_id, **kwargs):
        try:
            return cls.get(obj_id, **kwargs)
        except IndexError:
            return None

    def is_databased(self):
        pkey = getattr(self, self.primary_key, False)
        if not pkey:
            return False
        return pkey
    
    def __repr__(self):
        return unicode(self.__dict__)

    def json_serializable(self):
        """
        Returns an instance of the object which is json serializable
        """
        objson = dict([self.convert_attr2json(k,v) for k, v in self._clean_keys().items()])
        return objson

    @classmethod
    def convert_attr2json(cls, k, v):
        """
        This is a bit crufty, BADDIES isn't comprehensive.
        """
        BADDIES = [Decimal, datetime.datetime]
        return (k,v) if type(v) not in BADDIES else (k, str(v))
