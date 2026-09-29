"""宠物蛋孵化与变异系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pet.hatch import HatchSystem, Egg

class TestHatchTime:
    def test_legendary_egg_takes_longer(self):
        hs = HatchSystem()
        t_common = hs.get_hatch_time("common")
        t_legend = hs.get_hatch_time("legendary")
        assert t_legend > t_common

class TestTemperatureEffect:
    def test_optimal_temperature_increases_mutation(self):
        hs = HatchSystem()
        r_cold = hs.get_mutation_rate("epic", 5.0)
        r_optimal = hs.get_mutation_rate("epic", 35.0)
        assert r_optimal > r_cold

class TestMutationPity:
    def test_mutation_has_pity(self):
        hs = HatchSystem(seed=1)
        # 应该有保底机制
        assert hasattr(hs, "mutation_pity")
        hs.mutation_pity["e1"] = 50
        assert hs.mutation_pity["e1"] >= 50

class TestInterruptPreservesProgress:
    def test_interrupt_keeps_progress(self):
        hs = HatchSystem()
        hs.eggs["e1"] = Egg("e1", "rare", hatch_progress=50.0)
        hs.interrupt_hatch("e1")
        assert hs.eggs["e1"].hatch_progress > 0

class TestQualityStats:
    def test_legendary_pet_has_better_stats(self):
        hs = HatchSystem()
        common = hs.get_pet_stats("common")
        legendary = hs.get_pet_stats("legendary")
        assert legendary["atk"] > common["atk"]

class TestQualitySkillPool:
    def test_legendary_has_more_skills(self):
        hs = HatchSystem()
        common = hs.get_skill_pool("common")
        legendary = hs.get_skill_pool("legendary")
        assert len(legendary) > len(common)
