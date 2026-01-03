import pygame as pg

class Machine:
    def __init__(self, 
                 max_speed, accel, brake, friction, steer_speed,
                 shift_max, shift_inc, shift_decay, shift_min,
                 gravity, jump_force, hard_landing_penalty,
                 hull_points, canopy_points, hull_color, edge_color, canopy_color,
                 sprite_path=None, sprite_scale=1.0):
        # Physics
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
        
        # Visuals (Vector)
        self.hull_points = [pg.Vector2(p) for p in hull_points]
        self.canopy_points = [pg.Vector2(p) for p in canopy_points]
        self.hull_color = hull_color
        self.edge_color = edge_color
        self.canopy_color = canopy_color

        # Sprite logic
        self.sprite_scale = sprite_scale
        self.sprites = {}

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
            'right': [] # Placeholder for future sprites
        }

    def draw(self, screen, center, steer_lean, tilt_angle):
        # Select sprite based on steer_lean
        # steer_lean: 0 (Neutral) to 2 (Max Left)
        idx = int(abs(steer_lean))
        
        sprite = None
        if steer_lean > 0.1: # Steering Left
            if idx > 0 and idx <= len(self.sprites['left']):
                sprite = self.sprites['left'][idx-1]
            else:
                sprite = self.sprites['neutral'][0]
        # Future: handle steer_lean < -0.1 for Right
        else:
            sprite = self.sprites['neutral'][0]

        if sprite:
            # Rotate sprite based on tilt_angle (from shifting weights)
            # tilt_angle is in radians, rotozoom takes degrees
            angle_deg = -tilt_angle * 57.2958 
            rotated_sprite = pg.transform.rotozoom(sprite, angle_deg, 1.0)
            rect = rotated_sprite.get_rect(center=center)
            screen.blit(rotated_sprite, rect)
        else:
            # Fallback to polygon drawing using tilt_angle
            hull_pts = [center + p.rotate_rad(tilt_angle) for p in self.hull_points]
            canopy_pts = [center + p.rotate_rad(tilt_angle) for p in self.canopy_points]

            pg.draw.polygon(screen, self.hull_color, hull_pts)
            pg.draw.polygon(screen, self.edge_color, hull_pts, width=2)
            pg.draw.polygon(screen, self.canopy_color, canopy_pts)


# Instance with current settings
DOPAMINE_FALCON = Machine(
    max_speed=0.12,
    accel=0.0005,
    brake=0.01,
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
