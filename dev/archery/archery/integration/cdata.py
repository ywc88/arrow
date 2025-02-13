# licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import cffi
from contextlib import contextmanager
import functools

from .tester import CDataExporter, CDataImporter


_c_data_decls = """
    struct ArrowSchema {
      // Array type description
      const char* format;
      const char* name;
      const char* metadata;
      int64_t flags;
      int64_t n_children;
      struct ArrowSchema** children;
      struct ArrowSchema* dictionary;

      // Release callback
      void (*release)(struct ArrowSchema*);
      // Opaque producer-specific data
      void* private_data;
    };

    struct ArrowArray {
      // Array data description
      int64_t length;
      int64_t null_count;
      int64_t offset;
      int64_t n_buffers;
      int64_t n_children;
      const void** buffers;
      struct ArrowArray** children;
      struct ArrowArray* dictionary;

      // Release callback
      void (*release)(struct ArrowArray*);
      // Opaque producer-specific data
      void* private_data;
    };

    struct ArrowArrayStream {
      int (*get_schema)(struct ArrowArrayStream*, struct ArrowSchema* out);
      int (*get_next)(struct ArrowArrayStream*, struct ArrowArray* out);

      const char* (*get_last_error)(struct ArrowArrayStream*);

      // Release callback
      void (*release)(struct ArrowArrayStream*);
      // Opaque producer-specific data
      void* private_data;
    };
    """


@functools.lru_cache
def ffi() -> cffi.FFI:
    """
    Return a FFI object supporting C Data Interface types.
    """
    ffi = cffi.FFI()
    ffi.cdef(_c_data_decls)
    return ffi


@contextmanager
def check_memory_released(exporter: CDataExporter, importer: CDataImporter):
    """
    A context manager for memory release checks.

    The context manager arranges cooperation between the exporter and importer
    to try and release memory at the end of the enclosed block.

    However, if either the exporter or importer doesn't support deterministic
    memory release, no memory check is performed.
    """
    do_check = (exporter.supports_releasing_memory and
                importer.supports_releasing_memory)
    if do_check:
        before = exporter.record_allocation_state()
    yield
    # We don't use a `finally` clause: if the enclosed block raised an
    # exception, no need to add another one.
    if do_check:
        ok = exporter.compare_allocation_state(before, importer.gc_until)
        if not ok:
            after = exporter.record_allocation_state()
            raise RuntimeError(
                f"Memory was not released correctly after roundtrip: "
                f"before = {before}, after = {after} (should have been equal)")
