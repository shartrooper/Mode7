import numpy as np
from numba import njit, prange
import random

"""
Setup
Creates a Pool of N particles in memory using NumPy array.
Each particle is an 11 number array tracking:
- x, y, z position 
- vx, vy, vz velocity
- life life
- active active
- seed seed
- prev_sx prev_sx
- prev_sy prev_sy
"""

"""
Trigger Collision
SparkSystem.spawn(pos,vel, count=5) called passing the vehicle current 3D position and velocity vector.
System scans array of N particles looking for the first 5 inactive particles.
For each dormant particle it finds, it "wakes it up":
- Position: Sets its x, y, z to exactly where the vehicle grinds floor or hit the wall.
- Velocity: It inherits the vehicle's vx, vy (so the sparks fly forward with the car), but adds a random 3D "scatter" vector. 
- This scatter acts as a "grinding cone," launching the sparks slightly outwards and upwards (vz is boosted).
- Life: Gives it a random lifespan between 0.6 and 1.0 (its "fuel").
- Active: Sets the active flag to 1.0.
- Seed: Assigns a random number used later to make the spark flicker.
"""

"""
Physics
update_particles_numba iterates through the particle pool, skips the inactive and process 5 newly active sparks.
For each spark:
- Movement: It moves the spark through 3D space by adding its velocity multiplied by dt to its x, y, z position.
- Gravity: It pulls the spark downwards by reducing its vertical velocity (vz -= gravity * dt).
- Decay: The spark burns up. Its life value drops slightly (life -= decay_rate * dt).
- The Ground Check: It checks if the spark's z position has dropped below 0 (the track surface). If it has:
    - It snaps it back to z = 0.
    - It reverses and dampens its vertical velocity (vz *= -0.3), creating a small bounce.
    - It applies friction to its horizontal velocity (vx *= 0.8), slowing it down.
- Death Check: If the spark's life hits 0, it sets the active flag back to 0.0. It goes back to sleep in the pool.
"""

"""
Projection & Rendering
render_particles_numba figures out how to draw a 3D spark onto a 2D screen.
For each active spark:
- Mode7 Inversion (Math Magic): It calculates exactly where the spark is relative to the camera's position and angle. 
- Using focal length, altitude, and horizon math, it squashes the 3D (x, y, z) coordinates into 2D pixel coordinates (i, j) on your screen. If the spark is behind the camera or off-screen, it skips drawing it to save performance.
- Color Calculation (get_color): It determines the spark's color based on its remaining life:
- High Life ($>0.8$): It alternates between bright WHITE and HOT yellow based on its seed and the frame count, creating a rapid flickering effect.
- Mid Life ($0.4 - 0.8$): It smoothly interpolates from HOT yellow to MID orange.
- Low Life ($<0.4$): As it dies out, it interpolates from MID orange to a dim COLD red.
The Motion Blur Trail: To make the spark look fast, it draws a semi-transparent line from its screen position in the previous frame (prev_sx, prev_sy) to its current screen position (i, j).
The Glowing Head: At its current pixel (i, j), it draws the bright color. It also draws pixels immediately above, below, left, and right at 40% opacity. This creates a tiny cross-shaped "bloom" that makes the spark look like it's glowing intensely.
Memory: Finally, it updates prev_sx and prev_sy with the current screen coordinates, so the trail can be drawn properly on the next frame.
"""




# Color constants (R, G, B)
COLOR_WHITE = np.array([255, 255, 255], dtype=np.float32)
COLOR_HOT = np.array([255, 255, 0], dtype=np.float32)
COLOR_MID = np.array([255, 180, 0], dtype=np.float32)
COLOR_COLD = np.array([100, 20, 0], dtype=np.float32)

