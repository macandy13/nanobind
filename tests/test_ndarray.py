import test_ndarray_ext as t
import pytest
import warnings
import importlib
from common import collect

try:
    import numpy as np
    def needs_numpy(x):
        return x
except:
    needs_numpy = pytest.mark.skip(reason="NumPy is required")

try:
    import torch
    def needs_torch(x):
        return x
except:
    needs_torch = pytest.mark.skip(reason="PyTorch is required")

try:
    import tensorflow as tf
    def needs_tensorflow(x):
        return x
except:
    needs_tensorflow = pytest.mark.skip(reason="TensorFlow is required")

try:
    import jax.numpy as jnp
    def needs_jax(x):
        return x
except:
    needs_jax = pytest.mark.skip(reason="JAX is required")



@needs_numpy
def test01_metadata():
    a = np.zeros(shape=())
    assert t.get_shape(a) == []

    if hasattr(a, '__dlpack__'):
        b = a.__dlpack__()
        assert t.get_shape(b) == []
    else:
        b = None

    with pytest.raises(TypeError) as excinfo:
        # Capsule can only be consumed once
        assert t.get_shape(b) == []
    assert 'incompatible function arguments' in str(excinfo.value)

    a = np.zeros(shape=(3, 4, 5), dtype=np.float64)
    assert t.get_shape(a) == [3, 4, 5]
    assert t.get_size(a) == 60
    assert t.get_nbytes(a) == 60*8
    assert t.get_itemsize(a) == 8
    assert t.check_shape_ptr(a)
    assert t.check_stride_ptr(a)
    if hasattr(a, '__dlpack__'):
        assert t.get_shape(a.__dlpack__()) == [3, 4, 5]
    assert not t.check_float(np.array([1], dtype=np.bool_)) and \
           not t.check_float(np.array([1], dtype=np.uint32)) and \
               t.check_float(np.array([1], dtype=np.float32))
    assert not t.check_bool(np.array([1], dtype=np.uint32)) and \
           not t.check_bool(np.array([1], dtype=np.float32)) and \
               t.check_bool(np.array([1], dtype=np.bool_))


def test02_docstr():
    assert t.get_shape.__doc__ == "get_shape(array: ndarray[]) -> list"
    assert t.pass_uint32.__doc__ == "pass_uint32(array: ndarray[dtype=uint32]) -> None"
    assert t.pass_float32.__doc__ == "pass_float32(array: ndarray[dtype=float32]) -> None"
    assert t.pass_bool.__doc__ == "pass_bool(array: ndarray[dtype=bool]) -> None"
    assert t.pass_float32_shaped.__doc__ == "pass_float32_shaped(array: ndarray[dtype=float32, shape=(3, *, 4)]) -> None"
    assert t.pass_float32_shaped_ordered.__doc__ == "pass_float32_shaped_ordered(array: ndarray[dtype=float32, order='C', shape=(*, *, 4)]) -> None"
    assert t.check_device.__doc__ == ("check_device(arg: ndarray[device='cpu'], /) -> str\n"
                                      "check_device(arg: ndarray[device='cuda'], /) -> str")


@needs_numpy
def test03_constrain_dtype():
    a_u32 = np.array([1], dtype=np.uint32)
    a_f32 = np.array([1], dtype=np.float32)
    a_bool = np.array([1], dtype=np.bool_)

    t.pass_uint32(a_u32)
    t.pass_float32(a_f32)
    t.pass_bool(a_bool)

    with pytest.raises(TypeError) as excinfo:
        t.pass_uint32(a_f32)
    assert 'incompatible function arguments' in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        t.pass_float32(a_u32)
    assert 'incompatible function arguments' in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        t.pass_bool(a_u32)
    assert 'incompatible function arguments' in str(excinfo.value)


@needs_numpy
def test04_constrain_shape():
    t.pass_float32_shaped(np.zeros((3, 0, 4), dtype=np.float32))
    t.pass_float32_shaped(np.zeros((3, 5, 4), dtype=np.float32))

    with pytest.raises(TypeError) as excinfo:
        t.pass_float32_shaped(np.zeros((3, 5), dtype=np.float32))

    with pytest.raises(TypeError) as excinfo:
        t.pass_float32_shaped(np.zeros((2, 5, 4), dtype=np.float32))

    with pytest.raises(TypeError) as excinfo:
        t.pass_float32_shaped(np.zeros((3, 5, 6), dtype=np.float32))

    with pytest.raises(TypeError) as excinfo:
        t.pass_float32_shaped(np.zeros((3, 5, 4, 6), dtype=np.float32))


@needs_numpy
def test04_constrain_order():
    assert t.check_order(np.zeros((3, 5, 4, 6), order='C')) == 'C'
    assert t.check_order(np.zeros((3, 5, 4, 6), order='F')) == 'F'
    assert t.check_order(np.zeros((3, 5, 4, 6), order='C')[:, 2, :, :]) == '?'
    assert t.check_order(np.zeros((3, 5, 4, 6), order='F')[:, 2, :, :]) == '?'


