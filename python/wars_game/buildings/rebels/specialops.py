from vmath import Vector, QAngle
from core.buildings import WarsBuildingInfo, UnitBaseFactory as BaseClass
from entities import entity 

@entity('build_reb_specialops', networked=True)
class RebelsSpecialOps(BaseClass):
    # Settings
    autoconstruct = False
    buildtarget = Vector(0, -210, 32)
    buildangle = QAngle(0, 0, 0)   
    rallypoint = Vector(0, -250, 32)    
    
# Register unit
class SpecialOpsInfo(WarsBuildingInfo):
    name        = "build_reb_specialops" 
    displayname = "#BuildRebSpecialOps_Name"
    description = "#BuildRebSpecialOps_Description"
    cls_name    = "build_reb_specialops"
    image_name  = 'vgui/rebels/buildings/build_reb_specialops'
    modelname = 'models/structures/resistance/specops.mdl'
    techrequirements = ['build_reb_munitiondepot']
    costs = [('requisition', 12), ('scrap', 5)]
    health = 600
    buildtime = 60.0
    abilities   = {
        0 : 'unit_rebel_rpg',
        1 : 'unit_rebel_veteran',
        8 : 'cancel',
    } 
    sound_select = 'build_reb_specialops'
    sound_death = 'build_generic_explode1'
    explodeparticleeffect = 'building_explosion'
    explodeshake = (2, 10, 2, 512) # Amplitude, frequence, duration, radius
    sai_hint = WarsBuildingInfo.sai_hint | set(['sai_building_barracks'])