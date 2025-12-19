import pygame as pg
import numpy as np
from settings import *
from numba import njit, prange


class Player:
    def __init__(self, start_pos):
        self.pos = np.array(start_pos, dtype=np.float32)
        self.speed = 0.0
        self.angle = np.pi/2
        self.turn_input = 0.0
        self.shift_force = 0.0
        self.shift_dir = 0

    def update(self, dt):
        keys = pg.key.get_pressed()
        accelerating = keys[pg.K_SPACE]
        braking = keys[pg.K_s]

        if braking:
            if self.speed > 0:
                self.speed = max(0, self.speed - PLAYER_BRAKE * dt)
            elif self.speed < 0:
                self.speed = min(0, self.speed + PLAYER_BRAKE * dt)
        elif accelerating:
            self.speed += PLAYER_ACCEL * dt
        else:
            self._apply_friction(dt)

        self.speed = np.clip(self.speed, 0, PLAYER_MAX_SPEED)

        turn_dir = 0.0
        if keys[pg.K_LEFT]:
            turn_dir -= 1.0
        if keys[pg.K_RIGHT]:
            turn_dir += 1.0
        self.turn_input = turn_dir

        if turn_dir and self.speed:
            steer_scale = PLAYER_STEER_SPEED * (0.35 + abs(self.speed) / PLAYER_MAX_SPEED)
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

        shift_active = abs(self.speed) > SHIFT_MIN_SPEED
        if shift_input and shift_active:
            self.shift_dir = shift_input
            increment = SHIFT_INCREASE * abs(self.speed) * dt
            self.shift_force = min(self.shift_force + increment, SHIFT_MAX_FORCE)
        else:
            self.shift_force = max(0.0, self.shift_force - SHIFT_DECAY * dt)
            if self.shift_force == 0 or not shift_active:
                self.shift_dir = 0

        self.pos[0] += cos_a * self.speed * dt
        self.pos[1] += sin_a * self.speed * dt

        if self.shift_force and self.shift_dir and shift_active:
            side_vec = np.array([-sin_a, cos_a], dtype=np.float32)
            lateral = side_vec * self.shift_force * self.shift_dir * dt
            self.pos += lateral

    def _apply_friction(self, dt):
        if self.speed > 0.0:
            self.speed = max(0.0, self.speed - PLAYER_FRICTION * dt)


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

        self.player = Player(PLAYER_START_POS)
        self.alt = CAM_ALT
        self.cam_distance = CAM_DISTANCE

        pg.font.init()
        try:
            self.hud_font = pg.font.SysFont('Consolas', 26)
        except Exception:
            self.hud_font = None

    def update(self, dt):
        self.player.update(dt)
        cam_offset = np.array([
            -self.cam_distance * np.cos(self.player.angle),
            -self.cam_distance * np.sin(self.player.angle)
        ])
        cam_pos = self.player.pos + cam_offset

        self.screen_array = self.render_frame(self.floor_array, self.ceil_array, self.screen_array,
                                              self.tex_size, self.player.angle, cam_pos, self.alt)

    def draw(self):
        pg.surfarray.blit_array(self.app.screen, self.screen_array)
        self.draw_vehicle()
        self.draw_hud()

    def draw_vehicle(self):
        center = pg.Vector2(HALF_WIDTH, int(HEIGHT * 0.75))
        base_shape = [
            pg.Vector2(0, -50),
            pg.Vector2(28, 18),
            pg.Vector2(0, 30),
            pg.Vector2(-28, 18),
        ]
        canopy = [
            pg.Vector2(0, -30),
            pg.Vector2(10, 4),
            pg.Vector2(-10, 4),
        ]
        lean = self.player.turn_input * 0.3
        hull_pts = [center + point.rotate_rad(lean) for point in base_shape]
        canopy_pts = [center + point.rotate_rad(lean) for point in canopy]

        pg.draw.polygon(self.app.screen, (60, 180, 255), hull_pts)
        pg.draw.polygon(self.app.screen, (15, 35, 80), hull_pts, width=2)
        pg.draw.polygon(self.app.screen, (255, 255, 255), canopy_pts)

    def draw_hud(self):
        if not self.hud_font:
            return
        speed_ratio = min(abs(self.player.speed) / PLAYER_MAX_SPEED, 1.0)
        pseudo_kmh = int(speed_ratio * 500)
        speed_text = self.hud_font.render(f'Speed {pseudo_kmh}', True, (255, 255, 255))
        info_text = self.hud_font.render('SPACE accel | S brake | Q/E shift | arrows steer', True, (200, 200, 200))
        self.app.screen.blit(speed_text, (20, 20))
        self.app.screen.blit(info_text, (20, 50))

    @staticmethod
    @njit(fastmath=True, parallel=True)
    def render_frame(floor_array, ceil_array, screen_array, tex_size, angle, player_pos, alt):

        sin, cos = np.sin(angle), np.cos(angle)

        for i in prange(WIDTH):
            # ceiling / background up to horizon
            for j in range(0, STD_HORIZON):
                screen_array[i][j] = ceil_array[(i - int(angle * BACKGROUND_ROTATION_SPEED)) % tex_size[0]][j % tex_size[1]]

            # floor render from horizon to bottom
            for j in range(STD_HORIZON, HEIGHT):
                x = HALF_WIDTH - i
                y = j + FOCAL_LEN
                z = j - STD_HORIZON + 0.01

                rx = x * cos + y * sin
                ry = -x * sin + y * cos

                px = (rx / z + player_pos[1]) * SCALE
                py = (ry / z + player_pos[0]) * SCALE

                floor_pos = int(px % tex_size[0]), int(py % tex_size[1])
                floor_col = floor_array[floor_pos]

                attenuation = min(max(7.5 * (abs(z) / HALF_HEIGHT), 0), 1)
                fog = (1 - attenuation) * FOG_DENSITY

                floor_col = (floor_col[0] * attenuation + fog,
                             floor_col[1] * attenuation + fog,
                             floor_col[2] * attenuation + fog)

                screen_array[i, j] = floor_col

        return screen_array

