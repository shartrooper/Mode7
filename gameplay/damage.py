class DamageSystem:
    """
    Modular Damage & Health System for tracking vehicle health, DA Overshield,
    speed-based morale regeneration, pit stop healing, and collision damage.
    """
    def __init__(self, max_health=100.0, max_shield=50.0):
        self.max_health = max_health
        self.max_shield = max_shield
        self.health = max_health
        self.shield = 0.0
        self.is_dead = False

    def apply_damage(self, amount, is_ablative_plow=False):
        """
        Applies damage to the vehicle.
        
        :param amount: Float damage value
        :param is_ablative_plow: Boolean flag for Snail ramming. If True and shield > 0,
                                 the overshield shatters completely, protecting main Health
                                 from taking any spillover damage.
        """
        if self.is_dead:
            return

        if self.shield > 0:
            if is_ablative_plow:
                # Ablative Plow Mechanic:
                # Any active Overshield (>0 HP) completely absorbs and shatters on Snail impact,
                # protecting main Health from taking any spillover damage.
                self.shield = 0.0
                return
            else:
                # Standard Damage (Walls, Crashes, Hard Landings):
                # Overshield absorbs up to its capacity; spillover damage affects main Health.
                if self.shield >= amount:
                    self.shield -= amount
                    return
                else:
                    remaining_damage = amount - self.shield
                    self.shield = 0.0
                    amount = remaining_damage

        self.health = max(0.0, self.health - amount)
        if self.health <= 0:
            self.is_dead = True

    def apply_heal(self, amount):
        """
        Restores main Health (e.g., Pit Stop Strips).
        """
        if self.is_dead:
            return
        self.health = min(self.max_health, self.health + amount)

    def update_speed_regen(self, speed_ratio, dt):
        """
        Handles high speed Morale & Overshield regeneration (>90% max speed).
        Top speed charges Overshield FIRST. Main health slowly regens ONLY when Overshield is FULL.
        """
        if self.is_dead:
            return

        if speed_ratio > 0.90:
            if self.shield < self.max_shield:
                self.shield = min(self.max_shield, self.shield + 4.0 * dt)
            elif self.health < self.max_health:
                self.health = min(self.max_health, self.health + 0.4 * dt)

    def reset(self):
        """
        Resets health and overshield state to initial values.
        """
        self.health = self.max_health
        self.shield = 0.0
        self.is_dead = False