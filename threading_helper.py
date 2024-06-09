from threading import Lock

class ProtectedList(object):

    def __init__(self, buffer_size=8):
        # Inicializa la lista y el tamaño del búfer, así como el objeto de bloqueo.
        self.elements = []
        self.buffer_size = buffer_size
        self.lock = Lock()

    def put(self, element):
        # Adquiere el bloqueo antes de realizar la operación en la lista.
        self.lock.acquire()

        # Añade un nuevo elemento al final de la lista.
        self.elements.append(element)

        # Elimina el elemento más antiguo si la lista es demasiado larga.
        if len(self.elements) > self.buffer_size:
            self.elements.pop(0)

        # Libera el bloqueo después de completar la operación.
        self.lock.release()

    def get(self):
        # Adquiere el bloqueo antes de realizar la operación en la lista.
        self.lock.acquire()

        # Verifica si hay elementos en la lista.
        if len(self.elements) > 0:
            element = self.elements[0]
            del self.elements[0]
        else:
            # Si la lista está vacía, devuelve None.
            element = None

        # Libera el bloqueo después de completar la operación.
        self.lock.release()
        return element

    def __repr__(self):
        # Adquiere el bloqueo antes de obtener la representación en cadena de la lista.
        self.lock.acquire()

        # Obtiene una representación en cadena de la lista.
        string = str(self.elements)

        # Libera el bloqueo después de obtener la representación en cadena.
        self.lock.release()
        return string