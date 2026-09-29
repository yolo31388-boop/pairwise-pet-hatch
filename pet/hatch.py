"""宠物蛋孵化与变异系统

修复点：
1. 孵化时间按品质与蛋类型区分，稀有度越高、蛋型越特殊，耗时越久
2. 孵化温度影响变异概率与属性倾向（温度系数 0.5x~1.5x）
3. 变异概率按品质浮动，高品质蛋基础变异率更高
4. 变异形态走概率表，并有双重保底：连续未变异保底 + N 次必出目标形态
5. 中断孵化只保留进度、重置温度，重新孵化在原进度上累计，蛋不消失
6. 品质决定孵出宠物的基础属性区间与技能池，传说蛋属性上限最高
"""
import random
from dataclasses import dataclass, field

QUALITIES = ("common", "rare", "epic", "legendary")

# 品质基础孵化时间（秒）：传说蛋最久
QUALITY_HATCH_TIME = {
    "common": 1800.0,     # 30 分钟
    "rare": 3600.0,       # 1 小时
    "epic": 7200.0,       # 2 小时
    "legendary": 14400.0, # 4 小时
}

# 蛋类型的孵化耗时倍率
EGG_TYPE_TIME_MULTIPLIER = {
    "normal": 1.0,
    "fire": 1.2,
    "ice": 1.2,
    "wind": 1.1,
    "mystic": 1.5,
}

# 品质基础变异率：高品质蛋变异率更高
BASE_MUTATION_RATE = {
    "common": 0.01,
    "rare": 0.03,
    "epic": 0.06,
    "legendary": 0.10,
}

# 连续 N 次未变异则下一次必变异
MUTATION_PITY_THRESHOLD = 50
# 连续 N 次未出目标形态则下一次必出该形态
FORM_PITY_THRESHOLD = 10

# 各品质的属性区间（含温度倾向修正前的基础区间）
QUALITY_STAT_RANGE = {
    "common": {"atk": (5, 10), "def": (5, 10)},
    "rare": {"atk": (10, 20), "def": (10, 20)},
    "epic": {"atk": (20, 35), "def": (20, 35)},
    "legendary": {"atk": (35, 60), "def": (35, 60)},
}

# 分层技能池：高品质包含低品质技能，并额外拥有专属技能
SKILL_POOLS = {
    "common": ["bite", "scratch"],
    "rare": ["bite", "scratch", "tail_whip", "harden"],
    "epic": ["bite", "scratch", "tail_whip", "harden",
             "flame_burst", "frost_armor", "gale_slash"],
    "legendary": ["bite", "scratch", "tail_whip", "harden",
                  "flame_burst", "frost_armor", "gale_slash",
                  "dragon_roar", "meteor_strike", "divine_shield"],
}

# 变异形态概率表：高品质蛋更容易出稀有形态
FORMS = ("fire", "water", "earth", "wind", "dark")
FORM_TABLE = {
    "common": [0.30, 0.30, 0.20, 0.15, 0.05],
    "rare": [0.25, 0.25, 0.20, 0.20, 0.10],
    "epic": [0.20, 0.20, 0.15, 0.25, 0.20],
    "legendary": [0.15, 0.15, 0.10, 0.25, 0.35],
}

OPTIMAL_TEMPERATURE = 35.0
TEMPERATURE_TOLERANCE = 20.0


@dataclass
class Egg:
    eid: str
    quality: str  # common/rare/epic/legendary
    egg_type: str = "normal"  # normal/fire/ice/wind/mystic
    hatch_progress: float = 0.0
    temperature: float = 25.0
    status: str = "idle"  # idle/incubating/interrupted/hatched


