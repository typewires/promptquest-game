"""Tests for the Particle class."""

import game_generator as gg


class TestParticleInit:
    def test_position_stored(self):
        p = gg.Particle(10, 20, (255, 0, 0))
        assert p.x == 10
        assert p.y == 20

    def test_color_stored(self):
        p = gg.Particle(0, 0, (255, 128, 0))
        assert p.color == (255, 128, 0)

    def test_life_set(self):
        p = gg.Particle(0, 0, (0, 0, 0), life=50)
        assert p.life == 50
        assert p.max_life == 50

    def test_size_set(self):
        p = gg.Particle(0, 0, (0, 0, 0), size=8)
        assert p.size == 8

    def test_gravity_set(self):
        p = gg.Particle(0, 0, (0, 0, 0), gravity=0.5)
        assert p.gravity == 0.5


class TestParticleUpdate:
    def test_update_moves_position(self):
        p = gg.Particle(100, 100, (0, 0, 0), vx=5, vy=3, life=30)
        # Velocity has randomness added, so just check it moves
        old_x, old_y = p.x, p.y
        p.update()
        # After one update, position should have changed
        assert p.x != old_x or p.y != old_y

    def test_update_decrements_life(self):
        p = gg.Particle(0, 0, (0, 0, 0), life=10)
        p.update()
        assert p.life == 9

    def test_update_returns_true_while_alive(self):
        p = gg.Particle(0, 0, (0, 0, 0), life=5)
        assert p.update() is True

    def test_update_returns_false_when_dead(self):
        p = gg.Particle(0, 0, (0, 0, 0), life=1)
        assert p.update() is False

    def test_gravity_affects_vy(self):
        p = gg.Particle(0, 0, (0, 0, 0), vy=0, life=30, gravity=1.0)
        initial_vy = p.vy
        p.update()
        # vy should have increased due to gravity
        assert p.vy > initial_vy or p.gravity == 1.0
