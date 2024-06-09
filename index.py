from flask import Flask, render_template, request, send_file, jsonify
from threading import Thread
import copy
from pyaudio import PyAudio, paInt16
from datetime import datetime
import numpy as np
import re
import sys
import os
import time
import threading

app = Flask(__name__)

running = False
main_thread = None
TABLATURAS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Tablaturas')

@app.route('/')
def mainPage():
    return render_template('mainpage.html')
    
@app.route('/grabar_tablatura', methods=['GET'])
def grabarTablatura():
    global running, main_thread
    if running:
        running = False
        if main_thread:
            main_thread.join()
        latest_file = get_latest_file(TABLATURAS_DIR)
        if latest_file:
            return jsonify({'latest_file': latest_file})
        else:
            return jsonify({'latest_file': None})
    else:
        running = True
        main_thread = threading.Thread(target=main)
        main_thread.start()
        return jsonify({'status': 'started'})

def get_latest_file(directory):
    try:
        files = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        latest_file = max(files, key=os.path.getctime)
        return latest_file
    except ValueError:
        return None

@app.route('/rename_and_download', methods=['POST'])
def rename_and_download():
    data = request.get_json()
    old_name = data['old_name']
    new_name = data['new_name']

    if not new_name:
        return "New name cannot be empty", 400

    sanitized_name = re.sub(r'[<>:"/\\|?*]', '', new_name)

    if len(sanitized_name) > 255:
        sanitized_name = sanitized_name[:255]

    if not sanitized_name.endswith('.odt'):
        sanitized_name += '.odt'

    old_path = os.path.join(TABLATURAS_DIR, old_name)
    new_path = os.path.join(TABLATURAS_DIR, sanitized_name)

    if os.path.exists(new_path):
        return "A file with the new name already exists", 400

    try:
        os.rename(old_path, new_path)
        return send_file(new_path, as_attachment=True)
    except Exception as e:
        return f"An unexpected error occurred: {e}", 500

class AudioAnalyzer(Thread):
    # Settings
    SAMPLING_RATE = 48000
    CHUNK_SIZE = 1024 
    BUFFER_TIMES = 10 
    ZERO_PADDING = 3
    NUM_HPS = 4

    def __init__(self, queue, *args, **kwargs):
        Thread.__init__(self, *args, **kwargs)

        self.queue = queue 
        self.buffer = np.zeros(self.CHUNK_SIZE * self.BUFFER_TIMES)
        self.hanning_window = np.hanning(len(self.buffer))
        self.running = False

        try:
            self.audio_object = PyAudio()
            self.stream = self.audio_object.open(format=paInt16,
                                                 channels=1,
                                                 rate=self.SAMPLING_RATE,
                                                 input=True,
                                                 output=False,
                                                 frames_per_buffer=self.CHUNK_SIZE)
        except Exception as e:
            sys.stderr.write('Error: Line {} {} {}\n'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
            return

    @staticmethod
    def frequency_to_number(freq, a4_freq):

        if freq == 0:
            sys.stderr.write("Error: No frequency data. Program has potentially no access to microphone\n")
            return 0

        return 12 * np.log2(freq / a4_freq) + 69

    @staticmethod
    def number_to_frequency(number, a4_freq):

        return a4_freq * 2.0**((number - 69) / 12.0)

    @staticmethod
    def number_to_note_name(number):

        return AudioAnalyzer.NOTE_NAMES[int(round(number) % 12)]

    @staticmethod
    def frequency_to_note_name(frequency, a4_freq):

        number = AudioAnalyzer.frequency_to_number(frequency, a4_freq)
        note_name = AudioAnalyzer.number_to_note_name(number)
        return note_name

    def run(self):

        self.running = True

        while self.running:
            try:
                data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                data = np.frombuffer(data, dtype=np.int16)

                self.buffer[:-self.CHUNK_SIZE] = self.buffer[self.CHUNK_SIZE:]
                self.buffer[-self.CHUNK_SIZE:] = data

                magnitude_data = abs(np.fft.fft(np.pad(self.buffer * self.hanning_window,
                                                       (0, len(self.buffer) * self.ZERO_PADDING),
                                                       "constant")))
               
                magnitude_data = magnitude_data[:int(len(magnitude_data) / 2)]

                
                magnitude_data_orig = copy.deepcopy(magnitude_data)
                for i in range(2, self.NUM_HPS+1, 1):
                    hps_len = int(np.ceil(len(magnitude_data) / i))
                    magnitude_data[:hps_len] *= magnitude_data_orig[::i] 

                
                frequencies = np.fft.fftfreq(int((len(magnitude_data) * 2) / 1),
                                             1. / self.SAMPLING_RATE)
                
                for i, freq in enumerate(frequencies):
                    if freq > 60:
                        magnitude_data[:i - 1] = 0
                        break

                self.queue.put(round(frequencies[np.argmax(magnitude_data)], 2))

            except Exception as e:
                sys.stderr.write('Error: Line {} {} {}\n'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))

        self.stream.stop_stream()
        self.stream.close()
        self.audio_object.terminate()


