import pygame as pg
import numpy as np
from settings import *
from machine import DOPAMINE_FALCON
from numba import njit, prange


class Player:
    def __init__(self, start_pos, machine):
        self.pos = np.array(start_pos, dtype=np.float32)
        self.machine = machine
        self.speed = 0.0
        self.angle = np.pi/2
        self.turn_input = 0.0
        self.shift_force = 0.0
        self.shift_dir = 0
        
        # Vertical physics
        self.z = 0.0
        self.vz = 0.0
        self.pitch = 0  # -1: Nose Down, 0: Level, 1: Nose Up
        self.jump_timer = 0.0

    def update(self, dt):
        keys = pg.key.get_pressed()
        accelerating = keys[pg.K_SPACE]
        braking = keys[pg.K_s]
        
        # Immediate Pitch Control
        if keys[pg.K_UP]: self.pitch = 1
        elif keys[pg.K_DOWN]: self.pitch = -1
        else: self.pitch = 0

        # Movement Logic
        if self.z > 0:
            # Airborne speed logic: Air should preserve momentum BETTER than ground
            if braking:
                self.speed = max(0, self.speed - self.machine.brake * 0.5 * dt)
            elif accelerating:
                # Accelerating in air is weaker than ground
                self.speed += self.machine.accel * 0.4 * dt
            
            # Dynamic Air Drag: Lower than ground friction (5.5)
            # If gliding (Pitch -1), drag is reduced even further to maintain momentum
            air_drag_factor = 1.5 if self.pitch == -1 else 3.0
            drag = self.speed * (self.machine.friction * air_drag_factor) * dt
            self.speed = max(0, self.speed - drag)
        else:
            # Ground speed logic: Apply acceleration and braking
            if braking:
                self.speed = max(0, self.speed - self.machine.brake * dt)
            elif accelerating:
                self.speed += self.machine.accel * dt
            
            # ALWAYS Apply Drag (Proportional Friction)
            drag = self.speed * (self.machine.friction * 5.5) * dt
            self.speed = max(0, self.speed - drag)
            
            # Rolling Resistance: If not accelerating/braking, add a small flat speed loss
            if not accelerating and not braking and self.speed > 0:
                self.speed = max(0, self.speed - self.machine.friction * 0.4 * dt)

        self.speed = np.clip(self.speed, 0, self.machine.max_speed)

        # Vertical Physics Simulation
        if self.z > 0 or self.vz > 0:
            self.jump_timer += dt
            
            # Simulated gravity affected by pitch
            effective_gravity = self.machine.gravity
            if self.pitch == -1: effective_gravity *= 0.6
            elif self.pitch == 1: effective_gravity *= 1.6
            
            self.vz -= effective_gravity * dt
            self.z += self.vz * dt

            if self.z <= 0:
                self.handle_landing()

        turn_dir = 0.0
        if keys[pg.K_LEFT]:
            turn_dir -= 1.0
        if keys[pg.K_RIGHT]:
            turn_dir += 1.0
        self.turn_input = turn_dir

        if turn_dir and self.speed:
            steer_scale = self.machine.steer_speed * (0.35 + abs(self.speed) / self.machine.max_speed)
            self.angle -= turn_dir * steer_scale * dt

        cos_a = np.cos(self.angle)
        sin_a = np.sin(self.angle)

        shift_left = keys[pg.K_q]
        shift_right = keys[pg.K_e]
        shift_input = 0
        if shift_left and not shift_right:
            shift_input = 1
        elif shift_right and not shift_left:
            shift_input = -1

        shift_active = abs(self.speed) > self.machine.shift_min
        if shift_input and shift_active:
            self.shift_dir = shift_input
            increment = self.machine.shift_inc * abs(self.speed) * dt
            self.shift_force = min(self.shift_force + increment, self.machine.shift_max)
        else:
            self.shift_force = max(0.0, self.shift_force - self.machine.shift_decay * dt)
            if self.shift_force == 0 or not shift_active:
                self.shift_dir = 0

        self.pos[0] += cos_a * self.speed * dt
        self.pos[1] += sin_a * self.speed * dt

        if self.shift_force and self.shift_dir and shift_active:
            side_vec = np.array([-sin_a, cos_a], dtype=np.float32)
            lateral = side_vec * self.shift_force * self.shift_dir * dt
            self.pos += lateral

    def handle_landing(self):
        # High speed + Long jump requires Nose Down for smooth landing
        # Test 3: +200 kmh speed threshold (approx 0.048 in engine units)
        # Test 3: > 1.0s jump duration threshold (approx 60 frames)
        
        speed_threshold = self.machine.max_speed * 0.4  # 0.048 for 200 kmh
        time_threshold = 50  # Slightly less than 60 to be generous
        
        if self.jump_timer > time_threshold and self.speed > speed_threshold:
            if self.pitch == -1:
                # Smooth Landing: insignficant loss
                self.speed *= 0.98
            else:
                # Hard Landing: sharp loss
                self.speed *= self.machine.hard_landing_penalty
        
        self.z = 0
        self.vz = 0
        self.jump_timer = 0


class JumpPad:
    def __init__(self, pos, size):
        self.pos = np.array(pos, dtype=np.float32)
        self.size = np.array(size, dtype=np.float32)

    def check_trigger(self, player):
        if player.z == 0:
            # Simple AABB check in world coordinates
            if (self.pos[0] <= player.pos[1] <= self.pos[0] + self.size[0] and
                self.pos[1] <= player.pos[0] <= self.pos[1] + self.size[1]):
                player.vz = player.machine.jump_force


