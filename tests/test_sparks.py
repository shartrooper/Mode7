import pygame as pg
import numpy as np
import sys
import os
import time

# Ensure we can import from the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from effects.spark_system import SparkSystem
from settings import *

class SparkSandbox:
    def __init__(self):
        pg.init()
        self.screen = pg.display.set_mode(WIN_RES)
        pg.display.set_caption("Spark System Sandbox")
        self.clock = pg.time.Clock()
        
        self.spark_system = SparkSystem(max_particles=1500)
        
        # Mock Game State
        self.player_pos = np.array([PLAYER_START_POS[0], PLAYER_START_POS[1]], dtype=np.float32)
        self.player_angle = np.pi / 2
        self.player_speed = 0.1  # Fast enough for sparks
        self.visual_tilt = 0.0
        
        self.screen_array = np.zeros((WIDTH, HEIGHT, 3), dtype=np.uint8)

    def update(self):
        dt = self.clock.tick(FPS)
        
        # Simulate Tilting (Oscillate for testing)
        t = time.time()
        self.visual_tilt = np.sin(t * 2) * 1.0  # Swings -1 to 1
        
        # Trigger sparks when tilt is high
        if abs(self.visual_tilt) > 0.8:
            # Calculate a spawn position in world space
            # Offset it based on tilt direction
            side = -1.0 if self.visual_tilt > 0 else 1.0
            cos_a, sin_a = np.cos(self.player_angle), np.sin(self.player_angle)
            
            # Wingtip offset (roughly)
            offset_mag = 0.05 
            spawn_pos = self.player_pos + np.array([
                -sin_a * offset_mag * side,
                cos_a * offset_mag * side
            ], dtype=np.float32)
            
            # Z starts at 0 (contact)
            spawn_pos_3d = np.array([spawn_pos[0], spawn_pos[1], 0.0], dtype=np.float32)
            
            # Velocity: Ship vel (forward) + backward bias + spray
            ship_vel_vec = np.array([cos_a, sin_a, 0.0], dtype=np.float32) * self.player_speed
            spawn_vel = (ship_vel_vec * -0.5) # Thrown backwards
            
            self.spark_system.spawn(spawn_pos_3d, spawn_vel, count=3)
            
        self.spark_system.update(dt)

    def render(self):
        # Clear screen (dark grey)
        self.screen_array.fill(20)
        
        # Draw a simple grid on the "floor" for perspective context
        # We can't easily draw the whole Mode7 floor here, but we can do a few lines
        
        cam_offset = np.array([
            -CAM_DISTANCE * np.cos(self.player_angle),
            -CAM_DISTANCE * np.sin(self.player_angle)
        ])
        cam_pos = self.player_pos + cam_offset
        
        settings_dict = {
            'WIDTH': WIDTH,
            'HEIGHT': HEIGHT,
            'HALF_WIDTH': HALF_WIDTH,
            'HALF_HEIGHT': HALF_HEIGHT,
            'STD_HORIZON': STD_HORIZON,
            'SCALE': SCALE,
            'angle': self.player_angle,
            'cam_pos': cam_pos,
            'alt': CAM_ALT,
            'focal_len': FOCAL_LEN
        }
        
        self.spark_system.render(self.screen_array, settings_dict)
        
        pg.surfarray.blit_array(self.screen, self.screen_array)
        
        # Draw UI info
        font = pg.font.SysFont('Consolas', 20)
        tilt_text = font.render(f"Visual Tilt: {self.visual_tilt:.2f}", True, (255, 255, 255))
        count_text = font.render(f"Particles: {np.sum(self.spark_system.particles[:, 7])}", True, (255, 255, 255))
        self.screen.blit(tilt_text, (20, 20))
        self.screen.blit(count_text, (20, 50))
        
        pg.display.flip()

    def run(self):
        running = True
        while running:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    running = False
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_ESCAPE:
                        running = False
            
            self.update()
            self.render()
        pg.quit()

if __name__ == "__main__":
    sandbox = SparkSandbox()
    sandbox.run()