# if __name__ == "__main__":
#     # Only for testing:
#     from audio_analizador.threading_helper import ProtectedList
#     import time

#     q = ProtectedList()
#     a = AudioAnalyzer(q)
#     a.start()

#     while True:
#         q_data = q.get()
#         if q_data is not None:
#             print("loudest frequency:", q_data, "nearest note:", a.frequency_to_note_name(q_data, 440))
#             time.sleep(0.02)

milisegundos = round(datetime.now().timestamp() * 1000)
fileName = f"tablatura_{milisegundos}.txt"

contado = 1

nombre_nota = [
        [(81, 83), (86, 88), (91, 93), (97.5, 99), (102.5, 104.5), (110, 112), (115.5, 117.5), (122.5, 124.5), (129.5, 131.5), (138, 140), (146, 148), (155.5, 157.5), (165, 167), (174, 176), (185, 187), (196.4, 198.4)],
        [(108, 109), (115.5, 117.5), (121.5, 123.5), (129.5, 131.5), (138, 140), (146, 148), (155.5, 157.5), (165, 167), (174, 176), (185, 187), (195.4, 197.4), (207, 209), (220, 222), (233, 235), (246.5, 248.5), (262, 264)],
        [(146, 147.5), (154.8, 156.8), (166, 168), (175, 177), (185.8, 187.8), (196, 198), (207.8, 209.8), (221, 223), (234, 236), (248, 250), (263, 265), (278.7, 280.7), (296, 298), (311.8, 313.8), (332, 334), (350.5, 352.5)],
        [(195, 197), (207, 209), (219.8, 221.8), (232.8, 234.8), (246.8, 248.8), (261.5, 263.5), (276.8, 278.8), (293.5, 296), (311, 313), (330, 332), (349.5, 351.5), (370.8, 372.8), (393, 395), (416.8, 418.8), (441.8, 443.8), (468, 470)],
        [(246.5, 248.5), (262, 264), (277.8, 279.8), (294.5, 296.5), (311.8, 313.8), (330.5, 332.5), (350, 352), (371, 373), (393, 395), (417.6, 419.6), (441.5, 443.5), (468, 470), (496.5, 498.5), (526, 528), (557.5, 559.5), (591, 593)],
        [(328, 330.5), (349.7, 351.7), (370.5, 372.5), (392.5, 394.5), (415, 417), (440, 442), (466.3, 469.8), (494.5, 497.5), (523, 526), (555, 557), (587.3, 589.3), (621.4, 623.4), (658, 661), (700.5, 702.5), (739.6, 742.6), (784, 786.5)]
    ]

cuerda1, cuerda2, cuerda3, cuerda4, cuerda5, cuerda6 = "E|", "A|", "D|", "G|", "B|", "e|"
contado = 1

