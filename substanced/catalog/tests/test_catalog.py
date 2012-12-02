import re
import unittest
from pyramid import testing
import BTrees

from zope.interface import (
    implementer,
    alsoProvides,
    )

from hypatia.interfaces import IIndex

def _makeSite(**kw):
    from ...interfaces import IFolder
    site = testing.DummyResource(__provides__=kw.pop('__provides__', None))
    alsoProvides(site, IFolder)
    objectmap = kw.pop('objectmap', None)
    if objectmap is not None:
        site.__objectmap__ = objectmap
    for k, v in kw.items():
        site[k] = v
        v.__is_service__ = True
    return site

class TestCatalog(unittest.TestCase):
    family = BTrees.family64
    
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _getTargetClass(self):
        from .. import Catalog
        return Catalog
        
    def _makeOne(self, *arg, **kw):
        cls = self._getTargetClass()
        inst = cls(*arg, **kw)
        inst.__name__ = 'catalog'
        return inst

    def test___sdi_addable__True(self):
        inst = self._makeOne()
        intr = {'meta':{'is_index':True}}
        self.assertTrue(inst.__sdi_addable__(None, intr))

    def test___sdi_addable__False(self):
        inst = self._makeOne()
        intr = {'meta':{}}
        self.assertFalse(inst.__sdi_addable__(None, intr))

    def test_klass_provides_ICatalog(self):
        klass = self._getTargetClass()
        from zope.interface.verify import verifyClass
        from ...interfaces import ICatalog
        verifyClass(ICatalog, klass)
        
    def test_inst_provides_ICatalog(self):
        from zope.interface.verify import verifyObject
        from ...interfaces import ICatalog
        inst = self._makeOne()
        verifyObject(ICatalog, inst)

    def test_reset(self):
        catalog = self._makeOne()
        idx = DummyIndex()
        catalog['name'] = idx
        catalog.reset()
        self.assertEqual(idx.cleared, True)
        
    def test_reset_objectids(self):
        inst = self._makeOne()
        inst.objectids.insert(1)
        inst.reset()
        self.assertEqual(list(inst.objectids), [])

    def test_ctor_defaults(self):
        catalog = self._makeOne()
        self.failUnless(catalog.family is self.family)

    def test_ctor_explicit_family(self):
        catalog = self._makeOne(family=BTrees.family32)
        self.failUnless(catalog.family is BTrees.family32)

    def test_index_doc_indexes(self):
        catalog = self._makeOne()
        idx = DummyIndex()
        catalog['name'] = idx
        catalog.index_doc(1, 'value')
        self.assertEqual(idx.docid, 1)
        self.assertEqual(idx.value, 'value')

    def test_index_doc_objectids(self):
        inst = self._makeOne()
        inst.index_doc(1, object())
        self.assertEqual(list(inst.objectids), [1])

    def test_index_doc_nonint_docid(self):
        catalog = self._makeOne()
        idx = DummyIndex()
        catalog['name'] = idx
        self.assertRaises(ValueError, catalog.index_doc, 'abc', 'value')

    def test_unindex_doc_indexes(self):
        catalog = self._makeOne()
        idx = DummyIndex()
        catalog['name'] = idx
        catalog.unindex_doc(1)
        self.assertEqual(idx.unindexed, 1)
        
    def test_unindex_doc_objectids_exists(self):
        inst = self._makeOne()
        inst.objectids.insert(1)
        inst.unindex_doc(1)
        self.assertEqual(list(inst.objectids), [])

    def test_unindex_doc_objectids_notexists(self):
        inst = self._makeOne()
        inst.unindex_doc(1)
        self.assertEqual(list(inst.objectids), [])

    def test_reindex_doc_indexes(self):
        catalog = self._makeOne()
        idx = DummyIndex()
        catalog['name'] = idx
        catalog.reindex_doc(1, 'value')
        self.assertEqual(idx.reindexed_docid, 1)
        self.assertEqual(idx.reindexed_ob, 'value')

    def test_reindex_doc_objectids_exists(self):
        inst = self._makeOne()
        inst.objectids.insert(1)
        inst.reindex_doc(1, object())
        self.assertEqual(list(inst.objectids), [1])
        
    def test_reindex_doc_objectids_notexists(self):
        inst = self._makeOne()
        inst.reindex_doc(1, object())
        self.assertEqual(list(inst.objectids), [1])
        
    def test_reindex(self):
        a = testing.DummyModel()
        L = []
        transaction = DummyTransaction()
        inst = self._makeOne()
        inst.transaction = transaction
        objectmap = DummyObjectMap({1:[a, (u'', u'a')]})
        site = _makeSite(catalog=inst, objectmap=objectmap)
        site['a'] = a
        inst.objectids = [1]
        inst.reindex_doc = lambda objectid, model: L.append((objectid, model))
        out = []
        inst.reindex(output=out.append)
        self.assertEqual(len(L), 1)
        self.assertEqual(L[0][0], 1)
        self.assertEqual(L[0][1], a)
        self.assertEqual(out,
                          ["catalog reindexing /a",
                          '*** committing ***'])
        self.assertEqual(transaction.committed, 1)

    def test_reindex_with_missing_path(self):
        a = testing.DummyModel()
        L = []
        transaction = DummyTransaction()
        objectmap = DummyObjectMap(
            {1: [a, (u'', u'a')], 2:[None, (u'', u'b')]}
            )
        inst = self._makeOne()
        inst.transaction = transaction
        site = _makeSite(catalog=inst, objectmap=objectmap)
        site['a'] = a
        inst.objectids = [1, 2]
        inst.reindex_doc = lambda objectid, model: L.append((objectid, model))
        out = []
        inst.reindex(output=out.append)
        self.assertEqual(L[0][0], 1)
        self.assertEqual(L[0][1], a)
        self.assertEqual(out,
                          ["catalog reindexing /a",
                          "error: object at path /b not found",
                          '*** committing ***'])
        self.assertEqual(transaction.committed, 1)

    def test_reindex_with_missing_objectid(self):
        a = testing.DummyModel()
        L = []
        transaction = DummyTransaction()
        objectmap = DummyObjectMap()
        inst = self._makeOne()
        inst.transaction = transaction
        site = _makeSite(catalog=inst, objectmap=objectmap)
        site['a'] = a
        inst.objectids = [1]
        out = []
        inst.reindex(output=out.append)
        self.assertEqual(L, [])
        self.assertEqual(out,
                          ["error: no path for objectid 1 in object map",
                          '*** committing ***'])
        self.assertEqual(transaction.committed, 1)
        
        
    def test_reindex_pathre(self):
        a = testing.DummyModel()
        b = testing.DummyModel()
        L = []
        objectmap = DummyObjectMap({1: [a, (u'', u'a')], 2: [b, (u'', u'b')]})
        transaction = DummyTransaction()
        inst = self._makeOne()
        inst.transaction = transaction
        site = _makeSite(catalog=inst, objectmap=objectmap)
        site['a'] = a
        site['b'] = b
        inst.objectids = [1, 2]
        inst.reindex_doc = lambda objectid, model: L.append((objectid, model))
        out = []
        inst.reindex(
            path_re=re.compile('/a'), 
            output=out.append
            )
        self.assertEqual(L[0][0], 1)
        self.assertEqual(L[0][1], a)
        self.assertEqual(out,
                          ['catalog reindexing /a',
                          '*** committing ***'])
        self.assertEqual(transaction.committed, 1)

    def test_reindex_dryrun(self):
        a = testing.DummyModel()
        b = testing.DummyModel()
        L = []
        objectmap = DummyObjectMap({1: [a, (u'', u'a')], 2: [b, (u'', u'b')]})
        transaction = DummyTransaction()
        inst = self._makeOne()
        inst.transaction = transaction
        site = _makeSite(catalog=inst, objectmap=objectmap)
        site['a'] = a
        site['b'] = b
        inst.objectids = [1,2]
        inst.reindex_doc = lambda objectid, model: L.append((objectid, model))
        out = []
        inst.reindex(dry_run=True, output=out.append)
        self.assertEqual(len(L), 2)
        L.sort()
        self.assertEqual(L[0][0], 1)
        self.assertEqual(L[0][1], a)
        self.assertEqual(L[1][0], 2)
        self.assertEqual(L[1][1], b)
        self.assertEqual(out,
                         ['catalog reindexing /a',
                          'catalog reindexing /b',
                          '*** aborting ***'])
        self.assertEqual(transaction.aborted, 1)
        self.assertEqual(transaction.committed, 0)

    def test_reindex_with_indexes(self):
        a = testing.DummyModel()
        L = []
        objectmap = DummyObjectMap({1: [a, (u'', u'a')]})
        transaction = DummyTransaction()
        inst = self._makeOne()
        inst.transaction = transaction
        site = _makeSite(catalog=inst, objectmap=objectmap)
        site['a'] = a
        inst.objectids = [1]
        index = DummyIndex()
        inst['index'] = index
        self.config.registry._substanced_indexes = {'index':index}
        index.reindex_doc = lambda objectid, model: L.append((objectid, model))
        out = []
        inst.reindex(indexes=('index',),  output=out.append)
        self.assertEqual(out,
                          ["catalog reindexing only indexes ('index',)",
                          'catalog reindexing /a',
                          '*** committing ***'])
        self.assertEqual(transaction.committed, 1)
        self.assertEqual(len(L), 1)
        self.assertEqual(L[0][0], 1)
        self.assertEqual(L[0][1], a)

    def _setup_factory(self, factory=None):
        from substanced.interfaces import ICatalogFactory
        registry = self.config.registry
        if factory is None:
            factory = DummyFactory(True)
        registry.registerUtility(factory, ICatalogFactory, name='catalog')

    def test_update_indexes_nothing_to_do(self):
        self._setup_factory(DummyFactory(False))
        registry = self.config.registry
        out = []
        inst = self._makeOne()
        transaction = DummyTransaction()
        inst.transaction = transaction
        inst.update_indexes(registry=registry,  output=out.append)
        self.assertEqual(
            out,  
            ['catalog update_indexes: no indexes added or removed'],
            )
        self.assertEqual(transaction.committed, 0)
        self.assertEqual(transaction.aborted, 0)

    def test_update_indexes_replace(self):
        self._setup_factory()
        registry = self.config.registry
        out = []
        inst = self._makeOne()
        transaction = DummyTransaction()
        inst.transaction = transaction
        inst.update_indexes(registry=registry, output=out.append, replace=True)
        self.assertEqual(out, ['*** committing ***'])
        self.assertEqual(transaction.committed, 1)
        self.assertEqual(transaction.aborted, 0)
        self.assertTrue(inst.replaced)

    def test_update_indexes_noreplace(self):
        self._setup_factory()
        registry = self.config.registry
        out = []
        inst = self._makeOne()
        transaction = DummyTransaction()
        inst.transaction = transaction
        inst.update_indexes(registry=registry, output=out.append)
        self.assertEqual(out, ['*** committing ***'])
        self.assertEqual(transaction.committed, 1)
        self.assertEqual(transaction.aborted, 0)
        self.assertTrue(inst.synced)

    def test_update_indexes_dryrun(self):
        self._setup_factory()
        registry = self.config.registry
        out = []
        inst = self._makeOne()
        transaction = DummyTransaction()
        inst.transaction = transaction
        inst.update_indexes(registry=registry, output=out.append, dry_run=True)
        self.assertEqual(out, ['*** aborting ***'])
        self.assertEqual(transaction.committed, 0)
        self.assertEqual(transaction.aborted, 1)

