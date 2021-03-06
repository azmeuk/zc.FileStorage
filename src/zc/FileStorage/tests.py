##############################################################################
#
# Copyright (c) 2006 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

##############################################################################
# Test FileStorage packing sans GC
#
# This module is a bit of a hack.  It simply copies and modifies the
# tests affected by the lack of gc in pack.
##############################################################################

import binascii
import ZODB.blob
import ZODB.tests.testblob
import doctest
import time
import unittest
import zc.FileStorage

from ZODB.serialize import referencesf
from zope.testing import setupstack
from ZODB.tests.testFileStorage import FileStorageTests
from ZODB.tests.PackableStorage import pdumps
from ZODB.tests.TransactionalUndoStorage import snooze
from zodbpickle import pickle


class ZCFileStorageTests(FileStorageTests):

    blob_dir = None

    def setUp(self):
        self.open(create=1, packer=zc.FileStorage.packer, blob_dir=self.blob_dir)

    def tearDown(self):
        self._storage.close()
        self._storage.cleanup()
        if self.blob_dir:
            ZODB.blob.remove_committed_dir(self.blob_dir)

    def checkPackAllRevisions(self):
        self._initroot()
        eq = self.assertEqual
        raises = self.assertRaises
        # Create a `persistent' object
        obj = self._newobj()
        oid = obj.getoid()
        obj.value = 1
        # Commit three different revisions
        revid1 = self._dostoreNP(oid, data=pdumps(obj))
        obj.value = 2
        revid2 = self._dostoreNP(oid, revid=revid1, data=pdumps(obj))
        obj.value = 3
        revid3 = self._dostoreNP(oid, revid=revid2, data=pdumps(obj))
        # Now make sure all three revisions can be extracted
        data = self._storage.loadSerial(oid, revid1)
        pobj = pickle.loads(data)
        eq(pobj.getoid(), oid)
        eq(pobj.value, 1)
        data = self._storage.loadSerial(oid, revid2)
        pobj = pickle.loads(data)
        eq(pobj.getoid(), oid)
        eq(pobj.value, 2)
        data = self._storage.loadSerial(oid, revid3)
        pobj = pickle.loads(data)
        eq(pobj.getoid(), oid)
        eq(pobj.value, 3)
        # Now pack all transactions; need to sleep a second to make
        # sure that the pack time is greater than the last commit time.
        now = packtime = time.time()
        while packtime <= now:
            packtime = time.time()
        self._storage.pack(packtime, referencesf)
        # Only old revisions of the object should be gone. We don't gc
        raises(KeyError, self._storage.loadSerial, oid, revid1)
        raises(KeyError, self._storage.loadSerial, oid, revid2)
        self._storage.loadSerial(oid, revid3)

    def checkPackUndoLog(self):
        self._initroot()
        # Create a `persistent' object
        obj = self._newobj()
        oid = obj.getoid()
        obj.value = 1
        # Commit two different revisions
        revid1 = self._dostoreNP(oid, data=pdumps(obj))
        obj.value = 2
        snooze()
        packtime = time.time()
        snooze()
        self._dostoreNP(oid, revid=revid1, data=pdumps(obj))
        # Now pack the first transaction
        self.assertEqual(3, len(self._storage.undoLog()))
        self._storage.pack(packtime, referencesf)
        # The undo log contains only the most resent transaction
        self.assertEqual(3, len(self._storage.undoLog()))

    def checkPackWithGCOnDestinationAfterRestore(self):
        pass

    def checkPackWithMultiDatabaseReferences(self):
        pass


class ZCFileStorageTestsWithBlobs(ZCFileStorageTests):

    blob_dir = "blobs"


time_hack_template = """
now = 1268166473.0
import time

time_time, time_sleep = time.time, time.sleep

time.sleep(1) # Slow things down a bit to give the test time to commit

def faux_time():
    global now
    now += 1
    return now

def faux_sleep(x):
    logging.info('sleep '+ repr(x))

time.time, time.sleep = faux_time, faux_sleep
"""

GIG_hack_template = """

import sys

sys.path[:] = %(syspath)r

import zc.FileStorage
zc.FileStorage.GIG = 100

"""