def write_tablature(i_ant, j_ant):
    global contado, cuerda1, cuerda2, cuerda3, cuerda4, cuerda5, cuerda6

    cuerdas = [cuerda1, cuerda2, cuerda3, cuerda4, cuerda5, cuerda6]

    for i in range(6):
        if i_ant != 1:
            if i == i_ant:
                cuerdas[i] += "{j_ant:02}-".format(j_ant=j_ant)
            else:
                cuerdas[i] += "---"
        else:
            cuerdas[i] += "---"
        
        if contado == 12:
                cuerdas[i] += "|"

    cuerda1, cuerda2, cuerda3, cuerda4, cuerda5, cuerda6 = cuerdas

    if contado % 25 == 0:
        with open(".\\Tablaturas\\" + fileName, "a+") as f:
            cuerda1 += "|"
            cuerda2 += "|"
            cuerda3 += "|"
            cuerda4 += "|"
            cuerda5 += "|"
            cuerda6 += "|"

            f.write(cuerda6 + "\n")
            f.write(cuerda5 + "\n")
            f.write(cuerda4 + "\n")
            f.write(cuerda3 + "\n")
            f.write(cuerda2 + "\n")
            f.write(cuerda1 + "\n")
            f.write("\n")
            f.write("\n")

            cuerda1 = "E|"
            cuerda2 = "A|"
            cuerda3 = "D|"
            cuerda4 = "G|"
            cuerda5 = "B|"
            cuerda6 = "e|"

            contado = 0
    
    contado += 1 

        

def busq_defecto(q_data):
    for i, row in enumerate(nombre_nota):
        for j, intervalo in enumerate(row):
            if intervalo[0] <= q_data <= intervalo[1]:
                return (i, j) 
    return None

def encontrar_trast_cercano(i_ant, j_ant, hzs, nombre_nota):

    desplazamientos = [
        (1, 0), (0, 1), (2, 0), (0, 2),  
        (3, 0), (0, 3), (4, 0), (0, 4),  
        (5, 0), (0, 5), (6, 0), (0, 6)
    ]
    
    for dx, dy in desplazamientos:
        x=0
        y=0
        while (x, y) != (dx, dy):
            if(dx != 0):
                x+=1
                if dx % 2 == 0:
                    i_ant -= 1
                else:
                    i_ant += 1
            if(dy != 0):
                y+=1        
                if dy % 2 == 0:
                    j_ant -= 1
                else:
                    j_ant += 1

            if 0 <= i_ant < len(nombre_nota) and 0 <= j_ant < len(nombre_nota[0]):
                if nombre_nota[i_ant][j_ant][0] <= hzs <= nombre_nota[i_ant][j_ant][1]:
                    return [i_ant, j_ant]
            else:
                return None

def main():
    from threading_helper import ProtectedList

    q = ProtectedList()
    a = AudioAnalyzer(q)
    a.start()

    i_ant = None
    j_ant = None

    while running:
        q_data = q.get()
        if q_data is not None:
            if i_ant is None or j_ant is None: 
                traste_cercano = busq_defecto(q_data)
                if traste_cercano is None:
                    i_ant = -1
                    j_ant = -1
                else:
                    i_ant = traste_cercano[0]
                    j_ant = traste_cercano[1]
            else:
                traste_cercano = encontrar_trast_cercano(i_ant, j_ant, q_data, nombre_nota)
                if traste_cercano is not None:
                    i_ant = traste_cercano[0]
                    j_ant = traste_cercano[1]
                else:
                    traste_cercano = busq_defecto(q_data)
                    
                    if traste_cercano is None:
                        i_ant = -1
                        j_ant = -1
                    else:
                        i_ant = traste_cercano[0]
                        j_ant = traste_cercano[1]

            write_tablature(i_ant, j_ant)
        time.sleep(0.07)

if __name__ == '__main__':
    app.run(debug=True)