class Test_is_catalogable(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _callFUT(self, resource, registry=None):
        from .. import is_catalogable
        return is_catalogable(resource, registry)

    def _registerIndexView(self):
        from zope.interface import Interface
        from substanced.interfaces import IIndexView
        self.config.registry.registerAdapter(True, (Interface,), IIndexView)

    def test_no_registry_passed(self):
        resource = Dummy()
        self._registerIndexView()
        self.assertTrue(self._callFUT(resource))

    def test_true(self):
        resource = Dummy()
        self._registerIndexView()
        registry = self.config.registry
        self.assertTrue(self._callFUT(resource, registry))

    def test_false(self):
        resource = Dummy()
        registry = self.config.registry
        self.assertFalse(self._callFUT(resource, registry))

class Test_add_catalog_factory(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()
        
    def _callFUT(self, config, name, factory):
        from .. import add_catalog_factory
        return add_catalog_factory(config, name, factory)

    def test_it(self):
        from substanced.interfaces import ICatalogFactory
        config = DummyConfigurator(registry=self.config.registry)
        self._callFUT(config, 'name', 'factory')
        self.assertEqual(len(config.actions), 1)
        action = config.actions[0]
        self.assertEqual(
            action['discriminator'],
            ('sd-catalog-factory', 'name')
            )
        self.assertEqual(
            action['introspectables'], (config.intr,)
            )
        self.assertEqual(config.intr['name'], 'name')
        self.assertEqual(config.intr['factory'], 'factory')
        callable = action['callable']
        callable()
        self.assertEqual(
            self.config.registry.getUtility(ICatalogFactory, 'name'),
            'factory'
            )

class Test_add_indexview(unittest.TestCase):
    def _callFUT(self, config, view, catalog_name, index_name, **kw):
        from .. import add_indexview
        return add_indexview(config, view, catalog_name, index_name, **kw)


class Test_CatalogablePredicate(unittest.TestCase):
    def _makeOne(self, val, config):
        from .. import _CatalogablePredicate
        return _CatalogablePredicate(val, config)

    def test_text(self):
        config = Dummy()
        config.registry = Dummy()
        inst = self._makeOne(True, config)
        self.assertEqual(inst.text(), 'catalogable = True')

    def test_phash(self):
        config = Dummy()
        config.registry = Dummy()
        inst = self._makeOne(True, config)
        self.assertEqual(inst.phash(), 'catalogable = True')

    def test__call__(self):
        config = Dummy()
        config.registry = Dummy()
        inst = self._makeOne(True, config)
        def is_catalogable(context, registry):
            self.assertEqual(context, None)
            self.assertEqual(registry, config.registry)
            return True
        inst.is_catalogable = is_catalogable
        self.assertEqual(inst(None, None), True)

class Test_catalog_buttons(unittest.TestCase):
    def setUp(self):
        testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_it(self):
        from .. import catalog_buttons
        context = testing.DummyResource()
        request = testing.DummyRequest()
        default_buttons = [1]
        buttons = catalog_buttons(context, request, default_buttons)
        self.assertEqual(buttons,
                         [
                             {'buttons':
                              [{'text': 'Reindex',
                                'class': 'btn-primary',
                                'id': 'reindex',
                                'value': 'reindex',
                                'name': 'form.reindex'}],
                              'type': 'single'},
                             1])


class DummyIntrospectable(dict):
    pass

class DummyConfigurator(object):
    def __init__(self, registry):
        self.actions = []
        self.intr = DummyIntrospectable()
        self.registry = registry
        self.indexes = []

    def action(self, discriminator, callable, order=None, introspectables=()):
        self.actions.append(
            {
            'discriminator':discriminator,
            'callable':callable,
            'order':order,
            'introspectables':introspectables,
            })

    def introspectable(self, category, discriminator, name, single):
        return self.intr

class DummyObjectMap(object):
    def __init__(self, objectid_to=None): 
        if objectid_to is None: objectid_to = {}
        self.objectid_to = objectid_to

    def path_for(self, objectid):
        data = self.objectid_to.get(objectid)
        if data is None: return
        return data[1]

    def object_for(self, objectid):
        data = self.objectid_to.get(objectid)
        if data is None:
            return
        return data[0]

    def add(self, node, path_tuple, duplicating=False, moving=False):
        pass

class DummyCatalog(dict):
    pass

class DummyTransaction(object):
    def __init__(self):
        self.committed = 0
        self.aborted = 0
        
    def commit(self):
        self.committed += 1

    def abort(self):
        self.aborted += 1
        

@implementer(IIndex)
class DummyIndex(object):

    value = None
    docid = None
    limit = None
    sort_type = None

    def __init__(self, *arg, **kw):
        self.arg = arg
        self.kw = kw

    def index_doc(self, docid, value):
        self.docid = docid
        self.value = value
        return value

    def unindex_doc(self, docid):
        self.unindexed = docid

    def reset(self):
        self.cleared = True

    def reindex_doc(self, docid, object):
        self.reindexed_docid = docid
        self.reindexed_ob = object

    def apply_intersect(self, query, docids): # pragma: no cover
        if docids is None:
            return self.arg[0]
        L = []
        for docid in self.arg[0]:
            if docid in docids:
                L.append(docid)
        return L

class Dummy(object):
    pass

class DummyFactory(object):
    def __init__(self, result):
        self.result = result
        
    def replace(self, catalog, **kw):
        catalog.replaced = True
        return self.result

    def sync(self, catalog, **kw):
        catalog.synced = True
        return self.result