def test_pack_sleep():
    """
Make sure that sleep is being called. :)

Mess with time -- there should be infrastructure for this!

    >>> exec(time_hack_template)
    >>> time.sleep = time_sleep

    >>> import os, threading, transaction, shutil, ZODB.FileStorage, zc.FileStorage
    >>> fs = ZODB.FileStorage.FileStorage('data.fs',
    ...                                   packer=zc.FileStorage.packer1)
    >>> db = ZODB.DB(fs)
    >>> conn = db.open()
    >>> for i in range(5):
    ...     conn.root()[i] = conn.root().__class__()
    ...     transaction.commit()
    >>> pack_time = time.time()
    >>> for i in range(5):
    ...     conn.root()[i].x = 1
    ...     transaction.commit()

    >>> pack_script_template = zc.FileStorage.pack_script_template
    >>> zc.FileStorage.pack_script_template = (
    ...     time_hack_template + GIG_hack_template + pack_script_template)
    >>> thread = threading.Thread(target=fs.pack, args=(pack_time, now))
    >>> thread.start()
    >>> for i in range(100):
    ...     if os.path.exists('data.fs.packscript'):
    ...        break
    ...     time.sleep(0.01)
    >>> def faux_sleep(x):
    ...     print('sleep '+repr(x))
    >>> time.sleep = faux_sleep
    >>> conn.root().x = 1
    >>> transaction.commit()
    >>> thread.join()
    sleep 1.0

    >>> fs.close()
    >>> with open('data.fs.packlog') as fd:
    ...     print(fd.read()) # doctest: +NORMALIZE_WHITESPACE
    2010-03-09 15:27:55,000 root INFO packing to 2010-03-09 20:28:06.000000,
       sleep 1
    2010-03-09 15:27:57,000 root INFO read 162
    2010-03-09 15:27:59,000 root INFO sleep 2.0
    2010-03-09 15:28:01,000 root INFO read 411
    2010-03-09 15:28:03,000 root INFO sleep 2.0
    2010-03-09 15:28:05,000 root INFO read 680
    2010-03-09 15:28:07,000 root INFO sleep 2.0
    2010-03-09 15:28:09,000 root INFO read 968
    2010-03-09 15:28:11,000 root INFO sleep 2.0
    2010-03-09 15:28:13,000 root INFO read 1275
    2010-03-09 15:28:15,000 root INFO sleep 2.0
    2010-03-09 15:28:17,000 root INFO read 1601
    2010-03-09 15:28:19,000 root INFO sleep 2.0
    2010-03-09 15:28:21,000 root INFO initial scan 6 objects at 1601
    2010-03-09 15:28:22,000 root INFO copy to pack time
    2010-03-09 15:28:24,000 root INFO read 162
    2010-03-09 15:28:26,000 root INFO sleep 2.0
    2010-03-09 15:28:28,000 root INFO read 411
    2010-03-09 15:28:30,000 root INFO sleep 2.0
    2010-03-09 15:28:32,000 root INFO read 680
    2010-03-09 15:28:34,000 root INFO sleep 2.0
    2010-03-09 15:28:36,000 root INFO read 968
    2010-03-09 15:28:38,000 root INFO sleep 2.0
    2010-03-09 15:28:40,000 root INFO read 1275
    2010-03-09 15:28:42,000 root INFO sleep 2.0
    2010-03-09 15:28:44,000 root INFO read 1601
    2010-03-09 15:28:46,000 root INFO sleep 2.0
    2010-03-09 15:28:47,000 root INFO copy from pack time
    2010-03-09 15:28:51,000 root INFO sleep 1.0
    2010-03-09 15:28:52,000 root INFO read 1737
    2010-03-09 15:28:54,000 root INFO sleep 5.0
    2010-03-09 15:28:58,000 root INFO sleep 1.0
    2010-03-09 15:28:59,000 root INFO read 1873
    2010-03-09 15:29:01,000 root INFO sleep 5.0
    2010-03-09 15:29:05,000 root INFO sleep 1.0
    2010-03-09 15:29:06,000 root INFO read 2009
    2010-03-09 15:29:08,000 root INFO sleep 5.0
    2010-03-09 15:29:12,000 root INFO sleep 1.0
    2010-03-09 15:29:13,000 root INFO read 2145
    2010-03-09 15:29:15,000 root INFO sleep 5.0
    2010-03-09 15:29:19,000 root INFO sleep 1.0
    2010-03-09 15:29:20,000 root INFO read 2281
    2010-03-09 15:29:22,000 root INFO sleep 5.0
    2010-03-09 15:29:23,000 root INFO packscript done

    >>> time.sleep = time_sleep
    >>> time.time = time_time

Now do it all again with a longer sleep:

    >>> _ = shutil.copyfile('data.fs.old', 'data.fs')
    >>> fs = ZODB.FileStorage.FileStorage('data.fs',
    ...                                   packer=zc.FileStorage.packer2)
    >>> fs.pack(pack_time, now)
    >>> with open('data.fs.packlog') as fd:
    ...     print(fd.read()) # doctest: +NORMALIZE_WHITESPACE
    2010-03-09 15:27:55,000 root INFO packing to 2010-03-09 20:28:06.000000,
      sleep 2
    2010-03-09 15:27:57,000 root INFO read 162
    2010-03-09 15:27:59,000 root INFO sleep 4.0
    2010-03-09 15:28:01,000 root INFO read 411
    2010-03-09 15:28:03,000 root INFO sleep 4.0
    2010-03-09 15:28:05,000 root INFO read 680
    2010-03-09 15:28:07,000 root INFO sleep 4.0
    2010-03-09 15:28:09,000 root INFO read 968
    2010-03-09 15:28:11,000 root INFO sleep 4.0
    2010-03-09 15:28:13,000 root INFO read 1275
    2010-03-09 15:28:15,000 root INFO sleep 4.0
    2010-03-09 15:28:17,000 root INFO read 1601
    2010-03-09 15:28:19,000 root INFO sleep 4.0
    2010-03-09 15:28:21,000 root INFO initial scan 6 objects at 1601
    2010-03-09 15:28:22,000 root INFO copy to pack time
    2010-03-09 15:28:24,000 root INFO read 162
    2010-03-09 15:28:26,000 root INFO sleep 4.0
    2010-03-09 15:28:28,000 root INFO read 411
    2010-03-09 15:28:30,000 root INFO sleep 4.0
    2010-03-09 15:28:32,000 root INFO read 680
    2010-03-09 15:28:34,000 root INFO sleep 4.0
    2010-03-09 15:28:36,000 root INFO read 968
    2010-03-09 15:28:38,000 root INFO sleep 4.0
    2010-03-09 15:28:40,000 root INFO read 1275
    2010-03-09 15:28:42,000 root INFO sleep 4.0
    2010-03-09 15:28:44,000 root INFO read 1601
    2010-03-09 15:28:46,000 root INFO sleep 4.0
    2010-03-09 15:28:47,000 root INFO copy from pack time
    2010-03-09 15:28:51,000 root INFO sleep 2.0
    2010-03-09 15:28:52,000 root INFO read 1737
    2010-03-09 15:28:54,000 root INFO sleep 10.0
    2010-03-09 15:28:58,000 root INFO sleep 2.0
    2010-03-09 15:28:59,000 root INFO read 1873
    2010-03-09 15:29:01,000 root INFO sleep 10.0
    2010-03-09 15:29:05,000 root INFO sleep 2.0
    2010-03-09 15:29:06,000 root INFO read 2009
    2010-03-09 15:29:08,000 root INFO sleep 10.0
    2010-03-09 15:29:12,000 root INFO sleep 2.0
    2010-03-09 15:29:13,000 root INFO read 2145
    2010-03-09 15:29:15,000 root INFO sleep 10.0
    2010-03-09 15:29:19,000 root INFO sleep 2.0
    2010-03-09 15:29:20,000 root INFO read 2281
    2010-03-09 15:29:22,000 root INFO sleep 10.0
    2010-03-09 15:29:26,000 root INFO sleep 2.0
    2010-03-09 15:29:27,000 root INFO read 2514
    2010-03-09 15:29:29,000 root INFO sleep 10.0
    2010-03-09 15:29:30,000 root INFO packscript done

    >>> zc.FileStorage.pack_script_template = pack_script_template

    """


