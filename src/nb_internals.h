#pragma once

#if defined(__GNUC__)
// Don't warn about missing fields in PyTypeObject declarations
#  pragma GCC diagnostic ignored "-Wmissing-field-initializers"
#elif defined(_MSC_VER)
// Silence warnings that MSVC reports in robin_*.h
#  pragma warning(disable: 4127) // conditional expression is constant
#  pragma warning(disable: 4324) // structure was padded due to alignment specifier
#endif

#include <nanobind/nanobind.h>
#include <tsl/robin_map.h>
#include <typeindex>
#include <cstring>

#if defined(_MSC_VER)
#  define NB_THREAD_LOCAL __declspec(thread)
#else
#  define NB_THREAD_LOCAL __thread
#endif

NAMESPACE_BEGIN(NB_NAMESPACE)
NAMESPACE_BEGIN(detail)

#if defined(NB_COMPACT_ASSERTIONS)
[[noreturn]] extern void fail_unspecified() noexcept;
#  define check(cond, ...) if (NB_UNLIKELY(!(cond))) nanobind::detail::fail_unspecified()
#else
#  define check(cond, ...) if (NB_UNLIKELY(!(cond))) nanobind::detail::fail(__VA_ARGS__)
#endif

/// Nanobind function metadata (overloads, etc.)
struct func_data : func_data_prelim<0> {
    arg_data *args;
};

/// Python object representing an instance of a bound C++ type
struct nb_inst { // usually: 24 bytes
    PyObject_HEAD

    /// Offset to the actual instance data
    int32_t offset;

    /**
     * The variable 'offset' can either encode an offset relative to the
     * nb_inst address that leads to the instance data, or it can encode a
     * relative offset to a pointer that must be dereferenced to get to the
     * instance data. 'direct' is 'true' in the former case.
     */
    bool direct : 1;

    /// Is the instance data co-located with the Python object?
    bool internal : 1;

    /// Is the instance properly initialized?
    bool ready : 1;

    /// Should the destructor be called when this instance is GCed?
    bool destruct : 1;

    /// Should nanobind call 'operator delete' when this instance is GCed?
    bool cpp_delete : 1;

    /// Does this instance hold reference to others? (via internals.keep_alive)
    bool clear_keep_alive : 1;
};

static_assert(sizeof(nb_inst) == sizeof(PyObject) + sizeof(void *));

/// Python object representing a bound C++ function
struct nb_func {
    PyObject_VAR_HEAD
    PyObject* (*vectorcall)(PyObject *, PyObject * const*, size_t, PyObject *);
    uint32_t max_nargs_pos;
    bool complex_call;
};

/// Python object representing a `nb_ndarray` (which wraps a DLPack ndarray)
struct nb_ndarray {
    PyObject_HEAD
    ndarray_handle *th;
};

/// Python object representing an `nb_method` bound to an instance (analogous to non-public PyMethod_Type)
struct nb_bound_method {
    PyObject_HEAD
    PyObject* (*vectorcall)(PyObject *, PyObject * const*, size_t, PyObject *);
    nb_func *func;
    PyObject *self;
};

/// Pointers require a good hash function to randomize the mapping to buckets
struct ptr_hash {
    size_t operator()(const void *p) const {
        uintptr_t v = (uintptr_t) p;
        // fmix64 from MurmurHash by Austin Appleby (public domain)
        v ^= v >> 33;
        v *= (uintptr_t) 0xff51afd7ed558ccdull;
        v ^= v >> 33;
        v *= (uintptr_t) 0xc4ceb9fe1a85ec53ull;
        v ^= v >> 33;
        return (size_t) v;
    }
};

// Minimal allocator definition, contains only the parts needed by tsl::*
template <typename T> class py_allocator {
public:
    using value_type = T;
    using pointer = T *;
    using size_type = std::size_t;

    py_allocator() = default;
    py_allocator(const py_allocator &) = default;

    template <typename U> py_allocator(const py_allocator<U> &) { }

    pointer allocate(size_type n, const void * /*hint*/ = nullptr) noexcept {
        void *p = PyMem_Malloc(n * sizeof(T));
        if (!p)
            fail("PyMem_Malloc(): out of memory!");
        return static_cast<pointer>(p);
    }

    void deallocate(T *p, size_type /*n*/) noexcept { PyMem_Free(p); }
};

template <typename key, typename value, typename hash = std::hash<key>,
          typename eq = std::equal_to<key>>
using py_map = tsl::robin_map<key, value, hash, eq>;

// Linked list of instances with the same pointer address. Usually just 1.
struct nb_inst_seq {
    PyObject *inst;
    nb_inst_seq *next;
};

// Weak reference list. Usually, there is just one entry
struct nb_weakref_seq {
    void (*callback)(void *) noexcept;
    void *payload;
    nb_weakref_seq *next;
};

using nb_type_map = py_map<std::type_index, type_data *>;

/// A simple pointer-to-pointer map that is reused a few times below (even if
/// not 100% ideal) to avoid template code generation bloat.
using nb_ptr_map  = py_map<void *, void*, ptr_hash>;

/// Convenience functions to deal with the pointer encoding in 'internals.inst_c2p'

/// Does this entry store a linked list of instances?
NB_INLINE bool         nb_is_seq(void *p)   { return ((uintptr_t) p) & 1; }

