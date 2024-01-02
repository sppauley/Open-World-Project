from __future__ import annotations
from pickle import FALSE

from app.data.database.components import ComponentType
from app.data.database.database import DB
from app.data.database.item_components import ItemTags
from app.data.database.skill_components import SkillComponent, SkillTags
from app.engine import (action, banner, combat_calcs, engine, equations,
                        image_mods, item_funcs, item_system, skill_system,
                        target_system)
from app.engine.game_state import game
from app.engine.item_components.hit_components import Shove
from app.engine.objects.unit import UnitObject
from app.utilities import utils, static_random
from app.engine.combat import playback as pb

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

    def on_upkeep_unconditional(self, actions, playback, unit):
         self.skill.data['charge'] = 0

    def end_combat(self, playback, unit, item, target, mode):
        mark_playbacks = [p for p in playback if p.nid in ('mark_miss', 'mark_hit', 'mark_crit')]
        if target and self.skill.data['charge'] == 1:
                if any(p.main_attacker is unit for p in mark_playbacks):  # Unit is overall attacker
                    action.do(action.Reset(unit))
                    unit.has_run_ai = False
                    game.ai.load_unit(unit)
        action.do(action.TriggerCharge(unit, self.skill))

class ForceShove(Shove):
    nid = 'force_shove'
    desc = "Item shoves target on hit, ignoring movement costs"
    tag = ItemTags.SPECIAL

    expose = ComponentType.Int
    value = 1
    
    def _check_shove(self, unit_to_move, anchor_pos, magnitude):
        offset_x = utils.clamp(unit_to_move.position[0] - anchor_pos[0], -1, 1)
        offset_y = utils.clamp(unit_to_move.position[1] - anchor_pos[1], -1, 1)
        new_position = (unit_to_move.position[0] + offset_x * magnitude,
                        unit_to_move.position[1] + offset_y * magnitude)

        if game.board.check_bounds(new_position) and \
                not game.board.get_unit(new_position):
            return new_position
        return False
    
    def on_hit(self, actions, playback, unit, item, target, target_pos, mode, attack_info):
        if not skill_system.ignore_forced_movement(target):
            new_position = self._check_shove(target, unit.position, self.value)
            if new_position:
                actions.append(action.ForcedMovement(target, new_position))
                playback.append(pb.ShoveHit(unit, item, target))

class WitchWarpExpressionWeakCheck(SkillComponent):
    nid = 'witch_warp_expression_weak_check'
    desc = "Allows unit to witch warp to the units that satisfy the expression. Does NOT check if target terrain is traversable."
    tag = SkillTags.MOVEMENT

    expose = ComponentType.String
    value = 'True'

    def witch_warp(self, unit) -> list:
        from app.engine import evaluate
        positions = []
        for target in game.units:
            if target.position:
                try:
                    if evaluate.evaluate(self.value, target, unit, target.position):
                        positions += [
                            pos for pos in game.target_system.get_adjacent_positions(target.position) 
                            if not game.board.get_unit(pos)
                        ]
                except Exception as e:
                    return positions
        return positions
    
class EventAfterStaggering(SkillComponent):
    nid = 'event_after_staggering'
    desc = 'calls event after user staggers an enemy'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''

    _did_stagger = False

    def on_stagger(self, playback, unit, target, item):
        self._did_stagger = True

    def end_combat(self, playback, unit: UnitObject, item, target: UnitObject, mode):
        if self._did_stagger and mode == 'attack':
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode})
        self._did_stagger = False