def data_transform_and_untransform_hooks():
    r"""The Packer factory takes uptions to transform and untransform data

This is helpful when data records aren't raw pickles or when you want
to transform them so that they aren't raw pickles.  To test this,
we'll take a file storage database and convert it to use the
ZODB.tests.hexstorage trandormation.

    >>> import os, ZODB.FileStorage
    >>> db = ZODB.DB(ZODB.FileStorage.FileStorage(
    ...     'data.fs', blob_dir='blobs',
    ...     packer=zc.FileStorage.Packer(
    ...            transform='zc.FileStorage.tests:hexer',
    ...            untransform='zc.FileStorage.tests:unhexer',
    ...            )))
    >>> conn = db.open()
    >>> conn.root.b = ZODB.blob.Blob(b'test')
    >>> conn.transaction_manager.commit()

    >>> with conn.root.b.open() as fd:
    ...     _ = fd.read()

So, here we have some untransformed data. Now, we'll pack it:

    >>> db.pack()

Now, the database records are hex:

    >>> db.storage.load(b'\0'*8)[0][:50]
    '.h6370657273697374656e742e6d617070696e670a50657273'

    >>> db.storage.load(b'\0'*7+b'\1')[0][:50]
    '.h635a4f44422e626c6f620a426c6f620a71012e4e2e'

Let's add an object. (WE get away with this because the object's we
use are in the cache. :)

    >>> conn.root.a = conn.root().__class__()
    >>> conn.transaction_manager.commit()

Now the root and the new object are not hex:

    >>> db.storage.load(b'\0'*8)[0][:50]
    'cpersistent.mapping\nPersistentMapping\nq\x01.}q\x02U\x04data'

    >>> db.storage.load(b'\0'*7+b'\2')[0][:50]
    'cpersistent.mapping\nPersistentMapping\nq\x01.}q\x02U\x04data'

We capture the current time as the pack time:

    >>> import time
    >>> pack_time = time.time()
    >>> time.sleep(.1)

We'll throw in a blob modification:

    >>> with conn.root.b.open('w') as fd:
    ...     _ = fd.write(b'test 2')
    >>> conn.transaction_manager.commit()

Now pack and make sure all the records have been transformed:


    >>> db.pack()
    >>> from ZODB.utils import p64
    >>> for i in range(len(db.storage)):
    ...     if db.storage.load(p64(i))[0][:2] != '.h':
    ...         print(i)

We should have only one blob file:

    >>> nblobs = 0
    >>> for _, _, files in os.walk('blobs'):
    ...     for file in files:
    ...         if file.endswith('.blob'):
    ...             nblobs += 1
    >>> nblobs
    1

    """


