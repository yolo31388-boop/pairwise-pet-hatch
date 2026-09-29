"""宠物蛋孵化与变异系统 - 含6个bug"""
import random
from dataclasses import dataclass, field

@dataclass
class Egg:
    eid: str
    quality: str  # common/rare/epic/legendary
    hatch_progress: float = 0
    temperature: float = 25.0

class HatchSystem:
    def __init__(self, seed=42):
        self.rng = random.Random(seed)
        self.eggs: dict[str, Egg] = {}

    def get_hatch_time(self, quality: str) -> float:
        # bug1: 固定时间
        return 3600.0

    def get_mutation_rate(self, quality: str, temperature: float) -> float:
        # bug2: 温度不影响
        return 0.01

    def get_mutation_form(self, quality: str) -> str:
        # bug3: 随机无保底
        forms = ["fire", "water", "earth", "wind", "dark"]
        return self.rng.choice(forms)

    def interrupt_hatch(self, eid: str) -> tuple[bool, str]:
        # bug4: 中断清零
        self.eggs[eid].hatch_progress = 0
        return True, "interrupted"

    def get_pet_stats(self, quality: str) -> dict:
        # bug5: 品质不影响
        return {"atk": 10, "def": 10}

    def get_skill_pool(self, quality: str) -> list:
        # bug5: 品质不影响技能
        return ["bite", "scratch"]