@needs_jax
def test05_constrain_order_jax():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            c = jnp.zeros((3, 5))
        except:
            pytest.skip('jax is missing')

    z = jnp.zeros((3, 5, 4, 6))
    assert t.check_order(z) == 'C'


@needs_torch
@pytest.mark.filterwarnings
def test06_constrain_order_pytorch():
    try:
        c = torch.zeros(3, 5)
        c.__dlpack__()
    except:
        pytest.skip('pytorch is missing')

    f = c.t().contiguous().t()
    assert t.check_order(c) == 'C'
    assert t.check_order(f) == 'F'
    assert t.check_order(c[:, 2:5]) == '?'
    assert t.check_order(f[1:3, :]) == '?'
    assert t.check_device(torch.zeros(3, 5)) == 'cpu'
    if torch.cuda.is_available():
        assert t.check_device(torch.zeros(3, 5, device='cuda')) == 'cuda'


@needs_tensorflow
def test07_constrain_order_tensorflow():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            c = tf.zeros((3, 5))
        except:
            pytest.skip('tensorflow is missing')

    assert t.check_order(c) == 'C'


@needs_numpy
def test08_write_from_cpp():
    x = np.zeros(10, dtype=np.float32)
    t.initialize(x)
    assert np.all(x == np.arange(10, dtype=np.float32))

    x = np.zeros((10, 3), dtype=np.float32)
    t.initialize(x)
    assert np.all(x == np.arange(30, dtype=np.float32).reshape(10, 3))


@needs_numpy
def test09_implicit_conversion():
    t.implicit(np.zeros((2, 2), dtype=np.uint32))
    t.implicit(np.zeros((2, 2, 10), dtype=np.float32)[:, :, 4])
    t.implicit(np.zeros((2, 2, 10), dtype=np.uint32)[:, :, 4])
    t.implicit(np.zeros((2, 2, 10), dtype=np.bool_)[:, :, 4])

    with pytest.raises(TypeError) as excinfo:
        t.noimplicit(np.zeros((2, 2), dtype=np.bool_))

    with pytest.raises(TypeError) as excinfo:
        t.noimplicit(np.zeros((2, 2), dtype=np.uint32))

    with pytest.raises(TypeError) as excinfo:
        t.noimplicit(np.zeros((2, 2, 10), dtype=np.float32)[:, :, 4])


@needs_torch
def test10_implicit_conversion_pytorch():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            c = torch.zeros(3, 5)
            c.__dlpack__()
        except:
            pytest.skip('pytorch is missing')

    t.implicit(torch.zeros(2, 2, dtype=torch.int32))
    t.implicit(torch.zeros(2, 2, 10, dtype=torch.float32)[:, :, 4])
    t.implicit(torch.zeros(2, 2, 10, dtype=torch.int32)[:, :, 4])

    with pytest.raises(TypeError) as excinfo:
        t.noimplicit(torch.zeros(2, 2, dtype=torch.int32))

    with pytest.raises(TypeError) as excinfo:
        t.noimplicit(torch.zeros(2, 2, 10, dtype=torch.float32)[:, :, 4])


@needs_tensorflow
def test11_implicit_conversion_tensorflow():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            c = tf.zeros((3, 5))
        except:
            pytest.skip('tensorflow is missing')

        t.implicit(tf.zeros((2, 2), dtype=tf.int32))
        t.implicit(tf.zeros((2, 2, 10), dtype=tf.float32)[:, :, 4])
        t.implicit(tf.zeros((2, 2, 10), dtype=tf.int32)[:, :, 4])
        t.implicit(tf.zeros((2, 2, 10), dtype=tf.bool)[:, :, 4])

        with pytest.raises(TypeError) as excinfo:
            t.noimplicit(tf.zeros((2, 2), dtype=tf.int32))

        with pytest.raises(TypeError) as excinfo:
            t.noimplicit(tf.zeros((2, 2), dtype=tf.bool))


@needs_jax
def test12_implicit_conversion_jax():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            c = jnp.zeros((3, 5))
        except:
            pytest.skip('jax is missing')

    t.implicit(jnp.zeros((2, 2), dtype=jnp.int32))
    t.implicit(jnp.zeros((2, 2, 10), dtype=jnp.float32)[:, :, 4])
    t.implicit(jnp.zeros((2, 2, 10), dtype=jnp.int32)[:, :, 4])
    t.implicit(jnp.zeros((2, 2, 10), dtype=jnp.bool_)[:, :, 4])

    with pytest.raises(TypeError) as excinfo:
        t.noimplicit(jnp.zeros((2, 2), dtype=jnp.int32))

    with pytest.raises(TypeError) as excinfo:
        t.noimplicit(jnp.zeros((2, 2), dtype=jnp.uint8))

def test13_destroy_capsule():
    collect()
    dc = t.destruct_count()
    a = t.return_dlpack()
    assert dc == t.destruct_count()
    del a
    collect()
    assert t.destruct_count() - dc == 1


