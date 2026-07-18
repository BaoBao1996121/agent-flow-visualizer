import threading

lock = threading.RLock()
entered = threading.Event()
finished = threading.Event()

def writer():
    entered.set()
    with lock:
        with lock:
            finished.set()

with lock:
    thread = threading.Thread(target=writer)
    thread.start()
    assert entered.wait(1) and not finished.wait(0.05)
thread.join(1)
assert finished.is_set()
