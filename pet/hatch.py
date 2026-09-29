"""宠物蛋孵化与变异系统"""
import random
from dataclasses import dataclass

QUALITIES = ("common", "rare", "epic", "legendary")

# 品质基础孵化时间（秒）：品质越高孵化越久
BASE_HATCH_TIME = {
    "common": 1800.0,    # 30 分钟
    "rare": 2700.0,      # 45 分钟
    "epic": 3600.0,      # 1 小时
    "legendary": 7200.0, # 2 小时
}

# 蛋类型对孵化时长的修正系数
TYPE_HATCH_FACTOR = {
    "normal": 1.0,
    "earth": 1.0,
    "fire": 1.1,
    "water": 1.1,
    "wind": 1.2,
    "dark": 1.3,
}

# 品质基础变异率：高品质蛋变异率更高
BASE_MUTATION_RATE = {
    "common": 0.01,
    "rare": 0.03,
    "epic": 0.06,
    "legendary": 0.10,
}

OPTIMAL_TEMPERATURE = 30.0  # 适宜孵化温度
TEMP_TOLERANCE = 10.0       # 适宜温度上下浮动范围
WARM_TEMPERATURE = 30.0     # 偏暖：攻击倾向
COLD_TEMPERATURE = 15.0     # 偏冷：防御倾向

# 品质基础属性
BASE_STATS = {
    "common": {"atk": 10, "def": 10},
    "rare": {"atk": 14, "def": 14},
    "epic": {"atk": 18, "def": 18},
    "legendary": {"atk": 24, "def": 24},
}

# 品质属性上限：传说蛋上限最高
STAT_CAP = {
    "common": 20,
    "rare": 30,
    "epic": 45,
    "legendary": 60,
}

# 品质技能池：高品质蛋技能池更大
SKILL_POOLS = {
    "common": ["bite", "scratch"],
    "rare": ["bite", "scratch", "tail_whip", "growl"],
    "epic": ["bite", "scratch", "tail_whip", "growl", "ember", "bubble"],
    "legendary": [
        "bite", "scratch", "tail_whip", "growl",
        "ember", "bubble", "flame_burst", "tidal_wave", "meteor",
    ],
}

# 变异形态概率表（权重之和为 1）
MUTATION_FORMS = {
    "fire": 0.30,
    "water": 0.25,
    "earth": 0.20,
    "wind": 0.15,
    "dark": 0.10,
}

PITY_THRESHOLD = 50  # 保底次数：连续 N 次未出目标形态则第 N 次必出


@dataclass
class Egg:
    eid: str
    quality: str  # common/rare/epic/legendary
    pet_type: str = "normal"  # normal/fire/water/earth/wind/dark
    hatch_progress: float = 0.0
    temperature: float = 25.0
    hatching: bool = False


