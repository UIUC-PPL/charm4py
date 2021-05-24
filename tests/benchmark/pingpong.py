from charm4py import charm, Chare, Array, coro, Future, Channel, Group
import time
import numpy as np

class Ping(Chare):
    def __init__(self, use_zerocopy, print_format):
        self.zero_copy = use_zerocopy
        self.num_chares = charm.numPes()
        self.print_format = print_format
        self.am_low_chare = self.thisIndex == 0

        if self.am_low_chare:
            if print_format == 0:
                print("Msg Size, Iterations, One-way Time (us), "
                      "Bandwidth (bytes/us)"
                      )
            else:
                print(f'{"Msg Size": <30} {"Iterations": <25} '
                      f'{"One-way Time (us)": <20} {"Bandwidth (bytes/us)": <20}'
                      )

    @coro
    def do_iteration(self, message_size, num_iters, done_future):
        data = np.zeros(message_size, dtype='int8')
        partner_idx = int(not self.thisIndex)
        partner = self.thisProxy[partner_idx]
        partner_channel = Channel(self, partner)

        tstart = time.time()

        for _ in range(num_iters):
            if self.am_low_chare:
                if not self.zero_copy:
                    partner_channel.send(data)
                    partner_channel.recv()
                else:
                    raise NotImplementedError("TODO: ZeroCopy")

            else:
                if not self.zero_copy:
                    partner_channel.recv()
                    partner_channel.send(data)
                else:
                    raise NotImplementedError("TODO: ZeroCopy")

        tend = time.time()

        elapsed_time = tend - tstart

        if self.am_low_chare:
            self.display_iteration_data(elapsed_time, num_iters, message_size)

        self.reduce(done_future)

    def display_iteration_data(self, elapsed_time, num_iters, message_size):
        elapsed_time /= 2  # 1-way performance, not RTT
        elapsed_time /= num_iters  # Time for each message
        bandwidth = message_size / elapsed_time
        if self.print_format == 0:
            print(f'{message_size},{num_iters},{elapsed_time * 1e6},'
                  f'{bandwidth / 1e6}'
                  )
        else:
            print(f'{message_size: <30} {num_iters: <25} '
                  f'{elapsed_time * 1e6: <20} {bandwidth / 1e6: <20}'
                  )

def main(args):
    if len(args) < 7:
        print("Doesn't have the required input params. Usage:"
              "<min-msg-size> <max-msg-size> <low-iter> "
              "<high-iter> <print-format"
              "(0 for csv, 1 for "
              "regular)> <GPU (0 for CPU, 1 for GPU)>\n"
              )
        charm.exit(-1)

    min_msg_size = int(args[1])
    max_msg_size = int(args[2])
    low_iter = int(args[3])
    high_iter = int(args[4])
    print_format = int(args[5])
    use_zerocopy = int(args[6])

    pings = Group(Ping, args=[use_zerocopy, print_format])
    charm.awaitCreation(pings)
    msg_size = min_msg_size

    while msg_size <= max_msg_size:
        if msg_size <= 1048576:
            iter = low_iter
        else:
            iter = high_iter
        done_future = Future()
        pings.do_iteration(msg_size, iter, done_future)
        done_future.get()
        msg_size *= 2

    charm.exit()


charm.start(main)