class HatchSystem:
    def __init__(self, seed=42):
        self.rng = random.Random(seed)
        self.eggs: dict[str, Egg] = {}
        # 保底计数：每个蛋连续未变异次数
        self.mutation_pity: dict[str, int] = {}
        # 保底计数：每个蛋连续未出目标形态次数
        self.form_pity: dict[str, int] = {}

    def _check_egg(self, eid: str) -> Egg:
        if eid not in self.eggs:
            raise KeyError(f"egg not found: {eid}")
        return self.eggs[eid]

    def register_egg(self, egg: Egg) -> None:
        self.eggs[egg.eid] = egg
        self.mutation_pity.setdefault(egg.eid, 0)
        self.form_pity.setdefault(egg.eid, 0)

    def get_hatch_time(self, quality: str, egg_type: str = "normal") -> float:
        """孵化时间随品质与类型浮动，传说蛋最久。"""
        base = QUALITY_HATCH_TIME[quality]
        multiplier = EGG_TYPE_TIME_MULTIPLIER.get(egg_type, 1.0)
        return base * multiplier

    def get_temperature_factor(self, temperature: float) -> float:
        """以 35℃ 为适宜温度，偏离越远系数越低，范围 0.5~1.5。"""
        deviation = abs(temperature - OPTIMAL_TEMPERATURE)
        factor = 1.5 - deviation / TEMPERATURE_TOLERANCE
        return max(0.5, min(1.5, factor))

    def get_mutation_rate(self, quality: str, temperature: float) -> float:
        """品质决定基础变异率，适宜温度在此基础上提升变异率。"""
        base = BASE_MUTATION_RATE[quality]
        return max(0.0, min(1.0, base * self.get_temperature_factor(temperature)))

    def get_stat_tendency(self, temperature: float) -> dict:
        """温度属性倾向：偏暖偏向攻击，偏冷偏向防御。"""
        delta = (temperature - OPTIMAL_TEMPERATURE) / TEMPERATURE_TOLERANCE
        delta = max(-1.0, min(1.0, delta))
        return {"atk_bonus": -delta, "def_bonus": delta}

    def get_pet_stats(self, quality: str, temperature: float = OPTIMAL_TEMPERATURE) -> dict:
        """品质决定基础属性区间（传说上限最高），温度决定攻防倾向。"""
        atk_low, atk_high = QUALITY_STAT_RANGE[quality]["atk"]
        def_low, def_high = QUALITY_STAT_RANGE[quality]["def"]
        tendency = self.get_stat_tendency(temperature)
        atk = self.rng.uniform(atk_low, atk_high) * (1.0 + tendency["atk_bonus"] * 0.2)
        defense = self.rng.uniform(def_low, def_high) * (1.0 + tendency["def_bonus"] * 0.2)
        return {"atk": round(max(1.0, atk), 2), "def": round(max(1.0, defense), 2)}

    def get_skill_pool(self, quality: str) -> list:
        """技能池随品质分层扩充，传说蛋技能最多。"""
        return list(SKILL_POOLS[quality])

    def get_mutation_form(self, quality: str, target_form: str | None = None,
                          eid: str | None = None) -> str:
        """按概率表抽取变异形态；指定目标形态且连续 FORM_PITY_THRESHOLD
        次未出时，保底必出目标形态。"""
        if eid is not None and target_form is not None:
            if self.form_pity.get(eid, 0) >= FORM_PITY_THRESHOLD:
                self.form_pity[eid] = 0
                return target_form

        weights = FORM_TABLE[quality]
        form = self.rng.choices(FORMS, weights=weights, k=1)[0]

        if eid is not None and target_form is not None:
            if form == target_form:
                self.form_pity[eid] = 0
            else:
                self.form_pity[eid] = self.form_pity.get(eid, 0) + 1
        return form

    def roll_mutation(self, eid: str) -> tuple[bool, str | None]:
        """完整变异判定：品质+温度决定概率，连续未变异 MUTATION_PITY_THRESHOLD
        次则保底必变异，变异形态走概率表（可保底目标形态）。"""
        egg = self._check_egg(eid)
        rate = self.get_mutation_rate(egg.quality, egg.temperature)
        if self.mutation_pity.get(eid, 0) >= MUTATION_PITY_THRESHOLD or self.rng.random() < rate:
            self.mutation_pity[eid] = 0
            form = self.get_mutation_form(egg.quality, eid=eid)
            return True, form
        self.mutation_pity[eid] = self.mutation_pity.get(eid, 0) + 1
        return False, None

    def start_hatch(self, eid: str, temperature: float | None = None) -> tuple[bool, str]:
        """开始或继续孵化：中断后的进度保留并继续累计。"""
        egg = self._check_egg(eid)
        if egg.status == "hatched":
            return False, "already hatched"
        if temperature is not None:
            egg.temperature = temperature
        egg.status = "incubating"
        return True, "hatching"

    def advance_hatch(self, eid: str, elapsed: float) -> dict:
        """推进孵化进度，温度影响推进速度；时间到则孵出宠物。"""
        egg = self._check_egg(eid)
        if egg.status not in ("incubating", "interrupted", "idle"):
            return {"hatched": False, "progress": egg.hatch_progress}
        egg.status = "incubating"
        speed = max(0.25, min(1.5, self.get_temperature_factor(egg.temperature)))
        egg.hatch_progress += max(0.0, elapsed) * speed
        required = self.get_hatch_time(egg.quality, egg.egg_type)
        if egg.hatch_progress >= required:
            return self._hatch(eid, required)
        return {"hatched": False, "progress": egg.hatch_progress, "required": required}

    def interrupt_hatch(self, eid: str) -> tuple[bool, str]:
        """中断孵化：进度保留，蛋不消失，可重新孵化继续累计。"""
        egg = self._check_egg(eid)
        if egg.status == "hatched":
            return False, "already hatched"
        egg.status = "interrupted"
        return True, "interrupted"

    def resume_hatch(self, eid: str, temperature: float | None = None) -> tuple[bool, str]:
        """从中断处继续孵化，进度不清零。"""
        egg = self._check_egg(eid)
        if egg.status == "hatched":
            return False, "already hatched"
        return self.start_hatch(eid, temperature)

    def _hatch(self, eid: str, required: float) -> dict:
        egg = self.eggs[eid]
        egg.hatch_progress = required
        egg.status = "hatched"
        mutated, form = self.roll_mutation(eid)
        return {
            "hatched": True,
            "eid": eid,
            "quality": egg.quality,
            "stats": self.get_pet_stats(egg.quality, egg.temperature),
            "skills": self.get_skill_pool(egg.quality),
            "mutated": mutated,
            "mutation_form": form,
        }