@needs_numpy
def test14_consume_numpy():
    collect()
    class wrapper:
        def __init__(self, value):
            self.value = value
        def __dlpack__(self):
            return self.value
    dc = t.destruct_count()
    a = t.return_dlpack()
    if hasattr(np, '_from_dlpack'):
        x = np._from_dlpack(wrapper(a))
    elif hasattr(np, 'from_dlpack'):
        x = np.from_dlpack(wrapper(a))
    else:
        pytest.skip('your version of numpy is too old')

    del a
    collect()
    assert x.shape == (2, 4)
    assert np.all(x == [[1, 2, 3, 4], [5, 6, 7, 8]])
    assert dc == t.destruct_count()
    del x
    collect()
    assert t.destruct_count() - dc == 1


@needs_numpy
def test15_passthrough():
    collect()
    class wrapper:
        def __init__(self, value):
            self.value = value
        def __dlpack__(self):
            return self.value
    dc = t.destruct_count()
    a = t.return_dlpack()
    b = t.passthrough(a)
    if hasattr(np, '_from_dlpack'):
        y = np._from_dlpack(wrapper(b))
    elif hasattr(np, 'from_dlpack'):
        y = np.from_dlpack(wrapper(b))
    else:
        pytest.skip('your version of numpy is too old')

    del a
    del b
    collect()
    assert dc == t.destruct_count()
    assert y.shape == (2, 4)
    assert np.all(y == [[1, 2, 3, 4], [5, 6, 7, 8]])
    del y
    collect()
    assert t.destruct_count() - dc == 1

    a = np.array([1,2,3])
    b = t.passthrough(a)
    assert a is b

@needs_numpy
def test16_return_numpy():
    collect()
    dc = t.destruct_count()
    x = t.ret_numpy()
    assert x.shape == (2, 4)
    assert np.all(x == [[1, 2, 3, 4], [5, 6, 7, 8]])
    del x
    collect()
    assert t.destruct_count() - dc == 1


@needs_torch
def test17_return_pytorch():
    try:
        c = torch.zeros(3, 5)
    except:
        pytest.skip('pytorch is missing')
    collect()
    dc = t.destruct_count()
    x = t.ret_pytorch()
    assert x.shape == (2, 4)
    assert torch.all(x == torch.tensor([[1, 2, 3, 4], [5, 6, 7, 8]]))
    del x
    collect()
    assert t.destruct_count() - dc == 1

@needs_numpy
def test18_return_array_scalar():
    collect()
    dc = t.destruct_count()
    x = t.ret_array_scalar()
    assert np.array_equal(x, np.array(1))
    del x
    collect()
    assert t.destruct_count() - dc == 1

# See PR #162
@needs_torch
def test19_single_and_empty_dimension_pytorch():
    a = torch.ones((1,100,1025), dtype=torch.float32)
    t.noop_3d_c_contig(a)
    a = torch.ones((100,1,1025), dtype=torch.float32)
    t.noop_3d_c_contig(a)
    a = torch.ones((0,100,1025), dtype=torch.float32)
    t.noop_3d_c_contig(a)
    a = torch.ones((100,0,1025), dtype=torch.float32)
    t.noop_3d_c_contig(a)
    a = torch.ones((100,1025,0), dtype=torch.float32)
    t.noop_3d_c_contig(a)
    a = torch.ones((100,0,0), dtype=torch.float32)
    t.noop_3d_c_contig(a)
    a = torch.ones((0,0,0), dtype=torch.float32)
    t.noop_3d_c_contig(a)

# See PR #162
@needs_numpy
def test20_single_and_empty_dimension_numpy():
    a = np.ones((1,100,1025), dtype=np.float32)
    t.noop_3d_c_contig(a)
    a = np.ones((100,1,1025), dtype=np.float32)
    t.noop_3d_c_contig(a)
    a = np.ones((0,100,1025), dtype=np.float32)
    t.noop_3d_c_contig(a)
    a = np.ones((100,0,1025), dtype=np.float32)
    t.noop_3d_c_contig(a)
    a = np.ones((100,1025,0), dtype=np.float32)
    t.noop_3d_c_contig(a)
    a = np.ones((100,0,0), dtype=np.float32)
    t.noop_3d_c_contig(a)
    a = np.ones((0,0,0), dtype=np.float32)
    t.noop_3d_c_contig(a)

# See PR #162
@needs_torch
def test21_single_and_empty_dimension_fortran_order_pytorch():
    # This idiom creates a pytorch 2D tensor in column major (aka, 'F') ordering
    a = torch.ones((0,100), dtype=torch.float32).t().contiguous().t()
    t.noop_2d_f_contig(a)
    a = torch.ones((100,0), dtype=torch.float32).t().contiguous().t()
    t.noop_2d_f_contig(a)
    a = torch.ones((1,100), dtype=torch.float32).t().contiguous().t()
    t.noop_2d_f_contig(a)
    a = torch.ones((100,1), dtype=torch.float32).t().contiguous().t()
    t.noop_2d_f_contig(a)
