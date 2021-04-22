from charm4py import charm, Chare, Array, coro, Future, Channel, Group, ArrayMap
import numpy as np
from numba import cuda
import array


class A(Chare):
    def __init__(self, msg_size):
        self.msg_size = msg_size

    @coro
    def run(self, done_future, addr_optimization=False):
        partner = self.thisProxy[int(not self.thisIndex[0])]
        partner_channel = Channel(self, partner)

        device_data = cuda.device_array(self.msg_size, dtype='int8')

        d_addr = array.array('L', [0])
        d_size = array.array('L', [0])

        d_addr[0] = device_data.__cuda_array_interface__['data'][0]
        d_size[0] = device_data.nbytes

        if self.thisIndex[0]:
            host_data = np.zeros(self.msg_size, dtype='int8')
            host_data.fill(5)
            device_data.copy_to_device(host_data)
            if addr_optimization:
                partner_channel.send(1, 2, "hello",
                                     np.ones(self.msg_size, dtype='int8'),
                                     gpu_src_ptrs=d_addr, gpu_src_sizes=d_size
                                     )
                p_data = partner_channel.recv(post_buf_addresses=d_addr,
                                              post_buf_sizes=d_size
                                              )
            else:
                partner_channel.send(1, 2, "hello",
                                     device_data,
                                     np.ones(self.msg_size, dtype='int8')
                                     )
                p_data = partner_channel.recv(device_data)

            assert p_data == (2, 3)
            h_ary = device_data.copy_to_host()
            assert np.array_equal(h_ary, host_data)

            if addr_optimization:
                partner_channel.send(gpu_src_ptrs=d_addr, gpu_src_sizes=d_size)
                partner_channel.recv(post_buf_addresses=d_addr,
                                     post_buf_sizes=d_size
                                     )
            else:
                partner_channel.send(device_data)
                partner_channel.recv(device_data)

            h_ary = device_data.copy_to_host()
            assert np.array_equal(h_ary, host_data)
        else:
            if addr_optimization:
                p_data = partner_channel.recv(post_buf_addresses=d_addr,
                                              post_buf_sizes=d_size
                                              )
            else:
                p_data = partner_channel.recv(device_data)
            p_data, p_host_arr = p_data[0:-1], p_data[-1]
            recvd = device_data.copy_to_host()

            compare = np.zeros(self.msg_size, dtype='int8')
            compare.fill(5)
            assert np.array_equal(recvd, compare)
            assert np.array_equal(np.ones(self.msg_size, dtype='int8'),
                                  p_host_arr
                                  )
            assert p_data == (1, 2, "hello")

            if addr_optimization:
                partner_channel.send(2, 3, gpu_src_ptrs=d_addr,
                                     gpu_src_sizes=d_size
                                     )
            else:
                partner_channel.send(2, 3, device_data)

            if addr_optimization:
                partner_channel.recv(post_buf_addresses=d_addr,
                                     post_buf_sizes=d_size
                                     )
                partner_channel.send(gpu_src_ptrs=d_addr, gpu_src_sizes=d_size)
            else:
                partner_channel.recv(device_data)
                partner_channel.send(device_data)

        self.reduce(done_future)


class ArrMap(ArrayMap):
    def procNum(self, index):
        return index[0] % 2


def main(args):
    # if this is not a cuda-aware build,
    # vacuously pass the test
    if not charm.CkCudaEnabled():
        print("WARNING: Charm4Py was not build with CUDA-enabled Charm++. "
              "GPU-Direct functionality will not be tested"
              )
        charm.exit(0)

    peMap = Group(ArrMap)
    chares = Array(A, 2, args=[8192], map=peMap)
    done_fut = Future()
    chares.run(done_fut, addr_optimization=False)
    done_fut.get()

    done_fut = Future()
    chares.run(done_fut, addr_optimization=True)
    done_fut.get()
    charm.exit(0)


charm.start(main)