class HatchSystem:
    def __init__(self, seed=42):
        self.rng = random.Random(seed)
        self.eggs: dict[str, Egg] = {}
        self.mutation_pity: dict[str, int] = {}   # eid -> 连续未出目标形态次数
        self.target_forms: dict[str, str] = {}    # eid -> 玩家期望的目标形态

    # ---- 修复1：孵化时间按品质与类型区分 ----
    def get_hatch_time(self, quality: str, pet_type: str = "normal") -> float:
        base = BASE_HATCH_TIME.get(quality, BASE_HATCH_TIME["common"])
        factor = TYPE_HATCH_FACTOR.get(pet_type, 1.0)
        return base * factor

    # ---- 修复2/3：变异率按品质浮动，适宜温度提升变异率 ----
    def get_mutation_rate(self, quality: str, temperature: float) -> float:
        rate = BASE_MUTATION_RATE.get(quality, BASE_MUTATION_RATE["common"])
        deviation = abs(temperature - OPTIMAL_TEMPERATURE)
        if deviation <= TEMP_TOLERANCE:
            # 适宜温度：最高额外 +50% 变异率
            rate *= 1.0 + (1.0 - deviation / TEMP_TOLERANCE) * 0.5
        else:
            # 过冷/过热：偏离越远变异率越低，最多降至基础值的 20%
            penalty = min(0.8, (deviation - TEMP_TOLERANCE) / 20.0 * 0.8)
            rate *= 1.0 - penalty
        return min(1.0, max(0.0, rate))

    # ---- 修复4：变异形态走概率表 + 保底 ----
    def set_target_form(self, eid: str, form: str) -> None:
        if form not in MUTATION_FORMS:
            raise ValueError(f"unknown mutation form: {form}")
        self.target_forms[eid] = form
        self.mutation_pity.setdefault(eid, 0)

    def _weighted_form(self) -> str:
        roll = self.rng.random()
        cumulative = 0.0
        for form, weight in MUTATION_FORMS.items():
            cumulative += weight
            if roll <= cumulative:
                return form
        return next(reversed(MUTATION_FORMS))

    def roll_mutation_form(self, eid: str | None = None,
                           target_form: str | None = None) -> str:
        target = target_form
        if target is None and eid is not None:
            target = self.target_forms.get(eid)

        if eid is not None:
            self.mutation_pity[eid] = self.mutation_pity.get(eid, 0) + 1
            # 保底：第 N 次必出目标形态
            if target is not None and self.mutation_pity[eid] >= PITY_THRESHOLD:
                self.mutation_pity[eid] = 0
                return target

        form = self._weighted_form()
        if eid is not None and form == target:
            self.mutation_pity[eid] = 0
        return form

    def get_mutation_form(self, quality: str = "common") -> str:
        return self._weighted_form()

    def try_mutate(self, eid: str, quality: str, temperature: float,
                   target_form: str | None = None) -> str | None:
        if self.rng.random() < self.get_mutation_rate(quality, temperature):
            return self.roll_mutation_form(eid, target_form)
        return None

    # ---- 孵化生命周期：中断保留进度，恢复后继续累计 ----
    def add_egg(self, eid: str, quality: str, pet_type: str = "normal",
                temperature: float = 25.0) -> Egg:
        egg = Egg(eid, quality, pet_type=pet_type, temperature=temperature,
                  hatching=True)
        self.eggs[eid] = egg
        return egg

    def start_hatch(self, eid: str) -> tuple[bool, str]:
        egg = self.eggs.get(eid)
        if egg is None:
            return False, "egg not found"
        egg.hatching = True
        return True, "hatching"

    def resume_hatch(self, eid: str) -> tuple[bool, str]:
        return self.start_hatch(eid)

    # ---- 修复5：中断不清零、不删蛋 ----
    def interrupt_hatch(self, eid: str) -> tuple[bool, str]:
        egg = self.eggs.get(eid)
        if egg is None:
            return False, "egg not found"
        egg.hatching = False
        return True, "interrupted"

    def advance_hatch(self, eid: str, seconds: float) -> tuple[float, bool]:
        """推进孵化进度，返回（累计进度秒数, 是否孵完）。暂停时进度不增长。"""
        egg = self.eggs.get(eid)
        if egg is None:
            return 0.0, False
        if egg.hatching:
            egg.hatch_progress += seconds
        required = self.get_hatch_time(egg.quality, egg.pet_type)
        return egg.hatch_progress, egg.hatch_progress >= required

    def hatch(self, eid: str) -> dict | None:
        """进度达标后孵出宠物；未达标返回 None。"""
        egg = self.eggs.get(eid)
        if egg is None:
            return None
        required = self.get_hatch_time(egg.quality, egg.pet_type)
        if egg.hatch_progress < required:
            return None
        mutation = self.try_mutate(eid, egg.quality, egg.temperature)
        pet = {
            "eid": eid,
            "quality": egg.quality,
            "pet_type": egg.pet_type,
            "stats": self.get_pet_stats(egg.quality, egg.temperature),
            "skills": self.get_skill_pool(egg.quality),
            "mutation": mutation,
        }
        del self.eggs[eid]
        return pet

    # ---- 修复6：品质影响基础属性/上限/技能池，温度影响属性倾向 ----
    def get_pet_stats(self, quality: str,
                      temperature: float | None = None) -> dict:
        base = BASE_STATS.get(quality, BASE_STATS["common"])
        cap = STAT_CAP.get(quality, STAT_CAP["common"])
        stats = {
            "atk": base["atk"],
            "def": base["def"],
            "max_atk": cap,
            "max_def": cap,
        }
        if temperature is not None:
            # 暖温偏攻击、冷温偏防御，且不超过品质上限
            if temperature >= WARM_TEMPERATURE:
                bonus = int((temperature - WARM_TEMPERATURE) / 5.0)
                stats["atk"] = min(cap, stats["atk"] + bonus)
            elif temperature <= COLD_TEMPERATURE:
                bonus = int((COLD_TEMPERATURE - temperature) / 5.0)
                stats["def"] = min(cap, stats["def"] + bonus)
        return stats

    def get_skill_pool(self, quality: str) -> list:
        return list(SKILL_POOLS.get(quality, SKILL_POOLS["common"]))
