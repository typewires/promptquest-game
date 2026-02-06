"""Tests for the EffectsManager class."""

import game_generator as gg


class TestEffectsManagerInit:
    def test_starts_empty(self):
        em = gg.EffectsManager()
        assert em.particles == []
        assert em.flash == 0

    def test_allow_flash_default(self):
        em = gg.EffectsManager()
        assert em.allow_flash is True

    def test_allow_flash_disabled(self):
        em = gg.EffectsManager(allow_flash=False)
        assert em.allow_flash is False


class TestEffectsManagerSparkle:
    def test_sparkle_creates_particles(self):
        em = gg.EffectsManager()
        em.sparkle(100, 200)
        assert len(em.particles) == 20

    def test_sparkle_sets_flash_when_allowed(self):
        em = gg.EffectsManager(allow_flash=True)
        em.sparkle(100, 200)
        assert em.flash == 6

    def test_sparkle_no_flash_when_disabled(self):
        em = gg.EffectsManager(allow_flash=False)
        em.sparkle(100, 200)
        assert em.flash == 0


class TestEffectsManagerPickup:
    def test_pickup_creates_particles(self):
        em = gg.EffectsManager()
        em.pickup(50, 50)
        assert len(em.particles) == 15

    def test_pickup_sets_flash(self):
        em = gg.EffectsManager(allow_flash=True)
        em.pickup(50, 50)
        assert em.flash == 4


class TestEffectsManagerComplete:
    def test_complete_creates_particles(self):
        em = gg.EffectsManager()
        em.complete(50, 50)
        assert len(em.particles) == 25

    def test_complete_sets_flash(self):
        em = gg.EffectsManager(allow_flash=True)
        em.complete(50, 50)
        assert em.flash == 8


class TestEffectsManagerSmoke:
    def test_smoke_creates_particles(self):
        em = gg.EffectsManager()
        em.smoke(50, 50)
        assert len(em.particles) == 25

    def test_smoke_no_flash(self):
        em = gg.EffectsManager(allow_flash=True)
        em.smoke(50, 50)
        # smoke does not set flash
        assert em.flash == 0


class TestEffectsManagerUpdate:
    def test_update_removes_dead_particles(self):
        em = gg.EffectsManager()
        em.particles.append(gg.Particle(0, 0, (0, 0, 0), life=1))
        em.update()
        assert len(em.particles) == 0

    def test_update_keeps_alive_particles(self):
        em = gg.EffectsManager()
        em.particles.append(gg.Particle(0, 0, (0, 0, 0), life=100))
        em.update()
        assert len(em.particles) == 1

    def test_update_decrements_flash(self):
        em = gg.EffectsManager()
        em.flash = 5
        em.update()
        assert em.flash == 4

    def test_flash_does_not_go_negative(self):
        em = gg.EffectsManager()
        em.flash = 0
        em.update()
        assert em.flash == 0
