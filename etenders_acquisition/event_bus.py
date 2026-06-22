import queue

class EventBus:

    def __init__(self):
        self.q = queue.Queue()

    def publish(self, event):
        self.q.put(event)

    def consume(self):
        return self.q.get()
