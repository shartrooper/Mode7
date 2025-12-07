import pygame as pg
import numpy as np
from settings import *
from numba import njit, prange


class Player:
    def __init__(self, start_pos):
        self.pos = np.array(start_pos, dtype=np.float32)
        self.speed = 0.0
        self.angle = 0.0
        self.turn_input = 0.0

    def update(self):
        keys = pg.key.get_pressed()
        accelerating = keys[pg.K_w] or keys[pg.K_UP]
        braking = keys[pg.K_s] or keys[pg.K_DOWN]

        if accelerating:
            self.speed += PLAYER_ACCEL
        elif braking:
            self.speed -= PLAYER_BRAKE
        else:
            self._apply_friction()

        max_reverse = -PLAYER_MAX_SPEED * PLAYER_REVERSE_RATIO
        self.speed = np.clip(self.speed, max_reverse, PLAYER_MAX_SPEED)

        turn_dir = 0.0
        if keys[pg.K_LEFT]:
            turn_dir -= 1.0
        if keys[pg.K_RIGHT]:
            turn_dir += 1.0
        self.turn_input = turn_dir

        if turn_dir and self.speed:
            steer_scale = PLAYER_STEER_SPEED * (0.35 + abs(self.speed) / PLAYER_MAX_SPEED)
            self.angle -= turn_dir * steer_scale

        cos_a = np.cos(self.angle)
        sin_a = np.sin(self.angle)
        self.pos[0] += cos_a * self.speed
        self.pos[1] += sin_a * self.speed

    def _apply_friction(self):
        if self.speed > 0.0:
            self.speed = max(0.0, self.speed - PLAYER_FRICTION)
        elif self.speed < 0.0:
            self.speed = min(0.0, self.speed + PLAYER_FRICTION)


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

    def update(self):
        self.player.update()
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
        info_text = self.hud_font.render('W accel | S brake | arrows steer', True, (200, 200, 200))
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