class Mode7:
    def __init__(self, app):
        self.app = app
        self.floor_tex = pg.image.load('textures/track_4.png').convert()
        self.tex_size = self.floor_tex.get_size()
        self.floor_array = pg.surfarray.array3d(self.floor_tex)

        self.ceil_tex = pg.image.load('textures/ceil_2.png').convert()
        self.ceil_tex = pg.transform.scale(self.ceil_tex, self.tex_size)
        self.ceil_array = pg.surfarray.array3d(self.ceil_tex)

        self.screen_array = pg.surfarray.array3d(pg.Surface(WIN_RES))

        self.player = Player(PLAYER_START_POS, DOPAMINE_FALCON)
        self.alt = CAM_ALT
        self.cam_distance = CAM_DISTANCE

        # Jump Pads (World coordinates = Texture coordinates / SCALE)
        self.jump_pads = [
            JumpPad(pos=(960 / SCALE, 632 / SCALE), size=(35 / SCALE, 32 / SCALE)) 
        ]

        pg.font.init()
        try:
            self.hud_font = pg.font.SysFont('Consolas', 26)
        except Exception:
            self.hud_font = None

    def update(self, dt):
        self.player.update(dt)
        
        # Dynamic FOV: focal length decreases as speed increases
        speed_ratio = self.player.speed / self.player.machine.max_speed
        dynamic_focal_len = FOCAL_LEN - (speed_ratio * 40)

        shake = 0
        if speed_ratio > 0.8:
            shake = np.random.uniform(-1, 1) * (speed_ratio - 0.8) * 5

        # Check Jump Pad triggers
        for pad in self.jump_pads:
            pad.check_trigger(self.player)

        cam_offset = np.array([
            -self.cam_distance * np.cos(self.player.angle),
            -self.cam_distance * np.sin(self.player.angle)
        ])
        cam_pos = self.player.pos + cam_offset

        self.screen_array = self.render_frame(self.floor_array, self.ceil_array, self.screen_array,
                                              self.tex_size, self.player.angle, cam_pos, 
                                              self.alt + (self.player.z * 0.1), dynamic_focal_len + shake)

    def draw(self):
        pg.surfarray.blit_array(self.app.screen, self.screen_array)
        self.draw_vehicle()
        self.draw_hud()

    def draw_vehicle(self):
        center = pg.Vector2(HALF_WIDTH, int(HEIGHT * 0.75))
        
        # Engine Shudder based on speed ratio
        speed_ratio = self.player.speed / self.player.machine.max_speed
        shudder_x, shudder_y = 0, 0
        if speed_ratio > 0.1:
            intensity = speed_ratio * 1.5
            shudder_x = np.random.uniform(-intensity, intensity)
            shudder_y = np.random.uniform(-intensity, intensity)

        # Visual altitude offset and engine shudder
        center.y -= (self.player.z * 1500) + shudder_y
        center.x += shudder_x
        
        lean = self.player.turn_input * 0.3
        self.player.machine.draw(self.app.screen, center, lean)

    def draw_hud(self):
        if not self.hud_font:
            return
        speed_ratio = min(abs(self.player.speed) / self.player.machine.max_speed, 1.0)
        pseudo_kmh = int(speed_ratio * 500)
        speed_text = self.hud_font.render(f'Speed {pseudo_kmh}', True, (255, 255, 255))
        
        # Altitude and Pitch display
        z_text = self.hud_font.render(f'Z: {self.player.z:.2f}', True, (255, 255, 0))
        pitch_str = "LEVEL" if self.player.pitch == 0 else ("UP" if self.player.pitch == 1 else "DOWN")
        pitch_text = self.hud_font.render(f'Pitch: {pitch_str}', True, (0, 255, 255))
        
        # Debug Coordinates (Texture Space)
        pos_text = self.hud_font.render(f'TexPos: {int(self.player.pos[1]*SCALE)}, {int(self.player.pos[0]*SCALE)}', True, (255, 100, 100))
        
        info_text = self.hud_font.render('SPACE accel | S brake | Q/E shift | ARROWS steer/pitch', True, (200, 200, 200))
        
        self.app.screen.blit(speed_text, (20, 20))
        self.app.screen.blit(z_text, (20, 50))
        self.app.screen.blit(pitch_text, (20, 80))
        self.app.screen.blit(pos_text, (20, 110))
        self.app.screen.blit(info_text, (20, 140))

    @staticmethod
    @njit(fastmath=True, parallel=True)
    def render_frame(floor_array, ceil_array, screen_array, tex_size, angle, player_pos, alt, focal_len):

        sin, cos = np.sin(angle), np.cos(angle)

        for i in prange(WIDTH):
            # ceiling / background up to horizon
            for j in range(0, STD_HORIZON):
                screen_array[i][j] = ceil_array[(i - int(angle * BACKGROUND_ROTATION_SPEED)) % tex_size[0]][j % tex_size[1]]

            # floor render from horizon to bottom
            for j in range(STD_HORIZON, HEIGHT):
                x = HALF_WIDTH - i
                y = j + focal_len
                z = j - STD_HORIZON + 0.01

                rx = x * cos + y * sin
                ry = -x * sin + y * cos

                # Apply altitude to the projection
                px = (alt * rx / z + player_pos[1]) * SCALE
                py = (alt * ry / z + player_pos[0]) * SCALE

                floor_pos = int(px % tex_size[0]), int(py % tex_size[1])
                floor_col = floor_array[floor_pos]

                attenuation = min(max(7.5 * (abs(z) / HALF_HEIGHT), 0), 1)
                fog = (1 - attenuation) * FOG_DENSITY

                floor_col = (floor_col[0] * attenuation + fog,
                             floor_col[1] * attenuation + fog,
                             floor_col[2] * attenuation + fog)

                screen_array[i, j] = floor_col

        return screen_array

