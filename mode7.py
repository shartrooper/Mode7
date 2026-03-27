import pygame as pg
import numpy as np
from settings import *
from settings_debug import DEBUG_UI, REMOVE_WALL_COLLISION
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
        self.steer_lean = 0.0  # Animation state: -2 (Right) to 2 (Left)
        self.visual_tilt = 0.0  # Snappy visual tilt state
        
        # Collision & Bounce state
        self.hit_stun = 0.0  # Timer for ignoring input after a crash
        self.on_dirt = False
        self.on_ice = False

    def update(self, dt):
        keys = pg.key.get_pressed()
        
        # Update hit stun
        if self.hit_stun > 0:
            self.hit_stun = max(0, self.hit_stun - dt)
            accelerating = False
            braking = False
        else:
            accelerating = pg.key.get_pressed()[pg.K_SPACE]
            braking = pg.key.get_pressed()[pg.K_s]
        
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
            self.speed -= drag
        else:
            # Ground speed logic: Apply acceleration and braking
            
            # Rough Terrain Logic
            dirt_speed_cap = self.machine.max_speed * 0.2  # 100 km/h threshold
            
            if braking:
                # If moving forward, slow down. If moving backward (bounce), slow down towards 0.
                if self.speed > 0:
                    self.speed = max(0, self.speed - self.machine.brake * dt)
                else:
                    self.speed = min(0, self.speed + self.machine.brake * dt)
            elif accelerating:
                self.speed += self.machine.accel * dt
            
            # ALWAYS Apply Drag (Proportional Friction)
            # Friction should always pull speed towards zero, regardless of direction
            current_friction_mult = 3.0 if self.on_ice else 5.5
            drag = self.speed * (self.machine.friction * current_friction_mult) * dt
            self.speed -= drag
            
            if self.on_dirt:
                if self.speed > dirt_speed_cap:
                    # Softer deceleration when hitting dirt at high speeds
                    self.speed = max(dirt_speed_cap, self.speed - (self.machine.friction * 4.0) * dt)
                elif self.speed > 0:
                    # Cap acceleration strictly to the dirt threshold (100)
                    self.speed = min(self.speed, dirt_speed_cap)
            
            # Rolling Resistance: If not accelerating/braking, add a small flat speed loss
            if not accelerating and not braking and abs(self.speed) > 0:
                resistance = self.machine.friction * 0.4 * dt
                if self.speed > 0:
                    self.speed = max(0, self.speed - resistance)
                else:
                    self.speed = min(0, self.speed + resistance)

        # Clip speed to machine limits (allowing negative speed for bounces)
        self.speed = np.clip(self.speed, -self.machine.max_speed * 0.5, self.machine.max_speed)

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

        # Steer Lean Animation State
        target_lean = 0.0
        if keys[pg.K_LEFT]:
            target_lean = 2.0
        elif keys[pg.K_RIGHT]:
            target_lean = -2.0
        
        anim_speed = 0.15 * dt
        if self.steer_lean < target_lean:
            self.steer_lean = min(self.steer_lean + anim_speed, target_lean)
        elif self.steer_lean > target_lean:
            self.steer_lean = max(self.steer_lean - anim_speed, target_lean)

        turn_dir = 0.0
        if keys[pg.K_LEFT]:
            turn_dir -= 1.0
        if keys[pg.K_RIGHT]:
            turn_dir += 1.0
        self.turn_input = turn_dir

        if turn_dir and self.speed:
            steer_scale = self.machine.steer_speed * (0.35 + abs(self.speed) / self.machine.max_speed)
            if self.on_ice:
                steer_scale *= 0.30  # 70% reduction in steering grip
                
            # If shifting in the same direction as turning, boost steer_speed significantly
            shift_left = keys[pg.K_q]
            shift_right = keys[pg.K_e]
            shift_input = 0
            if shift_left and not shift_right:
                shift_input = -1
            elif shift_right and not shift_left:
                shift_input = 1

            if shift_input == turn_dir:
                steer_scale *= 1.6  # 60% boost to rotation speed for sharp cornering
                
            self.angle -= turn_dir * steer_scale * dt

        cos_a = np.cos(self.angle)
        sin_a = np.sin(self.angle)

        shift_left = keys[pg.K_q]
        shift_right = keys[pg.K_e]
        shift_input = 0
        if shift_left and not shift_right:
            shift_input = -1
        elif shift_right and not shift_left:
            shift_input = 1

        shift_active = abs(self.speed) > self.machine.shift_min
        if shift_input and shift_active:
            self.shift_dir = shift_input
            increment = self.machine.shift_inc * abs(self.speed) * dt
            self.shift_force = min(self.shift_force + increment, self.machine.shift_max)
        else:
            self.shift_force = max(0.0, self.shift_force - self.machine.shift_decay * dt)
            if self.shift_force == 0 or not shift_active:
                self.shift_dir = 0

        # Visual Tilt Animation (Snappy)
        target_tilt = shift_input

        tilt_speed = 0.8 * dt
        if self.visual_tilt < target_tilt:
            self.visual_tilt = min(self.visual_tilt + tilt_speed, target_tilt)
        elif self.visual_tilt > target_tilt:
            self.visual_tilt = max(self.visual_tilt - tilt_speed, target_tilt)

        # Opposite Shift Drag Penalty (Air Brakes)
        if shift_input and turn_dir and shift_input != turn_dir:
            # Shed speed rapidly if we shift opposite the turn (Pivot maneuver)
            drag = self.speed * (self.machine.friction * 4.0) * dt
            self.speed -= drag
            
        self.pos[0] += cos_a * self.speed * dt
        self.pos[1] += sin_a * self.speed * dt

        if self.shift_force and self.shift_dir and shift_active:
            side_vec = np.array([-sin_a, cos_a], dtype=np.float32)
            lateral = side_vec * self.shift_force * self.shift_dir * dt
            
            # If shifting in the same direction as turning, reduce lateral wide slide and add slight forward zip
            if shift_input == turn_dir:
                lateral *= 0.5  # Grip the road more, slide less
                # forward zip
                if self.speed > 0:
                    self.speed += (self.machine.accel * 0.5) * dt
            
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


