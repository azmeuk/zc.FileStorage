/*###########################################################################
 #
 # Copyright (c) 2003 Zope Corporation and Contributors.
 # All Rights Reserved.
 #
 # This software is subject to the provisions of the Zope Public License,
 # Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
 # THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
 # WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 # WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
 # FOR A PARTICULAR PURPOSE.
 #
 ############################################################################*/

#include <fcntl.h>
#include "Python.h"

#define OBJECT(O) ((PyObject*)(O))

static PyObject *
py_posix_fadvise(PyObject *self, PyObject *args)
{  
  int fd, advice;
  
  if (! PyArg_ParseTuple(args, "ii", &fd, &advice))
    return NULL; 
  return PyInt_FromLong(posix_fadvise(fd, 0, 0, advice));
}

static struct PyMethodDef m_methods[] = {
  {"advise", (PyCFunction)py_posix_fadvise, METH_VARARGS, ""},
  
  {NULL,	 (PyCFunction)NULL, 0, NULL}		/* sentinel */
};


#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
init_zc_FileStorage_posix_fadvise(void)
{
  PyObject *m;
  
  /* Create the module and add the functions */
  m = Py_InitModule3("_zc_FileStorage_posix_fadvise", m_methods, "");
  if (m == NULL)
    return;
  if (PyModule_AddObject(m, 
                         "POSIX_FADV_SEQUENTIAL",
                         OBJECT(PyInt_FromLong(POSIX_FADV_SEQUENTIAL))
                         ) < 0)
    return;
  if (PyModule_AddObject(m, 
                         "POSIX_FADV_NOREUSE",
                         OBJECT(PyInt_FromLong(POSIX_FADV_NOREUSE))
                         ) < 0)
    return;
}
