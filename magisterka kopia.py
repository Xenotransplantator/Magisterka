# Importowanie niezbędnych bibliotek
import tkinter as tk
from tkinter import messagebox
import numpy as np
import matplotlib.pyplot as plt
from rtlsdr import RtlSdr
from skyfield.api import Topos, load
from scipy.fft import fft
import sqlite3
from flask import Flask, render_template, jsonify, request
from datetime import datetime

# Funkcja sprawdzająca, czy urządzenie SDR-RTL jest podłączone
def is_rtl_sdr_connected():
    try:
        sdr = RtlSdr()
        sdr.close()
        return True
    except Exception as e:
        return False

# Funkcja wyświetlająca alert
def show_alert():
    root = tk.Tk()
    root.withdraw()  # Ukryj główne okno aplikacji
    messagebox.showerror("Błąd", "Urządzenie SDR-RTL nie jest podłączone.")
    root.destroy()

# Sprawdź, czy urządzenie SDR-RTL jest podłączone
if not is_rtl_sdr_connected():
    show_alert()

# Konfiguracja aplikacji Flask
app = Flask(__name__)

# Konfiguracja odbiornika RTL-SDR
sdr = RtlSdr()
sdr.sample_rate = 2.4e6
sdr.center_freq = 437.5e6
sdr.gain = 'auto'

# Wczytanie danych niezbędnych do obliczeń astronomicznych
data = load('de421.bsp')
earth = data['earth']

# Utworzenie obiektu Topos dla położenia obserwatora (współrzędne geograficzne użytkownika do wklepania poniżej) 
observer_latitude = 50.0647
observer_longitude = 19.9450
observer_elevation = 200
observer = earth + Topos(observer_latitude, observer_longitude, elevation_m=observer_elevation)

# Baza danych SQLite do przechowywania historii pomiarów
conn = sqlite3.connect('measurements.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY,
        date TIMESTAMP,
        latitude REAL,
        longitude REAL,
        elevation REAL,
        azimuth REAL,
        altitude REAL,
        velocity REAL,
        visibility BOOLEAN,
        sun_distance REAL,
        power_spectrum BLOB
    )
''')
conn.commit()

# Strona internetowa - interfejs użytkownika
@app.route('/')
def index():
    return render_template('index.html')

# Funkcja do analizy sygnału
def analyze_signal():
    samples = sdr.read_samples(1024*10)
    power_spectrum = np.abs(fft(samples))**2
    return power_spectrum

# Funkcja do obliczeń astronomicznych
def calculate_astronomical_data():
    ts = load.timescale()
    current_time = ts.now()
    geocentric = observer.at(current_time).observe(iss)
    subpoint = geocentric.subpoint()
    latitude = subpoint.latitude.degrees
    longitude = subpoint.longitude.degrees
    elevation = subpoint.elevation.km
    azimuth = geocentric.apparent().altaz()[1].degrees
    altitude = geocentric.apparent().altaz()[0].degrees
    velocity = iss.velocity.km_per_s
    visibility = geocentric.apparent().is_sunlit()
    return latitude, longitude, elevation, azimuth, altitude, velocity, visibility

# Zapisywanie pomiarów do bazy danych
def save_measurement(date, latitude, longitude, elevation, azimuth, altitude, velocity, visibility, sun_distance, power_spectrum):
    cursor.execute('''
        INSERT INTO measurements (date, latitude, longitude, elevation, azimuth, altitude, velocity, visibility, sun_distance, power_spectrum)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (date, latitude, longitude, elevation, azimuth, altitude, velocity, visibility, sun_distance, power_spectrum))
    conn.commit()

# Wywołanie funkcji analizy sygnału i obliczeń astronomicznych oraz zapis wyników do bazy danych
@app.route('/analyze', methods=['POST'])
def analyze():
    power_spectrum = analyze_signal()
    latitude, longitude, elevation, azimuth, altitude, velocity, visibility = calculate_astronomical_data()
    sun_distance = iss.distance().km
    date = datetime.now()
    save_measurement(date, latitude, longitude, elevation, azimuth, altitude, velocity, visibility, sun_distance, power_spectrum)
    return jsonify({
        'date': date,
        'latitude': latitude,
        'longitude': longitude,
        'elevation': elevation,
        'azimuth': azimuth,
        'altitude': altitude,
        'velocity': velocity,
        'visibility': visibility,
        'sun_distance': sun_distance,
        'power_spectrum': power_spectrum.tolist(),
    })

# Wyświetlanie historii pomiarów
@app.route('/history')
def history():
    cursor.execute('SELECT * FROM measurements ORDER BY id DESC LIMIT 10')
    rows = cursor.fetchall()
    measurements = []
    for row in rows:
        measurements.append({
            'id': row[0],
            'date': row[1],
            'latitude': row[2],
            'longitude': row[3],
            'elevation': row[4],
            'azimuth': row[5],
            'altitude': row[6],
            'velocity': row[7],
            'visibility': row[8],
            'sun_distance': row[9],
        })
    return jsonify(measurements)

if __name__ == '__main__':
    app.run(debug=True)