/// Tag a nb_inst_seq* pointer as such
NB_INLINE void*        nb_mark_seq(void *p) { return (void *) (((uintptr_t) p) | 1); }

/// Retrieve the nb_inst_seq* pointer from an 'inst_c2p' value
NB_INLINE nb_inst_seq* nb_get_seq(void *p)  { return (nb_inst_seq *) (((uintptr_t) p) ^ 1); }

struct nb_translator_seq {
    exception_translator translator;
    void *payload;
    nb_translator_seq *next = nullptr;
};

struct nb_internals {
    /// Internal nanobind module
    PyObject *nb_module;

    /// Meta-metaclass of nanobind instances
    PyTypeObject *nb_meta;

    /// Dictionary with nanobind metaclass(es) for different payload sizes
    PyObject *nb_type_dict;

    /// Types of nanobind functions and methods
    PyTypeObject *nb_func, *nb_method, *nb_bound_method;

    /// Property variant for static attributes (created on demand)
    PyTypeObject *nb_static_property = nullptr;
    bool nb_static_property_enabled = true;
    descrsetfunc nb_static_property_descr_set = nullptr;

    /// N-dimensional array wrapper (created on demand)
    PyTypeObject *nb_ndarray = nullptr;

    /**
     * C++ -> Python instance map
     *
     * This associative data structure maps a C++ instance pointer onto its
     * associated PyObject* (if bit 0 of the map value is zero) or a linked
     * list of type `nb_inst_seq*` (if bit 0 is set---it must be cleared before
     * interpreting the pointer in this case).
     *
     * The latter case occurs when several distinct Python objects reference
     * the same memory address (e.g. a struct and its first member).
     */
    nb_ptr_map inst_c2p;

    /// C++ -> Python type map
    nb_type_map type_c2p;

    /// Dictionary storing keep_alive references
    nb_ptr_map keep_alive;

    /// nb_func/meth instance map for leak reporting (used as set, the value is unused)
    nb_ptr_map funcs;

    /// Registered C++ -> Python exception translators
    nb_translator_seq translators;

    /// Should nanobind print leak warnings on exit?
    bool print_leak_warnings = true;

    /// Should nanobind print warnings after implicit cast failures?
    bool print_implicit_cast_warnings = true;

#if defined(Py_LIMITED_API)
    // Cache important functions from PyType_Type and PyProperty_Type
    freefunc PyType_Type_tp_free;
    initproc PyType_Type_tp_init;
    destructor PyType_Type_tp_dealloc;
    setattrofunc PyType_Type_tp_setattro;
    descrgetfunc PyProperty_Type_tp_descr_get;
    descrsetfunc PyProperty_Type_tp_descr_set;
#endif
};

/// Convenience macro to potentially access cached functions
#if defined(Py_LIMITED_API)
#  define NB_SLOT(internals, type, name) internals.type##_##name
#else
#  define NB_SLOT(internals, type, name) type.name
#endif

struct current_method {
    const char *name;
    PyObject *self;
};

extern NB_THREAD_LOCAL current_method current_method_data;
extern nb_internals *internals_p;
extern nb_internals *internals_fetch();

inline nb_internals &internals_get() noexcept {
    nb_internals *ptr = internals_p;
    if (NB_UNLIKELY(!ptr))
        ptr = internals_fetch();
    return *ptr;
}

extern char *type_name(const std::type_info *t);

// Forward declarations
extern PyObject *inst_new_impl(PyTypeObject *tp, void *value);
extern PyTypeObject *nb_static_property_tp() noexcept;

/// Fetch the nanobind function record from a 'nb_func' instance
NB_INLINE func_data *nb_func_data(void *o) {
    return (func_data *) (((char *) o) + sizeof(nb_func));
}

#if defined(Py_LIMITED_API)
extern type_data *nb_type_data_static(PyTypeObject *o) noexcept;
#endif

/// Fetch the nanobind type record from a 'nb_type' instance
NB_INLINE type_data *nb_type_data(PyTypeObject *o) noexcept{
    #if !defined(Py_LIMITED_API)
        return (type_data *) (((char *) o) + sizeof(PyHeapTypeObject));
    #else
        return nb_type_data_static(o);
    #endif
}

extern PyObject *nb_type_name(PyTypeObject *o) noexcept;
inline PyObject *nb_inst_name(PyObject *o) noexcept {
        return nb_type_name(Py_TYPE(o));
}

inline void *inst_ptr(nb_inst *self) {
    void *ptr = (void *) ((intptr_t) self + self->offset);
    return self->direct ? ptr : *(void **) ptr;
}

template <typename T> struct scoped_pymalloc {
    scoped_pymalloc(size_t size = 1) {
        ptr = (T *) PyMem_Malloc(size * sizeof(T));
        if (!ptr)
            fail("scoped_pymalloc(): could not allocate %zu bytes of memory!", size);
    }
    ~scoped_pymalloc() { PyMem_Free(ptr); }
    T *release() {
        T *temp = ptr;
        ptr = nullptr;
        return temp;
    }
    T *get() const { return ptr; }
    T &operator[](size_t i) { return ptr[i]; }
    T *operator->() { return ptr; }
private:
    T *ptr{ nullptr };
};

NAMESPACE_END(detail)
NAMESPACE_END(NB_NAMESPACE)
