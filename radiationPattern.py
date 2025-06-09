import os
import skrf as rf
import numpy as np
import serial
import time
import gc
import shutil

###This program allows the user to measure a radiation pattern.
#You will need to set up the frequency band, step size and folder path.
#Then the program will execute, recording the detected s21 level at each point.
#The results will be stored in a file.

def obtener_carpeta(path):
    # Get all subdirectories in the base directory
    subdirectorios = [os.path.join(path, d) for d in os.listdir(path) 
                     if os.path.isdir(os.path.join(path, d))]
    
    # If no subdirectories exist, return None
    if not subdirectorios:
        return None
    
    # Sort subdirectories by creation time (newest first)
    subdirectorios.sort(key=lambda x: os.path.getctime(x), reverse=True)
    
    # Return just the name of the most recent directory (not the full path)
    return subdirectorios[0]

def obtener_s2p_mas_reciente():
    carpeta = obtener_carpeta(path)
    files = [f for f in os.listdir(carpeta) if f.endswith('.s2p') and not f.endswith('c.s2p')]
    if not files:
        return None
    files.sort(key=lambda x: os.path.getmtime(os.path.join(carpeta, x)), reverse=True)
    
    archivo_corregido = corregir_formato_s2p(os.path.join(carpeta, files[0]))
    return archivo_corregido

def corregir_formato_s2p(archivo_original):
    with open(archivo_original, 'r', encoding='utf-8') as f:
        lineas = f.readlines()

    # Reemplazar comas solo en líneas que parecen contener datos
    lineas_corregidas = []
    for linea in lineas:
        if linea.strip().startswith('!') or linea.strip().startswith('#'):
            lineas_corregidas.append(linea)  # comentarios y headers no se tocan
        else:
            lineas_corregidas.append(linea.replace(',', '.'))

    # Guardar como archivo temporal
    archivo_corregido = archivo_original + "_c.s2p"
    with open(archivo_corregido, 'w', encoding='utf-8') as f:
        f.writelines(lineas_corregidas)

    return archivo_corregido


def borrar_subcarpetas_excepto_reciente(carpeta):
    # Obtener la carpeta más reciente
    carpeta_reciente = obtener_carpeta(carpeta)
    
    if not carpeta_reciente:
        return
    
    # Obtener todas las subcarpetas
    subcarpetas = [os.path.join(carpeta, d) for d in os.listdir(carpeta) 
                  if os.path.isdir(os.path.join(carpeta, d))]
    
    # Si solo hay una subcarpeta, no es necesario borrar nada
    if len(subcarpetas) <= 1:
        return
    
    print("\nBorrando subcarpetas antiguas")
    for subcarpeta in subcarpetas:
        # Borrar solo si no es la carpeta más reciente
        if subcarpeta != carpeta_reciente:
            try:
                # Usar shutil.rmtree para eliminar directorios y su contenido
                shutil.rmtree(subcarpeta)
                print(f"Borrada subcarpeta: {os.path.basename(subcarpeta)}")
            except Exception as e:
                print(f"Error al borrar subcarpeta {os.path.basename(subcarpeta)}: {e}")
    
    return

def borrar_archivos(carpeta):
    NUM_ARCHIVOS_BORRAR = 10;
    print("Intentando borrar")
    files = [f for f in os.listdir(carpeta) if f.endswith('.s2p')]
    if not files:
        return
    if len(files) <=NUM_ARCHIVOS_BORRAR:
        return
    files.sort(key=lambda x: os.path.getmtime(os.path.join(carpeta, x)), reverse=True)
    files_delete = files[NUM_ARCHIVOS_BORRAR:]
    print("\nBorrando archivos")
    for file in files_delete:
        os.remove(os.path.join(carpeta, file))
    return


def arduino_enviar(angulo):
    global t
    
    if t > T:
        t = 0
        borrar_archivos(CARPETA_S2P)
    if angulo < 0 or angulo > 180:
        time.sleep(DELAY)
        print("ERROR: Angulo fuera del rango")
        return
    # Enviar ángulo al Arduino
    print(f"Ángulo: {angulo}°")
    angulo = angulo/1.5
    arduino.write(f"{angulo}\n".encode())
    angulo = angulo*1.5
    # Esperar que tome medida nueva
    t += 1
    time.sleep(DELAY)

def obtener_s21():
    
    file = obtener_s2p_mas_reciente()
    red = rf.Network(file)
    
    
    s21_array = []
    s21_db = 0
    frecuencias = red.f
    i = (abs(frecuencias - BANDA[0])).argmin()
    idx_start = i
    idx_finish = (abs(frecuencias - BANDA[1])).argmin()
    while(i<idx_finish):
        s21_nat = red.s[i, 1, 0] #Freq,#out_port,#
        s21_db = 20*np.log10(np.abs(s21_nat))
        s21_array.append(round(s21_db,4))
        i += 1
    if len(s21_array) == 0:
        print("s21_array vacío. Has puesto bien la frecuencia?")
        pass
    print(f"s21 = {max(s21_array)}")
    return max(s21_array)

def set_threshold():
    
    print("\nSetting threshold")
    
    s21_angulos = []
    angulos = []
    for angulo in range(angulo_final, angulo_0-1, -step_barrido):
        
        arduino_enviar(angulo)
        s21 = obtener_s21()
        
        angulos.append(angulo)
        s21_angulos.append(s21)
   

    s21_angulos.sort()   
    s21_UMBRAL_DB = s21_angulos[-1] + Margen
    print(f"\nUmbral en: {s21_UMBRAL_DB}")


