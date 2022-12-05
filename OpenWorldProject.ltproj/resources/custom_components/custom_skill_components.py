from __future__ import annotations

from app.data.database.components import ComponentType
from app.data.database.database import DB
from app.data.database.skill_components import SkillComponent, SkillTags
from app.engine import (action, banner, combat_calcs, engine, equations,
                        image_mods, item_funcs, item_system, skill_system,
                        static_random, target_system)
from app.engine.game_state import game
from app.engine.objects.unit import UnitObject
from app.utilities import utils


class DoNothing(SkillComponent):
    nid = 'do_nothing'
    desc = 'does nothing'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 1

class StaggerGaleforce(SkillComponent):
    nid = 'stagger_galeforce'
    desc = "After staggering an enemy on player phase, unit can move again."
    tag = SkillTags.MOVEMENT

    def init(self, skill):
        self.skill.data['charge'] = 0

    def on_stagger(self, playback, unit, target, item):
        self.skill.data['charge'] = 1

    def trigger_charge(self, unit, skill):
        new_value = self.skill.data['charge'] - 1
        action.do(action.SetObjData(self.skill, 'charge', new_value))

    def end_combat(self, playback, unit, item, target, mode):
        mark_playbacks = [p for p in playback if p.nid in ('mark_miss', 'mark_hit', 'mark_crit')]
        if target and self.skill.data['charge'] == 1:
                if any(p.main_attacker is unit for p in mark_playbacks):  # Unit is overall attacker
                    action.do(action.Reset(unit))
        action.do(action.TriggerCharge(unit, self.skill))