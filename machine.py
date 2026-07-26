import pygame as pg

from settings import HULL_POINTS_MAX


class Machine:
    def __init__(self, 
                 max_speed, accel, brake, friction, steer_speed,
                 shift_max, shift_inc, shift_decay, shift_min,
                 gravity, jump_force, hard_landing_penalty,
                 hull_points, canopy_points, hull_color, edge_color, canopy_color,
                 sprite_scale=1.0):
        # ... existing physics init ...
        self.max_speed = max_speed
        self.accel = accel
        self.brake = brake
        self.friction = friction
        self.steer_speed = steer_speed
        
        # Jumping/Landing
        self.gravity = gravity
        self.jump_force = jump_force
        self.hard_landing_penalty = hard_landing_penalty
        
        # Shift/Strafe
        self.shift_max = shift_max
        self.shift_inc = shift_inc
        self.shift_decay = shift_decay
        self.shift_min = shift_min
        
        # Visuals (Vector fallback)
        self.hull_points = [pg.Vector2(p) for p in hull_points]
        self.canopy_points = [pg.Vector2(p) for p in canopy_points]
        self.hull_color = hull_color
        self.edge_color = edge_color
        self.canopy_color = canopy_color

        # Sprite logic
        self.sprite_scale = sprite_scale
        self.sprites = {}
        
        # Thruster Glow Config (Relative to 180x100 PNG center)
        self.thruster_offsets = {
            'neutral': {
                'circles': [
                    pg.Vector2(55.5 - 90, 54 - 50),
                    pg.Vector2(51.7 - 90, 72.5 - 50),
                    pg.Vector2(124 - 90, 54 - 50),
                    pg.Vector2(128.5 - 90, 72.5 - 50)
                ],
                'triangles': [
                    [pg.Vector2(35.5 - 90, 30.5 - 50), pg.Vector2(27.6 - 90, 37 - 50), pg.Vector2(43.7 - 90, 37 - 50)],
                    [pg.Vector2(144.4 - 90, 30.5 - 50), pg.Vector2(136 - 90, 37 - 50), pg.Vector2(152.4 - 90, 37 - 50)]
                ]
            },
            'jump': {
                'circles': [
                    pg.Vector2(55.5 - 90, 58.4 - 50),
                    pg.Vector2(51.6 - 90, 77.1 - 50),
                    pg.Vector2(124.1 - 90, 58 - 50),
                    pg.Vector2(128 - 90, 77 - 50)
                ],
                'triangles': [
                    # Defaulting to neutral for jump unless specified later
                    [pg.Vector2(35.5 - 90, 30.5 - 50), pg.Vector2(27.6 - 90, 37 - 50), pg.Vector2(43.7 - 90, 37 - 50)],
                    [pg.Vector2(144.4 - 90, 30.5 - 50), pg.Vector2(136 - 90, 37 - 50), pg.Vector2(152.4 - 90, 37 - 50)]
                ]
            },
            'right-1': {
                'circles': [
                    pg.Vector2(55.5 - 90, 54 - 50),
                    pg.Vector2(51.7 - 90, 72.5 - 50),
                    pg.Vector2(124 - 90, 54 - 50),
                    pg.Vector2(128.5 - 90, 72.5 - 50)
                ],
                'triangles': [
                    [pg.Vector2(30.2 - 90, 36 - 50), pg.Vector2(36 - 90, 30 - 50), pg.Vector2(44 - 90, 36 - 50)],
                    [pg.Vector2(140.4 - 90, 30 - 50), pg.Vector2(134 - 90, 36 - 50), pg.Vector2(148 - 90, 36 - 50)]
                ]
            },
            'right-2': {
                'circles': [
                    pg.Vector2(55.5 - 90, 54 - 50),
                    pg.Vector2(51.7 - 90, 72.5 - 50),
                    pg.Vector2(124 - 90, 54 - 50),
                    pg.Vector2(128.5 - 90, 72.5 - 50)
                ],
                'triangles': [
                    [pg.Vector2(24.5 - 90, 36 - 50), pg.Vector2(36 - 90, 36 - 50), pg.Vector2(27.6 - 90, 29 - 50)],
                    [pg.Vector2(132 - 90, 29 - 50), pg.Vector2(128 - 90, 36 - 50), pg.Vector2(140 - 90, 36 - 50)]
                ]
            },
            'left-1': {
                'circles': [
                    pg.Vector2(55.5 - 90, 54 - 50),
                    pg.Vector2(51.7 - 90, 72.5 - 50),
                    pg.Vector2(124 - 90, 54 - 50),
                    pg.Vector2(128.5 - 90, 72.5 - 50)
                ],
                'triangles': [
                    [pg.Vector2(32 - 90, 36 - 50), pg.Vector2(40 - 90, 30 - 50), pg.Vector2(46 - 90, 36 - 50)],
                    [pg.Vector2(144 - 90, 30 - 50), pg.Vector2(136 - 90, 36 - 50), pg.Vector2(150 - 90, 36 - 50)]
                ]
            },
            'left-2': {
                'circles': [
                    pg.Vector2(55.5 - 90, 54 - 50),
                    pg.Vector2(51.7 - 90, 72.5 - 50),
                    pg.Vector2(124 - 90, 54 - 50),
                    pg.Vector2(128.5 - 90, 72.5 - 50)
                ],
                'triangles': [
                    [pg.Vector2(46 - 90, 30 - 50), pg.Vector2(38 - 90, 37 - 50), pg.Vector2(50 - 90, 36.5 - 50)],
                    [pg.Vector2(150 - 90, 30 - 50), pg.Vector2(142.5 - 90, 37 - 50), pg.Vector2(153 - 90, 36.5 - 50)]
                ]
            }
        }

        # Machine health
        self.max_health = HULL_POINTS_MAX
        self.max_shield = 50.0

    def load_one(self, path):
        try:
            img = pg.image.load(path).convert_alpha()
            if self.sprite_scale != 1.0:
                new_size = (int(img.get_width() * self.sprite_scale), 
                            int(img.get_height() * self.sprite_scale))
                img = pg.transform.scale(img, new_size)
            return img
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return None

    def load_assets(self):
        self.sprites = {
            'neutral': [self.load_one('textures/machines/rear-view.png')],
            'left': [
                self.load_one('textures/machines/rear-view-left-1.png'),
                self.load_one('textures/machines/rear-view-left-2.png')
            ],
            'right': [
                self.load_one('textures/machines/rear-view-right-1.png'),
                self.load_one('textures/machines/rear-view-right-2.png')
            ],
            'jump': self.load_one('textures/machines/rear-view-jump.png')
        }

    def draw(self, screen, center, steer_lean, tilt_angle, pitch=0, z=0, accelerating=False, braking=False):
        # Select sprite based on state
        state_key = 'neutral'
        sprite = None
        
        # Override for braking: force neutral sprite and no thrusters
        if braking:
            sprite = self.sprites['neutral'][0]
            state_key = 'neutral'
        elif z > 0 and pitch == -1:
            sprite = self.sprites['jump']
            state_key = 'jump'
        else:
            idx = int(abs(steer_lean))
            if steer_lean > 0.1: # Steering Left
                state_key = f'left-{idx}' if idx > 0 else 'neutral'
                if idx > 0 and idx <= len(self.sprites['left']):
                    sprite = self.sprites['left'][idx-1]
                else:
                    sprite = self.sprites['neutral'][0]
            elif steer_lean < -0.1: # Steering Right
                state_key = f'right-{idx}' if idx > 0 else 'neutral'
                if idx > 0 and idx <= len(self.sprites['right']):
                    sprite = self.sprites['right'][idx-1]
                else:
                    sprite = self.sprites['neutral'][0]
            else:
                sprite = self.sprites['neutral'][0]

        if sprite:
            angle_deg = -tilt_angle * 57.2958 
            rotated_sprite = pg.transform.rotozoom(sprite, angle_deg, 1.0)
            rect = rotated_sprite.get_rect(center=center)
            screen.blit(rotated_sprite, rect)
            
            # Draw Thruster Combustion (only if NOT braking)
            if accelerating and not braking:
                self.draw_thrusters(screen, center, tilt_angle, state_key)
        else:
            # Fallback to...
            hull_pts = [center + p.rotate_rad(tilt_angle) for p in self.hull_points]
            canopy_pts = [center + p.rotate_rad(tilt_angle) for p in self.canopy_points]
            pg.draw.polygon(screen, self.hull_color, hull_pts)
            pg.draw.polygon(screen, self.edge_color, hull_pts, width=2)
            pg.draw.polygon(screen, self.canopy_color, canopy_pts)

    def draw_thrusters(self, screen, center, tilt_angle, state_key):
        # Use neutral offsets if specific state offsets aren't defined yet
        lookup_key = state_key if state_key in self.thruster_offsets else 'neutral'
        data = self.thruster_offsets[lookup_key]
        
        # Flicker logic
        ticks = pg.time.get_ticks()
        flicker = (ticks // 60) % 2 == 0
        core_col = (255, 255, 100) if flicker else (255, 150, 0)
        glow_col = (200, 50, 0)
        
        # 1. Draw Circles (Lower Thrusters)
        rx, ry = 8, 6
        for offset in data['circles']:
            rotated_offset = offset.rotate_rad(tilt_angle)
            pos = center + rotated_offset
            
            glow_surf = pg.Surface(((rx + 2) * 2, (ry + 2) * 2), pg.SRCALPHA)
            pg.draw.ellipse(glow_surf, glow_col, (0, 0, (rx + 2) * 2, (ry + 2) * 2))
            screen.blit(glow_surf, (pos.x - (rx + 2), pos.y - (ry + 2)), special_flags=pg.BLEND_ADD)
            pg.draw.ellipse(screen, core_col, pg.Rect(pos.x - rx, pos.y - ry, rx * 2, ry * 2))

        # 2. Draw Triangles (Upper Thrusters)
        for tri_offsets in data['triangles']:
            # Calculate bounding box for the temporary surface
            transformed = [off.rotate_rad(tilt_angle) for off in tri_offsets]
            xs = [p.x for p in transformed]
            ys = [p.y for p in transformed]
            min_x, max_x = min(xs) - 5, max(xs) + 5
            min_y, max_y = min(ys) - 5, max(ys) + 5
            width, height = int(max_x - min_x), int(max_y - min_y)
            
            glow_surf = pg.Surface((width, height), pg.SRCALPHA)
            local_pts = [(p.x - min_x, p.y - min_y) for p in transformed]
            
            # Thick lines for rounded glow
            pg.draw.lines(glow_surf, glow_col, True, local_pts, width=4)
            screen.blit(glow_surf, (center.x + min_x, center.y + min_y), special_flags=pg.BLEND_ADD)
            
            # Hot core
            final_pts = [center + p for p in transformed]
            pg.draw.polygon(screen, core_col, final_pts)





# Instance with current settings
DOPAMINE_FALCON = Machine(
    max_speed=0.12,
    accel=0.0005,
    brake=0.003,
    friction=0.0008,
    steer_speed=0.015,
    shift_max=0.15,
    shift_inc=0.005,
    shift_decay=0.0025,
    shift_min=0.005,
    gravity=0.0005,
    jump_force=0.015,
    hard_landing_penalty=0.5,
    hull_points=[(0, -50), (28, 18), (0, 30), (-28, 18)],
    canopy_points=[(0, -30), (10, 4), (-10, 4)],
    hull_color=(60, 180, 255),
    edge_color=(15, 35, 80),
    canopy_color=(255, 255, 255),
    sprite_scale=1.0
)