@njit(fastmath=True)
def get_color(life, seed, frame_count):
    # Flicker logic
    is_hot_frame = (int(seed * 100) + frame_count) % 2 == 0
    
    # Use explicit float32 literals
    l32 = np.float32(life)
    f32_1 = np.float32(1.0)
    f32_08 = np.float32(0.8)
    f32_04 = np.float32(0.4)
    
    if l32 > f32_08:
        if is_hot_frame:
            return COLOR_WHITE
        return COLOR_HOT
    elif l32 > f32_04:
        # Interpolate HOT to MID
        t = (l32 - f32_04) / f32_04
        # Explicitly cast the result of interpolation to float32 array
        res = COLOR_HOT * t + COLOR_MID * (f32_1 - t)
        return res.astype(np.float32)
    else:
        # Interpolate MID to COLD
        t = l32 / f32_04
        res = COLOR_MID * t + COLOR_COLD * (f32_1 - t)
        return res.astype(np.float32)

@njit(fastmath=True, parallel=True)
def update_particles_numba(particles, dt, gravity):
    for i in prange(len(particles)):
        if particles[i, 7] < 0.5:
            continue
            
        # Physics update
        particles[i, 0] += particles[i, 3] * dt  # x
        particles[i, 1] += particles[i, 4] * dt  # y
        particles[i, 2] += particles[i, 5] * dt  # z
        
        # Gravity
        particles[i, 5] -= gravity * dt
        
        # Decay life
        decay_rate = 0.015  # Adjust as needed
        particles[i, 6] -= decay_rate * dt
        
        # Ground collision (simple z check)
        if particles[i, 2] < 0:
            particles[i, 2] = 0
            particles[i, 5] *= -0.3  # Bounce with penalty
            particles[i, 4] *= 0.8   # Friction
            particles[i, 3] *= 0.8
            
        if particles[i, 6] <= 0:
            particles[i, 7] = 0.0  # Deactivate

