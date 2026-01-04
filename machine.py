import pygame as pg

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
            'neutral': [
                pg.Vector2(55.5 - 90, 54 - 50),
                pg.Vector2(51.7 - 90, 72.5 - 50),
                pg.Vector2(124 - 90, 54 - 50),
                pg.Vector2(128.5 - 90, 72.5 - 50)
            ],
            'jump': [
                pg.Vector2(55.5 - 90, 58.4 - 50),
                pg.Vector2(51.6 - 90, 77.1 - 50),
                pg.Vector2(124.1 - 90, 58 - 50),
                pg.Vector2(128 - 90, 77 - 50)
            ],
            # Left/Right to be filled as user provides coordinates
        }

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

    def draw(self, screen, center, steer_lean, tilt_angle, pitch=0, z=0, accelerating=False):
        # Select sprite based on state
        state_key = 'neutral'
        sprite = None
        
        if z > 0 and pitch == -1:
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
            
            # Draw Thruster Combustion
            if accelerating:
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
        # (Handling 'left-1', 'left-2', etc. gracefully)
        lookup_key = state_key if state_key in self.thruster_offsets else 'neutral'
        offsets = self.thruster_offsets[lookup_key]
        
        # Flicker logic
        ticks = pg.time.get_ticks()
        flicker = (ticks // 60) % 2 == 0
        core_col = (255, 255, 100) if flicker else (255, 150, 0) # Yellow vs Orange
        glow_col = (200, 50, 0) # Red glow
        
        # Ellipse dimensions from user: rx=8, ry=6
        rx, ry = 8, 6
        
        for offset in offsets:
            # Rotate offset to match ship tilt
            rotated_offset = offset.rotate_rad(tilt_angle)
            pos = center + rotated_offset
            
            # Draw outer glow (slightly larger)
            # Create a small temporary surface for the glow to apply special_flags
            glow_surf = pg.Surface(((rx + 4) * 2, (ry + 3) * 2), pg.SRCALPHA)
            pg.draw.ellipse(glow_surf, glow_col, (0, 0, (rx + 4) * 2, (ry + 3) * 2))
            screen.blit(glow_surf, (pos.x - (rx + 4), pos.y - (ry + 3)), special_flags=pg.BLEND_ADD)
            
            # Draw hot core
            core_rect = pg.Rect(0, 0, rx * 2, ry * 2)
            core_rect.center = pos
            pg.draw.ellipse(screen, core_col, core_rect)



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
