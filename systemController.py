import os
import skrf as rf
import numpy as np
import serial
import time
import gc
import shutil

###This program will let you control the rotating system in a specific angle or sweep the entire range.
#Can be useful for live measurements and prototype testing.

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
    print(f"{angulo}\n".encode())
    angulo = angulo/1.5
    arduino.write(f"{angulo}\n".encode())
    angulo = angulo *1.5
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
        print(f"s21 = {s21}")
        
        angulos.append(angulo)
        s21_angulos.append(s21)
   

    s21_angulos.sort()   
    s21_UMBRAL_DB = s21_angulos[2] + Margen
    print(f"\nUmbral en: {s21_UMBRAL_DB}")


def barrido(sentido):
    global angulo,s21_angulos,angulos,detect
   
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

        
def rotar(sentido):  ##Rotar no pilla el angulo en el que ya está
    global angulo,s21_angulos,angulos,detect
    pasos = pasos_busq
   
    if detect == 1:
        return
    if sentido in ("izq", "izquierda", "left"):
        mov = 1
    elif sentido in ("dr", "dcha", "derecha", "right", "der"):
        mov = -1
    else:
        print("Sentido no definido")
        return
    
    cambiar_mem_movimiento = 1
    s21_angulos = []
    angulos = []

    angulo_objetivo = angulo+int(mov*pasos*step_busqueda)
    if angulo_objetivo > angulo_final: angulo_objetivo = angulo_final
    if angulo_objetivo < angulo_final: angulo_objetivo = angulo_0
             

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
        
    cambiar_mem_movimiento = -1
        
def busqueda():
    if mem_movimiento != 1 or mem_movimiento != -1: mem_movimiento = 1
    if mem_movimiento == 1: #izquierda
        sentido = "izq"
    if mem_movimiento == -1:
        sentido = "dcha"
 
    rotar(sentido)
    mem_movimiento = mem_movimiento*cambiar_mem_movimiento
    

# # ARDUINO SETUP
SERIAL_PORT = 'COM4'  # Put your arduino port
BAUD_RATE = 9600
#  
#  
# # # Initiate serial comunication
arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.8) #timeout in seconds
time.sleep(2)  # Wait for the setup

###CONFIGURATION
    
#Folder 
path = "C:/Users/..." 

BANDA = [5.68e9,5.69e9] #Frequency range. max 6e9
s21_UMBRAL_DB = -40		#Manual threshold setting
Margen = 3     #Margin for the automatic threshold
DELAY = 0.4      #Waiting time in seconds between each measurement. Set higher or equal than 0.3 for better results
step_barrido = 15    #Step of movement in sweeping mode
step_busqueda = 15   #Step of movement in search mode
pasos_busq = 4

angulo_0 = 40 #Starting angle
angulo = angulo_0 
angulo_final = 145 #Final angle
umbral_dinamico = 0  #0 For manual threshold, 1 For automatic threshold setting at the start.

T = 50    #Number of measurements before attempting to delete nanoVNA files
t = 0

angulo_0 = 25
angulo = angulo_0 
angulo_final = 90
umbral_dinamico = 0

T = 50    #Numero de medidas hasta borrar archivos
t = 0


scan = 1
detect = -1   #-1, empieza el programa/scan, 1 detectado, 0 perdido
memoria_movimiento = 1#-1 dcha, +1 izq, 0 no tiene

s21_angulos = []
angulos = []
busqueda = 0
angulo_mitad = (angulo_0+angulo_final)/2

CARPETA_S2P = obtener_carpeta(path)
print(CARPETA_S2P)


step = 5 #Step size

#Initializing in angle 0º
arduino_enviar(0)
angulo_actual = 0

mediciones = []  # Para almacenar [ángulo, s21]

while True:
    # Mostrar menú de opciones
    print("\n=== Radiation Diagram Program ===")
    print(f"Current angle: {angulo_actual}°")
    print("Options:")
    print("  1 - Next angle")
    print("  2 - Reset (go back to 0°)")
    print("  3 - Go to a specific angle")
    print("  4 - Exit the program")
    
    # Leer medición actual
    s21 = obtener_s21()
    
    opcion = input("\nSelect one option (1-4): ")
    
    if opcion == "1":
        angulo_actual += step
        if arduino_enviar(angulo_actual):
            s21 = obtener_s21()
            mediciones.append([angulo_actual, s21])
                
    elif opcion == "2":
        mediciones = []
        arduino_enviar(0)
        angulo_actual = 0
        
    elif opcion == "3":
        try:
            angulo_actual = int(input("Introduce the desired angle (0º-180º)"))
            print(angulo_actual)
            if arduino_enviar(angulo_actual):
                s21 = obtener_s21()
                mediciones.append([angulo_actual, s21])
        except ValueError:
            print("Invalid input.")
            
    elif opcion == "4":
        # Guardar resultados antes de salir
        if mediciones:
            print("Guardando resultados...")
            try:
                np.savetxt("diagram.csv", 
                          np.array(mediciones), 
                          delimiter=",", 
                          header="Angulo,S21_dB", 
                          comments="")
                print(f"Results saved in 'diagram.csv'")
            except Exception as e:
                print(f"Error when saving results: {e}")
        break
    
    else:
        print("Invalid option")