def snapshot_in_time():
    r"""We can take a snapshot in time

    This is a copy of a database as of a given time and containing
    only current records as of that time.

    First, we'll hack time:

    >>> import logging, os
    >>> exec(time_hack_template)

    Next, we'll create a file storage with some data:

    >>> import ZODB.FileStorage
    >>> import transaction

    >>> conn = ZODB.connection('data.fs')
    >>> for i in range(5):
    ...     conn.root()[i] = conn.root().__class__()
    ...     transaction.commit()
    >>> for i in range(5):
    ...     conn.root()[i].x = 0
    ...     transaction.commit()
    >>> for j in range(10):
    ...     for i in range(5):
    ...         conn.root()[i].x += 1
    ...         transaction.commit()

    >>> import ZODB.TimeStamp
    >>> copy_time = ZODB.TimeStamp.TimeStamp(
    ...    conn.db().storage.lastTransaction())

    >>> for j in range(10):
    ...     for i in range(5):
    ...         conn.root()[i].x += 1
    ...         transaction.commit()

    We'll comput a hash of the old file contents:

    >>> import hashlib
    >>> with open('data.fs', 'rb') as fd:
    ...     hash = hashlib.sha1(fd.read()).digest()

    OK, we have a database with a bunch of revisions.
    Now, let's make a snapshot:

    >>> import zc.FileStorage.snapshotintime

    >>> copy_time = '%s-%s-%sT%s:%s:%s' % (
    ...   copy_time.year(), copy_time.month(), copy_time.day(),
    ...   copy_time.hour(), copy_time.minute(), int(copy_time.second()))
    >>> zc.FileStorage.snapshotintime.main(
    ...    ['data.fs', copy_time, 'snapshot.fs'])

    >>> sorted(os.listdir('.')) # doctest: +NORMALIZE_WHITESPACE
    ['data.fs', 'data.fs.index', 'data.fs.lock', 'data.fs.tmp',
    'snapshot.fs', 'snapshot.fs.index']

    The orginal file is unchanged:

    >>> with open('data.fs', 'rb') as fd:
    ...     hashlib.sha1(fd.read()).digest() == hash
    True

    The new file has just the final records:

    >>> for t in ZODB.FileStorage.FileIterator('snapshot.fs'):
    ...     print(ZODB.TimeStamp.TimeStamp(t.tid))
    ...     for record in t:
    ...         print(repr(record.oid))
    2010-03-09 20:28:05.000000
    '\x00\x00\x00\x00\x00\x00\x00\x00'
    2010-03-09 20:28:56.000000
    '\x00\x00\x00\x00\x00\x00\x00\x01'
    2010-03-09 20:28:57.000000
    '\x00\x00\x00\x00\x00\x00\x00\x02'
    2010-03-09 20:28:58.000000
    '\x00\x00\x00\x00\x00\x00\x00\x03'
    2010-03-09 20:28:59.000000
    '\x00\x00\x00\x00\x00\x00\x00\x04'
    2010-03-09 20:29:00.000000
    '\x00\x00\x00\x00\x00\x00\x00\x05'

    Of course, we can open the copy:

    >>> conn.close()
    >>> conn = ZODB.connection('snapshot.fs')
    >>> sorted(conn.root().keys()) == range(5)
    True

    >>> for i in range(5):
    ...     if conn.root()[i].x != 10:
    ...         print('oops', conn.root()[i].x)

    >>> time.time, time.sleep = time_time, time_sleep

    We get usage if the wrong number or form of arguments are given:

    >>> import sys
    >>> stderr = sys.stderr
    >>> sys.stderr = sys.stdout
    >>> argv0 = sys.argv[0]
    >>> sys.argv[0] = 'snapshot-in-time'
    >>> try: zc.FileStorage.snapshotintime.main([])
    ... except SystemExit as v: pass
    ... else: print('oops')
    Usage: snapshot-in-time [input-path utc-snapshot-time output-path]
    <BLANKLINE>
    Make a point-in time snapshot of a file-storage data file containing
    just the current records as of the given time.  The resulting file can
    be used as a basis of a demo storage.
    <BLANKLINE>
    If the output file isn't given, then a file name will be generated
    based on the input file name and the utc-snapshot-time.
    <BLANKLINE>
    If the utc-snapshot-time is ommitted, then the current time will be used.
    <BLANKLINE>
    Note: blobs (if any) aren't copied.
    <BLANKLINE>
    The UTC time is a string of the form: YYYY-MM-DDTHH:MM:SS.  The time
    conponents are optional.  The time defaults to midnight, UTC.
    <BLANKLINE>

    >>> sys.argv[0] = argv0

    >>> try: zc.FileStorage.snapshotintime.main(['xxx', 'xxx', 'xxx'])
    ... except SystemExit as v: pass
    ... else: print('oops')
    xxx Does not exist.

    >>> try: zc.FileStorage.snapshotintime.main(['data.fs', 'xxx', 'xxx'])
    ... except SystemExit as v: pass
    ... else: print('oops')
    Bad date-time: xxx

    >>> sys.stderr = stderr

    If you omit the output file, a file name will be generated based on the
    time:

    >>> zc.FileStorage.snapshotintime.main(['data.fs', copy_time])

    >>> sorted(os.listdir('.')) # doctest: +NORMALIZE_WHITESPACE
    ['data.fs', 'data.fs.index', 'data.fs.lock', 'data.fs.tmp',
     'data2010-3-9T20:29:0.fs', 'data2010-3-9T20:29:0.fs.index',
     'snapshot.fs', 'snapshot.fs.index', 'snapshot.fs.lock', 'snapshot.fs.tmp']

    >>> with open('data2010-3-9T20:29:0.fs', 'rb') as fd1, open('snapshot.fs', 'rb') as fd2:
    ...     fd1.read() == fd2.read()
    True

    """


def hexer(data):
    if data[:2] == b".h":
        return data

    return b".h" + binascii.hexlify(data)


def unhexer(data):
    if not data:
        return data

    if data[:2] == b".h":
        return binascii.unhexlify(data[2:])

    return data


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ZCFileStorageTests, "check"))
    suite.addTest(unittest.makeSuite(ZCFileStorageTestsWithBlobs, "check"))
    suite.addTest(
        doctest.DocFileSuite(
            "blob_packing.txt",
            setUp=setupstack.setUpDirectory,
            tearDown=setupstack.tearDown,
        )
    )
    suite.addTest(
        doctest.DocTestSuite(
            setUp=setupstack.setUpDirectory, tearDown=setupstack.tearDown
        )
    )
    return suite
