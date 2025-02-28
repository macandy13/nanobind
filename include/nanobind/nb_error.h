/*
    nanobind/nb_error.h: Python exception handling, binding of exceptions

    Copyright (c) 2022 Wenzel Jakob

    All rights reserved. Use of this source code is governed by a
    BSD-style license that can be found in the LICENSE file.
*/

NAMESPACE_BEGIN(NB_NAMESPACE)

/// RAII wrapper that temporarily clears any Python error state
struct error_scope {
    error_scope() { PyErr_Fetch(&type, &value, &trace); }
    ~error_scope() { PyErr_Restore(type, value, trace); }
    PyObject *type, *value, *trace;
};

/// Wraps a Python error state as a C++ exception
class NB_EXPORT python_error : public std::exception {
public:
    NB_EXPORT_SHARED python_error();
    NB_EXPORT_SHARED python_error(const python_error &);
    NB_EXPORT_SHARED python_error(python_error &&) noexcept;
    NB_EXPORT_SHARED ~python_error() override;

    bool matches(handle exc) const noexcept {
        return PyErr_GivenExceptionMatches(m_type, exc.ptr()) != 0;
    }

    /// Move the error back into the Python domain. This may only be called
    /// once, and you should not reraise the exception in C++ afterward.
    NB_EXPORT_SHARED void restore() noexcept;

    /// Pass the error to Python's `sys.unraisablehook`, which prints
    /// a traceback to `sys.stderr` by default but may be overridden.
    /// The *context* should be some object whose repr() helps clarify where
    /// the error occurred. Like `.restore()`, this consumes the error and
    /// you should not reraise the exception in C++ afterward.
    void discard_as_unraisable(handle context) noexcept {
        restore();
        PyErr_WriteUnraisable(context.ptr());
    }

    handle type() const { return m_type; }
    handle value() const { return m_value; }
    handle trace() const { return m_trace; }

    NB_EXPORT_SHARED const char *what() const noexcept override;

private:
    mutable PyObject *m_type = nullptr;
    mutable PyObject *m_value = nullptr;
    mutable PyObject *m_trace = nullptr;
    mutable char *m_what = nullptr;
};

/// Thrown by nanobind::cast when casting fails
using cast_error = std::bad_cast;

enum class exception_type {
    stop_iteration, index_error, key_error, value_error,
    type_error, buffer_error, import_error, attribute_error,
    next_overload
};

// Base interface used to expose common Python exceptions in C++
class NB_EXPORT builtin_exception : public std::runtime_error {
public:
    NB_EXPORT_SHARED builtin_exception(exception_type type, const char *what);
    NB_EXPORT_SHARED builtin_exception(builtin_exception &&) = default;
    NB_EXPORT_SHARED builtin_exception(const builtin_exception &) = default;
    NB_EXPORT_SHARED ~builtin_exception();
    NB_EXPORT_SHARED exception_type type() const { return m_type; }
private:
    exception_type m_type;
};

#define NB_EXCEPTION(name)                                                     \
    inline builtin_exception name(const char *what = nullptr) {                \
        return builtin_exception(exception_type::name, what);                  \
    }

NB_EXCEPTION(stop_iteration)
NB_EXCEPTION(index_error)
NB_EXCEPTION(key_error)
NB_EXCEPTION(value_error)
NB_EXCEPTION(type_error)
NB_EXCEPTION(buffer_error)
NB_EXCEPTION(import_error)
NB_EXCEPTION(attribute_error)
NB_EXCEPTION(next_overload)

#undef NB_EXCEPTION

inline void register_exception_translator(detail::exception_translator t,
                                          void *payload = nullptr) {
    detail::register_exception_translator(t, payload);
}

template <typename T>
class exception : public object {
    NB_OBJECT_DEFAULT(exception, object, "Exception", PyExceptionClass_Check)

    exception(handle scope, const char *name, handle base = PyExc_Exception)
        : object(detail::exception_new(scope.ptr(), name, base.ptr()),
                 detail::steal_t()) {
        detail::register_exception_translator(
            [](const std::exception_ptr &p, void *payload) {
                try {
                    std::rethrow_exception(p);
                } catch (T &e) {
                    PyErr_SetString((PyObject *) payload, e.what());
                }
            }, m_ptr);
    }
};

NAMESPACE_END(NB_NAMESPACE)