@njit(fastmath=True)
def render_particles_numba(particles, screen_array, width, height, 
                           half_width, _half_height, std_horizon, _scale,
                           angle, cam_pos, alt, focal_len, frame_count):
    sin_a, cos_a = np.sin(angle), np.cos(angle)
    
    for i in range(len(particles)):
        if particles[i, 7] < 0.5:
            continue
            
        # World to Screen Projection (Manual Mode7 Inversion)
        # This is the trickiest part: projecting world (px, py, pz) to screen (i, j)
        # Based on: px = (alt * rx / z + cam_pos[1]) * SCALE
        # We solve for i, j
        
        # Relative to camera
        rel_x = particles[i, 1] - cam_pos[1]
        rel_y = particles[i, 0] - cam_pos[0]
        
        # Un-rotate
        # rx = x * cos + y * sin
        # ry = -x * sin + y * cos
        # => x = rx * cos - ry * sin
        # => y = rx * sin + ry * cos
        
        # But here rx, ry are (alt * rel_x / z) etc.
        # This inversion is non-trivial for general (x, y, z).
        # We can approximate by finding the screen row j first.
        # z = j - STD_HORIZON
        # alt_eff = alt + particles[i, 2] * 0.1 # Altitude adjustment
        
        # Let's use a simpler projection for the sparks since they are close to ground:
        # dist_x = rel_x * cos_a + rel_y * sin_a
        # dist_y = -rel_x * sin_a + rel_y * cos_a
        
        # Mode 7 exact projection inversion:
        depth = rel_x * sin_a + rel_y * cos_a
        lateral = rel_x * cos_a - rel_y * sin_a
        if depth <= 0.1: continue # Too close or behind camera
        
        # denom = (depth / alt) - 1.0. If denom ~ 0, it's near the horizon center
        denom = (depth / alt) - 1.0
        if abs(denom) < 0.001: continue
        
        z_eff = (focal_len + std_horizon) / denom
        j = int(z_eff + std_horizon)
        if j < 0 or j >= height: continue
        
        x_eff = lateral * z_eff / alt
        i = int(half_width - x_eff)
        
        if i < 0 or i >= width: continue
        
        # Draw the particle
        color = get_color(particles[i, 6], particles[i, 8], frame_count)
        
        # Additive blend
        # Tail/Streak logic: draw a line from (prev_sx, prev_sy) to (i, j)
        prev_i = int(particles[i, 9])
        prev_j = int(particles[i, 10])
        
        # If this is the first frame, or particle just spawned, prev_i/j might be 0
        if prev_i == 0 and prev_j == 0:
            prev_i, prev_j = i, j
            
        # Simple line drawing (Bresenham-ish or just a few steps)
        # For performance, we'll just do 3-4 steps if the distance is large
        dist = max(abs(i - prev_i), abs(j - prev_j))
        steps = min(int(dist), 5) # Limit tail length for performance
        if steps > 0:
            for s in range(steps):
                t = s / steps
                ni = int(prev_i + (i - prev_i) * t)
                nj = int(prev_j + (j - prev_j) * t)
                if 0 <= ni < width and 0 <= nj < height:
                    screen_array[ni, nj, 0] = min(255, screen_array[ni, nj, 0] + color[0] * 0.5)
                    screen_array[ni, nj, 1] = min(255, screen_array[ni, nj, 1] + color[1] * 0.5)
                    screen_array[ni, nj, 2] = min(255, screen_array[ni, nj, 2] + color[2] * 0.5)

        # Update previous screen positions for next frame
        particles[i, 9] = float(i)
        particles[i, 10] = float(j)

        # Cross pattern (bloom) at the head
        if 0 <= i < width and 0 <= j < height:
            screen_array[i, j, 0] = min(255, screen_array[i, j, 0] + color[0])
            screen_array[i, j, 1] = min(255, screen_array[i, j, 1] + color[1])
            screen_array[i, j, 2] = min(255, screen_array[i, j, 2] + color[2])
            
            for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ni, nj = i + ox, j + oy
                if 0 <= ni < width and 0 <= nj < height:
                    screen_array[ni, nj, 0] = min(255, screen_array[ni, nj, 0] + color[0] * 0.4)
                    screen_array[ni, nj, 1] = min(255, screen_array[ni, nj, 1] + color[1] * 0.4)
                    screen_array[ni, nj, 2] = min(255, screen_array[ni, nj, 2] + color[2] * 0.4)

class SparkSystem:
    def __init__(self, max_particles=1000):
        self.max_particles = max_particles
        # [x, y, z, vx, vy, vz, life, active, seed, prev_sx, prev_sy]
        self.particles = np.zeros((max_particles, 11), dtype=np.float32)
        self.frame_count = 0
        
    def spawn(self, pos, vel, count=5):
        spawned = 0
        for i in range(self.max_particles):
            if self.particles[i, 7] < 0.5:
                self.particles[i, 0:3] = pos
                # Add randomness to velocity (grinding cone)
                rand_vel = np.array([
                    (random.random() - 0.5) * 0.02,
                    (random.random() - 0.5) * 0.02,
                    random.random() * 0.015
                ], dtype=np.float32)
                self.particles[i, 3:6] = vel + rand_vel
                self.particles[i, 6] = 0.6 + random.random() * 0.4 # life
                self.particles[i, 7] = 1.0 # active
                self.particles[i, 8] = random.random() # seed
                
                spawned += 1
                if spawned >= count:
                    break

    def update(self, dt):
        update_particles_numba(self.particles, dt, 0.0005) # Gravity matches Machine.gravity
        self.frame_count += 1

    def render(self, screen_array, settings_dict):
        render_particles_numba(
            self.particles, screen_array, 
            settings_dict['WIDTH'], settings_dict['HEIGHT'],
            settings_dict['HALF_WIDTH'], settings_dict['HALF_HEIGHT'],
            settings_dict['STD_HORIZON'], settings_dict['SCALE'],
            settings_dict['angle'], settings_dict['cam_pos'],
            settings_dict['alt'], settings_dict['focal_len'],
            self.frame_count
        )
