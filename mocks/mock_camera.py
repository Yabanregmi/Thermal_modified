# mock_camera.py
import numpy as np
import time
import random

class MockCameraController:
    def __init__(self):
        self.palette_width = 80
        self.palette_height = 60
        self.thermal_width = 80
        self.thermal_height = 60
        self.opened = True
        self._t0 = time.time()

    def read_frame(self):
        # Fake-RGB (schwarzes Bild mit grauer Fläche)
        rgb = np.full((self.palette_height, self.palette_width, 3), 64, dtype=np.uint8)
        # Fake-Temperatur: meist 22.0, alle ~7 s mal 55.0 (Anomalietest)
        if int(time.time() - self._t0) % 7 == 0:
            temp_c = 55.0
        else:
            temp_c = 22.0 + random.uniform(-0.5, 0.5)
        return rgb, temp_c

    def release(self):
        self.opened = False