class Mode7:
    def __init__(self, app):
        self.app = app
        self.floor_tex = pg.image.load('textures/mess_room/circuit.png').convert()
        self.tex_size = self.floor_tex.get_size()
        self.floor_array = pg.surfarray.array3d(self.floor_tex)

        self.ceil_tex = pg.image.load('textures/mess_room/pano.png').convert()
        self.ceil_size = self.ceil_tex.get_size()
        self.ceil_array = pg.surfarray.array3d(self.ceil_tex)

        self.logic_tex = pg.image.load('textures/mess_room/logic.png').convert_alpha()
        self.logic_size = self.logic_tex.get_size()
        self.logic_rgb = pg.surfarray.array3d(self.logic_tex)
        self.logic_alpha = pg.surfarray.array_alpha(self.logic_tex)

        self.screen_array = pg.surfarray.array3d(pg.Surface(WIN_RES))

        self.player = Player(PLAYER_START_POS, DOPAMINE_FALCON)
        self.player.machine.load_assets()
        self.alt = CAM_ALT
        self.cam_distance = CAM_DISTANCE

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

        # Wall collision (ground only)
        # Use multi-probe projected sampling for "Bumper Car" bounce effect
        if self.player.z <= 0:
            center_world = self.get_projected_world_pos(dynamic_focal_len + shake)
            
            # Define probe offsets (adjust based on ship size and SCALE)
            # 0.1 world units is roughly 6.4 pixels at SCALE 64
            probe_offset = 0.08 
            angle = self.player.angle
            cos_a, sin_a = np.cos(angle), np.sin(angle)
            
            # Calculate probe positions relative to ship heading
            # Front probe
            f_probe = center_world + np.array([cos_a, sin_a]) * probe_offset
            # Left/Right lateral probes
            l_probe = center_world + np.array([-sin_a, cos_a]) * probe_offset
            r_probe = center_world + np.array([sin_a, -cos_a]) * probe_offset

            hit_wall = False
            
            # Lateral Hits: Push the player away from the wall (Sliding effect)
            if self.is_wall(l_probe):
                # Push Right
                side_vec = np.array([sin_a, -cos_a]) 
                push_force = (self.player.speed * 0.4 + 0.02) * dt
                self.player.pos += side_vec * push_force
                hit_wall = True
            elif self.is_wall(r_probe):
                # Push Left
                side_vec = np.array([-sin_a, cos_a])
                push_force = (self.player.speed * 0.4 + 0.02) * dt
                self.player.pos += side_vec * push_force
                hit_wall = True

            # Frontal Hit: Bounce back
            if self.is_wall(f_probe):
                # Reverse speed with a penalty (F-Zero style bounce)
                # We now allow negative speed in Player class
                self.player.speed = -self.player.speed * 0.5
                
                # Push the player back slightly so they aren't stuck inside the wall
                # This prevents the "vibrating against wall" effect
                push_back_vec = np.array([cos_a, sin_a]) * 0.25
                self.player.pos -= push_back_vec
                
                # Add hit stun to prevent immediate acceleration fighting the bounce
                self.player.hit_stun = 15.0  # ~1/4 second at 60fps
                hit_wall = True

            if hit_wall:
                # General speed penalty for any wall contact
                self.player.speed *= 0.90
                
        # Terrain checking (use projected center to match visuals)
        projected_center = self.get_projected_world_pos(dynamic_focal_len + shake)
        px = int(projected_center[1] * SCALE) % self.logic_size[0]
        py = int(projected_center[0] * SCALE) % self.logic_size[1]
        r, g, b = self.logic_rgb[px][py]
        alpha = self.logic_alpha[px][py]
        
        self.player.on_dirt = False
        self.player.on_ice = False
        if alpha > 0:
            if 120 <= r <= 135 and 45 <= g <= 55 and b < 10:
                self.player.on_dirt = True
            elif r < 50 and g > 200 and b > 200:
                self.player.on_ice = True
            elif r > 200 and g > 200 and b < 50:
                # Jump Pad Trigger (Yellow)
                if self.player.z == 0:
                    self.player.vz = self.player.machine.jump_force

        cam_offset = np.array([
            -self.cam_distance * np.cos(self.player.angle),
            -self.cam_distance * np.sin(self.player.angle)
        ])
        cam_pos = self.player.pos + cam_offset

        self.screen_array = self.render_frame(self.floor_array, self.ceil_array, self.screen_array,
                                              self.tex_size, self.ceil_size, self.player.angle, cam_pos, 
                                              self.alt + (self.player.z * 0.1), dynamic_focal_len + shake)

    def get_projected_world_pos(self, focal_len):
        """
        Calculates the world position that corresponds to the screen pixel 
        where the ship is visually rendered.
        """
        # Ship is rendered at HALF_WIDTH and roughly ground_y
        # From draw_vehicle: ground_y = int(HEIGHT * 0.75)
        # We need to match the render_frame logic for screen pixel (i, j)
        i = HALF_WIDTH
        j = int(HEIGHT * 0.75)
        
        # 1. Camera setup (same as render_frame)
        angle = self.player.angle
        sin, cos = np.sin(angle), np.cos(angle)
        
        # cam_pos calculation (same as update)
        cam_offset = np.array([
            -self.cam_distance * np.cos(angle),
            -self.cam_distance * np.sin(angle)
        ])
        cam_pos = self.player.pos + cam_offset
        
        # 2. Invert Projection (from render_frame lines 345-355)
        # j is the screen row, i is the screen column
        x = HALF_WIDTH - i  # This is 0 since i = HALF_WIDTH
        y = j + focal_len
        z = j - STD_HORIZON + 0.01
        
        # Rotation
        rx = x * cos + y * sin
        ry = -x * sin + y * cos
        
        # Altitude and Scale
        alt = self.alt + (self.player.z * 0.1)
        px = (alt * rx / z + cam_pos[1])
        py = (alt * ry / z + cam_pos[0])
        
        # Return world coordinates (unscaled, as is_wall applies SCALE)
        # Note: render_frame uses cam_pos[1] for px and cam_pos[0] for py
        # We return them in [y, x] order to match how is_wall uses them
        return np.array([py, px], dtype=np.float32)

    def draw(self):
        pg.surfarray.blit_array(self.app.screen, self.screen_array)
        self.draw_vehicle()
        self.draw_hud()

    def draw_vehicle(self):
        ground_y = int(HEIGHT * 0.75)
        
        # Engine Shudder based on speed ratio
        speed_ratio = self.player.speed / self.player.machine.max_speed
        shudder_x, shudder_y = 0, 0
        if speed_ratio > 0.1:
            intensity = speed_ratio * 1.5
            shudder_x = np.random.uniform(-intensity, intensity)
            shudder_y = np.random.uniform(-intensity, intensity)

        # Ground shadow (stays at ground_y)
        shadow_scale = max(0.4, 1.0 - (self.player.z * 2.0))
        shadow_width = int(145 * shadow_scale)
        shadow_height = int(65 * shadow_scale)
        shadow_surf = pg.Surface((shadow_width, shadow_height), pg.SRCALPHA)
        pg.draw.ellipse(shadow_surf, (0, 0, 0, 80), shadow_surf.get_rect())
        # Shadow follows ship's X (with shudder) but stays at ground Y
        shadow_rect = shadow_surf.get_rect(center=(HALF_WIDTH + shudder_x, ground_y + 20))
        self.app.screen.blit(shadow_surf, shadow_rect)

        # Ship center (incorporates altitude and shudder)
        ship_center = pg.Vector2(HALF_WIDTH + shudder_x, ground_y - (self.player.z * 1500) - shudder_y)
        
        # Tilt angle from snappy visual state
        # Multiplying by 0.25 (since target_tilt is 1 or -1)
        # 1.0 * 0.25 rad = 0.25 rad (approx 14 degrees)
        tilt_angle = self.player.visual_tilt * 0.25
        
        keys = pg.key.get_pressed()
        accelerating = keys[pg.K_SPACE]
        braking = keys[pg.K_s]
        
        self.player.machine.draw(self.app.screen, ship_center, self.player.steer_lean, tilt_angle, self.player.pitch, self.player.z, accelerating, braking)

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
        if DEBUG_UI:
            debug_pos = self.hud_font.render(
                f'Pos: {self.player.pos[0]:.2f}, {self.player.pos[1]:.2f}', True, (180, 180, 180)
            )
            self.app.screen.blit(debug_pos, (20, 170))
            px, py, rgb, alpha = self.sample_logic_at_player()
            logic_text = self.hud_font.render(
                f'Logic: {px},{py} RGB:{rgb[0]},{rgb[1]},{rgb[2]} A:{alpha}', True, (180, 180, 180)
            )
            self.app.screen.blit(logic_text, (20, 200))
            if self.player.on_dirt:
                state_text = self.hud_font.render('ON DIRT', True, (255, 128, 0))
                self.app.screen.blit(state_text, (20, 230))
            elif self.player.on_ice:
                state_text = self.hud_font.render('ON ICE', True, (0, 255, 255))
                self.app.screen.blit(state_text, (20, 230))

    def sample_logic_at_player(self):
        px = int(self.player.pos[1] * SCALE) % self.logic_size[0]
        py = int(self.player.pos[0] * SCALE) % self.logic_size[1]
        r, g, b = self.logic_rgb[px][py]
        a = int(self.logic_alpha[px][py])
        return px, py, (int(r), int(g), int(b)), a

    def is_wall(self, world_pos):
        if REMOVE_WALL_COLLISION:
            return False
        # Sample logic map using world position (texture space)
        px = int(world_pos[1] * SCALE) % self.logic_size[0]
        py = int(world_pos[0] * SCALE) % self.logic_size[1]
        if self.logic_alpha[px][py] == 0:
            return False
        r, g, b = self.logic_rgb[px][py]
        return r < 10 and g < 10 and b < 10

    @staticmethod
    @njit(fastmath=True, parallel=True)
    def render_frame(floor_array, ceil_array, screen_array, tex_size, ceil_size, angle, player_pos, alt, focal_len):

        sin, cos = np.sin(angle), np.cos(angle)

        for i in prange(WIDTH):
            # ceiling / background (Panoramic Scroll)
            # Map screen width to a fraction of the panorama
            # Adjust the multiplier (0.2) to control how much of the sky is visible at once
            panorama_x = (i / WIDTH * 0.2 + angle / (2 * np.pi)) % 1.0
            tex_x = int(panorama_x * ceil_size[0])
            
            for j in range(0, STD_HORIZON):
                tex_y = int((j / STD_HORIZON) * ceil_size[1])
                screen_array[i][j] = ceil_array[tex_x][tex_y]

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