def barrido(sentido):
    global angulo,s21_angulos,angulos,detect, mov
   
    if detect == 1:
        return
    if sentido in ("izq", "izquierda", "left"):
        mov = 1
    elif sentido in ("dr", "dcha", "derecha", "right", "der"):
        mov = -1
    else:
        print("Sentido no definido")
        return
    
    print("\nIniciando barrido")
    s21_angulos = []
    angulos = []

    if mov == 1:
        angulo_objetivo = angulo_final
    else:
        angulo_objetivo = angulo_0
    angulo = angulo + int(step_barrido*mov)
    for angulo in range(angulo, int(angulo_objetivo), int(step_barrido*mov)):
        
        arduino_enviar(angulo)
        s21 = obtener_s21()
        angulos.append(angulo)
        s21_angulos.append(s21)
        if s21 > s21_UMBRAL_DB:
            detect = 1
            return

    if abs(angulo-angulo_objetivo) <= step_barrido:
        angulo = angulo_objetivo
        arduino_enviar(angulo)
        s21 = obtener_s21()
        angulos.append(angulo)
        s21_angulos.append(s21)
        if s21 > s21_UMBRAL_DB:
            detect = 1
            return
        
    if mov == 1 : barrido("derecha")
    if mov == -1: barrido("izquierda")
    
        
def rotar(sentido):  ##Rotar no pilla el angulo en el que ya está
    global angulo,s21_angulos,angulos,detect, mem_movimiento
    pasos = pasos_busq
   
    if detect == 1:
        return
    if sentido in ("izq", "izquierda", "left"):
        mov = 1
        print("\nRotando izq")
    elif sentido in ("dr", "dcha", "derecha", "right", "der"):
        mov = -1
        print("\nRotando dcha")
    else:
        print("Sentido no definido")
        return
    
    #cambiar_mem_movimiento = 1
    s21_angulos = []
    angulos = []

    angulo_objetivo = angulo+int(mov*pasos*step_busqueda)
    
    if angulo_objetivo > angulo_final: angulo_objetivo = angulo_final
    if angulo_objetivo < angulo_0: angulo_objetivo = angulo_0
    
    
    for angulo in range(angulo+int(step_busqueda*mov), angulo_objetivo, int(step_busqueda*mov)):
        
        arduino_enviar(angulo)
        s21 = obtener_s21()
        angulos.append(angulo)
        s21_angulos.append(s21)
        if s21 > s21_UMBRAL_DB:
            detect = 1
            return
        
    if abs(angulo-angulo_objetivo) <= step_barrido:
        angulo = angulo_objetivo
        arduino_enviar(angulo)
        s21 = obtener_s21()
        angulos.append(angulo)
        s21_angulos.append(s21)
        if s21 > s21_UMBRAL_DB:
            detect = 1
            
            return
    
        
def busqueda():
    global mem_movimiento, cambiar_mem_movimiento
    if detect == 1: return
    
    if mem_movimiento != 1 and mem_movimiento != -1:
        mem_movimiento = 1
    if mem_movimiento == 1: #izquierda
        sentido1 = "izq"
        sentido2 = "dcha"
    if mem_movimiento == -1:
        sentido1 = "dcha"
        sentido2 = "izq"

    rotar(sentido1)
    if detect == 1: return
    rotar(sentido2)
    mem_movimiento = int(-1*mem_movimiento)
    
def guardar_datos(carpeta, angulos, s21_valores, nombre_archivo=None):
    """
    Guarda los datos de ángulos y valores S21 en un archivo de texto en la carpeta especificada.
    
    Args:
        carpeta (str): Ruta de la carpeta donde guardar el archivo
        angulos (list): Lista de ángulos
        s21_valores (list): Lista de valores S21
        nombre_archivo (str, optional): Nombre del archivo. Si es None, se genera automáticamente
    
    Returns:
        str: Ruta completa del archivo guardado
    """
    from datetime import datetime
    

    # Generar nombre de archivo con timestamp si no se proporciona uno
    if nombre_archivo is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"medidas_s21_{timestamp}.txt"
    
    # Ruta completa del archivo
    ruta_archivo = os.path.join(carpeta, nombre_archivo)
    
    # Guardar los datos en el archivo
    with open(ruta_archivo, 'w') as f:
        f.write("Angulo\tS21\n")  # Encabezado
        for ang, s21 in zip(angulos, s21_valores):
            f.write(f"{ang}\t{s21}\n")
    
    print(f"Datos guardados en: {ruta_archivo}")
    return 

# # ARDUINO SETUP
SERIAL_PORT = 'COM4'  # Put your arduino port
BAUD_RATE = 9600
#  
#  
# # # Initiate serial comunication
arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.8) #timeout in seconds
time.sleep(2)  # Wait for the setup


###CONFIGURATION



angulo_0 = 0
angulo = angulo_0 
angulo_final = 180


T = 50    #Number of measurements before attempting to delete nanoVNA files
t = 0



####VARIABLES PARA CAMBIAR
#Set your folder path here
path = "C:/Users/..."
BANDA = [5.68e9,5.69e9] #Frequency range. max 6e9
s21_UMBRAL_DB = -40	
Margen = 3     
DELAY = 0.2      #Measurement delay in seconds. Around 0.3 for best results.
step_barrido = 5     #Step size (in degrees)



CARPETA_S2P = obtener_carpeta(path)
print(CARPETA_S2P)
borrar_subcarpetas_excepto_reciente(path)
borrar_archivos(CARPETA_S2P)


while True:
    
    s21_angulos = []
    angulos = []
    
    for angulo in range(angulo_0,angulo_final,step_barrido):
        arduino_enviar(angulo)
        s21 = obtener_s21()
        angulos.append(angulo)
        s21_angulos.append(s21)
    
    guardar_datos(path, angulos, s21_angulos)
    opcion = input("\nPress any key to repeat or 'q' to quit: ")
    if opcion.lower() == 'q':
        break
        
    

    